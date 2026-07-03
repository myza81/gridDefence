"""Substation Registry business errors (CLAUDE.md A9 — structured, not ad hoc)."""

from __future__ import annotations

from app.shared.exceptions import AppError, NotFoundError, ValidationAppError

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationAppError",
    "DuplicateMnemonicError",
    "DuplicateNameError",
    "DuplicatePsseBusNumberError",
    "InvalidGeolocationPairError",
    "InvalidStatusTransitionError",
    "ReferenceDataNotFoundError",
]


class DuplicateMnemonicError(ValidationAppError):
    def __init__(self, mnemonic: str) -> None:
        super().__init__(
            f"Mnemonic '{mnemonic}' is already in use by a current or historical substation "
            "and cannot be reassigned (substation-registry.md §8 rule 1)."
        )


class DuplicateNameError(ValidationAppError):
    def __init__(self, official_name: str) -> None:
        super().__init__(f"Official name '{official_name}' is already in use.")


class DuplicatePsseBusNumberError(ValidationAppError):
    def __init__(self, psse_bus_number: int) -> None:
        super().__init__(f"PSS/E bus number {psse_bus_number} is already in use.")


class InvalidGeolocationPairError(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "Latitude and longitude must both be present or both be null "
            "(substation-registry.md §8 rule 4)."
        )


class InvalidStatusTransitionError(ValidationAppError):
    def __init__(self, from_code: str, to_code: str) -> None:
        super().__init__(
            f"Operational status cannot transition from '{from_code}' to '{to_code}' — "
            "this is not a defined transition (substation-registry.md §10)."
        )


class ReferenceDataNotFoundError(ValidationAppError):
    def __init__(self, kind: str, value: object) -> None:
        super().__init__(f"{kind} '{value}' is not a recognized reference data value.")
