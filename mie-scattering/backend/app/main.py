from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import SimulationConfig
from app.runner import SimulationRunner
from app.simulation.scan_defaults import (
    apply_missing_solver_scan_defaults,
    apply_solver_scan_defaults,
    normalize_scan_for_solver_limits,
)
from app.simulation.solver_router import select_solver


BASE_DIR = Path(__file__).resolve().parents[2]
RESULTS_DIR = BASE_DIR / "results"
runner = SimulationRunner(RESULTS_DIR)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    runner.load_existing_jobs()
    yield

app = FastAPI(
    title="FDTD Nanoparticle Scattering API",
    description="Submit and inspect general nanoparticle scattering scans across materials, geometries, and arrays.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/default-config", response_model=SimulationConfig)
def default_config() -> SimulationConfig:
    return apply_solver_scan_defaults(SimulationConfig())


@app.post("/api/simulations", status_code=202)
def create_simulation(config: SimulationConfig) -> dict[str, str]:
    config = apply_missing_solver_scan_defaults(config)
    config = normalize_scan_for_solver_limits(config)
    selection = select_solver(config)
    if selection.blocking:
        detail = {"message": selection.reason, "solver_selection": selection.model_dump()}
        raise HTTPException(status_code=400, detail=detail)
    job = runner.submit(config)
    return {"job_id": job.job_id, "status": job.status}


@app.get("/api/simulations")
def list_simulations() -> dict[str, list[dict[str, object]]]:
    return {"jobs": runner.list_jobs()}


@app.get("/api/simulations/{job_id}")
def get_simulation(job_id: str) -> dict[str, object]:
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Simulation job not found")
    return job.to_dict()


@app.get("/api/simulations/{job_id}/results")
def get_results(job_id: str) -> dict[str, object]:
    job = runner.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Simulation job not found")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail="Simulation has not completed")
    return {"job_id": job_id, "files": runner.result_index(job_id)}


@app.get("/api/simulations/{job_id}/download/{filename}")
def download_result(job_id: str, filename: str) -> FileResponse:
    file_path = runner.result_file(job_id, filename)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Result file not found")
    return FileResponse(file_path, filename=filename)


frontend_dist = BASE_DIR / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
