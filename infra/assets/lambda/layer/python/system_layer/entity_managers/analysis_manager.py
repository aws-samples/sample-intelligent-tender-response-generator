import os

from botocore.exceptions import ClientError
from ..constants import *
from ..utils.solution_boto3 import get_client, get_resource

TABLE_NAME = os.environ.get('TABLE_ANALYSIS')
RAW_FILES_BUCKET = os.environ.get('RAW_FILES_BUCKET')
STAGING_FILES_BUCKET = os.environ.get('STAGING_FILES_BUCKET')
CLEAN_FILES_BUCKET = os.environ.get('CLEAN_FILES_BUCKET')
OUTPUT_FILES_BUCKET = os.environ.get('OUTPUT_FILES_BUCKET')

KEY = 'Id'

ddb = get_resource('dynamodb')
s3_client = get_client('s3')
s3_resource = get_resource('s3')


def put_analysis(item):
    table = ddb.Table(TABLE_NAME)

    return table.put_item(Item=item)


def get_analysis(analysis_id):
    table = ddb.Table(TABLE_NAME)

    response = table.get_item(
        Key={KEY: analysis_id}
    )

    return response.get('Item')


def get_analysis_input_files(analysis_id):
    contents = s3_client.list_objects_v2(
        Bucket=RAW_FILES_BUCKET,
        Prefix=analysis_id
    ).get('Contents', [])

    for c in contents:
        c['Category'] = 'Undefined'

        tags = s3_client.get_object_tagging(
            Bucket=RAW_FILES_BUCKET,
            Key=c['Key']
        ).get('TagSet', [])

        for tag in tags:
            if tag['Key'] == TAG_CATEGORY:
                c['Category'] = tag['Value']

    files = [
        {
            'Name': file['Key'].split('/')[-1],
            'SizeBytes': file['Size'],
            'Category': file['Category'],
            'LastModified': file['LastModified'].isoformat()
        }

        for file in contents
    ]

    files = [f for f in files if f['Name']]

    return files


def get_analysis_response_files(analysis_id):
    responses = s3_client.list_objects_v2(
        Bucket=OUTPUT_FILES_BUCKET,
        Prefix=f'{analysis_id}/',
        Delimiter='/'
    ).get('CommonPrefixes', [])

    if not responses:
        return []

    last_response = responses[-1]['Prefix']

    contents = s3_client.list_objects_v2(
        Bucket=OUTPUT_FILES_BUCKET,
        Prefix=f'{last_response}responses'
    ).get('Contents', [])

    files = [
        {
            'Name': file['Key'].split('/')[-1],
            'SizeBytes': file['Size'],
            'Key': file['Key'],
            'LastModified': file['LastModified'].isoformat()
        }

        for file in contents
    ]

    files = [f for f in files if f['Name']]

    return files


def scan_analysis(top_n=30, next_token=None):
    table = ddb.Table(TABLE_NAME)
    scan_kwargs = {"Limit": top_n}

    if next_token:
        scan_kwargs["ExclusiveStartKey"] = next_token

    response = table.scan(**scan_kwargs)

    items = response.get("Items", [])

    new_next_token = response.get("LastEvaluatedKey")

    return {
        'Items': items,
        'NextToken': new_next_token
    }


def update_analysis(analysis_id, fields):
    table = ddb.Table(TABLE_NAME)
    expressions, names, values = [], {}, {}

    for i, (name, value) in enumerate(fields.items()):
        expressions.append(f'#n{i} = :v{i}')
        names[f'#n{i}'] = name
        values[f':v{i}'] = value

    return table.update_item(
        Key={KEY: analysis_id},
        UpdateExpression=f"SET {', '.join(expressions)}",
        ExpressionAttributeValues=values,
        ExpressionAttributeNames=names
    )


def get_analysis_failed_state(current_state):
    index = ALL_STATES.index(current_state)

    if current_state.endswith('KO'):
        return current_state
    elif current_state.endswith('OK'):
        return ALL_STATES[index - 1]
    else:
        return ALL_STATES[index + 1]


def delete_analysis_input_files(analysis_id, keys):
    # Delete from raw files bucket
    s3_client.delete_objects(
        Bucket=RAW_FILES_BUCKET,
        Delete={
            'Objects': [
                {'Key': f'{analysis_id}/{key}'}
                for key in keys
            ],
        },
    )

    # Delete from staging bucket
    bucket = s3_resource.Bucket(STAGING_FILES_BUCKET)
    objects_to_delete = []

    for key in keys:
        prefix = key.split('.')[0]
        objects_to_delete += [{"Key": obj.key} for obj in bucket.objects.filter(Prefix=prefix)]

    if objects_to_delete:
        bucket.delete_objects(Delete={"Objects": objects_to_delete})

    # Delete from clean files bucket
    bucket = s3_resource.Bucket(CLEAN_FILES_BUCKET)
    objects_to_delete = []

    for key in keys:
        prefix = key.split('/')
        prefix.insert(1, 'to_index')
        prefix = '/'.join(prefix).split('.')[0]

        objects_to_delete += [{"Key": obj.key} for obj in bucket.objects.filter(Prefix=prefix)]

    if objects_to_delete:
        bucket.delete_objects(Delete={"Objects": objects_to_delete})
