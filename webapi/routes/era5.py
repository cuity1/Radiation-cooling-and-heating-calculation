from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

import json

from ..db.models import Job, User
from ..db.session import SessionLocal
from ..dependencies.auth import require_user
from ..services.era5_plot_specs import PLOTS
from ..services.storage_service import job_dir

router = APIRouter(tags=["era5"], dependencies=[Depends(require_user)])


def _assert_job_access(job_id: str, current_user: User) -> None:
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


@router.get("/era5/{job_id}/figures")
def list_era5_figures(job_id: str, current_user: User = Depends(require_user)) -> list[dict]:
    """List figure artifacts produced by ERA5 job."""
    _assert_job_access(job_id, current_user)
    base = job_dir(job_id) / "era5" / "figures"
    if not base.exists():
        return []

    files = sorted([p for p in base.iterdir() if p.is_file()])
    out: list[dict] = []
    for p in files:
        out.append(
            {
                "name": p.name,
                "url": f"/api/era5/{job_id}/figures/{p.name}",
                "mime": mimetypes.guess_type(p.name)[0] or "application/octet-stream",
            }
        )
    return out


@router.get("/era5/{job_id}/figures/{filename}")
def get_era5_figure(job_id: str, filename: str, current_user: User = Depends(require_user)):
    _assert_job_access(job_id, current_user)
    base = job_dir(job_id) / "era5" / "figures"
    p = (base / filename).resolve()

    # path traversal guard
    if base.resolve() not in p.parents:
        raise HTTPException(status_code=400, detail="invalid filename")

    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="figure not found")

    return FileResponse(str(p), media_type=mimetypes.guess_type(p.name)[0] or "image/png")


@router.get("/era5/{job_id}/plots")
def list_era5_plots(job_id: str, current_user: User = Depends(require_user)) -> list[dict]:
    _assert_job_access(job_id, current_user)
    base = job_dir(job_id) / "era5" / "plots"
    if not base.exists():
        return []

    supported = {p.plot_id: p for p in PLOTS}
    out: list[dict] = []
    for p in sorted(base.glob("*.json")):
        plot_id = p.stem
        meta = supported.get(plot_id)
        out.append(
            {
                "plot_id": plot_id,
                "title": (meta.title if meta else plot_id),
                "kind": (meta.kind if meta else "unknown"),
                "spec_url": f"/api/era5/{job_id}/plots/{plot_id}",
                "data_url": f"/api/era5/{job_id}/plot-data/{plot_id}",
            }
        )
    return out


@router.get("/era5/{job_id}/plots/{plot_id}")
def get_era5_plot(job_id: str, plot_id: str, current_user: User = Depends(require_user)) -> dict:
    _assert_job_access(job_id, current_user)
    base = job_dir(job_id) / "era5" / "plots"
    p = (base / f"{plot_id}.json").resolve()

    if base.resolve() not in p.parents:
        raise HTTPException(status_code=400, detail="invalid plot_id")

    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="plot spec not found")

    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/era5/{job_id}/plot-data/{plot_id}")
def download_plot_data(job_id: str, plot_id: str, current_user: User = Depends(require_user)):
    """Download data behind a given plot as CSV.

    plot_id is the figure filename without extension, e.g. "1_1_cooling_power_timeline".
    """
    _assert_job_access(job_id, current_user)
    base = job_dir(job_id) / "era5" / "plot_data"
    p = (base / f"{plot_id}.csv").resolve()

    if base.resolve() not in p.parents:
        raise HTTPException(status_code=400, detail="invalid plot_id")

    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="plot data not found")

    return FileResponse(str(p), media_type="text/csv", filename=p.name)


@router.get("/era5/{job_id}/results-csv")
def download_results_csv(job_id: str, current_user: User = Depends(require_user)):
    """Download radiative_cooling_results_from_weather.csv file for ERA5 job."""
    import logging
    logger = logging.getLogger(__name__)
    
    _assert_job_access(job_id, current_user)
    base = job_dir(job_id) / "era5"
    base_resolved = base.resolve()
    
    logger.info(f"Download request for job_id={job_id}, base={base_resolved}")
    
    # Check if base directory exists
    if not base_resolved.exists():
        logger.error(f"ERA5 job directory not found: {base_resolved}")
        raise HTTPException(status_code=404, detail=f"ERA5 job directory not found: {base_resolved}")
    
    p = (base / "radiative_cooling_results_from_weather.csv").resolve()
    logger.info(f"Looking for CSV file at: {p}")

    # path traversal guard - ensure the resolved path is within the base directory
    try:
        p.relative_to(base_resolved)
    except ValueError:
        logger.error(f"Path traversal check failed: {p} not relative to {base_resolved}")
        raise HTTPException(status_code=400, detail="invalid job_id")

    if not p.exists() or not p.is_file():
        logger.error(f"CSV file not found: {p} (exists={p.exists()}, is_file={p.is_file() if p.exists() else False})")
        raise HTTPException(
            status_code=404, 
            detail=f"results CSV not found at {p}"
        )

    logger.info(f"Returning file: {p}")
    return FileResponse(str(p), media_type="text/csv", filename=p.name)
