import { useEffect, useState } from "react";
import { apiFetch } from "../api";

export type TierStatus = { ready: boolean; reason: string; models?: string[] };
export type GenerationStatus = {
    tiers: Record<"anthropic" | "openai" | "ollama", TierStatus>;
    ready_count: number;
    usable: boolean;
    summary: string;
};

// Fetch the backend's view of which generation tiers are reachable. Errors are
// swallowed on purpose: a missing endpoint means an older backend, and the
// status line simply stays hidden rather than breaking the page.
export function useGenerationStatus(): GenerationStatus | null {
    const [status, setStatus] = useState<GenerationStatus | null>(null);
    useEffect(() => {
        let live = true;
        apiFetch<GenerationStatus>("/generation/status")
            .then((s) => { if (live) setStatus(s); })
            .catch(() => {});
        return () => { live = false; };
    }, []);
    return status;
}

// Inline pre-flight line: shows which providers generation can actually use
// before the user spends a minute watching "Generating..." fail.
export function GenerationStatusLine() {
    const status = useGenerationStatus();
    if (!status) return null;
    if (status.usable) {
        const ready = Object.entries(status.tiers).filter(([, t]) => t.ready).map(([n]) => n);
        return (
            <div className="dd-hint">
                Ready: {ready.join(", ")}.
                {Object.entries(status.tiers).filter(([, t]) => !t.ready).length > 0 &&
                    ` Unavailable: ${Object.entries(status.tiers).filter(([, t]) => !t.ready).map(([n, t]) => `${n} (${t.reason})`).join("; ")}.`}
            </div>
        );
    }
    return (
        <div className="dd-hint dd-hint-warn">
            Generation can't reach any backend yet. {status.summary}
        </div>
    );
}
