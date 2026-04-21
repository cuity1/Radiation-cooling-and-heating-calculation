from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..dependencies.auth import require_user

from ..db.session import SessionLocal

router = APIRouter(tags=["debug"], dependencies=[Depends(require_user)])


@router.get("/debug/db")
def debug_db() -> dict:
    try:
        with SessionLocal() as db:
            rows = db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
            tables = [r[0] for r in rows]
            jobs_count = db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] if "jobs" in tables else None
            return {"tables": tables, "jobs_count": jobs_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"debug_db_failed: {type(e).__name__}: {e}")
