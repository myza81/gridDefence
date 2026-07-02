"""Bootstrap Administrator tests — iam-module.md §9 rule 7,
docs/architecture/implementation-plan.md Phase 1's mandated test list.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.iam.bootstrap import run_bootstrap
from app.modules.iam.models import RolePermission, User, UserRole
from app.modules.iam.service import IAMService


def test_bootstrap_creates_the_administrator(db_session: Session) -> None:
    settings = get_settings()

    admin = run_bootstrap(db_session)

    assert admin.username == settings.bootstrap_admin_username
    assert admin.status == "active"
    # Self-referential: the bootstrap Administrator is its own creator, never
    # a null actor (a stronger realization of the schema's minimum allowance).
    assert admin.created_by_user_id == admin.user_id
    assert admin.updated_by_user_id == admin.user_id


def test_bootstrap_is_idempotent(db_session: Session) -> None:
    first_admin = run_bootstrap(db_session)
    second_admin = run_bootstrap(db_session)

    assert first_admin.user_id == second_admin.user_id
    assert db_session.query(User).count() == 1
    assert db_session.query(UserRole).filter_by(user_id=first_admin.user_id).count() == 1


def test_bootstrap_grants_the_administrator_every_registered_permission(
    db_session: Session,
) -> None:
    admin = run_bootstrap(db_session)
    service = IAMService(db_session)

    user_roles = service.list_user_roles(admin.user_id)
    assert len(user_roles) == 1
    assert user_roles[0].role.name == "Administrator"

    registered_permission_ids = {p.permission_id for p in service.list_permissions()}
    granted_permission_ids = set(user_roles[0].permissions)
    assert granted_permission_ids == registered_permission_ids
    assert granted_permission_ids  # non-empty: at least IAM's own catalog


def test_bootstrap_creates_engineer_and_viewer_roles_with_no_permissions(
    db_session: Session,
) -> None:
    run_bootstrap(db_session)
    service = IAMService(db_session)

    roles_by_name = {r.name: r for r in service.list_roles()}
    assert {"Administrator", "Engineer", "Viewer"} <= roles_by_name.keys()

    for role_name in ("Engineer", "Viewer"):
        role = roles_by_name[role_name]
        grants = db_session.query(RolePermission).filter_by(role_id=role.role_id).count()
        assert grants == 0


def test_bootstrap_administrator_can_authenticate_with_the_configured_password(
    db_session: Session,
) -> None:
    settings = get_settings()
    run_bootstrap(db_session)
    service = IAMService(db_session)

    authenticated = service.authenticate(
        settings.bootstrap_admin_username, settings.bootstrap_admin_password
    )
    assert authenticated.username == settings.bootstrap_admin_username
