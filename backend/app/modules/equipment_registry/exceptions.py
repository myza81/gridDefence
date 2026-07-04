"""Equipment Registry business errors (CLAUDE.md A9 — structured, not ad hoc)."""

from __future__ import annotations

from app.shared.exceptions import AppError, NotFoundError, ValidationAppError

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationAppError",
    "ReferenceDataNotFoundError",
    "SubstationNotFoundError",
    "VoltageYardNotFoundError",
    "DuplicateVoltageYardError",
    "InsufficientTerminalsError",
    "DuplicateTerminalVoltageYardError",
    "InvalidInitialStatusError",
    "TerminalVoltageLevelMismatchError",
    "InvalidGeolocationPairError",
]


class ReferenceDataNotFoundError(ValidationAppError):
    def __init__(self, kind: str, value: object) -> None:
        super().__init__(f"{kind} '{value}' is not a recognized reference data value.")


class SubstationNotFoundError(ValidationAppError):
    def __init__(self, substation_id: object) -> None:
        super().__init__(f"Substation '{substation_id}' does not exist in the Substation Registry.")


class VoltageYardNotFoundError(ValidationAppError):
    # Message says "switchyard" — the user-facing term (Phase 3 close-out;
    # ADR-008 addendum) — while the class/module/table/API all keep their
    # internal "voltage yard" names unchanged (deliberately not renamed;
    # see the ADR-008 addendum for the full reasoning).
    def __init__(self, voltage_yard_id: object) -> None:
        super().__init__(f"Switchyard '{voltage_yard_id}' does not exist.")


class DuplicateVoltageYardError(ValidationAppError):
    def __init__(self, substation_mnemonic: str, voltage_level_label: str) -> None:
        # Human-readable substation mnemonic + voltage level label, not raw
        # UUIDs/internal ids — found during Phase 3 UAT: a message reading
        # "voltage level '4'" gives an engineer no way to know that means
        # 132kV, making a correctly-rejected duplicate look like an
        # unexplained, generic failure.
        super().__init__(
            f"Substation '{substation_mnemonic}' already has a switchyard at "
            f"'{voltage_level_label}' — at most one switchyard per substation per voltage level "
            "(equipment-registry-module.md §7.5a)."
        )


class InsufficientTerminalsError(ValidationAppError):
    def __init__(self, terminal_count: int) -> None:
        super().__init__(
            f"A circuit must have at least two terminals to be created; {terminal_count} "
            "supplied (equipment-registry-module.md §9 rule 5)."
        )


class DuplicateTerminalVoltageYardError(ValidationAppError):
    def __init__(self, voltage_yard_id: object) -> None:
        super().__init__(
            f"Switchyard '{voltage_yard_id}' already has a terminal on this circuit — no "
            "switchyard may hold more than one terminal of the same circuit "
            "(equipment-registry-module.md §9 rule 6; ADR-008)."
        )


class InvalidInitialStatusError(ValidationAppError):
    def __init__(self, status_code: str) -> None:
        super().__init__(
            f"A circuit cannot be created with initial operational status '{status_code}' — "
            "new circuits must start as Planned or Active."
        )


class TerminalVoltageLevelMismatchError(ValidationAppError):
    def __init__(self, voltage_yard_label: str, circuit_voltage_level_label: str) -> None:
        # Human-readable voltage yard label + circuit's own voltage level
        # label, not raw ids — mirrors DuplicateVoltageYardError's lesson
        # from Phase 3 UAT: a message with bare ids gives no way to see
        # *why* the mismatch happened.
        super().__init__(
            f"Switchyard '{voltage_yard_label}' does not match this circuit's voltage level "
            f"'{circuit_voltage_level_label}' — every terminal of a circuit must connect at the "
            "circuit's own voltage level."
        )


class InvalidGeolocationPairError(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "Latitude and longitude must both be present or both be null "
            "(equipment-registry-module.md §7.5a)."
        )
