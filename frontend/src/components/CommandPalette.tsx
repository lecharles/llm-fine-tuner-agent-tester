import { useEffect, useMemo, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { useNavigate } from "react-router-dom";
import {
    Search, Database, MessagesSquare, CornerDownLeft, Globe, Lock, ArrowUp, ArrowDown,
} from "lucide-react";
import { apiSearch } from "../api";
import type { SearchResults } from "../types";
import Snippet from "./Snippet";

type Item = {
    kind: "dataset" | "pair" | "nav";
    label: string;      // primary line (may carry [marks] for search hits)
    sub: string;        // secondary line
    to: string;         // route to push on select
    marked?: boolean;   // label is an FTS snippet — render marks, not text
    subMarked?: boolean; // sub is also an FTS snippet (dataset description)
    mine?: boolean;     // ownership badge (search hits only)
};

// Every authenticated page, for the empty-query "jump to" state. Kept
// intentionally small and route-only: the palette navigates, it never acts —
// no mutation lives behind an ⌘K Enter.
const PAGES: Item[] = [
    { kind: "nav", label: "Welcome", sub: "/welcome", to: "/welcome" },
    { kind: "nav", label: "Get started", sub: "/get-started", to: "/get-started" },
    { kind: "nav", label: "Datasets", sub: "/datasets", to: "/datasets" },
    { kind: "nav", label: "Train", sub: "/train", to: "/train" },
    { kind: "nav", label: "History", sub: "/history", to: "/history" },
    { kind: "nav", label: "Models", sub: "/models", to: "/models" },
    { kind: "nav", label: "Compare", sub: "/compare", to: "/compare" },
    { kind: "nav", label: "Library", sub: "/library", to: "/library" },
    { kind: "nav", label: "Bridge", sub: "/bridge", to: "/bridge" },
    { kind: "nav", label: "Settings", sub: "/settings", to: "/settings" },
];

// Where a hit leads. The S31 rule, mirrored in the UI: your rows open the
// owner page (full CRUD), anyone's PUBLIC rows open the S53 read-only
// library detail. is_mine is the only ownership signal the API ships.
function datasetTarget(id: number, mine: boolean): string {
    return mine ? `/datasets/${id}` : `/library/datasets/${id}`;
}

const DEBOUNCE_MS = 250;
const SECTION_LIMIT = 7;

// S68: the shell's Command-K palette. ⌘K / Ctrl+K anywhere in the guarded
// shell opens it; typing runs the S67 FTS5 endpoint (debounced, one request
// in flight — a stale response can never overwrite a newer query's results).
// Empty query = page navigation; non-empty = dataset + QA-pair hits.
// Keyboard-first: ↑/↓ move the cursor, Enter goes, Esc closes, clicking the
// scrim or a result does the same. Results never echo owner metadata.
export default function CommandPalette() {
    const navigate = useNavigate();
    const [open, setOpen] = useState(false);
    const [query, setQuery] = useState("");
    const [results, setResults] = useState<SearchResults | null>(null);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [cursor, setCursor] = useState(0);
    const inputRef = useRef<HTMLInputElement>(null);
    const listRef = useRef<HTMLDivElement>(null);
    const seq = useRef(0); // request generation: late responses get dropped

    // Global hotkey. Registered once; the handler reads state via callbacks
    // only, so it never goes stale. The sidebar trigger dispatches the same
    // open via a shell event, so key and button share one code path and the
    // reset-on-close effect below guarantees every open starts fresh.
    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
                e.preventDefault();
                setOpen((o) => !o);
            }
        };
        const onOpen = () => setOpen(true);
        window.addEventListener("keydown", onKey);
        window.addEventListener("llmtuner:open-palette", onOpen);
        return () => {
            window.removeEventListener("keydown", onKey);
            window.removeEventListener("llmtuner:open-palette", onOpen);
        };
    }, []);

    // Autofocus on open; wipe query/results on close so the next ⌘K opens
    // empty instead of mid-search from wherever the user left it.
    useEffect(() => {
        if (open) {
            inputRef.current?.focus();
        } else {
            seq.current += 1; // any in-flight response is now orphaned
            setBusy(false);
            setQuery("");
            setResults(null);
            setError(null);
            setCursor(0);
        }
    }, [open]);

    const q = query.trim();

    // Debounced search. Closing the palette or typing a blank clears state.
    useEffect(() => {
        if (!open || q.length === 0) return;
        const mine = ++seq.current;
        setBusy(true);
        setError(null);
        const t = setTimeout(() => {
            apiSearch<SearchResults>(q, SECTION_LIMIT)
                .then((r) => {
                    if (seq.current !== mine) return; // a newer query won
                    setResults(r);
                    setCursor(0);
                })
                .catch((err) => {
                    if (seq.current !== mine) return;
                    setResults(null);
                    setError(err instanceof Error ? err.message : "Search failed");
                })
                .finally(() => {
                    if (seq.current === mine) setBusy(false);
                });
        }, DEBOUNCE_MS);
        return () => clearTimeout(t);
    }, [open, q]);

    const items = useMemo<Item[]>(() => {
        if (q.length === 0) return PAGES;
        const out: Item[] = [];
        for (const d of results?.datasets ?? []) {
            out.push({
                kind: "dataset",
                label: d.name_snippet || d.name,
                sub: d.description_snippet || d.description || d.source,
                to: datasetTarget(d.id, d.is_mine),
                marked: true,
                subMarked: true,
                mine: d.is_mine,
            });
        }
        for (const p of results?.pairs ?? []) {
            out.push({
                kind: "pair",
                label: p.question_snippet || p.question,
                sub: p.dataset_name,
                to: datasetTarget(p.dataset_id, p.is_mine),
                marked: true,
                mine: p.is_mine,
            });
        }
        // While typing before the debounce lands, don't show the page list.
        return out;
    }, [q, results]);

    const close = () => setOpen(false);
    const go = (item: Item) => {
        close();
        navigate(item.to);
    };

    // Keep the cursor in bounds when the list changes underneath it.
    useEffect(() => {
        setCursor((c) => Math.min(c, Math.max(items.length - 1, 0)));
    }, [items.length]);

    const onInputKey = (e: ReactKeyboardEvent) => {
        if (e.key === "Escape") {
            e.preventDefault();
            close();
        } else if (e.key === "ArrowDown") {
            e.preventDefault();
            setCursor((c) => (items.length ? (c + 1) % items.length : 0));
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setCursor((c) => (items.length ? (c - 1 + items.length) % items.length : 0));
        } else if (e.key === "Enter") {
            e.preventDefault();
            const item = items[cursor];
            if (item) go(item);
        }
    };

    // Scroll the cursor row into view (keyboard-only navigation).
    useEffect(() => {
        const el = listRef.current?.querySelector<HTMLElement>("[data-cursor='true']");
        el?.scrollIntoView({ block: "nearest" });
    }, [cursor, items.length]);

    if (!open) return null;

    const nothing =
        q.length > 0 && !busy && !error && items.length === 0;

    return (
        <div className="cmdk-scrim" onClick={close} role="presentation">
            <div
                className="cmdk"
                role="dialog"
                aria-modal="true"
                aria-label="Command palette"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="cmdk-input-row">
                    <Search size={15} className="cmdk-icon" />
                    <input
                        ref={inputRef}
                        className="cmdk-input"
                        placeholder="Search datasets and Q&A, or type a page name…"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                        onKeyDown={onInputKey}
                        aria-label="Search"
                        spellCheck={false}
                        autoComplete="off"
                    />
                    {busy && <span className="cmdk-busy" aria-live="polite">searching…</span>}
                    <kbd className="cmdk-kbd">esc</kbd>
                </div>

                {error && (
                    <p className="cmdk-error" role="alert">{error}</p>
                )}
                {nothing && (
                    <p className="cmdk-empty">No matches for “{q}” — search covers dataset names, descriptions and your visible Q&amp;A pairs.</p>
                )}

                <div className="cmdk-list" role="listbox" ref={listRef}>
                    {q.length === 0 && <div className="cmdk-group">Go to</div>}
                    {q.length > 0 && (results?.datasets?.length ?? 0) > 0 && (
                        <div className="cmdk-group">Datasets</div>
                    )}
                    {items.map((item, i) => {
                        const showPairsHeader =
                            q.length > 0 &&
                            item.kind === "pair" &&
                            items[i - 1]?.kind !== "pair";
                        return (
                            <div key={`${item.kind}-${item.to}-${i}`}>
                                {showPairsHeader && <div className="cmdk-group">Q&amp;A pairs</div>}
                                <button
                                    className="cmdk-item"
                                    data-cursor={i === cursor ? "true" : "false"}
                                    role="option"
                                    aria-selected={i === cursor}
                                    onMouseEnter={() => setCursor(i)}
                                    onClick={() => go(item)}
                                >
                                    <span className="cmdk-item-icon">
                                        {item.kind === "dataset" ? (
                                            <Database size={14} />
                                        ) : item.kind === "pair" ? (
                                            <MessagesSquare size={14} />
                                        ) : (
                                            <CornerDownLeft size={14} />
                                        )}
                                    </span>
                                    <span className="cmdk-item-body">
                                        <span className="cmdk-item-label">
                                            {item.marked ? <Snippet text={item.label} /> : item.label}
                                        </span>
                                        <span className="cmdk-item-sub">
                                            {item.subMarked ? <Snippet text={item.sub} /> : item.sub}
                                        </span>
                                    </span>
                                    {item.kind !== "nav" && (
                                        <span
                                            className={`cmdk-own ${item.mine ? "is-mine" : "is-public"}`}
                                            title={item.mine ? "Yours" : "Public — read-only"}
                                        >
                                            {item.mine ? <Lock size={12} /> : <Globe size={12} />}
                                        </span>
                                    )}
                                    {i === cursor && (
                                        <span className="cmdk-go" aria-hidden="true">↵</span>
                                    )}
                                </button>
                            </div>
                        );
                    })}
                </div>

                <div className="cmdk-foot">
                    <span><ArrowUp size={11} /> <ArrowDown size={11} /> navigate</span>
                    <span><CornerDownLeft size={11} /> open</span>
                    <span>FTS5 full-text · stems + prefixes</span>
                </div>
            </div>
        </div>
    );
}
