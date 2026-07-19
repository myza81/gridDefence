"""IAM Completion Sprint — user status lifecycle and the last-active-
Administrator safeguard (docs/architecture/iam-module.md §8).

Kept as its own file, separate from `test_service.py`'s original business
rule tests, given the volume of scenarios this sprint's own explicit test
list requires.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.iam.bootstrap import run_bootstrap
from app.modules.iam.exceptions import (
    InactiveUserError,
    InvalidUserStatusTransitionError,
    LastActiveAdministratorError,
    NotFoundError,
    StatusChangeReasonRequiredError,
    UserStatusUnchangedError,
)
from app.modules.iam.models import IAMAuditLog, UserStatus
from app.modules.iam.service import IAMService


def _bootstrap_administrator(db_session: Session) -> uuid.UUID:
    """A real Administrator, with the real system role and every
    permission, via the actual bootstrap entry point — not a hand-rolled
    substitute."""
    admin = run_bootstrap(db_session)
    db_session.commit()
    return admin.user_id


def _create_plain_user(service: IAMService, username: str) -> uuid.UUID:
    user = service.create_user(
        username=username,
        display_name=username,
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    service.db.commit()
    return user.user_id


def _make_second_administrator(service: IAMService, username: str) -> uuid.UUID:
    user_id = _create_plain_user(service, username)
    admin_role = service.repo.get_role_by_name("Administrator")
    assert admin_role is not None
    service.assign_role_to_user(user_id=user_id, role_id=admin_role.role_id, actor_user_id=None)
    service.db.commit()
    return user_id


# --- Status transitions: allowed edges ------------------------------------------------
class TestAllowedStatusTransitions:
    def test_active_to_suspended_succeeds(self, db_session: Session) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        second_admin_id = _make_second_administrator(service, "second_admin")

        user = service.set_user_status(
            second_admin_id,
            status=UserStatus.SUSPENDED,
            change_reason="Leaving the team",
            actor_user_id=admin_id,
        )
        db_session.commit()

        assert user.status == UserStatus.SUSPENDED

    def test_suspended_to_active_succeeds(self, db_session: Session) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")
        service.set_user_status(
            target_id, status=UserStatus.SUSPENDED, change_reason="temp", actor_user_id=admin_id
        )
        db_session.commit()

        user = service.set_user_status(
            target_id,
            status=UserStatus.ACTIVE,
            change_reason="Back from leave",
            actor_user_id=admin_id,
        )
        db_session.commit()

        assert user.status == UserStatus.ACTIVE

    def test_active_to_deactivated_succeeds_directly(self, db_session: Session) -> None:
        """Active -> Deactivated is a direct edge, not required to pass
        through Suspended first (this sprint's own explicit reading of
        iam-module.md §8 — not assumed to be a strictly linear chain)."""
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")

        user = service.set_user_status(
            target_id,
            status=UserStatus.DEACTIVATED,
            change_reason="Account retired",
            actor_user_id=admin_id,
        )
        db_session.commit()

        assert user.status == UserStatus.DEACTIVATED

    def test_suspended_to_deactivated_succeeds(self, db_session: Session) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")
        service.set_user_status(
            target_id, status=UserStatus.SUSPENDED, change_reason="temp", actor_user_id=admin_id
        )
        db_session.commit()

        user = service.set_user_status(
            target_id,
            status=UserStatus.DEACTIVATED,
            change_reason="Never returned",
            actor_user_id=admin_id,
        )
        db_session.commit()

        assert user.status == UserStatus.DEACTIVATED


# --- Status transitions: forbidden edges (Deactivated is terminal) --------------------
class TestForbiddenStatusTransitions:
    def test_deactivated_to_active_is_rejected(self, db_session: Session) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")
        service.set_user_status(
            target_id,
            status=UserStatus.DEACTIVATED,
            change_reason="retired",
            actor_user_id=admin_id,
        )
        db_session.commit()

        with pytest.raises(InvalidUserStatusTransitionError):
            service.set_user_status(
                target_id,
                status=UserStatus.ACTIVE,
                change_reason="Trying to come back",
                actor_user_id=admin_id,
            )

    def test_deactivated_to_suspended_is_rejected(self, db_session: Session) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")
        service.set_user_status(
            target_id,
            status=UserStatus.DEACTIVATED,
            change_reason="retired",
            actor_user_id=admin_id,
        )
        db_session.commit()

        with pytest.raises(InvalidUserStatusTransitionError):
            service.set_user_status(
                target_id,
                status=UserStatus.SUSPENDED,
                change_reason="attempt",
                actor_user_id=admin_id,
            )


# --- No-op rejection --------------------------------------------------------------------
class TestNoOpRejection:
    def test_active_to_active_is_rejected(self, db_session: Session) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")

        with pytest.raises(UserStatusUnchangedError):
            service.set_user_status(
                target_id, status=UserStatus.ACTIVE, change_reason="no-op", actor_user_id=admin_id
            )

    def test_suspended_to_suspended_is_rejected(self, db_session: Session) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")
        service.set_user_status(
            target_id, status=UserStatus.SUSPENDED, change_reason="temp", actor_user_id=admin_id
        )
        db_session.commit()

        with pytest.raises(UserStatusUnchangedError):
            service.set_user_status(
                target_id,
                status=UserStatus.SUSPENDED,
                change_reason="no-op",
                actor_user_id=admin_id,
            )


# --- Mandatory reason ---------------------------------------------------------------------
class TestMandatoryReason:
    def test_empty_reason_is_rejected(self, db_session: Session) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")

        with pytest.raises(StatusChangeReasonRequiredError):
            service.set_user_status(
                target_id, status=UserStatus.SUSPENDED, change_reason="", actor_user_id=admin_id
            )

    def test_whitespace_only_reason_is_rejected(self, db_session: Session) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")

        with pytest.raises(StatusChangeReasonRequiredError):
            service.set_user_status(
                target_id, status=UserStatus.SUSPENDED, change_reason="   ", actor_user_id=admin_id
            )


# --- User not found ------------------------------------------------------------------------
class TestUserNotFound:
    def test_unknown_user_id_raises_not_found(self, db_session: Session) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)

        with pytest.raises(NotFoundError):
            service.set_user_status(
                uuid.uuid4(),
                status=UserStatus.SUSPENDED,
                change_reason="does not matter",
                actor_user_id=admin_id,
            )


# --- Status transitions never touch username/password/roles ---------------------------------
class TestStatusChangeIsIsolated:
    def test_status_change_does_not_alter_username_display_name_or_roles(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")
        role = service.create_role(name="Custom Role", description=None, actor_user_id=admin_id)
        service.assign_role_to_user(user_id=target_id, role_id=role.role_id, actor_user_id=admin_id)
        db_session.commit()

        service.set_user_status(
            target_id, status=UserStatus.SUSPENDED, change_reason="temp", actor_user_id=admin_id
        )
        db_session.commit()

        user = service.repo.get_user_by_id(target_id)
        assert user is not None
        assert user.username == "engineer1"
        assert user.display_name == "engineer1"
        roles = service.list_user_roles(target_id)
        assert len(roles) == 1
        assert roles[0].role.role_id == role.role_id

    def test_status_change_does_not_alter_password_hash(self, db_session: Session) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")
        credential_before = service.repo.get_credential(target_id)
        assert credential_before is not None
        hash_before = credential_before.password_hash

        service.set_user_status(
            target_id, status=UserStatus.SUSPENDED, change_reason="temp", actor_user_id=admin_id
        )
        service.set_user_status(
            target_id, status=UserStatus.ACTIVE, change_reason="back", actor_user_id=admin_id
        )
        db_session.commit()

        credential_after = service.repo.get_credential(target_id)
        assert credential_after is not None
        assert credential_after.password_hash == hash_before
        # ...and the original password still authenticates.
        authenticated = service.authenticate("engineer1", "correct-horse-battery")
        assert authenticated.user_id == target_id


# --- Audit row contents -----------------------------------------------------------------------
class TestAuditRowContents:
    def test_successful_transition_records_full_audit_entry(self, db_session: Session) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")

        service.set_user_status(
            target_id,
            status=UserStatus.SUSPENDED,
            change_reason="Extended leave of absence",
            actor_user_id=admin_id,
        )
        db_session.commit()

        rows = (
            db_session.query(IAMAuditLog)
            .filter_by(entity_type="User", entity_id=str(target_id), field_name="status")
            .all()
        )
        assert len(rows) == 1
        entry = rows[0]
        assert entry.old_value == "active"
        assert entry.new_value == "suspended"
        assert entry.change_reason == "Extended leave of absence"
        assert entry.changed_by_user_id == admin_id
        assert entry.changed_at is not None

    def test_rejected_last_administrator_operation_creates_no_audit_row(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)

        before = db_session.query(IAMAuditLog).filter_by(entity_type="User").count()

        with pytest.raises(LastActiveAdministratorError):
            service.set_user_status(
                admin_id,
                status=UserStatus.SUSPENDED,
                change_reason="attempt",
                actor_user_id=admin_id,
            )

        after = db_session.query(IAMAuditLog).filter_by(entity_type="User").count()
        assert after == before


# --- Login behaviour after lifecycle changes ---------------------------------------------------
class TestLoginBehaviourAfterLifecycleChanges:
    def test_suspended_user_cannot_authenticate(self, db_session: Session) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")
        service.set_user_status(
            target_id, status=UserStatus.SUSPENDED, change_reason="temp", actor_user_id=admin_id
        )
        db_session.commit()

        with pytest.raises(InactiveUserError):
            service.authenticate("engineer1", "correct-horse-battery")

    def test_deactivated_user_cannot_authenticate(self, db_session: Session) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")
        service.set_user_status(
            target_id,
            status=UserStatus.DEACTIVATED,
            change_reason="retired",
            actor_user_id=admin_id,
        )
        db_session.commit()

        with pytest.raises(InactiveUserError):
            service.authenticate("engineer1", "correct-horse-battery")

    def test_reactivated_user_can_authenticate_with_original_password(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")
        service.set_user_status(
            target_id, status=UserStatus.SUSPENDED, change_reason="temp", actor_user_id=admin_id
        )
        service.set_user_status(
            target_id, status=UserStatus.ACTIVE, change_reason="back", actor_user_id=admin_id
        )
        db_session.commit()

        authenticated = service.authenticate("engineer1", "correct-horse-battery")
        assert authenticated.user_id == target_id


# --- Last-active-Administrator safeguard --------------------------------------------------------
class TestLastActiveAdministratorSafeguard:
    def test_revoking_administrator_role_from_the_last_active_administrator_is_rejected(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        admin_role = service.repo.get_role_by_name("Administrator")
        assert admin_role is not None

        with pytest.raises(LastActiveAdministratorError):
            service.revoke_role_from_user(
                user_id=admin_id, role_id=admin_role.role_id, actor_user_id=admin_id
            )

    def test_suspending_the_last_active_administrator_is_rejected(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)

        with pytest.raises(LastActiveAdministratorError):
            service.set_user_status(
                admin_id,
                status=UserStatus.SUSPENDED,
                change_reason="attempt",
                actor_user_id=admin_id,
            )

    def test_deactivating_the_last_active_administrator_is_rejected(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)

        with pytest.raises(LastActiveAdministratorError):
            service.set_user_status(
                admin_id,
                status=UserStatus.DEACTIVATED,
                change_reason="attempt",
                actor_user_id=admin_id,
            )

    def test_revoking_administrator_role_allowed_with_a_second_active_administrator(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        _make_second_administrator(service, "second_admin")
        admin_role = service.repo.get_role_by_name("Administrator")
        assert admin_role is not None

        service.revoke_role_from_user(
            user_id=admin_id, role_id=admin_role.role_id, actor_user_id=admin_id
        )
        db_session.commit()

        assert service.repo.get_active_user_role(admin_id, admin_role.role_id) is None

    def test_suspending_allowed_with_a_second_active_administrator(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        _make_second_administrator(service, "second_admin")

        user = service.set_user_status(
            admin_id,
            status=UserStatus.SUSPENDED,
            change_reason="stepping down",
            actor_user_id=admin_id,
        )
        db_session.commit()

        assert user.status == UserStatus.SUSPENDED

    def test_deactivating_allowed_with_a_second_active_administrator(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        _make_second_administrator(service, "second_admin")

        user = service.set_user_status(
            admin_id,
            status=UserStatus.DEACTIVATED,
            change_reason="recovery account retired",
            actor_user_id=admin_id,
        )
        db_session.commit()

        assert user.status == UserStatus.DEACTIVATED

    def test_a_suspended_administrator_does_not_count_toward_the_safeguard(
        self, db_session: Session
    ) -> None:
        """B holds the Administrator role but is itself Suspended — B
        must not count as a live safety net for A."""
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        second_admin_id = _make_second_administrator(service, "second_admin")
        service.set_user_status(
            second_admin_id,
            status=UserStatus.SUSPENDED,
            change_reason="on leave",
            actor_user_id=admin_id,
        )
        db_session.commit()

        with pytest.raises(LastActiveAdministratorError):
            service.set_user_status(
                admin_id,
                status=UserStatus.DEACTIVATED,
                change_reason="attempt",
                actor_user_id=admin_id,
            )

    def test_a_non_administrator_role_holder_does_not_count_toward_the_safeguard(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        engineer_id = _create_plain_user(service, "engineer1")
        engineer_role = service.repo.get_role_by_name("Engineer")
        assert engineer_role is not None
        service.assign_role_to_user(
            user_id=engineer_id, role_id=engineer_role.role_id, actor_user_id=admin_id
        )
        db_session.commit()

        with pytest.raises(LastActiveAdministratorError):
            service.set_user_status(
                admin_id,
                status=UserStatus.DEACTIVATED,
                change_reason="attempt",
                actor_user_id=admin_id,
            )

    def test_a_revoked_administrator_grant_does_not_count_toward_the_safeguard(
        self, db_session: Session
    ) -> None:
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        second_admin_id = _make_second_administrator(service, "second_admin")
        admin_role = service.repo.get_role_by_name("Administrator")
        assert admin_role is not None
        service.revoke_role_from_user(
            user_id=second_admin_id, role_id=admin_role.role_id, actor_user_id=admin_id
        )
        db_session.commit()

        with pytest.raises(LastActiveAdministratorError):
            service.set_user_status(
                admin_id,
                status=UserStatus.DEACTIVATED,
                change_reason="attempt",
                actor_user_id=admin_id,
            )

    def test_the_safeguard_never_blocks_a_non_administrator_status_change(
        self, db_session: Session
    ) -> None:
        """Suspending/deactivating an ordinary user is never blocked by
        this invariant, regardless of how many administrators exist."""
        service = IAMService(db_session)
        admin_id = _bootstrap_administrator(db_session)
        target_id = _create_plain_user(service, "engineer1")

        user = service.set_user_status(
            target_id,
            status=UserStatus.DEACTIVATED,
            change_reason="ordinary departure",
            actor_user_id=admin_id,
        )
        db_session.commit()

        assert user.status == UserStatus.DEACTIVATED
