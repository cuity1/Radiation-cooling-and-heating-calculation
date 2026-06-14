from __future__ import annotations

from dataclasses import dataclass
from math import pi

from app.models import ArrayConfig, GeometryConfig


@dataclass(frozen=True)
class GeometryMetrics:
    effective_diameter: float
    equivalent_sphere_diameter: float
    reference_area: float
    width: float
    depth: float
    height: float
    volume: float
    projected_area: float
    anisotropy: float
    fill_factor: float
    array_count: int
    unit_cell_area: float


def geometry_metrics(geometry: GeometryConfig, array: ArrayConfig, scanned_diameter: float | None = None) -> GeometryMetrics:
    size = geometry.size
    diameter = scanned_diameter if scanned_diameter is not None else size.diameter
    scale = diameter / max(size.diameter, 1e-12) if scanned_diameter is not None else 1.0
    radius = diameter / 2.0

    if geometry.type == "sphere":
        width = diameter
        depth = diameter
        height = diameter
        volume = 4.0 / 3.0 * pi * radius**3
        area = pi * radius**2
        anisotropy = 1.0
    elif geometry.type == "cylinder":
        width = diameter
        depth = diameter
        height = size.height * scale
        volume = pi * radius**2 * height
        area = pi * radius**2
        anisotropy = max(0.6, min(1.8, height / max(diameter, 1e-9) + 0.5))
    elif geometry.type == "cube":
        width = size.width * scale
        depth = size.depth * scale
        height = size.height * scale
        volume = width * depth * height
        area = width * depth
        anisotropy = max(0.55, min(2.2, height / max((width + depth) / 2.0, 1e-9) + 0.45))
    elif geometry.type == "ellipsoid":
        width = diameter
        depth = size.depth * scale
        height = size.height * scale
        a = width / 2.0
        b = depth / 2.0
        c = height / 2.0
        volume = 4.0 / 3.0 * pi * a * b * c
        area = pi * a * b
        anisotropy = max(0.55, min(2.0, (a + b) / max(2.0 * c, 1e-9)))
    else:
        width = diameter
        depth = diameter
        height = size.height * scale
        inner_radius = min((size.inner_diameter * scale) / 2.0, radius * 0.95)
        volume = pi * (radius**2 - inner_radius**2) * height
        area = pi * radius**2
        anisotropy = max(0.7, min(1.7, height / max(diameter, 1e-9) + 0.65))

    array_count = array.count_x * array.count_y if array.enabled else 1
    period_area = array.period_x * array.period_y if array.enabled else area
    if array.enabled:
        fill = min(0.92, area / max(period_area, 1e-9))
    else:
        fill = 0.0
    equivalent_sphere_diameter = (6.0 * max(volume, 0.0) / pi) ** (1.0 / 3.0)
    reference_area = pi * (equivalent_sphere_diameter / 2.0) ** 2

    return GeometryMetrics(
        effective_diameter=diameter,
        equivalent_sphere_diameter=equivalent_sphere_diameter,
        reference_area=reference_area,
        width=width,
        depth=depth,
        height=height,
        volume=volume,
        projected_area=area,
        anisotropy=anisotropy,
        fill_factor=fill,
        array_count=array_count,
        unit_cell_area=period_area,
    )


def geometry_summary(geometry: GeometryConfig, array: ArrayConfig, scanned_diameter: float | None = None) -> dict[str, object]:
    metrics = geometry_metrics(geometry, array, scanned_diameter)
    return {
        "type": geometry.type,
        "effective_diameter_um": metrics.effective_diameter,
        "equivalent_sphere_diameter_um": metrics.equivalent_sphere_diameter,
        "width_um": metrics.width,
        "depth_um": metrics.depth,
        "height_um": metrics.height,
        "volume_um3": metrics.volume,
        "projected_area_um2": metrics.projected_area,
        "mie_reference_area_um2": metrics.reference_area,
        "anisotropy": metrics.anisotropy,
        "array_enabled": array.enabled,
        "array_count": metrics.array_count,
        "period_x_um": array.period_x,
        "period_y_um": array.period_y,
        "unit_cell_area_um2": metrics.unit_cell_area,
        "fill_factor": metrics.fill_factor,
    }
