import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import or_

logger = logging.getLogger(__name__)

from ..db.models import Job, User
from ..db.session import SessionLocal
from ..schemas import CreateJobRequest, CreateJobResponse, JobDetail, JobResult, JobStats, JobSummary
from ..dependencies.auth import require_user
from ..services.inputs_resolver import resolve_input_paths
from ..services.job_runner import run_job_inline
from ..services.queue_service import enqueue_job
from ..services.storage_service import job_dir
from ..settings import settings

router = APIRouter(tags=["jobs"], dependencies=[Depends(require_user)])


def _get_task_counter() -> int:
    counter_path = settings.data_dir / "task_counter.txt"
    if counter_path.exists():
        try:
            return int(counter_path.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            return 3704
    return 3704


def _increment_task_counter() -> int:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    counter_path = settings.data_dir / "task_counter.txt"
    counter = _get_task_counter() + 1
    counter_path.write_text(str(counter), encoding="utf-8")
    return counter


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _job_to_summary(job: Job) -> JobSummary:
    # 兼容旧数据：将 'power_map' 映射到 'energy_map'
    job_type = job.type
    if job_type == "power_map":
        job_type = "energy_map"

    return JobSummary(
        id=job.id,
        type=job_type,  # type: ignore[arg-type]
        status=job.status,  # type: ignore[arg-type]
        remark=job.remark,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _job_to_detail(job: Job) -> JobDetail:
    # 兼容旧数据：将 'power_map' 映射到 'energy_map'
    job_type = job.type
    if job_type == "power_map":
        job_type = "energy_map"

    result_ready = bool(job.result_path and Path(job.result_path).exists())
    return JobDetail(
        id=job.id,
        type=job_type,  # type: ignore[arg-type]
        status=job.status,  # type: ignore[arg-type]
        remark=job.remark,
        created_at=job.created_at,
        updated_at=job.updated_at,
        params=job.params or {},
        result_ready=result_ready,
        error_message=job.error_message,
        user_id=job.user_id,
    )


@router.post("/jobs", response_model=CreateJobResponse)
def create_job(req: CreateJobRequest, current_user: User = Depends(require_user)) -> CreateJobResponse:
    # Increment persistent task counter
    _increment_task_counter()
    # Normal users are not allowed to submit in_situ_simulation jobs.
    # Note: both 'pro' and 'permanent_pro' are allowed for in_situ_simulation.
    if current_user.tier == "normal" and req.type == "in_situ_simulation":
        raise HTTPException(status_code=403, detail="job_type_forbidden_for_normal_users")

    job_id = str(uuid.uuid4())
    now = _now_utc()

    # Snapshot resolved input paths into params to make the job reproducible and
    # prevent "active inputs" changes from affecting already-submitted jobs.
    params = dict(req.params or {})
    try:
        require_material = req.type in {"cooling", "heating", "in_situ_simulation"}
        file_paths = resolve_input_paths(require_material=require_material, user_id=current_user.id)
        params["_file_paths"] = file_paths
    except Exception:
        # Best-effort only: if resolution fails here, worker will raise a clear error later.
        pass

    with SessionLocal() as db:
        job = Job(
            id=job_id,
            type=req.type,
            status="queued",
            user_id=current_user.id,
            created_at=now,
            updated_at=now,
            params=params,
            result_path=None,
            error_message=None,
            remark=req.remark or None,
        )
        db.add(job)
        db.commit()

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


@router.get("/jobs", response_model=list[JobSummary])
def list_jobs(current_user: User = Depends(require_user)) -> list[JobSummary]:
    with SessionLocal() as db:
        q = db.query(Job)
        if current_user.role != "admin":
            # Include current user's jobs and shared 'All' user jobs
            all_user = db.query(User).filter(User.username == "All").first()
            all_user_id = all_user.id if all_user else None
            filters = [Job.user_id == current_user.id]
            if all_user_id is not None:
                filters.append(Job.user_id == all_user_id)
            # Also optionally include legacy jobs without user_id
            q = q.filter(or_(Job.user_id.is_(None), *filters))
        rows = q.order_by(Job.created_at.desc()).limit(200).all()
        return [_job_to_summary(j) for j in rows]


@router.get("/jobs/stats", response_model=JobStats)
def get_job_stats(current_user: User = Depends(require_user)) -> JobStats:
    total_jobs = _get_task_counter()

    with SessionLocal() as db:
        today_start = datetime.now(timezone(timedelta(hours=8))).replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        today_count = (
            db.query(Job)
            .filter(Job.created_at >= today_start, Job.created_at < today_end)
            .count()
        )

    return JobStats(total_jobs=total_jobs, today_jobs=today_count)


@router.get("/jobs/{job_id}", response_model=JobDetail)
def get_job(job_id: str, current_user: User = Depends(require_user)) -> JobDetail:
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
        return _job_to_detail(job)


@router.get("/jobs/{job_id}/result", response_model=JobResult)
def get_job_result(job_id: str, current_user: User = Depends(require_user)) -> JobResult:
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

    if not job.result_path:
        raise HTTPException(status_code=409, detail="result not ready")

    p = Path(job.result_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="result file missing")

    data = json.loads(p.read_text(encoding="utf-8"))
    return JobResult(**data)


@router.get("/jobs/{job_id}/files/{file_path:path}")
def get_job_file(job_id: str, file_path: str, current_user: User = Depends(require_user)):
    """获取任务结果文件"""
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
    
    # 避免前端/浏览器缓存导致同名文件看起来不更新
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@router.get("/jobs/{job_id}/input-files/{file_key}")
def get_job_input_file(job_id: str, file_key: str, current_user: User = Depends(require_user)):
    """下载任务使用的输入文件"""
    # 权限检查
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

    # 获取 _file_paths
    file_paths = job.params.get("_file_paths", {})
    if file_key not in file_paths:
        raise HTTPException(status_code=404, detail=f"file key '{file_key}' not found in job params")

    file_path_str = file_paths[file_key]
    p = Path(file_path_str)

    logger.info(f"Looking for input file: key={file_key}, path={file_path_str}, is_absolute={p.is_absolute()}")

    # 允许的根目录列表
    allowed_roots = [
        settings.data_dir,
        settings.uploads_dir,
        Path(__file__).resolve().parents[2],  # 项目根目录
    ]

    file_full_path = None

    # 如果是绝对路径，直接使用
    if p.is_absolute():
        logger.info(f"Checking absolute path: {p}, exists={p.exists()}, is_file={p.is_file()}")
        if p.exists() and p.is_file():
            file_full_path = p
    else:
        # 相对路径：尝试在多个基础目录中查找
        base_dirs = [
            settings.data_dir,
            settings.data_dir / "user_configs",
            settings.uploads_dir / "processed" / "reflectance",
            settings.uploads_dir / "processed" / "emissivity",
            settings.uploads_dir / "processed" / "reflect_plus_transmittance",
            settings.uploads_dir / "atm_presets",
            Path(__file__).resolve().parents[2] / "default",
            Path(__file__).resolve().parents[2] / "Radiation-cooling-and-heating-calculation" / "default",
        ]
        for base_dir in base_dirs:
            candidate = base_dir / file_path_str
            logger.info(f"Checking relative path: {candidate}, exists={candidate.exists()}")
            if candidate.exists() and candidate.is_file():
                file_full_path = candidate
                logger.info(f"Found file at: {file_full_path}")
                break

    if file_full_path is None:
        raise HTTPException(status_code=404, detail=f"input file not found: {file_path_str}")

    # 安全检查：确保文件在允许的目录内
    allowed = False
    resolved_path = file_full_path.resolve()
    for root in allowed_roots:
        try:
            resolved_path.relative_to(root.resolve())
            allowed = True
            break
        except ValueError:
            continue

    if not allowed:
        raise HTTPException(status_code=403, detail="Access denied: file outside allowed directories")

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
    elif suffix == ".txt":
        media_type = "text/plain; charset=utf-8"
    elif suffix == ".dll":
        media_type = "application/x-msdownload"
    elif suffix == ".ini":
        media_type = "text/plain; charset=utf-8"

    resp = FileResponse(
        path=str(file_full_path),
        filename=file_full_path.name,
        media_type=media_type,
    )

    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp
