from __future__ import annotations

import csv
import json

import pytest
from pydantic import ValidationError

from app.models import SimulationConfig
from app.simulation.fast_solver import run_fast_fdtd_scan
from app.simulation.meep_solver import _validate_meep_config
from app.simulation.mie import mie_efficiencies
from app.simulation.scan_defaults import (
    apply_missing_solver_scan_defaults,
    apply_solver_scan_defaults,
    normalize_scan_for_solver_limits,
)
from app.simulation.solver_router import SolverUnavailableError, recommend_solver, select_solver


def test_auto_sphere_uses_exact_mie_and_writes_outputs(tmp_path) -> None:
    config = SimulationConfig(
        scan={
            "wavelength_min": 0.4,
            "wavelength_max": 1.2,
            "wavelength_points": 12,
            "diameter_min": 0.3,
            "diameter_max": 1.1,
            "diameter_points": 9,
            "spectrum_diameter": 0.7,
        }
    )
    summary = run_fast_fdtd_scan(config, tmp_path)

    expected = {
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
    }
    assert expected.issubset({item.name for item in tmp_path.iterdir()})
    assert not (tmp_path / "validation_report.json").exists()
    assert summary["requested_solver"] == "auto"
    assert summary["solver"] == "mie"
    assert summary["calculation_method"] == "miepython_homogeneous_sphere"
    assert summary["heatmap_shape"] == [9, 12]
    assert "publication_ready" not in summary
    assert "validation" not in summary

    with (tmp_path / "heatmap.csv").open(encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == 10
    assert len(rows[0]) == 13
    values = [[float(value) for value in row[1:]] for row in rows[1:]]
    assert max(max(row) for row in values) > 0

    saved_summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert saved_summary["solver"] == "mie"
    assert saved_summary["global_peak"]["scattering_efficiency"] > 0
    assert saved_summary["spectrum_peak"]["extinction_efficiency"] + 1e-12 >= saved_summary["spectrum_peak"]["scattering_efficiency"]

    with (tmp_path / "efficiencies.csv").open(encoding="utf-8") as handle:
        efficiency_header = next(csv.reader(handle))
    assert efficiency_header == ["wavelength_um", "diameter_um", "Qsca", "Qabs", "Qext", "albedo", "asymmetry_g"]


def test_material_choice_changes_scattering(tmp_path) -> None:
    dielectric = SimulationConfig(scan={"wavelength_points": 8, "diameter_points": 5}, material={"preset": "TiO2"})
    metal = SimulationConfig(scan={"wavelength_points": 8, "diameter_points": 5}, material={"preset": "Au"})
    dielectric_summary = run_fast_fdtd_scan(dielectric, tmp_path / "dielectric")
    metal_summary = run_fast_fdtd_scan(metal, tmp_path / "metal")
    assert dielectric_summary["global_peak"]["scattering_efficiency"] != metal_summary["global_peak"]["scattering_efficiency"] or (
        dielectric_summary["global_peak"]["absorption_efficiency"] != metal_summary["global_peak"]["absorption_efficiency"]
    )


def test_mie_small_particle_scales_like_rayleigh() -> None:
    small = mie_efficiencies(0.02, 1.0, 1.5 + 0j, 1.0 + 0j)
    large = mie_efficiencies(0.04, 1.0, 1.5 + 0j, 1.0 + 0j)
    ratio = large.qsca / small.qsca
    assert ratio == pytest.approx(16.0, rel=0.08)


def test_solver_scan_defaults_by_complexity() -> None:
    assert apply_solver_scan_defaults(SimulationConfig()).scan.wavelength_points == 160
    assert apply_solver_scan_defaults(SimulationConfig()).scan.diameter_points == 80

    tmatrix = apply_solver_scan_defaults(SimulationConfig(geometry={"type": "cylinder"}))
    assert tmatrix.scan.wavelength_points == 100
    assert tmatrix.scan.diameter_points == 50

    rcwa = apply_solver_scan_defaults(SimulationConfig(array={"enabled": True, "count_x": 4, "count_y": 4}))
    assert rcwa.scan.wavelength_points == 12
    assert rcwa.scan.diameter_points == 8

    proxy = apply_solver_scan_defaults(SimulationConfig(geometry={"type": "ellipsoid"}))
    assert proxy.scan.wavelength_points == 160
    assert proxy.scan.diameter_points == 80

    substrate = apply_solver_scan_defaults(SimulationConfig(substrate={"type": "glass"}))
    assert substrate.scan.wavelength_points == 160
    assert substrate.scan.diameter_points == 80


def test_missing_scan_points_use_solver_defaults_without_overwriting_explicit_values() -> None:
    tmatrix = apply_missing_solver_scan_defaults(SimulationConfig(geometry={"type": "cylinder"}, simulation={"solver": "tmatrix"}))
    assert tmatrix.scan.wavelength_points == 100
    assert tmatrix.scan.diameter_points == 50

    partial = apply_missing_solver_scan_defaults(
        SimulationConfig(
            geometry={"type": "cylinder"},
            simulation={"solver": "tmatrix"},
            scan={"wavelength_points": 33},
        )
    )
    assert partial.scan.wavelength_points == 33
    assert partial.scan.diameter_points == 50


def test_solver_limit_normalization_preserves_light_solver_density() -> None:
    mie = normalize_scan_for_solver_limits(SimulationConfig(simulation={"solver": "mie"}, scan={"wavelength_points": 200, "diameter_points": 100}))
    assert mie.scan.wavelength_points == 200
    assert mie.scan.diameter_points == 100

    rcwa = normalize_scan_for_solver_limits(
        SimulationConfig(
            array={"enabled": True, "count_x": 4, "count_y": 4},
            simulation={"solver": "rcwa"},
            scan={"wavelength_points": 30, "diameter_points": 10},
        )
    )
    assert rcwa.scan.wavelength_points * rcwa.scan.diameter_points <= 96


def test_auto_ellipsoid_uses_smart_proxy_without_meep(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.simulation.solver_router.find_spec", lambda name: None if name == "meep" else object())
    config = SimulationConfig(geometry={"type": "ellipsoid"}, scan={"wavelength_points": 5, "diameter_points": 3})
    selection = select_solver(config)
    assert selection.blocking is False
    assert selection.solver == "smart_proxy"
    assert recommend_solver(config) == "smart_proxy"
    assert "not used by auto" in " ".join(selection.notes)
    summary = run_fast_fdtd_scan(config, tmp_path)
    assert summary["solver"] == "smart_proxy"


def test_auto_selects_tmatrix_grcwa_and_proxy_without_meep(monkeypatch) -> None:
    monkeypatch.setattr("app.simulation.solver_router.find_spec", lambda name: object())
    cylinder = SimulationConfig(geometry={"type": "cylinder"}, scan={"wavelength_points": 24, "diameter_points": 12})
    selection = select_solver(cylinder)
    assert selection.blocking is False
    assert selection.solver == "tmatrix"

    periodic_array = SimulationConfig(geometry={"type": "cube"}, array={"enabled": True, "count_x": 2, "count_y": 2}, scan={"wavelength_points": 6, "diameter_points": 6})
    array_selection = select_solver(periodic_array)
    assert array_selection.blocking is False
    assert array_selection.solver == "grcwa"

    ellipsoid = SimulationConfig(geometry={"type": "ellipsoid"}, scan={"wavelength_points": 24, "diameter_points": 12})
    proxy_selection = select_solver(ellipsoid)
    assert proxy_selection.blocking is False
    assert proxy_selection.solver == "smart_proxy"


def test_auto_does_not_apply_meep_guardrail_to_proxy_fallback(monkeypatch) -> None:
    monkeypatch.setattr("app.simulation.solver_router.find_spec", lambda name: object())
    too_many_points = SimulationConfig(geometry={"type": "ellipsoid"}, scan={"wavelength_points": 30, "diameter_points": 10})
    selection = select_solver(too_many_points)
    assert selection.blocking is False
    assert selection.solver == "smart_proxy"
    assert selection.calculation_method == "analytical_mie_equivalent_sphere"


def test_solver_recommendations_by_geometry_and_environment() -> None:
    assert recommend_solver(SimulationConfig(geometry={"type": "sphere"})) == "mie"
    assert recommend_solver(SimulationConfig(geometry={"type": "cylinder"})) == "tmatrix"
    assert recommend_solver(SimulationConfig(geometry={"type": "ellipsoid"})) == "smart_proxy"
    assert recommend_solver(SimulationConfig(geometry={"type": "cube"})) == "smart_proxy"
    assert recommend_solver(SimulationConfig(geometry={"type": "shell"})) == "tmatrix"
    assert recommend_solver(SimulationConfig(geometry={"type": "sphere"}, array={"enabled": True})) == "grcwa"
    assert recommend_solver(SimulationConfig(geometry={"type": "sphere"}, substrate={"type": "glass"})) == "smart_proxy"
    assert recommend_solver(SimulationConfig(geometry={"type": "sphere"}, substrate={"type": "glass"}, array={"enabled": True})) == "grcwa"


def test_explicit_smart_proxy_still_runs_when_requested(tmp_path) -> None:
    config = SimulationConfig(
        geometry={"type": "cylinder"},
        scan={"wavelength_points": 6, "diameter_points": 4},
        simulation={"solver": "smart_proxy"},
    )
    summary = run_fast_fdtd_scan(config, tmp_path)
    assert summary["requested_solver"] == "smart_proxy"
    assert summary["solver"] == "smart_proxy"
    assert summary["calculation_method"] == "analytical_mie_equivalent_sphere"
    assert summary["global_peak"]["scattering_efficiency"] > 0


def test_explicit_tmatrix_runs_when_requested(tmp_path) -> None:
    config = SimulationConfig(
        geometry={"type": "cylinder"},
        scan={"wavelength_points": 3, "diameter_points": 2},
        simulation={"solver": "tmatrix"},
    )
    summary = run_fast_fdtd_scan(config, tmp_path)
    assert summary["requested_solver"] == "tmatrix"
    assert summary["solver"] == "tmatrix"
    assert summary["calculation_method"] == "treams_cylindrical_tmatrix"
    assert summary["heatmap_shape"] == [2, 3]
    assert summary["global_peak"]["scattering_efficiency"] > 0


def test_explicit_rcwa_and_grcwa_run_for_periodic_arrays(tmp_path) -> None:
    base = {
        "array": {"enabled": True, "count_x": 4, "count_y": 4},
        "scan": {"wavelength_points": 2, "diameter_points": 2},
    }
    for solver in ["rcwa", "grcwa"]:
        config = SimulationConfig(**base, simulation={"solver": solver})
        summary = run_fast_fdtd_scan(config, tmp_path / solver)
        assert summary["requested_solver"] == solver
        assert summary["solver"] == solver
        assert summary["heatmap_shape"] == [2, 2]
        assert summary["global_peak"]["scattering_efficiency"] >= 0


def test_rcwa_requires_enabled_array_and_guardrails() -> None:
    no_array = SimulationConfig(simulation={"solver": "rcwa"})
    assert select_solver(no_array).blocking is True
    assert "array.enabled=true" in select_solver(no_array).reason

    too_many_points = SimulationConfig(
        array={"enabled": True, "count_x": 4, "count_y": 4},
        simulation={"solver": "grcwa"},
        scan={"wavelength_points": 13, "diameter_points": 8},
    )
    assert select_solver(too_many_points).blocking is True
    assert "96 wavelength-diameter points" in select_solver(too_many_points).reason


def test_solver_does_not_normalize_every_material_to_same_peak(tmp_path) -> None:
    configs = [
        SimulationConfig(scan={"wavelength_points": 16, "diameter_points": 8}, material={"preset": preset})
        for preset in ["TiO2", "SiO2", "Au"]
    ]
    peaks = [run_fast_fdtd_scan(config, tmp_path / config.material.preset)["global_peak"]["scattering_efficiency"] for config in configs]
    assert len({round(value, 6) for value in peaks}) > 1


def test_meep_solver_requires_meep_installation_without_proxy_fallback(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.simulation.solver_router.find_spec", lambda name: None if name == "meep" else object())
    config = SimulationConfig(simulation={"solver": "meep"})
    selection = select_solver(config)
    assert selection.blocking is True
    assert selection.solver == "meep"
    with pytest.raises(SolverUnavailableError, match="Meep is not installed"):
        run_fast_fdtd_scan(config, tmp_path)


def test_meep_selection_rejects_unsupported_scope_before_queueing(monkeypatch) -> None:
    monkeypatch.setattr("app.simulation.solver_router.find_spec", lambda name: object())
    lossy = SimulationConfig(simulation={"solver": "meep"}, material={"preset": "Au"})
    substrate = SimulationConfig(simulation={"solver": "meep"}, substrate={"type": "glass"})
    too_many_points = SimulationConfig(simulation={"solver": "meep"}, scan={"wavelength_points": 30, "diameter_points": 10})

    assert select_solver(lossy).blocking is True
    assert "lossless constant-index" in select_solver(lossy).reason
    assert select_solver(substrate).blocking is True
    assert "substrate normalization" in select_solver(substrate).reason
    assert select_solver(too_many_points).blocking is True
    assert "288 wavelength-diameter points" in select_solver(too_many_points).reason


def test_meep_backend_rejects_lossy_material_until_dispersion_is_defined() -> None:
    config = SimulationConfig(simulation={"solver": "meep"}, material={"preset": "Au"})
    with pytest.raises(ValueError, match="lossless constant-index"):
        _validate_meep_config(config)


def test_meep_backend_limits_job_size_and_workers() -> None:
    too_many_points = SimulationConfig(simulation={"solver": "meep"}, scan={"wavelength_points": 30, "diameter_points": 10})
    with pytest.raises(ValueError, match="288 wavelength-diameter points"):
        _validate_meep_config(too_many_points)

    large_array = SimulationConfig(simulation={"solver": "meep"}, array={"enabled": True, "count_x": 6, "count_y": 5})
    with pytest.raises(ValueError, match="25 particles"):
        _validate_meep_config(large_array)

    with pytest.raises(ValidationError):
        SimulationConfig(simulation={"solver": "meep", "meep_workers": 3})
