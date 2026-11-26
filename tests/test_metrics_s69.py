"""S69: request-latency log lines + in-memory p50/p95 window.

Covers the three shipped pieces:
- the pure-ASGI middleware times http requests, logs ONE structured INFO
  line each (method/path/status/ms), records into the bounded window, and
  leaves websockets / exempt paths alone;
- percentile math is nearest-rank over the sorted window (empty -> None);
- GET /api/status carries the latency fragment — in-memory, restart-clear,
  no new deps.
"""

import asyncio
import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import metrics
from core.metrics import (
    EXEMPT_PATHS,
    WINDOW_SIZE,
    RequestMetricsMiddleware,
    percentile,
    sanitize_path,
    snapshot,
)


@pytest.fixture(autouse=True)
def clean_window():
    metrics.reset()
    yield
    metrics.reset()


# ---------- percentile math (nearest-rank, honest on small windows) ----------


def test_empty_window_percentiles_are_none():
    assert percentile([], 0.5) is None
    assert snapshot() == {
        "samples": 0,
        "window_size": WINDOW_SIZE,
        "p50_ms": None,
        "p95_ms": None,
    }


def test_nearest_rank_values():
    vals = [float(i) for i in range(1, 101)]  # sorted 1..100
    assert percentile(vals, 0.50) == 50.0
    assert percentile(vals, 0.95) == 95.0
    assert percentile([7.0], 0.95) == 7.0  # single sample: every q is it


def test_window_is_bounded_and_newest_win():
    for i in range(WINDOW_SIZE + 250):
        metrics.record(float(i))
    snap = snapshot()
    assert snap["samples"] == WINDOW_SIZE
    # oldest 250 evicted: window is now 250..1249, so p50 >= 250 — the
    # evicted head (0..249) can no longer drag it down below the floor.
    assert snap["p50_ms"] >= 250.0


def test_negative_record_floored():
    metrics.record(-123.0)
    assert snapshot()["p50_ms"] == 0.0


# ---------- middleware behaviour ----------


class _Echo:
    """Minimal ASGI app: accepts websockets, answers http with a status,
    optionally raises mid-handler."""

    def __init__(self, status_code=201, boom=False):
        self.status_code = status_code
        self.boom = boom

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            await send({"type": "websocket.accept"})
            await send({"type": "websocket.close"})
            return
        if self.boom:
            raise RuntimeError("handler exploded")
        await send({
            "type": "http.response.start",
            "status": self.status_code,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({"type": "http.response.body", "body": b"{}"})


def _drive(mw, scope):
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        pass

    asyncio.run(mw(scope, receive, send))


def _metric_lines(caplog):
    return [r.getMessage() for r in caplog.records if r.name == "llmtuner.metrics"]


def test_http_request_logged_with_shape(caplog):
    mw = RequestMetricsMiddleware(_Echo(status_code=204))
    with caplog.at_level(logging.INFO, logger="llmtuner.metrics"):
        _drive(mw, {"type": "http", "method": "GET", "path": "/api/x"})
    assert snapshot()["samples"] == 1
    lines = _metric_lines(caplog)
    assert len(lines) == 1
    line = lines[0]
    assert line.startswith("latency method=GET path=/api/x status=204 ms=")
    ms = float(line.rsplit("ms=", 1)[1])
    assert 0.0 <= ms < 60_000.0  # sane float, formatted to .1f


def test_ws_scope_passes_unmeasured(caplog):
    mw = RequestMetricsMiddleware(_Echo())
    with caplog.at_level(logging.INFO, logger="llmtuner.metrics"):
        _drive(mw, {"type": "websocket", "method": None, "path": "/companion/ws"})
    assert snapshot()["samples"] == 0
    assert _metric_lines(caplog) == []


def test_exempt_path_never_counted_or_logged(caplog):
    mw = RequestMetricsMiddleware(_Echo())
    for path in EXEMPT_PATHS:
        with caplog.at_level(logging.INFO, logger="llmtuner.metrics"):
            _drive(mw, {"type": "http", "method": "GET", "path": path})
    assert snapshot()["samples"] == 0
    assert _metric_lines(caplog) == []


def test_crashed_handler_still_times():
    mw = RequestMetricsMiddleware(_Echo(boom=True))
    with pytest.raises(RuntimeError):
        _drive(mw, {"type": "http", "method": "POST", "path": "/api/boom"})
    assert snapshot()["samples"] == 1  # the time really was spent


def test_crafted_newline_path_cannot_split_log_lines(caplog):
    assert sanitize_path("/a\nb\x1b[31m") == "/a?b?[31m"
    mw = RequestMetricsMiddleware(_Echo())
    with caplog.at_level(logging.INFO, logger="llmtuner.metrics"):
        _drive(mw, {"type": "http", "method": "GET", "path": "/a\nb\nc"})
    lines = _metric_lines(caplog)
    assert len(lines) == 1
    assert "\n" not in lines[0]
    assert "/a?b?c" in lines[0]


# ---------- /api/status integration ----------


@pytest.fixture()
def status_app(in_memory_db):
    """auth + status routers behind the S69 middleware, get_db overridden —
    same wiring order main.py ships (metrics registered outermost)."""
    from core.rate_limit import signup_limiter
    from database import get_db
    from routers import auth, status as status_router

    signup_limiter.reset()
    metrics.reset()

    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(status_router.router)

    def _override_db():
        yield in_memory_db

    app.dependency_overrides[get_db] = _override_db
    metrics.register(app)
    return app


def test_status_endpoint_carries_latency(status_app):
    with TestClient(status_app) as c:
        email = "s69@example.com"
        assert c.post("/api/auth/signup", json={
            "email": email, "password": "s69-password", "display_name": "M69",
        }).status_code == 201
        token = c.post(
            "/api/auth/login", data={"username": email, "password": "s69-password"}
        ).json()["access_token"]
        body = c.get("/api/status", headers={"Authorization": f"Bearer {token}"}).json()
    latency = body["latency"]
    assert set(latency) == {"samples", "window_size", "p50_ms", "p95_ms"}
    # The window is written in the middleware's finally block — a status
    # response reports its PRECEDING requests, never itself. Deterministic:
    # signup + login = exactly 2 samples in this brand-new window.
    assert latency["samples"] == 2
    assert latency["window_size"] == WINDOW_SIZE
    assert latency["p50_ms"] is not None
    assert latency["p95_ms"] >= latency["p50_ms"]  # 95 can never undercut 50
    # the auth shape S8 shipped is still intact next to the new fragment
    assert body["authenticated"] is True and body["lane"] == "user"
    # second call: the first status request is now counted
    with TestClient(status_app) as c:
        again = c.get(
            "/api/status", headers={"Authorization": f"Bearer {token}"}
        ).json()["latency"]
    assert again["samples"] == 3


def test_register_stacks_metrics_outermost_and_import_main_works():
    app = FastAPI()
    metrics.register(app)
    # add_middleware INSERTS at 0 — last registered is the outermost layer,
    # so metrics times the full inner stack (same trick S44 used for CSP).
    assert app.user_middleware[0].cls is RequestMetricsMiddleware
    # boot proof (S55 runbook step): the full app still imports clean
    import main  # noqa: F401
