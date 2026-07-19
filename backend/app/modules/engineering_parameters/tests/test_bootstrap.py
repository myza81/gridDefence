"""Tests for Engineering Parameter Configuration's permission-catalog
registration and initial-parameter seeding (bootstrap.py) — iam-module.md
§7.3; ADR-021.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.engineering_parameters.bootstrap import run_bootstrap
from app.modules.engineering_parameters.service import EngineeringParameterService
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.models import RolePermission
from app.modules.iam.service import IAMService


def test_registers_read_and_manage_permissions(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    permission_ids = {p.permission_id for p in service.list_permissions()}
    assert "engineering_parameters.read" in permission_ids
    assert "engineering_parameters.manage" in permission_ids


def test_is_idempotent(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)
    run_bootstrap(db_session)  # second run must not duplicate or error

    service = IAMService(db_session)
    permission_ids = [p.permission_id for p in service.list_permissions()]
    assert permission_ids.count("engineering_parameters.manage") == 1

    parameters = EngineeringParameterService(db_session).list_parameters()
    assert len(parameters) == 1  # not duplicated by the second run


def test_administrator_receives_both_permissions(db_session: Session) -> None:
    admin = bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    user_roles = service.list_user_roles(admin.user_id)
    admin_role = next(ur for ur in user_roles if ur.role.name == "Administrator")
    assert "engineering_parameters.read" in admin_role.permissions
    assert "engineering_parameters.manage" in admin_role.permissions


def test_engineer_receives_read_but_not_manage(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    engineer_role = next(r for r in service.list_roles() if r.name == "Engineer")
    grants = {p.permission_id for p in service.list_role_permissions(engineer_role.role_id)}
    assert "engineering_parameters.read" in grants
    assert "engineering_parameters.manage" not in grants


def test_viewer_receives_read_but_not_manage(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    viewer_role = next(r for r in service.list_roles() if r.name == "Viewer")
    grants = {p.permission_id for p in service.list_role_permissions(viewer_role.role_id)}
    assert "engineering_parameters.read" in grants
    assert "engineering_parameters.manage" not in grants


def test_running_before_iam_bootstrap_does_not_error(db_session: Session) -> None:
    run_bootstrap(db_session)  # IAM bootstrap has NOT run yet

    service = IAMService(db_session)
    permission_ids = {p.permission_id for p in service.list_permissions()}
    assert "engineering_parameters.manage" in permission_ids
    assert db_session.query(RolePermission).count() == 0


def test_seeds_the_one_approved_mw_tolerance_parameter(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    parameter_service = EngineeringParameterService(db_session)
    detail = parameter_service.get_parameter("mw_tolerance_percentage")
    assert detail is not None
    assert detail.value == "10"
    assert detail.unit == "percent"

    # Seeded through the same audited write path as any admin change —
    # exactly one audit entry, old_value None (creation).
    entries, total = parameter_service.list_audit_log(
        "mw_tolerance_percentage", page=1, page_size=50
    )
    assert total == 1
    assert entries[0].old_value is None
    assert entries[0].new_value == "10"
    assert entries[0].changed_by is None  # bootstrap-seed exception


def test_does_not_invent_additional_parameters(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    parameters = EngineeringParameterService(db_session).list_parameters()
    assert [p.parameter_key for p in parameters] == ["mw_tolerance_percentage"]
