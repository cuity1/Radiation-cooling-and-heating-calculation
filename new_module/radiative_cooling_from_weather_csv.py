#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import math
from dataclasses import dataclass
from typing import Union

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.dates as mdates
from datetime import datetime
from scipy import stats
import warnings

warnings.filterwarnings('ignore')

# =====================
# Global style controls (single knob)
# =====================
STYLE_SCALE = 1.0  # change this to scale *all* sizes consistently
FIG_DPI = 300

BASE_FIGSIZE = (10 * STYLE_SCALE, 6 * STYLE_SCALE)

plt.rcParams['font.sans-serif'] = ['Arial']
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['axes.titlesize'] = 14 * STYLE_SCALE
plt.rcParams['axes.labelsize'] = 12 * STYLE_SCALE
plt.rcParams['xtick.labelsize'] = 10 * STYLE_SCALE
plt.rcParams['ytick.labelsize'] = 10 * STYLE_SCALE
plt.rcParams['legend.fontsize'] = 10 * STYLE_SCALE

# ============ Colors (kept consistent with s.py, but simplified) ============
COLORS = {
    'blue': '#6BAED6',
    'red': '#FB6A4A',
    'green': '#74C476',
    'orange': '#FD8D3C',
    'purple': '#9E9AC8',
    'gray': '#969696',
    'yellow': '#FFD92F',
    'teal': '#66C2A4',
    'brown': '#A6761D',
    'dark_blue': '#3182BD',
    'dark_red': '#E6550D',
    'dark_green': '#31A354',
    'neutral': '#525252',
    'very_light_gray': '#F0F0F0',
}

# =====================
# Physics model copied/kept consistent with existing scripts
# =====================
Number = Union[float, int]
SIGMA = 5.670374419e-8


def sky_emissivity_poly(Ta_C: Number, RH_pct: Number, C: Number) -> float:
    Ta_C = float(Ta_C)
    RH_pct = max(0.0, min(100.0, float(RH_pct)))
    C = max(0.0, min(1.0, float(C)))

    es = 0.6108 * math.exp(17.27 * Ta_C / (Ta_C + 237.3))
    ea = (RH_pct / 100.0) * es
    TK = Ta_C + 273.15

    eps_clr = 1.24 * (ea / TK) ** (1.0 / 7.0)

    N = 10.0 * C
    corr = 1 + 0.0224 * N - 0.0035 * N**2 + 0.00028 * N**3

    eps_sky = eps_clr * corr
    return max(0.0, min(1.0, eps_sky))


def tau_atm_from_meteo(Ta_C: Number, RH_pct: Number, C: Number) -> float:
    eps_sky = sky_emissivity_poly(Ta_C, RH_pct, C)
    tau = 1.0 - eps_sky
    return max(0.0, min(1.0, tau))


@dataclass
class RadiativeCoolingParams:
    eps: Number
    rho_solar: Number
    tau_atm: Number
    sky_view: Number = 1.0
    alpha_solar: Number = None

    def __post_init__(self):
        if self.alpha_solar is None:
            self.alpha_solar = 1.0 - float(self.rho_solar)


MATERIAL_PARAMS = {
    'eps': 0.98,
    'rho_solar': 0.91,
    'sky_view': 1.0,
}


# =====================
# Meteo helpers (ERA5)
# =====================

def saturation_vapor_pressure_pa(T_C: float) -> float:
    # Tetens, Pa
    return 610.8 * math.exp(17.27 * T_C / (T_C + 237.3))


def rh_from_t_td(t2m_k: float, d2m_k: float) -> float:
    # RH = e/es, using dewpoint
    T_C = t2m_k - 273.15
    Td_C = d2m_k - 273.15
    es = saturation_vapor_pressure_pa(T_C)
    e = saturation_vapor_pressure_pa(Td_C)
    rh = 100.0 * (e / es) if es > 0 else np.nan
    return float(max(0.0, min(100.0, rh)))


def j_per_m2_to_w_per_m2(value_j_m2: float, time_step_seconds: float) -> float:
    if pd.isna(value_j_m2):
        return np.nan
    return float(value_j_m2) / float(time_step_seconds)


# =====================
# Data loading/mapping
# =====================

