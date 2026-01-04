"""Theoretical heating vs solar irradiance calculation."""

from __future__ import annotations

import numpy as np

from core.config import load_config
from core.spectrum import (
    calculate_weighted_reflectance,
    filter_wavelength,
    interpolate_spectrum,
    load_and_interpolate_emissivity,
    load_reflectance,
    load_spectrum,
)


def calculate_R_sol(file_paths: dict, config: dict) -> float:
    reflectance_data = load_reflectance(file_paths['reflectance'])
    spectrum_data = load_spectrum(file_paths['spectrum'])
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']

    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)
    return float(R_sol)


def main_theoretical_heating_vs_solar(file_paths: dict, angle_steps: int = 2000, skip_dialog: bool = True):
    """Compute theoretical heating power and return arrays for plotting.

    Kept backward compatible with old calls that pass skip_dialog.
    """
    config = load_config(file_paths['config'])
    C1 = config['C1']
    C2 = config['C2']

    # grids
    T_a_range = np.linspace(-100, 100, num=21)
    S_solar_range = np.linspace(0, 1200, num=49)

    R_sol = calculate_R_sol(file_paths, config)
    alpha_s = 1 - R_sol

    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
    )

    data1 = np.column_stack((X, emissivityatm_interpolated))
    data2 = np.column_stack((X, emissivity_interpolated))
    data1[:, 0] *= 1000
    data2[:, 0] *= 1000

    theta1 = 0
    theta2 = np.pi / 2
    nth = 100
    dth = (theta2 - theta1) / (nth - 1)
    theta = np.linspace(theta1, theta2, nth)
    angle_factor = 2 * np.pi * np.sin(theta) * np.cos(theta) * dth

    lambda1 = data1[:, 0] * 1e-9
    lambda2 = data2[:, 0] * 1e-9

    dlam1 = data1[1, 0] - data1[0, 0] if len(data1) > 1 else 1
    dlam2 = data2[1, 0] - data2[0, 0] if len(data2) > 1 else 1

    results = np.zeros((len(T_a_range), len(S_solar_range)))

    for i, Ta in enumerate(T_a_range):
        T = Ta + 273.15

        exponent_film = np.minimum(C2 / (lambda2 * T), 700)
        u_b1ams = 1e9 * (lambda2**5) * (np.exp(exponent_film) - 1)
        u_bs = C1 / u_b1ams
        tempint_R3 = u_bs * data2[:, 1] * dlam2
        int_R3am = np.sum(tempint_R3)
        p_r = int_R3am * np.sum(angle_factor)

        exponent_a = np.minimum(C2 / (lambda1 * T), 700)
        u_b1ams1 = 1e9 * (lambda1**5) * (np.exp(exponent_a) - 1)
        u_bs1 = C1 / u_b1ams1

        e_zmat_avg = float(np.mean(1 - np.power(data1[:, 1], 1 / np.cos(theta.mean()))))
        tempint_R1 = u_bs1 * data2[:, 1] * e_zmat_avg * dlam1
        int_R1am = np.sum(tempint_R1)
        p_a = int_R1am * np.sum(angle_factor)

        for j, S in enumerate(S_solar_range):
            Q_solar = alpha_s * S
            p_heat = Q_solar + p_a - p_r
            results[i, j] = p_heat

    return {
        'results': results,
        'T_a_range': T_a_range,
        'S_solar_range': S_solar_range,
    }

