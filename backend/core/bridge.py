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
- S50 adds the *durable* dispatch path (`dispatch_job`) the train handoff
  uses: the HTTP side returns a job id at once, the companion's progress
  `event` frames (with loss chunks in `data.points`) fold into the job
  record, and the web shell polls. Jobs awaiting a companion that vanished
  are failed on the spot, never left dangling to timeout.
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
    # S50: long-running jobs (train on a Mac takes up to the
    # companion's 2h deadline) stream `event` frames back while they run.
    # The record keeps a bounded view of them so the web shell can poll
    # status + the loss curve without holding a request open.
    user_id: int = 0
    summary: str = ""
    events: list[dict] = field(default_factory=list)
    losses: list[dict] = field(default_factory=list)


SESSIONS: dict[int, HubSession] = {}
JOBS: dict[str, JobRecord] = {}
_RESULTS: dict[str, asyncio.Future] = {}

# S50 bounds. Events/losses are display state for the web poller, not an
# audit ledger — ring-buffer them so a chatty companion cannot grow the
# per-process hub without limit. A train run emits at most `iters` loss
# points (capped at 5000 by the schema), so 5500 keeps any honest curve.
MAX_TRACKED_JOBS = 200
JOB_EVENTS_KEPT = 300
JOB_LOSSES_KEPT = 5500

# Strong refs to the background "await the companion result" tasks, so the
# event loop cannot GC them mid-flight (asyncio docs' standing warning).
_BG_TASKS: set[asyncio.Task] = set()


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
        # The old socket's in-flight jobs die with it: settle them now rather
        # than letting them dangle until the dispatch timeout.
        _fail_pending_jobs(permission_id, "superseded by a newer companion session")
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
        _fail_pending_jobs(permission_id, "companion disconnected mid-job")
        logger.info("companion unpaired: permission=%s", permission_id)


async def disconnect_permission(permission_id: int) -> bool:
    """Force-close a companion's live socket (used on revoke/unpair)."""
    session = SESSIONS.pop(permission_id, None)
    if session is None:
        return False
    _fail_pending_jobs(permission_id, "bridge permission revoked mid-job")
    try:
        await session.websocket.close(code=4001, reason="bridge permission revoked")
    except Exception:
        pass
    return True


def scope_allowed(permission_id: int, kind: str) -> bool:
    session = SESSIONS.get(permission_id)
    return bool(session and kind in session.scopes)


async def send_job(
    permission_id: int,
    kind: str,
    payload: dict | None = None,
    *,
    summary: str = "",
) -> JobRecord:
    """Dispatch one job frame to the paired companion. Raises LookupError if
    the companion is offline and PermissionError if the scope is not granted.
    The caller must have re-checked the *database* permission state too —
    scopes cached on the session reflect the pairing moment only."""
    session = SESSIONS.get(permission_id)
    if session is None:
        raise LookupError("no live companion for this bridge permission")
    if kind not in session.scopes:
        raise PermissionError(f"scope {kind!r} is not granted to this companion")

    _prune_jobs()
    job_id = uuid.uuid4().hex
    record = JobRecord(
        job_id=job_id, permission_id=permission_id, kind=kind,
        user_id=session.user_id, summary=summary,
    )
    JOBS[job_id] = record
    loop = asyncio.get_running_loop()
    future: asyncio.Future = loop.create_future()
    _RESULTS[job_id] = future
    frame = {"type": "job", "id": job_id, "kind": kind, "payload": payload or {}}
    await session.websocket.send_text(json.dumps(frame))
    record.status = "awaiting_result"
    return record


def _prune_jobs() -> None:
    """Keep the in-memory job table bounded: drop the oldest terminal jobs
    when it grows past MAX_TRACKED_JOBS. Running jobs are never dropped."""
    overflow = len(JOBS) - MAX_TRACKED_JOBS
    if overflow <= 0:
        return
    terminal = sorted(
        (r for r in JOBS.values() if r.status in ("done", "failed")),
        key=lambda r: r.started_at,
    )
    for record in terminal[:overflow]:
        JOBS.pop(record.job_id, None)


