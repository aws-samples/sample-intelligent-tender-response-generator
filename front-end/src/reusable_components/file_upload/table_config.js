import {formatBytes} from '../../utils/analysisUtils'
import {StatusIndicator} from "@cloudscape-design/components";

const FileStatus = ({file}) => {
    if (file.completed != null && file.completed === true) {
        return (
            <StatusIndicator>
                Completed
            </StatusIndicator>
        );
    }
    else if (file.errorText != null) {
        return (
            <StatusIndicator type="error">
                {file.errorText}
            </StatusIndicator>
        );
    }
    else if (file.loading != null && file.loading === true) {
        return (
            <StatusIndicator type="loading">
                In progress
            </StatusIndicator>
        );
    }

    return (
        <StatusIndicator type="pending">
            Not started
        </StatusIndicator>
    );
}

const rawColumns = [
    {
        id: 'name',
        header: 'File name',
        cell: item => item.file.name,
        width: 300,
    },
    {
        id: 'size',
        header: 'File size',
        cell: item => formatBytes(item.file.size),
        width: 150,
    },
    {
        id: 'status',
        header: 'Upload status',
        cell: item => <FileStatus file={item}></FileStatus>,
        width: 300,
    }
];

export const COLUMN_DEFINITIONS = rawColumns.map(column => ({...column}));