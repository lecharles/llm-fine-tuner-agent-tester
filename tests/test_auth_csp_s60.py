"""S60: auth throttle + CSP regressions extended on top of S44.

Three contracts pinned here that S44 left partially covered:

1. XSS-ish payloads through login/signup are DATA, never reflected HTML:
   every auth response (401, 429, 201, 200) is application/json, error
   details are fixed strings, and the canary never rides back in an error
   body. A malicious display_name round-trips byte-exact through signup
   and /me as JSON (escaping is the frontend's render-time job; the API
   must not HTML-reflect and must not 500 on it).

2. Security headers decorate the responses that BYPASS route handlers:
   the SPA catch-all fallback (index.html on a deep link), the JSON 404
   the catch-all raises for unknown /api/*, FastAPI's native 404, and the
   no-build splash. The S44 pure-ASGI middleware wraps the whole stack,
   so these must all carry CSP + the base trio.

3. Throttled responses (login 429 AND signup 429) carry both Retry-After
   and the security headers — a blocked request is exactly the response
   an attacker sees most, so the headers must not be special-cased away
   by the HTTPException path.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Unique canary: reflection assertions grep for "s60-canary", so a
# coincidental "script" substring in unrelated wording can't false-pass.
CANARY = "s60-canary"
XSS_SCRIPT = f"<script>alert('{CANARY}')</script>"
XSS_ATTR = f'"><img src=x onerror=alert(1) /* {CANARY} */>'


def _login(client, username, password="anything"):
    return client.post(
        "/api/auth/login",
        data={"username": username, "password": password},
    )


def _signup(client, email, password="s60-pw", display_name=None):
    return client.post("/api/auth/signup", json={
        "email": email, "password": password, "display_name": display_name,
    })


@pytest.fixture()
def sec_client(in_memory_db, monkeypatch, tmp_path):
    """Auth router + S44 headers + a built SPA dist, shaped like :8090.

    Limiter windows are process-global; this fixture owns them and resets
    on both ends so bleed between tests is impossible.
    """
    import config
    import static_serve
    from core import security_headers
    from core.rate_limit import login_limiter, signup_limiter
    from database import get_db
    from routers import auth

    login_limiter.reset()
    signup_limiter.reset()
    monkeypatch.setattr(config.settings, "login_failed_limit_per_minute", 3)
    monkeypatch.setattr(config.settings, "signup_rate_limit_per_hour", 50)

    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text(
        "<!doctype html><title>SPA s60</title>", encoding="utf-8"
    )
    monkeypatch.setattr(config.settings, "static_dir", str(dist))

    app = FastAPI()
    security_headers.register(app)
    app.include_router(auth.router)
    static_serve.mount_spa(app)  # registered last: catch-all after routers

    def _override_db():
        yield in_memory_db

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    login_limiter.reset()
    signup_limiter.reset()


# ---------------------------------------------------------------- part 1
# XSS-ish payloads through the auth endpoints


def test_xss_username_login_401_never_reflects_payload(sec_client):
    for username in (XSS_SCRIPT, XSS_ATTR):
        r = _login(sec_client, username)
        assert r.status_code == 401
        assert r.headers["content-type"].startswith("application/json")
        # Fixed generic wording — the identifier never rides back.
        assert r.json()["detail"] == "Incorrect email or password"
        assert CANARY not in r.text


def test_xss_password_round_trips_as_data(sec_client):
    email = "pw-s60@example.com"
    assert _signup(sec_client, email, password=XSS_SCRIPT).status_code == 201
    # The payload password is just bytes to bcrypt: login succeeds.
    ok = _login(sec_client, email, password=XSS_SCRIPT)
    assert ok.status_code == 200
    assert ok.json()["token_type"] == "bearer"
    # A wrong try that *contains* the payload in the password must not
    # echo it in the error either.
    bad = _login(sec_client, email, password=f"nope-{XSS_ATTR}")
    assert bad.status_code == 401 and CANARY not in bad.text


def test_xss_display_name_json_not_html_on_signup_and_me(sec_client):
    email = "name-s60@example.com"
    r = _signup(sec_client, email, display_name=XSS_SCRIPT)
    assert r.status_code == 201
    assert r.headers["content-type"].startswith("application/json")
    # JSON body (parseable), payload preserved verbatim as data.
    assert r.json()["display_name"] == XSS_SCRIPT

    token = _login(sec_client, email, password="s60-pw").json()["access_token"]
    me = sec_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    assert me.headers["content-type"].startswith("application/json")
    assert me.json()["display_name"] == XSS_SCRIPT
    # Belt for the render side: this response is CSP-covered too.
    assert "content-security-policy" in me.headers


def test_xss_identity_throttles_and_429_never_reflects(sec_client):
    for _ in range(3):  # login_failed_limit_per_minute = 3 in fixture
        assert _login(sec_client, XSS_SCRIPT).status_code == 401
    blocked = _login(sec_client, XSS_SCRIPT)
    assert blocked.status_code == 429
    assert CANARY not in blocked.text
    assert "Retry-After" in blocked.headers


# ---------------------------------------------------------------- part 2
# Security headers on responses produced outside route handlers


def test_csp_on_spa_fallback_deep_link(sec_client):
    r = sec_client.get("/datasets/42")  # client-side route -> index.html
    assert r.status_code == 200
    assert "SPA s60" in r.text
    csp = r.headers["content-security-policy"]
    assert "default-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"


def test_csp_on_api_json_404_under_spa_catchall(sec_client):
    # The catch-all's api/ branch answers JSON, not HTML — with headers on.
    r = sec_client.get("/api/definitely-not-a-route")
    assert r.status_code == 404
    assert r.json()["detail"] == "Not Found"
    assert "content-security-policy" in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"


def test_csp_on_native_404_without_spa():
    app = FastAPI()
    from core import security_headers

    security_headers.register(app)
    r = TestClient(app).get("/no-such-page")  # Starlette's own 404
    assert r.status_code == 404
    assert "content-security-policy" in r.headers


def test_splash_carries_security_headers(monkeypatch, tmp_path):
    # No dist on disk -> mount_spa installs the splash route; the no-build
    # first boot of a public instance must still be header-covered.
    import config
    import static_serve
    from core import security_headers

    monkeypatch.setattr(config.settings, "static_dir", str(tmp_path / "none"))
    app = FastAPI()
    security_headers.register(app)
    assert static_serve.mount_spa(app) is False
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "server up" in r.text.lower()
    assert "content-security-policy" in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"


# ---------------------------------------------------------------- part 3
# Throttled (429) responses carry Retry-After AND security headers


def test_login_429_carries_security_headers(sec_client):
    email = "hdr-s60@example.com"
    assert _signup(sec_client, email).status_code == 201
    for _ in range(3):
        assert _login(sec_client, email, "bad").status_code == 401
    blocked = _login(sec_client, email, "bad")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    # HTTPException path still passes through the pure-ASGI middleware.
    assert "content-security-policy" in blocked.headers
    assert blocked.headers["x-content-type-options"] == "nosniff"
    assert blocked.headers["referrer-policy"] == "no-referrer"


def test_signup_429_carries_security_headers(sec_client, monkeypatch):
    import config
    from core.rate_limit import signup_limiter

    monkeypatch.setattr(config.settings, "signup_rate_limit_per_hour", 2)
    signup_limiter.reset()
    for i in range(2):  # every attempt counts, even the 409-bound ones
        assert _signup(sec_client, f"s{i}-s60@example.com").status_code == 201
    blocked = _signup(sec_client, "blocked-s60@example.com")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert "content-security-policy" in blocked.headers
    # The refused email is not reflected beyond the fixed message.
    assert blocked.json()["detail"] == (
        "Too many signup attempts from this address. Try again later."
    )
