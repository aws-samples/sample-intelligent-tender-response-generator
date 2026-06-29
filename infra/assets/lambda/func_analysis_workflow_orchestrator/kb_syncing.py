import boto3

from aws_durable_execution_sdk_python import (
    DurableContext,
    StepContext,
    durable_step,
)
from aws_durable_execution_sdk_python.config import Duration
from aws_durable_execution_sdk_python.waits import WaitForConditionConfig, WaitForConditionDecision
from system_layer import *


bedrock_client = boto3.client('bedrock-agent')

KB_SYNC_DONE_STATUS = ('COMPLETE', 'FAILED')


def index(context: DurableContext, analysis, outputs):
    context.step(
        lambda _: update_analysis(analysis['Id'], {'State': STATE_SYNCING_KB}),
        name='set-state-syncing-kb',
    )

    ingestion_job = context.step(__sync_kb(outputs['KnowledgeBaseId'], outputs['DataSourceId']), name='sync-kb')
    ingestion_job_state = __wait_for_ingestion_job(context, ingestion_job, name='wait-for-kb-sync')
    ingestion_succeeded = ingestion_job_state['status'] == 'COMPLETE'

    if ingestion_succeeded:
        context.step(
            lambda _: update_analysis(analysis['Id'], {'State': STATE_SYNCING_KB_OK}),
            name='set-state-sync-kb-ok',
        )
    else:
        raise Exception("Knowledge Base sync failed.")


@durable_step
def __sync_kb(context: StepContext, kb_id, ds_id):
    return bedrock_client.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=ds_id,
    )['ingestionJob']


def __describe_ingestion_job(ingestion_job):
    response = bedrock_client.get_ingestion_job(
        knowledgeBaseId=ingestion_job['knowledgeBaseId'],
        dataSourceId=ingestion_job['dataSourceId'],
        ingestionJobId=ingestion_job['ingestionJobId']
    )['ingestionJob']

    return {'status': response['status']}


def __wait_for_ingestion_job(context: DurableContext, ingestion_job, name):
    return context.wait_for_condition(
        lambda state, _: __describe_ingestion_job(ingestion_job),
        name=name,
        config=WaitForConditionConfig(
            initial_state={'attempt': 0},
            wait_strategy=lambda state, attempt: (
                WaitForConditionDecision(should_continue=False, delay=Duration.from_seconds(0))
                if state["status"] in KB_SYNC_DONE_STATUS else
                WaitForConditionDecision(should_continue=True, delay=Duration.from_seconds(90))
            ),
        )
    )