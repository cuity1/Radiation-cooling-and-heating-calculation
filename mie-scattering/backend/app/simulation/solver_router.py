from __future__ import annotations

from dataclasses import dataclass
from importlib.util import find_spec

from app.models import SimulationConfig
from app.simulation.materials import resolve_medium_material, resolve_particle_material, resolve_shell_core_material
from app.simulation.solver_limits import (
    MEEP_HIGH_RESOLUTION,
    MEEP_HIGH_RESOLUTION_SCAN_POINTS,
    MEEP_MAX_ARRAY_PARTICLES,
    MEEP_MAX_SCAN_POINTS,
    MEEP_MAX_WORKERS,
    RCWA_MAX_SCAN_POINTS,
)


class SolverUnavailableError(RuntimeError):
    """Raised when a requested physics backend is not installed or not integrated."""


@dataclass(frozen=True)
class SolverSelection:
    requested_solver: str
    solver: str
    calculation_method: str
    reason: str
    notes: tuple[str, ...]
    blocking: bool = False

    def model_dump(self) -> dict[str, object]:
        return {
            "requested_solver": self.requested_solver,
            "solver": self.solver,
            "calculation_method": self.calculation_method,
            "reason": self.reason,
            "notes": list(self.notes),
            "blocking": self.blocking,
        }


def select_solver(config: SimulationConfig) -> SolverSelection:
    """Choose only installed and integrated solvers."""
    requested = config.simulation.solver
    if requested != "auto":
        return _explicit_selection(config, requested)

    if _is_exact_mie_scope(config):
        return SolverSelection(
            requested_solver=requested,
            solver="mie",
            calculation_method="miepython_homogeneous_sphere",
            reason="Homogeneous isolated sphere in a lossless uniform medium has an exact Mie solution.",
            notes=("Selected miepython for the analytical Maxwell solution.",),
        )

    tmatrix_reason = _tmatrix_blocking_reason(config, include_install_check=True)
    if tmatrix_reason is None:
        return SolverSelection(
            requested_solver=requested,
            solver="tmatrix",
            calculation_method=_tmatrix_method(config),
            reason="Selected installed treams T-matrix backend for this isolated particle model.",
            notes=("treams is installed and integrated in the active solver environment.",),
        )

    grcwa_reason = _rcwa_blocking_reason(config, "grcwa", include_install_check=True)
    if grcwa_reason is None:
        return SolverSelection(
            requested_solver=requested,
            solver="grcwa",
            calculation_method="grcwa_periodic_unit_cell",
            reason="Selected installed grcwa RCWA backend for an enabled periodic array model.",
            notes=("grcwa is installed and integrated for periodic-unit-cell calculations.",),
        )
    if config.array.enabled:
        return _blocking(
            requested,
            "grcwa_periodic_unit_cell",
            f"Auto solver could not run the installed grcwa backend: {grcwa_reason}",
            notes=(
                "Enabled arrays are routed to RCWA/grcwa periodic-unit-cell solvers by default.",
                f"grcwa cannot accept this configuration: {grcwa_reason}",
                f"Reduce wavelength_points * diameter_points to {RCWA_MAX_SCAN_POINTS} or lower.",
                "Select simulation.solver='meep' explicitly only if a finite-cluster FDTD calculation is intended.",
            ),
        )

    return SolverSelection(
        requested_solver=requested,
        solver="smart_proxy",
        calculation_method="analytical_mie_equivalent_sphere",
        reason="Auto selected the low-resource analytical proxy because no lighter integrated exact adapter accepts this model.",
        notes=(
            "Meep FDTD is intentionally not used by auto because it is resource intensive.",
            f"T-matrix cannot accept this configuration: {tmatrix_reason}",
            f"grcwa cannot accept this configuration: {grcwa_reason}",
            "Select simulation.solver='meep' explicitly only when a finite-domain FDTD calculation is intended.",
        ),
    )


def require_integrated_solver(config: SimulationConfig, solver: str) -> None:
    selection = _explicit_selection(config, solver)
    if selection.blocking:
        raise SolverUnavailableError(selection.reason)


def recommend_solver(config: SimulationConfig) -> str:
    """Return the preferred installed solver family for the current runtime."""
    if _is_exact_mie_scope(config):
        return "mie"
    if config.array.enabled:
        return "grcwa"
    if _tmatrix_blocking_reason(config, include_install_check=False) is None:
        return "tmatrix"
    return "smart_proxy"


