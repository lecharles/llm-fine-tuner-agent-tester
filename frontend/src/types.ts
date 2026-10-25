// Frontend mirrors of the backend Pydantic schemas. One place to keep the
// API contract typed, so every screen gets autocomplete and compile-time checks.

export type Dataset = {
    id: number;
    user_id: number;
    name: string;
    description: string | null;
    source: string;
    use_case_prompt: string | null;
    visibility: string; // S31/S32: "private" (default) | "public"
    created_at: string; // JSON has no Date type; ISO string over the wire
    updated_at: string | null;
};

export type TrainingRun = {
    id: number;
    user_id: number;
    dataset_id: number;
    base_model: string;
    method: string;
    iters: number;
    learning_rate: number | null;
    status: string; // queued | running | completed | failed
    error_message?: string | null; // set when status is failed (#42)
    created_at: string;
    completed_at: string | null;
};

// S29 (issue #33): one human-readable reading of a failed run's error text,
// from GET /api/training-runs/{id}/explain.
export type ErrorExplanation = {
    title: string;
    cause: string;
    fix: string;
};

// One point on the live loss curve, parsed from train.log by
// GET /training-runs/{id}/losses (S11, issue #4).
export type LossPoint = {
    step: number;
    loss: number;
};

export type FineTunedModel = {
    id: number;
    user_id: number;
    training_run_id: number;
    name: string;
    base_model: string;
    gguf_path: string | null;
    format: string | null;
    size_mb: number | null;
    status: string;
    visibility: string; // S31/S32: "private" (default) | "public"
    created_at: string;
};

export type ChatSession = {
    id: number;
    user_id: number;
    fine_tuned_model_id: number;
    title: string | null;
    compare_model_a: string | null;
    compare_model_b: string | null;
    compare_ollama_model: string | null; // S13: optional fifth column, null = off
    created_at: string;
};

export type ChatMessage = {
    id: number;
    chat_session_id: number;
    role: string;
    model_label: string | null; // fine_tuned | vanilla | openai | anthropic | ollama (null for user)
    content: string;
    created_at: string;
};

export type ChatTurn = {
    messages: ChatMessage[];
    // Per-column failure reasons for this turn: label -> message.
    errors: Record<string, string>;
};

export type QAPair = {
    id: number;
    dataset_id: number;
    question: string;
    answer: string;
    created_at: string;
};

// S25 (issue #28): one explicit, scoped, revocable grant of the user's Mac
// hardware. `token` exists only on the create response (shown once); the
// server keeps just its hash. `online` reflects the live hub session.
export type BridgePermission = {
    id: number;
    name: string;
    scopes: string[];
    status: string; // active | revoked
    online: boolean;
    last_capabilities: Record<string, unknown> | null;
    last_seen_at: string | null;
    created_at: string | null;
    revoked_at: string | null;
};

export type BridgePermissionCreated = BridgePermission & { token: string };

export type BridgeProbeResult = {
    ok: boolean;
    status: string;
    data: Record<string, unknown>;
    detail: string;
};

// S32 (sharing 2): GET /api/library — read-only view of everything S31 made
// public. Owner is a display label, never an email or ID.
export type LibraryDataset = {
    id: number;
    name: string;
    description: string | null;
    source: string;
    owner: string;
    created_at: string;
};

export type LibraryModel = {
    id: number;
    name: string;
    base_model: string;
    status: string;
    size_mb: number | null;
    owner: string;
    created_at: string;
};

export type LibraryPayload = {
    datasets: LibraryDataset[];
    models: LibraryModel[];
};