import os
import json
import boto3
import datetime

from system_layer import *


ORCHESTRATOR_FUNC = os.environ["ORCHESTRATOR_FUNC"]

lambda_client = boto3.client("lambda")


def create_analysis(analysis_id, kb_stack_name, reference_tender, contract_type_id):
    analysis = {
        'Id': analysis_id,
        'KbStackName': kb_stack_name,
        'State': STATE_CLASSIFYING_DOCS,
        'RunningWorkflow': True,
        'ReferenceTender': reference_tender,
        'ContractTypeId': contract_type_id,
        'Error': None,
        'LastExecutionDate': None,
        'CreatedAt': datetime.datetime.now().isoformat()
    }

    put_analysis(analysis)

    return analysis


def set_analysis_running(analysis, analysis_id, kb_stack_name, reference_tender, contract_type_id):
    fields = {
        'RunningWorkflow': True,
        'KbStackName': kb_stack_name,
        'State': STATE_CLASSIFYING_DOCS,
        'ReferenceTender': reference_tender,
        'ContractTypeId': contract_type_id,
        'Error': None,
        'LastExecutionDate': datetime.datetime.now().isoformat()
    }

    update_analysis(analysis_id, fields)
    analysis.update(fields)

    return analysis


def start_workflow_orchestration(analysis, create_kb):
    lambda_client.invoke(
        FunctionName=f'{ORCHESTRATOR_FUNC}:$LATEST',
        InvocationType="Event",
        Payload=json.dumps({
            'Analysis': analysis,
            'CreateKb': create_kb
        }).encode("utf-8"),
    )


@cors_enabler
@error_handler
def handler(event, context):
    analysis_id = event['pathParameters']['analysisId']
    reference_tender = (event.get('queryStringParameters', {}) or {}).get('referenceTender', '')
    contract_type_id = (event.get('queryStringParameters', {}) or {}).get('contractTypeId', 'public_works')

    kb_stack_name = f'kb-{analysis_id}'

    analysis = get_analysis(analysis_id)

    create_kb = analysis is None or analysis['KbStackName'] is None
    run_workflow = analysis is None or not analysis['RunningWorkflow']

    # Put the new analysis to DynamoDB
    if analysis is None:
        analysis = create_analysis(analysis_id, kb_stack_name, reference_tender, contract_type_id)

    # Invoke the workflow orchestration Lambda if needed
    if run_workflow:
        analysis = set_analysis_running(analysis, analysis_id, kb_stack_name, reference_tender, contract_type_id)
        start_workflow_orchestration(analysis, create_kb)

        return {
            'statusCode': 200,
            'body': json.dumps(analysis)
        }

    raise RequestError('This analysis is already being processed. Please, wait until it finishes.', 400)
