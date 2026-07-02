"""IAM repository layer (CLAUDE.md §14) — pure persistence access.

No business rules, no permission checks, no audit writing live here — that
is `service.py`'s responsibility. This layer only knows how to read and
write rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.iam.models import (
    ExternalIdentityMapping,
    IAMAuditLog,
    Permission,
    Role,
    RolePermission,
    User,
    UserCredential,
    UserRole,
)


class IAMRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- User -----------------------------------------------------------------
    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_user_by_username(self, username: str) -> User | None:
        stmt = select(User).where(func.lower(User.username) == username.lower())
        return self.db.execute(stmt).scalar_one_or_none()

    def add_user(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user

    def list_users(self, offset: int, limit: int) -> tuple[list[User], int]:
        total = self.db.execute(select(func.count()).select_from(User)).scalar_one()
        stmt = select(User).order_by(User.username).offset(offset).limit(limit)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def any_user_exists(self) -> bool:
        return self.db.execute(select(User.user_id).limit(1)).first() is not None

    # --- UserCredential ---------------------------------------------------------
    def get_credential(self, user_id: uuid.UUID) -> UserCredential | None:
        return self.db.get(UserCredential, user_id)

    def add_credential(self, credential: UserCredential) -> UserCredential:
        self.db.add(credential)
        self.db.flush()
        return credential

    # --- Role ---------------------------------------------------------------------
    def get_role_by_id(self, role_id: uuid.UUID) -> Role | None:
        return self.db.get(Role, role_id)

    def get_role_by_name(self, name: str) -> Role | None:
        stmt = select(Role).where(func.lower(Role.name) == name.lower())
        return self.db.execute(stmt).scalar_one_or_none()

    def add_role(self, role: Role) -> Role:
        self.db.add(role)
        self.db.flush()
        return role

    def list_roles(self) -> list[Role]:
        return list(self.db.execute(select(Role).order_by(Role.name)).scalars().all())

    # --- Permission -------------------------------------------------------------
    def get_permission(self, permission_id: str) -> Permission | None:
        return self.db.get(Permission, permission_id)

    def add_permission(self, permission: Permission) -> Permission:
        self.db.add(permission)
        self.db.flush()
        return permission

    def list_permissions(self) -> list[Permission]:
        return list(
            self.db.execute(select(Permission).order_by(Permission.permission_id)).scalars().all()
        )

    # --- RolePermission -----------------------------------------------------------
    def get_role_permission(self, role_id: uuid.UUID, permission_id: str) -> RolePermission | None:
        return self.db.get(RolePermission, (role_id, permission_id))

    def add_role_permission(self, grant: RolePermission) -> RolePermission:
        self.db.add(grant)
        self.db.flush()
        return grant

    def delete_role_permission(self, grant: RolePermission) -> None:
        self.db.delete(grant)
        self.db.flush()

    def list_role_permissions(self, role_id: uuid.UUID) -> list[RolePermission]:
        stmt = select(RolePermission).where(RolePermission.role_id == role_id)
        return list(self.db.execute(stmt).scalars().all())

    # --- UserRole -------------------------------------------------------------------
    def get_active_user_role(self, user_id: uuid.UUID, role_id: uuid.UUID) -> UserRole | None:
        stmt = select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
            UserRole.revoked_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def add_user_role(self, user_role: UserRole) -> UserRole:
        self.db.add(user_role)
        self.db.flush()
        return user_role

    def list_active_user_roles(self, user_id: uuid.UUID) -> list[UserRole]:
        stmt = select(UserRole).where(UserRole.user_id == user_id, UserRole.revoked_at.is_(None))
        return list(self.db.execute(stmt).scalars().all())

    def revoke_user_role(self, user_role: UserRole, revoked_at: datetime) -> None:
        user_role.revoked_at = revoked_at
        self.db.flush()

    # --- ExternalIdentityMapping ------------------------------------------------------
    def get_active_external_identity(
        self, external_principal_id: str, provider: str
    ) -> ExternalIdentityMapping | None:
        stmt = select(ExternalIdentityMapping).where(
            ExternalIdentityMapping.external_principal_id == external_principal_id,
            ExternalIdentityMapping.provider == provider,
            ExternalIdentityMapping.unlinked_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def add_external_identity_mapping(
        self, mapping: ExternalIdentityMapping
    ) -> ExternalIdentityMapping:
        self.db.add(mapping)
        self.db.flush()
        return mapping

    # --- Audit log ----------------------------------------------------------------
    def add_audit_log(self, entry: IAMAuditLog) -> IAMAuditLog:
        self.db.add(entry)
        self.db.flush()
        return entry
