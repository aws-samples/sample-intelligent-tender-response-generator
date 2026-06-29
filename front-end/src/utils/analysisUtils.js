import {useEnumCategoriesDataStore} from "../data_store/enumCategoriesDataStore.ts";
import {Badge, StatusIndicator} from "@cloudscape-design/components";

export function formatDate(dateStr) {
    if (dateStr == null) return '-';

    dateStr = dateStr.replace(
        /\.(\d{3})\d+/,
        ".$1"
    );

    const date = new Date(dateStr)

    return new Intl.DateTimeFormat("en-GB", {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(date);
}

export function formatBytes(bytes) {
    if (bytes === 0) return "0 B";

    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return `${Math.round(bytes / Math.pow(k, i))} ${sizes[i]}`;
}

export function getAnalysisProgress(stateStr) {
    if (stateStr == null) return 0;

    const states = useEnumCategoriesDataStore.getState().getById('analysis_states')?.Values

    if (states == null) return 0;

    const stateId = Number(stateStr.split("_", 1)[0]);
    const stateSteps = states.length * 3;

    return (stateId / stateSteps) * 100;
}

export function getAnalysisStep(stateStr) {
    if (stateStr == null) return 0;

    const stateId = Number(stateStr.split("_", 1)[0]);
    return Math.floor((stateId - 1) / 3);
}

export const AnalysisState = ({stateStr}) => {
    const stateGroupId = getAnalysisStep(stateStr);
    const states = useEnumCategoriesDataStore.getState().getById('analysis_states')?.Values;

    if (states == null || states[stateGroupId] == null) return stateStr

    const stateGroup = states[stateGroupId]['States']

    if (stateGroup['Running']['Id'] === stateStr) {
        return (
            <StatusIndicator type="loading">{stateGroup['Running']['Name']}</StatusIndicator>
        )
    }
    else if (stateGroup['Failed']['Id'] === stateStr) {
        return (
            <StatusIndicator type="error">{stateGroup['Failed']['Name']}</StatusIndicator>
        )
    }
    else if (stateGroup['Completed']['Id'] === stateStr) {
        return (
            <StatusIndicator>{stateGroup['Completed']['Name']}</StatusIndicator>
        )
    }
}

export const KnowledgeBaseIndicator = ({analysis}) => {
    if (analysis?.StackOutputs == null) return (
        <StatusIndicator type="pending">
            Not deployed
        </StatusIndicator>
    );

    return (
        <StatusIndicator type="success">
            Active
        </StatusIndicator>
    );
}

export const FileCategory = ({category}) => {
    const types = useEnumCategoriesDataStore.getState().getById('document_categories')?.Values ?? [];

    if (category === 'Undefined') return (
        <StatusIndicator type="pending">
            Pending classification
        </StatusIndicator>
    );
    else if (category === 'error') return (
        <StatusIndicator type="error">
            Classification error
        </StatusIndicator>
    )

    for (const group of types) {
        for (const type of group['options']) {
            if (type.value === category) return (<Badge>{type.label}</Badge>)
        }
    }

    return category
}

export const ContractType = ({contractTypeId}) => {
    const types = useEnumCategoriesDataStore.getState().getById('contract_types')?.Values ?? [];

    for (const type of types) {
        if (type.value === contractTypeId) return (<Badge>{type.label}</Badge>)
    }

    return contractTypeId
}