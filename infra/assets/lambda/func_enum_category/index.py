import json

from system_layer import *


@cors_enabler
def handler(event, context):
    enums = []

    for file in ['analysis_states.json', 'contract_types.json', 'document_categories.json']:
        with open(file) as fd:
            values = json.load(fd)

        enums.append({
            'Id': file.split('.')[0],
            'Values': values,
        })

    return {
        'statusCode': 200,
        'body': json.dumps(enums)
    }
