from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


JobType = Literal[
    "cooling",
    "heating",
    "in_situ_simulation",
    "energy_map",
    "material_env_temp_map",
    "compare_materials",
    "compare_glass",
    "radiation_cooling_clothing",
    "material_env_temp_cloud",
    "mock",
]
JobStatus = Literal["queued", "started", "succeeded", "failed", "cancelled"]


class CreateJobRequest(BaseModel):
    type: JobType = Field(..., description="Job type")
    remark: str | None = Field(default=None, max_length=50, description="Remark / note for the job")
    params: dict[str, Any] = Field(default_factory=dict, description="Job parameters")


class CreateJobResponse(BaseModel):
    job_id: str


class JobSummary(BaseModel):
    id: str
    type: JobType
    status: JobStatus
    remark: str | None = None
    created_at: datetime
    updated_at: datetime


class JobDetail(JobSummary):
    params: dict[str, Any] = Field(default_factory=dict)
    result_ready: bool = False
    error_message: str | None = None
    user_id: int | None = None


class JobResult(BaseModel):
    job_id: str
    generated_at: datetime
    summary: dict[str, Any] = Field(default_factory=dict)
    plots: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)


class JobStats(BaseModel):
    total_jobs: int
    today_jobs: int
