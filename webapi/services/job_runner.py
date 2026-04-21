from __future__ import annotations

import importlib
import sys
import traceback
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from ..db.models import Job
from ..db.session import SessionLocal

# 默认任务超时时间（秒）
# - angle_steps=5000 的高精度计算理论上在 1-2 分钟内完成
# - 如果超过这个时间，说明可能卡住了，需要强制终止并标记失败
DEFAULT_JOB_TIMEOUT_SECONDS = int(os.environ.get("JOB_TIMEOUT_SECONDS", "10000"))


def _ensure_project_on_syspath() -> None:
    # Ensure the project root (the directory that contains core/, worker/, webapi/) is on sys.path.
    # This makes imports like `import core` / `import worker` work regardless of the uvicorn CWD.
    root = Path(__file__).resolve().parents[2]
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)


def run_job_inline(job_id: str) -> None:
    """Run a job inline inside the API process (Windows-friendly).

    This avoids RQ's default fork-based worker model (not available on Windows),
    ensuring jobs won't stay in 'queued' forever during local development.

    Implements timeout protection to prevent tasks from hanging indefinitely.
    """
    _ensure_project_on_syspath()

    try:
        mod = importlib.import_module("worker.tasks")
        run_job = getattr(mod, "run_job")
    except Exception:
        err = traceback.format_exc()
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job:
                job.status = "failed"
                job.updated_at = datetime.now(timezone.utc)
                job.error_message = err[-8000:]
                db.commit()
        return

    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if not job:
            return
        job.status = "started"
        job.updated_at = datetime.now(timezone.utc)
        db.commit()

    # Use ThreadPoolExecutor for timeout protection (Windows-compatible)
    # Note: ThreadPoolExecutor is used because:
    # 1. The job involves numpy computations which release GIL for most operations
    # 2. Creating a subprocess would require complex serialization of DB/File objects
    # 3. On Windows, signal.SIGALRM is not available
    job_done_event = threading.Event()
    job_exception = [None]  # Container to store exception from thread

    def _thread_target():
        """Target function running in the worker thread."""
        try:
            run_job(job_id)
        except Exception as e:
            job_exception[0] = (type(e), e, traceback.format_exc())
        finally:
            job_done_event.set()

    worker_thread = threading.Thread(target=_thread_target, daemon=True)
    worker_thread.start()

    # Wait for job completion with timeout
    timeout_seconds = DEFAULT_JOB_TIMEOUT_SECONDS
    if not job_done_event.wait(timeout=timeout_seconds):
        # Timeout occurred - job has been running too long
        err_msg = (
            f"Job execution timed out after {timeout_seconds} seconds. "
            f"The calculation may have encountered an infinite loop, deadlock, or "
            f"is taking longer than expected. Please check input parameters "
            f"(e.g., angle_steps should be <= 2000 for reasonable performance)."
        )
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job:
                job.status = "failed"
                job.updated_at = datetime.now(timezone.utc)
                job.error_message = err_msg
                db.commit()

        # Note: We cannot forcibly terminate the thread on Python/Windows
        # The thread will continue running until it completes or the process exits
        # This is a known limitation - the best we can do is mark the job as failed
        return

    # Job completed normally (or threw an exception)
    if job_exception[0] is not None:
        exc_type, exc_value, exc_tb = job_exception[0]
        err = exc_tb or str(exc_value)
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job:
                job.status = "failed"
                job.updated_at = datetime.now(timezone.utc)
                job.error_message = err[-8000:]
                db.commit()
