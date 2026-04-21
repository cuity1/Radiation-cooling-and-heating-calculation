from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db.models import (
    CDK_TYPE_PERMANENT,
    CDK_TYPE_TEMPORARY,
    USER_TIER_PERMANENT_PRO,
    USER_TIER_PRO,
    CdkCode,
    User,
)
from ..db.session import SessionLocal
from ..dependencies.auth import (
    clear_session_cookie,
    get_current_user,
    require_user,
    set_session_cookie,
)
from ..services.auth_service import create_session, hash_password, verify_password


router = APIRouter(tags=["auth"])


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    tier: str
    pro_expires_at: datetime | None = None

    class Config:
        from_attributes = True


class RegisterRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class RedeemCdkRequest(BaseModel):
    code: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


@router.post("/auth/register", response_model=UserOut)
def register(req: RegisterRequest, db: Session = Depends(_get_db)) -> UserOut:
    existing = db.query(User).filter(User.username == req.username).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="username_taken")

    now = _now_utc()
    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        role="user",
        tier="normal",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user)


@router.post("/auth/login", response_model=UserOut)
def login(req: LoginRequest, response: Response, db: Session = Depends(_get_db)) -> UserOut:
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_credentials")

    sess = create_session(db, user)
    set_session_cookie(response, sess)
    return UserOut.model_validate(user)


@router.post("/auth/logout")
def logout(response: Response, db: Session = Depends(_get_db), current_user: User = Depends(get_current_user)) -> dict:
    # Remove all sessions for this user (simple implementation)
    from ..db.models import Session as DbSession

    db.query(DbSession).filter(DbSession.user_id == current_user.id).delete()
    db.commit()

    clear_session_cookie(response)
    return {"ok": True}


@router.get("/auth/me", response_model=UserOut)
def me(current_user: User = Depends(require_user)) -> UserOut:
    return UserOut.model_validate(current_user)


@router.post("/auth/redeem-cdk", response_model=UserOut)
def redeem_cdk(req: RedeemCdkRequest, db: Session = Depends(_get_db), current_user: User = Depends(require_user)) -> UserOut:
    # Validate CDK code
    if not req.code or not req.code.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_cdk")
    
    code = db.query(CdkCode).filter(CdkCode.code == req.code.strip()).first()
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_cdk")
    if code.redeemed_by_user_id is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cdk_already_used")

    # Reload user within this DB session to avoid mixing sessions
    db_user = db.query(User).filter(User.id == current_user.id).first()
    if not db_user:
        # Log this unexpected error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"User {current_user.id} not found in DB session during CDK redemption")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="user_not_found")

    now = _now_utc()

    # Decide target tier by key type
    kt = (code.key_type or "").strip().lower()
    if kt not in (CDK_TYPE_PERMANENT, CDK_TYPE_TEMPORARY):
        # Backward compatibility: treat unknown as permanent
        kt = CDK_TYPE_PERMANENT

    if kt == CDK_TYPE_PERMANENT:
        db_user.tier = USER_TIER_PERMANENT_PRO
        db_user.pro_expires_at = None
    else:
        # Temporary pro: 1 year from activation time
        db_user.tier = USER_TIER_PRO
        db_user.pro_expires_at = now + timedelta(days=365)

    db_user.updated_at = now

    code.redeemed_by_user_id = db_user.id
    code.redeemed_at = now

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to commit CDK redemption for user {db_user.id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="database_error")

    return UserOut.model_validate(db_user)


@router.post("/auth/change-password")
def change_password(
    req: ChangePasswordRequest,
    db: Session = Depends(_get_db),
    current_user: User = Depends(require_user),
) -> dict:
    db_user = db.query(User).filter(User.id == current_user.id).first()
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    if not verify_password(req.old_password, db_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="incorrect_old_password")

    if len(req.new_password) < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="password_too_short")

    db_user.password_hash = hash_password(req.new_password)
    db_user.updated_at = _now_utc()
    db.commit()
    return {"ok": True, "message": "password_changed"}

