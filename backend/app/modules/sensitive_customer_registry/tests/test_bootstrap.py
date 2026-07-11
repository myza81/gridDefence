"""Tests for the Sensitive Customer Registry's permission-catalog
registration (bootstrap.py) — iam-module.md §7.3.

Corrected permission model (task Correction 1): Administrator holds all
three permissions; Engineer holds `.read` only (no mutation permission,
unlike ALSF's own precedent); Viewer holds `.read` only. No new role is
introduced.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.models import RolePermission
from app.modules.iam.service import IAMService
from app.modules.sensitive_customer_registry.bootstrap import run_bootstrap


def test_registers_all_three_permissions(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    permission_ids = {p.permission_id for p in service.list_permissions()}
    assert "sensitive_customer_registry.read" in permission_ids
    assert "sensitive_customer_registry.write" in permission_ids
    assert "sensitive_customer_registry.manage_reference_data" in permission_ids


def test_is_idempotent(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)
    run_bootstrap(db_session)  # second run must not duplicate or error

    service = IAMService(db_session)
    permission_ids = [p.permission_id for p in service.list_permissions()]
    assert permission_ids.count("sensitive_customer_registry.write") == 1


def test_administrator_receives_all_three_permissions(db_session: Session) -> None:
    admin = bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    user_roles = service.list_user_roles(admin.user_id)
    admin_role = next(ur for ur in user_roles if ur.role.name == "Administrator")
    assert "sensitive_customer_registry.read" in admin_role.permissions
    assert "sensitive_customer_registry.write" in admin_role.permissions
    assert "sensitive_customer_registry.manage_reference_data" in admin_role.permissions


def test_engineer_receives_read_only_never_mutation_permissions(db_session: Session) -> None:
    """The corrected permission model's central assertion — Engineer must
    never receive `.write` or `.manage_reference_data`."""
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    engineer_role = next(r for r in service.list_roles() if r.name == "Engineer")
    grants = {p.permission_id for p in service.list_role_permissions(engineer_role.role_id)}
    assert grants == {"sensitive_customer_registry.read"}


def test_viewer_receives_read_but_not_write(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    viewer_role = next(r for r in service.list_roles() if r.name == "Viewer")
    grants = {p.permission_id for p in service.list_role_permissions(viewer_role.role_id)}
    assert "sensitive_customer_registry.read" in grants
    assert "sensitive_customer_registry.write" not in grants
    assert "sensitive_customer_registry.manage_reference_data" not in grants


def test_no_new_role_is_introduced(db_session: Session) -> None:
    bootstrap_iam(db_session)
    before = {r.name for r in IAMService(db_session).list_roles()}
    run_bootstrap(db_session)
    after = {r.name for r in IAMService(db_session).list_roles()}
    assert before == after


def test_running_before_iam_bootstrap_does_not_error(db_session: Session) -> None:
    run_bootstrap(db_session)  # IAM bootstrap has NOT run yet

    service = IAMService(db_session)
    permission_ids = {p.permission_id for p in service.list_permissions()}
    assert "sensitive_customer_registry.write" in permission_ids
    assert db_session.query(RolePermission).count() == 0
