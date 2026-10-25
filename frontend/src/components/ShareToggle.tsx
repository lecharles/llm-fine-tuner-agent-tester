import { useState } from "react";
import { Globe, Lock } from "lucide-react";
import { apiFetch } from "../api";

export type Visibility = "public" | "private";

type Props = {
    // Anything that isn't exactly "public" renders as private, so responses
    // from a backend that predates S31 degrade safely instead of crashing.
    visibility: string;
    name: string;
    kind: "dataset" | "model";
    id: number;
    onToggled: (next: Visibility) => void;
    onError: (message: string) => void;
};

// S32 (sharing 2): the owner-side share toggle. Datasets ride the normal
// owner-only PUT (only `visibility` is sent, exclude_unset keeps the rest);
// models use their dedicated PATCH. Backend stays the authority: both routes
// are owner-only and 404 anything that isn't yours.
export default function ShareToggle({ visibility, name, kind, id, onToggled, onError }: Props) {
    const [busy, setBusy] = useState(false);
    const isPublic = visibility === "public";
    const next: Visibility = isPublic ? "private" : "public";

    async function toggle() {
        setBusy(true);
        try {
            if (kind === "dataset") {
                await apiFetch(`/datasets/${id}`, { method: "PUT", body: { visibility: next } });
            } else {
                await apiFetch(`/fine-tuned-models/${id}/visibility`, {
                    method: "PATCH",
                    body: { visibility: next },
                });
            }
            onToggled(next);
        } catch (err) {
            onError(err instanceof Error ? err.message : "Share update failed");
        } finally {
            setBusy(false);
        }
    }

    return (
        <button
            type="button"
            className={`share-toggle${isPublic ? " share-public" : ""}`}
            onClick={toggle}
            disabled={busy}
            aria-label={
                isPublic
                    ? `Unshare ${name}: make it private again`
                    : `Share ${name}: let everyone signed-in read it`
            }
            title={
                isPublic
                    ? "Public — anyone signed in can read it. Click to make private."
                    : "Private — only you can see it. Click to share with everyone."
            }
        >
            {isPublic ? <Globe size={13} /> : <Lock size={13} />}
            <span>{busy ? "Saving…" : isPublic ? "Public" : "Private"}</span>
        </button>
    );
}
