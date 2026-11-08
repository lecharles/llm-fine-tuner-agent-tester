import { useEffect, useRef, useState } from "react";
import { Play, HelpCircle, SlidersHorizontal, Cable } from "lucide-react";
import { apiFetch } from "../api";
import { displayStatus } from "../statusText";
import LossChart from "../components/LossChart";
import type {
    BridgePermission,
    BridgeTrainAccepted,
    BridgeTrainJob,
    Dataset,
    ErrorExplanation,
    LossPoint,
    TrainingRun,
} from "../types";

const TERMINAL = ["completed", "failed"];

// S17: iters input guard rails + quick presets (10-20 smoke, 200-400 sweet
// spot per the quickstart guidance; 1000 for a proper run).
const DEFAULT_ITERS = 300;
const clampIters = (v: number) => Math.min(5000, Math.max(1, Math.round(v)));
const ITERS_PRESETS = [
    { value: 20, label: "smoke" },
    { value: 300, label: "recommended" },
    { value: 1000, label: "full run" },
];

// S34 (#35): advanced hyperparameter panel. Defaults mirror the backend's
// (mlx_lm.lora's own 8/16 rank/alpha; learning rate left unset = mlx picks).
// Bounds mirror the S33 schema, so the UI never sends a value 422s on.
const DEFAULT_LORA_RANK = 8;
const DEFAULT_LORA_ALPHA = 16;
const clampRank = (v: number) => Math.min(128, Math.max(1, Math.round(v)));
const clampAlpha = (v: number) => Math.min(256, Math.max(1, Math.round(v)));
const RANK_PRESETS = [4, 8, 16, 32];
const ALPHA_PRESETS = [8, 16, 32, 64];

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
    const [iters, setIters] = useState(DEFAULT_ITERS);
    const [loraRank, setLoraRank] = useState(DEFAULT_LORA_RANK);
    const [loraAlpha, setLoraAlpha] = useState(DEFAULT_LORA_ALPHA);
    const [lrText, setLrText] = useState(""); // empty = let mlx pick
    const [advancedOpen, setAdvancedOpen] = useState(false);

    const [run, setRun] = useState<TrainingRun | null>(null);
    const [losses, setLosses] = useState<LossPoint[]>([]);
    const [explains, setExplains] = useState<ErrorExplanation[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [starting, setStarting] = useState(false);
    const [attachId, setAttachId] = useState("");

    // S50: the train handoff — "Train on this Mac" button + live job card.
    const [macPerms, setMacPerms] = useState<BridgePermission[]>([]);
    const [macPermId, setMacPermId] = useState<number | "">("");
    const [macJob, setMacJob] = useState<BridgeTrainJob | null>(null);
    const [macStarting, setMacStarting] = useState(false);
    const macJobIdRef = useRef<string | null>(null);
    const macPollRef = useRef<number | null>(null);

    // A ref holds the interval id across renders without triggering re-renders.
    const pollRef = useRef<number | null>(null);

    // Load datasets for the picker.
    useEffect(() => {
        apiFetch<Dataset[]>("/datasets")
            .then(setDatasets)
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to load datasets"));
    }, []);

    // S50: load online bridge permissions with train scope for the Mac picker.
    useEffect(() => {
        apiFetch<BridgePermission[]>("/bridge/permissions")
            .then((perms) => {
                const online = perms.filter(
                    (p) => p.status === "active" && p.online && p.scopes.includes("train")
                );
                setMacPerms(online);
                if (online.length > 0 && macPermId === "") {
                    setMacPermId(online[0].id);
                }
            })
            .catch(() => undefined); // bridge is optional; swallow
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // Cleanup: if the component unmounts mid-poll, stop the interval.
    useEffect(() => {
        return () => {
            if (pollRef.current !== null) clearInterval(pollRef.current);
            if (macPollRef.current !== null) clearInterval(macPollRef.current);
        };
    }, []);

    // S29 (issue #33): once a failed run carries error text, ask the backend
    // to map it to human cause + fix. Fetch failures are swallowed — the raw
    // error box already shows the truth, the explainer is a courtesy.
    useEffect(() => {
        if (!run || run.status !== "failed" || !run.error_message) {
            setExplains([]);
            return;
        }
        apiFetch<ErrorExplanation[]>(`/training-runs/${run.id}/explain`)
            .then(setExplains)
            .catch(() => setExplains([]));
    }, [run]);

    function stopPolling() {
        if (pollRef.current !== null) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }
    }

    // Ask the backend for this run's latest state; stop once it's terminal.
    function pollOnce(id: number) {
        // S11 (issue #4): the loss curve rides the same tick. A failed/empty
        // losses fetch must never kill the status poll, so errors are swallowed
        // here (queued runs legitimately have no train.log yet).
        apiFetch<LossPoint[]>(`/training-runs/${id}/losses`)
            .then(setLosses)
            .catch(() => undefined);
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
        setLosses([]); // fresh curve for the fresh run
        // S34: validate the learning rate client-side (mirrors the S33 schema
        // bound 0 < lr <= 1) so a typo shows our words, not FastAPI's.
        let learningRate: number | null = null;
        if (lrText.trim() !== "") {
            const v = Number(lrText);
            if (!Number.isFinite(v) || v <= 0 || v > 1) {
                setError("Learning rate must be a number between 0 and 1 (e.g. 0.00002), or leave it blank.");
                setStarting(false);
                return;
            }
            learningRate = v;
        }
        try {
            const created = await apiFetch<TrainingRun>("/training-runs", {
                method: "POST",
                body: {
                    dataset_id: datasetId,
                    iters,
                    lora_rank: loraRank,
                    lora_alpha: loraAlpha,
                    ...(learningRate !== null ? { learning_rate: learningRate } : {}),
                },
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
        setLosses([]); // avoid flashing the previous run's curve
        startPolling(id);
    }

    // S50: the Mac train handoff. POST the job, then poll the hub for the
    // streamed events + loss curve until the companion reports a terminal
    // result (done/failed) or the user navigates away.
    function stopMacPolling() {
        if (macPollRef.current !== null) {
            clearInterval(macPollRef.current);
            macPollRef.current = null;
        }
    }

    function pollMacJob(jobId: string) {
        apiFetch<BridgeTrainJob>(`/bridge/jobs/${jobId}`)
            .then((job) => {
                setMacJob(job);
                if (job.status === "done" || job.status === "failed") {
                    stopMacPolling();
                }
            })
            .catch(() => undefined);
    }

    function startMacPolling(jobId: string) {
        stopMacPolling();
        macJobIdRef.current = jobId;
        pollMacJob(jobId);
        macPollRef.current = window.setInterval(() => pollMacJob(jobId), 4000);
    }

    async function handleMacTrain(e: React.FormEvent) {
        e.preventDefault();
        if (datasetId === "" || macPermId === "") return;
        setMacStarting(true);
        setError(null);
        setMacJob(null);
        let learningRate: number | null = null;
        if (lrText.trim() !== "") {
            const v = Number(lrText);
            if (!Number.isFinite(v) || v <= 0 || v > 1) {
                setError("Learning rate must be a number between 0 and 1 (e.g. 0.00002), or leave it blank.");
                setMacStarting(false);
                return;
            }
            learningRate = v;
        }
        try {
            const accepted = await apiFetch<BridgeTrainAccepted>(
                `/bridge/permissions/${macPermId}/train`,
                {
                    method: "POST",
                    body: {
                        dataset_id: datasetId,
                        iters,
                        lora_rank: loraRank,
                        lora_alpha: loraAlpha,
                        ...(learningRate !== null ? { learning_rate: learningRate } : {}),
                    },
                }
            );
            startMacPolling(accepted.job_id);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to queue the Mac job");
        } finally {
            setMacStarting(false);
        }
    }

    return (
        <div className="page">
            <div className="page-eyebrow" style={{ color: "var(--warning)" }}>Fine-tune</div>
            <h1 className="page-title">Train</h1>

            <form className="card train-config" onSubmit={handleStart}>
                <div className="field">
                    <label className="label" htmlFor="train-dataset">
                        Dataset
                        {/* S30 (#38): contextual help, reusing the S17 hint pattern. */}
                        <span className="hint" tabIndex={0} aria-label="About the dataset picker">
                            <HelpCircle size={13} />
                            <span className="hint-bubble">
                                The model learns from this dataset's Q&A pairs. 50-200 strong examples beat
                                thousands of noisy ones - curate it first under Datasets.
                            </span>
                        </span>
                    </label>
                    <select
                        id="train-dataset"
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
                        <label className="label" htmlFor="train-iters">
                            Iters
                            <span className="hint">
                                <HelpCircle size={13} />
                                <span className="hint-bubble">
                                    Training steps. More iters means more learning but a longer run. 200 to 400 is a good start.
                                </span>
                            </span>
                        </label>
                        {/* S17: stepper + presets replace the bare number box. */}
                        <div className="iters-stepper">
                            <button
                                type="button"
                                className="stepper-btn"
                                aria-label="Decrease iters by 50"
                                onClick={() => setIters((v) => clampIters(v - 50))}
                            >
                                −
                            </button>
                            <input
                                id="train-iters"
                                className="input iters-input"
                                type="number"
                                value={iters}
                                onChange={(e) => {
                                    const v = Number(e.target.value);
                                    setIters(Number.isFinite(v) ? clampIters(v) : DEFAULT_ITERS);
                                }}
                                min={1}
                                max={5000}
                            />
                            <button
                                type="button"
                                className="stepper-btn"
                                aria-label="Increase iters by 50"
                                onClick={() => setIters((v) => clampIters(v + 50))}
                            >
                                +
                            </button>
                        </div>
                        <div className="iters-presets" role="group" aria-label="Iters presets">
                            {ITERS_PRESETS.map((p) => (
                                <button
                                    key={p.value}
                                    type="button"
                                    className={`chip${iters === p.value ? " chip-active" : ""}`}
                                    onClick={() => setIters(p.value)}
                                >
                                    {p.value} · {p.label}
                                </button>
                            ))}
                        </div>
                    </div>
                    <button type="submit" className="btn btn-primary" disabled={starting || datasetId === ""}>
                        <Play size={16} /> {starting ? "Starting…" : "Start training"}
                    </button>
                    {/* S50: the train handoff — only shown when a Mac is online with train scope. */}
                    {macPerms.length > 0 && (
                        <>
                            {macPerms.length > 1 && (
                                <select
                                    className="select"
                                    value={macPermId}
                                    onChange={(e) => setMacPermId(Number(e.target.value))}
                                    style={{ maxWidth: 180 }}
                                >
                                    {macPerms.map((p) => (
                                        <option key={p.id} value={p.id}>{p.name}</option>
                                    ))}
                                </select>
                            )}
                            <button
                                type="button"
                                className="btn btn-ghost"
                                disabled={macStarting || datasetId === "" || macPermId === ""}
                                onClick={handleMacTrain}
                                title="Queue this training on the paired Mac"
                            >
                                <Cable size={16} /> {macStarting ? "Queueing…" : "Train on this Mac"}
                            </button>
                        </>
                    )}
                </div>

                {/* S34 (#35): advanced hyperparameters, closed by default so the
                    one-line flow stays one line. Every field carries a hint
                    bubble (S17/S30 pattern) and clamps to the S33 bounds. */}
                <div className="advanced">
                    <button
                        type="button"
                        className="advanced-toggle"
                        aria-expanded={advancedOpen}
                        onClick={() => setAdvancedOpen((open) => !open)}
                    >
                        <SlidersHorizontal size={13} /> Advanced hyperparameters
                    </button>
                    {advancedOpen && (
                        <div className="advanced-grid">
                            <div className="field">
                                <label className="label" htmlFor="train-rank">
                                    LoRA rank
                                    <span className="hint" tabIndex={0} aria-label="About LoRA rank">
                                        <HelpCircle size={13} />
                                        <span className="hint-bubble">
                                            How much the adapter can hold. Higher rank learns more but uses more
                                            memory and time. 8 is the safe default; reach for 16–32 when the model
                                            still ignores your examples.
                                        </span>
                                    </span>
                                </label>
                                <input
                                    id="train-rank"
                                    className="input"
                                    type="number"
                                    value={loraRank}
                                    onChange={(e) => {
                                        const v = Number(e.target.value);
                                        setLoraRank(Number.isFinite(v) ? clampRank(v) : DEFAULT_LORA_RANK);
                                    }}
                                    min={1}
                                    max={128}
                                />
                                <div className="iters-presets" role="group" aria-label="LoRA rank presets">
                                    {RANK_PRESETS.map((p) => (
                                        <button
                                            key={p}
                                            type="button"
                                            className={`chip${loraRank === p ? " chip-active" : ""}`}
                                            onClick={() => setLoraRank(p)}
                                        >
                                            {p}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div className="field">
                                <label className="label" htmlFor="train-alpha">
                                    LoRA alpha
                                    <span className="hint" tabIndex={0} aria-label="About LoRA alpha">
                                        <HelpCircle size={13} />
                                        <span className="hint-bubble">
                                            Scales how hard each update hits. The classic choice is 2× the rank —
                                            raise both together to learn more per step.
                                        </span>
                                    </span>
                                </label>
                                <input
                                    id="train-alpha"
                                    className="input"
                                    type="number"
                                    value={loraAlpha}
                                    onChange={(e) => {
                                        const v = Number(e.target.value);
                                        setLoraAlpha(Number.isFinite(v) ? clampAlpha(v) : DEFAULT_LORA_ALPHA);
                                    }}
                                    min={1}
                                    max={256}
                                />
                                <div className="iters-presets" role="group" aria-label="LoRA alpha presets">
                                    {ALPHA_PRESETS.map((p) => (
                                        <button
                                            key={p}
                                            type="button"
                                            className={`chip${loraAlpha === p ? " chip-active" : ""}`}
                                            onClick={() => setLoraAlpha(p)}
                                        >
                                            {p}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div className="field">
                                <label className="label" htmlFor="train-lr">
                                    Learning rate
                                    <span className="hint" tabIndex={0} aria-label="About the learning rate">
                                        <HelpCircle size={13} />
                                        <span className="hint-bubble">
                                            Step size per iteration. Leave blank for mlx's default (0.00002).
                                            If the loss curve bounces around, try half what you set.
                                        </span>
                                    </span>
                                </label>
                                <input
                                    id="train-lr"
                                    className="input"
                                    type="text"
                                    inputMode="decimal"
                                    placeholder="default (0.00002)"
                                    value={lrText}
                                    onChange={(e) => setLrText(e.target.value)}
                                />
                            </div>
                        </div>
                    )}
                </div>
            </form>

            {error && <p className="form-error" role="alert">{error}</p>}

            {run && (
                <div className="card run-card">
                    <div className="run-head">
                        <span className="run-id">Run #{run.id}</span>
                        <span className={`badge ${STATUS_CLASS[run.status] ?? "badge-neutral"}`}>
                            {run.status === "running" && <span className="pulse-dot" />}
                            {displayStatus(run.status)}
                        </span>
                    </div>
                    <div className="run-meta">
                        {run.base_model} · {run.method} · {run.iters} iters
                        {/* S34: echo the panel's choices when the run carries them. */}
                        {run.lora_rank != null && ` · LoRA r${run.lora_rank} α${run.lora_alpha}`}
                        {run.learning_rate != null && ` · lr ${Number(run.learning_rate)}`}
                    </div>
                    <LossChart points={losses} iters={run.iters} />
                    {run.status === "failed" && (
                        run.error_message ? (
                            <pre className="run-error">{run.error_message}</pre>
                        ) : (
                            <div className="run-meta">Failed before error capture shipped (no recorded reason).</div>
                        )
                    )}
                    {explains.length > 0 && (
                        <div className="run-explainer" role="note">
                            <div className="run-explainer-heading">What this probably means</div>
                            {explains.map((ex) => (
                                <div className="run-explainer-item" key={ex.title}>
                                    <strong>{ex.title}</strong>
                                    <p>{ex.cause}</p>
                                    <p className="run-explainer-fix">{ex.fix}</p>
                                </div>
                            ))}
                        </div>
                    )}
                    {run.completed_at && (
                        <div className="run-meta">Completed {new Date(run.completed_at).toLocaleString()}</div>
                    )}
                </div>
            )}

            {/* S50: the Mac train job card — live status + streamed loss curve. */}
            {macJob && (
                <div className="card run-card" style={{ marginTop: 12 }}>
                    <div className="run-head">
                        <span className="run-id">
                            <Cable size={14} style={{ verticalAlign: -2, marginRight: 4 }} />
                            Mac job · {macJob.summary}
                        </span>
                        <span className={`badge ${
                            macJob.status === "done" ? "badge-success" :
                            macJob.status === "failed" ? "badge-danger" :
                            "badge-warning"
                        }`}>
                            {(macJob.status === "awaiting_result" || macJob.status === "sent") && <span className="pulse-dot" />}
                            {macJob.status === "done" ? "completed" : macJob.status === "failed" ? "failed" : "running"}
                        </span>
                    </div>
                    <div className="run-meta">
                        {macJob.elapsed_s}s elapsed · {macJob.online ? "companion online" : "companion offline"}
                    </div>
                    {macJob.events.length > 0 && (
                        <div className="run-meta" style={{ marginTop: 6 }}>
                            {macJob.events[macJob.events.length - 1].stage}: {macJob.events[macJob.events.length - 1].detail}
                        </div>
                    )}
                    {macJob.losses.length > 0 && (
                        <LossChart points={macJob.losses} />
                    )}
                    {macJob.status === "done" && macJob.result && (
                        <div className="run-explainer-fix" style={{ marginTop: 8 }}>
                            Adapter ready on device · run #{String(macJob.result.run_id ?? "?")}
                        </div>
                    )}
                    {macJob.status === "failed" && macJob.detail && (
                        <pre className="run-error" style={{ marginTop: 8 }}>{macJob.detail}</pre>
                    )}
                </div>
            )}

            <form className="attach" onSubmit={handleAttach}>
                <span className="attach-label">
                    Resume a run
                    <span className="hint" tabIndex={0} aria-label="About resuming a run">
                        <HelpCircle size={13} />
                        <span className="hint-bubble">
                            Reconnect the live view to a run already on the server (e.g. after a page refresh).
                            Use the Run #id shown on the run card.
                        </span>
                    </span>
                </span>
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