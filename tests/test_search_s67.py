"""S67 regressions: Search 1 — dataset + QA-pair full-text search on FTS5.

Covers GET /api/search?q=...&limit=...:
- the index exists and stays in sync with plain ORM writes through the
  triggers (insert/update/delete, both tables);
- pre-existing rows get backfilled by ensure_fts (the migration path —
  rebuild command, not per-row replay);
- query semantics: BM25 ranking, porter stemming, prefix, multi-term AND;
- injection safety: operators/quotes/punctuation become plain data, never a
  500 and never FTS syntax;
- S31 visibility: own rows + others' public rows, private rows invisible to
  strangers (no leak of existence, ids or names);
- bounded payloads: limit param, preview clipping;
- honest 400/422/503 states and service-lane read rights (S8).
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.fts import build_match_query, ensure_fts
from core.security import get_current_user
from database import get_db
from models.dataset import Dataset
from models.qa_pair import QAPair
from models.user import User
from routers import search as search_module


@pytest.fixture()
def db_with_fts(in_memory_db):
    """Shared fixture DB + the S67 index bolted on (mirrors what the
    migration does to a production DB that already has rows)."""
    ensure_fts(in_memory_db)
    in_memory_db.commit()
    return in_memory_db


@pytest.fixture()
def two_users(db_with_fts):
    owner = User(email="s67-owner@mail.lmt-pytest.dev", hashed_password="x", display_name="Owner O")
    other = User(email="s67-other@mail.lmt-pytest.dev", hashed_password="x")
    db_with_fts.add_all([owner, other])
    db_with_fts.commit()
    db_with_fts.refresh(owner)
    db_with_fts.refresh(other)
    return owner, other


@pytest.fixture()
def app_for(db_with_fts, two_users):
    owner, _ = two_users
    state = {"user": owner}

    app = FastAPI()
    app.include_router(search_module.router)
    app.dependency_overrides[get_db] = lambda: db_with_fts
    app.dependency_overrides[get_current_user] = lambda: state["user"]

    with TestClient(app) as test_client:
        yield test_client, {"as": lambda u: state.update(user=u)}


def _dataset(db, user, name, description="plain", visibility="private"):
    ds = Dataset(user_id=user.id, name=name, description=description,
                 source="manual", visibility=visibility)
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


def _pair(db, ds, question, answer):
    p = QAPair(dataset_id=ds.id, question=question, answer=answer)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def test_search_finds_dataset_and_pair_sections(app_for, db_with_fts, two_users):
    client, _ = app_for
    owner, _ = two_users
    ds = _dataset(db_with_fts, owner, name="Finance Q&A", description="EBITDA and margin questions")
    pair = _pair(db_with_fts, ds, "What is EBITDA?", "Earnings before interest and taxes.")

    resp = client.get("/api/search", params={"q": "ebitda"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["query"] == "ebitda"
    assert [d["id"] for d in body["datasets"]] == [ds.id]
    assert [p["id"] for p in body["pairs"]] == [pair.id]
    hit = body["pairs"][0]
    assert hit["dataset_name"] == "Finance Q&A"
    assert hit["is_mine"] is True
    # snippets mark the match with the agreed [brackets] — per column:
    # "ebitda" hits question + the dataset description, not the answer text.
    assert "[EBITDA]" in hit["question_snippet"]
    assert hit["answer_snippet"] == "Earnings before interest and taxes."
    assert body["datasets"][0]["description_snippet"].count("[") >= 1

    # a term living ONLY in the answer gets marked there instead
    hit2 = client.get("/api/search", params={"q": "taxes"}).json()["pairs"][0]
    assert "[taxes]" in hit2["answer_snippet"]


def test_triggers_keep_index_in_sync_with_orm_writes(app_for, db_with_fts, two_users):
    client, _ = app_for
    owner, _ = two_users
    ds = _dataset(db_with_fts, owner, name="Alpha set")
    p = _pair(db_with_fts, ds, "How do I compute the wobble?", "See the sizing notes.")

    assert client.get("/api/search", params={"q": "wobble"}).json()["pairs"] != []

    # UPDATE (this is the exact shape of S56 merge retargeting and of edits)
    # "wobble" lives ONLY in the question, so the delete-reinsert pair of the
    # au trigger is provably what moved it.
    p.question = "How do I compute the giggle?"
    db_with_fts.commit()
    assert client.get("/api/search", params={"q": "wobble"}).json()["pairs"] == []
    assert [x["id"] for x in client.get("/api/search", params={"q": "giggle"}).json()["pairs"]] == [p.id]

    # dataset rename rides the datasets trigger
    ds.name = "Beta set"
    db_with_fts.commit()
    assert client.get("/api/search", params={"q": "alpha"}).json()["datasets"] == []
    assert client.get("/api/search", params={"q": "beta"}).json()["datasets"] != []

    # DELETE
    db_with_fts.delete(p)
    db_with_fts.commit()
    assert client.get("/api/search", params={"q": "giggle"}).json()["pairs"] == []


def test_backfill_indexes_pre_existing_rows():
    """The migration scenario: rows exist, THEN the index is built."""
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from database import Base
    import models  # noqa: F401

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        u = User(email="s67-backfill@mail.lmt-pytest.dev", hashed_password="x")
        db.add(u)
        db.commit()
        ds = Dataset(user_id=u.id, name="Old finance notes", description="pre-index content",
                     source="manual", visibility="private")
        db.add(ds)
        db.commit()
        db.add(QAPair(dataset_id=ds.id, question="What was the old question?",
                      answer="The old answer mentioned amortization."))
        db.commit()

        ensure_fts(db)  # create + rebuild backfill
        db.commit()
        rows = db.execute(
            __import__("sqlalchemy").text("SELECT rowid FROM qa_pairs_fts WHERE qa_pairs_fts MATCH '\"amort\"*'")
        ).fetchall()
        assert len(rows) == 1
        drows = db.execute(
            __import__("sqlalchemy").text("SELECT rowid FROM datasets_fts WHERE datasets_fts MATCH '\"notes\"'")
        ).fetchall()
        assert [r[0] for r in drows] == [ds.id]

        # ensure_fts is idempotent: a second call must not double-index
        ensure_fts(db)
        db.commit()
        assert len(db.execute(
            __import__("sqlalchemy").text("SELECT rowid FROM qa_pairs_fts WHERE qa_pairs_fts MATCH '\"amort\"*'")
        ).fetchall()) == 1
    finally:
        db.close()
        engine.dispose()


def test_ranking_stemming_prefix_and_and(app_for, db_with_fts, two_users):
    client, _ = app_for
    owner, _ = two_users
    ds = _dataset(db_with_fts, owner, name="General")
    near = _pair(db_with_fts, ds, "training training training the model", "train train train")
    far = _pair(db_with_fts, ds, "a word about train", "one train here")
    both = _pair(db_with_fts, ds, "Paris is the capital of France", "Paris — the capital.")

    resp = client.get("/api/search", params={"q": "train"}).json()
    ids = [p["id"] for p in resp["pairs"]]
    assert set(ids) == {near.id, far.id}  # porter: "training" is found by "train"
    # BM25: the term-dense row must outrank the sparse one
    assert ids[0] == near.id
    assert resp["pairs"][0]["score"] > resp["pairs"][1]["score"]

    # prefix across the stem boundary of the RAW word
    assert [p["id"] for p in client.get("/api/search", params={"q": "finan"}).json()["pairs"]] == []
    _pair(db_with_fts, ds, "What is finance?", "Finance means money.")
    assert client.get("/api/search", params={"q": "financ"}).json()["pairs"] != []

    # multi-term is AND
    resp = client.get("/api/search", params={"q": "paris capital"}).json()
    assert [p["id"] for p in resp["pairs"]] == [both.id]


def test_injection_attempts_are_data_never_syntax_or_500(app_for, db_with_fts, two_users):
    client, _ = app_for
    owner, _ = two_users
    ds = _dataset(db_with_fts, owner, name="Syntax set", description="about brackets")
    _pair(db_with_fts, ds, 'What is a "quoted" term?', "The NEAR operator and AND are syntax.")

    for payload in ('AND', 'NEAR(training run)', 'brackets AND (description OR name)',
                    '"; DROP TABLE qa_pairs; --', '***', '"', 'colons: between words'):
        resp = client.get("/api/search", params={"q": payload})
        # punctuation-only queries degrade to the honest 400; anything with
        # word characters is data and searches clean. Never a 500.
        assert resp.status_code in (200, 400), f"{payload!r} -> {resp.status_code} {resp.text}"

    # the table is still there, the row is still searchable
    assert client.get("/api/search", params={"q": "syntax"}).json()["datasets"] != []
    assert db_with_fts.query(QAPair).count() == 1


def test_s31_visibility_private_invisible_to_stranger(app_for, db_with_fts, two_users):
    client, act = app_for
    owner, other = two_users
    priv = _dataset(db_with_fts, owner, name="Private ledger")
    _pair(db_with_fts, priv, "What is the secret margin?", "Only the owner may know.")
    pub = _dataset(db_with_fts, owner, name="Public cookbook", visibility="public")
    _pair(db_with_fts, pub, "How do I plate the pasta?", "Pasta plating guide.")

    act["as"](other)
    resp = client.get("/api/search", params={"q": "margin secret"})
    assert resp.status_code == 200
    assert resp.json()["datasets"] == [] and resp.json()["pairs"] == []  # not even the name leaks

    resp = client.get("/api/search", params={"q": "pasta"})
    body = resp.json()
    # "pasta" lives in the pair only (dataset name/description don't carry it)
    assert body["datasets"] == []
    assert len(body["pairs"]) == 1
    assert body["pairs"][0]["dataset_id"] == pub.id
    assert body["pairs"][0]["is_mine"] is False

    # the public dataset itself is found by a term in ITS text
    assert [d["id"] for d in client.get("/api/search", params={"q": "cookbook"}).json()["datasets"]] == [pub.id]

    # the owner still sees the private rows
    act["as"](owner)
    assert client.get("/api/search", params={"q": "secret"}).json()["pairs"][0]["id"] is not None


def test_visibility_flip_is_searchable_both_ways(app_for, db_with_fts, two_users):
    client, act = app_for
    owner, other = two_users
    ds = _dataset(db_with_fts, owner, name="Flip flop notes")
    _pair(db_with_fts, ds, "which way does the flag flip?", "Both.")

    act["as"](other)
    assert client.get("/api/search", params={"q": "flip"}).json()["datasets"] == []

    ds.visibility = "public"
    db_with_fts.commit()  # UPDATE on datasets rides datasets_fts_au
    act["as"](other)
    assert [d["id"] for d in client.get("/api/search", params={"q": "flip"}).json()["datasets"]] == [ds.id]


def test_limit_bounds_each_section_and_clips_previews(app_for, db_with_fts, two_users):
    client, _ = app_for
    owner, _ = two_users
    ds = _dataset(db_with_fts, owner, name="Many rows")
    long_answer = "amortization " * 200
    for _ in range(5):
        _pair(db_with_fts, ds, "What is amortization?", long_answer)

    resp = client.get("/api/search", params={"q": "amortization", "limit": 2}).json()
    assert len(resp["pairs"]) == 2
    hit = resp["pairs"][0]
    assert len(hit["answer_preview"]) <= 161  # clip + ellipsis
    assert "…" in hit["answer_preview"]
    assert len(hit["answer_snippet"]) < len(long_answer)

    # limit validation is 422 before any work
    assert client.get("/api/search", params={"q": "x", "limit": 0}).status_code == 422
    assert client.get("/api/search", params={"q": "x", "limit": 1000}).status_code == 422


def test_honest_error_states(app_for):
    assert app_for[0].get("/api/search", params={"q": "!"}).status_code == 400
    assert app_for[0].get("/api/search", params={"q": "!!! ??? ***"}).status_code == 400
    assert app_for[0].get("/api/search", params={"q": "  "}).status_code == 400
    assert app_for[0].get("/api/search", params={"q": ""}).status_code == 422  # min_length
    assert app_for[0].get("/api/search", params={"q": "x" * 201}).status_code == 422


def test_503_when_index_missing(two_users):
    """The no-migration state fails honestly — not a 500 from the JOIN."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from database import Base
    import models  # noqa: F401

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    bare_db = sessionmaker(bind=engine)()
    try:
        app = FastAPI()
        app.include_router(search_module.router)
        app.dependency_overrides[get_db] = lambda: bare_db
        app.dependency_overrides[get_current_user] = lambda: two_users[0]
        with TestClient(app) as client:
            resp = client.get("/api/search", params={"q": "anything"})
            assert resp.status_code == 503
            assert "alembic" in resp.json()["detail"]
    finally:
        bare_db.close()
        engine.dispose()


