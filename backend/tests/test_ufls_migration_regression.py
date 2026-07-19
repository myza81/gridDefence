"""Regression test for the UFLS `GET /api/v1/ufls/schemes` 500/CORS
incident (2026-07-16).

**Root cause:** the real development database's Alembic revision had never
been advanced past `0016_gm_zone` — six migrations behind, including
`0022_ufls`, which creates `ufls_scheme` and the other six UFLS tables. Every
UFLS endpoint therefore raised an unhandled `sqlalchemy.exc.ProgrammingError`
("relation \"ufls_scheme\" does not exist"), which Starlette's own
`ServerErrorMiddleware` (outside `CORSMiddleware` in the middleware stack —
`app/main.py`) converted into a bare 500 response that never passed back
through `CORSMiddleware`, explaining the browser's simultaneous, secondary
"missing Access-Control-Allow-Origin" complaint. CORS configuration itself
was never broken; the response simply never reached the middleware that
would have added the header. The fix is operational (running
`alembic upgrade head` against the affected database), not a code change —
`0022_ufls.py` itself was always correct (already verified in the original
UFLS phase's own completion report against a real PostgreSQL database).

**Why every other UFLS test would never have caught this:** every other test
in this suite builds its schema via `Base.metadata.create_all()`
(`backend/conftest.py`'s own `db_session` fixture), which is always fully
up to date with every model regardless of Alembic's own migration history —
it cannot reproduce "a real, already-existing database whose Alembic
revision lags behind the code." This test closes that specific gap: it
builds its schema by running the *real* Alembic migration chain (the exact
operation a deployment runs), then exercises the real UFLS API end-to-end
against the result, proving the migration chain itself produces a working,
queryable `ufls_scheme` table — not just that `Base.metadata` describes one.

Requires a real PostgreSQL database (`GRIDDEFENCE_TEST_DATABASE_URL`) —
skipped otherwise. Alembic's own migration chain is not verified against
SQLite anywhere else in this suite either (see `docs/development/
postgresql-setup.md`), since several migrations in the chain predate
UFLS and are not guaranteed SQLite-compatible.
"""

from __future__ import annotations

import os

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session as SessionType
from sqlalchemy.orm import sessionmaker

from alembic import command
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.ufls.bootstrap import run_bootstrap as bootstrap_ufls

# Reuses the exact same env var backend/conftest.py's own `db_session`
# fixture reads. conftest.py's own module-level `_assert_safe_for_destructive_
# testing` check already ran (once, at collection time) by the time this
# test executes, since conftest.py is always loaded first — this test
# performs no destructive-database-safety check of its own.
_POSTGRES_TEST_URL = os.environ.get("GRIDDEFENCE_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not _POSTGRES_TEST_URL,
    reason="Requires a real PostgreSQL database (GRIDDEFENCE_TEST_DATABASE_URL) "
    "to exercise the real Alembic migration chain, not Base.metadata.create_all().",
)


def _alembic_config_root() -> str:
    # backend/tests/ -> backend/
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_ufls_schemes_endpoint_works_after_running_real_alembic_migrations() -> None:
    """Builds the schema via `alembic upgrade head` (never
    `Base.metadata.create_all()`), then calls `GET /api/v1/ufls/schemes` as
    a real authenticated Administrator and asserts a normal 200 response
    with CORS headers present — the exact request/response pair the
    frontend made during the incident, now against a schema built the same
    way a real deployment builds one."""
    previous_database_url = os.environ.get("DATABASE_URL")
    engine = create_engine(_POSTGRES_TEST_URL)
    # Defensive: ensure a genuinely clean slate regardless of any prior
    # test's own teardown. `db_session`'s own fixture (used by every other
    # test) drops every table via `Base.metadata.drop_all()` after each
    # test, but that never touches `alembic_version` (it isn't part of
    # `Base.metadata`, by design — see conftest.py's own docstring). A
    # stale `alembic_version` row claiming "head" from a previous run would
    # make `command.upgrade(..., "head")` below a silent no-op, exactly
    # the "stamp exists, tables don't" state this incident's own root cause
    # investigation already had to work around manually — so this table is
    # dropped explicitly, not left to `Base.metadata.drop_all()`.
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
    Base.metadata.drop_all(bind=engine)

    session: SessionType | None = None
    try:
        os.environ["DATABASE_URL"] = _POSTGRES_TEST_URL
        get_settings.cache_clear()

        alembic_cfg = Config(os.path.join(_alembic_config_root(), "alembic.ini"))
        alembic_cfg.set_main_option(
            "script_location", os.path.join(_alembic_config_root(), "alembic")
        )
        command.upgrade(alembic_cfg, "head")

        # The real migration chain must have created every UFLS table --
        # the incident's own direct symptom.
        table_names = set(inspect(engine).get_table_names())
        assert "ufls_scheme" in table_names
        assert "ufls_scheme_version" in table_names

        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        session = session_factory()

        def _override_get_db():
            yield session

        app.dependency_overrides[get_db] = _override_get_db
        client = TestClient(app, raise_server_exceptions=False)

        bootstrap_iam(session)
        bootstrap_ufls(session)
        session.commit()

        settings = get_settings()
        login = client.post(
            "/api/v1/auth/login",
            json={
                "username": settings.bootstrap_admin_username,
                "password": settings.bootstrap_admin_password,
            },
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]

        response = client.get(
            "/api/v1/ufls/schemes",
            headers={"Authorization": f"Bearer {token}", "Origin": "http://localhost:5173"},
        )

        assert response.status_code == 200, response.text
        assert response.json() == []
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    finally:
        app.dependency_overrides.pop(get_db, None)
        if session is not None:
            session.close()
        Base.metadata.drop_all(bind=engine)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        engine.dispose()
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url
        get_settings.cache_clear()
