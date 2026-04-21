from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PlotSpec:
    plot_id: str
    title: str
    kind: str
    # Optional: if the underlying PNG is text/table and we still want a plotly preview,
    # we can set kind accordingly.


# 32 plots aligned with output/results/figures/*.png
PLOTS: List[PlotSpec] = [
    PlotSpec("1_1_cooling_power_timeline", "Cooling power timeline (+efficiency)", "timeseries"),
    PlotSpec("1_2_power_components", "Power components (time)", "timeseries"),
    PlotSpec("1_3_temperature_cloud", "Temperature & cloud (time)", "timeseries"),
    PlotSpec("1_4_wind_humidity", "Wind & humidity (time)", "timeseries"),
    PlotSpec("1_5_solar_components", "Solar components (time)", "timeseries"),

    PlotSpec("2_1_hourly_variation", "Hourly variation (mean±std)", "line_band"),
    PlotSpec("2_2_power_composition", "Hourly power composition (stacked)", "stacked_bar"),
    PlotSpec("2_3_day_night_boxplot", "Day vs Night (box)", "box"),
    PlotSpec("2_4_cooling_vs_temperature", "Cooling vs temperature (day/night)", "scatter_group"),
    PlotSpec("2_5_cooling_vs_wind", "Cooling vs wind (day/night)", "scatter_group"),
    PlotSpec("2_6_humidity_vs_solar", "Humidity vs solar (day/night)", "scatter_group"),

    PlotSpec("3_1_distribution", "Distribution (hist)", "hist"),
    PlotSpec("3_2_cumulative", "Cumulative cooling", "timeseries"),
    PlotSpec("3_3_material_vs_ideal", "Material vs ideal", "scatter_color"),
    PlotSpec("3_4_heatmap_cloud_temp", "Heatmap: cloud vs temperature", "heatmap"),
    PlotSpec("3_5_radar", "Radar metrics", "radar"),
    PlotSpec("3_6_transmittance_effect", "Transmittance effect", "scatter"),

    PlotSpec("4_1_solar_reflectance_opt", "Solar reflectance optimization", "line"),
    PlotSpec("4_2_emissivity_opt", "Emissivity optimization", "line"),
    PlotSpec("4_3_best_conditions", "Best conditions", "scatter"),
    PlotSpec("4_4_correlation_matrix", "Correlation matrix", "heatmap"),
    PlotSpec("4_5_humidity_effect", "Humidity effect (alt)", "scatter"),
    PlotSpec("4_6_recommendations", "Recommendations summary", "text"),

    PlotSpec("5_0_kpi_cards", "KPI cards", "text"),
    PlotSpec("5_1_time_series", "Report: net cooling time series", "timeseries"),
    PlotSpec("5_2_hourly_avg", "Report: hourly average", "bar"),
    PlotSpec("5_3_distribution", "Report: distribution", "hist"),
    PlotSpec("5_4_cloud_temp_power", "Report: cloud-temp-power", "scatter_color"),
    PlotSpec("5_5_day_night_box", "Report: day/night box", "box"),
    PlotSpec("5_6_efficiency", "Report: efficiency time series", "timeseries"),
    PlotSpec("5_7_transmittance", "Report: transmittance effect", "scatter"),
    PlotSpec("5_8_summary_table", "Report: summary table", "table"),
]


def list_supported_plot_ids() -> List[str]:
    return [p.plot_id for p in PLOTS]


def build_plot(plot_id: str, df: pd.DataFrame) -> Dict:
    builders: Dict[str, Callable[[pd.DataFrame], Dict]] = {
        # fig1_split
        "1_1_cooling_power_timeline": _plot_1_1,
        "1_2_power_components": _plot_1_2,
        "1_3_temperature_cloud": _plot_1_3,
        "1_4_wind_humidity": _plot_1_4,
        "1_5_solar_components": _plot_1_5,

        # fig2_split
        "2_1_hourly_variation": _plot_2_1,
        "2_2_power_composition": _plot_2_2,
        "2_3_day_night_boxplot": _plot_2_3,
        "2_4_cooling_vs_temperature": _plot_2_4,
        "2_5_cooling_vs_wind": _plot_2_5,
        "2_6_humidity_vs_solar": _plot_2_6,

        # fig3_split
        "3_1_distribution": _plot_3_1,
        "3_2_cumulative": _plot_3_2,
        "3_3_material_vs_ideal": _plot_3_3,
        "3_4_heatmap_cloud_temp": _plot_3_4,
        "3_5_radar": _plot_3_5,
        "3_6_transmittance_effect": _plot_3_6,

        # fig4/fig5 approximations
        "4_1_solar_reflectance_opt": _plot_4_1,
        "4_2_emissivity_opt": _plot_4_2,
        "4_3_best_conditions": _plot_4_3,
        "4_4_correlation_matrix": _plot_4_4,
        "4_5_humidity_effect": _plot_4_5,
        "4_6_recommendations": _plot_4_6_text,

        "5_0_kpi_cards": _plot_5_0_text,
        "5_1_time_series": _plot_5_1,
        "5_2_hourly_avg": _plot_5_2,
        "5_3_distribution": _plot_5_3,
        "5_4_cloud_temp_power": _plot_5_4,
        "5_5_day_night_box": _plot_5_5,
        "5_6_efficiency": _plot_5_6,
        "5_7_transmittance": _plot_5_7,
        "5_8_summary_table": _plot_5_8_table,
    }

    if plot_id not in builders:
        raise KeyError(plot_id)

    return builders[plot_id](df)


