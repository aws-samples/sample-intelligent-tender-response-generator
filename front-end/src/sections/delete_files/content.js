import {
    ContentLayout, Header, SpaceBetween,
    Box, Button, Flashbar, Container, Alert, Input, FormField
} from "@cloudscape-design/components";
import * as React from "react";
import {useLocation, useNavigate, useParams} from "react-router-dom";
import {useState} from "react";
import {useAuth} from "react-oidc-context";
import {CollectionsTable} from "../../reusable_components/filteredTable/collectionsTable";
import {
    INPUT_FILES_COLUMN_DEFINITIONS,
    INPUT_FILES_FILTERING_PROPERTIES,
    INPUT_FILES_TEXTS
} from "../analysis_detail/input_files_table_config";
import {Endpoint, handleResponse, sendRequest} from "../../utils/api";


const DeleteConfirmationForm = ({text, onChange}) => (
    <Container
        header={
            <Header
                variant="h2"
            >
                Permanently delete files?
            </Header>
        }
    >
        <FormField
            label={
                <span>
                To confirm deletion, type <em>permanently delete</em> in the text input field.
                </span>
            }
        >
            <Input
                placeholder="permanently delete"
                onChange={({ detail }) => {
                    onChange(detail.value);
                }}
                value={text}
            />
        </FormField>
    </Container>
)

const DeleteWarningAlert = () => (
    <Alert type="warning">
        Deleting files is permanent and cannot be undone. Once deleted, these files will be permanently removed and cannot be recovered.
    </Alert>
)

export const DeleteFiles = () => {
    const auth = useAuth();
    const navigate = useNavigate()
    const id = useParams()['id'];
    const { state } = useLocation();

    const inputFiles = state?.files ?? [];
    const [showDeleteSuccess, setShowDeleteSuccess] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);
    const [deleteConfirmation, setDeleteConfirmation] = useState('');

    function deleteFiles() {
        setIsDeleting(true)

        const keys = inputFiles.map(x => x.Name);

        sendRequest(Endpoint.deleteFiles(auth.user.id_token, id, keys))
            .then(handleResponse)
            .then(() => setShowDeleteSuccess(true))
            .catch((error) => console.error(error.message))
            .finally(() => setIsDeleting(false));
    }

    function isConfirmationValid() {
        return deleteConfirmation.toLowerCase() === 'permanently delete';
    }

    const InputFiles = () => {
        return (
            <CollectionsTable
                data={inputFiles}
                pageSize={10}
                loading={false}
                texts={INPUT_FILES_TEXTS}
                columnDefinitions={INPUT_FILES_COLUMN_DEFINITIONS}
                filteringProperties={INPUT_FILES_FILTERING_PROPERTIES}
                sortingColumn={INPUT_FILES_COLUMN_DEFINITIONS[0]}
                variant={'container'}
                stickyHeader={false}
                stripedRows={false}
                resizableColumns={false}
                header={
                    <Header
                        variant="h2"
                        counter={'(' + inputFiles.length + ')'}
                    >
                        Selected files
                    </Header>
                }
            />
        )
    }

    const FileDeleteSuccessFlashbar = () => (
        <Flashbar items={[
            {
                type: "success",
                content: "All files were deleted successfully.",
                dismissible: false,
                dismissLabel: "Dismiss message",
                id: "message_1",
                action: (
                    <Button onClick={() => navigate(-1)}>
                        Back to analysis
                    </Button>
                )
            }
        ]} />
    )

    return (
        <ContentLayout
            header={
                <SpaceBetween direction={'vertical'} size={'m'}>
                    <Header
                        variant="h1"
                        description="On this page, you can delete the files you no longer want considered to generate a new tender response."
                    >
                        Delete input files
                    </Header>

                    {showDeleteSuccess &&
                        <FileDeleteSuccessFlashbar/>
                    }
                </SpaceBetween>
            }
        >
            <SpaceBetween direction={'vertical'} size={'l'}>
                <DeleteWarningAlert/>
                <InputFiles/>
                <DeleteConfirmationForm
                    text={deleteConfirmation}
                    onChange={(value) => setDeleteConfirmation(value)}
                >
                </DeleteConfirmationForm>

                <Box float={'right'}>
                    <SpaceBetween direction={'horizontal'} size={'s'}>
                        <Button variant={'link'} onClick={() => navigate(-1)} disabled={isDeleting}>Cancel</Button>

                        <Button
                            variant={'primary'}
                            loading={isDeleting}
                            disabled={!isConfirmationValid()}
                            onClick={() => deleteFiles()}
                        >
                            Delete files
                        </Button>
                    </SpaceBetween>
                </Box>
            </SpaceBetween>
        </ContentLayout>
    )
}