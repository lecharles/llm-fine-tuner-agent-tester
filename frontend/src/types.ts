// Frontend mirrors of the backend Pydantic schemas. One place to keep the
// API contract typed, so every screen gets autocomplete and compile-time checks.

export type Dataset = {
    id: number;
    user_id: number;
    name: string;
    description: string | null;
    source: string;
    use_case_prompt: string | null;
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
    created_at: string;
    completed_at: string | null;
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
    created_at: string;
};

export type ChatSession = {
    id: number;
    user_id: number;
    fine_tuned_model_id: number;
    title: string | null;
    compare_model_a: string | null;
    compare_model_b: string | null;
    created_at: string;
};

export type ChatMessage = {
    id: number;
    chat_session_id: number;
    role: string;
    model_label: string | null; // fine_tuned | vanilla | openai | anthropic (null for user)
    content: string;
    created_at: string;
};

export type QAPair = {
    id: number;
    dataset_id: number;
    question: string;
    answer: string;
    created_at: string;
};