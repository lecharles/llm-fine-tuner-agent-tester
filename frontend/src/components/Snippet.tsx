// S68 (Search 2): renders an FTS5 snippet with the server's '[' … ']' match
// marks as real <mark> elements. React escapes every text node, so this is
// XSS-safe by construction — the marked spans are the ONLY thing the snippet
// string can influence, and it can never inject markup the way an
// innerHTML-based highlighter would. Unbalanced brackets (they were part of
// the user's own text) just render as literal characters.

import type { ReactNode } from "react";

const MARK = /\[([^[\]]*)\]/g;

export default function Snippet({ text, fallback }: { text: string; fallback?: string }) {
    const source = text || fallback || "";
    if (!source) return null;

    const parts: ReactNode[] = [];
    let last = 0;
    let key = 0;
    for (const m of source.matchAll(MARK)) {
        const at = m.index ?? 0;
        if (at > last) parts.push(source.slice(last, at));
        if (m[1]) parts.push(<mark key={key++} className="hit-mark">{m[1]}</mark>);
        last = at + m[0].length;
    }
    if (last < source.length) parts.push(source.slice(last));

    return <span className="snippet">{parts}</span>;
}
