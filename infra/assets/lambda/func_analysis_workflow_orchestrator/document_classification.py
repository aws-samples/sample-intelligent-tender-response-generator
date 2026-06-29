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


RAW_FILES_BUCKET = os.environ['RAW_FILES_BUCKET']
STAGING_BUCKET = os.environ['STAGING_BUCKET']
DOCUMENT_CLASSIFIER_RUNTIME_ARN = os.environ['DOCUMENT_CLASSIFIER_RUNTIME_ARN']

agentcore_client = boto3.client("bedrock-agentcore")


def index(context: DurableContext, analysis):
    context.step(
        lambda _: update_analysis(analysis['Id'], {'State': STATE_CLASSIFYING_DOCS}),
        name='set-state-classifying-documents',
    )

    task_id = context.step(__classify_documents(analysis), name='classify-documents')
    classification_state = __wait_for_document_classification(context, task_id, name='wait-for-document-classification')
    success = classification_state['invocation']['Success'] == True
    staged_files = classification_state['invocation']['Response']['staged']

    if not success:
        raise Exception(f"Document classification failed with error: {classification_state['invocation']['Error']}")

    success = context.step(__validate_classified_documents(analysis), name='validate-classified-documents')

    if not success:
        raise Exception('The uploaded input files do not contain any tender requirement documents.')

    context.step(
        lambda _: update_analysis(analysis['Id'], {'State': STATE_CLASSIFYING_DOCS_OK}),
        name='set-state-classifying-documents-ok',
    )

    return len(staged_files) > 0


@durable_step
def __classify_documents(context: StepContext, analysis):
    response = agentcore_client.invoke_agent_runtime(
        agentRuntimeArn=DOCUMENT_CLASSIFIER_RUNTIME_ARN,
        payload=json.dumps({
            'prefix': analysis['Id'],
            'referenceTender': analysis['ReferenceTender']
        })
    )

    body = json.loads(response["response"].read())

    return body["TaskId"]


def __retrieve_runtime_invocation(invocation_id):
    return {'invocation': get_runtime_invocation(invocation_id)}


def __wait_for_document_classification(context: DurableContext, invocation_id, name):
    return context.wait_for_condition(
        lambda state, _: __retrieve_runtime_invocation(invocation_id),
        name=name,
        config=WaitForConditionConfig(
            initial_state={'attempt': 0},
            wait_strategy=lambda state, attempt: (
                WaitForConditionDecision(should_continue=False, delay=Duration.from_seconds(0))
                if state["invocation"] is not None else
                WaitForConditionDecision(should_continue=True, delay=Duration.from_seconds(7))
            ),
        )
    )


@durable_step
def __validate_classified_documents(context: StepContext, analysis):
    input_files = get_analysis_input_files(analysis['Id'])

    for f in input_files:
        if f['Category'] in PROJECT_CATEGORIES:
            return True

    return False
