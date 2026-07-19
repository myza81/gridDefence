"""Service-layer tests for `PublicationRecordService.evaluate_and_record_
publication` — the shared publication orchestration algorithm, exercised
entirely through the synthetic scheme-version fixture (synthetic_scheme.py),
never a real scheme module.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.findings_publication_governance.exceptions import (
    AcknowledgementForNonAcknowledgeableFindingError,
    DuplicateAcknowledgementError,
    DuplicatePublicationEventError,
    MissingAcknowledgementError,
    MissingAcknowledgementJustificationError,
    NoApplicablePolicyError,
    PrerequisiteFailedError,
    PublicationBlockedByFindingError,
    UnknownAcknowledgementTargetError,
)
from app.modules.findings_publication_governance.findings import FindingType, SchemeType, Severity
from app.modules.findings_publication_governance.service import (
    PublicationRecordService,
    PublicationTreatmentPolicyService,
)
from app.modules.findings_publication_governance.tests.synthetic_scheme import (
    synthetic_acknowledgement,
    synthetic_finding,
    synthetic_prerequisite,
    synthetic_publication_request,
    synthetic_scheme_request_factory,  # noqa: F401 -- imported so pytest discovers this fixture
)


def _seed_baselines(
    policy_service: PublicationTreatmentPolicyService, actor_user_id: uuid.UUID
) -> None:
    baseline_treatments = {
        "CRITICAL": "BLOCK",
        "WARNING": "ALLOW_WITH_ACKNOWLEDGEMENT",
        "ADVISORY": "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
        "INFORMATION": "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
    }
    for severity, treatment in baseline_treatments.items():
        policy_service.create_policy(
            severity=severity,
            finding_type=None,
            scheme_type=None,
            treatment=treatment,
            change_reason="Initial baseline seeded at deployment.",
            actor_user_id=actor_user_id,
        )


# --- Successful publication scenarios -------------------------------------------------


def test_successful_publication_with_no_findings(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, findings=[], acknowledgements=[]
    )

    result = service.evaluate_and_record_publication(request)
    db_session.commit()

    assert result.finding_count == 0
    assert result.acknowledgement_count == 0
    detail = service.get_publication_record(result.publication_record_id)
    assert detail is not None
    assert detail.findings == []
    assert len(detail.prerequisites) == 1


def test_successful_publication_with_allow_without_ack_findings(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    finding = synthetic_finding(severity=Severity.ADVISORY)
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, findings=[finding], acknowledgements=[]
    )

    result = service.evaluate_and_record_publication(request)
    db_session.commit()

    detail = service.get_publication_record(result.publication_record_id)
    assert detail is not None
    assert len(detail.findings) == 1
    assert detail.findings[0].resolved_treatment == "ALLOW_WITHOUT_ACKNOWLEDGEMENT"
    assert detail.findings[0].acknowledgement_required is False


def test_successful_publication_with_fully_acknowledged_warning_findings(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    finding = synthetic_finding(severity=Severity.WARNING)
    ack = synthetic_acknowledgement(0, acknowledged_by_user_id=actor_user_id)
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, findings=[finding], acknowledgements=[ack]
    )

    result = service.evaluate_and_record_publication(request)
    db_session.commit()

    detail = service.get_publication_record(result.publication_record_id)
    assert detail is not None
    assert detail.findings[0].resolved_treatment == "ALLOW_WITH_ACKNOWLEDGEMENT"
    assert detail.findings[0].acknowledgement_required is True
    assert len(detail.acknowledgements) == 1
    assert detail.acknowledgements[0].finding_index == 0
    assert detail.acknowledgements[0].justification


def test_mixed_treatment_collection(db_session: Session, actor_user_id: uuid.UUID) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    findings = [
        synthetic_finding(severity=Severity.WARNING, affected_object_id="stage-1"),
        synthetic_finding(severity=Severity.ADVISORY, affected_object_id="stage-2"),
        synthetic_finding(severity=Severity.INFORMATION, affected_object_id="stage-3"),
    ]
    ack = synthetic_acknowledgement(0, acknowledged_by_user_id=actor_user_id)
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, findings=findings, acknowledgements=[ack]
    )

    result = service.evaluate_and_record_publication(request)
    db_session.commit()

    detail = service.get_publication_record(result.publication_record_id)
    assert detail is not None
    treatments = [f.resolved_treatment for f in detail.findings]
    assert treatments == [
        "ALLOW_WITH_ACKNOWLEDGEMENT",
        "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
        "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
    ]


# --- Blocking behaviour ----------------------------------------------------------------


def test_blocked_critical_finding(db_session: Session, actor_user_id: uuid.UUID) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    finding = synthetic_finding(severity=Severity.CRITICAL)
    request = synthetic_publication_request(published_by_user_id=actor_user_id, findings=[finding])

    with pytest.raises(PublicationBlockedByFindingError) as exc_info:
        service.evaluate_and_record_publication(request)
    assert exc_info.value.blocked_findings[0]["severity"] == "CRITICAL"

    # No record was created.
    assert service.repo.get_by_event_id(request.publication_event_id) is None


def test_failed_structural_prerequisite(db_session: Session, actor_user_id: uuid.UUID) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    failing_prerequisite = synthetic_prerequisite(
        prerequisite_code="MISSING_TARGET_MW", passed=False, description="No target MW set."
    )
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, prerequisites=[failing_prerequisite]
    )

    with pytest.raises(PrerequisiteFailedError) as exc_info:
        service.evaluate_and_record_publication(request)
    assert exc_info.value.failed_prerequisites[0]["prerequisite_code"] == "MISSING_TARGET_MW"
    assert service.repo.get_by_event_id(request.publication_event_id) is None


def test_prerequisite_failure_checked_before_policy_resolution(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """A failed prerequisite blocks publication unconditionally — even
    when bootstrap never ran, so no policy could resolve anyway (module
    document §5: structural prerequisites are outside policy entirely)."""
    service = PublicationRecordService(db_session)  # no baselines seeded
    failing_prerequisite = synthetic_prerequisite(passed=False)
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id,
        findings=[synthetic_finding()],
        prerequisites=[failing_prerequisite],
    )

    with pytest.raises(PrerequisiteFailedError):
        service.evaluate_and_record_publication(request)


# --- Acknowledgement validation ---------------------------------------------------------


def test_missing_acknowledgement(db_session: Session, actor_user_id: uuid.UUID) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    finding = synthetic_finding(severity=Severity.WARNING)
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, findings=[finding], acknowledgements=[]
    )

    with pytest.raises(MissingAcknowledgementError) as exc_info:
        service.evaluate_and_record_publication(request)
    assert exc_info.value.missing_finding_indexes == [0]


def test_duplicate_acknowledgement(db_session: Session, actor_user_id: uuid.UUID) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    finding = synthetic_finding(severity=Severity.WARNING)
    ack1 = synthetic_acknowledgement(0, acknowledged_by_user_id=actor_user_id)
    ack2 = synthetic_acknowledgement(0, acknowledged_by_user_id=actor_user_id)
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, findings=[finding], acknowledgements=[ack1, ack2]
    )

    with pytest.raises(DuplicateAcknowledgementError):
        service.evaluate_and_record_publication(request)


def test_acknowledgement_for_wrong_finding_unknown_target(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    finding = synthetic_finding(severity=Severity.WARNING)
    ack = synthetic_acknowledgement(5, acknowledged_by_user_id=actor_user_id)  # out of bounds
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, findings=[finding], acknowledgements=[ack]
    )

    with pytest.raises(UnknownAcknowledgementTargetError):
        service.evaluate_and_record_publication(request)


def test_unnecessary_acknowledgement(db_session: Session, actor_user_id: uuid.UUID) -> None:
    """An acknowledgement submitted for a finding whose resolved
    treatment is ALLOW_WITHOUT_ACKNOWLEDGEMENT — not required, not
    permitted (this sprint's own instructions §10)."""
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    finding = synthetic_finding(severity=Severity.ADVISORY)
    ack = synthetic_acknowledgement(0, acknowledged_by_user_id=actor_user_id)
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, findings=[finding], acknowledgements=[ack]
    )

    with pytest.raises(AcknowledgementForNonAcknowledgeableFindingError):
        service.evaluate_and_record_publication(request)


