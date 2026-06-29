import {
    Box,
    FileDropzone,
    FileInput,
    FileTokenGroup,
    SpaceBetween,
    Table
} from "@cloudscape-design/components";
import * as React from "react";
import {COLUMN_DEFINITIONS} from "./table_config";

// Only images, Word documents (DOCX) and PDFs may be uploaded.
// The MIME list drives the native file picker filter; the extension list is a
// fallback because some browsers report an empty type for DOCX files.
const ALLOWED_MIME_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];
const ALLOWED_EXTENSIONS = [
    ".pdf", ".docx",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".svg",
];

// Value for the FileInput `accept` attribute (native picker pre-filter).
export const ALLOWED_FILE_ACCEPT =
    [...ALLOWED_MIME_TYPES, "image/*"].join(",");

export function isAllowedFile(file) {
    const type = (file.type || "").toLowerCase();

    if (type.startsWith("image/")) return true;
    if (ALLOWED_MIME_TYPES.includes(type)) return true;

    // Fallback to extension when the browser does not provide a MIME type.
    const name = (file.name || "").toLowerCase();
    return ALLOWED_EXTENSIONS.some(ext => name.endsWith(ext));
}

// Split a list of File objects into accepted and rejected based on type.
export function partitionFilesByType(fileList) {
    const accepted = [];
    const rejected = [];

    for (const file of fileList) {
        (isAllowedFile(file) ? accepted : rejected).push(file);
    }

    return {accepted, rejected};
}

export function updateFileState(
    setFiles,
    filename,
    setLoading = false,
    completed = false,
    errorText = "",
    warningText = ""
) {
    setFiles(prevItems =>
        prevItems.map(item => {
            if (item.file.name !== filename) {
                return item;
            }

            return {
                ...item,
                loading: setLoading,
                completed: completed,
                ...(errorText && { errorText }),
                ...(warningText && { warningText })
            };
        })
    );
}


export const FileUpload = ({files, setFiles}) => {
    return (
        <SpaceBetween direction={'vertical'} size={'s'}>
            <FileDropzone
                onChange={({ detail }) => setFiles(detail.value.map(file => ({ file })))}
            >
                <SpaceBetween size="xxs" alignItems="center">
                    <Box color="inherit">
                        Drop files here or select from below
                    </Box>

                    <FileInput
                        value={files.map(item => item.file)}
                        multiple
                        onChange={({ detail }) => setFiles(detail.value.map(file => ({ file })))}
                    >
                        Choose files
                    </FileInput>
                </SpaceBetween>
            </FileDropzone>

            <FileTokenGroup
                items={files}
                onDismiss={({ detail }) =>
                    setFiles(_ =>
                        files.filter(
                            (_, index) => index !== detail.fileIndex
                        )
                    )
                }
                i18nStrings={{
                    removeFileAriaLabel: () => "Remove file",
                    limitShowFewer: "Show fewer files",
                    limitShowMore: "Show more files",
                    errorIconAriaLabel: "Error",
                    warningIconAriaLabel: "Warning"
                }}
                showFileLastModified
                showFileSize
                showFileThumbnail
                alignment={'horizontal'}
            />
        </SpaceBetween>
    )
}


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


export const FileUploadTable = ({files, setFiles, extraColumnDefinitions=[], onRejectedFiles}) => {
    // Accept only images, DOCX and PDF. Drag-and-drop ignores the `accept`
    // attribute, so both handlers filter explicitly and report rejected files.
    const handleSelected = (selected) => {
        const {accepted, rejected} = partitionFilesByType(selected);

        if (rejected.length > 0 && onRejectedFiles) {
            onRejectedFiles(rejected);
        }

        setFiles(accepted.map(file => ({ file })));
    };

    return (
        <SpaceBetween direction={'vertical'} size={'s'}>
            <FileDropzone
                onChange={({ detail }) => handleSelected(detail.value)}
            >
                <SpaceBetween size="s" alignItems="center">
                    <Box color="inherit">
                        Drop files here or select from below. Previously selected files will be replaced.
                    </Box>

                    <Box color="text-status-inactive" fontSize="body-s">
                        Supported file types: images, Word documents (.docx) and PDF.
                    </Box>

                    <FileInput
                        accept={ALLOWED_FILE_ACCEPT}
                        value={files.map(item => item.file)}
                        multiple
                        onChange={({ detail }) => handleSelected(detail.value)}
                    >
                        Choose files
                    </FileInput>
                </SpaceBetween>
            </FileDropzone>

            {files.length > 0 &&
                <Table
                    resizableColumns
                    items={files}
                    columnDefinitions={[...COLUMN_DEFINITIONS, ...extraColumnDefinitions]}
                    empty={<EmptyState title={'No files'} subtitle={'You have not chosen any files to upload.'}/>}
                ></Table>
            }
        </SpaceBetween>
    )
}