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

## Release Baselines & Tagging

An annotated Git tag (`vX.Y.0`, one per accepted phase) marks an **accepted
engineering baseline** — not every commit, and not every development
milestone. A tag is created only after a phase has, in order:

1. Passed its automated test suite (backend `pytest`, frontend `vitest`,
   both against real PostgreSQL where the phase touches schema — see
   [`docs/development/postgresql-setup.md`](docs/development/postgresql-setup.md)).
2. Passed manual UAT.
3. Been architecturally reviewed against [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md).
4. Been explicitly accepted (recorded in [`CHANGELOG.md`](CHANGELOG.md)).
5. Been committed to Git.

Tags are annotated (`git tag -a`, never lightweight) so the tag itself
carries a message and an identifiable tagger, distinct from the commit it
points to. Existing baselines:

| Tag | Commit | Marks |
|---|---|---|
| `v0.2.0` | `ff830a4f0999c5d9eeca79d55647da4e53f6b3f8` | Phase 2 — Substation Registry, accepted with PostgreSQL verification |

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

### Seeding and Bootstrapping (required before first login or UAT)

`alembic upgrade head` only creates schema — it does not populate reference data, create the bootstrap Administrator, or register any module's permissions. **Every module's `bootstrap.py` is a manual step; none of it runs automatically on server startup or on first login.** A freshly migrated database has an empty `permission` table and no usable account until these are run, in order, from `backend/` with `.venv` activated:

```bash
python -m app.reference_data.seed          # voltage levels, regions, states, grid owners, operational statuses, line types
python -m app.modules.iam.bootstrap         # bootstrap Administrator account + baseline Administrator/Engineer/Viewer roles
python -m app.modules.substation_registry.bootstrap    # registers substation_registry.read/.write, grants to baseline roles
python -m app.modules.equipment_registry.bootstrap     # registers equipment_registry.read/.write, grants to baseline roles
```

Every business module added in a future phase gets its own `bootstrap.py` following this same pattern — add its command to this list when that phase ships. All four commands are idempotent (safe to re-run against an already-bootstrapped database) and order-tolerant except that `iam.bootstrap` must run before a business module's own bootstrap can actually grant its permissions to a role (a module's bootstrap run before IAM's own will register the permission but skip the role grants, logging a warning — re-running it afterward completes the grants, per each `bootstrap.py`'s own docstring).

**`python -m app.reference_data.seed` must be re-run every time it changes, not only once.** It is idempotent (only ever inserts rows that don't already exist — see `app/reference_data/seed.py`'s `run_seed()`), but nothing runs it automatically when a later phase adds a new reference table or new rows to an existing one. Pulling code that adds to `seed.py` does not update your already-running local/dev database on its own — you must re-run the command by hand against that specific database. The same is true for each module's `bootstrap.py` whenever it adds a new permission.

**Two deployment gaps were found and fixed during Phase 3 UAT, both of the same shape** — code was correct and fully tested, but the persistent dev database was never re-synchronized with it:

- `equipment_registry.write` was never granted to any role, because `python -m app.modules.equipment_registry.bootstrap` had never been run against the persistent dev database (only inside the automated test suite, which bootstraps its own disposable database per test). The write-permission-gated controls on `/circuits` were correctly hidden — the frontend was accurately reflecting an incomplete backend deployment.
- The Line Type dropdown on Create Circuit was empty, because `line_type` was added to `app/reference_data/seed.py` by Phase 3, but `python -m app.reference_data.seed` was last run against the dev database *before* that change — leaving the `line_type` table created (by the Phase 3 migration) but empty. Re-running the seed command (idempotent — it left the other five already-populated reference tables untouched and inserted only the four missing `line_type` rows) resolved it.

**A third category exists alongside seeding and bootstrapping: Alembic migrations that backfill data, not just schema.** `0005_substation_voltage_yard` (Phase 3 UAT fix package — see [`docs/adr/ADR-008-substation-voltage-yard.md`](docs/adr/ADR-008-substation-voltage-yard.md)) is the first migration in this project that both changes schema *and* backfills real rows from existing data (one default `SubstationVoltageYard` per existing substation, and every existing `circuit_terminal` repointed at it) — this happens automatically as part of `alembic upgrade head`, unlike seeding/bootstrapping, which are always separate manual commands. Do not confuse the three: **migrations** (`alembic upgrade head`, schema plus, occasionally, structural backfill) run first; **reference-data seeding** (`python -m app.reference_data.seed`) and **module permission bootstrap** (`python -m app.modules.<name>.bootstrap`) are separate, independently-rerunnable steps that must be repeated by hand whenever their own source changes, exactly as described above.

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
