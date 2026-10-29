import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Box } from "lucide-react";
import { apiFetch } from "../api";
import { displayStatus } from "../statusText";
import ShareToggle, { type Visibility } from "../components/ShareToggle";
import VuMeter from "../components/VuMeter";
import EmptyState from "../components/EmptyState";
import type { FineTunedModel } from "../types";

// Model status -> badge color (a model lands "ready" once it is fused).
const STATUS_CLASS: Record<string, string> = {
    ready: "badge-success",
    completed: "badge-success",
    fused: "badge-success",
};

// Models: the user's fused fine-tuned models. The list itself is read-only,
// but S32 adds the one owner-side mutation: the public/private share toggle.
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

            {loading && (
                <p className="loading">
                    <VuMeter bars={4} /> Loading…
                </p>
            )}
            {error && <p className="form-error" role="alert">{error}</p>}
            {!loading && !error && models.length === 0 && (
                <EmptyState
                    icon={Box}
                    tint="success"
                    title="No fine-tuned models yet"
                    hint="Finish a training run and its fused model lands here, ready to compare."
                    action={
                        <Link className="btn btn-primary" to="/train">
                            Go to Train
                        </Link>
                    }
                />
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
                                <div className="model-actions">
                                    <ShareToggle
                                        kind="model"
                                        id={m.id}
                                        visibility={m.visibility}
                                        name={m.name}
                                        onToggled={(v: Visibility) =>
                                            setModels((prev) => prev.map((x) => (x.id === m.id ? { ...x, visibility: v } : x)))
                                        }
                                        onError={(msg) => setError(msg)}
                                    />
                                    <span className={`badge ${STATUS_CLASS[m.status] ?? "badge-neutral"}`}>
                                        {displayStatus(m.status)}
                                    </span>
                                </div>
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