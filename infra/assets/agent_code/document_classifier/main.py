import datetime
import os
import json
import logging
import threading
import boto3

from botocore.config import Config
from json_repair import repair_json
from pdf_utils import *
from s3_utils import *
from bedrock_agentcore.runtime import BedrockAgentCoreApp


logger = logging.getLogger(__name__)


# These default values are placeholders for local development only. At runtime
# the values are provided via environment variables by the deployed stack.
HISTORIC_FILES_BUCKET = os.environ.get('HISTORIC_FILES_BUCKET', 'your-historic-files-bucket')
RAW_FILES_BUCKET = os.environ.get('RAW_FILES_BUCKET', 'your-raw-files-bucket')
STAGING_BUCKET = os.environ.get('STAGING_BUCKET', 'your-staging-bucket')
MODEL_ID = os.environ.get('MODEL_ID', 'us.anthropic.claude-3-5-sonnet-20240620-v1:0')
QUEUE_URL = os.environ.get('RUNTIME_INVOCATIONS_QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/123456789012/RuntimeInvocationsQueue')
RUNNING_LOCALLY = os.environ.get('RUNNING_LOCALLY', '1') == '1'

app = BedrockAgentCoreApp(debug=True)

# Identifies this solution's AWS service API calls, including its Bedrock traffic.
# The user agent is supplied by the deployed stack.
SOLUTION_CONFIG = Config(user_agent_extra=os.environ.get("USER_AGENT_STRING", ""))

sqs = boto3.client("sqs", config=SOLUTION_CONFIG)
s3 = boto3.client("s3", config=SOLUTION_CONFIG)
bedrock = boto3.client("bedrock-runtime", config=SOLUTION_CONFIG)


def send_to_queue(task_id, success, error=None, response=None):
    body = {
        "Id": task_id,
        "Success": success,
        'CreatedAt': datetime.datetime.now().isoformat()
    }

    if error:
        body['Error'] = error

    if response:
        body['Response'] = response

    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(body),
    )


def guess_document_category(pdf_bytes, pages_to_read=PAGES_TO_READ):
    text, page_count = extract_text_and_page_count(pdf_bytes, pages_to_read)

    system_text = (
        "You are a document classifier for public procurement tender PDFs."
        "Classify the document into exactly one category from the allowed list provided by the user."
        "You must follow the output constraints exactly."
        "Do not include any additional keys, text, markdown, explanations, or punctuation outside valid JSON."
        "If the text is insufficient or ambiguous, choose the `supporting_doc` category."
    )

    user_text = {
        "task": "classify_tender_pdf",
        "allowed_categories": LABELS,
        "keywords_map": KEYWORDS_MAP,
        "rules": [
            "Return EXACTLY one category from allowed_categories.",
            "The output MUST be valid JSON with a single top-level field named 'category'.",
            "The value of 'category' MUST match exactly one of the allowed_categories (case-sensitive).",
            "If the document is a bidder-submitted response (offer/proposal) rather than the tender requirements, classify it as technical_response or administrative_response.",
            "Use technical_response for bidder technical submissions (methodology, approach, work plan, team/CVs, technical offer, compliance matrix).",
            "Use administrative_response for bidder administrative/legal submissions (declarations, DEUC/ESPD, representation, company documents, certificates, Sobre A).",
            "If the document is a modification/correction/errata of tender requirements, use the corresponding *_modifications category.",
            "Do NOT include any additional fields or text outside the JSON object.",
            "If the text is ambiguous or incomplete, choose the `supporting_doc` category."
        ],
        "extracted_text": text
    }

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": system_text}],
        inferenceConfig={
            "temperature": 0.0,
            "maxTokens": 64
        },
        messages=[
            {"role": "user", "content": [{"text": json.dumps(user_text, ensure_ascii=False)}]},
        ],
    )

    category = json.loads(repair_json(response['output']['message']['content'][0]['text']))['category']

    if category not in LABELS:
        category = 'supporting_doc'

    return category, str(page_count)


def classify_documents(payload):
    summary = {'skipped': [], 'error': [], 'classified': [], 'staged': []}
    args = [(RAW_FILES_BUCKET, payload['prefix'], True)]

    if payload['referenceTender']:
        args.append((HISTORIC_FILES_BUCKET, payload['referenceTender'], False))

    def classify_files_in_path(bucket, prefix, copy_to_staging):
        files = list_prefix(s3, bucket, prefix)

        for f in files:
            # Do nothing, file unchanged
            if f['SkipClassification'] and f['SkipPageCount']:
                summary['skipped'].append(f['Key'])
                continue

            try:
                obj_bytes = get_object_bytes(s3, bucket, f['Key'])

                if not f['SkipClassification']:
                    category, page_count = guess_document_category(obj_bytes)
                    f['PageCount'] = page_count
                    f['Category'] = category
                elif not f['SkipPageCount']:
                    page_count = extract_page_count(obj_bytes)
                    f['PageCount'] = page_count

                # Tag the file in the source bucket
                set_object_tags(s3, bucket, f)
                summary['classified'].append(f)

                # Copy the file to the staging bucket
                if f['Category'] in LABELS_TO_STAGE and copy_to_staging:
                    copy_object_preserving_tags(s3, bucket, STAGING_BUCKET, f['Key'])
                    summary['staged'].append(f)
            except Exception as e:
                summary['error'].append({f['Key']: str(e)})
                f['Category'] = 'error'

                try:
                    set_object_tags(s3, bucket, f)
                except Exception as tag_error:
                    logger.warning("Failed to tag file %s as 'error': %s", f.get('Key'), tag_error)

    for arg_tuple in args:
        classify_files_in_path(*arg_tuple)

    return summary


@app.entrypoint
async def handler(event, context):
    task_id = app.add_async_task('process_request')

    def async_invoke_agent(payload):
        try:
            result = classify_documents(payload)
            send_to_queue(task_id, True, response=result)
        except Exception as e:
            send_to_queue(task_id, False, error=str(e))
        finally:
            app.complete_async_task(task_id)

    threading.Thread(target=async_invoke_agent, daemon=True, args=[event]).start()

    return {'TaskId': task_id}


def local_run():
    payload = {'prefix': 'borja-test', 'referenceTender': 'empty-for-testing'}
    result = classify_documents(payload)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    if RUNNING_LOCALLY:
        local_run()
    else:
        app.run()
