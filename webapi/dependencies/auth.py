from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ..db.models import USER_TIER_NORMAL, USER_TIER_PRO, Session as DbSession, User
from ..db.session import SessionLocal
from ..services.auth_service import create_session, destroy_session, get_session

SESSION_COOKIE_NAME = "session_id"


def _now_utc() -> datetime:
    """Return naive UTC datetime to match SQLite storage."""
    return datetime.utcnow()


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    db: Session = Depends(get_db),
    session_id: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> User:
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")

    sess: DbSession | None = get_session(db, session_id)
    if not sess:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired session")

    user = db.get(User, sess.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found or inactive")

    # Auto-downgrade expired time-limited Pro users
    if user.tier == USER_TIER_PRO and user.pro_expires_at is not None and user.pro_expires_at <= _now_utc():
        user.tier = USER_TIER_NORMAL
        user.pro_expires_at = None
        user.updated_at = _now_utc()
        db.commit()
        db.refresh(user)

    return user


def require_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin required")
    return current_user


def set_session_cookie(response: Response, session: DbSession) -> None:
    # Cookie lifetime: align roughly with server-side session lifetime.
    # Avoid naive/aware datetime subtraction issues by using a fixed TTL.
    # 180 days in seconds (keep in sync with SESSION_LIFETIME_HOURS).
    max_age = 180 * 24 * 60 * 60
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session.id,
        httponly=True,
        secure=False,  # can be toggled via settings in future
        samesite="lax",
        max_age=max_age,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")

