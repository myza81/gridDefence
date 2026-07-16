"""The MW tolerance deviation detector (continuous-evaluation-
architecture.md §7; ADR-021; this sprint's own instructions §12-15).

Formula, exactly as documented, no invention:

    deviation_percentage = (current_mw - reference_mw) / reference_mw * 100

Directional, signed — never collapsed to an absolute value. The single
documented tolerance boundary is symmetric and inclusive on both sides:

    deviation_percentage < -tolerance   -> under-allocation finding
    -tolerance <= deviation_percentage <= tolerance -> within tolerance, no finding
    deviation_percentage > tolerance    -> over-allocation finding

Both directions share the one canonical `FindingType.MW_TOLERANCE_DEVIATION`
(no duplicate finding type is invented for "under" vs "over" — direction is
evidence, not taxonomy).

Severity: the architecture documents exactly one tolerance boundary and no
secondary escalation threshold, and ADR-018 explicitly left "the exact
severity banding" as "an implementation detail for the Continuous
Evaluation Architecture" to decide. This sprint's own instructions forbid
inventing percentage-based escalation bands and require, when the
architecture defines only one severity for an exceeded tolerance, that
exactly that one severity be used. This detector therefore assigns exactly
one severity — `Severity.WARNING` — to *every* out-of-tolerance MW finding,
regardless of magnitude: a WARNING-severity finding, per this platform's
own established severity/treatment baseline (findings-and-publication-
governance-architecture.md §4.2), is "allow with mandatory
acknowledgement" — a real, engineering-meaningful deviation an
Administrator must consciously see and acknowledge before publishing, but
not a structurally forbidden condition (that category, `Severity.CRITICAL`
-> Block, is reserved for genuinely prohibited conditions such as a
Critical Infrastructure conflict — a fundamentally different kind of
problem than a load-allocation deviation). No 10-20%/>20% or similar bands
are implemented.

All arithmetic uses `decimal.Decimal` — never floats (this sprint's own
instructions §21).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.modules.continuous_evaluation.detectors.base import EngineeringFindingDetector
from app.modules.continuous_evaluation.exceptions import (
    InvalidCurrentMwError,
    InvalidEngineeringParameterUnitError,
    InvalidEngineeringParameterValueError,
    InvalidReferenceMwError,
    MissingEngineeringParameterError,
    ZeroReferenceMwError,
)
from app.modules.continuous_evaluation.schemas import EvaluationRequest, MwAssignmentGroupInput
from app.modules.engineering_parameters.service import EngineeringParameterService
from app.modules.findings_publication_governance.findings import (
    Finding,
    FindingType,
    SchemeType,
    Severity,
)

_MW_TOLERANCE_PARAMETER_KEY = "mw_tolerance_percentage"
_MW_TOLERANCE_PARAMETER_UNIT = "percent"

_UNDER_ALLOCATION = "under_allocation"
_OVER_ALLOCATION = "over_allocation"


class MwToleranceDetector(EngineeringFindingDetector):
    """First and, this sprint, only registered detector. Reads the
    approved tolerance exclusively through `EngineeringParameterService`'s
    own public interface (CLAUDE.md A1) — never the repository or ORM
    model directly, and never a hardcoded threshold."""

    detector_id = "mw_tolerance"
    # MW tolerance applies uniformly across UFLS, UVLS, and EMLS — every
    # scheme type's own stage/priority-group shares the same
    # target-MW/current-MW/deviation shape (shared-defence-scheme-domain-
    # model.md's own EMLS priority-group description).
    applicable_scheme_types = frozenset(SchemeType)

    def __init__(self, engineering_parameters: EngineeringParameterService) -> None:
        self._engineering_parameters = engineering_parameters

    def detect(self, context: EvaluationRequest) -> list[Finding]:
        if context.mw_inputs is None or not context.mw_inputs.groups:
            return []

        tolerance_percentage = self._resolve_tolerance_percentage()

        findings: list[Finding] = []
        for group in context.mw_inputs.groups:
            self._validate_group(group)
            deviation_percentage = self._deviation_percentage(group)
            if deviation_percentage < -tolerance_percentage:
                findings.append(
                    self._build_finding(
                        context,
                        group,
                        deviation_percentage=deviation_percentage,
                        tolerance_percentage=tolerance_percentage,
                        direction=_UNDER_ALLOCATION,
                    )
                )
            elif deviation_percentage > tolerance_percentage:
                findings.append(
                    self._build_finding(
                        context,
                        group,
                        deviation_percentage=deviation_percentage,
                        tolerance_percentage=tolerance_percentage,
                        direction=_OVER_ALLOCATION,
                    )
                )
        return findings

    # --- internal helpers -------------------------------------------------------
    def _resolve_tolerance_percentage(self) -> Decimal:
        detail = self._engineering_parameters.get_parameter(_MW_TOLERANCE_PARAMETER_KEY)
        if detail is None:
            raise MissingEngineeringParameterError(_MW_TOLERANCE_PARAMETER_KEY)
        if detail.unit != _MW_TOLERANCE_PARAMETER_UNIT:
            raise InvalidEngineeringParameterUnitError(
                _MW_TOLERANCE_PARAMETER_KEY, _MW_TOLERANCE_PARAMETER_UNIT, detail.unit
            )
        try:
            value = Decimal(detail.value)
        except InvalidOperation as exc:
            raise InvalidEngineeringParameterValueError(
                _MW_TOLERANCE_PARAMETER_KEY, detail.value
            ) from exc
        if value <= 0 or value > 100:
            raise InvalidEngineeringParameterValueError(_MW_TOLERANCE_PARAMETER_KEY, detail.value)
        return value

    def _validate_group(self, group: MwAssignmentGroupInput) -> None:
        if group.reference_mw < 0:
            raise InvalidReferenceMwError(group.group_id, group.reference_mw)
        if group.current_mw < 0:
            raise InvalidCurrentMwError(group.group_id, group.current_mw)
        if group.reference_mw == 0:
            raise ZeroReferenceMwError(group.group_id)

    def _deviation_percentage(self, group: MwAssignmentGroupInput) -> Decimal:
        return (group.current_mw - group.reference_mw) / group.reference_mw * Decimal(100)

    def _build_finding(
        self,
        context: EvaluationRequest,
        group: MwAssignmentGroupInput,
        *,
        deviation_percentage: Decimal,
        tolerance_percentage: Decimal,
        direction: str,
    ) -> Finding:
        deviation_mw = group.current_mw - group.reference_mw
        description = (
            f"MW group '{group.group_label}' is {direction.replace('_', '-')}d: current MW "
            f"({group.current_mw}) deviates from reference MW ({group.reference_mw}) by "
            f"{deviation_percentage}%, exceeding the configured tolerance of "
            f"+/-{tolerance_percentage}%."
        )
        evidence: dict[str, Any] = {
            "reference_mw": str(group.reference_mw),
            "current_mw": str(group.current_mw),
            "deviation_mw": str(deviation_mw),
            "deviation_percentage": str(deviation_percentage),
            "tolerance_percentage": str(tolerance_percentage),
            "direction": direction,
            "group_id": group.group_id,
            "group_label": group.group_label,
            "unit": "MW",
            "evaluation_snapshot_id": (
                str(context.evaluation_snapshot_id) if context.evaluation_snapshot_id else None
            ),
            "topology_version_id": (
                str(context.topology_version_id) if context.topology_version_id else None
            ),
            "load_snapshot_id": (
                str(context.load_snapshot_id) if context.load_snapshot_id else None
            ),
        }
        return Finding(
            finding_type=FindingType.MW_TOLERANCE_DEVIATION,
            severity=Severity.WARNING,
            source=self.detector_id,
            description=description,
            affected_object_type="mw_assignment_group",
            affected_object_id=group.group_id,
            scheme_type=context.scheme_type,
            scheme_version_id=str(context.scheme_version_id),
            evidence=evidence,
        )
