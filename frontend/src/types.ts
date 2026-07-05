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