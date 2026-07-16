"""MW tolerance detector tests (this sprint's own instructions §24):
deviation below/at/above tolerance, positive/negative direction, zero
reference/current MW, Decimal precision, missing/wrong-unit/invalid
parameter, parameter changes affecting only later evaluations, correct
Finding shape, and no Finding within tolerance.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.modules.continuous_evaluation.detectors.mw_tolerance import MwToleranceDetector
from app.modules.continuous_evaluation.exceptions import (
    InvalidCurrentMwError,
    InvalidEngineeringParameterUnitError,
    InvalidEngineeringParameterValueError,
    InvalidReferenceMwError,
    MissingEngineeringParameterError,
    ZeroReferenceMwError,
)
from app.modules.continuous_evaluation.schemas import MwEvaluationInputs
from app.modules.continuous_evaluation.tests.synthetic_evaluation import (
    synthetic_evaluation_request,
    synthetic_mw_group,
)
from app.modules.engineering_parameters.models import EngineeringParameter
from app.modules.engineering_parameters.repository import EngineeringParameterRepository
from app.modules.engineering_parameters.service import EngineeringParameterService
from app.modules.findings_publication_governance.findings import FindingType, Severity


@pytest.fixture()
def detector(db_session: Session) -> MwToleranceDetector:
    return MwToleranceDetector(EngineeringParameterService(db_session))


def _seed_tolerance(db_session: Session, value: str = "10", unit: str = "percent") -> None:
    EngineeringParameterService(db_session).set_parameter_value(
        "mw_tolerance_percentage",
        value=value,
        unit=unit,
        description=None,
        change_reason="test",
        actor_user_id=None,
    )
    db_session.commit()


def _seed_tolerance_bypassing_write_validation(
    db_session: Session, value: str, unit: str = "percent"
) -> None:
    """`EngineeringParameterService.set_parameter_value` already validates
    `mw_tolerance_percentage` as a 0-100 number at write time
    (`_NUMERIC_PARAMETER_BOUNDS`), so a malformed value can never reach
    storage through that path. This helper writes directly through the
    repository to simulate a value that arrived through some other means
    (e.g. a manually edited row) — exercising the detector's own
    defense-in-depth validation independent of that upstream guarantee."""
    repo = EngineeringParameterRepository(db_session)
    repo.add(
        EngineeringParameter(
            parameter_key="mw_tolerance_percentage",
            value=value,
            unit=unit,
            description=None,
            updated_by_user_id=None,
        )
    )
    db_session.commit()


class TestWithinTolerance:
    def test_exact_reference_produces_no_finding(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        _seed_tolerance(db_session)
        request = synthetic_evaluation_request(
            mw_inputs=MwEvaluationInputs(
                groups=[synthetic_mw_group(reference_mw=Decimal("100"), current_mw=Decimal("100"))]
            )
        )
        assert detector.detect(request) == []

    def test_boundary_at_exactly_negative_tolerance_is_within_tolerance(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        _seed_tolerance(db_session, value="10")
        request = synthetic_evaluation_request(
            mw_inputs=MwEvaluationInputs(
                groups=[synthetic_mw_group(reference_mw=Decimal("100"), current_mw=Decimal("90"))]
            )
        )
        assert detector.detect(request) == []

    def test_boundary_at_exactly_positive_tolerance_is_within_tolerance(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        _seed_tolerance(db_session, value="10")
        request = synthetic_evaluation_request(
            mw_inputs=MwEvaluationInputs(
                groups=[synthetic_mw_group(reference_mw=Decimal("100"), current_mw=Decimal("110"))]
            )
        )
        assert detector.detect(request) == []


class TestOutOfTolerance:
    def test_under_allocation_beyond_tolerance_raises_finding(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        _seed_tolerance(db_session, value="10")
        request = synthetic_evaluation_request(
            mw_inputs=MwEvaluationInputs(
                groups=[synthetic_mw_group(reference_mw=Decimal("100"), current_mw=Decimal("89"))]
            )
        )
        findings = detector.detect(request)
        assert len(findings) == 1
        finding = findings[0]
        assert finding.finding_type == FindingType.MW_TOLERANCE_DEVIATION
        assert finding.severity == Severity.WARNING
        assert finding.source == "mw_tolerance"
        assert finding.affected_object_type == "mw_assignment_group"
        assert finding.affected_object_id == "stage-1"
        assert finding.scheme_version_id == str(request.scheme_version_id)
        assert finding.evidence is not None
        assert finding.evidence["direction"] == "under_allocation"
        assert Decimal(finding.evidence["deviation_percentage"]) == Decimal("-11")
        assert Decimal(finding.evidence["reference_mw"]) == Decimal("100")
        assert Decimal(finding.evidence["current_mw"]) == Decimal("89")
        assert Decimal(finding.evidence["deviation_mw"]) == Decimal("-11")
        assert Decimal(finding.evidence["tolerance_percentage"]) == Decimal("10")

    def test_over_allocation_beyond_tolerance_raises_finding(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        _seed_tolerance(db_session, value="10")
        request = synthetic_evaluation_request(
            mw_inputs=MwEvaluationInputs(
                groups=[synthetic_mw_group(reference_mw=Decimal("100"), current_mw=Decimal("111"))]
            )
        )
        findings = detector.detect(request)
        assert len(findings) == 1
        assert findings[0].evidence["direction"] == "over_allocation"
        assert Decimal(findings[0].evidence["deviation_percentage"]) == Decimal("11")

    def test_multiple_groups_each_evaluated_independently(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        _seed_tolerance(db_session, value="10")
        request = synthetic_evaluation_request(
            mw_inputs=MwEvaluationInputs(
                groups=[
                    synthetic_mw_group(
                        group_id="stage-1", reference_mw=Decimal("100"), current_mw=Decimal("100")
                    ),
                    synthetic_mw_group(
                        group_id="stage-2", reference_mw=Decimal("50"), current_mw=Decimal("40")
                    ),
                ]
            )
        )
        findings = detector.detect(request)
        assert len(findings) == 1
        assert findings[0].affected_object_id == "stage-2"


class TestDecimalPrecision:
    def test_deviation_uses_decimal_not_float(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        _seed_tolerance(db_session, value="10")
        request = synthetic_evaluation_request(
            mw_inputs=MwEvaluationInputs(
                groups=[synthetic_mw_group(reference_mw=Decimal("3"), current_mw=Decimal("1"))]
            )
        )
        findings = detector.detect(request)
        assert len(findings) == 1
        deviation = Decimal(findings[0].evidence["deviation_percentage"])
        assert isinstance(deviation, Decimal)
        # (1 - 3) / 3 * 100 = -66.66... exactly in Decimal, not a float
        # rounding artifact.
        assert deviation == (Decimal("1") - Decimal("3")) / Decimal("3") * Decimal("100")


class TestInvalidMwInputs:
    def test_zero_reference_mw_raises(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        _seed_tolerance(db_session)
        request = synthetic_evaluation_request(
            mw_inputs=MwEvaluationInputs(
                groups=[synthetic_mw_group(reference_mw=Decimal("0"), current_mw=Decimal("10"))]
            )
        )
        with pytest.raises(ZeroReferenceMwError):
            detector.detect(request)

    def test_negative_reference_mw_raises(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        _seed_tolerance(db_session)
        request = synthetic_evaluation_request(
            mw_inputs=MwEvaluationInputs(
                groups=[synthetic_mw_group(reference_mw=Decimal("-5"), current_mw=Decimal("10"))]
            )
        )
        with pytest.raises(InvalidReferenceMwError):
            detector.detect(request)

    def test_negative_current_mw_raises(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        _seed_tolerance(db_session)
        request = synthetic_evaluation_request(
            mw_inputs=MwEvaluationInputs(
                groups=[synthetic_mw_group(reference_mw=Decimal("100"), current_mw=Decimal("-1"))]
            )
        )
        with pytest.raises(InvalidCurrentMwError):
            detector.detect(request)

    def test_zero_current_mw_is_a_valid_full_deviation(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        _seed_tolerance(db_session, value="10")
        request = synthetic_evaluation_request(
            mw_inputs=MwEvaluationInputs(
                groups=[synthetic_mw_group(reference_mw=Decimal("100"), current_mw=Decimal("0"))]
            )
        )
        findings = detector.detect(request)
        assert len(findings) == 1
        assert Decimal(findings[0].evidence["deviation_percentage"]) == Decimal("-100")


class TestNoMwInputs:
    def test_missing_mw_inputs_produces_no_findings(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        request = synthetic_evaluation_request(mw_inputs=None)
        assert detector.detect(request) == []

    def test_empty_group_list_produces_no_findings(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        request = synthetic_evaluation_request(mw_inputs=MwEvaluationInputs(groups=[]))
        assert detector.detect(request) == []


class TestEngineeringParameterIntegration:
    def test_missing_parameter_raises(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        request = synthetic_evaluation_request()
        with pytest.raises(MissingEngineeringParameterError):
            detector.detect(request)

    def test_wrong_unit_raises(self, db_session: Session, detector: MwToleranceDetector) -> None:
        _seed_tolerance(db_session, value="10", unit="mw")
        request = synthetic_evaluation_request()
        with pytest.raises(InvalidEngineeringParameterUnitError):
            detector.detect(request)

    def test_non_numeric_value_raises(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        _seed_tolerance_bypassing_write_validation(db_session, value="not-a-number")
        request = synthetic_evaluation_request()
        with pytest.raises(InvalidEngineeringParameterValueError):
            detector.detect(request)

    def test_out_of_range_value_raises(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        _seed_tolerance_bypassing_write_validation(db_session, value="150")
        request = synthetic_evaluation_request()
        with pytest.raises(InvalidEngineeringParameterValueError):
            detector.detect(request)

    def test_changing_parameter_affects_only_later_evaluations(
        self, db_session: Session, detector: MwToleranceDetector
    ) -> None:
        _seed_tolerance(db_session, value="10")
        request = synthetic_evaluation_request(
            mw_inputs=MwEvaluationInputs(
                groups=[synthetic_mw_group(reference_mw=Decimal("100"), current_mw=Decimal("85"))]
            )
        )
        # -15% deviation: out of tolerance at 10%, within tolerance at 20%.
        assert len(detector.detect(request)) == 1

        _seed_tolerance(db_session, value="20")
        assert detector.detect(request) == []
