from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    fine_tuned_model_id: int
    title: str | None = None
    # The two hosted compare columns. Defaults are sensible picks the caller can
    # override; the two local Llama columns are derived from the fine-tuned model.
    compare_model_a: str = "gpt-4o-mini"
    compare_model_b: str = "claude-opus-4-8"
    # S13 (#15): the optional Ollama column. None = off; a model name from
    # GET /api/compare/ollama-models adds it as a fifth column.
    compare_ollama_model: str | None = None


class ChatSessionOut(BaseModel):
    id: int
    user_id: int
    fine_tuned_model_id: int
    title: str | None = None
    compare_model_a: str | None = None
    compare_model_b: str | None = None
    compare_ollama_model: str | None = None
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
    # S75: "error" = persisted per-column failure row (content is the reason);
    # None = a normal reply. The UI renders these as the error bubble so a
    # failed column stays visible after a reload instead of vanishing.
    status: str | None = None
    # S58: thumbs scoring. 1 = 👍, -1 = 👎, None = unrated. Only answered
    # assistant rows can carry one (see routers/chat.py set_message_rating).
    rating: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class RatingUpdate(BaseModel):
    # Body of the per-message rating endpoint. Literal-typed so anything but
    # up/down/clear is a 422 before we ever touch the DB.
    rating: Literal[1, -1] | None = None


class ColumnScore(BaseModel):
    # S58: one leaderboard row for a compare column inside one session.
    # "replies" counts answerable assistant rows (S75 error rows excluded),
    # so "unrated" below is always a truthful gap-to-cover number.
    label: str
    up: int
    down: int
    net: int
    replies: int
    rated: int


class SessionScores(BaseModel):
    session_id: int
    total_rated: int
    # Ranked best-first: net score, then raw thumbs-up, then label for a
    # stable order when models tie.
    scores: list[ColumnScore]


class ChatTurnOut(BaseModel):
    # One send's result: the persisted messages plus per-column failure
    # reasons. S75 changed the persistence story: failures now DO land as
    # status="error" rows (surviving reload), but the history rebuild skips
    # those rows, so a failed column never leaks its error text into the
    # model's own future context. The errors map is kept for live callers.
    messages: list[ChatMessageOut]
    errors: dict[str, str] = {}