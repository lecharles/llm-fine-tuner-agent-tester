import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { apiFetch } from "../api";
import type { Dataset } from "../types";
import DatasetFormModal, { type DatasetFormValues } from "../components/DatasetFormModal";
import ConfirmDialog from "../components/ConfirmDialog";

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

            {loading && <p className="loading">Loading…</p>}
            {error && <p className="form-error">{error}</p>}
            {!loading && !error && datasets.length === 0 && (
                <p className="empty">No datasets yet. Create your first one.</p>
            )}

            {!loading && !error && datasets.length > 0 && (
                <div className="table">
                    <div className="table-head">
                        <div className="cell cell-grow">Name</div>
                        <div className="cell cell-source">Source</div>
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
                                    {d.source}
                                </span>
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