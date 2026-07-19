"""Tests for the Stage Setting Registry's permission-catalog registration
(bootstrap.py) — iam-module.md §7.3; ADR-020.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.models import RolePermission
from app.modules.iam.service import IAMService
from app.modules.stage_setting_registry.bootstrap import run_bootstrap
from app.modules.stage_setting_registry.service import StageSettingRegistryService

_ALL_PERMISSIONS = {
    "stage_setting_registry.read",
    "stage_setting_registry.manage",
    "stage_setting_registry.publish",
    "stage_setting_registry.enter_in_error",
}


def test_registers_all_four_permissions(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    permission_ids = {p.permission_id for p in service.list_permissions()}
    assert _ALL_PERMISSIONS <= permission_ids


def test_is_idempotent(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)
    run_bootstrap(db_session)  # second run must not duplicate or error

    service = IAMService(db_session)
    permission_ids = [p.permission_id for p in service.list_permissions()]
    assert permission_ids.count("stage_setting_registry.manage") == 1


def test_administrator_receives_all_four_permissions(db_session: Session) -> None:
    admin = bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    user_roles = service.list_user_roles(admin.user_id)
    admin_role = next(ur for ur in user_roles if ur.role.name == "Administrator")
    assert _ALL_PERMISSIONS <= set(admin_role.permissions)


def test_engineer_receives_read_and_manage_but_not_publish_or_enter_in_error(
    db_session: Session,
) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    engineer_role = next(r for r in service.list_roles() if r.name == "Engineer")
    grants = {p.permission_id for p in service.list_role_permissions(engineer_role.role_id)}
    assert "stage_setting_registry.read" in grants
    assert "stage_setting_registry.manage" in grants
    assert "stage_setting_registry.publish" not in grants
    assert "stage_setting_registry.enter_in_error" not in grants


def test_viewer_receives_read_only(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    viewer_role = next(r for r in service.list_roles() if r.name == "Viewer")
    grants = {p.permission_id for p in service.list_role_permissions(viewer_role.role_id)}
    assert grants == {"stage_setting_registry.read"}


def test_running_before_iam_bootstrap_does_not_error(db_session: Session) -> None:
    run_bootstrap(db_session)  # IAM bootstrap has NOT run yet

    service = IAMService(db_session)
    permission_ids = {p.permission_id for p in service.list_permissions()}
    assert "stage_setting_registry.manage" in permission_ids
    assert db_session.query(RolePermission).count() == 0


def test_does_not_seed_any_stage_setting_set(db_session: Session) -> None:
    """This sprint's own instructions: no default UFLS/UVLS thresholds are
    invented, and no Stage Setting Set is seeded unless the architecture
    explicitly defines one (it does not)."""
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    registry_service = StageSettingRegistryService(db_session)
    assert registry_service.list_sets() == []
