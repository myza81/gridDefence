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
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.main import app

# Import every module's models so they register with Base.metadata before
# create_all runs — mirrors alembic/env.py's own import block.
from app.modules.iam import models as iam_models  # noqa: F401
from app.modules.substation_registry import models as substation_registry_models  # noqa: F401
from app.reference_data import models as reference_data_models  # noqa: F401

_POSTGRES_TEST_URL = os.environ.get("GRIDDEFENCE_TEST_DATABASE_URL")


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
