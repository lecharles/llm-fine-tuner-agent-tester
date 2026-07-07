import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { SlidersHorizontal } from "lucide-react";
import { signup } from "../auth";

// Signup form. Creates the account, then auth.ts logs in automatically, so the
// user lands authenticated on /get-started rather than back at a login form.
export default function Signup() {
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState<string | null>(null);
    const [busy, setBusy] = useState(false);
    const navigate = useNavigate();

    async function handleSubmit(e: React.FormEvent) {
        e.preventDefault();
        setError(null);
        setBusy(true);
        try {
            await signup(email, password);
            navigate("/get-started");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Signup failed");
        } finally {
            setBusy(false);
        }
    }

    return (
        <div className="auth">
            <div className="auth-card">
                <div className="auth-brand">
                    <span className="auth-mark"><SlidersHorizontal size={22} /></span>
                    <div className="auth-title">Create your account</div>
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
                        {busy ? "Creating…" : "Sign up"}
                    </button>
                </form>
                <div className="auth-alt">
                    Have an account? <Link to="/login">Log in</Link>
                </div>
            </div>
        </div>
    );
}