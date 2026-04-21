"""High-level calculation entry points (non-GUI).

These functions are called by GUI windows/threads.
Keep heavy plotting/UI imports out of here.
"""

from __future__ import annotations

import os

import numpy as np

from core.config import load_config
from core.physics import calculate_average_emissivity, calculate_convection_coefficient
from core.spectrum import (
    calculate_weighted_reflectance,
    filter_wavelength,
    interpolate_spectrum,
    load_and_interpolate_emissivity,
    load_reflectance,
    load_spectrum,
)


def create_declaration_file(default_directory: str, declare_file: str, email_contact: str) -> None:
    """Create declaration file in default directory."""
    try:
        if not os.path.exists(default_directory):
            os.makedirs(default_directory)
        file_path = os.path.join(default_directory, declare_file)

        content = f"""仅需要有两个测试数据：涉及可见光波段的反射率和涉及大气窗口的透过率。
在txt文件中仅出现数据，请不要存在任何汉字！软件会自动匹配数据
该软件免费分享，免费使用。如有疑问联系{email_contact}
诚信科研，使用此工具希望能够引用我的文章。"""

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f'声明文件已创建：{file_path}')
    except Exception as e:
        print(f'创建声明文件时出错: {e}')


def calculate_R_sol(file_paths: dict, config: dict) -> float:
    """Calculate the weighted average reflectance R_sol."""
    reflectance_data = load_reflectance(file_paths['reflectance'])
    spectrum_data = load_spectrum(file_paths['spectrum'])
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']

    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)
    return float(R_sol)


def _build_angle_grid(angle_steps: int) -> tuple[np.ndarray, np.ndarray]:
    """Return theta column vector and angle_factor column vector.

    angle_factor = 2π sinθ cosθ dθ
    """
    theta1 = 0.0
    theta2 = np.pi / 2
    nth = int(angle_steps)
    if nth < 10:
        nth = 10
    dth = (theta2 - theta1) / (nth - 1)
    theta = np.linspace(theta1, theta2 - dth, nth - 1).reshape(-1, 1)
    angle_factor = 2 * np.pi * np.sin(theta) * np.cos(theta) * dth
    return theta, angle_factor


def _planck_spectral_exitance(C1: float, C2: float, lam_m: np.ndarray, T: float) -> np.ndarray:
    """Numerically-stable Planck term used in legacy code."""
    exponent = C2 / (lam_m * T)
    exponent = np.minimum(exponent, 700)
    u_b1ams = 1e9 * (lam_m**5) * (np.exp(exponent) - 1)
    with np.errstate(divide='ignore', invalid='ignore'):
        u_bs = np.divide(C1, u_b1ams, out=np.zeros_like(u_b1ams), where=u_b1ams != 0)
    return u_bs


def _radiative_terms(
    C1: float,
    C2: float,
    lam1_m: np.ndarray,
    lam2_m: np.ndarray,
    tmat: np.ndarray,
    e_smat: np.ndarray,
    T_a: float,
    T_s: float,
    angle_factor: np.ndarray,
    theta: np.ndarray,
    dlam1_nm: float,
    dlam2_nm: float,
) -> tuple[float, float]:
    """Compute p_r (surface -> space) and p_a (atmosphere -> surface)."""
    u_bs_surface = _planck_spectral_exitance(C1, C2, lam2_m, T_s)
    u_bs_atm = _planck_spectral_exitance(C1, C2, lam1_m, T_a)

    tempint_R3 = u_bs_surface * e_smat * dlam2_nm
    int_R3am = float(np.sum(tempint_R3))
    p_r = float(np.sum(angle_factor * int_R3am))

    with np.errstate(divide='ignore', invalid='ignore'):
        e_zmat = 1.0 - np.power(tmat, 1.0 / np.cos(theta))  # (Nθ, Nλ)
        e_zmat = np.nan_to_num(e_zmat, nan=0.0, posinf=0.0, neginf=0.0)

    tempint_R1 = u_bs_atm * e_smat * e_zmat * dlam1_nm
    int_R1am_theta = np.sum(tempint_R1, axis=1)
    p_a = float(np.sum(angle_factor.flatten() * int_R1am_theta))

    return p_r, p_a


def _phase_power(
    T_film_c: float,
    phase_temp_c: float | None,
    phase_power_wm2: float,
    phase_half_width_c: float,
) -> float:
    """Phase-change additional cooling power (ramp then plateau)."""
    if phase_temp_c is None:
        return 0.0
    w = float(phase_half_width_c)
    if w <= 0:
        return 0.0

    if T_film_c <= phase_temp_c:
        return 0.0

    if T_film_c >= phase_temp_c + w:
        return float(phase_power_wm2)

    frac = (T_film_c - phase_temp_c) / w
    frac = max(0.0, min(1.0, frac))
    return float(phase_power_wm2) * frac


