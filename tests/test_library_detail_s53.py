"""S53 regressions: library 2 — public dataset detail + owner profile line.

Covers GET /api/library/datasets/{id}:
- strictly public: private rows 404 for everyone, INCLUDING their owner
  (the owner's own view is /api/datasets/{id}; existence is not leaked);
- a public row returns metadata + a bounded, oldest-first Q&A preview,
  the true pair_count, and a truncated flag;
- the owner profile line counts ONLY public datasets/models of the owner;
- no contact fields ride out: masked owner label, no email/user_id leak.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import get_current_user
from database import get_db
from models.dataset import Dataset
from models.fine_tuned_model import FineTunedModel
from models.qa_pair import QAPair
from models.training_run import TrainingRun
from models.user import User
from routers import library as library_module
from routers.library import PREVIEW_LIMIT


@pytest.fixture()
def two_users(in_memory_db):
    owner = User(email="s53-owner@mail.lmt-pytest.dev", hashed_password="x", display_name="Owner O")
    other = User(email="s53-other@mail.lmt-pytest.dev", hashed_password="x")
    in_memory_db.add_all([owner, other])
    in_memory_db.commit()
    in_memory_db.refresh(owner)
    in_memory_db.refresh(other)
    return owner, other


@pytest.fixture()
def app_for(in_memory_db, two_users):
    owner, other = two_users
    state = {"user": other}  # the library is the *viewer's* page

    app = FastAPI()
    app.include_router(library_module.router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    app.dependency_overrides[get_current_user] = lambda: state["user"]

    with TestClient(app) as test_client:
        yield test_client, {"owner": owner, "other": other, "as": lambda u: state.update(user=u)}


def _dataset(in_memory_db, user, name="shared", visibility="public", **kw):
    ds = Dataset(
        user_id=user.id, name=name, description="d", source="manual",
        visibility=visibility, **kw,
    )
    in_memory_db.add(ds)
    in_memory_db.commit()
    in_memory_db.refresh(ds)
    return ds


def _public_model(in_memory_db, user, ds, name="model", visibility="public"):
    run = TrainingRun(user_id=user.id, dataset_id=ds.id, base_model="Llama-3.2-1B", status="complete")
    in_memory_db.add(run)
    in_memory_db.commit()
    in_memory_db.refresh(run)
    m = FineTunedModel(
        user_id=user.id, training_run_id=run.id, name=name,
        base_model=run.base_model, status="ready", visibility=visibility,
    )
    in_memory_db.add(m)
    in_memory_db.commit()
    in_memory_db.refresh(m)
    return m


def _pairs(in_memory_db, ds, n, start=1):
    in_memory_db.add_all(
        [QAPair(dataset_id=ds.id, question=f"Q{i}?", answer=f"A{i}.") for i in range(start, start + n)]
    )
    in_memory_db.commit()


# --- gating ---------------------------------------------------------------------

def test_private_dataset_404s_for_everyone_including_owner(app_for, in_memory_db, two_users):
    test_client, ctx = app_for
    owner, other = two_users
    ds = _dataset(in_memory_db, owner, visibility="private")

    ctx["as"](other)
    assert test_client.get(f"/api/library/datasets/{ds.id}").status_code == 404
    # The owner does NOT get a back door through the community endpoint.
    ctx["as"](owner)
    assert test_client.get(f"/api/library/datasets/{ds.id}").status_code == 404
    assert test_client.get("/api/library/datasets/999999").status_code == 404


# --- the detail payload -----------------------------------------------------------

def test_public_detail_returns_metadata_and_preview(app_for, in_memory_db, two_users):
    test_client, ctx = app_for
    owner, other = two_users
    ds = _dataset(in_memory_db, owner, name="Finance 101", use_case_prompt="Terse answers.")
    _pairs(in_memory_db, ds, 3)

    ctx["as"](other)
    resp = test_client.get(f"/api/library/datasets/{ds.id}")
    assert resp.status_code == 200
    body = resp.json()

    assert body["dataset"] == {
        "id": ds.id, "name": "Finance 101", "description": "d", "source": "manual",
        "use_case_prompt": "Terse answers.", "created_at": body["dataset"]["created_at"],
    }
    # Oldest-first preview, ids only for keys — no dataset_id/user_id leakage.
    assert [p["question"] for p in body["pairs"]] == ["Q1?", "Q2?", "Q3?"]
    assert all(set(p.keys()) == {"id", "question", "answer"} for p in body["pairs"])
    assert body["pair_count"] == 3
    assert body["truncated"] is False
    assert "email" not in resp.text and "user_id" not in resp.text


# --- owner profile line -------------------------------------------------------------

def test_owner_profile_counts_only_public_rows(app_for, in_memory_db, two_users):
    test_client, ctx = app_for
    owner, other = two_users
    ds_a = _dataset(in_memory_db, owner, name="pub-a", visibility="public")
    _dataset(in_memory_db, owner, name="pub-b", visibility="public")
    _dataset(in_memory_db, owner, name="secret", visibility="private")
    _public_model(in_memory_db, owner, ds_a, visibility="public")
    _public_model(in_memory_db, owner, ds_a, name="private-model", visibility="private")
    _dataset(in_memory_db, other, name="other-pub", visibility="public")  # must not count

    ctx["as"](other)
    body = test_client.get(f"/api/library/datasets/{ds_a.id}").json()
    assert body["owner"] == {
        "name": "Owner O", "public_datasets": 2, "public_models": 1,
        "member_since": body["owner"]["member_since"],
    }


def test_owner_label_masks_email_when_no_display_name(app_for, in_memory_db, two_users):
    test_client, ctx = app_for
    owner, other = two_users
    owner.display_name = None
    in_memory_db.commit()
    ds = _dataset(in_memory_db, owner, name="anon-pub")

    ctx["as"](other)
    resp = test_client.get(f"/api/library/datasets/{ds.id}")
    assert resp.json()["owner"]["name"] == "s53-owner"  # local part only
    assert "lmt-pytest.dev" not in resp.text


# --- preview bound ---------------------------------------------------------------

def test_preview_is_capped_and_flagged(app_for, in_memory_db, two_users):
    test_client, ctx = app_for
    owner, other = two_users
    ds = _dataset(in_memory_db, owner, name="big-pub")
    _pairs(in_memory_db, ds, PREVIEW_LIMIT + 5)

    ctx["as"](other)
    body = test_client.get(f"/api/library/datasets/{ds.id}").json()
    assert len(body["pairs"]) == PREVIEW_LIMIT
    assert body["pair_count"] == PREVIEW_LIMIT + 5
    assert body["truncated"] is True
    assert [p["question"] for p in body["pairs"][:2]] == ["Q1?", "Q2?"]
