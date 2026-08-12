import os, boto3

from botocore.config import Config

TABLE = os.environ["TABLE_NAME"]

# Identifies this solution's AWS service API calls. This function does not use the
# system layer, so the user agent the stack supplies is applied here directly.
CONFIG = Config(user_agent_extra=os.environ.get("USER_AGENT_STRING", ""))

dynamo = boto3.resource("dynamodb", config=CONFIG)
table = dynamo.Table(TABLE)


def handler(event, context):
    rc = event.get("requestContext", {})
    connection_id = rc.get("connectionId")

    try:
        table.delete_item(Key={"connectionId": connection_id})
    except Exception as e:
        print(e)

    return {"statusCode": 200}
