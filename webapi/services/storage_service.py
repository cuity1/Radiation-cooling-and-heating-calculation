from __future__ import annotations

from pathlib import Path

from ..settings import settings


def job_dir(job_id: str) -> Path:
    p = settings.jobs_dir / job_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def job_result_path(job_id: str) -> Path:
    return job_dir(job_id) / "result.json"
