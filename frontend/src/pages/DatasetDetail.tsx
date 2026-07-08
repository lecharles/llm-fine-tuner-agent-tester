import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Sparkles, Download, Plus, Pencil, Trash2 } from "lucide-react";
import Pager from "../components/Pager";
import { apiFetch } from "../api";
import type { Dataset, QAPair } from "../types";
import QAPairModal, { type QAPairValues } from "../components/QAPairModal";
import ConfirmDialog from "../components/ConfirmDialog";

const PAGE_SIZE = 10;

// Dataset detail: edit the use-case prompt, generate or import pairs in bulk,
// and add/edit/delete individual pairs. Pairs paginate client-side. Create and
// edit go through one modal; delete goes through the ConfirmDialog.
export default function DatasetDetail() {
    const { datasetId } = useParams<{ datasetId: string }>();

    const [dataset, setDataset] = useState<Dataset | null>(null);
    const [pairs, setPairs] = useState<QAPair[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Use-case prompt editor + generate/import controls.
    const [prompt, setPrompt] = useState("");
    const [savingPrompt, setSavingPrompt] = useState(false);
    const [genCount, setGenCount] = useState(20);
    const [generating, setGenerating] = useState(false);
    const [preset, setPreset] = useState("general");
    const [impCount, setImpCount] = useState(50);
    const [importing, setImporting] = useState(false);

    // Pair create/edit modal, delete confirmation, and the current page.
    const [pairForm, setPairForm] = useState<{ open: boolean; mode: "create" | "edit"; pair: QAPair | null }>({
        open: false,
        mode: "create",
        pair: null,
    });
    const [confirmTarget, setConfirmTarget] = useState<QAPair | null>(null);
    const [page, setPage] = useState(0);

    useEffect(() => {
        Promise.all([
            apiFetch<Dataset>(`/datasets/${datasetId}`),
            apiFetch<QAPair[]>(`/datasets/${datasetId}/qa-pairs`),
        ])
            .then(([d, p]) => {
                setDataset(d);
                setPairs(p);
                setPrompt(d.use_case_prompt ?? "");
            })
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
            .finally(() => setLoading(false));
    }, [datasetId]);

    // Save the dataset's use_case_prompt (generation reads it server-side).
    async function handleSavePrompt() {
        setSavingPrompt(true);
        setError(null);
        try {
            const updated = await apiFetch<Dataset>(`/datasets/${datasetId}`, {
                method: "PUT",
                body: { use_case_prompt: prompt },
            });
            setDataset(updated);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Save failed");
        } finally {
            setSavingPrompt(false);
        }
    }

    async function handleGenerate() {
        setGenerating(true);
        setError(null);
        try {
            const created = await apiFetch<QAPair[]>(`/datasets/${datasetId}/generate`, {
                method: "POST",
                body: { count: genCount },
            });
            setPairs((prev) => [...prev, ...created]);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Generate failed");
        } finally {
            setGenerating(false);
        }
    }

    async function handleImport() {
        setImporting(true);
        setError(null);
        try {
            const created = await apiFetch<QAPair[]>(`/datasets/${datasetId}/import`, {
                method: "POST",
                body: { preset, count: impCount },
            });
            setPairs((prev) => [...prev, ...created]);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Import failed");
        } finally {
            setImporting(false);
        }
    }

    const openCreatePair = () => setPairForm({ open: true, mode: "create", pair: null });
    const openEditPair = (p: QAPair) => setPairForm({ open: true, mode: "edit", pair: p });
    const closePairForm = () => setPairForm((f) => ({ ...f, open: false }));

    async function submitPair(values: QAPairValues) {
        if (pairForm.mode === "create") {
            const created = await apiFetch<QAPair>(`/datasets/${datasetId}/qa-pairs`, { method: "POST", body: values });
            setPairs((prev) => [...prev, created]);
        } else if (pairForm.pair) {
            const id = pairForm.pair.id;
            const updated = await apiFetch<QAPair>(`/datasets/${datasetId}/qa-pairs/${id}`, { method: "PUT", body: values });
            setPairs((prev) => prev.map((p) => (p.id === id ? updated : p)));
        }
    }

    async function confirmDeletePair() {
        if (!confirmTarget) return;
        try {
            await apiFetch<null>(`/datasets/${datasetId}/qa-pairs/${confirmTarget.id}`, { method: "DELETE" });
            setPairs((prev) => prev.filter((p) => p.id !== confirmTarget.id));
        } catch (err) {
            setError(err instanceof Error ? err.message : "Delete failed");
        } finally {
            setConfirmTarget(null);
        }
    }

    const totalPages = Math.max(1, Math.ceil(pairs.length / PAGE_SIZE));
    const safePage = Math.min(page, totalPages - 1);
    const start = safePage * PAGE_SIZE;
    const pagePairs = pairs.slice(start, start + PAGE_SIZE);

    return (
        <div className="page dd-page">
            <Link to="/datasets" className="dd-back"><ArrowLeft size={15} /> Datasets</Link>

            {loading && <p className="loading">Loading…</p>}
            {error && <p className="form-error">{error}</p>}

            {!loading && dataset && (
                <>
                    <div className="dd-head">
                        <h1 className="page-title">{dataset.name}</h1>
                        <div className="dd-sub">
                            <span className={`badge ${dataset.source === "generated" ? "badge-info" : "badge-neutral"}`}>{dataset.source}</span>
                            {dataset.description && <span className="dd-desc">{dataset.description}</span>}
                        </div>
                    </div>

                    <div className="dd-controls">
                        <div className="card">
                            <div className="label">Use-case prompt</div>
                            <textarea
                                className="textarea"
                                rows={3}
                                placeholder="e.g. A terse assistant that answers in one sentence"
                                value={prompt}
                                onChange={(e) => setPrompt(e.target.value)}
                            />
                            <div className="dd-row">
                                <button className="btn btn-ghost" onClick={handleSavePrompt} disabled={savingPrompt}>
                                    {savingPrompt ? "Saving…" : "Save prompt"}
                                </button>
                                <div className="dd-row-right">
                                    <input className="input dd-count" type="number" min={1} max={100} value={genCount} onChange={(e) => setGenCount(Number(e.target.value))} />
                                    <button className="btn btn-primary" onClick={handleGenerate} disabled={generating || genCount < 1 || !dataset.use_case_prompt}>
                                        <Sparkles size={15} /> {generating ? "Generating…" : "Generate"}
                                    </button>
                                </div>
                            </div>
                            {!dataset.use_case_prompt && <div className="dd-hint">Save a use-case prompt first.</div>}
                        </div>

                        <div className="card">
                            <div className="label">Import preset</div>
                            <select className="select" value={preset} onChange={(e) => setPreset(e.target.value)}>
                                <option value="general">General instructions (Dolly)</option>
                                <option value="finance">Finance Q&amp;A</option>
                            </select>
                            <div className="dd-row dd-row-end">
                                <div className="dd-row-right">
                                    <input className="input dd-count" type="number" min={1} max={500} value={impCount} onChange={(e) => setImpCount(Number(e.target.value))} />
                                    <button className="btn btn-ghost" onClick={handleImport} disabled={importing || impCount < 1}>
                                        <Download size={15} /> {importing ? "Importing…" : "Import"}
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <div className="dd-pairs-head">
                        <div className="dd-pairs-title">Q&amp;A pairs <span className="dd-count-label">· {pairs.length}</span></div>
                        <button className="btn btn-primary btn-sm" onClick={openCreatePair}><Plus size={15} /> Add pair</button>
                    </div>

                    {pairs.length === 0 ? (
                        <p className="empty">No pairs yet. Add one, generate from a prompt, or import a preset.</p>
                    ) : (
                        <>
                            <div className="table">
                                <div className="table-head">
                                    <div className="cell cell-q">Question</div>
                                    <div className="cell cell-a">Answer</div>
                                    <div className="cell cell-actions" />
                                </div>
                                {pagePairs.map((p) => (
                                    <div className="table-row" key={p.id}>
                                        <div className="cell cell-q dd-cell-text">{p.question}</div>
                                        <div className="cell cell-a dd-cell-text">{p.answer}</div>
                                        <div className="cell cell-actions">
                                            <button className="btn-icon" onClick={() => openEditPair(p)} aria-label="Edit pair"><Pencil size={15} /></button>
                                            <button className="btn-icon btn-icon-danger" onClick={() => setConfirmTarget(p)} aria-label="Delete pair"><Trash2 size={15} /></button>
                                        </div>
                                    </div>
                                ))}
                            </div>

                            {totalPages > 1 && (
                                <div className="pager">
                                    <div className="pager-info">
                                        Showing {start + 1}–{Math.min(start + PAGE_SIZE, pairs.length)} of {pairs.length}
                                    </div>
                                    <Pager page={safePage} total={totalPages} onChange={setPage} />
                                </div>
                            )}
                        </>
                    )}

                    <QAPairModal open={pairForm.open} mode={pairForm.mode} pair={pairForm.pair} onClose={closePairForm} onSubmit={submitPair} />
                    <ConfirmDialog
                        open={confirmTarget !== null}
                        title="Delete pair?"
                        message="This deletes this Q&A pair. This can't be undone."
                        onConfirm={confirmDeletePair}
                        onCancel={() => setConfirmTarget(null)}
                    />
                </>
            )}
        </div>
    );
}