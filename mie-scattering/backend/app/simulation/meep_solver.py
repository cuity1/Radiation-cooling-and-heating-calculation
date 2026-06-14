from __future__ import annotations

import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from math import pi
from pathlib import Path
from typing import Callable

import h5py
import numpy as np

from app.models import SimulationConfig
from app.simulation.geometry import geometry_metrics, geometry_summary
from app.simulation.materials import material_summary, resolve_medium_material, resolve_particle_material, resolve_shell_core_material, substrate_index
from app.simulation.meep_adapter import MeepUnavailableError
from app.simulation.solver_limits import (
    MEEP_HIGH_RESOLUTION,
    MEEP_HIGH_RESOLUTION_SCAN_POINTS,
    MEEP_MAX_ARRAY_PARTICLES,
    MEEP_MAX_SCAN_POINTS,
    MEEP_MAX_WORKERS,
)


ProgressCallback = Callable[[float, str], None]


@dataclass(frozen=True)
class MeepLayout:
    cell_x: float
    cell_y: float
    cell_z: float
    box_x: float
    box_y: float
    box_z: float
    source_x: float
    source_span_y: float
    source_span_z: float
    incident_area: float


@dataclass
class DiameterResult:
    wavelengths: np.ndarray
    qsca: np.ndarray
    qabs: np.ndarray
    qext: np.ndarray
    flux_rows: list[dict[str, float]]
    field: dict[str, np.ndarray] | None = None


@dataclass
class NormalizationRun:
    flux_data: list[object]
    incident_power: np.ndarray
    freqs: np.ndarray


