import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import {App} from './app/App';
import reportWebVitals from './utils/reportWebVitals';
import { AuthProvider, AuthContext } from "react-oidc-context";
import AuthGate from "./utils/AuthGate";


const cognitoAuthConfig = {
    authority: process.env.REACT_APP_COGNITO_AUTHORITY,
    client_id: process.env.REACT_APP_USER_POOL_CLIENT_ID,
    redirect_uri: window.location.origin,
    post_logout_redirect_uri: `${window.location.origin}/login`,
    response_type: "code",
    scope: "email openid profile",
};

const onSignInCallback = () => {
    const url = new URL(window.location.href);
    window.history.replaceState({}, document.title, url.pathname + url.hash);
    window.location.reload()
};

const root = ReactDOM.createRoot(document.getElementById('root'));

// Local UI preview only: when REACT_APP_PREVIEW=true, skip the Cognito sign-in
// redirect and supply a mock auth context so the interface can be viewed on
// localhost without a deployed backend. This branch is inert in normal builds
// (the flag is unset), so the deployed app's authentication is unaffected.
const isPreview = process.env.REACT_APP_PREVIEW === 'true';

const mockAuth = {
    isLoading: false,
    isAuthenticated: true,
    activeNavigator: undefined,
    error: undefined,
    user: {
        id_token: 'preview-token',
        access_token: 'preview-token',
        profile: { email: 'preview@example.com' },
    },
    signinRedirect: () => Promise.resolve(),
    signoutRedirect: () => Promise.resolve(),
    removeUser: () => Promise.resolve(),
};

root.render(
    <React.StrictMode>
        {isPreview ? (
            <AuthContext.Provider value={mockAuth}>
                <App />
            </AuthContext.Provider>
        ) : (
            <AuthProvider {...cognitoAuthConfig} onSigninCallback={onSignInCallback}>
                <AuthGate>
                    <App />
                </AuthGate>
            </AuthProvider>
        )}
    </React.StrictMode>
);

reportWebVitals();
