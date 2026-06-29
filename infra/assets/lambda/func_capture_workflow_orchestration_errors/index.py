import boto3
import json

from system_layer import *

lambda_client = boto3.client('lambda')


def handler(event, context):
    execution_arn = event['detail']['durableExecutionArn']

    response = lambda_client.get_durable_execution(
        DurableExecutionArn=execution_arn
    )

    error_message = response['Error']['ErrorMessage']
    input_payload = json.loads(response['InputPayload'])
    analysis_id = input_payload['Analysis']['Id']

    analysis = get_analysis(analysis_id)
    failed_state = get_analysis_failed_state(analysis['State'])

    new_fields = {
        'State': failed_state,
        'RunningWorkflow': False,
        'Error': error_message,
    }

    # The orchestration failed before deploying the KB stack.
    # Reset the field so that it is deployed again on the next invocation
    if int(failed_state.split('_')[0]) < int(STATE_CREATING_KB_OK.split('_')[0]):
        new_fields['KbStackName'] = None

    update_analysis(
        analysis_id,
        new_fields
    )

    return {'statusCode': 200}
