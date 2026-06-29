import os, boto3

TABLE = os.environ["TABLE_NAME"]
dynamo = boto3.resource("dynamodb")
table = dynamo.Table(TABLE)


def handler(event, context):
    rc = event.get("requestContext", {})
    connection_id = rc.get("connectionId")

    try:
        table.delete_item(Key={"connectionId": connection_id})
    except Exception as e:
        print(e)

    return {"statusCode": 200}
