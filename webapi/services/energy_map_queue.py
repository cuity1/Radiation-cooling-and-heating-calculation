from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_

from ..db.models import Job
from ..db.session import SessionLocal
from ..services.job_runner import run_job_inline
from ..services.queue_service import enqueue_job
from ..settings import settings


def has_running_energy_map_job() -> bool:
    """检查是否有正在运行的节能地图任务（status为'started'）"""
    with SessionLocal() as db:
        running_job = db.query(Job).filter(
            and_(
                Job.type == "compare_materials",
                Job.status == "started"
            )
        ).first()
        return running_job is not None


def get_next_queued_energy_map_job() -> str | None:
    """获取下一个排队的节能地图任务ID（按创建时间排序）"""
    with SessionLocal() as db:
        queued_job = db.query(Job).filter(
            and_(
                Job.type == "compare_materials",
                Job.status == "queued"
            )
        ).order_by(Job.created_at.asc()).first()
        return queued_job.id if queued_job else None


def start_next_queued_energy_map_job() -> None:
    """启动下一个排队的节能地图任务（如果有）"""
    # 检查是否有正在运行的任务
    if has_running_energy_map_job():
        return
    
    # 获取下一个排队的任务ID
    next_job_id = get_next_queued_energy_map_job()
    if not next_job_id:
        return
    
    # 启动任务
    if not settings.rq_is_async:
        # 内联模式：直接运行
        run_job_inline(next_job_id)
    else:
        # 异步模式：加入队列
        try:
            enqueue_job(next_job_id)
        except Exception as e:
            # 如果入队失败，更新任务状态为失败
            with SessionLocal() as db:
                job = db.get(Job, next_job_id)
                if job:
                    job.status = "failed"
                    job.updated_at = datetime.now(timezone.utc)
                    job.error_message = f"enqueue_failed: {type(e).__name__}: {e}"
                    db.commit()
