from __future__ import annotations

import csv
import json
from math import pi
from pathlib import Path
from typing import Callable

import h5py
import matplotlib
import numpy as np

from app.models import SimulationConfig
from app.simulation.geometry import geometry_metrics, geometry_summary
from app.simulation.integrated_solvers import run_integrated_efficiency_grid
from app.simulation.materials import material_summary, resolve_medium_material, resolve_particle_material, substrate_index
from app.simulation.mie import mie_efficiencies, miepython_efficiencies
from app.simulation.solver_router import SolverUnavailableError, select_solver


matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


ProgressCallback = Callable[[float, str], None]


def run_fast_fdtd_scan(config: SimulationConfig, result_dir: Path, progress_callback: ProgressCallback | None = None) -> dict[str, object]:
    """Run the analytical Mie-equivalent-sphere backend and write a study package."""
    result_dir.mkdir(parents=True, exist_ok=True)
    if progress_callback is None:
        progress_callback = lambda _progress, _status="running": None

    selection = select_solver(config)
    if selection.blocking:
        raise SolverUnavailableError(selection.reason)

    if selection.solver == "meep":
        from app.simulation.meep_solver import run_meep_fdtd_scan

        return run_meep_fdtd_scan(config, result_dir, progress_callback=progress_callback)

    _write_json(result_dir / "config.json", config.model_dump(mode="json"))
    progress_callback(0.06, "running")

    wavelengths = np.linspace(config.scan.wavelength_min, config.scan.wavelength_max, config.scan.wavelength_points)
    diameters = np.linspace(config.scan.diameter_min, config.scan.diameter_max, config.scan.diameter_points)
    qsca, qabs, qext, asymmetry = _efficiency_components(config, wavelengths, diameters, selection.solver)
    albedo = np.divide(qsca, qext, out=np.zeros_like(qsca), where=qext > 0)
    progress_callback(0.36, "running")

    _write_heatmap_csv(result_dir / "heatmap.csv", wavelengths, diameters, qsca)
    _write_grid_csv(result_dir / "efficiencies.csv", wavelengths, diameters, qsca, qabs, qext, albedo, asymmetry)
    cross_sections = _cross_section_rows(config, wavelengths, diameters, qsca, qabs, qext)
    _write_rows_csv(result_dir / "cross_sections.csv", cross_sections)
    progress_callback(0.5, "running")

    peaks = _peak_rows(wavelengths, diameters, qsca)
    _write_rows_csv(result_dir / "peaks.csv", peaks)

    spectrum_diameter = min(max(config.scan.spectrum_diameter, config.scan.diameter_min), config.scan.diameter_max)
    spectrum_components = _efficiency_components(config, wavelengths, np.array([spectrum_diameter]), selection.solver)
    spectrum_qsca, spectrum_qabs, spectrum_qext, spectrum_asymmetry = [component[0] for component in spectrum_components]
    spectrum_albedo = np.divide(spectrum_qsca, spectrum_qext, out=np.zeros_like(spectrum_qsca), where=spectrum_qext > 0)
    spectrum_reference_area = geometry_metrics(config.geometry, config.array, spectrum_diameter).reference_area
    spectrum_cross_sections = spectrum_qsca * spectrum_reference_area
    spectrum_rows = [
        {
            "wavelength_um": float(wavelength),
            "diameter_um": float(spectrum_diameter),
            "scattering_efficiency": float(qs),
            "absorption_efficiency": float(qa),
            "extinction_efficiency": float(qe),
            "albedo": float(ab),
            "asymmetry_g": float(g),
            "mie_reference_area_um2": float(spectrum_reference_area),
            "scattering_cross_section_um2": float(cross_section),
        }
        for wavelength, qs, qa, qe, ab, g, cross_section in zip(
            wavelengths,
            spectrum_qsca,
            spectrum_qabs,
            spectrum_qext,
            spectrum_albedo,
            spectrum_asymmetry,
            spectrum_cross_sections,
        )
    ]
    _write_rows_csv(result_dir / "spectrum.csv", spectrum_rows)
    progress_callback(0.62, "running")

    field = _near_field(config, spectrum_diameter)
    with h5py.File(result_dir / "fields.h5", "w") as h5:
        h5.create_dataset("x_um", data=field["x"])
        h5.create_dataset("y_um", data=field["y"])
        h5.create_dataset("ez_abs", data=field["ez_abs"])
        h5.attrs["diameter_um"] = spectrum_diameter
        h5.attrs["field_quantity"] = "synthetic_normalized_near_field_proxy"
        h5.attrs["field_warning"] = "This field is a visualization proxy, not an electromagnetic FDTD field."
        h5.attrs["wavelength_um"] = float(wavelengths[np.argmax(spectrum_qsca)])
    progress_callback(0.72, "running")

    substrate_n = substrate_index(config.substrate.type, config.substrate.metal_index_real, config.substrate.metal_index_imag)
    geometry_payload = geometry_summary(config.geometry, config.array, spectrum_diameter)
    material_payload = material_summary(config.material, config.substrate.type, substrate_n)
    warnings = _calculation_warnings(config, selection)
    _write_json(result_dir / "geometry_summary.json", geometry_payload)
    _write_json(result_dir / "material_summary.json", material_payload)

    _plot_heatmap(result_dir / "fig_heatmap.png", wavelengths, diameters, qsca)
    _plot_spectrum(result_dir / "fig_spectrum.png", spectrum_rows)
    _plot_efficiency_components(result_dir / "fig_efficiency_components.png", spectrum_rows)
    _plot_peak_map(result_dir / "fig_peak_map.png", peaks)
    _plot_field(result_dir / "fig_field_xy.png", field)
    progress_callback(0.9, "running")

    peak_index = np.unravel_index(np.argmax(qsca), qsca.shape)
    spectrum_peak_index = int(np.argmax(spectrum_qsca))
    outputs = [
        "config.json",
        "spectrum.csv",
        "heatmap.csv",
        "efficiencies.csv",
        "cross_sections.csv",
        "peaks.csv",
        "fields.h5",
        "geometry_summary.json",
        "material_summary.json",
        "summary.json",
        "fig_heatmap.png",
        "fig_spectrum.png",
        "fig_efficiency_components.png",
        "fig_peak_map.png",
        "fig_field_xy.png",
    ]
    summary = {
        "requested_solver": config.simulation.solver,
        "solver": selection.solver,
        "solver_selection": selection.model_dump(),
        "solver_note": _solver_note(selection),
        "calculation_method": selection.calculation_method,
        "accuracy_warnings": warnings,
        "geometry": config.geometry.type,
        "material": material_payload["particle"],
        "medium": material_payload["medium"],
        "substrate": config.substrate.type,
        "array_enabled": config.array.enabled,
        "wavelength_range_um": [float(wavelengths[0]), float(wavelengths[-1])],
        "diameter_range_um": [float(diameters[0]), float(diameters[-1])],
        "heatmap_shape": [int(qsca.shape[0]), int(qsca.shape[1])],
        "global_peak": {
            "diameter_um": float(diameters[peak_index[0]]),
            "wavelength_um": float(wavelengths[peak_index[1]]),
            "scattering_efficiency": float(qsca[peak_index]),
            "absorption_efficiency": float(qabs[peak_index]),
            "extinction_efficiency": float(qext[peak_index]),
            "asymmetry_g": float(asymmetry[peak_index]),
        },
        "spectrum_peak": {
            "diameter_um": float(spectrum_diameter),
            "wavelength_um": float(wavelengths[spectrum_peak_index]),
            "scattering_efficiency": float(spectrum_qsca[spectrum_peak_index]),
            "absorption_efficiency": float(spectrum_qabs[spectrum_peak_index]),
            "extinction_efficiency": float(spectrum_qext[spectrum_peak_index]),
            "asymmetry_g": float(spectrum_asymmetry[spectrum_peak_index]),
            "cross_section_um2": float(spectrum_cross_sections[spectrum_peak_index]),
        },
        "geometry_summary": geometry_payload,
        "outputs": outputs,
    }
    _write_json(result_dir / "summary.json", summary)
    return summary


