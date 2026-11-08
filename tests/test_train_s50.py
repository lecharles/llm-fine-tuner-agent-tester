"""S50 regressions: the train handoff.

Covers the row's guarantees end-to-end at the hub + router level:
- POST /api/bridge/permissions/{id}/train dispatches a `train` job frame to
  the paired companion and returns a job id (202);
- the router enforces consent (revoked → 409, no train scope → 403, no live
  session → 409) and the dataset boundaries (missing → 404, empty → 400,
  too large → 409);
- GET /api/bridge/jobs/{id} returns the streamed events + loss curve, and
  refuses other users' job ids with the same 404 (no leak);
- a companion that disconnects mid-job fails the pending jobs on the spot
  instead of leaving them dangling to the dispatch timeout.

No real sockets — the companion side is a fake websocket that captures the
job frame the hub pushes down.
"""

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import bridge
from core.security import get_current_user
from database import get_db
from models.bridge import BridgePermission
from models.dataset import Dataset
from models.qa_pair import QAPair
from models.user import User
from routers import bridge as bridge_module


class FakeWS:
    """A websocket stand-in that records the job frames the hub sends."""

    def __init__(self):
        self.sent = []
        self.closed = False

    async def send_text(self, payload: str) -> None:
        self.sent.append(json.loads(payload))

    async def close(self, code: int = 1000, reason: str = "") -> None:
        self.closed = True


