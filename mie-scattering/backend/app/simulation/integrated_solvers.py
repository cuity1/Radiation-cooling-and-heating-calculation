from __future__ import annotations

from dataclasses import dataclass
from math import ceil, pi

import numpy as np

from app.models import SimulationConfig
from app.simulation.geometry import geometry_metrics
from app.simulation.materials import resolve_medium_material, resolve_particle_material, resolve_shell_core_material, substrate_index
from app.simulation.solver_limits import GRCWA_NG, RCWA_GRID_SIZE, RCWA_HARMONICS


@dataclass(frozen=True)
class EfficiencyGrid:
    qsca: np.ndarray
    qabs: np.ndarray
    qext: np.ndarray
    asymmetry: np.ndarray


def run_integrated_efficiency_grid(config: SimulationConfig, wavelengths: np.ndarray, diameters: np.ndarray, solver: str) -> EfficiencyGrid:
    if solver == "tmatrix":
        return _tmatrix_grid(config, wavelengths, diameters)
    if solver == "rcwa":
        return _rcwa_grid(config, wavelengths, diameters)
    if solver == "grcwa":
        return _grcwa_grid(config, wavelengths, diameters)
    raise ValueError(f"Unsupported integrated solver '{solver}'.")


def _tmatrix_grid(config: SimulationConfig, wavelengths: np.ndarray, diameters: np.ndarray) -> EfficiencyGrid:
    import treams

    particle = resolve_particle_material(config.material)
    medium = resolve_medium_material(config.material)
    shell_core = resolve_shell_core_material(config.material)
    eps_particle = particle.epsilon
    eps_medium = medium.epsilon
    eps_core = shell_core.epsilon

    qsca = np.zeros((len(diameters), len(wavelengths)), dtype=float)
    qabs = np.zeros_like(qsca)
    qext = np.zeros_like(qsca)
    asymmetry = np.full_like(qsca, np.nan)

    for d_index, diameter in enumerate(diameters):
        metrics = geometry_metrics(config.geometry, config.array, float(diameter))
        area = max(metrics.reference_area, 1e-18)
        radius = max(metrics.width, metrics.depth) / 2.0
        inner_radius = min(config.geometry.size.inner_diameter * (float(diameter) / max(config.geometry.size.diameter, 1e-12)) / 2.0, radius * 0.95)
        for w_index, wavelength in enumerate(wavelengths):
            k0 = 2.0 * pi / float(wavelength)
            size_parameter = abs(k0 * medium.refractive_index.real * radius)
            order = _multipole_order(size_parameter)
            if config.geometry.type == "sphere":
                tmatrix = treams.TMatrix.sphere(order, k0, radius, [eps_particle, eps_medium])
                csca = float(np.real(tmatrix.xs_sca_avg))
                cext = float(np.real(tmatrix.xs_ext_avg))
            elif config.geometry.type == "shell":
                tmatrix = treams.TMatrixC.cylinder([0.0], order, k0, [inner_radius, radius], [eps_core, eps_particle, eps_medium])
                csca = float(np.real(tmatrix.xw_sca_avg * metrics.height))
                cext = float(np.real(tmatrix.xw_ext_avg * metrics.height))
            elif config.geometry.type == "cylinder":
                tmatrix = treams.TMatrixC.cylinder([0.0], order, k0, radius, [eps_particle, eps_medium])
                csca = float(np.real(tmatrix.xw_sca_avg * metrics.height))
                cext = float(np.real(tmatrix.xw_ext_avg * metrics.height))
            else:
                raise ValueError("T-matrix adapter currently supports sphere, cylinder, and shell geometries.")
            csca = max(csca, 0.0)
            cext = max(cext, csca)
            qsca[d_index, w_index] = csca / area
            qext[d_index, w_index] = cext / area
            qabs[d_index, w_index] = max(qext[d_index, w_index] - qsca[d_index, w_index], 0.0)
    return EfficiencyGrid(qsca=qsca, qabs=qabs, qext=qext, asymmetry=asymmetry)


