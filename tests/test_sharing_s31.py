"""S31 regressions: public/private visibility + owner-or-public authz.

Covers the issue's guarantees:
- datasets and fine-tuned models default to private and are invisible (404,
  not 403) to other signed-in users;
- toggling visibility is owner-only and constrained to {private, public};
- a public dataset is readable (metadata + Q&A pairs) by non-owners, but its
  mutation routes stay owner-only;
- a public model is readable by non-owners; the visibility PATCH is not;
- /api/library lists only public rows, with owner display names.
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
from routers import dataset as dataset_module
from routers import fine_tuned_model as ftm_module
from routers import library as library_module
from routers import qa_pair as qa_pair_module


@pytest.fixture()
def two_users(in_memory_db):
    owner = User(email="s31-owner@mail.lmt-pytest.dev", hashed_password="x", display_name="Owner O")
    other = User(email="s31-other@mail.lmt-pytest.dev", hashed_password="x")
    in_memory_db.add_all([owner, other])
    in_memory_db.commit()
    in_memory_db.refresh(owner)
    in_memory_db.refresh(other)
    return owner, other


@pytest.fixture()
def app_for(in_memory_db, two_users):
    """Wires the four sharing routers with a switchable current user."""
    owner, other = two_users
    state = {"user": owner}

    app = FastAPI()
    for mod in (dataset_module, qa_pair_module, ftm_module, library_module):
        app.include_router(mod.router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    app.dependency_overrides[get_current_user] = lambda: state["user"]

    with TestClient(app) as test_client:
        yield test_client, {"owner": owner, "other": other, "as": lambda u: state.update(user=u)}


def _dataset(in_memory_db, user, name="shares", visibility=None):
    ds = Dataset(user_id=user.id, name=name, description="d", source="manual")
    in_memory_db.add(ds)
    in_memory_db.commit()
    in_memory_db.refresh(ds)
    if visibility:
        ds.visibility = visibility
        in_memory_db.commit()
    return ds


def _model(in_memory_db, user):
    ds = _dataset(in_memory_db, user, name="train-src")
    run = TrainingRun(user_id=user.id, dataset_id=ds.id, base_model="Llama-3.2-1B", status="complete")
    in_memory_db.add(run)
    in_memory_db.commit()
    in_memory_db.refresh(run)
    m = FineTunedModel(
        user_id=user.id, training_run_id=run.id, name="My Tune", base_model=run.base_model, status="ready"
    )
    in_memory_db.add(m)
    in_memory_db.commit()
    in_memory_db.refresh(m)
    return m


# --- defaults ------------------------------------------------------------------

def test_visibility_defaults_to_private(app_for, in_memory_db, two_users):
    owner, _ = two_users
    ds = _dataset(in_memory_db, owner)
    m = _model(in_memory_db, owner)
    assert ds.visibility == "private"
    assert m.visibility == "private"


# --- dataset authz ---------------------------------------------------------------

def test_private_dataset_invisible_to_other_users_404(app_for, in_memory_db, two_users):
    owner, other = two_users
    ds = _dataset(in_memory_db, owner)
    test_client, ctx = app_for

    ctx["as"](other)
    assert test_client.get(f"/api/datasets/{ds.id}").status_code == 404
    ctx["as"](owner)
    assert test_client.get(f"/api/datasets/{ds.id}").status_code == 200


def test_owner_can_share_and_unshare_dataset(app_for, in_memory_db, two_users):
    test_client, ctx = app_for
    owner, other = two_users
    ds = _dataset(in_memory_db, owner)

    resp = test_client.put(f"/api/datasets/{ds.id}", json={"visibility": "public"})
    assert resp.status_code == 200 and resp.json()["visibility"] == "public"

    # Non-owner can now READ...
    ctx["as"](other)
    assert test_client.get(f"/api/datasets/{ds.id}").status_code == 200
    # ...but not mutate: PUT stays owner-only.
    assert test_client.put(f"/api/datasets/{ds.id}", json={"visibility": "private"}).status_code == 404
    assert test_client.post(f"/api/datasets/{ds.id}/qa-pairs",
                            json={"question": "q", "answer": "a"}).status_code == 404

    # Bogus visibility is rejected outright.
    ctx["as"](owner)
    assert test_client.put(f"/api/datasets/{ds.id}", json={"visibility": "everyone"}).status_code == 422


def test_public_dataset_pairs_readable_by_others(app_for, in_memory_db, two_users):
    test_client, ctx = app_for
    owner, other = two_users
    ds = _dataset(in_memory_db, owner, visibility="public")
    in_memory_db.add(QAPair(dataset_id=ds.id, question="Q?", answer="A."))
    in_memory_db.commit()

    ctx["as"](other)
    resp = test_client.get(f"/api/datasets/{ds.id}/qa-pairs")
    assert resp.status_code == 200
    assert [p["question"] for p in resp.json()] == ["Q?"]

    # Private dataset of the same owner still 404s.
    private = _dataset(in_memory_db, owner, name="secret")
    assert test_client.get(f"/api/datasets/{private.id}/qa-pairs").status_code == 404


# --- model authz --------------------------------------------------------------

def test_public_model_readable_and_patch_is_owner_only(app_for, in_memory_db, two_users):
    test_client, ctx = app_for
    owner, other = two_users
    m = _model(in_memory_db, owner)

    ctx["as"](other)
    assert test_client.get(f"/api/fine-tuned-models/{m.id}").status_code == 404
    assert test_client.patch(f"/api/fine-tuned-models/{m.id}/visibility",
                             json={"visibility": "public"}).status_code == 404

    ctx["as"](owner)
    resp = test_client.patch(f"/api/fine-tuned-models/{m.id}/visibility",
                             json={"visibility": "public"})
    assert resp.status_code == 200 and resp.json()["visibility"] == "public"

    ctx["as"](other)
    assert test_client.get(f"/api/fine-tuned-models/{m.id}").status_code == 200
    # Toggling a public model back is still owner-only.
    assert test_client.patch(f"/api/fine-tuned-models/{m.id}/visibility",
                             json={"visibility": "private"}).status_code == 404


# --- library --------------------------------------------------------------------

def test_library_only_shows_public_rows_with_owner_names(app_for, in_memory_db, two_users):
    test_client, ctx = app_for
    owner, other = two_users
    _dataset(in_memory_db, owner, name="public ds", visibility="public")
    _dataset(in_memory_db, other, name="private ds")
    _model(in_memory_db, owner)  # stays private

    ctx["as"](other)
    lib = test_client.get("/api/library").json()
    assert [d["name"] for d in lib["datasets"]] == ["public ds"]
    assert lib["datasets"][0]["owner"] == "Owner O"
    assert lib["models"] == []
