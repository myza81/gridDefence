"""Tests for PSS/E Integration's permission-catalog registration
(app/modules/psse_integration/bootstrap.py) — iam-module.md §7.3.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.models import RolePermission
from app.modules.iam.service import IAMService
from app.modules.psse_integration.bootstrap import run_bootstrap


def test_registers_all_three_permissions(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    permission_ids = {p.permission_id for p in service.list_permissions()}
    assert "psse_integration.read" in permission_ids
    assert "psse_integration.import" in permission_ids
    assert "psse_integration.activate" in permission_ids


def test_is_idempotent(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)
    run_bootstrap(db_session)  # second run must not duplicate or error

    service = IAMService(db_session)
    permission_ids = [p.permission_id for p in service.list_permissions()]
    assert permission_ids.count("psse_integration.import") == 1


def test_administrator_receives_all_three_permissions(db_session: Session) -> None:
    admin = bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    user_roles = service.list_user_roles(admin.user_id)
    admin_role = next(ur for ur in user_roles if ur.role.name == "Administrator")
    assert "psse_integration.read" in admin_role.permissions
    assert "psse_integration.import" in admin_role.permissions
    assert "psse_integration.activate" in admin_role.permissions


def test_engineer_receives_import_but_not_activate(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    engineer_role = next(r for r in service.list_roles() if r.name == "Engineer")
    grants = {p.permission_id for p in service.list_role_permissions(engineer_role.role_id)}
    assert "psse_integration.read" in grants
    assert "psse_integration.import" in grants
    assert "psse_integration.activate" not in grants


def test_viewer_receives_read_only(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    viewer_role = next(r for r in service.list_roles() if r.name == "Viewer")
    grants = {p.permission_id for p in service.list_role_permissions(viewer_role.role_id)}
    assert grants == {"psse_integration.read"}


def test_running_before_iam_bootstrap_does_not_error(db_session: Session) -> None:
    run_bootstrap(db_session)  # IAM bootstrap has NOT run yet

    service = IAMService(db_session)
    permission_ids = {p.permission_id for p in service.list_permissions()}
    assert "psse_integration.import" in permission_ids
    assert db_session.query(RolePermission).count() == 0
