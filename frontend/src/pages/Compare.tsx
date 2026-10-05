import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { apiFetch } from "../api";
import VuMeter from "../components/VuMeter";
import type { FineTunedModel, ChatSession, ChatMessage, ChatTurn } from "../types";

// The four always-on compare columns, in display order. The backend tags each
// assistant reply with one of these model_label values. S13 (#15) adds a
// fifth, optional "ollama" column that only exists while a model is picked.
const BASE_COLUMNS = ["fine_tuned", "vanilla", "openai", "anthropic"] as const;

// Hardcoded hosted model pickers (S13, #15). The defaults match the backend
// schema defaults in schemas/chat.py, so untouched pickers behave exactly
// like before this feature existed.
const OPENAI_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-5.5"];
const ANTHROPIC_MODELS = ["claude-opus-4-8", "claude-sonnet-5"];

// Per-column display: a name, a category (your model / baseline / hosted), and
// an accent color. Both hosted columns share the coral, on purpose.
const COL_NAME: Record<string, string> = {
    fine_tuned: "Fine-tuned",
    vanilla: "Vanilla base",
    openai: "OpenAI",
    anthropic: "Anthropic",
    ollama: "Ollama",
};
const COL_CATEGORY: Record<string, string> = {
    fine_tuned: "Your model",
    vanilla: "Baseline",
    openai: "Hosted",
    anthropic: "Hosted",
    ollama: "Local extra",
};
const COL_COLOR: Record<string, string> = {
    fine_tuned: "var(--primary)",
    vanilla: "var(--text-muted)",
    openai: "var(--hosted)",
    anthropic: "var(--hosted)",
    ollama: "var(--info)",
};

