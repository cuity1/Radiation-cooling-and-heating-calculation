from __future__ import annotations

import numpy as np

from .inputs_resolver import resolve_input_paths


def compute_wind_cloud(
    *,
    user_id: int,
    wind_min: float,
    wind_max: float,
    wind_points: int,
    emissivity_min: float,
    emissivity_max: float,
    emissivity_points: int,
    s_solar: float | None,
) -> dict:
    """Wind–emissivity cloud map (equilibrium ΔT and convection coefficient).

    ΔT is defined as:
      ΔT = T_film - T_env

    Performance note:
    - Grid resolution is capped to 200x200.
    - Uses a greybody equilibrium approximation for speed.
    """

    # hard cap: 200x200
    if wind_points < 2 or wind_points > 200:
        raise ValueError("wind_points must be between 2 and 200")
    if emissivity_points < 2 or emissivity_points > 200:
        raise ValueError("emissivity_points must be between 2 and 200")
    if wind_max <= wind_min:
        raise ValueError("wind_max must be greater than wind_min")
    if emissivity_max <= emissivity_min:
        raise ValueError("emissivity_max must be greater than emissivity_min")

    file_paths = resolve_input_paths(require_material=True, user_id=int(user_id))

    from core.config import load_config
    from core.physics import calculate_average_emissivity, calculate_convection_coefficient
    from core.spectrum import (
        calculate_weighted_reflectance,
        filter_wavelength,
        interpolate_spectrum,
        load_reflectance,
        load_spectrum,
    )

    from scipy.optimize import brentq, minimize_scalar

    config = load_config(file_paths["config"])
    T_a1 = float(config["T_a1"])

    if s_solar is None:
        try:
            s_solar_val = float(config["S_solar"])
        except Exception:
            s_solar_val = float(config.get("S_solar", 0.0))
    else:
        s_solar_val = float(s_solar)

    T_env = T_a1 + 273.15

    # Root bracket for ΔT (°C). (Numerically identical to K)
    XMIN = -100.0
    XMAX = 300.0

    sigma = 5.670374419e-8

    # Get solar absorptance from cooling power calculation logic
    from core.calculations import main_calculating_gui
    avg_emissivity_for_alpha, alpha_s, _ = main_calculating_gui(file_paths)
    # If reflectance is needed, use: r_sol = 1 - alpha_s
    r_sol = float(1.0 - alpha_s)

    # Material average emissivity (greybody approximation)
    data = np.loadtxt(file_paths["emissivity"])
    wavelength_um = data[:, 0]
    emissivity = data[:, 1]
    wavelength_m = wavelength_um * 1e-6
    avg_emissivity = float(calculate_average_emissivity(wavelength_m, emissivity, T_env))

    emissivity_variable = np.linspace(float(emissivity_min), float(emissivity_max), num=int(emissivity_points))
    wind = np.linspace(float(wind_min), float(wind_max), num=int(wind_points))

    delta_t_values = np.full((len(emissivity_variable), len(wind)), np.nan, dtype=float)

    def p_net_equation(delta_t: float, emissivity_atm: float, wind_speed: float) -> float:
        # ΔT = T_film - T_env
        h = float(calculate_convection_coefficient(float(wind_speed), float(delta_t), float(T_env)))
        t_film = float(T_env + delta_t)

        # Greybody radiative balance with effective atmospheric emissivity.
        # P_rad_net = ε_s σ (T_film^4 - ε_atm T_env^4)
        p_rad = avg_emissivity * sigma * (t_film**4 - float(emissivity_atm) * T_env**4)

        # Convection flux leaving surface (positive when T_film > T_env)
        p_conv = h * float(delta_t)

        # Absorbed solar power (into surface)
        p_solar = alpha_s * float(s_solar_val)

        # Equilibrium: P_rad_net + P_conv - P_solar = 0
        return float(p_rad + p_conv - p_solar)

    def find_approximate_solution(emissivity_atm: float, wind_speed: float) -> float:
        res = minimize_scalar(
            lambda dt: abs(p_net_equation(float(dt), float(emissivity_atm), float(wind_speed))),
            bounds=(XMIN, XMAX),
            method="bounded",
        )
        return float(res.x) if res.success else float("nan")

    for i, emissivity_atm in enumerate(emissivity_variable):
        for j, wind_speed in enumerate(wind):
            try:
                delta_t_values[i, j] = float(brentq(p_net_equation, XMIN, XMAX, args=(emissivity_atm, wind_speed)))
            except ValueError:
                delta_t_values[i, j] = find_approximate_solution(emissivity_atm, wind_speed)

    # h_conv matrix at equilibrium ΔT
    h_conv_matrix = np.full_like(delta_t_values, np.nan, dtype=float)
    for i, emissivity_atm in enumerate(emissivity_variable):
        for j, wind_speed in enumerate(wind):
            dt = float(delta_t_values[i, j])
            if np.isnan(dt):
                continue
            h_conv_matrix[i, j] = float(calculate_convection_coefficient(float(wind_speed), dt, float(T_env)))

    return {
        "wind": wind.tolist(),
        "emissivity": emissivity_variable.tolist(),
        "delta_t": delta_t_values.tolist(),
        "h_conv": h_conv_matrix.tolist(),
        "meta": {
            "t_env_c": float(T_a1),
            "s_solar": float(s_solar_val),
            "r_sol": float(r_sol),
            "alpha_s": float(alpha_s),
            "avg_emissivity": float(avg_emissivity),
            "delta_t_definition": "T_film - T_env",
            "model": "greybody_equilibrium",
            "grid": {
                "wind_points": int(wind_points),
                "emissivity_points": int(emissivity_points),
            },
        },
    }


