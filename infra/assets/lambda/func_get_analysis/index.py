import json

from system_layer import *


@cors_enabler
@error_handler
def handler(event, context):
    analysis_id = event['pathParameters']['analysisId']
    path = event.get('path', '') or ''

    if 'input-files' in path:
        response = {'Files': get_analysis_input_files(analysis_id)}
    elif 'response-files' in path:
        response = {'Files': get_analysis_response_files(analysis_id)}
    else:
        response = {'Item': get_analysis(analysis_id)}

        if response['Item'] is None:
            raise RequestError.not_found()

    return {
        'statusCode': 200,
        'body': json.dumps(response)
    }
