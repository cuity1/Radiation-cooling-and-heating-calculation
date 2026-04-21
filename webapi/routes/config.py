from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..db.models import User
from ..dependencies.auth import require_user
from ..services.config_service import (
    ensure_user_config_exists,
    load_config_raw,
    parse_config,
    restore_user_config,
    save_user_config,
)

router = APIRouter(tags=["config"], dependencies=[Depends(require_user)])


class ConfigSaveRequest(BaseModel):
    content: str


@router.get("/config")
def get_config(current_user: User = Depends(require_user)) -> dict:
    path = ensure_user_config_exists(current_user.id)
    return {
        "user": {"id": current_user.id, "username": current_user.username},
        "path": str(path),
        "content": load_config_raw(path),
        "parsed": parse_config(path),
    }


@router.put("/config")
def put_config(req: ConfigSaveRequest, current_user: User = Depends(require_user)) -> dict:
    path = save_user_config(req.content, current_user.id)
    return {
        "user": {"id": current_user.id, "username": current_user.username},
        "path": str(path),
        "content": load_config_raw(path),
        "parsed": parse_config(path),
    }


@router.post("/config/restore")
def restore_config(current_user: User = Depends(require_user)) -> dict:
    path = restore_user_config(current_user.id)
    return {
        "user": {"id": current_user.id, "username": current_user.username},
        "path": str(path),
        "content": load_config_raw(path),
        "parsed": parse_config(path),
    }
