from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

import numpy as np

from webapi.settings import settings

# NOTE:
# This project's directory name contains '-' so we cannot use normal `from x-y import ...` syntax.
# We must ensure imports resolve regardless of CWD.

_ensure_project_on_syspath_done = False


def _ensure_project_on_syspath():
    """Ensure the project root is on sys.path for reliable imports."""
    global _ensure_project_on_syspath_done
    if _ensure_project_on_syspath_done:
        return
    import sys

    root = Path(__file__).resolve().parents[1]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    _ensure_project_on_syspath_done = True


_ensure_project_on_syspath()

_core_calculations = importlib.import_module("core.calculations")
main_cooling_gui = getattr(_core_calculations, "main_cooling_gui")
main_heating_gui = getattr(_core_calculations, "main_heating_gui")
calculate_latent_heat_power = getattr(_core_calculations, "_calculate_latent_heat_power")

_webapi_db_models = importlib.import_module("webapi.db.models")
Job = getattr(_webapi_db_models, "Job")

_webapi_db_session = importlib.import_module("webapi.db.session")
SessionLocal = getattr(_webapi_db_session, "SessionLocal")

_webapi_schemas = importlib.import_module("webapi.schemas")
JobResult = getattr(_webapi_schemas, "JobResult")

_webapi_storage = importlib.import_module("webapi.services.storage_service")
_webapi_storage = importlib.import_module("webapi.services.storage_service")
job_result_path = getattr(_webapi_storage, "job_result_path")

_worker_active_inputs = importlib.import_module("worker.active_inputs")
resolve_active_material_paths_for_user = getattr(_worker_active_inputs, "resolve_active_material_paths_for_user")


def _to_list_safe(data):
    if hasattr(data, "tolist"):
        return data.tolist()
    if data is None:
        return []
    return list(data)


def _json_default(o):
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")


def _default_file_paths() -> dict:
    base = Path(__file__).resolve().parents[1]
    default_dir = base / "default"

    # IMPORTANT:
    # The WebAPI active config lives in the workspace root data/ (WEB/data/config.ini),
    # not under the package directory.
    #
    return {
        # NOTE: real config path is resolved per-job in _resolve_common_paths (per-user config).
        "config": str(default_dir / "config.ini"),
        "spectrum": str(default_dir / "AM1.5.xlsx"),
        "wavelength": str(default_dir / "Wavelength.csv"),
    }


def _resolve_atm_emissivity_path(job: Job, atm_name: str, default_dir: Path) -> str:
    """Resolve atmospheric emissivity DLL path with support for per-user uploads.

    Resolution order:
    1. If atm_name matches an uploaded file under settings.atm_uploads_dir, use it.
    2. If atm_name is a base name like "test.dll", and "<stem>_<user_id>.dll" exists
       in the uploads dir, use that.
    3. Fallback to the built-in default DLL under `default_dir/atm_name`.
    """
    # 1) Prefer explicit match in user uploads folder
    uploads_dir = settings.atm_uploads_dir
    uploads_dir.mkdir(parents=True, exist_ok=True)
    direct_path = uploads_dir / atm_name
    if direct_path.exists():
        return str(direct_path)

    # 2) Try user-specific suffixed name: "<stem>_<user_id>.dll"
    user_id = getattr(job, "user_id", None)
    if user_id is not None:
        p = Path(atm_name)
        stem, ext = p.stem, p.suffix or ".dll"
        candidate = uploads_dir / f"{stem}_{user_id}{ext}"
        if candidate.exists():
            return str(candidate)

    # 3) Fallback to built-in default directory
    return str(default_dir / str(atm_name))


def _resolve_common_paths(job: Job, params: dict) -> dict:
    base = _default_file_paths()
    # default_dir is where atmospheric emissivity presets live (default/)
    default_dir = Path(__file__).resolve().parents[1] / "default"

    # Default atmosphere depends on job type:
    # - cooling / heating: clear_sky.dll
    # - in_situ_simulation: Fullytransparent.dll
    raw_atm_name = params.get("atm_preset")
    if raw_atm_name:
        atm_name = raw_atm_name
    else:
        job_type = getattr(job, "type", None)
        if job_type == "in_situ_simulation":
            atm_name = "Fullytransparent.dll"
        else:
            atm_name = "clear_sky.dll"

    # Prefer job snapshot (to avoid active-input changes affecting an already submitted job).
    snap = params.get("_file_paths")
    if isinstance(snap, dict):
        r = snap.get("reflectance")
        e = snap.get("emissivity")
        c = snap.get("config")
        r_orig = snap.get("reflectance_original")
        t = snap.get("transmittance")
        if isinstance(r, str) and isinstance(e, str) and isinstance(c, str):
            result = {
                **base,
                "config": c,
                "reflectance": r,
                "emissivity": e,
                "atm_emissivity": _resolve_atm_emissivity_path(job, str(atm_name), default_dir),
            }
            if isinstance(r_orig, str) and Path(r_orig).exists():
                result["reflectance_original"] = r_orig
            if isinstance(t, str) and Path(t).exists():
                result["transmittance"] = t
            return result

    # Fallback: resolve from current active inputs + per-user config.
    user_id = getattr(job, "user_id", None)
    if user_id is None:
        user_id = 0
    from webapi.services.config_service import ensure_user_config_exists

    config_path = str(ensure_user_config_exists(int(user_id)))

    # Active default material files (uploaded + processed), per job owner.
    active = None
    try:
        user_id = getattr(job, "user_id", None)
        if user_id is not None:
            active = resolve_active_material_paths_for_user(int(user_id))
        # Fallback to legacy global active inputs if per-user not available
        if not active:
            from worker.active_inputs import resolve_active_material_paths

            active = resolve_active_material_paths()
    except Exception:
        active = None

    if not active:
        raise RuntimeError(
            "Active material files are not ready. Please upload and process BOTH reflectance and emissivity in /uploads first."
        )

    # Get original reflectance and transmittance paths for separate calculations
    from webapi.services.active_inputs_service import get_active_input_for_user
    user_id = getattr(job, "user_id", None)
    if user_id is None:
        user_id = 0
    
    r_original = get_active_input_for_user(int(user_id), "reflectance")
    t_original = get_active_input_for_user(int(user_id), "transmittance")
    
    result = {
        **base,
        "config": config_path,
        "reflectance": active["reflectance"],  # Combined (R+T) for absorptance calculation
        "emissivity": active["emissivity"],
        "atm_emissivity": _resolve_atm_emissivity_path(job, str(atm_name), default_dir),
    }

    # Always pass original reflectance (for correct R_sol_reflectance_only in output)
    if r_original and Path(r_original.path).exists():
        result["reflectance_original"] = r_original.path

    # Pass transmittance if exists (for correct T_sol in output and absorptivity)
    if t_original and Path(t_original.path).exists():
        result["transmittance"] = t_original.path

    return result