def _calculate_latent_heat_power(
    T_surface_K: float,  # 材料表面温度 (K)
    T_ambient_K: float,  # 环境温度 (K)
    RH: float,  # 环境相对湿度 (0-1)
    h_m: float | None = None,  # 质量传递系数 (m/s)，如果为None则从对流系数计算
    h_conv: float | None = None,  # 总对流换热系数 (W/(m²·K))，Lewis 类比下用于推算 h_m
) -> float:
    """
    计算单位面积潜热通量对应的等效功率 (W/m²)。

    用水蒸气密度差驱动质量通量：Δρ = ρ_sat(T_s)/T_s 界面饱和 − ρ_v,∞（主流区，由 RH 与 T_amb 确定）。
    Q = m_dot · L_v(T_s)；m_dot>0 为蒸发（增强表观制冷），m_dot<0 为凝结放热（削弱制冷）。

    不再对「P_sat ≤ P_v」做硬截断或对 m_dot 做 max(0,·)，避免与 Δρ 判据冲突而在曲线上产生折点/凹陷。
    """
    # 物理常数
    R_v = 461.5  # 水蒸气气体常数 (J/(kg·K))
    
    # 转换为摄氏度用于 Tetens 方程
    T_surface_C = T_surface_K - 273.15
    T_ambient_C = T_ambient_K - 273.15
    
    # Tetens 方程计算饱和水蒸气压力 (kPa)
    # P_sat(T) = 0.61078 × exp(17.27 × T / (T + 237.3))
    def p_sat_kpa(T_C: float) -> float:
        if T_C <= -50.0:
            return 0.0
        return 0.61078 * np.exp(17.27 * T_C / (T_C + 237.3))
    
    # 计算饱和水蒸气压力
    P_sat_surface = p_sat_kpa(T_surface_C)  # kPa
    P_sat_ambient = p_sat_kpa(T_ambient_C)  # kPa
    
    # 计算实际水蒸气压力（环境主流区）
    P_v = RH * P_sat_ambient  # kPa

    # 转换为 Pa
    P_sat_surface_Pa = P_sat_surface * 1000.0
    P_v_Pa = P_v * 1000.0

    # 水蒸气密度差驱动质量通量（与界面饱和、主流区水汽分压一致）
    # 不再使用「P_sat_surface <= P_v 则直接返回 0」：该条件与下面 ρ 公式在 T_s ≠ T_a 时不总等价，
    # 会在露点附近和另一温度区间产生非物理的折线/凹陷；凝结时 Δρ<0，Q_latent 为负（加热表面）。
    rho_v_sat = P_sat_surface_Pa / (R_v * T_surface_K)  # 界面饱和水蒸气密度
    rho_v_ambient = P_v_Pa / (R_v * T_ambient_K)  # 环境水蒸气密度
    
    # 计算质量传递系数
    if h_m is None:
        if h_conv is not None and h_conv > 0:
            # 从对流换热系数计算质量传递系数
            # 使用 Lewis 数关系：h_m = h_conv / (ρ_air * cp_air * Le^(2/3))
            T_film = (T_surface_K + T_ambient_K) / 2.0  # 膜温度
            cp_air = 1005.0  # 空气比热容 (J/(kg·K))
            rho_air = 1.225 * (273.15 / T_film)  # 空气密度 (kg/m³)，理想气体近似
            Le = 0.84  # Lewis 数（水蒸气–空气系统实测值约 0.84）
            # 与 physics.calculate_convection_coefficient 的数值下限一致，避免 h_m 过小
            h_conv_effective = max(float(h_conv), 0.05)
            h_m = h_conv_effective / (rho_air * cp_air * (Le ** (2.0 / 3.0)))
        else:
            # 默认值（保守估计，适用于自然对流）
            h_m = 0.005  # m/s（修正后的默认值，更保守）
    
    # 质量通量 (kg/(m²·s))；可正（蒸发）可负（凝结）
    m_dot = h_m * (rho_v_sat - rho_v_ambient)
    
    # 计算温度相关的蒸发潜热 (J/kg)
    # 使用经验公式，考虑温度依赖性
    if T_surface_C < 0:
        # 冰的升华潜热（近似）
        L_v = 2.501e6
    elif T_surface_C <= 100:
        # 0-100°C 范围内的经验公式
        # L_v(T) = (2501.0 - 2.36*T - 0.0016*T²) × 1000
        L_v = (2501.0 - 2.36 * T_surface_C - 0.0016 * T_surface_C**2) * 1000
    else:
        # 超过100°C的近似（不常见，但提供连续性）
        L_v = (2257.0 - 0.5 * (T_surface_C - 100)) * 1000
    
    # 计算蒸发潜热功率 (W/m²)
    Q_latent = m_dot * L_v
    
    return float(Q_latent)


def main_calculating_gui(file_paths: dict):
    required_files = ['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity']
    for key in required_files:
        if key not in file_paths or not file_paths[key]:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{key}")

    config = load_config(file_paths['config'])

    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    WAVELENGTH_RANGE_EMISSIVITY = config['WAVELENGTH_RANGE_EMISSIVITY']
    VISIABLE_RANGE = config['VISIABLE_RANGE']

    reflectance_data = load_reflectance(file_paths['reflectance'])
    spectrum_data = load_spectrum(file_paths['spectrum'])

    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)

    ref_wavelength1, reflectance_values1 = filter_wavelength(reflectance_data, 0, 1, VISIABLE_RANGE)
    spec_wavelength1, spectrum_values1 = filter_wavelength(spectrum_data, 0, 1, VISIABLE_RANGE)

    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    interpolated_spectrum1 = interpolate_spectrum(ref_wavelength1, spec_wavelength1, spectrum_values1)

    R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)
    R_sol1 = calculate_weighted_reflectance(reflectance_values1, interpolated_spectrum1, ref_wavelength1)

    T_a = config['T_a1'] + 273.15
    WAVELENGTH_RANGE_EMISSIVITY = config['WAVELENGTH_RANGE_EMISSIVITY']
    data = np.loadtxt(file_paths['emissivity'])
    wavelength_um = data[:, 0]
    emissivity = data[:, 1]
    # 使用发射率波长范围过滤
    filtered_wavelength_um, filtered_emissivity = filter_wavelength(
        np.column_stack((wavelength_um, emissivity)), 0, 1, WAVELENGTH_RANGE_EMISSIVITY
    )
    wavelength_m = filtered_wavelength_um * 1e-6
    avg_emissivity = calculate_average_emissivity(wavelength_m, filtered_emissivity, T_a)

    # Compute absorptance: alpha = 1 - (R + T).
    # If transmittance is available AND we have the original reflectance separately
    # (not the R+T combined file), compute T_sol and correct absorptance.
    # When only transmittance exists without original R, we cannot correctly separate
    # R and T, so alpha = 1 - R_combined is used as before (pre-existing limitation).
    alpha_sol = 1.0 - float(R_sol)
    alpha_sol1 = 1.0 - float(R_sol1)

    has_original_r = 'reflectance_original' in file_paths and file_paths['reflectance_original']
    if has_original_r and 'transmittance' in file_paths and file_paths['transmittance']:
        trans_data = load_reflectance(file_paths['transmittance'])
        trans_wavelength, trans_values = filter_wavelength(trans_data, 0, 1, WAVELENGTH_RANGE)
        trans_wavelength1, trans_values1 = filter_wavelength(trans_data, 0, 1, VISIABLE_RANGE)

        trans_interp = interpolate_spectrum(ref_wavelength, trans_wavelength, trans_values)
        trans_interp1 = interpolate_spectrum(ref_wavelength1, trans_wavelength1, trans_values1)

        T_sol_weighted = float(calculate_weighted_reflectance(trans_interp, interpolated_spectrum, ref_wavelength))
        T_sol1_weighted = float(calculate_weighted_reflectance(trans_interp1, interpolated_spectrum1, ref_wavelength1))

        alpha_sol = 1.0 - (float(R_sol) + T_sol_weighted)
        alpha_sol1 = 1.0 - (float(R_sol1) + T_sol1_weighted)

    return avg_emissivity, alpha_sol, alpha_sol1


