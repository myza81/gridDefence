"""Tests for Findings and Publication Governance's bootstrap.py — permission
registration and the four architecture-approved baseline policies
(findings-and-publication-governance-architecture.md §4.2; ADR-018).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.findings_publication_governance.bootstrap import run_bootstrap
from app.modules.findings_publication_governance.service import PublicationTreatmentPolicyService
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService

_ALL_PERMISSIONS = {
    "findings_publication_governance.read",
    "findings_publication_governance.manage_policy",
    "findings_publication_governance.view_audit",
}


def test_registers_all_three_permissions(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    permission_ids = {p.permission_id for p in service.list_permissions()}
    assert _ALL_PERMISSIONS <= permission_ids


def test_seeds_exactly_four_baseline_policies(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    policy_service = PublicationTreatmentPolicyService(db_session)
    policies = policy_service.list_policies()
    assert len(policies) == 4
    by_severity = {p.severity: p.treatment for p in policies}
    assert by_severity == {
        "CRITICAL": "BLOCK",
        "WARNING": "ALLOW_WITH_ACKNOWLEDGEMENT",
        "ADVISORY": "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
        "INFORMATION": "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
    }
    for policy in policies:
        assert policy.finding_type is None
        assert policy.scheme_type is None


def test_is_idempotent(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)
    run_bootstrap(db_session)  # second run must not duplicate or error

    policy_service = PublicationTreatmentPolicyService(db_session)
    assert len(policy_service.list_policies()) == 4

    service = IAMService(db_session)
    permission_ids = [p.permission_id for p in service.list_permissions()]
    assert permission_ids.count("findings_publication_governance.manage_policy") == 1


def test_administrator_receives_all_three_permissions(db_session: Session) -> None:
    admin = bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    user_roles = service.list_user_roles(admin.user_id)
    admin_role = next(ur for ur in user_roles if ur.role.name == "Administrator")
    assert _ALL_PERMISSIONS <= set(admin_role.permissions)


def test_engineer_and_viewer_receive_read_only(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    for role_name in ("Engineer", "Viewer"):
        role = next(r for r in service.list_roles() if r.name == role_name)
        grants = {p.permission_id for p in service.list_role_permissions(role.role_id)}
        assert grants == {"findings_publication_governance.read"}


def test_baseline_creation_is_audited_with_system_actor(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    policy_service = PublicationTreatmentPolicyService(db_session)
    critical_policy = next(p for p in policy_service.list_policies(severity="CRITICAL"))
    entries, total = policy_service.list_audit_log(critical_policy.policy_id, page=1, page_size=10)
    assert total == 1
    assert entries[0].action == "created"
    assert entries[0].changed_by is None  # system actor — actor_user_id=None
    assert entries[0].change_reason


def test_running_before_iam_bootstrap_does_not_error(db_session: Session) -> None:
    run_bootstrap(db_session)  # IAM bootstrap has NOT run yet

    service = IAMService(db_session)
    permission_ids = {p.permission_id for p in service.list_permissions()}
    assert "findings_publication_governance.manage_policy" in permission_ids

    policy_service = PublicationTreatmentPolicyService(db_session)
    assert len(policy_service.list_policies()) == 4
