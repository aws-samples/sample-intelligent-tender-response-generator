import {useEffect, useState} from "react";
import {Endpoint, handleResponse, sendRequest} from "../../utils/api";
import {useAuth} from "react-oidc-context";
import {
    Button,
    Header,
    SpaceBetween,
    ContentLayout
} from "@cloudscape-design/components";
import {createColumnDefinitions, FILTERING_PROPERTIES, TEXTS} from "./table_config";
import {CollectionsTable} from "../../reusable_components/filteredTable/collectionsTable";
import * as React from "react";
import {useLocation, useNavigate, useParams} from "react-router-dom";

export const SubmittedResponses = () => {
    const auth = useAuth()
    const folder = useParams()['folder'];
    const navigate = useNavigate();
    const location = useLocation()

    const COLUMN_DEFINITIONS = createColumnDefinitions(pathFollowed)
    const isFolderView = folder != null;

    const [items, setItems] = useState([])
    const [loading, setLoading] = useState(false)
    const [selectedItems, setSelectedItems] = useState([])
    const [path, setPath] = useState(isFolderView? folder : '')

    useEffect(() => {
        setSelectedItems([])
        listPath()
    }, [path])

    useEffect(() => {
        const paths = location.pathname.split("/")

        if (paths.length === 2) setPath('')
        else setPath(paths[2])
    }, [location]);

    function listPath() {
        setLoading(true);

        sendRequest(Endpoint.listTenders(auth.user.id_token, path))
            .then(handleResponse)
            .then(response => {setItems(response.Items)})
            .catch((error) => {console.error(error.message)})
            .finally(() => setLoading(false));
    }

    function pathFollowed(event) {
        event.preventDefault()
        navigate(event.detail.href)
    }

    return (
        <ContentLayout>
            <CollectionsTable
                data={items}
                loading={loading}
                texts={TEXTS}
                columnDefinitions={COLUMN_DEFINITIONS}
                filteringProperties={FILTERING_PROPERTIES}
                sortingColumn={COLUMN_DEFINITIONS[0]}
                variant={'full-page'}
                stickyHeader={true}
                stripedRows={false}
                resizableColumns={true}
                selectionType={isFolderView? 'multi' :'single'}
                trackBy={'Name'}
                onSelectionChange={({ detail }) =>
                    setSelectedItems(detail.selectedItems)
                }
                selectedItems={selectedItems}
                header={
                    <Header
                        variant="h1"
                        counter={'(' + items.length + ')'}
                        description={'This page allows you to view and upload successful tender responses, which can be reused as references for generating new responses to other tenders.'}
                        actions={
                            <SpaceBetween direction={'horizontal'} size={'xs'}>
                                <Button iconName={'refresh'} onClick={listPath}></Button>
                                <Button disabled={selectedItems.length === 0}>{isFolderView? 'Delete files' : 'Delete folder'}</Button>
                            </SpaceBetween>
                        }
                    >
                        {isFolderView? folder : 'Submitted tender responses'}
                    </Header>
                }
            />
        </ContentLayout>
    )
}