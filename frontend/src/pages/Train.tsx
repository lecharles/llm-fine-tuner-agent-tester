import { useEffect, useRef, useState } from "react";
import { Play, HelpCircle } from "lucide-react";
import { apiFetch } from "../api";
import type { Dataset, TrainingRun } from "../types";

const TERMINAL = ["completed", "failed"];

// Map a run's status to its badge color.
const STATUS_CLASS: Record<string, string> = {
    queued: "badge-neutral",
    running: "badge-warning",
    completed: "badge-success",
    failed: "badge-danger",
};

// Train: pick a dataset + iters, start a run, then poll its status every 2s until
// it reaches a terminal state (completed/failed). Polling is the core new pattern.
export default function Train() {
    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [datasetId, setDatasetId] = useState<number | "">("");
    const [iters, setIters] = useState(300);

    const [run, setRun] = useState<TrainingRun | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [starting, setStarting] = useState(false);
    const [attachId, setAttachId] = useState("");

    // A ref holds the interval id across renders without triggering re-renders.
    const pollRef = useRef<number | null>(null);

    // Load datasets for the picker.
    useEffect(() => {
        apiFetch<Dataset[]>("/datasets")
            .then(setDatasets)
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to load datasets"));
    }, []);

    // Cleanup: if the component unmounts mid-poll, stop the interval.
    useEffect(() => {
        return () => {
            if (pollRef.current !== null) clearInterval(pollRef.current);
        };
    }, []);

    function stopPolling() {
        if (pollRef.current !== null) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    }

    // Ask the backend for this run's latest state; stop once it's terminal.
    function pollOnce(id: number) {
        apiFetch<TrainingRun>(`/training-runs/${id}`)
            .then((latest) => {
                setRun(latest);
                if (TERMINAL.includes(latest.status)) stopPolling();
            })
            .catch((err) => {
                setError(err instanceof Error ? err.message : "Poll failed");
                stopPolling();
            });
    }

    // Begin polling a run every 4s (and immediately once, so the UI updates fast).
    function startPolling(id: number) {
        stopPolling();
        pollOnce(id);
        pollRef.current = window.setInterval(() => pollOnce(id), 4000);
    }

    async function handleStart(e: React.FormEvent) {
        e.preventDefault();
        if (datasetId === "") return;
        setStarting(true);
        setError(null);
        try {
            const created = await apiFetch<TrainingRun>("/training-runs", {
                method: "POST",
                body: { dataset_id: datasetId, iters },
            });
            setRun(created);
            startPolling(created.id); // walk queued -> running -> completed/failed live
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to start run");
        } finally {
            setStarting(false);
        }
    }

    // Utility: attach the poller to an existing run id without starting a new run.
    // Handy for resuming after a refresh, or showing a finished run instantly.
    function handleAttach(e: React.FormEvent) {
        e.preventDefault();
        const id = Number(attachId);
        if (!id) return;
        setError(null);
        startPolling(id);
    }

    return (
        <div className="page">
            <div className="page-eyebrow" style={{ color: "var(--warning)" }}>Fine-tune</div>
            <h1 className="page-title">Train</h1>

            <form className="card train-config" onSubmit={handleStart}>
                <div className="field">
                    <label className="label">Dataset</label>
                    <select
                        className="select"
                        value={datasetId}
                        onChange={(e) => setDatasetId(e.target.value === "" ? "" : Number(e.target.value))}
                        required
                    >
                        <option value="">Select a dataset</option>
                        {datasets.map((d) => (
                            <option key={d.id} value={d.id}>
                                {d.name}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="config-row">
                    <div className="field field-iters">
                        <label className="label">
                            Iters
                            <span className="hint">
                                <HelpCircle size={13} />
                                <span className="hint-bubble">
                                    Training steps. More iters means more learning but a longer run. 200 to 400 is a good start.
                                </span>
                            </span>
                        </label>
                        <input
                            className="input"
                            type="number"
                            value={iters}
                            onChange={(e) => setIters(Number(e.target.value))}
                            min={1}
                        />
                    </div>
                    <button type="submit" className="btn btn-primary" disabled={starting || datasetId === ""}>
                        <Play size={16} /> {starting ? "Starting…" : "Start training"}
                    </button>
                </div>
            </form>

            {error && <p className="form-error">{error}</p>}

            {run && (
                <div className="card run-card">
                    <div className="run-head">
                        <span className="run-id">Run #{run.id}</span>
                        <span className={`badge ${STATUS_CLASS[run.status] ?? "badge-neutral"}`}>
                            {run.status === "running" && <span className="pulse-dot" />}
                            {run.status}
                        </span>
                    </div>
                    <div className="run-meta">
                        {run.base_model} · {run.method} · {run.iters} iters
                    </div>
                    {run.completed_at && (
                        <div className="run-meta">Completed {new Date(run.completed_at).toLocaleString()}</div>
                    )}
                </div>
            )}

            <form className="attach" onSubmit={handleAttach}>
                <span className="attach-label">Resume a run</span>
                <input
                    className="input attach-input"
                    type="number"
                    placeholder="Run id"
                    min={1}
                    value={attachId}
                    onChange={(e) => setAttachId(e.target.value)}
                />
                <button type="submit" className="btn btn-ghost btn-sm">Attach</button>
            </form>
        </div>
    );
}