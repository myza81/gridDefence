"""Automatic Load Shedding Functionality Registry business errors
(CLAUDE.md A9 — structured, not ad hoc)."""

from __future__ import annotations

from app.shared.exceptions import AppError, NotFoundError, ValidationAppError

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationAppError",
    "FunctionalityNotFoundError",
    "CircuitTerminalNotFoundError",
    "TransformerTerminalNotFoundError",
    "TerminalAlreadyHasFunctionalityError",
    "NoFunctionAssignedError",
    "DecommissionReasonRequiredError",
    "FunctionalityDecommissionedImmutableError",
]


class FunctionalityNotFoundError(NotFoundError):
    def __init__(self, functionality_id: object) -> None:
        super().__init__(
            f"Automatic load shedding functionality record '{functionality_id}' not found."
        )


class CircuitTerminalNotFoundError(ValidationAppError):
    def __init__(self, circuit_terminal_id: object) -> None:
        super().__init__(
            f"Circuit terminal '{circuit_terminal_id}' does not exist in the Equipment Registry."
        )


class TransformerTerminalNotFoundError(ValidationAppError):
    def __init__(self, transformer_terminal_id: object) -> None:
        super().__init__(
            f"Transformer terminal '{transformer_terminal_id}' does not exist in the "
            "Equipment Registry."
        )


class TerminalAlreadyHasFunctionalityError(ValidationAppError):
    """Module document §9 rule 2 / §11: at most one non-decommissioned
    record per Bay Terminal."""

    def __init__(self, target_type: str, terminal_id: object) -> None:
        super().__init__(
            f"This {target_type.replace('_', ' ').lower()} already has an active automatic load "
            f"shedding functionality record ('{terminal_id}') — decommission the existing record "
            "before creating a new one, or edit it directly."
        )


class NoFunctionAssignedError(ValidationAppError):
    """Module document §9 rule 3 / §10: a record with both flags false
    represents no functionality at all."""

    def __init__(self) -> None:
        super().__init__(
            "At least one of ufls_function/uvls_function must be true — a record with neither "
            "represents no automatic shedding functionality at all "
            "(automatic-load-shedding-functionality-registry-module.md §9 rule 3)."
        )


class DecommissionReasonRequiredError(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "A change_reason is required when decommissioning an automatic load shedding "
            "functionality record (automatic-load-shedding-functionality-registry-module.md §10)."
        )


class FunctionalityDecommissionedImmutableError(ValidationAppError):
    """A decommissioned record is fully immutable — no field, including
    remarks, may be edited afterward, and it can never be decommissioned a
    second time (decommissioning is a one-way, terminal transition; a bay
    whose functionality is later reinstalled receives a **new** record,
    never a reactivated one). The approved module document does not carve
    out any post-decommission exception; create a new record for the
    terminal instead."""

    def __init__(self, functionality_id: object) -> None:
        super().__init__(
            f"Automatic load shedding functionality record '{functionality_id}' is decommissioned "
            "and cannot be edited — decommissioned records are immutable. Create a new record for "
            "this terminal instead."
        )
