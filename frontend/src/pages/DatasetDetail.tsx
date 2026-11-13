import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Sparkles, Download, Plus, Pencil, Trash2, ChevronLeft, ChevronRight, Upload, HelpCircle, Wand2, MessagesSquare, Eraser, GitMerge } from "lucide-react";
import { apiFetch, apiUpload } from "../api";
import { displayStatus } from "../statusText";
import type { Dataset, QAPair, DedupeResult, MergeResult } from "../types";
import QAPairModal, { type QAPairValues } from "../components/QAPairModal";
import ConfirmDialog from "../components/ConfirmDialog";
import VuMeter from "../components/VuMeter";
import EmptyState from "../components/EmptyState";
import { GenerationStatusLine } from "../components/GenerationStatus";

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
    const [suggesting, setSuggesting] = useState(false);
    const [genCount, setGenCount] = useState(20);
    const [generating, setGenerating] = useState(false);
    const [preset, setPreset] = useState("general");
    const [impCount, setImpCount] = useState(50);
    const [importing, setImporting] = useState(false);
    const [fileImporting, setFileImporting] = useState(false);

    // S56: dedupe + merge across datasets. Preview-then-act: every destructive
    // write is first computed server-side with dry_run=true.
    const [ownDatasets, setOwnDatasets] = useState<Dataset[]>([]);
    const [dedupeBusy, setDedupeBusy] = useState(false);
    const [dedupeNote, setDedupeNote] = useState<string | null>(null);
    const [dedupePlan, setDedupePlan] = useState<DedupeResult | null>(null);
    const [mergeSource, setMergeSource] = useState("");
    const [mergeBusy, setMergeBusy] = useState(false);
    const [mergeNote, setMergeNote] = useState<string | null>(null);
    const [mergePreview, setMergePreview] = useState<MergeResult | null>(null);

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
        // S56: the merge picker lists the account's other datasets; a failure
        // here only empties the picker, it must not poison the page error.
        apiFetch<Dataset[]>("/datasets")
            .then((ds) => setOwnDatasets(ds))
            .catch(() => setOwnDatasets([]));
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

    // S27: fill the prompt box with a zero-LLM starter built from the dataset's
    // saved name/description. The suggestion stays editable until the user saves.
    async function handleSuggest() {
        setSuggesting(true);
        setError(null);
        try {
            const res = await apiFetch<{ suggestion: string }>(
                `/datasets/${datasetId}/use-case-suggestion`,
                { method: "POST" },
            );
            if (res.suggestion) {
                setPrompt(res.suggestion);
            } else {
                setError("Give the dataset a name or description first.");
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Suggestion failed");
        } finally {
            setSuggesting(false);
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

    // S12 (#14): upload a CSV/JSONL file and append the parsed pairs.
    async function handleFileImport(e: React.ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        e.target.value = ""; // allow re-picking the same file after a failure
        if (!file) return;
        setFileImporting(true);
        setError(null);
        try {
            const created = await apiUpload<QAPair[]>(`/datasets/${datasetId}/qa-pairs/upload`, file);
            setPairs((prev) => [...prev, ...created]);
        } catch (err) {
            setError(err instanceof Error ? err.message : "Upload failed");
        } finally {
            setFileImporting(false);
        }
    }

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

    // S56: reload the pair list from the server after a dedupe or merge -
    // rows were deleted and/or moved with fresh ids, so local state is stale.
    async function reloadPairs() {
        const p = await apiFetch<QAPair[]>(`/datasets/${datasetId}/qa-pairs`);
        setPairs(p);
        setPage(0);
    }

    // S56: dedupe preview -> confirmation dialog -> real run.
    async function handleDedupe() {
        setDedupeBusy(true);
        setDedupeNote(null);
        setError(null);
        try {
            const plan = await apiFetch<DedupeResult>(`/datasets/${datasetId}/dedupe`, {
                method: "POST",
                body: { dry_run: true },
            });
            if (plan.removed === 0) {
                setDedupeNote("No duplicates found - every pair is unique.");
            } else {
                setDedupePlan(plan);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Dedupe check failed");
        } finally {
            setDedupeBusy(false);
        }
    }

    async function confirmDedupe() {
        setDedupePlan(null);
        setDedupeBusy(true);
        try {
            const res = await apiFetch<DedupeResult>(`/datasets/${datasetId}/dedupe`, { method: "POST", body: {} });
            setDedupeNote(
                res.removed === 0
                    ? "No duplicates found - every pair is unique."
                    : `Removed ${res.removed} duplicate ${res.removed === 1 ? "pair" : "pairs"} in ${res.duplicate_groups} ${res.duplicate_groups === 1 ? "group" : "groups"} (oldest kept).`,
            );
            await reloadPairs();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Dedupe failed");
        } finally {
            setDedupeBusy(false);
        }
    }

    // S56: merge preview, then the real move. Picking another source or
    // editing pairs invalidates the preview on purpose.
    async function handleMergePreview() {
        if (!mergeSource) return;
        setMergeBusy(true);
        setMergeNote(null);
        setMergePreview(null);
        setError(null);
        try {
            const res = await apiFetch<MergeResult>(`/datasets/${datasetId}/merge`, {
                method: "POST",
                body: { source_dataset_id: Number(mergeSource), dry_run: true },
            });
            setMergePreview(res);
            setMergeNote(
                res.moved === 0
                    ? `Nothing to move - all ${res.skipped_duplicates} source ${res.skipped_duplicates === 1 ? "pair is" : "pairs are"} already here.`
                    : `${res.moved} ${res.moved === 1 ? "pair would move" : "pairs would move"} here; ${res.skipped_duplicates} ${res.skipped_duplicates === 1 ? "duplicate stays" : "duplicates stay"} in the source.`,
            );
        } catch (err) {
            setError(err instanceof Error ? err.message : "Merge preview failed");
        } finally {
            setMergeBusy(false);
        }
    }

    async function handleMerge() {
        if (!mergePreview) return;
        setMergeBusy(true);
        setError(null);
        try {
            const res = await apiFetch<MergeResult>(`/datasets/${datasetId}/merge`, {
                method: "POST",
                body: { source_dataset_id: mergePreview.source_dataset_id },
            });
            const src = ownDatasets.find((d) => d.id === res.source_dataset_id)?.name ?? "source";
            setMergeNote(
                `Moved ${res.moved} ${res.moved === 1 ? "pair" : "pairs"} from "${src}"; left ${res.skipped_duplicates} ${res.skipped_duplicates === 1 ? "duplicate" : "duplicates"} there.`,
            );
            setMergeSource("");
            setMergePreview(null);
            await reloadPairs();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Merge failed");
        } finally {
            setMergeBusy(false);
        }
    }

    const totalPages = Math.max(1, Math.ceil(pairs.length / PAGE_SIZE));
    const safePage = Math.min(page, totalPages - 1);
    const start = safePage * PAGE_SIZE;
    const pagePairs = pairs.slice(start, start + PAGE_SIZE);

    return (
        <div className="page dd-page">
            <Link to="/datasets" className="dd-back"><ArrowLeft size={15} /> Datasets</Link>

            {loading && (
                <p className="loading">
                    <VuMeter bars={4} /> Loading…
                </p>
            )}
            {error && <p className="form-error" role="alert">{error}</p>}

            {!loading && dataset && (
                <>
                    <div className="dd-head">
                        <h1 className="page-title">{dataset.name}</h1>
                        <div className="dd-sub">
                            <span className={`badge ${dataset.source === "generated" ? "badge-info" : "badge-neutral"}`}>{displayStatus(dataset.source)}</span>
                            {dataset.description && <span className="dd-desc">{dataset.description}</span>}
                        </div>
                    </div>

                    <div className="dd-controls">
                        <div className="card">
                            <div className="label">
                                Use-case prompt
                                {/* S30 (#38): contextual help, reusing the S17 hint pattern. */}
                                <span className="hint" tabIndex={0} aria-label="About the use-case prompt">
                                    <HelpCircle size={13} />
                                    <span className="hint-bubble">
                                        One or two sentences describing the persona you want. Every generated
                                        pair follows it - save it before pressing Generate, which reads the
                                        saved prompt, not the unsaved box.
                                    </span>
                                </span>
                            </div>
                            <textarea
                                aria-label="Use-case prompt for Q&A generation"
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
                                {/* S27: zero-LLM starter from the dataset's name/description. */}
                                <button className="btn btn-ghost" onClick={handleSuggest} disabled={suggesting}>
                                    <Wand2 size={15} /> {suggesting ? "Thinking…" : "Suggest"}
                                </button>
                                <div className="dd-row-right">
                                    <input className="input dd-count" type="number" min={1} max={100} aria-label="Number of Q&A pairs to generate" value={genCount} onChange={(e) => setGenCount(Number(e.target.value))} />
                                    <button className="btn btn-primary" onClick={handleGenerate} disabled={generating || genCount < 1 || !dataset.use_case_prompt}>
                                        <Sparkles size={15} /> {generating ? "Generating…" : "Generate"}
                                    </button>
                                </div>
                            </div>
                            {!dataset.use_case_prompt && <div className="dd-hint">Save a use-case prompt first.</div>}
                            <GenerationStatusLine />
                        </div>

                        <div className="card">
                            <div className="label">
                                Import from file
                                <span className="hint" tabIndex={0} aria-label="About file import">
                                    <HelpCircle size={13} />
                                    <span className="hint-bubble">
                                        Bring your own examples. Header names are matched loosely - question,
                                        prompt, input, instruction or q / answer, completion, output, response
                                        or a all work.
                                    </span>
                                </span>
                            </div>
                            <div className="dd-hint">CSV or JSONL with question/answer columns (up to 2 MB, 5,000 pairs).</div>
                            <div className="dd-row dd-row-end">
                                <label className="btn btn-ghost" style={{ marginBottom: 0 }}>
                                    <Upload size={15} /> {fileImporting ? "Uploading…" : "Choose file"}
                                    <input
                                        type="file"
                                        accept=".csv,.jsonl,.tsv"
                                        className="sr-file-input"
                                        aria-label="Choose CSV or JSONL file to import Q&A pairs"
                                        onChange={handleFileImport}
                                        disabled={fileImporting}
                                    />
                                </label>
                            </div>
                        </div>

                        <div className="card">
                            <div className="label">
                                Import preset
                                <span className="hint" tabIndex={0} aria-label="About preset import">
                                    <HelpCircle size={13} />
                                    <span className="hint-bubble">
                                        Ready-made public pairs (Dolly instructions or finance Q&A) to pad a
                                        small dataset. Mix presets with your own examples - don't train on
                                        presets alone.
                                    </span>
                                </span>
                            </div>
                            <select className="select" aria-label="Import preset" value={preset} onChange={(e) => setPreset(e.target.value)}>
                                <option value="general">General instructions (Dolly)</option>
                                <option value="finance">Finance Q&amp;A</option>
                            </select>
                            <div className="dd-row dd-row-end">
                                <div className="dd-row-right">
                                    <input className="input dd-count" type="number" min={1} max={500} aria-label="Number of preset pairs to import" value={impCount} onChange={(e) => setImpCount(Number(e.target.value))} />
                                    <button className="btn btn-ghost" onClick={handleImport} disabled={importing || impCount < 1}>
                                        <Download size={15} /> {importing ? "Importing…" : "Import"}
                                    </button>
                                </div>
                            </div>
                        </div>

                        {/* S56: remove exact-duplicate pairs here, or pull a
                            sibling dataset's pairs in. Both flows are
                            preview-first: nothing is written blindly. */}
                        <div className="card">
                            <div className="label">
                                Duplicates &amp; merge
                                <span className="hint" tabIndex={0} aria-label="About dedupe and merge">
                                    <HelpCircle size={13} />
                                    <span className="hint-bubble">
                                        Two pairs with the same question and answer teach the example twice.
                                        Matching ignores letter case and extra spaces. Merge pulls another
                                        of your datasets' pairs in; ones already here stay in the source.
                                    </span>
                                </span>
                            </div>
                            <div className="dd-row">
                                <button className="btn btn-ghost" onClick={handleDedupe} disabled={dedupeBusy}>
                                    <Eraser size={15} /> {dedupeBusy ? "Working…" : "Find & remove duplicates"}
                                </button>
                                {dedupeNote && <span className="dd-hint dd-note-inline">{dedupeNote}</span>}
                            </div>
                            <div className="dd-row">
                                <select
                                    className="select"
                                    aria-label="Source dataset to merge from"
                                    value={mergeSource}
                                    onChange={(e) => {
                                        setMergeSource(e.target.value);
                                        setMergePreview(null);
                                        setMergeNote(null);
                                    }}
                                    disabled={mergeBusy}
                                >
                                    <option value="">Merge from…</option>
                                    {ownDatasets
                                        .filter((d) => String(d.id) !== datasetId)
                                        .map((d) => (
                                            <option key={d.id} value={d.id}>{d.name}</option>
                                        ))}
                                </select>
                                <div className="dd-row-right">
                                    <button className="btn btn-ghost" onClick={handleMergePreview} disabled={mergeBusy || !mergeSource}>
                                        {mergeBusy ? "Working…" : "Preview"}
                                    </button>
                                    <button className="btn btn-primary" onClick={handleMerge} disabled={mergeBusy || !mergePreview}>
                                        <GitMerge size={15} /> Merge
                                    </button>
                                </div>
                            </div>
                            {mergeNote && <div className="dd-hint">{mergeNote}</div>}
                        </div>
                    </div>

                    <div className="dd-pairs-head">
                        <div className="dd-pairs-title">
                            Q&amp;A pairs
                            <span className="hint" tabIndex={0} aria-label="About Q&A pairs">
                                <HelpCircle size={13} />
                                <span className="hint-bubble">
                                    Each pair is one training example: the question is what the model sees,
                                    the answer is what it learns to say. Aim for 50+ clean pairs before
                                    training.
                                </span>
                            </span>
                            <span className="dd-count-label">· {pairs.length}</span>
                        </div>
                        <button className="btn btn-primary btn-sm" onClick={openCreatePair}><Plus size={15} /> Add pair</button>
                    </div>

                    {pairs.length === 0 ? (
                        <EmptyState
                            icon={MessagesSquare}
                            tint="info"
                            title="No pairs yet"
                            hint="Each pair is one training example. Add one by hand, generate a batch from a prompt, or import a CSV/JSONL file."
                            action={
                                <button className="btn btn-primary btn-sm" onClick={openCreatePair}>
                                    <Plus size={15} /> Add pair
                                </button>
                            }
                        />
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
                                    <div className="pager-controls">
                                        <button className="pager-btn" onClick={() => setPage(Math.max(0, safePage - 1))} disabled={safePage === 0} aria-label="Previous page">
                                            <ChevronLeft size={14} />
                                        </button>
                                        <span className="pager-page">{safePage + 1} / {totalPages}</span>
                                        <button className="pager-btn" onClick={() => setPage(Math.min(totalPages - 1, safePage + 1))} disabled={safePage === totalPages - 1} aria-label="Next page">
                                            <ChevronRight size={14} />
                                        </button>
                                    </div>
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
                    {/* S56: dedupe lands here only after a dry-run found dupes. */}
                    <ConfirmDialog
                        open={dedupePlan !== null}
                        title="Remove duplicate pairs?"
                        message={
                            dedupePlan
                                ? `${dedupePlan.removed} duplicate ${dedupePlan.removed === 1 ? "pair" : "pairs"} in ${dedupePlan.duplicate_groups} ${dedupePlan.duplicate_groups === 1 ? "group" : "groups"}. The oldest pair of each group is kept; the rest are deleted. This can't be undone.`
                                : ""
                        }
                        confirmLabel="Remove"
                        onConfirm={confirmDedupe}
                        onCancel={() => setDedupePlan(null)}
                    />
                </>
            )}
        </div>
    );
}