import os
import json
import boto3
import re

from system_layer import *

s3 = boto3.client("s3")
BUCKET = os.environ["DST_BUCKET"]

SUPPORTED_FILE_FORMATS = {
    '.pdf': 'application/pdf'
}


def __extract_file_format(filename):
    for format, _ in SUPPORTED_FILE_FORMATS.items():
        if filename.endswith(format):
            return format

    raise RequestError(
        f'Unsupported file format. Supported formats are {list(SUPPORTED_FILE_FORMATS.keys())}.',
        400
    )


def __generate_tagging(tags):
    if 'category' in tags and tags['category']:
        return f'{TAG_CATEGORY}={tags["category"]}&skipClassification=1'

    return ''


def __generate_presigned_url(key, content_type, tags):
    return s3.generate_presigned_url(
        'put_object',
        ExpiresIn=900,
        Params={
            "Bucket": BUCKET,
            "Key": key,
            "ContentType": content_type,
            'Tagging': tags
        }
    )


def __sanitise_key(key):
    return re.sub(r"[^A-Za-z0-9.-]", "", key)


@cors_enabler
@error_handler
def handler(event, context):
    analysis_id = event['pathParameters']['analysisId']
    body = json.loads(event['body'])

    for i in range(len(body)):
        key = body[i]['key']

        file_format = __extract_file_format(key)
        content_type = SUPPORTED_FILE_FORMATS[file_format]

        # Construct the key that points to the file in S3
        key = f'{analysis_id}/{__sanitise_key(key)}'

        # Extract upload tags
        tags = __generate_tagging(body[i]['tags'])

        # Generate the URL that authenticated users use to upload files
        url = __generate_presigned_url(key, content_type, tags)

        body[i] = {
            'File': body[i]['key'],
            'UploadUrl': url,
            'Tags': tags
        }

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body)
    }
