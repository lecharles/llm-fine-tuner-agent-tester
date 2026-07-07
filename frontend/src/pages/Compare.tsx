import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { apiFetch } from "../api";
import type { FineTunedModel, ChatSession, ChatMessage } from "../types";

// The four compare columns, in display order. The backend tags each assistant
// reply with one of these model_label values.
const COLUMNS = ["fine_tuned", "vanilla", "openai", "anthropic"] as const;

// Per-column display: a name, a category (your model / baseline / hosted), and
// an accent color. Both hosted columns share the coral, on purpose.
const COL_NAME: Record<string, string> = {
    fine_tuned: "Fine-tuned",
    vanilla: "Vanilla base",
    openai: "OpenAI",
    anthropic: "Anthropic",
};
const COL_CATEGORY: Record<string, string> = {
    fine_tuned: "Your model",
    vanilla: "Baseline",
    openai: "Hosted",
    anthropic: "Hosted",
};
const COL_COLOR: Record<string, string> = {
    fine_tuned: "var(--primary)",
    vanilla: "var(--text-muted)",
    openai: "var(--hosted)",
    anthropic: "var(--hosted)",
};

export default function Compare() {
    const [models, setModels] = useState<FineTunedModel[]>([]);
    const [modelId, setModelId] = useState<number | "">("");
    const [prompt, setPrompt] = useState("");
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [sending, setSending] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // The session id lives in a ref: it persists across renders and we read it
    // synchronously inside the send handler. null means "no session yet".
    const sessionRef = useRef<number | null>(null);
    // Which model the current session was created for, so we can detect a change.
    const sessionModelRef = useRef<number | null>(null);
    // The columns container, so we can keep each thread scrolled to the bottom.
    const colsRef = useRef<HTMLDivElement>(null);

    // Load the model picker options.
    useEffect(() => {
        apiFetch<FineTunedModel[]>("/fine-tuned-models")
            .then(setModels)
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to load models"));
    }, []);

    // On every new message (or while a reply is pending), pin each column's
    // thread to the bottom so the latest turn is in view.
    useEffect(() => {
        colsRef.current?.querySelectorAll(".compare-thread").forEach((t) => {
            t.scrollTop = t.scrollHeight;
        });
    }, [messages, sending]);

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
        setMessages([]); // a new session (first use or model change) starts a fresh transcript
        return session.id;
    }

    async function handleSend(e: React.FormEvent) {
        e.preventDefault();
        if (modelId === "" || prompt.trim() === "") return;
        setSending(true);
        setError(null);
        try {
            const sessionId = await ensureSession(); // create-on-first-use
            // POST the prompt; backend threads each column's history, fans out to
            // all four, and returns this turn's user message plus the four replies.
            const turn = await apiFetch<ChatMessage[]>(
                `/chat-sessions/${sessionId}/messages`,
                { method: "POST", body: { content: prompt } }
            );
            setMessages((prev) => [...prev, ...turn]);
            setPrompt("");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Send failed");
        } finally {
            setSending(false);
        }
    }

    // Each column is its own conversation: the shared user turns interleaved with
    // only that column's own replies. Filtering the flat list gives exactly that.
    function columnThread(label: string): ChatMessage[] {
        return messages.filter((m) => m.role === "user" || m.model_label === label);
    }

    return (
        <div className="compare">
            <div className="compare-head">
                <div>
                    <div className="page-eyebrow" style={{ color: "var(--primary)" }}>Agent tester</div>
                    <h1 className="page-title">Compare</h1>
                </div>
                <select
                    className="select compare-model-select"
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
            </div>

            {error && <p className="form-error">{error}</p>}

            <div className="compare-cols" ref={colsRef}>
                {COLUMNS.map((label) => (
                    <div className="compare-col" key={label}>
                        <div className="compare-col-head">
                            <span className="col-dot" style={{ background: COL_COLOR[label] }} />
                            <span className="col-name" style={{ color: COL_COLOR[label] }}>{COL_NAME[label]}</span>
                            <span className="col-cat">{COL_CATEGORY[label]}</span>
                        </div>
                        <div className="compare-thread">
                            {columnThread(label).map((m) =>
                                m.role === "user" ? (
                                    <div className="msg msg-user" key={m.id}>
                                        <div className="bubble bubble-user">{m.content}</div>
                                    </div>
                                ) : (
                                    <div className="msg msg-model" key={m.id}>
                                        <div className="bubble bubble-model">{m.content}</div>
                                    </div>
                                )
                            )}
                            {sending && (
                                <div className="msg msg-model">
                                    <div className="thinking" style={{ color: COL_COLOR[label] }}>
                                        <span className="tdot" />
                                        <span className="tdot" />
                                        <span className="tdot" />
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            <form className="compare-input" onSubmit={handleSend}>
                <input
                    className="input"
                    placeholder="Message all four models…"
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    required
                />
                <button type="submit" className="btn btn-primary" disabled={sending || modelId === "" || prompt.trim() === ""}>
                    <Send size={16} /> {sending ? "Asking…" : "Send"}
                </button>
            </form>
        </div>
    );
}