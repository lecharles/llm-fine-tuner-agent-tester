import { apiFetch, setToken } from "./api";

// The login endpoint is OAuth2, so it wants form fields (not JSON): the
// username field carries the email. apiFetch sends URLSearchParams as a form.
type TokenResponse = { access_token: string; token_type: string };

export async function login(email: string, password: string): Promise<void> {
    const form = new URLSearchParams();
    form.set("username", email);
    form.set("password", password);
    const data = await apiFetch<TokenResponse>("/auth/login", {
        method: "POST",
        body: form,
    });
    setToken(data.access_token);
}

// Signup takes JSON. On success it returns the created user; we then log in
// with the same credentials so the user lands authenticated, not at a login form.
type User = { id: number; email: string };

export async function signup(email: string, password: string): Promise<void> {
    await apiFetch<User>("/auth/signup", {
        method: "POST",
        body: { email, password },
    });
    await login(email, password);
}

// Phase 6 slice 3: check if the app is running in local mode.
// If yes, auto-login with the local user so the frontend skips the login screen.
type AuthConfig = { local_mode: boolean };

export async function checkLocalMode(): Promise<boolean> {
    try {
        const config = await apiFetch<AuthConfig>("/auth/config");
        return config.local_mode;
    } catch {
        return false;
    }
}

export async function autoLoginLocal(): Promise<void> {
    // In local mode, the backend auto-provisions local@llmtuner and bypasses JWT.
    // We just need to set a dummy token so the frontend thinks we're authenticated.
    setToken("local-mode-bypass");
}