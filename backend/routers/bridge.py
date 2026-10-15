"""S25 (#28) — the opt-in bridge: explicit prompt, scoped + revocable
hardware access, and the hub endpoint the Mac companion dials into.

S26 (#29) adds the data-split surface: device artifact *bytes* never cross
to the host — only a metadata manifest does, via the companion's `artifacts`
frame, recorded in the device_artifacts ledger and readable/forgettable
through the REST endpoints below. Nothing in this module opens a device path.

REST surface (JWT-authenticated, per-user rows):
    POST /api/bridge/permissions              consent act; token returned once
    GET  /api/bridge/permissions              list mine (+ online flag)
    POST /api/bridge/permissions/{id}/revoke  revoke *and* drop the live socket
    POST /api/bridge/permissions/{id}/probe   scoped `status` round-trip
    GET  /api/bridge/artifacts                device-artifact metadata ledger (mine)
    DELETE /api/bridge/artifacts/{id}         forget one pointer (bytes never lived here)

WebSocket surface (pairing-token authenticated, no user JWT by design — the
token inside the hello frame is the consent proof, matching the protocol S24
shipped; the token never travels in a URL):
    WS /companion/ws    hello -> welcome, then event/result/artifacts frames
                        fold in (artifacts get an `artifacts_ack` back)

`fuse` and `export` share one companion implementation upstream; scoping
either is honest, both dispatch. Hub state lives per-process — see
core/bridge.py for the multi-worker caveat.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from core import bridge
from core.security import get_current_user
from database import get_db
from models.bridge import BridgePermission
from models.device_artifact import DeviceArtifact
from models.user import User
from schemas.bridge import ArtifactsFrame, BridgePermissionCreate

MAX_ACTIVE_PERMISSIONS = 20

router = APIRouter(prefix="/api/bridge", tags=["bridge"])
ws_router = APIRouter(tags=["bridge"])

PROBE_TIMEOUT_S = 20.0


def _serialize(perm: BridgePermission) -> dict:
    try:
        scopes = json.loads(perm.scopes or "[]")
    except json.JSONDecodeError:
        scopes = []
    try:
        caps = json.loads(perm.last_capabilities) if perm.last_capabilities else None
    except json.JSONDecodeError:
        caps = None
    return {
        "id": perm.id,
        "name": perm.name,
        "scopes": scopes,
        "status": perm.status,
        "online": perm.id in bridge.SESSIONS,
        "last_capabilities": caps,
        "last_seen_at": perm.last_seen_at,
        "created_at": perm.created_at,
        "revoked_at": perm.revoked_at,
    }


def _get_own_permission(db: Session, current_user: User, permission_id: int) -> BridgePermission:
    perm = (
        db.query(BridgePermission)
        .filter(BridgePermission.id == permission_id,
                BridgePermission.user_id == current_user.id)
        .first()
    )
    if perm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Bridge permission not found")
    return perm


@router.post("/permissions", status_code=status.HTTP_201_CREATED)
def create_permission(
    body: BridgePermissionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    active = (
        db.query(BridgePermission)
        .filter(BridgePermission.user_id == current_user.id,
                BridgePermission.status == "active")
        .count()
    )
    if active >= MAX_ACTIVE_PERMISSIONS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"too many active bridge permissions (max {MAX_ACTIVE_PERMISSIONS})",
        )

    token = bridge.new_pairing_token()
    perm = BridgePermission(
        user_id=current_user.id,
        name=body.name.strip(),
        scopes=json.dumps(body.scopes),
        token_hash=bridge.hash_token(token),
        status="active",
    )
    db.add(perm)
    db.commit()
    db.refresh(perm)
    out = _serialize(perm)
    out["token"] = token  # the ONLY time the plaintext leaves the server
    return out


@router.get("/permissions")
def list_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(BridgePermission)
        .filter(BridgePermission.user_id == current_user.id)
        .order_by(BridgePermission.id.desc())
        .all()
    )
    return [_serialize(p) for p in rows]


@router.post("/permissions/{permission_id}/revoke")
async def revoke_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    perm = _get_own_permission(db, current_user, permission_id)
    if perm.status != "revoked":
        perm.status = "revoked"
        perm.revoked_at = datetime.now(timezone.utc)
        db.commit()
    # Revocation is not "eventually": a live session dies on the spot.
    dropped = await bridge.disconnect_permission(perm.id)
    out = _serialize(perm)
    out["dropped_live_session"] = dropped
    return out


@router.post("/permissions/{permission_id}/probe")
async def probe_permission(
    permission_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Round-trip the companion's read-only `status` job. Scope is checked
    against the *database* row (not just the session cache), so a grant that
    was revoked and re-paired cannot sneak through a stale socket."""
    perm = _get_own_permission(db, current_user, permission_id)
    if perm.status != "active":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Bridge permission is revoked")
    try:
        scopes = json.loads(perm.scopes or "[]")
    except json.JSONDecodeError:
        scopes = []
    if "status" not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This bridge permission does not include the 'status' scope",
        )
    try:
        record = await bridge.send_job(perm.id, "status")
    except LookupError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="No live companion on this permission (is it running?)")
    finished = await bridge.await_job(record.job_id, timeout_s=PROBE_TIMEOUT_S)
    return {
        "ok": finished.status == "done",
        "status": finished.status,
        "data": finished.result,
        "detail": finished.detail,
    }


# ── S26 (#29): the device-artifact metadata ledger ─────────────────────────
#
# The split rule in one sentence: artifact BYTES stay on the Mac; the hosted
# DB keeps pointers only. These rows are written exclusively by a paired
# companion's `artifacts` frame (below) and are metadata-safe to list.
# Nothing in the hosted app opens, stats, or serves a device path.

