"""S67: SQLite FTS5 full-text search over datasets and QA pairs.

One implementation of the search index, shared by three callers so they can
never drift (the S62 lesson): the alembic migration (fresh + existing DBs),
the test fixtures (the shared ``in_memory_db`` only has ORM tables, so it
bolts the index on explicitly), and any future repair tooling.

Design — external-content FTS5:
- ``datasets_fts`` indexes (name, description); ``qa_pairs_fts`` indexes
  (question, answer). Both are ``content=``/``content_rowid=`` tables: the
  text lives ONLY in the real tables, the index stores postings. Cheap, and
  snippet()/BM25 read the live rows, so an edit is reflected the moment the
  triggers keep the postings in sync.
- triggers keep the index honest for every write path that exists today
  (manual pairs, S12 uploads, S56 merge retargeting dataset_id via UPDATE,
  bulk IN() deletes in dedupe, service-lane imports) — none of them needs to
  know the index exists.
- tokenize "porter unicode61": stemming means "training" finds "train" and
  accents/case stop mattering; unicode61 keeps 日本語 searchable.
"""

import re

from sqlalchemy import text

# Cap the MATCH expression: a user pasting an essay is not a search, and
# every extra term multiplies index work.
MAX_TERMS = 8

# Table DDL first (rebuild below needs the tables), then triggers (they must
# not double-index the rebuild backfill — hence: create, rebuild, trigger).
_CREATE_SQL = (
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS datasets_fts USING fts5(
        name,
        description,
        content='datasets',
        content_rowid='id',
        tokenize="porter unicode61"
    )
    """,
    """
    CREATE VIRTUAL TABLE IF NOT EXISTS qa_pairs_fts USING fts5(
        question,
        answer,
        content='qa_pairs',
        content_rowid='id',
        tokenize="porter unicode61"
    )
    """,
)

_REBUILD_SQL = (
    "INSERT INTO datasets_fts(datasets_fts) VALUES('rebuild')",
    "INSERT INTO qa_pairs_fts(qa_pairs_fts) VALUES('rebuild')",
)

# The 'delete' command needs the OLD indexed values verbatim — that is what
# old.* supplies in AFTER triggers on the content table.
_TRIGGER_SQL = (
    """
    CREATE TRIGGER IF NOT EXISTS datasets_fts_ai AFTER INSERT ON datasets BEGIN
      INSERT INTO datasets_fts(rowid, name, description)
      VALUES (new.id, new.name, new.description);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS datasets_fts_ad AFTER DELETE ON datasets BEGIN
      INSERT INTO datasets_fts(datasets_fts, rowid, name, description)
      VALUES('delete', old.id, old.name, old.description);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS datasets_fts_au AFTER UPDATE ON datasets BEGIN
      INSERT INTO datasets_fts(datasets_fts, rowid, name, description)
      VALUES('delete', old.id, old.name, old.description);
      INSERT INTO datasets_fts(rowid, name, description)
      VALUES (new.id, new.name, new.description);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS qa_pairs_fts_ai AFTER INSERT ON qa_pairs BEGIN
      INSERT INTO qa_pairs_fts(rowid, question, answer)
      VALUES (new.id, new.question, new.answer);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS qa_pairs_fts_ad AFTER DELETE ON qa_pairs BEGIN
      INSERT INTO qa_pairs_fts(qa_pairs_fts, rowid, question, answer)
      VALUES('delete', old.id, old.question, old.answer);
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS qa_pairs_fts_au AFTER UPDATE ON qa_pairs BEGIN
      INSERT INTO qa_pairs_fts(qa_pairs_fts, rowid, question, answer)
      VALUES('delete', old.id, old.question, old.answer);
      INSERT INTO qa_pairs_fts(rowid, question, answer)
      VALUES (new.id, new.question, new.answer);
    END
    """,
)

FTS_TABLES = ("datasets_fts", "qa_pairs_fts")


def _has(bind, name: str) -> bool:
    # Virtual tables appear in sqlite_master with type='table'.
    return (
        bind.execute(
            text("SELECT 1 FROM sqlite_master WHERE type='table' AND name = :n"),
            {"n": name},
        ).first()
        is not None
    )


def index_ready(bind) -> bool:
    """True when both FTS index tables exist (endpoint guard + tests)."""
    return all(_has(bind, name) for name in FTS_TABLES)


def ensure_fts(bind) -> None:
    """Create index + triggers if missing; backfill ONLY when just created.

    Safe to call repeatedly: existing databases keep their index (triggers
    have been maintaining it), and a database with rows but no index (the
    pre-migration production DB, or a test DB seeded before this call) gets
    every existing row indexed by the rebuild. The caller owns the commit —
    alembic wraps this in its transaction, tests call session.commit().
    """
    created = not index_ready(bind)
    for stmt in _CREATE_SQL:
        bind.execute(text(stmt))
    if created:
        for stmt in _REBUILD_SQL:
            bind.execute(text(stmt))
    for stmt in _TRIGGER_SQL:
        bind.execute(text(stmt))


def drop_fts(bind) -> None:
    """Downgrade path: triggers first (their bodies reference the tables),
    then the virtual tables (dropping an external-content FTS table never
    touches the content rows)."""
    for t in (
        "datasets_fts_ai",
        "datasets_fts_ad",
        "datasets_fts_au",
        "qa_pairs_fts_ai",
        "qa_pairs_fts_ad",
        "qa_pairs_fts_au",
    ):
        bind.execute(text(f"DROP TRIGGER IF EXISTS {t}"))
    for name in FTS_TABLES:
        bind.execute(text(f"DROP TABLE IF EXISTS {name}"))


# At least one word character, or the phrase tokenizes to nothing.
_HAS_WORD = re.compile(r"\w", re.UNICODE)


def build_match_query(raw: str) -> str | None:
    """Turn user input into a safe FTS5 MATCH expression, or None.

    Each whitespace-separated term becomes a quoted prefix phrase
    (``"term"`` -> ``"term"*``); internal double quotes are doubled, which
    FTS5 unescapes inside quoted strings. That makes operators, brackets,
    colons and stray quotes plain DATA — a user searching ``AND`` or
    ``NEAR(a b)`` or ``""; DROP`` can never inject FTS syntax (and SQLite
    would reject it anyway) nor get a 500 from a parse error. AND semantics
    across terms: multi-term queries narrow, which is what people expect
    from a box already labelled "search".
    """
    parts = []
    for term in raw.split()[:MAX_TERMS]:
        if not _HAS_WORD.search(term):
            continue  # punctuation-only term can only match nothing; skip it
        parts.append('"' + term.replace('"', '""') + '"*')
    return " ".join(parts) if parts else None
