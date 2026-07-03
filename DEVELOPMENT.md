# GridDefence Development Guide

This document defines the day-to-day development workflow for GridDefence. It
sits below [`.claude/CLAUDE.md`](.claude/CLAUDE.md) in the standards
hierarchy — `CLAUDE.md` is the engineering standard; this document explains
how to work inside that standard on a day-to-day basis. Where anything here
appears to conflict with `CLAUDE.md`, `CLAUDE.md` governs.

This document does not redefine architecture. It does not replace
`docs/architecture/`, `docs/adr/`, or `.claude/CLAUDE.md`. It is a workflow
reference for anyone — human or AI — implementing a phase of GridDefence.

---

## 1. Architecture-First Implementation

Architecture always precedes implementation (CLAUDE.md §10, §24).

Before writing code for any module or feature:

1. The relevant module architecture document under `docs/architecture/`
   must already exist and be current.
2. Any decision that changes domain ownership, versioning, security, or
   database standards requires an ADR under `docs/adr/` (CLAUDE.md A13)
   *before* implementation, not after.
3. Implementation must follow the architecture document exactly. If the
   architecture is ambiguous, silent, or internally inconsistent, **stop and
   report the conflict** rather than inventing a resolution (see §9).

Do not redesign architecture while implementing. Architecture changes go
through `docs/architecture/` and `docs/adr/`, never through an
implementation session alone.

---

## 2. One Phase at a Time

GridDefence is built in the sequence defined by
[`docs/architecture/implementation-plan.md`](docs/architecture/implementation-plan.md).

- Implement exactly the phase requested. Do not implement functionality
  belonging to a later phase, even if it seems convenient or related.
- Do not skip ahead because a later phase's entity "will be needed soon."
  Dependencies flow one direction only (CLAUDE.md §7, A2, F2) — build in
  order.
- A phase is not "mostly done" or "done except tests." It is done per the
  Definition of Done in §8 below, or it is not done.

---

## 3. Python Environment: `.venv` Only

GridDefence uses a single project-local virtual environment, `.venv`,
created at the repository root.

- **Never** install Python packages globally.
- **Never** create a second virtual environment (no per-module venvs, no
  `backend/.venv`).
- Every Python command (`pytest`, `ruff`, `alembic`, `uvicorn`, seed/bootstrap
  scripts) runs through this `.venv`.
- If a new Python package is required, install it into `.venv` **and**
  record it in `backend/pyproject.toml` (§5). An install that isn't reflected
  in `pyproject.toml` is not a completed change — the next person's `.venv`
  won't have it.

```bash
# from the repository root
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # Linux/macOS

pip install -e "./backend[dev]"
```

---

## 4. Dependency Management

### Backend (Python)

`backend/pyproject.toml` is the single source of truth for backend
dependencies. There is no `requirements.txt`.

- Add a new runtime dependency to `[project].dependencies`.
- Add a new development-only dependency (test/lint tooling) to
  `[project.optional-dependencies].dev`.
- Pin a version range, not a bare package name — see the existing entries
  for the expected style (`"fastapi>=0.115,<1.0"`).
- After editing `pyproject.toml`, reinstall (`pip install -e "./backend[dev]"`)
  so `.venv` matches the declared dependencies.

### Frontend (Node)

`frontend/package.json` is the single source of truth for frontend
dependencies.

- Runtime dependency → `dependencies`.
- Build/test/lint-only tooling → `devDependencies`.
- Run `npm install` from `frontend/` after any change so `package-lock.json`
  stays in sync and is committed alongside `package.json`.

---

## 5. Python Package Metadata Rule

`backend/pyproject.toml` must not reference any file outside `backend/`.

- `readme = "README.md"` must resolve to `backend/README.md` (a path
  relative to `pyproject.toml` itself), never to the repository root
  `README.md`.
- `[tool.setuptools.packages.find]` must only ever discover packages under
  `backend/` (currently `include = ["app*"]`).
- `[tool.pytest.ini_options] testpaths` must only ever list paths inside
  `backend/` (currently `["tests", "app"]`).
- No `path = "../..."`-style relative reference to anything outside
  `backend/` is permitted anywhere in the file.

This keeps the backend package self-contained and installable
(`pip install -e ./backend`) regardless of what exists elsewhere in the
repository, and keeps `backend/` extractable as an independent service
later without carrying hidden dependencies on sibling directories
(consistent with CLAUDE.md F6's modular-monolith-to-service extraction
principle).

---

## 6. Docker Compose: Maintained, Optional Locally

