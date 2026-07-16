"""Detector framework tests (this sprint's own instructions §23):
interface compliance, duplicate-id rejection, deterministic ordering,
scheme-type filtering, no dynamic discovery, and additive registration
without engine branching.
"""

from __future__ import annotations

import pytest

from app.modules.continuous_evaluation.detectors.base import EngineeringFindingDetector
from app.modules.continuous_evaluation.detectors.registry import DetectorRegistry
from app.modules.continuous_evaluation.exceptions import DuplicateDetectorIdError
from app.modules.continuous_evaluation.schemas import EvaluationRequest
from app.modules.findings_publication_governance.findings import Finding, SchemeType


class _StubDetector(EngineeringFindingDetector):
    def __init__(self, detector_id: str, scheme_types: frozenset[SchemeType]) -> None:
        self.detector_id = detector_id
        self.applicable_scheme_types = scheme_types
        self.call_count = 0

    def detect(self, context: EvaluationRequest) -> list[Finding]:
        self.call_count += 1
        return []


def test_engineering_finding_detector_is_an_abstract_base_class() -> None:
    with pytest.raises(TypeError):
        EngineeringFindingDetector()  # type: ignore[abstract]


def test_registry_starts_empty_no_dynamic_discovery() -> None:
    """ADR-022: no package scanning, no entry points — a fresh registry
    contains only what has been explicitly registered."""
    registry = DetectorRegistry()
    assert registry.all() == []


def test_register_rejects_duplicate_detector_id() -> None:
    registry = DetectorRegistry()
    registry.register(_StubDetector("dup", frozenset({SchemeType.UFLS})))
    with pytest.raises(DuplicateDetectorIdError):
        registry.register(_StubDetector("dup", frozenset({SchemeType.UVLS})))


def test_registration_order_is_the_deterministic_execution_order() -> None:
    registry = DetectorRegistry()
    first = _StubDetector("first", frozenset({SchemeType.UFLS}))
    second = _StubDetector("second", frozenset({SchemeType.UFLS}))
    third = _StubDetector("third", frozenset({SchemeType.UFLS}))
    registry.register(first)
    registry.register(second)
    registry.register(third)

    ordered = registry.for_scheme_type(SchemeType.UFLS)
    assert [d.detector_id for d in ordered] == ["first", "second", "third"]
    # Stable across repeated calls too.
    assert [d.detector_id for d in registry.for_scheme_type(SchemeType.UFLS)] == [
        "first",
        "second",
        "third",
    ]


def test_for_scheme_type_filters_by_applicability() -> None:
    registry = DetectorRegistry()
    ufls_only = _StubDetector("ufls_only", frozenset({SchemeType.UFLS}))
    all_schemes = _StubDetector("all_schemes", frozenset(SchemeType))
    registry.register(ufls_only)
    registry.register(all_schemes)

    assert [d.detector_id for d in registry.for_scheme_type(SchemeType.UFLS)] == [
        "ufls_only",
        "all_schemes",
    ]
    assert [d.detector_id for d in registry.for_scheme_type(SchemeType.EMLS)] == ["all_schemes"]


def test_a_new_detector_registers_additively_without_engine_branching() -> None:
    """Registering a brand-new detector type requires no change to
    `DetectorRegistry` itself — only one additional `register()` call."""
    registry = DetectorRegistry()
    registry.register(_StubDetector("existing", frozenset(SchemeType)))
    registry.register(_StubDetector("brand_new", frozenset(SchemeType)))
    assert len(registry.all()) == 2
    assert {d.detector_id for d in registry.all()} == {"existing", "brand_new"}
