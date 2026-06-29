import {formatBytes, formatDate} from '../../utils/analysisUtils'
import {Button} from "@cloudscape-design/components";

function formatNameColumn(item, onClickListener) {
    return (
        <Button external variant={'inline-link'} onClick={() => onClickListener(item)}>{item.Name}</Button>
    )
}

export const RESPONSE_FILES_TEXTS = {loadingText: "Retrieving response files...", emptyTitle: 'No response files', emptyMessage: 'A response has not yet been generated for this tender.'}

export const RESPONSE_FILES_FILTERING_PROPERTIES = [
    {
        propertyLabel: 'Name',
        key: 'Name',
        groupValuesLabel: 'Names',
        operators: [':', '!:', '=', '!='],
    }
];

export function createColumnDefinitions(onClickListener)  {
    const rawColumns = [
        {
            id: 'Name',
            sortingField: 'Name',
            header: 'Name',
            cell: item => formatNameColumn(item, onClickListener),
            size: 'Medium',
        },
        {
            id: 'LastModified',
            sortingField: 'LastModified',
            header: 'Last modified',
            cell: item => formatDate(item.LastModified),
            size: 'Medium',
        },
        {
            id: 'Size',
            sortingField: 'Size',
            header: 'Size',
            cell: item => formatBytes(item.SizeBytes),
            size: 'Small',
        }
    ];

    return rawColumns.map(column => ({...column}));
}