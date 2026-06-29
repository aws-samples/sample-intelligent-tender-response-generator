import {Button, Modal, SpaceBetween, Box, Spinner, Alert} from "@cloudscape-design/components";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize from "rehype-sanitize";

const LoadingContent = () => (
    <Box textAlign="center">
        <Spinner size="large" />
    </Box>
)

const MarkdownView = ({text}) => (
    <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={{
            a: ({ node, ...props }) => (
                <a {...props} target="_blank" rel="noopener noreferrer" />
            ),
        }}
    >
        {text}
    </ReactMarkdown>
)

const ErrorAlert = () => (
    <Alert
        type="error"
        header="Markdown content could not be rendered"
    >
        Check your network connection and try again later.
    </Alert>
)

export const MarkdownPreview = ({markdown, isVisible, title, size, isLoading, hasError, onDismiss}) => {
    return (
        <Modal
            onDismiss={() => onDismiss()}
            visible={isVisible}
            footer={
                <Box float="right">
                    <SpaceBetween direction="horizontal" size="xs">
                        <Button variant="link" onClick={() => onDismiss()}>Close</Button>
                    </SpaceBetween>
                </Box>
            }
            header={title}
            size={size? size: 'large'}
        >
            {
                isLoading ? (
                    <LoadingContent />
                ) : hasError ? (
                    <ErrorAlert />
                ) : (
                    <MarkdownView text={markdown} />
                )
            }
        </Modal>
    )
}