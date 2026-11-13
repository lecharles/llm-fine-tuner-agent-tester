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


# S56: dedupe/merge payloads. dry_run lets the UI preview the exact numbers
# before anything is deleted or moved.
class DedupeRequest(BaseModel):
    dry_run: bool = False


class MergeRequest(BaseModel):
    source_dataset_id: int
    dry_run: bool = False


class DedupeGroup(BaseModel):
    question: str
    answer: str
    kept_id: int
    removed_ids: list[int]


class DedupeResult(BaseModel):
    dry_run: bool
    total_pairs: int
    unique_pairs: int
    removed: int
    duplicate_groups: int
    # Bounded preview (house rule: never return an unbounded list) — the
    # counts above are always complete, the preview is capped.
    groups_preview: list[DedupeGroup]
    preview_truncated: bool


class MergeResult(BaseModel):
    dry_run: bool
    target_dataset_id: int
    source_dataset_id: int
    moved: int
    skipped_duplicates: int
    source_remaining: int


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