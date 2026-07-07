import { useEffect, useState } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import {
    SlidersHorizontal, Route, Database, Cpu, Box, Columns3,
    PanelLeftClose, PanelLeft, Moon, Sun, LogOut,
} from "lucide-react";
import { apiFetch, clearToken } from "../api";

type Props = {
    collapsed: boolean;
    onToggleCollapse: () => void;
    theme: "dark" | "light";
    onToggleTheme: () => void;
};

// Each destination carries its own accent, so the sidebar reads as a color-coded
// map. Red and coral are deliberately absent here: they mean delete and hosted.
const NAV = [
    { to: "/get-started", label: "Get started", Icon: Route, color: "var(--accent-guide)" },
    { to: "/datasets", label: "Datasets", Icon: Database, color: "var(--info)" },
    { to: "/train", label: "Train", Icon: Cpu, color: "var(--warning)" },
    { to: "/models", label: "Models", Icon: Box, color: "var(--success)" },
    { to: "/compare", label: "Compare", Icon: Columns3, color: "var(--primary)" },
];

export default function Sidebar({ collapsed, onToggleCollapse, theme, onToggleTheme }: Props) {
    const navigate = useNavigate();
    const [email, setEmail] = useState("");

    // Show who is signed in: look up the current user once on mount.
    useEffect(() => {
        apiFetch<{ id: number; email: string }>("/auth/me")
            .then((user) => setEmail(user.email))
            .catch(() => { });
    }, []);

    function logout() {
        clearToken();
        navigate("/login");
    }

    return (
        <aside className="sidebar">
            <div className="sidebar-head">
                <div className="brand">
                    <span className="brand-mark">
                        <SlidersHorizontal size={14} style={{ color: "var(--primary)" }} />
                    </span>
                    <span className="brand-name">LLM Tuner</span>
                </div>
                <button
                    className="icon-btn"
                    onClick={onToggleCollapse}
                    aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                >
                    {collapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
                </button>
            </div>

            <nav className="nav">
                {NAV.map(({ to, label, Icon, color }) => (
                    <NavLink key={to} to={to} className="nav-link" title={collapsed ? label : undefined}>
                        <Icon size={16} style={{ color }} />
                        <span className="nav-label">{label}</span>
                    </NavLink>
                ))}
            </nav>

            <div className="sidebar-foot">
                <button className="theme-toggle" onClick={onToggleTheme}>
                    {theme === "dark" ? <Moon size={15} /> : <Sun size={15} />}
                    <span className="theme-label">{theme === "dark" ? "Dark" : "Light"}</span>
                    <span className="switch" />
                </button>
                <div className="account">
                    <span className="avatar">{email ? email[0].toUpperCase() : "?"}</span>
                    <div className="account-info">
                        <div className="account-email">{email || "\u2026"}</div>
                        <button className="logout" onClick={logout}>
                            <LogOut size={12} /> Log out
                        </button>
                    </div>
                </div>
            </div>
        </aside>
    );
}