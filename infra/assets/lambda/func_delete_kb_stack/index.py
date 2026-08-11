import json

from system_layer import *

client = get_client('cloudformation')


@cors_enabler
@error_handler
def handler(event, context):
    analysis_id = event['pathParameters']['analysisId']
    analysis = get_analysis(analysis_id)

    if not analysis['RunningWorkflow'] and analysis['KbStackName'] is not None:
        client.delete_stack(
            StackName=analysis['KbStackName']
        )

        update_analysis(analysis_id, {'KbStackName': None, 'StackOutputs': None})

        return {'statusCode': 200, 'body': json.dumps('')}
    elif analysis['KbStackName'] is None:
        raise RequestError('This stack has already been deleted', 400)
    else:
        raise RequestError('Cannot delete the stack while there is an ongoing analysis', 400)
