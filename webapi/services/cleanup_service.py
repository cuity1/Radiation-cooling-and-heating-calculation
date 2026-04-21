from __future__ import annotations

import shutil
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..db.models import Job, User
from ..db.session import SessionLocal
from ..settings import settings

logger = logging.getLogger(__name__)

def cleanup_old_jobs(days: int = 180):
    """
    删除除用户 'All' 以外的所有距今指定天数（默认180天）之前的计算任务数据。
    同时清理数据库记录和磁盘上的结果文件。
    """
    now = datetime.now(timezone.utc)
    cutoff_date = now - timedelta(days=days)
    
    logger.info(f"Starting scheduled cleanup: jobs older than {days} days (before {cutoff_date})")
    
    with SessionLocal() as db:
        # 1. 找到用户 'All' 的 ID
        all_user = db.query(User).filter(User.username == "All").first()
        all_user_id = all_user.id if all_user else None
        
        # 2. 查询符合条件的任务：
        # - 创建时间早于截止日期
        # - 用户 ID 不是 'All' 的 ID (如果 'All' 用户不存在则清理所有超期任务)
        query = db.query(Job).filter(Job.created_at < cutoff_date)
        if all_user_id is not None:
            query = query.filter(Job.user_id != all_user_id)
            
        old_jobs = query.all()
        count = len(old_jobs)
        
        if count == 0:
            logger.info("No expired jobs found for cleanup.")
            return

        logger.info(f"Found {count} expired jobs to delete.")
        
        for job in old_jobs:
            # 删除磁盘上的结果文件夹 (settings.jobs_dir / job_id)
            job_path = settings.jobs_dir / job.id
            if job_path.exists() and job_path.is_dir():
                try:
                    shutil.rmtree(job_path)
                    logger.debug(f"Deleted disk data for job {job.id}")
                except Exception as e:
                    logger.error(f"Failed to delete disk data for job {job.id}: {e}")
            
            # 从数据库删除
            db.delete(job)
            
        try:
            db.commit()
            logger.info(f"Successfully cleaned up {count} jobs from database and disk.")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to commit database cleanup: {e}")
