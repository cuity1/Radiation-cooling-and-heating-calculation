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

    # NumPy compatibility:
    # - Some environments may not expose np.trapezoid even on newer NumPy builds.
    # - np.trapz is widely available and sufficient here.
    numerator = np.trapz(I_BB * emissivity, wavelength)
    denominator = np.trapz(I_BB, wavelength)
    average_emissivity = numerator / denominator
    return average_emissivity


def calculate_convection_coefficient(
    wind_speed,
    delta_T,
    T_a,
    L_char: float = 0.025,
    surface_orientation: str = "horizontal_up",
):
    """计算考虑自然对流和强制对流的对流换热系数（Churchill-Usagi 混合法）

    针对水平铺设薄膜的自然对流进行了优化。
    特征长度默认取 0.025 m（对应 10cm x 10cm 方形样品）。
    对于水平面自然对流，L_char = A / P，典型值参考：
      - 10cm x 10cm 方形: L_char = 0.025 m
      - 20cm x 20cm 方形: L_char = 0.050 m
      - 50cm x 50cm 方形: L_char = 0.125 m

    强制对流使用 Churchill-Bernstein 关联式，适用于平板外部横掠流动。
    自然对流根据 surface_orientation 使用对应的经验关联式。

    参数：
        wind_speed: 风速 (m/s)
        delta_T: 表面与环境的温差 (K)，正值表示表面比空气热
        T_a: 环境空气温度 (K)
        L_char: 特征长度 (m)，默认 0.025 m（10cm x 10cm 方形样品）
        surface_orientation: 表面朝向，候选值：
            "horizontal_up"   - 水平面，向上加热（薄膜上表面向天空，Ra < 1e7 层流 / Ra >= 1e7 湍流）
            "horizontal_down" - 水平面，向下加热（冷表面）
            "vertical"        - 竖直面（Churchill-Chu 关联式）

    返回值单位：W/(m²·K)

    典型值参考（水平向上，L_char=0.025m, T_a=30°C）：
      wind=0 m/s, ΔT≈0   → h ≈ 3.5 W/m²·K（纯自然对流下限）
      wind=0 m/s, ΔT=5    → h ≈ 9.5 W/m²·K
      wind=0 m/s, ΔT=10   → h ≈ 11.8 W/m²·K
      wind=1 m/s          → h ≈ 19 W/m²·K
      wind=2 m/s          → h ≈ 26 W/m²·K
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

    # natural convection — use a smoothed buoyancy ΔT so h_nat does not
    # collapse to 0 (and then hit the output floor) exactly at ΔT=0, which
    # caused visible kinks in p_net vs T_film when latent heat was enabled.
    delta_T_buoy = float((float(delta_T) ** 2 + (0.15) ** 2) ** 0.5)
    Ra = max(1e-9, g * beta * delta_T_buoy * L_char**3 / (nu * alpha))

    ori = (surface_orientation or "horizontal_up").lower()
    if ori == "horizontal_up":
        # 水平面向上加热（薄膜表面向上，朝向天空）
        if Ra < 1e7:
            Nu_nat = 0.54 * Ra**0.25
        else:
            Nu_nat = 0.15 * Ra ** (1 / 3)
    elif ori == "horizontal_down":
        # 水平面向下加热（冷表面，浮力方向向下）
        # 系数约为向上加热的一半（Incropera & DeWitt）
        if Ra < 1e7:
            Nu_nat = 0.27 * Ra**0.25
        else:
            Nu_nat = 0.075 * Ra ** (1 / 3)
    else:
        # 竖直面（Churchill and Chu），适用于 Ra 全范围
        Nu_nat = 0.68 + 0.67 * (Ra ** 0.25) / (1.0 + (0.492 / Pr) ** (9.0 / 16.0)) ** (4.0 / 9.0)
        if Ra >= 1e9:
            Nu_nat = 0.825 + 0.387 * (Ra ** (1.0 / 6.0)) / (1.0 + (0.492 / Pr) ** (9.0 / 16.0)) ** (8.0 / 27.0)

    h_natural = Nu_nat * k_air / L_char

    # forced convection — Churchill-Bernstein 关联式（外部横掠平板流动）
    # 适用于整个 Re 范围（层流+湍流），是工程上最广泛使用的外部流关联式之一
    # Nu = 0.3 + (0.62*Re^0.5*Pr^(1/3)) / [1+(0.4/Pr)^(2/3)]^(1/4)
    #                   * [1 + (Re/282000)^(5/8)]^(4/5)
    if wind_speed > 1e-3:
        Re = max(1.0, wind_speed * L_char / nu)
        term1 = 0.62 * (Re**0.5) * (Pr ** (1.0 / 3.0))
        term2 = 1.0 + (0.4 / Pr) ** (2.0 / 3.0)
        term3 = 1.0 + (Re / 282000.0) ** (5.0 / 8.0)
        Nu_forced = (0.3 + term1 / (term2 ** 0.25)) * (term3 ** 0.8)
        h_forced = Nu_forced * k_air / L_char
    else:
        h_forced = 0.0

    n = 3
    h_conv = (h_natural**n + h_forced**n) ** (1 / n)
    # Soft floor only for numerical stability (avoid identically zero h).
    return max(0.05, float(h_conv))