def main_cooling_gui(
    file_paths: dict,
    *,
    angle_steps: int = 2000,
    h_cond_wm2k: float | None = None,
    enable_natural_convection: bool = False,
    skip_dialog: bool = False,
    debug: bool = False,
    phase_temp_c: float | None = None,
    phase_power_wm2: float = 0.0,
    phase_half_width_c: float = 0.0,
    enable_latent_heat: bool = False,
    relative_humidity: float | None = None,
    wet_fraction: float = 1.0,
):
    required_files = ['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity']
    for key in required_files:
        if key not in file_paths or not file_paths[key]:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{key}")

    config = load_config(file_paths['config'])

    DEFAULT_DIRECTORY = config['DEFAULT_DIRECTORY']
    DECLARE_FILE = config['DECLARE_FILE']
    EMAIL_CONTACT = config['EMAIL_CONTACT']

    C1 = config['C1']
    C2 = config['C2']
    T_a1 = config['T_a1']
    T_filmmin = config['T_filmmin']
    T_filmmax = config['T_filmmax']
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    WAVELENGTH_RANGE_EMISSIVITY = config['WAVELENGTH_RANGE_EMISSIVITY']
    VISIABLE_RANGE = config['VISIABLE_RANGE']
    HC_VALUES = config['HC_VALUES']
    S_solar = float(config['S_solar'])

    # Load combined (R+T) or pure R data for absorptance calculation
    reflectance_data = load_reflectance(file_paths['reflectance'])
    spectrum_data = load_spectrum(file_paths['spectrum'])

    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)

    ref_wavelength1, reflectance_values1 = filter_wavelength(reflectance_data, 0, 1, VISIABLE_RANGE)
    spec_wavelength1, spectrum_values1 = filter_wavelength(spectrum_data, 0, 1, VISIABLE_RANGE)

    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    interpolated_spectrum1 = interpolate_spectrum(ref_wavelength1, spec_wavelength1, spectrum_values1)

    # Separate reflectance-only and transmittance for correct output values.
    # absorptance = 1 - R - T is computed from the original reflectance and
    # the separately loaded transmittance (interpolated onto the R wavelength grid).
    has_original_r = 'reflectance_original' in file_paths and file_paths['reflectance_original']
    has_trans = 'transmittance' in file_paths and file_paths['transmittance']

    R_sol_reflectance_only = None
    R_sol1_reflectance_only = None
    T_sol = 0.0
    T_sol1 = 0.0
    T_sol_weighted = 0.0
    T_sol1_weighted = 0.0

    if has_original_r:
        reflectance_orig_data = load_reflectance(file_paths['reflectance_original'])
        ref_orig_wl, ref_orig_vals = filter_wavelength(reflectance_orig_data, 0, 1, WAVELENGTH_RANGE)
        ref_orig_wl1, ref_orig_vals1 = filter_wavelength(reflectance_orig_data, 0, 1, VISIABLE_RANGE)

        interp_orig = interpolate_spectrum(ref_orig_wl, spec_wavelength, spectrum_values)
        interp_orig1 = interpolate_spectrum(ref_orig_wl1, spec_wavelength1, spectrum_values1)

        R_sol_reflectance_only = float(calculate_weighted_reflectance(ref_orig_vals, interp_orig, ref_orig_wl))
        R_sol1_reflectance_only = float(calculate_weighted_reflectance(ref_orig_vals1, interp_orig1, ref_orig_wl1))

        if has_trans:
            trans_data = load_reflectance(file_paths['transmittance'])
            trans_wl, trans_vals = filter_wavelength(trans_data, 0, 1, WAVELENGTH_RANGE)
            trans_wl1, trans_vals1 = filter_wavelength(trans_data, 0, 1, VISIABLE_RANGE)

            trans_interp = interpolate_spectrum(ref_orig_wl, trans_wl, trans_vals)
            trans_interp1 = interpolate_spectrum(ref_orig_wl1, trans_wl1, trans_vals1)

            T_sol_weighted = float(calculate_weighted_reflectance(trans_interp, interp_orig, ref_orig_wl))
            T_sol1_weighted = float(calculate_weighted_reflectance(trans_interp1, interp_orig1, ref_orig_wl1))

            T_sol = T_sol_weighted
            T_sol1 = T_sol1_weighted
    else:
        # No separate reflectance; use the combined (R+T) file for R_only as before
        R_sol_reflectance_only = float(calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength))
        R_sol1_reflectance_only = float(calculate_weighted_reflectance(reflectance_values1, interpolated_spectrum1, ref_wavelength1))
        if has_trans:
            trans_data = load_reflectance(file_paths['transmittance'])
            trans_wl, trans_vals = filter_wavelength(trans_data, 0, 1, WAVELENGTH_RANGE)
            trans_wl1, trans_vals1 = filter_wavelength(trans_data, 0, 1, VISIABLE_RANGE)

            trans_interp = interpolate_spectrum(ref_wavelength, trans_wl, trans_vals)
            trans_interp1 = interpolate_spectrum(ref_wavelength1, trans_wl1, trans_vals1)

            T_sol_weighted = float(calculate_weighted_reflectance(trans_interp, interpolated_spectrum, ref_wavelength))
            T_sol1_weighted = float(calculate_weighted_reflectance(trans_interp1, interpolated_spectrum1, ref_wavelength1))

            T_sol = T_sol_weighted
            T_sol1 = T_sol1_weighted

    # Absorptance = 1 - R - T (uses the weighted R and T computed above)
    if R_sol_reflectance_only is not None:
        alpha_sol = 1.0 - (R_sol_reflectance_only + T_sol_weighted)
        alpha_sol1 = 1.0 - (R_sol1_reflectance_only + T_sol1_weighted)
    else:
        alpha_sol = 1.0 - float(calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength))
        alpha_sol1 = 1.0 - float(calculate_weighted_reflectance(reflectance_values1, interpolated_spectrum1, ref_wavelength1))

    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity'],
        wavelength_range=WAVELENGTH_RANGE_EMISSIVITY
    )
    data1 = np.column_stack((X, emissivityatm_interpolated))
    data2 = np.column_stack((X, emissivity_interpolated))
    data1[:, 0] *= 1000
    data2[:, 0] *= 1000

    T_a = T_a1 + 273.15
    T_film = np.arange(T_filmmin, T_filmmax, 1)
    if T_film.size == 0:
        raise ValueError(
            "T_film is empty. Please check config values: T_filmmin, T_filmmax (must satisfy T_filmmin < T_filmmax)."
            f" Got T_filmmin={T_filmmin}, T_filmmax={T_filmmax}."
        )
    T_sll = T_film + 273.15

    # 使用发射率波长范围过滤
    data = np.loadtxt(file_paths['emissivity'])
    wavelength_um = data[:, 0]
    emissivity = data[:, 1]
    filtered_wavelength_um, filtered_emissivity = filter_wavelength(
        np.column_stack((wavelength_um, emissivity)), 0, 1, WAVELENGTH_RANGE_EMISSIVITY
    )
    wavelength_m = filtered_wavelength_um * 1e-6
    avg_emissivity = calculate_average_emissivity(wavelength_m, filtered_emissivity, T_a)

    theta, angle_factor = _build_angle_grid(angle_steps)

    lam1_m = data1[:, 0] * 1e-9
    lam2_m = data2[:, 0] * 1e-9
    tmat = data1[:, 1]
    e_smat = data2[:, 1]

    dlam1 = data1[1, 0] - data1[0, 0] if len(data1) > 1 else 1
    dlam2 = data2[1, 0] - data2[0, 0] if len(data2) > 1 else 1

    alpha_s = alpha_sol  # Use the computed absorptance (1 - R - T)
    results = np.zeros((len(T_film), len(HC_VALUES)))

    for hc_index, h_extra in enumerate(HC_VALUES):
        for i, T_s_current in enumerate(T_sll):
            p_r, p_a = _radiative_terms(
                C1,
                C2,
                lam1_m,
                lam2_m,
                tmat,
                e_smat,
                T_a=T_a,
                T_s=float(T_s_current),
                angle_factor=angle_factor,
                theta=theta,
                dlam1_nm=dlam1,
                dlam2_nm=dlam2,
            )

            delta_T = float(T_s_current - T_a)  # K
            if enable_natural_convection:
                h_nat = calculate_convection_coefficient(
                    wind_speed=0.0, delta_T=delta_T, T_a=T_a,
                    L_char=0.025, surface_orientation="horizontal_up"
                )
            else:
                h_nat = 0.0

            h_total = float(h_nat + float(h_extra))
            Q_conv = float(h_total * (T_a1 - T_film[i]))

            Q_solar = float(alpha_s * S_solar)
            P_phase = _phase_power(
                T_film_c=float(T_film[i]),
                phase_temp_c=phase_temp_c,
                phase_power_wm2=phase_power_wm2,
                phase_half_width_c=phase_half_width_c,
            )

            # 计算蒸发潜热功率
            if enable_latent_heat and relative_humidity is not None:
                # 处理相对湿度输入（支持 0-1 或 0-100 范围）
                RH_normalized = float(relative_humidity) / 100.0 if relative_humidity > 1.0 else float(relative_humidity)
                RH_normalized = max(0.0, min(1.0, RH_normalized))  # 确保在 0-1 范围内
                Q_latent = _calculate_latent_heat_power(
                    T_surface_K=float(T_s_current),
                    T_ambient_K=T_a,
                    RH=RH_normalized,
                    # Lewis 类比：质量边界层与总对流热阻一致，使用 h_nat + h_extra（与 Q_conv 同一套 h_total）
                    h_conv=float(h_total),
                )
                wf = float(wet_fraction)
                wf = max(0.0, min(1.0, wf))
                Q_latent = float(Q_latent) * wf
            else:
                Q_latent = 0.0

            p_net = float(p_r - p_a - Q_conv - Q_solar + P_phase + Q_latent)

            if debug:
                print(f"--- T_film: {T_film[i]:.2f}°C, h_extra: {float(h_extra):.2f} W/m²K ---")
                print(f"  p_r (向外辐射): {p_r:.4f} W/m²")
                print(f"  p_a (大气辐射): {p_a:.4f} W/m²")
                print(
                    f"  Q_conv (对流换热): {Q_conv:.4f} W/m² (h_nat={h_nat:.3f}, h_total={h_total:.3f})"
                )
                print(f"  Q_solar (太阳吸收): {Q_solar:.4f} W/m²")
                print(f"  P_phase (相变功率): {P_phase:.4f} W/m²")
                print(f"  Q_latent (蒸发潜热): {Q_latent:.4f} W/m²")
                print(f"  p_net (净制冷功率): {p_net:.4f} W/m²")
                print('-' * 50 + '\n')

            results[i, hc_index] = p_net

    idx_zero_diff = int(np.argmin(np.abs(T_film - T_a1)))
    cooling_power_zero_diff = results[idx_zero_diff, :]

    create_declaration_file(DEFAULT_DIRECTORY, DECLARE_FILE, EMAIL_CONTACT)

    if skip_dialog:
        return {
            'avg_emissivity': avg_emissivity,
            'R_sol': float(alpha_sol),
            'R_sol1': float(alpha_sol1),
            'R_sol_reflectance_only': float(R_sol_reflectance_only) if R_sol_reflectance_only is not None else float(calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)),
            'R_sol1_reflectance_only': float(R_sol1_reflectance_only) if R_sol1_reflectance_only is not None else float(calculate_weighted_reflectance(reflectance_values1, interpolated_spectrum1, ref_wavelength1)),
            'T_sol': float(T_sol),
            'T_sol1': float(T_sol1),
            'Power_0': float(cooling_power_zero_diff[0]),
            'results': results,
            'T_film': T_film,
            'T_a1': T_a1,
            'HC_VALUES': HC_VALUES,
            'phase_temp_c': phase_temp_c,
            'phase_power_wm2': phase_power_wm2,
            'phase_half_width_c': phase_half_width_c,
            'enable_natural_convection': bool(enable_natural_convection),
            'enable_latent_heat': bool(enable_latent_heat),
            'relative_humidity': float(relative_humidity) if relative_humidity is not None else None,
            'wet_fraction': float(wet_fraction),
        }

    return avg_emissivity, float(alpha_sol), float(alpha_sol1), float(cooling_power_zero_diff[0])


