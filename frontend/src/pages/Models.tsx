import { useEffect, useState } from "react";
import { apiFetch } from "../api";
import type { FineTunedModel } from "../types";

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
        <div>
            <h1>Models</h1>

            {loading && <p>Loading...</p>}
            {error && <p>Error: {error}</p>}

            {!loading && !error && models.length === 0 && <p>No fine-tuned models yet.</p>}

            {!loading && !error && models.length > 0 && (
                <ul>
                    {models.map((m) => (
                        <li key={m.id}>
                            {m.name} — base: {m.base_model} — {m.status}
                            {m.size_mb !== null && <> — {m.size_mb} MB</>} — from run #{m.training_run_id}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}