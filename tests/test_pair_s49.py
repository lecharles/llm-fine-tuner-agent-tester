"""S49 regressions: companion bridge 1 — the pairing redemption lane.

Covers the row's three surfaces:
- `POST /api/bridge/pair` redeems a pasted token against the S25 consent
  ledger: active tokens return the grant summary (name/scopes/ws path),
  unknown AND revoked tokens get the same 401 wording (no guessing oracle),
  malformed paste gets a 422 that tells the user about the `br1-` prefix,
  and because the endpoint is JWT-free by design, failed redemptions burn
  a per-peer sliding window (429 + Retry-After) while success clears it;
- the CLI helpers (`llmtuner companion`) are pure and offline-testable:
  hub URL mapping, 0600 pair-file roundtrip, masked status, and the
  redemption happy/sad paths with the HTTP seam monkeypatched.

No sockets, no Mac, nothing real dialed.
"""

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.rate_limit import pair_limiter
from core.security import get_current_user
from database import get_db
from models.user import User
from routers import bridge as bridge_module

# The CLI package is not an installed dependency of the backend; borrow it.
CLI_ROOT = Path(__file__).resolve().parent.parent / "cli"
if str(CLI_ROOT) not in sys.path:
    sys.path.insert(0, str(CLI_ROOT))


@pytest.fixture()
def pair_env(in_memory_db):
    user = User(email="s49@mail.lmt-pytest.dev", hashed_password="x", display_name="S49")
    in_memory_db.add(user)
    in_memory_db.commit()
    in_memory_db.refresh(user)

    app = FastAPI()
    app.include_router(bridge_module.router)
    app.include_router(bridge_module.ws_router)
    app.dependency_overrides[get_db] = lambda: in_memory_db
    app.dependency_overrides[get_current_user] = lambda: user

    pair_limiter.reset()  # module-global windows must not leak between tests
    with TestClient(app) as test_client:
        yield test_client, user
    pair_limiter.reset()


def _create(test_client, name="studio-mac", scopes=("status", "train")):
    resp = test_client.post("/api/bridge/permissions",
                            json={"name": name, "scopes": list(scopes)})
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- hub-side redemption: POST /api/bridge/pair -----------------------------

