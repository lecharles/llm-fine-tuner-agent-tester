import { useEffect, useState, type FormEvent } from "react";
import Modal from "./Modal";
import type { Dataset } from "../types";

export type DatasetFormValues = { name: string; description: string; source: string };

type Props = {
    open: boolean;
    mode: "create" | "edit";
    dataset: Dataset | null; // on edit, its values pre-fill the form
    onClose: () => void;
    onSubmit: (values: DatasetFormValues) => Promise<void>;
};

// Create and edit are the same form. The parent owns the API call (passed as
// onSubmit) and just tells us the mode and, for edit, which dataset to seed from.
export default function DatasetFormModal({ open, mode, dataset, onClose, onSubmit }: Props) {
    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [source, setSource] = useState("manual");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // Re-seed the fields each time the modal opens, so edit shows current values
    // and create always starts blank.
    useEffect(() => {
        if (open) {
            setName(dataset?.name ?? "");
            setDescription(dataset?.description ?? "");
            setSource(dataset?.source ?? "manual");
            setError(null);
        }
    }, [open, dataset]);

    async function submit(e: FormEvent) {
        e.preventDefault();
        setBusy(true);
        setError(null);
        try {
            await onSubmit({ name, description, source });
            onClose();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Something went wrong");
        } finally {
            setBusy(false);
        }
    }

    return (
        <Modal open={open} onClose={onClose} title={mode === "create" ? "New dataset" : "Edit dataset"}>
            <form className="form" onSubmit={submit}>
                <div className="field">
                    <label className="label">Name</label>
                    <input className="input" value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
                </div>
                <div className="field">
                    <label className="label">Description</label>
                    <input
                        className="input"
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="Optional"
                    />
                </div>
                {mode === "create" && (
                    <div className="field">
                        <label className="label">Source</label>
                        <select className="select" value={source} onChange={(e) => setSource(e.target.value)}>
                            <option value="manual">Manual</option>
                            <option value="generated">Generated</option>
                            <option value="imported">Imported</option>
                        </select>
                    </div>
                )}
                {error && <p className="form-error">{error}</p>}
                <div className="modal-actions">
                    <button type="button" className="btn btn-ghost" onClick={onClose}>
                        Cancel
                    </button>
                    <button type="submit" className="btn btn-primary" disabled={busy}>
                        {busy ? "Saving\u2026" : mode === "create" ? "Create dataset" : "Save changes"}
                    </button>
                </div>
            </form>
        </Modal>
    );
}