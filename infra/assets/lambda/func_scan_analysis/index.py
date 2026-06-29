import json

from system_layer import *


@cors_enabler
@error_handler
def handler(event, context):
    try:
        body = json.loads(event['body'])
        next_token = body['NextToken']
    except Exception:
        next_token = None

    response = scan_analysis(next_token=next_token)

    return {
        'statusCode': 200,
        'body': json.dumps(response)
    }
