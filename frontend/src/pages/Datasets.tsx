import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Database, Plus, Pencil, Trash2, Search, X, HelpCircle } from "lucide-react";
import { apiFetch, apiSearch } from "../api";
import { displayStatus } from "../statusText";
import type { Dataset, SearchResults } from "../types";
import DatasetFormModal, { type DatasetFormValues } from "../components/DatasetFormModal";
import ConfirmDialog from "../components/ConfirmDialog";
import ShareToggle, { type Visibility } from "../components/ShareToggle";
import Snippet from "../components/Snippet";
import VuMeter from "../components/VuMeter";
import EmptyState from "../components/EmptyState";

// Datasets: read (list) + create + edit + delete. Each mutation updates local
// state so the list re-renders immediately, no refetch and no page reload.
// Create and edit go through one modal; delete goes through the ConfirmDialog.
export default function Datasets() {
    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // The create/edit modal: open flag, which mode, and (for edit) which dataset.
    const [form, setForm] = useState<{ open: boolean; mode: "create" | "edit"; dataset: Dataset | null }>({
        open: false,
        mode: "create",
        dataset: null,
    });

    // The dataset pending a delete confirmation; null means the dialog is closed.
    const [confirmTarget, setConfirmTarget] = useState<Dataset | null>(null);

    // S68: full-text search mode. A non-empty trimmed query swaps the table
    // for the S67 endpoint's results (datasets + Q&A pairs, BM25-ordered).
    // One request in flight; a stale response can never land after a newer
    // query (seq guard), so fast typing can't reorder the list.
    const [searchQ, setSearchQ] = useState("");
    const [searchRes, setSearchRes] = useState<SearchResults | null>(null);
    const [searchBusy, setSearchBusy] = useState(false);
    const [searchError, setSearchError] = useState<string | null>(null);
    const searchSeqRef = useRef(0);
    const searching = searchQ.trim().length > 0;

    useEffect(() => {
        const q = searchQ.trim();
        if (!q) {
            searchSeqRef.current += 1; // any in-flight response is now stale
            setSearchRes(null);
            setSearchError(null);
            return;
        }
        const mine = ++searchSeqRef.current;
        setSearchBusy(true);
        setSearchError(null);
        const t = setTimeout(() => {
            apiSearch<SearchResults>(q, 50)
                .then((r) => {
                    if (searchSeqRef.current !== mine) return; // superseded
                    setSearchRes(r);
                })
                .catch((err) => {
                    if (searchSeqRef.current !== mine) return;
                    setSearchRes(null);
                    setSearchError(err instanceof Error ? err.message : "Search failed");
                })
                .finally(() => {
                    if (searchSeqRef.current === mine) setSearchBusy(false);
                });
        }, 250);
        return () => clearTimeout(t);
    }, [searchQ]);

    // Load once, after first render. The token rides along via apiFetch.
    useEffect(() => {
        apiFetch<Dataset[]>("/datasets")
            .then((data) => setDatasets(data))
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to load"))
            .finally(() => setLoading(false));
    }, []);

    const openCreate = () => setForm({ open: true, mode: "create", dataset: null });
    const openEdit = (d: Dataset) => setForm({ open: true, mode: "edit", dataset: d });
    const closeForm = () => setForm((f) => ({ ...f, open: false }));

    // Create prepends; edit swaps in place. Errors bubble to the modal, which shows them.
    async function submitForm(values: DatasetFormValues) {
        if (form.mode === "create") {
            const created = await apiFetch<Dataset>("/datasets", {
                method: "POST",
                body: { name: values.name, description: values.description || null, source: values.source },
            });
            setDatasets((prev) => [created, ...prev]);
        } else if (form.dataset) {
            const id = form.dataset.id;
            const updated = await apiFetch<Dataset>(`/datasets/${id}`, {
                method: "PUT",
                body: { name: values.name, description: values.description || null },
            });
            setDatasets((prev) => prev.map((d) => (d.id === id ? updated : d)));
        }
    }

    async function confirmDelete() {
        if (!confirmTarget) return;
        try {
            await apiFetch<null>(`/datasets/${confirmTarget.id}`, { method: "DELETE" });
            setDatasets((prev) => prev.filter((d) => d.id !== confirmTarget.id));
        } catch (err) {
            setError(err instanceof Error ? err.message : "Delete failed");
        } finally {
            setConfirmTarget(null);
        }
    }

    return (
        <div className="page">
            <div className="page-head">
                <h1 className="page-title">Datasets</h1>
                <button className="btn btn-primary" onClick={openCreate}>
                    <Plus size={16} /> New dataset
                </button>
            </div>

            {/* S68: full-text search (S67 endpoint). Typing swaps the table
                for BM25-ranked dataset + Q&A hits; clearing it swaps back. */}
            <div className="search-bar">
                <Search size={14} className="search-bar-icon" />
                <input
                    className="input search-bar-input"
                    type="search"
                    placeholder="Search dataset names, descriptions and Q&A pairs…"
                    value={searchQ}
                    onChange={(e) => setSearchQ(e.target.value)}
                    aria-label="Search datasets and Q&A pairs"
                    spellCheck={false}
                />
                {searching && (
                    <button className="btn-icon" onClick={() => setSearchQ("")} aria-label="Clear search">
                        <X size={14} />
                    </button>
                )}
                <span className="hint" tabIndex={0} aria-label="About search">
                    <HelpCircle size={13} />
                    <span className="hint-bubble">
                        Full-text search over names, descriptions, questions and answers —
                        stemmed (&ldquo;training&rdquo; finds &ldquo;train&rdquo;), word-prefix
                        matched, ranked by relevance. It covers your rows plus everyone&rsquo;s
                        public ones; nobody&rsquo;s private data can appear. Press ⌘K / Ctrl+K
                        anywhere to search from the shell.
                    </span>
                </span>
            </div>

            {searching ? (
                <div className="search-results">
                    {searchBusy && (
                        <p className="loading">
                            <VuMeter bars={4} /> Searching…
                        </p>
                    )}
                    {searchError && (
                        <p className="form-error" role="alert">{searchError}</p>
                    )}
                    {!searchBusy && !searchError && searchRes && (
                        <>
                            {searchRes.datasets.length === 0 && searchRes.pairs.length === 0 && (
                                <EmptyState
                                    icon={Search}
                                    tint="info"
                                    title={`Nothing matches “${searchRes.query}”`}
                                    hint="Search sees dataset names and descriptions plus the Q&A pairs you can see (yours and public ones). Try a shorter word — the index stems endings and matches word prefixes."
                                />
                            )}
                            {searchRes.datasets.length > 0 && (
                                <section className="search-sec">
                                    <h2 className="search-sec-title">
                                        Datasets <span className="search-count">{searchRes.datasets.length}</span>
                                    </h2>
                                    {searchRes.datasets.map((d) => (
                                        <div className="search-hit" key={`d-${d.id}`}>
                                            <Link
                                                className="search-hit-title"
                                                to={d.is_mine ? `/datasets/${d.id}` : `/library/datasets/${d.id}`}
                                            >
                                                <Snippet text={d.name_snippet} fallback={d.name} />
                                            </Link>
                                            <span
                                                className={`badge ${d.is_mine ? "badge-neutral" : "badge-info"}`}
                                                title={d.is_mine ? "Yours" : "Public — read-only view"}
                                            >
                                                {d.is_mine ? "yours" : "public"}
                                            </span>
                                            <span className="badge badge-neutral">{displayStatus(d.source)}</span>
                                            <div className="search-hit-sub">
                                                <Snippet text={d.description_snippet} fallback={d.description ?? ""} />
                                            </div>
                                        </div>
                                    ))}
                                </section>
                            )}
                            {searchRes.pairs.length > 0 && (
                                <section className="search-sec">
                                    <h2 className="search-sec-title">
                                        Q&amp;A pairs <span className="search-count">{searchRes.pairs.length}</span>
                                    </h2>
                                    {searchRes.pairs.map((p) => (
                                        <div className="search-hit" key={`p-${p.id}`}>
                                            <Link
                                                className="search-hit-title"
                                                to={p.is_mine ? `/datasets/${p.dataset_id}` : `/library/datasets/${p.dataset_id}`}
                                            >
                                                <Snippet text={p.question_snippet} fallback={p.question} />
                                            </Link>
                                            <span
                                                className={`badge ${p.is_mine ? "badge-neutral" : "badge-info"}`}
                                                title={p.is_mine ? "Yours" : "Public — read-only view"}
                                            >
                                                {p.is_mine ? "yours" : "public"}
                                            </span>
                                            <div className="search-hit-sub">
                                                <Snippet text={p.answer_snippet} fallback={p.answer_preview} />
                                            </div>
                                            <div className="search-hit-dataset">
                                                in{" "}
                                                <Link to={p.is_mine ? `/datasets/${p.dataset_id}` : `/library/datasets/${p.dataset_id}`}>
                                                    {p.dataset_name}
                                                </Link>
                                            </div>
                                        </div>
                                    ))}
                                </section>
                            )}
                        </>
                    )}
                </div>
            ) : (
                <>
            {loading && (
                <p className="loading">
                    <VuMeter bars={4} /> Loading…
                </p>
            )}
            {error && <p className="form-error" role="alert">{error}</p>}
            {!loading && !error && datasets.length === 0 && (
                <EmptyState
                    icon={Database}
                    tint="info"
                    title="No datasets yet"
                    hint="A dataset is a set of question/answer pairs the model rehearses on. Create one, then add pairs by hand, generate, or import a file."
                    action={
                        <button className="btn btn-primary" onClick={openCreate}>
                            <Plus size={16} /> New dataset
                        </button>
                    }
                />
            )}

            {!loading && !error && datasets.length > 0 && (
                <div className="table">
                    <div className="table-head">
                        <div className="cell cell-grow">Name</div>
                        <div className="cell cell-source">Source</div>
                        <div className="cell cell-share">Share</div>
                        <div className="cell cell-date">Created</div>
                        <div className="cell cell-actions" />
                    </div>
                    {datasets.map((d) => (
                        <div className="table-row" key={d.id}>
                            <div className="cell cell-grow">
                                <Link to={`/datasets/${d.id}`} className="row-name">
                                    {d.name}
                                </Link>
                                {d.description && <div className="row-sub">{d.description}</div>}
                            </div>
                            <div className="cell cell-source">
                                <span className={`badge ${d.source === "generated" ? "badge-info" : "badge-neutral"}`}>
                                    {displayStatus(d.source)}
                                </span>
                            </div>
                            <div className="cell cell-share">
                                {/* S32: owner-only toggle; the backend 404s anyone else. */}
                                <ShareToggle
                                    kind="dataset"
                                    id={d.id}
                                    visibility={d.visibility}
                                    name={d.name}
                                    onToggled={(v: Visibility) =>
                                        setDatasets((prev) => prev.map((x) => (x.id === d.id ? { ...x, visibility: v } : x)))
                                    }
                                    onError={(msg) => setError(msg)}
                                />
                            </div>
                            <div className="cell cell-date">
                                {new Date(d.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                            </div>
                            <div className="cell cell-actions">
                                <button className="btn-icon" onClick={() => openEdit(d)} aria-label={`Edit ${d.name}`}>
                                    <Pencil size={15} />
                                </button>
                                <button
                                    className="btn-icon btn-icon-danger"
                                    onClick={() => setConfirmTarget(d)}
                                    aria-label={`Delete ${d.name}`}
                                >
                                    <Trash2 size={15} />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
                </>
            )}

            <DatasetFormModal
                open={form.open}
                mode={form.mode}
                dataset={form.dataset}
                onClose={closeForm}
                onSubmit={submitForm}
            />

            <ConfirmDialog
                open={confirmTarget !== null}
                title="Delete dataset?"
                message={
                    confirmTarget ? (
                        <>
                            This permanently deletes <strong>{confirmTarget.name}</strong> and its pairs. This can't be undone.
                        </>
                    ) : (
                        ""
                    )
                }
                onConfirm={confirmDelete}
                onCancel={() => setConfirmTarget(null)}
            />
        </div>
    );
}