def load_weather_csv(filepath: str) -> pd.DataFrame:
    df = pd.read_csv(filepath)
    if 'time' not in df.columns:
        raise KeyError("CSV must contain 'time' column")

    df['日期时间'] = pd.to_datetime(df['time'])

    # Required columns in your shown file
    required = ['t2m', 'd2m', 'u10']
    for c in required:
        if c not in df.columns:
            raise KeyError(f"CSV missing required column: {c}")

    # Cloud fraction: prefer tcc
    if 'tcc' not in df.columns:
        raise KeyError("CSV missing 'tcc' (total cloud cover)")

    # Radiation: use ssrd (surface solar radiation downwards) and strd (surface thermal radiation downwards)
    if 'ssrd' not in df.columns:
        raise KeyError("CSV missing 'ssrd' (surface solar radiation downwards)")
    if 'strd' not in df.columns:
        raise KeyError("CSV missing 'strd' (surface thermal radiation downwards)")

    # Wind: if v10 exists, use it; else fallback to v10n if present; else u10 only
    if 'v10' in df.columns:
        v_col = 'v10'
    elif 'v10n' in df.columns:
        v_col = 'v10n'
    else:
        v_col = None

    df['风速_m/s'] = np.sqrt(df['u10'] ** 2 + (df[v_col] ** 2 if v_col else 0.0))

    df['近地面气温_K'] = df['t2m']
    df['气温_C'] = df['t2m'] - 273.15
    df['露点_C'] = df['d2m'] - 273.15

    df['相对湿度_%'] = [rh_from_t_td(tk, dk) for tk, dk in zip(df['t2m'].values, df['d2m'].values)]

    df['云量'] = df['tcc']

    # Determine timestep seconds from time diff median
    dt = df['日期时间'].sort_values().diff().dt.total_seconds().dropna()
    if len(dt) == 0:
        time_step_seconds = 3600.0
    else:
        time_step_seconds = float(dt.median())

    df['time_step_seconds'] = time_step_seconds

    # ERA5 accumulated radiation is typically J/m^2 over the step
    df['地表下行短波_W/m2'] = [j_per_m2_to_w_per_m2(v, time_step_seconds) for v in df['ssrd'].values]
    df['地表下行长波_W/m2'] = [j_per_m2_to_w_per_m2(v, time_step_seconds) for v in df['strd'].values]

    # Optional fields used by existing plots
    if 'ssr' in df.columns:
        df['地表净太阳辐射_W/m2'] = [j_per_m2_to_w_per_m2(v, time_step_seconds) for v in df['ssr'].values]
    else:
        df['地表净太阳辐射_W/m2'] = np.nan

    if 'str' in df.columns:
        df['地表净热辐射_W/m2'] = [j_per_m2_to_w_per_m2(v, time_step_seconds) for v in df['str'].values]
    else:
        df['地表净热辐射_W/m2'] = np.nan

    if 'sp' in df.columns:
        df['气压_Pa'] = df['sp']
    else:
        df['气压_Pa'] = np.nan

    # For s.py compatibility: provide the expected column names
    df['太阳辐射_W/m2'] = df['地表下行短波_W/m2']

    return df


# =====================
# Cooling power calculation (kept aligned with s.py component naming)
# =====================

def compute_cooling(df: pd.DataFrame, use_empirical_atm: int = 0, enable_latent_heat: bool = False, wet_fraction: float = 1.0) -> pd.DataFrame:
    out = df.copy()

    # Atmospheric transmittance derived from meteo (same as s.py)
    out['大气透过率'] = [tau_atm_from_meteo(t, rh, c) for t, rh, c in zip(out['气温_C'].values, out['相对湿度_%'].values, out['云量'].values)]
    out['天空发射率'] = 1.0 - out['大气透过率']

    params = RadiativeCoolingParams(
        eps=MATERIAL_PARAMS['eps'],
        rho_solar=MATERIAL_PARAMS['rho_solar'],
        tau_atm=1.0,  # placeholder; per-row below
        sky_view=MATERIAL_PARAMS['sky_view'],
    )

    # Components
    Ts = out['近地面气温_K'].values  # no surface temperature in this CSV; align with existing logic by using t2m as proxy
    Tatm = out['近地面气温_K'].values
    tau = out['大气透过率'].values

    out['材料热辐射_W/m2'] = MATERIAL_PARAMS['eps'] * SIGMA * (Ts ** 4)
    
    # Calculate atmospheric downwelling radiation
    # use_empirical_atm: 0=真实ERA5 strd, 1=修正混合模式(0.3经验+0.7strd), 2=理论模式(0.8经验+0.2strd)
    # If strd is missing, always fallback to empirical formula only
    model_downwelling = MATERIAL_PARAMS['eps'] * (1.0 - tau) * SIGMA * (Tatm ** 4)
    measured_downwelling = MATERIAL_PARAMS['eps'] * out['地表下行长波_W/m2'].values
    
    if use_empirical_atm == 1:
        # Corrected mixed mode: 0.3 empirical + 0.7 strd
        out['大气向下辐射_W/m2'] = np.where(
            pd.notna(out['地表下行长波_W/m2'].values),
            0.3 * model_downwelling + 0.7 * measured_downwelling,
            model_downwelling
        )
    elif use_empirical_atm == 2:
        # Theoretical mode: 0.8 empirical + 0.2 strd
        out['大气向下辐射_W/m2'] = np.where(
            pd.notna(out['地表下行长波_W/m2'].values),
            0.8 * model_downwelling + 0.2 * measured_downwelling,
            model_downwelling
        )
    else:
        # Real atmospheric data: use measured strd, fallback to empirical if missing
        out['大气向下辐射_W/m2'] = np.where(
            pd.notna(out['地表下行长波_W/m2'].values),
            measured_downwelling,
            model_downwelling
        )

    # Solar absorption uses (1-rho)*downward shortwave (same naming as earlier script)
    out['太阳吸收_W/m2'] = (1.0 - MATERIAL_PARAMS['rho_solar']) * np.maximum(0.0, out['地表下行短波_W/m2'].values)

    # First calculate net cooling power without latent heat (for surface temperature estimation)
    out['净制冷功率_无蒸发_W/m2'] = out['材料热辐射_W/m2'] - out['大气向下辐射_W/m2'] - out['太阳吸收_W/m2']

    # Calculate latent heat power if enabled (using ERA5 humidity and temperature data)
    if enable_latent_heat:
        # Import required functions
        from core.calculations import _calculate_latent_heat_power
        from core.physics import calculate_convection_coefficient
        
        # Initialize latent heat array
        Q_latent_array = np.zeros(len(out))
        
        # Ensure wet_fraction is in valid range
        wf = max(0.0, min(1.0, float(wet_fraction)))
        
        # For each row, calculate latent heat power
        # Estimate material surface temperature from energy balance
        # Simplified approach: T_surface ≈ T_ambient - ΔT, where ΔT is related to net cooling power
        for i in range(len(out)):
            T_ambient_K = out['近地面气温_K'].iloc[i]
            T_ambient_C = T_ambient_K - 273.15
            RH = out['相对湿度_%'].iloc[i] / 100.0  # Convert percentage to fraction
            
            # Estimate surface temperature from net cooling power (without latent heat)
            # Use a simplified energy balance: assume surface is slightly cooler than ambient
            # For radiative cooling, surface is typically 1-5°C below ambient
            # We use a conservative estimate based on net cooling power
            p_net_no_latent = out['净制冷功率_无蒸发_W/m2'].iloc[i]
            
            # Rough estimate: if net cooling is positive, surface is cooler
            # Use a simplified relation: ΔT ≈ p_net / (h_conv * A), but we don't have h_conv yet
            # For now, use a conservative approximation: assume 2-3°C below ambient for positive cooling
            if pd.notna(p_net_no_latent) and p_net_no_latent > 0:
                # Conservative estimate: surface is 2-3°C below ambient for typical cooling
                # This is a simplified approximation; more accurate would require iterative solution
                delta_T_estimate = min(5.0, max(0.5, p_net_no_latent / 50.0))  # Rough scaling
                T_surface_C = T_ambient_C - delta_T_estimate
            else:
                # If no net cooling or negative, surface is close to ambient
                T_surface_C = T_ambient_C - 0.5  # Small offset for safety
            
            T_surface_K = T_surface_C + 273.15
            
            # Calculate convection coefficient if wind speed is available
            wind_speed = out['风速_m/s'].iloc[i] if '风速_m/s' in out.columns and pd.notna(out['风速_m/s'].iloc[i]) else 0.0
            delta_T = T_surface_K - T_ambient_K
            h_conv = calculate_convection_coefficient(
                wind_speed=float(wind_speed),
                delta_T=float(delta_T),
                T_a=float(T_ambient_K),
                L_char=0.025,
                surface_orientation="horizontal_up",
            )
            
            # Only calculate if we have valid data
            if pd.notna(T_surface_K) and pd.notna(T_ambient_K) and pd.notna(RH):
                Q_latent_base = _calculate_latent_heat_power(
                    T_surface_K=float(T_surface_K),
                    T_ambient_K=float(T_ambient_K),
                    RH=float(RH),
                    h_conv=float(h_conv),
                )
                # Apply wet fraction scaling (consistent with cooling power calculation)
                Q_latent_array[i] = Q_latent_base * wf
            else:
                Q_latent_array[i] = 0.0
        
        out['蒸发潜热功率_W/m2'] = Q_latent_array
    else:
        # If not enabled, set to zero (ensures no change to existing calculations)
        out['蒸发潜热功率_W/m2'] = 0.0

    # Net cooling power: emission - downwelling - absorbed solar + latent heat (if enabled)
    out['净制冷功率_W/m2'] = out['材料热辐射_W/m2'] - out['大气向下辐射_W/m2'] - out['太阳吸收_W/m2'] + out['蒸发潜热功率_W/m2']

    # Ideal radiative (no solar) reference used in s.py
    out['理想制冷功率_W/m2'] = SIGMA * (Ts ** 4) - (1.0 - tau) * SIGMA * (Tatm ** 4)
    out['制冷效率'] = np.where(out['理想制冷功率_W/m2'] != 0, out['净制冷功率_W/m2'] / out['理想制冷功率_W/m2'], 0.0)

    # Time features
    out['小时'] = out['日期时间'].dt.hour
    out['日期'] = out['日期时间'].dt.date
    day_hours = range(6, 20)
    out['时段'] = out['小时'].apply(lambda x: '白天' if x in day_hours else '夜间')

    return out


