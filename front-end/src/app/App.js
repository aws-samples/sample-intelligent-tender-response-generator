import './App.css';
import {useEffect} from "react";
import {HashRouter} from 'react-router-dom';
import {PageRouter} from "./pageRouter";
import {useAuth} from "react-oidc-context";
import {startWebSocket} from "../utils/wsClient";
import {useEnumCategoriesDataStore} from "../data_store/enumCategoriesDataStore.ts";
import {Endpoint, handleResponse, sendRequest} from "../utils/api";
import {PREVIEW_ENUM_CATEGORIES} from "../utils/previewData";

const IS_PREVIEW = process.env.REACT_APP_PREVIEW === 'true';


export const App = () => {
    const auth = useAuth()
    const enumCategoriesDataStore = useEnumCategoriesDataStore();

    useEffect(() => {
        // Local UI preview: no backend is available, so seed the enum store
        // with static fixtures (otherwise dropdowns such as "Contract type"
        // render empty) and skip the WebSocket/API calls that would fail.
        if (IS_PREVIEW) {
            enumCategoriesDataStore.setMany(PREVIEW_ENUM_CATEGORIES);
            return;
        }

        startWebSocket(process.env.REACT_APP_WSS_URL, auth.user.id_token);
        getEnumCategories()
    }, []);

    function getEnumCategories() {
        sendRequest(Endpoint.getEnumCategories(auth.user.id_token))
            .then(handleResponse)
            .then(response => {enumCategoriesDataStore.setMany(response)})
            .catch((error) => {console.error(error.message)})
    }

    return (
        <HashRouter>
            <PageRouter></PageRouter>
        </HashRouter>
    )
}