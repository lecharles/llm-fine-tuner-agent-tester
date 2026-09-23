from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.security import (
    LANE_PERMISSIONS,
    get_current_user,
    is_service_lane,
    parse_service_tokens,
)
from database import get_db
from models.user import User

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status")
def lane_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """S8 (#11): lane identity endpoint for tmux/agent clients.

    Returns who the caller is (lane name for service tokens, email for user
    JWTs) plus the caller's permissions. Never returns token material.
    """
    lane = getattr(current_user, "lane_name", None)
    return {
        "authenticated": True,
        "lane": lane or "user",
        "identity": f"lane-{lane}@service.local" if is_service_lane(current_user) else current_user.email,
        "permissions": list(LANE_PERMISSIONS) if is_service_lane(current_user) else ["read", "create", "queue_generation", "delete"],
        "service_lanes_configured": len(parse_service_tokens()),
        "server_time_utc": datetime.now(timezone.utc).isoformat(),
    }
