import { useEffect, useState } from "react";
import {
    Cable, Copy, HelpCircle, ShieldAlert, ShieldCheck, Plug, RefreshCw,
} from "lucide-react";
import { apiFetch } from "../api";
import type { BridgeProbeResult, BridgePermission, BridgePermissionCreated } from "../types";
import ConfirmDialog from "../components/ConfirmDialog";
import VuMeter from "../components/VuMeter";

// S25 (issue #28) — the opt-in bridge. The web shell is the consent surface:
// a Mac can only ever touch this account's hardware through one of these
// grants, each scoped to the job kinds ticked here and revocable in one
// click. Nothing here runs on the Mac by itself; the companion dials in
// with a token that only ever appears once, on this page.

const SCOPES: { kind: string; label: string; blurb: string }[] = [
    { kind: "status", label: "status", blurb: "read-only device snapshot (safe)" },
    { kind: "train", label: "train", blurb: "run fine-tunes on this Mac" },
    { kind: "fuse", label: "fuse", blurb: "merge adapters into a model" },
    { kind: "export", label: "export", blurb: "convert/export the fused model" },
    { kind: "serve", label: "serve", blurb: "pull + serve models via Ollama" },
];

function hubUrl(): string {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.host}/companion/ws`;
}

function fmtSeen(iso: string | null): string {
    if (!iso) return "never";
    const t = new Date(iso).getTime();
    const mins = Math.max(0, Math.round((Date.now() - t) / 60000));
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins} min ago`;
    return new Date(iso).toLocaleString();
}