# =====================
# Output directories
# =====================

def create_directories():
    dirs = ['figures', 'figures/individual']
    for d in dirs:
        if not os.path.exists(d):
            os.makedirs(d)
    return dirs


# =====================
# Plot utilities (fixed size for all single plots)
# =====================

def _format_time_axis(ax):
    locator = mdates.AutoDateLocator(minticks=4, maxticks=8)
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    for label in ax.get_xticklabels():
        label.set_rotation(30)
        label.set_ha('right')


def save_text_figure(text: str, out_path: str, title: str = None):
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    ax.axis('off')
    if title:
        ax.set_title(title)
    ax.text(
        0.01, 0.99, text,
        transform=ax.transAxes,
        va='top', ha='left',
        family='monospace',
        bbox=dict(boxstyle='round', facecolor=COLORS['very_light_gray'], alpha=0.8),
    )
    fig.tight_layout()
    fig.savefig(out_path, dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)


# =====================
# Figures split (re-implement each subplot as one figure)
# =====================

def fig1_split(df, out_dir='figures/individual'):
    # 1) Cooling power timeline (+ efficiency twin axis)
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    ax.fill_between(df['日期时间'], 0, df['净制冷功率_W/m2'], where=(df['净制冷功率_W/m2'] > 0), alpha=0.5, color=COLORS['blue'], label='Cooling (>0)')
    ax.fill_between(df['日期时间'], 0, df['净制冷功率_W/m2'], where=(df['净制冷功率_W/m2'] <= 0), alpha=0.5, color=COLORS['red'], label='Heating (≤0)')
    ax.axhline(0, color=COLORS['neutral'], linewidth=0.8)
    ax.set_ylabel('Cooling power (W/m²)')
    ax.grid(True, alpha=0.2)
    ax2 = ax.twinx()
    ax2.plot(df['日期时间'], df['制冷效率'] * 100, color=COLORS['green'], linewidth=1.5, label='Efficiency (%)', alpha=0.8)
    ax2.set_ylabel('Cooling efficiency (%)')
    _format_time_axis(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '1_1_cooling_power_timeline.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 2) Power components
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    ax.plot(df['日期时间'], df['材料热辐射_W/m2'], color=COLORS['red'], label='Thermal emission', linewidth=1.5, alpha=0.8)
    ax.plot(df['日期时间'], df['大气向下辐射_W/m2'], color=COLORS['blue'], label='Atmospheric downwelling', linewidth=1.5, alpha=0.8)
    ax.plot(df['日期时间'], df['太阳吸收_W/m2'], color=COLORS['orange'], label='Solar absorption', linewidth=1.5, alpha=0.8)
    # Add latent heat power if enabled (check if column exists and has non-zero values)
    if '蒸发潜热功率_W/m2' in df.columns and df['蒸发潜热功率_W/m2'].abs().max() > 1e-6:
        ax.plot(df['日期时间'], df['蒸发潜热功率_W/m2'], color=COLORS['teal'], label='Latent heat', linewidth=1.5, alpha=0.8)
    ax.set_ylabel('Power (W/m²)')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.2)
    _format_time_axis(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '1_2_power_components.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 3) Temperature & cloud (twin)
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    ax.plot(df['日期时间'], df['气温_C'], color=COLORS['red'], linewidth=1.5, alpha=0.8, label='Temperature (°C)')
    ax.set_ylabel('Temperature (°C)')
    ax.grid(True, alpha=0.2)
    ax2 = ax.twinx()
    ax2.fill_between(df['日期时间'], 0, df['云量'], alpha=0.3, color=COLORS['gray'], label='Cloud (0–1)')
    ax2.set_ylabel('Cloud fraction (0–1)')
    ax2.set_ylim(0, 1)
    _format_time_axis(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '1_3_temperature_cloud.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 4) Wind & humidity (twin)
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    ax.plot(df['日期时间'], df['风速_m/s'], color=COLORS['teal'], linewidth=1.5, alpha=0.8, label='Wind (m/s)')
    ax.set_ylabel('Wind speed (m/s)')
    ax.grid(True, alpha=0.2)
    ax2 = ax.twinx()
    ax2.plot(df['日期时间'], df['相对湿度_%'], color=COLORS['purple'], linewidth=1.5, alpha=0.8, label='RH (%)')
    ax2.set_ylabel('Humidity (%)')
    _format_time_axis(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '1_4_wind_humidity.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 5) Solar components
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    if '地表净太阳辐射_W/m2' in df.columns and df['地表净太阳辐射_W/m2'].notna().any():
        ax.plot(df['日期时间'], df['地表净太阳辐射_W/m2'], color=COLORS['yellow'], label='Surface net solar (W/m²)', linewidth=1.5, alpha=0.8)
    ax.plot(df['日期时间'], df['地表下行短波_W/m2'], color=COLORS['brown'], label='Surface down solar (W/m²)', linewidth=1.5, alpha=0.8)
    ax.set_ylabel('Solar irradiance (W/m²)')
    ax.set_xlabel('Time')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.2)
    _format_time_axis(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '1_5_solar_components.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)


def fig2_split(df, out_dir='figures/individual'):
    # 1) hourly variation
    hourly = df.groupby('小时')['净制冷功率_W/m2'].agg(['mean', 'std'])
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    hours = hourly.index
    ax.plot(hours, hourly['mean'], color=COLORS['dark_blue'], linewidth=2)
    ax.fill_between(hours, hourly['mean'] - hourly['std'], hourly['mean'] + hourly['std'], alpha=0.3, color=COLORS['blue'])
    ax.axhline(0, color=COLORS['neutral'], linestyle='--', alpha=0.5)
    ax.axvspan(6, 18, alpha=0.1, color=COLORS['yellow'])
    ax.set_xlabel('Hour')
    ax.set_ylabel('Cooling power (W/m²)')
    ax.set_xticks(range(0, 24, 3))
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '2_1_hourly_variation.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 2) power composition bars
    hourly2_agg = {
        '材料热辐射_W/m2': 'mean',
        '大气向下辐射_W/m2': 'mean',
        '太阳吸收_W/m2': 'mean'
    }
    # Add latent heat if enabled
    has_latent_heat = '蒸发潜热功率_W/m2' in df.columns and df['蒸发潜热功率_W/m2'].abs().max() > 1e-6
    if has_latent_heat:
        hourly2_agg['蒸发潜热功率_W/m2'] = 'mean'
    hourly2 = df.groupby('小时').agg(hourly2_agg)
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    # Positive components (stacked upward)
    bottom_pos = 0
    ax.bar(hours, hourly2['材料热辐射_W/m2'], bottom=bottom_pos, color=COLORS['red'], alpha=0.6, label='Thermal emission')
    bottom_pos = bottom_pos + hourly2['材料热辐射_W/m2']
    # Add latent heat bar if enabled (stacked on top of thermal emission)
    if has_latent_heat:
        ax.bar(hours, hourly2['蒸发潜热功率_W/m2'], bottom=bottom_pos, color=COLORS['teal'], alpha=0.6, label='Latent heat')
    # Negative components (stacked downward)
    bottom_neg = 0
    ax.bar(hours, -hourly2['大气向下辐射_W/m2'], bottom=bottom_neg, color=COLORS['blue'], alpha=0.6, label='Atmospheric absorption')
    bottom_neg = bottom_neg - hourly2['大气向下辐射_W/m2']
    ax.bar(hours, -hourly2['太阳吸收_W/m2'], bottom=bottom_neg, color=COLORS['orange'], alpha=0.6, label='Solar absorption')
    ax.axhline(0, color=COLORS['neutral'], linewidth=0.5)
    ax.set_xlabel('Hour')
    ax.set_ylabel('Power (W/m²)')
    ax.set_xticks(range(0, 24, 3))
    ax.grid(True, alpha=0.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '2_2_power_composition.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 3) day vs night box
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    day = df[df['时段'] == '白天']['净制冷功率_W/m2']
    night = df[df['时段'] == '夜间']['净制冷功率_W/m2']
    bp = ax.boxplot([day, night], labels=['Day', 'Night'], patch_artist=True, showmeans=True)
    for patch, color in zip(bp['boxes'], [COLORS['yellow'], COLORS['dark_blue']]):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)
    ax.axhline(0, color=COLORS['neutral'], linestyle='--', alpha=0.5)
    ax.set_ylabel('Cooling power (W/m²)')
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '2_3_day_night_boxplot.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 4) cooling vs temperature
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    for period, color, label in [('白天', COLORS['orange'], 'Day'), ('夜间', COLORS['blue'], 'Night')]:
        dd = df[df['时段'] == period]
        ax.scatter(dd['气温_C'], dd['净制冷功率_W/m2'], alpha=0.5, s=20, color=color, label=label)
    ax.axhline(0, color=COLORS['neutral'], linestyle='--', alpha=0.5)
    ax.set_xlabel('Temperature (°C)')
    ax.set_ylabel('Cooling power (W/m²)')
    ax.grid(True, alpha=0.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '2_4_cooling_vs_temperature.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 5) cooling vs wind
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    for period, color, label in [('白天', COLORS['orange'], 'Day'), ('夜间', COLORS['blue'], 'Night')]:
        dd = df[df['时段'] == period]
        ax.scatter(dd['风速_m/s'], dd['净制冷功率_W/m2'], alpha=0.5, s=20, color=color, label=label)
    ax.axhline(0, color=COLORS['neutral'], linestyle='--', alpha=0.5)
    ax.set_xlabel('Wind (m/s)')
    ax.set_ylabel('Cooling power (W/m²)')
    ax.grid(True, alpha=0.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '2_5_cooling_vs_wind.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 6) humidity vs solar (aligned with s.py bottom-right intent)
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    if '地表净太阳辐射_W/m2' in df.columns and df['地表净太阳辐射_W/m2'].notna().any():
        y_col = '地表净太阳辐射_W/m2'
        y_label = 'Surface net solar (W/m²)'
    else:
        y_col = '地表下行短波_W/m2'
        y_label = 'Surface down solar (W/m²)'

    for period, color, label in [('白天', COLORS['orange'], 'Day'), ('夜间', COLORS['blue'], 'Night')]:
        dd = df[df['时段'] == period]
        ax.scatter(dd['相对湿度_%'], dd[y_col], alpha=0.5, s=20, color=color, label=label)

    ax.set_xlabel('Humidity (%)')
    ax.set_ylabel(y_label)
    ax.grid(True, alpha=0.2)
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '2_6_humidity_vs_solar.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)


def fig3_split(df, out_dir='figures/individual'):
    # 1) distribution
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    ax.hist(df['净制冷功率_W/m2'], bins=50, edgecolor=COLORS['neutral'], alpha=0.6, color=COLORS['blue'], density=True)
    mu, std = df['净制冷功率_W/m2'].mean(), df['净制冷功率_W/m2'].std()
    x = np.linspace(ax.get_xlim()[0], ax.get_xlim()[1], 100)
    ax.plot(x, stats.norm.pdf(x, mu, std), color=COLORS['dark_red'], linewidth=2)
    ax.axvline(0, color=COLORS['neutral'], linestyle='--', alpha=0.5)
    ax.set_xlabel('Cooling power (W/m²)')
    ax.set_ylabel('Probability density')
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '3_1_distribution.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 2) cumulative
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    dd = df.sort_values('日期时间').copy()
    dd['累积制冷量_kWh'] = dd['净制冷功率_W/m2'].cumsum() / 1000.0
    ax.plot(dd['日期时间'], dd['累积制冷量_kWh'], color=COLORS['dark_blue'], linewidth=2)
    ax.fill_between(dd['日期时间'], 0, dd['累积制冷量_kWh'], alpha=0.3, color=COLORS['blue'])
    ax.set_xlabel('Time')
    ax.set_ylabel('Cumulative cooling (kWh/m²)')
    ax.grid(True, alpha=0.2)
    _format_time_axis(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '3_2_cumulative.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 3) material vs ideal
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    sc = ax.scatter(df['理想制冷功率_W/m2'], df['净制冷功率_W/m2'], alpha=0.5, s=10, c=df['小时'], cmap='coolwarm')
    lim = max(abs(df['理想制冷功率_W/m2'].min()), df['理想制冷功率_W/m2'].max(), abs(df['净制冷功率_W/m2'].min()), df['净制冷功率_W/m2'].max())
    ax.plot([-lim, lim], [-lim, lim], color=COLORS['dark_red'], linestyle='--', alpha=0.5)
    ax.set_xlabel('Ideal cooling power (W/m²)')
    ax.set_ylabel('Cooling power (W/m²)')
    ax.grid(True, alpha=0.2)
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    fig.colorbar(sc, ax=ax).set_label('Hour')
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '3_3_material_vs_ideal.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 4) heatmap: cloud vs temp
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    temp_bins = pd.cut(df['气温_C'], bins=5)
    cloud_bins = pd.cut(df['云量'], bins=5)
    pivot = df.pivot_table(values='净制冷功率_W/m2', index=cloud_bins, columns=temp_bins, aggfunc='mean')
    sns.heatmap(pivot, annot=True, fmt='.1f', cmap='RdBu_r', center=0, ax=ax, cbar_kws={'label': 'Cooling power (W/m²)'})
    ax.set_xlabel('Temperature bin (°C)')
    ax.set_ylabel('Cloudiness bin')
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '3_4_heatmap_cloud_temp.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 5) radar (keep as in s.py but single)
    metrics = {
        'Avg net cooling': df['净制冷功率_W/m2'].mean() / 100,
        'Peak net cooling': df['净制冷功率_W/m2'].max() / 200,
        'Night avg': df[df['时段'] == '夜间']['净制冷功率_W/m2'].mean() / 100,
        'Stability': 1 - (df['净制冷功率_W/m2'].std() / abs(df['净制冷功率_W/m2'].mean())) if df['净制冷功率_W/m2'].mean() != 0 else 0,
        'ε_LW': MATERIAL_PARAMS['eps'],
        'ρ_solar': MATERIAL_PARAMS['rho_solar'],
    }
    angles = np.linspace(0, 2 * np.pi, len(metrics), endpoint=False)
    values = [max(0, min(1, v)) for v in metrics.values()]
    values += values[:1]
    angles = np.concatenate([angles, [angles[0]]])

    fig = plt.figure(figsize=BASE_FIGSIZE)
    ax = fig.add_subplot(111, projection='polar')
    ax.plot(angles, values, color=COLORS['dark_blue'], linewidth=2)
    ax.fill(angles, values, color=COLORS['blue'], alpha=0.25)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(list(metrics.keys()))
    ax.set_ylim(0, 1)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '3_5_radar.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 6) transmittance effect
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    sc = ax.scatter(df['大气透过率'], df['净制冷功率_W/m2'], alpha=0.5, s=20, c=df['云量'], cmap='gray_r')
    z = np.polyfit(df['大气透过率'], df['净制冷功率_W/m2'], 1)
    p = np.poly1d(z)
    x_trend = np.linspace(df['大气透过率'].min(), df['大气透过率'].max(), 100)
    ax.plot(x_trend, p(x_trend), color=COLORS['dark_red'], linewidth=2)
    ax.axhline(0, color=COLORS['neutral'], linestyle='--', alpha=0.5)
    ax.set_xlabel('Atmospheric transmittance')
    ax.set_ylabel('Cooling power (W/m²)')
    ax.grid(True, alpha=0.2)
    fig.colorbar(sc, ax=ax).set_label('Cloud fraction')
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '3_6_transmittance_effect.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)


def fig4_split(df, out_dir='figures/individual'):
    # 1) solar reflectance optimization
    reflectances = np.arange(0.85, 0.99, 0.02)
    avg_cooling = []
    for r in reflectances:
        solar_absorbed = (1 - r) * df['太阳辐射_W/m2']
        cooling = df['材料热辐射_W/m2'] - df['大气向下辐射_W/m2'] - solar_absorbed
        avg_cooling.append(cooling.mean())
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    ax.plot(reflectances * 100, avg_cooling, color=COLORS['dark_blue'], linewidth=2)
    ax.axvline(x=MATERIAL_PARAMS['rho_solar'] * 100, color=COLORS['dark_red'], linestyle='--', linewidth=2)
    ax.set_xlabel('Solar reflectance (%)')
    ax.set_ylabel('Average cooling power (W/m²)')
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '4_1_solar_reflectance_opt.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 2) emissivity optimization
    emissivities = np.arange(0.90, 1.00, 0.01)
    avg_cooling_em = []
    for e in emissivities:
        thermal_rad = e * SIGMA * (df['近地面气温_K'] ** 4)
        cooling = thermal_rad - df['大气向下辐射_W/m2'] - df['太阳吸收_W/m2']
        avg_cooling_em.append(cooling.mean())
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    ax.plot(emissivities * 100, avg_cooling_em, color=COLORS['dark_green'], linewidth=2)
    ax.axvline(x=MATERIAL_PARAMS['eps'] * 100, color=COLORS['dark_red'], linestyle='--', linewidth=2)
    ax.set_xlabel('Longwave emissivity (%)')
    ax.set_ylabel('Average cooling power (W/m²)')
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '4_2_emissivity_opt.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 3) best conditions class
    dd = df.copy()
    dd['制冷等级'] = pd.cut(dd['净制冷功率_W/m2'], bins=[-np.inf, 0, 50, 100, np.inf], labels=['Poor (<0)', 'Fair (0–50)', 'Good (50–100)', 'Excellent (>100)'])
    condition_stats = dd.groupby('制冷等级').agg({'气温_C': 'mean', '云量': 'mean', '风速_m/s': 'mean', '净制冷功率_W/m2': 'count'})
    x = np.arange(len(condition_stats.index))
    width = 0.25
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    ax2 = ax.twinx()
    ax.bar(x - width, condition_stats['气温_C'], width, color=COLORS['red'], alpha=0.6, label='Temp (°C)')
    ax.bar(x, condition_stats['云量'] * 30, width, color=COLORS['gray'], alpha=0.6, label='Cloud ×30')
    ax.bar(x + width, condition_stats['风速_m/s'] * 5, width, color=COLORS['blue'], alpha=0.6, label='Wind ×5')
    ax2.plot(x, condition_stats['净制冷功率_W/m2'], color=COLORS['dark_green'], marker='o', linewidth=2, label='Count')
    ax.set_xticks(x)
    ax.set_xticklabels([str(i) for i in condition_stats.index])
    ax.set_xlabel('Cooling class')
    ax.set_ylabel('Scaled environmental parameters')
    ax2.set_ylabel('Sample count')
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '4_3_best_conditions.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 4) correlation matrix (English labels to avoid Chinese font issues)
    corr_key_to_label = {
        '净制冷功率_W/m2': 'Net cooling power (W/m²)',
        '气温_C': 'Air temperature (°C)',
        '云量': 'Cloud fraction',
        '地表净太阳辐射_W/m2': 'Surface net solar (W/m²)',
        '风速_m/s': 'Wind speed (m/s)',
        '大气透过率': 'Atmospheric transmittance',
    }
    # Add latent heat if enabled
    if '蒸发潜热功率_W/m2' in df.columns and df['蒸发潜热功率_W/m2'].abs().max() > 1e-6:
        corr_key_to_label['蒸发潜热功率_W/m2'] = 'Latent heat (W/m²)'

    corr_keys = [k for k in corr_key_to_label.keys() if k in df.columns]
    corr = df[corr_keys].corr()
    corr_vars = [corr_key_to_label[k] for k in corr_keys]
    corr.columns = corr_vars
    corr.index = corr_vars
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    im = ax.imshow(corr, cmap='RdBu_r', vmin=-1, vmax=1, alpha=0.8)
    ax.set_xticks(range(len(corr_vars)))
    ax.set_yticks(range(len(corr_vars)))
    ax.set_xticklabels(corr_vars, rotation=30, ha='right')
    ax.set_yticklabels(corr_vars)
    for i in range(len(corr_vars)):
        for j in range(len(corr_vars)):
            ax.text(j, i, f'{corr.iloc[i, j]:.2f}', ha='center', va='center', color='white' if abs(corr.iloc[i, j]) > 0.5 else 'black')
    fig.colorbar(im, ax=ax, fraction=0.06, pad=0.04)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '4_4_correlation_matrix.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 5) humidity bins
    humidity_bins = pd.cut(df['相对湿度_%'], bins=5)
    humidity_stats = df.groupby(humidity_bins)['净制冷功率_W/m2'].agg(['mean', 'std'])
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    x_pos = range(len(humidity_stats))
    ax.bar(list(x_pos), humidity_stats['mean'], yerr=humidity_stats['std'], capsize=5, color=COLORS['purple'], alpha=0.6)
    ax.set_xticks(list(x_pos))
    ax.set_xticklabels([f'{i.left:.0f}-{i.right:.0f}%' for i in humidity_stats.index], rotation=45)
    ax.set_xlabel('Relative humidity bin')
    ax.set_ylabel('Average cooling power (W/m²)')
    ax.grid(True, alpha=0.2, axis='y')
    ax.axhline(0, color=COLORS['neutral'], linestyle='--', alpha=0.5)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '4_5_humidity_effect.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 6) recommendation text
    avg_cooling = df['净制冷功率_W/m2'].mean()
    max_cooling = df['净制冷功率_W/m2'].max()
    night_cooling = df[df['时段'] == '夜间']['净制冷功率_W/m2'].mean()
    best_hour = df.groupby('小时')['净制冷功率_W/m2'].mean().idxmax()
    efficiency = (df['净制冷功率_W/m2'] > 0).mean() * 100

    suggestions = f"""
[Material performance summary]
• Average Cooling power: {avg_cooling:.1f} W/m²
• Peak Cooling power: {max_cooling:.1f} W/m²
• Nighttime average power: {night_cooling:.1f} W/m²
• Effective cooling time: {efficiency:.1f}%
• Best operating hour: {best_hour}:00

[Recommendations]
1) Increase solar reflectance
   Current {MATERIAL_PARAMS['rho_solar']:.0%} → target 95%+

2) Longwave emissivity
   Current {MATERIAL_PARAMS['eps']:.0%} (near ideal)

3) Optimal environmental conditions
   • Low cloud fraction (<30%)
   • Low humidity (<50%)
   • Moderate temperature (15–25°C)

4) Application tips
   • Prioritize nighttime operation
   • Best under clear skies
   • Consider spectrally selective emitters/coatings
"""
    save_text_figure(suggestions, os.path.join(out_dir, '4_6_recommendations.png'), title='Recommendations summary')


def fig5_split(df, out_dir='figures/individual'):
    # 5 in s.py is a composite report with cards + plots + summary table.
    # Here we export 7 plots + 2 text figures (cards + table) as requested.

    # (Text) KPI cards
    total_cooling = df['净制冷功率_W/m2'].sum() / 1000
    avg_cooling = df['净制冷功率_W/m2'].mean()
    efficiency = (df['净制冷功率_W/m2'] > 0).mean() * 100
    max_cooling = df['净制冷功率_W/m2'].max()

    cards_text = f"""
Total cooling: {total_cooling:.2f} kWh/m²
Avg. net cooling: {avg_cooling:.2f} W/m²
Effective cooling time: {efficiency:.1f}%
Max net cooling: {max_cooling:.2f} W/m²
""".strip()
    save_text_figure(cards_text, os.path.join(out_dir, '5_0_kpi_cards.png'), title='KPI summary')

    # 1) time series
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    ax.plot(df['日期时间'], df['净制冷功率_W/m2'], color=COLORS['dark_blue'], linewidth=1, alpha=0.8)
    ax.fill_between(df['日期时间'], 0, df['净制冷功率_W/m2'], where=(df['净制冷功率_W/m2'] > 0), alpha=0.3, color=COLORS['blue'])
    ax.axhline(0, color=COLORS['neutral'], linewidth=0.5)
    ax.set_ylabel('Cooling power (W/m²)')
    ax.grid(True, alpha=0.2)
    _format_time_axis(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '5_1_time_series.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 2) 24h average bar
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    hourly_avg = df.groupby('小时')['净制冷功率_W/m2'].mean()
    ax.bar(hourly_avg.index, hourly_avg.values, color=COLORS['blue'], alpha=0.7)
    ax.axhline(0, color=COLORS['neutral'], linestyle='--', alpha=0.5)
    ax.set_xlabel('Hour')
    ax.set_ylabel('Average power (W/m²)')
    ax.set_xticks(range(0, 24, 3))
    ax.grid(True, alpha=0.2, axis='y')
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '5_2_hourly_avg.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 3) distribution
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    ax.hist(df['净制冷功率_W/m2'], bins=30, edgecolor=COLORS['neutral'], alpha=0.6, color=COLORS['green'])
    ax.axvline(0, color=COLORS['dark_red'], linestyle='--', alpha=0.5)
    ax.axvline(avg_cooling, color=COLORS['dark_blue'], linewidth=2)
    ax.set_xlabel('Cooling power (W/m²)')
    ax.set_ylabel('Count')
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '5_3_distribution.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 4) cloud-temp-power scatter
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    sc = ax.scatter(df['云量'], df['净制冷功率_W/m2'], c=df['气温_C'], cmap='RdBu_r', alpha=0.5, s=20)
    fig.colorbar(sc, ax=ax).set_label('Temperature (°C)')
    ax.axhline(0, color=COLORS['neutral'], linestyle='--', alpha=0.5)
    ax.set_xlabel('Cloud fraction')
    ax.set_ylabel('Cooling power (W/m²)')
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '5_4_cloud_temp_power.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 5) day/night box
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    day = df[df['时段'] == '白天']['净制冷功率_W/m2']
    night = df[df['时段'] == '夜间']['净制冷功率_W/m2']
    bp = ax.boxplot([day, night], labels=['Day', 'Night'], patch_artist=True, showmeans=True)
    for patch, color in zip(bp['boxes'], [COLORS['yellow'], COLORS['dark_blue']]):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)
    ax.axhline(0, color=COLORS['neutral'], linestyle='--', alpha=0.5)
    ax.set_ylabel('Cooling power (W/m²)')
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '5_5_day_night_box.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 6) efficiency time series
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    ax.plot(df['日期时间'], df['制冷效率'] * 100, color=COLORS['purple'], linewidth=1, alpha=0.8)
    ax.fill_between(df['日期时间'], 0, df['制冷效率'] * 100, alpha=0.3, color=COLORS['purple'])
    ax.set_ylabel('Cooling efficiency (%)')
    ax.set_ylim(-100, 100)
    ax.grid(True, alpha=0.2)
    _format_time_axis(ax)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '5_6_efficiency.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # 7) transmittance effect
    fig, ax = plt.subplots(figsize=BASE_FIGSIZE)
    ax.scatter(df['大气透过率'], df['净制冷功率_W/m2'], alpha=0.5, s=20, color=COLORS['teal'])
    ax.axhline(0, color=COLORS['neutral'], linestyle='--', alpha=0.5)
    ax.set_xlabel('Atmospheric transmittance')
    ax.set_ylabel('Cooling power (W/m²)')
    ax.grid(True, alpha=0.2)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, '5_7_transmittance.png'), dpi=FIG_DPI, bbox_inches='tight')
    plt.close(fig)

    # (Text) summary table
    day_data = df[df['时段'] == '白天']
    night_data = df[df['时段'] == '夜间']
    day_avg = day_data['净制冷功率_W/m2'].mean()
    night_avg = night_data['净制冷功率_W/m2'].mean()
    std_dev = df['净制冷功率_W/m2'].std()

    rows = [
        ('Avg. net cooling', f'{avg_cooling:8.2f} W/m^2'),
        ('Daytime average', f'{day_avg:8.2f} W/m^2'),
        ('Nighttime average', f'{night_avg:8.2f} W/m^2'),
        ('Maximum', f'{max_cooling:8.2f} W/m^2'),
        ('Std. dev.', f'{std_dev:8.2f} W/m^2'),
        ('Effective time ratio', f'{efficiency:8.1f} %'),
        ('Total cooling', f'{total_cooling:8.2f} kWh/m^2'),
    ]

    table_text = '\n'.join([f'{k}: {v}' for k, v in rows])
    save_text_figure(table_text, os.path.join(out_dir, '5_8_summary_table.png'), title='Summary table')


# =====================
# Main
# =====================

def main(weather_csv_path='weather/era5_merged.csv'):
    print("=" * 60)
    print("Radiative cooling from weather CSV")
    print("=" * 60)

    create_directories()

    print(f"Loading weather data: {weather_csv_path}")
    df_raw = load_weather_csv(weather_csv_path)
    df = compute_cooling(df_raw)

    # Export results (keep same file name style)
    out_csv = 'radiative_cooling_results_from_weather.csv'
    df.to_csv(out_csv, index=False, encoding='utf-8-sig')
    print(f"Saved results: {out_csv}")

    # Split figures as requested
    out_dir = 'figures/individual'

    print("Exporting split figures...")
    fig1_split(df, out_dir)
    fig2_split(df, out_dir)
    fig3_split(df, out_dir)
    fig4_split(df, out_dir)
    fig5_split(df, out_dir)

    print("Done.")
    return df


if __name__ == '__main__':
    main('weather/era5_merged.csv')
