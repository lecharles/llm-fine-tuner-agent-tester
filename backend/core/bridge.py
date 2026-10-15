"""S25 (#28) — in-process companion hub.

The hub is the *hosted side* of the Phase 6 opt-in bridge. Mac companions
dial OUT to `wss://HOST/companion/ws` (transport decision from
docs/ADR-001-phase6-hybrid-vs-local-first.md and companion/README.md), so
this module only ever tracks *outbound* sockets: one live session per
bridge permission id, plus the futures for jobs sent and awaiting a result.

Design notes / limits, stated on purpose:
- State is per-process (no Redis). The VPS team instance runs one uvicorn
  process (scripts/keepalive.sh), so that is fine; multi-worker deploys
  would need to move SESSIONS/RESULTS to shared state first.
- A companion that dials in without being *paired* (no active
  BridgePermission matching its token) gets an `error` frame and a closed
  socket — there is no implicit accept path anywhere in the bridge.
- Job dispatch here is request/response style (`send_job` + `await_job`)
  over the existing `llmtuner-companion/0` protocol frames, kept compatible
  with companion/companion.py as shipped by S24.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field

logger = logging.getLogger("llmtuner.bridge")

# The wire protocol companion/companion.py (S24) speaks in its hello frame.
# The hub must answer it verbatim or every dial-out is rejected.
PROTOCOL = "llmtuner-companion/0"


class CompanionHelloRejected(Exception):
    """Bad hello frame or a pairing token with no active permission."""


def rejected(detail: str) -> CompanionHelloRejected:
    return CompanionHelloRejected(detail)

# Job kinds a bridge permission may scope. `status` is the safe probe the
# web shell uses to answer "is this Mac actually here"; the compute kinds
# mirror the companion's job handlers (fuse/export share one impl upstream).
JOB_KINDS = ("status", "train", "fuse", "export", "serve")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_pairing_token() -> str:
    import secrets

    return "br1-" + secrets.token_urlsafe(24)


@dataclass
class HubSession:
    """One live companion socket."""

    companion_id: str
    permission_id: int
    user_id: int
    name: str
    scopes: tuple[str, ...]
    websocket: object  # fastapi.WebSocket, typed loosely to keep imports light
    connected_at: float = field(default_factory=time.time)
    last_event: dict | None = None


@dataclass
class JobRecord:
    job_id: str
    permission_id: int
    kind: str
    status: str = "sent"  # sent | awaiting_result | done | failed
    detail: str = ""
    started_at: float = field(default_factory=time.time)
    result: dict = field(default_factory=dict)


SESSIONS: dict[int, HubSession] = {}
JOBS: dict[str, JobRecord] = {}
_RESULTS: dict[str, asyncio.Future] = {}


async def register_session(
    websocket,
    *,
    permission_id: int,
    user_id: int,
    name: str,
    scopes: list[str],
) -> HubSession:
    """Adopt a paired companion socket. Any older session for the same
    permission is dropped first (a companion reconnect should win)."""
    old = SESSIONS.pop(permission_id, None)
    if old is not None:
        try:
            await old.websocket.close(code=4009, reason="superseded by a newer session")
        except Exception:  # already gone — fine
            pass
    session = HubSession(
        companion_id=f"perm-{permission_id}",
        permission_id=permission_id,
        user_id=user_id,
        name=name,
        scopes=tuple(scopes),
        websocket=websocket,
    )
    SESSIONS[permission_id] = session
    logger.info("companion paired: permission=%s name=%s scopes=%s", permission_id, name, scopes)
    return session


def unregister_session(permission_id: int, session: HubSession | None = None) -> None:
    cur = SESSIONS.get(permission_id)
    if session is None or cur is session:
        SESSIONS.pop(permission_id, None)
        logger.info("companion unpaired: permission=%s", permission_id)


async def disconnect_permission(permission_id: int) -> bool:
    """Force-close a companion's live socket (used on revoke/unpair)."""
    session = SESSIONS.pop(permission_id, None)
    if session is None:
        return False
    try:
        await session.websocket.close(code=4001, reason="bridge permission revoked")
    except Exception:
        pass
    return True


def scope_allowed(permission_id: int, kind: str) -> bool:
    session = SESSIONS.get(permission_id)
    return bool(session and kind in session.scopes)


async def send_job(permission_id: int, kind: str, payload: dict | None = None) -> JobRecord:
    """Dispatch one job frame to the paired companion. Raises LookupError if
    the companion is offline and PermissionError if the scope is not granted.
    The caller must have re-checked the *database* permission state too —
    scopes cached on the session reflect the pairing moment only."""
    session = SESSIONS.get(permission_id)
    if session is None:
        raise LookupError("no live companion for this bridge permission")
    if kind not in session.scopes:
        raise PermissionError(f"scope {kind!r} is not granted to this companion")

    job_id = uuid.uuid4().hex
    record = JobRecord(job_id=job_id, permission_id=permission_id, kind=kind)
    JOBS[job_id] = record
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()
    _RESULTS[job_id] = future
    frame = {"type": "job", "id": job_id, "kind": kind, "payload": payload or {}}
    await session.websocket.send_text(json.dumps(frame))
    record.status = "awaiting_result"
    return record


async def await_job(job_id: str, timeout_s: float = 120.0) -> JobRecord:
    record = JOBS.get(job_id)
    if record is None:
        raise LookupError(f"unknown job {job_id}")
    future = _RESULTS.get(job_id)
    if future is None:
        raise LookupError(f"no pending future for job {job_id}")
    try:
        msg = await asyncio.wait_for(future, timeout=timeout_s)
        record.status = "done" if msg.get("ok") else "failed"
        record.result = msg.get("data") or {}
        record.detail = str(record.result.get("detail", ""))[:500]
    except asyncio.TimeoutError:
        record.status = "failed"
        record.detail = f"companion did not answer within {int(timeout_s)}s"
    finally:
        _RESULTS.pop(job_id, None)
    return record


def ingest_message(permission_id: int, msg: dict) -> None:
    """Fold one inbound companion frame into hub state."""
    mtype = msg.get("type")
    session = SESSIONS.get(permission_id)
    if session is None:
        return
    if mtype == "event":
        session.last_event = {k: msg.get(k) for k in ("id", "stage", "detail")}
    elif mtype == "result":
        job_id = str(msg.get("id", ""))
        future = _RESULTS.get(job_id)
        if future is not None and not future.done():
            future.set_result(msg)
