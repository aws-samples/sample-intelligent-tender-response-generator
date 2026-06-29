import json


def handler(event, context):
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Hello from Lambda!'}),
        "headers": {
            "Access-Control-Allow-Origin": event["headers"].get("origin", ""),
            "Access-Control-Allow-Headers": "Content-Type,Authorization,x-api-key",
            "Access-Control-Allow-Methods": "*"
        }
    }
