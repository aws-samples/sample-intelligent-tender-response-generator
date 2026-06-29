import {
    Box,
    Icon,
    Link, SpaceBetween
} from "@cloudscape-design/components";
import {formatBytes, formatDate} from "../../utils/analysisUtils";

export const TEXTS = {loadingText: "Retrieving objects...", emptyTitle: 'No objects', emptyMessage: 'This path does not contain any object.'}

function formatNameColumn(item, onClickListener) {
    const iconName = item.CanBeExpanded? 'folder' : 'file';

    if (item.CanBeExpanded) {
        return (
            <SpaceBetween direction={'horizontal'} size={'xs'}>
                <Icon name={iconName} />
                <Link href={'/submitted-responses/' + item.Name} onFollow={(event) => {onClickListener(event)}}>{item.Name}</Link>
            </SpaceBetween>
        )
    }

    return <SpaceBetween direction={'horizontal'} size={'xs'}>
        <Icon name={iconName} />
        <Box>{item.Name}</Box>
    </SpaceBetween>
}

export const FILTERING_PROPERTIES = [
    {
        propertyLabel: 'Name',
        key: 'Name',
        groupValuesLabel: 'Names',
        operators: [':', '!:', '=', '!='],
    }
];


export function createColumnDefinitions(onClickListener) {
    const rawColumns = [
        {
            id: 'Name',
            sortingField: 'Name',
            header: 'Name',
            cell: item => formatNameColumn(item, onClickListener),
            width: 300,
        },
        {
            id: 'Type',
            sortingField: 'Type',
            header: 'Type',
            cell: item => item.Type,
            width: 150
        },
        {
            id: 'LastModified',
            sortingField: 'LastModified',
            header: 'Last modified',
            cell: item => item.Type === 'Folder'? '-' : formatDate(item.LastModified),
            width: 300
        },
        {
            id: 'Size',
            sortingField: 'Size',
            header: 'Size',
            cell: item => item.Type === 'Folder'? '-' : formatBytes(item.SizeBytes),
            width: 150
        }
    ];

    return rawColumns.map(column => ({...column}));
}