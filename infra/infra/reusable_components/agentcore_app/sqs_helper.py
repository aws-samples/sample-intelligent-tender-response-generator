import os
import boto3
import json
import datetime

sqs = boto3.client("sqs")


def send_to_queue(task_id: int, success: bool, error=None, response=None):
    body = {
        'Id': task_id,
        "Success": success,
        'CreatedAt': datetime.datetime.now().isoformat()
    }

    if error:
        body['Error'] = error

    if response:
        body['Response'] = response

    sqs.send_message(
        QueueUrl=os.environ['RUNTIME_INVOCATIONS_QUEUE_URL'],
        MessageBody=json.dumps(body)
    )
