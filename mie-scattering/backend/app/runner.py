from __future__ import annotations

import json
import threading
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models import SimulationConfig
from app.simulation.fast_solver import run_fast_fdtd_scan


RESULT_FILES = [
    "config.json",
    "spectrum.csv",
    "heatmap.csv",
    "efficiencies.csv",
    "cross_sections.csv",
    "peaks.csv",
    "fdtd_fluxes.csv",
    "fields.h5",
    "geometry_summary.json",
    "material_summary.json",
    "summary.json",
    "fig_heatmap.png",
    "fig_spectrum.png",
    "fig_efficiency_components.png",
    "fig_peak_map.png",
    "fig_field_xy.png",
]


@dataclass
class SimulationJob:
    job_id: str
    config: SimulationConfig
    result_dir: Path
    status: str = "queued"
    progress: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error: str | None = None
    summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
            "config": self.config.model_dump(mode="json"),
            "summary": self.summary,
        }


class SimulationRunner:
    def __init__(self, results_dir: Path) -> None:
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, SimulationJob] = {}
        self._futures: dict[str, Future[None]] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=2)

    def load_existing_jobs(self) -> None:
        for result_dir in sorted(self.results_dir.glob("*")):
            if not result_dir.is_dir():
                continue
            config_file = result_dir / "config.json"
            summary_file = result_dir / "summary.json"
            if not config_file.exists():
                continue
            try:
                config_payload = json.loads(config_file.read_text(encoding="utf-8"))
                config_payload.pop("validation", None)
                if isinstance(config_payload.get("simulation"), dict):
                    workers = int(config_payload["simulation"].get("meep_workers", 1))
                    config_payload["simulation"]["meep_workers"] = max(1, min(workers, 2))
                    if config_payload["simulation"].get("solver") in {"bem", "dda"}:
                        config_payload["simulation"]["solver"] = "auto"
                config = SimulationConfig.model_validate(config_payload)
                summary = None
                status = "completed" if summary_file.exists() else "unknown"
                if summary_file.exists():
                    summary = json.loads(summary_file.read_text(encoding="utf-8"))
                self._jobs[result_dir.name] = SimulationJob(
                    job_id=result_dir.name,
                    config=config,
                    result_dir=result_dir,
                    status=status,
                    progress=1.0 if status == "completed" else 0.0,
                    summary=summary,
                )
            except Exception:
                continue

    def submit(self, config: SimulationConfig) -> SimulationJob:
        job_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
        result_dir = self.results_dir / job_id
        result_dir.mkdir(parents=True, exist_ok=False)
        job = SimulationJob(job_id=job_id, config=config, result_dir=result_dir)
        with self._lock:
            self._jobs[job_id] = job
        future = self._executor.submit(self._run_job, job_id)
        with self._lock:
            self._futures[job_id] = future
        return job

    def get(self, job_id: str) -> SimulationJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            jobs = list(self._jobs.values())
        return [
            {
                "job_id": job.job_id,
                "name": job.config.name,
                "status": job.status,
                "progress": job.progress,
                "created_at": job.created_at,
                "updated_at": job.updated_at,
                "summary": job.summary,
            }
            for job in sorted(jobs, key=lambda item: item.created_at, reverse=True)
        ]

    def result_index(self, job_id: str) -> list[dict[str, Any]]:
        job = self.get(job_id)
        if job is None:
            return []
        files: list[dict[str, Any]] = []
        for filename in RESULT_FILES:
            path = job.result_dir / filename
            if path.exists():
                files.append(
                    {
                        "name": filename,
                        "size": path.stat().st_size,
                        "url": f"/api/simulations/{job_id}/download/{filename}",
                    }
                )
        return files

    def result_file(self, job_id: str, filename: str) -> Path | None:
        if "/" in filename or "\\" in filename or filename not in RESULT_FILES:
            return None
        job = self.get(job_id)
        if job is None:
            return None
        path = job.result_dir / filename
        return path if path.exists() else None

    def _run_job(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None:
            return

        def set_progress(progress: float, status: str = "running") -> None:
            with self._lock:
                job.progress = progress
                job.status = status
                job.updated_at = datetime.now(timezone.utc).isoformat()

        try:
            set_progress(0.02)
            summary = run_fast_fdtd_scan(job.config, job.result_dir, progress_callback=set_progress)
            with self._lock:
                job.status = "completed"
                job.progress = 1.0
                job.updated_at = datetime.now(timezone.utc).isoformat()
                job.summary = summary
        except Exception as exc:
            with self._lock:
                job.status = "failed"
                job.progress = 1.0
                job.error = str(exc)
                job.updated_at = datetime.now(timezone.utc).isoformat()