@pytest.fixture()
def train_env(in_memory_db):
    """App with the bridge router + a fake authenticated owner + a live
    companion session (train scope) wired into the hub."""
    user = User(email="s50@mail.lmt-pytest.dev", hashed_password="x", display_name="S50")
    in_memory_db.add(user)
    in_memory_db.commit()
    in_memory_db.refresh(user)

    app = FastAPI()
    app.include_router(bridge_module.router)
    app.include_router(bridge_module.ws_router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    app.dependency_overrides[get_current_user] = lambda: user

    # Clear any leftover hub state from other tests.
    bridge.SESSIONS.clear()
    bridge.JOBS.clear()
    bridge._RESULTS.clear()
    bridge._BG_TASKS.clear()

    with TestClient(app) as test_client:
        yield test_client, user, in_memory_db


def _make_perm(test_client, scopes=("status", "train")):
    resp = test_client.post("/api/bridge/permissions",
                            json={"name": "studio-mac", "scopes": list(scopes)})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _register_session(perm_id: int, user_id: int, scopes=("status", "train")):
    """Wire a fake websocket into the hub as if the companion had just dialed
    in. Returns the fake so tests can inspect what the hub pushed."""
    ws = FakeWS()
    loop = asyncio.new_event_loop()
    try:
        session = loop.run_until_complete(bridge.register_session(
            ws, permission_id=perm_id, user_id=user_id,
            name="studio-mac", scopes=list(scopes),
        ))
    finally:
        loop.close()
    return ws, session


def _seed_dataset(db, user_id: int, *, name: str = "demo", pairs: int = 3):
    ds = Dataset(user_id=user_id, name=name, source="test")
    db.add(ds)
    db.commit()
    db.refresh(ds)
    for i in range(pairs):
        db.add(QAPair(dataset_id=ds.id, question=f"q{i}", answer=f"a{i}"))
    db.commit()
    return ds.id


# --- happy path -------------------------------------------------------------

def test_train_dispatch_returns_job_id(train_env):
    test_client, user, db = train_env
    perm = _make_perm(test_client)
    ws, _ = _register_session(perm["id"], user.id)
    dataset_id = _seed_dataset(db, user.id)

    resp = test_client.post(f"/api/bridge/permissions/{perm['id']}/train",
                            json={"dataset_id": dataset_id, "iters": 30})
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["kind"] == "train"
    assert body["status"] == "awaiting_result"
    assert body["companion"] == "studio-mac"
    assert body["summary"].endswith("30 iters")

    # The hub pushed a `train` job frame with the hosted dataset content.
    assert len(ws.sent) == 1
    frame = ws.sent[0]
    assert frame["type"] == "job" and frame["kind"] == "train"
    assert frame["payload"]["dataset_id"] == dataset_id
    assert frame["payload"]["iters"] == 30
    hosted = frame["payload"]["hosted_dataset"]
    assert hosted["name"] == "demo"
    assert len(hosted["pairs"]) == 3
    assert hosted["pairs"][0] == {"question": "q0", "answer": "a0"}


def test_train_hyperparameters_forwarded(train_env):
    test_client, user, db = train_env
    perm = _make_perm(test_client)
    ws, _ = _register_session(perm["id"], user.id)
    dataset_id = _seed_dataset(db, user.id)

    resp = test_client.post(f"/api/bridge/permissions/{perm['id']}/train",
                            json={"dataset_id": dataset_id, "iters": 50,
                                  "lora_rank": 16, "lora_alpha": 32,
                                  "learning_rate": 0.00002,
                                  "base_model": "mlx-community/Qwen2-0.5B"})
    assert resp.status_code == 202, resp.text
    payload = ws.sent[0]["payload"]
    assert payload["lora_rank"] == 16 and payload["lora_alpha"] == 32
    assert payload["learning_rate"] == 0.00002
    assert payload["base_model"] == "mlx-community/Qwen2-0.5B"


# --- consent enforcement ----------------------------------------------------

def test_train_no_train_scope_403(train_env):
    test_client, user, db = train_env
    perm = _make_perm(test_client, scopes=("status",))
    _register_session(perm["id"], user.id, scopes=("status",))
    dataset_id = _seed_dataset(db, user.id)

    resp = test_client.post(f"/api/bridge/permissions/{perm['id']}/train",
                            json={"dataset_id": dataset_id, "iters": 30})
    assert resp.status_code == 403


def test_train_revoked_perm_409(train_env):
    test_client, user, db = train_env
    perm = _make_perm(test_client)
    _register_session(perm["id"], user.id)
    dataset_id = _seed_dataset(db, user.id)

    test_client.post(f"/api/bridge/permissions/{perm['id']}/revoke")
    resp = test_client.post(f"/api/bridge/permissions/{perm['id']}/train",
                            json={"dataset_id": dataset_id, "iters": 30})
    assert resp.status_code == 409


def test_train_offline_companion_409(train_env):
    test_client, user, db = train_env
    perm = _make_perm(test_client)
    # No session registered — the companion has not dialed in yet.
    dataset_id = _seed_dataset(db, user.id)

    resp = test_client.post(f"/api/bridge/permissions/{perm['id']}/train",
                            json={"dataset_id": dataset_id, "iters": 30})
    assert resp.status_code == 409


# --- dataset boundaries -----------------------------------------------------

def test_train_dataset_not_found_404(train_env):
    test_client, user, _db = train_env
    perm = _make_perm(test_client)
    _register_session(perm["id"], user.id)

    resp = test_client.post(f"/api/bridge/permissions/{perm['id']}/train",
                            json={"dataset_id": 9999, "iters": 30})
    assert resp.status_code == 404


def test_train_empty_dataset_400(train_env):
    test_client, user, db = train_env
    perm = _make_perm(test_client)
    _register_session(perm["id"], user.id)
    dataset_id = _seed_dataset(db, user.id, pairs=0)

    resp = test_client.post(f"/api/bridge/permissions/{perm['id']}/train",
                            json={"dataset_id": dataset_id, "iters": 30})
    assert resp.status_code == 400


def test_train_oversized_dataset_409(train_env):
    test_client, user, db = train_env
    perm = _make_perm(test_client)
    _register_session(perm["id"], user.id)
    dataset_id = _seed_dataset(db, user.id, pairs=bridge_module.MAX_BRIDGE_TRAIN_PAIRS + 1)

    resp = test_client.post(f"/api/bridge/permissions/{perm['id']}/train",
                            json={"dataset_id": dataset_id, "iters": 30})
    assert resp.status_code == 409
    assert "too many" in resp.json()["detail"].lower() or "slim" in resp.json()["detail"].lower()


# --- job status + streaming -------------------------------------------------

def test_train_job_status_streams_events_and_losses(train_env):
    test_client, user, db = train_env
    perm = _make_perm(test_client)
    ws, session = _register_session(perm["id"], user.id)
    dataset_id = _seed_dataset(db, user.id)

    resp = test_client.post(f"/api/bridge/permissions/{perm['id']}/train",
                            json={"dataset_id": dataset_id, "iters": 30})
    job_id = resp.json()["job_id"]

    # Simulate the companion streaming progress + loss points.
    bridge.ingest_message(perm["id"], {
        "type": "event", "id": job_id,
        "stage": "running", "detail": "step 1",
    })
    bridge.ingest_message(perm["id"], {
        "type": "event", "id": job_id,
        "stage": "loss", "detail": "2 new points",
        "data": {"points": [{"step": 1, "loss": 2.5}, {"step": 2, "loss": 1.9}]},
    })
    # Final result.
    bridge.ingest_message(perm["id"], {
        "type": "result", "id": job_id, "ok": True,
        "data": {"run_id": 7, "status": "completed"},
    })

    # The background awaiter needs a tick to settle the record.
    import time
    deadline = time.time() + 2.0
    while time.time() < deadline:
        view = test_client.get(f"/api/bridge/jobs/{job_id}").json()
        if view["status"] == "done":
            break
        import time as _t; _t.sleep(0.05)

    assert view["status"] == "done"
    assert view["losses"] == [{"step": 1, "loss": 2.5}, {"step": 2, "loss": 1.9}]
    assert any(e["stage"] == "running" for e in view["events"])
    assert view["result"]["run_id"] == 7


def test_train_job_other_user_404(train_env):
    """Other users' job ids return the same 404 — no leak."""
    test_client, user, db = train_env
    perm = _make_perm(test_client)
    _register_session(perm["id"], user.id)
    dataset_id = _seed_dataset(db, user.id)

    resp = test_client.post(f"/api/bridge/permissions/{perm['id']}/train",
                            json={"dataset_id": dataset_id, "iters": 30})
    job_id = resp.json()["job_id"]

    # Swap the authenticated user to someone else.
    other = User(email="other@mail.lmt-pytest.dev", hashed_password="x", display_name="O")
    db.add(other)
    db.commit()
    db.refresh(other)
    test_client.app.dependency_overrides[get_current_user] = lambda: other

    resp2 = test_client.get(f"/api/bridge/jobs/{job_id}")
    assert resp2.status_code == 404
    # Unknown ids get the same 404 wording — no oracle.
    resp3 = test_client.get("/api/bridge/jobs/does-not-exist")
    assert resp3.status_code == 404
    assert resp2.json()["detail"] == resp3.json()["detail"]


# --- disconnect fail-fast ---------------------------------------------------

def test_train_disconnect_fails_pending_job(train_env):
    test_client, user, db = train_env
    perm = _make_perm(test_client)
    _register_session(perm["id"], user.id)
    dataset_id = _seed_dataset(db, user.id)

    resp = test_client.post(f"/api/bridge/permissions/{perm['id']}/train",
                            json={"dataset_id": dataset_id, "iters": 30})
    job_id = resp.json()["job_id"]

    # The companion drops off the socket.
    import time
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(bridge.disconnect_permission(perm["id"]))
    finally:
        loop.close()

    deadline = time.time() + 2.0
    while time.time() < deadline:
        view = test_client.get(f"/api/bridge/jobs/{job_id}").json()
        if view["status"] == "failed":
            break
        import time as _t; _t.sleep(0.05)

    assert view["status"] == "failed"
    assert "revoked" in view["detail"].lower() or "disconnected" in view["detail"].lower()


# --- jobs list --------------------------------------------------------------

def test_jobs_list_mine_only(train_env):
    test_client, user, db = train_env
    perm = _make_perm(test_client)
    _register_session(perm["id"], user.id)
    dataset_id = _seed_dataset(db, user.id)

    test_client.post(f"/api/bridge/permissions/{perm['id']}/train",
                     json={"dataset_id": dataset_id, "iters": 30})

    listing = test_client.get("/api/bridge/jobs").json()
    assert len(listing) >= 1
    assert all("losses" not in item for item in listing), "list view is slim"
    assert listing[0]["kind"] == "train"
    assert listing[0]["online"] is True
