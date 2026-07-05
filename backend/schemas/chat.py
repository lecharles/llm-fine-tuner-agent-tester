from datetime import datetime

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    fine_tuned_model_id: int
    title: str | None = None
    # The two hosted compare columns. Defaults are sensible picks the caller can
    # override; the two local Llama columns are derived from the fine-tuned model.
    compare_model_a: str = "gpt-4o-mini"
    compare_model_b: str = "claude-opus-4-8"


class ChatSessionOut(BaseModel):
    id: int
    user_id: int
    fine_tuned_model_id: int
    title: str | None = None
    compare_model_a: str | None = None
    compare_model_b: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageCreate(BaseModel):
    # The user's prompt. The endpoint fans this out to all four columns and
    # persists the user turn plus each model's reply.
    content: str = Field(min_length=1)


class ChatMessageOut(BaseModel):
    id: int
    chat_session_id: int
    role: str
    model_label: str | None = None
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}