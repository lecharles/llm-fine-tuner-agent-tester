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