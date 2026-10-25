from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class FineTunedModelOut(BaseModel):
    id: int
    user_id: int
    training_run_id: int
    name: str
    base_model: str
    gguf_path: str | None = None
    format: str | None = None
    size_mb: int | None = None
    status: str
    visibility: str = "private"
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelVisibilityUpdate(BaseModel):
    """S31: owner-only share toggle for a fine-tuned model."""

    visibility: Literal["private", "public"]