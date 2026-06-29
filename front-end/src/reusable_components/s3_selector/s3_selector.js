import {useEffect, useState} from "react";
import {Endpoint, handleResponse, sendRequest} from "../../utils/api";
import {useAuth} from "react-oidc-context";
import {Button, Container, Header, Modal, SpaceBetween, Box, BreadcrumbGroup} from "@cloudscape-design/components";
import {createColumnDefinitions, FILTERING_PROPERTIES, TEXTS} from "./table_config";
import {CollectionsTable} from "../filteredTable/collectionsTable";
import * as React from "react";

export const S3Selector = ({visible, setVisible, onFolderSelected, rootText, title, initialPath=''}) => {
    const auth = useAuth()

    const [items, setItems] = useState([])
    const [loading, setLoading] = useState(false)
    const [selectedItems, setSelectedItems] = useState([])
    const [path, setPath] = useState(initialPath)

    const COLUMN_DEFINITIONS = createColumnDefinitions(pathFollowed)

    useEffect(() => {
        setItems([])
        setSelectedItems([])
        listPath()
    }, [path])

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

        if (path === '/' || path === '') setPath(event.detail.href)
        else setPath(path + '/' + event.detail.href)
    }

    const PathBreadcrumbs = () => {
        let accumPath = ''
        let items = [{text: rootText, href: ''}]

        for (let item of path.split('/')) {
            if (item.length > 0) {
                items.push(
                    {text: item, href: accumPath + '/' + item},
                )
            }

            if (accumPath.length > 0) accumPath += '/' + item
            else accumPath = item
        }

        return (
            <BreadcrumbGroup
                items={items}
                ariaLabel="Breadcrumbs"
                onClick={(event) => {
                    event.preventDefault()
                    setPath(event.detail.href)
                }}
            />
        )
    }

    return (
        <Modal
            onDismiss={() => setVisible(false)}
            visible={visible}
            size='large'
            footer={
                <Box float="right">
                    <SpaceBetween direction="horizontal" size="xs">
                        <Button variant="link" onClick={() => setVisible(false)}>Cancel</Button>
                        <Button variant="primary" disabled={selectedItems.length === 0} onClick={() => {
                            const folderPath = path === ''? selectedItems[0].Name : path + '/' + selectedItems[0].Name

                            setVisible(false)
                            onFolderSelected(folderPath)
                        }}
                        >Choose</Button>
                    </SpaceBetween>
                </Box>
            }
            header={title}
        >
            <SpaceBetween direction={'vertical'} size={'m'}>
                <PathBreadcrumbs></PathBreadcrumbs>

                <CollectionsTable
                    data={items}
                    loading={loading}
                    texts={TEXTS}
                    columnDefinitions={COLUMN_DEFINITIONS}
                    filteringProperties={FILTERING_PROPERTIES}
                    sortingColumn={COLUMN_DEFINITIONS[0]}
                    variant={'container'}
                    stickyHeader={true}
                    stripedRows={false}
                    resizableColumns={false}
                    selectionType={'single'}
                    trackBy={'Name'}
                    onSelectionChange={({ detail }) =>
                        setSelectedItems(detail.selectedItems)
                    }
                    selectedItems={selectedItems}
                    isItemDisabled={item => !item.CanBeSelected}
                    header={
                        <Header
                            variant="h2"
                            counter={'(' + items.length + ')'}
                        >
                            Objects
                        </Header>
                    }
                />
            </SpaceBetween>
        </Modal>
    )
}