"""Tests for Substation Registry's permission-catalog registration
(app/modules/substation_registry/bootstrap.py) — iam-module.md §7.3.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.models import RolePermission
from app.modules.iam.service import IAMService
from app.modules.substation_registry.bootstrap import run_bootstrap


def test_registers_read_and_write_permissions(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    permission_ids = {p.permission_id for p in service.list_permissions()}
    assert "substation_registry.read" in permission_ids
    assert "substation_registry.write" in permission_ids


def test_is_idempotent(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)
    run_bootstrap(db_session)  # second run must not duplicate or error

    service = IAMService(db_session)
    permission_ids = [p.permission_id for p in service.list_permissions()]
    assert permission_ids.count("substation_registry.write") == 1


def test_administrator_receives_both_permissions(db_session: Session) -> None:
    admin = bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    user_roles = service.list_user_roles(admin.user_id)
    admin_role = next(ur for ur in user_roles if ur.role.name == "Administrator")
    assert "substation_registry.read" in admin_role.permissions
    assert "substation_registry.write" in admin_role.permissions


def test_engineer_receives_write_but_not_read(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    engineer_role = next(r for r in service.list_roles() if r.name == "Engineer")
    grants = {p.permission_id for p in service.list_role_permissions(engineer_role.role_id)}
    assert "substation_registry.write" in grants
    assert "substation_registry.read" not in grants


def test_viewer_receives_read_but_not_write(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    viewer_role = next(r for r in service.list_roles() if r.name == "Viewer")
    grants = {p.permission_id for p in service.list_role_permissions(viewer_role.role_id)}
    assert "substation_registry.read" in grants
    assert "substation_registry.write" not in grants


def test_running_before_iam_bootstrap_does_not_error(db_session: Session) -> None:
    """Permission catalog entries can be registered even before IAM's own
    bootstrap has created the baseline roles; role grants are simply
    skipped and can be applied by a later re-run (see bootstrap.py)."""
    run_bootstrap(db_session)  # IAM bootstrap has NOT run yet

    service = IAMService(db_session)
    permission_ids = {p.permission_id for p in service.list_permissions()}
    assert "substation_registry.write" in permission_ids
    assert db_session.query(RolePermission).count() == 0
