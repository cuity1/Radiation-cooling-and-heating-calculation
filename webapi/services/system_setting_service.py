from __future__ import annotations

from datetime import datetime, timezone

from ..db.models import SystemSetting
from ..db.session import SessionLocal

MAINTENANCE_MODE_KEY = "maintenance_mode"


def is_maintenance_mode() -> bool:
    with SessionLocal() as db:
        row = db.get(SystemSetting, MAINTENANCE_MODE_KEY)
        return row is not None and row.value == "true"


def set_maintenance_mode(enabled: bool) -> None:
    now = datetime.now(timezone.utc)
    with SessionLocal() as db:
        row = db.get(SystemSetting, MAINTENANCE_MODE_KEY)
        if enabled:
            if row is None:
                row = SystemSetting(key=MAINTENANCE_MODE_KEY, value="true", updated_at=now)
                db.add(row)
            else:
                row.value = "true"
                row.updated_at = now
        else:
            if row is not None:
                db.delete(row)
        db.commit()
