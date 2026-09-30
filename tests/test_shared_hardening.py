"""S15 (#17) regressions: shared-instance hardening.

Covers the three issue-#17 guarantees: signup returns 429 once the
per-IP/hour budget is spent, LOCAL_MODE=true + a non-loopback uvicorn
bind refuses startup, and a running local_mode instance refuses
non-loopback peers with 403 (keeping /health open for monitors).

All peers are RFC 5737 documentation addresses; nothing hits a real
network here.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import config
from core import bind_guard
from routers import auth

PASSWORD = "correct-horse-battery"
PUBLIC_PEER = ("203.0.113.7", 51234)    # TEST-NET-3, pretend remote client
LOOPBACK_PEER = ("127.0.0.1", 51234)


def _signup(client, n: int):
    return client.post(
        "/api/auth/signup",
        json={
            "email": f"s15-user-{n}@mail.lmt-pytest.dev",
            "password": PASSWORD,
            "display_name": "S15 Tester",
        },
    )


# --- signup rate limit ------------------------------------------------------

def test_signup_second_attempt_same_hour_is_429(client, monkeypatch):
    monkeypatch.setattr(config.settings, "signup_rate_limit_per_hour", 1)
    assert _signup(client, 1).status_code == 201
    r = _signup(client, 2)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1
    assert "signup attempts" in r.json()["detail"].lower()


def test_failed_attempts_still_burn_the_window(client, monkeypatch):
    # Duplicate-email 400s are attempts too, or probing stays free.
    monkeypatch.setattr(config.settings, "signup_rate_limit_per_hour", 2)
    assert _signup(client, 1).status_code == 201
    assert _signup(client, 1).status_code == 400  # duplicate email
    assert _signup(client, 2).status_code == 429  # budget already spent


def test_signup_rate_limit_can_be_disabled(client, monkeypatch):
    monkeypatch.setattr(config.settings, "signup_rate_limit_per_hour", 0)
    for n in range(1, 4):
        assert _signup(client, n).status_code == 201


# --- local_mode bind refusal -------------------------------------------------

def _guarded_client(peer):
    """Minimal app with the real guard middleware + auth router mounted."""
    app = FastAPI()
    app.include_router(auth.router)
    bind_guard.register(app)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return TestClient(app, client=peer)


def test_startup_refuses_local_mode_on_public_bind(monkeypatch):
    monkeypatch.setattr(config.settings, "local_mode", True)
    argv = ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8090"]
    with pytest.raises(RuntimeError, match="local_mode"):
        bind_guard.ensure_local_mode_bind_ok(argv)


def test_startup_allows_local_mode_on_loopback_or_default(monkeypatch):
    monkeypatch.setattr(config.settings, "local_mode", True)
    base = ["python", "-m", "uvicorn", "main:app"]
    bind_guard.ensure_local_mode_bind_ok(base + ["--host", "127.0.0.1"])
    bind_guard.ensure_local_mode_bind_ok(base + ["--host", "::1"])
    bind_guard.ensure_local_mode_bind_ok(base + ["--host", "localhost"])
    bind_guard.ensure_local_mode_bind_ok(base)  # no flag => uvicorn default


def test_startup_allows_public_bind_when_local_mode_off(monkeypatch):
    monkeypatch.setattr(config.settings, "local_mode", False)
    bind_guard.ensure_local_mode_bind_ok(
        ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0"]
    )


def test_runtime_local_mode_403s_non_loopback_but_keeps_health(monkeypatch):
    monkeypatch.setattr(config.settings, "local_mode", True)
    c = _guarded_client(PUBLIC_PEER)
    r = c.get("/api/auth/config")
    assert r.status_code == 403
    assert "docs/CREDENTIALS.md" in r.json()["detail"]
    assert c.get("/health").status_code == 200


def test_runtime_local_mode_serves_loopback_peers(monkeypatch):
    monkeypatch.setattr(config.settings, "local_mode", True)
    c = _guarded_client(LOOPBACK_PEER)
    r = c.get("/api/auth/config")
    assert r.status_code == 200
    assert r.json() == {"local_mode": True}


def test_runtime_guard_inactive_when_local_mode_off(monkeypatch):
    monkeypatch.setattr(config.settings, "local_mode", False)
    c = _guarded_client(PUBLIC_PEER)
    r = c.get("/api/auth/config")
    assert r.status_code == 200
    assert r.json() == {"local_mode": False}