def _artifact_out(row: DeviceArtifact, perm: BridgePermission | None) -> dict:
    return {
        "id": row.id,
        "permission_id": row.permission_id,
        "device_name": perm.name if perm else None,
        "device_online": bool(perm and row.permission_id in bridge.SESSIONS),
        "device_run_id": row.device_run_id,
        "kind": row.kind,
        "name": row.name,
        "base_model": row.base_model,
        "size_bytes": row.size_bytes,
        "sha256": row.sha256,
        "device_path": row.device_path,  # display-only pointer; never resolved host-side
        "first_reported_at": row.first_reported_at,
        "last_seen_at": row.last_seen_at,
    }


@router.get("/artifacts")
def list_device_artifacts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(DeviceArtifact)
        .filter(DeviceArtifact.user_id == current_user.id)
        .order_by(DeviceArtifact.id.desc())
        .all()
    )
    perms = {p.id: p for p in db.query(BridgePermission).all()}
    return [_artifact_out(r, perms.get(r.permission_id)) for r in rows]


@router.delete("/artifacts/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
def forget_device_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Forget the pointer. The bytes were never hosted, so there is nothing
    else to delete here — that is the point of the split."""
    row = (
        db.query(DeviceArtifact)
        .filter(DeviceArtifact.id == artifact_id,
                DeviceArtifact.user_id == current_user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Device artifact record not found")
    db.delete(row)
    db.commit()


def _store_artifacts_frame(db: Session, perm: BridgePermission, frame: ArtifactsFrame) -> int:
    """Upsert one manifest frame into the ledger, keyed by the consent that
    reported it: (permission, device_run_id, kind). Re-reports refresh
    metadata + last_seen instead of duplicating. Returns stored count."""
    now = datetime.now(timezone.utc)
    for item in frame.items:
        row = (
            db.query(DeviceArtifact)
            .filter(DeviceArtifact.permission_id == perm.id,
                    DeviceArtifact.device_run_id == item.device_run_id,
                    DeviceArtifact.kind == item.kind)
            .first()
        )
        if row is None:
            row = DeviceArtifact(
                user_id=perm.user_id,
                permission_id=perm.id,
                device_run_id=item.device_run_id,
                kind=item.kind,
            )
            db.add(row)
        row.name = item.name
        row.base_model = item.base_model
        row.size_bytes = item.size_bytes
        row.sha256 = item.sha256
        row.device_path = item.device_path
        row.last_seen_at = now
    db.commit()
    return len(frame.items)


@ws_router.websocket("/companion/ws")
async def companion_hub(websocket: WebSocket, db: Session = Depends(get_db)):
    """Hub side of the S24 dial-out protocol (llmtuner-companion/0).

    Uses the shared get_db dependency (overridable in tests) rather than a
    private SessionLocal; the session idles for the life of the socket,
    which is fine at single-Mac-per-permission scale.
    """
    await websocket.accept()
    permission_id: int | None = None
    perm: BridgePermission | None = None
    session: bridge.HubSession | None = None
    try:
        hello = json.loads(await websocket.receive_text())
        if (
            not isinstance(hello, dict)
            or hello.get("type") != "hello"
            or hello.get("protocol") != bridge.PROTOCOL
            or not hello.get("token")
        ):
            raise bridge.rejected("expected a hello frame for protocol " + bridge.PROTOCOL)

        perm = (
            db.query(BridgePermission)
            .filter(BridgePermission.token_hash == bridge.hash_token(str(hello["token"])))
            .first()
        )
        if perm is None or perm.status != "active":
            raise bridge.rejected("pairing token rejected — no active bridge permission matches")

        scopes = json.loads(perm.scopes or "[]")
        caps = hello.get("capabilities") or {}
        perm.last_capabilities = json.dumps(caps)[:2000]
        perm.last_seen_at = datetime.now(timezone.utc)
        db.commit()

        session = await bridge.register_session(
            websocket,
            permission_id=perm.id,
            user_id=perm.user_id,
            name=str(hello.get("name") or perm.name),
            scopes=scopes,
        )
        permission_id = perm.id

        await websocket.send_json({
            "type": "welcome",
            "companion_id": session.companion_id,
            "hub_protocol": bridge.PROTOCOL,
            "granted_scopes": list(session.scopes),
        })

        while True:
            msg = json.loads(await websocket.receive_text())
            if not isinstance(msg, dict):
                continue
            mtype = msg.get("type")
            if mtype in ("event", "result"):
                bridge.ingest_message(permission_id, msg)
            elif mtype == "artifacts" and perm is not None:
                # S26 (#29): metadata-only manifest of files that stay on the
                # device. Validate, upsert pointers, ack. Never touch paths.
                try:
                    frame = ArtifactsFrame.model_validate(msg)
                except ValidationError as err:
                    await websocket.send_json({
                        "type": "artifacts_ack", "ok": False,
                        "stored": 0, "detail": str(err)[:400],
                    })
                    continue
                stored = _store_artifacts_frame(db, perm, frame)
                await websocket.send_json({"type": "artifacts_ack", "ok": True,
                                          "stored": stored})
    except bridge.CompanionHelloRejected as err:
        try:
            await websocket.send_json({"type": "error", "detail": str(err)})
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        except Exception:
            pass
    except WebSocketDisconnect:
        pass
    except (json.JSONDecodeError, TypeError):
        try:
            await websocket.send_json({"type": "error", "detail": "non-JSON frame"})
            await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
        except Exception:
            pass
    finally:
        if permission_id is not None:
            bridge.unregister_session(permission_id, session)
