"""Tests for the shared `Finding` value contract (findings.py) — module
document §2; this sprint's own instructions §4/§16.
"""

from __future__ import annotations

import pydantic
import pytest

from app.modules.findings_publication_governance.findings import (
    Finding,
    FindingType,
    SchemeType,
    Severity,
)


def _minimal_finding(**overrides: object) -> Finding:
    defaults: dict[str, object] = dict(
        finding_type=FindingType.MW_TOLERANCE_DEVIATION,
        severity=Severity.WARNING,
        source="mw_tolerance_detector",
        description="Stage 2 current MW deviates -12% from target.",
        affected_object_type="stage",
        affected_object_id="stage-2",
    )
    defaults.update(overrides)
    return Finding(**defaults)  # type: ignore[arg-type]


def test_construction_with_required_fields_only() -> None:
    finding = _minimal_finding()
    assert finding.finding_type == FindingType.MW_TOLERANCE_DEVIATION
    assert finding.severity == Severity.WARNING
    assert finding.source == "mw_tolerance_detector"
    assert finding.scheme_type is None
    assert finding.scheme_version_id is None
    assert finding.evidence is None


def test_construction_with_full_context() -> None:
    finding = _minimal_finding(
        scheme_type=SchemeType.UFLS,
        scheme_version_id="ufls-version-123",
        evidence={"condition_description": "Only allowed during system emergency."},
    )
    assert finding.scheme_type == SchemeType.UFLS
    assert finding.scheme_version_id == "ufls-version-123"
    assert finding.evidence == {"condition_description": "Only allowed during system emergency."}


@pytest.mark.parametrize("finding_type", list(FindingType))
def test_every_canonical_finding_type_constructs(finding_type: FindingType) -> None:
    finding = _minimal_finding(finding_type=finding_type)
    assert finding.finding_type == finding_type


@pytest.mark.parametrize("severity", list(Severity))
def test_every_canonical_severity_constructs(severity: Severity) -> None:
    finding = _minimal_finding(severity=severity)
    assert finding.severity == severity


def test_invalid_finding_type_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        _minimal_finding(finding_type="NOT_A_REAL_FINDING_TYPE")


def test_invalid_severity_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        _minimal_finding(severity="NOT_A_REAL_SEVERITY")


def test_invalid_scheme_type_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        _minimal_finding(scheme_type="EMLS_TYPO")


def test_finding_is_immutable() -> None:
    finding = _minimal_finding()
    with pytest.raises(pydantic.ValidationError):
        finding.severity = Severity.CRITICAL  # type: ignore[misc]


def test_finding_has_no_publication_treatment_field() -> None:
    """Module document §4; this sprint's own instructions §4 — treatment
    is always resolved separately, never embedded on the finding."""
    assert "treatment" not in Finding.model_fields
    assert "acknowledgement_required" not in Finding.model_fields


def test_finding_has_no_persisted_identity_field() -> None:
    """No stable finding identity/deduplication key — none is required
    in this sprint's scope (findings are recomputed live, never diffed
    against a persisted prior finding)."""
    assert "finding_id" not in Finding.model_fields
    assert "id" not in Finding.model_fields


def test_serialization_round_trips_through_dict() -> None:
    finding = _minimal_finding(
        scheme_type=SchemeType.UVLS, evidence={"deviation_percentage": -12.5}
    )
    dumped = finding.model_dump()
    assert dumped["finding_type"] == FindingType.MW_TOLERANCE_DEVIATION
    assert dumped["severity"] == Severity.WARNING
    assert dumped["scheme_type"] == SchemeType.UVLS
    assert dumped["evidence"] == {"deviation_percentage": -12.5}

    reconstructed = Finding(**dumped)
    assert reconstructed == finding


def test_serialization_to_json_is_plain_strings() -> None:
    """Structured serialization suitable for API responses (this sprint's
    own instructions §4) — enum values serialize as their plain string
    values in JSON mode, not Python enum repr."""
    finding = _minimal_finding(scheme_type=SchemeType.EMLS)
    json_mode_dump = finding.model_dump(mode="json")
    assert json_mode_dump["severity"] == "WARNING"
    assert json_mode_dump["finding_type"] == "MW_TOLERANCE_DEVIATION"
    assert json_mode_dump["scheme_type"] == "EMLS"

    json_text = finding.model_dump_json()
    assert '"severity":"WARNING"' in json_text.replace(" ", "")


def test_no_orm_dependency() -> None:
    """`Finding` is a plain Pydantic value object — no SQLAlchemy
    `Base`/`Mapped` coupling, no database session, no table (this
    sprint's own instructions §4)."""
    assert not hasattr(Finding, "__tablename__")
    assert not hasattr(Finding, "__table__")