def _explicit_selection(config: SimulationConfig, requested: str) -> SolverSelection:
    if requested == "mie":
        if not _is_mie_scope(config):
            return _blocking(
                requested,
                "miepython_homogeneous_sphere",
                "Mie solver is only valid for isolated homogeneous spheres without substrate or array.",
                ("Change geometry to sphere without substrate/array, or select a geometry-appropriate full-wave backend.",),
            )
        if find_spec("miepython") is None:
            return _blocking(requested, "miepython_homogeneous_sphere", "miepython is not installed.", ("Install miepython in the backend environment.",))
        return SolverSelection(
            requested_solver=requested,
            solver="mie",
            calculation_method="miepython_homogeneous_sphere",
            reason="Explicit mie solver selected for a homogeneous isolated sphere.",
            notes=("Uses miepython.efficiencies.",),
        )

    if requested == "smart_proxy":
        return SolverSelection(
            requested_solver=requested,
            solver="smart_proxy",
            calculation_method="analytical_mie_equivalent_sphere",
            reason="Explicit analytical proxy selected.",
            notes=("Equivalent-volume sphere Mie approximation; not shape-, substrate-, or array-exact.",),
        )

    if requested == "tmatrix":
        blocking_reason = _tmatrix_blocking_reason(config, include_install_check=True)
        if blocking_reason is not None:
            return _blocking(requested, _tmatrix_method(config), blocking_reason, ("treams T-matrix is only accepted for the geometries covered by this adapter.",))
        return SolverSelection(
            requested_solver=requested,
            solver="tmatrix",
            calculation_method=_tmatrix_method(config),
            reason="Explicit treams T-matrix backend selected.",
            notes=("Uses treams TMatrix/TMatrixC cross-section APIs.",),
        )

    if requested in {"rcwa", "grcwa"}:
        blocking_reason = _rcwa_blocking_reason(config, requested, include_install_check=True)
        if blocking_reason is not None:
            return _blocking(requested, f"{requested}_periodic_unit_cell", blocking_reason, ("RCWA is only accepted for enabled periodic-array configurations within the scan guardrails.",))
        package_name = "rcwa" if requested == "rcwa" else "grcwa"
        return SolverSelection(
            requested_solver=requested,
            solver=requested,
            calculation_method=f"{requested}_periodic_unit_cell",
            reason=f"Explicit {package_name} RCWA backend selected.",
            notes=("Uses a periodic unit cell with gridded particle cross sections.",),
        )

    if requested == "meep":
        blocking_reason = _meep_blocking_reason(config, include_install_check=True)
        if blocking_reason is not None:
            return _blocking(
                requested,
                "meep_fdtd_flux_box",
                blocking_reason,
                ("Meep is only accepted when the configured model fits the implemented FDTD workflow and server limits.",),
            )
        notes = ["Requires pymeep and uses the configured resolution, runtime, padding, and PML settings."]
        if config.array.enabled:
            notes.append("Array-enabled Meep runs are finite-cluster FDTD, not Bloch-periodic RCWA.")
        return SolverSelection(
            requested_solver=requested,
            solver="meep",
            calculation_method="meep_fdtd_flux_box",
            reason="Explicit Meep FDTD backend selected.",
            notes=tuple(notes),
        )

    return _blocking(requested, "unknown", f"Unknown or inactive solver '{requested}'.", ("Active solvers are auto, mie, tmatrix, rcwa, grcwa, meep, and smart_proxy.",))


def _recommended_method(solver: str) -> str:
    methods = {
        "mie": "miepython_homogeneous_sphere",
        "tmatrix": "treams_tmatrix",
        "rcwa": "rcwa_periodic_unit_cell",
        "grcwa": "grcwa_periodic_unit_cell",
        "meep": "meep_fdtd_flux_box",
        "smart_proxy": "analytical_mie_equivalent_sphere",
    }
    return methods.get(solver, "unknown")


def _blocking(requested: str, calculation_method: str, reason: str, notes: tuple[str, ...]) -> SolverSelection:
    return SolverSelection(
        requested_solver=requested,
        solver=requested,
        calculation_method=calculation_method,
        reason=reason,
        notes=notes,
        blocking=True,
    )


def _is_exact_mie_scope(config: SimulationConfig) -> bool:
    return (
        config.geometry.type == "sphere"
        and not config.array.enabled
        and config.substrate.type == "none"
        and abs(config.material.medium_n_imag) <= 1e-12
    )


def _is_mie_scope(config: SimulationConfig) -> bool:
    return (
        config.geometry.type == "sphere"
        and not config.array.enabled
        and config.substrate.type == "none"
        and abs(config.material.medium_n_imag) <= 1e-12
    )


def _tmatrix_method(config: SimulationConfig) -> str:
    if config.geometry.type == "sphere":
        return "treams_spherical_tmatrix"
    return "treams_cylindrical_tmatrix"


