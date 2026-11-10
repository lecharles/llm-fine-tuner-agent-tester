import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Eye, UserRound, ChevronLeft, ChevronRight } from "lucide-react";
import { apiFetch } from "../api";
import { displayStatus } from "../statusText";
import type { LibraryDatasetDetail as Detail } from "../types";
import VuMeter from "../components/VuMeter";
import EmptyState from "../components/EmptyState";

const PAGE_SIZE = 10;

// S53 (library 2): the read-only public dataset detail. Library cards land
// here instead of /datasets/:id so viewers never see owner affordances
// (generate/import/edit/delete) that would only 404 at the API. Everything
// comes from GET /api/library/datasets/{id} — metadata, a bounded Q&A
// preview, and the owner's profile line. Editing stays with the owner's own
// detail page.
export default function LibraryDatasetDetail() {
    const { datasetId } = useParams<{ datasetId: string }>();

    const [detail, setDetail] = useState<Detail | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [page, setPage] = useState(0);

    useEffect(() => {
        setLoading(true);
        setError(null);
        apiFetch<Detail>(`/library/datasets/${datasetId}`)
            .then(setDetail)
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to load the dataset"))
            .finally(() => setLoading(false));
    }, [datasetId]);

    const totalPages = detail ? Math.max(1, Math.ceil(detail.pairs.length / PAGE_SIZE)) : 1;
    const safePage = Math.min(page, totalPages - 1);
    const start = safePage * PAGE_SIZE;
    const pagePairs = detail ? detail.pairs.slice(start, start + PAGE_SIZE) : [];

    const fmtDate = (iso: string) =>
        new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });

    return (
        <div className="page dd-page">
            <Link to="/library" className="dd-back"><ArrowLeft size={15} /> Library</Link>

            {loading && (
                <p className="loading">
                    <VuMeter bars={4} /> Loading…
                </p>
            )}
            {error && <p className="form-error" role="alert">{error}</p>}

            {!loading && !error && !detail && (
                <EmptyState
                    icon={Eye}
                    tint="info"
                    title="Not in the library"
                    hint={<>This dataset is private or was unshared since the page opened. <Link to="/library">Back to the library</Link>.</>}
                />
            )}

            {!loading && detail && (
                <>
                    <div className="dd-head">
                        <h1 className="page-title">{detail.dataset.name}</h1>
                        <div className="dd-sub">
                            <span className={`badge ${detail.dataset.source === "generated" ? "badge-info" : "badge-neutral"}`}>
                                {displayStatus(detail.dataset.source)}
                            </span>
                            {detail.dataset.description && <span className="dd-desc">{detail.dataset.description}</span>}
                        </div>
                    </div>

                    {/* S53: the owner profile line — who shared this, and how
                        much of their work is in the library. */}
                    <div className="card">
                        <div className="library-row">
                            <span className="row-name">
                                <UserRound size={14} style={{ color: "var(--info)" }} /> shared by <b>{detail.owner.name}</b>
                            </span>
                        </div>
                        <div className="model-meta">
                            <span><b>{detail.owner.public_datasets}</b> public dataset{detail.owner.public_datasets === 1 ? "" : "s"}</span>
                            <span><b>{detail.owner.public_models}</b> public model{detail.owner.public_models === 1 ? "" : "s"}</span>
                            <span>member since <b>{fmtDate(detail.owner.member_since)}</b></span>
                            <span>shared <b>{fmtDate(detail.dataset.created_at)}</b></span>
                        </div>
                        <div className="dd-hint">
                            <Eye size={13} /> Read-only view — this dataset belongs to {detail.owner.name}. Only they can edit it or take it down.
                        </div>
                    </div>

                    {detail.dataset.use_case_prompt && (
                        <div className="card">
                            <div className="label">Use-case prompt</div>
                            <div className="dd-cell-text">{detail.dataset.use_case_prompt}</div>
                        </div>
                    )}

                    <div className="dd-pairs-head">
                        <div className="dd-pairs-title">
                            Q&amp;A pairs
                            <span className="dd-count-label">
                                · {detail.truncated
                                    ? `${detail.pairs.length} of ${detail.pair_count} shown (preview)`
                                    : detail.pair_count}
                            </span>
                        </div>
                    </div>

                    {detail.pairs.length === 0 ? (
                        <EmptyState
                            icon={Eye}
                            tint="info"
                            title="No pairs yet"
                            hint="The owner hasn't added any Q&A pairs to this dataset."
                        />
                    ) : (
                        <>
                            <div className="table">
                                <div className="table-head">
                                    <div className="cell cell-q">Question</div>
                                    <div className="cell cell-a">Answer</div>
                                </div>
                                {pagePairs.map((p) => (
                                    <div className="table-row" key={p.id}>
                                        <div className="cell cell-q dd-cell-text">{p.question}</div>
                                        <div className="cell cell-a dd-cell-text">{p.answer}</div>
                                    </div>
                                ))}
                            </div>

                            {totalPages > 1 && (
                                <div className="pager">
                                    <div className="pager-info">
                                        Showing {start + 1}–{Math.min(start + PAGE_SIZE, detail.pairs.length)} of {detail.pairs.length}
                                        {detail.truncated ? ` (preview of ${detail.pair_count})` : ""}
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
                </>
            )}
        </div>
    );
}
