# GridDefence Changelog

This changelog records what has actually shipped, phase by phase, per
[`docs/architecture/implementation-plan.md`](docs/architecture/implementation-plan.md).
It is a factual record of implementation outcomes — not a design document.
Architecture rationale lives in `docs/architecture/` and `docs/adr/`;
day-to-day workflow lives in [`DEVELOPMENT.md`](DEVELOPMENT.md); review
criteria live in [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md).

Entries are added, never rewritten, as phases complete.

---

## Phase 2 — Substation Registry

**Scope:** The platform's master data anchor —
[`docs/architecture/substation-registry.md`](docs/architecture/substation-registry.md).

**Backend**

- `Substation`, `SubstationAlias`, `SubstationAuditLog` — model, repository,
  service, router, wired to Phase 1's IAM (`getUser`/`hasPermission`,
  `require_permission("substation_registry.write")`) for accountability and
  authorization.
- A shared, read-only Core Platform reference-data API
  (`app/reference_data/router.py`) — not owned by Substation Registry, added
  as a necessary prerequisite for populating create/edit form dropdowns,
  reusable by every future module.
- `substation_registry.read`/`substation_registry.write` permission codes
  registered in IAM's catalog and granted to the baseline
  Administrator/Engineer/Viewer roles.
- Alembic migration `0003_substation_registry`.

**Frontend**

- Substation list (TanStack Table, with region/status filtering and search),
  detail/edit view, create form, and status-change control, under
  `frontend/src/modules/substation_registry/`.

**Tests:** 45 backend service/bootstrap tests + 9 API contract tests + 8
frontend tests, covering mnemonic uniqueness (case-insensitive, incl.
historical-alias reuse), `substation_id` immutability, alias creation on
mnemonic change, geolocation pair validation, and soft-delete-only
enforcement.

**Architectural issue flagged, not resolved at the time:** substation-registry.md
§10's lifecycle diagram omitted the `UNDER_CONSTRUCTION` status entirely and
showed no direct `Active → Decommissioned` edge. Resolved conservatively for
this phase (closed allow-list of only the drawn edges) and explicitly
flagged for follow-up — see below.

### Phase 2 follow-up — lifecycle resolution and PostgreSQL verification

**Operational status lifecycle resolved via [ADR-005](docs/adr/ADR-005-substation-operational-status-lifecycle.md).**
substation-registry.md §10 revised to a seven-edge closed transition graph
restoring `Under Construction` to active use
(`Planned → Under Construction → Active`) and adding a direct
`Active → Decommissioned` edge (mothballing is not a mandatory
precondition of decommissioning). `Planned → Active` directly is no longer
legal — a behavioural change from this phase's original interim
implementation. Backend allow-list and 20 status-transition tests updated;
no frontend changes were needed (the UI never replicated the transition
graph client-side, by design — CLAUDE.md A12).

**PostgreSQL environment established as a permanent part of local
development** — dedicated `engineering_platform` database and
least-privileged `engineering_app` role (never the default `postgres`
database/superuser), documented in full in
[`docs/development/postgresql-setup.md`](docs/development/postgresql-setup.md).
A real, pre-existing configuration bug was found and fixed in the process:
`backend/app/core/config.py`'s `env_file=".env"` was a relative path,
resolved against the process's current working directory — meaning the
documented root `.env` was never actually read during local (non-Docker)
backend runs (`cd backend && uvicorn ...`/`pytest`), only during Docker
Compose (which injects real environment variables directly, bypassing the
file entirely). Fixed by resolving `.env` via an absolute path computed from
`config.py`'s own location.

