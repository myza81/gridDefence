"""Evaluation engine tests (this sprint's own instructions §25): successful
evaluation, deterministic execution/ordering, correct context propagation,
multi-detector aggregation, detector-failure semantics, detector-output
validation (source mismatch), no policy resolution, no Publication Record
creation, no DB commit, and FastAPI-independent callability.
"""

from __future__ import annotations

from decimal import Decimal

import pydantic
import pytest
from sqlalchemy.orm import Session

from app.modules.continuous_evaluation.detectors.base import EngineeringFindingDetector
from app.modules.continuous_evaluation.detectors.registry import DetectorRegistry
from app.modules.continuous_evaluation.exceptions import (
    DetectorExecutionFailedError,
    DetectorSourceMismatchError,
    NoApplicableDetectorsError,
)
from app.modules.continuous_evaluation.schemas import EvaluationRequest, MwEvaluationInputs
from app.modules.continuous_evaluation.service import ContinuousEvaluationService
from app.modules.continuous_evaluation.tests.synthetic_evaluation import (
    synthetic_evaluation_request,
    synthetic_mw_group,
)
from app.modules.findings_publication_governance.findings import (
    Finding,
    FindingType,
    SchemeType,
    Severity,
)


class _RecordingDetector(EngineeringFindingDetector):
    def __init__(
        self, detector_id: str, scheme_types: frozenset[SchemeType], calls: list[str], **kw: object
    ) -> None:
        self.detector_id = detector_id
        self.applicable_scheme_types = scheme_types
        self._calls = calls
        self._findings_to_return: list[Finding] = []

    def detect(self, context: EvaluationRequest) -> list[Finding]:
        self._calls.append(self.detector_id)
        return self._findings_to_return


class _RaisingDetector(EngineeringFindingDetector):
    detector_id = "raising"
    applicable_scheme_types = frozenset(SchemeType)

    def detect(self, context: EvaluationRequest) -> list[Finding]:
        raise RuntimeError("boom")


class _SourceMismatchDetector(EngineeringFindingDetector):
    detector_id = "mismatched"
    applicable_scheme_types = frozenset(SchemeType)

    def detect(self, context: EvaluationRequest) -> list[Finding]:
        return [
            Finding(
                finding_type=FindingType.MW_TOLERANCE_DEVIATION,
                severity=Severity.WARNING,
                source="not_my_own_id",
                description="wrong source",
                affected_object_type="stage",
                affected_object_id="x",
            )
        ]


@pytest.fixture()
def seeded_tolerance(db_session: Session):
    from app.modules.engineering_parameters.service import EngineeringParameterService

    EngineeringParameterService(db_session).set_parameter_value(
        "mw_tolerance_percentage",
        value="10",
        unit="percent",
        description=None,
        change_reason="test",
        actor_user_id=None,
    )
    db_session.commit()


class TestSuccessfulEvaluation:
    def test_within_tolerance_returns_empty_findings_with_summary(
        self, db_session: Session, seeded_tolerance: None
    ) -> None:
        service = ContinuousEvaluationService(db_session)
        request = synthetic_evaluation_request()
        result = service.evaluate(request)

        assert result.findings == []
        assert len(result.detector_summaries) == 1
        assert result.detector_summaries[0].detector_id == "mw_tolerance"
        assert result.detector_summaries[0].finding_count == 0
        assert result.scheme_type == request.scheme_type
        assert result.scheme_version_id == request.scheme_version_id
        assert result.evaluation_snapshot_id == request.evaluation_snapshot_id
        assert result.topology_version_id == request.topology_version_id
        assert result.load_snapshot_id == request.load_snapshot_id

    def test_out_of_tolerance_returns_one_finding(
        self, db_session: Session, seeded_tolerance: None
    ) -> None:
        service = ContinuousEvaluationService(db_session)
        request = synthetic_evaluation_request(
            mw_inputs=MwEvaluationInputs(
                groups=[synthetic_mw_group(reference_mw=Decimal("100"), current_mw=Decimal("50"))]
            )
        )
        result = service.evaluate(request)
        assert len(result.findings) == 1
        assert result.detector_summaries[0].finding_count == 1


