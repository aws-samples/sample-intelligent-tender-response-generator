import boto3
import os
import time


TABLE_NAME = os.environ.get("TABLE_RUNTIME_INVOCATIONS")
KEY = 'Id'
TTL_ATTR = 'ExpiresAt'
TTL_EPOCH = 3600 * 24 * 30 # 30 days

ddb = boto3.resource('dynamodb')


def put_runtime_invocation(item, ttl: int=TTL_EPOCH):
    table = ddb.Table(TABLE_NAME)
    item[TTL_ATTR] = int(time.time()) + ttl

    return table.put_item(Item=item)


def get_runtime_invocation(task_id: str):
    table = ddb.Table(TABLE_NAME)

    response = table.get_item(
        Key={KEY: task_id}
    )

    return response.get('Item')
