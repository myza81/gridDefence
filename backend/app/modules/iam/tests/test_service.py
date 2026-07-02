"""Business rule tests for IAMService — docs/architecture/iam-module.md §9.

Covers, among the rules already implemented: the mandated fail-closed
`hasPermission()` behaviour, username uniqueness, role name uniqueness, and
external identity uniqueness (Phase 1's required test list), plus the other
business rules this checkpoint's implementation already enforces.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.iam.exceptions import (
    DuplicateExternalIdentityError,
    DuplicateRoleNameError,
    DuplicateUsernameError,
    InactiveUserError,
    InvalidCredentialsError,
    NotFoundError,
    RoleRetiredError,
)
from app.modules.iam.models import RoleStatus, UserRole, UserStatus
from app.modules.iam.service import IAMService

ADMIN_PERMISSION = "iam.user.manage"


def _register_permission(service: IAMService, permission_id: str = ADMIN_PERMISSION) -> None:
    service.register_permission(
        permission_id=permission_id, label="Manage users", description=None, module_scope="iam"
    )


def _create_user(service: IAMService, username: str = "engineer1") -> uuid.UUID:
    user = service.create_user(
        username=username,
        display_name="Test Engineer",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    service.db.commit()
    return user.user_id


# --- Username uniqueness (mandated) ------------------------------------------------
class TestUsernameUniqueness:
    def test_duplicate_username_raises(self, db_session: Session) -> None:
        service = IAMService(db_session)
        _create_user(service, "engineer1")

        with pytest.raises(DuplicateUsernameError):
            service.create_user(
                username="engineer1",
                display_name="Someone Else",
                email=None,
                password="another-password",
                actor_user_id=None,
            )

    def test_duplicate_username_is_case_insensitive(self, db_session: Session) -> None:
        service = IAMService(db_session)
        _create_user(service, "Engineer1")

        with pytest.raises(DuplicateUsernameError):
            service.create_user(
                username="ENGINEER1",
                display_name="Someone Else",
                email=None,
                password="another-password",
                actor_user_id=None,
            )


# --- Role name uniqueness (mandated) -----------------------------------------------
class TestRoleNameUniqueness:
    def test_duplicate_role_name_raises(self, db_session: Session) -> None:
        service = IAMService(db_session)
        service.create_role(name="Engineer", description=None, actor_user_id=None)
        db_session.commit()

        with pytest.raises(DuplicateRoleNameError):
            service.create_role(name="Engineer", description="different", actor_user_id=None)


# --- External identity uniqueness (mandated) ----------------------------------------
class TestExternalIdentityUniqueness:
    def test_duplicate_active_mapping_raises(self, db_session: Session) -> None:
        service = IAMService(db_session)
        user_id = _create_user(service)
        other_user_id = _create_user(service, "engineer2")

        service.link_external_identity(
            user_id=user_id,
            external_principal_id="CN=engineer1,DC=example,DC=com",
            provider="ldap",
            actor_user_id=None,
        )
        db_session.commit()

        with pytest.raises(DuplicateExternalIdentityError):
            service.link_external_identity(
                user_id=other_user_id,
                external_principal_id="CN=engineer1,DC=example,DC=com",
                provider="ldap",
                actor_user_id=None,
            )

    def test_resolve_external_principal_returns_user_id(self, db_session: Session) -> None:
        service = IAMService(db_session)
        user_id = _create_user(service)
        service.link_external_identity(
            user_id=user_id,
            external_principal_id="CN=engineer1,DC=example,DC=com",
            provider="ldap",
            actor_user_id=None,
        )
        db_session.commit()

        resolved = service.resolve_external_principal("CN=engineer1,DC=example,DC=com", "ldap")
        assert resolved == user_id

    def test_resolve_external_principal_returns_none_when_unmapped(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        assert service.resolve_external_principal("unknown", "ldap") is None


# --- hasPermission fail-closed (mandated) --------------------------------------------
class TestHasPermissionFailsClosed:
    def test_unregistered_permission_code_returns_false(self, db_session: Session) -> None:
        service = IAMService(db_session)
        user_id = _create_user(service)

        assert service.has_permission(user_id, "not.a.real.permission") is False

    def test_unknown_user_returns_false(self, db_session: Session) -> None:
        service = IAMService(db_session)
        _register_permission(service)
        db_session.commit()

        assert service.has_permission(uuid.uuid4(), ADMIN_PERMISSION) is False

    def test_user_with_no_role_grant_returns_false(self, db_session: Session) -> None:
        service = IAMService(db_session)
        _register_permission(service)
        user_id = _create_user(service)
        db_session.commit()

        assert service.has_permission(user_id, ADMIN_PERMISSION) is False

    def test_inactive_user_returns_false_even_with_grant(self, db_session: Session) -> None:
        service = IAMService(db_session)
        _register_permission(service)
        user_id = _create_user(service)
        role = service.create_role(name="Manager", description=None, actor_user_id=None)
        service.grant_permission_to_role(
            role_id=role.role_id, permission_id=ADMIN_PERMISSION, actor_user_id=None
        )
        service.assign_role_to_user(user_id=user_id, role_id=role.role_id, actor_user_id=None)
        db_session.commit()

        user = service.repo.get_user_by_id(user_id)
        assert user is not None
        user.status = UserStatus.SUSPENDED
        db_session.commit()

        assert service.has_permission(user_id, ADMIN_PERMISSION) is False

    def test_true_only_after_permission_granted_via_active_role(self, db_session: Session) -> None:
        service = IAMService(db_session)
        _register_permission(service)
        user_id = _create_user(service)
        role = service.create_role(name="Manager", description=None, actor_user_id=None)
        db_session.commit()

        assert service.has_permission(user_id, ADMIN_PERMISSION) is False

        service.grant_permission_to_role(
            role_id=role.role_id, permission_id=ADMIN_PERMISSION, actor_user_id=None
        )
        service.assign_role_to_user(user_id=user_id, role_id=role.role_id, actor_user_id=None)
        db_session.commit()

        assert service.has_permission(user_id, ADMIN_PERMISSION) is True

    def test_revoked_role_grant_returns_false(self, db_session: Session) -> None:
        service = IAMService(db_session)
        _register_permission(service)
        user_id = _create_user(service)
        role = service.create_role(name="Manager", description=None, actor_user_id=None)
        service.grant_permission_to_role(
            role_id=role.role_id, permission_id=ADMIN_PERMISSION, actor_user_id=None
        )
        service.assign_role_to_user(user_id=user_id, role_id=role.role_id, actor_user_id=None)
        db_session.commit()
        assert service.has_permission(user_id, ADMIN_PERMISSION) is True

        service.revoke_role_from_user(user_id=user_id, role_id=role.role_id, actor_user_id=None)
        db_session.commit()

        assert service.has_permission(user_id, ADMIN_PERMISSION) is False


# --- Role lifecycle ------------------------------------------------------------------
class TestRoleLifecycle:
    def test_cannot_assign_a_retired_role(self, db_session: Session) -> None:
        service = IAMService(db_session)
        user_id = _create_user(service)
        role = service.create_role(name="Legacy", description=None, actor_user_id=None)
        role.status = RoleStatus.RETIRED
        db_session.commit()

        with pytest.raises(RoleRetiredError):
            service.assign_role_to_user(user_id=user_id, role_id=role.role_id, actor_user_id=None)

    def test_revoke_sets_revoked_at_rather_than_deleting_the_grant(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        user_id = _create_user(service)
        role = service.create_role(name="Manager", description=None, actor_user_id=None)
        service.assign_role_to_user(user_id=user_id, role_id=role.role_id, actor_user_id=None)
        db_session.commit()

        service.revoke_role_from_user(user_id=user_id, role_id=role.role_id, actor_user_id=None)
        db_session.commit()

        # No longer an *active* grant...
        assert service.list_user_roles(user_id) == []
        assert service.repo.get_active_user_role(user_id, role.role_id) is None

        # ...but the row itself still exists with revoked_at populated
        # (never deleted, CLAUDE.md §5.2).
        rows = db_session.query(UserRole).filter_by(user_id=user_id, role_id=role.role_id).all()
        assert len(rows) == 1
        assert rows[0].revoked_at is not None

    def test_assigning_an_already_active_grant_is_idempotent_not_an_error(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        user_id = _create_user(service)
        role = service.create_role(name="Manager", description=None, actor_user_id=None)
        db_session.commit()

        first = service.assign_role_to_user(
            user_id=user_id, role_id=role.role_id, actor_user_id=None
        )
        second = service.assign_role_to_user(
            user_id=user_id, role_id=role.role_id, actor_user_id=None
        )
        db_session.commit()

        assert first.id == second.id
        assert len(service.list_user_roles(user_id)) == 1


# --- Authentication --------------------------------------------------------------------
class TestAuthenticate:
    def test_wrong_password_raises_invalid_credentials(self, db_session: Session) -> None:
        service = IAMService(db_session)
        _create_user(service)

        with pytest.raises(InvalidCredentialsError):
            service.authenticate("engineer1", "wrong-password")

    def test_unknown_username_raises_invalid_credentials_not_not_found(
        self, db_session: Session
    ) -> None:
        """Never leaks whether the username exists (iam-module.md §9)."""
        service = IAMService(db_session)

        with pytest.raises(InvalidCredentialsError):
            service.authenticate("nobody", "irrelevant")

    def test_correct_credentials_return_the_user(self, db_session: Session) -> None:
        service = IAMService(db_session)
        user_id = _create_user(service)

        authenticated = service.authenticate("engineer1", "correct-horse-battery")
        assert authenticated.user_id == user_id

    def test_suspended_user_cannot_authenticate(self, db_session: Session) -> None:
        service = IAMService(db_session)
        user_id = _create_user(service)
        user = service.repo.get_user_by_id(user_id)
        assert user is not None
        user.status = UserStatus.SUSPENDED
        db_session.commit()

        with pytest.raises(InactiveUserError):
            service.authenticate("engineer1", "correct-horse-battery")


# --- Segregation of duties -------------------------------------------------------------
class TestAssertDifferentActors:
    def test_same_actor_returns_false(self) -> None:
        actor = uuid.uuid4()
        assert IAMService.assert_different_actors(actor, actor) is False

    def test_different_actors_returns_true(self) -> None:
        assert IAMService.assert_different_actors(uuid.uuid4(), uuid.uuid4()) is True


# --- listUserRoles ----------------------------------------------------------------------
class TestListUserRoles:
    def test_aggregates_permissions_from_the_granted_role(self, db_session: Session) -> None:
        service = IAMService(db_session)
        _register_permission(service, "iam.audit.read")
        user_id = _create_user(service)
        role = service.create_role(name="Auditor", description=None, actor_user_id=None)
        service.grant_permission_to_role(
            role_id=role.role_id, permission_id="iam.audit.read", actor_user_id=None
        )
        service.assign_role_to_user(user_id=user_id, role_id=role.role_id, actor_user_id=None)
        db_session.commit()

        summaries = service.list_user_roles(user_id)

        assert len(summaries) == 1
        assert summaries[0].role.role_id == role.role_id
        assert summaries[0].permissions == ["iam.audit.read"]


# --- Grant/permission not-found guards -------------------------------------------------
class TestGrantGuards:
    def test_granting_permission_to_unknown_role_raises_not_found(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        _register_permission(service)
        db_session.commit()

        with pytest.raises(NotFoundError):
            service.grant_permission_to_role(
                role_id=uuid.uuid4(), permission_id=ADMIN_PERMISSION, actor_user_id=None
            )

    def test_granting_unregistered_permission_raises_not_found(self, db_session: Session) -> None:
        service = IAMService(db_session)
        role = service.create_role(name="Manager", description=None, actor_user_id=None)
        db_session.commit()

        with pytest.raises(NotFoundError):
            service.grant_permission_to_role(
                role_id=role.role_id, permission_id="not.registered", actor_user_id=None
            )
