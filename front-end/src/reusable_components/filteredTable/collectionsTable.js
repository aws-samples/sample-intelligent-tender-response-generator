import {Box, Button, Pagination, PropertyFilter, SpaceBetween, Table} from "@cloudscape-design/components";
import {useCollection} from "@cloudscape-design/collection-hooks";
import {propertyFilterI18nStrings, getTextFilterCounterText} from "./propertyFilter";


const NoMatchState = props => (
    <Box margin={{ vertical: 'xs' }} textAlign="center" color="inherit">
        <SpaceBetween size="xxs">
            <div>
                <b>No matches</b>
                <Box variant="p" color="inherit">
                    We can't find a match.
                </Box>
            </div>
            <Button onClick={props.onClearFilter}>Clear filter</Button>
        </SpaceBetween>
    </Box>
)

const EmptyState = ({title, subtitle}) => (
    <Box margin={{ vertical: 'xs' }} textAlign="center" color="inherit">
        <SpaceBetween size="xxs">
            <div>
                <b>{title}</b>
                <Box variant="p" color="inherit">
                    {subtitle}
                </Box>
            </div>
        </SpaceBetween>
    </Box>
)

export const CollectionsTable = (props) => {
    const filteringProperties = props.filteringProperties
    const {items, actions, filteredItemsCount, collectionProps,
        propertyFilterProps, paginationProps} = useCollection(
        props.data,
        {
            propertyFiltering: {
                filteringProperties,
                empty: <EmptyState title={props.texts.emptyTitle} subtitle={props.texts.emptyMessage}/>,
                noMatch: (
                    <NoMatchState
                        onClearFilter={() => {
                            actions.setPropertyFiltering({tokens: [], operation: 'and'});
                        }}
                    />
                )
            },
            pagination: {pageSize: props.pageSize?? 20},
            sorting: {defaultState: {sortingColumn: props.sortingColumn, isDescending: props.sortingDescending || false}},
            selection: {},
        }
    );

    return (
        <Table
            {...collectionProps}
            {...props}
            loadingText={props.texts.loadingText}
            items={items}
            pagination={<Pagination{...paginationProps}/>}
            wrapLines={true}
            filter={
                <PropertyFilter
                    {...props.texts}
                    {...propertyFilterProps}
                    i18nStrings={propertyFilterI18nStrings}
                    countText={getTextFilterCounterText(filteredItemsCount)}
                    expandToViewport={true}
                />
            }
            onSelectionChange={event => {
                collectionProps.onSelectionChange(event)
                props.onSelectionChange(event)
            }}
        />
    );
}