"""Evaluation Projection lifecycle tests (this sprint's own instructions
§28): initial creation, status transitions, coalescing/deduplication,
generation-based concurrency safety, failure handling, and read-DTO
reconstruction.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.modules.continuous_evaluation.models import EvaluationProjection
from app.modules.continuous_evaluation.provider import EvaluationRequestProviderRegistry
from app.modules.continuous_evaluation.schemas import (
    EvaluationTarget,
    MwEvaluationInputs,
    ProjectionDetail,
    ProjectionStatus,
)
from app.modules.continuous_evaluation.service import ContinuousEvaluationService
from app.modules.continuous_evaluation.tests.synthetic_evaluation import (
    FakeEvaluationRequestProvider,
    RaisingEvaluationRequestProvider,
    RecordingExecutionEngine,
    synthetic_evaluation_request,
    synthetic_mw_group,
)
from app.modules.findings_publication_governance.findings import SchemeType


@pytest.fixture()
def target() -> EvaluationTarget:
    return EvaluationTarget(scheme_type=SchemeType.UFLS, scheme_version_id=uuid.uuid4())


def _service_with_provider(
    db_session: Session, target: EvaluationTarget, provider=None, *, execution_engine=None
) -> ContinuousEvaluationService:
    registry = EvaluationRequestProviderRegistry()
    registry.register(target.scheme_type, provider or FakeEvaluationRequestProvider())
    return ContinuousEvaluationService(
        db_session, provider_registry=registry, execution_engine=execution_engine
    )


class TestDirectExecutionModeEndToEnd:
    def test_request_refresh_via_the_real_default_execution_engine_completes_on_commit(
        self,
        db_session: Session,
        seeded_mw_tolerance: str,
        target: EvaluationTarget,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Regression test for a genuine self-deadlock this sprint's own
        PostgreSQL verification pass found: `execution_mode="direct"`
        (this platform's own default) runs the submitted job function
        immediately, in-process, on a *separate* database connection
        (`worker.py`'s own `SessionLocal()`). Enqueueing synchronously,
        before this transaction commits, deadlocked against that second
        connection on a real multi-connection database (invisible on
        SQLite's shared-connection `StaticPool` test setup — this test
        exercises the same code path but cannot, by itself, prove the
        deadlock is gone; that required the real-PostgreSQL run this
        sprint's own report documents). Deferring the actual submission
        to `self.db`'s own `after_commit` event (service.py's own
        `request_refresh` docstring) is the fix — this test confirms the
        deferred, real (uninjected) `DirectExecutionEngine` path still
        completes the full refresh end-to-end once committed."""
        # The deferred submission runs the *real* worker function, which
        # constructs its own `ContinuousEvaluationService(db)` using the
        # default (empty) provider registry — not this test's own
        # `service` object. Monkeypatch the one production composition
        # point, exactly as a real future scheme module's own bootstrap
        # would populate it (mirrors test_worker_queue_integration.py's
        # own `registered_fake_provider` fixture).
        from app.modules.continuous_evaluation import service as service_module

        registry = EvaluationRequestProviderRegistry()
        registry.register(target.scheme_type, FakeEvaluationRequestProvider())
        monkeypatch.setattr(service_module, "build_default_provider_registry", lambda: registry)

        # No `execution_engine` override — the real, default
        # `get_execution_engine()` (`DirectExecutionEngine` under this
        # test environment's own default settings).
        service = ContinuousEvaluationService(db_session)

        result = service.request_refresh(target, trigger="test")
        assert result.enqueued is True
        assert result.job_id is not None

        db_session.commit()  # fires the deferred submission

        db_session.expire_all()
        projection = db_session.query(EvaluationProjection).one()
        assert projection.status == ProjectionStatus.CURRENT
        assert projection.last_result_snapshot is not None


