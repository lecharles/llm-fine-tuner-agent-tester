import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { History as HistoryIcon, X } from "lucide-react";
import { apiFetch } from "../api";
import { displayStatus } from "../statusText";
import LossChart from "../components/LossChart";
import VuMeter from "../components/VuMeter";
import EmptyState from "../components/EmptyState";
import type { LossPoint, TrainingRun, TrainingRunHistory } from "../types";

// S36 (#36): run history 2 — the history page. The list comes from the S35
// endpoint GET /api/training-runs/history (dataset, base model, iters, final
// loss); selecting a row replays that run's loss curve via GET /losses (the
// same tolerant train.log parser the live Train chart uses) and opens the log
// viewer for whatever the backend persisted on the run (#42: error text +
// train.log tail + fuse.log tail on failures).

const STATUS_CLASS: Record<string, string> = {
    queued: "badge-neutral",
    running: "badge-warning",
    completed: "badge-success",
    failed: "badge-danger",
};

const fmtLoss = (v: number | null) => (v == null ? "—" : v.toFixed(4));
const shortModel = (m: string) => m.split("/").pop() ?? m;
const fmtDate = (iso: string) =>
    new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });

export default function History() {
    const [rows, setRows] = useState<TrainingRunHistory[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [selectedId, setSelectedId] = useState<number | null>(null);
    const [detail, setDetail] = useState<TrainingRun | null>(null);
    const [losses, setLosses] = useState<LossPoint[]>([]);
    const [detailLoading, setDetailLoading] = useState(false);
    const [detailError, setDetailError] = useState<string | null>(null);

    useEffect(() => {
        let alive = true;
        apiFetch<TrainingRunHistory[]>("/training-runs/history")
            .then((data) => { if (alive) setRows(data); })
            .catch((e: Error) => { if (alive) setError(e.message); })
            .finally(() => { if (alive) setLoading(false); });
        return () => { alive = false; };
    }, []);

    async function openDetail(run: TrainingRunHistory) {
        setSelectedId(run.id);
        setDetail(null);
        setLosses([]);
        setDetailError(null);
        setDetailLoading(true);
        try {
            // Run row (carries the persisted failure text) + its loss points,
            // fetched together — the curve is the log replay, the text is the
            // log the backend kept.
            const [runRow, points] = await Promise.all([
                apiFetch<TrainingRun>(`/training-runs/${run.id}`),
                apiFetch<LossPoint[]>(`/training-runs/${run.id}/losses`),
            ]);
            setDetail(runRow);
            setLosses(points);
        } catch (e) {
            setDetailError((e as Error).message);
        } finally {
            setDetailLoading(false);
        }
    }

    const selected = rows.find((r) => r.id === selectedId) ?? null;

    return (
        <div className="page">
            <div className="page-eyebrow" style={{ color: "var(--info)" }}>Training</div>
            <h1 className="page-title">Run history</h1>
            <div className="page-sub">Every training run you started, newest first. Pick a run to replay its loss curve and read the log.</div>

            {error && <p className="form-error" role="alert">{error}</p>}
            {loading && (
                <p className="hist-loading">Loading runs&hellip; <VuMeter bars={4} /></p>
            )}
            {!loading && !error && rows.length === 0 && (
                <EmptyState
                    icon={HistoryIcon}
                    tint="info"
                    title="No training runs yet"
                    hint="Every run you start lands here — pick one later to replay its loss curve and read the log."
                    action={
                        <Link className="btn btn-primary" to="/train">
                            Start a run
                        </Link>
                    }
                />
            )}

            {!loading && !error && rows.length > 0 && (
                <div className="table">
                    <div className="table-head">
                        <div className="cell hist-cell-run">Run</div>
                        <div className="cell cell-grow">Dataset</div>
                        <div className="cell hist-cell-model">Base model</div>
                        <div className="cell hist-cell-num">Iters</div>
                        <div className="cell hist-cell-num">Final loss</div>
                        <div className="cell hist-cell-status">Status</div>
                        <div className="cell cell-date">Created</div>
                        <div className="cell cell-actions" />
                    </div>
                    {rows.map((r) => (
                        <div
                            className={`table-row hist-row${r.id === selectedId ? " hist-row-active" : ""}`}
                            key={r.id}
                            onClick={() => openDetail(r)}
                        >
                            <div className="cell hist-cell-run">#{r.id}</div>
                            <div className="cell cell-grow">{r.dataset_name}</div>
                            <div className="cell hist-cell-model" title={r.base_model}>{shortModel(r.base_model)}</div>
                            <div className="cell hist-cell-num">{r.iters}</div>
                            <div className="cell hist-cell-num">{fmtLoss(r.final_loss)}</div>
                            <div className="cell hist-cell-status">
                                <span className={`badge ${STATUS_CLASS[r.status] ?? "badge-neutral"}`}>
                                    {r.status === "running" && <span className="pulse-dot" />}
                                    {displayStatus(r.status)}
                                </span>
                            </div>
                            <div className="cell cell-date">{fmtDate(r.created_at)}</div>
                            <div className="cell cell-actions">
                                <button
                                    className="btn-icon"
                                    onClick={(e) => { e.stopPropagation(); openDetail(r); }}
                                    aria-label={`View run #${r.id} log and loss replay`}
                                >
                                    <span className="hist-view-label">View</span>
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {selected && (
                <div className="card hist-detail" aria-live="polite">
                    <div className="run-head">
                        <span className="run-id">Run #{selected.id}</span>
                        <span className={`badge ${STATUS_CLASS[selected.status] ?? "badge-neutral"}`}>
                            {displayStatus(selected.status)}
                        </span>
                        <button className="btn-icon hist-close" onClick={() => setSelectedId(null)} aria-label="Close run details">
                            <X size={15} />
                        </button>
                    </div>
                    <div className="run-meta">
                        {selected.dataset_name} · {selected.base_model} · {selected.method} · {selected.iters} iters
                        {" · final loss "}{fmtLoss(selected.final_loss)}
                        {selected.completed_at && <> · finished {fmtDate(selected.completed_at)}</>}
                    </div>

                    {detailLoading && (
                        <p className="hist-loading">Loading log &amp; curve&hellip; <VuMeter bars={4} /></p>
                    )}
                    {detailError && <p className="form-error" role="alert">{detailError}</p>}

                    {!detailLoading && !detailError && (
                        <>
                            <div className="hist-section-title">Loss replay</div>
                            <LossChart points={losses} iters={selected.iters} />
                            {losses.length > 0 && (
                                <div className="run-meta">{losses.length} loss point{losses.length === 1 ? "" : "s"} replayed from train.log</div>
                            )}

                            <div className="hist-section-title">Log</div>
                            {detail?.error_message ? (
                                <pre className="run-error">{detail.error_message}</pre>
                            ) : (
                                <div className="hist-log-note">
                                    No log text was persisted for this run — the backend stores error text and the
                                    train.log tail when a run <em>fails</em> (#42). A finished run&rsquo;s raw train.log
                                    stays in its workspace on the machine that trained it; the loss replay above is
                                    parsed from it while the file exists.
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
