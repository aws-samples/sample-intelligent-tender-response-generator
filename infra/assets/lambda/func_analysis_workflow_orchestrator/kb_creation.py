import boto3
import os

from aws_durable_execution_sdk_python import (
    DurableContext,
    StepContext,
    durable_step,
)
from aws_durable_execution_sdk_python.config import Duration
from aws_durable_execution_sdk_python.waits import WaitForConditionConfig, WaitForConditionDecision
from system_layer import *


CF_DEPLOY_ARN = os.environ['CF_DEPLOY_ARN']
CF_DONE_STATUS = ('CREATE_FAILED', 'CREATE_COMPLETE', 'ROLLBACK_FAILED', 'ROLLBACK_COMPLETE')

cf_client = boto3.client('cloudformation')


def index(context: DurableContext, analysis):
    context.step(
        lambda _: update_analysis(analysis['Id'], {'State': STATE_CREATING_KB}),
        name='set-state-creating-kb',
    )

    context.step(__deploy_kb_stack(analysis), name='deploy-kb-stack')
    stack_state = __wait_for_stack_deployment(context, analysis, name='wait-for-kb-deployment')
    creation_succeeded = stack_state['status'] == 'CREATE_COMPLETE'
    outputs = {}

    if creation_succeeded:
        outputs = stack_state['outputs']

        context.step(
            lambda _: update_analysis(analysis['Id'],
                                      {'StackOutputs': outputs, 'State': STATE_CREATING_KB_OK}),
            name='set-state-creating-kb-ok',
        )
    else:
        raise Exception(f"Knowledge Base creation failed with error: {stack_state['error']}")

    return outputs


@durable_step
def __deploy_kb_stack(context: StepContext, analysis):
    with open('kb_template.yaml') as fd:
        template = fd.read()

    cf_client.create_stack(
        StackName=analysis['KbStackName'],
        TemplateBody=template,
        Capabilities=['CAPABILITY_IAM', 'CAPABILITY_NAMED_IAM'],
        OnFailure='ROLLBACK',
        RoleARN=CF_DEPLOY_ARN,
        EnableTerminationProtection=False,
        Parameters=[
            {
                'ParameterKey': 'Suffix',
                'ParameterValue': analysis['Id'].lower()
            },
            {
                'ParameterKey': 'S3URI',
                'ParameterValue': analysis['Id']
            }
        ],
        Tags=[
            {
                'Key': 'auto-delete',
                'Value': 'no'
            }
        ]
    )


def __describe_stack(stack_name):
    response = cf_client.describe_stacks(StackName=stack_name)
    response = response.get('Stacks', [])

    outputs = {
        output['OutputKey']: output['OutputValue']
        for output in response[0].get('Outputs', [])
    }

    return {'status': response[0]['StackStatus'], 'outputs': outputs, 'error': response[0].get('StackStatusReason', 'undefined.')}


def __wait_for_stack_deployment(context: DurableContext, analysis, name):
    return context.wait_for_condition(
        lambda state, _: __describe_stack(analysis['KbStackName']),
        name=name,
        config=WaitForConditionConfig(
            initial_state={'attempt': 0},
            wait_strategy=lambda state, attempt: (
                WaitForConditionDecision(should_continue=False, delay=Duration.from_seconds(0))
                if state["status"] in CF_DONE_STATUS else
                WaitForConditionDecision(should_continue=True, delay=Duration.from_seconds(30))
            ),
        )
    )