def test_pair_redeems_active_token_and_summarizes_the_grant(pair_env):
    test_client, _ = pair_env
    created = _create(test_client, name="air-m1", scopes=("status", "fuse"))

    resp = test_client.post("/api/bridge/pair", json={"token": created["token"]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["paired"] is True
    assert body["permission_id"] == created["id"]
    assert body["name"] == "air-m1"
    assert body["granted_scopes"] == ["fuse", "status"]  # schema sorts them
    assert body["protocol"] == "llmtuner-companion/0"
    assert body["ws_path"] == "/companion/ws"
    assert body["already_online"] is False
    # the response must not re-echo the token (it already left once)
    assert created["token"] not in resp.text


def test_pair_unknown_and_revoked_share_one_401_wording(pair_env):
    test_client, _ = pair_env
    created = _create(test_client)

    ghost = test_client.post("/api/bridge/pair", json={"token": "br1-" + "z" * 32})
    assert ghost.status_code == 401
    revoked = test_client.post(f"/api/bridge/permissions/{created['id']}/revoke")
    assert revoked.status_code == 200

    stale = test_client.post("/api/bridge/pair", json={"token": created["token"]})
    assert stale.status_code == 401
    # no oracle: identical detail for "never existed" and "was revoked"
    assert stale.json()["detail"] == ghost.json()["detail"]


def test_pair_malformed_paste_is_422(pair_env):
    test_client, _ = pair_env
    resp = test_client.post("/api/bridge/pair", json={"token": "totally-wrong-shape"})
    assert resp.status_code == 422
    assert "br1-" in resp.text  # the validator tells the user what to copy

    empty = test_client.post("/api/bridge/pair", json={"token": ""})
    assert empty.status_code == 422


def test_pair_failures_burn_the_window_then_success_clears_it(pair_env):
    test_client, _ = pair_env
    created = _create(test_client)

    for i in range(bridge_module.PAIR_ATTEMPTS_PER_WINDOW):
        bad = test_client.post("/api/bridge/pair", json={"token": f"br1-guess-{i:02d}padpad"})
        assert bad.status_code == 401, f"attempt {i}"

    throttled = test_client.post("/api/bridge/pair", json={"token": created["token"]})
    assert throttled.status_code == 429
    assert "Retry-After" in throttled.headers

    # A success clears the key: reset, spend failures, redeem, spend MORE
    # failures than the window — still allowed, because the win wiped them.
    pair_limiter.reset()
    for i in range(3):
        assert test_client.post("/api/bridge/pair",
                                json={"token": "br1-nope-nope-nope"}).status_code == 401
    ok = test_client.post("/api/bridge/pair", json={"token": created["token"]})
    assert ok.status_code == 200
    for i in range(bridge_module.PAIR_ATTEMPTS_PER_WINDOW):
        again = test_client.post("/api/bridge/pair", json={"token": f"br1-more-{i:02d}padpad"})
        assert again.status_code == 401, f"post-success attempt {i} should still be allowed"


# --- CLI helpers (cli/llmtuner/companion.py), offline ------------------------

from llmtuner import companion as cli_mod  # noqa: E402


@pytest.mark.parametrize("base,expected", [
    ("https://tuner.example", "wss://tuner.example/companion/ws"),
    ("https://tuner.example/", "wss://tuner.example/companion/ws"),
    ("http://127.0.0.1:8090", "ws://127.0.0.1:8090/companion/ws"),
    ("tuner.example:8443", "wss://tuner.example:8443/companion/ws"),
    ("wss://tuner.example/companion/ws", "wss://tuner.example/companion/ws"),
    ("", ""),
])
def test_cli_ws_url_mapping(base, expected):
    assert cli_mod.ws_url_for(base) == expected


def test_cli_pair_roundtrip_is_owner_only(tmp_path, monkeypatch):
    monkeypatch.setenv("LLMTUNER_HOME", str(tmp_path))
    assert cli_mod.read_pair() is None

    cli_mod.write_pair({"token": "br1-secret", "hub": "wss://h/companion/ws"})
    path = cli_mod.pair_file()
    assert path.exists()
    assert (path.stat().st_mode & 0o777) == 0o600  # plaintext token: owner only
    assert cli_mod.read_pair()["token"] == "br1-secret"


def test_cli_pair_flow_writes_only_on_success(tmp_path, monkeypatch):
    monkeypatch.setenv("LLMTUNER_HOME", str(tmp_path))
    calls = []

    def fake_post(api_base, token, timeout=15.0):
        calls.append((api_base, token))
        if token == "br1-good":
            return 200, {"paired": True, "permission_id": 5, "name": "air-m1",
                         "granted_scopes": ["status"], "protocol": "llmtuner-companion/0",
                         "ws_path": "/companion/ws", "already_online": False}
        return 401, {"detail": "pairing token rejected — no active bridge permission matches"}

    monkeypatch.setattr(cli_mod, "_post_pair", fake_post)

    assert cli_mod.pair("https://tuner.example", token="br1-bad") == 1
    assert cli_mod.read_pair() is None  # nothing persisted on a rejection

    assert cli_mod.pair("https://tuner.example", token="br1-good") == 0
    assert calls[1] == ("https://tuner.example", "br1-good")
    saved = cli_mod.read_pair()
    assert saved["device_name"] == "air-m1"
    assert saved["hub"] == "wss://tuner.example/companion/ws"


def test_cli_status_masks_the_token(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("LLMTUNER_HOME", str(tmp_path))
    cli_mod.write_pair({"token": "br1-supersecretvalue123456", "hub": "wss://h/companion/ws",
                        "device_name": "studio", "permission_id": 1,
                        "granted_scopes": ["status", "train"], "paired_at": "2026-11-07T00:00:00+00:00"})
    assert cli_mod.status() == 0
    out = capsys.readouterr().out
    assert "br1-supersecretvalue123456" not in out  # masked to the tail
    assert "studio" in out
