from datetime import datetime

from pydantic import BaseModel, Field


class TrainingRunCreate(BaseModel):
    dataset_id: int
    base_model: str = "mlx-community/Llama-3.2-1B-Instruct-4bit"
    method: str = "qlora"
    # S33 (#35): guard rails mirror the S17 UI clamps, and the advanced panel's
    # LoRA rank/alpha get sane bounds (rank is what costs memory; alpha is a
    # scaling factor, classically 2x rank). Out-of-range requests 422.
    iters: int = Field(300, ge=1, le=5000)
    learning_rate: float | None = Field(None, gt=0, le=1)
    lora_rank: int = Field(8, ge=1, le=128)
    lora_alpha: int = Field(16, ge=1, le=256)


class LossPoint(BaseModel):
    # One point on the live loss curve (S11, issue #4), parsed from train.log.
    step: int
    loss: float


class ErrorExplanationOut(BaseModel):
    # S29 (issue #33): one human reading of a failed run's error text.
    title: str
    cause: str
    fix: str


class TrainingRunHistoryOut(BaseModel):
    # S35 (#36): run history 1 — one summary row per run for the history list:
    # dataset name (denormalized via a LEFT JOIN so runs whose dataset was
    # deleted still show), base model, iters, and the final train loss (last
    # point parsed from the run's train.log; None while no log/points exist).
    id: int
    dataset_id: int
    dataset_name: str
    base_model: str
    method: str
    iters: int
    status: str
    final_loss: float | None = None
    created_at: datetime
    completed_at: datetime | None = None


class TrainingRunOut(BaseModel):
    id: int
    user_id: int
    dataset_id: int
    base_model: str
    method: str
    iters: int
    learning_rate: float | None = None
    lora_rank: int = 8
    lora_alpha: int = 16
    status: str
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}