import boto3
import os
import json

from system_layer import *


s3 = boto3.client("s3")
BUCKET = os.environ["SRC_BUCKET"]


@cors_enabler
@error_handler
def handler(event, context):
    key = event["queryStringParameters"]["key"]

    # Generate the URL that users use to download files
    url = s3.generate_presigned_url(
        'get_object',
        ExpiresIn=900,
        Params={
            "Bucket": BUCKET,
            "Key": key
        }
    )

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({'DownloadUrl': url})
    }
