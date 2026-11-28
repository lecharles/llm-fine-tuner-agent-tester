"""S71 regressions: first-run starter demo (10-pair seed) + guard rails.

Guarantees covered:
- signup auto-seeds exactly one demo dataset (source "seed") with exactly 10
  Q&A pairs, private, carrying the H4 iters guidance in its description;
- the seed is idempotent: signup path, endpoint path, and direct calls never
  produce a second copy for the same user;
- POST /api/datasets/seed-demo is the deliberate (re)seed path for legacy
  accounts / deleted demos;
- service lanes are NOT auto-seeded (ensure_lane_user never touches datasets);
- a failing seed NEVER breaks signup (best-effort contract);
- local-mode provisioning seeds the local user (the Mac first-run path);
- the seeded demo is private: strangers 404 (S31 no-leak), library empty.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import ensure_lane_user, ensure_local_user, get_current_user, ServiceLane
from database import get_db
from models.dataset import Dataset
from models.qa_pair import QAPair
from models.user import User
from routers import auth as auth_module
from routers import dataset as dataset_module


# --- helpers ---------------------------------------------------------------


def _signup(client, email, password="s71-***", display_name=None):
    return client.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "display_name": display_name},
    )


def _datasets_of(db, user):
    return db.query(Dataset).filter(Dataset.user_id == user.id).all()


def _pairs_of(db, dataset):
    return db.query(QAPair).filter(QAPair.dataset_id == dataset.id).all()


@pytest.fixture()
def full_client(in_memory_db):
    """Auth + datasets routers on the shared in-memory session, real JWTs."""
    from core.rate_limit import login_limiter, signup_limiter

    signup_limiter.reset()
    login_limiter.reset()
    app = FastAPI()
    app.include_router(auth_module.router)
    app.include_router(dataset_module.router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    with TestClient(app) as test_client:
        yield test_client


# --- 1. signup auto-seed -----------------------------------------------------


def test_signup_seeds_one_demo_dataset_with_ten_pairs(full_client, in_memory_db):
    r = _signup(full_client, "s71-new@mail.lmt-pytest.dev")
    assert r.status_code == 201, r.text
    user = in_memory_db.query(User).filter(User.email == "s71-new@mail.lmt-pytest.dev").one()

    mine = _datasets_of(in_memory_db, user)
    assert len(mine) == 1
    demo = mine[0]
    assert demo.source == "seed"
    assert demo.visibility == "private"
    assert demo.name == "Starter demo: refunds"
    # H4 guidance lives in the description — the first-run advice is where
    # the new user actually looks, not only in the docs.
    assert "10-20 iters" in demo.description
    assert "200-400 iters" in demo.description

    pairs = _pairs_of(in_memory_db, demo)
    assert len(pairs) == 10
    assert all(p.question.strip() and p.answer.strip() for p in pairs)
    # The DEMO.md storyline is present verbatim-ish: the 40-day no-receipt
    # question is what the tuned model is supposed to answer correctly.
    assert any("40 days" in p.question for p in pairs)


# --- 2. idempotency ----------------------------------------------------------


def test_second_seed_call_is_idempotent(full_client, in_memory_db):
    _signup(full_client, "s71-idem@mail.lmt-pytest.dev")
    user = in_memory_db.query(User).filter(User.email == "s71-idem@mail.lmt-pytest.dev").one()
    first = _datasets_of(in_memory_db, user)[0]

    token = full_client.post(
        "/api/auth/login",
        data={"username": "s71-idem@mail.lmt-pytest.dev", "password": "s71-***"},
    ).json()["access_token"]
    for _ in range(2):
        r = full_client.post("/api/datasets/seed-demo", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 201, r.text
        assert r.json()["id"] == first.id

    assert len(_datasets_of(in_memory_db, user)) == 1
    assert len(_pairs_of(in_memory_db, first)) == 10  # no pair duplication either


def test_seed_demo_endpoint_seeds_legacy_account(full_client, in_memory_db):
    # A user predating S71: created straight in the DB, never signed up.
    legacy = User(email="s71-legacy@mail.lmt-pytest.dev", hashed_password="x", display_name="Legacy")
    in_memory_db.add(legacy)
    in_memory_db.commit()
    assert _datasets_of(in_memory_db, legacy) == []

    # Override the identity the dataset router sees (legacy row has a hash
    # "x" that can never log in — we're testing the endpoint, not auth).
    app = full_client.app
    app.dependency_overrides[get_current_user] = lambda: legacy
    r = full_client.post("/api/datasets/seed-demo")
    assert r.status_code == 201, r.text
    assert r.json()["source"] == "seed"
    assert len(_datasets_of(in_memory_db, legacy)) == 1
    del app.dependency_overrides[get_current_user]


# --- 3. lanes are not onboarded ---------------------------------------------


def test_service_lane_user_is_not_seeded(in_memory_db):
    lane = ServiceLane(name="s71", token="s71-***")
    user = ensure_lane_user(in_memory_db, lane)
    assert _datasets_of(in_memory_db, user) == []


# --- 4. a broken seed must never break signup --------------------------------


def test_signup_survives_a_failing_seed(full_client, in_memory_db, monkeypatch):
    # Break what best_effort_seed CALLS, so the real try/except/rollback
    # contract is exercised (patching best_effort_seed itself would bypass
    # the guard and prove nothing).
    def boom(db, user):
        raise RuntimeError("seed exploded")

    monkeypatch.setattr("core.onboarding.seed_demo_dataset", boom)
    r = _signup(full_client, "s71-unlucky@mail.lmt-pytest.dev")
    assert r.status_code == 201, r.text
    user = in_memory_db.query(User).filter(User.email == "s71-unlucky@mail.lmt-pytest.dev").one()
    assert _datasets_of(in_memory_db, user) == []  # no half-written demo


# --- 5. local-mode first run (the Mac path) ----------------------------------


def test_ensure_local_user_seeds_once(in_memory_db):
    user = ensure_local_user(in_memory_db)
    mine = _datasets_of(in_memory_db, user)
    assert len(mine) == 1
    assert len(_pairs_of(in_memory_db, mine[0])) == 10
    again = ensure_local_user(in_memory_db)  # boot #2, same DB
    assert again.id == user.id
    assert len(_datasets_of(in_memory_db, user)) == 1  # not re-seeded on boot


# --- 6. the demo is private; no leak through sharing surfaces ----------------


def test_seeded_demo_is_private_and_does_not_leak(full_client, in_memory_db):
    _signup(full_client, "s71-sharer@mail.lmt-pytest.dev")
    stranger = User(email="s71-stranger@mail.lmt-pytest.dev", hashed_password="x")
    in_memory_db.add(stranger)
    in_memory_db.commit()

    token = full_client.post(
        "/api/auth/login",
        data={"username": "s71-sharer@mail.lmt-pytest.dev", "password": "s71-***"},
    ).json()["access_token"]
    demo_id = full_client.get(
        "/api/datasets", headers={"Authorization": f"Bearer {token}"}
    ).json()[0]["id"]

    app = full_client.app
    app.dependency_overrides[get_current_user] = lambda: stranger
    r = full_client.get(f"/api/datasets/{demo_id}")
    assert r.status_code == 404  # S31 wording: no existence leak
    from routers import library as library_module
    app.include_router(library_module.router)
    lib = full_client.get("/api/library")
    assert lib.status_code == 200
    ids = [d["id"] for d in lib.json()["datasets"]]
    assert demo_id not in ids
    del app.dependency_overrides[get_current_user]
