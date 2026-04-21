# Web Platform Refactor (Async / Queue-based) — Bootstrap Plan

This document describes the **initial scaffolding** plan for converting the current PyQt5 desktop app into a **Web platform** with **FastAPI + RQ + Redis** and a **Web GUI**. The goal of this phase is to build a solid, extensible *framework* first (pages, APIs, job model), then gradually fill in real calculation logic.

> Repo note: the existing computation logic is already well-isolated under `core/` and has **no PyQt dependency**. This is a strong foundation for service-ization.

---

## 0. Architecture choices (best-fit for this codebase)

### Queue
- **RQ + Redis (chosen first)**
  - Lightweight, easy to reason about, good for a first platform cut.
  - Fits the project’s current nature (single-machine/local/department server) and Python-first stack.
- Future upgrade path: Celery if you later need complex workflows (chords/chains), scheduling, or advanced retries.

### Database
- **SQLite (chosen first)** for job metadata
  - Minimal ops burden; good for MVP and single-node deployments.
  - Keep storage logic behind a small repository/service layer so Postgres can be swapped in later.

### Storage
- **Filesystem as the source of truth** for large artifacts
  - `data/uploads/{upload_id}/...`
  - `data/jobs/{job_id}/result.json` and `data/jobs/{job_id}/artifacts/*`

### Frontend
- **React + Vite (chosen)**
  - Best ergonomics for page scaffolding, routing, state, and future charting.
  - UI-first request: build page frames now, wire actual content later.

### API style
- **Resource-oriented REST**
  - Simple for the first iteration.
  - Keep room for adding WebSocket/SSE later for status push.

---

## 1. Target MVP (first “platform skeleton”)

### What MVP should allow
- Create a job (with placeholder/mock compute first).
- Observe job state transitions:
  - `queued -> started -> succeeded/failed`
- View job list and job detail pages in Web UI.
- Fetch a job’s `result.json` (even if mocked).

### What MVP does NOT need yet
- Full parameter forms for every feature.
- Real file parsing / all default datasets selection.
- Full visualization parity with PyQt.

---

## 2. Proposed repo layout (incremental, non-breaking)

Keep existing code; add new modules alongside.

```
Radiation-cooling-and-heating-calculation/
  core/                       # existing compute library
  gui/                        # existing PyQt GUI (kept for now)

  webapi/                     # NEW: FastAPI service
    main.py
    settings.py
    schemas.py
    routes/
      health.py
      jobs.py
      files.py
    services/
      jobs_service.py
      storage_service.py
      queue_service.py
    db/
      models.py
      session.py

  worker/                     # NEW: RQ worker entry + job functions
    tasks.py
    worker.py

  frontend/                   # NEW: React app scaffold
    (vite project)

  data/                       # NEW: runtime data (uploads/results)
    uploads/
    jobs/

  scripts/                    # NEW: dev start helpers (optional)
```

---

## 3. Job model (platform contract)

### Job entity
- `id`: UUID
- `type`: `cooling | heating | energy_map | ...` (string)
- `status`: `queued | started | succeeded | failed | cancelled`
- `created_at`, `updated_at`
- `params_json`: JSON blob (request payload)
- `result_path`: filesystem path to `result.json` (nullable)
- `error_message`: nullable

### Result format (first iteration)
- `result.json` (must exist on success)
  - `summary`: basic numbers and metadata
  - `plots`: list of plot descriptors (front-end decides how to render)
  - `artifacts`: downloadable files list

---

## 4. API design (skeleton endpoints)

### Health
- `GET /api/health`

### Jobs
- `POST /api/jobs` (create job)
  - body: `{ type: "cooling", params: {...} }`
  - returns: `{ job_id }`
- `GET /api/jobs` (list jobs)
- `GET /api/jobs/{job_id}` (job detail)
- `GET /api/jobs/{job_id}/result` (returns JSON result if ready)

### Files (later)
- `POST /api/files/upload`
- `GET /api/files/presets`

---

## 5. Worker (RQ) execution flow

1. API creates job record in DB (status `queued`).
2. API enqueues an RQ job with payload `{job_id}`.
3. Worker picks it up:
   - sets DB status `started`
   - runs compute (initially mocked)
   - writes `data/jobs/{job_id}/result.json`
   - sets DB status `succeeded` (or `failed` with error)

---

## 6. Frontend page skeleton (UI-first)

### Routes
- `/` redirect to `/jobs`
- `/jobs` job list
- `/jobs/new` create job
- `/jobs/:jobId` job detail

### UI behavior
- Job list: polling every ~2s while there are active jobs.
- Job detail: show status, timestamps, and a placeholder result panel.

---

## 7. Development & run (intended)

### Local dev components
- Redis
- API
- Worker
- Frontend

### Recommended dev order
1. Start Redis
2. Start API
3. Start worker
4. Start frontend

---

## 8. Migration plan from mock to real compute

- Phase 1: worker returns mocked results quickly (proves platform pipeline).
- Phase 2: integrate one real feature end-to-end (e.g. cooling power) using `core/`.
- Phase 3: expand types + file handling + presets.

---

## 9. Non-goals / constraints (for stability)

- Keep `core/` importable and side-effect free.
- Avoid changing existing PyQt GUI now; keep it as a reference implementation.
- Avoid heavy infra at the start (no Celery, no Postgres) until MVP is stable.
