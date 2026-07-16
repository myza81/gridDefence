"""Platform event contract and consumer tests (this sprint's own
instructions §29): envelope validation, immutability, affected-target
resolution, deterministic deduplication, and confirmation that no
engineering calculation ever runs inside the event-consumer path itself.
"""

from __future__ import annotations

import uuid

import pydantic
import pytest
from sqlalchemy.orm import Session

from app.modules.continuous_evaluation.schemas import EvaluationTarget
from app.modules.continuous_evaluation.service import ContinuousEvaluationService
from app.modules.continuous_evaluation.tests.synthetic_evaluation import (
    FakeAffectedSchemeResolver,
    RecordingExecutionEngine,
    synthetic_change_descriptor,
)
from app.modules.findings_publication_governance.findings import SchemeType


class TestChangeDescriptorValidation:
    def test_valid_descriptor_shape_is_accepted(self) -> None:
        event = synthetic_change_descriptor(
            descriptor="substation_registry.substation.status_changed"
        )
        assert event.descriptor == "substation_registry.substation.status_changed"

    @pytest.mark.parametrize(
        "bad_descriptor",
        ["not_namespaced", "only.two", "trailing.dot.", ".leading.dot", "a..b.c", ""],
    )
    def test_malformed_descriptor_is_rejected(self, bad_descriptor: str) -> None:
        with pytest.raises(pydantic.ValidationError):
            synthetic_change_descriptor(descriptor=bad_descriptor)

    def test_change_descriptor_is_frozen(self) -> None:
        event = synthetic_change_descriptor()
        with pytest.raises(pydantic.ValidationError):
            event.descriptor = "something.else.changed"  # type: ignore[misc]


class TestNotifySourceDataChanged:
    def test_zero_affected_targets_returns_empty_list(self, db_session: Session) -> None:
        service = ContinuousEvaluationService(db_session, resolver=FakeAffectedSchemeResolver([]))
        results = service.notify_source_data_changed(synthetic_change_descriptor())
        assert results == []

    def test_one_affected_target_produces_one_refresh_result(self, db_session: Session) -> None:
        target = EvaluationTarget(scheme_type=SchemeType.UFLS, scheme_version_id=uuid.uuid4())
        recorder = RecordingExecutionEngine()
        service = ContinuousEvaluationService(
            db_session,
            resolver=FakeAffectedSchemeResolver([target]),
            execution_engine=recorder,
        )
        results = service.notify_source_data_changed(synthetic_change_descriptor())
        assert len(results) == 1
        assert results[0].scheme_type == target.scheme_type
        assert results[0].scheme_version_id == target.scheme_version_id
        # The actual submission is deferred to `self.db`'s own
        # `after_commit` event (service.py's own `request_refresh`
        # docstring) — it only fires once this transaction commits.
        db_session.commit()
        assert len(recorder.calls) == 1

    def test_multiple_affected_targets_each_produce_a_refresh_result(
        self, db_session: Session
    ) -> None:
        targets = [
            EvaluationTarget(scheme_type=SchemeType.UFLS, scheme_version_id=uuid.uuid4()),
            EvaluationTarget(scheme_type=SchemeType.EMLS, scheme_version_id=uuid.uuid4()),
        ]
        recorder = RecordingExecutionEngine()
        service = ContinuousEvaluationService(
            db_session, resolver=FakeAffectedSchemeResolver(targets), execution_engine=recorder
        )
        results = service.notify_source_data_changed(synthetic_change_descriptor())
        assert len(results) == 2
        assert {(r.scheme_type, r.scheme_version_id) for r in results} == {
            (t.scheme_type, t.scheme_version_id) for t in targets
        }
        db_session.commit()
        assert len(recorder.calls) == 2

    def test_duplicate_targets_from_the_resolver_are_deduplicated(
        self, db_session: Session
    ) -> None:
        target = EvaluationTarget(scheme_type=SchemeType.UFLS, scheme_version_id=uuid.uuid4())
        recorder = RecordingExecutionEngine()
        service = ContinuousEvaluationService(
            db_session,
            resolver=FakeAffectedSchemeResolver([target, target, target]),
            execution_engine=recorder,
        )
        results = service.notify_source_data_changed(synthetic_change_descriptor())
        assert len(results) == 1
        db_session.commit()
        assert len(recorder.calls) == 1

    def test_correlation_id_propagates_into_the_enqueued_job_arguments(
        self, db_session: Session
    ) -> None:
        target = EvaluationTarget(scheme_type=SchemeType.UFLS, scheme_version_id=uuid.uuid4())
        correlation_id = uuid.uuid4()
        recorder = RecordingExecutionEngine()
        service = ContinuousEvaluationService(
            db_session,
            resolver=FakeAffectedSchemeResolver([target]),
            execution_engine=recorder,
        )
        service.notify_source_data_changed(
            synthetic_change_descriptor(correlation_id=correlation_id)
        )
        db_session.commit()
        assert len(recorder.calls) == 1
        job_args = recorder.calls[0]["args"]
        assert str(correlation_id) in job_args

    def test_trigger_propagated_is_the_event_descriptor(self, db_session: Session) -> None:
        target = EvaluationTarget(scheme_type=SchemeType.UFLS, scheme_version_id=uuid.uuid4())
        recorder = RecordingExecutionEngine()
        service = ContinuousEvaluationService(
            db_session, resolver=FakeAffectedSchemeResolver([target]), execution_engine=recorder
        )
        service.notify_source_data_changed(
            synthetic_change_descriptor(descriptor="equipment_registry.circuit.corrected")
        )
        db_session.commit()
        job_args = recorder.calls[0]["args"]
        assert "equipment_registry.circuit.corrected" in job_args

    def test_duplicate_event_delivery_is_safe(self, db_session: Session) -> None:
        """Calling `notify_source_data_changed` twice for the same
        underlying change (e.g. an at-least-once delivery retry) must not
        produce unbounded duplicate jobs — the second call's own
        `request_refresh` coalesces exactly the same way a duplicate
        direct `request_refresh` call would (this sprint's own
        instructions §12, §29)."""
        target = EvaluationTarget(scheme_type=SchemeType.UFLS, scheme_version_id=uuid.uuid4())
        recorder = RecordingExecutionEngine()
        service = ContinuousEvaluationService(
            db_session, resolver=FakeAffectedSchemeResolver([target]), execution_engine=recorder
        )
        event = synthetic_change_descriptor()
        service.notify_source_data_changed(event)
        service.notify_source_data_changed(event)
        db_session.commit()
        # Two requests, but only the first was still outstanding — the
        # second coalesced (see test_projection_lifecycle's own coverage
        # of this exact rule).
        assert len(recorder.calls) == 1

    def test_event_handler_never_runs_detector_calculations_directly(
        self, db_session: Session
    ) -> None:
        """No `mw_tolerance_percentage` parameter is seeded in this test
        at all — if `notify_source_data_changed` ever ran `evaluate()`
        inline, it would raise `MissingEngineeringParameterError`. It
        must not: only `request_refresh` (mark stale + enqueue) runs,
        never the synchronous evaluation core."""
        target = EvaluationTarget(scheme_type=SchemeType.UFLS, scheme_version_id=uuid.uuid4())
        recorder = RecordingExecutionEngine()
        service = ContinuousEvaluationService(
            db_session, resolver=FakeAffectedSchemeResolver([target]), execution_engine=recorder
        )
        results = service.notify_source_data_changed(synthetic_change_descriptor())
        assert len(results) == 1
        assert results[0].status.value == "STALE"
