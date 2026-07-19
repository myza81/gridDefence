"""Engineering Parameter Configuration business errors (CLAUDE.md A9 —
structured, not ad hoc)."""

from __future__ import annotations

from app.shared.exceptions import AppError, NotFoundError, ValidationAppError

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationAppError",
    "ParameterNotFoundError",
    "ChangeReasonRequiredError",
    "InvalidParameterValueError",
]


class ParameterNotFoundError(NotFoundError):
    def __init__(self, parameter_key: object) -> None:
        super().__init__(f"Engineering parameter '{parameter_key}' not found.")


class ChangeReasonRequiredError(ValidationAppError):
    """Module document §9 rule 1: every value change must carry a
    non-empty reason, no exception for the first-ever value either."""

    def __init__(self) -> None:
        super().__init__(
            "A change_reason is required when setting an engineering parameter's value "
            "(engineering-parameter-configuration-architecture.md §9)."
        )


class InvalidParameterValueError(ValidationAppError):
    """Module document §10: per-`parameter_key` type/range validation."""

    def __init__(self, parameter_key: str, reason: str) -> None:
        super().__init__(f"Invalid value for engineering parameter '{parameter_key}': {reason}")