def test_service_lane_may_search_reads_only(app_for, db_with_fts, two_users):
    """S8: search is a read; the lane sees its own rows, not the owner's."""
    client, act = app_for
    owner, _ = two_users
    lane = User(email="s67-lane@mail.lmt-pytest.dev", hashed_password="x")
    lane.lane_name = "s67-lane"
    db_with_fts.add(lane)
    db_with_fts.commit()
    db_with_fts.refresh(lane)
    ds = _dataset(db_with_fts, lane, name="Lane workbench")
    _pair(db_with_fts, ds, "What does the lane import?", "Bulk QA rows.")
    _dataset(db_with_fts, owner, name="Owner-only vault")

    act["as"](lane)
    body = client.get("/api/search", params={"q": "lane"}).json()
    assert [d["id"] for d in body["datasets"]] == [ds.id]
    assert client.get("/api/search", params={"q": "vault"}).json()["datasets"] == []


def test_match_query_builder_units():
    assert build_match_query("paris capital") == '"paris"* "capital"*'
    # internal quotes double per FTS5 string-literal rules
    assert build_match_query('say "hi"') == '"say"* """hi"""*'
    assert build_match_query("!!! ???") is None
    assert build_match_query("one two three four five six seven eight nine ten") == (
        " ".join(f'"{w}"*' for w in "one two three four five six seven eight".split())
    )  # capped at MAX_TERMS=8
    # apostrophes are fine inside quoted phrases
    assert build_match_query("don't") == '"don\'t"*'
