import json

from runtime_invocations_manager import *


def handler(event, context):
    for record in event.get("Records", []):
        body = json.loads(record["body"])
        put_runtime_invocation(body)
