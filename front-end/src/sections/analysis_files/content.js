import {
    Container,
    ContentLayout, FormField, Header, Input, SpaceBetween,
    Box, Button, Flashbar, Alert, Select
} from "@cloudscape-design/components";
import * as React from "react";
import {useNavigate, useParams} from "react-router-dom";
import {useAnalysisDataStore} from "../../data_store/analysisDataStore.ts";
import {useEffect, useState} from "react";
import {S3Selector} from "../../reusable_components/s3_selector/s3_selector";
import {FileUploadTable, updateFileState} from "../../reusable_components/file_upload/file_upload";
import {Endpoint, handleResponse, sendRequest, uploadFile} from "../../utils/api";
import {useAuth} from "react-oidc-context";
import {useEnumCategoriesDataStore} from "../../data_store/enumCategoriesDataStore.ts";
import {buildColumnDefinitions} from "./table_config";

const REGEX = /^[A-Za-z0-9][A-Za-z0-9-]{0,24}$/;


const GeneralConfiguration = ({
                                  value, onChange, error, referenceTender,
                                  onReferenceTenderSelectorClick, disabled, onReferenceTenderClearClick,
                                  contractTypes, contractType, onContractTypeChange
}) => {
    return <Container
        header={
            <Header
                variant="h2"
            >
                General configuration
            </Header>
        }
    >
        <SpaceBetween direction={"vertical"} size={"l"}>
            <FormField
                label="Tender response name"
                constraintText="The value must start with a letter (A–Z or a–z) or number, may contain only letters, numbers, and hyphens (-), and must be no more than 25 characters in length."
                errorText={error}
            >
                <Input
                    disabled={disabled}
                    placeholder="Name of the tender for which you are generating a response"
                    onChange={({ detail }) => {
                        onChange(detail.value);
                    }}
                    value={value}
                />
            </FormField>

            <SpaceBetween direction={'horizontal'} size={'xl'}>
                <FormField
                    label="Contract type"
                    description="Select the category that best defines the nature of the tender."
                >
                    <Select
                        disabled={disabled}
                        selectedOption={contractType}
                        onChange={({ detail }) =>
                            onContractTypeChange(detail.selectedOption)
                        }
                        options={contractTypes}
                        filteringType="auto"
                    />
                </FormField>

                <FormField
                    label="Reference response"
                    description="Response that you have submitted in the past that you want to use as a reference for generating the new response."
                >
                    <Button variant={'inline-link'} disabled={disabled} onClick={() => onReferenceTenderSelectorClick()}>{referenceTender? referenceTender : 'Choose'}</Button>

                    {referenceTender !== '' &&
                        <Button disabled={disabled} iconName="remove" variant="link" onClick={() => onReferenceTenderClearClick()}></Button>
                    }
                </FormField>
            </SpaceBetween>
        </SpaceBetween>
    </Container>
}


const NoticeAlert = () => (
    <Alert
        header="Notice about response generation"
    >
        <SpaceBetween direction={'vertical'} size={'xs'}>
            <Box>
                If no reference response is chosen, the generated response will be based exclusively on the uploaded tender project and requirement files, without inferring any specific format or writing style.
                Uncategorized input files are automatically classified during response generation.
            </Box>
        </SpaceBetween>
    </Alert>
)


