"""Physical models and helper computations."""

from __future__ import annotations

import numpy as np


def planck_lambda(wavelength, temperature):
    """黑体谱强度 I_BB(λ)。wavelength 单位: m, temperature 单位: K"""
    h = 6.62607015e-34
    c = 3.0e8
    k = 1.380649e-23
    numerator = 2 * h * c**2
    denominator = (wavelength**5) * (np.exp((h * c) / (wavelength * k * temperature)) - 1)
    return numerator / denominator


def calculate_average_emissivity(wavelength, emissivity, temperature):
    """计算平均发射率。wavelength单位为米"""
    I_BB = planck_lambda(wavelength, temperature)
    numerator = np.trapezoid(I_BB * emissivity, wavelength)
    denominator = np.trapezoid(I_BB, wavelength)
    average_emissivity = numerator / denominator
    return average_emissivity


def calculate_convection_coefficient(wind_speed, delta_T, T_a, L_char: float = 1.0):
    """计算考虑自然对流和强制对流的对流换热系数（Churchill-Usagi 混合法）

    返回值单位：W/(m²·K)
    """
    T_film = max(150.0, T_a + delta_T / 2)
    rho = 1.225 * (273.15 / T_film)
    mu = 1.81e-5 * (T_film / 273.15) ** 0.7
    k_air = 0.024 * (T_film / 273.15) ** 0.8
    cp = 1005
    nu = mu / rho
    alpha = k_air / (rho * cp)
    Pr = max(0.68, min(0.75, nu / alpha))

    g = 9.81
    beta = 1.0 / T_film

    # natural convection
    if abs(delta_T) > 1e-3:
        Ra = max(1e-9, g * beta * abs(delta_T) * L_char**3 / (nu * alpha))
        if Ra < 1e7:
            Nu_nat = 0.54 * Ra**0.25
        else:
            Nu_nat = 0.15 * Ra ** (1 / 3)
        h_natural = Nu_nat * k_air / L_char
    else:
        h_natural = 0.0

    # forced convection
    if wind_speed > 1e-3:
        Re = max(1.0, wind_speed * L_char / nu)
        if Re < 5e5:
            Nu_forced = 0.664 * Re**0.5 * Pr ** (1 / 3)
        else:
            Nu_forced = 0.037 * Re**0.8 * Pr ** (1 / 3)
        h_forced = Nu_forced * k_air / L_char
    else:
        h_forced = 0.0

    n = 3
    h_conv = (h_natural**n + h_forced**n) ** (1 / n)
    return max(1.0, float(h_conv))