def _rcwa_grid(config: SimulationConfig, wavelengths: np.ndarray, diameters: np.ndarray) -> EfficiencyGrid:
    from rcwa import Crystal, Layer, LayerStack, Solver, Source

    particle = resolve_particle_material(config.material)
    medium = resolve_medium_material(config.material)
    substrate_n = substrate_index(config.substrate.type, config.substrate.metal_index_real, config.substrate.metal_index_imag)

    qsca = np.zeros((len(diameters), len(wavelengths)), dtype=float)
    qabs = np.zeros_like(qsca)
    qext = np.zeros_like(qsca)
    asymmetry = np.full_like(qsca, np.nan)

    for d_index, diameter in enumerate(diameters):
        metrics = geometry_metrics(config.geometry, config.array, float(diameter))
        layers = _periodic_eps_layers(config, float(diameter), RCWA_GRID_SIZE)
        for w_index, wavelength in enumerate(wavelengths):
            internal_layers = []
            for eps_grid, thickness in layers:
                crystal = Crystal([config.array.period_x, 0.0], [0.0, config.array.period_y], er=eps_grid, ur=np.ones_like(eps_grid, dtype=complex))
                internal_layers.append(Layer(thickness=thickness, crystal=crystal))
            incident = Layer(n=medium.refractive_index)
            transmission = Layer(n=substrate_n if config.substrate.type != "none" else medium.refractive_index)
            source = Source(wavelength=float(wavelength), layer=incident)
            solver = Solver(LayerStack(*internal_layers, incident_layer=incident, transmission_layer=transmission), source, (RCWA_HARMONICS, RCWA_HARMONICS))
            result = solver.solve()
            qext_value, qabs_value, qsca_value = _periodic_efficiencies(result["RTot"], result["TTot"], metrics)
            qext[d_index, w_index] = qext_value
            qabs[d_index, w_index] = qabs_value
            qsca[d_index, w_index] = qsca_value
    return EfficiencyGrid(qsca=qsca, qabs=qabs, qext=qext, asymmetry=asymmetry)


def _grcwa_grid(config: SimulationConfig, wavelengths: np.ndarray, diameters: np.ndarray) -> EfficiencyGrid:
    import grcwa

    particle = resolve_particle_material(config.material)
    medium = resolve_medium_material(config.material)
    substrate_n = substrate_index(config.substrate.type, config.substrate.metal_index_real, config.substrate.metal_index_imag)

    qsca = np.zeros((len(diameters), len(wavelengths)), dtype=float)
    qabs = np.zeros_like(qsca)
    qext = np.zeros_like(qsca)
    asymmetry = np.full_like(qsca, np.nan)

    for d_index, diameter in enumerate(diameters):
        metrics = geometry_metrics(config.geometry, config.array, float(diameter))
        layers = _periodic_eps_layers(config, float(diameter), RCWA_GRID_SIZE)
        for w_index, wavelength in enumerate(wavelengths):
            obj = grcwa.obj(GRCWA_NG, [config.array.period_x, 0.0], [0.0, config.array.period_y], 1.0 / float(wavelength), 0.0, 0.0, verbose=0)
            obj.Add_LayerUniform(1.0, medium.epsilon)
            for _eps_grid, thickness in layers:
                obj.Add_LayerGrid(thickness, RCWA_GRID_SIZE, RCWA_GRID_SIZE)
            obj.Add_LayerUniform(1.0, substrate_n * substrate_n if config.substrate.type != "none" else medium.epsilon)
            obj.Init_Setup(Gmethod=0)
            obj.MakeExcitationPlanewave(1.0, 0.0, 0.0, 0.0, order=0)
            obj.GridLayer_geteps(np.concatenate([eps_grid.reshape(-1) for eps_grid, _thickness in layers]))
            reflectance, transmittance = obj.RT_Solve(normalize=1)
            qext_value, qabs_value, qsca_value = _periodic_efficiencies(reflectance, transmittance, metrics)
            qext[d_index, w_index] = qext_value
            qabs[d_index, w_index] = qabs_value
            qsca[d_index, w_index] = qsca_value
    return EfficiencyGrid(qsca=qsca, qabs=qabs, qext=qext, asymmetry=asymmetry)


