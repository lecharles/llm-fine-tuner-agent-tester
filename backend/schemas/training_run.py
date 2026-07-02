from datetime import datetime

from pydantic import BaseModel


class TrainingRunCreate(BaseModel):
    dataset_id: int
    base_model: str = "mlx-community/Llama-3.2-1B-Instruct-4bit"
    method: str = "qlora"
    iters: int = 300
    learning_rate: float | None = None


class TrainingRunOut(BaseModel):
    id: int
    user_id: int
    dataset_id: int
    base_model: str
    method: str
    iters: int
    learning_rate: float | None = None
    status: str
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}