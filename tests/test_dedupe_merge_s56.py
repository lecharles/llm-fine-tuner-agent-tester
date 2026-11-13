"""S56 regressions: datasets 3 — dedupe + merge QA pairs across datasets.

Covers the two new endpoints on /api/datasets:
- POST /{id}/dedupe removes exact-duplicate Q&A pairs keeping the OLDEST
  (lowest id) of each group; keys are whitespace/case-normalized; dry_run
  reports the same numbers without writing; preview is bounded;
- POST /{id}/merge moves the source's unique pairs into the target, skips
  pairs already present in the target (they stay in the source), treats a
  self-merge as 400, and 404s datasets the caller does not own — public
  included (writes stay owner-only per S31);
- both endpoints refuse service lanes (403), same rule as dataset delete.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import get_current_user
from database import get_db
from models.dataset import Dataset
from models.qa_pair import QAPair
from models.user import User
from routers import dataset as dataset_module
from routers import qa_pair as qa_pair_module


@pytest.fixture()
def two_users(in_memory_db):
    owner = User(email="s56-owner@mail.lmt-pytest.dev", hashed_password="x", display_name="Owner O")
    other = User(email="s56-other@mail.lmt-pytest.dev", hashed_password="x")
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
    for mod in (dataset_module, qa_pair_module):
        app.include_router(mod.router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    app.dependency_overrides[get_current_user] = lambda: state["user"]

    with TestClient(app) as test_client:
        yield test_client, {"owner": owner, "other": other, "as": lambda u: state.update(user=u)}


def _dataset(in_memory_db, user, name="s56", visibility=None):
    ds = Dataset(user_id=user.id, name=name, description="d", source="manual")
    in_memory_db.add(ds)
    in_memory_db.commit()
    in_memory_db.refresh(ds)
    if visibility:
        ds.visibility = visibility
        in_memory_db.commit()
    return ds


def _pair(in_memory_db, ds, question, answer):
    p = QAPair(dataset_id=ds.id, question=question, answer=answer)
    in_memory_db.add(p)
    in_memory_db.commit()
    in_memory_db.refresh(p)
    return p


def _pair_ids(in_memory_db, ds_id):
    return sorted(
        p.id for p in in_memory_db.query(QAPair).filter(QAPair.dataset_id == ds_id).all()
    )


# ---------------------------------------------------------------- dedupe

def test_dedupe_removes_exact_duplicates_keeps_oldest(app_for, in_memory_db):
    client, ctx = app_for
    ds = _dataset(in_memory_db, ctx["owner"])
    p1 = _pair(in_memory_db, ds, "Capital of France?", "Paris.")
    p2 = _pair(in_memory_db, ds, "Capital of Spain?", "Madrid.")
    p3 = _pair(in_memory_db, ds, "Capital of France?", "Paris.")  # exact dupe of p1
    # Snapshot ids as plain ints: the endpoint's commit expires the ORM rows,
    # and the deleted one would raise ObjectDeletedError on lazy refresh.
    p1_id, p2_id, p3_id = p1.id, p2.id, p3.id

    res = client.post(f"/api/datasets/{ds.id}/dedupe", json={})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body == {
        "dry_run": False,
        "total_pairs": 3,
        "unique_pairs": 2,
        "removed": 1,
        "duplicate_groups": 1,
        "groups_preview": [
            {"question": "Capital of France?", "answer": "Paris.", "kept_id": p1_id, "removed_ids": [p3_id]}
        ],
        "preview_truncated": False,
    }
    surviving = _pair_ids(in_memory_db, ds.id)
    assert surviving == sorted([p1_id, p2_id])


def test_dedupe_normalizes_whitespace_and_case(app_for, in_memory_db):
    client, ctx = app_for
    ds = _dataset(in_memory_db, ctx["owner"])
    oldest = _pair(in_memory_db, ds, "What is 2+2?", "Four")
    _pair(in_memory_db, ds, "  what   is  2+2? ", "  four ")

    res = client.post(f"/api/datasets/{ds.id}/dedupe", json={})
    assert res.status_code == 200
    body = res.json()
    assert body["removed"] == 1 and body["duplicate_groups"] == 1
    assert body["groups_preview"][0]["kept_id"] == oldest.id
    assert len(_pair_ids(in_memory_db, ds.id)) == 1


def test_dedupe_same_question_different_answer_not_merged(app_for, in_memory_db):
    client, ctx = app_for
    ds = _dataset(in_memory_db, ctx["owner"])
    _pair(in_memory_db, ds, "Capital of France?", "Paris.")
    _pair(in_memory_db, ds, "Capital of France?", "The capital is Paris.")

    body = client.post(f"/api/datasets/{ds.id}/dedupe", json={}).json()
    assert body["removed"] == 0 and body["duplicate_groups"] == 0
    assert len(_pair_ids(in_memory_db, ds.id)) == 2


def test_dedupe_dry_run_previews_without_writing(app_for, in_memory_db):
    client, ctx = app_for
    ds = _dataset(in_memory_db, ctx["owner"])
    for _ in range(3):
        _pair(in_memory_db, ds, "Q?", "A.")

    body = client.post(f"/api/datasets/{ds.id}/dedupe", json={"dry_run": True}).json()
    assert body["dry_run"] is True
    assert body["removed"] == 2 and body["unique_pairs"] == 1
    assert len(_pair_ids(in_memory_db, ds.id)) == 3  # nothing deleted

    # ...and the real run afterwards removes exactly what was previewed.
    body = client.post(f"/api/datasets/{ds.id}/dedupe", json={}).json()
    assert body["removed"] == 2
    assert len(_pair_ids(in_memory_db, ds.id)) == 1


def test_dedupe_preview_is_bounded(app_for, in_memory_db):
    client, ctx = app_for
    from routers.dataset import PREVIEW_GROUPS

    ds = _dataset(in_memory_db, ctx["owner"])
    for i in range(PREVIEW_GROUPS + 5):
        _pair(in_memory_db, ds, f"Q{i}?", "A.")
        _pair(in_memory_db, ds, f"Q{i}?", "A.")  # one dupe per group

    body = client.post(f"/api/datasets/{ds.id}/dedupe", json={"dry_run": True}).json()
    assert body["duplicate_groups"] == PREVIEW_GROUPS + 5
    assert body["removed"] == PREVIEW_GROUPS + 5
    assert len(body["groups_preview"]) == PREVIEW_GROUPS
    assert body["preview_truncated"] is True


def test_dedupe_empty_dataset_is_clean(app_for, in_memory_db):
    client, ctx = app_for
    ds = _dataset(in_memory_db, ctx["owner"])
    body = client.post(f"/api/datasets/{ds.id}/dedupe", json={}).json()
    assert body["total_pairs"] == 0 and body["removed"] == 0


# ---------------------------------------------------------------- merge

def test_merge_moves_unique_skips_duplicates_keeps_source(app_for, in_memory_db):
    client, ctx = app_for
    owner = ctx["owner"]
    target = _dataset(in_memory_db, owner, name="target")
    source = _dataset(in_memory_db, owner, name="source")
    t1 = _pair(in_memory_db, target, "Shared?", "Same.")       # duplicate in target
    t2 = _pair(in_memory_db, target, "Only target?", "T.")
    s_dup = _pair(in_memory_db, source, "  SHARED? ", " same. ")   # dupe modulo normalization
    s1 = _pair(in_memory_db, source, "Only source?", "S.")
    t1_id, t2_id, s1_id, sd_id = t1.id, t2.id, s1.id, s_dup.id

    res = client.post(f"/api/datasets/{target.id}/merge", json={"source_dataset_id": source.id})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body == {
        "dry_run": False,
        "target_dataset_id": target.id,
        "source_dataset_id": source.id,
        "moved": 1,
        "skipped_duplicates": 1,
        "source_remaining": 1,
    }
    assert _pair_ids(in_memory_db, target.id) == sorted([t1_id, t2_id, s1_id])
    assert _pair_ids(in_memory_db, source.id) == [sd_id]  # the dupe was NOT deleted


def test_merge_source_internal_dupes_only_first_moves(app_for, in_memory_db):
    client, ctx = app_for
    owner = ctx["owner"]
    target = _dataset(in_memory_db, owner, name="target")
    source = _dataset(in_memory_db, owner, name="source")
    a = _pair(in_memory_db, source, "Same?", "Yes.")
    b = _pair(in_memory_db, source, "Same?", "Yes.")  # dupe within the source
    _pair(in_memory_db, source, "Other?", "No.")

    body = client.post(f"/api/datasets/{target.id}/merge", json={"source_dataset_id": source.id}).json()
    assert body["moved"] == 2 and body["skipped_duplicates"] == 1
    assert _pair_ids(in_memory_db, source.id) == [b.id]
    assert a.id in _pair_ids(in_memory_db, target.id)


def test_merge_dry_run_does_not_write(app_for, in_memory_db):
    client, ctx = app_for
    owner = ctx["owner"]
    target = _dataset(in_memory_db, owner, name="target")
    source = _dataset(in_memory_db, owner, name="source")
    _pair(in_memory_db, target, "Dup?", "A.")
    _pair(in_memory_db, source, "New?", "B.")
    _pair(in_memory_db, source, "Dup?", "A.")

    body = client.post(
        f"/api/datasets/{target.id}/merge",
        json={"source_dataset_id": source.id, "dry_run": True},
    ).json()
    assert body["dry_run"] is True and body["moved"] == 1 and body["skipped_duplicates"] == 1
    assert len(_pair_ids(in_memory_db, target.id)) == 1  # nothing moved yet
    assert len(_pair_ids(in_memory_db, source.id)) == 2

    # real run afterwards is idempotent-consistent with the preview
    body = client.post(
        f"/api/datasets/{target.id}/merge", json={"source_dataset_id": source.id}
    ).json()
    assert body["moved"] == 1 and body["skipped_duplicates"] == 1
    # merging again now finds the single leftover source pair a duplicate
    body = client.post(
        f"/api/datasets/{target.id}/merge", json={"source_dataset_id": source.id}
    ).json()
    assert body["moved"] == 0 and body["skipped_duplicates"] == 1


def test_merge_self_is_400(app_for, in_memory_db):
    client, ctx = app_for
    ds = _dataset(in_memory_db, ctx["owner"])
    res = client.post(f"/api/datasets/{ds.id}/merge", json={"source_dataset_id": ds.id})
    assert res.status_code == 400


# ---------------------------------------------------------------- authz

def test_merge_foreign_source_404_even_when_public(app_for, in_memory_db):
    client, ctx = app_for
    owner, other = ctx["owner"], ctx["other"]
    mine = _dataset(in_memory_db, owner, name="mine")
    theirs = _dataset(in_memory_db, other, name="theirs", visibility="public")
    _pair(in_memory_db, theirs, "Q?", "A.")

    res = client.post(f"/api/datasets/{mine.id}/merge", json={"source_dataset_id": theirs.id})
    # 404, not 403: existence of non-owned rows is not leaked, public included.
    assert res.status_code == 404

    res = client.post(f"/api/datasets/{theirs.id}/merge", json={"source_dataset_id": mine.id})
    assert res.status_code == 404

    res = client.post(f"/api/datasets/{theirs.id}/dedupe", json={})
    assert res.status_code == 404
    assert _pair_ids(in_memory_db, theirs.id)  # still untouched


def test_unknown_ids_404(app_for):
    client, _ = app_for
    assert client.post("/api/datasets/999/dedupe", json={}).status_code == 404
    assert client.post("/api/datasets/999/merge", json={"source_dataset_id": 1}).status_code == 404


def test_service_lane_blocked(app_for, in_memory_db):
    client, ctx = app_for
    owner = ctx["owner"]
    mine = _dataset(in_memory_db, owner, name="mine")
    other_ds = _dataset(in_memory_db, owner, name="other")
    _pair(in_memory_db, mine, "Dup?", "A.")
    _pair(in_memory_db, mine, "Dup?", "A.")
    _pair(in_memory_db, other_ds, "Q?", "A.")

    lane = User(email="s56-lane@mail.lmt-pytest.dev", hashed_password="x")
    lane.lane_name = "lane-s56"  # in-memory attribute; is_service_lane uses getattr
    ctx["as"](lane)

    res = client.post(f"/api/datasets/{mine.id}/dedupe", json={})
    assert res.status_code == 403
    res = client.post(f"/api/datasets/{mine.id}/merge", json={"source_dataset_id": other_ds.id})
    assert res.status_code == 403
    # nothing mutated
    assert len(_pair_ids(in_memory_db, mine.id)) == 2
    assert len(_pair_ids(in_memory_db, other_ds.id)) == 1
