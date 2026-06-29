import boto3
import os
import time


TABLE_NAME = os.environ.get("TABLE_RUNTIME_INVOCATIONS")
TTL_ATTR = os.environ.get("TTL_ATTR", 'ExpiresAt')

TTL_DAYS = int(os.environ.get("TTL_DAYS", "14"))
TTL_EPOCH = 3600 * 24 * TTL_DAYS

ddb = boto3.resource('dynamodb')


def put_runtime_invocation(item, ttl: int=TTL_EPOCH):
    table = ddb.Table(TABLE_NAME)
    item[TTL_ATTR] = int(time.time()) + ttl

    return table.put_item(Item=item)
