import os
import json
import boto3

from system_layer import *

BUCKET = os.environ['BUCKET']
CLEAN_FILES_BUCKET = os.environ['CLEAN_FILES_BUCKET']

s3_client = boto3.client('s3')


def list_files(path):
    contents = s3_client.list_objects_v2(
        Bucket=BUCKET,
        Prefix=path,
    ).get('Contents', [])

    return [obj['Key'] for obj in contents if obj['Key'].endswith('.pdf')]


def select_response_files(files):
    filtered_files = []

    for file in files:
        tag_set = s3_client.get_object_tagging(
            Bucket=BUCKET,
            Key=file
        ).get('TagSet', [])

        for tag in tag_set:
            if tag['Key'] == TAG_CATEGORY and tag['Value'] in APPLICANT_RESPONSE_CATEGORIES:
                filtered_files.append(file)

    return filtered_files


def generate_response_uris_file(uris, prefix):
    s3_client.put_object(
        Bucket=CLEAN_FILES_BUCKET,
        Key=f"{prefix}/response_uris.json",
        Body=json.dumps({'ResponseURIS': uris}).encode("utf-8"),
        ContentType="application/json",
    )


@cors_enabler
@error_handler
def handler(event, context):
    analysis_id = event["analysisId"]
    reference_tender = event['referenceTender']

    files = []

    if reference_tender:
        files = list_files(reference_tender)
        files = select_response_files(files)
        files = [f's3://{BUCKET}/{file}' for file in files]

    generate_response_uris_file(files, analysis_id)

    return {
        'statusCode': 200,
        'body': json.dumps({'ReferenceFiles': files})
    }