class TestRequestRefreshCreatesAndCoalesces:
    def test_first_request_creates_a_stale_projection_and_enqueues(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        # `RecordingExecutionEngine` always returns a job_id (unlike the
        # default `DirectExecutionEngine`, which never produces one since
        # it runs immediately, in-process — this test is about the
        # enqueue *decision*, not about which execution mode is active).
        recorder = RecordingExecutionEngine()
        service = _service_with_provider(db_session, target, execution_engine=recorder)
        result = service.request_refresh(target, trigger="test.trigger")

        assert result.status == ProjectionStatus.STALE
        assert result.generation == 1
        assert result.enqueued is True
        assert result.job_id is not None

    def test_repeated_requests_before_any_worker_claim_coalesce(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        recorder = RecordingExecutionEngine()
        service = _service_with_provider(db_session, target, execution_engine=recorder)

        first = service.request_refresh(target, trigger="a")
        second = service.request_refresh(target, trigger="b")
        third = service.request_refresh(target, trigger="c")

        assert first.enqueued is True
        assert second.enqueued is False
        assert third.enqueued is False
        assert second.generation == 2
        assert third.generation == 3
        # The actual submission is deferred to `self.db`'s own
        # `after_commit` event (service.py's own `request_refresh`
        # docstring).
        db_session.commit()
        # Exactly one job was ever actually submitted.
        assert len(recorder.calls) == 1

    def test_request_while_recalculating_bumps_generation_without_enqueueing(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        recorder = RecordingExecutionEngine()
        service = _service_with_provider(db_session, target, execution_engine=recorder)
        service.request_refresh(target, trigger="first")

        # Manually move the projection into RECALCULATING, simulating a
        # worker having claimed it.
        projection = db_session.query(EvaluationProjection).one()
        projection.status = ProjectionStatus.RECALCULATING
        db_session.flush()

        result = service.request_refresh(target, trigger="second")
        assert result.enqueued is False
        assert result.generation == 2
        db_session.commit()
        assert len(recorder.calls) == 1

    def test_current_projection_transitions_back_to_stale_and_enqueues(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        service = _service_with_provider(db_session, target)
        service.request_refresh(target, trigger="first")
        service.run_refresh_worker_cycle(
            target, requested_generation=1, trigger="first", correlation_id=None
        )
        projection = db_session.query(EvaluationProjection).one()
        assert projection.status == ProjectionStatus.CURRENT

        result = service.request_refresh(target, trigger="second")
        assert result.status == ProjectionStatus.STALE
        assert result.generation == 2
        assert result.enqueued is True

    def test_failed_projection_transitions_back_to_stale_and_enqueues(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        service = _service_with_provider(
            db_session, target, provider=RaisingEvaluationRequestProvider()
        )
        service.request_refresh(target, trigger="first")
        service.run_refresh_worker_cycle(
            target, requested_generation=1, trigger="first", correlation_id=None
        )
        projection = db_session.query(EvaluationProjection).one()
        assert projection.status == ProjectionStatus.FAILED

        result = service.request_refresh(target, trigger="second")
        assert result.status == ProjectionStatus.STALE
        assert result.enqueued is True


class TestWorkerCycleSuccess:
    def test_successful_cycle_marks_current_and_stores_result(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        request = synthetic_evaluation_request(
            scheme_type=target.scheme_type,
            scheme_version_id=target.scheme_version_id,
            mw_inputs=MwEvaluationInputs(
                groups=[synthetic_mw_group(reference_mw=Decimal("100"), current_mw=Decimal("50"))]
            ),
        )
        service = _service_with_provider(
            db_session, target, provider=FakeEvaluationRequestProvider(request)
        )
        service.request_refresh(target, trigger="test")
        service.run_refresh_worker_cycle(
            target, requested_generation=1, trigger="test", correlation_id=None
        )

        projection = db_session.query(EvaluationProjection).one()
        assert projection.status == ProjectionStatus.CURRENT
        assert projection.evaluated_at is not None
        assert projection.recalculation_completed_at is not None
        assert projection.last_result_snapshot is not None
        assert len(projection.last_result_snapshot["findings"]) == 1

    def test_worker_cycle_is_a_no_op_when_no_projection_exists(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        service = _service_with_provider(db_session, target)
        # No request_refresh was ever called — simulates the outbox-
        # problem case (the enqueueing transaction rolled back).
        service.run_refresh_worker_cycle(
            target, requested_generation=1, trigger="test", correlation_id=None
        )
        assert db_session.query(EvaluationProjection).count() == 0

    def test_worker_cycle_is_a_no_op_when_already_recalculating(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        service = _service_with_provider(db_session, target)
        service.request_refresh(target, trigger="test")
        projection = db_session.query(EvaluationProjection).one()
        projection.status = ProjectionStatus.RECALCULATING
        projection.recalculation_started_at = projection.recalculation_requested_at
        db_session.commit()

        # A second, concurrent claim attempt for the same target.
        service.run_refresh_worker_cycle(
            target, requested_generation=1, trigger="test", correlation_id=None
        )
        db_session.refresh(projection)
        # Still RECALCULATING — the second call was a safe no-op, not a
        # second concurrent evaluation.
        assert projection.status == ProjectionStatus.RECALCULATING
        assert projection.last_result_snapshot is None


class TestWorkerCycleFailure:
    def test_provider_failure_marks_failed_with_error_metadata(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        service = _service_with_provider(
            db_session, target, provider=RaisingEvaluationRequestProvider()
        )
        service.request_refresh(target, trigger="test")
        service.run_refresh_worker_cycle(
            target, requested_generation=1, trigger="test", correlation_id=None
        )

        projection = db_session.query(EvaluationProjection).one()
        assert projection.status == ProjectionStatus.FAILED
        assert projection.last_error is not None
        assert "synthetic provider failure" in projection.last_error
        assert projection.last_error_at is not None

    def test_missing_engineering_parameter_is_a_failure_not_a_finding(
        self, db_session: Session, target: EvaluationTarget
    ) -> None:
        # No `seeded_mw_tolerance` fixture used here — the parameter is
        # deliberately absent.
        service = _service_with_provider(db_session, target)
        service.request_refresh(target, trigger="test")
        service.run_refresh_worker_cycle(
            target, requested_generation=1, trigger="test", correlation_id=None
        )
        projection = db_session.query(EvaluationProjection).one()
        assert projection.status == ProjectionStatus.FAILED
        assert projection.last_result_snapshot is None

    def test_no_registered_provider_is_a_failure(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        service = ContinuousEvaluationService(
            db_session, provider_registry=EvaluationRequestProviderRegistry()
        )
        service.request_refresh(target, trigger="test")
        service.run_refresh_worker_cycle(
            target, requested_generation=1, trigger="test", correlation_id=None
        )
        projection = db_session.query(EvaluationProjection).one()
        assert projection.status == ProjectionStatus.FAILED
        assert "NoEvaluationRequestProviderError" in projection.last_error or (
            "No EvaluationRequestProvider" in projection.last_error
        )

    def test_failure_preserves_previous_successful_result(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        good_request = synthetic_evaluation_request(
            scheme_type=target.scheme_type, scheme_version_id=target.scheme_version_id
        )
        provider = FakeEvaluationRequestProvider(good_request)
        service = _service_with_provider(db_session, target, provider=provider)
        service.request_refresh(target, trigger="ok")
        service.run_refresh_worker_cycle(
            target, requested_generation=1, trigger="ok", correlation_id=None
        )
        projection = db_session.query(EvaluationProjection).one()
        first_snapshot = projection.last_result_snapshot
        assert projection.status == ProjectionStatus.CURRENT

        # Swap in a failing provider and trigger another refresh.
        provider._request = None
        failing_service = _service_with_provider(
            db_session, target, provider=RaisingEvaluationRequestProvider()
        )
        failing_service.request_refresh(target, trigger="fails")
        failing_service.run_refresh_worker_cycle(
            target, requested_generation=2, trigger="fails", correlation_id=None
        )
        db_session.refresh(projection)
        assert projection.status == ProjectionStatus.FAILED
        # The last *successful* snapshot is preserved, not wiped.
        assert projection.last_result_snapshot == first_snapshot


class TestGenerationMismatchConcurrency:
    def test_newer_generation_arriving_mid_run_leaves_projection_stale_and_reenqueues(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        """The critical concurrency case (this sprint's own instructions
        §15-16): a `request_refresh` call arrives *while* a worker cycle
        is evaluating (simulated here via a provider that itself calls
        `request_refresh` as a side effect of `build_request`, exactly
        modelling "a new event arrived mid-recalculation"). The
        in-progress cycle must not falsely mark `CURRENT`."""
        recorder = RecordingExecutionEngine()
        registry = EvaluationRequestProviderRegistry()
        service = ContinuousEvaluationService(
            db_session, provider_registry=registry, execution_engine=recorder
        )

        class _MidFlightInvalidatingProvider:
            def build_request(self, target: EvaluationTarget, *, trigger: str):
                # Simulates a concurrent invalidation arriving while this
                # worker cycle is already RECALCULATING.
                service.request_refresh(target, trigger="concurrent.invalidation")
                return synthetic_evaluation_request(
                    scheme_type=target.scheme_type, scheme_version_id=target.scheme_version_id
                )

        registry.register(target.scheme_type, _MidFlightInvalidatingProvider())

        service.request_refresh(target, trigger="initial")
        # Commit now, exactly as a real caller would before a separate
        # worker process ever picks up the job — this fires the initial
        # request's own deferred submission (service.py's own
        # `request_refresh` docstring) on *this* session, so it does not
        # unexpectedly re-fire later when the worker cycle below commits
        # its own claim step on this same (test-only, shared) session.
        db_session.commit()
        recorder.calls.clear()  # only interested in what happens during the cycle itself

        service.run_refresh_worker_cycle(
            target, requested_generation=1, trigger="initial", correlation_id=None
        )

        projection = db_session.query(EvaluationProjection).one()
        # Never falsely CURRENT — a newer generation (2) exists relative
        # to what this cycle started with (1).
        assert projection.status == ProjectionStatus.STALE
        assert projection.generation == 2
        assert projection.last_result_snapshot is not None  # the (correct, as-of-then) result
        # Exactly one reconciliation job was enqueued to converge.
        assert len(recorder.calls) == 1


class TestGetProjection:
    def test_returns_none_when_no_projection_exists(
        self, db_session: Session, target: EvaluationTarget
    ) -> None:
        service = _service_with_provider(db_session, target)
        assert service.get_projection(target) is None

    def test_returns_detail_reconstructed_from_storage(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        service = _service_with_provider(db_session, target)
        service.request_refresh(target, trigger="test")
        service.run_refresh_worker_cycle(
            target, requested_generation=1, trigger="test", correlation_id=None
        )

        detail = service.get_projection(target)
        assert detail is not None
        assert detail.status == ProjectionStatus.CURRENT
        assert detail.scheme_type == target.scheme_type
        assert detail.scheme_version_id == target.scheme_version_id
        assert detail.last_result is not None
        assert detail.last_result.scheme_version_id == target.scheme_version_id

    def test_projection_is_disposable_and_non_authoritative(
        self, db_session: Session, seeded_mw_tolerance: str, target: EvaluationTarget
    ) -> None:
        """No engineering decision is ever read from the projection
        itself — it carries no policy/acknowledgement/publication
        fields (this sprint's own instructions §5, §19)."""
        detail_fields = set(ProjectionDetail.model_fields.keys())
        assert "resolved_treatment" not in detail_fields
        assert "acknowledgement_required" not in detail_fields
        assert "publication_record_id" not in detail_fields