export default function Bridge() {
    const [perms, setPerms] = useState<BridgePermission[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // New-permission form.
    const [name, setName] = useState("");
    const [scopes, setScopes] = useState<string[]>(["status", "train"]);
    const [busy, setBusy] = useState(false);
    const [created, setCreated] = useState<BridgePermissionCreated | null>(null);
    const [copied, setCopied] = useState(false);

    // Per-row actions.
    const [probing, setProbing] = useState<number | null>(null);
    const [probeOut, setProbeOut] = useState<Record<number, BridgeProbeResult>>({});
    const [revokeTarget, setRevokeTarget] = useState<BridgePermission | null>(null);

    async function reload() {
        try {
            setPerms(await apiFetch<BridgePermission[]>("/bridge/permissions"));
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to load bridge permissions");
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        void reload();
        // Online state changes as companions dial in/out: a slow heartbeat.
        const tick = setInterval(() => void reload(), 15000);
        return () => clearInterval(tick);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    function toggleScope(kind: string) {
        setScopes((cur) => (cur.includes(kind) ? cur.filter((s) => s !== kind) : [...cur, kind]));
    }

    async function createPermission(e: React.FormEvent) {
        e.preventDefault();
        if (!name.trim() || scopes.length === 0) return;
        setBusy(true);
        try {
            const out = await apiFetch<BridgePermissionCreated>("/bridge/permissions", {
                method: "POST",
                body: { name: name.trim(), scopes },
            });
            setCreated(out);
            setName("");
            await reload();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Could not create the permission");
        } finally {
            setBusy(false);
        }
    }

    async function copyToken() {
        if (!created) return;
        try {
            await navigator.clipboard.writeText(created.token);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        } catch {
            /* clipboard blocked (http + no permission): the code is on screen anyway */
        }
    }

    async function probe(p: BridgePermission) {
        setProbing(p.id);
        try {
            const out = await apiFetch<BridgeProbeResult>(`/bridge/permissions/${p.id}/probe`, {
                method: "POST",
            });
            setProbeOut((cur) => ({ ...cur, [p.id]: out }));
        } catch (err) {
            setProbeOut((cur) => ({
                ...cur,
                [p.id]: {
                    ok: false,
                    status: "failed",
                    data: {},
                    detail: err instanceof Error ? err.message : "probe failed",
                },
            }));
        } finally {
            setProbing(null);
            void reload();
        }
    }

    async function doRevoke() {
        const p = revokeTarget;
        setRevokeTarget(null);
        if (!p) return;
        try {
            await apiFetch(`/bridge/permissions/${p.id}/revoke`, { method: "POST" });
            await reload();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Could not revoke");
        }
    }

    return (
        <div className="page">
            <div className="page-eyebrow" style={{ color: "var(--accent-guide)" }}>Hardware bridge</div>
            <h1 className="page-title">
                <Cable size={18} style={{ verticalAlign: -2, marginRight: 6 }} />
                Bridge permissions
            </h1>
            <div className="page-sub">
                Let the hosted app use your Mac's GPU, models and files — only where you allowed it,
                only while you say so. Every grant is scoped and one-click revocable.
            </div>

            {loading && (
                <p className="loading"><VuMeter /> Loading bridge…</p>
            )}
            {error && <p className="form-error" role="alert">{error}</p>}

            {/* The consent form: this click is the opt-in. */}
            <form className="card train-config" onSubmit={createPermission}>
                <div className="field">
                    <label className="label" htmlFor="bridge-name">
                        Device name
                        <span className="hint" tabIndex={0} aria-label="About device names">
                            <HelpCircle size={13} />
                            <span className="hint-bubble">
                                Any label you recognise, e.g. "studio-mac". The companion on the Mac
                                announces itself against this grant.
                            </span>
                        </span>
                    </label>
                    <input
                        id="bridge-name"
                        className="input"
                        placeholder="studio-mac"
                        value={name}
                        maxLength={60}
                        onChange={(e) => setName(e.target.value)}
                        required
                    />
                </div>

                <div className="field">
                    <span className="label">Allowed scopes</span>
                    <div className="iters-presets" role="group" aria-label="Allowed scopes">
                        {SCOPES.map((s) => (
                            <button
                                key={s.kind}
                                type="button"
                                className={`chip${scopes.includes(s.kind) ? " chip-active" : ""}`}
                                aria-pressed={scopes.includes(s.kind)}
                                title={s.blurb}
                                onClick={() => toggleScope(s.kind)}
                            >
                                {s.label}
                            </button>
                        ))}
                    </div>
                </div>

                <button className="btn btn-primary" type="submit" disabled={busy || !name.trim() || scopes.length === 0}>
                    <ShieldAlert size={14} /> Grant bridge access
                </button>
            </form>

            {/* One-time pairing sheet: shown immediately after consent, never re-shown. */}
            {created && (
                <div className="card run-explainer" style={{ marginTop: 14 }}>
                    <div className="run-explainer-heading">
                        <Plug size={14} /> Pair “{created.name}” on the Mac — this token is shown once
                    </div>
                    <p className="run-explainer-item">
                        <strong>Pairing token</strong>
                        <span className="bridge-token">
                            <code>{created.token}</code>
                            <button className="btn btn-ghost btn-sm" onClick={copyToken} aria-label="Copy pairing token">
                                <Copy size={13} /> {copied ? "Copied" : "Copy"}
                            </button>
                        </span>
                    </p>
                    <p className="run-explainer-item">
                        <strong>Run on the Mac</strong>
                        <p>
                            In the llm-fine-tuner checkout (or <code>~/.llmtuner</code>):<br />
                            <code>LLMTUNER_PAIRING_TOKEN=*** python companion/companion.py --hub {hubUrl()} --name {created.name}</code>
                        </p>
                    </p>
                    <p className="run-explainer-item run-explainer-fix">
                        Close this sheet when the Mac is paired. If you lose the token, revoke this
                        permission and grant a fresh one.
                        <button className="btn btn-ghost btn-sm" onClick={() => setCreated(null)}>Dismiss</button>
                    </p>
                </div>
            )}

            {!loading && perms.length === 0 && !error && (
                <p className="empty">No devices paired yet. Nothing on the hosted side can reach
                    your Mac until you grant it above.</p>
            )}

            {perms.map((p) => {
                const out = probeOut[p.id];
                return (
                    <div key={p.id} className="card run-card" style={{ marginTop: 12 }}>
                        <div className="run-head">
                            <span className="run-id">{p.name}</span>
                            <span className={`badge ${p.status === "active" ? (p.online ? "badge-success" : "badge-info") : "badge-neutral"}`}>
                                {p.status === "active" && p.online && <span className="pulse-dot" />}
                                {p.status === "active" ? (p.online ? "online" : "granted · offline") : "revoked"}
                            </span>
                            <span className="run-meta">seen {fmtSeen(p.last_seen_at)}</span>
                        </div>
                        <div className="run-meta">
                            scopes: {p.scopes.join(", ")}
                        </div>
                        {p.status === "active" && (
                            <div className="cell-actions">
                                <button
                                    className="btn btn-ghost btn-sm"
                                    onClick={() => probe(p)}
                                    disabled={probing === p.id || !p.scopes.includes("status")}
                                    title={p.scopes.includes("status") ? "Ask the Mac for a status snapshot" : "Grant the status scope to probe"}
                                >
                                    <RefreshCw size={13} /> {probing === p.id ? "Probing…" : "Probe"}
                                </button>
                                <button className="btn btn-danger btn-sm" onClick={() => setRevokeTarget(p)}>
                                    Revoke
                                </button>
                            </div>
                        )}
                        {out && (
                            <p className={out.ok ? "run-explainer-fix" : "run-error"} style={{ marginTop: 8 }}>
                                {out.ok ? (
                                    <>
                                        <ShieldCheck size={13} /> platform={String(out.data.capabilities ? (out.data.capabilities as Record<string, unknown>).platform ?? "?" : "?")} ·
                                        backend {out.data.backend_up ? "up" : "down"} · mlx_lm {JSON.stringify((out.data.capabilities as Record<string, unknown> | undefined)?.mlx_lm ?? "?")}
                                    </>
                                ) : (
                                    <>probe failed: {out.detail}</>
                                )}
                            </p>
                        )}
                    </div>
                );
            })}

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
