"""IAM service layer (CLAUDE.md §14) — business rules, transactions,
orchestration, and audit writing live here, and only here (CLAUDE.md A1:
IAM's own tables are written to exclusively by this layer).

Implements the five service interfaces named in
docs/architecture/iam-module.md §13 and docs/architecture/
implementation-plan.md Phase 1: hasPermission, getUser,
resolveExternalPrincipal, assertDifferentActors, listUserRoles — plus the
CRUD/orchestration operations every module document assumes IAM already
provides.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.iam import security
from app.modules.iam.exceptions import (
    DuplicateExternalIdentityError,
    DuplicatePermissionError,
    DuplicateRoleNameError,
    DuplicateUsernameError,
    InactiveUserError,
    InvalidCredentialsError,
    NotFoundError,
    RoleRetiredError,
)
from app.modules.iam.models import (
    ExternalIdentityMapping,
    IAMAuditLog,
    Permission,
    Role,
    RolePermission,
    RoleStatus,
    User,
    UserCredential,
    UserRole,
    UserStatus,
)
from app.modules.iam.repository import IAMRepository
from app.modules.iam.schemas import (
    PermissionSummary,
    RoleSummary,
    UserRoleSummary,
    UserSummary,
)


class IAMService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = IAMRepository(db)

    # --- internal audit helper --------------------------------------------------
    def _audit(
        self,
        *,
        entity_type: str,
        entity_id: str,
        changed_by_user_id: uuid.UUID | None,
        field_name: str | None = None,
        old_value: str | None = None,
        new_value: str | None = None,
        change_reason: str | None = None,
    ) -> None:
        """Every write to an owned entity is audited (iam-module.md §14).

        `changed_by_user_id` is nullable only for the bootstrap exception
        (iam-module.md §9 rule 7); in practice the bootstrap flow always
        supplies a real, self-referential user_id (see bootstrap.py), so this
        is exercised as a schema allowance, not a routine null.
        """
        self.repo.add_audit_log(
            IAMAuditLog(
                entity_type=entity_type,
                entity_id=entity_id,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                changed_by_user_id=changed_by_user_id,
                change_reason=change_reason,
            )
        )

    # --- Users --------------------------------------------------------------------
    def create_user(
        self,
        *,
        username: str,
        display_name: str,
        email: str | None,
        password: str,
        actor_user_id: uuid.UUID | None,
        change_reason: str = "User created",
    ) -> User:
        """Create a locally-authenticating user (iam-module.md §9 rule 1, 2)."""
        if self.repo.get_user_by_username(username) is not None:
            raise DuplicateUsernameError(username)

        user = self.repo.add_user(
            User(
                user_id=uuid.uuid4(),
                username=username,
                display_name=display_name,
                email=email,
                status=UserStatus.ACTIVE,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )
        self.repo.add_credential(
            UserCredential(
                user_id=user.user_id,
                password_hash=security.hash_password(password),
                hash_algorithm=security.HASH_ALGORITHM,
            )
        )
        self._audit(
            entity_type="User",
            entity_id=str(user.user_id),
            changed_by_user_id=actor_user_id,
            new_value=f"username={username}",
            change_reason=change_reason,
        )
        return user

    def authenticate(self, username: str, password: str) -> User:
        """Local username/password authentication only (Phase 1 scope —
        iam-module.md §4: LDAP/AD/OAuth/OIDC/MFA/SSO are Future Extensions,
        not implemented here).

        Deliberately raises the same `InvalidCredentialsError` for "user not
        found," "no local credential," and "wrong password" — never leaking
        which one occurred.
        """
        user = self.repo.get_user_by_username(username)
        if user is None:
            raise InvalidCredentialsError()

        credential = self.repo.get_credential(user.user_id)
        if credential is None:
            raise InvalidCredentialsError()

        if not security.verify_password(password, credential.password_hash):
            raise InvalidCredentialsError()

        if user.status != UserStatus.ACTIVE:
            # Authorization never varies by authentication method (§7.6), but
            # a suspended/deactivated user must not be able to establish a
            # session at all — CLAUDE.md A10 baseline.
            raise InactiveUserError()

        return user

    def get_user(self, user_id: uuid.UUID) -> UserSummary | None:
        """`getUser(user_id) -> user summary` — iam-module.md §13."""
        user = self.repo.get_user_by_id(user_id)
        return UserSummary.model_validate(user) if user else None

    def list_users(self, *, page: int, page_size: int) -> tuple[list[UserSummary], int]:
        items, total = self.repo.list_users(offset=(page - 1) * page_size, limit=page_size)
        return [UserSummary.model_validate(u) for u in items], total

    # --- Roles --------------------------------------------------------------------
    def create_role(
        self,
        *,
        name: str,
        description: str | None,
        actor_user_id: uuid.UUID | None,
        is_system_role: bool = False,
    ) -> Role:
        """Roles are configurable business entities (iam-module.md §7.2,
        §9 rule 5)."""
        if self.repo.get_role_by_name(name) is not None:
            raise DuplicateRoleNameError(name)

        role = self.repo.add_role(
            Role(
                role_id=uuid.uuid4(),
                name=name,
                description=description,
                is_system_role=is_system_role,
                status=RoleStatus.ACTIVE,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )
        self._audit(
            entity_type="Role",
            entity_id=str(role.role_id),
            changed_by_user_id=actor_user_id,
            new_value=f"name={name}",
            change_reason="Role created",
        )
        return role

    def list_roles(self) -> list[RoleSummary]:
        return [RoleSummary.model_validate(r) for r in self.repo.list_roles()]

    # --- Permissions --------------------------------------------------------------
    def register_permission(
        self,
        *,
        permission_id: str,
        label: str,
        description: str | None,
        module_scope: str,
    ) -> Permission:
        """Idempotent-safe registration of a catalog entry (iam-module.md
        §7.3) — used by each module's own seed/bootstrap process. Returns the
        existing row unchanged if already registered (a `Permission`'s
        meaning is immutable once created, §9 rule 4 — this method never
        updates an existing row's label/description/scope).
        """
        existing = self.repo.get_permission(permission_id)
        if existing is not None:
            return existing

        permission = self.repo.add_permission(
            Permission(
                permission_id=permission_id,
                label=label,
                description=description,
                module_scope=module_scope,
            )
        )
        self._audit(
            entity_type="Permission",
            entity_id=permission_id,
            changed_by_user_id=None,
            new_value=f"label={label}",
            change_reason="Permission catalog entry registered",
        )
        return permission

    def register_permission_strict(
        self, *, permission_id: str, label: str, description: str | None, module_scope: str
    ) -> Permission:
        """Same as `register_permission` but raises if already registered —
        for explicit API-driven registration rather than idempotent seeding.
        """
        if self.repo.get_permission(permission_id) is not None:
            raise DuplicatePermissionError(permission_id)
        return self.register_permission(
            permission_id=permission_id,
            label=label,
            description=description,
            module_scope=module_scope,
        )

    def list_permissions(self) -> list[PermissionSummary]:
        return [PermissionSummary.model_validate(p) for p in self.repo.list_permissions()]

    # --- Role <-> Permission grants -------------------------------------------------
    def grant_permission_to_role(
        self, *, role_id: uuid.UUID, permission_id: str, actor_user_id: uuid.UUID | None
    ) -> RolePermission:
        """A RolePermission grant must reference an existing Permission
        (iam-module.md §10). Idempotent: granting an already-granted
        permission is a no-op, not an error.
        """
        role = self.repo.get_role_by_id(role_id)
        if role is None:
            raise NotFoundError(f"Role {role_id} not found")
        permission = self.repo.get_permission(permission_id)
        if permission is None:
            raise NotFoundError(f"Permission '{permission_id}' not found")

        existing = self.repo.get_role_permission(role_id, permission_id)
        if existing is not None:
            return existing

        grant = self.repo.add_role_permission(
            RolePermission(
                role_id=role_id, permission_id=permission_id, granted_by_user_id=actor_user_id
            )
        )
        self._audit(
            entity_type="RolePermission",
            entity_id=f"{role_id}:{permission_id}",
            changed_by_user_id=actor_user_id,
            new_value=f"role={role.name} permission={permission_id}",
            change_reason="Permission granted to role",
        )
        return grant

    def revoke_permission_from_role(
        self, *, role_id: uuid.UUID, permission_id: str, actor_user_id: uuid.UUID | None
    ) -> None:
        grant = self.repo.get_role_permission(role_id, permission_id)
        if grant is None:
            raise NotFoundError(
                f"Role {role_id} does not have permission '{permission_id}' granted"
            )

        self.repo.delete_role_permission(grant)
        self._audit(
            entity_type="RolePermission",
            entity_id=f"{role_id}:{permission_id}",
            changed_by_user_id=actor_user_id,
            old_value=f"role={role_id} permission={permission_id}",
            change_reason="Permission revoked from role",
        )

    def list_role_permissions(self, role_id: uuid.UUID) -> list[PermissionSummary]:
        grants = self.repo.list_role_permissions(role_id)
        permissions = [self.repo.get_permission(g.permission_id) for g in grants]
        return [PermissionSummary.model_validate(p) for p in permissions if p is not None]

    # --- User <-> Role grants ---------------------------------------------------------
    def assign_role_to_user(
        self, *, user_id: uuid.UUID, role_id: uuid.UUID, actor_user_id: uuid.UUID | None
    ) -> UserRole:
        """A UserRole grant must reference an existing, non-Retired Role
        (iam-module.md §10). Idempotent: assigning an already-active grant
        is a no-op, not an error (§9 rule 6 — grants are never duplicated).
        """
        user = self.repo.get_user_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        role = self.repo.get_role_by_id(role_id)
        if role is None:
            raise NotFoundError(f"Role {role_id} not found")
        if role.status != RoleStatus.ACTIVE:
            raise RoleRetiredError(role.name)

        existing = self.repo.get_active_user_role(user_id, role_id)
        if existing is not None:
            return existing

        grant = self.repo.add_user_role(
            UserRole(user_id=user_id, role_id=role_id, granted_by_user_id=actor_user_id)
        )
        self._audit(
            entity_type="UserRole",
            entity_id=str(grant.id),
            changed_by_user_id=actor_user_id,
            new_value=f"user={user.username} role={role.name}",
            change_reason="Role granted to user",
        )
        return grant

    def revoke_role_from_user(
        self, *, user_id: uuid.UUID, role_id: uuid.UUID, actor_user_id: uuid.UUID | None
    ) -> None:
        """Ends a grant by setting `revoked_at` — never deletes the row
        (iam-module.md §9 rule 6, CLAUDE.md §5.2)."""
        grant = self.repo.get_active_user_role(user_id, role_id)
        if grant is None:
            raise NotFoundError(f"User {user_id} does not have an active grant of role {role_id}")

        self.repo.revoke_user_role(grant, revoked_at=datetime.now(UTC))
        self._audit(
            entity_type="UserRole",
            entity_id=str(grant.id),
            changed_by_user_id=actor_user_id,
            old_value="active",
            new_value="revoked",
            change_reason="Role revoked from user",
        )

    def list_user_roles(self, user_id: uuid.UUID) -> list[UserRoleSummary]:
        """`listUserRoles(user_id) -> roles/permissions summary` —
        iam-module.md §13."""
        summaries: list[UserRoleSummary] = []
        for user_role in self.repo.list_active_user_roles(user_id):
            role = self.repo.get_role_by_id(user_role.role_id)
            if role is None:
                continue
            grants = self.repo.list_role_permissions(role.role_id)
            summaries.append(
                UserRoleSummary(
                    role=RoleSummary.model_validate(role),
                    granted_at=user_role.granted_at,
                    permissions=[g.permission_id for g in grants],
                )
            )
        return summaries

    # --- External identity mapping -----------------------------------------------------
    def link_external_identity(
        self,
        *,
        user_id: uuid.UUID,
        external_principal_id: str,
        provider: str,
        actor_user_id: uuid.UUID | None,
    ) -> ExternalIdentityMapping:
        """Structural support for future federation (iam-module.md §7.5,
        §17) — not exercised by Phase 1's local-only authentication, but the
        data model and this method exist so later phases need no schema
        change to use it.
        """
        if self.repo.get_user_by_id(user_id) is None:
            raise NotFoundError(f"User {user_id} not found")
        if self.repo.get_active_external_identity(external_principal_id, provider) is not None:
            raise DuplicateExternalIdentityError(external_principal_id, provider)

        mapping = self.repo.add_external_identity_mapping(
            ExternalIdentityMapping(
                user_id=user_id,
                external_principal_id=external_principal_id,
                provider=provider,
                linked_by_user_id=actor_user_id,
            )
        )
        self._audit(
            entity_type="ExternalIdentityMapping",
            entity_id=str(mapping.id),
            changed_by_user_id=actor_user_id,
            new_value=f"user={user_id} provider={provider}",
            change_reason="External identity linked",
        )
        return mapping

    def resolve_external_principal(
        self, external_principal_id: str, provider: str
    ) -> uuid.UUID | None:
        """`resolveExternalPrincipal(external_principal_id, provider) ->
        user_id` — iam-module.md §13."""
        mapping = self.repo.get_active_external_identity(external_principal_id, provider)
        return mapping.user_id if mapping else None

    # --- Authorization decision point --------------------------------------------------
    def has_permission(self, user_id: uuid.UUID, permission_code: str) -> bool:
        """`hasPermission(user_id, permission_code) -> boolean` —
        iam-module.md §13. **Fails closed** on any ambiguity (§9 rule 11):
        unregistered permission code, unknown/inactive user, or no active
        grant all resolve to `False`, never `True`.
        """
        if self.repo.get_permission(permission_code) is None:
            return False

        user = self.repo.get_user_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            return False

        stmt = (
            select(RolePermission.permission_id)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .join(Role, Role.role_id == RolePermission.role_id)
            .where(
                UserRole.user_id == user_id,
                UserRole.revoked_at.is_(None),
                Role.status == RoleStatus.ACTIVE,
                RolePermission.permission_id == permission_code,
            )
            .limit(1)
        )
        return self.db.execute(stmt).first() is not None

    # --- Segregation-of-duties helper --------------------------------------------------
    @staticmethod
    def assert_different_actors(user_id_a: uuid.UUID, user_id_b: uuid.UUID) -> bool:
        """`assertDifferentActors(user_id_a, user_id_b) -> boolean` —
        iam-module.md §13, §7.7. A reusable convenience for scheme modules
        implementing their own segregation-of-duties rule (e.g. "the Draft
        editor may not also be the Approver") — IAM does not itself enforce
        any such scheme-specific rule (§9 rule 8).
        """
        return user_id_a != user_id_b
