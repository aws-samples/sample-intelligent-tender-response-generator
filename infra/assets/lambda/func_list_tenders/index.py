import os
import json

from system_layer import *

BUCKET = os.environ['BUCKET']
MAX_LEVELS = int(os.environ.get('MAX_LEVELS', 3))

s3_client = get_client('s3')


def list_directory(prefix, max_keys=1000):
    if prefix and not prefix.endswith('/'):
        prefix += '/'

    params = {
        'Bucket': BUCKET,
        'MaxKeys': max_keys,
        'Delimiter': '/',
        'Prefix': prefix
    }

    response = s3_client.list_objects_v2(**params)

    folders = response.get('CommonPrefixes', [])
    files = response.get('Contents', [])

    # Exclude the "directory marker" itself if present
    return [c for c in folders if c['Prefix'] != prefix], [f for f in files if f['Size'] != 0]


@cors_enabler
@error_handler
def handler(event, context):
    parameters = event.get('queryStringParameters') or {}
    path = parameters.get('path', '').strip("/")

    folders, files = list_directory(path)

    items = [
        {
            'Name': obj['Prefix'].split('/')[-2],
            'CanBeSelected': True,
            'CanBeExpanded': True,
            'Type': 'Folder',
            'LastModified': '',
            'SizeBytes': ''
        }
        for obj in folders
    ]

    items += [
        {
            'Name': obj['Key'].split('/')[-1],
            'CanBeSelected': False,
            'CanBeExpanded': False,
            'Type': obj['Key'].split('/')[-1].split('.')[-1],
            'LastModified': obj['LastModified'].isoformat(),
            'SizeBytes': obj['Size']
        }
        for obj in files
    ]

    return {
        'statusCode': 200,
        'body': json.dumps({
            'Count': len(items),
            'Items': items
        })
    }