def main_power_components_gui(
    file_paths: dict,
    *,
    angle_steps: int = 2000,
    h_cond_wm2k: float = 5.0,
    enable_natural_convection: bool = False,
    phase_temp_c: float | None = None,
    phase_power_wm2: float = 0.0,
    phase_half_width_c: float = 0.0,
    enable_latent_heat: bool = False,
    relative_humidity: float | None = None,
    wet_fraction: float = 1.0,
):
    """Calculate all radiative/convective power components for plotting."""
    required_files = ['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity']
    for key in required_files:
        if key not in file_paths or not file_paths[key]:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{key}")

    config = load_config(file_paths['config'])

    C1 = config['C1']
    C2 = config['C2']
    T_a1 = config['T_a1']
    T_filmmin = config['T_filmmin']
    T_filmmax = config['T_filmmax']
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    WAVELENGTH_RANGE_EMISSIVITY = config['WAVELENGTH_RANGE_EMISSIVITY']
    S_solar = float(config['S_solar'])

    spectrum_data = load_spectrum(file_paths['spectrum'])

    # Use original reflectance if available, otherwise fall back to the combined (R+T) file.
    if 'reflectance_original' in file_paths and file_paths['reflectance_original']:
        reflectance_data = load_reflectance(file_paths['reflectance_original'])
    else:
        reflectance_data = load_reflectance(file_paths['reflectance'])

    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    R_sol = float(calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength))

    # Compute absorptance = 1 - R - T (load transmittance separately only if original R is available)
    alpha_s = 1.0 - R_sol
    has_original_r = 'reflectance_original' in file_paths and file_paths['reflectance_original']
    if has_original_r and 'transmittance' in file_paths and file_paths['transmittance']:
        trans_data = load_reflectance(file_paths['transmittance'])
        trans_wl, trans_vals = filter_wavelength(trans_data, 0, 1, WAVELENGTH_RANGE)
        trans_interp = interpolate_spectrum(ref_wavelength, trans_wl, trans_vals)
        T_sol_weighted = float(calculate_weighted_reflectance(trans_interp, interpolated_spectrum, ref_wavelength))
        alpha_s = 1.0 - (R_sol + T_sol_weighted)

    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity'],
        wavelength_range=WAVELENGTH_RANGE_EMISSIVITY
    )
    data1 = np.column_stack((X, emissivityatm_interpolated))
    data2 = np.column_stack((X, emissivity_interpolated))
    data1[:, 0] *= 1000
    data2[:, 0] *= 1000

    T_a = T_a1 + 273.15
    T_film = np.arange(T_filmmin, T_filmmax, 1)
    T_sll = T_film + 273.15

    theta, angle_factor = _build_angle_grid(angle_steps)

    lam1_m = data1[:, 0] * 1e-9
    lam2_m = data2[:, 0] * 1e-9
    tmat = data1[:, 1]
    e_smat = data2[:, 1]

    dlam1 = data1[1, 0] - data1[0, 0] if len(data1) > 1 else 1
    dlam2 = data2[1, 0] - data2[0, 0] if len(data2) > 1 else 1

    alpha_s = 1 - R_sol

    components = {
        'p_r': [],
        'p_a': [],
        'Q_conv': [],
        'Q_nat': [],
        'Q_cond': [],
        'P_solar': [],  # 太阳辐照度 (W/m²)
        'Q_solar': [],  # 太阳吸收功率 (W/m²) = alpha_s * P_solar
        'P_phase': [],
        'Q_latent': [],  # 蒸发潜热功率 (W/m²)
        'p_net': [],
        'h_nat': [],
        'h_total': [],
    }

    for i, T_s_current in enumerate(T_sll):
        p_r, p_a = _radiative_terms(
            C1,
            C2,
            lam1_m,
            lam2_m,
            tmat,
            e_smat,
            T_a=T_a,
            T_s=float(T_s_current),
            angle_factor=angle_factor,
            theta=theta,
            dlam1_nm=dlam1,
            dlam2_nm=dlam2,
        )

        delta_T = float(T_s_current - T_a)
        if enable_natural_convection:
            h_nat = float(
                calculate_convection_coefficient(
                    wind_speed=0.0, delta_T=delta_T, T_a=T_a,
                    L_char=0.025, surface_orientation="horizontal_up"
                )
            )
        else:
            h_nat = 0.0

        h_total = float(h_cond_wm2k + h_nat)

        # Heat flux decomposition
        # Note: use (T_a1 - T_film) to stay consistent with existing sign convention
        Q_nat = float(h_nat * (T_a1 - T_film[i]))
        Q_cond = float(h_cond_wm2k * (T_a1 - T_film[i]))
        Q_conv = float((Q_nat + Q_cond))

        P_solar = float(S_solar)  # 太阳辐照度 (W/m²)
        Q_solar = float(alpha_s * S_solar)  # 太阳吸收功率 (W/m²)
        P_phase = _phase_power(
            T_film_c=float(T_film[i]),
            phase_temp_c=phase_temp_c,
            phase_power_wm2=phase_power_wm2,
            phase_half_width_c=phase_half_width_c,
        )

        # 计算蒸发潜热功率
        if enable_latent_heat and relative_humidity is not None:
            # 处理相对湿度输入（支持 0-1 或 0-100 范围）
            RH_normalized = float(relative_humidity) / 100.0 if relative_humidity > 1.0 else float(relative_humidity)
            RH_normalized = max(0.0, min(1.0, RH_normalized))  # 确保在 0-1 范围内
            Q_latent = _calculate_latent_heat_power(
                T_surface_K=float(T_s_current),
                T_ambient_K=T_a,
                RH=RH_normalized,
                # 与主制冷路径一致：用总对流系数驱动 Lewis 类比下的 h_m
                h_conv=float(h_total),
            )
            wf = float(wet_fraction)
            wf = max(0.0, min(1.0, wf))
            Q_latent = float(Q_latent) * wf
        else:
            Q_latent = 0.0

        p_net = float(p_r - p_a - Q_conv - Q_solar + P_phase + Q_latent)

        components['p_r'].append(p_r)
        components['p_a'].append(p_a)
        components['Q_conv'].append(Q_conv)
        components['Q_nat'].append(Q_nat)
        components['Q_cond'].append(Q_cond)
        components['P_solar'].append(P_solar)
        components['Q_solar'].append(Q_solar)
        components['P_phase'].append(P_phase)
        components['Q_latent'].append(Q_latent)
        components['p_net'].append(p_net)
        components['h_nat'].append(h_nat)
        components['h_total'].append(h_total)

    return {
        'components': {k: np.array(v) for k, v in components.items()},
        'T_film': T_film,
        'T_a1': T_a1,
        'enable_natural_convection': bool(enable_natural_convection),
        'enable_latent_heat': bool(enable_latent_heat),
        'relative_humidity': float(relative_humidity) if relative_humidity is not None else None,
        'wet_fraction': float(wet_fraction),
    }


