import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import Sidebar from "./Sidebar";

type Theme = "dark" | "light";

// The app shell. The sidebar renders once here; each page swaps into <main>
// through the router's Outlet. Collapse and theme are state at this level.
export default function Layout() {
    const [collapsed, setCollapsed] = useState(false);
    const [theme, setTheme] = useState<Theme>(
        () => (localStorage.getItem("theme") as Theme) || "dark"
    );

    // Reflect the theme on <html> so the [data-theme] variables apply, and
    // remember the choice across refreshes.
    useEffect(() => {
        document.documentElement.dataset.theme = theme;
        localStorage.setItem("theme", theme);
    }, [theme]);

    return (
        <div className={`app-shell${collapsed ? " is-collapsed" : ""}`}>
            <Sidebar
                collapsed={collapsed}
                onToggleCollapse={() => setCollapsed((c) => !c)}
                theme={theme}
                onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
            />
            <main className="app-main">
                <Outlet />
            </main>
        </div>
    );
}