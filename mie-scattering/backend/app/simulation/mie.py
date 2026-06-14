from __future__ import annotations

from dataclasses import dataclass
from math import pi

import numpy as np


@dataclass(frozen=True)
class MieResult:
    qext: float
    qsca: float
    qabs: float
    g: float


def mie_efficiencies(diameter_um: float, wavelength_um: float, particle_n: complex, medium_n: complex) -> MieResult:
    """Mie efficiencies for a homogeneous equivalent sphere.

    Wavelength is the vacuum wavelength in micrometers. The surrounding medium must be
    effectively lossless for the efficiency definitions to remain physically meaningful.
    """
    if diameter_um <= 0:
        raise ValueError("diameter_um must be positive")
    if wavelength_um <= 0:
        raise ValueError("wavelength_um must be positive")
    if medium_n.real <= 0:
        raise ValueError("medium refractive-index real part must be positive")
    if abs(medium_n.imag) > 1e-12:
        raise ValueError("absorbing media are not supported by the analytical Mie backend")

    x = pi * diameter_um * medium_n.real / wavelength_um
    m = particle_n / medium_n.real
    if x < 1e-3:
        return _rayleigh_limit(x, m)
    return _mie_series(x, m)


def miepython_efficiencies(diameter_um: float, wavelength_um: float, particle_n: complex, medium_n: complex) -> MieResult:
    """Mie efficiencies using the externally maintained miepython implementation."""
    if diameter_um <= 0:
        raise ValueError("diameter_um must be positive")
    if wavelength_um <= 0:
        raise ValueError("wavelength_um must be positive")
    if medium_n.real <= 0:
        raise ValueError("medium refractive-index real part must be positive")
    if abs(medium_n.imag) > 1e-12:
        raise ValueError("absorbing media are not supported by miepython efficiency normalization")

    try:
        import miepython
    except ModuleNotFoundError as exc:
        raise RuntimeError("miepython is not installed. Install miepython to use simulation.solver='mie'.") from exc

    qext, qsca, _qback, g = miepython.efficiencies(particle_n, diameter_um, wavelength_um, n_env=medium_n.real)
    qext_value = float(np.real(qext))
    qsca_value = float(max(np.real(qsca), 0.0))
    qext_value = float(max(qext_value, qsca_value))
    qabs_value = float(max(qext_value - qsca_value, 0.0))
    return MieResult(qext=qext_value, qsca=qsca_value, qabs=qabs_value, g=float(np.real(g)))


def _rayleigh_limit(x: float, m: complex) -> MieResult:
    alpha = (m * m - 1.0) / (m * m + 2.0)
    qsca = float((8.0 / 3.0) * x**4 * abs(alpha) ** 2)
    qext = float(max(4.0 * x * alpha.imag + qsca, qsca))
    qabs = float(max(qext - qsca, 0.0))
    return MieResult(qext=qext, qsca=qsca, qabs=qabs, g=0.0)


def _mie_series(x: float, m: complex) -> MieResult:
    nstop = max(1, int(round(x + 4.0 * x ** (1.0 / 3.0) + 2.0)))
    nmx = max(nstop + 16, int(abs(m * x)) + 16)
    z = m * x
    dlog = _log_derivatives(z, nmx)
    psi, chi = _riccati_bessel_real(x, nstop)
    xi = psi - 1j * chi

    qsca_sum = 0.0
    qext_sum = 0.0
    a_coeff: list[complex] = []
    b_coeff: list[complex] = []

    for n in range(1, nstop + 1):
        dn = dlog[n]
        n_over_x = n / x
        a_num = ((dn / m) + n_over_x) * psi[n] - psi[n - 1]
        a_den = ((dn / m) + n_over_x) * xi[n] - xi[n - 1]
        b_num = ((m * dn) + n_over_x) * psi[n] - psi[n - 1]
        b_den = ((m * dn) + n_over_x) * xi[n] - xi[n - 1]
        an = a_num / a_den
        bn = b_num / b_den
        weight = 2 * n + 1
        qsca_sum += weight * (abs(an) ** 2 + abs(bn) ** 2)
        qext_sum += weight * (an + bn).real
        a_coeff.append(an)
        b_coeff.append(bn)

    qsca = float(max((2.0 / x**2) * qsca_sum, 0.0))
    qext = float(max((2.0 / x**2) * qext_sum, qsca))
    qabs = float(max(qext - qsca, 0.0))
    g = _asymmetry_parameter(x, qsca, a_coeff, b_coeff)
    return MieResult(qext=qext, qsca=qsca, qabs=qabs, g=g)


def _log_derivatives(z: complex, nmx: int) -> np.ndarray:
    derivatives = np.zeros(nmx + 1, dtype=complex)
    for n in range(nmx, 0, -1):
        nz = n / z
        derivatives[n - 1] = nz - 1.0 / (derivatives[n] + nz)
    return derivatives


def _riccati_bessel_real(x: float, nstop: int) -> tuple[np.ndarray, np.ndarray]:
    psi = np.zeros(nstop + 1, dtype=float)
    chi = np.zeros(nstop + 1, dtype=float)
    psi[0] = np.sin(x)
    chi[0] = np.cos(x)
    if nstop >= 1:
        psi[1] = psi[0] / x - np.cos(x)
        chi[1] = chi[0] / x + np.sin(x)
    for n in range(1, nstop):
        factor = (2 * n + 1) / x
        psi[n + 1] = factor * psi[n] - psi[n - 1]
        chi[n + 1] = factor * chi[n] - chi[n - 1]
    return psi, chi


def _asymmetry_parameter(x: float, qsca: float, a_coeff: list[complex], b_coeff: list[complex]) -> float:
    if qsca <= 0:
        return 0.0
    nmax = len(a_coeff)
    total = 0.0
    for n in range(1, nmax):
        an = a_coeff[n - 1]
        bn = b_coeff[n - 1]
        an1 = a_coeff[n]
        bn1 = b_coeff[n]
        total += (n * (n + 2) / (n + 1)) * (an * an1.conjugate() + bn * bn1.conjugate()).real
    for n in range(1, nmax + 1):
        an = a_coeff[n - 1]
        bn = b_coeff[n - 1]
        total += ((2 * n + 1) / (n * (n + 1))) * (an * bn.conjugate()).real
    return float((4.0 / (x**2 * qsca)) * total)
