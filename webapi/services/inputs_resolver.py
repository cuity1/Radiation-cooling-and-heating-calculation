from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from ..db.models import User
from ..settings import settings
from .active_inputs_service import get_active_input_for_user, get_combined_reflectance_path_for_user
from .config_service import ensure_user_config_exists


def project_default_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "default"


def resolve_input_paths(*, require_material: bool, user_id: int) -> dict[str, str]:
    """Resolve file paths for computations.

    - If require_material=True, reflectance & emissivity are required.
      When active inputs are set, always use processed active files.
      If active inputs are not complete, raise 409 with a clear message.

    - If require_material=False, fall back to default material files.

    All other common files (config/spectrum/wavelength/atm_emissivity) are from default/ for now.
    """

    base = project_default_dir()
    user_config = ensure_user_config_exists(int(user_id))
    file_paths: dict[str, str] = {
        # Per-user editable config (WEBUI saves to data/user_configs/{user_id}.ini)
        "config": str(user_config),
        "spectrum": str(base / "AM1.5.xlsx"),
        "wavelength": str(base / "Wavelength.csv"),
        "atm_emissivity": str(base / "clear_sky.dll"),
    }

    # For calculations, always use the effective "reflectance" spectrum:
    # - pure reflectance if no transmittance is uploaded;
    # - combined (reflectance + transmittance) otherwise.
    refl_effective_path = get_combined_reflectance_path_for_user(int(user_id))
    refl_active = get_active_input_for_user(int(user_id), "reflectance")
    emis_active = get_active_input_for_user(int(user_id), "emissivity")
    trans_active = get_active_input_for_user(int(user_id), "transmittance")

    if refl_effective_path and emis_active:
        file_paths["reflectance"] = refl_effective_path
        file_paths["emissivity"] = emis_active.path
        # Pass original reflectance (for correct R_sol_reflectance_only output)
        if refl_active and Path(refl_active.path).exists():
            file_paths["reflectance_original"] = refl_active.path
        # Pass transmittance (for correct T_sol output and absorptance calculation)
        if trans_active and Path(trans_active.path).exists():
            file_paths["transmittance"] = trans_active.path
        return file_paths

    # Active not ready
    if require_material:
        raise HTTPException(
            status_code=409,
            detail=(
                "Active material files are not ready. "
                "Please upload and process BOTH reflectance and emissivity in /uploads first."
            ),
        )

    # Non-material computations can continue with defaults
    file_paths["reflectance"] = str(base / "use-高温.txt")
    file_paths["emissivity"] = str(base / "高温发射率.txt")
    return file_paths
