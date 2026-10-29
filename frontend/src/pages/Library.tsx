import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Box, Database, Library as LibraryIcon } from "lucide-react";
import { apiFetch } from "../api";
import { displayStatus } from "../statusText";
import VuMeter from "../components/VuMeter";
import EmptyState from "../components/EmptyState";
import type { LibraryPayload } from "../types";

// S32 (sharing 2): the public library. Everything the community shared via the
// S31 toggles, read-only. Datasets link to their detail page (the backend's
// owner-or-public read lets non-owners see metadata + Q&A pairs); models stay
// metadata cards — chatting with someone else's model is deliberately not a
// public action.
export default function Library() {
    const [lib, setLib] = useState<LibraryPayload | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        apiFetch<LibraryPayload>("/library")
            .then(setLib)
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to load the library"))
            .finally(() => setLoading(false));
    }, []);

    const empty = lib && lib.datasets.length === 0 && lib.models.length === 0;

    return (
        <div className="page">
            <div className="page-eyebrow" style={{ color: "var(--info)" }}>Community</div>
            <h1 className="page-title">Library</h1>
            <div className="page-sub">
                Datasets and models shared publicly by other members. Reading is open; editing stays with the owner.
            </div>

            {loading && (
                <p className="loading">
                    <VuMeter bars={4} /> Loading…
                </p>
            )}
            {error && <p className="form-error" role="alert">{error}</p>}
            {empty && (
                <EmptyState
                    icon={LibraryIcon}
                    tint="info"
                    title="Nothing shared yet"
                    hint={<>Flip the <strong>Share</strong> toggle on one of your datasets or models and it will appear here for everyone.</>}
                />
            )}

            {lib && lib.datasets.length > 0 && (
                <section className="library-section" aria-labelledby="library-datasets">
                    <h2 className="section-title" id="library-datasets">
                        <Database size={15} style={{ color: "var(--info)" }} /> Shared datasets
                    </h2>
                    <div className="card-grid">
                        {lib.datasets.map((d) => (
                            <div className="card" key={d.id}>
                                <div className="library-row">
                                    <Link to={`/datasets/${d.id}`} className="row-name">
                                        {d.name}
                                    </Link>
                                    <span className="badge badge-neutral">{displayStatus(d.source)}</span>
                                </div>
                                {d.description && <div className="row-sub">{d.description}</div>}
                                <div className="model-meta">
                                    <span>by <b>{d.owner}</b></span>
                                    <span>
                                        shared{" "}
                                        <b>
                                            {new Date(d.created_at).toLocaleDateString(undefined, {
                                                month: "short",
                                                day: "numeric",
                                            })}
                                        </b>
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </section>
            )}

            {lib && lib.models.length > 0 && (
                <section className="library-section" aria-labelledby="library-models">
                    <h2 className="section-title" id="library-models">
                        <Box size={15} style={{ color: "var(--success)" }} /> Shared models
                    </h2>
                    <div className="card-grid">
                        {lib.models.map((m) => (
                            <div className="card" key={m.id}>
                                <div className="library-row">
                                    <span className="row-name">{m.name}</span>
                                    <span className="badge badge-success">{displayStatus(m.status)}</span>
                                </div>
                                <div className="model-meta">
                                    <span>base <b>{m.base_model}</b></span>
                                    {m.size_mb !== null && <span>size <b>{m.size_mb} MB</b></span>}
                                    <span>by <b>{m.owner}</b></span>
                                </div>
                            </div>
                        ))}
                    </div>
                </section>
            )}
        </div>
    );
}
