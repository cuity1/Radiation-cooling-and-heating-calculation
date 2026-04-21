from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .services.cleanup_service import cleanup_old_jobs
from .services.koppen_map_service import download_base_raster as _dl_raster
from .services.system_setting_service import is_maintenance_mode

from .db.models import Base, CDK_TYPE_PERMANENT, USER_TIER_PERMANENT_PRO, USER_TIER_PRO
from .db.session import engine
from .routes.auth import router as auth_router
from .routes.admin import router as admin_router
from .routes.config import router as config_router
from .routes.health import router as health_router
from .routes.jobs import router as jobs_router
from .routes.presets import router as presets_router
from .routes.tools import router as tools_router
from .routes.root import router as root_router
from .routes.uploads import router as uploads_router
from .routes.era5 import router as era5_router
from .routes.materials import router as materials_router
from .routes.glass import router as glass_router
from .routes.qa import router as qa_router
from .routes.ai import router as ai_router
from .settings import settings


logger = logging.getLogger(__name__)


def _sleep_until_next_run(hour: int, minute: int, tz: str) -> float:
    try:
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo(tz))
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            from datetime import timedelta

            target = target + timedelta(days=1)
        return (target - now).total_seconds()
    except Exception:
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            from datetime import timedelta

            target = target + timedelta(days=1)
        return (target - now).total_seconds()


def _start_cleanup_scheduler() -> None:
    if not settings.cleanup_enabled:
        logger.info("Scheduled cleanup disabled.")
        return

    def _loop() -> None:
        while True:
            delay = _sleep_until_next_run(
                settings.cleanup_cron_hour,
                settings.cleanup_cron_minute,
                settings.cleanup_timezone,
            )
            logger.info(f"Next cleanup run in {delay:.0f}s")
            time.sleep(max(delay, 1))
            try:
                cleanup_old_jobs(days=settings.cleanup_days)
            except Exception as e:
                logger.exception(f"Scheduled cleanup failed: {type(e).__name__}: {e}")
            time.sleep(1)

    t = threading.Thread(target=_loop, name="cleanup_scheduler", daemon=True)
    t.start()


def _bootstrap_base_raster() -> None:
    """Pre-download the Köppen-Geiger base raster on server startup."""
    try:
        result = _dl_raster()
        if result["is_fresh"]:
            logger.info(
                f"Base raster downloaded from GEE: {result['shape']}, "
                f"SHA-256={result['sha256'][:16]}"
            )
        else:
            logger.info(f"Base raster loaded from local cache: {result['shape']}")
    except Exception as e:
        logger.warning(
            f"Could not pre-download Köppen base raster (will retry on first request): {e}"
        )


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Ensure data directories exist (must happen before SQLite DB init)
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)

    # Bootstrap base raster on startup (downloads once from GEE if not cached)
    _bootstrap_base_raster()

    # Ensure DB schema exists
    Base.metadata.create_all(bind=engine)

    # Bootstrap initial admin user (admin / ustcadmin) and shared 'All' user if missing
    from sqlalchemy.orm import Session
    from .db.session import SessionLocal
    from .db.models import CdkCode, User
    from .services.auth_service import hash_password
    from datetime import datetime, timezone

    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        existing_admin = db.query(User).filter(User.username == "admin").first()
        if not existing_admin:
            admin_user = User(
                username="admin",
                password_hash=hash_password("ustcadmin"),
                role="admin",
                tier=USER_TIER_PERMANENT_PRO,
                pro_expires_at=None,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(admin_user)

        existing_all = db.query(User).filter(User.username == "All").first()
        if not existing_all:
            shared_user = User(
                username="All",
                password_hash=hash_password("admin"),
                role="user",
                tier=USER_TIER_PERMANENT_PRO,
                pro_expires_at=None,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            db.add(shared_user)

        # Data compatibility migration:
        # - legacy users with tier == 'pro' AND NO EXpiration were permanent; migrate them to 'permanent_pro'
        # - legacy cdks have NULL/empty key_type; set to 'permanent'
        legacy_users = (
            db.query(User)
            .filter(User.tier == USER_TIER_PRO)
            .filter(User.pro_expires_at.is_(None))
            .all()
        )
        for u in legacy_users:
            u.tier = USER_TIER_PERMANENT_PRO
            u.pro_expires_at = None
            u.updated_at = now

        legacy_cdks = (
            db.query(CdkCode)
            .filter((CdkCode.key_type.is_(None)) | (CdkCode.key_type == ""))
            .all()
        )
        for c in legacy_cdks:
            c.key_type = CDK_TYPE_PERMANENT

        # Migration: add 'remark' column to 'jobs' table if it doesn't exist.
        # SQLite's PRAGMA table_info does not raise on unknown columns.
        from sqlalchemy import text

        result = db.execute(text("PRAGMA table_info(jobs)"))
        existing_cols = {row[1] for row in result}
        if "remark" not in existing_cols:
            db.execute(text("ALTER TABLE jobs ADD COLUMN remark TEXT"))
            logger.info("Migration applied: added 'remark' column to 'jobs' table")

        db.commit()
    finally:
        db.close()

    app.include_router(root_router, prefix=settings.api_prefix)

    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(health_router, prefix=settings.api_prefix)
    app.include_router(jobs_router, prefix=settings.api_prefix)
    app.include_router(presets_router, prefix=settings.api_prefix)
    app.include_router(config_router, prefix=settings.api_prefix)
    app.include_router(tools_router, prefix=settings.api_prefix)
    app.include_router(uploads_router, prefix=settings.api_prefix)
    app.include_router(era5_router, prefix=settings.api_prefix)
    app.include_router(materials_router, prefix=settings.api_prefix)
    app.include_router(glass_router, prefix=settings.api_prefix)
    app.include_router(qa_router, prefix=settings.api_prefix)
    app.include_router(ai_router, prefix=settings.api_prefix)

    # Local-dev admin endpoints
    app.include_router(admin_router, prefix=settings.api_prefix)

    # Public maintenance check endpoint (no auth required)
    @app.get(settings.api_prefix + "/maintenance", include_in_schema=True)
    def check_maintenance() -> dict:
        return {"maintenance": is_maintenance_mode()}

    _start_cleanup_scheduler()

    return app


app = create_app()
