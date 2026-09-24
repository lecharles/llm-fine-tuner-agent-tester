"""Auth regression tests for S9 (issue #12): signup/login/me in JWT mode.

Also pins the local-mode bypass and the S8 lane service-token path through
GET /api/auth/me, since both are auth regressions we explicitly do not want
back.
"""

import pytest

# Non-special test domain: email-validator rejects reserved TLDs like .test
# for EmailStr input validation. This is a fake account, never a real one.
EMAIL = "s9-user@mail.lmt-pytest.dev"
PASSWORD = "s9-fake-pw"
LANE_TOKEN = "sekrit-fake-lane-token"


def _signup_login(client, email=EMAIL, password=PASSWORD):
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "password": password, "display_name": "S9 Tester"},
    )
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    return body["access_token"]


def test_me_returns_user_without_password(client):
    token = _signup_login(client)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["email"] == EMAIL
    assert body["display_name"] == "S9 Tester"
    # The whole point: the hashed password never rides along in a response.
    assert "hashed_password" not in body
    assert "password" not in body


def test_me_rejects_missing_and_garbage_tokens(client):
    assert client.get("/api/auth/me").status_code == 401
    garbage = "Bearer not-a-jwt-at-all"
    r = client.get("/api/auth/me", headers={"Authorization": garbage})
    assert r.status_code == 401


def test_login_wrong_password_is_401(client):
    _signup_login(client)
    r = client.post("/api/auth/login", data={"username": EMAIL, "password": "***"})
    assert r.status_code == 401


def test_login_form_accepts_browser_origin_header(client):
    """H1 regression: browser-shaped POSTs carrying Origin must still get 200."""
    _signup_login(client)
    r = client.post(
        "/api/auth/login",
        data={"username": EMAIL, "password": PASSWORD},
        headers={"Origin": "http://localhost:5173"},
    )
    assert r.status_code == 200, r.text


def test_me_rejects_expired_token(client, monkeypatch):
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    import config

    # Expire in the past, then mint a token that is already stale.
    monkeypatch.setattr(config.settings, "access_token_expire_minutes", -5)
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    token = jwt.encode(
        {"sub": "42", "exp": past},
        config.settings.jwt_secret_key,
        algorithm=config.settings.jwt_algorithm,
    )
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_me_rejects_token_signed_with_wrong_key(client, monkeypatch):
    from datetime import datetime, timedelta, timezone

    from jose import jwt

    import config

    future = datetime.now(timezone.utc) + timedelta(hours=1)
    token = jwt.encode(
        {"sub": "1", "exp": future},
        "attacker-key",
        algorithm=config.settings.jwt_algorithm,
    )
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_local_mode_me_serves_seeded_user(client, in_memory_db, monkeypatch):
    """local mode bypass: no token, me == the auto-provisioned local user."""
    import config

    monkeypatch.setattr(config.settings, "local_mode", True)
    r = client.get("/api/auth/me")
    assert r.status_code == 200
    assert r.json()["email"] == "local@llmtuner"
    # Idempotent: second call reuses the same row.
    assert client.get("/api/auth/me").json()["id"] == r.json()["id"]


def test_lane_service_token_authenticates_as_lane_user(client, monkeypatch):
    import config

    monkeypatch.setattr(config.settings, "api_service_tokens", f"pytest-lane:{LANE_TOKEN}")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {LANE_TOKEN}"})
    assert r.status_code == 200
    assert r.json()["email"] == "lane-pytest-lane@service.local"
    # JWT users are unaffected by the lane config.
    token = _signup_login(client)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_service_token_parsing_edge_cases():
    from core.security import parse_service_tokens, resolve_service_lane

    import config

    raw = "lane-a:tok-a, :bad, lane-b:tok-b ,no-colon"
    original = config.settings.api_service_tokens
    config.settings.api_service_tokens = raw
    try:
        lanes = parse_service_tokens()
        assert [lane.name for lane in lanes] == ["lane-a", "lane-b"]
        assert resolve_service_lane("tok-b").name == "lane-b"
        assert resolve_service_lane("nope") is None
    finally:
        config.settings.api_service_tokens = original
