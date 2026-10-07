import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { apiFetch, clearToken } from "../api";

// S20: who is signed in, and a small Linear-style user menu. The trigger sits
// in the sidebar foot (avatar + name/email); clicking it opens a popover with
// the full identity and the log-out action. The popover is positioned fixed
// from the trigger's rect so the sidebar's overflow never clips it.

type Me = { id: number; email: string; display_name: string | null };

export default function UserMenu() {
    const navigate = useNavigate();
    const [me, setMe] = useState<Me | null>(null);
    const [open, setOpen] = useState(false);
    const [pos, setPos] = useState<{ left: number; bottom: number } | null>(null);
    const triggerRef = useRef<HTMLButtonElement>(null);
    const rootRef = useRef<HTMLDivElement>(null);

    // Look up the current user once on mount; GET /api/auth/me is the source.
    useEffect(() => {
        apiFetch<Me>("/auth/me")
            .then(setMe)
            .catch(() => { });
    }, []);

    // Dismiss on Escape or a click outside, like Modal does elsewhere in the app.
    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") setOpen(false);
        };
        const onMouseDown = (e: MouseEvent) => {
            if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false);
        };
        window.addEventListener("keydown", onKey);
        window.addEventListener("mousedown", onMouseDown);
        return () => {
            window.removeEventListener("keydown", onKey);
            window.removeEventListener("mousedown", onMouseDown);
        };
    }, [open]);

    function toggle() {
        if (!open && triggerRef.current) {
            // Anchor the popover just above the trigger, in viewport coords.
            const r = triggerRef.current.getBoundingClientRect();
            setPos({ left: r.left, bottom: window.innerHeight - r.top + 6 });
        }
        setOpen(!open);
    }

    function logout() {
        setOpen(false);
        clearToken();
        navigate("/login");
    }

    const email = me?.email ?? "";
    const name = me?.display_name?.trim() || "";
    const label = name || email || "\u2026";
    const initial = (name || email || "?")[0].toUpperCase();

    return (
        <div className="user-menu" ref={rootRef}>
            {open && pos && (
                <div
                    className="user-menu-pop"
                    role="menu"
                    aria-label="Account menu"
                    style={{ left: pos.left, bottom: pos.bottom }}
                >
                    <div className="user-menu-id">
                        <span className="avatar" aria-hidden="true">{initial}</span>
                        <div className="user-menu-idtext">
                            {name && <div className="user-menu-name">{name}</div>}
                            <div className="user-menu-email">{email}</div>
                        </div>
                    </div>
                    <div className="user-menu-sep" />
                    <button role="menuitem" className="user-menu-item" onClick={logout}>
                        <LogOut size={13} /> Log out
                    </button>
                </div>
            )}
            <button
                ref={triggerRef}
                className="user-menu-trigger"
                onClick={toggle}
                aria-haspopup="menu"
                aria-expanded={open}
                aria-label={me ? `Account: ${label}` : "Account"}
            >
                <span className="avatar" aria-hidden="true">{initial}</span>
                <span className="user-menu-label">{label}</span>
            </button>
        </div>
    );
}
