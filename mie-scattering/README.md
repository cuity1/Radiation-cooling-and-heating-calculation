# Nanoparticle Scattering Module

This repository contains a FastAPI scattering backend and a React dashboard that
can be embedded into a larger web project.

## Run

```bash
conda run -n mie-solvers --no-capture-output uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 9000
npm run dev --prefix frontend
```

Open:

```text
http://localhost:5174
```

## Solvers Exposed In UI

- `auto`
- `mie`
- `tmatrix`
- `rcwa`
- `grcwa`
- `smart_proxy`

The frontend does not expose Meep. The automatic solver path avoids Meep and
uses lower-resource analytical, T-matrix, and RCWA/grcwa routes.

## Main Files

- `backend/app/main.py`: API routes and static frontend mount.
- `backend/app/models.py`: shared request/config schema.
- `backend/app/runner.py`: async job queue and result indexing.
- `backend/app/simulation/solver_router.py`: solver selection.
- `backend/app/simulation/scan_defaults.py`: default scan density and limits.
- `backend/app/simulation/fast_solver.py`: result generation for non-Meep routes.
- `backend/app/simulation/integrated_solvers.py`: T-matrix, rcwa, grcwa adapters.
- `frontend/src/main.jsx`: React app and API integration.
- `frontend/src/styles.css`: dashboard styling.
- `docs/project_architecture.md`: migration and embedding notes.

