from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..db.models import User
from ..dependencies.auth import require_user
from ..services.tool_service import (
    compute_angular_power,
    compute_emissivity_solar_cloud,
    compute_power_components,
    compute_solar_efficiency,
    compute_wind_cloud,
)
from ..services.material_env_temp_cloud import compute_material_env_temp_cloud
from ..services.modtran_ltn import LtnParams
from ..services.modtran_wrapper import ModtranRunner, summarize_run

router = APIRouter(tags=["tools"], dependencies=[Depends(require_user)])

modtran_runner = ModtranRunner()


class WindCloudRequest(BaseModel):
    wind_min: float = Field(0.0, description="Wind speed min (m/s)")
    wind_max: float = Field(5.0, description="Wind speed max (m/s)")
    wind_points: int = Field(100, description="Sampling rate along wind axis (max 200)")

    emissivity_min: float = Field(0.0, description="Atmospheric emissivity min")
    emissivity_max: float = Field(1.0, description="Atmospheric emissivity max")
    emissivity_points: int = Field(100, description="Sampling rate along emissivity axis (max 200)")

    s_solar: float | None = Field(None, description="Override S_solar (W/m^2). If null, use config.ini")


@router.post("/tools/wind-cloud")
def wind_cloud(req: WindCloudRequest, current_user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        return compute_wind_cloud(
            user_id=current_user.id,
            wind_min=req.wind_min,
            wind_max=req.wind_max,
            wind_points=req.wind_points,
            emissivity_min=req.emissivity_min,
            emissivity_max=req.emissivity_max,
            emissivity_points=req.emissivity_points,
            s_solar=req.s_solar,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"wind_cloud_failed: {type(e).__name__}: {e}")


class SolarEfficiencyRequest(BaseModel):
    angle_steps: int = Field(2000, description="Angular integration steps (kept for desktop parity)")

    # Sampling rates (grid resolution)
    t_a_points: int = Field(100, description="Sampling rate along T_a axis (max 200)")
    s_solar_points: int = Field(100, description="Sampling rate along S_solar axis (max 200)")

    # Grid ranges
    t_a_min: float = Field(-100.0, description="T_a min (°C)")
    t_a_max: float = Field(100.0, description="T_a max (°C)")
    s_solar_min: float = Field(0.0, description="S_solar min (W/m^2)")
    s_solar_max: float = Field(1200.0, description="S_solar max (W/m^2)")


@router.post("/tools/solar-efficiency")
def solar_efficiency(req: SolarEfficiencyRequest, current_user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        return compute_solar_efficiency(
            user_id=current_user.id,
            angle_steps=req.angle_steps,
            t_a_points=req.t_a_points,
            s_solar_points=req.s_solar_points,
            t_a_min=req.t_a_min,
            t_a_max=req.t_a_max,
            s_solar_min=req.s_solar_min,
            s_solar_max=req.s_solar_max,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"solar_efficiency_failed: {type(e).__name__}: {e}")


class EmissivitySolarCloudRequest(BaseModel):
    n_emissivity: int = Field(100, description="Emissivity sampling rate (0..1), max 200")
    n_solar: int = Field(100, description="Solar sampling rate (0..solar_max), max 200")
    solar_max: float = Field(1000.0, description="Max solar irradiance (W/m^2)")


@router.post("/tools/emissivity-solar")
def emissivity_solar_cloud(req: EmissivitySolarCloudRequest, current_user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        return compute_emissivity_solar_cloud(
            user_id=current_user.id,
            n_emissivity=req.n_emissivity,
            n_solar=req.n_solar,
            solar_max=req.solar_max,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"emissivity_solar_cloud_failed: {type(e).__name__}: {e}")


class PowerComponentsRequest(BaseModel):
    angle_steps: int = Field(2000, description="Angular integration steps")
    h_cond_wm2k: float = Field(5.0, description="Equivalent conduction coefficient (W/m^2/K)")
    enable_natural_convection: bool = Field(False, description="Enable natural convection")

    phase_temp_c: float | None = Field(None, description="Phase-change temperature (°C)")
    phase_power_wm2: float = Field(0.0, description="Phase-change power (W/m^2)")
    phase_half_width_c: float = Field(0.0, description="Phase-change half width (°C)")

    enable_latent_heat: bool = Field(False, description="Enable latent heat calculation")
    relative_humidity: float | None = Field(None, description="Relative humidity (0-100%)")
    wet_fraction: float = Field(1.0, ge=0.0, le=1.0, description="Wet surface fraction (0..1), scales latent heat")


@router.post("/tools/power-components")
def power_components(req: PowerComponentsRequest, current_user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        return compute_power_components(
            user_id=current_user.id,
            angle_steps=req.angle_steps,
            h_cond_wm2k=req.h_cond_wm2k,
            enable_natural_convection=req.enable_natural_convection,
            phase_temp_c=req.phase_temp_c,
            phase_power_wm2=req.phase_power_wm2,
            phase_half_width_c=req.phase_half_width_c,
            enable_latent_heat=req.enable_latent_heat,
            relative_humidity=req.relative_humidity,
            wet_fraction=req.wet_fraction,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"power_components_failed: {type(e).__name__}: {e}")


class AngularPowerRequest(BaseModel):
    temp_diff_c: float = Field(0.0, description="Temperature difference (°C)")
    angle_steps: int = Field(91, description="Number of angle samples (0..90 deg)")


@router.post("/tools/angular-power")
def angular_power(req: AngularPowerRequest, current_user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        return compute_angular_power(user_id=current_user.id, temp_diff_c=req.temp_diff_c, angle_steps=req.angle_steps)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"angular_power_failed: {type(e).__name__}: {e}")


class MaterialEnvTempCloudRequest(BaseModel):
    t_env_min_c: float = Field(-20.0, description="Ambient temperature min (°C)")
    t_env_max_c: float = Field(60.0, description="Ambient temperature max (°C)")
    h_c_wm2k: float = Field(5.0, description="Convection coefficient h_c (W/m²·K)")
    enable_natural_convection: bool = Field(False, description="Enable natural convection")
    enable_latent_heat: bool = Field(False, description="Enable latent heat calculation")
    relative_humidity: float | None = Field(None, description="Relative humidity (0-100% or 0-1)")
    wet_fraction: float = Field(1.0, ge=0.0, le=1.0, description="Wet surface fraction (0..1)")
    phase_temp_c: float | None = Field(None, description="Phase-change temperature (°C)")
    phase_power_wm2: float = Field(0.0, description="Phase-change power (W/m²)")
    phase_half_width_c: float = Field(0.0, description="Phase-change half width (°C)")


@router.post("/tools/material-env-temp-cloud")
def material_env_temp_cloud(
    req: MaterialEnvTempCloudRequest,
    current_user: User = Depends(require_user),
) -> dict[str, Any]:
    try:
        return compute_material_env_temp_cloud(
            user_id=current_user.id,
            t_env_min_c=req.t_env_min_c,
            t_env_max_c=req.t_env_max_c,
            h_c_wm2k=req.h_c_wm2k,
            enable_natural_convection=req.enable_natural_convection,
            enable_latent_heat=req.enable_latent_heat,
            relative_humidity=req.relative_humidity,
            wet_fraction=req.wet_fraction,
            phase_temp_c=req.phase_temp_c,
            phase_power_wm2=req.phase_power_wm2,
            phase_half_width_c=req.phase_half_width_c,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"material_env_temp_cloud_failed: {type(e).__name__}: {e}")


# ---------- MODTRAN 透过率 ----------


@router.get("/tools/modtran/templates")
def modtran_templates(current_user: User = Depends(require_user)) -> dict[str, Any]:
    return {"templates": modtran_runner.list_templates()}


@router.get("/tools/modtran/template-params")
def modtran_template_params(name: str, current_user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        data = modtran_runner.load_template_params(name)
        params: LtnParams = data["params"]
        return {
            "lines": data["lines"],
            "params": params.__dict__,
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"modtran_template_params_failed: {type(e).__name__}: {e}")


class ModtranRunRequest(BaseModel):
    template: str = Field(..., description="模板文件名，如 Anew1.ltn")
    model_type: str = Field("T", description="T/R")
    atmosphere_model: int = Field(6, ge=1, le=6)
    aerosol_model: int = Field(2, ge=0, le=5)
    observer_zenith_deg: float = 0.0
    observer_azimuth_deg: float = 30.0
    solar_zenith_deg: float = 45.0
    solar_azimuth_deg: float = 0.0
    ground_alt_km: float = 1.5
    start_cm1: float = 400.0
    end_cm1: float = 50000.0
    res_cm1: float = 5.0
    out_res_cm1: float = 5.0
    export_excel: bool = True


@router.post("/tools/modtran/run")
def modtran_run(req: ModtranRunRequest, current_user: User = Depends(require_user)) -> dict[str, Any]:
    try:
        params = LtnParams(
            model_type=req.model_type.upper(),
            atmosphere_model=int(req.atmosphere_model),
            aerosol_model=int(req.aerosol_model),
            observer_zenith_deg=float(req.observer_zenith_deg),
            observer_azimuth_deg=float(req.observer_azimuth_deg),
            solar_zenith_deg=float(req.solar_zenith_deg),
            solar_azimuth_deg=float(req.solar_azimuth_deg),
            ground_alt_km=float(req.ground_alt_km),
            start_cm1=float(req.start_cm1),
            end_cm1=float(req.end_cm1),
            res_cm1=float(req.res_cm1),
            out_res_cm1=float(req.out_res_cm1),
        )

        if params.start_cm1 <= 0 or params.end_cm1 <= 0 or params.start_cm1 >= params.end_cm1:
            raise ValueError("起止波数必须 >0 且 start < end")
        if params.res_cm1 <= 0 or params.out_res_cm1 <= 0:
            raise ValueError("分辨率必须 > 0")
        if params.model_type not in {"T", "R"}:
            raise ValueError("模型类型仅支持 T 或 R")

        run = modtran_runner.run_with_params(
            template_name=req.template,
            params=params,
            user_id=current_user.id,
            export_excel=req.export_excel,
        )
        return summarize_run(run)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"modtran_run_failed: {type(e).__name__}: {e}")


@router.get("/tools/modtran/download/{run_id}/{filename}")
def modtran_download(run_id: str, filename: str, current_user: User = Depends(require_user)):
    # 路径安全校验：仅允许访问当前用户 run 目录下的文件
    base = modtran_runner.runs_root / str(current_user.id) / run_id
    target = (base / filename).resolve()
    try:
        base_resolved = base.resolve()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="run_id not found")

    if not str(target).startswith(str(base_resolved)):
        raise HTTPException(status_code=403, detail="forbidden")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")
    return FileResponse(target)


# ---------- Koppen Map Preview (GEE raster remap, synchronous) ----------


class KoppenMapPreviewRequest(BaseModel):
    csv_content: str = Field(
        ...,
        description="CSV raw text content; columns: FQ (Köppen zone code), results (numeric value)",
    )
    colormap: str = Field("Blues", description="Colormap key, matching ColormapSelector options")
    title: str = Field("", description="Map title, empty = no title")
    colorbar_label: str = Field("", description="Colorbar label, empty = default label")
    z_min: float | None = Field(None, description="Color range min, None = auto from data")
    z_max: float | None = Field(None, description="Color range max, None = auto from data")
    add_grid: bool = Field(False, description="Overlay EPSG:4326 lat/lon grid on the map")


@router.post("/tools/koppen-map-preview")
def koppen_map_preview(
    req: KoppenMapPreviewRequest,
    current_user: User = Depends(require_user),
):
    """Synchronous Köppen map preview via Google Earth Engine.

    - Returns an inline base64 data URL (no polling required).
    - Results are cached locally by a SHA-256 hash of all input params;
      identical subsequent requests are served from disk instantly.
    - For full-resolution export use GET /tools/koppen-map-export/{cache_key}.
    """
    from ..services.koppen_map_service import KoppenMapParams, get_koppen_preview

    params = KoppenMapParams(
        csv_content=req.csv_content,
        colormap=req.colormap,
        title=req.title,
        colorbar_label=req.colorbar_label,
        z_min=req.z_min,
        z_max=req.z_max,
        add_grid=req.add_grid,
    )
    result = get_koppen_preview(params)
    return result.model_dump(mode="json")


@router.get("/tools/koppen-map-export/{cache_key}")
def koppen_map_export(
    cache_key: str,
    current_user: User = Depends(require_user),
):
    """Return cached full-resolution PNG for a previously generated preview."""
    from ..services.koppen_map_service import get_export_png_path

    path = get_export_png_path(cache_key)
    if path is None:
        raise HTTPException(status_code=404, detail="export not found or expired")
    return FileResponse(
        path,
        media_type="image/png",
        headers={"Cache-Control": "no-store"},
        filename=f"koppen_map_{cache_key}.png",
    )
