from datetime import datetime

from pydantic import BaseModel


class DatasetCreate(BaseModel):
    name: str
    description: str | None = None
    source: str
    use_case_prompt: str | None = None


class DatasetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    use_case_prompt: str | None = None


class DatasetOut(BaseModel):
    id: int
    user_id: int
    name: str
    description: str | None = None
    source: str
    use_case_prompt: str | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}