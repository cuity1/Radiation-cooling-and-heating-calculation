# Project Architecture And Migration Notes

## Purpose

This module provides nanoparticle scattering scans through a FastAPI backend and
a React dashboard. It is ready to be embedded into another web project as either:

- a standalone microservice plus embedded frontend route, or
- a backend API module consumed by an existing frontend.

## Runtime Ports

| Service | Default |
| --- | --- |
| Backend API | `http://localhost:9000` |
| Frontend dev server | `http://localhost:5174` |

The frontend API base is defined in `frontend/src/main.jsx`:

```js
const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:9000';
```

Set `VITE_API_BASE` in the host web project if the API path changes.

## Backend Layout

| File | Responsibility |
| --- | --- |
| `backend/app/main.py` | FastAPI app, CORS, API routes, static frontend mount |
| `backend/app/models.py` | Pydantic request schema for geometry, material, array, scan, solver |
| `backend/app/runner.py` | Job queue, result directories, job status, result file index |
| `backend/app/simulation/solver_router.py` | Solver selection and solver applicability checks |
| `backend/app/simulation/scan_defaults.py` | Default scan density and scan guardrails |
| `backend/app/simulation/fast_solver.py` | Main non-Meep scan execution and output generation |
| `backend/app/simulation/integrated_solvers.py` | `treams`, `rcwa`, `grcwa` adapters |
| `backend/app/simulation/mie.py` | Analytical Mie helper functions |
| `backend/app/simulation/geometry.py` | Geometry metrics and geometry summaries |
| `backend/app/simulation/materials.py` | Preset materials and refractive-index resolution |
| `backend/app/simulation/solver_limits.py` | Shared solver limits |

## Frontend Layout

| File | Responsibility |
| --- | --- |
| `frontend/src/main.jsx` | React app, controls, 3D preview, API calls, job polling, plots |
| `frontend/src/styles.css` | Dashboard layout and visual styling |
| `frontend/package.json` | Vite scripts and frontend dependencies |

The frontend is currently a single React entry file. For embedding into a larger
app, the natural extraction boundary is:

- keep API helpers and config state close to the host app route,
- move the parameter panel, preview, and results views into separate components,
- keep `API_BASE` configurable through environment or host props.

## API Surface

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Health check |
| `GET` | `/api/default-config` | Returns a full default `SimulationConfig` |
| `POST` | `/api/simulations` | Queue a scan |
| `GET` | `/api/simulations` | List jobs |
| `GET` | `/api/simulations/{job_id}` | Get one job |
| `GET` | `/api/simulations/{job_id}/results` | List result files |
| `GET` | `/api/simulations/{job_id}/download/{filename}` | Download one result file |

## Solver Policy

The UI exposes these solvers:

- `auto`
- `mie`
- `tmatrix`
- `rcwa`
- `grcwa`
- `smart_proxy`

Meep is intentionally hidden from the frontend. The backend still contains the
explicit Meep route for compatibility, but `auto` avoids it.

Current automatic routing:

| Model scope | Auto solver | Default scan |
| --- | --- | --- |
| Isolated homogeneous sphere | `mie` | `160 x 80` |
| Isolated cylinder | `tmatrix` | `100 x 50` |
| Isolated shell | `tmatrix` | `100 x 50` |
| Enabled periodic array | `grcwa` | `12 x 8` |
| Cube or ellipsoid without array | `smart_proxy` | `160 x 80` |
| Non-array model with substrate | `smart_proxy` | `160 x 80` |

RCWA/grcwa scans are capped at 96 wavelength-diameter points per job.

## Required Python Dependencies

Install from `requirements.txt` or mirror these dependencies in the host
project:

```text
fastapi
uvicorn[standard]
pydantic
numpy
scipy
matplotlib
h5py
miepython
treams
rcwa
grcwa
pytest
httpx
```

Recommended backend environment:

```bash
conda run -n mie-solvers --no-capture-output uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 9000
```

## Required Frontend Dependencies

Defined in `frontend/package.json`:

```text
@vitejs/plugin-react
lucide-react
plotly.js-dist-min
react
react-dom
react-plotly.js
three
vite
```

## Generated Files

Runtime jobs write to:

```text
results/<job_id>/
```

Typical result files:

- `config.json`
- `summary.json`
- `spectrum.csv`
- `heatmap.csv`
- `efficiencies.csv`
- `cross_sections.csv`
- `peaks.csv`
- `fields.h5`
- `geometry_summary.json`
- `material_summary.json`
- `fig_heatmap.png`
- `fig_spectrum.png`
- `fig_efficiency_components.png`
- `fig_peak_map.png`
- `fig_field_xy.png`

These are generated artifacts and should not be migrated as source.

## Embedding Checklist

1. Copy `backend/app` into the host backend or keep it as a separate service.
2. Preserve `backend/app/models.py` and `backend/app/simulation/*` together; the
   solver code depends on shared schema, geometry, and material helpers.
3. Expose the API routes from `backend/app/main.py`, or mount the FastAPI app
   under a host prefix.
4. Copy `frontend/src/main.jsx` and `frontend/src/styles.css`, or split them into
   host components.
5. Set `VITE_API_BASE` if the API is not served from `http://localhost:9000`.
6. Keep `results/` writable by the backend runtime.
7. Do not migrate `frontend/dist`, `results`, `audit_runs`, `__pycache__`, or
   `.pytest_cache` as source files.

