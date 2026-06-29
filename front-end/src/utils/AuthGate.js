import { useEffect, useRef } from "react";
import { useAuth } from "react-oidc-context";


export default function AuthGate({ children }) {
    const auth = useAuth();
    const triedRef = useRef(false);

    useEffect(() => {
        if (triedRef.current) return;
        if (auth.isLoading || auth.activeNavigator) return;

        const url = new URL(window.location.href);

        const onCallback =
            url.searchParams.has("code") ||
            url.searchParams.has("error") ||
            url.pathname.endsWith("/signin-callback");

        if (!auth.isAuthenticated && !onCallback) {
            triedRef.current = true;
            auth.signinRedirect().catch(() => {});
        }
    }, [auth.isLoading, auth.isAuthenticated, auth.activeNavigator]);

    if (auth.isLoading || !auth.isAuthenticated) return null;

    return children;
}
