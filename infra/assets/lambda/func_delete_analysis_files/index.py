import json

from system_layer import *


@cors_enabler
@error_handler
def handler(event, context):
    keys = json.loads(event['body'])
    analysis_id = event['pathParameters']['analysisId']

    delete_analysis_input_files(analysis_id, keys)

    return {'statusCode': 200, 'body': json.dumps('')}
