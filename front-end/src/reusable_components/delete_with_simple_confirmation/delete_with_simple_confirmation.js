import {Alert, Button, Modal, SpaceBetween, Box} from "@cloudscape-design/components";

export const DeleteWithSimpleConfirmation = ({isVisible, onDismiss, onDelete}) => {
    return (
        <Modal
            visible={isVisible}
            onDismiss={() => onDismiss()}
            header={'Delete Knowledge Base'}
            closeAriaLabel="Close dialog"
            footer={
                <Box float="right">
                    <SpaceBetween direction="horizontal" size="xs">
                        <Button variant="link" onClick={() => onDismiss()}>
                            Cancel
                        </Button>

                        <Button variant="primary" onClick={() => onDelete()} data-testid="submit">
                            Delete
                        </Button>
                    </SpaceBetween>
                </Box>
            }
        >
            <SpaceBetween size="m">
                <Box variant="span">
                    Permanently delete Knowledge Base? You can’t undo this action.
                </Box>

                <Alert type={'warning'}>
                    Proceeding with this action will delete the Knowledge Base stack associated with this tender response,
                    including all indexed data sources.
                </Alert>
            </SpaceBetween>
        </Modal>
    );
}