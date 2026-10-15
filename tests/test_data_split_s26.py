"""S26 (#29) regressions: the local/hosted data split.

Guarantees under test — all *hosted-side*:
- a paired companion's `artifacts` frame upserts metadata-only pointer rows
  (keyed by permission + device_run_id + kind), never any bytes;
- malformed frames (bad kind, bad sha256, empty list) get an ok:false ack and
  store nothing;
- GET /api/bridge/artifacts shows the owner their pointers (+ device name and
  online flag) and an unauthenticated call is refused;
- DELETE forgets exactly one pointer;
- reporting artifacts never touches the fine_tuned_models table — hosted
  training rows can't exist here anyway (H3's 425 preflight), which is the
  whole point of the split.

Transport is starlette's TestClient websocket — no sockets, no Mac, nothing
left running.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.security import get_current_user
from database import get_db
from models.fine_tuned_model import FineTunedModel
from models.user import User
from routers import bridge as bridge_module

ARTIFACT_ITEMS = [
    {"device_run_id": 7, "kind": "adapter", "name": "run7-adapters",
     "base_model": "mlx-community/Llama-3.2-1B", "size_bytes": 41_943_040,
     "sha256": "a" * 64,
     "device_path": "/Users/carlos/_training_runs/7/adapters"},
    {"device_run_id": 7, "kind": "fused", "name": "run7-fused",
     "base_model": "mlx-community/Llama-3.2-1B", "size_bytes": 1_234_567_890,
     "device_path": "/Users/carlos/_training_runs/7/fused_model"},
]


@pytest.fixture()
def split_env(in_memory_db):
    """Bridge app + one consent grant (same wiring as the S25 suite)."""
    user = User(email="s26@mail.lmt-pytest.dev", hashed_password="x",
                display_name="S26")
    in_memory_db.add(user)
    in_memory_db.commit()
    in_memory_db.refresh(user)

    app = FastAPI()
    app.include_router(bridge_module.router)
    app.include_router(bridge_module.ws_router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as test_client:
        created = test_client.post(
            "/api/bridge/permissions",
            json={"name": "studio-mac", "scopes": ["status", "train"]},
        ).json()
        yield test_client, created


def _hello(ws, created):
    ws.send_json({"type": "hello", "protocol": "llmtuner-companion/0",
                  "name": "studio-mac", "token": created["token"],
                  "capabilities": {"platform": "darwin"}})
    assert ws.receive_json()["type"] == "welcome"


def _artifacts(test_client):
    resp = test_client.get("/api/bridge/artifacts")
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_manifest_upserts_pointer_rows_and_lists_them(split_env, in_memory_db):
    test_client, created = split_env
    with test_client.websocket_connect("/companion/ws") as ws:
        _hello(ws, created)
        ws.send_json({"type": "artifacts", "items": ARTIFACT_ITEMS})
        ack = ws.receive_json()
        assert ack["type"] == "artifacts_ack" and ack["ok"] is True
        assert ack["stored"] == 2

    rows = _artifacts(test_client)
    assert len(rows) == 2
    by_kind = {r["kind"]: r for r in rows}
    assert by_kind["adapter"]["sha256"] == "a" * 64
    assert by_kind["adapter"]["size_bytes"] == 41_943_040
    # pointer semantics: the device path round-trips as a STRING only —
    # nothing opened or resolved it (this DB never had that dir).
    assert by_kind["fused"]["device_path"] == "/Users/carlos/_training_runs/7/fused_model"
    assert by_kind["fused"]["device_name"] == "studio-mac"
    assert by_kind["fused"]["device_online"] is False  # socket closed after block

    # The split holds: reporting artifacts never creates hosted training/model rows.
    assert in_memory_db.query(FineTunedModel).count() == 0


def test_re_report_upserts_instead_of_duplicating(split_env, in_memory_db):
    test_client, created = split_env
    with test_client.websocket_connect("/companion/ws") as ws:
        _hello(ws, created)
        ws.send_json({"type": "artifacts", "items": ARTIFACT_ITEMS})
        assert ws.receive_json()["stored"] == 2
        updated = [dict(i) for i in ARTIFACT_ITEMS if i["kind"] == "adapter"]
        updated[0]["size_bytes"] = 999
        updated[0]["name"] = "run7-adapters-v2"
        ws.send_json({"type": "artifacts", "items": updated})
        assert ws.receive_json()["stored"] == 1

    rows = _artifacts(test_client)
    assert len(rows) == 2  # not three
    adapter = next(r for r in rows if r["kind"] == "adapter")
    assert adapter["size_bytes"] == 999 and adapter["name"] == "run7-adapters-v2"


def test_bad_frames_are_rejected_and_store_nothing(split_env, in_memory_db):
    test_client, created = split_env
    bad = [
        {"type": "artifacts", "items": []},                               # empty
        {"type": "artifacts", "items": [{"device_run_id": 1, "kind": "rm_rf",
                                         "name": "x"}]},                  # bad kind
        {"type": "artifacts", "items": [{"device_run_id": 1, "kind": "gguf",
                                         "name": "x", "sha256": "nothex"}]},  # bad sha
    ]
    with test_client.websocket_connect("/companion/ws") as ws:
        _hello(ws, created)
        for frame in bad:
            ws.send_json(frame)
            ack = ws.receive_json()
            assert ack["type"] == "artifacts_ack" and ack["ok"] is False
            assert ack["stored"] == 0

    assert _artifacts(test_client) == []


def test_artifacts_are_per_user(split_env):
    test_client, created = split_env
    with test_client.websocket_connect("/companion/ws") as ws:
        _hello(ws, created)
        ws.send_json({"type": "artifacts", "items": ARTIFACT_ITEMS[:1]})
        assert ws.receive_json()["stored"] == 1

    # Second account sees nothing of the first, and cannot delete it.
    victim = _artifacts(test_client)[0]
    test_client.app.dependency_overrides[get_current_user] = lambda: User(
        id=999, email="other@mail.lmt-pytest.dev", hashed_password="x")
    assert test_client.get("/api/bridge/artifacts").json() == []
    assert test_client.delete(f"/api/bridge/artifacts/{victim['id']}").status_code == 404


def test_delete_forgets_exactly_one_pointer(split_env, in_memory_db):
    test_client, created = split_env
    with test_client.websocket_connect("/companion/ws") as ws:
        _hello(ws, created)
        ws.send_json({"type": "artifacts", "items": ARTIFACT_ITEMS})
        ws.receive_json()

    rows = _artifacts(test_client)
    victim = next(r for r in rows if r["kind"] == "adapter")
    assert test_client.delete(f"/api/bridge/artifacts/{victim['id']}").status_code == 204
    assert [r["kind"] for r in _artifacts(test_client)] == ["fused"]
    assert test_client.delete(f"/api/bridge/artifacts/{victim['id']}").status_code == 404