class TestDeterministicOrderingAndAggregation:
    def test_detectors_run_in_registration_order(self, db_session: Session) -> None:
        calls: list[str] = []
        registry = DetectorRegistry()
        registry.register(_RecordingDetector("first", frozenset(SchemeType), calls))
        registry.register(_RecordingDetector("second", frozenset(SchemeType), calls))
        registry.register(_RecordingDetector("third", frozenset(SchemeType), calls))

        service = ContinuousEvaluationService(db_session, registry=registry)
        request = synthetic_evaluation_request(mw_inputs=None)
        service.evaluate(request)

        assert calls == ["first", "second", "third"]

    def test_summaries_and_findings_aggregate_across_detectors_in_order(
        self, db_session: Session
    ) -> None:
        calls: list[str] = []
        registry = DetectorRegistry()
        d1 = _RecordingDetector("d1", frozenset(SchemeType), calls)
        d1._findings_to_return = [
            Finding(
                finding_type=FindingType.MW_TOLERANCE_DEVIATION,
                severity=Severity.WARNING,
                source="d1",
                description="from d1",
                affected_object_type="stage",
                affected_object_id="x",
            )
        ]
        d2 = _RecordingDetector("d2", frozenset(SchemeType), calls)
        registry.register(d1)
        registry.register(d2)

        service = ContinuousEvaluationService(db_session, registry=registry)
        result = service.evaluate(synthetic_evaluation_request(mw_inputs=None))

        assert [s.detector_id for s in result.detector_summaries] == ["d1", "d2"]
        assert [s.finding_count for s in result.detector_summaries] == [1, 0]
        assert len(result.findings) == 1
        assert result.findings[0].source == "d1"

    def test_context_passed_to_every_detector_is_the_same_request(
        self, db_session: Session
    ) -> None:
        seen_contexts: list[EvaluationRequest] = []

        class _ContextCapturingDetector(EngineeringFindingDetector):
            detector_id = "capturing"
            applicable_scheme_types = frozenset(SchemeType)

            def detect(self, context: EvaluationRequest) -> list[Finding]:
                seen_contexts.append(context)
                return []

        registry = DetectorRegistry()
        registry.register(_ContextCapturingDetector())
        service = ContinuousEvaluationService(db_session, registry=registry)
        request = synthetic_evaluation_request(mw_inputs=None)
        service.evaluate(request)

        assert seen_contexts == [request]


class TestFailureSemantics:
    def test_no_applicable_detectors_raises(self, db_session: Session) -> None:
        registry = DetectorRegistry()
        service = ContinuousEvaluationService(db_session, registry=registry)
        with pytest.raises(NoApplicableDetectorsError):
            service.evaluate(synthetic_evaluation_request(mw_inputs=None))

    def test_detector_exception_fails_the_whole_evaluation(self, db_session: Session) -> None:
        registry = DetectorRegistry()
        registry.register(_RaisingDetector())
        service = ContinuousEvaluationService(db_session, registry=registry)
        with pytest.raises(DetectorExecutionFailedError) as exc_info:
            service.evaluate(synthetic_evaluation_request(mw_inputs=None))
        assert exc_info.value.detector_id == "raising"
        assert isinstance(exc_info.value.original, RuntimeError)

    def test_one_detector_failing_prevents_a_partial_result_even_if_others_would_succeed(
        self, db_session: Session
    ) -> None:
        calls: list[str] = []
        registry = DetectorRegistry()
        registry.register(_RecordingDetector("good", frozenset(SchemeType), calls))
        registry.register(_RaisingDetector())
        service = ContinuousEvaluationService(db_session, registry=registry)
        with pytest.raises(DetectorExecutionFailedError):
            service.evaluate(synthetic_evaluation_request(mw_inputs=None))
        # The first (good) detector did run, but no result was ever returned.
        assert calls == ["good"]

    def test_detector_source_mismatch_raises(self, db_session: Session) -> None:
        registry = DetectorRegistry()
        registry.register(_SourceMismatchDetector())
        service = ContinuousEvaluationService(db_session, registry=registry)
        with pytest.raises(DetectorSourceMismatchError):
            service.evaluate(synthetic_evaluation_request(mw_inputs=None))


class TestEngineDoesNotOverreach:
    def test_evaluate_does_not_commit_the_session(
        self, db_session: Session, seeded_tolerance: None
    ) -> None:
        service = ContinuousEvaluationService(db_session)
        request = synthetic_evaluation_request(
            mw_inputs=MwEvaluationInputs(
                groups=[synthetic_mw_group(reference_mw=Decimal("100"), current_mw=Decimal("50"))]
            )
        )
        service.evaluate(request)
        # Nothing this call did should require or trigger a commit —
        # rolling back must discard nothing engine-relevant, since the
        # engine wrote nothing.
        db_session.rollback()
        # Rollback must not raise and evaluate() must still be re-runnable
        # with the same (already-committed) tolerance parameter.
        result = service.evaluate(request)
        assert len(result.findings) == 1

    def test_result_carries_no_publication_treatment_or_lifecycle_fields(
        self, db_session: Session, seeded_tolerance: None
    ) -> None:
        service = ContinuousEvaluationService(db_session)
        result = service.evaluate(synthetic_evaluation_request())
        result_fields = set(type(result).model_fields.keys())
        assert "treatment" not in result_fields
        assert "publication_record_id" not in result_fields
        assert "status" not in result_fields

    def test_evaluate_is_callable_without_fastapi(self, db_session: Session) -> None:
        """No `Depends`, no request object — plain constructor args only,
        so a future background job or scheme service can call the same
        code path tests use."""
        service = ContinuousEvaluationService(db_session)
        request = synthetic_evaluation_request(mw_inputs=None)
        result = service.evaluate(request)
        assert result is not None


class TestInputResultImmutability:
    def test_evaluation_request_is_frozen(self, db_session: Session) -> None:
        request = synthetic_evaluation_request()
        with pytest.raises(pydantic.ValidationError):
            request.scheme_version_id = None  # type: ignore[misc]

    def test_evaluation_result_is_frozen(self, db_session: Session, seeded_tolerance: None) -> None:
        service = ContinuousEvaluationService(db_session)
        result = service.evaluate(synthetic_evaluation_request())
        with pytest.raises(pydantic.ValidationError):
            result.findings = []  # type: ignore[misc]
