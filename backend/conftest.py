"""Shared pytest fixtures for every test under tests/ and app/*/tests/.

No live PostgreSQL is reachable in this environment (no Docker, no local
PostgreSQL install — see Phase 1's final report); SQLite in-memory is used
here as a pragmatic stand-in, exercising the same SQLAlchemy models and
Alembic-equivalent schema (app.db.base.Base.metadata) rather than any
hand-duplicated test schema. Each test gets its own fresh in-memory database
so tests never leak state into one another.
"""

from __future__ import annotations

from collections.abc import Generator

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
from app.reference_data import models as reference_data_models  # noqa: F401


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
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