def _fail_pending_jobs(permission_id: int, detail: str) -> None:
    """S50: when a companion's socket goes away, every job awaiting *it*
    must end now — resolve the open futures with a synthesized failed result
    so background awaiters settle instead of idling to their timeout."""
    for record in JOBS.values():
        if record.permission_id != permission_id or record.status != "awaiting_result":
            continue
        future = _RESULTS.get(record.job_id)
        if future is not None and not future.done():
            future.set_result({"ok": False, "data": {"detail": detail}})


async def dispatch_job(
    permission_id: int,
    kind: str,
    payload: dict | None = None,
    *,
    summary: str = "",
    timeout_s: float,
) -> JobRecord:
    """S50 fire-and-forget dispatch: send the job and hand the result-wait
    to a background task, so the HTTP caller gets the job id immediately and
    polls `get_job_view` instead of holding a request open for hours.
    (probe keeps the synchronous send_job + await_job pair; nothing is lost.)"""
    record = await send_job(permission_id, kind, payload, summary=summary)

    async def _finish() -> None:
        try:
            await await_job(record.job_id, timeout_s=timeout_s)
        except (LookupError, asyncio.CancelledError):
            pass  # job pruned or task cancelled — record already terminal-ish
        except Exception as err:  # never let a companion answer crash the loop
            record.status = "failed"
            record.detail = f"hub could not process the result: {err}"[:500]
            _RESULTS.pop(record.job_id, None)

    task = asyncio.create_task(_finish())
    _BG_TASKS.add(task)
    task.add_done_callback(_BG_TASKS.discard)
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
        # S50: a train companion also streams loss — event frames may carry
        # {"data": {"points": [{"step", "loss"}, ...]}} chunks. Fold them
        # into the owning job's bounded buffers so the web poller can render
        # a live curve. Unknown/dropped job ids stay harmless (ring drop).
        record = JOBS.get(str(msg.get("id", "")))
        if record is not None and record.status not in ("done", "failed"):
            event = {
                "stage": str(msg.get("stage", ""))[:80],
                "detail": str(msg.get("detail", ""))[:300],
                "ts": time.time(),
            }
            record.events.append(event)
            if len(record.events) > JOB_EVENTS_KEPT:
                del record.events[:-JOB_EVENTS_KEPT]
            data = msg.get("data")
            points = data.get("points") if isinstance(data, dict) else None
            if isinstance(points, list):
                clean = [
                    p for p in points
                    if isinstance(p, dict)
                    and isinstance(p.get("step"), (int, float))
                    and isinstance(p.get("loss"), (int, float))
                ]
                record.losses.extend(clean)
                if len(record.losses) > JOB_LOSSES_KEPT:
                    del record.losses[:-JOB_LOSSES_KEPT]
    elif mtype == "result":
        job_id = str(msg.get("id", ""))
        future = _RESULTS.get(job_id)
        if future is not None and not future.done():
            future.set_result(msg)


def get_job_view(record: JobRecord) -> dict:
    """Serialize a JobRecord for the web poller (GET /api/bridge/jobs/...)."""
    return {
        "job_id": record.job_id,
        "permission_id": record.permission_id,
        "kind": record.kind,
        "status": record.status,
        "detail": record.detail,
        "summary": record.summary,
        "started_at": record.started_at,
        "elapsed_s": round(time.time() - record.started_at, 1),
        "online": record.permission_id in SESSIONS,
        "events": record.events[-30:],
        "losses": record.losses,
        "result": record.result if record.status in ("done", "failed") else {},
    }


def list_jobs_for_user(user_id: int, limit: int = 20) -> list[JobRecord]:
    """This user's recent jobs, newest first (in-memory hub state)."""
    rows = [r for r in JOBS.values() if r.user_id == user_id]
    rows.sort(key=lambda r: r.started_at, reverse=True)
    return rows[:limit]