def run_meep_fdtd_scan(config: SimulationConfig, result_dir: Path, progress_callback: ProgressCallback | None = None) -> dict[str, object]:
    """Run a real Meep/FDTD flux-monitor calculation.

    This backend performs a normalizing empty-cell run, subtracts the incident Fourier
    fields from a six-face scattering flux box, and estimates absorption from the net
    total-field flux through the same closed box.
    """
    _validate_meep_config(config)
    try:
        import meep as mp
    except Exception as exc:  # pragma: no cover - depends on optional external package
        raise MeepUnavailableError("Meep is not installed. Install python-meep to use simulation.solver='meep'.") from exc

    from app.simulation.fast_solver import (
        _cross_section_rows,
        _peak_rows,
        _plot_efficiency_components,
        _plot_field,
        _plot_heatmap,
        _plot_peak_map,
        _plot_spectrum,
        _write_grid_csv,
        _write_heatmap_csv,
        _write_json,
        _write_rows_csv,
    )

    result_dir.mkdir(parents=True, exist_ok=True)
    if progress_callback is None:
        progress_callback = lambda _progress, _status="running": None

    _write_json(result_dir / "config.json", config.model_dump(mode="json"))
    requested_diameters = np.linspace(config.scan.diameter_min, config.scan.diameter_max, config.scan.diameter_points)
    qsca_rows: list[np.ndarray | None] = [None] * len(requested_diameters)
    qabs_rows: list[np.ndarray | None] = [None] * len(requested_diameters)
    qext_rows: list[np.ndarray | None] = [None] * len(requested_diameters)
    flux_rows: list[dict[str, float]] = []
    wavelengths: np.ndarray | None = None
    norm_cache: dict[tuple[float, ...], NormalizationRun] = {}

    total_runs = len(requested_diameters) + 1
    workers = _meep_worker_count(config, len(requested_diameters))
    if workers == 1:
        for index, diameter in enumerate(requested_diameters):
            progress_callback(0.04 + 0.68 * index / max(total_runs, 1), "running")
            result = _run_single_diameter(mp, config, float(diameter), capture_field=False, norm_cache=norm_cache)
            wavelengths = result.wavelengths
            qsca_rows[index] = result.qsca
            qabs_rows[index] = result.qabs
            qext_rows[index] = result.qext
            flux_rows.extend(result.flux_rows)
    else:
        config_payload = config.model_dump(mode="json")
        completed = 0
        with ProcessPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_run_single_diameter_worker, config_payload, float(diameter)): index
                for index, diameter in enumerate(requested_diameters)
            }
            for future in as_completed(futures):
                index = futures[future]
                result = future.result()
                completed += 1
                wavelengths = result.wavelengths
                qsca_rows[index] = result.qsca
                qabs_rows[index] = result.qabs
                qext_rows[index] = result.qext
                flux_rows.extend(result.flux_rows)
                progress_callback(0.04 + 0.68 * completed / max(total_runs, 1), "running")

    spectrum_diameter = min(max(config.scan.spectrum_diameter, config.scan.diameter_min), config.scan.diameter_max)
    spectrum_result = _run_single_diameter(mp, config, float(spectrum_diameter), capture_field=True, norm_cache=norm_cache)
    wavelengths = spectrum_result.wavelengths
    progress_callback(0.76, "running")

    qsca = np.vstack([row for row in qsca_rows if row is not None])
    qabs = np.vstack([row for row in qabs_rows if row is not None])
    qext = np.vstack([row for row in qext_rows if row is not None])
    albedo = np.divide(qsca, qext, out=np.zeros_like(qsca), where=qext > 0)
    asymmetry = np.full_like(qsca, np.nan)

    _write_heatmap_csv(result_dir / "heatmap.csv", wavelengths, requested_diameters, qsca)
    _write_grid_csv(result_dir / "efficiencies.csv", wavelengths, requested_diameters, qsca, qabs, qext, albedo, asymmetry)
    cross_sections = _cross_section_rows(config, wavelengths, requested_diameters, qsca, qabs, qext)
    _write_rows_csv(result_dir / "cross_sections.csv", cross_sections)
    peaks = _peak_rows(wavelengths, requested_diameters, qsca)
    _write_rows_csv(result_dir / "peaks.csv", peaks)
    _write_rows_csv(result_dir / "fdtd_fluxes.csv", flux_rows)
    progress_callback(0.82, "running")

    spectrum_albedo = np.divide(spectrum_result.qsca, spectrum_result.qext, out=np.zeros_like(spectrum_result.qsca), where=spectrum_result.qext > 0)
    spectrum_area = geometry_metrics(config.geometry, config.array, spectrum_diameter).reference_area * _array_count(config)
    spectrum_rows = [
        {
            "wavelength_um": float(wavelength),
            "diameter_um": float(spectrum_diameter),
            "scattering_efficiency": float(qs),
            "absorption_efficiency": float(qa),
            "extinction_efficiency": float(qe),
            "albedo": float(ab),
            "asymmetry_g": float("nan"),
            "mie_reference_area_um2": float(spectrum_area),
            "scattering_cross_section_um2": float(qs * spectrum_area),
        }
        for wavelength, qs, qa, qe, ab in zip(wavelengths, spectrum_result.qsca, spectrum_result.qabs, spectrum_result.qext, spectrum_albedo)
    ]
    _write_rows_csv(result_dir / "spectrum.csv", spectrum_rows)

    field = spectrum_result.field or {"x": np.array([0.0]), "y": np.array([0.0]), "ez_abs": np.zeros((1, 1))}
    with h5py.File(result_dir / "fields.h5", "w") as h5:
        h5.create_dataset("x_um", data=field["x"])
        h5.create_dataset("y_um", data=field["y"])
        h5.create_dataset("field_abs", data=field["field_abs"])
        h5.create_dataset("ez_abs", data=field["field_abs"])
        h5.attrs["diameter_um"] = spectrum_diameter
        h5.attrs["field_quantity"] = "normalized_total_electric_field_magnitude"
        h5.attrs["field_source"] = "Meep DFT sqrt(|Ex|^2+|Ey|^2+|Ez|^2) in z=0 plane, normalized by its maximum"
        h5.attrs["wavelength_um"] = float(wavelengths[int(np.argmax(spectrum_result.qsca))])

    substrate_n = substrate_index(config.substrate.type, config.substrate.metal_index_real, config.substrate.metal_index_imag)
    geometry_payload = geometry_summary(config.geometry, config.array, spectrum_diameter)
    material_payload = material_summary(config.material, config.substrate.type, substrate_n)
    _write_json(result_dir / "geometry_summary.json", geometry_payload)
    _write_json(result_dir / "material_summary.json", material_payload)

    _plot_heatmap(result_dir / "fig_heatmap.png", wavelengths, requested_diameters, qsca)
    _plot_spectrum(result_dir / "fig_spectrum.png", spectrum_rows)
    _plot_efficiency_components(result_dir / "fig_efficiency_components.png", spectrum_rows)
    _plot_peak_map(result_dir / "fig_peak_map.png", peaks)
    _plot_field(result_dir / "fig_field_xy.png", field)
    progress_callback(0.92, "running")

    peak_index = np.unravel_index(np.argmax(qsca), qsca.shape)
    spectrum_peak_index = int(np.argmax(spectrum_result.qsca))
    outputs = [
        "config.json",
        "spectrum.csv",
        "heatmap.csv",
        "efficiencies.csv",
        "cross_sections.csv",
        "peaks.csv",
        "fdtd_fluxes.csv",
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
        "solver": "meep",
        "solver_note": "Real Meep/FDTD flux-monitor calculation with empty-cell normalization and six-face scattered-flux subtraction.",
        "calculation_method": "meep_fdtd_flux_box",
        "accuracy_warnings": _meep_warnings(config),
        "geometry": config.geometry.type,
        "material": material_payload["particle"],
        "medium": material_payload["medium"],
        "substrate": config.substrate.type,
        "array_enabled": config.array.enabled,
        "wavelength_range_um": [float(wavelengths[0]), float(wavelengths[-1])],
        "diameter_range_um": [float(requested_diameters[0]), float(requested_diameters[-1])],
        "heatmap_shape": [int(qsca.shape[0]), int(qsca.shape[1])],
        "global_peak": {
            "diameter_um": float(requested_diameters[peak_index[0]]),
            "wavelength_um": float(wavelengths[peak_index[1]]),
            "scattering_efficiency": float(qsca[peak_index]),
            "absorption_efficiency": float(qabs[peak_index]),
            "extinction_efficiency": float(qext[peak_index]),
            "asymmetry_g": None,
        },
        "spectrum_peak": {
            "diameter_um": float(spectrum_diameter),
            "wavelength_um": float(wavelengths[spectrum_peak_index]),
            "scattering_efficiency": float(spectrum_result.qsca[spectrum_peak_index]),
            "absorption_efficiency": float(spectrum_result.qabs[spectrum_peak_index]),
            "extinction_efficiency": float(spectrum_result.qext[spectrum_peak_index]),
            "asymmetry_g": None,
            "cross_section_um2": float(spectrum_result.qsca[spectrum_peak_index] * spectrum_area),
        },
        "geometry_summary": geometry_payload,
        "outputs": outputs,
    }
    _write_json(result_dir / "summary.json", summary)
    return summary


