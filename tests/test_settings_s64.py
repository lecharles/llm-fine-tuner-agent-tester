"""S64 regressions: Settings page backend surface.

Guarantees covered:
- PATCH /api/auth/me: display-name round-trip with strip; blank / too-long /
  NULL-byte bodies 422 before touching the DB; email is NOT on this surface;
- POST /api/auth/password: wrong current password 400s and never changes the
  hash; correct current password rotates (old login 401s, new login works);
  new password under 8 chars 422s; failed attempts burn the (peer, user)
  login window into a 429 with Retry-After, and a success still clears it;
  already-issued JWTs keep working until expiry (stateless by design — the
  slice documents it, the test pins it);
- GET /api/auth/session: reports the REAL auth shape — jwt (subject +
  expiry), service_lane (lane name, never token bytes), local (local-mode
  bypass) — and 401s with no bearer at all;
- service lanes get read/create/queue only: both account writes 403.
"""

import pytest
from datetime import datetime, timezone

from config import settings
from core.rate_limit import login_limiter, signup_limiter

PW1 = "corr3ct-horse-battery"
PW2 = "rotated-horse-battery-2"
EMAIL = "s64-acc@lmt-pytest.dev"


@pytest.fixture(autouse=True)
def _fresh_windows():
    # Process-global sliding windows: give every test a clean slate and
    # restore the production-ish limits afterwards.
    signup_limiter.reset()
    login_limiter.reset()
    yield
    signup_limiter.reset()
    login_limiter.reset()


def _signup_login(client, email=EMAIL, password=PW1):
    r = client.post("/api/auth/signup",
                    json={"email": email, "password": password, "display_name": "Old Name"})
    assert r.status_code == 201, r.text
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── display name ──────────────────────────────────────────────────────────

