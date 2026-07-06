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
    const [messages, setMessages] = useState<ChatMessage[]>([]);
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
            // Append the whole turn to the running transcript, then clear the box.
            setMessages((prev) => [...prev, ...turn]);
            setPrompt("");
        } catch (err) {
            setError(err instanceof Error ? err.message : "Send failed");
        } finally {
            setSending(false);
        }
    }

    // Group the flat message list into turns: each user message starts a turn and
    // the assistant replies that follow attach to it. This is what lets us render
    // the conversation as prompt -> four answers, repeated down the page.
    type Turn = { id: number; prompt: string; replies: ChatMessage[] };
    const turns: Turn[] = [];
    for (const m of messages) {
        if (m.role === "user") {
            turns.push({ id: m.id, prompt: m.content, replies: [] });
        } else if (turns.length > 0) {
            turns[turns.length - 1].replies.push(m);
        }
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

            {messages.length === 0 && !sending && <p>Pick a model and ask all four something.</p>}

            {/* The transcript: each turn is the prompt, then the four columns'
          answers for that turn. Unstyled; the grid is a styling-phase concern. */}
            {turns.map((turn) => (
                <div key={turn.id}>
                    <p><strong>You:</strong> {turn.prompt}</p>
                    <div>
                        {COLUMNS.map((label) => {
                            const reply = turn.replies.find((r) => r.model_label === label);
                            return (
                                <div key={label}>
                                    <h3>{COLUMN_LABEL[label]}</h3>
                                    {reply ? <p>{reply.content}</p> : <p>(no reply)</p>}
                                </div>
                            );
                        })}
                    </div>
                </div>
            ))}

            {sending && <p>Asking all four...</p>}
        </div>
    );
}