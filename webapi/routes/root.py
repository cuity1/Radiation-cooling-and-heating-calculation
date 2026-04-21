from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse

router = APIRouter(tags=["root"])

# Manual file path (relative to webapi parent = project root)
_MANUAL_PATH = Path(__file__).resolve().parents[2] / "docs" / "用户手册.md"


@router.get("/")
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@router.get("/user-manual")
def get_user_manual() -> JSONResponse:
    """Serve the user manual markdown file with KaTeX math support."""
    if not _MANUAL_PATH.exists():
        raise HTTPException(status_code=404, detail="用户手册文件未找到")
    content = _MANUAL_PATH.read_text(encoding="utf-8")
    return JSONResponse({"content": content})
