"""Shared pytest fixtures for every test under tests/ and app/*/tests/.

By default, uses SQLite in-memory as a fast, dependency-free stand-in —
exercising the same SQLAlchemy models and Alembic-equivalent schema
(app.db.base.Base.metadata) rather than any hand-duplicated test schema.
Each test gets its own fresh in-memory database so tests never leak state
into one another.

Set GRIDDEFENCE_TEST_DATABASE_URL to run the same suite against a real
PostgreSQL database instead (see docs/development/postgresql-setup.md) —
e.g. for the periodic full-fidelity verification pass CLAUDE.md A11/DEVELOPMENT.md
call for, catching PostgreSQL-specific behaviour SQLite cannot reproduce
(case-insensitive functional indexes, real FK RESTRICT enforcement, native
UUID/TIMESTAMPTZ types). Point this at a *dedicated test database*, never at
a real development database — this fixture drops all tables after every test.

**Safety incident (Development Database Recovery, see the incident's own
completion report):** `GRIDDEFENCE_TEST_DATABASE_URL` was once pointed at the
same database as `DATABASE_URL` — this fixture's own `drop_all()` teardown
then destroyed every application table in the real development database,
with no backup. `_assert_safe_for_destructive_testing`, below, is the
fail-closed guard this incident produced: PostgreSQL mode now refuses to run
at all — before creating or dropping a single table — unless every one of
its checks passes. This is deliberately strict, not merely documented
convention; a warning in a docstring was already proven insufficient.
"""

from __future__ import annotations

import os
from collections.abc import Generator

