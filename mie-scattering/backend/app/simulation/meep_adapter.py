from __future__ import annotations

from typing import Any

from app.models import SimulationConfig


class MeepUnavailableError(RuntimeError):
    pass


def build_meep_geometry(config: SimulationConfig, diameter: float | None = None) -> list[Any]:
    """Build a Meep geometry list when Meep is installed.

    The project can run without Meep, so imports are intentionally local. This function
    provides the explicit adapter point for replacing the smart proxy with full FDTD.
    """
    try:
        import meep as mp
    except Exception as exc:  # pragma: no cover - depends on optional external package
        raise MeepUnavailableError("Meep is not installed. Install meep to use simulation.solver='meep'.") from exc

    size = config.geometry.size
    d = diameter if diameter is not None else size.diameter
    from app.simulation.materials import resolve_particle_material, resolve_shell_core_material

    particle = resolve_particle_material(config.material)
    shell_core = resolve_shell_core_material(config.material)
    medium = mp.Medium(index=particle.refractive_index.real)
    center = mp.Vector3()

    if config.geometry.type == "sphere":
        return [mp.Sphere(radius=d / 2.0, center=center, material=medium)]
    if config.geometry.type == "cylinder":
        return [mp.Cylinder(radius=d / 2.0, height=size.height, center=center, material=medium)]
    if config.geometry.type == "cube":
        return [mp.Block(size=mp.Vector3(d, d, d), center=center, material=medium)]
    if config.geometry.type == "ellipsoid":
        return [mp.Ellipsoid(size=mp.Vector3(d, size.width, size.height), center=center, material=medium)]

    outer = mp.Cylinder(radius=d / 2.0, height=size.height, center=center, material=medium)
    core = mp.Cylinder(radius=size.inner_diameter / 2.0, height=size.height * 1.02, center=center, material=mp.Medium(index=shell_core.refractive_index.real))
    return [outer, core]
