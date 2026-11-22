import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
    Cable, Clock3, HelpCircle, KeyRound, Save, Settings as SettingsIcon, ShieldCheck,
} from "lucide-react";
import { apiFetch } from "../api";
import ConfirmDialog from "../components/ConfirmDialog";
import type { BridgePermission, PasswordChangeResult, SessionInfo } from "../types";

// S64 — the Settings page: the account things that had no home. Display
// name and password live here (email stays read-only: it IS the login key,
// and lane/local identities are synthetic). The session card answers
// "what am I signed in with and when does it die" straight from the
// server's decode of this very token — JWT, service lane, or local mode —
// instead of guessing. Bridge grants are listed and revocable here too:
// "who can reach my Mac" is a settings question as much as a bridge one,
// and revocation should never be more than one honest click from anywhere.

type Me = { id: number; email: string; display_name: string | null; created_at: string };

function fmtSeen(iso: string | null): string {
    if (!iso) return "never";
    const t = new Date(iso).getTime();
    const mins = Math.max(0, Math.round((Date.now() - t) / 60000));
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins} min ago`;
    return new Date(iso).toLocaleString();
}

const MODE_META: Record<SessionInfo["mode"], { label: string; badge: string }> = {
    jwt: { label: "user JWT", badge: "badge-info" },
    service_lane: { label: "service lane token", badge: "badge-warning" },
    local: { label: "local mode", badge: "badge-neutral" },
    other: { label: "opaque token", badge: "badge-neutral" },
};

export default function Settings() {
    const [me, setMe] = useState<Me | null>(null);
    const [session, setSession] = useState<SessionInfo | null>(null);
    const [perms, setPerms] = useState<BridgePermission[]>([]);
    const [error, setError] = useState<string | null>(null);

    // Account form.
    const [name, setName] = useState("");
    const [nameBusy, setNameBusy] = useState(false);
    const [nameOk, setNameOk] = useState(false);

    // Password form.
    const [curPw, setCurPw] = useState("");
    const [newPw, setNewPw] = useState("");
    const [confirmPw, setConfirmPw] = useState("");
    const [pwBusy, setPwBusy] = useState(false);
    const [pwError, setPwError] = useState<string | null>(null);
    const [pwOkTtl, setPwOkTtl] = useState<number | null>(null);

    // Bridge revoke.
    const [revokeTarget, setRevokeTarget] = useState<BridgePermission | null>(null);

    useEffect(() => {
        // One load on mount: /me seeds the form, /session and the bridge
        // rows render straight from the server. Actions refresh what they
        // changed (and only that), so a background refresh can never
        // stomp a half-typed display name.
        (async () => {
            try {
                const [meOut, sessOut, permOut] = await Promise.all([
                    apiFetch<Me>("/auth/me"),
                    apiFetch<SessionInfo>("/auth/session"),
                    apiFetch<BridgePermission[]>("/bridge/permissions"),
                ]);
                setMe(meOut);
                setName(meOut.display_name ?? "");
                setSession(sessOut);
                setPerms(permOut);
                setError(null);
            } catch (err) {
                setError(err instanceof Error ? err.message : "Failed to load settings");
            }
        })();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    async function reloadPerms() {
        try {
            setPerms(await apiFetch<BridgePermission[]>("/bridge/permissions"));
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to reload bridge permissions");
        }
    }

    async function saveName(e: React.FormEvent) {
        e.preventDefault();
        if (!name.trim()) return;
        setNameBusy(true);
        setNameOk(false);
        try {
            const out = await apiFetch<Me>("/auth/me", {
                method: "PATCH",
                body: { display_name: name.trim() },
            });
            setMe(out);
            setName(out.display_name ?? "");
            setNameOk(true);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Could not save the display name");
        } finally {
            setNameBusy(false);
        }
    }

    async function changePassword(e: React.FormEvent) {
        e.preventDefault();
        setPwError(null);
        setPwOkTtl(null);
        if (newPw.length < 8) {
            setPwError("New password must be at least 8 characters.");
            return;
        }
        if (newPw !== confirmPw) {
            setPwError("The new passwords do not match.");
            return;
        }
        setPwBusy(true);
        try {
            const out = await apiFetch<PasswordChangeResult>("/auth/password", {
                method: "POST",
                body: { current_password: curPw, new_password: newPw },
            });
            setCurPw("");
            setNewPw("");
            setConfirmPw("");
            setPwOkTtl(out.jwt_ttl_minutes);
        } catch (err) {
            setPwError(err instanceof Error ? err.message : "Could not change the password");
        } finally {
            setPwBusy(false);
        }
    }

    async function doRevoke() {
        const p = revokeTarget;
        setRevokeTarget(null);
        if (!p) return;
        try {
            await apiFetch(`/bridge/permissions/${p.id}/revoke`, { method: "POST" });
            await reloadPerms();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Could not revoke");
        }
    }

    const nameDirty = (me?.display_name ?? "") !== name.trim() && name.trim() !== "";
    const pwReady = curPw !== "" && newPw.length >= 8 && confirmPw !== "";
    const modeMeta = session ? MODE_META[session.mode] : null;

    return (
        <div className="page">
            <div className="page-eyebrow" style={{ color: "var(--info)" }}>Account</div>
            <h1 className="page-title">
                <SettingsIcon size={18} style={{ verticalAlign: -2, marginRight: 6 }} />
                Settings
            </h1>
            <div className="page-sub">
                Your name on the community library, the password that signs you in,
                what this session runs on, and who can reach your Mac.
            </div>

            {error && <p className="form-error" role="alert">{error}</p>}

            {/* 1 — account: display name (email is read-only, it is the login key). */}
            <form className="card train-config" onSubmit={saveName}>
                <div className="section-title">Account</div>
                <div className="field">
                    <label className="label" htmlFor="settings-name">
                        Display name
                        {/* S65 (#38): contextual help, reusing the S30 hint pattern. */}
                        <span className="hint" tabIndex={0} aria-label="About the display name">
                            <HelpCircle size={13} />
                            <span className="hint-bubble">
                                This is how your shared datasets and models are credited in the Library — including
                                the owner line on their detail pages. 1–60 characters.
                            </span>
                        </span>
                    </label>
                    <input
                        id="settings-name"
                        className="input"
                        placeholder={me?.email ?? "Your name"}
                        value={name}
                        maxLength={60}
                        onChange={(e) => { setName(e.target.value); setNameOk(false); }}
                    />
                </div>
                <div className="field">
                    <span className="label">
                        Email
                        {/* S65 (#38): contextual help, reusing the S30 hint pattern. */}
                        <span className="hint" tabIndex={0} aria-label="About the email field">
                            <HelpCircle size={13} />
                            <span className="hint-bubble">
                                The email is your login key, so it is deliberately read-only here. Lane and local
                                identities are synthetic — signing in another way shows that address instead.
                            </span>
                        </span>
                    </span>
                    <input className="input" value={me?.email ?? "…"} readOnly aria-readonly="true" />
                </div>
                {me && (
                    <div className="run-meta">member since {new Date(me.created_at).toLocaleDateString()}</div>
                )}
                <button className="btn btn-primary" type="submit" disabled={nameBusy || !nameDirty}>
                    <Save size={14} /> {nameBusy ? "Saving…" : "Save name"}
                </button>
                {nameOk && <span className="run-explainer-fix" style={{ marginLeft: 10 }}>Saved.</span>}
            </form>

            {/* 2 — password rotation. The success note is honest about the
                stateless-JWT window instead of promising instant global sign-out. */}
            <form className="card train-config" onSubmit={changePassword} style={{ marginTop: 12 }}>
                <div className="section-title">Password</div>
                {pwError && <p className="form-error" role="alert">{pwError}</p>}
                {pwOkTtl !== null && (
                    <p className="run-explainer-fix" role="status">
                        <ShieldCheck size={13} /> Password changed. This device keeps working;
                        tokens issued to other devices expire on their own within {pwOkTtl} min.
                    </p>
                )}
                <div className="field">
                    <label className="label" htmlFor="pw-current">Current password</label>
                    <input
                        id="pw-current"
                        className="input"
                        type="password"
                        autoComplete="current-password"
                        value={curPw}
                        onChange={(e) => { setCurPw(e.target.value); setPwOkTtl(null); }}
                        required
                    />
                </div>
                <div className="field">
                    <label className="label" htmlFor="pw-new">New password</label>
                    <input
                        id="pw-new"
                        className="input"
                        type="password"
                        autoComplete="new-password"
                        value={newPw}
                        minLength={8}
                        onChange={(e) => { setNewPw(e.target.value); setPwOkTtl(null); }}
                        required
                    />
                </div>
                <div className="field">
                    <label className="label" htmlFor="pw-confirm">Repeat new password</label>
                    <input
                        id="pw-confirm"
                        className="input"
                        type="password"
                        autoComplete="new-password"
                        value={confirmPw}
                        onChange={(e) => { setConfirmPw(e.target.value); setPwOkTtl(null); }}
                        required
                    />
                </div>
                <button className="btn btn-primary" type="submit" disabled={pwBusy || !pwReady}>
                    <KeyRound size={14} /> {pwBusy ? "Changing…" : "Change password"}
                </button>
            </form>

            {/* 3 — session: the server's own decode of the token making this call. */}
            <div className="card train-config" style={{ marginTop: 12 }}>
                <div className="section-title">
                    Session
                    {/* S65 (#38): contextual help, reusing the S30 hint pattern. */}
                    <span className="hint" tabIndex={0} aria-label="About the session card">
                        <HelpCircle size={13} />
                        <span className="hint-bubble">
                            The server decodes the token making this very request — nothing is stored or guessed.
                            Password changes do not sign other devices out on the spot; their tokens expire on
                            their own inside this window.
                        </span>
                    </span>
                </div>
                {session && modeMeta ? (
                    <>
                        <div className="run-head">
                            <span className="run-id">Signed in via</span>
                            <span className={`badge ${modeMeta.badge}`}>{modeMeta.label}</span>
                        </div>
                        <div className="run-meta">
                            {session.mode === "jwt" && (
                                <>
                                    user id {session.subject} · signed with {session.algorithm} ·
                                    expires{" "}
                                    {session.expires_at ? new Date(session.expires_at).toLocaleString() : "unknown"}
                                    {session.expires_in_seconds !== null &&
                                        ` · in about ${Math.max(1, Math.round(session.expires_in_seconds / 60))} min`}
                                </>
                            )}
                            {session.mode === "service_lane" && (
                                <>lane “{session.lane}” — a long-lived ops token, not a login</>
                            )}
                            {session.mode === "local" && (
                                <>local single-user mode — no JWT on this machine</>
                            )}
                            {session.mode === "other" && (
                                <>the bearer in use is not a user JWT, not a lane, not local mode</>
                            )}
                        </div>
                        <div className="run-meta">
                            <Clock3 size={12} style={{ verticalAlign: -1 }} /> user tokens live {session.jwt_ttl_minutes} min; signing out clears this device only.
                        </div>
                    </>
                ) : (
                    <div className="run-meta">Loading session…</div>
                )}
            </div>

            {/* 4 — bridge grants, listed + revocable from the settings seat. */}
            <div className="card train-config" style={{ marginTop: 12 }}>
                <div className="section-title">
                    <Cable size={14} style={{ verticalAlign: -2 }} /> Bridge permissions
                    {/* S65 (#38): contextual help, reusing the S30 hint pattern. */}
                    <span className="hint" tabIndex={0} aria-label="About bridge permissions">
                        <HelpCircle size={13} />
                        <span className="hint-bubble">
                            Grants let a paired Mac answer this account&rsquo;s bridge requests. Revoke is
                            instant: the live connection dies on the spot and the pairing token stops working —
                            the Mac needs a fresh grant to come back.
                        </span>
                    </span>
                </div>
                {perms.length === 0 && (
                    <div className="run-meta">
                        No Mac is granted access. Pair one from the Bridge page.
                    </div>
                )}
                {perms.map((p) => (
                    <div key={p.id} className="run-card" style={{ marginTop: 10 }}>
                        <div className="run-head">
                            <span className="run-id">{p.name}</span>
                            <span className={`badge ${p.status === "active" ? (p.online ? "badge-success" : "badge-info") : "badge-neutral"}`}>
                                {p.status === "active" && p.online && <span className="pulse-dot" />}
                                {p.status === "active" ? (p.online ? "online" : "granted · offline") : "revoked"}
                            </span>
                            <span className="run-meta">seen {fmtSeen(p.last_seen_at)}</span>
                        </div>
                        <div className="run-meta">scopes: {p.scopes.join(", ")}</div>
                        {p.status === "active" && (
                            <div className="cell-actions">
                                <button className="btn btn-danger btn-sm" onClick={() => setRevokeTarget(p)}>
                                    Revoke
                                </button>
                            </div>
                        )}
                    </div>
                ))}
                <p className="run-meta" style={{ marginTop: 10 }}>
                    <Link to="/bridge">Open the Bridge page</Link> to grant a new device or probe one.
                </p>
            </div>

            <ConfirmDialog
                open={revokeTarget !== null}
                title="Revoke bridge access"
                confirmLabel="Revoke"
                message={
                    <>
                        Immediately cut <strong>{revokeTarget?.name}</strong>'s hardware access?
                        Its live connection is closed on the spot, the pairing token stops working,
                        and the Mac must be re-paired with a fresh grant to come back.
                    </>
                }
                onConfirm={doRevoke}
                onCancel={() => setRevokeTarget(null)}
            />
        </div>
    );
}
