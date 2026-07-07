import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";

type Props = {
    open: boolean;
    onClose: () => void;
    title: string;
    icon?: ReactNode; // optional accented icon in the header (e.g. the delete warning)
    children: ReactNode;
};

// A styled dialog: a full-viewport scrim plus a centered card. This is the app's
// answer to window.confirm, which is unstyleable and fails WCAG. Closes on the
// Escape key or a click on the scrim; a click inside the card is swallowed.
export default function Modal({ open, onClose, title, icon, children }: Props) {
    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") onClose();
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open, onClose]);

    if (!open) return null;

    return (
        <div className="modal-scrim" onClick={onClose}>
            <div
                className="modal"
                role="dialog"
                aria-modal="true"
                aria-label={title}
                onClick={(e) => e.stopPropagation()}
            >
                <div className="modal-head">
                    <div className="modal-title">
                        {icon}
                        {title}
                    </div>
                    <button className="icon-btn" onClick={onClose} aria-label="Close">
                        <X size={16} />
                    </button>
                </div>
                {children}
            </div>
        </div>
    );
}