def _tmatrix_blocking_reason(config: SimulationConfig, *, include_install_check: bool) -> str | None:
    if include_install_check and find_spec("treams") is None:
        return "treams is not installed in the Python environment that is running the backend."
    if config.array.enabled:
        return "T-matrix adapter is limited to isolated particles; use rcwa or grcwa for enabled periodic arrays."
    if config.substrate.type != "none":
        return "T-matrix adapter does not include substrate coupling."
    if config.material.medium_n_imag > 0:
        return "T-matrix cross-section averages require a non-absorbing embedding medium."
    if config.geometry.type not in {"sphere", "cylinder", "shell"}:
        return "T-matrix adapter currently supports sphere, cylinder, and shell geometries."
    return None


def _rcwa_blocking_reason(config: SimulationConfig, solver: str, *, include_install_check: bool) -> str | None:
    package_name = "rcwa" if solver == "rcwa" else "grcwa"
    if include_install_check and find_spec(package_name) is None:
        return f"{package_name} is not installed in the Python environment that is running the backend."
    if not config.array.enabled:
        return "RCWA requires array.enabled=true so the model has a periodic unit cell."
    total_points = config.scan.wavelength_points * config.scan.diameter_points
    if total_points > RCWA_MAX_SCAN_POINTS:
        return f"RCWA scans are limited to {RCWA_MAX_SCAN_POINTS} wavelength-diameter points per job."
    if config.material.medium_n_imag > 0:
        return "RCWA adapter currently requires a non-absorbing incident medium."
    return None


def _meep_blocking_reason(config: SimulationConfig, *, include_install_check: bool) -> str | None:
    total_points = config.scan.wavelength_points * config.scan.diameter_points
    if total_points > MEEP_MAX_SCAN_POINTS:
        return f"Meep scan is limited to {MEEP_MAX_SCAN_POINTS} wavelength-diameter points per job."
    if config.simulation.resolution > MEEP_HIGH_RESOLUTION and total_points > MEEP_HIGH_RESOLUTION_SCAN_POINTS:
        return f"Meep scans above resolution {MEEP_HIGH_RESOLUTION} are limited to {MEEP_HIGH_RESOLUTION_SCAN_POINTS} wavelength-diameter points per job."
    if config.array.enabled and config.array.count_x * config.array.count_y > MEEP_MAX_ARRAY_PARTICLES:
        return f"Meep finite-array jobs are limited to {MEEP_MAX_ARRAY_PARTICLES} particles per job."
    if config.simulation.meep_workers > MEEP_MAX_WORKERS:
        return f"Meep worker count is limited to {MEEP_MAX_WORKERS}."
    if _has_lossy_meep_material(config):
        return "Meep backend currently supports only lossless constant-index particle, shell-core, and ambient media."
    if config.substrate.type != "none":
        return "Meep substrate normalization is not implemented yet."
    if include_install_check and find_spec("meep") is None:
        return "Meep is not installed in the Python environment that is running the backend. Start the backend in the mie-solvers conda environment."
    return None


def _has_lossy_meep_material(config: SimulationConfig) -> bool:
    particle = resolve_particle_material(config.material)
    medium = resolve_medium_material(config.material)
    shell_core = resolve_shell_core_material(config.material)
    return (
        abs(particle.refractive_index.imag) > 1e-12
        or abs(medium.refractive_index.imag) > 1e-12
        or (config.geometry.type == "shell" and abs(shell_core.refractive_index.imag) > 1e-12)
    )


def _meep_adjustment_note(config: SimulationConfig) -> str:
    total_points = config.scan.wavelength_points * config.scan.diameter_points
    if total_points > MEEP_MAX_SCAN_POINTS:
        return f"Reduce wavelength_points * diameter_points to {MEEP_MAX_SCAN_POINTS} or lower."
    if config.simulation.resolution > MEEP_HIGH_RESOLUTION and total_points > MEEP_HIGH_RESOLUTION_SCAN_POINTS:
        return f"For resolution above {MEEP_HIGH_RESOLUTION}, reduce scan points to {MEEP_HIGH_RESOLUTION_SCAN_POINTS} or lower."
    if config.array.enabled and config.array.count_x * config.array.count_y > MEEP_MAX_ARRAY_PARTICLES:
        return f"Reduce finite array count_x * count_y to {MEEP_MAX_ARRAY_PARTICLES} or lower."
    if config.substrate.type != "none":
        return "Set substrate.type='none' until substrate-normalized Meep runs are enabled."
    if _has_lossy_meep_material(config):
        return "Use lossless constant-index particle/core/ambient settings, or add explicit dispersive Meep material models."
    return "The current configuration is outside the installed solver set."
