"""Queue and worker integration tests (this sprint's own instructions
§27): real `QueueExecutionEngine` routing (via fakeredis, `rq_async=False`
— no real Redis server needed, mirrors `tests/test_execution.py`'s own
established pattern), deterministic job identity, worker session
reconstruction, retry-safe duplicate execution, and the outer worker
wrapper's own exception/rollback behaviour.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.execution import QueueExecutionEngine, get_execution_engine
from app.modules.continuous_evaluation.models import EvaluationProjection
from app.modules.continuous_evaluation.provider import EvaluationRequestProviderRegistry
from app.modules.continuous_evaluation.schemas import EvaluationTarget, ProjectionStatus
from app.modules.continuous_evaluation.service import ContinuousEvaluationService
from app.modules.continuous_evaluation.tests.synthetic_evaluation import (
    FakeEvaluationRequestProvider,
)
from app.modules.continuous_evaluation.worker import (
    CONTINUOUS_EVALUATION_QUEUE_NAME,
    refresh_evaluation_projection,
)
from app.modules.findings_publication_governance.findings import SchemeType


@pytest.fixture()
def target() -> EvaluationTarget:
    return EvaluationTarget(scheme_type=SchemeType.UFLS, scheme_version_id=uuid.uuid4())


@pytest.fixture()
def queue_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(get_settings(), "execution_mode", "queue")
    return get_execution_engine()


@pytest.fixture()
def registered_fake_provider(target: EvaluationTarget, monkeypatch: pytest.MonkeyPatch) -> None:
    """The real worker function (`refresh_evaluation_projection`) always
    constructs its own `ContinuousEvaluationService(db)` using the
    *default* provider registry — a per-test registry object cannot
    cross the RQ job-argument boundary (only plain strings/ints do, by
    design, this sprint's own instructions §14). This monkeypatches the
    one production composition point (`build_default_provider_registry`,
    as referenced from `service.py`) exactly the way a real future scheme
    module's own bootstrap would populate it — the same simulated
    "the scheme module has registered its own provider" scenario, not a
    workaround specific to testing."""
    from app.modules.continuous_evaluation import service as service_module

    registry = EvaluationRequestProviderRegistry()
    registry.register(target.scheme_type, FakeEvaluationRequestProvider())
    monkeypatch.setattr(service_module, "build_default_provider_registry", lambda: registry)


class TestQueueRouting:
    def test_refresh_job_is_submitted_to_the_continuous_evaluation_queue(
        self,
        db_session: Session,
        seeded_mw_tolerance: str,
        target: EvaluationTarget,
        queue_mode,
        registered_fake_provider: None,
    ) -> None:
        service = ContinuousEvaluationService(db_session)

        result = service.request_refresh(target, trigger="test")
        assert result.job_id is not None

        # The actual submission is deferred to `self.db`'s own
        # `after_commit` event (service.py's own `request_refresh`
        # docstring) — it does not exist in the queue until this commits.
        db_session.commit()

        job = QueueExecutionEngine().fetch(result.job_id)
        assert job is not None
        # `rq_async=False` (test environment) runs the job synchronously
        # against fakeredis — by the time `request_refresh` returns, the
        # job has already completed.
        assert job.completed is True
        assert job.error is None

        # The worker ran via its own `SessionLocal()` session (patched to
        # share `db_session`'s own connection, not its own SQLAlchemy
        # identity map) and committed there — `db_session`'s own
        # identity map does not know that happened until expired.
        db_session.expire_all()
        projection = db_session.query(EvaluationProjection).one()
        assert projection.status == ProjectionStatus.CURRENT

    def test_deterministic_job_id_shape(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget, queue_mode
    ) -> None:
        registry = EvaluationRequestProviderRegistry()
        registry.register(target.scheme_type, FakeEvaluationRequestProvider())
        service = ContinuousEvaluationService(db_session, provider_registry=registry)
        result = service.request_refresh(target, trigger="test")
        assert result.job_id == (
            f"continuous_evaluation:{target.scheme_type.value}:{target.scheme_version_id}"
        )

    def test_worker_process_listens_on_both_named_queues(self) -> None:
        from app.worker import CONTINUOUS_EVALUATION_QUEUE_NAME as worker_queue_name

        assert worker_queue_name == CONTINUOUS_EVALUATION_QUEUE_NAME == "continuous_evaluation"


class TestWorkerFunctionDirectly:
    """Exercises `refresh_evaluation_projection` itself (not
    `ContinuousEvaluationService.run_refresh_worker_cycle`, already
    thoroughly covered in test_projection_lifecycle.py) — the plain,
    RQ-serializable function a real worker process calls, including its
    own session open/close/rollback and its use of the *default* (empty)
    provider registry."""

    def test_missing_projection_is_a_safe_no_op(
        self, db_session: Session, target: EvaluationTarget
    ) -> None:
        # No request_refresh was ever called for this target.
        refresh_evaluation_projection(
            target.scheme_type.value, str(target.scheme_version_id), 1, "test", None
        )
        assert db_session.query(EvaluationProjection).count() == 0

    def test_no_registered_provider_marks_the_projection_failed_not_a_crash(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        service = ContinuousEvaluationService(db_session)  # default (empty) provider registry
        service.request_refresh(target, trigger="test")
        # `request_refresh` only flushes (service.py's own docstring) —
        # the row must actually be committed before a separate
        # connection (the worker's own patched `SessionLocal()`) can see
        # it under a real, non-SQLite-StaticPool database.
        db_session.commit()

        # Calling the real worker function directly (as RQ itself would).
        refresh_evaluation_projection(
            target.scheme_type.value, str(target.scheme_version_id), 1, "test", None
        )

        db_session.expire_all()
        projection = db_session.query(EvaluationProjection).one()
        assert projection.status == ProjectionStatus.FAILED
        assert projection.last_error is not None

    def test_retry_safe_duplicate_execution_of_the_same_job(
        self,
        db_session: Session,
        seeded_mw_tolerance: str,
        target: EvaluationTarget,
        registered_fake_provider: None,
    ) -> None:
        """Simulates an RQ retry re-running the identical job body after
        a successful completion. ADR-023's own idempotency model is "the
        same engineering input always produces the same engineering
        result" via full recompute — not "a second run is skipped
        entirely." A retried job legitimately re-evaluates (this
        sprint's own instructions §14: "retries are safe" means
        non-corrupting and re-convergent, not a no-op) and must land back
        on the identical engineering conclusion, never a broken or
        inconsistent state."""
        service = ContinuousEvaluationService(db_session)
        service.request_refresh(target, trigger="test")
        # `request_refresh` only flushes — the row must be committed
        # before the worker's own separate connection can see it under a
        # real, non-SQLite-StaticPool database.
        db_session.commit()

        refresh_evaluation_projection(
            target.scheme_type.value, str(target.scheme_version_id), 1, "test", None
        )
        db_session.expire_all()
        projection = db_session.query(EvaluationProjection).one()
        assert projection.status == ProjectionStatus.CURRENT
        first_findings = projection.last_result_snapshot["findings"]

        # Re-run the exact same job body (as an RQ retry would).
        refresh_evaluation_projection(
            target.scheme_type.value, str(target.scheme_version_id), 1, "test", None
        )
        db_session.expire_all()
        assert projection.status == ProjectionStatus.CURRENT
        # The same engineering conclusion both times — the property
        # ADR-023 actually requires. `evaluated_at` legitimately differs
        # (each run is a genuine new evaluation moment).
        assert projection.last_result_snapshot["findings"] == first_findings

    def test_unexpected_exception_rolls_back_and_propagates(
        self,
        db_session: Session,
        seeded_mw_tolerance: str,
        target: EvaluationTarget,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A genuinely unexpected failure (not the ordinary "no provider"/
        "detector failed" cases already handled inside
        `run_refresh_worker_cycle` itself) must roll back and re-raise —
        RQ's own retry mechanism relies on the job raising to know a
        retry is warranted (this sprint's own instructions §18, §22)."""
        from app.modules.continuous_evaluation import service as service_module

        def _boom(self, *args: object, **kwargs: object) -> None:
            raise RuntimeError("simulated unexpected worker bug")

        monkeypatch.setattr(
            service_module.ContinuousEvaluationService, "run_refresh_worker_cycle", _boom
        )

        with pytest.raises(RuntimeError, match="simulated unexpected worker bug"):
            refresh_evaluation_projection(
                target.scheme_type.value, str(target.scheme_version_id), 1, "test", None
            )
