import { useEffect, useRef, useState } from "react";
import { apiFetch } from "../api";
import type { Dataset, TrainingRun } from "../types";

const TERMINAL = ["completed", "failed"];

// Train: pick a dataset + iters, start a run, then poll its status every 2s until
// it reaches a terminal state (completed/failed). Polling is the core new pattern.
export default function Train() {
    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [datasetId, setDatasetId] = useState<number | "">("");
    const [iters, setIters] = useState(300);

    const [run, setRun] = useState<TrainingRun | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [starting, setStarting] = useState(false);

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

    // Prove-polling helper: attach the poller to an existing run id (e.g. a finished
    // one) without starting a new run. Lets us validate the machinery instantly.
    function handleAttach(e: React.FormEvent) {
        e.preventDefault();
        const idStr = (new FormData(e.currentTarget as HTMLFormElement).get("existingId") as string) ?? "";
        const id = Number(idStr);
        if (!id) return;
        setError(null);
        startPolling(id);
    }

    return (
        <div>
            <h1>Train</h1>

            <form onSubmit={handleStart}>
                <select
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
                <input
                    type="number"
                    value={iters}
                    onChange={(e) => setIters(Number(e.target.value))}
                    min={1}
                />
                <button type="submit" disabled={starting}>
                    {starting ? "Starting..." : "Start training"}
                </button>
            </form>

            <form onSubmit={handleAttach}>
                <input name="existingId" type="number" placeholder="Poll existing run id" min={1} />
                <button type="submit">Attach to run</button>
            </form>

            {error && <p>Error: {error}</p>}

            {run && (
                <div>
                    <h2>Run #{run.id}</h2>
                    <p>Status: {run.status}</p>
                    <p>Base model: {run.base_model}</p>
                    <p>Iters: {run.iters}</p>
                    {run.completed_at && <p>Completed at: {run.completed_at}</p>}
                    {!TERMINAL.includes(run.status) && <p>Polling every 4s...</p>}
                </div>
            )}
        </div>
    );
}