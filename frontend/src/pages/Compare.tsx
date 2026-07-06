import { useEffect, useRef, useState } from "react";
import { apiFetch } from "../api";
import type { FineTunedModel, ChatSession, ChatMessage } from "../types";

// The four compare columns, in display order. The backend tags each assistant
// reply with one of these model_label values.
const COLUMNS = ["fine_tuned", "vanilla", "openai", "anthropic"] as const;
const COLUMN_LABEL: Record<string, string> = {
    fine_tuned: "Fine-tuned",
    vanilla: "Vanilla base",
    openai: "OpenAI",
    anthropic: "Anthropic",
};

export default function Compare() {
    const [models, setModels] = useState<FineTunedModel[]>([]);
    const [modelId, setModelId] = useState<number | "">("");
    const [prompt, setPrompt] = useState("");
    const [replies, setReplies] = useState<ChatMessage[]>([]);
    const [sending, setSending] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // The session id lives in a ref: it persists across renders and we read it
    // synchronously inside the send handler. null means "no session yet".
    const sessionRef = useRef<number | null>(null);
    // Which model the current session was created for, so we can detect a change.
    const sessionModelRef = useRef<number | null>(null);

    // Load the model picker options.
    useEffect(() => {
        apiFetch<FineTunedModel[]>("/fine-tuned-models")
            .then(setModels)
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to load models"));
    }, []);

    // Lazy session: create one only when we first need it (or when the chosen
    // model changed since the last session). Returns the session id to use.
    async function ensureSession(): Promise<number> {
        if (sessionRef.current !== null && sessionModelRef.current === modelId) {
            return sessionRef.current;
        }
        const session = await apiFetch<ChatSession>("/chat-sessions", {
            method: "POST",
            body: { fine_tuned_model_id: modelId },
        });
        sessionRef.current = session.id;
        sessionModelRef.current = modelId as number;
        return session.id;
    }

    async function handleSend(e: React.FormEvent) {
        e.preventDefault();
        if (modelId === "" || prompt.trim() === "") return;
        setSending(true);
        setError(null);
        try {
            const sessionId = await ensureSession(); // create-on-first-use
            // POST the prompt; backend fans out to all four and returns the user
            // turn plus the four assistant replies (each tagged by model_label).
            const messages = await apiFetch<ChatMessage[]>(
                `/chat-sessions/${sessionId}/messages`,
                { method: "POST", body: { content: prompt } }
            );
            // Keep only the assistant replies for the columns (drop the user turn).
            setReplies(messages.filter((m) => m.role === "assistant"));
        } catch (err) {
            setError(err instanceof Error ? err.message : "Send failed");
        } finally {
            setSending(false);
        }
    }

    // Find the reply for a given column, if it came back (a column can be absent
    // if its backend call errored — per-column isolation).
    function replyFor(label: string): ChatMessage | undefined {
        return replies.find((m) => m.model_label === label);
    }

    return (
        <div>
            <h1>Compare</h1>

            <form onSubmit={handleSend}>
                <select
                    value={modelId}
                    onChange={(e) => setModelId(e.target.value === "" ? "" : Number(e.target.value))}
                    required
                >
                    <option value="">Select a fine-tuned model</option>
                    {models.map((m) => (
                        <option key={m.id} value={m.id}>
                            {m.name}
                        </option>
                    ))}
                </select>
                <input
                    placeholder="Ask all four models something..."
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    required
                />
                <button type="submit" disabled={sending}>
                    {sending ? "Asking all four..." : "Send"}
                </button>
            </form>

            {error && <p>Error: {error}</p>}

            {/* Four columns. Unstyled: four labeled blocks. The grid layout is a
          styling-phase concern; the four labeled replies are all here. */}
            <div>
                {COLUMNS.map((label) => {
                    const reply = replyFor(label);
                    return (
                        <div key={label}>
                            <h3>{COLUMN_LABEL[label]}</h3>
                            {sending && <p>...</p>}
                            {!sending && reply && <p>{reply.content}</p>}
                            {!sending && !reply && replies.length > 0 && <p>(no reply)</p>}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}