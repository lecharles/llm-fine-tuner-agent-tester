import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { signup } from "../auth";

// Signup form. Creates the account, then auth.ts logs in automatically, so the
// user lands authenticated on /datasets rather than back at a login form.
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
            navigate("/datasets");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Signup failed");
        } finally {
            setBusy(false);
        }
    }

    return (
        <div>
            <h1>Sign up</h1>
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
                    {busy ? "Creating..." : "Sign up"}
                </button>
            </form>
            {error && <p>Error: {error}</p>}
            <p>
                Have an account? <a href="/login">Log in</a>
            </p>
        </div>
    );
}