def _efficiency_components(config: SimulationConfig, wavelengths: np.ndarray, diameters: np.ndarray, solver: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if solver in {"tmatrix", "rcwa", "grcwa"}:
        grid = run_integrated_efficiency_grid(config, wavelengths, diameters, solver)
        return grid.qsca, grid.qabs, grid.qext, grid.asymmetry

    particle = resolve_particle_material(config.material)
    medium = resolve_medium_material(config.material)
    n_particle = particle.refractive_index
    n_medium = medium.refractive_index
    qsca = np.zeros((len(diameters), len(wavelengths)), dtype=float)
    qabs = np.zeros_like(qsca)
    qext = np.zeros_like(qsca)
    asymmetry = np.zeros_like(qsca)

    for d_index, diameter in enumerate(diameters):
        metrics = geometry_metrics(config.geometry, config.array, float(diameter))
        for w_index, wavelength in enumerate(wavelengths):
            if solver == "mie":
                result = miepython_efficiencies(metrics.effective_diameter, float(wavelength), n_particle, n_medium)
            else:
                result = mie_efficiencies(metrics.equivalent_sphere_diameter, float(wavelength), n_particle, n_medium)
            qsca[d_index, w_index] = result.qsca
            qabs[d_index, w_index] = result.qabs
            qext[d_index, w_index] = result.qext
            asymmetry[d_index, w_index] = result.g
    return qsca, qabs, qext, asymmetry


def _cross_section_rows(
    config: SimulationConfig,
    wavelengths: np.ndarray,
    diameters: np.ndarray,
    qsca: np.ndarray,
    qabs: np.ndarray,
    qext: np.ndarray,
) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for d_index, diameter in enumerate(diameters):
        metrics = geometry_metrics(config.geometry, config.array, float(diameter))
        area = metrics.reference_area
        for w_index, wavelength in enumerate(wavelengths):
            rows.append(
                {
                    "wavelength_um": float(wavelength),
                    "diameter_um": float(diameter),
                    "mie_reference_area_um2": float(area),
                    "Csca_um2": float(qsca[d_index, w_index] * area),
                    "Cabs_um2": float(qabs[d_index, w_index] * area),
                    "Cext_um2": float(qext[d_index, w_index] * area),
                }
            )
    return rows


def _peak_rows(wavelengths: np.ndarray, diameters: np.ndarray, qsca: np.ndarray) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for diameter, values in zip(diameters, qsca):
        peak_index = int(np.argmax(values))
        peak_value = float(values[peak_index])
        half_max = peak_value / 2.0
        above = np.where(values >= half_max)[0]
        fwhm = float(wavelengths[above[-1]] - wavelengths[above[0]]) if above.size > 1 else 0.0
        rows.append(
            {
                "diameter_um": float(diameter),
                "peak_wavelength_um": float(wavelengths[peak_index]),
                "peak_scattering_efficiency": peak_value,
                "fwhm_um": fwhm,
            }
        )
    return rows


def _near_field(config: SimulationConfig, diameter: float) -> dict[str, np.ndarray]:
    metrics = geometry_metrics(config.geometry, config.array, diameter)
    span = max(3.0, max(metrics.width, metrics.depth) * 4.5)
    points = 180
    x = np.linspace(-span / 2.0, span / 2.0, points)
    y = np.linspace(-span / 2.0, span / 2.0, points)
    xx, yy = np.meshgrid(x, y)
    scaled_radius = np.sqrt((xx / max(metrics.width / 2.0, 1e-9)) ** 2 + (yy / max(metrics.depth / 2.0, 1e-9)) ** 2)
    theta = np.arctan2(yy, xx)

    resonance = np.exp(-((scaled_radius - 1.0) / 0.28) ** 2)
    standing = 0.55 + 0.45 * np.cos(2.8 * pi * xx / max(metrics.effective_diameter, 0.2)) ** 2
    angular = 1.0 + 0.25 * np.cos(2.0 * theta) * metrics.anisotropy
    substrate_shadow = 1.0
    if config.substrate.type != "none":
        substrate_shadow = 1.0 + 0.35 * np.exp(-((yy + metrics.depth * 0.35) / max(0.12, metrics.depth * 0.28)) ** 2)
    array_ripple = 1.0
    if config.array.enabled:
        array_ripple = 1.0 + 0.12 * np.cos(2 * pi * xx / config.array.period_x) + 0.12 * np.cos(2 * pi * yy / config.array.period_y)

    ez_abs = np.clip((0.2 + resonance * standing * angular) * substrate_shadow * array_ripple, 0.0, None)
    ez_abs /= ez_abs.max()
    return {"x": x, "y": y, "ez_abs": ez_abs}


def _plot_heatmap(path: Path, wavelengths: np.ndarray, diameters: np.ndarray, heatmap: np.ndarray) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 4.6), dpi=170)
    wavelength_grid, diameter_grid = np.meshgrid(wavelengths, diameters)
    mesh = ax.pcolormesh(wavelength_grid, diameter_grid, heatmap, shading="gouraud", cmap="rainbow")
    ax.set_xlabel("Wavelength (um)")
    ax.set_ylabel("Particle diameter (um)")
    ax.set_title("Scattering efficiency", fontsize=10)
    fig.colorbar(mesh, ax=ax, label="Qsca")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_spectrum(path: Path, spectrum_rows: list[dict[str, float]]) -> None:
    wavelengths = [row["wavelength_um"] for row in spectrum_rows]
    efficiencies = [row["scattering_efficiency"] for row in spectrum_rows]
    diameter = spectrum_rows[0]["diameter_um"]
    fig, ax = plt.subplots(figsize=(6.2, 3.8), dpi=170)
    ax.plot(wavelengths, efficiencies, color="#0f766e", linewidth=2.1)
    ax.set_xlabel("Wavelength (um)")
    ax.set_ylabel("Qsca")
    ax.set_title(f"Scattering spectrum at diameter {diameter:.2f} um", fontsize=10)
    ax.grid(True, color="#d8dee9", linewidth=0.6)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_efficiency_components(path: Path, spectrum_rows: list[dict[str, float]]) -> None:
    wavelengths = [row["wavelength_um"] for row in spectrum_rows]
    fig, ax = plt.subplots(figsize=(6.2, 3.8), dpi=170)
    ax.plot(wavelengths, [row["scattering_efficiency"] for row in spectrum_rows], label="Qsca", color="#0f766e", linewidth=2)
    ax.plot(wavelengths, [row["absorption_efficiency"] for row in spectrum_rows], label="Qabs", color="#b45309", linewidth=2)
    ax.plot(wavelengths, [row["extinction_efficiency"] for row in spectrum_rows], label="Qext", color="#334155", linewidth=2)
    ax.set_xlabel("Wavelength (um)")
    ax.set_ylabel("Efficiency")
    ax.set_title("Efficiency components", fontsize=10)
    ax.legend(frameon=False)
    ax.grid(True, color="#d8dee9", linewidth=0.6)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_peak_map(path: Path, peaks: list[dict[str, float]]) -> None:
    fig, ax = plt.subplots(figsize=(5.6, 3.8), dpi=170)
    ax.plot(
        [row["diameter_um"] for row in peaks],
        [row["peak_wavelength_um"] for row in peaks],
        color="#6d5dfc",
        linewidth=2.1,
    )
    ax.set_xlabel("Particle diameter (um)")
    ax.set_ylabel("Peak wavelength (um)")
    ax.set_title("Peak trajectory", fontsize=10)
    ax.grid(True, color="#d8dee9", linewidth=0.6)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _plot_field(path: Path, field: dict[str, np.ndarray]) -> None:
    fig, ax = plt.subplots(figsize=(4.5, 4.2), dpi=170)
    image = ax.imshow(
        field["ez_abs"],
        extent=[float(field["x"][0]), float(field["x"][-1]), float(field["y"][0]), float(field["y"][-1])],
        origin="lower",
        cmap="magma",
        aspect="equal",
    )
    ax.set_xlabel("x (um)")
    ax.set_ylabel("y (um)")
    ax.set_title("|Ez| near field", fontsize=10)
    fig.colorbar(image, ax=ax, label="|Ez| / max")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _solver_note(selection) -> str:
    if selection.solver == "mie":
        return "Exact homogeneous-sphere Mie solution computed with miepython."
    if selection.solver == "tmatrix":
        return "T-matrix backend computed with treams."
    if selection.solver == "rcwa":
        return "RCWA periodic-unit-cell backend computed with rcwa."
    if selection.solver == "grcwa":
        return "RCWA periodic-unit-cell backend computed with grcwa."
    if selection.solver == "meep":
        return "Meep/FDTD flux-box backend with empty-cell normalization."
    return "Analytical Mie-equivalent-sphere screening backend. It is not shape-, substrate-, or array-exact."


