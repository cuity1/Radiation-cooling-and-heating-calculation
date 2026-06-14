from __future__ import annotations

from app.models import SimulationConfig
from app.simulation.solver_limits import MEEP_MAX_SCAN_POINTS, RCWA_MAX_SCAN_POINTS


SCAN_DEFAULTS: dict[str, tuple[int, int]] = {
    "auto": (160, 80),
    "mie": (160, 80),
    "smart_proxy": (160, 80),
    "tmatrix": (100, 50),
    "rcwa": (12, 8),
    "grcwa": (12, 8),
    "meep": (12, 6),
}


def apply_solver_scan_defaults(config: SimulationConfig) -> SimulationConfig:
    payload = config.model_dump(mode="json")
    solver = _effective_solver_for_defaults(config)
    wavelength_points, diameter_points = SCAN_DEFAULTS[solver]
    payload["scan"]["wavelength_points"] = wavelength_points
    payload["scan"]["diameter_points"] = diameter_points
    return SimulationConfig.model_validate(payload)


def apply_missing_solver_scan_defaults(config: SimulationConfig) -> SimulationConfig:
    payload = config.model_dump(mode="json")
    solver = _effective_solver_for_defaults(config)
    wavelength_points, diameter_points = SCAN_DEFAULTS[solver]
    explicit_scan_fields = config.scan.model_fields_set
    if "wavelength_points" not in explicit_scan_fields:
        payload["scan"]["wavelength_points"] = wavelength_points
    if "diameter_points" not in explicit_scan_fields:
        payload["scan"]["diameter_points"] = diameter_points
    return SimulationConfig.model_validate(payload)


def normalize_scan_for_solver_limits(config: SimulationConfig) -> SimulationConfig:
    payload = config.model_dump(mode="json")
    solver = _effective_solver_for_defaults(config)
    max_points = None
    if solver in {"rcwa", "grcwa"}:
        max_points = RCWA_MAX_SCAN_POINTS
    elif solver == "meep":
        max_points = MEEP_MAX_SCAN_POINTS
        payload["simulation"]["runtime"] = min(float(payload["simulation"]["runtime"]), 60.0)
        payload["simulation"]["resolution"] = min(int(payload["simulation"]["resolution"]), 24)
        payload["simulation"]["meep_workers"] = min(int(payload["simulation"].get("meep_workers", 1)), 1)
    if max_points is not None:
        wavelength_points, diameter_points = _clamp_scan_product(
            int(payload["scan"]["wavelength_points"]),
            int(payload["scan"]["diameter_points"]),
            max_points,
        )
        payload["scan"]["wavelength_points"] = wavelength_points
        payload["scan"]["diameter_points"] = diameter_points
    return SimulationConfig.model_validate(payload)


def _effective_solver_for_defaults(config: SimulationConfig) -> str:
    solver = config.simulation.solver
    if solver != "auto":
        return solver
    if config.array.enabled:
        return "grcwa"
    if config.substrate.type != "none":
        return "smart_proxy"
    if config.geometry.type == "sphere":
        return "mie"
    if config.geometry.type in {"cylinder", "shell"}:
        return "tmatrix"
    return "smart_proxy"


def _clamp_scan_product(wavelength_points: int, diameter_points: int, max_points: int) -> tuple[int, int]:
    while wavelength_points * diameter_points > max_points:
        if wavelength_points >= diameter_points and wavelength_points > 2:
            wavelength_points -= 1
        elif diameter_points > 2:
            diameter_points -= 1
        else:
            break
    return wavelength_points, diameter_points
