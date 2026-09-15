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


class ChatTurnOut(BaseModel):
    # One send's result: the persisted messages plus per-column failure
    # reasons. Errors are deliberately NOT persisted rows: a failed column
    # must not leak its error text into the model's own future history.
    messages: list[ChatMessageOut]
    errors: dict[str, str] = {}