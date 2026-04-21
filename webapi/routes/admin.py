from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from redis import Redis
from rq import Queue

from ..db.models import (
    CDK_TYPE_PERMANENT,
    CDK_TYPE_TEMPORARY,
    USER_TIER_NORMAL,
    USER_TIER_PERMANENT_PRO,
    USER_TIER_PRO,
    CdkCode,
    Job,
    Session as DbSession,
    User,
)
from ..db.session import SessionLocal
from ..dependencies.auth import require_admin
from ..services.active_inputs_service import delete_active_inputs_for_user
from ..services.auth_service import hash_password
from ..services.config_service import user_config_path
from ..services.system_setting_service import is_maintenance_mode, set_maintenance_mode
from ..settings import settings

router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin)])


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _get_redis() -> Redis:
    return Redis.from_url(settings.redis_url)


def _get_queue() -> Queue:
    return Queue(name=settings.rq_queue_name, connection=_get_redis())


class UpdateUserTierRequest(BaseModel):
    tier: str
    # Only used when tier == 'pro'. If omitted, defaults to now+365 days.
    pro_expires_at: datetime | None = None


@router.post("/admin/jobs/cleanup")
def cleanup_jobs(status: str = "queued") -> dict:
    """Cleanup jobs by status.

    - Marks DB jobs as cancelled.
    - Optionally clears the RQ queue (safe for Windows sync mode).

    This endpoint is intended for local development.
    """
    allowed = {"queued", "started", "failed", "succeeded", "cancelled"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"invalid status: {status}")

    now = _now_utc()
    updated = 0

    with SessionLocal() as db:
        rows = db.query(Job).filter(Job.status == status).all()
        for j in rows:
            j.status = "cancelled"
            j.updated_at = now
            updated += 1
        db.commit()

    # Also clear queue in Redis to remove stale queued jobs
    try:
        q = _get_queue()
        q.empty()
    except Exception:
        # If redis/queue not available, ignore.
        pass

    return {"cancelled": updated}


@router.get("/admin/jobs/active")
def list_active_jobs() -> list[dict]:
    """
    List queued and started jobs for admin monitoring.
    """
    with SessionLocal() as db:
        rows = (
            db.query(Job, User)
            .outerjoin(User, Job.user_id == User.id)
            .filter(Job.status.in_(("queued", "started")))
            .order_by(Job.created_at.asc())
            .all()
        )
        out: list[dict] = []
        for job, user in rows:
            out.append(
                {
                    "id": job.id,
                    "type": job.type,
                    "status": job.status,
                    "created_at": job.created_at,
                    "updated_at": job.updated_at,
                    "user_id": user.id if user else None,
                    "username": user.username if user else None,
                }
            )
        return out


