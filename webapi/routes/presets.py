from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from ..dependencies.auth import require_user
from ..settings import settings

router = APIRouter(tags=["presets"], dependencies=[Depends(require_user)])


@router.get("/presets/atm")
def list_atm_presets() -> dict[str, list[str]]:
    """List available atmospheric transmittance presets (DLL) from default/."""
    base_dir = Path(__file__).resolve().parents[2]
    default_dir = base_dir / "default"

    dlls: list[str] = []
    if default_dir.exists():
        dlls = sorted([p.name for p in default_dir.glob("*.dll")])

    return {"items": dlls}


@router.get("/presets/material")
def list_material_presets() -> dict[str, dict[str, str]]:
    """Return the MVP material preset mapping used by Option-A default mode."""
    # Keep this stable and explicit.
    return {
        "items": {
            "reflectance": "use-高温.txt",
            "emissivity": "高温发射率.txt",
        }
    }


@router.get("/presets/spectrum")
def list_spectrum_presets() -> dict[str, dict[str, str]]:
    return {"items": {"spectrum": "AM1.5.xlsx", "wavelength": "Wavelength.csv", "config": "config.ini"}}