const FileUploadSuccessFlashbar = () => {
    const navigate = useNavigate()

    return (
        <Flashbar items={[
            {
                type: "success",
                content: "All files were uploaded successfully.",
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
}


const UnsupportedFilesFlashbar = ({fileNames, onDismiss}) => (
    <Flashbar items={[
        {
            type: "error",
            content: `Some files were not added because their type is not supported. Only images, Word documents (.docx) and PDF files are allowed. Skipped: ${fileNames.join(", ")}.`,
            dismissible: true,
            dismissLabel: "Dismiss message",
            onDismiss: onDismiss,
            id: "unsupported_files"
        }
    ]} />
)


export const AnalysisFiles = () => {
    const auth = useAuth();
    const id = useParams()['id'];
    const navigate = useNavigate()

    const contractTypes = useEnumCategoriesDataStore((state) => state.getById('contract_types')?.Values) ?? [];
    const fileCategories = useEnumCategoriesDataStore((state) => state.getById('document_categories')?.Values[0].options) ?? [];
    const isUpdateMode = id != null
    const columnDefinitions = buildColumnDefinitions(fileCategories, updateFileCategory)

    let analysis = useAnalysisDataStore((state) => state.getById(id));

    if (analysis == null) analysis = {Id: '', ReferenceTender: '', ContractTypeId: 'public_works'}

    const [analysisIdError, setAnalysisIdError] = useState('');
    const [showUploadSuccess, setShowUploadSuccess] = useState(false);
    const [isUploading, setIsUploading] = useState(false);
    const [analysisId, setAnalysisId] = useState(analysis.Id);
    const [referenceTender, setReferenceTender] = useState(analysis.ReferenceTender);
    const [s3SelectorVisible, setS3SelectorVisible] = useState(false);
    const [files, setFiles] = useState([]);
    const [tokenGroupFiles, setTokenGroupFiles] = useState([]);
    const [contractType, setContractType] = useState({});
    const [rejectedFileNames, setRejectedFileNames] = useState([]);

    useEffect(() => {
        initialiseContractTypeSelect()
    }, [contractTypes]);

    function initialiseContractTypeSelect() {
        for (let item of contractTypes) {
            if (item.value === analysis.ContractTypeId) setContractType(item);
        }
    }

    function validateAnalysisId(text) {
        if (!REGEX.test(text)) {
            setAnalysisIdError('Invalid format')
        }
        else {
            setAnalysisIdError('');
        }
    }

    function startAnalysis() {
        setIsUploading(true);

        sendRequest(Endpoint.startAnalysis(auth.user.id_token, analysisId, referenceTender, contractType.value))
            .then(handleResponse)
            .then(() => navigate('/analysis/' + analysisId))
            .catch((error) => console.error(error.message))
            .finally(() => setIsUploading(false));
    }

    function uploadFiles(startAnalysisPostUpload = false) {
        const fileInfo = files.map(f => ({key: f.file.name, tags: {category: f.category?.value}}));

        setShowUploadSuccess(false);
        setIsUploading(true);

        sendRequest(Endpoint.generateUploadUrl(auth.user.id_token, analysisId, fileInfo))
            .then(handleResponse)
            .then(async response => {
                const uploadPromises = response.map((item, index) => {
                    updateFileState(setFiles, item.File, true);

                    return uploadFile(files[index].file, item.UploadUrl, item.Tags)
                        .catch(err => {
                            updateFileState(setFiles, item.File, false, false, '' + err);
                        })
                        .finally(() => {
                            updateFileState(setFiles, item.File, false, true);
                        });
                });

                await Promise.all(uploadPromises);

                if (startAnalysisPostUpload) startAnalysis();
                else {
                    setShowUploadSuccess(true);
                    setIsUploading(false)
                }
            })
            .catch((error) => console.error(error.message))
            .finally(() => setIsUploading(false))
    }

    function updateFileCategory(file, selectedOption) {
        setFiles(prevItems =>
            prevItems.map(item =>
                item === file
                    ? { ...item, category: selectedOption }
                    : item
            )
        );
    }

    const InputFiles = () => {
        return <Container
            header={
                <Header
                    variant="h2"
                    description={'Upload the tender project and requirement files for which a response will be generated.'}
                >
                    Input files
                </Header>
            }
        >
            <FileUploadTable
                files={files}
                setFiles={setFiles}
                tokenGroupFiles={tokenGroupFiles}
                setTokenGroupFiles={setTokenGroupFiles}
                extraColumnDefinitions={columnDefinitions}
                onRejectedFiles={(rejected) => setRejectedFileNames(rejected.map(f => f.name))}
            ></FileUploadTable>
        </Container>
    }

    return (
        <ContentLayout
            header={
                <SpaceBetween direction={'vertical'} size={'m'}>
                    <Header
                        variant="h1"
                        description={isUpdateMode?
                            "On this page, you can upload the files required to generate a new tender response."
                            : "On this page, you can upload the files required to generate a new tender response and specify a submitted response to use as a reference."
                        }
                    >
                        {isUpdateMode? 'Upload input files' : 'New response'}
                    </Header>

                    {rejectedFileNames.length > 0 &&
                        <UnsupportedFilesFlashbar
                            fileNames={rejectedFileNames}
                            onDismiss={() => setRejectedFileNames([])}
                        />
                    }

                    {showUploadSuccess &&
                        <FileUploadSuccessFlashbar/>
                    }
                </SpaceBetween>
            }
        >
            <SpaceBetween direction={'vertical'} size={'l'}>
                {!isUpdateMode &&
                    <NoticeAlert/>
                }

                {!isUpdateMode &&
                    <GeneralConfiguration
                        value={analysisId}
                        error={analysisIdError}
                        referenceTender={referenceTender}
                        disabled={isUploading}
                        onChange={(value) => {
                            setAnalysisId(value);
                            validateAnalysisId(value);
                        }}
                        onReferenceTenderSelectorClick={() => {
                            setS3SelectorVisible(true);
                        }}
                        onReferenceTenderClearClick={() => {
                           setReferenceTender('')
                        }}
                        contractType={contractType}
                        contractTypes={contractTypes}
                        onContractTypeChange={(selectedOption) => (setContractType(selectedOption))}
                    />
                }

                <InputFiles/>

                <Box float={'right'}>
                    <SpaceBetween direction={'horizontal'} size={'s'}>
                        <Button variant={'link'} onClick={() => navigate(-1)} disabled={isUploading}>Cancel</Button>

                        {!isUpdateMode ?
                            (
                                <Button
                                    variant={'primary'}
                                    iconName={'gen-ai'}
                                    loading={isUploading}
                                    disabled={analysisId.length === 0 || analysisIdError.length !== 0 || files.length === 0}
                                    onClick={() => uploadFiles(true)}
                                >
                                    Start response generation
                                </Button>
                            ) :
                            (
                                <Button
                                    variant={'primary'}
                                    loading={isUploading}
                                    disabled={analysisId.length === 0 || analysisIdError.length !== 0 || files.length === 0}
                                    onClick={() => uploadFiles(false)}
                                >
                                    Upload files
                                </Button>
                            )
                        }
                    </SpaceBetween>
                </Box>
            </SpaceBetween>

            {!isUpdateMode &&
                <S3Selector
                    initialPath={referenceTender}
                    visible={s3SelectorVisible}
                    setVisible={setS3SelectorVisible}
                    onFolderSelected={(path) => setReferenceTender(path)}
                    rootText={'Submitted tender responses'}
                    title={'Reference response selection'}
                ></S3Selector>
            }
        </ContentLayout>
    )
}