def test_display_name_roundtrip_and_strip(client):
    token = _signup_login(client)
    r = client.patch("/api/auth/me", json={"display_name": "  Carlos  "}, headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json()["display_name"] == "Carlos"
    # GET /me is the same source the UserMenu reads — the write must be visible.
    assert client.get("/api/auth/me", headers=_auth(token)).json()["display_name"] == "Carlos"


def test_display_name_validation_rejects_before_writing(client):
    token = _signup_login(client)
    for bad in ("   ", "x" * 61, "ab\x00cd"):
        r = client.patch("/api/auth/me", json={"display_name": bad}, headers=_auth(token))
        assert r.status_code == 422, (bad, r.text)
    me = client.get("/api/auth/me", headers=_auth(token)).json()
    assert me["display_name"] == "Old Name"  # untouched
    assert me["email"] == EMAIL              # email never mutable here


# ── password change ───────────────────────────────────────────────────────

def test_password_change_rotates_and_reports_ttl_window(client):
    token = _signup_login(client)
    r = client.post("/api/auth/password",
                    json={"current_password": "wrong-current-9", "new_password": PW2},
                    headers=_auth(token))
    assert r.status_code == 400
    assert "Current password" in r.json()["detail"]

    r = client.post("/api/auth/password",
                    json={"current_password": PW1, "new_password": PW2},
                    headers=_auth(token))
    assert r.status_code == 200, r.text
    assert r.json() == {"changed": True, "jwt_ttl_minutes": settings.access_token_expire_minutes}

    # Old password is dead for logins; the new one works.
    r = client.post("/api/auth/login", data={"username": EMAIL, "password": PW1})
    assert r.status_code == 401
    assert client.post("/api/auth/login", data={"username": EMAIL, "password": PW2}).status_code == 200

    # Documented stateless-JWT semantics: the token minted before the
    # rotation keeps verifying until its natural expiry. If this ever
    # flips, the Settings page copy ("other devices expire within N min")
    # needs to change too — hence a pin, not an accident.
    me = client.get("/api/auth/me", headers=_auth(token))
    assert me.status_code == 200


def test_new_password_floor_is_422_not_a_write(client):
    token = _signup_login(client)
    r = client.post("/api/auth/password",
                    json={"current_password": PW1, "new_password": "shortie"},  # 7 chars
                    headers=_auth(token))
    assert r.status_code == 422
    # Old password still valid => nothing was written.
    assert client.post("/api/auth/login",
                       data={"username": EMAIL, "password": PW1}).status_code == 200


def test_failed_password_changes_throttle_but_success_clears(client, monkeypatch):
    monkeypatch.setattr(settings, "login_failed_limit_per_minute", 3)
    token = _signup_login(client)
    for _ in range(3):
        r = client.post("/api/auth/password",
                        json={"current_password": "guessed-" + "x", "new_password": PW2},
                        headers=_auth(token))
        assert r.status_code == 400
    r = client.post("/api/auth/password",
                    json={"current_password": "nope", "new_password": PW2},
                    headers=_auth(token))
    assert r.status_code == 429
    assert "Retry-After" in r.headers

    # The honest user who finally brings the RIGHT current password still
    # gets through (window cleared on success) — same S44 login semantics.
    r = client.post("/api/auth/password",
                    json={"current_password": PW1, "new_password": PW2},
                    headers=_auth(token))
    assert r.status_code == 200, r.text


# ── session view ──────────────────────────────────────────────────────────

def test_session_reports_jwt_with_expiry(client):
    token = _signup_login(client)
    r = client.get("/api/auth/session", headers=_auth(token))
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["mode"] == "jwt"
    assert out["lane"] is None
    assert out["local_mode"] is False
    assert out["algorithm"] == settings.jwt_algorithm
    # subject is the user id the JWT carries — /me agrees on the same row.
    me = client.get("/api/auth/me", headers=_auth(token)).json()
    assert out["subject"] == str(me["id"])
    assert 0 < out["expires_in_seconds"] <= settings.access_token_expire_minutes * 60
    exp = datetime.fromisoformat(out["expires_at"])
    assert exp.tzinfo is not None
    assert exp > datetime.now(timezone.utc)
    # Never a token echo.
    assert token not in r.text


def test_session_requires_a_bearer(client):
    assert client.get("/api/auth/session").status_code == 401


def test_session_reports_service_lane_and_lane_is_read_only(client, monkeypatch):
    monkeypatch.setattr(settings, "api_service_tokens", "tmux-test:sekrit-lane-token")
    headers = _auth("sekrit-lane-token")
    r = client.get("/api/auth/session", headers=headers)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["mode"] == "service_lane"
    assert out["lane"] == "tmux-test"
    assert out["subject"] == "lane-tmux-test"
    assert out["expires_at"] is None  # opaque config token, no per-token expiry
    assert "sekrit-lane-token" not in r.text

    # S8 permission rule on the account writes: 403, not silent success.
    assert client.patch("/api/auth/me", json={"display_name": "Renamed Lane"},
                        headers=headers).status_code == 403
    r = client.post("/api/auth/password",
                    json={"current_password": "whatever12", "new_password": PW2},
                    headers=headers)
    assert r.status_code == 403


def test_session_reports_local_mode(client, monkeypatch):
    monkeypatch.setattr(settings, "local_mode", True)
    # Local mode authenticates regardless of bearer content (Phase 6); the
    # real frontend ships the "local-mode-bypass" dummy — decode failure
    # must land on mode "local", not "other" or 401.
    headers = _auth("local-mode-bypass")
    r = client.get("/api/auth/session", headers=headers)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["mode"] == "local"
    assert out["local_mode"] is True
    me = client.get("/api/auth/me", headers=headers).json()
    assert me["email"] == "local@llmtuner"
    assert out["subject"] == str(me["id"])
    # And the local account can still edit its own name.
    assert client.patch("/api/auth/me", json={"display_name": "Studio Machine"},
                        headers=headers).json()["display_name"] == "Studio Machine"
