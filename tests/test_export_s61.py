"""S61 regressions: Export 1 — dataset export (JSONL + ShareGPT shapes).

Covers GET /api/datasets/{id}/export?format=jsonl|sharegpt:
- jsonl shape is the importer's own dialect (S12 round-trip proof through
  datasets_import.parse_upload — export → re-import lands the same pairs);
- sharegpt shape is the ecosystem {"conversations":[human/gpt]} schema;
- attachment headers (Content-Disposition with slugified name + id,
  application/x-ndjson media type), oldest-first line order;
- unicode content survives byte-exact (ensure_ascii=False);
- S31 read semantics: owner yes, public yes for strangers, private 404-no-
  leak for strangers; export carries pair content only, never owner metadata;
- unknown format 400 naming the accepted ones; empty dataset 200 with zero
  lines (the button must not trap the user); service lanes may read/export.
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import get_current_user
from database import get_db
from datasets_import import parse_upload
from models.dataset import Dataset
from models.qa_pair import QAPair
from models.user import User
from routers import dataset as dataset_module


@pytest.fixture()
def two_users(in_memory_db):
    owner = User(email="s61-owner@mail.lmt-pytest.dev", hashed_password="x", display_name="Owner O")
    other = User(email="s61-other@mail.lmt-pytest.dev", hashed_password="x")
    in_memory_db.add_all([owner, other])
    in_memory_db.commit()
    in_memory_db.refresh(owner)
    in_memory_db.refresh(other)
    return owner, other


@pytest.fixture()
def app_for(in_memory_db, two_users):
    owner, other = two_users
    state = {"user": owner}

    app = FastAPI()
    app.include_router(dataset_module.router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    app.dependency_overrides[get_current_user] = lambda: state["user"]

    with TestClient(app) as test_client:
        yield test_client, {"as": lambda u: state.update(user=u)}


def _dataset(in_memory_db, user, name="s61 export set!", visibility="private"):
    ds = Dataset(user_id=user.id, name=name, description="d", source="manual", visibility=visibility)
    in_memory_db.add(ds)
    in_memory_db.commit()
    in_memory_db.refresh(ds)
    return ds


def _pair(in_memory_db, ds, question, answer):
    p = QAPair(dataset_id=ds.id, question=question, answer=answer)
    in_memory_db.add(p)
    in_memory_db.commit()
    in_memory_db.refresh(p)
    return p


def _lines(resp):
    return [ln for ln in resp.text.splitlines() if ln.strip()]


def test_jsonl_shape_round_trips_through_the_importer(app_for, in_memory_db, two_users):
    """Export default shape == the S12 import dialect: export re-imports as-is."""
    client, _ = app_for
    owner, _ = two_users
    ds = _dataset(in_memory_db, owner)
    _pair(in_memory_db, ds, "What is the capital of France?", "Paris.")
    _pair(in_memory_db, ds, "Q2?", "A2.")

    resp = client.get(f"/api/datasets/{ds.id}/export")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("application/x-ndjson")
    rows = [json.loads(ln) for ln in _lines(resp)]
    assert rows == [
        {"question": "What is the capital of France?", "answer": "Paris."},
        {"question": "Q2?", "answer": "A2."},
    ]

    # Round-trip proof: the exported bytes are a valid S12 upload.
    pairs = parse_upload("exported.jsonl", resp.content)
    assert pairs == rows


def test_sharegpt_shape_and_headers(app_for, in_memory_db, two_users):
    client, _ = app_for
    owner, _ = two_users
    ds = _dataset(in_memory_db, owner, name="Finance Q&A 2026!!")
    _pair(in_memory_db, ds, "What is EBITDA?", "Earnings before interest, taxes, depreciation and amortization.")

    resp = client.get(f"/api/datasets/{ds.id}/export", params={"format": "sharegpt"})
    assert resp.status_code == 200, resp.text
    rows = [json.loads(ln) for ln in _lines(resp)]
    assert rows == [
        {
            "conversations": [
                {"from": "human", "value": "What is EBITDA?"},
                {"from": "gpt", "value": "Earnings before interest, taxes, depreciation and amortization."},
            ]
        }
    ]
    # Filename: slugified name + dataset id; both shapes ship as .jsonl.
    cd = resp.headers["content-disposition"]
    assert f'filename="finance-q-a-2026-d{ds.id}.jsonl"' in cd


def test_unicode_survives_byte_exact(app_for, in_memory_db, two_users):
    client, _ = app_for
    owner, _ = two_users
    ds = _dataset(in_memory_db, owner)
    _pair(in_memory_db, ds, "Wie geht's, Welt? — 日本語 🌍", "Gut! こんにちは。")

    resp = client.get(f"/api/datasets/{ds.id}/export")
    assert resp.status_code == 200
    # Raw bytes carry the text (no \uXXXX soup), and json parses it back exactly.
    assert "日本語 🌍".encode("utf-8") in resp.content
    assert "\\u" not in resp.text
    row = json.loads(_lines(resp)[0])
    assert row["question"] == "Wie geht's, Welt? — 日本語 🌍"


def test_s31_read_semantics_no_owner_leak(app_for, in_memory_db, two_users):
    client, act = app_for
    owner, other = two_users
    private = _dataset(in_memory_db, owner, visibility="private")
    _pair(in_memory_db, private, "secret q", "secret a")
    public = _dataset(in_memory_db, owner, name="Public set", visibility="public")
    _pair(in_memory_db, public, "open q", "open a")

    # Stranger: private 404s with the standard no-leak wording.
    act["as"](other)
    resp = client.get(f"/api/datasets/{private.id}/export")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Dataset not found"

    # Stranger: public exports fine — pairs only, no owner/email/id metadata.
    resp = client.get(f"/api/datasets/{public.id}/export")
    assert resp.status_code == 200
    rows = [json.loads(ln) for ln in _lines(resp)]
    assert rows == [{"question": "open q", "answer": "open a"}]
    flat = resp.text.lower()
    assert "owner" not in flat and "mail.lmt-pytest.dev" not in flat

    # Unknown dataset id 404s for the owner too.
    act["as"](owner)
    assert client.get("/api/datasets/99999/export").status_code == 404


def test_unknown_format_400_names_accepted(app_for, in_memory_db, two_users):
    client, _ = app_for
    owner, _ = two_users
    ds = _dataset(in_memory_db, owner)
    resp = client.get(f"/api/datasets/{ds.id}/export", params={"format": "csv"})
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "csv" in detail and "jsonl" in detail and "sharegpt" in detail


def test_empty_dataset_is_a_valid_empty_export(app_for, in_memory_db, two_users):
    client, _ = app_for
    owner, _ = two_users
    ds = _dataset(in_memory_db, owner, name="😂🎉")  # nothing slug-safe in the name
    for fmt in ("jsonl", "sharegpt"):
        resp = client.get(f"/api/datasets/{ds.id}/export", params={"format": fmt})
        assert resp.status_code == 200, resp.text
        assert resp.text == ""
        assert f'filename="dataset-d{ds.id}.jsonl"' in resp.headers["content-disposition"]


def test_service_lane_can_read_export(app_for, in_memory_db, two_users):
    """S8: export is a read — service lanes keep read/create/queue rights."""
    client, act = app_for
    owner, _ = two_users
    lane = User(email="s61-lane@mail.lmt-pytest.dev", hashed_password="x")
    lane.lane_name = "s61-lane"  # in-memory attribute; is_service_lane uses getattr
    in_memory_db.add(lane)
    in_memory_db.commit()
    in_memory_db.refresh(lane)
    ds = _dataset(in_memory_db, lane, name="lane owned")
    _pair(in_memory_db, ds, "q from lane", "a from lane")

    act["as"](lane)
    resp = client.get(f"/api/datasets/{ds.id}/export")
    assert resp.status_code == 200
    assert json.loads(_lines(resp)[0]) == {"question": "q from lane", "answer": "a from lane"}
