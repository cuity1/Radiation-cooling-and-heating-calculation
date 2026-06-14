from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import SimulationConfig
from app.simulation.geometry import geometry_metrics, geometry_summary
from app.simulation.materials import PRESET_MATERIALS, resolve_particle_material


def test_default_config_is_valid() -> None:
    config = SimulationConfig()
    assert config.geometry.type == "sphere"
    assert config.material.preset == "TiO2"
    assert config.simulation.solver == "auto"
    assert config.scan.wavelength_min == 0.3
    assert config.scan.wavelength_points == 24
    assert config.scan.diameter_points == 12
    dumped = config.model_dump_json()
    assert '"particle"' not in dumped
    assert "paper" not in dumped.lower()
    assert "publication" not in dumped.lower()
    assert "reproduction" not in dumped.lower()


def test_sphere_geometry_metrics_are_exact_for_mie_reference() -> None:
    config = SimulationConfig(geometry={"type": "sphere"})
    metrics = geometry_metrics(config.geometry, config.array, 0.8)
    assert metrics.width == pytest.approx(0.8)
    assert metrics.depth == pytest.approx(0.8)
    assert metrics.height == pytest.approx(0.8)
    assert metrics.equivalent_sphere_diameter == pytest.approx(0.8)
    assert metrics.reference_area == pytest.approx(3.141592653589793 * 0.4**2)


def test_shell_inner_diameter_must_be_smaller() -> None:
    with pytest.raises(ValidationError):
        SimulationConfig(
            geometry={
                "type": "shell",
                "size": {
                    "diameter": 0.7,
                    "inner_diameter": 0.8,
                    "height": 0.45,
                    "width": 0.8,
                    "depth": 0.8,
                    "shell_thickness": 0.05,
                },
            }
        )


def test_geometry_metrics_for_array_fill_factor() -> None:
    config = SimulationConfig(array={"enabled": True, "period_x": 1.0, "period_y": 1.0, "count_x": 3, "count_y": 2})
    metrics = geometry_metrics(config.geometry, config.array, 0.5)
    assert metrics.projected_area > 0
    assert 0 < metrics.fill_factor < 1


def test_array_count_limit_accepts_100_and_rejects_101() -> None:
    config = SimulationConfig(array={"enabled": True, "count_x": 100, "count_y": 100})
    assert config.array.count_x == 100
    assert config.array.count_y == 100

    with pytest.raises(ValidationError):
        SimulationConfig(array={"enabled": True, "count_x": 101, "count_y": 100})
    with pytest.raises(ValidationError):
        SimulationConfig(array={"enabled": True, "count_x": 100, "count_y": 101})


def test_all_preset_materials_resolve() -> None:
    for preset in PRESET_MATERIALS:
        material = resolve_particle_material(SimulationConfig(material={"preset": preset}).material)
        assert material.refractive_index.real > 0
        assert material.refractive_index.imag >= 0


def test_custom_material_resolves_from_input() -> None:
    config = SimulationConfig(material={"preset": "custom", "name": "sample", "n_real": 1.8, "n_imag": 0.2})
    material = resolve_particle_material(config.material)
    assert material.name == "sample"
    assert material.refractive_index == 1.8 + 0.2j


def test_geometry_summary_uses_real_dimensions_for_cube() -> None:
    config = SimulationConfig(
        geometry={
            "type": "cube",
            "size": {"diameter": 0.8, "width": 0.4, "depth": 0.6, "height": 1.2, "inner_diameter": 0.2, "shell_thickness": 0.1},
        }
    )
    summary = geometry_summary(config.geometry, config.array)
    assert summary["volume_um3"] == 0.4 * 0.6 * 1.2
    assert summary["projected_area_um2"] == 0.4 * 0.6