def compute_solar_efficiency(
    *,
    user_id: int,
    angle_steps: int = 2000,
    t_a_points: int = 21,
    s_solar_points: int = 49,
    t_a_min: float = -100.0,
    t_a_max: float = 100.0,
    s_solar_min: float = 0.0,
    s_solar_max: float = 1200.0,
) -> dict:
    if angle_steps < 100 or angle_steps > 20000:
        raise ValueError("angle_steps must be between 100 and 20000")

    # hard cap: 200x200
    if t_a_points < 2 or t_a_points > 200:
        raise ValueError("t_a_points must be between 2 and 200")
    if s_solar_points < 2 or s_solar_points > 200:
        raise ValueError("s_solar_points must be between 2 and 200")
    if t_a_max <= t_a_min:
        raise ValueError("t_a_max must be greater than t_a_min")
    if s_solar_max <= s_solar_min:
        raise ValueError("s_solar_max must be greater than s_solar_min")

    file_paths = resolve_input_paths(require_material=True, user_id=int(user_id))

    from core.theoretical import main_theoretical_heating_vs_solar

    result = main_theoretical_heating_vs_solar(
        file_paths,
        angle_steps=int(angle_steps),
        skip_dialog=True,
        t_a_min=float(t_a_min),
        t_a_max=float(t_a_max),
        t_a_points=int(t_a_points),
        s_solar_min=float(s_solar_min),
        s_solar_max=float(s_solar_max),
        s_solar_points=int(s_solar_points),
    )

    t_a_range = result.get("T_a_range")
    s_solar_range = result.get("S_solar_range")
    results_mat = result.get("results")

    return {
        "t_a_range": (t_a_range.tolist() if hasattr(t_a_range, "tolist") else list(t_a_range or [])),
        "s_solar_range": (s_solar_range.tolist() if hasattr(s_solar_range, "tolist") else list(s_solar_range or [])),
        "p_heat": (results_mat.tolist() if hasattr(results_mat, "tolist") else list(results_mat or [])),
        "meta": {
            "angle_steps": int(angle_steps),
            "grid": {
                "t_a_points": int(t_a_points),
                "s_solar_points": int(s_solar_points),
                "t_a_min": float(t_a_min),
                "t_a_max": float(t_a_max),
                "s_solar_min": float(s_solar_min),
                "s_solar_max": float(s_solar_max),
            },
        },
    }


def compute_emissivity_solar_cloud(
    *,
    user_id: int,
    n_emissivity: int = 101,
    n_solar: int = 101,
    solar_max: float = 1000.0,
) -> dict:
    # hard cap: 200x200
    if n_emissivity < 2 or n_emissivity > 200:
        raise ValueError("n_emissivity must be between 2 and 200")
    if n_solar < 2 or n_solar > 200:
        raise ValueError("n_solar must be between 2 and 200")
    if solar_max <= 0:
        raise ValueError("solar_max must be > 0")

    file_paths = resolve_input_paths(require_material=True, user_id=int(user_id))

    from core.calculations import main_calculating_gui
    from core.config import load_config

    config = load_config(file_paths["config"])
    t_a1 = float(config["T_a1"])
    t_a = t_a1 + 273.15
    sigma = 5.670374419e-8

    # main_calculating_gui returns: (avg_emissivity, alpha_sol, alpha_sol1)
    # Use absorptance directly from cooling power calculation logic
    avg_emissivity, alpha_s, _ = main_calculating_gui(file_paths)
    # If reflectance is needed, use: r_sol = 1 - alpha_s
    r_sol = float(1.0 - alpha_s)

    atm_emissivity_range = np.linspace(0, 1, int(n_emissivity))
    solar_irradiance_range = np.linspace(0, float(solar_max), int(n_solar))

    cooling_power_matrix = np.zeros((len(solar_irradiance_range), len(atm_emissivity_range)))

    for i, s_solar in enumerate(solar_irradiance_range):
        p_solar = alpha_s * s_solar
        for j, emissivity_atm in enumerate(atm_emissivity_range):
            t_film = t_a
            p_rad_out = avg_emissivity * sigma * t_film**4
            p_rad_in = avg_emissivity * emissivity_atm * sigma * t_a**4
            p_cooling = p_rad_out - p_rad_in - p_solar
            cooling_power_matrix[i, j] = p_cooling

    return {
        "atm_emissivity": atm_emissivity_range.tolist(),
        "solar_irradiance": solar_irradiance_range.tolist(),
        "cooling_power": cooling_power_matrix.tolist(),
        "meta": {
            "avg_emissivity": float(avg_emissivity),
            "r_sol": float(r_sol),
            "alpha_s": float(alpha_s),
            "t_a1": float(t_a1),
            "delta_t": 0.0,
            "n_emissivity": int(n_emissivity),
            "n_solar": int(n_solar),
            "solar_max": float(solar_max),
        },
    }