def main_heating_gui(
    file_paths: dict,
    *,
    angle_steps: int = 2000,
    enable_natural_convection: bool = False,
    skip_dialog: bool = False,
    debug: bool = False,
    phase_temp_c: float | None = None,
    phase_power_wm2: float = 0.0,
    phase_half_width_c: float = 0.0,
):
    required_files = ['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity']
    for key in required_files:
        if key not in file_paths or not file_paths[key]:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{key}")

    config = load_config(file_paths['config'])

    DEFAULT_DIRECTORY = config['DEFAULT_DIRECTORY']
    DECLARE_FILE = config['DECLARE_FILE']
    EMAIL_CONTACT = config['EMAIL_CONTACT']

    C1 = config['C1']
    C2 = config['C2']
    T_a1 = config['T_a1']
    T_filmmin = config['T_filmmins']
    T_filmmax = config['T_filmmaxs']
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    WAVELENGTH_RANGE_EMISSIVITY = config['WAVELENGTH_RANGE_EMISSIVITY']
    VISIABLE_RANGE = config['VISIABLE_RANGE']
    HC_VALUES = config['HC_VALUES']
    S_solar = float(config['S_solar'])

    # Load combined (R+T) or pure R data for absorptance calculation
    reflectance_data = load_reflectance(file_paths['reflectance'])
    spectrum_data = load_spectrum(file_paths['spectrum'])

    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)

    ref_wavelength1, reflectance_values1 = filter_wavelength(reflectance_data, 0, 1, VISIABLE_RANGE)
    spec_wavelength1, spectrum_values1 = filter_wavelength(spectrum_data, 0, 1, VISIABLE_RANGE)

    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    interpolated_spectrum1 = interpolate_spectrum(ref_wavelength1, spec_wavelength1, spectrum_values1)

    # Separate reflectance-only and transmittance for correct output values.
    # absorptance = 1 - R - T is computed from the original reflectance and
    # the separately loaded transmittance (interpolated onto the R wavelength grid).
    has_original_r = 'reflectance_original' in file_paths and file_paths['reflectance_original']
    has_trans = 'transmittance' in file_paths and file_paths['transmittance']

    R_sol_reflectance_only = None
    R_sol1_reflectance_only = None
    T_sol = 0.0
    T_sol1 = 0.0
    T_sol_weighted = 0.0
    T_sol1_weighted = 0.0

    if has_original_r:
        reflectance_orig_data = load_reflectance(file_paths['reflectance_original'])
        ref_orig_wl, ref_orig_vals = filter_wavelength(reflectance_orig_data, 0, 1, WAVELENGTH_RANGE)
        ref_orig_wl1, ref_orig_vals1 = filter_wavelength(reflectance_orig_data, 0, 1, VISIABLE_RANGE)

        interp_orig = interpolate_spectrum(ref_orig_wl, spec_wavelength, spectrum_values)
        interp_orig1 = interpolate_spectrum(ref_orig_wl1, spec_wavelength1, spectrum_values1)

        R_sol_reflectance_only = float(calculate_weighted_reflectance(ref_orig_vals, interp_orig, ref_orig_wl))
        R_sol1_reflectance_only = float(calculate_weighted_reflectance(ref_orig_vals1, interp_orig1, ref_orig_wl1))

        if has_trans:
            trans_data = load_reflectance(file_paths['transmittance'])
            trans_wl, trans_vals = filter_wavelength(trans_data, 0, 1, WAVELENGTH_RANGE)
            trans_wl1, trans_vals1 = filter_wavelength(trans_data, 0, 1, VISIABLE_RANGE)

            trans_interp = interpolate_spectrum(ref_orig_wl, trans_wl, trans_vals)
            trans_interp1 = interpolate_spectrum(ref_orig_wl1, trans_wl1, trans_vals1)

            T_sol_weighted = float(calculate_weighted_reflectance(trans_interp, interp_orig, ref_orig_wl))
            T_sol1_weighted = float(calculate_weighted_reflectance(trans_interp1, interp_orig1, ref_orig_wl1))

            T_sol = T_sol_weighted
            T_sol1 = T_sol1_weighted
    else:
        # No separate reflectance; use the combined (R+T) file for R_only as before
        R_sol_reflectance_only = float(calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength))
        R_sol1_reflectance_only = float(calculate_weighted_reflectance(reflectance_values1, interpolated_spectrum1, ref_wavelength1))
        if has_trans:
            trans_data = load_reflectance(file_paths['transmittance'])
            trans_wl, trans_vals = filter_wavelength(trans_data, 0, 1, WAVELENGTH_RANGE)
            trans_wl1, trans_vals1 = filter_wavelength(trans_data, 0, 1, VISIABLE_RANGE)

            trans_interp = interpolate_spectrum(ref_wavelength, trans_wl, trans_vals)
            trans_interp1 = interpolate_spectrum(ref_wavelength1, trans_wl1, trans_vals1)

            T_sol_weighted = float(calculate_weighted_reflectance(trans_interp, interpolated_spectrum, ref_wavelength))
            T_sol1_weighted = float(calculate_weighted_reflectance(trans_interp1, interpolated_spectrum1, ref_wavelength1))

            T_sol = T_sol_weighted
            T_sol1 = T_sol1_weighted

    # Absorptance = 1 - R - T (uses the weighted R and T computed above)
    if R_sol_reflectance_only is not None:
        alpha_sol = 1.0 - (R_sol_reflectance_only + T_sol_weighted)
        alpha_sol1 = 1.0 - (R_sol1_reflectance_only + T_sol1_weighted)
    else:
        alpha_sol = 1.0 - float(calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength))
        alpha_sol1 = 1.0 - float(calculate_weighted_reflectance(reflectance_values1, interpolated_spectrum1, ref_wavelength1))

    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity'],
        wavelength_range=WAVELENGTH_RANGE_EMISSIVITY
    )

    data1 = np.column_stack((X, emissivityatm_interpolated))
    data2 = np.column_stack((X, emissivity_interpolated))
    data1[:, 0] *= 1000
    data2[:, 0] *= 1000

    T_film = np.arange(T_filmmin, T_filmmax, 1)
    T_sll = T_film + 273.15

    theta, angle_factor = _build_angle_grid(angle_steps)

    lam1_m = data1[:, 0] * 1e-9
    lam2_m = data2[:, 0] * 1e-9
    tmat = data1[:, 1]
    e_smat = data2[:, 1]

    dlam1 = data1[1, 0] - data1[0, 0] if len(data1) > 1 else 1
    dlam2 = data2[1, 0] - data2[0, 0] if len(data2) > 1 else 1

    alpha_s = alpha_sol  # Use the computed absorptance (1 - R - T)
    results = np.zeros((len(T_film), len(HC_VALUES)))

    T_a = T_a1 + 273.15

    for hc_index, h_extra in enumerate(HC_VALUES):
        for i, T_s_current in enumerate(T_sll):
            p_r, p_a = _radiative_terms(
                C1,
                C2,
                lam1_m,
                lam2_m,
                tmat,
                e_smat,
                T_a=T_a,
                T_s=float(T_s_current),
                angle_factor=angle_factor,
                theta=theta,
                dlam1_nm=dlam1,
                dlam2_nm=dlam2,
            )

            delta_T = float(T_s_current - T_a)
            if enable_natural_convection:
                h_nat = calculate_convection_coefficient(
                    wind_speed=0.0, delta_T=delta_T, T_a=T_a,
                    L_char=0.025, surface_orientation="horizontal_up"
                )
            else:
                h_nat = 0.0

            h_total = float(h_nat + float(h_extra))
            Q_conv = float(h_total * (T_a1 - T_film[i]))

            Q_solar = float(alpha_s * S_solar)
            P_phase = _phase_power(
                T_film_c=float(T_film[i]),
                phase_temp_c=phase_temp_c,
                phase_power_wm2=phase_power_wm2,
                phase_half_width_c=phase_half_width_c,
            )

            p_heat = float(Q_solar + p_a + Q_conv - p_r - P_phase)

            if debug:
                print(f"--- T_film: {T_film[i]:.2f}°C, h_extra: {float(h_extra):.2f} W/m²K ---")
                print(f"  p_r (向外辐射): {p_r:.4f} W/m²")
                print(f"  p_a (大气辐射): {p_a:.4f} W/m²")
                print(
                    f"  Q_conv (对流换热): {Q_conv:.4f} W/m² (h_nat={h_nat:.3f}, h_total={h_total:.3f})"
                )
                print(f"  Q_solar (太阳吸收): {Q_solar:.4f} W/m²")
                print(f"  P_phase (相变功率): {P_phase:.4f} W/m²")
                print(f"  p_heat (净制热功率): {p_heat:.4f} W/m²")
                print('-' * 50 + '\n')

            results[i, hc_index] = p_heat

    idx_zero_diff = int(np.argmin(np.abs(T_film - T_a1)))
    heating_power_zero_diff = results[idx_zero_diff, :]

    create_declaration_file(DEFAULT_DIRECTORY, DECLARE_FILE, EMAIL_CONTACT)

    if skip_dialog:
        # Also return weighted solar reflectance and weighted emissivity for UI display.
        # 使用发射率波长范围过滤
        data_emis = np.loadtxt(file_paths['emissivity'])
        wavelength_um = data_emis[:, 0]
        emissivity = data_emis[:, 1]
        filtered_wavelength_um, filtered_emissivity = filter_wavelength(
            np.column_stack((wavelength_um, emissivity)), 0, 1, WAVELENGTH_RANGE_EMISSIVITY
        )
        wavelength_m = filtered_wavelength_um * 1e-6
        avg_emissivity = calculate_average_emissivity(wavelength_m, filtered_emissivity, T_a)

        return {
            'Power_0': float(heating_power_zero_diff[0]),
            'results': results,
            'T_film': T_film,
            'T_a1': T_a1,
            'HC_VALUES': HC_VALUES,
            'phase_temp_c': phase_temp_c,
            'phase_power_wm2': phase_power_wm2,
            'phase_half_width_c': phase_half_width_c,
            'enable_natural_convection': bool(enable_natural_convection),
            'R_sol': float(alpha_sol),
            'R_sol1': float(alpha_sol1),
            'R_sol_reflectance_only': float(R_sol_reflectance_only) if R_sol_reflectance_only is not None else float(calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)),
            'R_sol1_reflectance_only': float(R_sol1_reflectance_only) if R_sol1_reflectance_only is not None else float(calculate_weighted_reflectance(reflectance_values1, interpolated_spectrum1, ref_wavelength1)),
            'T_sol': float(T_sol),
            'T_sol1': float(T_sol1),
            'avg_emissivity': float(avg_emissivity),
        }

    return float(heating_power_zero_diff[0])


