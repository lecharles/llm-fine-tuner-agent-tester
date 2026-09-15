import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";
import { getToken } from "../api";
import { checkLocalMode, autoLoginLocal } from "../auth";

// Wraps any authenticated page. If there's no token, redirect to /login
// Phase 6 slice 3: if local mode is active, auto-login and skip the redirect.

type Props = { children: React.ReactNode };

export default function ProtectedRoute({ children }: Props) {
    const [checking, setChecking] = useState(true);
    const [isLocalMode, setIsLocalMode] = useState(false);

    useEffect(() => {
        if (getToken()) {
            setChecking(false);
            return;
        }
        // No token — check if we're in local mode
        checkLocalMode().then((local) => {
            if (local) {
                autoLoginLocal();
                setIsLocalMode(true);
            }
            setChecking(false);
        });
    }, []);

    if (checking) {
        return <div>Checking auth...</div>;
    }

    if (!getToken() && !isLocalMode) {
        return <Navigate to="/login" replace />;
    }

    return <>{children}</>;
}