from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..db.models import Session as DbSession, User

SESSION_ID_BYTES = 32
SESSION_LIFETIME_HOURS = 180 * 24  # 180 days


def _now_utc() -> datetime:
    """
    Return a naive UTC datetime.

    SQLite typically stores naive datetimes; using naive UTC here avoids
    offset-naive vs offset-aware comparison issues when loading from DB.
    """
    return datetime.utcnow()


def hash_password(plain: str) -> str:
    """
    Very simple password hash helper.

    NOTE: For production, consider using passlib[bcrypt] or similar.
    """
    import hashlib

    # random 16-byte salt
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + plain).encode("utf-8")).hexdigest()
    return f"sha256${salt}${h}"


def verify_password(plain: str, stored: str) -> bool:
    import hashlib

    try:
        algo, salt, h = stored.split("$", 2)
    except ValueError:
        return False

    if algo != "sha256":
        return False

    new_h = hashlib.sha256((salt + plain).encode("utf-8")).hexdigest()
    return secrets.compare_digest(new_h, h)


def create_session(db: Session, user: User) -> DbSession:
    """Create a new session row for the given user."""
    session_id = secrets.token_urlsafe(SESSION_ID_BYTES)
    now = _now_utc()
    expires_at = now + timedelta(hours=SESSION_LIFETIME_HOURS)

    db_sess = DbSession(id=session_id, user_id=user.id, created_at=now, expires_at=expires_at)
    db.add(db_sess)
    db.commit()
    db.refresh(db_sess)
    return db_sess


def get_session(db: Session, session_id: str) -> Optional[DbSession]:
    if not session_id:
        return None
    sess = db.get(DbSession, session_id)
    if not sess:
        return None
    if sess.expires_at <= _now_utc():
        # expired: clean up
        db.delete(sess)
        db.commit()
        return None
    return sess


def destroy_session(db: Session, session_id: str) -> None:
    if not session_id:
        return
    sess = db.get(DbSession, session_id)
    if not sess:
        return
    db.delete(sess)
    db.commit()