# Must be set before `app.core.config.get_settings()` is ever called (the
# `from app.main import app` import below triggers that indirectly) — RQ
# jobs (PSS/E Integration, Phase 4) then run synchronously, in-process,
# against a `fakeredis` connection (app.core.queue.get_redis_connection),
# so the test suite needs no real Redis server or worker process.
os.environ.setdefault("RQ_ASYNC", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Import every module's models so they register with Base.metadata before
# create_all runs — mirrors alembic/env.py's own import block.
from app.modules.iam import models as iam_models  # noqa: F401
from app.modules.substation_registry import models as substation_registry_models  # noqa: F401
from app.reference_data import models as reference_data_models  # noqa: F401

_POSTGRES_TEST_URL = os.environ.get("GRIDDEFENCE_TEST_DATABASE_URL")

# The one documented, canonical GridDefence development database name
# (docs/development/postgresql-setup.md §3.2, .env.example) — refused
# unconditionally, regardless of what GRIDDEFENCE_TEST_DATABASE_URL's own
# name looks like, as a hard-coded extra layer independent of naming
# convention alone (the incident this guard exists for used exactly this
# database name).
_KNOWN_DEVELOPMENT_DATABASE_NAMES = frozenset({"engineering_platform"})

# Created (raw SQL, deliberately outside `Base.metadata`, so `drop_all()`
# never removes it) the first time a URL passes every other check below —
# proof, on every later run, that this specific database was genuinely
# provisioned for disposable, destructive testing, not just named
# plausibly. Mirrors `alembic_version`'s own "survives drop_all because
# it isn't part of Base.metadata" property.
_TEST_DB_MARKER_TABLE = "_griddefence_test_database_marker"


def _connection_summary(url_str: str) -> str:
    """Host and database name only — never the password, never the full
    URL (CLAUDE.md A10). A guard's own error message is exactly the kind
    of place a credential could otherwise leak into a CI log or a
    developer's terminal scrollback."""
    url = make_url(url_str)
    return f"{url.host}:{url.port}/{url.database}"


def _assert_safe_for_destructive_testing(url_str: str) -> None:
    """Fail-closed guard for PostgreSQL test mode. Every check below must
    pass before this module lets `db_session` create a single table —
    let alone drop one — against `url_str`. Raises `RuntimeError`,
    aborting pytest collection itself, on the first unmet condition."""
    url = make_url(url_str)
    database_name = url.database or ""
    problems: list[str] = []

    if not database_name.endswith("_test"):
        problems.append(
            f"database name '{database_name}' does not end in '_test' "
            "(e.g. engineering_platform_test)"
        )

    development_database_name = None
    try:
        development_database_name = make_url(get_settings().database_url).database
    except Exception:
        pass
    if development_database_name and database_name == development_database_name:
        problems.append(
            "database name is identical to the application's own configured "
            "DATABASE_URL — this would run destructive tests against the "
            "development database"
        )

    if database_name in _KNOWN_DEVELOPMENT_DATABASE_NAMES:
        problems.append(
            f"'{database_name}' is a known GridDefence development database "
            "name (docs/development/postgresql-setup.md §3.2) — refused "
            "unconditionally regardless of GRIDDEFENCE_TEST_DATABASE_URL's "
            "own naming"
        )

    if os.environ.get("GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE", "").strip().lower() != "true":
        problems.append(
            "GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE=true was not set — "
            "required, explicit acknowledgement that this run will drop "
            "every table in the target database after every test"
        )

    if problems:
        raise RuntimeError(
            "Refusing to run destructive PostgreSQL tests against "
            f"{_connection_summary(url_str)}:\n  - "
            + "\n  - ".join(problems)
            + "\nPoint GRIDDEFENCE_TEST_DATABASE_URL at a dedicated, disposable "
            "test database (e.g. engineering_platform_test, created per "
            "docs/development/postgresql-setup.md §3.3), never at the "
            "database DATABASE_URL points to, and set "
            "GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE=true to confirm "
            "you mean it."
        )

    # Every naming/URL-shape check above passed — one more, structural
    # check: a database that merely looks like a test database (right
    # name, right acknowledgement variable) but was never actually
    # provisioned as one still is not trusted blindly. It must either be
    # genuinely empty (first-ever run — the marker is created now, below)
    # or already carry this fixture's own marker from a prior run.
    #
    # Uses `sqlalchemy.inspect()` rather than a raw `information_schema`
    # query so this exact function is dialect-agnostic and can be
    # exercised directly, in tests, against a disposable SQLite file —
    # never against a real PostgreSQL database — see
    # tests/test_destructive_test_database_guard.py.
    engine = create_engine(url_str)
    try:
        with engine.connect() as conn:
            existing_tables = inspect(engine).get_table_names()
            if _TEST_DB_MARKER_TABLE in existing_tables:
                return
            if existing_tables:
                raise RuntimeError(
                    "Refusing to run destructive PostgreSQL tests against "
                    f"{_connection_summary(url_str)}: this database already "
                    f"contains {len(existing_tables)} table(s) but has never "
                    f"been provisioned with this fixture's own marker table "
                    f"('{_TEST_DB_MARKER_TABLE}'). If this is genuinely a "
                    "disposable test database, drop and recreate it empty "
                    "and let this fixture provision the marker itself."
                )
            conn.execute(
                text(f"CREATE TABLE {_TEST_DB_MARKER_TABLE} (provisioned_at TIMESTAMP NOT NULL)")
            )
            conn.execute(text(f"INSERT INTO {_TEST_DB_MARKER_TABLE} VALUES (CURRENT_TIMESTAMP)"))
            conn.commit()
    finally:
        engine.dispose()


if _POSTGRES_TEST_URL:
    _assert_safe_for_destructive_testing(_POSTGRES_TEST_URL)


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    if _POSTGRES_TEST_URL:
        engine = create_engine(_POSTGRES_TEST_URL)
    else:
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    Base.metadata.create_all(bind=engine)

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        if _POSTGRES_TEST_URL:
            Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """A TestClient whose `get_db` dependency is overridden to hand out the
    same isolated `db_session` used directly by any fixture-level setup in
    the test (e.g. seeding a user before exercising an endpoint).
    """

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
