"""IAM-specific business errors (CLAUDE.md A9 — structured, not ad hoc)."""

from __future__ import annotations

from app.shared.exceptions import AppError, NotFoundError, ValidationAppError

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationAppError",
    "DuplicateUsernameError",
    "DuplicateRoleNameError",
    "DuplicatePermissionError",
    "DuplicateExternalIdentityError",
    "RoleRetiredError",
    "InvalidCredentialsError",
    "InactiveUserError",
    "InvalidUserStatusTransitionError",
    "UserStatusUnchangedError",
    "StatusChangeReasonRequiredError",
    "LastActiveAdministratorError",
]


class DuplicateUsernameError(ValidationAppError):
    def __init__(self, username: str) -> None:
        super().__init__(f"Username '{username}' is already in use.")


class DuplicateRoleNameError(ValidationAppError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Role name '{name}' is already in use.")


class DuplicatePermissionError(ValidationAppError):
    def __init__(self, permission_id: str) -> None:
        super().__init__(f"Permission '{permission_id}' is already registered.")


class DuplicateExternalIdentityError(ValidationAppError):
    def __init__(self, external_principal_id: str, provider: str) -> None:
        super().__init__(
            f"External identity '{external_principal_id}' for provider '{provider}' "
            "is already linked to another user."
        )


class RoleRetiredError(ValidationAppError):
    def __init__(self, role_name: str) -> None:
        super().__init__(f"Role '{role_name}' is retired and cannot be newly assigned.")


class InvalidCredentialsError(ValidationAppError):
    def __init__(self) -> None:
        super().__init__("Invalid username or password.")


class InactiveUserError(ValidationAppError):
    def __init__(self) -> None:
        super().__init__("This user account is not active.")


class InvalidUserStatusTransitionError(ValidationAppError):
    """iam-module.md §8's `Active ⇄ Suspended`, `Active/Suspended →
    Deactivated` lifecycle is a closed allow-list — mirrors Substation
    Registry's own `InvalidStatusTransitionError` precedent exactly."""

    def __init__(self, from_status: str, to_status: str) -> None:
        super().__init__(
            f"User status cannot transition from '{from_status}' to '{to_status}' — "
            "this is not a defined transition (iam-module.md §8)."
        )


class UserStatusUnchangedError(ValidationAppError):
    """A status change to the user's own current status is rejected, not
    silently accepted as a no-op — unlike Substation Registry's own
    `change_status` precedent, which tolerates this. IAM Completion
    Sprint's own explicit requirement: "reject no-op transitions.\""""

    def __init__(self, status: str) -> None:
        super().__init__(f"User is already '{status}' — no status change to apply.")


class StatusChangeReasonRequiredError(ValidationAppError):
    def __init__(self) -> None:
        super().__init__("A non-empty reason is required for a user status change.")


class LastActiveAdministratorError(ValidationAppError):
    """The last-active-Administrator invariant (IAM Completion Sprint) —
    an "active Administrator" is a User with `status = ACTIVE` holding a
    currently-active (non-revoked) grant of the `Administrator` system
    role. This must never reach zero."""

    def __init__(self) -> None:
        super().__init__(
            "At least one active Administrator must remain — this action would leave "
            "the system with no active Administrator."
        )
