"""S25 (#28) regressions: the opt-in bridge.

Covers the issue-#28 guarantees:
- consent creates a scoped permission whose pairing token is returned once
  and stored only as a sha256;
- the hub (`/companion/ws`) accepts a hello ONLY with a token that matches
  an active permission — everything else gets an error frame + close;
- job dispatch is scope-checked (a `status` probe with no status scope is
  refused 403 even while paired);
- revoking drops the live session and the permission goes offline.

Transport is starlette's TestClient websocket — no real sockets, no Mac,
nothing left running.
"""

import json
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from core.security import get_current_user
from database import get_db
from models.bridge import BridgePermission
from models.user import User
from routers import bridge as bridge_module


@pytest.fixture()
def bridge_env(in_memory_db):
    """App with the bridge routers wired + a fake authenticated owner."""
    user = User(email="s25@mail.lmt-pytest.dev", hashed_password="x", display_name="S25")
    in_memory_db.add(user)
    in_memory_db.commit()
    in_memory_db.refresh(user)

    app = FastAPI()
    app.include_router(bridge_module.router)
    app.include_router(bridge_module.ws_router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as test_client:
        yield test_client, user


def _create(test_client, name="studio-mac", scopes=("status",)):
    resp = test_client.post("/api/bridge/permissions",
                            json={"name": name, "scopes": list(scopes)})
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- consent + storage ------------------------------------------------------

def test_create_returns_token_once_and_stores_only_hash(bridge_env, in_memory_db):
    test_client, _ = bridge_env
    created = _create(test_client)
    assert created["token"].startswith("br1-")
    assert created["status"] == "active"
    assert created["online"] is False

    row = in_memory_db.query(BridgePermission).filter_by(id=created["id"]).one()
    assert row.token_hash != created["token"]
    assert created["token"] not in row.token_hash
    assert len(row.token_hash) == 64  # sha256 hex, nothing else about it

    listed = test_client.get("/api/bridge/permissions").json()
    assert all("token" not in item for item in listed)


def test_unknown_scope_is_rejected(bridge_env):
    test_client, _ = bridge_env
    resp = test_client.post("/api/bridge/permissions",
                            json={"name": "x", "scopes": ["status", "rm_rf"]})
    assert resp.status_code == 422


# --- hub pairing ------------------------------------------------------------

def test_hello_with_bad_token_gets_error_and_close(bridge_env):
    test_client, _ = bridge_env
    _create(test_client)
    with test_client.websocket_connect("/companion/ws") as ws:
        ws.send_json({"type": "hello", "protocol": "llmtuner-companion/0",
                      "name": "ghost", "token": "br1-not-a-real-token",
                      "capabilities": {}})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "pairing token rejected" in msg["detail"]
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()


def test_hello_without_active_permission_never_welcomes(bridge_env):
    test_client, _ = bridge_env
    with test_client.websocket_connect("/companion/ws") as ws:
        ws.send_json({"type": "job", "id": "j0", "kind": "status"})  # not a hello
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "hello" in msg["detail"]


def test_paired_companion_shows_online_and_scope_gate_holds(bridge_env):
    test_client, _ = bridge_env
    created = _create(test_client, scopes=("train",))  # deliberately no status
    with test_client.websocket_connect("/companion/ws") as ws:
        ws.send_json({"type": "hello", "protocol": "llmtuner-companion/0",
                      "name": "studio-mac", "token": created["token"],
                      "capabilities": {"platform": "darwin", "mlx_lm": True}})
        welcome = ws.receive_json()
        assert welcome["type"] == "welcome"
        assert welcome["companion_id"] == f"perm-{created['id']}"
        assert welcome["granted_scopes"] == ["train"]

        listed = test_client.get("/api/bridge/permissions").json()
        assert listed[0]["online"] is True
        assert listed[0]["last_capabilities"]["platform"] == "darwin"

        # Paired, but the requested kind is not in scope -> 403, no frame sent.
        probe = test_client.post(f"/api/bridge/permissions/{created['id']}/probe")
        assert probe.status_code == 403
        assert "status" in probe.json()["detail"]


def test_probe_round_trips_when_companion_answers(bridge_env):
    test_client, _ = bridge_env
    created = _create(test_client, scopes=("status",))
    holder: dict = {}

    def probe():
        holder["resp"] = test_client.post(
            f"/api/bridge/permissions/{created['id']}/probe")

    with test_client.websocket_connect("/companion/ws") as ws:
        ws.send_json({"type": "hello", "protocol": "llmtuner-companion/0",
                      "name": "studio-mac", "token": created["token"],
                      "capabilities": {"platform": "darwin"}})
        assert ws.receive_json()["type"] == "welcome"

        thread = threading.Thread(target=probe)
        thread.start()
        job = ws.receive_json()
        assert job["type"] == "job" and job["kind"] == "status"
        ws.send_json({"type": "event", "id": job["id"], "stage": "probing",
                      "detail": ""})
        ws.send_json({"type": "result", "id": job["id"], "ok": True,
                      "data": {"backend_up": False, "capabilities": {"platform": "darwin"}}})
        thread.join(timeout=30)

    resp = holder["resp"]
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ok"] is True and body["status"] == "done"
    assert body["data"]["capabilities"]["platform"] == "darwin"


def test_revoke_drops_the_live_session(bridge_env):
    test_client, _ = bridge_env
    created = _create(test_client, scopes=("status",))
    with test_client.websocket_connect("/companion/ws") as ws:
        ws.send_json({"type": "hello", "protocol": "llmtuner-companion/0",
                      "name": "studio-mac", "token": created["token"],
                      "capabilities": {}})
        assert ws.receive_json()["type"] == "welcome"

        revoked = test_client.post(f"/api/bridge/permissions/{created['id']}/revoke")
        assert revoked.status_code == 200
        assert revoked.json()["status"] == "revoked"
        assert revoked.json()["dropped_live_session"] is True

        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()

    assert test_client.get("/api/bridge/permissions").json()[0]["online"] is False

    # A revoked token can never re-pair.
    stale = test_client.post(f"/api/bridge/permissions/{created['id']}/probe")
    assert stale.status_code == 409
