"""S52: companion protocol unit tests on the VPS (no Mac, no network).

Extends the S24 self_test() scenarios into hermetic pytest: the companion's
hello/welcome/pairing-token/auth-error framing is driven against a fake hub
that only queues raw frames. The real `websockets` library is never opened;
`connect` is monkeypatched. Nothing here touches mlx, ollama, or the backend.
"""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "companion" / "companion.py"


def _load_companion():
    # unique module name: other suites may import "companion" differently
    spec = importlib.util.spec_from_file_location("companion_s52", SPEC_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


mod = _load_companion()

CAPS = {
    "platform": "macOS-15.2-arm64",
    "machine": "Mac15,2",
    "mlx_lm": "0.19.1",
    "ollama": True,
    "cpus": 8,
    "memory_gb": 16,
}


class FakeWS:
    """Scripted inbound raw frames; records every sent object."""

    def __init__(self, inbound):
        self.inbound = list(inbound)
        self.sent = []

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def recv(self):
        if not self.inbound:
            raise ConnectionError("inbox empty")
        return self.inbound.pop(0)

    async def _iterate(self):
        while self.inbound:
            yield self.inbound.pop(0)

    def __aiter__(self):
        return self._iterate()


class FakeConn:
    def __init__(self, ws):
        self.ws = ws

    async def __aenter__(self):
        return self.ws

    async def __aexit__(self, *exc):
        return False


@pytest.fixture()
def hub(monkeypatch):
    """Patch websockets.connect + probes; return helper to script sessions."""
    import websockets  # imported lazily by companion, force it into sys.modules now
    calls = []

    def fake_connect(url, **kw):
        ws = FakeWS(session.pop(0)) if session else None
        calls.append((url, kw, ws))
        return FakeConn(ws)

    monkeypatch.setattr(websockets, "connect", fake_connect)
    monkeypatch.setattr(mod, "probe_capabilities", lambda: dict(CAPS))

    session = []

    class Hub:
        def __init__(self):
            self.calls = calls
            self._session = session

        def script(self, *sessions):
            """Each arg is the inbound frame list for one dial-out."""
            self._session.extend(list(s) for s in sessions)

    return Hub()


def make_companion():
    return mod.Companion(
        hub="wss://hub.example/api/bridge/ws",
        token="pair-tok-1",
        name="air-m1",
        start_backend=False,
    )


def test_hello_welcome_handshake(hub):
    hub.script([json.dumps({"type": "welcome", "companion_id": 42})])
    comp = make_companion()
    rc = asyncio.run(comp._session())
    assert rc == 0
    hello = hub.calls[0][2].sent[0]
    assert hello["type"] == "hello"
    assert hello["protocol"] == mod.PROTOCOL  # llmtuner-companion/0
    assert hello["name"] == "air-m1"
    assert hello["token"] == "pair-tok-1"  # S49: token rides hello, never the URL
    assert hello["capabilities"] == CAPS


def test_error_frame_before_welcome_is_auth_rejection(hub):
    hub.script([json.dumps({"type": "error", "detail": "unknown companion"})])
    comp = make_companion()
    with pytest.raises(mod.HubAuthError, match="unknown companion"):
        asyncio.run(comp._session())


def test_non_welcome_frame_before_welcome_is_auth_rejection(hub):
    hub.script([json.dumps({"type": "job", "id": "j0", "kind": "status"})])
    comp = make_companion()
    with pytest.raises(mod.HubAuthError, match="expected welcome"):
        asyncio.run(comp._session())


def test_non_json_welcome_is_a_plain_crash_not_auth(hub):
    hub.script(["not json at all"])
    comp = make_companion()
    with pytest.raises(ValueError, match="non-JSON"):
        asyncio.run(comp._session())


def test_run_returns_2_on_rejection_without_retry_looping(hub):
    hub.script([json.dumps({"type": "error", "detail": "revoked"})])
    comp = make_companion()
    rc = asyncio.run(comp.run())
    assert rc == 2
    assert len(hub.calls) == 1  # never re-dial a hub that rejected the token


def test_run_reconnects_after_transport_drop(hub):
    hub.script([], [json.dumps({"type": "welcome", "companion_id": 42})])
    comp = make_companion()
    rc = asyncio.run(comp.run())  # first dial: empty inbox -> ConnectionError -> redial
    assert rc == 0
    assert len(hub.calls) == 2
    hello = hub.calls[1][2].sent[0]
    assert hello["type"] == "hello" and hello["token"] == "pair-tok-1"


def test_status_job_roundtrip_frames(hub):
    inbound = [
        json.dumps({"type": "welcome", "companion_id": 42}),
        json.dumps({"type": "job", "id": "j1", "kind": "status", "payload": {}}),
    ]
    hub.script(inbound)
    comp = make_companion()

    async def fake_backend_up(self):
        return True

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(type(comp), "backend_up", fake_backend_up)
    try:
        async def scenario():
            rc = await comp._session()
            await asyncio.gather(*list(comp._tasks))  # same loop: let the job finish
            return rc

        assert asyncio.run(scenario()) == 0
    finally:
        monkeypatch.undo()

    frames = hub.calls[0][2].sent
    result = [f for f in frames if f["type"] == "result"]
    assert len(result) == 1
    assert result[0]["id"] == "j1" and result[0]["ok"] is True
    assert result[0]["data"]["capabilities"] == CAPS
    assert result[0]["data"]["backend_up"] is True


def test_unknown_job_kind_gets_failed_result(hub):
    inbound = [
        json.dumps({"type": "welcome", "companion_id": 42}),
        json.dumps({"type": "job", "id": "jX", "kind": "dance", "payload": {}}),
    ]
    hub.script(inbound)
    comp = make_companion()

    async def scenario():
        rc = await comp._session()
        await asyncio.gather(*list(comp._tasks))
        return rc

    assert asyncio.run(scenario()) == 0
    frames = hub.calls[0][2].sent
    result = [f for f in frames if f["type"] == "result"][0]
    assert result["id"] == "jX" and result["ok"] is False
    assert "unknown job kind" in result["data"]["detail"]
