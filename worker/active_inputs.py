from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def _project_root() -> Path:
    # Radiation-cooling-and-heating-calculation/
    return Path(__file__).resolve().parents[1]


def _web_root() -> Path:
    # WEB/
    return _project_root().parents[0]


def _active_inputs_path() -> Path:
    """
    Single source of truth:
    Always use webapi.settings.settings.data_dir / active_inputs.json.
    This avoids accidentally reading a different data folder (which can look like "窜台").
    """
    from webapi.settings import settings  # lazy import to keep worker import order stable

    return settings.data_dir / "active_inputs.json"


def load_active_inputs() -> dict[str, Any]:
    p = _active_inputs_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _to_abs_existing(p: str | None) -> Path | None:
    if not isinstance(p, str):
        return None
    path = Path(p)
    if not path.is_absolute():
        # Make relative paths absolute relative to WEB/ root for legacy entries.
        path = _web_root() / path
    return path if path.exists() else None


def _combine_reflectance_and_transmittance(
    reflectance_path: Path,
    transmittance_path: Path,
    user_bucket: dict[str, Any],
) -> Path:
    """Local R+T combination for worker-side calculations only.

    - Align T(λ) onto R(λ) grid via interpolation.
    - y_combined = clip(R + T_interp, 0, 1).
    - Save to WEB/data/processed/reflect_plus_transmittance using a deterministic name
      based on active_id pairs, so repeated calls reuse the same file.
    """
    from webapi.settings import settings  # imported lazily to avoid circular issues

    r_node = user_bucket.get("reflectance") or {}
    t_node = user_bucket.get("transmittance") or {}
    r_id = r_node.get("active_id") or "unknown_r"
    t_id = t_node.get("active_id") or "unknown_t"

    out_dir = settings.uploads_dir / "processed" / "reflect_plus_transmittance"
    out_dir.mkdir(parents=True, exist_ok=True)
    combined_name = f"{r_id}__{t_id}.txt"
    out_path = out_dir / combined_name

    if out_path.exists():
        return out_path

    r_data = np.loadtxt(reflectance_path, dtype=float)
    t_data = np.loadtxt(transmittance_path, dtype=float)

    if r_data.ndim != 2 or r_data.shape[1] < 2:
        raise ValueError("reflectance file must have at least two columns")
    if t_data.ndim != 2 or t_data.shape[1] < 2:
        raise ValueError("transmittance file must have at least two columns")

    x_r = r_data[:, 0]
    y_r = r_data[:, 1]
    x_t = t_data[:, 0]
    y_t = t_data[:, 1]

    if x_r.size < 5 or x_t.size < 5:
        raise ValueError("Both reflectance and transmittance must have at least 5 rows")

    y_t_interp = np.interp(x_r, x_t, y_t, left=0.0, right=0.0)
    y_combined = np.clip(y_r + y_t_interp, 0.0, 1.0)
    combined = np.column_stack([x_r, y_combined])

    np.savetxt(out_path, combined, fmt="%.6f", delimiter=" ", encoding="utf-8")
    return out_path


def _resolve_paths_from_node(bucket: dict[str, Any]) -> dict[str, str] | None:
    r_node = bucket.get("reflectance")
    e_node = bucket.get("emissivity")
    if not isinstance(r_node, dict) or not isinstance(e_node, dict):
        return None

    r_path_abs = _to_abs_existing(r_node.get("path"))
    e_path_abs = _to_abs_existing(e_node.get("path"))
    if not (r_path_abs and e_path_abs):
        return None

    # Optional transmittance; if available, use combined (R+T) as effective reflectance.
    t_node = bucket.get("transmittance")
    t_path_abs = _to_abs_existing(t_node.get("path")) if isinstance(t_node, dict) else None

    if t_path_abs:
        try:
            r_effective = _combine_reflectance_and_transmittance(r_path_abs, t_path_abs, bucket)
        except Exception:
            # If combination fails for any reason, fall back to pure reflectance.
            r_effective = r_path_abs
    else:
        r_effective = r_path_abs

    return {"reflectance": str(r_effective), "emissivity": str(e_path_abs)}


def resolve_active_material_paths_for_user(user_id: int) -> dict[str, str] | None:
    """Return reflectance/emissivity paths for given user_id if ready, else None."""
    raw = load_active_inputs()
    users = raw.get("users")
    if not isinstance(users, dict):
        return None
    bucket = users.get(str(user_id))
    if not isinstance(bucket, dict):
        return None
    return _resolve_paths_from_node(bucket)


def resolve_active_material_paths() -> dict[str, str] | None:
    """Legacy global resolver (uses user_id = 0 bucket or root-level keys)."""
    raw = load_active_inputs()

    # Prefer per-user bucket with id 0 (used by webapi.services.active_inputs_service legacy helpers)
    users = raw.get("users")
    if isinstance(users, dict):
        bucket = users.get("0")
        if isinstance(bucket, dict):
            resolved = _resolve_paths_from_node(bucket)
            if resolved:
                return resolved

    # Fallback to legacy flat structure
    bucket = {
        "reflectance": raw.get("reflectance"),
        "emissivity": raw.get("emissivity"),
        "transmittance": raw.get("transmittance"),
    }
    return _resolve_paths_from_node(bucket)
