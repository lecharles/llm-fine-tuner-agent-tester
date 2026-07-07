import { useEffect, useState } from "react";
import { Box } from "lucide-react";
import { apiFetch } from "../api";
import type { FineTunedModel } from "../types";

// Model status -> badge color (a model lands "ready" once it is fused).
const STATUS_CLASS: Record<string, string> = {
    ready: "badge-success",
    completed: "badge-success",
    fused: "badge-success",
};

// Models: read-only list of the user's fused fine-tuned models. Same
// fetch-on-mount + map pattern as the Datasets read; no mutations here.
export default function Models() {
    const [models, setModels] = useState<FineTunedModel[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        apiFetch<FineTunedModel[]>("/fine-tuned-models")
            .then(setModels)
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to load models"))
            .finally(() => setLoading(false));
    }, []);

    return (
        <div className="page">
            <div className="page-eyebrow" style={{ color: "var(--success)" }}>Fine-tuned</div>
            <h1 className="page-title">Models</h1>
            {!loading && !error && models.length > 0 && (
                <div className="page-sub">
                    {models.length} model{models.length !== 1 ? "s" : ""} from your training runs.
                </div>
            )}

            {loading && <p className="loading">Loading…</p>}
            {error && <p className="form-error">{error}</p>}
            {!loading && !error && models.length === 0 && (
                <p className="empty">No fine-tuned models yet. Train one to see it here.</p>
            )}

            {!loading && !error && models.length > 0 && (
                <div className="models-list">
                    {models.map((m) => (
                        <div className="card" key={m.id}>
                            <div className="model-head">
                                <div className="model-id">
                                    <span className="model-icon">
                                        <Box size={18} />
                                    </span>
                                    <div>
                                        <div className="model-name">{m.name}</div>
                                        <div className="model-sub">from run #{m.training_run_id}</div>
                                    </div>
                                </div>
                                <span className={`badge ${STATUS_CLASS[m.status] ?? "badge-neutral"}`}>
                                    {m.status}
                                </span>
                            </div>
                            <div className="model-meta">
                                <span>base <b>{m.base_model}</b></span>
                                {m.size_mb !== null && <span>size <b>{m.size_mb} MB</b></span>}
                                {m.format && <span>format <b>{m.format}</b></span>}
                                <span>created <b>{new Date(m.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}</b></span>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}