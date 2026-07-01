from datetime import datetime

from pydantic import BaseModel


class QAPairCreate(BaseModel):
    question: str
    answer: str


class QAPairUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None


class QAPairOut(BaseModel):
    id: int
    dataset_id: int
    question: str
    answer: str
    created_at: datetime

    model_config = {"from_attributes": True}