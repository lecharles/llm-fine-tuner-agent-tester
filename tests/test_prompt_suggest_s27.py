"""S27 regressions: zero-LLM use-case-prompt suggestions.

Covers the S27 slice ("Generation UX: auto-fill use-case prompt from dataset
name/description"):
- the template prefers the description, falls back to the name, and returns
  "" when there is nothing to build from;
- the endpoint is owner-scoped (404 for someone else's dataset), never writes
  to the dataset, and is idempotent;
- long descriptions are bounded so the suggestion stays textarea-friendly.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import get_current_user
from database import get_db
from models.dataset import Dataset
from models.user import User
from routers import dataset as dataset_module
from generation.prompt_suggest import suggest_use_case_prompt


@pytest.fixture()
def s27_env(in_memory_db):
    """App with the dataset router wired + one fake authenticated owner."""
    user = User(email="s27@mail.lmt-pytest.dev", hashed_password="x", display_name="S27")
    in_memory_db.add(user)
    in_memory_db.commit()
    in_memory_db.refresh(user)

    app = FastAPI()
    app.include_router(dataset_module.router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as test_client:
        yield test_client, user


def _make_dataset(in_memory_db, user, name, description=None):
    ds = Dataset(user_id=user.id, name=name, description=description, source="manual")
    in_memory_db.add(ds)
    in_memory_db.commit()
    in_memory_db.refresh(ds)
    return ds


# --- pure template -----------------------------------------------------------

def test_prefers_description_over_name():
    out = suggest_use_case_prompt("Spanish Drills", "Spanish vocabulary for travelers")
    assert "Spanish vocabulary for travelers" in out
    assert out.startswith("You are an assistant for ")


def test_falls_back_to_name_when_description_missing():
    out = suggest_use_case_prompt("Spanish Drills", None)
    assert "Spanish Drills" in out
    assert out.startswith("You are an assistant that helps with ")


def test_empty_inputs_yield_empty_suggestion():
    assert suggest_use_case_prompt("", "   ") == ""
    assert suggest_use_case_prompt(None, None) == ""


def test_long_description_is_truncated():
    out = suggest_use_case_prompt("X", "word " * 100)
    assert "…" in out
    assert len(out) < 260


# --- endpoint ----------------------------------------------------------------

def test_suggestion_endpoint_fills_from_saved_fields(s27_env, in_memory_db):
    test_client, user = s27_env
    ds = _make_dataset(in_memory_db, user, "Pirate Talk", "Terse pirate-English tutor")
    resp = test_client.post(f"/api/datasets/{ds.id}/use-case-suggestion")
    assert resp.status_code == 200, resp.text
    body = resp.json()["suggestion"]
    assert "Terse pirate-English tutor" in body

    # Never writes: the stored prompt is untouched, and the call is idempotent.
    stored = in_memory_db.query(Dataset).filter(Dataset.id == ds.id).first()
    assert stored.use_case_prompt is None
    again = test_client.post(f"/api/datasets/{ds.id}/use-case-suggestion")
    assert again.json() == resp.json()


def test_suggestion_endpoint_is_owner_scoped(s27_env, in_memory_db):
    test_client, user = s27_env
    other = User(email="other@mail.lmt-pytest.dev", hashed_password="x")
    in_memory_db.add(other)
    in_memory_db.commit()
    in_memory_db.refresh(other)
    ds = _make_dataset(in_memory_db, other, "Not yours")

    resp = test_client.post(f"/api/datasets/{ds.id}/use-case-suggestion")
    assert resp.status_code == 404