def _validate_meep_config(config: SimulationConfig) -> None:
    particle = resolve_particle_material(config.material)
    medium = resolve_medium_material(config.material)
    shell_core = resolve_shell_core_material(config.material)
    total_points = config.scan.wavelength_points * config.scan.diameter_points
    if total_points > MEEP_MAX_SCAN_POINTS:
        raise ValueError(f"Meep scan is limited to {MEEP_MAX_SCAN_POINTS} wavelength-diameter points per job to protect server load.")
    if config.simulation.resolution > MEEP_HIGH_RESOLUTION and total_points > MEEP_HIGH_RESOLUTION_SCAN_POINTS:
        raise ValueError(
            f"Meep scans above resolution {MEEP_HIGH_RESOLUTION} are limited to {MEEP_HIGH_RESOLUTION_SCAN_POINTS} wavelength-diameter points per job."
        )
    if config.array.enabled and config.array.count_x * config.array.count_y > MEEP_MAX_ARRAY_PARTICLES:
        raise ValueError(f"Meep finite-array jobs are limited to {MEEP_MAX_ARRAY_PARTICLES} particles per job.")
    if config.simulation.meep_workers > MEEP_MAX_WORKERS:
        raise ValueError(f"Meep worker count is limited to {MEEP_MAX_WORKERS}.")
    if abs(particle.refractive_index.imag) > 1e-12:
        raise ValueError("Meep backend currently supports only lossless constant-index particle materials. Use a dispersive Meep material model for lossy metals.")
    if abs(medium.refractive_index.imag) > 1e-12:
        raise ValueError("Meep backend currently supports only lossless ambient media.")
    if config.geometry.type == "shell" and abs(shell_core.refractive_index.imag) > 1e-12:
        raise ValueError("Meep backend currently supports only lossless shell-core media.")
    if config.substrate.type != "none":
        raise ValueError("Meep substrate normalization is not implemented yet; use substrate.type='none' for real FDTD runs.")


