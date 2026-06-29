import {FileCategory, formatBytes, formatDate} from '../../utils/analysisUtils'

export const INPUT_FILES_TEXTS = {loadingText: "Retrieving input files...", emptyTitle: 'No input files', emptyMessage: 'You have not uploaded any files yet.'}

const rawColumns = [
    {
        id: 'Name',
        sortingField: 'Name',
        header: 'Name',
        cell: item => item.Name,
        size: 'Large',
    },
    {
        id: 'Category',
        sortingField: 'Category',
        header: 'Category',
        cell: item => <FileCategory category={item.Category}></FileCategory>,
        size: 'Small',
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

export const INPUT_FILES_FILTERING_PROPERTIES = [
    {
        propertyLabel: 'Name',
        key: 'Name',
        groupValuesLabel: 'Names',
        operators: [':', '!:', '=', '!='],
    },
    {
        propertyLabel: 'Category',
        key: 'Category',
        groupValuesLabel: 'Categories',
        operators: [':', '!:', '=', '!='],
    },
];

export const INPUT_FILES_COLUMN_DEFINITIONS = rawColumns.map(column => ({...column}));