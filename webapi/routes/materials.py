from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from ..db.models import Job, User
from ..db.session import SessionLocal
from ..schemas import CreateJobRequest, CreateJobResponse
from ..services.queue_service import enqueue_job
from ..services.job_runner import run_job_inline
from ..dependencies.auth import require_user
from ..services.storage_service import job_dir
from ..services.energy_map_queue import has_running_energy_map_job, start_next_queued_energy_map_job
from ..settings import settings

router = APIRouter(tags=["materials"], dependencies=[Depends(require_user)])


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@router.post("/materials/compare", response_model=CreateJobResponse)
def create_material_comparison_job(req: CreateJobRequest, current_user: User = Depends(require_user)) -> CreateJobResponse:
    """创建材料对比分析任务（使用EnergyPlus）
    
    参数：
    - type: 必须是 "compare_materials"
    - params: 包含以下字段：
        - weather_group: "china"、"world" 或 "world_weather2025"
        - scenarios: 场景列表（至少3个），每个场景包含 name, desc, wall, roof
        - idf_template_dir: IDF模板目录路径（可选，默认使用exe目录）
        - energyplus_exe: EnergyPlus可执行文件路径（可选，默认：D:\\academic_tool\\EnergyPlusV9-1-0\\energyplus.exe）
        
    注意：已移除以下旧参数（不再使用SimulationEngine）：
        - preset_mode, warmup_days, timestep, sampling_mode, reuse_engine, 
          use_multiprocessing, sky_temp_weights
    """
    if req.type != "compare_materials":
        raise HTTPException(status_code=400, detail="Job type must be 'compare_materials'")
    if current_user.tier == "normal":
        # Map visualization / materials comparison is Pro-only
        # Note: both 'pro' and 'permanent_pro' are allowed.
        # Check against explicitly 'normal' to allow all pro tiers.
        raise HTTPException(status_code=403, detail="job_type_forbidden_for_normal_users")
    
    job_id = str(uuid.uuid4())
    now = _now_utc()

    # 打印收到的参数，核实 enable_latent_heat 是否存在
    print(f"\n[API DEBUG] 创建材料对比任务: {job_id}")
    print(f"[API DEBUG] 原始参数: {req.params}")

    with SessionLocal() as db:
        job = Job(
            id=job_id,
            type=req.type,
            status="queued",
            user_id=current_user.id,
            created_at=now,
            updated_at=now,
            params=req.params,
            result_path=None,
            error_message=None,
        )
        db.add(job)
        db.commit()

    # 节能地图任务队列控制：检查是否有正在运行的任务
    if has_running_energy_map_job():
        # 如果有正在运行的任务，新任务保持 queued 状态，等待执行
        return CreateJobResponse(job_id=job_id)

    # 没有正在运行的任务，立即启动
    # Windows-friendly default: run inline (no RQ worker / no fork).
    if not settings.rq_is_async:
        run_job_inline(job_id)
        return CreateJobResponse(job_id=job_id)

    # Async mode: enqueue to Redis/RQ
    try:
        enqueue_job(job_id)
    except Exception as e:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job:
                job.status = "failed"
                job.updated_at = _now_utc()
                job.error_message = f"enqueue_failed: {type(e).__name__}: {e}"
                db.commit()
        raise HTTPException(status_code=500, detail=f"enqueue_failed: {type(e).__name__}: {e}")

    return CreateJobResponse(job_id=job_id)


@router.get("/materials/{job_id}/files/{file_path:path}")
def get_material_comparison_file(job_id: str, file_path: str, current_user: User = Depends(require_user)):
    """获取材料对比分析结果文件"""
    # 权限检查：仅管理员或任务所有者可访问
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        if current_user.role != "admin":
            all_user = db.query(User).filter(User.username == "All").first()
            all_user_id = all_user.id if all_user else None
            allowed_ids = {current_user.id}
            if all_user_id is not None:
                allowed_ids.add(all_user_id)
            if job.user_id not in allowed_ids and job.user_id is not None:
                raise HTTPException(status_code=404, detail="job not found")
    job_base = job_dir(job_id)
    file_full_path = job_base / file_path
    
    # 安全检查：确保文件在job目录内
    try:
        file_full_path.resolve().relative_to(job_base.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not file_full_path.exists() or not file_full_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    
    # 根据文件扩展名设置正确的 Content-Type
    media_type = "application/octet-stream"
    suffix = file_full_path.suffix.lower()
    if suffix == ".html":
        media_type = "text/html; charset=utf-8"
    elif suffix == ".css":
        media_type = "text/css; charset=utf-8"
    elif suffix == ".js":
        media_type = "application/javascript; charset=utf-8"
    elif suffix == ".json":
        media_type = "application/json; charset=utf-8"
    elif suffix == ".png":
        media_type = "image/png"
    elif suffix == ".jpg" or suffix == ".jpeg":
        media_type = "image/jpeg"
    elif suffix == ".csv":
        media_type = "text/csv; charset=utf-8"
    elif suffix == ".xlsx":
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    
    resp = FileResponse(
        path=str(file_full_path),
        filename=file_full_path.name,
        media_type=media_type,
    )

    # 避免前端/浏览器缓存导致同名图片看起来不更新
    # 由于结果文件可能在同一路径被覆盖写入（每个job内固定文件名），这里强制禁用缓存
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@router.get("/materials/climate-params")
def get_climate_params(current_user: User = Depends(require_user)):
    """下载气候参数XLSX文件"""
    # 获取项目根目录
    base_dir = Path(__file__).resolve().parents[2]
    xlsx_path = base_dir / "material_comparison_tool" / "气候参数.xlsx"

    if not xlsx_path.exists() or not xlsx_path.is_file():
        raise HTTPException(status_code=404, detail="Climate params XLSX file not found")

    return FileResponse(
        path=str(xlsx_path),
        filename="气候参数.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/materials/model-preview/{model_key}/figure")
def get_model_preview_figure(model_key: str, current_user: User = Depends(require_user)):
    """获取指定模型目录下的预览图片 figure.png。
    
    约定目录结构：
    - material_comparison_tool/model/model1/figure.png
    - material_comparison_tool/model/model2/figure.png
    - material_comparison_tool/model/model3/figure.png
    """
    # 为安全起见，仅允许有限的模型键
    allowed_models = {"model1", "model2", "model3"}
    if model_key not in allowed_models:
        raise HTTPException(status_code=404, detail="Model not found")

    base_dir = Path(__file__).resolve().parents[2]
    fig_path = base_dir / "material_comparison_tool" / "model" / model_key / "figure.png"

    if not fig_path.exists() or not fig_path.is_file():
        raise HTTPException(status_code=404, detail="figure.png not found for this model")

    resp = FileResponse(
        path=str(fig_path),
        filename="figure.png",
        media_type="image/png",
    )
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@router.get("/materials/model-preview/{model_key}/inf")
def get_model_preview_inf(model_key: str, current_user: User = Depends(require_user)):
    """获取指定模型目录下的 inf.csv 内容（供前端展示表格）。"""
    allowed_models = {"model1", "model2", "model3"}
    if model_key not in allowed_models:
        raise HTTPException(status_code=404, detail="Model not found")

    base_dir = Path(__file__).resolve().parents[2]
    csv_path = base_dir / "material_comparison_tool" / "model" / model_key / "inf.csv"

    if not csv_path.exists() or not csv_path.is_file():
        raise HTTPException(status_code=404, detail="inf.csv not found for this model")

    # 直接以文本流形式返回，前端自行解析为表格
    return FileResponse(
        path=str(csv_path),
        filename="inf.csv",
        media_type="text/csv; charset=utf-8",
    )
