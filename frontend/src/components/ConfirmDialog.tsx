import type { ReactNode } from "react";
import { Trash2 } from "lucide-react";
import Modal from "./Modal";

type Props = {
    open: boolean;
    title: string;
    message: ReactNode;
    confirmLabel?: string;
    onConfirm: () => void;
    onCancel: () => void;
};

// One confirm dialog for every destructive action. Danger styling (red icon,
// red confirm button) is baked in so "are you sure?" always looks the same.
export default function ConfirmDialog({
    open,
    title,
    message,
    confirmLabel = "Delete",
    onConfirm,
    onCancel,
}: Props) {
    return (
        <Modal
            open={open}
            onClose={onCancel}
            title={title}
            icon={
                <span className="modal-icon danger">
                    <Trash2 size={16} />
                </span>
            }
        >
            <p className="modal-message">{message}</p>
            <div className="modal-actions">
                <button className="btn btn-ghost" onClick={onCancel}>
                    Cancel
                </button>
                <button className="btn btn-danger" onClick={onConfirm}>
                    {confirmLabel}
                </button>
            </div>
        </Modal>
    );
}