import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

# S54: passlib retirement. CryptContext was a thin wrapper over the same
# `bcrypt` package we now call directly; passlib 1.7.4 is unmaintained and
# imports the stdlib `crypt` module (removed in 3.13), so its pin of
# bcrypt==4.0.1 held us off current bcrypt releases.
#
# Hash-compatibility with existing users rows (all `$2b$12$...`, produced by
# passlib's bcrypt handler): bcrypt.gensalt() defaults to the ident "2b" and
# round cost 12 — byte-for-byte the same shape passlib emitted, verified
# round-trip both directions (passlib hash -> bcrypt.checkpw, bcrypt hash ->
# passlib verify) before the swap. bcrypt.checkpw accepts any $2a/$2b/$2y hash.
#
# passlib's handler silently truncated passwords to bcrypt's 72-byte input
# cap; we keep that behavior explicitly so long-password hashes match the
# legacy rows AND we don't inherit bcrypt 4.1+'s stricter ValueError (nor the
# reverse: bcrypt 4.0.1 truncated silently, 5.x raises — pinning the truncate
# in our own code makes behavior stable across bcrypt versions). NULL bytes
# are rejected outright, like passlib did, so "abc\0def" can never hash as
# "abc".
_BCRYPT_MAX_INPUT_BYTES = 72


def _bcrypt_input(password: str) -> bytes:
    raw = password.encode("utf-8")
    if b"\x00" in raw:
        raise ValueError("password cannot contain NULL bytes")
    return raw[:_BCRYPT_MAX_INPUT_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_bcrypt_input(password), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            _bcrypt_input(plain_password), hashed_password.encode()
        )
    except ValueError:
        # Malformed/garbage stored hash: fail closed (login just fails)
        # instead of surfacing a 500. passlib raised UnknownHashError here.
        return False


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


# --- S8 (#11): team lanes over service tokens -------------------------------
# API_SERVICE_TOKENS is a comma-separated list of lane:token pairs, e.g.
#   API_SERVICE_TOKENS=tmux-hermes:s3cr3t-a,tmux-opencode:s3cr3t-b
# A request carrying `Authorization: Bearer <lane token>` acts as that lane:
# it gets a dedicated, auto-provisioned service user, so every existing
# per-user ownership filter keeps the lanes apart. Lanes may read, create
# datasets, and queue generation — they may NOT delete (enforced in the
# delete endpoints via the `lane_name` marker set below).

LANE_PERMISSIONS = ("read", "create", "queue_generation")


@dataclass(frozen=True)
class ServiceLane:
    name: str
    token: str


def parse_service_tokens() -> list[ServiceLane]:
    lanes: list[ServiceLane] = []
    for entry in settings.api_service_tokens.split(","):
        entry = entry.strip()
        if not entry or ":" not in entry:
            continue
        name, _, token = entry.partition(":")
        name, token = name.strip(), token.strip()
        if name and token:
            lanes.append(ServiceLane(name=name, token=token))
    return lanes


def resolve_service_lane(token: str) -> ServiceLane | None:
    # Constant-time comparison against every configured lane token; empty
    # configuration (default) disables lane auth entirely.
    match: ServiceLane | None = None
    for lane in parse_service_tokens():
        if hmac.compare_digest(lane.token.encode(), token.encode()):
            match = lane
    return match


def ensure_lane_user(db: Session, lane: ServiceLane) -> User:
    """Provision (idempotently) the service user backing a lane."""
    email = f"lane-{lane.name}@service.local"
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(
            email=email,
            hashed_password=hash_password("no-login-service-lane"),
            display_name=f"Lane {lane.name}",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    # Request-scoped marker (not persisted): tells delete endpoints to 403.
    user.lane_name = lane.name
    return user


def is_service_lane(user: User) -> bool:
    return getattr(user, "lane_name", None) is not None


def get_current_user(
    token: str | None = Depends(OAuth2PasswordBearer(tokenUrl="api/auth/login", auto_error=False)),
    db: Session = Depends(get_db)
) -> User:
    # Phase 6 slice 3: local mode bypass. Auto-provision a local user and skip JWT.
    if settings.local_mode:
        return ensure_local_user(db)

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # S8 (#11): a token that matches a configured lane acts as that lane.
    lane = resolve_service_lane(token)
    if lane is not None:
        return ensure_lane_user(db, lane)

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user


def ensure_local_user(db: Session) -> User:
    """Auto-provision a single local user for local_mode. Idempotent."""
    local_email = "local@llmtuner"
    user = db.query(User).filter(User.email == local_email).first()
    if user is None:
        user = User(
            email=local_email,
            hashed_password=hash_password("local"),
            display_name="Local User",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user