`docker-compose.yml` must be kept working and current, but Docker is **not**
required for local development.

- Every phase that changes backend or frontend runtime configuration must
  keep `docker-compose.yml` consistent with the change (new environment
  variables, new ports, etc.).
- Local development, verification, and testing during implementation may
  run entirely outside Docker (`.venv` + a locally reachable PostgreSQL, or
  SQLite as a documented stand-in when no PostgreSQL is reachable — see
  §7).
- Do not claim Docker-based verification occurred unless `docker compose up`
  (or the specific service command used) was actually run. If Docker was
  unavailable in the environment an implementation session ran in, say so
  explicitly in the implementation report (§10) rather than omitting it.

---

## 7. Backend Layering: Router → Service → Repository → Models

Every backend module follows the same layered structure (CLAUDE.md §14, A6):

```
Router          HTTP, request validation, authentication
    ↓
Service         Business rules, transactions, orchestration, audit writing
    ↓
Repository      Persistence access — no business logic
    ↓
Models          SQLAlchemy persistence mapping
```

Rules:

- Business logic never lives in a router. A router handler's job is to
  parse the request, call exactly one service method, and shape the
  response.
- A repository method does one thing: read or write rows. It never
  evaluates a business rule, never decides whether an action is allowed,
  and never writes an audit record.
- All mutating business rules and all audit writes live in the service
  layer, not scattered between router and repository.
- API DTOs (Pydantic schemas), domain concepts, and persistence models
  (SQLAlchemy) are three distinct layers (CLAUDE.md A6). A persistence model
  is never returned directly from an API endpoint.

## 7a. No Cross-Module Repository Imports

Modules are bounded contexts (CLAUDE.md §12, A1).

- A module may call another module's **service layer** (in-process,
  CLAUDE.md A1).
- A module must never import or instantiate another module's
  **repository**, and must never write to another module's tables
  directly.
- Read-only SQL joins across module-owned tables are permitted only for
  query optimisation, reporting, and dashboard read models (CLAUDE.md F6) —
  never as a substitute for calling the owning module's service for a
  business decision.

## 7b. No Duplicated Master Data

Every engineering entity has exactly one owner (CLAUDE.md §5.1, §8).

