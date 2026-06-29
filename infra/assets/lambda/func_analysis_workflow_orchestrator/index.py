import reference_response_selection
import document_classification
import document_chunking
import kb_creation
import kb_syncing
import response_generation

from system_layer import *

from aws_durable_execution_sdk_python import (
    DurableContext,
    durable_execution,
)


@durable_execution
def handler(event, context: DurableContext):
    """
    1: Classify files (raw files bucket -> staging bucket)
    2: Find reference response files to use based on the provided reference tender
    3: Chunk files (staging bucket -> clean files bucket)
    4: Deploy KnowledgeBase Stack (only if it does not exist yet)
    5: Sync KnowledgeBase Data Source
    6: Generate response -> output bucket
    """

    analysis = event['Analysis']
    create_kb = event['CreateKb']
    outputs = analysis.get('StackOutputs', {})

    had_file_changes = document_classification.index(context, analysis)
    reference_response_selection.index(context, analysis)

    # Only chunk the files if needed
    if had_file_changes:
        document_chunking.index(context, analysis)

    # Only deploy the KB stack if needed
    if create_kb:
        outputs = kb_creation.index(context, analysis)

    # Only rerun a sync if needed
    if create_kb or had_file_changes:
        kb_syncing.index(context, analysis, outputs)

    response_generation.index(context, analysis, outputs['KnowledgeBaseId'])

    update_analysis(analysis['Id'], {'RunningWorkflow': False})

    return {'statusCode': 200}