def _run_single_diameter(mp, config: SimulationConfig, diameter: float, capture_field: bool, norm_cache: dict[tuple[float, ...], NormalizationRun] | None = None) -> DiameterResult:
    fmin = 1.0 / config.scan.wavelength_max
    fmax = 1.0 / config.scan.wavelength_min
    fcen = 0.5 * (fmin + fmax)
    df = fmax - fmin
    nfreq = config.scan.wavelength_points
    layout = _layout_for(config, diameter)

    cache_key = _normalization_cache_key(layout, fcen, df, nfreq, config)
    if norm_cache is not None and cache_key in norm_cache:
        normalization = norm_cache[cache_key]
    else:
        norm_sim = _make_simulation(mp, config, diameter, layout, geometry=[])
        norm_fluxes = _add_flux_box(mp, norm_sim, fcen, df, nfreq, layout)
        norm_sim.run(until_after_sources=config.simulation.runtime)
        normalization = NormalizationRun(
            flux_data=[norm_sim.get_flux_data(flux) for flux in norm_fluxes],
            incident_power=np.asarray(mp.get_fluxes(norm_fluxes[0]), dtype=float),
            freqs=np.asarray(mp.get_flux_freqs(norm_fluxes[0]), dtype=float),
        )
        if norm_cache is not None:
            norm_cache[cache_key] = normalization
    incident_power = normalization.incident_power
    freqs = normalization.freqs

    scatter_sim = _make_simulation(mp, config, diameter, layout, geometry=_geometry_objects(mp, config, diameter))
    scatter_fluxes = _add_flux_box(mp, scatter_sim, fcen, df, nfreq, layout)
    for flux, data in zip(scatter_fluxes, normalization.flux_data):
        scatter_sim.load_minus_flux_data(flux, data)
    total_fluxes = _add_flux_box(mp, scatter_sim, fcen, df, nfreq, layout)
    dft_fields = None
    if capture_field:
        dft_fields = scatter_sim.add_dft_fields(
            [mp.Ex, mp.Ey, mp.Ez],
            fcen,
            df,
            nfreq,
            center=mp.Vector3(0, 0, 0),
            size=mp.Vector3(layout.box_x, layout.box_y, 0),
        )
    scatter_sim.run(until_after_sources=config.simulation.runtime)

    scattered_signed_flux = _signed_box_flux(mp, scatter_fluxes)
    total_signed_flux = _signed_box_flux(mp, total_fluxes)
    scattered_power = -scattered_signed_flux
    absorbed_power = -total_signed_flux
    incident_intensity = np.divide(incident_power, layout.incident_area, out=np.zeros_like(incident_power), where=np.abs(incident_power) > 0)
    metrics = geometry_metrics(config.geometry, config.array, diameter)
    reference_area = metrics.reference_area * _array_count(config)
    csca = np.divide(scattered_power, incident_intensity, out=np.zeros_like(scattered_power), where=np.abs(incident_intensity) > 0)
    cabs = np.divide(absorbed_power, incident_intensity, out=np.zeros_like(absorbed_power), where=np.abs(incident_intensity) > 0)
    csca = np.clip(csca, 0.0, None)
    cabs = np.clip(cabs, 0.0, None)
    cext = csca + cabs
    qsca = csca / reference_area
    qabs = cabs / reference_area
    qext = cext / reference_area

    wavelengths = 1.0 / freqs
    order = np.argsort(wavelengths)
    flux_rows = [
        {
            "wavelength_um": float(wavelengths[index]),
            "diameter_um": float(diameter),
            "incident_power": float(incident_power[index]),
            "incident_intensity": float(incident_intensity[index]),
            "scattered_power": float(scattered_power[index]),
            "absorbed_power": float(max(absorbed_power[index], 0.0)),
            "total_outward_power": float(total_signed_flux[index]),
            "Csca_um2": float(csca[index]),
            "Cabs_um2": float(cabs[index]),
            "Cext_um2": float(cext[index]),
        }
        for index in order
    ]

    field = None
    if capture_field and dft_fields is not None:
        peak_index_unsorted = int(np.argmax(qsca))
        field = _extract_dft_field(mp, scatter_sim, dft_fields, peak_index_unsorted)

    return DiameterResult(
        wavelengths=wavelengths[order],
        qsca=qsca[order],
        qabs=qabs[order],
        qext=qext[order],
        flux_rows=flux_rows,
        field=field,
    )


def _run_single_diameter_worker(config_payload: dict[str, object], diameter: float) -> DiameterResult:
    import meep as mp

    config = SimulationConfig.model_validate(config_payload)
    return _run_single_diameter(mp, config, diameter, capture_field=False, norm_cache=None)