export default function Compare() {
    const [models, setModels] = useState<FineTunedModel[]>([]);
    const [modelId, setModelId] = useState<number | "">("");
    const [prompt, setPrompt] = useState("");
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [sending, setSending] = useState(false);
    const [error, setError] = useState<string | null>(null);
    // Columns that could not answer the most recent turn: label -> reason.
    const [colErrors, setColErrors] = useState<Record<string, string>>({});
    // Hosted-column model pickers (S13, #15): which model each hosted column
    // uses. Applied when the session is created; changing one starts a new
    // session, same rule as swapping the fine-tuned model.
    const [openaiModel, setOpenaiModel] = useState(OPENAI_MODELS[0]);
    const [anthropicModel, setAnthropicModel] = useState(ANTHROPIC_MODELS[0]);
    // Optional fifth column: an installed Ollama model, or "" for off.
    const [ollamaModel, setOllamaModel] = useState("");
    const [ollamaModels, setOllamaModels] = useState<string[]>([]);

    // The session id lives in a ref: it persists across renders and we read it
    // synchronously inside the send handler. null means "no session yet".
    const sessionRef = useRef<number | null>(null);
    // The column setup the current session was created with (fine-tuned model
    // + the three pickers), so we can detect any change.
    const sessionSetupRef = useRef<string | null>(null);
    // The columns container, so we can keep each thread scrolled to the bottom.
    const colsRef = useRef<HTMLDivElement>(null);

    // Load the model picker options.
    useEffect(() => {
        apiFetch<FineTunedModel[]>("/fine-tuned-models")
            .then(setModels)
            .catch((err) => setError(err instanceof Error ? err.message : "Failed to load models"));
    }, []);

    // S13: list the models installed on this machine's Ollama so the compare
    // can offer the optional column. Empty (or a failed call) just means the
    // picker offers nothing to enable — no error, the four columns work alone.
    useEffect(() => {
        apiFetch<{ models: string[] }>("/compare/ollama-models")
            .then((r) => setOllamaModels(r.models ?? []))
            .catch(() => setOllamaModels([]));
    }, []);

    // On every new message (or while a reply is pending), pin each column's
    // thread to the bottom so the latest turn is in view.
    useEffect(() => {
        colsRef.current?.querySelectorAll(".compare-thread").forEach((t) => {
            t.scrollTop = t.scrollHeight;
        });
    }, [messages, sending]);

    // Lazy session: create one only when we first need it (or when the column
    // setup changed since the last session). Returns the session id to use.
    async function ensureSession(): Promise<number> {
        const setup = `${modelId}|${openaiModel}|${anthropicModel}|${ollamaModel}`;
        if (sessionRef.current !== null && sessionSetupRef.current === setup) {
            return sessionRef.current;
        }
        const session = await apiFetch<ChatSession>("/chat-sessions", {
            method: "POST",
            body: {
                fine_tuned_model_id: modelId,
                compare_model_a: openaiModel,
                compare_model_b: anthropicModel,
                compare_ollama_model: ollamaModel === "" ? null : ollamaModel,
            },
        });
        sessionRef.current = session.id;
        sessionSetupRef.current = setup;
        setMessages([]); // a new session (first use or setup change) starts a fresh transcript
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
            // every column, and returns this turn's messages plus per-column failures.
            const turn = await apiFetch<ChatTurn>(
                `/chat-sessions/${sessionId}/messages`,
                { method: "POST", body: { content: prompt } }
            );
            setMessages((prev) => [...prev, ...turn.messages]);
            setColErrors(turn.errors ?? {});
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

    // The ollama column renders only while one is picked; the backend adds it
    // to the fan-out via the session's compare_ollama_model.
    const columns: string[] = ollamaModel === "" ? [...BASE_COLUMNS] : [...BASE_COLUMNS, "ollama"];

    return (
        <div className="compare">
            <div className="compare-head">
                <div>
                    <div className="page-eyebrow" style={{ color: "var(--primary)" }}>Agent tester</div>
                    <h1 className="page-title">Compare</h1>
                </div>
                <div className="compare-picks">
                    <select
                        className="select compare-model-select"
                        value={modelId}
                        aria-label="Fine-tuned model to test"
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
                    <select
                        className="select compare-model-select"
                        value={ollamaModel}
                        aria-label="Ollama model for the extra column"
                        onChange={(e) => setOllamaModel(e.target.value)}
                        title={ollamaModels.length === 0 ? "No models installed in Ollama" : "Optional fifth column"}
                    >
                        <option value="">Ollama column: off</option>
                        {ollamaModels.map((m) => (
                            <option key={m} value={m}>Ollama: {m}</option>
                        ))}
                    </select>
                </div>
            </div>

            {error && <p className="form-error" role="alert">{error}</p>}

            <div className={`compare-cols${columns.length === 5 ? " cols-five" : ""}`} ref={colsRef}>
                {columns.map((label) => (
                    <div className="compare-col" key={label}>
                        <div className="compare-col-head">
                            <span className="col-dot" style={{ background: COL_COLOR[label] }} />
                            <span className="col-name" style={{ color: COL_COLOR[label] }}>{COL_NAME[label]}</span>
                            {label === "openai" ? (
                                <select
                                    className="select col-picker"
                                    value={openaiModel}
                                    onChange={(e) => setOpenaiModel(e.target.value)}
                                    title="OpenAI model for this column"
                                >
                                    {OPENAI_MODELS.map((m) => (
                                        <option key={m} value={m}>{m}</option>
                                    ))}
                                </select>
                            ) : label === "anthropic" ? (
                                <select
                                    className="select col-picker"
                                    value={anthropicModel}
                                    onChange={(e) => setAnthropicModel(e.target.value)}
                                    title="Anthropic model for this column"
                                >
                                    {ANTHROPIC_MODELS.map((m) => (
                                        <option key={m} value={m}>{m}</option>
                                    ))}
                                </select>
                            ) : label === "ollama" ? (
                                <span className="col-cat">{ollamaModel}</span>
                            ) : (
                                <span className="col-cat">{COL_CATEGORY[label]}</span>
                            )}
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
                                    {/* S18: the shared VU meter replaces the
                                        per-column pulsing dots. */}
                                    <div className="thinking" style={{ color: COL_COLOR[label] }}>
                                        <VuMeter bars={4} />
                                    </div>
                                </div>
                            )}
                            {!sending && colErrors[label] && (
                                <div className="msg msg-model">
                                    <div className="bubble bubble-error">⚠ {colErrors[label]}</div>
                                </div>
                            )}
                        </div>
                    </div>
                ))}
            </div>

            <form className="compare-input" onSubmit={handleSend}>
                <input
                    className="input"
                    aria-label={`Message to send to all ${columns.length} compared models`}
                    placeholder={`Message all ${columns.length} models…`}
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