def _periodic_efficiencies(reflectance: complex, transmittance: complex, metrics) -> tuple[float, float, float]:
    reflected = float(max(np.real(reflectance), 0.0))
    transmitted = float(max(np.real(transmittance), 0.0))
    absorbed = float(max(1.0 - reflected - transmitted, 0.0))
    area_ratio = metrics.unit_cell_area / max(metrics.reference_area, 1e-18)
    qsca = reflected * area_ratio
    qabs = absorbed * area_ratio
    qext = qsca + qabs
    return qext, qabs, qsca


def _periodic_eps_layers(config: SimulationConfig, diameter: float, grid_size: int) -> list[tuple[np.ndarray, float]]:
    particle = resolve_particle_material(config.material)
    medium = resolve_medium_material(config.material)
    shell_core = resolve_shell_core_material(config.material)
    metrics = geometry_metrics(config.geometry, config.array, diameter)
    base = np.full((grid_size, grid_size), medium.epsilon, dtype=complex)
    period_x = config.array.period_x
    period_y = config.array.period_y
    x = (np.arange(grid_size) + 0.5) / grid_size * period_x - period_x / 2.0
    y = (np.arange(grid_size) + 0.5) / grid_size * period_y - period_y / 2.0
    xx, yy = np.meshgrid(x, y, indexing="ij")

    if config.geometry.type in {"cylinder", "shell"}:
        eps_grid = base.copy()
        outer = (xx / max(metrics.width / 2.0, 1e-12)) ** 2 + (yy / max(metrics.depth / 2.0, 1e-12)) ** 2 <= 1.0
        eps_grid[outer] = particle.epsilon
        if config.geometry.type == "shell":
            scale = diameter / max(config.geometry.size.diameter, 1e-12)
            inner_diameter = min(config.geometry.size.inner_diameter * scale, metrics.width * 0.95)
            inner = (xx / max(inner_diameter / 2.0, 1e-12)) ** 2 + (yy / max(inner_diameter / 2.0, 1e-12)) ** 2 <= 1.0
            eps_grid[inner] = shell_core.epsilon
        return [(eps_grid, max(metrics.height, 1e-6))]

    if config.geometry.type == "cube":
        eps_grid = base.copy()
        inside = (np.abs(xx) <= metrics.width / 2.0) & (np.abs(yy) <= metrics.depth / 2.0)
        eps_grid[inside] = particle.epsilon
        return [(eps_grid, max(metrics.height, 1e-6))]

    if config.geometry.type in {"sphere", "ellipsoid"}:
        layer_count = 5
        layers: list[tuple[np.ndarray, float]] = []
        z_edges = np.linspace(-metrics.height / 2.0, metrics.height / 2.0, layer_count + 1)
        for z0, z1 in zip(z_edges[:-1], z_edges[1:]):
            z = 0.5 * (z0 + z1)
            axial = max(0.0, 1.0 - (z / max(metrics.height / 2.0, 1e-12)) ** 2)
            radius_scale = axial**0.5
            eps_grid = base.copy()
            inside = (xx / max(metrics.width * radius_scale / 2.0, 1e-12)) ** 2 + (yy / max(metrics.depth * radius_scale / 2.0, 1e-12)) ** 2 <= 1.0
            eps_grid[inside] = particle.epsilon
            layers.append((eps_grid, max(float(z1 - z0), 1e-6)))
        return layers

    raise ValueError(f"Unsupported periodic geometry '{config.geometry.type}'.")


def _multipole_order(size_parameter: float) -> int:
    order = int(ceil(size_parameter + 4.0 * size_parameter ** (1.0 / 3.0) + 2.0))
    return max(3, min(order, 18))
