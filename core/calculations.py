"""High-level calculation entry points (non-GUI).

These functions are called by GUI windows/threads.
Keep heavy plotting/UI imports out of here.
"""

from __future__ import annotations

import os

import numpy as np

from core.config import check_expiration, load_config
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


def main_calculating_gui(file_paths: dict):
    required_files = ['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity']
    for key in required_files:
        if key not in file_paths or not file_paths[key]:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{key}")

    config = load_config(file_paths['config'])
    check_expiration(config['EXPIRATION_DATE'], config['EMAIL_CONTACT'])

    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
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
    data = np.loadtxt(file_paths['emissivity'])
    wavelength_um = data[:, 0]
    emissivity = data[:, 1]
    wavelength_m = wavelength_um * 1e-6
    avg_emissivity = calculate_average_emissivity(wavelength_m, emissivity, T_a)

    return avg_emissivity, float(R_sol), float(R_sol1)


def main_cooling_gui(
    file_paths: dict,
    *,
    angle_steps: int = 2000,
    h_cond_wm2k: float | None = None,
    enable_natural_convection: bool = True,
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
    check_expiration(config['EXPIRATION_DATE'], config['EMAIL_CONTACT'])

    DEFAULT_DIRECTORY = config['DEFAULT_DIRECTORY']
    DECLARE_FILE = config['DECLARE_FILE']
    EMAIL_CONTACT = config['EMAIL_CONTACT']

    C1 = config['C1']
    C2 = config['C2']
    T_a1 = config['T_a1']
    T_filmmin = config['T_filmmin']
    T_filmmax = config['T_filmmax']
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    VISIABLE_RANGE = config['VISIABLE_RANGE']
    HC_VALUES = config['HC_VALUES']
    S_solar = float(config['S_solar'])

    reflectance_data = load_reflectance(file_paths['reflectance'])
    spectrum_data = load_spectrum(file_paths['spectrum'])

    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)

    ref_wavelength1, reflectance_values1 = filter_wavelength(reflectance_data, 0, 1, VISIABLE_RANGE)
    spec_wavelength1, spectrum_values1 = filter_wavelength(spectrum_data, 0, 1, VISIABLE_RANGE)

    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    interpolated_spectrum1 = interpolate_spectrum(ref_wavelength1, spec_wavelength1, spectrum_values1)

    R_sol = float(calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength))
    R_sol1 = float(calculate_weighted_reflectance(reflectance_values1, interpolated_spectrum1, ref_wavelength1))

    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
    )
    data1 = np.column_stack((X, emissivityatm_interpolated))
    data2 = np.column_stack((X, emissivity_interpolated))
    data1[:, 0] *= 1000
    data2[:, 0] *= 1000

    T_a = T_a1 + 273.15
    T_film = np.arange(T_filmmin, T_filmmax, 1)
    T_sll = T_film + 273.15

    data = np.loadtxt(file_paths['emissivity'])
    wavelength_um = data[:, 0]
    emissivity = data[:, 1]
    wavelength_m = wavelength_um * 1e-6
    avg_emissivity = calculate_average_emissivity(wavelength_m, emissivity, T_a)

    theta, angle_factor = _build_angle_grid(angle_steps)

    lam1_m = data1[:, 0] * 1e-9
    lam2_m = data2[:, 0] * 1e-9
    tmat = data1[:, 1]
    e_smat = data2[:, 1]

    dlam1 = data1[1, 0] - data1[0, 0] if len(data1) > 1 else 1
    dlam2 = data2[1, 0] - data2[0, 0] if len(data2) > 1 else 1

    alpha_s = 1 - R_sol
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
                h_nat = calculate_convection_coefficient(wind_speed=0.0, delta_T=delta_T, T_a=T_a, L_char=1.0)
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

            p_net = float(p_r - p_a - Q_conv - Q_solar + P_phase)

            if debug:
                print(f"--- T_film: {T_film[i]:.2f}°C, h_extra: {float(h_extra):.2f} W/m²K ---")
                print(f"  p_r (向外辐射): {p_r:.4f} W/m²")
                print(f"  p_a (大气辐射): {p_a:.4f} W/m²")
                print(
                    f"  Q_conv (对流换热): {Q_conv:.4f} W/m² (h_nat={h_nat:.3f}, h_total={h_total:.3f})"
                )
                print(f"  Q_solar (太阳吸收): {Q_solar:.4f} W/m²")
                print(f"  P_phase (相变功率): {P_phase:.4f} W/m²")
                print(f"  p_net (净制冷功率): {p_net:.4f} W/m²")
                print('-' * 50 + '\n')

            results[i, hc_index] = p_net

    idx_zero_diff = int(np.argmin(np.abs(T_film - T_a1)))
    cooling_power_zero_diff = results[idx_zero_diff, :]

    create_declaration_file(DEFAULT_DIRECTORY, DECLARE_FILE, EMAIL_CONTACT)

    if skip_dialog:
        return {
            'avg_emissivity': avg_emissivity,
            'R_sol': float(R_sol),
            'R_sol1': float(R_sol1),
            'Power_0': float(cooling_power_zero_diff[0]),
            'results': results,
            'T_film': T_film,
            'T_a1': T_a1,
            'HC_VALUES': HC_VALUES,
            'phase_temp_c': phase_temp_c,
            'phase_power_wm2': phase_power_wm2,
            'phase_half_width_c': phase_half_width_c,
            'enable_natural_convection': bool(enable_natural_convection),
        }

    return avg_emissivity, float(R_sol), float(R_sol1), float(cooling_power_zero_diff[0])