def test_missing_acknowledgement_justification(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    finding = synthetic_finding(severity=Severity.WARNING)
    ack = synthetic_acknowledgement(0, acknowledged_by_user_id=actor_user_id, justification="   ")
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, findings=[finding], acknowledgements=[ack]
    )

    with pytest.raises(MissingAcknowledgementJustificationError):
        service.evaluate_and_record_publication(request)


# --- Policy resolution integration -------------------------------------------------------


def test_scheme_specific_policy_override(db_session: Session, actor_user_id: uuid.UUID) -> None:
    policy_service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(policy_service, actor_user_id)
    policy_service.create_policy(
        severity="WARNING",
        finding_type=None,
        scheme_type="EMLS",
        treatment="BLOCK",
        change_reason="EMLS retains a stricter Warning default.",
        actor_user_id=actor_user_id,
    )
    service = PublicationRecordService(db_session)
    finding = synthetic_finding(severity=Severity.WARNING)
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, scheme_type=SchemeType.EMLS, findings=[finding]
    )

    with pytest.raises(PublicationBlockedByFindingError):
        service.evaluate_and_record_publication(request)


def test_finding_type_policy_override(db_session: Session, actor_user_id: uuid.UUID) -> None:
    policy_service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(policy_service, actor_user_id)
    policy_service.create_policy(
        severity="WARNING",
        finding_type="MW_TOLERANCE_DEVIATION",
        scheme_type=None,
        treatment="ALLOW_WITHOUT_ACKNOWLEDGEMENT",
        change_reason="MW deviations at Warning are informational only for now.",
        actor_user_id=actor_user_id,
    )
    service = PublicationRecordService(db_session)
    finding = synthetic_finding(
        severity=Severity.WARNING, finding_type=FindingType.MW_TOLERANCE_DEVIATION
    )
    request = synthetic_publication_request(published_by_user_id=actor_user_id, findings=[finding])

    result = service.evaluate_and_record_publication(request)
    db_session.commit()
    detail = service.get_publication_record(result.publication_record_id)
    assert detail is not None
    assert detail.findings[0].resolved_treatment == "ALLOW_WITHOUT_ACKNOWLEDGEMENT"
    assert detail.findings[0].matched_policy_finding_type == "MW_TOLERANCE_DEVIATION"


