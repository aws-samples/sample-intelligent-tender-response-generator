import os
import json

from aws_durable_execution_sdk_python import (
    DurableContext,
    StepContext,
    durable_step,
)
from system_layer import *


FUNC_CHUNK_FILES = os.environ["FUNC_CHUNK_FILES"]

lambda_client = get_client("lambda")


def index(context: DurableContext, analysis):
    context.step(
        lambda _: update_analysis(analysis['Id'], {'State': STATE_CHUNKING_DOCS}),
        name='set-state-chunking-documents',
    )

    success = context.step(__chunk_documents(analysis), name='chunk-documents')

    if success:
        context.step(
            lambda _: update_analysis(analysis['Id'], {'State': STATE_CHUNKING_DOCS_OK}),
            name='set-state-chunking-documents-ok',
        )
    else:
        raise Exception('Document chunking failed.')


@durable_step
def __chunk_documents(context: StepContext, analysis):
    response = lambda_client.invoke(
        FunctionName=f'{FUNC_CHUNK_FILES}:$LATEST',
        InvocationType="RequestResponse",
        Payload=json.dumps({
            'analysisId': analysis['Id']
        }).encode("utf-8"),
    )

    return response['StatusCode'] == 200
