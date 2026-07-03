# PostgreSQL Development Environment Setup

This document lets a new developer reproduce GridDefence's PostgreSQL
environment from scratch, for local (non-Docker) backend development. It
supplements [`DEVELOPMENT.md`](../../DEVELOPMENT.md) and
[`README.md`](../../README.md) — read those first for the overall workflow;
this document is the detailed walkthrough for the database piece
specifically.

If you prefer Docker Compose instead of a native PostgreSQL install, skip to
[Alternative: Docker Compose](#alternative-docker-compose) — Docker Compose
provisions its own PostgreSQL container automatically and none of the manual
steps below apply.

---

## 1. Why a dedicated database and a dedicated application user

GridDefence uses a dedicated database (`engineering_platform`) and a
dedicated, least-privileged application role (`engineering_app`) — never the
default `postgres` database, and never the `postgres` superuser role for
day-to-day application connections.

This is not optional ceremony:

- **CLAUDE.md §17 (Principle of Least Privilege).** The application only
  ever needs to read/write its own schema. It has no legitimate need for
  superuser privileges (creating/dropping other databases, other roles,
  bypassing row-level security, etc.).
- **Isolation.** A dedicated database means GridDefence's schema never
  shares a namespace with anything else that might be installed on the same
  PostgreSQL server (other local projects, `pgAdmin` scratch tables, etc.).
- **Reproducibility.** `postgres`/`postgres` is what every tutorial uses by
  default; a project-specific name and role make it unambiguous which
  database belongs to GridDefence when a developer has several projects'
  databases on the same local PostgreSQL instance.

A separate **test** database (`engineering_platform_test`) is also
recommended — see [§9](#9-running-the-backend-pytest-suite-against-postgresql).
It exists because the test suite's `db_session` fixture calls
`Base.metadata.drop_all()` after every test when pointed at PostgreSQL; that
must never run against a database holding real development data.

---

## 2. Prerequisites

- PostgreSQL 16 or later, installed and running, reachable at `localhost:5432`
  (or wherever you configure `DATABASE_URL` to point).
- A way to run SQL as the PostgreSQL superuser (`psql`, pgAdmin, or
  equivalent) — needed only for the one-time setup in §3, not for day-to-day
  development afterward.

**Windows:** install via the [EnterpriseDB installer](https://www.postgresql.org/download/windows/)
or `winget install PostgreSQL.PostgreSQL.<version>`. The installer prompts
you to set the `postgres` superuser password during setup — remember it, you
need it for §3.

**macOS/Linux:** install via your platform's package manager
(`brew install postgresql@16`, `apt install postgresql`, etc.) per the
[official PostgreSQL documentation](https://www.postgresql.org/download/).

---

## 3. Database creation

Connect as the PostgreSQL superuser (`psql -U postgres`, pgAdmin, or
equivalent) and run the following, one statement at a time. Substitute your
own password where indicated — do not reuse a password from anywhere else,
and never commit it anywhere (see §5).

**3.1 — Create the application role:**

```sql
CREATE USER engineering_app WITH PASSWORD 'choose-your-own-local-password';
```

A plain `CREATE USER` (equivalent to `CREATE ROLE ... LOGIN`) grants no
special attributes — no `SUPERUSER`, no `CREATEDB`, no `CREATEROLE` — which
is exactly the least-privilege posture CLAUDE.md §17 calls for. See
[§4](#4-required-privileges) for why no further `GRANT` statements are
needed.

**3.2 — Create the application database, owned by that role:**

```sql
CREATE DATABASE engineering_platform OWNER engineering_app;
```

**3.3 — (Recommended) Create a dedicated test database, same owner:**

```sql
CREATE DATABASE engineering_platform_test OWNER engineering_app;
```

Only needed if you intend to run the backend test suite against real
PostgreSQL (§9) — the default SQLite-backed test run needs nothing here.

---

## 4. Required privileges

**No `GRANT` statements are required beyond the two `CREATE DATABASE ...
OWNER engineering_app` statements above.** Being the *owner* of a database
already grants full privileges on everything inside it (creating tables,
indexes, sequences; reading/writing/deleting rows; running Alembic
migrations) — PostgreSQL does not require separate schema-level or
table-level grants for a database's own owner.

`engineering_app` deliberately cannot: create or drop other databases,
create or alter other roles, or access any other database on the same
PostgreSQL instance it does not own. This is enforced by PostgreSQL itself,
not by application code — exactly the "enforced by the database, not just
application logic" posture CLAUDE.md §11.8 calls for.

---

## 5. DATABASE_URL format

```
postgresql+psycopg://<username>:<password>@<host>:<port>/<database>
```

For the setup above, connecting locally:

```
postgresql+psycopg://engineering_app:<your-password>@localhost:5432/engineering_platform
```

This goes in the repository-root `.env` (copy [`../../.env.example`](../../.env.example)
to `.env` if you have not already) — **`.env` is the single source of truth**
for both Docker Compose (which reads it automatically) and local backend
runs. `backend/app/core/config.py` resolves this file by an absolute path
computed from its own location, so it is found correctly regardless of
whether you run commands from the repository root or from `backend/` —
**do not create a second `backend/.env`**; there is exactly one `.env` for
this project.

`.env` is git-ignored (CLAUDE.md §22) — your password never leaves your
machine via source control.

---

## 6. Verifying the connection

From `backend/`, with `.venv` activated:

```bash
python -c "
from app.core.config import get_settings
from sqlalchemy import create_engine, text

engine = create_engine(get_settings().database_url)
with engine.connect() as conn:
    print(conn.execute(text('SELECT version()')).scalar())
"
```

If this prints a PostgreSQL version string, the connection works.

Then verify Alembic sees the same database:

```bash
alembic current
```

`Context impl PostgresqlImpl` in the output confirms Alembic is talking to
PostgreSQL, not silently falling back to anything else.

---

## 7. Alembic migration workflow

From `backend/`, with `.venv` activated and `DATABASE_URL` pointing at
`engineering_platform`:

```bash
alembic upgrade head          # apply all migrations
alembic current                 # show the current revision
alembic history                  # view the full migration chain
alembic downgrade -1              # roll back one revision
```

Every migration in this project is hand-reviewed (never blindly committed
from `--autogenerate`) and has a working `downgrade()` — see
[`DEVELOPMENT.md`](../../DEVELOPMENT.md) §8 for the full migration rules.

---

## 8. Running the backend against PostgreSQL

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

With `DATABASE_URL` in the root `.env` pointing at `engineering_platform`,
the backend now serves requests against real PostgreSQL rather than SQLite.

---

## 9. Running the backend pytest suite against PostgreSQL

By default, `pytest` uses SQLite in-memory (fast, no setup required) — this
is correct for day-to-day iteration. To run the same suite against real
PostgreSQL (recommended before closing out any phase that changes database
schema — see `DEVELOPMENT.md` §10):

```bash
cd backend
export GRIDDEFENCE_TEST_DATABASE_URL="postgresql+psycopg://engineering_app:<your-password>@localhost:5432/engineering_platform_test"
pytest
```

**Always point this at `engineering_platform_test` (§3.3), never at
`engineering_platform`.** The `db_session` fixture calls
`Base.metadata.drop_all()` after every test when this variable is set — safe
for a disposable test database, destructive against a database holding real
data.

Unset the variable (or open a new shell) to go back to the fast SQLite
default.

---

## 10. Troubleshooting common PostgreSQL issues

**`connection refused` / cannot connect to `localhost:5432`**
PostgreSQL is not running, or is listening on a different port. On Windows,
check the "postgresql-x64-&lt;version&gt;" service is started (Services app, or
`Get-Service postgresql*` in PowerShell). Confirm the port with
`netstat -an | grep 5432` (a `LISTENING` line on `5432` confirms it's up).

**`password authentication failed for user "engineering_app"`**
The password in `DATABASE_URL` does not match what you set in §3.1. There is
no way to recover a forgotten PostgreSQL role password — reset it as the
superuser: `ALTER USER engineering_app WITH PASSWORD 'new-password';`, then
update `.env` to match.

**`database "engineering_platform" does not exist`**
§3.2 was not run, or you're connecting to the wrong PostgreSQL instance
(check for a stray Docker Compose `postgres` container also listening on
`5432` — see §10.1 below).

**`permission denied to create database` / `permission denied for schema public`**
You're likely connected as a role other than `engineering_app`, or
`engineering_app` was not made the `OWNER` in §3.2. Re-run
`ALTER DATABASE engineering_platform OWNER TO engineering_app;` as the
superuser if ownership is wrong.

**Alembic reports `Target database is not up to date` or migration chain confusion**
Run `alembic current` and `alembic history` to see where the database
actually is, and reconcile against `backend/alembic/versions/`. Never edit a
previously committed migration to "fix" this — see `DEVELOPMENT.md` §8.

**`smallint out of range` or similar type errors that never happen on SQLite**
This is a real PostgreSQL-vs-SQLite behavioural difference, not a bug in
your setup — SQLite's flexible typing silently accepts values a strict
PostgreSQL column type (e.g. `SMALLINT`, max 32767) would reject outright.
This is exactly why `DEVELOPMENT.md` §10 recommends periodically running the
test suite against real PostgreSQL — see that section's "PostgreSQL
verification pass".

### 10.1 Port conflicts with Docker Compose

Both a native local PostgreSQL install and Docker Compose's `postgres`
service default to publishing port `5432`. If both are running at once,
Docker Compose will fail to start with a port-binding error. Stop your
native PostgreSQL service before running `docker compose up`, or vice versa
— they are two independent PostgreSQL instances (with independent data) and
are not intended to run simultaneously on the same machine.

---

## Alternative: Docker Compose

If you prefer not to install PostgreSQL natively, `docker compose up`
provisions its own PostgreSQL container automatically, using the
`POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB` values from your root
`.env` (defaulting to `engineering_app`/`changeme`/`engineering_platform` if
unset — see [`docker-compose.yml`](../../docker-compose.yml)). None of the
manual `CREATE USER`/`CREATE DATABASE` steps in §3 are needed in this case —
the official `postgres` Docker image bootstraps the role and database
automatically from those environment variables on first container start.
See [`README.md`](../../README.md) → "Running with Docker Compose" for the
full Docker workflow.
