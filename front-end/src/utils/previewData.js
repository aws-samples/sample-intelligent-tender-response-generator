// Local UI preview only.
//
// When the app runs with REACT_APP_PREVIEW=true there is no deployed backend,
// so the /enum-categories endpoint cannot populate the enum store and dropdowns
// (e.g. "Contract type") would render empty. This module mirrors the static
// data returned by the enumCategory Lambda
// (infra/assets/lambda/func_enum_category/*.json) so the interface can be
// explored locally. It has no effect on a normal build (the flag is unset).

export const PREVIEW_ENUM_CATEGORIES = [
    {
        Id: "analysis_states",
        Values: [
            {
                Id: "CLASSIFY_DOCS",
                States: {
                    Pending: { Name: "Document classification" },
                    Running: { Id: "1_CLASSIFYING_DOCS", Name: "Classifying documents" },
                    Failed: { Id: "2_CLASSIFYING_DOCS_KO", Name: "Document classification failed" },
                    Completed: { Id: "3_CLASSIFYING_DOCS_OK", Name: "Documents classified" },
                },
            },
            {
                Id: "SELECT_REFERENCE_RESPONSE",
                States: {
                    Pending: { Name: "Reference response selection" },
                    Running: { Id: "4_SELECTING_REFERENCE_RESPONSE", Name: "Selecting reference response" },
                    Failed: { Id: "5_SELECTING_REFERENCE_RESPONSE_KO", Name: "Reference response selection failed" },
                    Completed: { Id: "6_SELECTING_REFERENCE_RESPONSE_OK", Name: "Reference response selected" },
                },
            },
            {
                Id: "CHUNK_DOCS",
                States: {
                    Pending: { Name: "Document chunking" },
                    Running: { Id: "7_CHUNKING_DOCS", Name: "Chunking documents" },
                    Failed: { Id: "8_CHUNKING_DOCS_KO", Name: "Document chunking failed" },
                    Completed: { Id: "9_CHUNKING_DOCS_OK", Name: "Documents chunked" },
                },
            },
            {
                Id: "CREATE_KB",
                States: {
                    Pending: { Name: "Knowledge Base creation" },
                    Running: { Id: "10_CREATING_KB", Name: "Deploying Knowledge Base" },
                    Failed: { Id: "11_CREATING_KB_KO", Name: "Knowledge Base deployment failed" },
                    Completed: { Id: "12_CREATING_KB_OK", Name: "Knowledge Base deployed" },
                },
            },
            {
                Id: "SYNC_KB",
                States: {
                    Pending: { Name: "Document indexation" },
                    Running: { Id: "13_SYNCING_KB", Name: "Indexing documents" },
                    Failed: { Id: "14_SYNCING_KB_KO", Name: "Document indexation failed" },
                    Completed: { Id: "15_SYNCING_KB_OK", Name: "Documents indexed" },
                },
            },
            {
                Id: "GENERATE_RESPONSE",
                States: {
                    Pending: { Name: "Response generation" },
                    Running: { Id: "16_GENERATING_RESPONSE", Name: "Generating response" },
                    Failed: { Id: "17_GENERATING_RESPONSE_KO", Name: "Response generation failed" },
                    Completed: { Id: "18_GENERATING_RESPONSE_OK", Name: "Response generated" },
                },
            },
        ],
    },
    {
        Id: "contract_types",
        Values: [
            { value: "public_works", label: "Concession of Public Works" },
            { value: "construction_works", label: "Construction works" },
            { value: "oil_gas", label: "Oil and gas" },
            { value: "patrimonial", label: "Patrimonial" },
            { value: "services", label: "Services" },
            { value: "supplies", label: "Supplies" },
        ],
    },
    {
        Id: "document_categories",
        Values: [
            {
                label: "Tender request categories",
                options: [
                    { value: "technical_specifications", label: "Technical specifications" },
                    { value: "technical_specifications_modifications", label: "Technical specifications - amendment" },
                    { value: "legal_clauses", label: "Administrative clauses" },
                    { value: "legal_clauses_modifications", label: "Administrative clauses - amendment" },
                    { value: "economic_requirements", label: "Economic requirements" },
                ],
            },
            {
                label: "Tender response categories",
                options: [
                    { value: "technical_response", label: "Technical response" },
                    { value: "administrative_response", label: "Administrative response" },
                ],
            },
            {
                label: "Other categories",
                options: [
                    { value: "supporting_doc", label: "Supporting document" },
                ],
            },
        ],
    },
];
