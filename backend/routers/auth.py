from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.user import User
from schemas.user import UserCreate, UserOut
from schemas.token import Token
from core.rate_limit import signup_limiter
from core.security import hash_password, verify_password, create_access_token

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
    return user


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    access_token = create_access_token(subject=str(user.id))
    return {"access_token": access_token, "token_type": "bearer"}

from core.security import get_current_user
from models.user import User


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user