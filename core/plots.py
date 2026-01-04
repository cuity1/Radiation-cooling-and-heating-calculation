"""Plot generation (lazy matplotlib/scipy imports).

IMPORTANT:
- Keep heavy imports (matplotlib/scipy.optimize/tkinter) *inside* functions.
- This helps PyInstaller exclude unused GUI backends/features if you build a subset.
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


def generate_wind_cooling_plot(file_paths: dict, S_solar: float | None = None, skip_dialog: bool = False):
    """Generate wind-speed vs emissivity cloud plot.

    Note: contains optional tkinter save dialog, imported lazily.
    """
    # heavy imports are local
    import matplotlib.pyplot as plt
    from scipy.optimize import brentq, minimize_scalar

    config = load_config(file_paths['config'])
    T_a1 = config['T_a1']

    # If not provided, use S_solar from config
    if S_solar is None:
        try:
            S_solar = float(config['S_solar'])
        except Exception:
            S_solar = float(config.get('S_solar', 0.0))

    T_a = T_a1 + 273.15

    XMIN = -100
    XMAX = 300
    sigma = 5.670374419e-8

    reflectance_data = load_reflectance(file_paths['reflectance'])
    spectrum_data = load_spectrum(file_paths['spectrum'])
    WAVELENGTH_RANGE = config['WAVELENGTH_RANGE']

    ref_wavelength, reflectance_values = filter_wavelength(reflectance_data, 0, 1, WAVELENGTH_RANGE)
    spec_wavelength, spectrum_values = filter_wavelength(spectrum_data, 0, 1, WAVELENGTH_RANGE)
    interpolated_spectrum = interpolate_spectrum(ref_wavelength, spec_wavelength, spectrum_values)
    R_sol = calculate_weighted_reflectance(reflectance_values, interpolated_spectrum, ref_wavelength)

    _, emissivity_interpolated, emissivityatm_interpolated = load_and_interpolate_emissivity(
        file_paths['wavelength'], file_paths['emissivity'], file_paths['atm_emissivity']
    )

    # average emissivity from raw emissivity file
    data = np.loadtxt(file_paths['emissivity'])
    wavelength_um = data[:, 0]
    emissivity = data[:, 1]
    wavelength_m = wavelength_um * 1e-6
    avg_emissivity = calculate_average_emissivity(wavelength_m, emissivity, T_a)

    emissivitys = avg_emissivity
    alpha_s = 1 - R_sol

    def p_net_equation(delta_T, emissivity_atm, wind_speed):
        H = calculate_convection_coefficient(wind_speed, delta_T, T_a)
        T_s = T_a + delta_T
        return emissivitys * sigma * (T_s**4 - emissivity_atm * T_a**4) + H * delta_T - alpha_s * S_solar

    emissivity_variable = np.linspace(0, 1, num=50)
    wind = np.linspace(0, 5, num=50)
    delta_T_values = np.zeros((len(emissivity_variable), len(wind)))

    def find_approximate_solution(emissivity_atm, wind_speed, delta_T_min, delta_T_max):
        result = minimize_scalar(
            lambda dt: abs(p_net_equation(dt, emissivity_atm, wind_speed)),
            bounds=(delta_T_min, delta_T_max),
            method='bounded',
        )
        return result.x if result.success else np.nan

    for i, emissivity_atm in enumerate(emissivity_variable):
        for j, wind_speed in enumerate(wind):
            try:
                delta_T_solution = brentq(p_net_equation, XMIN, XMAX, args=(emissivity_atm, wind_speed))
                delta_T_values[i, j] = delta_T_solution
            except ValueError:
                delta_T_values[i, j] = find_approximate_solution(emissivity_atm, wind_speed, XMIN, XMAX)

    if skip_dialog:
        return {
            'delta_T_values': delta_T_values,
            'emissivity_variable': emissivity_variable,
            'wind': wind,
        }

    fig, ax = plt.subplots(figsize=(10, 8))
    X_mesh, Y_mesh = np.meshgrid(wind, emissivity_variable)
    cp = ax.contourf(X_mesh, Y_mesh, delta_T_values, levels=100, cmap='viridis')
    fig.colorbar(cp, ax=ax, label='ΔT (°C)')
    ax.set_xlabel('Wind (m/s)')
    ax.set_ylabel('Atomosphere emissivity')
    fig.tight_layout()
    plt.show()

    # optional save dialog (tkinter)
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    save_file_path = filedialog.asksaveasfilename(
        defaultextension='.csv',
        title='保存结果文件',
        filetypes=[('CSV files', '*.csv')],
    )
    root.destroy()

    if save_file_path:
        import pandas as pd

        df_matrix = pd.DataFrame(delta_T_values, index=emissivity_variable, columns=np.round(wind, 3))
        df_matrix.index.name = 'emissivity'
        df_matrix.columns.name = 'wind'
        df_matrix.to_csv(save_file_path)
        print(f'结果已保存到 {save_file_path}')

    return None
