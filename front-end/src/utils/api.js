export async function downloadFile(url, filename) {
    const response = await fetch(url, {});

    if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
    }

    const blob = await response.blob();
    const objectUrl = URL.createObjectURL(blob);

    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = filename;

    document.body.appendChild(link);
    link.click();

    URL.revokeObjectURL(objectUrl);
    document.body.removeChild(link);
}

export async function fetchFileContents(url) {
    const response = await fetch(url, {});

    if (!response.ok) {
        throw new Error(`Download failed: ${response.status}`);
    }

    return await response.text();
}

export async function uploadFile(file, uploadUrl, tags) {
    const response = await fetch(uploadUrl, {
        method: "PUT",
        headers: {
            "Content-Type": file.type,
            'x-amz-tagging': tags
        },
        body: file,
    });

    if (!response.ok) {
        throw new Error(`Upload failed: ${response.statusText}`);
    }
}

export class Endpoint {
    constructor(path, headers={}, body={}, method='GET') {
        this.url = process.env.REACT_APP_API_URL + path
        this.method = method
        this.body = body
        this.headers = headers
    }

    static scanAnalysis(token) {
        return new Endpoint('/analysis', {'Authorization': token, 'x-api-key': process.env.REACT_APP_API_KEY})
    }

    static getEnumCategories(token) {
        return new Endpoint('/enum-categories', {'Authorization': token, 'x-api-key': process.env.REACT_APP_API_KEY})
    }

    static getAnalysis(token, analysisId) {
        return new Endpoint(`/analysis/${analysisId}`, {'Authorization': token, 'x-api-key': process.env.REACT_APP_API_KEY})
    }

    static getAnalysisInputFiles(token, analysisId) {
        return new Endpoint(`/analysis/${analysisId}/input-files`, {'Authorization': token, 'x-api-key': process.env.REACT_APP_API_KEY})
    }

    static getAnalysisResponseFiles(token, analysisId) {
        return new Endpoint(`/analysis/${analysisId}/response-files`, {'Authorization': token, 'x-api-key': process.env.REACT_APP_API_KEY})
    }

    static startAnalysis(token, analysisId, referenceTender, contractTypeId) {
        const params = new URLSearchParams({
            referenceTender: referenceTender,
            contractTypeId: contractTypeId,
        });

        return new Endpoint(`/analysis/${analysisId}/start?${params.toString()}`, {'Authorization': token, 'x-api-key': process.env.REACT_APP_API_KEY})
    }

    static listTenders(token, path) {
        const params = new URLSearchParams({
            path: path
        });

        return new Endpoint(`/list-tenders?${params.toString()}`, {'Authorization': token, 'x-api-key': process.env.REACT_APP_API_KEY})
    }

    static generateDownloadUrl(token, analysisId, key) {
        const params = new URLSearchParams({
            key: key
        });

        return new Endpoint(`/analysis/${analysisId}/generate-download-url?${params.toString()}`, {'Authorization': token, 'x-api-key': process.env.REACT_APP_API_KEY})
    }

    static generateUploadUrl(token, analysisId, keys) {
        return new Endpoint(
            `/analysis/${analysisId}/generate-upload-url`,
            {'Authorization': token, 'x-api-key': process.env.REACT_APP_API_KEY},
            keys,
            'POST'
        )
    }

    static deleteFiles(token, analysisId, files) {
        return new Endpoint(
            `/analysis/${analysisId}/delete-files`,
            {'Authorization': token, 'x-api-key': process.env.REACT_APP_API_KEY},
            files,
            'POST'
        )
    }

    static deleteKb(token, analysisId) {
        return new Endpoint(
            `/analysis/${analysisId}/kb`,
            {'Authorization': token, 'x-api-key': process.env.REACT_APP_API_KEY},
            '',
            'DELETE'
        )
    }
}

export const sendRequest = (endpoint) => {
    return fetch(endpoint.url, {
        method: endpoint.method,
        headers: endpoint.headers,
        body: endpoint.method === "GET"? null : JSON.stringify(endpoint.body)
    })
}

export const handleResponse = (response) => {
    if (!response.ok) {
        return response.json()
            .catch(() => {
                throw new Error(response.status);
            })
            .then(({message}) => {
                throw new Error(message || response.status);
            });
    }

    return response.json();
}