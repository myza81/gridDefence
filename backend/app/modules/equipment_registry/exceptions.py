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
    "InvalidTransformerInitialStatusError",
    "SameSwitchyardTerminalsError",
    "InvalidTransformerVoltageOrderError",
    "TransformerYardSubstationMismatchError",
    "DuplicateTransformerError",
    "SwitchyardEnteredInErrorError",
    "SwitchyardHasActiveReferencesError",
    "InsufficientActiveTerminalsForActivationError",
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


# --- Transformer Registry (Phase 3.5) ------------------------------------------------


class InvalidTransformerInitialStatusError(ValidationAppError):
    def __init__(self, status_code: str) -> None:
        super().__init__(
            f"A transformer cannot be created with initial operational status '{status_code}' — "
            "new transformers must start as Planned or Active."
        )


class SameSwitchyardTerminalsError(ValidationAppError):
    def __init__(self, switchyard_label: str) -> None:
        super().__init__(
            f"A transformer's HV and LV terminals cannot both connect to the same switchyard "
            f"('{switchyard_label}') — a transformer must step between two different voltage "
            "levels."
        )


class InvalidTransformerVoltageOrderError(ValidationAppError):
    def __init__(self, hv_label: str, lv_label: str) -> None:
        super().__init__(
            f"The HV side ('{hv_label}') must be a strictly higher voltage level than the LV "
            f"side ('{lv_label}') — got the same level, or the order reversed."
        )


class TransformerYardSubstationMismatchError(ValidationAppError):
    """UAT correction: a transformer is substation-owned equipment — its HV
    and LV switchyards must both belong to the substation it is being
    created at. The Malaysian transmission/distribution domain does not
    model a transformer as spanning two different substations."""

    def __init__(
        self,
        side: str,
        yard_label: str,
        yard_substation_mnemonic: str,
        selected_substation_mnemonic: str,
    ) -> None:
        super().__init__(
            f"The {side} switchyard ('{yard_label}') belongs to substation "
            f"'{yard_substation_mnemonic}', not the selected substation "
            f"'{selected_substation_mnemonic}' — a transformer's HV and LV switchyards must both "
            "belong to the substation it is installed at; transformers are not modeled as "
            "spanning substations."
        )


class DuplicateTransformerError(ValidationAppError):
    """UAT correction #2: uniqueness is scoped to `(substation_id,
    hv_switchyard_id, lv_switchyard_id, transformer_number)`, not
    `(substation_id, transformer_number)` alone — a transformer number is
    reused legitimately across different transformation pairs at the same
    substation (e.g. a "1" on the 275/132kV pair and a separate "1" on the
    132/33kV pair)."""

    def __init__(self, transformer_number: str, substation_mnemonic: str) -> None:
        # Human-readable substation mnemonic, not a raw id — same lesson as
        # DuplicateVoltageYardError (Phase 3 UAT).
        super().__init__(
            f"A transformer numbered '{transformer_number}' already exists for this HV/LV "
            f"switchyard pair at substation '{substation_mnemonic}' — transformer numbers are "
            "scoped to a specific voltage-transformation pair, not the whole substation (the same "
            "number may be reused across a different HV/LV pair at the same substation, e.g. a "
            "'1' at the 275/132kV pair and a separate '1' at the 132/33kV pair)."
        )


# --- Deletion/correction policy (Phase 3 follow-up) ----------------------------------


class SwitchyardEnteredInErrorError(ValidationAppError):
    """A new circuit/transformer terminal may never be created against a
    switchyard that has already been corrected as a mistake — the
    forward-looking half of policy point 8 (future references must not
    point at entered-in-error records) that is actually enforceable today,
    since Switchyard is the one entity with real downstream consumers in
    this phase."""

    def __init__(self, voltage_yard_label: str) -> None:
        super().__init__(
            f"Switchyard '{voltage_yard_label}' has been marked Entered in Error and cannot be "
            "used for a new terminal — select a different switchyard, or correct the switchyard's "
            "status first if this was itself a mistake."
        )


class SwitchyardHasActiveReferencesError(ValidationAppError):
    """A switchyard cannot be corrected as Entered in Error while it is
    still genuinely in use — existing references must be protected
    (deletion/correction policy point 5). "Active" here means a
    CircuitTerminal/TransformerTerminal that is not itself already
    entered-in-error, on a parent Circuit/Transformer that is not itself
    already entered-in-error."""

    def __init__(self, voltage_yard_label: str, circuit_count: int, transformer_count: int) -> None:
        parts = []
        if circuit_count:
            parts.append(f"{circuit_count} active circuit terminal(s)")
        if transformer_count:
            parts.append(f"{transformer_count} active transformer terminal(s)")
        referenced_by = " and ".join(parts)
        super().__init__(
            f"Switchyard '{voltage_yard_label}' cannot be marked Entered in Error while it is "
            f"still referenced by {referenced_by} — correct or retire those references first."
        )


class InsufficientActiveTerminalsForActivationError(ValidationAppError):
    """A circuit may be temporarily incomplete while its terminals are
    being corrected (marking a terminal Entered in Error is never blocked
    on its own), but it may not transition into Active with fewer than two
    active terminals — the same two-terminal completeness rule
    (equipment-registry-module.md §9 rule 5) enforced at the activation
    boundary rather than at correction time."""

    def __init__(self, active_terminal_count: int) -> None:
        super().__init__(
            f"Circuit cannot be set to Active with fewer than two active terminals — currently "
            f"{active_terminal_count}. Correct or add terminals until at least two are active "
            "before activating this circuit (equipment-registry-module.md §9 rule 5)."
        )
