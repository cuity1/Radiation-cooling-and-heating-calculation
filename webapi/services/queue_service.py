from __future__ import annotations

from redis import Redis
from rq import Queue

from ..settings import settings


def get_redis() -> Redis:
    return Redis.from_url(settings.redis_url)


def get_queue() -> Queue:
    # On Windows, RQ cannot fork; run workers in burst mode or use an alternative worker class.
    # Setting is_async=False makes jobs execute in-process (useful for development / Windows).
    return Queue(name=settings.rq_queue_name, connection=get_redis(), is_async=bool(getattr(settings, "rq_is_async", False)))


def enqueue_job(job_id: str) -> str:
    q = get_queue()
    job_func_path = "Radiation-cooling-and-heating-calculation.worker.tasks.run_job"
    job = q.enqueue(job_func_path, job_id)
    return job.id