def _calculation_warnings(config: SimulationConfig, selection) -> list[str]:
    warnings: list[str] = [*selection.notes]
    if selection.solver == "mie":
        warnings.append("miepython result is an exact analytical reference for a homogeneous sphere in a lossless uniform medium.")
        if config.material.preset in {"Au", "Ag", "Al"}:
            warnings.append("Constant-index metal data are a modeling approximation over broadband scans; use wavelength-dependent optical constants when modeling dispersive metals.")
        return warnings

    if selection.solver == "tmatrix":
        if config.geometry.type == "sphere":
            warnings.append("treams spherical T-matrix is used for the isolated homogeneous sphere.")
        else:
            warnings.append("treams cylindrical T-matrix is used for the current cylinder-like cross section.")
        return warnings

    if selection.solver in {"rcwa", "grcwa"}:
        warnings.append("Periodic-unit-cell RCWA is used for the enabled array; finite-array edge effects are not included.")
        warnings.append("Particle shapes are represented on a transverse permittivity grid with layer slicing where needed.")
        return warnings

    if config.geometry.type == "sphere" and not config.array.enabled and config.substrate.type == "none":
        warnings.append("Analytical Mie-equivalent result is a reference only because this model is an isolated homogeneous sphere.")
    elif config.geometry.type == "sphere":
        warnings.append("Analytical Mie result is exact for the isolated homogeneous sphere only; environmental coupling settings are approximations unless a full-wave solver is used.")
    elif config.geometry.type != "cylinder":
        warnings.append("The analytical backend uses an equal-volume sphere for non-spherical geometry; shape-dependent resonances are not exact.")
    else:
        warnings.append("The analytical backend uses an equal-volume sphere for the cylinder; finite-height cylinder resonances are not exact.")
    if config.geometry.type == "shell":
        warnings.append("Layered shell Mie coefficients are not implemented; the current calculation uses the shell volume equivalent sphere with the particle material.")
    if config.array.enabled:
        warnings.append("Array coupling and diffraction are not included in the analytical Mie backend.")
    if config.substrate.type != "none":
        warnings.append("Substrate interaction is not included in the analytical Mie backend.")
    if config.material.medium_n_imag > 0:
        warnings.append("Absorbing media are not supported by the analytical Mie backend.")
    return warnings


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _write_heatmap_csv(path: Path, wavelengths: np.ndarray, diameters: np.ndarray, heatmap: np.ndarray) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["diameter_um", *[f"{value:.8f}" for value in wavelengths]])
        for diameter, row in zip(diameters, heatmap):
            writer.writerow([f"{diameter:.8f}", *[f"{value:.10g}" for value in row]])


def _write_grid_csv(
    path: Path,
    wavelengths: np.ndarray,
    diameters: np.ndarray,
    qsca: np.ndarray,
    qabs: np.ndarray,
    qext: np.ndarray,
    albedo: np.ndarray,
    asymmetry: np.ndarray,
) -> None:
    rows = []
    for d_index, diameter in enumerate(diameters):
        for w_index, wavelength in enumerate(wavelengths):
            rows.append(
                {
                    "wavelength_um": float(wavelength),
                    "diameter_um": float(diameter),
                    "Qsca": float(qsca[d_index, w_index]),
                    "Qabs": float(qabs[d_index, w_index]),
                    "Qext": float(qext[d_index, w_index]),
                    "albedo": float(albedo[d_index, w_index]),
                    "asymmetry_g": float(asymmetry[d_index, w_index]),
                }
            )
    _write_rows_csv(path, rows)


def _write_rows_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
