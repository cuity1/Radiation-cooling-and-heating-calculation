from __future__ import annotations

import numpy as np

from .inputs_resolver import resolve_input_paths


def compute_material_env_temp_cloud(
    *,
    user_id: int,
    t_env_min_c: float,
    t_env_max_c: float,
    h_c_wm2k: float,
    temp_step_c: float = 0.5,
    enable_natural_convection: bool = False,
    enable_latent_heat: bool = False,
    relative_humidity: float | None = None,
    wet_fraction: float = 1.0,
    phase_temp_c: float | None = None,
    phase_power_wm2: float = 0.0,
    phase_half_width_c: float = 0.0,
) -> dict:
    """Material–environment temperature cooling-power cloud map.

    For a fixed convection coefficient h_c (W/m²·K), this computes radiative
    cooling power spectra for a range of ambient temperatures. The result is a
    2D matrix over (T_env, T_film), where each row corresponds to one
    ambient temperature and each column corresponds to one film temperature.

    Notes
    -----
    - The core physics is aligned with ``main_cooling_gui`` in
      ``core.calculations`` but:
        * We no longer iterate over HC_VALUES from config.
        * We fix a single user-provided h_c_wm2k.
        * We sweep ambient temperature T_env over [t_env_min_c, t_env_max_c]
          with a fixed step of ``temp_step_c`` (default 0.1 °C).
    """

    from core.config import load_config
    from core.physics import calculate_average_emissivity, calculate_convection_coefficient
    from core.spectrum import (
        calculate_weighted_reflectance,
        filter_wavelength,
        interpolate_spectrum,
        load_reflectance,
        load_spectrum,
        load_and_interpolate_emissivity,
    )
    from core.calculations import _build_angle_grid, _radiative_terms, _phase_power, _calculate_latent_heat_power

    if temp_step_c <= 0:
        raise ValueError("temp_step_c must be > 0")
    if t_env_max_c <= t_env_min_c:
        raise ValueError("t_env_max_c must be greater than t_env_min_c")
    if h_c_wm2k <= 0 or h_c_wm2k > 5000:
        raise ValueError("h_c_wm2k must be between 0 and 5000")

    # Hard cap on number of ambient temperature samples for performance
    max_env_points = 2000
    n_env = int(np.floor((t_env_max_c - t_env_min_c) / temp_step_c)) + 1
    if n_env < 2:
        raise ValueError("Ambient temperature range is too small; need at least 2 points.")
    if n_env > max_env_points:
        raise ValueError(
            f"Too many ambient temperature points ({n_env}). "
            f"Please reduce the range or increase the step size (max {max_env_points})."
        )

    file_paths = resolve_input_paths(require_material=True, user_id=int(user_id))

    # --- Load config & spectral data (independent of T_env sweep) ---
    config = load_config(file_paths["config"])

    C1 = config["C1"]
    C2 = config["C2"]
    T_filmmin = config["T_filmmin"]
    T_filmmax = config["T_filmmax"]
    WAVELENGTH_RANGE = config["WAVELENGTH_RANGE"]
    WAVELENGTH_RANGE_EMISSIVITY = config["WAVELENGTH_RANGE_EMISSIVITY"]
    VISIABLE_RANGE = config["VISIABLE_RANGE"]
    S_solar = float(config["S_solar"])

    # Reflectance / spectrum for solar absorptance
    reflectance_data = load_reflectance(file_paths["reflectance"])
    spectrum_data = load_spectrum(file_paths["spectrum"])

    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)

    ref_wavelength1, reflectance_values1 = filter_wavelength(reflectance_data, 0, 1, VISIABLE_RANGE)
    spec_wavelength1, spectrum_values1 = filter_wavelength(spectrum_data, 0, 1, VISIABLE_RANGE)

    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    interpolated_spectrum1 = interpolate_spectrum(ref_wavelength1, spec_wavelength1, spectrum_values1)

    # Combined (R+T) weighted values; absorptance alpha = 1 - (R+T)
    R_plus_T_sol = float(calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength))
    R_plus_T_sol1 = float(
        calculate_weighted_reflectance(reflectance_values1, interpolated_spectrum1, ref_wavelength1)
    )

    alpha_sol = 1.0 - R_plus_T_sol
    alpha_sol1 = 1.0 - R_plus_T_sol1

    # Emissivity / atmospheric emissivity spectra
    X, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths["wavelength"], file_paths["emissivity"], file_paths["atm_emissivity"],
        wavelength_range=WAVELENGTH_RANGE_EMISSIVITY
    )
    data1 = np.column_stack((X, emissivityatm_interpolated))
    data2 = np.column_stack((X, emissivity_interpolated))
    data1[:, 0] *= 1000
    data2[:, 0] *= 1000

    # Film temperature grid (°C) – shared for all ambient temperatures
    T_film = np.arange(T_filmmin, T_filmmax, 1)
    if T_film.size == 0:
        raise ValueError(
            "T_film is empty. Please check config values: T_filmmin, T_filmmax "
            f"(must satisfy T_filmmin < T_filmmax). Got T_filmmin={T_filmmin}, T_filmmax={T_filmmax}."
        )
    T_sll_offset = T_film + 273.15  # Will be adjusted by T_env if needed

    # Average emissivity for metadata (uses reference T_a1 from config)
    data_emis = np.loadtxt(file_paths["emissivity"])
    wavelength_um = data_emis[:, 0]
    emissivity = data_emis[:, 1]
    wavelength_m = wavelength_um * 1e-6
    T_a1_ref = float(config["T_a1"])
    T_a_ref = T_a1_ref + 273.15
    avg_emissivity = float(calculate_average_emissivity(wavelength_m, emissivity, T_a_ref))

    # Angle grid & radiative integration constants (shared)
    theta, angle_factor = _build_angle_grid(angle_steps=2000)

    lam1_m = data1[:, 0] * 1e-9
    lam2_m = data2[:, 0] * 1e-9
    tmat = data1[:, 1]
    e_smat = data2[:, 1]

    dlam1 = data1[1, 0] - data1[0, 0] if len(data1) > 1 else 1
    dlam2 = data2[1, 0] - data2[0, 0] if len(data2) > 1 else 1

    # Ambient temperature samples (°C)
    t_env_range_c = t_env_min_c + np.arange(n_env) * temp_step_c

    # Result matrix: shape (n_env, n_film)
    cooling_power = np.zeros((len(t_env_range_c), len(T_film)), dtype=float)

    for idx_env, T_env_c in enumerate(t_env_range_c):
        T_a = float(T_env_c + 273.15)
        T_sll = T_sll_offset  # film temperature in K (relative to each film point)

        for i, T_s_current in enumerate(T_sll):
            # Radiative terms
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
            # Natural convection based on delta_T and ambient temperature
            if enable_natural_convection:
                h_nat = calculate_convection_coefficient(
                    wind_speed=0.0, delta_T=delta_T, T_a=T_a,
                    L_char=0.025, surface_orientation="horizontal_up"
                )
            else:
                h_nat = 0.0

            # Total convection coefficient: natural + user-specified h_c
            h_total = float(h_nat + float(h_c_wm2k))
            Q_conv = float(h_total * (T_env_c - T_film[i]))

            Q_solar = float(alpha_sol * S_solar)
            P_phase = _phase_power(
                T_film_c=float(T_film[i]),
                phase_temp_c=phase_temp_c,
                phase_power_wm2=phase_power_wm2,
                phase_half_width_c=phase_half_width_c,
            )

            # Latent heat (optional, same convention as main_cooling_gui)
            if enable_latent_heat and relative_humidity is not None:
                RH_normalized = (
                    float(relative_humidity) / 100.0
                    if relative_humidity > 1.0
                    else float(relative_humidity)
                )
                RH_normalized = max(0.0, min(1.0, RH_normalized))
                Q_latent = _calculate_latent_heat_power(
                    T_surface_K=float(T_s_current),
                    T_ambient_K=T_a,
                    RH=RH_normalized,
                    h_conv=float(h_total),
                )
                wf = float(wet_fraction)
                wf = max(0.0, min(1.0, wf))
                Q_latent = float(Q_latent) * wf
            else:
                Q_latent = 0.0

            p_net = float(p_r - p_a - Q_conv - Q_solar + P_phase + Q_latent)
            cooling_power[idx_env, i] = p_net

    return {
        "t_env_c": t_env_range_c.tolist(),
        "t_film_c": T_film.tolist(),
        "cooling_power": cooling_power.tolist(),
        "meta": {
            "h_c_wm2k": float(h_c_wm2k),
            "temp_step_c": float(temp_step_c),
            "alpha_sol": float(alpha_sol),
            "alpha_sol_visible": float(alpha_sol1),
            "avg_emissivity": float(avg_emissivity),
            "S_solar": float(S_solar),
            "T_a1_ref_c": float(T_a1_ref),
            "enable_natural_convection": bool(enable_natural_convection),
            "enable_latent_heat": bool(enable_latent_heat),
            "relative_humidity": float(relative_humidity) if relative_humidity is not None else None,
            "wet_fraction": float(wet_fraction),
            "phase_temp_c": phase_temp_c,
            "phase_power_wm2": float(phase_power_wm2),
            "phase_half_width_c": float(phase_half_width_c),
        },
    }

