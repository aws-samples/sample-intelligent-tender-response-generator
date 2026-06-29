import {AnalysisState, ContractType, formatDate} from "../../utils/analysisUtils";
import {CustomLink} from '../../reusable_components/link/link'

export const TEXTS = {loadingText: "Retrieving generated tender responses...", emptyTitle: 'No generated tender responses', emptyMessage: 'To get started, click on "Generate new response".'}

const rawColumns = [
    {
        id: 'Id',
        sortingField: 'Id',
        header: 'Name',
        cell: item => ( <CustomLink href={"/analysis/" + item.Id}>{item.Id}</CustomLink>),
    },
    {
        id: 'ContractType',
        sortingField: 'ContractType',
        header: 'Contract type',
        cell: item => <ContractType contractTypeId={item.ContractTypeId} />,
    },
    {
        id: 'State',
        sortingField: 'State',
        header: 'State',
        cell: item => <AnalysisState stateStr={item.State} />,
    },
    {
        id: 'CreatedAt',
        sortingField: 'CreatedAt',
        header: 'Creation date',
        cell: item => formatDate(item.CreatedAt),
    },
    {
        id: 'LastExecutionDate',
        sortingField: 'LastExecutionDate',
        header: 'Last response generation date',
        cell: item => formatDate(item.LastExecutionDate),
    },
];

export const FILTERING_PROPERTIES = [
    {
        propertyLabel: 'Name',
        key: 'Id',
        groupValuesLabel: 'Names',
        operators: [':', '!:', '=', '!='],
    },
    {
        propertyLabel: 'State',
        key: 'State',
        groupValuesLabel: 'States',
        operators: [':', '!:', '=', '!='],
    },
    {
        propertyLabel: 'ContractType',
        key: 'ContractTypeId',
        groupValuesLabel: 'Contract types',
        operators: [':', '!:', '=', '!='],
    },
];

export const COLUMN_DEFINITIONS = rawColumns.map(column => ({...column}));