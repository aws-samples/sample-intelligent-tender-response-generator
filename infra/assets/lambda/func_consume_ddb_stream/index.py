from boto3.dynamodb.types import TypeDeserializer
from system_layer import *


_deser = TypeDeserializer()


def ddb_to_python(ddb_item) -> dict:
    return {k: _deser.deserialize(v) for k, v in ddb_item.items()}


def handler(event, context):
    for rec in event.get("Records", []):
        ddb = rec.get("dynamodb", {})
        new_img = ddb_to_python(ddb["NewImage"]) if "NewImage" in ddb else None

        if new_img is not None:
            ws_wrapper.broadcast_message(new_img)

    return {"ok": True}
