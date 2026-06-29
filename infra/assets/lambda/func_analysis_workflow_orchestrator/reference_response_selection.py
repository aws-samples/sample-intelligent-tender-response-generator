import boto3
import os
import json

from aws_durable_execution_sdk_python import (
    DurableContext,
    StepContext,
    durable_step,
)
from system_layer import *


FUNC_SELECT_REFERENCE_RESPONSE = os.environ["FUNC_SELECT_REFERENCE_RESPONSE"]

lambda_client = boto3.client("lambda")


def index(context: DurableContext, analysis):
    context.step(
        lambda _: update_analysis(analysis['Id'], {'State': STATE_SELECTING_REFERENCE_RESPONSE}),
        name='set-state-selecting-reference-response',
    )

    success = context.step(__select_reference_response(analysis), name='select-reference-response')

    if success:
        context.step(
            lambda _: update_analysis(analysis['Id'], {'State': STATE_SELECTING_REFERENCE_RESPONSE_OK}),
            name='set-state-selecting-reference-response-ok',
        )
    else:
        raise Exception("The provided reference tender does not contain any response files.")


@durable_step
def __select_reference_response(context: StepContext, analysis):
    # Standalone generation without a reference
    allow_empty = not analysis['ReferenceTender']

    response = lambda_client.invoke(
        FunctionName=f'{FUNC_SELECT_REFERENCE_RESPONSE}:$LATEST',
        InvocationType="RequestResponse",
        Payload=json.dumps({
            'referenceTender': analysis['ReferenceTender'],
            'analysisId': analysis['Id']
        }).encode("utf-8"),
    )

    if 'FunctionError' in response or response['StatusCode'] != 200:
        return False

    payload_bytes = response["Payload"].read()
    payload = json.loads(payload_bytes)
    responses = json.loads(payload["body"]).get('ReferenceFiles', [])

    return True if allow_empty else len(responses) != 0