def compute_power_components(
    *,
    user_id: int,
    angle_steps: int = 2000,
    h_cond_wm2k: float = 5.0,
    enable_natural_convection: bool = False,
    phase_temp_c: float | None = None,
    phase_power_wm2: float = 0.0,
    phase_half_width_c: float = 0.0,
    enable_latent_heat: bool = False,
    relative_humidity: float | None = None,
    wet_fraction: float = 1.0,
) -> dict:
    if angle_steps < 100 or angle_steps > 20000:
        raise ValueError("angle_steps must be between 100 and 20000")
    if h_cond_wm2k <= 0 or h_cond_wm2k > 5000:
        raise ValueError("h_cond_wm2k must be between 0 and 5000")

    file_paths = resolve_input_paths(require_material=True, user_id=int(user_id))

    from core.calculations import main_power_components_gui

    result = main_power_components_gui(
        file_paths,
        angle_steps=angle_steps,
        h_cond_wm2k=h_cond_wm2k,
        enable_natural_convection=enable_natural_convection,
        phase_temp_c=phase_temp_c,
        phase_power_wm2=phase_power_wm2,
        phase_half_width_c=phase_half_width_c,
        enable_latent_heat=enable_latent_heat,
        relative_humidity=float(relative_humidity) if relative_humidity is not None else None,
        wet_fraction=float(wet_fraction),
    )

    comps = result.get('components') or {}
    components_json = {k: (v.tolist() if hasattr(v, 'tolist') else list(v)) for k, v in comps.items()}

    t_film = result.get('T_film')
    return {
        't_film': (t_film.tolist() if hasattr(t_film, 'tolist') else list(t_film or [])),
        't_a1': float(result.get('T_a1')),
        'components': components_json,
        'meta': {
            'angle_steps': int(angle_steps),
            'h_cond_wm2k': float(h_cond_wm2k),
            'enable_natural_convection': bool(enable_natural_convection),
            'phase_temp_c': phase_temp_c,
            'phase_power_wm2': float(phase_power_wm2),
            'phase_half_width_c': float(phase_half_width_c),
            'enable_latent_heat': bool(enable_latent_heat),
            'relative_humidity': float(relative_humidity) if relative_humidity is not None else None,
            'wet_fraction': float(wet_fraction),
        },
    }


def compute_angular_power(*, user_id: int, temp_diff_c: float = 0.0, angle_steps: int = 91) -> dict:
    if angle_steps < 2 or angle_steps > 720:
        raise ValueError("angle_steps must be between 2 and 720")
    if temp_diff_c < -300 or temp_diff_c > 300:
        raise ValueError("temp_diff_c must be between -300 and 300")

    file_paths = resolve_input_paths(require_material=True, user_id=int(user_id))

    from core.calculations import calculate_angular_power

    result = calculate_angular_power(file_paths, temp_diff_c=temp_diff_c, angle_steps=angle_steps)

    theta_deg = result.get('theta_deg')
    power = result.get('power_density_per_sr')
    power_total = result.get('power_density_total')
    hsa = result.get('hemispherical_solid_angle')
    half_angle = result.get('half_power_angle_deg')

    return {
        'theta_deg': (theta_deg.tolist() if hasattr(theta_deg, 'tolist') else list(theta_deg or [])),
        'power_density_per_sr': (power.tolist() if hasattr(power, 'tolist') else list(power or [])),
        'power_density_total': float(power_total) if power_total is not None else None,
        'hemispherical_solid_angle': float(hsa) if hsa is not None else None,
        'half_power_angle_deg': float(half_angle) if half_angle is not None else None,
        'meta': {
            'temp_diff_c': float(temp_diff_c),
            'angle_steps': int(angle_steps),
            'T_a_K': result.get('meta', {}).get('T_a_K'),
            'T_s_K': result.get('meta', {}).get('T_s_K'),
            'wavelength_range_um': result.get('meta', {}).get('wavelength_range_um'),
            'dlam_nm': result.get('meta', {}).get('dlam_nm'),
        },
    }
