# GridDefence

Engineering platform for managing transmission grid defence schemes (UFLS, UVLS, EMLS) in Peninsular Malaysia — the single source of truth for grid defence planning, implementation, auditing, and simulation.

Full architecture documentation lives in [`docs/architecture/`](docs/architecture/) and [`docs/adr/`](docs/adr/); engineering standards are defined in [`.claude/CLAUDE.md`](.claude/CLAUDE.md). This repository is currently at **Phase 0 — Repository Foundation** (see [`docs/architecture/implementation-plan.md`](docs/architecture/implementation-plan.md)): the project skeleton, tooling, and infrastructure exist, but no business modules (IAM, Substation Registry, UFLS, etc.) have been implemented yet.

---

## Development Workflow

Day-to-day implementation workflow, review criteria, and the shipped-phase
history live in three project governance documents at the repository root:

- [`DEVELOPMENT.md`](DEVELOPMENT.md) — architecture-first, one-phase-at-a-time
  workflow: environment setup, dependency management, backend layering
  rules, Alembic migration rules, and the required implementation report
  format.
- [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md) — the standard checklist
  applied to every phase, plus a running list of each phase's high-risk
  files that warrant closer review.
- [`CHANGELOG.md`](CHANGELOG.md) — a factual, phase-by-phase record of what
  has actually shipped.

---

## Repository Structure

```
griddefence/
├── .claude/CLAUDE.md   # Engineering standards (governing document)
├── docs/                # Architecture documents and ADRs
├── backend/              # FastAPI + SQLAlchemy + Alembic
├── frontend/              # React + TypeScript + Vite
├── docker-compose.yml
├── .env.example
└── .venv/                  # Project-local Python virtual environment (not committed)
```

---

## Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16+ (for local, non-Docker development — see [`docs/development/postgresql-setup.md`](docs/development/postgresql-setup.md)) **or** Docker + Docker Compose (for the containerised workflow)

---

## Python Development Environment

GridDefence uses a **project-local virtual environment named `.venv`, created at the repository root.** Every Python package is installed inside it — never globally.

### Create and activate `.venv`

From the repository root:

```bash
python -m venv .venv
```

Activate it:

**Windows (PowerShell):**

```powershell
.venv\Scripts\activate
```

**Linux/macOS:**

```bash
source .venv/bin/activate
```

### Install backend dependencies

With `.venv` activated:

```bash
pip install -e "./backend[dev]"
```

This installs the backend package in editable mode, including development tools (`pytest`, `ruff`). `backend/pyproject.toml` is the single source of truth for backend dependencies — there is no separate `requirements.txt`.

---

## Running Locally (without Docker)

### Backend

From the repository root, with `.venv` activated:

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

The API is available at `http://localhost:8000`, with an unversioned health check at `GET /health` and the versioned API mounted at `/api/v1` (empty until later phases add module routers).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs at `http://localhost:5173` and expects the backend at `http://localhost:8000` by default (override via `VITE_API_BASE_URL`, see [Environment Variables](#environment-variables)).

### Database

The backend expects PostgreSQL to be reachable at the connection string in `DATABASE_URL`. See [`docs/development/postgresql-setup.md`](docs/development/postgresql-setup.md) for the full setup walkthrough (installation, dedicated database/user creation, connection verification, migration workflow, and troubleshooting) — the short version: create a dedicated `engineering_platform` database owned by a dedicated `engineering_app` user (never use the default `postgres` database for the application), point `DATABASE_URL` at it in the repository-root `.env`, then run `alembic upgrade head` from `backend/`.

---

## Running with Docker Compose

From the repository root:

```bash
cp .env.example .env
docker compose up --build
```

This starts three services:

- `postgres` — PostgreSQL 16, data persisted in a named volume.
- `backend` — FastAPI, reachable at `http://localhost:8000`.
- `frontend` — Vite dev server, reachable at `http://localhost:5173`.

The backend waits for Postgres to report healthy before starting. The local `.venv` is never mounted into any container — containers install their own dependencies independently inside the image, keeping the containerised environment isolated from the host's Python environment.

Stop everything with `docker compose down` (add `-v` to also remove the database volume).

---

## Tests

### Backend

```bash
cd backend
pytest
```

### Frontend

```bash
cd frontend
npm run test
```

---

## Quality Tooling

### Backend

```bash
cd backend
ruff check .          # lint
ruff format .          # format
```

### Frontend

```bash
cd frontend
npm run lint            # ESLint
npm run typecheck        # TypeScript, no emit
```

---

## Database Migrations (Alembic)

Migrations are **hand-reviewed, never blindly committed** — `alembic revision --autogenerate` produces a draft that must be checked before merging (see `docs/architecture/implementation-plan.md` §5).

From `backend/`, with `.venv` activated and `DATABASE_URL` pointing at a reachable Postgres instance:

```bash
alembic upgrade head          # apply all migrations
alembic revision --autogenerate -m "describe the change"   # generate a draft migration
alembic downgrade -1           # roll back one revision
alembic history                 # view the migration chain
```

Phase 0 ships a single no-op baseline revision (`0001_initial_baseline`) that establishes the migration chain without creating any domain tables. The first real schema migration lands with Phase 1 (IAM + Core Reference Data).

---

## Environment Variables

See [`.env.example`](.env.example) for the full list with defaults. Summary:

| Variable | Purpose |
|---|---|
| `POSTGRES_USER` | Database username (Docker Compose Postgres service) |
| `POSTGRES_PASSWORD` | Database password |
| `POSTGRES_DB` | Database name |
| `DATABASE_URL` | Full SQLAlchemy connection string the backend uses |
| `BACKEND_HOST` | Backend bind host |
| `BACKEND_PORT` | Backend port |
| `FRONTEND_PORT` | Frontend dev server port |
| `ENVIRONMENT` | `development` \| `test` \| `production` |

No secrets are committed to source control (CLAUDE.md §22) — `.env` is git-ignored; `.env.example` documents the shape only.

---

## Architecture

This project follows a **modular monolith** architecture (ADR-001): each business module (IAM, Substation Registry, Equipment Registry, PSS/E Integration, Network Model, UFLS, UVLS, EMLS, Critical Infrastructure, Cross-Scheme Compliance, Dashboard) is an independent bounded context communicating through in-process service interfaces — never by importing another module's repository or writing to its tables. See [`docs/architecture/system-overview.md`](docs/architecture/system-overview.md) and [`docs/architecture/implementation-plan.md`](docs/architecture/implementation-plan.md) for the full module build order and phased rollout plan.

**Do not** copy implementation patterns from the legacy Django MVP referenced in the architecture documents — FastAPI/SQLAlchemy/Alembic use different idioms (explicit service layers, reviewed migrations, Pydantic schemas) than Django's admin/signal/`makemigrations` conventions.
