import { Navigate } from "react-router-dom";
import type { ReactNode } from "react";
import { getToken } from "../api";

// Wraps any authenticated page. If there's no token, redirect to /login
// instead of rendering the page. `replace` keeps the bounce out of history,
// so the back button never loops.
export default function ProtectedRoute({ children }: { children: ReactNode }) {
    if (!getToken()) {
        return <Navigate to="/login" replace />;
    }
    return <>{children}</>;
}