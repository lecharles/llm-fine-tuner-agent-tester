import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../auth";

// Login form. Controlled inputs (React owns the values via state), submit calls
// the real backend through apiFetch, stores the token, and routes to /datasets.
export default function Login() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const navigate = useNavigate();

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault(); // stop the browser's default full-page form reload
        setError(null);
        setBusy(true);
        try {
            await login(email, password);
            navigate("/get-started"); // token is stored; the guard will now let us in
        } catch (err) {
            setError(err instanceof Error ? err.message : "Login failed");
        } finally {
            setBusy(false);
        }
    }

    return (
        <div>
            <h1>Login</h1>
            <form onSubmit={handleSubmit}>
                <div>
                    <label>
                        Email
                        <input
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                        />
                    </label>
                </div>
                <div>
                    <label>
                        Password
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </label>
                </div>
                <button type="submit" disabled={busy}>
                    {busy ? "Logging in..." : "Log in"}
                </button>
            </form>
            {error && <p>Error: {error}</p>}
            <p>
                No account? <a href="/signup">Sign up</a>
            </p>
        </div>
    );
}