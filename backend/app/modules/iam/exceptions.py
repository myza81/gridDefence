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