def test_global_baseline_fallback(db_session: Session, actor_user_id: uuid.UUID) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    finding = synthetic_finding(severity=Severity.ADVISORY)
    request = synthetic_publication_request(published_by_user_id=actor_user_id, findings=[finding])

    result = service.evaluate_and_record_publication(request)
    db_session.commit()
    detail = service.get_publication_record(result.publication_record_id)
    assert detail is not None
    assert detail.findings[0].matched_policy_finding_type is None
    assert detail.findings[0].matched_policy_scheme_type is None


def test_no_applicable_policy_when_bootstrap_never_ran(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = PublicationRecordService(db_session)
    finding = synthetic_finding(severity=Severity.CRITICAL)
    request = synthetic_publication_request(published_by_user_id=actor_user_id, findings=[finding])

    with pytest.raises(NoApplicablePolicyError):
        service.evaluate_and_record_publication(request)


# --- Frozen evidence and immutability -----------------------------------------------------


def test_frozen_policy_evidence_includes_matched_policy_identity(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    policy_service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(policy_service, actor_user_id)
    baseline = policy_service.list_policies(severity="WARNING")[0]

    service = PublicationRecordService(db_session)
    finding = synthetic_finding(severity=Severity.WARNING)
    ack = synthetic_acknowledgement(0, acknowledged_by_user_id=actor_user_id)
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, findings=[finding], acknowledgements=[ack]
    )
    result = service.evaluate_and_record_publication(request)
    db_session.commit()

    detail = service.get_publication_record(result.publication_record_id)
    assert detail is not None
    assert detail.findings[0].matched_policy_id == baseline.policy_id
    assert detail.findings[0].matched_policy_severity == "WARNING"


def test_policy_changed_after_publication_does_not_change_historical_record(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    policy_service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(policy_service, actor_user_id)
    baseline = policy_service.list_policies(severity="WARNING")[0]

    service = PublicationRecordService(db_session)
    finding = synthetic_finding(severity=Severity.WARNING)
    ack = synthetic_acknowledgement(0, acknowledged_by_user_id=actor_user_id)
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, findings=[finding], acknowledgements=[ack]
    )
    result = service.evaluate_and_record_publication(request)
    db_session.commit()

    # Change the policy after publication.
    policy_service.update_treatment(
        baseline.policy_id,
        treatment="BLOCK",
        change_reason="Tightening after review.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_publication_record(result.publication_record_id)
    assert detail is not None
    assert detail.findings[0].resolved_treatment == "ALLOW_WITH_ACKNOWLEDGEMENT"  # unchanged


def test_policy_removed_after_publication_does_not_change_historical_record(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    policy_service = PublicationTreatmentPolicyService(db_session)
    _seed_baselines(policy_service, actor_user_id)
    override = policy_service.create_policy(
        severity="WARNING",
        finding_type="MW_TOLERANCE_DEVIATION",
        scheme_type=None,
        treatment="ALLOW_WITHOUT_ACKNOWLEDGEMENT",
        change_reason="Temporary relaxation.",
        actor_user_id=actor_user_id,
    )

    service = PublicationRecordService(db_session)
    finding = synthetic_finding(
        severity=Severity.WARNING, finding_type=FindingType.MW_TOLERANCE_DEVIATION
    )
    request = synthetic_publication_request(published_by_user_id=actor_user_id, findings=[finding])
    result = service.evaluate_and_record_publication(request)
    db_session.commit()

    policy_service.remove_policy(
        override.policy_id, change_reason="No longer needed.", actor_user_id=actor_user_id
    )
    db_session.commit()

    detail = service.get_publication_record(result.publication_record_id)
    assert detail is not None
    # Still fully interpretable — the frozen row, not the (now-gone) policy.
    assert detail.findings[0].resolved_treatment == "ALLOW_WITHOUT_ACKNOWLEDGEMENT"
    assert detail.findings[0].matched_policy_finding_type == "MW_TOLERANCE_DEVIATION"


def test_finding_input_mutation_after_publication_does_not_change_record(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    findings_list = [synthetic_finding(severity=Severity.ADVISORY, description="Original.")]
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, findings=findings_list
    )
    result = service.evaluate_and_record_publication(request)
    db_session.commit()

    # Mutate the caller's own list after the call returns.
    findings_list.append(synthetic_finding(severity=Severity.INFORMATION))
    findings_list[0] = synthetic_finding(severity=Severity.ADVISORY, description="Mutated!")

    detail = service.get_publication_record(result.publication_record_id)
    assert detail is not None
    assert len(detail.findings) == 1
    assert detail.findings[0].description == "Original."


def test_prerequisite_input_mutation_after_publication_does_not_change_record(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    prerequisites_list = [synthetic_prerequisite(description="Original prerequisite.")]
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, prerequisites=prerequisites_list
    )
    result = service.evaluate_and_record_publication(request)
    db_session.commit()

    prerequisites_list.append(synthetic_prerequisite(prerequisite_code="EXTRA"))
    prerequisites_list[0] = synthetic_prerequisite(description="Mutated prerequisite!")

    detail = service.get_publication_record(result.publication_record_id)
    assert detail is not None
    assert len(detail.prerequisites) == 1
    assert detail.prerequisites[0].description == "Original prerequisite."


# --- Concurrency / idempotency -----------------------------------------------------------


def test_duplicate_publication_event_prevented(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    event_id = uuid.uuid4()
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, publication_event_id=event_id
    )
    service.evaluate_and_record_publication(request)
    db_session.commit()

    retry_request = synthetic_publication_request(
        published_by_user_id=actor_user_id, publication_event_id=event_id
    )
    with pytest.raises(DuplicatePublicationEventError):
        service.evaluate_and_record_publication(retry_request)


def test_retry_with_new_event_id_succeeds(db_session: Session, actor_user_id: uuid.UUID) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    first_request = synthetic_publication_request(published_by_user_id=actor_user_id)
    first_result = service.evaluate_and_record_publication(first_request)
    db_session.commit()

    second_request = synthetic_publication_request(published_by_user_id=actor_user_id)
    second_result = service.evaluate_and_record_publication(second_request)
    db_session.commit()

    assert first_result.publication_record_id != second_result.publication_record_id


def test_no_hidden_commit(db_session: Session, actor_user_id: uuid.UUID) -> None:
    """The service must never call commit() itself — a caller can still
    roll back after a successful `evaluate_and_record_publication` call,
    proving no commit happened inside it."""
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    db_session.commit()  # commit the baselines only

    service = PublicationRecordService(db_session)
    request = synthetic_publication_request(published_by_user_id=actor_user_id)
    result = service.evaluate_and_record_publication(request)

    db_session.rollback()  # rolls back the publication itself

    assert service.repo.get_by_id(result.publication_record_id) is None


def test_rollback_on_downstream_failure_leaves_no_partial_record(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """If the caller's own outer transaction fails after this service
    call succeeds (but before commit), nothing partial is left behind —
    this service never commits independently."""
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    db_session.commit()

    service = PublicationRecordService(db_session)
    finding = synthetic_finding(severity=Severity.WARNING)
    ack = synthetic_acknowledgement(0, acknowledged_by_user_id=actor_user_id)
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, findings=[finding], acknowledgements=[ack]
    )
    result = service.evaluate_and_record_publication(request)

    # Simulate the caller's own outer transaction failing before commit.
    db_session.rollback()

    assert service.repo.get_by_id(result.publication_record_id) is None
    assert service.repo.list_findings(result.publication_record_id) == []


# --- Deterministic ordering --------------------------------------------------------------


def test_deterministic_finding_and_prerequisite_ordering(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    findings = [
        synthetic_finding(severity=Severity.INFORMATION, affected_object_id="third"),
        synthetic_finding(severity=Severity.ADVISORY, affected_object_id="first"),
        synthetic_finding(severity=Severity.ADVISORY, affected_object_id="second"),
    ]
    prerequisites = [
        synthetic_prerequisite(prerequisite_code="B"),
        synthetic_prerequisite(prerequisite_code="A"),
    ]
    request = synthetic_publication_request(
        published_by_user_id=actor_user_id, findings=findings, prerequisites=prerequisites
    )
    result = service.evaluate_and_record_publication(request)
    db_session.commit()

    detail = service.get_publication_record(result.publication_record_id)
    assert detail is not None
    # Findings preserve request order (finding_index 0, 1, 2), not sorted
    # by severity or any other key.
    assert [f.affected_object_id for f in detail.findings] == ["third", "first", "second"]
    assert [p.prerequisite_code for p in detail.prerequisites] == ["B", "A"]


# --- Synthetic scheme adapter reuse -------------------------------------------------------


def test_synthetic_scheme_request_factory_fixture_reusable(
    db_session: Session,
    actor_user_id: uuid.UUID,
    synthetic_scheme_request_factory,  # noqa: F811 -- pytest fixture injection by name
) -> None:
    """The pytest-fixture convenience wrapper (synthetic_scheme.py) is
    itself reusable — demonstrating the same factory this file's own
    module-level functions already exercise directly."""
    _seed_baselines(PublicationTreatmentPolicyService(db_session), actor_user_id)
    service = PublicationRecordService(db_session)
    findings = [synthetic_finding(severity=Severity.ADVISORY)]
    request = synthetic_scheme_request_factory(findings=findings)

    result = service.evaluate_and_record_publication(request)
    db_session.commit()
    assert result.finding_count == 1