def main_power_components_gui(
    file_paths: dict,
    *,
    angle_steps: int = 2000,
    h_cond_wm2k: float = 5.0,
    enable_natural_convection: bool = True,
    phase_temp_c: float | None = None,
    phase_power_wm2: float = 0.0,
    phase_half_width_c: float = 0.0,
):
    """Calculate all radiative/convective power components for plotting."""
    required_files = ['config', 'reflectance', 'spectrum', 'wavelength', 'emissivity', 'atm_emissivity']
    for key in required_files:
        if key not in file_paths or not file_paths[key]:
            raise Exception(f"请确保已选择所有必要的文件。缺少：{key}")

    config = load_config(file_paths['config'])
    check_expiration(config['EXPIRATION_DATE'], config['EMAIL_CONTACT'])

    C1 = config['C1']
    C2 = config['C2']
    T_a1 = config['T_a1']
    T_filmmin = config['T_filmmin']
    T_filmmax = config['T_filmmax']
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    S_solar = float(config['S_solar'])

    reflectance_data = load_reflectance(file_paths['reflectance'])
    spectrum_data = load_spectrum(file_paths['spectrum'])

    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    R_sol = float(calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength))

    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
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
        'Q_solar': [],
        'P_phase': [],
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
            h_nat = float(calculate_convection_coefficient(wind_speed=0.0, delta_T=delta_T, T_a=T_a, L_char=1.0))
        else:
            h_nat = 0.0

        h_total = float(h_cond_wm2k + h_nat)

        # Heat flux decomposition
        # Note: use (T_a1 - T_film) to stay consistent with existing sign convention
        Q_nat = float(h_nat * (T_a1 - T_film[i]))
        Q_cond = float(h_cond_wm2k * (T_a1 - T_film[i]))
        Q_conv = float((Q_nat + Q_cond))

        Q_solar = float(alpha_s * S_solar)
        P_phase = _phase_power(
            T_film_c=float(T_film[i]),
            phase_temp_c=phase_temp_c,
            phase_power_wm2=phase_power_wm2,
            phase_half_width_c=phase_half_width_c,
        )

        p_net = float(p_r - p_a - Q_conv - Q_solar + P_phase)

        components['p_r'].append(p_r)
        components['p_a'].append(p_a)
        components['Q_conv'].append(Q_conv)
        components['Q_nat'].append(Q_nat)
        components['Q_cond'].append(Q_cond)
        components['Q_solar'].append(Q_solar)
        components['P_phase'].append(P_phase)
        components['p_net'].append(p_net)
        components['h_nat'].append(h_nat)
        components['h_total'].append(h_total)

    return {
        'components': {k: np.array(v) for k, v in components.items()},
        'T_film': T_film,
        'T_a1': T_a1,
        'enable_natural_convection': bool(enable_natural_convection),
    }


def main_heating_gui(
    file_paths: dict,
    *,
    angle_steps: int = 2000,
    enable_natural_convection: bool = True,
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
    check_expiration(config['EXPIRATION_DATE'], config['EMAIL_CONTACT'])

    DEFAULT_DIRECTORY = config['DEFAULT_DIRECTORY']
    DECLARE_FILE = config['DECLARE_FILE']
    EMAIL_CONTACT = config['EMAIL_CONTACT']

    C1 = config['C1']
    C2 = config['C2']
    T_a1 = config['T_a1']
    T_filmmin = config['T_filmmins']
    T_filmmax = config['T_filmmaxs']
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']
    HC_VALUES = config['HC_VALUES']
    S_solar = float(config['S_solar'])

    reflectance_data = load_reflectance(file_paths['reflectance'])
    spectrum_data = load_spectrum(file_paths['spectrum'])

    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)

    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    R_sol = float(calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength))

    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
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

    alpha_s = 1 - float(R_sol)
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
                h_nat = calculate_convection_coefficient(wind_speed=0.0, delta_T=delta_T, T_a=T_a, L_char=1.0)
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
        }

    return float(heating_power_zero_diff[0])