def _meep_worker_count(config: SimulationConfig, task_count: int) -> int:
    if task_count <= 1:
        return 1
    return max(1, min(config.simulation.meep_workers, task_count, MEEP_MAX_WORKERS))


def _layout_for(config: SimulationConfig, diameter: float) -> MeepLayout:
    metrics = geometry_metrics(config.geometry, config.array, diameter)
    count_x = config.array.count_x if config.array.enabled else 1
    count_y = config.array.count_y if config.array.enabled else 1
    extent_x = metrics.width + (count_x - 1) * config.array.period_x
    extent_y = metrics.depth + (count_y - 1) * config.array.period_y
    extent_z = metrics.height
    padding = max(config.simulation.cell_padding, 0.25)
    pml = config.simulation.pml_thickness
    box_x = extent_x + 2.0 * padding
    box_y = extent_y + 2.0 * padding
    box_z = extent_z + 2.0 * padding
    source_gap = max(0.35, 0.5 * padding)
    cell_x = box_x + 2.0 * (pml + source_gap + 0.25 * padding)
    cell_y = box_y + 2.0 * (pml + 0.25 * padding)
    cell_z = box_z + 2.0 * (pml + 0.25 * padding)
    source_span_y = box_y
    source_span_z = box_z
    return MeepLayout(
        cell_x=cell_x,
        cell_y=cell_y,
        cell_z=cell_z,
        box_x=box_x,
        box_y=box_y,
        box_z=box_z,
        source_x=-0.5 * box_x - source_gap,
        source_span_y=source_span_y,
        source_span_z=source_span_z,
        incident_area=source_span_y * source_span_z,
    )


def _normalization_cache_key(layout: MeepLayout, fcen: float, df: float, nfreq: int, config: SimulationConfig) -> tuple[float, ...]:
    return (
        round(layout.cell_x, 12),
        round(layout.cell_y, 12),
        round(layout.cell_z, 12),
        round(layout.box_x, 12),
        round(layout.box_y, 12),
        round(layout.box_z, 12),
        round(layout.source_x, 12),
        round(layout.source_span_y, 12),
        round(layout.source_span_z, 12),
        round(fcen, 12),
        round(df, 12),
        float(nfreq),
        float(config.simulation.resolution),
        round(config.simulation.pml_thickness, 12),
        round(config.simulation.runtime, 12),
        round(config.material.medium_n_real, 12),
    )


def _make_simulation(mp, config: SimulationConfig, diameter: float, layout: MeepLayout, geometry: list[object]):
    fmin = 1.0 / config.scan.wavelength_max
    fmax = 1.0 / config.scan.wavelength_min
    fcen = 0.5 * (fmin + fmax)
    df = fmax - fmin
    medium = resolve_medium_material(config.material)
    return mp.Simulation(
        cell_size=mp.Vector3(layout.cell_x, layout.cell_y, layout.cell_z),
        boundary_layers=[mp.PML(config.simulation.pml_thickness)],
        geometry=geometry,
        sources=[
            mp.Source(
                mp.GaussianSource(frequency=fcen, fwidth=df, is_integrated=True),
                component=mp.Ez,
                center=mp.Vector3(layout.source_x, 0, 0),
                size=mp.Vector3(0, layout.source_span_y, layout.source_span_z),
            )
        ],
        default_material=mp.Medium(index=medium.refractive_index.real),
        resolution=config.simulation.resolution,
        k_point=mp.Vector3(),
    )


def _flux_box_regions(mp, layout: MeepLayout) -> list[object]:
    return [
        mp.FluxRegion(center=mp.Vector3(x=-0.5 * layout.box_x), size=mp.Vector3(0, layout.box_y, layout.box_z)),
        mp.FluxRegion(center=mp.Vector3(x=+0.5 * layout.box_x), size=mp.Vector3(0, layout.box_y, layout.box_z)),
        mp.FluxRegion(center=mp.Vector3(y=-0.5 * layout.box_y), size=mp.Vector3(layout.box_x, 0, layout.box_z)),
        mp.FluxRegion(center=mp.Vector3(y=+0.5 * layout.box_y), size=mp.Vector3(layout.box_x, 0, layout.box_z)),
        mp.FluxRegion(center=mp.Vector3(z=-0.5 * layout.box_z), size=mp.Vector3(layout.box_x, layout.box_y, 0)),
        mp.FluxRegion(center=mp.Vector3(z=+0.5 * layout.box_z), size=mp.Vector3(layout.box_x, layout.box_y, 0)),
    ]


