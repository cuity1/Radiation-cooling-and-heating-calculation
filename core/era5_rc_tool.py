"""ERA5 radiative cooling tool helpers.

This module is a light wrapper around the implementation that originally lived
under `new_module/`.

It intentionally avoids any Qt imports so it can be called from GUI threads.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass(frozen=True)
class Era5DownloadParams:
    start_date: str  # YYYY-MM-DD
    end_date: str  # YYYY-MM-DD
    lon: float
    lat: float
    tz_offset_hours: float = 0.0


@dataclass(frozen=True)
class Era5ComputeParams:
    eps: float
    rho_solar: float
    sky_view: float = 1.0
    use_empirical_atm: int = 0  # 大气辐射模式: 0=真实ERA5 strd, 1=修正混合模式(0.3经验+0.7strd), 2=理论模式(0.8经验+0.2strd)
    enable_latent_heat: bool = False  # 是否启用蒸发潜热计算
    wet_fraction: float = 1.0  # 湿润面积比例 (0-1)，用于缩放蒸发潜热功率


def download_era5_to_dir(params: Era5DownloadParams, weather_dir: str | Path) -> tuple[Path, int | None]:
    """Download ERA5 into `weather_dir`.

    Notes:
    - `new_module.get.download_era5` always writes under CWD/weather. We keep
      behavior deterministic by temporarily changing working directory to the
      chosen folder's parent and ensuring folder name is `weather`.

    Returns:
        Path to the downloaded .nc file.
    """
    import os

    from new_module.get import LAST_CDS_LINE, area_from_point, download_era5

    weather_dir = Path(weather_dir).resolve()
    weather_dir.mkdir(parents=True, exist_ok=True)

    # Ensure `download_era5` writes into this directory by setting CWD so that
    # ./weather == weather_dir
    parent = weather_dir.parent
    old_cwd = os.getcwd()
    try:
        # Force upstream downloader to write into ./weather under a controlled CWD.
        os.chdir(str(parent))
        local_weather = Path(parent) / "weather"
        local_weather.mkdir(parents=True, exist_ok=True)

        # If user-selected folder is not literally named 'weather', keep a clean
        # separation by downloading into ./weather then moving files.
        target_is_local_weather = weather_dir.resolve() == local_weather.resolve()

        area = area_from_point(params.lon, params.lat)
        # Track which CDS line/key was used for this download.
        old_line = LAST_CDS_LINE
        line_no = download_era5(
            params.start_date,
            params.end_date,
            area,
            output_path=None,
            lon=params.lon,
            lat=params.lat,
            tz_offset_hours=params.tz_offset_hours,
        )

        # Infer output filename
        if params.start_date == params.end_date:
            name = f"era5_{params.start_date}.nc"
        else:
            name = f"era5_{params.start_date}_to_{params.end_date}.nc"

        produced = local_weather / name
        if not produced.exists():
            # If CDS returns zip or naming differs, just return the most recent nc/zip.
            cand = sorted(local_weather.glob("*.nc"), key=lambda p: p.stat().st_mtime, reverse=True)
            if not cand:
                cand = sorted(local_weather.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
            if cand:
                produced = cand[0]

        if target_is_local_weather:
            return produced, int(line_no) if line_no is not None else None

        # Move all produced ERA5 artifacts into requested folder
        weather_dir.mkdir(parents=True, exist_ok=True)
        moved_main = None
        for fp in sorted(local_weather.iterdir(), key=lambda p: p.stat().st_mtime):
            if fp.is_file():
                dest = weather_dir / fp.name
                try:
                    fp.replace(dest)
                except Exception:
                    # fallback copy+remove
                    import shutil

                    shutil.copy2(fp, dest)
                    fp.unlink(missing_ok=True)
                if moved_main is None and dest.suffix.lower() in (".nc", ".zip"):
                    moved_main = dest

        produced_final = moved_main or (weather_dir / name)
        return produced_final, int(line_no) if line_no is not None else None
    finally:
        os.chdir(old_cwd)


def merge_weather_csvs(weather_dir: str | Path, output_csv: str | Path) -> Path:
    from new_module.merge_weather_csv import merge_weather_csvs as _merge

    out = _merge(str(weather_dir), str(output_csv))
    return Path(out)


def compute_radiative_cooling_from_merged_csv(
    merged_csv: str | Path,
    *,
    out_csv: str | Path,
    params: Era5ComputeParams,
    export_figures: bool = True,
    figures_dir: Optional[str | Path] = None,
) -> pd.DataFrame:
    import os

    import new_module.radiative_cooling_from_weather_csv as rc

    merged_csv = Path(merged_csv)
    if not merged_csv.exists():
        raise FileNotFoundError(f"Merged weather CSV not found: {merged_csv}")

    # Set material params for this run
    rc.MATERIAL_PARAMS["eps"] = float(params.eps)
    rc.MATERIAL_PARAMS["rho_solar"] = float(params.rho_solar)
    rc.MATERIAL_PARAMS["sky_view"] = float(params.sky_view)

    df_raw = rc.load_weather_csv(str(merged_csv))
    df = rc.compute_cooling(
        df_raw,
        use_empirical_atm=params.use_empirical_atm,
        enable_latent_heat=params.enable_latent_heat,
        wet_fraction=params.wet_fraction,
    )

    out_csv = Path(out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(str(out_csv), index=False, encoding="utf-8-sig")

    if export_figures:
        rc.create_directories()
        out_dir = Path(figures_dir) if figures_dir else Path("figures") / "individual"
        os.makedirs(out_dir, exist_ok=True)
        rc.fig1_split(df, str(out_dir))
        rc.fig2_split(df, str(out_dir))
        rc.fig3_split(df, str(out_dir))
        rc.fig4_split(df, str(out_dir))
        rc.fig5_split(df, str(out_dir))

    return df
