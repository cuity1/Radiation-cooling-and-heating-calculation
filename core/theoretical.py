"""Theoretical heating vs solar irradiance calculation."""

from __future__ import annotations

import numpy as np

from core.config import load_config
from core.spectrum import (
    load_and_interpolate_emissivity,
)


def main_theoretical_heating_vs_solar(
    file_paths: dict,
    angle_steps: int = 2000,
    skip_dialog: bool = True,
    *,
    t_a_min: float = -100.0,
    t_a_max: float = 100.0,
    t_a_points: int = 21,
    s_solar_min: float = 0.0,
    s_solar_max: float = 1200.0,
    s_solar_points: int = 49,
):
    """Compute theoretical heating power and return arrays for plotting.

    - angle_steps controls angular integration resolution (theta discretization count).
    - t_a_* and s_solar_* control the heatmap grid resolution/range.

    Notes:
    - The Web UI enforces an upper bound (<=200) for the grid size.
    """

    config = load_config(file_paths['config'])
    C1 = config['C1']
    C2 = config['C2']

    # grids (heatmap resolution)
    t_a_points_i = int(t_a_points)
    s_solar_points_i = int(s_solar_points)
    if t_a_points_i < 2:
        t_a_points_i = 2
    if s_solar_points_i < 2:
        s_solar_points_i = 2

    T_a_range = np.linspace(float(t_a_min), float(t_a_max), num=t_a_points_i)
    S_solar_range = np.linspace(float(s_solar_min), float(s_solar_max), num=s_solar_points_i)

    # Get solar absorptance from cooling power calculation logic
    from core.calculations import main_calculating_gui
    _, alpha_s, _ = main_calculating_gui(file_paths)
    # If reflectance is needed, use: R_sol = 1 - alpha_s
    R_sol = float(1.0 - alpha_s)

    # Load config for emissivity wavelength range
    config = load_config(file_paths['config'])
    WAVELENGTH_RANGE_EMISSIVITY = config['WAVELENGTH_RANGE_EMISSIVITY']

    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity'],
        wavelength_range=WAVELENGTH_RANGE_EMISSIVITY
    )

    data1 = np.column_stack((X, emissivityatm_interpolated))
    data2 = np.column_stack((X, emissivity_interpolated))
    data1[:, 0] *= 1000
    data2[:, 0] *= 1000

    theta1 = 0
    theta2 = np.pi / 2

    # Increase angular integration precision.
    # angle_steps is used as the discretization count for theta (0..pi/2).
    nth = int(angle_steps)
    if nth < 100:
        nth = 100
    if nth > 20000:
        nth = 20000

    dth = (theta2 - theta1) / (nth - 1)
    theta = np.linspace(theta1, theta2, nth)
    angle_factor = 2 * np.pi * np.sin(theta) * np.cos(theta) * dth

    lambda1 = data1[:, 0] * 1e-9
    lambda2 = data2[:, 0] * 1e-9

    dlam1 = data1[1, 0] - data1[0, 0] if len(data1) > 1 else 1
    dlam2 = data2[1, 0] - data2[0, 0] if len(data2) > 1 else 1

    results = np.zeros((len(T_a_range), len(S_solar_range)))

    # Precompute angular factor sum
    ang_sum = float(np.sum(angle_factor))

    # Use a representative mean angle for the legacy e_zmat average approximation
    cos_mean = float(np.cos(float(theta.mean())))
    if cos_mean == 0.0:
        cos_mean = 1e-9

    # e_zmat_avg depends only on atmosphere transmittance + angle, so we can precompute it.
    e_zmat_avg = float(np.mean(1 - np.power(data1[:, 1], 1 / cos_mean)))

    for i, Ta in enumerate(T_a_range):
        T = float(Ta) + 273.15

        exponent_film = np.minimum(C2 / (lambda2 * T), 700)
        u_b1ams = 1e9 * (lambda2**5) * (np.exp(exponent_film) - 1)
        u_bs = C1 / u_b1ams
        tempint_R3 = u_bs * data2[:, 1] * dlam2
        int_R3am = np.sum(tempint_R3)
        p_r = float(int_R3am) * ang_sum

        exponent_a = np.minimum(C2 / (lambda1 * T), 700)
        u_b1ams1 = 1e9 * (lambda1**5) * (np.exp(exponent_a) - 1)
        u_bs1 = C1 / u_b1ams1

        tempint_R1 = u_bs1 * data2[:, 1] * e_zmat_avg * dlam1
        int_R1am = np.sum(tempint_R1)
        p_a = float(int_R1am) * ang_sum

        # Vectorize over S_solar
        Q_solar = alpha_s * S_solar_range
        results[i, :] = Q_solar + p_a - p_r

    return {
        'results': results,
        'T_a_range': T_a_range,
        'S_solar_range': S_solar_range,
    }
