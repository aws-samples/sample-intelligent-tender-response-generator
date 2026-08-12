import os, json, boto3

from botocore.config import Config
from json import JSONDecodeError

TABLE = os.environ["TABLE_NAME"]

# Identifies this solution's AWS service API calls. This function does not use the
# system layer, so the user agent the stack supplies is applied here directly.
CONFIG = Config(user_agent_extra=os.environ.get("USER_AGENT_STRING", ""))

dynamo = boto3.resource("dynamodb", config=CONFIG)
table = dynamo.Table(TABLE)


def handler(event, context):
    rc = event.get("requestContext", {})
    domain = rc.get("domainName")
    stage = rc.get("stage")
    connection_id = rc.get("connectionId")

    try:
        body = json.loads(event["body"])
    except (KeyError, JSONDecodeError):
        body = {"raw": event["body"]}

    conn = table.get_item(Key={"connectionId": connection_id}).get("Item", {})
    username = conn.get("username", "unknown")
    user_id = conn.get("userId", "unknown")

    payload = {
        "echo": True,
        "from": {"userId": user_id, "username": username},
        "received": body,
    }

    mgmt = boto3.client("apigatewaymanagementapi", endpoint_url=f"https://{domain}/{stage}", config=CONFIG)
    mgmt.post_to_connection(ConnectionId=connection_id, Data=json.dumps(payload).encode("utf-8"))

    return {"statusCode": 200}
