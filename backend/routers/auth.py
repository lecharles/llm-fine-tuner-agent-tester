from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.user import User
from schemas.user import PasswordChange, UserCreate, UserOut, UserUpdate
from schemas.token import Token
from core.rate_limit import signup_limiter, login_limiter
from core.onboarding import best_effort_seed
from core.security import (
    hash_password,
    is_service_lane,
    oauth2_scheme,
    resolve_service_lane,
    verify_password,
    create_access_token,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/config")
def auth_config():
    """Phase 6 slice 3: frontend uses this to detect local mode and skip login."""
    return {"local_mode": settings.local_mode}


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def signup(user_in: UserCreate, request: Request, db: Session = Depends(get_db)):
    # S15 (#17): shared-instance hardening. Attempts (not just successes)
    # count against a per-client-IP sliding window, so duplicate-email
    # probing can't burn the hour for free. The key is the TCP peer from
    # request.client (no X-Forwarded-For trust — nothing runs behind a
    # proxy today, and a spoofable header would defeat the limit).
    peer = request.client.host if request.client else "unknown-peer"
    allowed, retry_after = signup_limiter.allow(
        peer, settings.signup_rate_limit_per_hour, 3600.0
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many signup attempts from this address. Try again later.",
            headers={"Retry-After": str(int(retry_after))},
        )
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    user = User(
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        display_name=user_in.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    # S71: first-run onboarding. New human accounts get the 10-pair starter
    # demo dataset so Train is usable from minute one (see core/onboarding).
    # Best-effort by contract: signup has already committed; a seed failure
    # logs and rolls back only the seed, never the account.
    best_effort_seed(db, user)
    return user


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    # S44: credential-stuffing pass. Only FAILED attempts burn the window, so
    # a legitimate user is never locked out by someone else hammering the same
    # (IP, email); a success clears the key. Same no-XFF-trust rationale as
    # signup above — this box is not behind a proxy.
    peer = request.client.host if request.client else "unknown-peer"
    key = f"{peer}|{(form_data.username or '').lower()}"
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        allowed, retry_after = login_limiter.allow(
            key, settings.login_failed_limit_per_minute, 60.0
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Try again later.",
                headers={"Retry-After": str(int(retry_after))},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    login_limiter.clear(key)
    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "token_type": "bearer"}

from core.security import get_current_user
from models.user import User


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


# --- S64: the Settings page surface ---------------------------------------
# Account editing (display name, password rotation), an honest answer to
# "who am I and when does this token die" (GET /session), and the raw
# materials. No new tables, no migration: display_name and hashed_password
# already live on users; the session view decodes the CALLER's own token —
# a JWT is self-contained, so there is nothing to store per session.

@router.patch("/me", response_model=UserOut)
def update_current_user(
    body: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Email is deliberately NOT editable: it is the login key, and the
    # lane-*/local@ identities are synthetic (S8/S-phase6). Service lanes
    # get read/create/queue only (same S8 rule as the delete endpoints) —
    # renaming a lane's auto-provisioned user would silently rewrite the
    # identity every agent on that lane shares.
    if is_service_lane(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service lanes cannot change account settings",
        )
    current_user.display_name = body.display_name
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/password")
def change_password(
    body: PasswordChange,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rotate your own password. Stateless JWTs already issued keep working
    until their natural expiry (there is no server-side session to kill, by
    the same S16 decision that keeps log-in tokenless); that window is
    `access_token_expire_minutes` — 60 by default — and the response names
    it so the UI can say so honestly."""
    if is_service_lane(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Service lanes authenticate by token, not password",
        )
    # S44-shaped throttle: only FAILED current-password checks burn the
    # window, keyed per (peer, user) so another lane on the same box can't
    # lock you out of your own rotation. A success clears the key.
    peer = request.client.host if request.client else "unknown-peer"
    key = f"pwchange:{peer}|{current_user.id}"
    if not verify_password(body.current_password, current_user.hashed_password):
        allowed, retry_after = login_limiter.allow(
            key, settings.login_failed_limit_per_minute, 60.0
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed password attempts. Try again later.",
                headers={"Retry-After": str(int(retry_after))},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    login_limiter.clear(key)
    current_user.hashed_password = hash_password(body.new_password)
    db.commit()
    return {
        "changed": True,
        "jwt_ttl_minutes": settings.access_token_expire_minutes,
    }


@router.get("/session")
def session_info(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """What is this connection actually running on? Three auth shapes
    exist (user JWT, service lane token, local-mode bypass) and the
    Settings page refuses to guess: we report the real one. Never echoes
    the token itself — exp/sub/algorithm are claims the caller already
    holds; the signature stays on the server side."""
    out = {
        "mode": "other",
        "subject": None,
        "algorithm": settings.jwt_algorithm,
        "expires_at": None,
        "expires_in_seconds": None,
        "jwt_ttl_minutes": settings.access_token_expire_minutes,
        "local_mode": settings.local_mode,
        "lane": getattr(current_user, "lane_name", None),
    }

    # Lane wins over decode: lane tokens are opaque by configuration.
    lane = resolve_service_lane(token)
    if lane is not None:
        out["mode"] = "service_lane"
        out["subject"] = f"lane-{lane.name}"
        return out

    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        payload = None
    if payload is not None and payload.get("sub") is not None:
        out["mode"] = "jwt"
        out["subject"] = str(payload["sub"])
        exp = payload.get("exp")
        if exp is not None:
            out["expires_at"] = datetime.fromtimestamp(exp, tz=timezone.utc).isoformat()
            out["expires_in_seconds"] = int(exp - datetime.now(timezone.utc).timestamp())
        return out

    if settings.local_mode:
        out["mode"] = "local"
        out["subject"] = str(current_user.id)
    return out