def _require(df: pd.DataFrame, *cols: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise KeyError(f"Missing columns: {missing}")


def _time_col(df: pd.DataFrame) -> str:
    if "日期时间" in df.columns:
        return "日期时间"
    if "time" in df.columns:
        return "time"
    raise KeyError("Missing time column")


def _plot_1_1(df: pd.DataFrame) -> Dict:
    _require(df, "净制冷功率_W/m2", "制冷效率")
    tcol = _time_col(df)
    data_df = df[[tcol, "净制冷功率_W/m2", "制冷效率"]].copy()

    # Match matplotlib fig1_split first panel more closely:
    # - line for net cooling power
    # - blue filled area where cooling > 0
    # - red filled area where cooling < 0
    # - horizontal 0 line
    # - efficiency (%) as a secondary y-axis line
    time_vals = data_df[tcol].astype(str).tolist()
    power_vals = data_df["净制冷功率_W/m2"].astype(float).tolist()
    eff_vals = (data_df["制冷效率"].astype(float) * 100.0).tolist()

    # Split positive / negative for filled areas
    pos_vals = [v if v > 0 else 0.0 for v in power_vals]
    neg_vals = [v if v <= 0 else 0.0 for v in power_vals]

    spec = {
        "data": [
            # Line for net cooling power (on top of filled areas)
            {
                "type": "scatter",
                "mode": "lines",
                "name": "Net cooling power",
                "x": time_vals,
                "y": power_vals,
                "line": {"color": "#3182BD", "width": 2},  # dark_blue
                "yaxis": "y1",
            },
            # Positive cooling area
            {
                "type": "scatter",
                "mode": "lines",
                "name": "Cooling (>0)",
                "x": time_vals,
                "y": pos_vals,
                "line": {"width": 0},
                "fill": "tozeroy",
                "fillcolor": "rgba(107,174,214,0.6)",  # COLORS['blue'] with alpha
                "showlegend": False,
            },
            # Negative (heating) area
            {
                "type": "scatter",
                "mode": "lines",
                "name": "Heating (≤0)",
                "x": time_vals,
                "y": neg_vals,
                "line": {"width": 0},
                "fill": "tozeroy",
                "fillcolor": "rgba(251,106,74,0.6)",  # COLORS['red'] with alpha
                "showlegend": False,
            },
            # Zero reference line
            {
                "type": "scatter",
                "mode": "lines",
                "name": "0",
                "x": time_vals,
                "y": [0.0] * len(time_vals),
                "line": {"color": "#525252", "width": 1},  # COLORS['neutral']
                "showlegend": False,
            },
            # Efficiency on secondary axis
            {
                "type": "scatter",
                "mode": "lines",
                "name": "Efficiency (%)",
                "x": time_vals,
                "y": eff_vals,
                "yaxis": "y2",
                "line": {"color": "#31A354", "width": 1.5},  # COLORS['green']
            },
        ],
        "layout": {
            "title": "Cooling power timeline",
            "xaxis": {"title": "Time"},
            "yaxis": {"title": "Cooling power (W/m²)"},
            "yaxis2": {
                "title": "Cooling efficiency (%)",
                "overlaying": "y",
                "side": "right",
            },
            "margin": {"l": 60, "r": 60, "t": 50, "b": 50},
            "legend": {"orientation": "h"},
        },
    }
    return {"spec": spec, "data": data_df}


def _plot_1_2(df: pd.DataFrame) -> Dict:
    _require(df, "材料热辐射_W/m2", "大气向下辐射_W/m2", "太阳吸收_W/m2")
    tcol = _time_col(df)
    cols = [tcol, "材料热辐射_W/m2", "大气向下辐射_W/m2", "太阳吸收_W/m2"]
    # Add latent heat if enabled
    has_latent_heat = "蒸发潜热功率_W/m2" in df.columns and df["蒸发潜热功率_W/m2"].abs().max() > 1e-6
    if has_latent_heat:
        cols.append("蒸发潜热功率_W/m2")
    data_df = df[cols].copy()
    data_series = [
        {"type": "scatter", "mode": "lines", "name": "Thermal emission", "x": data_df[tcol].astype(str).tolist(), "y": data_df["材料热辐射_W/m2"].astype(float).tolist()},
        {"type": "scatter", "mode": "lines", "name": "Atmospheric downwelling", "x": data_df[tcol].astype(str).tolist(), "y": data_df["大气向下辐射_W/m2"].astype(float).tolist()},
        {"type": "scatter", "mode": "lines", "name": "Solar absorption", "x": data_df[tcol].astype(str).tolist(), "y": data_df["太阳吸收_W/m2"].astype(float).tolist()},
    ]
    # Add latent heat if enabled
    if has_latent_heat:
        data_series.append({
            "type": "scatter",
            "mode": "lines",
            "name": "Latent heat",
            "x": data_df[tcol].astype(str).tolist(),
            "y": data_df["蒸发潜热功率_W/m2"].astype(float).tolist(),
            "line": {"color": "#66C2A4"},  # teal color
        })
    spec = {
        "data": data_series,
        "layout": {"title": "Power components", "xaxis": {"title": "Time"}, "yaxis": {"title": "W/m²"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": data_df}


def _plot_1_3(df: pd.DataFrame) -> Dict:
    _require(df, "气温_C", "云量")
    tcol = _time_col(df)
    data_df = df[[tcol, "气温_C", "云量"]].copy()
    spec = {
        "data": [
            {"type": "scatter", "mode": "lines", "name": "Temp (°C)", "x": data_df[tcol].astype(str).tolist(), "y": data_df["气温_C"].astype(float).tolist(), "yaxis": "y1"},
            {"type": "scatter", "mode": "lines", "name": "Cloud", "x": data_df[tcol].astype(str).tolist(), "y": data_df["云量"].astype(float).tolist(), "yaxis": "y2"},
        ],
        "layout": {
            "title": "Temperature & cloud",
            "xaxis": {"title": "Time"},
            "yaxis": {"title": "°C"},
            "yaxis2": {"title": "Cloud (0-1)", "overlaying": "y", "side": "right", "range": [0, 1]},
            "margin": {"l": 60, "r": 60, "t": 50, "b": 50},
            "legend": {"orientation": "h"},
        },
    }
    return {"spec": spec, "data": data_df}


def _plot_1_4(df: pd.DataFrame) -> Dict:
    # humidity column differs between modules: 相对湿度_% in split figures
    _require(df, "风速_m/s")
    tcol = _time_col(df)
    rh_col = "相对湿度_%" if "相对湿度_%" in df.columns else ("相对湿度" if "相对湿度" in df.columns else None)
    if rh_col is None:
        raise KeyError("Missing humidity column")

    data_df = df[[tcol, "风速_m/s", rh_col]].copy()
    spec = {
        "data": [
            {"type": "scatter", "mode": "lines", "name": "Wind (m/s)", "x": data_df[tcol].astype(str).tolist(), "y": data_df["风速_m/s"].astype(float).tolist(), "yaxis": "y1"},
            {"type": "scatter", "mode": "lines", "name": "RH (%)", "x": data_df[tcol].astype(str).tolist(), "y": data_df[rh_col].astype(float).tolist(), "yaxis": "y2"},
        ],
        "layout": {
            "title": "Wind & humidity",
            "xaxis": {"title": "Time"},
            "yaxis": {"title": "m/s"},
            "yaxis2": {"title": "%", "overlaying": "y", "side": "right"},
            "margin": {"l": 60, "r": 60, "t": 50, "b": 50},
            "legend": {"orientation": "h"},
        },
    }
    return {"spec": spec, "data": data_df}


def _plot_1_5(df: pd.DataFrame) -> Dict:
    tcol = _time_col(df)
    # prefer net solar if present
    cols = [tcol]
    series: List[Tuple[str, str]] = []
    if "地表净太阳辐射_W/m2" in df.columns and df["地表净太阳辐射_W/m2"].notna().any():
        cols.append("地表净太阳辐射_W/m2")
        series.append(("Surface net solar", "地表净太阳辐射_W/m2"))
    _require(df, "地表下行短波_W/m2")
    cols.append("地表下行短波_W/m2")
    series.append(("Surface down solar", "地表下行短波_W/m2"))

    data_df = df[cols].copy()
    spec_data = []
    for name, c in series:
        spec_data.append({"type": "scatter", "mode": "lines", "name": name, "x": data_df[tcol].astype(str).tolist(), "y": data_df[c].astype(float).tolist()})

    spec = {
        "data": spec_data,
        "layout": {"title": "Solar components", "xaxis": {"title": "Time"}, "yaxis": {"title": "W/m²"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": data_df}


def _plot_2_1(df: pd.DataFrame) -> Dict:
    _require(df, "小时", "净制冷功率_W/m2")
    g = df.groupby("小时")["净制冷功率_W/m2"].agg(["mean", "std"]).reset_index()
    g["小时"] = g["小时"].astype(int)

    spec = {
        "data": [
            {"type": "scatter", "mode": "lines", "name": "mean", "x": g["小时"].tolist(), "y": g["mean"].astype(float).tolist()},
            {
                "type": "scatter",
                "mode": "lines",
                "name": "mean+std",
                "x": g["小时"].tolist(),
                "y": (g["mean"] + g["std"]).astype(float).tolist(),
                "line": {"width": 0},
                "showlegend": False,
            },
            {
                "type": "scatter",
                "mode": "lines",
                "name": "mean-std",
                "x": g["小时"].tolist(),
                "y": (g["mean"] - g["std"]).astype(float).tolist(),
                "fill": "tonexty",
                "fillcolor": "rgba(31,119,180,0.2)",
                "line": {"width": 0},
                "showlegend": False,
            },
        ],
        "layout": {"title": "Hourly variation (mean±std)", "xaxis": {"title": "Hour"}, "yaxis": {"title": "W/m²"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": g}


def _plot_2_2(df: pd.DataFrame) -> Dict:
    _require(df, "小时", "材料热辐射_W/m2", "大气向下辐射_W/m2", "太阳吸收_W/m2")
    # Check if latent heat is enabled
    has_latent_heat = "蒸发潜热功率_W/m2" in df.columns and df["蒸发潜热功率_W/m2"].abs().max() > 1e-6
    agg_dict = {"材料热辐射_W/m2": "mean", "大气向下辐射_W/m2": "mean", "太阳吸收_W/m2": "mean"}
    if has_latent_heat:
        agg_dict["蒸发潜热功率_W/m2"] = "mean"
    g = df.groupby("小时").agg(agg_dict).reset_index()
    g["小时"] = g["小时"].astype(int)

    data_series = [
        {"type": "bar", "name": "Thermal emission", "x": g["小时"].tolist(), "y": g["材料热辐射_W/m2"].astype(float).tolist()},
        {"type": "bar", "name": "Atmospheric absorption", "x": g["小时"].tolist(), "y": (-g["大气向下辐射_W/m2"]).astype(float).tolist()},
        {"type": "bar", "name": "Solar absorption", "x": g["小时"].tolist(), "y": (-g["太阳吸收_W/m2"]).astype(float).tolist()},
    ]
    # Add latent heat bar if enabled (stacked on top of thermal emission)
    if has_latent_heat:
        data_series.append({
            "type": "bar",
            "name": "Latent heat",
            "x": g["小时"].tolist(),
            "y": g["蒸发潜热功率_W/m2"].astype(float).tolist(),
            "marker": {"color": "#66C2A4"},  # teal color
        })
    spec = {
        "data": data_series,
        "layout": {
            "title": "Hourly power composition",
            "barmode": "relative",
            "xaxis": {"title": "Hour"},
            "yaxis": {"title": "W/m²"},
            "margin": {"l": 60, "r": 20, "t": 50, "b": 50},
        },
    }
    return {"spec": spec, "data": g}


def _plot_2_3(df: pd.DataFrame) -> Dict:
    _require(df, "时段", "净制冷功率_W/m2")
    data_df = df[["时段", "净制冷功率_W/m2"]].copy()

    def _y(seg: str):
        return data_df.loc[data_df["时段"] == seg, "净制冷功率_W/m2"].astype(float).tolist()

    spec = {
        "data": [
            {"type": "box", "name": "Day", "y": _y("白天")},
            {"type": "box", "name": "Night", "y": _y("夜间")},
        ],
        "layout": {"title": "Day vs Night cooling power", "yaxis": {"title": "W/m²"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": data_df}


def _plot_2_4(df: pd.DataFrame) -> Dict:
    _require(df, "时段", "气温_C", "净制冷功率_W/m2")
    data_df = df[["时段", "气温_C", "净制冷功率_W/m2"]].copy()

    def _scatter(seg: str, name: str):
        dd = data_df.loc[data_df["时段"] == seg]
        return {"type": "scatter", "mode": "markers", "name": name, "x": dd["气温_C"].astype(float).tolist(), "y": dd["净制冷功率_W/m2"].astype(float).tolist()}

    spec = {
        "data": [_scatter("白天", "Day"), _scatter("夜间", "Night")],
        "layout": {"title": "Cooling vs temperature", "xaxis": {"title": "°C"}, "yaxis": {"title": "W/m²"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": data_df}


def _plot_2_5(df: pd.DataFrame) -> Dict:
    _require(df, "时段", "风速_m/s", "净制冷功率_W/m2")
    data_df = df[["时段", "风速_m/s", "净制冷功率_W/m2"]].copy()

    def _scatter(seg: str, name: str):
        dd = data_df.loc[data_df["时段"] == seg]
        return {"type": "scatter", "mode": "markers", "name": name, "x": dd["风速_m/s"].astype(float).tolist(), "y": dd["净制冷功率_W/m2"].astype(float).tolist()}

    spec = {
        "data": [_scatter("白天", "Day"), _scatter("夜间", "Night")],
        "layout": {"title": "Cooling vs wind", "xaxis": {"title": "m/s"}, "yaxis": {"title": "W/m²"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": data_df}


def _plot_2_6(df: pd.DataFrame) -> Dict:
    # replicate: humidity vs solar (day/night)
    rh = "相对湿度_%" if "相对湿度_%" in df.columns else ("相对湿度" if "相对湿度" in df.columns else None)
    if rh is None:
        raise KeyError("Missing humidity column")

    _require(df, "时段")
    solar = "地表净太阳辐射_W/m2" if ("地表净太阳辐射_W/m2" in df.columns and df["地表净太阳辐射_W/m2"].notna().any()) else "地表下行短波_W/m2"
    _require(df, solar)

    data_df = df[["时段", rh, solar]].copy()

    def _scatter(seg: str, name: str):
        dd = data_df.loc[data_df["时段"] == seg]
        return {"type": "scatter", "mode": "markers", "name": name, "x": dd[rh].astype(float).tolist(), "y": dd[solar].astype(float).tolist()}

    spec = {
        "data": [_scatter("白天", "Day"), _scatter("夜间", "Night")],
        "layout": {"title": "Humidity vs solar", "xaxis": {"title": "Humidity (%)"}, "yaxis": {"title": "Solar (W/m²)"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": data_df}


def _plot_3_1(df: pd.DataFrame) -> Dict:
    _require(df, "净制冷功率_W/m2")
    data_df = df[["净制冷功率_W/m2"]].copy()

    # Match matplotlib fig3_split: histogram (density) + normal fit curve
    vals = data_df["净制冷功率_W/m2"].astype(float).to_numpy()
    vals = vals[~np.isnan(vals)]
    if vals.size == 0:
        raise ValueError("No valid data for 3_1_distribution")

    mu = float(np.mean(vals))
    std = float(np.std(vals))

    x_min = float(np.min(vals))
    x_max = float(np.max(vals))
    if x_min == x_max:
        x_min -= 1.0
        x_max += 1.0
    x_line = np.linspace(x_min, x_max, 200)

    if std > 0:
        norm_y = (1.0 / (std * np.sqrt(2.0 * np.pi))) * np.exp(-0.5 * ((x_line - mu) / std) ** 2)
    else:
        norm_y = np.zeros_like(x_line)

    spec = {
        "data": [
            {
                "type": "histogram",
                "name": "Cooling power",
                "x": vals.tolist(),
                "nbinsx": 50,
                "histnorm": "probability density",
                "marker": {
                    "color": "#6BAED6",  # blue
                    "opacity": 0.6,
                    "line": {"color": "#525252", "width": 1},  # neutral edge
                },
            },
            {
                "type": "scatter",
                "mode": "lines",
                "name": "Normal fit",
                "x": x_line.tolist(),
                "y": norm_y.tolist(),
                "line": {"color": "#E6550D", "width": 2},  # dark_red
            },
        ],
        "layout": {
            "title": "Cooling power distribution",
            "xaxis": {"title": "Cooling power (W/m²)"},
            "yaxis": {"title": "Probability density"},
            "margin": {"l": 60, "r": 20, "t": 50, "b": 50},
        },
    }
    return {"spec": spec, "data": data_df}


def _plot_3_2(df: pd.DataFrame) -> Dict:
    _require(df, "净制冷功率_W/m2")
    tcol = _time_col(df)
    dd = df[[tcol, "净制冷功率_W/m2"]].copy()
    dd = dd.sort_values(tcol)
    dd["累积制冷量_kWh"] = dd["净制冷功率_W/m2"].astype(float).cumsum() / 1000.0

    spec = {
        "data": [{"type": "scatter", "mode": "lines", "name": "Cumulative", "x": dd[tcol].astype(str).tolist(), "y": dd["累积制冷量_kWh"].astype(float).tolist()}],
        "layout": {"title": "Cumulative cooling", "xaxis": {"title": "Time"}, "yaxis": {"title": "kWh/m²"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": dd[[tcol, "累积制冷量_kWh"]]}


def _plot_3_3(df: pd.DataFrame) -> Dict:
    _require(df, "理想制冷功率_W/m2", "净制冷功率_W/m2")
    hour = "小时" if "小时" in df.columns else None
    cols = ["理想制冷功率_W/m2", "净制冷功率_W/m2"] + ([hour] if hour else [])
    data_df = df[cols].copy()

    marker = {"size": 6, "opacity": 0.6}
    if hour:
        marker = {**marker, "color": data_df[hour].astype(float).tolist(), "colorscale": "RdBu", "showscale": True, "colorbar": {"title": "Hour"}}

    # Match matplotlib: symmetric limits and y=x reference line
    ideal_vals = data_df["理想制冷功率_W/m2"].astype(float).to_numpy()
    mat_vals = data_df["净制冷功率_W/m2"].astype(float).to_numpy()
    lim = float(
        np.max(
            [
                np.abs(np.min(ideal_vals)),
                np.max(ideal_vals),
                np.abs(np.min(mat_vals)),
                np.max(mat_vals),
            ]
        )
    )
    if not np.isfinite(lim) or lim <= 0:
        lim = float(np.nanmax([np.max(ideal_vals), np.max(mat_vals)]))
    if not np.isfinite(lim) or lim <= 0:
        lim = 1.0

    diag_x = [-lim, lim]
    diag_y = [-lim, lim]

    spec = {
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "name": "Points",
                "x": data_df["理想制冷功率_W/m2"].astype(float).tolist(),
                "y": data_df["净制冷功率_W/m2"].astype(float).tolist(),
                "marker": marker,
            },
            {
                "type": "scatter",
                "mode": "lines",
                "name": "Ideal = material",
                "x": diag_x,
                "y": diag_y,
                "line": {"color": "#E6550D", "width": 2, "dash": "dash"},
                "showlegend": True,
            },
        ],
        "layout": {
            "title": "Material vs ideal",
            "xaxis": {"title": "Ideal cooling power (W/m²)", "range": [0, lim]},
            "yaxis": {"title": "Cooling power (W/m²)", "range": [0, lim]},
            "margin": {"l": 60, "r": 20, "t": 50, "b": 50},
        },
    }
    return {"spec": spec, "data": data_df}


def _plot_3_4(df: pd.DataFrame) -> Dict:
    _require(df, "气温_C", "云量", "净制冷功率_W/m2")
    # Create bins (5x5) like the matplotlib version
    temp_bins = pd.cut(df["气温_C"], bins=5)
    cloud_bins = pd.cut(df["云量"], bins=5)
    pivot = df.pivot_table(values="净制冷功率_W/m2", index=cloud_bins, columns=temp_bins, aggfunc="mean")

    # Convert to plotly heatmap
    z = pivot.values.astype(float)
    x = [str(c) for c in pivot.columns]
    y = [str(i) for i in pivot.index]

    spec = {
        "data": [{"type": "heatmap", "z": z.tolist(), "x": x, "y": y, "colorscale": "RdBu"}],
        "layout": {"title": "Heatmap: cloud vs temperature", "xaxis": {"title": "Temperature bin"}, "yaxis": {"title": "Cloud bin"}, "margin": {"l": 90, "r": 20, "t": 50, "b": 90}},
    }

    # Export pivot table as data
    data_df = pivot.reset_index().copy()
    return {"spec": spec, "data": data_df}


def _plot_3_5(df: pd.DataFrame) -> Dict:
    # Radar uses aggregated metrics. We approximate without MATERIAL_PARAMS.
    _require(df, "净制冷功率_W/m2")
    night = df[df["时段"] == "夜间"]["净制冷功率_W/m2"].mean() if "时段" in df.columns else float("nan")
    avg = df["净制冷功率_W/m2"].mean()
    peak = df["净制冷功率_W/m2"].max()
    std = df["净制冷功率_W/m2"].std()

    metrics = {
        "Avg": float(avg),
        "Peak": float(peak),
        "Night avg": float(night) if not np.isnan(night) else 0.0,
        "Stability": float(1 - (std / abs(avg))) if avg != 0 else 0.0,
    }

    labels = list(metrics.keys())
    values = [max(0.0, min(1.0, float(v))) for v in metrics.values()]

    spec = {
        "data": [
            {
                "type": "scatterpolar",
                "r": values + [values[0]],
                "theta": labels + [labels[0]],
                "fill": "toself",
                "name": "Metrics",
            }
        ],
        "layout": {"title": "Radar metrics (normalized)", "polar": {"radialaxis": {"visible": True, "range": [0, 1]}}, "margin": {"l": 60, "r": 60, "t": 50, "b": 50}},
    }

    data_df = pd.DataFrame({"metric": labels, "value": list(metrics.values())})
    return {"spec": spec, "data": data_df}


def _plot_3_6(df: pd.DataFrame) -> Dict:
    # use atmospheric transmittance vs cooling power if available
    trans = "大气透过率" if "大气透过率" in df.columns else None
    if trans is None:
        raise KeyError("Missing 大气透过率")
    _require(df, "净制冷功率_W/m2")
    data_df = df[[trans, "净制冷功率_W/m2"]].copy()
    spec = {
        "data": [{"type": "scatter", "mode": "markers", "name": "Points", "x": data_df[trans].astype(float).tolist(), "y": data_df["净制冷功率_W/m2"].astype(float).tolist()}],
        "layout": {"title": "Transmittance effect", "xaxis": {"title": "Transmittance"}, "yaxis": {"title": "W/m²"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": data_df}


def _plot_4_1(df: pd.DataFrame) -> Dict:
    # Approx: reuse relationship between solar absorption and cooling power
    if "太阳吸收_W/m2" not in df.columns or "净制冷功率_W/m2" not in df.columns:
        raise KeyError("Missing columns for 4_1")
    data_df = df[["太阳吸收_W/m2", "净制冷功率_W/m2"]].copy()
    spec = {
        "data": [{"type": "scatter", "mode": "markers", "name": "Points", "x": data_df["太阳吸收_W/m2"].astype(float).tolist(), "y": data_df["净制冷功率_W/m2"].astype(float).tolist()}],
        "layout": {"title": "Solar reflectance optimization (proxy)", "xaxis": {"title": "Solar absorption (W/m²)"}, "yaxis": {"title": "Net cooling (W/m²)"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": data_df}


def _plot_4_2(df: pd.DataFrame) -> Dict:
    # Approx: emissivity proxy using thermal emission
    _require(df, "材料热辐射_W/m2", "净制冷功率_W/m2")
    data_df = df[["材料热辐射_W/m2", "净制冷功率_W/m2"]].copy()
    spec = {
        "data": [{"type": "scatter", "mode": "markers", "name": "Points", "x": data_df["材料热辐射_W/m2"].astype(float).tolist(), "y": data_df["净制冷功率_W/m2"].astype(float).tolist()}],
        "layout": {"title": "Emissivity optimization (proxy)", "xaxis": {"title": "Thermal emission (W/m²)"}, "yaxis": {"title": "Net cooling (W/m²)"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": data_df}


def _plot_4_3(df: pd.DataFrame) -> Dict:
    # Approx: best conditions -> pick top cooling points vs cloud/humidity
    cloud = "云量" if "云量" in df.columns else None
    rh = "相对湿度_%" if "相对湿度_%" in df.columns else None
    if cloud is None or rh is None:
        raise KeyError("Missing 云量 or 相对湿度_%")
    _require(df, "净制冷功率_W/m2")

    dd = df[[cloud, rh, "净制冷功率_W/m2"]].copy().sort_values("净制冷功率_W/m2", ascending=False).head(500)
    spec = {
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "name": "Top cooling",
                "x": dd[cloud].astype(float).tolist(),
                "y": dd[rh].astype(float).tolist(),
                "marker": {"color": dd["净制冷功率_W/m2"].astype(float).tolist(), "colorscale": "Viridis", "showscale": True, "colorbar": {"title": "W/m²"}},
            }
        ],
        "layout": {"title": "Best conditions (top cooling)", "xaxis": {"title": "Cloud"}, "yaxis": {"title": "RH (%)"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": dd}


def _plot_4_4(df: pd.DataFrame) -> Dict:
    # correlation matrix on selected numeric columns
    # Include latent heat if enabled (it will be in numeric columns if it exists)
    numeric = df.select_dtypes(include=["number"]).copy()
    if numeric.shape[1] < 2:
        raise ValueError("Not enough numeric columns")
    # Rename latent heat column for better display if it exists
    if "蒸发潜热功率_W/m2" in numeric.columns:
        numeric = numeric.rename(columns={"蒸发潜热功率_W/m2": "Latent heat (W/m²)"})
    corr = numeric.corr(numeric_only=True)

    spec = {
        "data": [{"type": "heatmap", "z": corr.values.tolist(), "x": corr.columns.tolist(), "y": corr.index.tolist(), "colorscale": "RdBu", "zmin": -1, "zmax": 1}],
        "layout": {"title": "Correlation matrix", "margin": {"l": 90, "r": 20, "t": 50, "b": 90}},
    }
    data_df = corr.reset_index().rename(columns={"index": "var"})
    return {"spec": spec, "data": data_df}


def _plot_4_5(df: pd.DataFrame) -> Dict:
    # reuse humidity vs cooling
    rh = "相对湿度_%" if "相对湿度_%" in df.columns else None
    if rh is None:
        raise KeyError("Missing humidity")
    _require(df, "净制冷功率_W/m2")
    data_df = df[[rh, "净制冷功率_W/m2"]].copy()
    spec = {
        "data": [{"type": "scatter", "mode": "markers", "name": "Points", "x": data_df[rh].astype(float).tolist(), "y": data_df["净制冷功率_W/m2"].astype(float).tolist()}],
        "layout": {"title": "Humidity effect", "xaxis": {"title": "RH (%)"}, "yaxis": {"title": "W/m²"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": data_df}


def _plot_4_6_text(df: pd.DataFrame) -> Dict:
    # Provide a simple text panel derived from stats
    _require(df, "净制冷功率_W/m2")
    avg = float(df["净制冷功率_W/m2"].mean())
    mx = float(df["净制冷功率_W/m2"].max())
    eff = float((df["净制冷功率_W/m2"] > 0).mean() * 100.0)

    text = f"Recommendations (auto)\n\nAvg net cooling: {avg:.2f} W/m²\nMax net cooling: {mx:.2f} W/m²\nEffective time: {eff:.1f}%"
    data_df = pd.DataFrame({"text": [text]})
    spec = {
        "data": [
            {
                "type": "scatter",
                "mode": "text",
                "x": [0],
                "y": [0],
                "text": [text.replace("\n", "<br>")],
                "textposition": "middle center",
            }
        ],
        "layout": {"title": "Recommendations", "xaxis": {"visible": False}, "yaxis": {"visible": False}, "margin": {"l": 20, "r": 20, "t": 50, "b": 20}},
    }
    return {"spec": spec, "data": data_df}


def _plot_5_0_text(df: pd.DataFrame) -> Dict:
    _require(df, "净制冷功率_W/m2")
    total_kwh = float(df["净制冷功率_W/m2"].clip(lower=0.0).sum() / 1000.0)
    avg = float(df["净制冷功率_W/m2"].mean())
    mx = float(df["净制冷功率_W/m2"].max())
    eff = float((df["净制冷功率_W/m2"] > 0).mean() * 100.0)

    text = f"KPI\n\nTotal cooling: {total_kwh:.2f} kWh/m²\nAvg: {avg:.2f} W/m²\nMax: {mx:.2f} W/m²\nEffective: {eff:.1f}%"
    data_df = pd.DataFrame({"kpi": ["total_kwh_m2", "avg_wm2", "max_wm2", "effective_pct"], "value": [total_kwh, avg, mx, eff]})
    spec = {
        "data": [
            {
                "type": "scatter",
                "mode": "text",
                "x": [0],
                "y": [0],
                "text": [text.replace("\n", "<br>")],
                "textposition": "middle center",
            }
        ],
        "layout": {"title": "KPI cards", "xaxis": {"visible": False}, "yaxis": {"visible": False}, "margin": {"l": 20, "r": 20, "t": 50, "b": 20}},
    }
    return {"spec": spec, "data": data_df}


def _plot_5_1(df: pd.DataFrame) -> Dict:
    # same as 5_1_time_series.png: time vs net cooling
    _require(df, "净制冷功率_W/m2")
    tcol = _time_col(df)
    data_df = df[[tcol, "净制冷功率_W/m2"]].copy()
    spec = {
        "data": [{"type": "scatter", "mode": "lines", "name": "Net cooling", "x": data_df[tcol].astype(str).tolist(), "y": data_df["净制冷功率_W/m2"].astype(float).tolist()}],
        "layout": {"title": "Net cooling time series", "xaxis": {"title": "Time"}, "yaxis": {"title": "W/m²"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": data_df}


def _plot_5_2(df: pd.DataFrame) -> Dict:
    _require(df, "小时", "净制冷功率_W/m2")
    g = df.groupby("小时")["净制冷功率_W/m2"].mean().reset_index()
    g["小时"] = g["小时"].astype(int)
    spec = {
        "data": [{"type": "bar", "name": "Hourly avg", "x": g["小时"].tolist(), "y": g["净制冷功率_W/m2"].astype(float).tolist()}],
        "layout": {"title": "Hourly average", "xaxis": {"title": "Hour"}, "yaxis": {"title": "W/m²"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": g}


def _plot_5_3(df: pd.DataFrame) -> Dict:
    return _plot_3_1(df)


def _plot_5_4(df: pd.DataFrame) -> Dict:
    _require(df, "云量", "气温_C", "净制冷功率_W/m2")
    data_df = df[["云量", "气温_C", "净制冷功率_W/m2"]].copy()
    spec = {
        "data": [
            {
                "type": "scatter",
                "mode": "markers",
                "name": "Points",
                "x": data_df["云量"].astype(float).tolist(),
                "y": data_df["净制冷功率_W/m2"].astype(float).tolist(),
                "marker": {"color": data_df["气温_C"].astype(float).tolist(), "colorscale": "RdBu", "showscale": True, "colorbar": {"title": "°C"}},
            }
        ],
        "layout": {"title": "Cloud-temp-power", "xaxis": {"title": "Cloud"}, "yaxis": {"title": "W/m²"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": data_df}


def _plot_5_5(df: pd.DataFrame) -> Dict:
    # same concept as day/night box
    if "时段" not in df.columns:
        raise KeyError("Missing 时段")
    return _plot_2_3(df)


def _plot_5_6(df: pd.DataFrame) -> Dict:
    _require(df, "制冷效率")
    tcol = _time_col(df)
    data_df = df[[tcol, "制冷效率"]].copy()
    spec = {
        "data": [{"type": "scatter", "mode": "lines", "name": "Efficiency (%)", "x": data_df[tcol].astype(str).tolist(), "y": (data_df["制冷效率"].astype(float) * 100.0).tolist()}],
        "layout": {"title": "Cooling efficiency", "xaxis": {"title": "Time"}, "yaxis": {"title": "%"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": data_df}


def _plot_5_7(df: pd.DataFrame) -> Dict:
    trans = "大气透过率" if "大气透过率" in df.columns else None
    if trans is None:
        raise KeyError("Missing 大气透过率")
    _require(df, "净制冷功率_W/m2")
    data_df = df[[trans, "净制冷功率_W/m2"]].copy()
    spec = {
        "data": [{"type": "scatter", "mode": "markers", "name": "Points", "x": data_df[trans].astype(float).tolist(), "y": data_df["净制冷功率_W/m2"].astype(float).tolist()}],
        "layout": {"title": "Transmittance effect", "xaxis": {"title": "Transmittance"}, "yaxis": {"title": "W/m²"}, "margin": {"l": 60, "r": 20, "t": 50, "b": 50}},
    }
    return {"spec": spec, "data": data_df}


def _plot_5_8_table(df: pd.DataFrame) -> Dict:
    _require(df, "净制冷功率_W/m2")
    day_avg = float(df[df["时段"] == "白天"]["净制冷功率_W/m2"].mean()) if "时段" in df.columns else float("nan")
    night_avg = float(df[df["时段"] == "夜间"]["净制冷功率_W/m2"].mean()) if "时段" in df.columns else float("nan")
    avg = float(df["净制冷功率_W/m2"].mean())
    mx = float(df["净制冷功率_W/m2"].max())
    std = float(df["净制冷功率_W/m2"].std())
    eff = float((df["净制冷功率_W/m2"] > 0).mean() * 100.0)
    total_kwh = float(df["净制冷功率_W/m2"].clip(lower=0.0).sum() / 1000.0)

    rows = [
        ("Avg. net cooling", avg),
        ("Daytime average", day_avg),
        ("Nighttime average", night_avg),
        ("Maximum", mx),
        ("Std. dev.", std),
        ("Effective time ratio (%)", eff),
        ("Total cooling (kWh/m²)", total_kwh),
    ]
    data_df = pd.DataFrame({"metric": [r[0] for r in rows], "value": [r[1] for r in rows]})

    spec = {
        "data": [
            {
                "type": "table",
                "header": {"values": ["Metric", "Value"], "align": "left"},
                "cells": {"values": [data_df["metric"].tolist(), [f"{v:.4g}" if isinstance(v, (int, float)) and not np.isnan(v) else str(v) for v in data_df["value"].tolist()]], "align": "left"},
            }
        ],
        "layout": {"title": "Summary table", "margin": {"l": 20, "r": 20, "t": 50, "b": 20}},
    }
    return {"spec": spec, "data": data_df}
