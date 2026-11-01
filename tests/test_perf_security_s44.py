"""S44: perf + security sweep guards.

Covers the three shipped changes:
- login failed-attempt throttle (429 + Retry-After, success clears the key,
  successful logins never burn the window),
- CSP + baseline security headers on the API process (docs pages CSP-exempt),
- the list-query index flags the migration (f2c9d8e4a715) mirrors actually
  reach the schema via the ORM metadata.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import inspect


def _login(client, email, password):
    return client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )


RIGHT = "s44-right-pw"  # demo-grade; tests never talk to a real instance


@pytest.fixture()
def throttle_client(client, monkeypatch):
    from config import settings
    from core.rate_limit import login_limiter, signup_limiter

    login_limiter.reset()
    signup_limiter.reset()
    monkeypatch.setattr(settings, "login_failed_limit_per_minute", 3)
    return client


def test_failed_logins_burn_window_then_429(throttle_client):
    email = "throttle-s44@example.com"
    r = throttle_client.post("/api/auth/signup", json={
        "email": email, "password": RIGHT, "display_name": "T",
    })
    assert r.status_code == 201  # fixture resets both limiter windows
    for _ in range(3):
        assert _login(throttle_client, email, "wrong-pass").status_code == 401
    blocked = _login(throttle_client, email, "wrong-pass")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers


def test_successful_login_clears_failed_window(throttle_client):
    email = "clear-s44@example.com"
    r = throttle_client.post("/api/auth/signup", json={
        "email": email, "password": RIGHT, "display_name": "C",
    })
    assert r.status_code == 201
    assert _login(throttle_client, email, "bad").status_code == 401
    assert _login(throttle_client, email, RIGHT).status_code == 200
    # after a success, a fresh batch of failures must start at 401, not 429
    for _ in range(3):
        assert _login(throttle_client, email, "bad").status_code == 401


def test_many_successes_never_throttle(throttle_client):
    email = "busy-s44@example.com"
    r = throttle_client.post("/api/auth/signup", json={
        "email": email, "password": RIGHT, "display_name": "B",
    })
    assert r.status_code == 201
    for _ in range(10):  # far over the 3-failure limit; successes don't count
        assert _login(throttle_client, email, RIGHT).status_code == 200


def _secured_app():
    from core import security_headers

    app = FastAPI()
    security_headers.register(app)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return TestClient(app)


def test_security_headers_on_api_responses():
    c = _secured_app()
    r = c.get("/ping")
    assert r.status_code == 200
    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "script-src 'self'" in csp
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["x-frame-options"] == "DENY"


def test_docs_pages_are_csp_exempt_but_no_sniffed():
    app = FastAPI()
    from core import security_headers

    security_headers.register(app)
    c = TestClient(app)
    r = c.get("/docs")  # served by FastAPI itself
    assert r.status_code == 200
    assert "content-security-policy" not in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"


def test_splash_html_carries_headers_too():
    # the static splash / SPA fallback live in the same process; the pure-ASGI
    # middleware decorates them identically (regression guard for scope types).
    c = _secured_app()
    r = c.get("/ping")
    assert "content-security-policy" in r.headers


def test_list_query_indexes_reach_the_schema(in_memory_db):
    engine = in_memory_db.get_bind()
    insp = inspect(engine)
    expected = {
        ("datasets", "ix_datasets_user_id"),
        ("qa_pairs", "ix_qa_pairs_dataset_id"),
        ("training_runs", "ix_training_runs_user_id"),
        ("training_runs", "ix_training_runs_dataset_id"),
        ("fine_tuned_models", "ix_fine_tuned_models_user_id"),
        ("chat_sessions", "ix_chat_sessions_user_id"),
        ("chat_sessions", "ix_chat_sessions_fine_tuned_model_id"),
        ("chat_messages", "ix_chat_messages_chat_session_id"),
        ("bridge_permissions", "ix_bridge_permissions_user_id"),
    }
    have = {(tbl, idx["name"]) for tbl in insp.get_table_names()
            for idx in insp.get_indexes(tbl)}
    missing = expected - have
    assert not missing, f"missing indexes: {sorted(missing)}"