@router.post("/admin/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    """
    Mark a job as cancelled. For queued jobs also try to remove from RQ queue.
    """
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job_not_found")

        job.status = "cancelled"
        job.updated_at = _now_utc()
        db.commit()

    # Best-effort removal from RQ queue (if async mode is used)
    try:
        q = _get_queue()
        for j in list(q.jobs):
            if getattr(j, "id", None) == job_id or getattr(j, "args", [None])[0] == job_id:
                q.remove(j)
    except Exception:
        pass

    return {"cancelled": True}


@router.get("/admin/users")
def list_users() -> list[dict]:
    with SessionLocal() as db:
        rows = db.query(User).order_by(User.created_at.asc()).all()
        out: list[dict] = []
        for u in rows:
            out.append(
                {
                    "id": u.id,
                    "username": u.username,
                    "role": u.role,
                    "tier": u.tier,
                    "pro_expires_at": u.pro_expires_at,
                    "is_active": u.is_active,
                    "created_at": u.created_at,
                }
            )
        return out


@router.post("/admin/users/{user_id}/tier")
def update_user_tier(user_id: int, req: UpdateUserTierRequest) -> dict:
    desired = (req.tier or "").strip().lower()
    allowed = {USER_TIER_NORMAL, USER_TIER_PRO, USER_TIER_PERMANENT_PRO}
    if desired not in allowed:
        raise HTTPException(status_code=400, detail="invalid_tier")

    now = _now_utc()

    with SessionLocal() as db:
        user = db.get(User, int(user_id))
        if not user:
            raise HTTPException(status_code=404, detail="user_not_found")

        if desired == USER_TIER_NORMAL:
            user.tier = USER_TIER_NORMAL
            user.pro_expires_at = None
        elif desired == USER_TIER_PERMANENT_PRO:
            user.tier = USER_TIER_PERMANENT_PRO
            user.pro_expires_at = None
        else:
            user.tier = USER_TIER_PRO
            user.pro_expires_at = req.pro_expires_at or (now + timedelta(days=365))

        user.updated_at = now
        db.commit()

    return {"ok": True}


@router.post("/admin/users/check-expired")
def check_expired_users() -> dict:
    now = _now_utc()
    downgraded = 0

    with SessionLocal() as db:
        rows = (
            db.query(User)
            .filter(User.tier == USER_TIER_PRO)
            .filter(User.pro_expires_at.isnot(None))
            .filter(User.pro_expires_at <= now)
            .all()
        )
        for u in rows:
            u.tier = USER_TIER_NORMAL
            u.pro_expires_at = None
            u.updated_at = now
            downgraded += 1
        db.commit()

    return {"downgraded": downgraded}


@router.post("/admin/users/{user_id}/reset-password")
def reset_password(user_id: int, new_password: str) -> dict:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="user_not_found")
        user.password_hash = hash_password(new_password)
        user.updated_at = _now_utc()
        db.commit()
    return {"ok": True}


@router.delete("/admin/users/{user_id}")
def delete_user(user_id: int, current_user: User = Depends(require_admin)) -> dict:
    if int(user_id) == int(current_user.id):
        raise HTTPException(status_code=400, detail="cannot_delete_self")

    with SessionLocal() as db:
        u = db.get(User, int(user_id))
        if not u:
            raise HTTPException(status_code=404, detail="user_not_found")
        if u.username == "All":
            raise HTTPException(status_code=400, detail="cannot_delete_shared_user_all")

        db.query(DbSession).filter(DbSession.user_id == u.id).delete()
        db.query(Job).filter(Job.user_id == u.id).update({"user_id": None})

        db.delete(u)
        db.commit()

    try:
        p = user_config_path(int(user_id))
        if p.exists() and p.is_file():
            p.unlink(missing_ok=True)
    except Exception:
        pass

    try:
        delete_active_inputs_for_user(int(user_id))
    except Exception:
        pass

    return {"deleted": True}


@router.post("/admin/generate-cdk")
def generate_cdk(count: int = 1, key_type: str = CDK_TYPE_PERMANENT) -> dict:
    import secrets

    if count <= 0 or count > 1000:
        raise HTTPException(status_code=400, detail="invalid_count")

    kt = (key_type or "").strip().lower()
    if kt not in (CDK_TYPE_PERMANENT, CDK_TYPE_TEMPORARY):
        raise HTTPException(status_code=400, detail="invalid_key_type")

    now = _now_utc()
    codes: list[str] = []
    with SessionLocal() as db:
        for _ in range(count):
            code = secrets.token_urlsafe(16)
            row = CdkCode(
                code=code,
                key_type=kt,
                created_by_user_id=None,
                redeemed_by_user_id=None,
                created_at=now,
                redeemed_at=None,
            )
            db.add(row)
            codes.append(code)
        db.commit()
    return {"codes": codes}


@router.get("/admin/cdks")
def list_cdks(limit: int = 200) -> list[dict]:
    if limit <= 0 or limit > 1000:
        limit = 200
    with SessionLocal() as db:
        rows = db.query(CdkCode).order_by(CdkCode.created_at.desc()).limit(limit).all()
        out: list[dict] = []
        for c in rows:
            out.append(
                {
                    "id": c.id,
                    "code": c.code,
                    "key_type": c.key_type,
                    "created_at": c.created_at,
                    "redeemed_at": c.redeemed_at,
                    "redeemed_by_user_id": c.redeemed_by_user_id,
                }
            )
        return out


@router.delete("/admin/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    import shutil

    from ..services.storage_service import job_dir

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job_not_found")
        db.delete(job)
        db.commit()

    base = job_dir(job_id)
    try:
        if base.exists():
            if base.is_dir():
                shutil.rmtree(base)
            else:
                base.unlink()
    except Exception:
        pass

    return {"deleted": True}


class MaintenanceModeRequest(BaseModel):
    enabled: bool


@router.get("/admin/maintenance")
def get_maintenance_mode() -> dict:
    return {"enabled": is_maintenance_mode()}


@router.post("/admin/maintenance")
def update_maintenance_mode(req: MaintenanceModeRequest) -> dict:
    set_maintenance_mode(req.enabled)
    return {"enabled": req.enabled}
