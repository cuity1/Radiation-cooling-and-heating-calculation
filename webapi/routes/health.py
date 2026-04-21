from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies.auth import require_user

router = APIRouter(tags=["health"], dependencies=[Depends(require_user)])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
