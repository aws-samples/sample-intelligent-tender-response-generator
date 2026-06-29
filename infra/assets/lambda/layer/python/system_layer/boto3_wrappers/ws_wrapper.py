import os
import json
import boto3

from boto3.dynamodb.conditions import Key


dynamodb = boto3.resource("dynamodb")


def __post_message(connections, message):
    table = dynamodb.Table(os.environ["CONNECTIONS_TABLE"])

    for conn in connections:
        api_client = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=conn["callbackUrl"]
        )

        connection_id = conn['connectionId']

        try:
            api_client.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(message)
            )
        except api_client.exceptions.GoneException:
            table.delete_item(Key={"connectionId": connection_id})


def broadcast_message(message):
    """
    Broadcasts a message to all active WebSocket connections.
    """

    table = dynamodb.Table(os.environ["CONNECTIONS_TABLE"])
    connections = table.scan().get("Items", [])

    __post_message(connections, message)


def send_message_to_user(message, user_id):
    """
    Broadcasts a message to all active user connections.
    """

    table = dynamodb.Table(os.environ["CONNECTIONS_TABLE"])
    connections = table.query(
        IndexName='byUserId',
        KeyConditionExpression=Key("userId").eq(user_id)
    ).get("Items", [])

    __post_message(connections, message)
