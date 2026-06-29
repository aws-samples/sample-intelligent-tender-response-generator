import * as React from "react";
import {useEffect, useState} from "react";
import {
    Header,
    KeyValuePairs,
    ProgressBar,
    SpaceBetween,
    Container,
    Grid,
    Steps,
    ButtonDropdown, Alert, ContentLayout, Button, Box, Select
} from "@cloudscape-design/components";
import {Endpoint, sendRequest, handleResponse, downloadFile, fetchFileContents} from "../../utils/api";
import {useAuth} from "react-oidc-context";
import {formatDate, getAnalysisProgress, getAnalysisStep, KnowledgeBaseIndicator} from "../../utils/analysisUtils";
import {useNavigate, useParams} from "react-router-dom";
import {useAnalysisDataStore} from "../../data_store/analysisDataStore.ts";
import {useEnumCategoriesDataStore} from "../../data_store/enumCategoriesDataStore.ts";
import {S3Selector} from "../../reusable_components/s3_selector/s3_selector";
import {INPUT_FILES_COLUMN_DEFINITIONS, INPUT_FILES_FILTERING_PROPERTIES, INPUT_FILES_TEXTS} from "./input_files_table_config";
import {createColumnDefinitions, RESPONSE_FILES_FILTERING_PROPERTIES, RESPONSE_FILES_TEXTS} from "./response_files_table_config";
import {CollectionsTable} from "../../reusable_components/filteredTable/collectionsTable";
import {MarkdownPreview} from "../../reusable_components/mardown_preview/markdown_preview";
import {
    DeleteWithSimpleConfirmation
} from "../../reusable_components/delete_with_simple_confirmation/delete_with_simple_confirmation";


const MarkdownModal = ({markdown, isVisible, title, size, isLoading, hasError, onDismiss}) => (
    <MarkdownPreview
        markdown={markdown}
        isVisible={isVisible}
        title={title}
        size={size}
        isLoading={isLoading}
        hasError={hasError}
        onDismiss={onDismiss}
    ></MarkdownPreview>
)


const AnalysisError = ({analysis}) => {
    return (
        <Alert
            type="error"
            header="An error occurred while generating the response"
        >
            {analysis.Error}
        </Alert>
    )
}


