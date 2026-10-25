from datetime import datetime
from typing import Literal

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
    # S31: owner-only share toggle. Literal keeps the value space to exactly
    # the two states the authz checks understand.
    visibility: Literal["private", "public"] | None = None


class DatasetOut(BaseModel):
    id: int
    user_id: int
    name: str
    description: str | None = None
    source: str
    use_case_prompt: str | None = None
    visibility: str = "private"
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}