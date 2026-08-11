import os
import boto3
import json
import datetime

from botocore.config import Config

# Identifies this solution's AWS service API calls. This module does not use the
# system layer, so the user agent the stack supplies is applied here directly.
CONFIG = Config(user_agent_extra=os.environ.get("USER_AGENT_STRING", ""))

sqs = boto3.client("sqs", config=CONFIG)


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
