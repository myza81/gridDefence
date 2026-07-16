"""Fixtures shared by every Continuous Evaluation Engine test."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.modules.continuous_evaluation import worker as worker_module
from app.modules.engineering_parameters.service import EngineeringParameterService
from app.modules.iam.service import IAMService


@pytest.fixture(autouse=True)
def _use_test_engine_for_worker(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """`worker.refresh_evaluation_projection` opens its own `SessionLocal()`
    session — the real, module-level `SessionLocal`, since an RQ job runs
    in a worker process outside any FastAPI request context. For tests,
    that module-level name is monkeypatched to a sessionmaker bound to
    the *same engine* `db_session` already uses, so the worker's writes
    are visible to test assertions — mirrors
    `psse_integration/tests/test_jobs.py`'s own established precedent
    exactly."""
    test_session_factory = sessionmaker(
        bind=db_session.bind, autoflush=False, autocommit=False, future=True
    )
    monkeypatch.setattr(worker_module, "SessionLocal", test_session_factory)


@pytest.fixture()
def actor_user_id(db_session: Session) -> uuid.UUID:
    """A plain, locally-authenticated IAM user — the service layer itself
    does not check permissions (CLAUDE.md §14), so no specific grant is
    needed for these service-level tests."""
    iam = IAMService(db_session)
    user = iam.create_user(
        username="continuous_evaluation_tester",
        display_name="Continuous Evaluation Tester",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    return user.user_id


@pytest.fixture()
def seeded_mw_tolerance(db_session: Session) -> str:
    """Seeds the one architecture-approved `mw_tolerance_percentage`
    parameter (ADR-021; continuous-evaluation-architecture.md §7) the same
    way the module's own bootstrap does — value "10", unit "percent" —
    through the one audited write path, `set_parameter_value`."""
    service = EngineeringParameterService(db_session)
    service.set_parameter_value(
        "mw_tolerance_percentage",
        value="10",
        unit="percent",
        description="Test-seeded MW tolerance.",
        change_reason="Continuous Evaluation Engine test setup.",
        actor_user_id=None,
    )
    db_session.commit()
    return "10"