def calculate_angular_power(
    file_paths: dict,
    *,
    temp_diff_c: float = 0.0,
    angle_steps: int = 91
):
    """Calculate radiative power density vs. zenith angle.

    Returns:
        dict with:
            theta_deg            -- zenith angles (0..90 deg)
            power_density_per_sr -- net radiative power density (W/m²/sr)
            power_density_total  -- total hemispherical power (W/m²) via angular integration
            hemispherical_solid_angle -- total solid angle of hemisphere (sr)
            half_power_angle_deg -- zenith angle where power drops to half its max (deg, NaN if none)
            meta:
                temp_diff_c          -- surface-air temperature difference (°C)
                angle_steps          -- number of angular samples
                T_a_K                -- ambient air temperature (K)
                T_s_K                -- surface temperature (K)
                wavelength_range_um  -- emissivity wavelength range (μm)
                dlam_nm              -- wavelength integration step (nm)
    """
    config = load_config(file_paths['config'])
    C1 = config['C1']
    C2 = config['C2']
    T_a1 = config['T_a1']
    WAVELENGTH_RANGE_EMISSIVITY = config['WAVELENGTH_RANGE_EMISSIVITY']

    # Load spectral data
    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity'],
        wavelength_range=WAVELENGTH_RANGE_EMISSIVITY
    )
    data1 = np.column_stack((X, emissivityatm_interpolated))
    data2 = np.column_stack((X, emissivity_interpolated))
    data1[:, 0] *= 1000
    data2[:, 0] *= 1000

    T_a = T_a1 + 273.15
    T_s = T_a + temp_diff_c

    # Angle array (0 to 90 degrees inclusive)
    theta = np.linspace(0, np.pi / 2, angle_steps).reshape(-1, 1)

    lam1_m = data1[:, 0] * 1e-9
    lam2_m = data2[:, 0] * 1e-9
    tmat = data1[:, 1]  # Zenith atmospheric transmittance
    e_smat = data2[:, 1]  # Material emissivity

    # FIX Bug 1: unify wavelength step. data1 and data2 share the same wavelength
    # grid, so dlam1 == dlam2. Guard against single-point edge case.
    if len(data1) > 1:
        dlam_nm = float(data1[1, 0] - data1[0, 0])
    else:
        dlam_nm = 1.0

    # Planck spectral exitance (W/m²/nm)
    u_bs_surface = _planck_spectral_exitance(C1, C2, lam2_m, T_s)
    u_bs_atm = _planck_spectral_exitance(C1, C2, lam1_m, T_a)

    # FIX Bug 2: robust 90° boundary handling.
    # cos(90°) ≈ 6.12e-17 (not exactly zero in float).
    # Use a relative threshold instead of hardcoded epsilon.
    with np.errstate(divide='ignore', invalid='ignore'):
        cos_theta = np.cos(theta)  # shape (N_theta, 1)
        # Near-zero cos_theta is treated as 1e-15 (equivalent to ~89.99994°);
        # at such extreme angles the atmosphere is already opaque in the window.
        cos_theta_safe = np.where(np.abs(cos_theta) < 1e-15, 1e-15, cos_theta)
        e_zmat = 1.0 - np.power(tmat, 1.0 / cos_theta_safe)  # (N_theta, N_lambda)
        e_zmat = np.nan_to_num(e_zmat, nan=0.0, posinf=1.0, neginf=0.0)
        e_zmat = np.clip(e_zmat, 0.0, 1.0)

    # Spectral radiance (W/m²/sr/nm): M_BB / π
    L_surf_spectral = u_bs_surface / np.pi  # (N_lambda,)
    L_atm_spectral = u_bs_atm / np.pi  # (N_lambda,)

    # Net spectral radiance toward each zenith angle
    # L_net(λ,θ) = ε_s(λ) * [L_surf(λ) - ε_z(λ,θ) * L_atm(λ)]
    L_net_spectral = e_smat * (L_surf_spectral - e_zmat * L_atm_spectral)  # (N_theta, N_lambda)

    # Integrate over wavelength: P(θ) = Σ L_net(λ,θ) * Δλ  [W/m²/sr]
    radiance = np.sum(L_net_spectral * dlam_nm, axis=1)

    # --- OPTIMISATION: additional derived quantities ---

    # 1. Total hemispherical radiative power by angular integration.
    # P_total = ∫₀^{2π} ∫₀^{π/2} P(θ) sinθ cosθ dθ dφ
    #         = 2π Σ P(θᵢ) sin(θᵢ) cos(θᵢ) Δθ
    dtheta = float(np.pi / 2) / max(angle_steps - 1, 1)
    ang_factor = 2 * np.pi * np.sin(theta) * np.cos(theta) * dtheta  # (N_theta, 1)
    power_density_total = float(np.sum(radiance.flatten() * ang_factor.flatten()))
    hemispherical_solid_angle = float(np.sum(ang_factor.flatten()))

    # 2. Half-power zenith angle (angle where P(θ) = P_max / 2).
    power_max = float(np.max(radiance))
    power_min = float(np.min(radiance))
    if power_max == power_min or power_max <= 0:
        half_power_angle_deg = float('nan')
    else:
        half_power_value = power_max / 2.0
        # Find the first angle where P(θ) <= half_power_value (descending side)
        below_half = radiance.flatten() <= half_power_value
        if np.any(below_half):
            half_power_angle_deg = float(np.rad2deg(theta.flatten()[np.argmax(below_half)]))
        else:
            half_power_angle_deg = float('nan')

    return {
        'theta_deg': np.rad2deg(theta).flatten(),
        'power_density_per_sr': radiance.flatten(),
        'power_density_total': power_density_total,
        'hemispherical_solid_angle': hemispherical_solid_angle,
        'half_power_angle_deg': half_power_angle_deg,
        'meta': {
            'temp_diff_c': float(temp_diff_c),
            'angle_steps': int(angle_steps),
            'T_a_K': float(T_a),
            'T_s_K': float(T_s),
            'wavelength_range_um': list(WAVELENGTH_RANGE_EMISSIVITY),
            'dlam_nm': float(dlam_nm),
        },
    }
