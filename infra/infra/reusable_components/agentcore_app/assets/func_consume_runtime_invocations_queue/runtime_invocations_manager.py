import boto3
import os
import time

from botocore.config import Config


TABLE_NAME = os.environ.get("TABLE_RUNTIME_INVOCATIONS")
TTL_ATTR = os.environ.get("TTL_ATTR", 'ExpiresAt')

TTL_DAYS = int(os.environ.get("TTL_DAYS", "14"))
TTL_EPOCH = 3600 * 24 * TTL_DAYS

# Identifies this solution's AWS service API calls. This function does not use the
# system layer, so the user agent the stack supplies is applied here directly.
CONFIG = Config(user_agent_extra=os.environ.get("USER_AGENT_STRING", ""))

ddb = boto3.resource('dynamodb', config=CONFIG)


def put_runtime_invocation(item, ttl: int=TTL_EPOCH):
    table = ddb.Table(TABLE_NAME)
    item[TTL_ATTR] = int(time.time()) + ttl

    return table.put_item(Item=item)
