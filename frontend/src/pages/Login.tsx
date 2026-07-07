import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { SlidersHorizontal } from "lucide-react";
import { login } from "../auth";

// Login form. Controlled inputs (React owns the values via state); submit calls
// the real backend through apiFetch, stores the token, and routes to /get-started.
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
        <div className="auth">
            <div className="auth-card">
                <div className="auth-brand">
                    <span className="auth-mark"><SlidersHorizontal size={22} /></span>
                    <div className="auth-title">LLM Tuner</div>
                    <div className="auth-tagline">Fine-tune an LLM as easily as tuning a guitar.</div>
                </div>
                <form onSubmit={handleSubmit}>
                    <div className="field">
                        <label className="label">Email</label>
                        <input
                            className="input"
                            type="email"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            required
                            autoFocus
                        />
                    </div>
                    <div className="field">
                        <label className="label">Password</label>
                        <input
                            className="input"
                            type="password"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            required
                        />
                    </div>
                    {error && <p className="form-error">{error}</p>}
                    <button type="submit" className="btn btn-primary auth-submit" disabled={busy}>
                        {busy ? "Logging in…" : "Log in"}
                    </button>
                </form>
                <div className="auth-alt">
                    No account? <Link to="/signup">Sign up</Link>
                </div>
            </div>
        </div>
    );
}