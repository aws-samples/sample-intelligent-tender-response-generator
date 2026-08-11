import os, time, boto3

from botocore.config import Config

TABLE_NAME = os.environ["TABLE_NAME"]
TTL_ATTR = os.environ.get("TTL_ATTR", 'ExpiresAt')

TTL_HOURS = int(os.environ.get("TTL_HOURS", "14"))
TTL_EPOCH = 3600 * TTL_HOURS

# Identifies this solution's AWS service API calls. This function does not use the
# system layer, so the user agent the stack supplies is applied here directly.
CONFIG = Config(user_agent_extra=os.environ.get("USER_AGENT_STRING", ""))

dynamo = boto3.resource("dynamodb", config=CONFIG)
table = dynamo.Table(TABLE_NAME)


def handler(event, context):
    rc = event.get("requestContext", {})
    connection_id = rc.get("connectionId")
    domain = rc.get("domainName")
    stage = rc.get("stage")
    authorizer = rc.get("authorizer", {})
    user_id = authorizer.get("sub", "unknown")
    username = authorizer.get("username") or user_id

    item = {
        "connectionId": connection_id,
        "userId": user_id,
        "username": username,
        "connectedAt": int(time.time()),
        "callbackUrl": f"https://{domain}/{stage}",
        TTL_ATTR: int(time.time()) + TTL_EPOCH
    }

    table.put_item(Item=item)

    return {"statusCode": 200}
