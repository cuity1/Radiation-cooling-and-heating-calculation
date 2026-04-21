from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pathlib import Path

from ..db.models import User
from ..dependencies.auth import require_user
from ..services.active_inputs_service import (
    clear_active_input_for_user,
    get_active_input_for_user,
    set_active_input_for_user,
)
from ..services.file_processing_service import process_upload
from ..settings import settings

router = APIRouter(tags=["uploads"], dependencies=[Depends(require_user)])


# Support a third optional kind "transmittance" for transparent materials.
UploadKind = Literal["reflectance", "emissivity", "transmittance"]


def _processed_dir(kind: UploadKind):
    return settings.uploads_dir / "processed" / kind


def _default_sample_path(kind: UploadKind):
    base = settings.data_dir.parent / "Radiation-cooling-and-heating-calculation" / "default"
    if kind == "reflectance":
        return base / "反射率.txt"
    if kind == "transmittance":
        return base / "透过率.txt"
    return base / "发射率.txt"


def _node(x):
    if not x:
        return None
    return {
        "id": x.id,
        "path": x.path,
        "original_name": x.original_name,
        "updated_at": x.updated_at,
    }


@router.get("/uploads/active")
def get_active(current_user: User = Depends(require_user)) -> dict[str, Any]:
    r = get_active_input_for_user(current_user.id, "reflectance")
    e = get_active_input_for_user(current_user.id, "emissivity")
    t = get_active_input_for_user(current_user.id, "transmittance")

    return {
        "reflectance": _node(r),
        "emissivity": _node(e),
        # Transmittance is optional (only needed for transparent materials),
        # so readiness for core calculations still depends on R + ε only.
        "transmittance": _node(t),
        "ready": bool(r and e),
    }


@router.post("/uploads/use-sample")
def use_sample(current_user: User = Depends(require_user)) -> dict[str, Any]:
    """Use built-in sample files as active defaults.

    Always runs through the same processing pipeline to generate processed files.
    """

    results: dict[str, Any] = {}
    for kind in ("reflectance", "emissivity", "transmittance"):
        p = _default_sample_path(kind)  # type: ignore[arg-type]
        if not p.exists():
            raise HTTPException(status_code=500, detail=f"sample file missing: {p}")
        content = p.read_bytes()
        res = process_upload(
            filename=p.name,
            content=content,
            output_type=kind,  # type: ignore[arg-type]
            processed_dir=_processed_dir(kind),
        )
        set_active_input_for_user(
            current_user.id,
            kind=kind,
            active_id=res.processed_id,
            path=str(res.processed_path),
            original_name=res.original_name,
        )
        results[kind] = {
            "processed_id": res.processed_id,
            "processed_path": str(res.processed_path),
            "original_name": res.original_name,
            "rows": res.rows,
            "tips": res.tips,
            "preview": res.preview,
        }

    r = get_active_input_for_user(current_user.id, "reflectance")
    e = get_active_input_for_user(current_user.id, "emissivity")
    t = get_active_input_for_user(current_user.id, "transmittance")

    return {
        "reflectance": results.get("reflectance"),
        "emissivity": results.get("emissivity"),
        "transmittance": results.get("transmittance"),
        "ready": bool(r and e),
    }


@router.post("/uploads/atm")
def upload_atm_preset(
    file: UploadFile = File(...),
    current_user: User = Depends(require_user),
) -> dict[str, Any]:
    """Upload a user-specific atmospheric DLL preset.

    Rules:
    - Files are stored under settings.atm_uploads_dir
    - Each file is renamed to "<stem>_<user_id>.dll"
    - For the same (user_id, stem), only one file is kept (overwritten on re-upload)
    - Different users can upload files with the same original name; they get different suffixed files.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing filename")

    original_name = file.filename
    ext = Path(original_name).suffix.lower()
    if ext != ".dll":
        raise HTTPException(status_code=400, detail="only .dll files are allowed for atmospheric presets")

    try:
        content = file.file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"failed to read file: {type(e).__name__}: {e}")

    if not content:
        raise HTTPException(status_code=400, detail="empty file")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file too large (max 10MB)")

    atm_dir = settings.atm_uploads_dir
    atm_dir.mkdir(parents=True, exist_ok=True)

    stem = Path(original_name).stem
    safe_stem = stem.replace(" ", "_")
    stored_name = f"{safe_stem}_{current_user.id}{ext}"
    stored_path = atm_dir / stored_name

    try:
        stored_path.write_bytes(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"failed_to_save_atm_preset: {type(e).__name__}: {e}")

    return {
        "original_name": original_name,
        "stored_name": stored_name,
        "path": str(stored_path),
    }


@router.post("/uploads/{kind}")
def upload(kind: UploadKind, file: UploadFile = File(...), current_user: User = Depends(require_user)) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing filename")

    try:
        content = file.file.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"failed to read file: {type(e).__name__}: {e}")

    # Limit to 10MB
    if content is None or len(content) == 0:
        raise HTTPException(status_code=400, detail="empty file")
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file too large (max 10MB)")

    try:
        res = process_upload(
            filename=file.filename,
            content=content,
            output_type=kind,
            processed_dir=_processed_dir(kind),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"upload_process_failed: {type(e).__name__}: {e}")

    set_active_input_for_user(
        current_user.id,
        kind=kind,
        active_id=res.processed_id,
        path=str(res.processed_path),
        original_name=res.original_name,
    )

    r = get_active_input_for_user(current_user.id, "reflectance")
    e = get_active_input_for_user(current_user.id, "emissivity")

    return {
        "kind": kind,
        "processed_id": res.processed_id,
        "processed_path": str(res.processed_path),
        "original_name": res.original_name,
        "rows": res.rows,
        "tips": res.tips,
        "preview": res.preview,
        "active_ready": bool(r and e),
    }


@router.delete("/uploads/{kind}")
def clear(kind: UploadKind, current_user: User = Depends(require_user)) -> dict[str, Any]:
    """Clear the active input of the specified kind for the current user."""
    clear_active_input_for_user(current_user.id, kind)
    r = get_active_input_for_user(current_user.id, "reflectance")
    e = get_active_input_for_user(current_user.id, "emissivity")
    return {
        "kind": kind,
        "cleared": True,
        "ready": bool(r and e),
    }
