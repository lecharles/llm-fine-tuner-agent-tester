import { useEffect, useState, type FormEvent } from "react";
import Modal from "./Modal";
import type { QAPair } from "../types";

export type QAPairValues = { question: string; answer: string };

type Props = {
    open: boolean;
    mode: "create" | "edit";
    pair: QAPair | null; // on edit, its values pre-fill the form
    onClose: () => void;
    onSubmit: (values: QAPairValues) => Promise<void>;
};

// One form for adding and editing a Q&A pair. The parent owns the API call.
export default function QAPairModal({ open, mode, pair, onClose, onSubmit }: Props) {
    const [question, setQuestion] = useState("");
    const [answer, setAnswer] = useState("");
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (open) {
            setQuestion(pair?.question ?? "");
            setAnswer(pair?.answer ?? "");
            setError(null);
        }
    }, [open, pair]);

    async function submit(e: FormEvent) {
        e.preventDefault();
        setBusy(true);
        setError(null);
        try {
            await onSubmit({ question, answer });
            onClose();
        } catch (err) {
            setError(err instanceof Error ? err.message : "Something went wrong");
        } finally {
            setBusy(false);
        }
    }

    return (
        <Modal open={open} onClose={onClose} title={mode === "create" ? "Add pair" : "Edit pair"}>
            <form className="form" onSubmit={submit}>
                <div className="field">
                    <label className="label">Question</label>
                    <textarea className="textarea" rows={2} value={question} onChange={(e) => setQuestion(e.target.value)} required autoFocus />
                </div>
                <div className="field">
                    <label className="label">Answer</label>
                    <textarea className="textarea" rows={3} value={answer} onChange={(e) => setAnswer(e.target.value)} required />
                </div>
                {error && <p className="form-error">{error}</p>}
                <div className="modal-actions">
                    <button type="button" className="btn btn-ghost" onClick={onClose}>Cancel</button>
                    <button type="submit" className="btn btn-primary" disabled={busy}>
                        {busy ? "Saving\u2026" : mode === "create" ? "Add pair" : "Save changes"}
                    </button>
                </div>
            </form>
        </Modal>
    );
}