import boto3
import os
import json

from aws_durable_execution_sdk_python import (
    DurableContext,
    StepContext,
    durable_step,
)
from aws_durable_execution_sdk_python.config import Duration
from aws_durable_execution_sdk_python.waits import WaitForConditionConfig, WaitForConditionDecision
from system_layer import *


CLEAN_FILES_BUCKET = os.environ['CLEAN_FILES_BUCKET']
OUTPUT_FILES_BUCKET = os.environ['OUTPUT_FILES_BUCKET']
RESPONSE_GENERATOR_RUNTIME_ARN = os.environ['RESPONSE_GENERATOR_RUNTIME_ARN']

agentcore_client = boto3.client("bedrock-agentcore")


def index(context: DurableContext, analysis, kb_id):
    context.step(
        lambda _: update_analysis(analysis['Id'], {'State': STATE_GENERATING_RESPONSE}),
        name='set-state-generating-response',
    )

    task_id = context.step(__generate_response(analysis, kb_id), name='generate-response')
    response_state = __wait_for_response_generation(context, task_id, name='wait-for-response-generation')
    success = response_state['invocation']['Success'] == True

    if success:
        context.step(
            lambda _: update_analysis(analysis['Id'], {'State': STATE_GENERATING_RESPONSE_OK}),
            name='set-state-generating-response-ok',
        )
    else:
        raise Exception(f"Response generation failed with error: {response_state['invocation']['Error']}")


@durable_step
def __generate_response(context: StepContext, analysis, kb_id):
    response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=RESPONSE_GENERATOR_RUNTIME_ARN,
        payload=json.dumps({
            'tender_id': analysis['Id'],
            'knowledge_base_id': kb_id,
            'output_bucket': OUTPUT_FILES_BUCKET,
            'response_uris_s3_uri': f's3://{CLEAN_FILES_BUCKET}/{analysis["Id"]}/response_uris.json',
        })
    )

    body = json.loads(response["response"].read())

    return body["TaskId"]


def __retrieve_runtime_invocation(invocation_id):
    return {'invocation': get_runtime_invocation(invocation_id)}


def __wait_for_response_generation(context: DurableContext, invocation_id, name):
    return context.wait_for_condition(
        lambda state, _: __retrieve_runtime_invocation(invocation_id),
        name=name,
        config=WaitForConditionConfig(
            initial_state={'attempt': 0},
            wait_strategy=lambda state, attempt: (
                WaitForConditionDecision(should_continue=False, delay=Duration.from_seconds(0))
                if state["invocation"] is not None else
                WaitForConditionDecision(should_continue=True, delay=Duration.from_seconds(60))
            ),
        )
    )