**Full verification against real PostgreSQL 18** (migrations 0001–0003,
schema inspection, full pytest suite, `downgrade -1`/`upgrade head`
reversibility) — see `docs/development/postgresql-setup.md` §9 for the
opt-in `GRIDDEFENCE_TEST_DATABASE_URL` mechanism added to
`backend/conftest.py` to make this repeatable. Found and fixed one genuine
PostgreSQL-only defect: `voltage_level_id=99999` (and equivalent
out-of-range reference-data ids) is silently accepted by SQLite's flexible
integer typing but raises an unhandled `psycopg.errors.NumericValueOutOfRange`
on PostgreSQL's real `SMALLINT` columns — would have surfaced as a raw 500
error in production, never caught by SQLite-only testing. Fixed in
`app/reference_data/repository.py` by treating any id outside `SMALLINT`'s
representable range as "not found" before it reaches the database.

### Phase 2 UAT — ACCEPTED

Manually verified end-to-end through `localhost` against the real
PostgreSQL `engineering_platform` database (not SQLite) — see
`docs/development/postgresql-setup.md` for how that environment is set up.
Tested:

- Backend starts successfully.
- Frontend starts successfully.
- Login with the bootstrap Administrator account works.
- Substations page is accessible.
- Create substation works.
- Editing a substation's official name and mnemonic works.
- The created row is visible directly in the PostgreSQL table.
- Duplicate-mnemonic and duplicate-name validation both correctly reject.

**Phase 2 (Substation Registry) is ACCEPTED.** All required backend/frontend
tests pass, the operational status lifecycle gap is resolved (ADR-005), the
schema is verified against real PostgreSQL, and manual UAT confirms the
end-to-end flow works as built.

---

## Phase 1 — IAM + Core Reference Data

**Scope:** Identity and Access Management (local authentication only) and
the Core Platform reference/lookup tables, per
[`docs/architecture/iam-module.md`](docs/architecture/iam-module.md),
[`docs/adr/ADR-002-identity-and-access-management.md`](docs/adr/ADR-002-identity-and-access-management.md),
and `substation-registry.md` §6.

**Backend**

- IAM data model: `User`, `UserCredential`, `Role`, `Permission`,
  `RolePermission`, `UserRole`, `ExternalIdentityMapping`, `IAMAuditLog`.
- IAM service layer implementing the five interfaces named in
  `iam-module.md` §13: `hasPermission()` (fail-closed), `getUser()`,
  `resolveExternalPrincipal()`, `assertDifferentActors()`,
  `listUserRoles()` — plus user/role/permission CRUD and grant/revoke
  orchestration, each with audit writes.
- Local username/password authentication only. LDAP, Active Directory,
  OAuth, OIDC, MFA, and SSO are explicitly out of scope for this phase
  (structurally supported by `ExternalIdentityMapping`, not implemented).
- A stateless, HMAC-SHA256-signed bearer access token
  (`app/modules/iam/security.py`) — chosen because `iam-module.md` §4
  scopes the token mechanism itself as an implementation detail outside
  architectural scope, and no `Session` entity exists among IAM's owned
  entities.
- Idempotent bootstrap of the initial Administrator account, the baseline
  `Administrator`/`Engineer`/`Viewer` roles, and IAM's own permission
  catalog (`app/modules/iam/bootstrap.py`) — the bootstrap Administrator
  self-references its own `user_id` as creator and audit actor, a stronger
  realization of "never a null actor" than the architecture's stated
  minimum.
- Core Platform reference data: `voltage_level`, `region`, `state`,
  `grid_owner`, `operational_status`, seeded by an idempotent script
  (`app/reference_data/seed.py`).
- Alembic migration `0002_iam_and_core_reference_data` — hand-written (no
  live PostgreSQL reachable in the implementation environment to
  autogenerate against), manually reviewed, verified via `alembic upgrade
  head` → schema inspection → `alembic downgrade base` against a
  throwaway SQLite database as a stand-in.

**Frontend**

- Local login page, current-user display and sign-out (`AppShell`), role
  management, permission catalog management, and user↔role assignment
  UI, under `frontend/src/modules/iam/`.
- Client-side route gating (`ProtectedRoute`) and UI-only permission
  gating derived from the current user's granted permissions — the
  backend remains the sole authorization authority (CLAUDE.md A12); the
  frontend gate only decides what to *show*, never what to *allow*.

**Tests**

