"""Bootstrap the initial Administrator account, baseline system roles, and
IAM's own permission catalog entries.

Idempotent: safe to run on every startup/deploy. Each step checks before
acting, so a partially-completed prior run (or a fresh run against an
already-bootstrapped database) never duplicates data or fails.

Implements iam-module.md §9 rule 7 (the bootstrap exception): rather than
exercising the schema's nullable `created_by_user_id`/`changed_by_user_id`
allowance, the bootstrap Administrator **self-references its own `user_id`**
as its creator and as the actor on its own audit trail — a stronger
realization of "never a silently missing or null actor" than the minimum the
architecture requires (see Phase 1's final report for this design choice).

Run standalone:
    python -m app.modules.iam.bootstrap
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.modules.iam import security
from app.modules.iam.models import (
    IAMAuditLog,
    Role,
    RolePermission,
    RoleStatus,
    User,
    UserCredential,
    UserRole,
    UserStatus,
)
from app.modules.iam.repository import IAMRepository
from app.modules.iam.service import IAMService

logger = logging.getLogger(__name__)

# IAM's own permission catalog (iam-module.md §7.9) — registered here as part
# of IAM's own deployment/seed process, per §7.3's "each module registers its
# own permission codes." No other module's permissions are registered here.
IAM_PERMISSIONS: list[dict[str, str]] = [
    {
        "permission_id": "iam.user.manage",
        "label": "Manage users",
        "description": "Create/edit users and grant or revoke their role assignments.",
        "module_scope": "iam",
    },
    {
        "permission_id": "iam.role.manage",
        "label": "Manage roles and permissions",
        "description": (
            "Create/edit roles and grant or revoke permissions to a role. "
            "The most powerful permission in the system — it can grant any "
            "other permission (iam-module.md §15)."
        ),
        "module_scope": "iam",
    },
    {
        "permission_id": "iam.audit.read",
        "label": "Read IAM audit log",
        "description": (
            "Read access to IAM's own audit trail, gated separately from "
            "general read access (iam-module.md §14)."
        ),
        "module_scope": "iam",
    },
]

# System-defined baseline roles (iam-module.md §7.2, §9 rule 5).
# "Administrator" is granted every currently-registered permission at
# bootstrap time; "Engineer" and "Viewer" start with none — future modules
# grant their own permissions to these baseline roles as part of their own
# seed process (iam-module.md §7.3), not here.
SYSTEM_ROLES: list[dict[str, str]] = [
    {"name": "Administrator", "description": "Full administrative access to GridDefence."},
    {
        "name": "Engineer",
        "description": (
            "General engineering baseline role. Modules grant their own "
            "Editor-tier permissions to this role as they are built."
        ),
    },
    {
        "name": "Viewer",
        "description": (
            "Baseline read-only role. Modules grant their own read "
            "permissions to this role as they are built; sensitive-tier "
            "read permissions (e.g. Critical Infrastructure) are granted "
            "separately, never bundled here."
        ),
    },
]


def _get_or_create_role(
    repo: IAMRepository, *, name: str, description: str, actor_id: uuid.UUID
) -> Role:
    existing = repo.get_role_by_name(name)
    if existing is not None:
        return existing

    role = repo.add_role(
        Role(
            role_id=uuid.uuid4(),
            name=name,
            description=description,
            is_system_role=True,
            status=RoleStatus.ACTIVE,
            created_by_user_id=actor_id,
            updated_by_user_id=actor_id,
        )
    )
    repo.add_audit_log(
        IAMAuditLog(
            entity_type="Role",
            entity_id=str(role.role_id),
            changed_by_user_id=actor_id,
            new_value=f"name={name}",
            change_reason="System bootstrap: baseline system role created",
        )
    )
    return role


def run_bootstrap(db: Session) -> User:
    """Idempotently ensure the bootstrap Administrator, baseline roles, and
    IAM's own permission catalog all exist. Returns the Administrator user
    (whether newly created or pre-existing).
    """
    settings = get_settings()
    repo = IAMRepository(db)
    service = IAMService(db)

    existing_admin = repo.get_user_by_username(settings.bootstrap_admin_username)
    if existing_admin is not None:
        logger.info(
            "Bootstrap: Administrator '%s' already exists — nothing to do.", existing_admin.username
        )
        return existing_admin

    # The bootstrap Administrator is its own creator (self-referential
    # user_id, generated client-side before insert) — see module docstring.
    admin_id = uuid.uuid4()

    admin_user = repo.add_user(
        User(
            user_id=admin_id,
            username=settings.bootstrap_admin_username,
            display_name="System Administrator",
            email=settings.bootstrap_admin_email,
            status=UserStatus.ACTIVE,
            created_by_user_id=admin_id,
            updated_by_user_id=admin_id,
        )
    )
    repo.add_credential(
        UserCredential(
            user_id=admin_id,
            password_hash=security.hash_password(settings.bootstrap_admin_password),
            hash_algorithm=security.HASH_ALGORITHM,
        )
    )
    repo.add_audit_log(
        IAMAuditLog(
            entity_type="User",
            entity_id=str(admin_id),
            changed_by_user_id=admin_id,
            new_value=f"username={settings.bootstrap_admin_username}",
            change_reason="System bootstrap: initial Administrator account created",
        )
    )

    # Baseline system roles.
    admin_role = _get_or_create_role(
        repo, name="Administrator", description=SYSTEM_ROLES[0]["description"], actor_id=admin_id
    )
    _get_or_create_role(
        repo, name="Engineer", description=SYSTEM_ROLES[1]["description"], actor_id=admin_id
    )
    _get_or_create_role(
        repo, name="Viewer", description=SYSTEM_ROLES[2]["description"], actor_id=admin_id
    )

    # IAM's own permission catalog (idempotent — service.register_permission
    # is a no-op if already registered).
    registered_permissions = [
        service.register_permission(
            permission_id=p["permission_id"],
            label=p["label"],
            description=p["description"],
            module_scope=p["module_scope"],
        )
        for p in IAM_PERMISSIONS
    ]

    # Administrator gets every currently-registered permission.
    for permission in registered_permissions:
        if repo.get_role_permission(admin_role.role_id, permission.permission_id) is None:
            repo.add_role_permission(
                RolePermission(
                    role_id=admin_role.role_id,
                    permission_id=permission.permission_id,
                    granted_by_user_id=admin_id,
                )
            )
            repo.add_audit_log(
                IAMAuditLog(
                    entity_type="RolePermission",
                    entity_id=f"{admin_role.role_id}:{permission.permission_id}",
                    changed_by_user_id=admin_id,
                    new_value=f"role=Administrator permission={permission.permission_id}",
                    change_reason="System bootstrap: baseline Administrator grant",
                )
            )

    # Assign the Administrator role to the bootstrap user.
    if repo.get_active_user_role(admin_id, admin_role.role_id) is None:
        repo.add_user_role(
            UserRole(user_id=admin_id, role_id=admin_role.role_id, granted_by_user_id=admin_id)
        )
        repo.add_audit_log(
            IAMAuditLog(
                entity_type="UserRole",
                entity_id=f"{admin_id}:{admin_role.role_id}",
                changed_by_user_id=admin_id,
                new_value="role=Administrator",
                change_reason="System bootstrap: initial Administrator role assignment",
            )
        )

    db.commit()
    logger.info("Bootstrap: created Administrator '%s'.", admin_user.username)
    return admin_user


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        run_bootstrap(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