def _add_flux_box(mp, sim, fcen: float, df: float, nfreq: int, layout: MeepLayout) -> list[object]:
    return [sim.add_flux(fcen, df, nfreq, region) for region in _flux_box_regions(mp, layout)]


def _signed_box_flux(mp, fluxes: list[object]) -> np.ndarray:
    values = [np.asarray(mp.get_fluxes(flux), dtype=float) for flux in fluxes]
    return values[0] - values[1] + values[2] - values[3] + values[4] - values[5]


def _geometry_objects(mp, config: SimulationConfig, diameter: float) -> list[object]:
    particle = resolve_particle_material(config.material)
    shell_core = resolve_shell_core_material(config.material)
    metrics = geometry_metrics(config.geometry, config.array, diameter)
    count_x = config.array.count_x if config.array.enabled else 1
    count_y = config.array.count_y if config.array.enabled else 1
    offset_x = 0.5 * (count_x - 1) * config.array.period_x
    offset_y = 0.5 * (count_y - 1) * config.array.period_y
    objects: list[object] = []
    particle_medium = mp.Medium(index=particle.refractive_index.real)
    core_medium = mp.Medium(index=shell_core.refractive_index.real)
    for ix in range(count_x):
        for iy in range(count_y):
            center = mp.Vector3(ix * config.array.period_x - offset_x, iy * config.array.period_y - offset_y, 0)
            if config.geometry.type == "sphere":
                objects.append(mp.Sphere(radius=0.5 * metrics.width, center=center, material=particle_medium))
            elif config.geometry.type == "cylinder":
                objects.append(mp.Cylinder(radius=0.5 * metrics.width, height=metrics.height, axis=mp.Vector3(0, 0, 1), center=center, material=particle_medium))
            elif config.geometry.type == "cube":
                objects.append(mp.Block(size=mp.Vector3(metrics.width, metrics.depth, metrics.height), center=center, material=particle_medium))
            elif config.geometry.type == "ellipsoid":
                objects.append(mp.Ellipsoid(size=mp.Vector3(metrics.width, metrics.depth, metrics.height), center=center, material=particle_medium))
            else:
                inner_diameter = min(config.geometry.size.inner_diameter * diameter / max(config.geometry.size.diameter, 1e-12), metrics.width * 0.95)
                objects.append(mp.Cylinder(radius=0.5 * metrics.width, height=metrics.height, axis=mp.Vector3(0, 0, 1), center=center, material=particle_medium))
                objects.append(mp.Cylinder(radius=0.5 * inner_diameter, height=metrics.height * 1.02, axis=mp.Vector3(0, 0, 1), center=center, material=core_medium))
    return objects


def _extract_dft_field(mp, sim, dft_fields, peak_index: int) -> dict[str, np.ndarray]:
    ex = sim.get_dft_array(dft_fields, mp.Ex, peak_index)
    ey = sim.get_dft_array(dft_fields, mp.Ey, peak_index)
    ez = sim.get_dft_array(dft_fields, mp.Ez, peak_index)
    magnitude = np.sqrt(np.abs(ex) ** 2 + np.abs(ey) ** 2 + np.abs(ez) ** 2)
    x, y, _z, _w = sim.get_array_metadata(dft_cell=dft_fields)
    squeezed = np.squeeze(magnitude)
    if squeezed.ndim == 1:
        squeezed = squeezed[:, None]
    if squeezed.max() > 0:
        squeezed = squeezed / squeezed.max()
    return {"x": np.asarray(x, dtype=float), "y": np.asarray(y, dtype=float), "field_abs": squeezed, "ez_abs": squeezed}


def _array_count(config: SimulationConfig) -> int:
    return config.array.count_x * config.array.count_y if config.array.enabled else 1


def _meep_warnings(config: SimulationConfig) -> list[str]:
    warnings = ["FDTD results depend on resolution, PML thickness, cell padding, runtime, and source bandwidth."]
    if config.array.enabled:
        warnings.append("Finite-array simulation is used; this is not a Bloch-periodic infinite-array calculation.")
    if config.geometry.type == "shell":
        warnings.append("Shell geometry is represented by overlapping Meep objects; verify material precedence for your installed Meep version.")
    return warnings
