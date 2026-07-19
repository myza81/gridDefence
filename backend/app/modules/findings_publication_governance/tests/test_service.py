"""Service-layer tests for `PublicationTreatmentPolicyService` — policy
CRUD, baseline protection, duplicate prevention, the four-level
precedence order, fallback behaviour, mandatory reason, no-op mutation
handling, and audit history.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.findings_publication_governance.exceptions import (
    CannotRemoveBaselinePolicyError,
    ChangeReasonRequiredError,
    DuplicatePolicyError,
    InvalidFindingTypeError,
    InvalidSchemeTypeError,
    InvalidSeverityError,
    InvalidTreatmentError,
    NoApplicablePolicyError,
    PolicyNotFoundError,
)
from app.modules.findings_publication_governance.findings import (
    Finding,
    FindingType,
    SchemeType,
    Severity,
)
from app.modules.findings_publication_governance.service import PublicationTreatmentPolicyService


def _finding(**overrides: object) -> Finding:
    defaults: dict[str, object] = dict(
        finding_type=FindingType.MW_TOLERANCE_DEVIATION,
        severity=Severity.WARNING,
        source="mw_tolerance_detector",
        description="Deviation outside tolerance.",
        affected_object_type="stage",
        affected_object_id="stage-1",
    )
    defaults.update(overrides)
    return Finding(**defaults)  # type: ignore[arg-type]


def _seed_baselines(service: PublicationTreatmentPolicyService, actor_user_id: uuid.UUID) -> None:
    baseline_treatments = {
        "CRITICAL": "BLOCK",
        "WARNING": "ALLOW_WITH_ACKNOWLEDGEMENT",
        "ADVISORY": "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
        "INFORMATION": "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
    }
    for severity, treatment in baseline_treatments.items():
        service.create_policy(
            severity=severity,
            finding_type=None,
            scheme_type=None,
            treatment=treatment,
            change_reason="Initial baseline seeded at deployment.",
            actor_user_id=actor_user_id,
        )


# --- Policy creation ---------------------------------------------------------------------


def test_create_baseline_policy(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    policy = service.create_policy(
        severity="CRITICAL",
        finding_type=None,
        scheme_type=None,
        treatment="BLOCK",
        change_reason="Initial baseline.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_policy(policy.policy_id)
    assert detail is not None
    assert detail.severity == "CRITICAL"
    assert detail.finding_type is None
    assert detail.scheme_type is None
    assert detail.treatment == "BLOCK"


def test_create_finding_type_override(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)

    override = service.create_policy(
        severity="WARNING",
        finding_type="MW_TOLERANCE_DEVIATION",
        scheme_type=None,
        treatment="BLOCK",
        change_reason="MW deviations should always block for now.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    assert override.finding_type == "MW_TOLERANCE_DEVIATION"


def test_create_rejects_invalid_severity(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    with pytest.raises(InvalidSeverityError):
        service.create_policy(
            severity="EXTREME",
            finding_type=None,
            scheme_type=None,
            treatment="BLOCK",
            change_reason="x",
            actor_user_id=actor_user_id,
        )


def test_create_rejects_invalid_finding_type(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    with pytest.raises(InvalidFindingTypeError):
        service.create_policy(
            severity="WARNING",
            finding_type="NOT_A_TYPE",
            scheme_type=None,
            treatment="BLOCK",
            change_reason="x",
            actor_user_id=actor_user_id,
        )


def test_create_rejects_invalid_scheme_type(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    with pytest.raises(InvalidSchemeTypeError):
        service.create_policy(
            severity="WARNING",
            finding_type=None,
            scheme_type="SPS",
            treatment="BLOCK",
            change_reason="x",
            actor_user_id=actor_user_id,
        )


def test_create_rejects_invalid_treatment(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    with pytest.raises(InvalidTreatmentError):
        service.create_policy(
            severity="WARNING",
            finding_type=None,
            scheme_type=None,
            treatment="IGNORE",
            change_reason="x",
            actor_user_id=actor_user_id,
        )


def test_create_requires_non_empty_reason(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    with pytest.raises(ChangeReasonRequiredError):
        service.create_policy(
            severity="WARNING",
            finding_type=None,
            scheme_type=None,
            treatment="BLOCK",
            change_reason="   ",
            actor_user_id=actor_user_id,
        )


def test_create_rejects_duplicate_at_same_precedence_key(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)

    with pytest.raises(DuplicatePolicyError):
        service.create_policy(
            severity="CRITICAL",
            finding_type=None,
            scheme_type=None,
            treatment="ALLOW_WITHOUT_ACKNOWLEDGEMENT",
            change_reason="Attempt to duplicate baseline.",
            actor_user_id=actor_user_id,
        )


def test_create_allows_same_severity_different_scope(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """Same severity, different (finding_type, scheme_type) key — not a
    duplicate."""
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)

    override_a = service.create_policy(
        severity="WARNING",
        finding_type="MW_TOLERANCE_DEVIATION",
        scheme_type=None,
        treatment="BLOCK",
        change_reason="Global MW override.",
        actor_user_id=actor_user_id,
    )
    override_b = service.create_policy(
        severity="WARNING",
        finding_type=None,
        scheme_type="EMLS",
        treatment="BLOCK",
        change_reason="EMLS-specific override.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    assert override_a.policy_id != override_b.policy_id


# --- Policy modification ------------------------------------------------------------------


def test_update_treatment(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    policies = service.list_policies(severity="ADVISORY")
    policy_id = policies[0].policy_id

    service.update_treatment(
        policy_id,
        treatment="ALLOW_WITH_ACKNOWLEDGEMENT",
        change_reason="Tightening Advisory-severity handling.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_policy(policy_id)
    assert detail is not None
    assert detail.treatment == "ALLOW_WITH_ACKNOWLEDGEMENT"


def test_update_unknown_policy_raises(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    with pytest.raises(PolicyNotFoundError):
        service.update_treatment(
            uuid.uuid4(), treatment="BLOCK", change_reason="x", actor_user_id=actor_user_id
        )


def test_update_requires_non_empty_reason(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    policy_id = service.list_policies(severity="ADVISORY")[0].policy_id

    with pytest.raises(ChangeReasonRequiredError):
        service.update_treatment(
            policy_id, treatment="BLOCK", change_reason="", actor_user_id=actor_user_id
        )


def test_update_to_same_value_is_a_no_op_without_audit_noise(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    policy_id = service.list_policies(severity="ADVISORY")[0].policy_id

    entries_before, total_before = service.list_audit_log(policy_id, page=1, page_size=50)
    service.update_treatment(
        policy_id,
        treatment="ALLOW_WITHOUT_ACKNOWLEDGEMENT",  # already this value
        change_reason="Attempted no-op change.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    entries_after, total_after = service.list_audit_log(policy_id, page=1, page_size=50)
    assert total_after == total_before
    assert entries_after == entries_before


def test_update_cannot_change_key_fields() -> None:
    """severity/finding_type/scheme_type simply aren't parameters of
    `update_treatment` — the immutability is structural, verified via the
    method signature rather than a runtime check."""
    import inspect

    signature = inspect.signature(PublicationTreatmentPolicyService.update_treatment)
    assert "severity" not in signature.parameters
    assert "finding_type" not in signature.parameters
    assert "scheme_type" not in signature.parameters


# --- Policy removal and baseline protection -----------------------------------------------


def test_remove_override(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    override = service.create_policy(
        severity="WARNING",
        finding_type="MW_TOLERANCE_DEVIATION",
        scheme_type=None,
        treatment="BLOCK",
        change_reason="Temporary override.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.remove_policy(
        override.policy_id, change_reason="No longer needed.", actor_user_id=actor_user_id
    )
    db_session.commit()

    assert service.get_policy(override.policy_id) is None


def test_cannot_remove_baseline(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    baseline_id = service.list_policies(severity="CRITICAL")[0].policy_id

    with pytest.raises(CannotRemoveBaselinePolicyError):
        service.remove_policy(
            baseline_id, change_reason="Attempt to remove baseline.", actor_user_id=actor_user_id
        )
    db_session.commit()
    assert service.get_policy(baseline_id) is not None


def test_remove_requires_non_empty_reason(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    override = service.create_policy(
        severity="WARNING",
        finding_type="MW_TOLERANCE_DEVIATION",
        scheme_type=None,
        treatment="BLOCK",
        change_reason="Temporary override.",
        actor_user_id=actor_user_id,
    )
    with pytest.raises(ChangeReasonRequiredError):
        service.remove_policy(override.policy_id, change_reason="", actor_user_id=actor_user_id)


def test_remove_unknown_policy_raises(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    with pytest.raises(PolicyNotFoundError):
        service.remove_policy(uuid.uuid4(), change_reason="x", actor_user_id=actor_user_id)


def test_audit_survives_override_removal(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    override = service.create_policy(
        severity="WARNING",
        finding_type="MW_TOLERANCE_DEVIATION",
        scheme_type=None,
        treatment="BLOCK",
        change_reason="Temporary override.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    policy_id = override.policy_id

    service.remove_policy(policy_id, change_reason="No longer needed.", actor_user_id=actor_user_id)
    db_session.commit()

    entries, total = service.list_audit_log(policy_id, page=1, page_size=50)
    assert total == 2  # created, removed
    actions = {e.action for e in entries}
    assert actions == {"created", "removed"}
    removed_entry = next(e for e in entries if e.action == "removed")
    assert removed_entry.severity == "WARNING"
    assert removed_entry.finding_type == "MW_TOLERANCE_DEVIATION"
    assert removed_entry.new_value is None


# --- Precedence resolution: all four levels -----------------------------------------------


def test_resolves_global_severity_baseline_by_default(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    db_session.commit()

    treatment = service.resolve_publication_treatment(_finding(severity=Severity.CRITICAL))
    assert treatment == "BLOCK"
    treatment = service.resolve_publication_treatment(_finding(severity=Severity.ADVISORY))
    assert treatment == "ALLOW_WITHOUT_ACKNOWLEDGEMENT"


def test_global_finding_type_override_beats_severity_baseline(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    # Baseline for WARNING is ALLOW_WITH_ACKNOWLEDGEMENT; override MW
    # deviations specifically to BLOCK.
    service.create_policy(
        severity="WARNING",
        finding_type="MW_TOLERANCE_DEVIATION",
        scheme_type=None,
        treatment="BLOCK",
        change_reason="Tighten MW deviation handling globally.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    mw_finding = _finding(
        severity=Severity.WARNING, finding_type=FindingType.MW_TOLERANCE_DEVIATION
    )
    other_finding = _finding(
        severity=Severity.WARNING, finding_type=FindingType.ALSF_CAPABILITY_ABSENCE
    )
    assert service.resolve_publication_treatment(mw_finding) == "BLOCK"
    # A different finding type at the same severity still falls through
    # to the unaffected global baseline.
    assert service.resolve_publication_treatment(other_finding) == "ALLOW_WITH_ACKNOWLEDGEMENT"


def test_scheme_specific_severity_override_beats_global_baseline(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    service.create_policy(
        severity="WARNING",
        finding_type=None,
        scheme_type="EMLS",
        treatment="BLOCK",
        change_reason="EMLS retains a stricter Warning default (manual-invocation stakes).",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    emls_finding = _finding(severity=Severity.WARNING, scheme_type=SchemeType.EMLS)
    ufls_finding = _finding(severity=Severity.WARNING, scheme_type=SchemeType.UFLS)
    assert service.resolve_publication_treatment(emls_finding) == "BLOCK"
    assert service.resolve_publication_treatment(ufls_finding) == "ALLOW_WITH_ACKNOWLEDGEMENT"


def test_scheme_and_finding_type_specific_override_is_most_specific(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """Level 1 beats every other level, including a global finding-type
    override (level 2) and a scheme-specific severity override (level 3)
    that would otherwise also match."""
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    service.create_policy(
        severity="WARNING",
        finding_type="MW_TOLERANCE_DEVIATION",
        scheme_type=None,
        treatment="BLOCK",
        change_reason="Global MW override — level 2.",
        actor_user_id=actor_user_id,
    )
    service.create_policy(
        severity="WARNING",
        finding_type=None,
        scheme_type="EMLS",
        treatment="BLOCK",
        change_reason="EMLS-wide override — level 3.",
        actor_user_id=actor_user_id,
    )
    service.create_policy(
        severity="WARNING",
        finding_type="MW_TOLERANCE_DEVIATION",
        scheme_type="EMLS",
        treatment="ALLOW_WITHOUT_ACKNOWLEDGEMENT",
        change_reason="EMLS's own MW tolerance is intentionally looser — level 1.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    finding = _finding(
        severity=Severity.WARNING,
        finding_type=FindingType.MW_TOLERANCE_DEVIATION,
        scheme_type=SchemeType.EMLS,
    )
    assert service.resolve_publication_treatment(finding) == "ALLOW_WITHOUT_ACKNOWLEDGEMENT"


def test_explicit_scheme_type_parameter_overrides_finding_scheme_type(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    service.create_policy(
        severity="WARNING",
        finding_type=None,
        scheme_type="UVLS",
        treatment="BLOCK",
        change_reason="UVLS-specific override.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    finding = _finding(severity=Severity.WARNING, scheme_type=SchemeType.UFLS)
    # Finding itself is tagged UFLS, but the caller explicitly resolves
    # in the context of UVLS.
    assert service.resolve_publication_treatment(finding, scheme_type="UVLS") == "BLOCK"
    assert service.resolve_publication_treatment(finding) == "ALLOW_WITH_ACKNOWLEDGEMENT"


def test_fallback_to_baseline_after_override_removed(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    override = service.create_policy(
        severity="WARNING",
        finding_type="MW_TOLERANCE_DEVIATION",
        scheme_type=None,
        treatment="BLOCK",
        change_reason="Temporary override.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    finding = _finding(severity=Severity.WARNING, finding_type=FindingType.MW_TOLERANCE_DEVIATION)
    assert service.resolve_publication_treatment(finding) == "BLOCK"

    service.remove_policy(
        override.policy_id, change_reason="Reverting to baseline.", actor_user_id=actor_user_id
    )
    db_session.commit()

    assert service.resolve_publication_treatment(finding) == "ALLOW_WITH_ACKNOWLEDGEMENT"


def test_unresolved_policy_raises_when_bootstrap_never_ran(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    finding = _finding(severity=Severity.CRITICAL)
    with pytest.raises(NoApplicablePolicyError):
        service.resolve_publication_treatment(finding)


def test_batch_resolution_is_deterministic(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    db_session.commit()

    findings = [
        _finding(severity=Severity.CRITICAL),
        _finding(severity=Severity.WARNING),
        _finding(severity=Severity.ADVISORY),
        _finding(severity=Severity.INFORMATION),
    ]
    results = service.resolve_publication_treatments(findings)
    assert [treatment for _finding_obj, treatment in results] == [
        "BLOCK",
        "ALLOW_WITH_ACKNOWLEDGEMENT",
        "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
        "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
    ]
    # Repeating resolution never depends on row insertion order.
    results_again = service.resolve_publication_treatments(list(reversed(findings)))
    assert [treatment for _finding_obj, treatment in results_again] == [
        "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
        "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
        "ALLOW_WITH_ACKNOWLEDGEMENT",
        "BLOCK",
    ]


# --- Listing / filtering --------------------------------------------------------------


def test_list_policies_filters(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(service, actor_user_id)
    service.create_policy(
        severity="WARNING",
        finding_type="MW_TOLERANCE_DEVIATION",
        scheme_type=None,
        treatment="BLOCK",
        change_reason="Override.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    all_policies = service.list_policies()
    assert len(all_policies) == 5

    warning_only = service.list_policies(severity="WARNING")
    assert len(warning_only) == 2

    mw_only = service.list_policies(finding_type="MW_TOLERANCE_DEVIATION")
    assert len(mw_only) == 1
