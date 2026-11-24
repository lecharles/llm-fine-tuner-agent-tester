"""S67 response shapes for GET /api/search."""

from pydantic import BaseModel


class DatasetHit(BaseModel):
    id: int
    name: str
    description: str | None
    source: str
    visibility: str
    # True when the caller owns the row; public hits of other users are
    # False. Never an owner id/email — search ships content + a flag.
    is_mine: bool
    # '['-marked excerpts so a UI can show WHERE the query hit; raw text is
    # clipped (house rule: bounded payloads).
    name_snippet: str
    description_snippet: str
    # BM25 relevance, sign-flipped so higher is better. Ranking-only field.
    score: float


class PairHit(BaseModel):
    id: int
    dataset_id: int
    dataset_name: str
    visibility: str
    is_mine: bool
    question: str
    question_snippet: str
    # The answer ships clipped raw text plus a marked snippet centered on
    # the match — never the whole stored blob.
    answer_preview: str
    answer_snippet: str
    score: float


class SearchResults(BaseModel):
    query: str
    # The sanitized FTS5 expression actually run (transparency + debuggability).
    fts_query: str
    limit: int
    datasets: list[DatasetHit]
    pairs: list[PairHit]
