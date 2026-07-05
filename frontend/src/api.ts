// Single door to the backend. Every screen's data calls go through here.
// In dev, /api is proxied to FastAPI on :8000; in prod it's the same-origin API
// path. So we always use relative /api URLs and never hardcode a host.

const BASE = "/api";
const TOKEN_KEY = "token";

// JWT storage. The token lives in localStorage so it survives a page refresh.
export function getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string): void {
    localStorage.setItem(TOKEN_KEY, token);
}
export function clearToken(): void {
    localStorage.removeItem(TOKEN_KEY);
}

type ApiOptions = {
    method?: string;
    body?: unknown; // plain object -> JSON; URLSearchParams -> form-encoded (for login)
    headers?: Record<string, string>;
};

export async function apiFetch<T>(path: string, options: ApiOptions = {}): Promise<T> {
    const headers: Record<string, string> = { ...options.headers };

    // Attach the JWT if we have one, so protected routes accept the request.
    const token = getToken();
    if (token) {
        headers["Authorization"] = `Bearer ${token}`;
    }

    // Choose the encoding: plain objects go as JSON; URLSearchParams are left
    // alone so the browser sets form-encoding, which the OAuth2 login expects.
    let body: BodyInit | undefined;
    if (options.body instanceof URLSearchParams) {
        body = options.body;
    } else if (options.body !== undefined) {
        headers["Content-Type"] = "application/json";
        body = JSON.stringify(options.body);
    }

    const response = await fetch(`${BASE}${path}`, {
        method: options.method ?? "GET",
        headers,
        body,
    });

    // A dead or missing token: drop it and send the user to log in. The guard
    // avoids a redirect loop when the failing call IS the login attempt.
    if (response.status === 401) {
        clearToken();
        if (window.location.pathname !== "/login") {
            window.location.href = "/login";
        }
        throw new Error("Unauthorized");
    }

    if (!response.ok) {
        // FastAPI sends errors as { detail: "..." }; surface that when present.
        const err = await response.json().catch(() => null);
        throw new Error(err?.detail ?? `Request failed: ${response.status}`);
    }

    // 204 No Content (e.g. after a delete) has no body to parse.
    if (response.status === 204) {
        return null as T;
    }

    return response.json() as Promise<T>;
}