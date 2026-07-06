from datetime import datetime

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
    created_at: datetime

    model_config = {"from_attributes": True}