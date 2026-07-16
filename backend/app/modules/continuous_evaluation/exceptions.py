"""Continuous Evaluation Engine business errors (CLAUDE.md A9 — structured,
not ad hoc). Every expected failure mode this sprint's own instructions
enumerate (§22) gets its own narrow exception rather than a generic 500 or
a bare `ValueError`.

A software/configuration failure (missing parameter, bad detector output,
a detector raising) is never converted into a `Finding` — a `Finding` is
an engineering fact about the scheme being evaluated, not a statement
about whether the evaluation machinery itself worked (this sprint's own
instructions §11, §22).
"""

from __future__ import annotations

from app.shared.exceptions import AppError, NotFoundError, ValidationAppError

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationAppError",
    "DuplicateDetectorIdError",
    "NoApplicableDetectorsError",
    "DetectorSourceMismatchError",
    "DetectorExecutionFailedError",
    "MissingEngineeringParameterError",
    "InvalidEngineeringParameterUnitError",
    "InvalidEngineeringParameterValueError",
    "InvalidReferenceMwError",
    "InvalidCurrentMwError",
    "ZeroReferenceMwError",
    "DuplicateProviderRegistrationError",
    "NoEvaluationRequestProviderError",
]


class DuplicateDetectorIdError(ValidationAppError):
    """Raised by `DetectorRegistry.register` — ADR-022's own explicit
    static registration model requires every `detector_id` to be unique;
    a second registration under the same id is a composition-time bug,
    not a runtime engineering condition."""

    def __init__(self, detector_id: str) -> None:
        super().__init__(f"A detector is already registered under id '{detector_id}'.")


class NoApplicableDetectorsError(ValidationAppError):
    """Raised when `evaluate()` is asked to evaluate a scheme type for
    which zero registered detectors declare applicability. An evaluation
    claiming to be complete while structurally unable to check anything
    would be misleading (this sprint's own instructions §22)."""

    def __init__(self, scheme_type: str) -> None:
        super().__init__(f"No registered detector is applicable to scheme type '{scheme_type}'.")


class DetectorSourceMismatchError(ValidationAppError):
    """Raised when a detector returns a `Finding` whose `source` does not
    match the detector's own `detector_id` — ADR-022's own integrity
    requirement that a detector cannot impersonate another detector's
    identity."""

    def __init__(self, detector_id: str, finding_source: str) -> None:
        super().__init__(
            f"Detector '{detector_id}' returned a Finding whose source was "
            f"'{finding_source}' instead of its own detector_id."
        )


class DetectorExecutionFailedError(AppError):
    """Raised by the engine when a detector's own `detect()` call raises.

    This sprint's own instructions §11: an evaluation must never silently
    omit a failed detector or report itself as complete when a detector
    could not run. The safest choice, absent an architecture-defined
    partial-evaluation mode, is to fail the whole evaluation rather than
    return a result that looks complete but is missing a detector's own
    findings. The original exception is preserved via `__cause__`."""

    def __init__(self, detector_id: str, original: Exception) -> None:
        super().__init__(
            f"Detector '{detector_id}' failed during evaluation: {original}",
            code="detector_execution_failed",
        )
        self.detector_id = detector_id
        self.original = original


class MissingEngineeringParameterError(ValidationAppError):
    def __init__(self, parameter_key: str) -> None:
        super().__init__(
            f"Engineering parameter '{parameter_key}' is not configured. "
            "The MW tolerance detector cannot evaluate without it (ADR-021)."
        )


class InvalidEngineeringParameterUnitError(ValidationAppError):
    def __init__(self, parameter_key: str, expected_unit: str, actual_unit: str | None) -> None:
        super().__init__(
            f"Engineering parameter '{parameter_key}' must have unit "
            f"'{expected_unit}', got '{actual_unit}'."
        )


class InvalidEngineeringParameterValueError(ValidationAppError):
    def __init__(self, parameter_key: str, value: str) -> None:
        super().__init__(
            f"Engineering parameter '{parameter_key}' has an invalid value: '{value}'."
        )


class InvalidReferenceMwError(ValidationAppError):
    def __init__(self, group_id: str, reference_mw: object) -> None:
        super().__init__(
            f"MW group '{group_id}' has an invalid reference MW value: {reference_mw!r} "
            "(reference MW must be zero or positive)."
        )


class InvalidCurrentMwError(ValidationAppError):
    def __init__(self, group_id: str, current_mw: object) -> None:
        super().__init__(
            f"MW group '{group_id}' has an invalid current MW value: {current_mw!r} "
            "(current MW must be zero or positive)."
        )


class ZeroReferenceMwError(ValidationAppError):
    """Reference (target) MW is the denominator of the deviation-percentage
    formula (continuous-evaluation-architecture.md §7). A zero reference
    makes percentage deviation undefined — this is treated as an invalid
    evaluation input, not silently divided or coerced to +/-infinity
    (this sprint's own instructions §12, §22)."""

    def __init__(self, group_id: str) -> None:
        super().__init__(
            f"MW group '{group_id}' has a reference (target) MW of zero; percentage "
            "deviation is undefined and cannot be evaluated."
        )


class DuplicateProviderRegistrationError(ValidationAppError):
    """Raised by `EvaluationRequestProviderRegistry.register` — exactly
    one `EvaluationRequestProvider` per scheme type; a second registration
    for the same scheme type is a composition-time bug."""

    def __init__(self, scheme_type: object) -> None:
        super().__init__(
            f"An EvaluationRequestProvider is already registered for scheme type '{scheme_type}'."
        )


class NoEvaluationRequestProviderError(AppError):
    """Raised by the background worker when no `EvaluationRequestProvider`
    is registered for the target's scheme type. No real scheme module is
    registered yet in production this sprint (§9) — a clean, recorded
    projection failure, never a crash."""

    def __init__(self, scheme_type: object) -> None:
        super().__init__(
            f"No EvaluationRequestProvider is registered for scheme type '{scheme_type}'.",
            code="no_evaluation_request_provider",
        )