- Backend: 47 pytest tests covering fail-closed `hasPermission()`,
  username/role-name/external-identity uniqueness, role lifecycle
  (retired-role guard, revoke-not-delete, idempotent grants),
  authentication, bootstrap idempotency, reference data seed idempotency,
  and API-contract-level authorization enforcement.
- Frontend: 16 Vitest tests covering login success/failure, session
  handling (including a fix for a defect this test suite caught — see
  below), route protection, and permission-gated management UI.

**Defects found and fixed during this phase**

- A SQLite-only autoincrement incompatibility on reference-table primary
  keys (SQLite requires a literal `INTEGER PRIMARY KEY` for its
  rowid-autoincrement behaviour; `SMALLINT PRIMARY KEY` does not qualify)
  was found via the seed-idempotency test and fixed with a
  dialect-variant column type (`SMALLINT` on PostgreSQL, `INTEGER`
  elsewhere) applied identically to both the SQLAlchemy model and the
  Alembic migration.
- The frontend session handler originally cleared a valid access token on
  *any* failure of the `/users/me` request, including transient network
  errors — meaning a brief outage could silently sign a user out. Fixed
  to clear the token only on an explicit `401 Unauthorized` response;
  covered by a regression test.

**Known limitations**

- No Docker and no local PostgreSQL instance was reachable in the
  implementation environment; both the migration and the full test suite
  were verified against SQLite as a documented stand-in. The migration
  should still be run once against real PostgreSQL before being treated
  as final.
- Frontend styling is intentionally minimal — this phase prioritized
  correctness over visual design.

**Architectural issue surfaced**

- `implementation-plan.md` §6 mentions seeding "the MVP's grid codes,"
  but `substation-registry.md`'s canonical schema (the authoritative
  source for this phase) defines no `grid` table. Flagged during
  implementation and resolved by following `substation-registry.md`
  exactly — only the five documented reference tables were seeded, using
  region groupings rather than grid codes.

---

## Phase 0 — Repository Foundation

**Scope:** Project skeleton, tooling, and infrastructure — no business
modules — per `docs/architecture/implementation-plan.md`'s Phase 0
section.

**Backend**

- FastAPI application skeleton with an unversioned `/health` check and an
  empty versioned `/api/v1` router that later phases attach module
  routers to.
- SQLAlchemy `Base` declarative model shared by every future module.
- Alembic initialized with a single no-op baseline revision
  (`0001_initial_baseline`) establishing the migration chain without
  creating any domain tables.
- `backend/pyproject.toml` established as the single source of truth for
  backend dependencies (no `requirements.txt`); Ruff configured for
  linting and formatting; Pytest configured with per-module test
  discovery.
- Empty module packages created for every module named in
  `implementation-plan.md` §2 (`__init__.py` only) — no business logic.

**Frontend**

- Vite + React + TypeScript skeleton: `AppShell`, a `StatusPage` proving
  connectivity to the backend `/health` endpoint through TanStack Query,
  and a minimal `StatusBadge` UI primitive.
- `frontend/package.json` established as the single source of truth for
  frontend dependencies; ESLint, TypeScript strict checking, and Vitest
  configured.
- `src/modules/` established as the convention every future business
  module's frontend feature folder lands in.

**Infrastructure**

- `docker-compose.yml` defining `postgres`, `backend`, and `frontend`
  services — Postgres 16 with a persisted named volume, backend waiting
  for Postgres health before starting. The host's `.venv` is never
  mounted into any container.
- Project-local Python virtual environment convention established:
  `.venv` at the repository root, no global installs, `pip install -e
  "./backend[dev]"` as the standard setup command.
- `.env.example` documenting every environment variable with defaults; no
  secrets committed to source control.

**Tests**

- Backend smoke tests confirming the app starts and `/health` responds
  correctly, and that settings load from the environment without error.
- Frontend smoke test confirming the app shell renders the status page
  without crashing.

**Known limitations**

- No business logic, no domain models beyond Alembic's baseline revision,
  and no API endpoints beyond `/health` — by design, this phase is
  infrastructure only.