export const AnalysisDetail = () => {
    const id = useParams()['id']
    const auth = useAuth();
    const navigate = useNavigate();

    const analysis = useAnalysisDataStore((state) => state.getById(id));
    const contractTypes = useEnumCategoriesDataStore((state) => state.getById('contract_types')?.Values) ?? [];
    const analysisStates = useEnumCategoriesDataStore.getState().getById('analysis_states')?.Values ?? []

    const [referenceTender, setReferenceTender] = useState(analysis?.ReferenceTender ?? '');
    const [contractType, setContractType] = useState('');

    const [inputFiles, setInputFiles] = useState([]);
    const [responseFiles, setResponseFiles] = useState([]);

    const [isLoadingAnalysis, setIsLoadingAnalysis] = useState(false);
    const [isLoadingInputFiles, setIsLoadingInputFiles] = useState(false);
    const [isLoadingResponseFiles, setIsLoadingResponseFiles] = useState(false);
    const [isDownloadingFile, setIsDownloadingFile] = useState(false);
    const [isPerformingTenderAction, setIsPerformingTenderAction] = useState(false);

    const [isLoadingMarkdownPreview, setIsLoadingMarkdownPreview] = useState(false);
    const [hasMarkdownPreviewError, setHasMarkdownPreviewError] = useState(false);
    const [markdownPreviewTitle, setMarkdownPreviewTitle] = useState("");
    const [markdownPreviewText, setMarkdownPreviewText] = useState("");
    const [isMarkdownPreviewVisible, setIsMarkdownPreviewVisible] = useState(false);

    const [s3SelectorVisible, setS3SelectorVisible] = useState(false);
    const [inputFilesToDelete, setInputFilesToDelete] = useState([]);
    const [responseFilesToDownload, setResponseFilesToDownload] = useState([]);

    const [deleteKbVisible, setDeleteKbVisible] = useState(false);

    const RESPONSE_FILES_COLUMN_DEFINITIONS = createColumnDefinitions(previewFile)

    useEffect(() => {
        if (analysis == null) getAnalysis()
        if (inputFiles.length === 0) getAnalysisInputFiles()
        if (responseFiles.length === 0) getAnalysisResponseFiles()
    }, []);

    useEffect(() => {
        initialiseContractTypeSelect()
        setReferenceTender(analysis?.ReferenceTender ?? '');
        setIsPerformingTenderAction(false)
    }, [analysis]);

    function initialiseContractTypeSelect() {
        for (let item of contractTypes) {
            if (item.value === analysis?.ContractTypeId) setContractType(item);
        }
    }

    function getAnalysis() {
        if (isLoadingAnalysis) return;

        setIsLoadingAnalysis(true)

        sendRequest(Endpoint.getAnalysis(auth.user.id_token, id))
            .then(handleResponse)
            .then(response => useAnalysisDataStore.getState().upsertItem(response.Item))
            .catch((error) => console.error(error.message))
            .finally(() => setIsLoadingAnalysis(false));
    }

    function getAnalysisInputFiles() {
        if (isLoadingInputFiles) return;

        setIsLoadingInputFiles(true);
        setInputFilesToDelete([])

        sendRequest(Endpoint.getAnalysisInputFiles(auth.user.id_token, id))
            .then(handleResponse)
            .then(response => setInputFiles(response.Files))
            .catch((error) => console.error(error.message))
            .finally(() => setIsLoadingInputFiles(false));
    }

    function getAnalysisResponseFiles() {
        if (isLoadingResponseFiles) return;

        setResponseFilesToDownload([])
        setIsLoadingResponseFiles(true);

        sendRequest(Endpoint.getAnalysisResponseFiles(auth.user.id_token, id))
            .then(handleResponse)
            .then(response => setResponseFiles(response.Files))
            .catch((error) => console.error(error.message))
            .finally(() => setIsLoadingResponseFiles(false));
    }

    function handleButtonClick(event) {
        if (event.detail.id === 'generate-response') {
            setIsPerformingTenderAction(true)

            sendRequest(Endpoint.startAnalysis(auth.user.id_token, id, referenceTender, contractType.value))
                .then(handleResponse)
                .catch((error) => {
                    setIsPerformingTenderAction(false)
                    console.error(error.message)
                })
        }
        else if (event.detail.id === 'delete-kb') {
            setDeleteKbVisible(true);
        }
    }

    function deleteFiles() {
        navigate('delete-files', {
            state: { files: inputFilesToDelete }
        })
    }

    function deleteKbStack() {
        setIsPerformingTenderAction(true)

        sendRequest(Endpoint.deleteKb(auth.user.id_token, id))
            .then(handleResponse)
            .catch((error) => {
                setIsPerformingTenderAction(false)
                console.error(error.message)
            })
    }

    async function downloadResponseFiles() {
        for (let file of responseFilesToDownload) {
            setIsDownloadingFile(true);

            sendRequest(Endpoint.generateDownloadUrl(auth.user.id_token, id, file.Key))
                .then(handleResponse)
                .then(response => {
                    downloadFile(response.DownloadUrl, file.Name)
                })
                .catch((error) => console.error(error.message))
                .finally(() => setIsDownloadingFile(false));
        }
    }

    async function previewFile(file) {
        setMarkdownPreviewTitle(file.Name)
        setMarkdownPreviewText('')
        setIsLoadingMarkdownPreview(true)
        setHasMarkdownPreviewError(false)
        setIsMarkdownPreviewVisible(true)

        sendRequest(Endpoint.generateDownloadUrl(auth.user.id_token, id, file.Key))
            .then(handleResponse)
            .then(response => {
                fetchFileContents(response.DownloadUrl)
                    .then(text => {
                        setMarkdownPreviewText(text)
                    })
                    .catch((error) => {
                        console.error(error.message)
                        setHasMarkdownPreviewError(true)
                    })
                    .finally(() => {
                        setIsLoadingMarkdownPreview(false)
                    })
            })
            .catch((error) => {
                console.error(error.message)
                setIsLoadingMarkdownPreview(false)
                setHasMarkdownPreviewError(true)
            })
    }

    const AnalysisSummary = () => {
        return (
            <Container
                header={
                    <Header
                        variant="h2"
                    >
                        Summary
                    </Header>
                }
            >
                <KeyValuePairs
                    columns={3}
                    items={[
                        {
                            label: "Creation date",
                            value: formatDate(analysis?.CreatedAt),
                        },
                        {
                            label: "Last response generation date",
                            value: formatDate(analysis?.LastExecutionDate),
                        },
                        {
                            label: "Response generation progress",
                            value: (
                                <ProgressBar variant={'key-value'} value={getAnalysisProgress(analysis?.State)}/>
                            )
                        },

                        {
                            label: "Contract type",
                            value: (
                                <Select
                                    selectedOption={contractType}
                                    options={contractTypes}
                                    onChange={({ detail }) =>
                                        setContractType(detail.selectedOption)
                                    }
                                ></Select>
                            )
                        },
                        {
                            label: "Reference response",
                            value: (
                                <Box>
                                    <Button variant={'inline-link'} onClick={() => setS3SelectorVisible(true)}>{referenceTender? referenceTender : 'Choose'}</Button>

                                    {referenceTender !== '' &&
                                        <Button iconName="remove" variant="inline-link" onClick={() => setReferenceTender('')}></Button>
                                    }
                                </Box>
                            )
                        },
                        {
                            label: "Knowledge Base status",
                            value: (
                                <KnowledgeBaseIndicator analysis={analysis}></KnowledgeBaseIndicator>
                            )
                        },
                    ]}
                />
            </Container>
        )
    }

    const WorkflowProgress = () => {
        let steps = []
        const currentStep = getAnalysisStep(analysis?.State)

        for (let i = 0; i < analysisStates.length; i++) {
            if (currentStep < i) {
                steps.push({
                    status: "stopped",
                    header: analysisStates[i]['States']['Pending']['Name'],
                    statusIconAriaLabel: "Not started"
                })
            }
            else if (currentStep > i) {
                steps.push({
                    status: "success",
                    header: analysisStates[i]['States']['Completed']['Name'],
                    statusIconAriaLabel: "Success"
                })
            }
            else {
                if (analysis?.State === analysisStates[i]['States']['Running']['Id']) {
                    steps.push({
                        status: "loading",
                        header: analysisStates[i]['States']['Running']['Name'],
                        statusIconAriaLabel: "Loading"
                    })
                }
                else if (analysis?.State === analysisStates[i]['States']['Failed']['Id']) {
                    steps.push({
                        status: "error",
                        header: analysisStates[i]['States']['Failed']['Name'],
                        statusIconAriaLabel: "Error"
                    })
                }
                else {
                    steps.push({
                        status: "success",
                        header: analysisStates[i]['States']['Completed']['Name'],
                        statusIconAriaLabel: "Success"
                    })
                }
            }
        }

        return <Container
            header={
                <Header
                    variant="h3"
                >
                    Workflow Progress
                </Header>
            }
        >
            <Steps steps={steps}></Steps>
        </Container>
    }

    const InputFiles = () => {
        return (
            <CollectionsTable
                data={inputFiles}
                pageSize={10}
                loading={isLoadingInputFiles}
                texts={INPUT_FILES_TEXTS}
                columnDefinitions={INPUT_FILES_COLUMN_DEFINITIONS}
                filteringProperties={INPUT_FILES_FILTERING_PROPERTIES}
                sortingColumn={INPUT_FILES_COLUMN_DEFINITIONS[0]}
                variant={'container'}
                stickyHeader={false}
                stripedRows={false}
                resizableColumns={false}
                selectionType={'multi'}
                selectedItems={inputFilesToDelete}
                onSelectionChange={({ detail }) =>
                    setInputFilesToDelete(detail.selectedItems)
                }
                header={
                    <Header
                        variant="h2"
                        counter={'(' + inputFiles.length + ')'}
                        description={'These are all the files you uploaded for generating the tender response.'}
                        actions={
                            <SpaceBetween direction="horizontal" size="xs">
                                <Button disabled={isLoadingInputFiles} iconName="refresh" onClick={() => getAnalysisInputFiles()}/>
                                <Button disabled={analysis?.RunningWorkflow || inputFilesToDelete.length === 0} onClick={() => deleteFiles()}>Delete</Button>
                                <Button disabled={analysis?.RunningWorkflow} onClick={() => navigate('upload-files')} iconName="upload">Upload</Button>
                            </SpaceBetween>
                        }
                    >
                        Input files
                    </Header>
                }
            />
        )
    }

    const ResponseFiles = () => {
        return (
            <CollectionsTable
                data={responseFiles}
                loading={isLoadingResponseFiles}
                texts={RESPONSE_FILES_TEXTS}
                columnDefinitions={RESPONSE_FILES_COLUMN_DEFINITIONS}
                filteringProperties={RESPONSE_FILES_FILTERING_PROPERTIES}
                sortingColumn={RESPONSE_FILES_COLUMN_DEFINITIONS[0]}
                variant={'container'}
                stickyHeader={false}
                stripedRows={false}
                resizableColumns={false}
                selectionType={'multi'}
                selectedItems={responseFilesToDownload}
                onSelectionChange={({ detail }) => setResponseFilesToDownload(detail.selectedItems)}
                header={
                    <Header
                        variant="h2"
                        counter={'(' + responseFiles.length + ')'}
                        description={'Here are all the tender response files generated by the agent. Click a file name to preview its contents.'}
                        actions={
                            <SpaceBetween direction="horizontal" size="xs">
                                <Button disabled={isLoadingResponseFiles} iconName="refresh" onClick={() => getAnalysisResponseFiles()}/>
                                <Button loading={isDownloadingFile} disabled={responseFilesToDownload.length === 0} onClick={(event) => downloadResponseFiles()} iconName="download">Download</Button>
                            </SpaceBetween>
                        }
                    >
                        Response files
                    </Header>
                }
            />
        )
    }

    return (
        <ContentLayout
            header={
                <SpaceBetween direction={'vertical'} size={'m'}>
                    <Header
                        variant="h1"
                        description="On this page, you can view the details of a response you attempted to generate, including the workflow steps and the files you uploaded."
                        actions={
                            <SpaceBetween direction="horizontal" size="xs">
                                <Button disabled={isLoadingAnalysis} iconName="refresh" onClick={() => getAnalysis()}/>

                                <ButtonDropdown
                                    loading={isPerformingTenderAction}
                                    variant={'primary'}
                                    onItemClick={(event) => {
                                        handleButtonClick(event)}
                                    }
                                    items={[
                                        { text: "Regenerate response", id: "generate-response", disabled: analysis?.RunningWorkflow},
                                        { text: "Delete Knowledge Base", id: "delete-kb", disabled: analysis?.RunningWorkflow || !analysis?.KbActive == null || analysis?.KbStackName == null }
                                    ]}
                                >
                                    Tender actions
                                </ButtonDropdown>
                            </SpaceBetween>
                        }
                    >
                        {id}
                    </Header>

                    {analysis?.Error &&
                        <AnalysisError analysis={analysis} />
                    }
                </SpaceBetween>
            }
        >
            <Grid
                gridDefinition={[{ colspan: 9 }, { colspan: 3 }]}
            >
                <SpaceBetween size={'l'} direction={'vertical'}>
                    <AnalysisSummary/>
                    <InputFiles/>
                    <ResponseFiles/>
                </SpaceBetween>

                <WorkflowProgress></WorkflowProgress>
            </Grid>

            <S3Selector
                initialPath={referenceTender}
                visible={s3SelectorVisible}
                setVisible={setS3SelectorVisible}
                onFolderSelected={(path) => setReferenceTender(path)}
                rootText={'Submitted tender responses'}
                title={'Reference response selection'}
            ></S3Selector>

            <MarkdownModal
                markdown={markdownPreviewText}
                isVisible={isMarkdownPreviewVisible}
                title={markdownPreviewTitle}
                size={'large'}
                isLoading={isLoadingMarkdownPreview}
                hasError={hasMarkdownPreviewError}
                onDismiss={() => setIsMarkdownPreviewVisible(false)}
            ></MarkdownModal>

            <DeleteWithSimpleConfirmation
                isVisible={deleteKbVisible}
                onDismiss={() => setDeleteKbVisible(false)}
                onDelete={() => {
                    setDeleteKbVisible(false)
                    deleteKbStack()
                }}
            ></DeleteWithSimpleConfirmation>
        </ContentLayout>
    );
}
