"""S67: Search 1 — dataset + QA-pair full-text search on SQLite FTS5.

GET /api/search?q=...&limit=... runs ONE sanitized FTS5 MATCH against both
indexes (core/fts.py owns the index DDL; this router only reads it) and
merges the hits, ranked by BM25.

Read semantics are S31 to the letter: results span the caller's own rows
plus other users' PUBLIC rows, and nothing else — a private dataset or pair
never shows up in someone else's results, at any tier. Search is a read, so
service lanes (S8) may use it, scoped to what the lane user can see.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.fts import build_match_query, index_ready
from core.security import get_current_user
from database import get_db
from models.user import User
from schemas.search import DatasetHit, PairHit, SearchResults

router = APIRouter(prefix="/api/search", tags=["search"])

# Rows per section per call (house rule: bounded lists).
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
# Snippet window per column, in tokens.
SNIPPET_TOKENS = 12
# Raw-text clip so a 1 MB answer never rides whole.
PREVIEW_CHARS = 160


def _clip(value: str | None, n: int = PREVIEW_CHARS) -> str | None:
    if value is None:
        return None
    return value if len(value) <= n else value[:n].rstrip() + "…"


_DATASET_SQL = f"""
    SELECT d.id, d.name, d.description, d.source, d.visibility, d.user_id,
           snippet(datasets_fts, 0, '[', ']', '…', {SNIPPET_TOKENS}) AS name_snippet,
           snippet(datasets_fts, 1, '[', ']', '…', {SNIPPET_TOKENS}) AS description_snippet,
           -bm25(datasets_fts) AS score
    FROM datasets_fts
    JOIN datasets d ON d.id = datasets_fts.rowid
    WHERE datasets_fts MATCH :q
      AND (d.user_id = :uid OR d.visibility = 'public')
    ORDER BY score DESC, d.id ASC
    LIMIT :lim
"""

_PAIR_SQL = f"""
    SELECT p.id, p.dataset_id, d.name AS dataset_name, d.visibility, d.user_id,
           p.question, p.answer,
           snippet(qa_pairs_fts, 0, '[', ']', '…', {SNIPPET_TOKENS}) AS question_snippet,
           snippet(qa_pairs_fts, 1, '[', ']', '…', {SNIPPET_TOKENS}) AS answer_snippet,
           -bm25(qa_pairs_fts) AS score
    FROM qa_pairs_fts
    JOIN qa_pairs p ON p.id = qa_pairs_fts.rowid
    JOIN datasets d ON d.id = p.dataset_id
    WHERE qa_pairs_fts MATCH :q
      AND (d.user_id = :uid OR d.visibility = 'public')
    ORDER BY score DESC, p.id ASC
    LIMIT :lim
"""


@router.get("", response_model=SearchResults)
def search(
    q: str = Query(..., min_length=1, max_length=200, description="full-text query"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fts_query = build_match_query(q)
    if fts_query is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query has no searchable terms (letters or digits required)",
        )

    # Fresh DBs that skipped the migration, or a build without FTS5 compiled
    # in: fail honestly instead of a 500 from the JOIN.
    if not index_ready(db):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search index not built; run `alembic upgrade head`",
        )

    params = {"q": fts_query, "uid": current_user.id, "lim": limit}
    try:
        dataset_rows = db.execute(text(_DATASET_SQL), params).mappings().all()
        pair_rows = db.execute(text(_PAIR_SQL), params).mappings().all()
    except Exception:
        # MATCH is sanitized (core/fts.build_match_query), so a parse error
        # here means a corrupt index — surface it, never a bare 500 trace.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search index error; run `alembic upgrade head`",
        )

    datasets = [
        DatasetHit(
            id=r["id"],
            name=r["name"],
            description=_clip(r["description"]),
            source=r["source"],
            visibility=r["visibility"],
            is_mine=r["user_id"] == current_user.id,
            name_snippet=r["name_snippet"],
            description_snippet=r["description_snippet"],
            score=r["score"],
        )
        for r in dataset_rows
    ]
    pairs = [
        PairHit(
            id=r["id"],
            dataset_id=r["dataset_id"],
            dataset_name=r["dataset_name"],
            visibility=r["visibility"],
            is_mine=r["user_id"] == current_user.id,
            question=_clip(r["question"]) or "",
            question_snippet=r["question_snippet"],
            answer_preview=_clip(r["answer"]),
            answer_snippet=r["answer_snippet"],
            score=r["score"],
        )
        for r in pair_rows
    ]
    return SearchResults(query=q, fts_query=fts_query, limit=limit, datasets=datasets, pairs=pairs)
