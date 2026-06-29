import * as React from "react";
import {useEffect, useState} from "react";
import {Button, Header, SpaceBetween} from "@cloudscape-design/components";
import {Endpoint, sendRequest, handleResponse} from "../../utils/api";
import {useAuth} from "react-oidc-context";
import {useAnalysisDataStore} from "../../data_store/analysisDataStore.ts";
import {COLUMN_DEFINITIONS, FILTERING_PROPERTIES, TEXTS} from "./table_config";
import {CollectionsTable} from "../../reusable_components/filteredTable/collectionsTable";
import {useNavigate} from "react-router-dom";


export const Home = () => {
    const auth = useAuth();
    const navigate = useNavigate();

    const analysisDataStore = useAnalysisDataStore();
    const analyses = useAnalysisDataStore((s) => s.items);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        if (analyses.length === 0) scanAnalysis()
    }, []);

    function scanAnalysis() {
        if (isLoading) return;

        setIsLoading(true);

        sendRequest(Endpoint.scanAnalysis(auth.user.id_token))
            .then(handleResponse)
            .then(response => analysisDataStore.setMany(response.Items))
            .catch((error) => {console.error(error.message)})
            .finally(() => setIsLoading(false));
    }

    return (
        <CollectionsTable
            data={analyses}
            loading={isLoading}
            texts={TEXTS}
            columnDefinitions={COLUMN_DEFINITIONS}
            filteringProperties={FILTERING_PROPERTIES}
            sortingColumn={COLUMN_DEFINITIONS[2]}
            variant={'full-page'}
            stickyHeader={true}
            stripedRows={false}
            resizableColumns={false}
            header={
                <Header
                    variant="h1"
                    counter={'(' + analyses.length + ')'}
                    description={'On this page, you can view all generated tender responses. Click a response name to see its details.'}
                    actions={
                        <SpaceBetween direction="horizontal" size="xs">
                            <Button iconName="refresh" disabled={isLoading} onClick={() => scanAnalysis()}/>

                            <Button variant="primary" iconName={'gen-ai'}
                                onClick={() => navigate('/newAnalysis')}
                            >
                                Generate new response
                            </Button>
                        </SpaceBetween>
                    }
                >
                    Generated tender responses
                </Header>
            }
        />
    );
}