- If a module needs data owned by another module (e.g. UFLS needing a
  substation's voltage level), it references that data through a foreign
  key or a service call — it never copies the value into its own table.
- Reference/lookup data (voltage levels, regions, grid owners, operational
  statuses, etc.) lives in the dedicated reference tables owned by the
  module responsible for them (CLAUDE.md §11.3) — never re-declared or
  re-seeded per-module.

## 7c. No Hardcoded Engineering Values

Engineering parameters are versioned, auditable database data — never
literals in source code (CLAUDE.md A7).

- Frequency thresholds, voltage thresholds, priority levels, load block
  definitions, activation dates, approval statuses, and similar engineering
  parameters must be read from the database, not hardcoded in Python or
  TypeScript.
- Reference/seed data (voltage levels, regions, grid owner codes, etc.) is
  the one exception this rule explicitly allows: it is still database data,
  populated by an idempotent seed script, not inline application logic —
  see §8 below for the rules governing that seed data itself.
- Infrastructure configuration (database URL, secret keys, ports, log
  level) is the other exception — that belongs in environment variables
  (CLAUDE.md §22), not the database and not hardcoded either.

---

## 8. Alembic Migration Rules

- One logical schema change per migration. Do not bundle unrelated schema
  changes into a single revision.
- Every migration is reviewed manually before it is treated as final —
  whether hand-written or produced by `alembic revision --autogenerate`.
  Autogenerate output is a draft, not a finished migration.
- **Never modify a migration that has already been committed.** A mistake
  in a committed migration is corrected by a new migration, not by editing
  history — this mirrors CLAUDE.md §5.2's immutable-history principle at
  the schema level.
- Every migration must have a working, tested `downgrade()`. A migration
  that only supports `upgrade()` is incomplete.
- If no PostgreSQL instance is reachable in the environment a migration is
  authored in, verify it against a throwaway SQLite database as a
  stand-in (`alembic upgrade head` → inspect schema → `alembic downgrade
  base`), and say so explicitly in the implementation report — this is not
  a substitute for eventually running the migration against real
  PostgreSQL, only a pragmatic interim check.
- Reference/lookup table primary keys are `SMALLINT`/`INTEGER` on
  PostgreSQL (CLAUDE.md A5); if a dialect-variant type is needed to keep a
  migration testable against SQLite, the migration's column types must stay
  byte-for-byte consistent with the corresponding SQLAlchemy model.

```bash
# from backend/, with .venv activated and DATABASE_URL reachable
alembic upgrade head
alembic revision --autogenerate -m "describe the change"
alembic downgrade -1
alembic history
```

---

## 9. When Architecture Conflicts With Implementation

If, while implementing, you discover that:

- an architecture document is silent on something implementation requires,
- two architecture documents (or an architecture document and an ADR)
  disagree, or
- the documented design is not implementable as written,

**stop and explain the conflict.** Do not make an architectural decision to
route around it. Report the conflict plainly (what the documents say, where
they conflict or fall short, and the options as you see them) so the
Project Owner or the Chief Solution Architect can resolve it — resolution
happens in `docs/architecture/` or `docs/adr/`, not silently inside an
implementation session.

A narrow, low-stakes implementation detail an architecture document
genuinely leaves open (explicitly marked "implementation detail" in the
document itself) is not a conflict — implement it reasonably and document
the choice made in the implementation report (§10).

---

## 10. Testing and Verification Commands

### Backend

```bash
cd backend
ruff check .              # lint
ruff format .              # format
pytest                       # full test suite
pytest -v                     # verbose
```

### Frontend

```bash
cd frontend
npm run lint                 # ESLint
npm run typecheck             # TypeScript, no emit
npm run test                   # Vitest (single run)
npm run build                   # production build (tsc -b && vite build)
```

A phase is not verified until all four frontend commands and both backend
commands (`ruff check`, `pytest`) pass. Report exactly which of these were
run and their results — do not report a command as passing without having
run it in this session.

### PostgreSQL verification pass

`backend/conftest.py`'s `db_session` fixture uses SQLite in-memory by
default — fast, dependency-free, correct for day-to-day iteration. SQLite's
flexible typing hides real PostgreSQL-specific behaviour (e.g. `SMALLINT`
range enforcement, native `UUID`/`TIMESTAMPTZ` types, real FK `RESTRICT`
enforcement), so periodically — and always before closing out a phase that
adds or changes database schema — run the same suite against a real
PostgreSQL database:

```bash
cd backend
export GRIDDEFENCE_TEST_DATABASE_URL="postgresql+psycopg://engineering_app:<password>@localhost:5432/engineering_platform_test"
pytest
```

Point this at a **dedicated test database** (see
[`docs/development/postgresql-setup.md`](docs/development/postgresql-setup.md)),
never at a real development database — the fixture calls
`Base.metadata.drop_all()` after every test.

---

## 11. Required Implementation Report Format

Every phase implementation ends with a report in this shape:

1. **Files created** — grouped by area (backend module, frontend module,
   migrations, tests).
2. **Files modified** — with a one-line reason for each.
3. **Alembic migrations** — revision id(s), what each creates/changes, how
   each was verified.
4. **Seed scripts** — what they seed, and confirmation of idempotency
   (safe to re-run).
5. **Backend tests** — what was added, grouped by the business rule each
   test covers.
6. **Frontend tests** — same, for frontend behaviour.
7. **Commands executed** — the literal commands run for verification
   (§10), not a paraphrase.
8. **Verification results** — pass/fail for each command in §7.
9. **Assumptions made** — anywhere the architecture left a detail open and
   a reasonable choice was made to proceed.
10. **Known limitations** — anything not fully verified (e.g. no Docker or
    PostgreSQL available in the environment) and what that means for
    follow-up.
11. **Architectural issues encountered** — any conflict surfaced per §9,
    whether resolved by a narrow implementation-detail choice or left open
    for the Project Owner.

This is the same structure used for the Phase 1 (IAM + Core Reference Data)
report — see [`CHANGELOG.md`](CHANGELOG.md) for the summarized outcome.

---

## 12. Related Documents

- [`.claude/CLAUDE.md`](.claude/CLAUDE.md) — governing engineering standard.
- [`docs/architecture/implementation-plan.md`](docs/architecture/implementation-plan.md) —
  phase sequence and per-phase scope.
- [`docs/adr/`](docs/adr/) — accepted architecture decisions.
- [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md) — what to check before
  accepting a phase as complete.
- [`CHANGELOG.md`](CHANGELOG.md) — what has actually shipped, phase by
  phase.
- [`docs/development/postgresql-setup.md`](docs/development/postgresql-setup.md) —
  PostgreSQL environment setup, connection verification, and the
  PostgreSQL-vs-SQLite testing workflow.