def _generate_china_power_map_from_csv(
    csv_path: Path,
    png_path: Path,
    value_column: str = "AveragePower",
    custom_title: str = "",
    custom_label: str = "",
) -> bool:
    """根据 data.csv 的指定列绘制中国省级功量地图并保存为 PNG。

    仅用于 weather_group == 'china' 的功量地图任务。

    Args:
        csv_path: CSV文件路径
        png_path: 输出PNG文件路径
        value_column: 用于着色的值列名，默认为"AveragePower"
        custom_title: 自定义地图标题（空字符串使用默认标题）
        custom_label: 自定义颜色条标签（空字符串使用默认标签）
    """
    try:
        import matplotlib

        # 使用非交互式后端，避免服务器环境下 GUI 问题
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib as mpl
        import matplotlib.colors as mcolors
        import geopandas as gpd
        import pandas as pd
        import numpy as np
    except Exception as e:  # pragma: no cover - 依赖缺失时仅打印日志
        print(f"[Power Map] Skip China map drawing, missing matplotlib/geopandas deps: {e}")
        return False

    # 智能颜色条范围计算函数
    def _compute_cbar_range(data_min, data_max):
        """根据数据范围计算最优的cbar范围"""
        if not np.isfinite(data_min) or not np.isfinite(data_max):
            return (0, 1)
        
        if data_max - data_min < 1e-10:
            data_max = data_min + 1.0
        
        # 功率值通常为正，从0开始
        vmin = 0 if data_min >= 0 else data_min
        vmax = data_max * 1.1  # 添加10%的边界
        
        return (float(vmin), float(vmax))

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"[Power Map] Failed to read data.csv for China map: {e}")
        return False

    if "NAME" not in df.columns or value_column not in df.columns:
        print(f"[Power Map] data.csv missing 'NAME' or '{value_column}' column, skip China map drawing.")
        return False

    df = df[["NAME", value_column]].dropna()
    df["NAME"] = df["NAME"].astype(str).str.strip()
    if df.empty:
        print("[Power Map] data.csv has no valid rows for China map, skip drawing.")
        return False

    china_url = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json"

    # 本地缓存路径
    cache_dir = Path(__file__).parent.parent / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    china_geojson_cache = cache_dir / "china_provinces_full.json"

    # 尝试加载 GeoJSON：优先使用本地缓存，失败则从阿里云下载
    try:
        if china_geojson_cache.exists():
            print(f"[Power Map] Loading China GeoJSON from local cache: {china_geojson_cache}")
            china = gpd.read_file(china_geojson_cache)
        else:
            print(f"[Power Map] Loading China GeoJSON from Aliyun...")
            china = gpd.read_file(china_url)
            # 保存到本地缓存
            china.to_file(china_geojson_cache, driver="GeoJSON")
            print(f"[Power Map] Saved China GeoJSON to local cache: {china_geojson_cache}")
    except Exception as e:
        # 如果本地缓存存在，尝试使用缓存
        if china_geojson_cache.exists():
            try:
                print(f"[Power Map] Aliyun failed, trying local cache: {e}")
                china = gpd.read_file(china_geojson_cache)
            except Exception as cache_err:
                print(f"[Power Map] Failed to load China GeoJSON from local cache: {cache_err}")
                return False
        else:
            print(f"[Power Map] Failed to load China GeoJSON from Aliyun: {e}")
            return False

    # 仅保留省级边界（如果存在 level 字段）
    try:
        if "level" in china.columns:
            china_prov = china[china["level"] == "province"].copy()
        else:
            china_prov = china.copy()
    except Exception as e:
        print(f"[Power Map] Failed to filter province level from GeoJSON: {e}")
        return False

    if "name" not in china_prov.columns:
        print("[Power Map] China GeoJSON missing 'name' column, cannot join with data.csv.")
        return False

    china_prov["name"] = china_prov["name"].astype(str).str.strip()

    merged = china_prov.merge(df, left_on="name", right_on="NAME", how="left")

    try:
        fig, ax = plt.subplots(1, 1, figsize=(10, 8))
        
        # 根据值列确定标题和单位
        if value_column == "CoolingPower":
            title = "China Cooling Power Distribution"
            label = "Cooling Power (W)"
        else:
            # 默认使用 AveragePower 标题
            title = "China Average Power Distribution"
            label = "Average Power (W/m²)"

        # 允许外部覆盖标题和标签
        if custom_title:
            title = custom_title
        if custom_label:
            label = custom_label
        
        # 计算数据的范围
        valid_data = merged[value_column].dropna()
        if len(valid_data) > 0:
            data_min = valid_data.min()
            data_max = valid_data.max()
            vmin, vmax = _compute_cbar_range(data_min, data_max)
            norm = mpl.colors.Normalize(vmin=vmin, vmax=vmax)
        else:
            norm = None

        # 绘制地图（不使用默认图例）
        merged.plot(
            column=value_column,
            ax=ax,
            cmap="RdYlBu",  # 红黄蓝
            edgecolor="black",
            linewidth=0.5,
            legend=True,  # 不使用默认图例
            norm=norm,
            missing_kwds={"color": "lightgray", "label": "No data"},
        )

        # 添加自定义颜色条
        # sm = plt.cm.ScalarMappable(cmap="RdYlBu_r", norm=norm)
        # sm.set_array([])
        #
        # # 计算合适的ticks
        # if norm is not None and np.isfinite(norm.vmin) and np.isfinite(norm.vmax):
        #     vmin, vmax = norm.vmin, norm.vmax
        #     if vmax <= 25:
        #         tick_step = 4
        #         ticks = [vmin] + list(range(int(tick_step), int(vmax), tick_step)) + [vmax]
        #     elif vmax <= 50:
        #         tick_step = 10
        #         ticks = [vmin] + list(range(int(tick_step), int(vmax), tick_step)) + [vmax]
        #     elif vmax <= 100:
        #         tick_step = 20
        #         ticks = [vmin] + list(range(int(tick_step), int(vmax), tick_step)) + [vmax]
        #     elif vmax <= 200:
        #         tick_step = 40
        #         ticks = [vmin] + list(range(int(tick_step), int(vmax), tick_step)) + [vmax]
        #     elif vmax <= 300:
        #         tick_step = 60
        #         ticks = [vmin] + list(range(int(tick_step), int(vmax), tick_step)) + [vmax]
        #     elif vmax <= 500:
        #         tick_step = 100
        #         ticks = [vmin] + list(range(int(tick_step), int(vmax), tick_step)) + [vmax]
        #     elif vmax <= 1000:
        #         tick_step = 200
        #         ticks = [vmin] + list(range(int(tick_step), int(vmax), tick_step)) + [vmax]
        #     elif vmax <= 2000:
        #         tick_step = 400
        #         ticks = [vmin] + list(range(int(tick_step), int(vmax), tick_step)) + [vmax]
        #     elif vmax <= 5000:
        #         tick_step = 1000
        #         ticks = [vmin] + list(range(int(tick_step), int(vmax), tick_step)) + [vmax]
        #     else:
        #         tick_step = int(vmax // 5)
        #         ticks = [vmin] + list(range(tick_step, int(vmax), tick_step)) + [vmax]
        #     ticks = [t for t in ticks if vmin <= t <= vmax]
        # else:
        #     ticks = None
        #
        # cbar = fig.colorbar(sm, ax=ax, shrink=0.7, pad=0.02)
        # cbar.set_label(label, fontsize=12)
        # if ticks:
        #     cbar.set_ticks(ticks)
        # cbar.ax.tick_params(labelsize=10)

        ax.set_title(title, fontsize=14, fontweight='bold')
        ax.set_axis_off()

        png_path.parent.mkdir(parents=True, exist_ok=True)
        plt.tight_layout()
        fig.savefig(png_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

        print(f"[Power Map] China AveragePower map saved to: {png_path}")
        return True
    except Exception as e:
        print(f"[Power Map] Failed to draw/save China map: {e}")
        import traceback
        traceback.print_exc()
        return False


def _build_line_plot_payload(*, title: str, x_values, series_values: np.ndarray, hc_vals) -> dict:
    results_mat = np.asarray(series_values)
    return {
        "kind": "line",
        "title": title,
        "x": {"label": "T_film (°C)", "values": _to_list_safe(x_values)},
        "series": [
            {
                "name": f"h_c={hc}",
                "values": _to_list_safe(results_mat[:, i]) if results_mat.size else [],
            }
            for i, hc in enumerate(list(hc_vals or []))
        ],
    }


def run_job(job_id: str) -> None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            return
        job.status = "started"
        job.updated_at = datetime.utcnow()
        db.commit()

    try:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if not job:
                return
            params = job.params or {}
            job_type = job.type

        if job_type not in {
            "cooling",
            "heating",
            "in_situ_simulation",
            "compare_materials",
            "compare_glass",
            "energy_map",
            "material_env_temp_map",
            "radiation_cooling_clothing",
            "material_env_temp_cloud",
            "mock",
        }:
            raise RuntimeError(f"Unsupported job type in MVP: {job_type}")

        if job_type == "mock":
            payload = JobResult(
                job_id=job_id,
                generated_at=datetime.utcnow(),
                summary={"note": "mock job"},
                plots=[],
                artifacts=[],
            ).model_dump(mode="json")
            out = job_result_path(job_id)
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")

        elif job_type == "in_situ_simulation":
            # ERA5 in-situ radiative cooling / photothermal validation
            from webapi.services.storage_service import job_dir

            from core.calculations import main_calculating_gui
            from core.era5_rc_tool import Era5ComputeParams, Era5DownloadParams, compute_radiative_cooling_from_merged_csv, download_era5_to_dir, merge_weather_csvs

            # --- input params ---
            start_date = str(params.get("start_date") or "")
            end_date = str(params.get("end_date") or "")
            lon = float(params.get("lon"))
            lat = float(params.get("lat"))
            tz_offset_hours = float(params.get("tz_offset_hours", 0.0) or 0.0)
            sky_view = float(params.get("sky_view", 1.0) or 1.0)
            use_empirical_atm: int = int(params.get("use_empirical_atm", 0))  # 0=真实ERA5, 1=修正混合模式(0.3+0.7), 2=理论模式(0.8+0.2)
            enable_latent_heat = bool(params.get("enable_latent_heat", False))
            wet_fraction = float(params.get("wet_fraction", 1.0) or 1.0)

            # figure enable flags: list[bool] length 32, aligned with filenames in output/results/figures
            figure_flags = params.get("figure_flags")
            if not isinstance(figure_flags, list) or len(figure_flags) != 32:
                figure_flags = [True] * 32
            figure_flags = [bool(x) for x in figure_flags]

            # Use active material to derive eps/rho_solar (desktop parity)
            file_paths = _resolve_common_paths(job, params)
            avg_emissivity, alpha_sol, _ = main_calculating_gui(file_paths)

            eps_override = params.get("eps")
            rho_override = params.get("rho_solar")
            eps = float(avg_emissivity if eps_override is None else eps_override)
            # main_calculating_gui returns absorptance (alpha), convert back to reflectance (rho) for calculations
            # rho_solar = 1 - alpha_sol
            rho_solar = float((1.0 - alpha_sol) if rho_override is None else rho_override)

            job_base = job_dir(job_id) / "era5"
            weather_dir = job_base / "weather"
            figures_dir = job_base / "figures"
            plot_data_dir = job_base / "plot_data"
            plots_dir = job_base / "plots"
            weather_dir.mkdir(parents=True, exist_ok=True)
            figures_dir.mkdir(parents=True, exist_ok=True)
            plot_data_dir.mkdir(parents=True, exist_ok=True)
            plots_dir.mkdir(parents=True, exist_ok=True)

            # --- stage 0: validate date range (server-side safety) ---
            from datetime import date

            def _parse_ymd(s: str) -> date:
                try:
                    return date.fromisoformat(s)
                except Exception:
                    raise ValueError(f"Invalid date format (YYYY-MM-DD required): {s}")

            sd = _parse_ymd(start_date)
            ed = _parse_ymd(end_date)
            if ed < sd:
                raise ValueError("end_date must be >= start_date")
            if sd.year != ed.year:
                raise ValueError("Cross-year ERA5 download is not allowed")
            month_span = (ed.year * 12 + ed.month) - (sd.year * 12 + sd.month)
            if month_span > 1:
                raise ValueError("Date range exceeds 1 month; rejected for safety")

            # --- stage 1: prepare weather dir (clean to avoid mixing history) ---
            try:
                for fp in weather_dir.iterdir():
                    if fp.is_file():
                        fp.unlink(missing_ok=True)
            except Exception:
                pass

            # --- stage 2: download ERA5 (split into 1-2 downloads) ---
            downloaded = []

            cds_lines: list[int | None] = []

            def _download_range(d0: date, d1: date):
                p, line_no = download_era5_to_dir(
                    Era5DownloadParams(
                        start_date=d0.isoformat(),
                        end_date=d1.isoformat(),
                        lon=lon,
                        lat=lat,
                        tz_offset_hours=tz_offset_hours,
                    ),
                    weather_dir,
                )
                downloaded.append(p.name)
                cds_lines.append(line_no)
                return p

            # Always download at least once
            nc_path = None
            if month_span == 0:
                nc_path = _download_range(sd, ed)
            else:
                # adjacent months only
                import calendar

                last_day = calendar.monthrange(sd.year, sd.month)[1]
                first_end = date(sd.year, sd.month, last_day)
                second_start = date(ed.year, ed.month, 1)

                _download_range(sd, first_end)
                p2 = _download_range(second_start, ed)
                nc_path = p2  # keep last as representative

            # Record which CDS lines were used (only line numbers, no keys)
            cds_line_1 = cds_lines[0] if len(cds_lines) >= 1 else None
            cds_line_2 = cds_lines[1] if len(cds_lines) >= 2 else None

            # --- stage 3: merge weather CSVs ---
            merged_csv = weather_dir / "era5_merged.csv"
            merge_weather_csvs(str(weather_dir), str(merged_csv))

            # --- stage 2: compute + figures ---
            out_csv = job_base / "radiative_cooling_results_from_weather.csv"

            # Selectively generate figures by monkey-patching figure functions
            # We can't map 32 flags onto 5 split calls directly; instead: run full compute with export_figures=False
            # then copy pre-generated figures from canonical output folder based on flags.
            # However, if latent heat is enabled, we need to regenerate figures with the new data
            df = compute_radiative_cooling_from_merged_csv(
                merged_csv,
                out_csv=out_csv,
                params=Era5ComputeParams(
                    eps=eps,
                    rho_solar=rho_solar,
                    sky_view=sky_view,
                    use_empirical_atm=use_empirical_atm,
                    enable_latent_heat=enable_latent_heat,
                    wet_fraction=wet_fraction,
                ),
                export_figures=enable_latent_heat,  # Regenerate figures if latent heat is enabled
                figures_dir=str(figures_dir) if enable_latent_heat else None,
            )

            # Solar irradiance stats (for "关键设置" display; no DB schema change needed)
            solar_mean = None
            solar_max = None
            try:
                col_candidates = [
                    "地表下行短波_W/m2",
                    "太阳辐射_W/m2",
                    "solar_radiation",
                    "GloHorzRad",
                ]
                col = next((c for c in col_candidates if c in df.columns), None)
                if col:
                    ser = df[col]
                    # numeric, ignore NaNs
                    solar_mean = float(ser.mean(skipna=True))
                    solar_max = float(ser.max(skipna=True))
            except Exception:
                solar_mean = None
                solar_max = None

            # Copy selected figures from repo canonical output folder (32 files)
            # If latent heat is enabled, figures were already generated in figures_dir, so use those
            if enable_latent_heat and figures_dir.exists():
                figure_files = sorted([p for p in figures_dir.glob("*.png")])
            else:
                canonical = Path(__file__).resolve().parents[1] / "output" / "results" / "figures"
                figure_files = sorted([p for p in canonical.iterdir() if p.is_file()])
                if len(figure_files) != 32:
                    # If canonical set differs, just copy all pngs found.
                    figure_files = sorted([p for p in canonical.glob("*.png")])

            # Build Plotly preview specs + matching CSV exports (data used to render the preview)
            # Only generate for enabled items.
            from webapi.services.era5_plot_specs import build_plot

            enabled_plot_ids: list[str] = []
            for idx, fp in enumerate(figure_files[:32]):
                if idx < len(figure_flags) and not figure_flags[idx]:
                    continue
                enabled_plot_ids.append(fp.stem)

            for plot_id in enabled_plot_ids:
                try:
                    built = build_plot(plot_id, df)
                except Exception:
                    # If a given plot cannot be built (missing columns), skip it.
                    continue

                spec = built.get("spec")
                data_df = built.get("data")
                if spec is None or data_df is None:
                    continue

                (plots_dir / f"{plot_id}.json").write_text(
                    json.dumps(spec, ensure_ascii=False, indent=2, default=_json_default),
                    encoding="utf-8",
                )
                data_df.to_csv(plot_data_dir / f"{plot_id}.csv", index=False, encoding="utf-8-sig")

            copied = []
            for idx, fp in enumerate(figure_files):
                if idx < len(figure_flags) and not figure_flags[idx]:
                    continue
                dest = figures_dir / fp.name
                try:
                    dest.write_bytes(fp.read_bytes())
                except Exception:
                    pass
                copied.append(fp.name)

            payload = JobResult(
                job_id=job_id,
                generated_at=datetime.utcnow(),
                summary={
                    "start_date": start_date,
                    "end_date": end_date,
                    "lon": lon,
                    "lat": lat,
                    "tz_offset_hours": tz_offset_hours,
                    "eps": eps,
                    "rho_solar": rho_solar,
                    "sky_view": sky_view,
                    "enable_latent_heat": enable_latent_heat,
                    "wet_fraction": wet_fraction,
                    "solar_irradiance_mean_wm2": solar_mean,
                    "solar_irradiance_max_wm2": solar_max,
                    "rows": int(len(df)),
                    "nc_file": str(nc_path.name) if nc_path else None,
                    "downloaded": downloaded,
                    "cross_month": bool(month_span == 1),
                    "cds_line_1": (f"线路{cds_line_1}" if cds_line_1 else None),
                    "cds_line_2": (f"线路{cds_line_2}" if cds_line_2 else None),
                    "results_csv": str(out_csv.name),
                    "figures_count": int(len(copied)),
                },
                plots=[],
                artifacts=(
                    [
                        {
                            "kind": "csv",
                            "name": "all.csv",
                            "url": f"/api/era5/{job_id}/plot-data/all",
                        },
                        {
                            "kind": "csv",
                            "name": out_csv.name,
                            "url": f"/api/era5/{job_id}/plot-data/all",
                        },
                    ]
                    + [
                        {
                            "kind": "image",
                            "name": name,
                            "url": f"/api/era5/{job_id}/figures/{name}",
                        }
                        for name in copied
                    ]
                ),
            ).model_dump(mode="json")

            out = job_result_path(job_id)
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")

        elif job_type == "compare_materials":
            # 材料辐射节能效果对比分析（使用EnergyPlus）
            from webapi.services.storage_service import job_dir
            from pathlib import Path as PathLib  # 显式导入避免作用域冲突
            
            # 导入材料对比模块
            _material_comparison = importlib.import_module("material_comparison_tool.examples.compare_materials")
            run_material_comparison_energyplus = getattr(_material_comparison, "run_material_comparison_energyplus")
            
            # 解析参数
            print(f"\n[WORKER DEBUG] job_id={job_id} raw params={params}")
            weather_group = params.get("weather_group", "china")
            scenarios = params.get("scenarios", [])
            idf_template_dir = params.get("idf_template_dir")  # 新增：IDF模板目录
            energyplus_exe = params.get("energyplus_exe", "D:\\academic_tool\\EnergyPlusV9-1-0\\energyplus.exe")  # 新增：EnergyPlus路径
            global_params = params.get("global_params")  # 新增：全局参数
            enable_latent_heat = bool(params.get("enable_latent_heat", False))  # 新增：是否启用蒸发潜热
            wet_fraction = float(params.get("wet_fraction", 1.0) or 1.0)  # 新增：润湿面积比例
            colormap_params = params.get("colormap_params")  # 色系参数
            print(f"[WORKER DEBUG] enable_latent_heat={enable_latent_heat} wet_fraction={wet_fraction} weather_group={weather_group}")
            print(f"[WORKER DEBUG] colormap_params={colormap_params}")
            
            # 根据前端选择的 IDF 模型目录，自适应设置单位换算因子
            # 约定：
            # - model1: 除以 1.63
            # - model2: 除以 0.245
            # - model3: 除以 1.26
            # - 其他/自定义路径: 回退到历史默认值 2.2（兼容旧行为）
            scale_factor = 2.2
            if isinstance(idf_template_dir, str):
                lower_dir = idf_template_dir.lower()
                if "model1" in lower_dir:
                    scale_factor = 1.63
                elif "model2" in lower_dir:
                    scale_factor = 0.245
                elif "model3" in lower_dir:
                    scale_factor = 1.26
            print(f"[WORKER DEBUG] materials scale_factor={scale_factor} (idf_template_dir={idf_template_dir})")
            
            # 创建job工作目录（每次运行使用独立目录）
            job_base = job_dir(job_id)
            work_dir = str(job_base / "work")  # 使用work子目录作为工作目录
            
            try:
                # 运行材料对比分析（使用EnergyPlus）
                success = run_material_comparison_energyplus(
                    scenarios=scenarios if scenarios else None,
                    progress_cb=None,  # 在后台任务中不使用进度回调
                    weather_group=weather_group,
                    idf_template_dir=idf_template_dir,
                    energyplus_exe=energyplus_exe,
                    work_dir=work_dir,  # 使用job目录作为工作目录
                    global_params=global_params,  # 传递全局参数
                    enable_latent_heat=enable_latent_heat,  # 传递蒸发潜热参数
                    wet_fraction=wet_fraction,  # 传递润湿面积比例
                    scale_factor=scale_factor,  # 按模型自适应的单位换算因子
                    colormap_params=colormap_params,  # 传递色系参数
                )
                
                if not success:
                    raise RuntimeError("Material comparison failed: EnergyPlus simulation returned False")
                
                # 收集生成的文件（PNG、CSV、XLSX、HTML、ZIP）
                artifacts = []
                work_dir_path = PathLib(work_dir)
                if work_dir_path.exists():
                    for item in work_dir_path.rglob("*"):
                        if item.is_file():
                            rel_path = item.relative_to(job_base)
                            # 收集所有结果文件，包括压缩包
                            if item.suffix in [".xlsx", ".csv", ".png", ".html", ".zip"]:
                                artifacts.append({
                                    "kind": "file",
                                    "name": item.name,
                                    "url": f"/api/materials/{job_id}/files/{rel_path.as_posix()}",
                                })
                
                payload = JobResult(
                    job_id=job_id,
                    generated_at=datetime.utcnow(),
                    summary={
                        "weather_group": weather_group,
                        "scenarios_count": len(scenarios),
                        "output_files_count": len(artifacts),
                        "work_dir": work_dir,
                    },
                    plots=[],
                    artifacts=artifacts,
                ).model_dump(mode="json")
                
                out = job_result_path(job_id)
                out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
                
            except Exception as e:
                err = traceback.format_exc()
                raise RuntimeError(f"Material comparison failed: {err}") from e

        elif job_type == "compare_glass":
            # 玻璃辐射节能效果对比分析（使用EnergyPlus）
            from webapi.services.storage_service import job_dir
            from pathlib import Path as PathLib  # 显式导入避免作用域冲突

            # 导入玻璃对比模块
            _glass_comparison = importlib.import_module("glass_comparison_tool.examples.glass_compare")
            run_glass_comparison_energyplus = getattr(_glass_comparison, "run_glass_comparison_energyplus")

            # 解析参数
            print(f"\n[WORKER DEBUG] job_id={job_id} raw params={params}")
            weather_group = params.get("weather_group", "china")
            scenarios = params.get("scenarios", [])
            idf_template_dir = params.get("idf_template_dir")  # 新增：IDF模板目录
            energyplus_exe = params.get("energyplus_exe", "D:\\academic_tool\\EnergyPlusV9-1-0\\energyplus.exe")  # 新增：EnergyPlus路径
            global_params = params.get("global_params")  # 新增：全局参数
            enable_latent_heat = bool(params.get("enable_latent_heat", False))  # 新增：是否启用蒸发潜热
            wet_fraction = float(params.get("wet_fraction", 1.0) or 1.0)  # 新增：润湿面积比例
            colormap_params = params.get("colormap_params")  # 色系参数
            print(f"[WORKER DEBUG] enable_latent_heat={enable_latent_heat} wet_fraction={wet_fraction} weather_group={weather_group}")
            print(f"[WORKER DEBUG] colormap_params={colormap_params}")

            # 玻璃对比工具不再做缩放，直接使用 EnergyPlus 原始输出值
            scale_factor = 1.0
            print(f"[WORKER DEBUG] glass scale_factor={scale_factor} (no scaling)")

            # 创建job工作目录（每次运行使用独立目录）
            job_base = job_dir(job_id)
            work_dir = str(job_base / "work")  # 使用work子目录作为工作目录

            try:
                # 运行玻璃对比分析（使用EnergyPlus）
                success = run_glass_comparison_energyplus(
                    scenarios=scenarios if scenarios else None,
                    progress_cb=None,  # 在后台任务中不使用进度回调
                    weather_group=weather_group,
                    idf_template_dir=idf_template_dir,
                    energyplus_exe=energyplus_exe,
                    work_dir=work_dir,  # 使用job目录作为工作目录
                    global_params=global_params,  # 传递全局参数
                    enable_latent_heat=enable_latent_heat,  # 传递蒸发潜热参数
                    wet_fraction=wet_fraction,  # 传递润湿面积比例
                    scale_factor=scale_factor,  # 按模型自适应的单位换算因子
                    colormap_params=colormap_params,  # 传递色系参数
                )

                if not success:
                    raise RuntimeError("Glass comparison failed: EnergyPlus simulation returned False")

                # 收集生成的文件（PNG、CSV、XLSX、HTML、ZIP）
                artifacts = []
                work_dir_path = PathLib(work_dir)
                if work_dir_path.exists():
                    for item in work_dir_path.rglob("*"):
                        if item.is_file():
                            rel_path = item.relative_to(job_base)
                            # 收集所有结果文件，包括压缩包
                            if item.suffix in [".xlsx", ".csv", ".png", ".html", ".zip"]:
                                artifacts.append({
                                    "kind": "file",
                                    "name": item.name,
                                    "url": f"/api/glass/{job_id}/files/{rel_path.as_posix()}",
                                })

                payload = JobResult(
                    job_id=job_id,
                    generated_at=datetime.utcnow(),
                    summary={
                        "weather_group": weather_group,
                        "scenarios_count": len(scenarios),
                        "output_files_count": len(artifacts),
                        "work_dir": work_dir,
                    },
                    plots=[],
                    artifacts=artifacts,
                ).model_dump(mode="json")

                out = job_result_path(job_id)
                out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")

            except Exception as e:
                err = traceback.format_exc()
                raise RuntimeError(f"Glass comparison failed: {err}") from e

        elif job_type == "energy_map":
            # 功量地图计算
            try:
                from webapi.services.storage_service import job_dir
                from pathlib import Path as PathLib
                import pandas as pd
                import numpy as np
                
                # 解析参数
                calculation_mode = params.get("calculation_mode", "cooling")  # cooling, heating, or cooling+heating
                weather_group = params.get("weather_group", "china")  # china, world, or world_weather2025
                phases = params.get("phases", [])  # 材料相态配置
                transition_mode = params.get("transition_mode", "gradient")  # gradient or step
                enable_latent_heat = bool(params.get("enable_latent_heat", False))
                wet_fraction = float(params.get("wet_fraction", 1.0) or 1.0)
                
                if weather_group not in ("china", "world", "world_weather2025"):
                    raise ValueError(f"Invalid weather_group: {weather_group}")
                if not phases or len(phases) == 0:
                    raise ValueError("At least one material phase is required")
                
                # 确定需要计算哪些模式
                need_cooling = calculation_mode in ("cooling", "cooling+heating")
                need_heating = calculation_mode in ("heating", "cooling+heating")
                
                # 创建job工作目录
                job_base = job_dir(job_id)
                work_dir = job_base / "work"
                work_dir.mkdir(parents=True, exist_ok=True)
                
                # 根据weather_group确定EPW文件目录
                base = PathLib(__file__).resolve().parents[1]
                if weather_group == "china":
                    epw_dir = base / "material_comparison_tool" / "china_weather"
                elif weather_group == "world":
                    epw_dir = base / "material_comparison_tool" / "world_weather"
                elif weather_group == "world_weather2025":
                    epw_dir = base / "material_comparison_tool" / "world_weather2025"
                else:
                    raise ValueError(f"Unknown weather_group: {weather_group}")
                
                if not epw_dir.exists():
                    raise FileNotFoundError(f"EPW directory not found: {epw_dir}")
                
                # 材料相态插值函数
                def get_material_properties(temp: float, phases: list, mode: str) -> tuple[float, float]:
                    """根据温度获取发射率和吸收率"""
                    if mode == "gradient":
                        # 渐变模式：高斯插值
                        if len(phases) == 1:
                            return phases[0]["emissivity"], phases[0]["absorptivity"]
                        
                        # 计算带宽参数σ（基于数据点的平均间距）
                        sorted_phases = sorted(phases, key=lambda p: p["temperature"])
                        temp_diffs = []
                        for i in range(len(sorted_phases) - 1):
                            diff = abs(sorted_phases[i + 1]["temperature"] - sorted_phases[i]["temperature"])
                            temp_diffs.append(diff)
                        
                        avg_diff = sum(temp_diffs) / len(temp_diffs) if temp_diffs else 5.0
                        # 降低带宽：σ设为平均间距的0.25倍，至少0.5°C（更小的带宽使插值更接近数据点）
                        sigma = max(avg_diff * 0.4, 0.5)
                        
                        # 高斯加权插值
                        weighted_emissivity = 0.0
                        weighted_absorptivity = 0.0
                        total_weight = 0.0
                        
                        for phase in phases:
                            dist = abs(phase["temperature"] - temp)
                            # 高斯核函数：exp(-(x-xi)^2 / (2*σ^2))
                            weight = np.exp(-(dist * dist) / (2 * sigma * sigma))
                            
                            weighted_emissivity += phase["emissivity"] * weight
                            weighted_absorptivity += phase["absorptivity"] * weight
                            total_weight += weight
                        
                        # 归一化
                        if total_weight > 0:
                            return weighted_emissivity / total_weight, weighted_absorptivity / total_weight
                        
                        # 如果权重为0（理论上不会发生），返回最近的点
                        closest_phase = min(phases, key=lambda p: abs(p["temperature"] - temp))
                        return closest_phase["emissivity"], closest_phase["absorptivity"]
                    else:
                        # 突变模式：使用最近温度点
                        closest_phase = min(phases, key=lambda p: abs(p["temperature"] - temp))
                        return closest_phase["emissivity"], closest_phase["absorptivity"]
                    
                    # 默认返回第一个相态的值
                    return phases[0]["emissivity"], phases[0]["absorptivity"]
                
                # 查找所有EPW文件
                import glob
                epw_files = sorted(glob.glob(str(epw_dir / "*.epw")))
                if not epw_files:
                    raise FileNotFoundError(f"No EPW files found in {epw_dir}")
                
                # 导入WeatherData类
                _weather_data = importlib.import_module("core.weather_data")
                WeatherData = getattr(_weather_data, "WeatherData")
                
                # Stefan-Boltzmann常数 (W/m²·K⁴)
                STEFAN_BOLTZMANN = 5.670374419e-8
                
                # 存储每个EPW文件的结果
                epw_results = []
                total_power_wh = 0.0  # 总功量（Wh）
                artifacts = []  # 初始化artifacts列表
                
                # 遍历所有EPW文件
                for epw_file_path in epw_files:
                    epw_path_obj = PathLib(epw_file_path)
                    print(f"[Power Map] Processing EPW file: {epw_path_obj.name}")
                    
                    try:
                        # 读取EPW文件
                        weather_data = WeatherData(str(epw_file_path))
                        
                        # 获取全年数据
                        annual_data = weather_data.get_annual_data()
                        
                        if annual_data.empty:
                            print(f"[Power Map] Warning: EPW file {epw_path_obj.name} has no data")
                            continue
                        
                        # 计算该EPW文件的总功量
                        epw_cooling_power_wh = 0.0
                        epw_heating_power_wh = 0.0
                        hourly_results = []
                        
                        # 遍历每个小时
                        for idx, row in annual_data.iterrows():
                            # 获取每小时数据
                            dbt = float(row['DBT'])  # 干球温度 (°C)
                            if pd.isna(dbt) or dbt < -50 or dbt > 60:
                                continue  # 跳过无效温度
                            
                            # 获取材料参数（根据温度）
                            emissivity, absorptivity = get_material_properties(dbt, phases, transition_mode)
                            
                            # 获取辐射数据
                            # Global Solar (W/m²) - 水平面全球辐射
                            global_solar_wm2 = float(row['GloHorzRad']) if 'GloHorzRad' in annual_data.columns and pd.notna(row['GloHorzRad']) else 0.0
                            global_solar_wm2 = max(0.0, global_solar_wm2)  # 确保非负
                            
                            # Infrared Sky Radiation (W/m²) - 水平面红外天空辐射
                            infrared_sky_wm2 = float(row['HorzIR']) if 'HorzIR' in annual_data.columns and pd.notna(row['HorzIR']) else 0.0
                            infrared_sky_wm2 = max(0.0, infrared_sky_wm2)  # 确保非负
                            
                            # 计算每小时总热辐射能量（使用Stefan-Boltzmann定律）
                            # E = σ * T^4，其中T是开尔文温度
                            temp_k = dbt + 273.15  # 转换为开尔文
                            total_thermal_radiation_wm2 = STEFAN_BOLTZMANN * (temp_k ** 4)  # W/m²
                            
                            # 转换为每小时能量（Wh/m²）：功率 (W/m²) × 1小时 = 能量 (Wh/m²)
                            # 1 W = 1 J/s, 1 Wh = 3600 J, 所以 1 W × 1 h = 1 Wh
                            # 因此转换系数为 1（不是 3.6）
                            total_thermal_radiation_wh = total_thermal_radiation_wm2 * 1.0  # Wh/m²
                            global_solar_wh = global_solar_wm2 * 1.0  # Wh/m²
                            infrared_sky_wh = infrared_sky_wm2 * 1.0  # Wh/m²
                            
                            # 计算制冷功量（如果需要）
                            hourly_cooling_power_wh = 0.0
                            if need_cooling:
                                # 制冷计算：
                                # 1. 太阳光热吸收 = Global Solar (Wh) × 吸收率
                                solar_heat_absorption_wh = global_solar_wh * absorptivity
                                
                                # 2. 大气热发射 = (每小时总热辐射能量 - infrared Sky radiation) × 发射率
                                atmospheric_heat_emission_wh = (total_thermal_radiation_wh - infrared_sky_wh) * emissivity

                                # 3. 总制冷功量（辐射贡献）= 大气热发射 - 太阳光热吸收
                                total_cooling_power_wh = atmospheric_heat_emission_wh - solar_heat_absorption_wh

                                # 4. 可选：叠加蒸发冷却功率（使用天气文件中的相对湿度）
                                if enable_latent_heat and 'RH' in annual_data.columns and pd.notna(row.get('RH')):
                                    try:
                                        rh_val = float(row['RH'])
                                        RH_normalized = rh_val / 100.0 if rh_val > 1.0 else rh_val
                                        RH_normalized = max(0.0, min(1.0, RH_normalized))
                                        # 与 core/calculations.py 主路径一致：
                                        # 使用固定 h_conv=5.0 W/(m²·K)（无强制风典型值），避免默认 h_m=0.005 m/s 过小。
                                        Q_latent_wm2 = calculate_latent_heat_power(
                                            T_surface_K=float(temp_k),
                                            T_ambient_K=float(temp_k),
                                            RH=RH_normalized,
                                            h_conv=5.0,
                                        )
                                        wf = max(0.0, min(1.0, float(wet_fraction)))
                                        Q_latent_wh = float(Q_latent_wm2) * wf
                                        total_cooling_power_wh += Q_latent_wh
                                    except Exception:
                                        pass

                                # 5. 如果总制冷功量 < 0，设为 0
                                hourly_cooling_power_wh = max(0.0, total_cooling_power_wh)
                                epw_cooling_power_wh += hourly_cooling_power_wh
                            
                            # 计算制热功量（如果需要）
                            hourly_heating_power_wh = 0.0
                            if need_heating:
                                # 制热：太阳光热吸收 + 大气热吸收
                                solar_absorption_wh = global_solar_wh * absorptivity
                                atmospheric_absorption_wh = (infrared_sky_wh - total_thermal_radiation_wh) * emissivity
                                total_heating_power_wh = solar_absorption_wh + atmospheric_absorption_wh
                                # 如果总制热功量 < 0，设为 0
                                hourly_heating_power_wh = max(0.0, total_heating_power_wh)
                                epw_heating_power_wh += hourly_heating_power_wh
                            
                            # 记录每小时数据（用于调试和详细结果）
                            hourly_results.append({
                                "datetime": str(row['DateTime']),
                                "dbt_c": dbt,
                                "emissivity": emissivity,
                                "absorptivity": absorptivity,
                                "total_thermal_radiation_wh": total_thermal_radiation_wh,
                                "global_solar_wh": global_solar_wh,
                                "infrared_sky_wh": infrared_sky_wh,
                                "cooling_power_wh": hourly_cooling_power_wh,
                                "heating_power_wh": hourly_heating_power_wh,
                            })
                        
                        # 计算总功量
                        epw_total_power_wh = epw_cooling_power_wh + epw_heating_power_wh
                        total_power_wh += epw_total_power_wh
                        
                        # 不保存详细结果文件，只保留汇总数据
                        epw_results.append({
                            "epw_file": epw_path_obj.name,
                            "cooling_power_wh": epw_cooling_power_wh,
                            "heating_power_wh": epw_heating_power_wh,
                            "total_power_wh": epw_total_power_wh,
                            "hours_count": len(hourly_results),
                        })
                        
                        print(f"[Power Map] {epw_path_obj.name}: cooling={epw_cooling_power_wh:.2f} Wh, heating={epw_heating_power_wh:.2f} Wh, total={epw_total_power_wh:.2f} Wh ({len(hourly_results)} hours)")
                        
                    except Exception as e:
                        print(f"[Power Map] Error processing {epw_path_obj.name}: {e}")
                        # NOTE: don't import `traceback` here; importing inside `run_job()`
                        # would make it a local variable and can break later references
                        # (e.g. `traceback.format_exc()` in the outer exception handler).
                        traceback.print_exc()
                        continue
                
                print(f"[Power Map] Processed {len(epw_results)} EPW files")
                
                if len(epw_results) == 0:
                    raise RuntimeError(f"No EPW files were successfully processed. Checked {len(epw_files)} files in {epw_dir}")
                
                # 生成data.csv文件（用于前端绘制柱状图）
                # 格式参考compare_materials的data.csv
                data_csv_rows = []
                
                print(f"[Power Map] Starting to generate data.csv from {len(epw_results)} EPW results")
                
                HOURS_PER_YEAR = 8760.0

                for epw_result in epw_results:
                    epw_name = epw_result["epw_file"]
                    cooling_power_wh = epw_result.get("cooling_power_wh", 0.0)
                    heating_power_wh = epw_result.get("heating_power_wh", 0.0)
                    total_power_wh = epw_result.get("total_power_wh", cooling_power_wh + heating_power_wh)
                    average_power = float(total_power_wh) / HOURS_PER_YEAR if HOURS_PER_YEAR > 0 else 0.0
                    
                    # 提取EPW文件名（不含扩展名）作为FQ
                    epw_stem = PathLib(epw_name).stem
                    
                    if weather_group == "china":
                        # 中国模式：需要映射EPW文件名到省份名
                        epw_to_name = {
                            'anhui province': '安徽省', 'beijing': '北京市', 'chongqing': '重庆市',
                            'fujian': '福建省', 'gansu': '甘肃省', 'guangdong province': '广东省',
                            'guangxi zhuang autonomous region': '广西壮族自治区', 'guizhou province': '贵州省',
                            'hainan province': '海南省', 'hebei province': '河北省', 'heilongjiang province': '黑龙江省',
                            'henan province': '河南省', 'hongkong': '香港特别行政区', 'hubei province': '湖北省',
                            'hunan province': '湖南省', 'inner mongolia autonomous region': '内蒙古自治区',
                            'jiangsu': '江苏省', 'jiangxi province': '江西省', 'jilin province': '吉林省',
                            'liaoning': '辽宁省', 'macao': '澳门特别行政区', 'ningxia hui autonomous region': '宁夏回族自治区',
                            'qinghai province': '青海省', 'shaanxi province': '陕西省', 'shandong province': '山东省',
                            'shanghai': '上海市', 'shanxi province': '山西省', 'shenzhen': '深圳市',
                            'sichuan': '四川省', 'taiwan province': '台湾省', 'tianjin': '天津市',
                            'tibet autonomous region': '西藏自治区', 'xinjiang uyghur autonomous region': '新疆维吾尔自治区',
                            'yunnan province': '云南省', 'zhejiang province': '浙江省',
                        }
                        
                        epw_key = epw_stem.lower().strip()
                        province_name = epw_to_name.get(epw_key, None)
                        
                        if province_name:
                            # 根据计算方案设置列名
                            data_csv_rows.append({
                                "NAME": province_name,
                                "FQ": epw_stem,
                                "Cooling": cooling_power_wh,
                                "Heating": heating_power_wh,
                                "Total": total_power_wh,
                                "AveragePower": average_power,
                            })
                            print(f"[Power Map] Added to data.csv: {epw_stem} -> {province_name}, cooling={cooling_power_wh:.2f} Wh, heating={heating_power_wh:.2f} Wh, total={total_power_wh:.2f} Wh, avg={average_power:.4f} W/(m2*year)")
                        else:
                            print(f"[Power Map] WARNING: EPW file '{epw_stem}' (key: '{epw_key}') not found in province mapping, skipping from data.csv")
                    else:
                        # 世界模式：需要QID和FQ
                        # 尝试从模板文件读取QID映射
                        fq_to_qid_map = None
                        template_path = r"g:\Energyplus\map\world\GISDATA\气候区划\1data.csv"
                        
                        if PathLib(template_path).exists():
                            try:
                                template_df = pd.read_csv(template_path, encoding='utf-8-sig', engine='python')
                                if 'FQ' in template_df.columns and 'QID' in template_df.columns:
                                    fq_to_qid_map = {}
                                    for _, row in template_df.iterrows():
                                        fq_val = str(row['FQ']).strip().lower() if pd.notna(row['FQ']) else ''
                                        qid_val = row['QID'] if pd.notna(row['QID']) else None
                                        if fq_val and qid_val is not None:
                                            fq_to_qid_map[fq_val] = qid_val
                            except Exception as e:
                                print(f"[WARN] 读取模板文件失败: {e}，将使用内置映射")
                        
                        if not fq_to_qid_map:
                            # 内置FQ到QID映射
                            fq_to_qid_map = {
                                'af': 1, 'am': 2, 'aw': 3, 'bsh': 6, 'bsk': 7, 'bwh': 4, 'bwk': 5,
                                'cfa': 14, 'cfb': 15, 'cfc': 16, 'csa': 8, 'csb': 9, 'csc': 10,
                                'cwa': 11, 'cwb': 12, 'cwc': 13, 'dfa': 25, 'dfb': 26, 'dfc': 27, 'dfd': 28,
                                'dsa': 17, 'dsb': 18, 'dsc': 19, 'dsd': 20, 'dwa': 21, 'dwb': 22, 'dwc': 23, 'dwd': 24,
                                'ef': 29, 'et': 30,
                            }
                        
                        fq_key = epw_stem.lower().strip()
                        qid = fq_to_qid_map.get(fq_key, None)
                        
                        if qid is None:
                            # 如果没有找到QID，使用序号
                            max_qid = max([r.get('QID', 0) for r in data_csv_rows if 'QID' in r], default=0)
                            qid = int(max_qid) + 1
                        
                        data_csv_rows.append({
                            "QID": qid,
                            "FQ": epw_stem,
                            "Cooling": cooling_power_wh,
                            "Heating": heating_power_wh,
                            "Total": total_power_wh,
                        })
                        # 为世界模式同样添加平均功率列（使用相同 total_power_wh / 8760 定义）
                        data_csv_rows[-1]["AveragePower"] = average_power
                        print(f"[Power Map] Added to data.csv: {epw_stem} -> QID={qid}, cooling={cooling_power_wh:.2f} Wh, heating={heating_power_wh:.2f} Wh, total={total_power_wh:.2f} Wh, avg={average_power:.4f} W/(m2*year)")
                
                # 生成data.csv
                print(f"[Power Map] data_csv_rows count: {len(data_csv_rows)}")
                if data_csv_rows:
                    data_csv_path = work_dir / "data.csv"
                    print(f"[Power Map] Writing data.csv to: {data_csv_path.absolute()}")
                    data_df = pd.DataFrame(data_csv_rows)
                    data_df.to_csv(data_csv_path, index=False, encoding='utf-8-sig')
                    
                    # 验证文件是否创建成功
                    if data_csv_path.exists():
                        file_size = data_csv_path.stat().st_size
                        print(f"[Power Map] ✓ data.csv created successfully at: {data_csv_path.absolute()}")
                        print(f"[Power Map] ✓ data.csv file size: {file_size} bytes")
                        print(f"[Power Map] ✓ data.csv contains {len(data_csv_rows)} rows")
                    else:
                        print(f"[Power Map] ✗ ERROR: data.csv file was not created at: {data_csv_path.absolute()}")
                    
                    artifacts.append(
                        {
                            "kind": "csv",
                            "name": "data.csv",
                            "url": f"/api/jobs/{job_id}/files/work/data.csv",
                        }
                    )
                    print(f"[Power Map] Added data.csv to artifacts with URL: /api/jobs/{job_id}/files/work/data.csv")

                    # 基于 AveragePower 列生成中国功量地图（仅中国模式）
                    if weather_group == "china":
                        china_map_png = work_dir / "china_power_map_average_power.png"
                        try:
                            ok = _generate_china_power_map_from_csv(data_csv_path, china_map_png)
                        except Exception:
                            # 防止地图绘制异常导致整个任务失败
                            traceback.print_exc()
                            ok = False

                        if ok and china_map_png.exists():
                            artifacts.append(
                                {
                                    "kind": "image",
                                    "name": china_map_png.name,
                                    "url": f"/api/jobs/{job_id}/files/work/{china_map_png.name}",
                                }
                            )
                            print(
                                f"[Power Map] Added China AveragePower map to artifacts with URL: "
                                f"/api/jobs/{job_id}/files/work/{china_map_png.name}"
                            )
                else:
                    print(f"[Power Map] ✗ WARNING: data_csv_rows is empty, no data.csv will be generated!")
                    print(f"[Power Map] epw_results: {epw_results}")
                
                # 只保留data.csv，不生成其他汇总文件
                print(f"[Power Map] Total artifacts count: {len(artifacts)}")
                
                payload = JobResult(
                    job_id=job_id,
                    generated_at=datetime.utcnow(),
                    summary={
                        "calculation_mode": calculation_mode,
                        "total_power_wh": total_power_wh,
                        "weather_group": weather_group,
                        "phases_count": len(phases),
                        "transition_mode": transition_mode,
                        "enable_latent_heat": enable_latent_heat,
                        "wet_fraction": wet_fraction,
                    },
                    plots=[],
                    artifacts=artifacts,
                ).model_dump(mode="json")
                
                out = job_result_path(job_id)
                out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
                
            except Exception as e:
                err = traceback.format_exc()
                raise RuntimeError(f"Power map calculation failed: {err}") from e

        elif job_type == "material_env_temp_map":
            # 材料温度地图计算
            # 目标：在给定EPW气象点和材料相态配置下，求解辐射制冷功率为0时的材料温度 T_eq
            # 温差 ΔT = T_eq - T_a（ΔT > 0 表示材料温度高于环境，仍可被动降温；
            #          ΔT ≤ 0 表示材料温度低于/等于环境，制冷失效）
            # 输出：全年最大温差地图 + 全年平均温差地图
            try:
                from webapi.services.storage_service import job_dir
                from pathlib import Path as PathLib
                import pandas as pd
                import numpy as np

                # 解析参数
                weather_group = params.get("weather_group", "china")
                phases = params.get("phases", [])
                transition_mode = params.get("transition_mode", "gradient")
                h_coefficient = float(params.get("h_coefficient", 20.0) or 20.0)
                # 辐射制冷效率经验修正系数（0.5~1.0），1.0 = 不修正，0.75 = 打75折
                # 用于补偿简化宽带模型对辐射制冷效果的高估（天空有效温度、视角因子等未精确建模）
                cooling_efficiency_factor = float(params.get("cooling_efficiency_factor", 0.75) or 0.75)
                cooling_efficiency_factor = max(0.5, min(1.0, cooling_efficiency_factor))

                # 对流换热系数 = 基础项 + 用户输入项
                # 基础项 25 W/(m²·K)：代表材料与环境之间不可避免的基准对流散热（提高自 10）
                # 用户输入项：额外增加的对流散热（如有风、强制对流等）
                BASELINE_H = 25.0
                total_h = BASELINE_H + h_coefficient

                if weather_group not in ("china", "world", "world_weather2025"):
                    raise ValueError(f"Invalid weather_group: {weather_group}")
                if not phases or len(phases) == 0:
                    raise ValueError("At least one material phase is required")

                # 创建job工作目录
                job_base = job_dir(job_id)
                work_dir = job_base / "work"
                work_dir.mkdir(parents=True, exist_ok=True)

                # 根据weather_group确定EPW文件目录
                base = PathLib(__file__).resolve().parents[1]
                if weather_group == "china":
                    epw_dir = base / "material_comparison_tool" / "china_weather"
                elif weather_group == "world":
                    epw_dir = base / "material_comparison_tool" / "world_weather"
                elif weather_group == "world_weather2025":
                    epw_dir = base / "material_comparison_tool" / "world_weather2025"
                else:
                    raise ValueError(f"Unknown weather_group: {weather_group}")

                if not epw_dir.exists():
                    raise FileNotFoundError(f"EPW directory not found: {epw_dir}")

                # 材料相态插值函数（与energy_map完全一致）
                def get_material_properties(temp: float, phases: list, mode: str) -> tuple[float, float]:
                    if mode == "gradient":
                        if len(phases) == 1:
                            return phases[0]["emissivity"], phases[0]["absorptivity"]

                        sorted_phases = sorted(phases, key=lambda p: p["temperature"])
                        temp_diffs = []
                        for i in range(len(sorted_phases) - 1):
                            diff = abs(sorted_phases[i + 1]["temperature"] - sorted_phases[i]["temperature"])
                            temp_diffs.append(diff)

                        avg_diff = sum(temp_diffs) / len(temp_diffs) if temp_diffs else 5.0
                        sigma = max(avg_diff * 0.4, 0.5)

                        weighted_emissivity = 0.0
                        weighted_absorptivity = 0.0
                        total_weight = 0.0

                        for phase in phases:
                            dist = abs(phase["temperature"] - temp)
                            weight = np.exp(-(dist * dist) / (2 * sigma * sigma))
                            weighted_emissivity += phase["emissivity"] * weight
                            weighted_absorptivity += phase["absorptivity"] * weight
                            total_weight += weight

                        if total_weight > 0:
                            return weighted_emissivity / total_weight, weighted_absorptivity / total_weight

                        closest_phase = min(phases, key=lambda p: abs(p["temperature"] - temp))
                        return closest_phase["emissivity"], closest_phase["absorptivity"]
                    else:
                        closest_phase = min(phases, key=lambda p: abs(p["temperature"] - temp))
                        return closest_phase["emissivity"], closest_phase["absorptivity"]

                # Stefan-Boltzmann常数 (W/m²·K⁴)
                STEFAN_BOLTZMANN = 5.670374419e-8

                # 定义目标函数：
                # f(T_eq) = εσ(T_eq⁴ - T_a⁴) + ε·IR_sky - α·G_solar + h·(T_eq - T_a) = 0
                # 即：大气热发射 - 太阳光热吸收 + 对流换热 = 0
                def residual_cooling(T_eq_K: float, T_a_C: float, G_solar: float, IR_sky: float,
                                     phases: list, mode: str, h: float,
                                     cooling_eff: float = 1.0) -> float:
                    """制冷功率残差（W/m²），T_eq_K为开尔文温度，h为对流换热系数（W/m²·K）
                    cooling_eff: 辐射制冷效率修正系数，0.5~1.0，用于补偿简化模型对制冷效果的高估"""
                    eps, alpha = get_material_properties(T_eq_K - 273.15, phases, mode)
                    T_eq = T_eq_K
                    T_a = T_a_C + 273.15
                    # 大气热发射 = ε·σ·T_eq⁴ - ε·σ·T_a⁴ + ε·IR_sky
                    atmospheric_emission = eps * STEFAN_BOLTZMANN * (T_eq ** 4 - T_a ** 4) + eps * IR_sky
                    # 太阳光热吸收
                    solar_absorption = alpha * G_solar
                    # 对流换热：h·(T_eq - T_a)，T_eq > T_a 时为正（从材料带走热量）
                    convection = h * (T_eq - T_a)
                    # 经验修正：将辐射制冷贡献（大气发射 - 太阳吸收）乘以效率系数
                    return (atmospheric_emission - solar_absorption) * cooling_eff + convection

                def d_residual_cooling_dT(T_eq_K: float, T_a_C: float, G_solar: float, IR_sky: float,
                                         phases: list, mode: str, h: float,
                                         cooling_eff: float = 1.0) -> float:
                    """残差对T_eq的解析导数（含效率系数修正）"""
                    eps, _ = get_material_properties(T_eq_K - 273.15, phases, mode)
                    T_eq = T_eq_K
                    # d(ε·σ·T⁴)/dT = ε·σ·4T³；d(h·(T-T_a))/dT = h
                    return eps * STEFAN_BOLTZMANN * 4.0 * (T_eq ** 3) * cooling_eff + h

                def solve_T_eq(T_a_C: float, G_solar: float, IR_sky: float,
                               phases: list, mode: str, h: float,
                               cooling_eff: float = 1.0) -> float:
                    """
                    求解制冷功率为0时的材料温度T_eq（°C）。
                    使用牛顿迭代法，初始猜测为 T_a + 5K（略高于环境温度）。
                    T_eq > T_a 时表示可以实现被动降温。
                    """
                    T_a_K = T_a_C + 273.15
                    T_init_K = T_a_K + 5.0  # 初始猜测：略高于环境

                    T_curr = T_init_K
                    # 温度搜索范围：-50°C ~ 200°C
                    T_min_K = -50.0 + 273.15
                    T_max_K = 200.0 + 273.15

                    for _ in range(100):
                        f_val = residual_cooling(T_curr, T_a_C, G_solar, IR_sky, phases, mode, h, cooling_eff)
                        df_val = d_residual_cooling_dT(T_curr, T_a_C, G_solar, IR_sky, phases, mode, h, cooling_eff)

                        if abs(df_val) < 1e-12:
                            # 导数接近0，切换策略：二分搜索
                            T_lo = T_min_K
                            T_hi = T_max_K
                            for _ in range(60):
                                T_mid = (T_lo + T_hi) / 2.0
                                f_mid = residual_cooling(T_mid, T_a_C, G_solar, IR_sky, phases, mode, h, cooling_eff)
                                if abs(f_mid) < 1e-6:
                                    return T_mid - 273.15
                                if f_mid * residual_cooling(T_lo, T_a_C, G_solar, IR_sky, phases, mode, h, cooling_eff) < 0:
                                    T_hi = T_mid
                                else:
                                    T_lo = T_mid
                            return (T_lo + T_hi) / 2.0 - 273.15

                        delta = f_val / df_val
                        T_next = T_curr - delta
                        T_next = max(T_min_K, min(T_max_K, T_next))

                        if abs(T_next - T_curr) < 1e-6:
                            T_curr = T_next
                            break
                        T_curr = T_next

                    return T_curr - 273.15

                # 查找所有EPW文件
                import glob
                epw_files = sorted(glob.glob(str(epw_dir / "*.epw")))
                if not epw_files:
                    raise FileNotFoundError(f"No EPW files found in {epw_dir}")

                # 导入WeatherData类
                _weather_data = importlib.import_module("core.weather_data")
                WeatherData = getattr(_weather_data, "WeatherData")

                # 存储每个EPW文件的结果
                epw_results = []
                artifacts = []

                print(f"[Material Env Temp Map] Starting calculation with {len(epw_files)} EPW files")

                for epw_file_path in epw_files:
                    epw_path_obj = PathLib(epw_file_path)
                    print(f"[Material Env Temp Map] Processing EPW file: {epw_path_obj.name}")

                    try:
                        weather_data = WeatherData(str(epw_file_path))
                        annual_data = weather_data.get_annual_data()

                        if annual_data.empty:
                            print(f"[Material Env Temp Map] Warning: EPW file {epw_path_obj.name} has no data")
                            continue

                        hourly_dTs = []
                        hours_with_data = 0

                        for idx, row in annual_data.iterrows():
                            dbt = float(row['DBT'])
                            if pd.isna(dbt) or dbt < -50 or dbt > 60:
                                continue

                            G_solar = float(row['GloHorzRad']) if 'GloHorzRad' in annual_data.columns and pd.notna(row['GloHorzRad']) else 0.0
                            G_solar = max(0.0, G_solar)
                            IR_sky = float(row['HorzIR']) if 'HorzIR' in annual_data.columns and pd.notna(row['HorzIR']) else 0.0
                            IR_sky = max(0.0, IR_sky)

                            # 求解该时刻的T_eq（使用总对流换热系数 = 基准25 + 用户输入，辐射制冷效率系数修正）
                            T_eq_C = solve_T_eq(dbt, G_solar, IR_sky, phases, transition_mode, total_h, cooling_efficiency_factor)
                            dT = T_eq_C - dbt
                            hourly_dTs.append(dT)
                            hours_with_data += 1

                        if not hourly_dTs:
                            print(f"[Material Env Temp Map] Warning: No valid hours for {epw_path_obj.name}")
                            continue

                        arr_dT = np.array(hourly_dTs)
                        min_dT = float(np.min(arr_dT))  # 最深降温（最负值）：制冷效果最强的时刻
                        max_dT = float(np.max(arr_dT))  # 最差情况（最正值）：材料比环境还热
                        avg_dT = float(np.mean(arr_dT))  # 全年平均温差

                        epw_results.append({
                            "epw_file": epw_path_obj.name,
                            "min_dT": min_dT,   # 最深降温，用于"最大制冷温差地图"
                            "avg_dT": avg_dT,    # 平均温差，用于"平均温差地图"
                            "max_dT": max_dT,    # 最差情况（材料比环境热）
                            "hours_count": hours_with_data,
                        })

                        print(f"[Material Env Temp Map] {epw_path_obj.name}: min_dT={min_dT:.2f}°C (deepest cooling), avg_dT={avg_dT:.2f}°C, max_dT={max_dT:.2f}°C (worst) ({hours_with_data} hours)")

                    except Exception as e:
                        print(f"[Material Env Temp Map] Error processing {epw_path_obj.name}: {e}")
                        traceback.print_exc()
                        continue

                print(f"[Material Env Temp Map] Processed {len(epw_results)} EPW files")

                if len(epw_results) == 0:
                    raise RuntimeError(f"No EPW files were successfully processed. Checked {len(epw_files)} files in {epw_dir}")

                # 生成 data.csv
                data_csv_rows = []
                print(f"[Material Env Temp Map] Starting to generate data.csv from {len(epw_results)} EPW results")

                for epw_result in epw_results:
                    epw_name = epw_result["epw_file"]
                    max_dT = epw_result.get("max_dT", 0.0)
                    avg_dT = epw_result.get("avg_dT", 0.0)
                    min_dT = epw_result.get("min_dT", 0.0)
                    epw_stem = PathLib(epw_name).stem

                    if weather_group == "china":
                        epw_to_name = {
                            'anhui province': '安徽省', 'beijing': '北京市', 'chongqing': '重庆市',
                            'fujian': '福建省', 'gansu': '甘肃省', 'guangdong province': '广东省',
                            'guangxi zhuang autonomous region': '广西壮族自治区', 'guizhou province': '贵州省',
                            'hainan province': '海南省', 'hebei province': '河北省', 'heilongjiang province': '黑龙江省',
                            'henan province': '河南省', 'hongkong': '香港特别行政区', 'hubei province': '湖北省',
                            'hunan province': '湖南省', 'inner mongolia autonomous region': '内蒙古自治区',
                            'jiangsu': '江苏省', 'jiangxi province': '江西省', 'jilin province': '吉林省',
                            'liaoning': '辽宁省', 'macao': '澳门特别行政区', 'ningxia hui autonomous region': '宁夏回族自治区',
                            'qinghai province': '青海省', 'shaanxi province': '陕西省', 'shandong province': '山东省',
                            'shanghai': '上海市', 'shanxi province': '山西省', 'shenzhen': '深圳市',
                            'sichuan': '四川省', 'taiwan province': '台湾省', 'tianjin': '天津市',
                            'tibet autonomous region': '西藏自治区', 'xinjiang uyghur autonomous region': '新疆维吾尔自治区',
                            'yunnan province': '云南省', 'zhejiang province': '浙江省',
                        }

                        epw_key = epw_stem.lower().strip()
                        province_name = epw_to_name.get(epw_key, None)

                        if province_name:
                            data_csv_rows.append({
                                "NAME": province_name,
                                "FQ": epw_stem,
                                "MaxDeltaT": min_dT,   # 最深降温（制冷最强）：用于"最大制冷温差地图"
                                "AvgDeltaT": avg_dT,
                                "MinDeltaT": max_dT,   # 最差情况（材料最热）
                            })
                            print(f"[Material Env Temp Map] Added to data.csv: {epw_stem} -> {province_name}, min_dT={min_dT:.2f}°C (deepest cooling), avg_dT={avg_dT:.2f}°C, max_dT={max_dT:.2f}°C (worst)")
                        else:
                            print(f"[Material Env Temp Map] WARNING: EPW file '{epw_stem}' not found in province mapping, skipping")
                    else:
                        # 世界模式
                        fq_to_qid_map = None
                        template_path = r"g:\Energyplus\map\world\GISDATA\气候区划\1data.csv"
                        if PathLib(template_path).exists():
                            try:
                                template_df = pd.read_csv(template_path, encoding='utf-8-sig', engine='python')
                                if 'FQ' in template_df.columns and 'QID' in template_df.columns:
                                    fq_to_qid_map = {}
                                    for _, row in template_df.iterrows():
                                        fq_val = str(row['FQ']).strip().lower() if pd.notna(row['FQ']) else ''
                                        qid_val = row['QID'] if pd.notna(row['QID']) else None
                                        if fq_val and qid_val is not None:
                                            fq_to_qid_map[fq_val] = qid_val
                            except Exception:
                                pass

                        if not fq_to_qid_map:
                            fq_to_qid_map = {
                                'af': 1, 'am': 2, 'aw': 3, 'bsh': 6, 'bsk': 7, 'bwh': 4, 'bwk': 5,
                                'cfa': 14, 'cfb': 15, 'cfc': 16, 'csa': 8, 'csb': 9, 'csc': 10,
                                'cwa': 11, 'cwb': 12, 'cwc': 13, 'dfa': 25, 'dfb': 26, 'dfc': 27, 'dfd': 28,
                                'dsa': 17, 'dsb': 18, 'dsc': 19, 'dsd': 20, 'dwa': 21, 'dwb': 22, 'dwc': 23, 'dwd': 24,
                                'ef': 29, 'et': 30,
                            }

                        fq_key = epw_stem.lower().strip()
                        qid = fq_to_qid_map.get(fq_key, None)

                        if qid is None:
                            max_qid = max([r.get('QID', 0) for r in data_csv_rows if 'QID' in r], default=0)
                            qid = int(max_qid) + 1

                        data_csv_rows.append({
                            "QID": qid,
                            "FQ": epw_stem,
                            "MaxDeltaT": min_dT,   # 最深降温（制冷最强）：用于"最大制冷温差地图"
                            "AvgDeltaT": avg_dT,
                            "MinDeltaT": max_dT,   # 最差情况（材料最热）
                        })

                print(f"[Material Env Temp Map] data_csv_rows count: {len(data_csv_rows)}")

                if data_csv_rows:
                    data_csv_path = work_dir / "data.csv"
                    data_df = pd.DataFrame(data_csv_rows)
                    data_df.to_csv(data_csv_path, index=False, encoding='utf-8-sig')

                    if data_csv_path.exists():
                        print(f"[Material Env Temp Map] data.csv created successfully: {data_csv_path.stat().st_size} bytes, {len(data_csv_rows)} rows")

                    artifacts.append({
                        "kind": "csv",
                        "name": "data.csv",
                        "url": f"/api/jobs/{job_id}/files/work/data.csv",
                    })

                    # 绘制中国温差地图（仅中国模式）
                    if weather_group == "china":
                        # 全年最大温差地图
                        max_map_png = work_dir / "china_max_deltaT_map.png"
                        try:
                            ok_max = _generate_china_power_map_from_csv(
                                data_csv_path, max_map_png, value_column="MaxDeltaT",
                                custom_title="China Max Temperature Difference Distribution",
                                custom_label="Max ΔT (°C)",
                            )
                        except Exception:
                            traceback.print_exc()
                            ok_max = False

                        if ok_max and max_map_png.exists():
                            artifacts.append({
                                "kind": "image",
                                "name": max_map_png.name,
                                "url": f"/api/jobs/{job_id}/files/work/{max_map_png.name}",
                            })
                            print(f"[Material Env Temp Map] Added MaxDeltaT map to artifacts")

                        # 全年平均温差地图
                        avg_map_png = work_dir / "china_avg_deltaT_map.png"
                        try:
                            ok_avg = _generate_china_power_map_from_csv(
                                data_csv_path, avg_map_png, value_column="AvgDeltaT",
                                custom_title="China Average Temperature Difference Distribution",
                                custom_label="Avg ΔT (°C)",
                            )
                        except Exception:
                            traceback.print_exc()
                            ok_avg = False

                        if ok_avg and avg_map_png.exists():
                            artifacts.append({
                                "kind": "image",
                                "name": avg_map_png.name,
                                "url": f"/api/jobs/{job_id}/files/work/{avg_map_png.name}",
                            })
                            print(f"[Material Env Temp Map] Added AvgDeltaT map to artifacts")
                else:
                    print(f"[Material Env Temp Map] WARNING: data_csv_rows is empty, no data.csv will be generated!")

                print(f"[Material Env Temp Map] Total artifacts count: {len(artifacts)}")

                payload = JobResult(
                    job_id=job_id,
                    generated_at=datetime.utcnow(),
                    summary={
                        "weather_group": weather_group,
                        "phases_count": len(phases),
                        "transition_mode": transition_mode,
                        "h_coefficient": h_coefficient,   # 用户输入的额外对流散热
                        "total_h": total_h,                # 实际使用的总对流换热系数 = 25 + h_coefficient
                        "cooling_efficiency_factor": cooling_efficiency_factor,  # 辐射制冷效率修正系数
                        "total_epw_processed": len(epw_results),
                    },
                    plots=[],
                    artifacts=artifacts,
                ).model_dump(mode="json")

                out = job_result_path(job_id)
                out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")

            except Exception as e:
                err = traceback.format_exc()
                raise RuntimeError(f"Material Env Temp Map calculation failed: {err}") from e

        elif job_type == "radiation_cooling_clothing":
            # 辐射制冷服饰计算：基于energy_map，但只计算制冷，并乘以人口和衣物面积
            try:
                from webapi.services.storage_service import job_dir
                from pathlib import Path as PathLib
                import pandas as pd
                import numpy as np
                
                # 解析参数
                weather_group = params.get("weather_group", "china")
                phases = params.get("phases", [])
                transition_mode = params.get("transition_mode", "gradient")
                enable_latent_heat = bool(params.get("enable_latent_heat", False))
                wet_fraction = float(params.get("wet_fraction", 1.0) or 1.0)
                clothing_area_per_person = float(params.get("clothing_area_per_person", 0.0))
                
                if clothing_area_per_person <= 0:
                    raise ValueError("clothing_area_per_person must be greater than 0")
                
                if weather_group not in ("china", "world", "world_weather2025"):
                    raise ValueError(f"Invalid weather_group: {weather_group}")
                if not phases or len(phases) == 0:
                    raise ValueError("At least one material phase is required")
                
                # 固定为只计算制冷
                need_cooling = True
                need_heating = False
                
                # 创建job工作目录
                job_base = job_dir(job_id)
                work_dir = job_base / "work"
                work_dir.mkdir(parents=True, exist_ok=True)
                
                # 根据weather_group确定EPW文件目录
                base = PathLib(__file__).resolve().parents[1]
                if weather_group == "china":
                    epw_dir = base / "material_comparison_tool" / "china_weather"
                elif weather_group == "world":
                    epw_dir = base / "material_comparison_tool" / "world_weather"
                elif weather_group == "world_weather2025":
                    epw_dir = base / "material_comparison_tool" / "world_weather2025"
                else:
                    raise ValueError(f"Unknown weather_group: {weather_group}")
                
                if not epw_dir.exists():
                    raise FileNotFoundError(f"EPW directory not found: {epw_dir}")
                
                # 材料相态插值函数（复用energy_map的逻辑）
                def get_material_properties(temp: float, phases: list, mode: str) -> tuple[float, float]:
                    """根据温度获取发射率和吸收率"""
                    if mode == "gradient":
                        if len(phases) == 1:
                            return phases[0]["emissivity"], phases[0]["absorptivity"]
                        
                        sorted_phases = sorted(phases, key=lambda p: p["temperature"])
                        temp_diffs = []
                        for i in range(len(sorted_phases) - 1):
                            diff = abs(sorted_phases[i + 1]["temperature"] - sorted_phases[i]["temperature"])
                            temp_diffs.append(diff)
                        
                        avg_diff = sum(temp_diffs) / len(temp_diffs) if temp_diffs else 5.0
                        sigma = max(avg_diff * 0.4, 0.5)
                        
                        weighted_emissivity = 0.0
                        weighted_absorptivity = 0.0
                        total_weight = 0.0
                        
                        for phase in phases:
                            dist = abs(phase["temperature"] - temp)
                            weight = np.exp(-(dist * dist) / (2 * sigma * sigma))
                            weighted_emissivity += phase["emissivity"] * weight
                            weighted_absorptivity += phase["absorptivity"] * weight
                            total_weight += weight
                        
                        if total_weight > 0:
                            return weighted_emissivity / total_weight, weighted_absorptivity / total_weight
                        
                        closest_phase = min(phases, key=lambda p: abs(p["temperature"] - temp))
                        return closest_phase["emissivity"], closest_phase["absorptivity"]
                    else:
                        closest_phase = min(phases, key=lambda p: abs(p["temperature"] - temp))
                        return closest_phase["emissivity"], closest_phase["absorptivity"]
                
                # 查找所有EPW文件
                import glob
                epw_files = sorted(glob.glob(str(epw_dir / "*.epw")))
                if not epw_files:
                    raise FileNotFoundError(f"No EPW files found in {epw_dir}")
                
                # 导入WeatherData类
                _weather_data = importlib.import_module("core.weather_data")
                WeatherData = getattr(_weather_data, "WeatherData")
                
                STEFAN_BOLTZMANN = 5.670374419e-8
                
                # 存储每个EPW文件的结果
                epw_results = []
                artifacts = []
                
                # 遍历所有EPW文件（只计算制冷）
                for epw_file_path in epw_files:
                    epw_path_obj = PathLib(epw_file_path)
                    print(f"[Radiation Cooling Clothing] Processing EPW file: {epw_path_obj.name}")
                    
                    try:
                        weather_data = WeatherData(str(epw_file_path))
                        annual_data = weather_data.get_annual_data()
                        
                        if annual_data.empty:
                            print(f"[Radiation Cooling Clothing] Warning: EPW file {epw_path_obj.name} has no data")
                            continue
                        
                        epw_cooling_power_wh = 0.0
                        
                        for idx, row in annual_data.iterrows():
                            dbt = float(row['DBT'])
                            if pd.isna(dbt) or dbt < -50 or dbt > 60:
                                continue
                            
                            emissivity, absorptivity = get_material_properties(dbt, phases, transition_mode)
                            
                            global_solar_wm2 = float(row['GloHorzRad']) if 'GloHorzRad' in annual_data.columns and pd.notna(row['GloHorzRad']) else 0.0
                            global_solar_wm2 = max(0.0, global_solar_wm2)
                            
                            infrared_sky_wm2 = float(row['HorzIR']) if 'HorzIR' in annual_data.columns and pd.notna(row['HorzIR']) else 0.0
                            infrared_sky_wm2 = max(0.0, infrared_sky_wm2)
                            
                            temp_k = dbt + 273.15
                            total_thermal_radiation_wm2 = STEFAN_BOLTZMANN * (temp_k ** 4)
                            
                            total_thermal_radiation_wh = total_thermal_radiation_wm2 * 1.0
                            global_solar_wh = global_solar_wm2 * 1.0
                            infrared_sky_wh = infrared_sky_wm2 * 1.0
                            
                            # 计算制冷功量
                            hourly_cooling_power_wh = 0.0
                            if need_cooling:
                                solar_heat_absorption_wh = global_solar_wh * absorptivity
                                atmospheric_heat_emission_wh = (total_thermal_radiation_wh - infrared_sky_wh) * emissivity
                                total_cooling_power_wh = atmospheric_heat_emission_wh - solar_heat_absorption_wh
                                
                                if enable_latent_heat and 'RH' in annual_data.columns and pd.notna(row.get('RH')):
                                    try:
                                        rh_val = float(row['RH'])
                                        RH_normalized = rh_val / 100.0 if rh_val > 1.0 else rh_val
                                        RH_normalized = max(0.0, min(1.0, RH_normalized))
                                        # 与 core/calculations.py 主路径一致：固定 h_conv=5.0 W/(m²·K)（无强制风典型值）
                                        Q_latent_wm2 = calculate_latent_heat_power(
                                            T_surface_K=float(temp_k),
                                            T_ambient_K=float(temp_k),
                                            RH=RH_normalized,
                                            h_conv=5.0,
                                        )
                                        wf = max(0.0, min(1.0, float(wet_fraction)))
                                        Q_latent_wh = float(Q_latent_wm2) * wf
                                        total_cooling_power_wh += Q_latent_wh
                                    except Exception:
                                        pass

                                hourly_cooling_power_wh = max(0.0, total_cooling_power_wh)
                                epw_cooling_power_wh += hourly_cooling_power_wh
                        
                        epw_results.append({
                            "epw_file": epw_path_obj.name,
                            "cooling_power_wh": epw_cooling_power_wh,
                        })
                        
                        print(f"[Radiation Cooling Clothing] {epw_path_obj.name}: cooling={epw_cooling_power_wh:.2f} Wh")
                        
                    except Exception as e:
                        print(f"[Radiation Cooling Clothing] Error processing {epw_path_obj.name}: {e}")
                        traceback.print_exc()
                        continue
                
                print(f"[Radiation Cooling Clothing] Processed {len(epw_results)} EPW files")
                
                if len(epw_results) == 0:
                    raise RuntimeError(f"No EPW files were successfully processed. Checked {len(epw_files)} files in {epw_dir}")
                
                # 读取人口数据
                population_csv_path = PathLib(r"g:\Energyplus\study\xxigua\data.csv")
                population_data = {}
                
                if population_csv_path.exists():
                    try:
                        pop_df = pd.read_csv(population_csv_path, encoding='utf-8-sig')
                        # 读取NAME和人数（人）列
                        if 'NAME' in pop_df.columns and '人数（人）' in pop_df.columns:
                            for _, row in pop_df.iterrows():
                                name = str(row['NAME']).strip()
                                # 处理人数（人）列，可能包含逗号分隔符
                                pop_str = str(row['人数（人）']).replace(',', '').strip()
                                try:
                                    population = float(pop_str) if pop_str else 0.0
                                    if name and population > 0:
                                        population_data[name] = population
                                except ValueError:
                                    continue
                        print(f"[Radiation Cooling Clothing] Loaded {len(population_data)} population records")
                    except Exception as e:
                        print(f"[Radiation Cooling Clothing] Warning: Failed to load population data: {e}")
                else:
                    print(f"[Radiation Cooling Clothing] Warning: Population CSV file not found at {population_csv_path}")
                
                # 生成data.csv文件
                data_csv_rows = []
                HOURS_PER_YEAR = 8760.0
                
                for epw_result in epw_results:
                    epw_name = epw_result["epw_file"]
                    cooling_power_wh = epw_result.get("cooling_power_wh", 0.0)
                    average_power = float(cooling_power_wh) / HOURS_PER_YEAR if HOURS_PER_YEAR > 0 else 0.0
                    
                    epw_stem = PathLib(epw_name).stem
                    
                    if weather_group == "china":
                        epw_to_name = {
                            'anhui province': '安徽省', 'beijing': '北京市', 'chongqing': '重庆市',
                            'fujian': '福建省', 'gansu': '甘肃省', 'guangdong province': '广东省',
                            'guangxi zhuang autonomous region': '广西壮族自治区', 'guizhou province': '贵州省',
                            'hainan province': '海南省', 'hebei province': '河北省', 'heilongjiang province': '黑龙江省',
                            'henan province': '河南省', 'hongkong': '香港特别行政区', 'hubei province': '湖北省',
                            'hunan province': '湖南省', 'inner mongolia autonomous region': '内蒙古自治区',
                            'jiangsu': '江苏省', 'jiangxi province': '江西省', 'jilin province': '吉林省',
                            'liaoning': '辽宁省', 'macao': '澳门特别行政区', 'ningxia hui autonomous region': '宁夏回族自治区',
                            'qinghai province': '青海省', 'shaanxi province': '陕西省', 'shandong province': '山东省',
                            'shanghai': '上海市', 'shanxi province': '山西省', 'shenzhen': '深圳市',
                            'sichuan': '四川省', 'taiwan province': '台湾省', 'tianjin': '天津市',
                            'tibet autonomous region': '西藏自治区', 'xinjiang uyghur autonomous region': '新疆维吾尔自治区',
                            'yunnan province': '云南省', 'zhejiang province': '浙江省',
                        }
                        
                        epw_key = epw_stem.lower().strip()
                        province_name = epw_to_name.get(epw_key, None)
                        
                        if province_name:
                            # 获取人口数据
                            population = population_data.get(province_name, 0.0)
                            
                            # 计算制冷功量：AveragePower × 衣物面积/人 × 人口数
                            cooling_power_w = average_power * clothing_area_per_person * population
                            
                            data_csv_rows.append({
                                "NAME": province_name,
                                "FQ": epw_stem,
                                "Cooling": cooling_power_wh,
                                "AveragePower": average_power,
                                "人数（人）": population,
                                "CoolingPower": cooling_power_w,  # 制冷功量（W）
                            })
                            print(f"[Radiation Cooling Clothing] Added: {province_name}, avg={average_power:.4f} W/m², pop={population:.0f}, cooling_power={cooling_power_w:.2f} W")
                    else:
                        # 世界模式暂不支持人口数据
                        data_csv_rows.append({
                            "FQ": epw_stem,
                            "Cooling": cooling_power_wh,
                            "AveragePower": average_power,
                        })
                
                # 生成data.csv
                if data_csv_rows:
                    data_csv_path = work_dir / "data.csv"
                    data_df = pd.DataFrame(data_csv_rows)
                    data_df.to_csv(data_csv_path, index=False, encoding='utf-8-sig')
                    
                    artifacts.append({
                        "kind": "csv",
                        "name": "data.csv",
                        "url": f"/api/jobs/{job_id}/files/work/data.csv",
                    })
                    
                    # 基于制冷功量生成中国地图（仅中国模式）
                    if weather_group == "china":
                        china_map_png = work_dir / "china_cooling_power_map.png"
                        try:
                            # 使用CoolingPower列绘制地图
                            ok = _generate_china_power_map_from_csv(data_csv_path, china_map_png, value_column="CoolingPower")
                        except Exception:
                            traceback.print_exc()
                            ok = False
                        
                        if ok and china_map_png.exists():
                            artifacts.append({
                                "kind": "image",
                                "name": china_map_png.name,
                                "url": f"/api/jobs/{job_id}/files/work/{china_map_png.name}",
                            })
                
                payload = JobResult(
                    job_id=job_id,
                    generated_at=datetime.utcnow(),
                    summary={
                        "weather_group": weather_group,
                        "phases_count": len(phases),
                        "transition_mode": transition_mode,
                        "enable_latent_heat": enable_latent_heat,
                        "wet_fraction": wet_fraction,
                        "clothing_area_per_person": clothing_area_per_person,
                    },
                    plots=[],
                    artifacts=artifacts,
                ).model_dump(mode="json")
                
                out = job_result_path(job_id)
                out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")
                
            except Exception as e:
                err = traceback.format_exc()
                raise RuntimeError(f"Radiation cooling clothing calculation failed: {err}") from e

        elif job_type == "material_env_temp_cloud":
            # 异步材料-环境温度云图：复用 WebAPI 的计算函数
            from webapi.services.material_env_temp_cloud import compute_material_env_temp_cloud

            with SessionLocal() as db:
                job = db.get(Job, job_id)
                user_id = getattr(job, "user_id", None)

            if user_id is None:
                raise RuntimeError("material_env_temp_cloud job missing user_id")

            # params 来自前端 NewJobPage 或其它调用方，字段名与同步工具保持一致
            t_env_min_c = float(params.get("t_env_min_c", -20.0))
            t_env_max_c = float(params.get("t_env_max_c", 60.0))
            h_c_wm2k = float(params.get("h_c_wm2k", 5.0))
            enable_natural_convection = bool(params.get("enable_natural_convection", False))
            enable_latent_heat = bool(params.get("enable_latent_heat", False))
            relative_humidity = params.get("relative_humidity")
            wet_fraction = float(params.get("wet_fraction", 1.0) or 1.0)
            phase_temp_c = params.get("phase_temp_c")
            phase_power_wm2 = float(params.get("phase_power_wm2", 0.0) or 0.0)
            phase_half_width_c = float(params.get("phase_half_width_c", 0.0) or 0.0)

            cloud = compute_material_env_temp_cloud(
                user_id=int(user_id),
                t_env_min_c=t_env_min_c,
                t_env_max_c=t_env_max_c,
                h_c_wm2k=h_c_wm2k,
                enable_natural_convection=enable_natural_convection,
                enable_latent_heat=enable_latent_heat,
                relative_humidity=relative_humidity,
                wet_fraction=wet_fraction,
                phase_temp_c=phase_temp_c,
                phase_power_wm2=phase_power_wm2,
                phase_half_width_c=phase_half_width_c,
            )

            payload = JobResult(
                job_id=job_id,
                generated_at=datetime.utcnow(),
                summary={
                    "kind": "material_env_temp_cloud",
                    "cloud": cloud,
                },
                plots=[],
                artifacts=[],
            ).model_dump(mode="json")

            out = job_result_path(job_id)
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")

        else:
            file_paths = _resolve_common_paths(job, params)

            angle_steps = int(params.get("angle_steps", 2000))
            enable_natural_convection = bool(params.get("enable_natural_convection", False))
            phase_temp_c = params.get("phase_temp_c")
            phase_power_wm2 = float(params.get("phase_power_wm2", 0.0) or 0.0)
            phase_half_width_c = float(params.get("phase_half_width_c", 0.0) or 0.0)
            enable_latent_heat = bool(params.get("enable_latent_heat", False))
            relative_humidity = params.get("relative_humidity")
            wet_fraction = params.get("wet_fraction", 1.0)

            # Record irradiance used for this run (from user config).
            s_solar_wm2 = None
            t_a1_c = None
            try:
                _core_config = importlib.import_module("core.config")
                load_config = getattr(_core_config, "load_config")
                cfg = load_config(file_paths["config"])
                s_solar_wm2 = float(cfg.get("S_solar"))
                t_a1_c = float(cfg.get("T_a1"))
            except Exception:
                s_solar_wm2 = None
                t_a1_c = None

            if job_type == "cooling":
                result = main_cooling_gui(
                    file_paths,
                    angle_steps=angle_steps,
                    skip_dialog=True,
                    enable_natural_convection=enable_natural_convection,
                    phase_temp_c=phase_temp_c,
                    phase_power_wm2=phase_power_wm2,
                    phase_half_width_c=phase_half_width_c,
                    enable_latent_heat=enable_latent_heat,
                    relative_humidity=float(relative_humidity) if relative_humidity is not None else None,
                    wet_fraction=float(wet_fraction) if wet_fraction is not None else 1.0,
                    debug=False,
                )

                plot = _build_line_plot_payload(
                    title="Cooling power vs film temperature",
                    x_values=result.get("T_film"),
                    series_values=result.get("results"),
                    hc_vals=result.get("HC_VALUES"),
                )

                summary = {
                    "Power_0": result.get("Power_0"),
                    "R_sol": result.get("R_sol"),  # Absorptance
                    "R_sol1": result.get("R_sol1"),  # Absorptance
                    "R_sol_reflectance_only": result.get("R_sol_reflectance_only"),
                    "R_sol1_reflectance_only": result.get("R_sol1_reflectance_only"),
                    "T_sol": result.get("T_sol"),
                    "T_sol1": result.get("T_sol1"),
                    "avg_emissivity": result.get("avg_emissivity"),
                    "S_solar_wm2": s_solar_wm2,
                    "T_a1_c": t_a1_c,
                    "R_sol_desc_zh": "太阳光吸收率",
                    "R_sol_desc_en": "Solar spectral absorptance",
                    "R_sol1_desc_zh": "可见光吸收率",
                    "R_sol1_desc_en": "Visible spectral absorptance",
                    "R_sol_reflectance_only_desc_zh": "太阳光谱反射率",
                    "R_sol_reflectance_only_desc_en": "Solar spectral reflectance",
                    "R_sol1_reflectance_only_desc_zh": "可见光谱反射率",
                    "R_sol1_reflectance_only_desc_en": "Visible spectral reflectance",
                    "T_sol_desc_zh": "太阳光谱透过率",
                    "T_sol_desc_en": "Solar spectral transmittance",
                    "T_sol1_desc_zh": "可见光谱透过率",
                    "T_sol1_desc_en": "Visible spectral transmittance",
                    "avg_emissivity_desc_zh": "加权发射率",
                    "avg_emissivity_desc_en": "Weighted emissivity",
                    "enable_natural_convection": result.get("enable_natural_convection"),
                    "phase_temp_c": result.get("phase_temp_c"),
                    "phase_power_wm2": result.get("phase_power_wm2"),
                    "phase_half_width_c": result.get("phase_half_width_c"),
                    "enable_latent_heat": result.get("enable_latent_heat"),
                    "relative_humidity": result.get("relative_humidity"),
                    "wet_fraction": result.get("wet_fraction"),
                    "atm_preset": params.get("atm_preset") or "clear_sky.dll",
                    "reflectance_preset": params.get("reflectance_preset") or "use-高温.txt",
                    "emissivity_preset": params.get("emissivity_preset") or "高温发射率.txt",
                }

            else:  # heating
                result = main_heating_gui(
                    file_paths,
                    angle_steps=angle_steps,
                    skip_dialog=True,
                    enable_natural_convection=enable_natural_convection,
                    phase_temp_c=phase_temp_c,
                    phase_power_wm2=phase_power_wm2,
                    phase_half_width_c=phase_half_width_c,
                    debug=False,
                )

                plot = _build_line_plot_payload(
                    title="Heating power vs film temperature",
                    x_values=result.get("T_film"),
                    series_values=result.get("results"),
                    hc_vals=result.get("HC_VALUES"),
                )

                summary = {
                    "Power_0": result.get("Power_0"),
                    "R_sol": result.get("R_sol"),  # Absorptance
                    "R_sol1": result.get("R_sol1"),  # Absorptance
                    "R_sol_reflectance_only": result.get("R_sol_reflectance_only"),
                    "R_sol1_reflectance_only": result.get("R_sol1_reflectance_only"),
                    "T_sol": result.get("T_sol"),
                    "T_sol1": result.get("T_sol1"),
                    "avg_emissivity": result.get("avg_emissivity"),
                    "S_solar_wm2": s_solar_wm2,
                    "T_a1_c": t_a1_c,
                    "R_sol_desc_zh": "太阳光吸收率",
                    "R_sol_desc_en": "Solar spectral absorptance",
                    "R_sol1_desc_zh": "可见光吸收率",
                    "R_sol1_desc_en": "Visible spectral absorptance",
                    "R_sol_reflectance_only_desc_zh": "太阳光谱反射率",
                    "R_sol_reflectance_only_desc_en": "Solar spectral reflectance",
                    "R_sol1_reflectance_only_desc_zh": "可见光谱反射率",
                    "R_sol1_reflectance_only_desc_en": "Visible spectral reflectance",
                    "T_sol_desc_zh": "太阳光谱透过率",
                    "T_sol_desc_en": "Solar spectral transmittance",
                    "T_sol1_desc_zh": "可见光谱透过率",
                    "T_sol1_desc_en": "Visible spectral transmittance",
                    "avg_emissivity_desc_zh": "加权发射率",
                    "avg_emissivity_desc_en": "Weighted emissivity",
                    "enable_natural_convection": result.get("enable_natural_convection"),
                    "phase_temp_c": result.get("phase_temp_c"),
                    "phase_power_wm2": result.get("phase_power_wm2"),
                    "phase_half_width_c": result.get("phase_half_width_c"),
                    "atm_preset": params.get("atm_preset") or "clear_sky.dll",
                    "reflectance_preset": params.get("reflectance_preset") or "use-高温.txt",
                    "emissivity_preset": params.get("emissivity_preset") or "高温发射率.txt",
                }

            payload = JobResult(
                job_id=job_id,
                generated_at=datetime.utcnow(),
                summary=summary,
                plots=[plot],
                artifacts=[],
            ).model_dump(mode="json")

            out = job_result_path(job_id)
            out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default), encoding="utf-8")

        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job:
                job_type = job.type
                job.status = "succeeded"
                job.updated_at = datetime.utcnow()
                job.result_path = str(job_result_path(job_id))
                job.error_message = None
                db.commit()
                
                # 如果是节能地图任务，任务完成后启动下一个排队的任务
                if job_type == "compare_materials":
                    try:
                        from webapi.services.energy_map_queue import start_next_queued_energy_map_job
                        start_next_queued_energy_map_job()
                    except Exception:
                        # 如果启动下一个任务失败，不影响当前任务的完成状态
                        pass

    except Exception:
        err = traceback.format_exc()
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job:
                job_type = job.type
                job.status = "failed"
                job.updated_at = datetime.utcnow()
                job.error_message = err[-8000:]
                db.commit()
                
                # 如果是节能地图任务，任务失败后也启动下一个排队的任务
                if job_type == "compare_materials":
                    try:
                        from webapi.services.energy_map_queue import start_next_queued_energy_map_job
                        start_next_queued_energy_map_job()
                    except Exception:
                        # 如果启动下一个任务失败，不影响当前任务的失败状态
                        pass