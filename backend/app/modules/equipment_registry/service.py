"""Equipment Registry service layer (CLAUDE.md §14) — business rules,
transactions, orchestration, and audit writing live here, and only here
(CLAUDE.md A1: this module's own tables are written to exclusively by this
layer).

Scope and open questions carried forward from
docs/architecture/equipment-registry-module.md, left deliberately
unresolved here (DEVELOPMENT.md §9 — a narrow, low-stakes implementation
detail the architecture document leaves open is implemented reasonably and
documented, not silently over-specified):

- `Circuit.bay_number` uniqueness scope is explicitly left open by
  equipment-registry-module.md §10 ("not resolved by this document") — no
  uniqueness constraint is enforced here.
- `CircuitTerminal.breaker_number` "has no cross-substation uniqueness
  requirement" per §10 — no constraint is enforced here, including within
  the same substation (the spec does not state a same-substation rule
  either).
- Operational status *transition legality* (an ADR-005-style closed
  allow-list graph) is not asserted by equipment-registry-module.md to
  apply to `Circuit` — only that it "follows the same lifecycle *values*"
  as Substation Registry. This service therefore validates that a target
  status is a real reference-data row, and that the *initial* status on
  creation is Planned or Active (mirroring Substation Registry's own
  creation-time rule), but does not enforce a specific transition graph.
  If Circuit should follow ADR-005's exact 7-edge graph, that can be added
  identically to `SubstationService._STATUS_TRANSITIONS`.

Phase 3 UAT fix package (ADR-008): `CircuitTerminal` now connects to a
`SubstationVoltageYard`, not a `Substation` directly — see
`_require_voltage_yard`, `create_voltage_yard`, and the terminal-summary
resolution helpers below. A terminal's own `breaker_number`,
`commissioning_date`, and `remarks` are now editable after creation via
`update_terminal` (task must-fix items 1–2); the voltage yard a terminal
connects to is not editable after creation (out of this fix package's
scope — re-pointing a terminal to a different yard is a materially
different operation from correcting its breaker number or commissioning
date, and was not requested).
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.modules.equipment_registry.exceptions import (
    DuplicateTerminalVoltageYardError,
    DuplicateTransformerError,
    DuplicateVoltageYardError,
    InsufficientActiveTerminalsForActivationError,
    InsufficientTerminalsError,
    InvalidGeolocationPairError,
    InvalidInitialStatusError,
    InvalidTransformerInitialStatusError,
    InvalidTransformerVoltageOrderError,
    NotFoundError,
    ReferenceDataNotFoundError,
    SameSwitchyardTerminalsError,
    SubstationNotFoundError,
    SwitchyardEnteredInErrorError,
    SwitchyardHasActiveReferencesError,
    TerminalVoltageLevelMismatchError,
    TransformerYardSubstationMismatchError,
    VoltageYardNotFoundError,
)
from app.modules.equipment_registry.models import (
    Circuit,
    CircuitTerminal,
    EquipmentRegistryAuditLog,
    SubstationVoltageYard,
    SubstationVoltageYardAuditLog,
    Transformer,
    TransformerAuditLog,
    TransformerTerminal,
)
from app.modules.equipment_registry.repository import (
    EquipmentRegistryRepository,
    VoltageYardDisplayData,
)
from app.modules.equipment_registry.schemas import (
    CircuitAuditLogEntry,
    CircuitDetail,
    CircuitSummary,
    CircuitTerminalSummary,
    TransformerAuditLogEntry,
    TransformerDetail,
    TransformerSummary,
    TransformerTerminalSummary,
    VoltageYardAuditLogEntry,
    VoltageYardSummary,
)
from app.modules.iam.schemas import UserSummary
from app.modules.iam.service import IAMService
from app.reference_data.repository import ReferenceDataRepository

# "Create: always starts as Planned or Active" — mirrors the same
# creation-time exception already established for Substation Registry
# (substation_registry/service.py), since equipment-registry-module.md §8
# reuses the same operational_status *values*. Reused for Transformer too
# (Phase 3.5), for the same consistency reason, even though it was not
# explicitly requested in that phase's spec.
_ALLOWED_INITIAL_STATUS_CODES = {"PLANNED", "ACTIVE"}
_MINIMUM_TERMINALS = 2

# Equipment Registry deletion/correction policy (Phase 3 follow-up):
# ENTERED_IN_ERROR corrects a mistakenly-created switchyard, circuit
# terminal, circuit, or transformer without a hard delete (CLAUDE.md
# §11.6). ACTIVE is the status every newly-created switchyard/terminal
# starts in. Both are looked up by code, never a hardcoded numeric id,
# since seed insertion order is not part of this module's contract.
_ENTERED_IN_ERROR_STATUS_CODE = "ENTERED_IN_ERROR"
_ACTIVE_STATUS_CODE = "ACTIVE"

# TNB engineering short-name prefix convention, keyed by the HV terminal's
# nominal voltage (Transformer Registry spec, Phase 3.5). Deliberately does
# not distinguish auto-transformers (typically SGT/XGT in real TNB usage)
# from two-winding transformers (typically T) — this phase's `Transformer`
# entity does not model that distinction (see models.py's Transformer
# docstring).
_TRANSFORMER_SHORT_NAME_PREFIX_BY_NOMINAL_KV: dict[int, str] = {
    500: "XGT",
    275: "SGT",
    230: "SGT",
    132: "T",
    33: "T",
    22: "T",
    11: "T",
}


class TerminalInput:
    """Plain data carrier for one terminal supplied at circuit-creation
    time — avoids importing the Pydantic schema into the service layer
    (CLAUDE.md A6 — service layer works with domain concepts, not API DTOs).
    """

    def __init__(
        self,
        *,
        voltage_yard_id: uuid.UUID,
        breaker_number: str,
        commissioning_date: date | None = None,
        remarks: str | None = None,
    ) -> None:
        self.voltage_yard_id = voltage_yard_id
        self.breaker_number = breaker_number
        self.commissioning_date = commissioning_date
        self.remarks = remarks


class EquipmentRegistryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = EquipmentRegistryRepository(db)
        self.reference_data = ReferenceDataRepository(db)
        self.iam = IAMService(db)

    # --- internal helpers -----------------------------------------------------
    def _audit_field_change(
        self,
        *,
        circuit_id: uuid.UUID,
        field_name: str,
        old_value: object,
        new_value: object,
        actor_user_id: uuid.UUID,
        change_reason: str | None = None,
    ) -> None:
        self.repo.add_audit_log(
            EquipmentRegistryAuditLog(
                circuit_id=circuit_id,
                field_name=field_name,
                old_value=None if old_value is None else str(old_value),
                new_value=None if new_value is None else str(new_value),
                changed_by_user_id=actor_user_id,
                change_reason=change_reason,
            )
        )

    def _resolve_user(self, user_id: uuid.UUID | None) -> UserSummary | None:
        if user_id is None:
            return None
        return self.iam.get_user(user_id)

    def _require_voltage_level_and_line_type(
        self, *, voltage_level_id: int, line_type_id: int
    ) -> None:
        if self.reference_data.get_voltage_level(voltage_level_id) is None:
            raise ReferenceDataNotFoundError("voltage_level_id", voltage_level_id)
        if self.reference_data.get_line_type(line_type_id) is None:
            raise ReferenceDataNotFoundError("line_type_id", line_type_id)

    def _require_operational_status(self, operational_status_id: int) -> str:
        """Returns the status's stable `code`."""
        status = self.reference_data.get_operational_status(operational_status_id)
        if status is None:
            raise ReferenceDataNotFoundError("operational_status_id", operational_status_id)
        return status.code

    def _require_substation(self, substation_id: uuid.UUID) -> None:
        if not self.repo.substation_exists(substation_id):
            raise SubstationNotFoundError(substation_id)

    def _require_active_operational_status_id(self) -> int:
        """Resolves ACTIVE's id — the status every newly-created switchyard
        or circuit terminal starts in (deletion/correction policy, Phase 3
        follow-up). ACTIVE is core reference data seeded since Phase 1."""
        status = self.reference_data.get_operational_status_by_code(_ACTIVE_STATUS_CODE)
        assert status is not None, "ACTIVE operational status is missing from reference data"
        return status.operational_status_id

    def _entered_in_error_status_id(self) -> int | None:
        status = self.reference_data.get_operational_status_by_code(_ENTERED_IN_ERROR_STATUS_CODE)
        return status.operational_status_id if status is not None else None

    def _require_voltage_yard(self, voltage_yard_id: uuid.UUID) -> SubstationVoltageYard:
        voltage_yard = self.repo.get_voltage_yard_by_id(voltage_yard_id)
        if voltage_yard is None:
            raise VoltageYardNotFoundError(voltage_yard_id)
        status = self.reference_data.get_operational_status(voltage_yard.operational_status_id)
        if status is not None and status.code == _ENTERED_IN_ERROR_STATUS_CODE:
            # Deletion/correction policy (Phase 3 follow-up), forward-looking
            # half of point 8: a new terminal must never be created against
            # a switchyard that has already been corrected as a mistake.
            display = self.repo.get_voltage_yard_display_data({voltage_yard.voltage_yard_id})
            raise SwitchyardEnteredInErrorError(
                self._switchyard_label(voltage_yard.voltage_yard_id, display)
            )
        return voltage_yard

    def _require_voltage_yard_matches_circuit_level(
        self, voltage_yard: SubstationVoltageYard, circuit_voltage_level_id: int
    ) -> None:
        """A circuit has exactly one `voltage_level_id`; every terminal's
        voltage yard must match it — a circuit cannot legitimately connect a
        132kV yard on one end and a 275kV yard on the other. Enforced here
        (not only in the frontend dropdown) so a mismatched voltage yard
        submitted directly to the API is rejected with a clear error, not
        silently accepted."""
        if voltage_yard.voltage_level_id == circuit_voltage_level_id:
            return
        display = self.repo.get_voltage_yard_display_data({voltage_yard.voltage_yard_id})
        info = display.get(voltage_yard.voltage_yard_id)
        yard_label = (
            self._compute_voltage_yard_label(info.substation_mnemonic, info.voltage_level_label)
            if info is not None
            else str(voltage_yard.voltage_yard_id)
        )
        circuit_level = self.reference_data.get_voltage_level(circuit_voltage_level_id)
        circuit_level_label = (
            circuit_level.label if circuit_level is not None else str(circuit_voltage_level_id)
        )
        raise TerminalVoltageLevelMismatchError(yard_label, circuit_level_label)

    def _validate_terminal_inputs(
        self, terminals: list[TerminalInput], *, circuit_voltage_level_id: int
    ) -> None:
        if len(terminals) < _MINIMUM_TERMINALS:
            raise InsufficientTerminalsError(len(terminals))

        seen_voltage_yard_ids: set[uuid.UUID] = set()
        for terminal in terminals:
            if terminal.voltage_yard_id in seen_voltage_yard_ids:
                raise DuplicateTerminalVoltageYardError(terminal.voltage_yard_id)
            seen_voltage_yard_ids.add(terminal.voltage_yard_id)
            voltage_yard = self._require_voltage_yard(terminal.voltage_yard_id)
            self._require_voltage_yard_matches_circuit_level(voltage_yard, circuit_voltage_level_id)

    @staticmethod
    def _check_geolocation_pair(latitude: float | None, longitude: float | None) -> None:
        if (latitude is None) != (longitude is None):
            raise InvalidGeolocationPairError()

    @staticmethod
    def _compute_circuit_name(mnemonics: list[str]) -> str:
        """Canonical, deterministic route name — sorted terminal mnemonics
        only, never `bay_number` (Phase 3 close-out). Two defects this
        fixes: (1) embedding `bay_number` here duplicated it when the UI
        also displayed `bay_number` separately, e.g. "PKLG–IGBK 1" next to
        a "Bay / Circuit No.: 1" field looked like "...1 1"; (2) mnemonics
        were previously joined in terminal-insertion order, so the same
        physical circuit could display as "PKLG–IGBK" or "IGBK–PKLG"
        depending on which terminal happened to be entered first. No
        documented PSS/E or other engineering naming convention exists yet
        for terminal ordering (equipment-registry-module.md §7.4), so a
        stable, case-insensitive alphabetical-by-mnemonic rule is used as
        the default — deterministic regardless of entry order, and applies
        uniformly to two-terminal circuits and tee-offs alike."""
        return "–".join(sorted(mnemonics, key=str.casefold))

    @staticmethod
    def _compute_voltage_yard_label(mnemonic: str, voltage_level_label: str) -> str:
        return f"{mnemonic} — {voltage_level_label}"

    # --- Create -----------------------------------------------------------------
    def create_circuit(
        self,
        *,
        bay_number: str,
        voltage_level_id: int,
        line_type_id: int,
        operational_status_id: int,
        is_interconnector: bool,
        remarks: str | None,
        terminals: list[TerminalInput],
        actor_user_id: uuid.UUID,
    ) -> Circuit:
        # Voltage level/line type must be validated as real reference data
        # *before* terminal validation, since the terminal-voltage-level-
        # match check below needs a real voltage_level_id to compare
        # against and resolve a human-readable label from.
        self._require_voltage_level_and_line_type(
            voltage_level_id=voltage_level_id, line_type_id=line_type_id
        )
        self._validate_terminal_inputs(terminals, circuit_voltage_level_id=voltage_level_id)
        status_code = self._require_operational_status(operational_status_id)
        if status_code not in _ALLOWED_INITIAL_STATUS_CODES:
            raise InvalidInitialStatusError(status_code)

        circuit = self.repo.add_circuit(
            Circuit(
                circuit_id=uuid.uuid4(),
                bay_number=bay_number,
                voltage_level_id=voltage_level_id,
                line_type_id=line_type_id,
                operational_status_id=operational_status_id,
                is_interconnector=is_interconnector,
                remarks=remarks,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )
        # No audit row for creation itself — accountability is already
        # captured by created_by_user_id/created_at directly on the row
        # (CLAUDE.md §5.4), matching Substation Registry's own precedent.
        active_status_id = self._require_active_operational_status_id()
        for terminal in terminals:
            self.repo.add_terminal(
                CircuitTerminal(
                    circuit_terminal_id=uuid.uuid4(),
                    circuit_id=circuit.circuit_id,
                    voltage_yard_id=terminal.voltage_yard_id,
                    breaker_number=terminal.breaker_number,
                    commissioning_date=terminal.commissioning_date,
                    remarks=terminal.remarks,
                    operational_status_id=active_status_id,
                    created_by_user_id=actor_user_id,
                    updated_by_user_id=actor_user_id,
                )
            )
        return circuit

    # --- Add terminal (extend an existing circuit, e.g. into a tee-off) ---------------
    def add_terminal(
        self,
        circuit_id: uuid.UUID,
        *,
        voltage_yard_id: uuid.UUID,
        breaker_number: str,
        commissioning_date: date | None,
        remarks: str | None,
        actor_user_id: uuid.UUID,
    ) -> CircuitTerminal:
        circuit = self.repo.get_circuit_by_id(circuit_id)
        if circuit is None:
            raise NotFoundError(f"Circuit {circuit_id} not found")

        voltage_yard = self._require_voltage_yard(voltage_yard_id)
        self._require_voltage_yard_matches_circuit_level(voltage_yard, circuit.voltage_level_id)
        if self.repo.terminal_exists_for_voltage_yard(circuit_id, voltage_yard_id):
            raise DuplicateTerminalVoltageYardError(voltage_yard_id)

        terminal = self.repo.add_terminal(
            CircuitTerminal(
                circuit_terminal_id=uuid.uuid4(),
                circuit_id=circuit_id,
                voltage_yard_id=voltage_yard_id,
                breaker_number=breaker_number,
                commissioning_date=commissioning_date,
                remarks=remarks,
                operational_status_id=self._require_active_operational_status_id(),
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )

        display = self.repo.get_voltage_yard_display_data({voltage_yard_id}).get(voltage_yard_id)
        yard_label = (
            self._compute_voltage_yard_label(
                display.substation_mnemonic, display.voltage_level_label
            )
            if display is not None
            else str(voltage_yard_id)
        )
        self._audit_field_change(
            circuit_id=circuit_id,
            field_name="terminal_added",
            old_value=None,
            new_value=f"voltage_yard={yard_label}; breaker_number={breaker_number}",
            actor_user_id=actor_user_id,
        )
        circuit.updated_by_user_id = actor_user_id
        self.db.flush()
        return terminal

    # --- Update terminal (breaker_number / commissioning_date / remarks / status) ----
    def update_terminal(
        self,
        circuit_id: uuid.UUID,
        circuit_terminal_id: uuid.UUID,
        *,
        breaker_number: str | None = None,
        commissioning_date: date | None = ...,
        remarks: str | None = ...,
        operational_status_id: int | None = None,
        actor_user_id: uuid.UUID,
    ) -> CircuitTerminal:
        """`operational_status_id` corrects a mistakenly-added terminal
        (deletion/correction policy, Phase 3 follow-up) — always allowed,
        never blocked here even if it would leave the parent circuit with
        fewer than two active terminals. `CircuitTerminal` is a first-class
        connectivity object that may legitimately require individual
        correction; the two-active-terminal completeness rule is enforced
        instead at the point the circuit tries to (re)enter Active
        (`change_status`), not at correction time — a circuit may be
        temporarily incomplete while being corrected."""
        terminal = self.repo.get_terminal_by_id(circuit_terminal_id)
        if terminal is None or terminal.circuit_id != circuit_id:
            raise NotFoundError(f"Terminal {circuit_terminal_id} not found on circuit {circuit_id}")

        changed = False

        if breaker_number is not None and breaker_number != terminal.breaker_number:
            self._audit_field_change(
                circuit_id=circuit_id,
                field_name="terminal_breaker_number",
                old_value=terminal.breaker_number,
                new_value=breaker_number,
                actor_user_id=actor_user_id,
            )
            terminal.breaker_number = breaker_number
            changed = True

        if commissioning_date is not ... and commissioning_date != terminal.commissioning_date:
            self._audit_field_change(
                circuit_id=circuit_id,
                field_name="terminal_commissioning_date",
                old_value=terminal.commissioning_date,
                new_value=commissioning_date,
                actor_user_id=actor_user_id,
            )
            terminal.commissioning_date = commissioning_date
            changed = True

        if remarks is not ... and remarks != terminal.remarks:
            self._audit_field_change(
                circuit_id=circuit_id,
                field_name="terminal_remarks",
                old_value=terminal.remarks,
                new_value=remarks,
                actor_user_id=actor_user_id,
            )
            terminal.remarks = remarks
            changed = True

        if (
            operational_status_id is not None
            and operational_status_id != terminal.operational_status_id
        ):
            old_code = self._require_operational_status(terminal.operational_status_id)
            new_code = self._require_operational_status(operational_status_id)
            self._audit_field_change(
                circuit_id=circuit_id,
                field_name="terminal_status",
                old_value=old_code,
                new_value=new_code,
                actor_user_id=actor_user_id,
            )
            terminal.operational_status_id = operational_status_id
            changed = True

        if changed:
            terminal.updated_by_user_id = actor_user_id
            self.db.flush()

        return terminal

    # --- SubstationVoltageYard ----------------------------------------------------
    def create_voltage_yard(
        self,
        *,
        substation_id: uuid.UUID,
        voltage_level_id: int,
        commissioning_date: date | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        actor_user_id: uuid.UUID,
    ) -> SubstationVoltageYard:
        self._require_substation(substation_id)
        self._check_geolocation_pair(latitude, longitude)
        voltage_level = self.reference_data.get_voltage_level(voltage_level_id)
        if voltage_level is None:
            raise ReferenceDataNotFoundError("voltage_level_id", voltage_level_id)
        if self.repo.voltage_yard_exists_for_substation_and_level(substation_id, voltage_level_id):
            substation = self.repo.get_substation_by_id(substation_id)
            substation_mnemonic = (
                substation.mnemonic if substation is not None else str(substation_id)
            )
            raise DuplicateVoltageYardError(substation_mnemonic, voltage_level.label)

        return self.repo.add_voltage_yard(
            SubstationVoltageYard(
                voltage_yard_id=uuid.uuid4(),
                substation_id=substation_id,
                voltage_level_id=voltage_level_id,
                commissioning_date=commissioning_date,
                latitude=latitude,
                longitude=longitude,
                operational_status_id=self._require_active_operational_status_id(),
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )

    def _audit_voltage_yard_field_change(
        self,
        *,
        voltage_yard_id: uuid.UUID,
        field_name: str,
        old_value: object,
        new_value: object,
        actor_user_id: uuid.UUID,
        change_reason: str | None = None,
    ) -> None:
        self.repo.add_voltage_yard_audit_log(
            SubstationVoltageYardAuditLog(
                voltage_yard_id=voltage_yard_id,
                field_name=field_name,
                old_value=None if old_value is None else str(old_value),
                new_value=None if new_value is None else str(new_value),
                changed_by_user_id=actor_user_id,
                change_reason=change_reason,
            )
        )

    def _require_no_active_references_to_voltage_yard(
        self, voltage_yard: SubstationVoltageYard
    ) -> None:
        """Deletion/correction policy point 5: existing references must be
        protected. A switchyard cannot be corrected as Entered in Error
        while a non-entered-in-error CircuitTerminal or TransformerTerminal
        (on a non-entered-in-error parent) still uses it."""
        circuit_count = self.repo.count_active_circuit_terminal_references(
            voltage_yard.voltage_yard_id
        )
        transformer_count = self.repo.count_active_transformer_terminal_references(
            voltage_yard.voltage_yard_id
        )
        if circuit_count or transformer_count:
            display = self.repo.get_voltage_yard_display_data({voltage_yard.voltage_yard_id})
            raise SwitchyardHasActiveReferencesError(
                self._switchyard_label(voltage_yard.voltage_yard_id, display),
                circuit_count,
                transformer_count,
            )

    # --- Update voltage yard (commissioning_date/latitude/longitude/status —
    # the substation/voltage level a yard represents are immutable after creation) ----
    def update_voltage_yard(
        self,
        voltage_yard_id: uuid.UUID,
        *,
        commissioning_date: date | None = ...,
        latitude: float | None = ...,
        longitude: float | None = ...,
        operational_status_id: int | None = None,
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> SubstationVoltageYard:
        yard = self.repo.get_voltage_yard_by_id(voltage_yard_id)
        if yard is None:
            raise VoltageYardNotFoundError(voltage_yard_id)

        changed = False

        if commissioning_date is not ... and commissioning_date != yard.commissioning_date:
            yard.commissioning_date = commissioning_date
            changed = True

        if latitude is not ... or longitude is not ...:
            new_latitude = yard.latitude if latitude is ... else latitude
            new_longitude = yard.longitude if longitude is ... else longitude
            if new_latitude != yard.latitude or new_longitude != yard.longitude:
                self._check_geolocation_pair(new_latitude, new_longitude)
                yard.latitude = new_latitude
                yard.longitude = new_longitude
                changed = True

        if (
            operational_status_id is not None
            and operational_status_id != yard.operational_status_id
        ):
            old_code = self._require_operational_status(yard.operational_status_id)
            new_code = self._require_operational_status(operational_status_id)
            if new_code == _ENTERED_IN_ERROR_STATUS_CODE:
                self._require_no_active_references_to_voltage_yard(yard)
            self._audit_voltage_yard_field_change(
                voltage_yard_id=voltage_yard_id,
                field_name="operational_status_id",
                old_value=old_code,
                new_value=new_code,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            yard.operational_status_id = operational_status_id
            changed = True

        if changed:
            yard.updated_by_user_id = actor_user_id
            self.db.flush()

        return yard

    def list_voltage_yards(
        self,
        *,
        substation_id: uuid.UUID | None = None,
        include_entered_in_error: bool = False,
    ) -> list[VoltageYardSummary]:
        yards = self.repo.list_voltage_yards(
            substation_id=substation_id, include_entered_in_error=include_entered_in_error
        )
        display = self.repo.get_voltage_yard_display_data({y.voltage_yard_id for y in yards})
        summaries: list[VoltageYardSummary] = []
        for yard in yards:
            info = display.get(yard.voltage_yard_id)
            if info is None:
                continue
            summaries.append(self._voltage_yard_summary(yard, info))
        return summaries

    def _voltage_yard_summary(
        self, yard: SubstationVoltageYard, info: VoltageYardDisplayData
    ) -> VoltageYardSummary:
        return VoltageYardSummary(
            voltage_yard_id=info.voltage_yard_id,
            substation_id=info.substation_id,
            substation_mnemonic=info.substation_mnemonic,
            substation_official_name=info.substation_official_name,
            voltage_level_id=info.voltage_level_id,
            voltage_level_label=info.voltage_level_label,
            display_label=self._compute_voltage_yard_label(
                info.substation_mnemonic, info.voltage_level_label
            ),
            commissioning_date=yard.commissioning_date,
            latitude=yard.latitude,
            longitude=yard.longitude,
            operational_status_id=yard.operational_status_id,
        )

    def list_voltage_yard_audit_log(
        self, voltage_yard_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[VoltageYardAuditLogEntry], int]:
        items, total = self.repo.list_voltage_yard_audit_log(
            voltage_yard_id, offset=(page - 1) * page_size, limit=page_size
        )
        entries = [
            VoltageYardAuditLogEntry(
                log_id=e.log_id,
                field_name=e.field_name,
                old_value=e.old_value,
                new_value=e.new_value,
                changed_at=e.changed_at,
                changed_by=self._resolve_user(e.changed_by_user_id),
                change_reason=e.change_reason,
            )
            for e in items
        ]
        return entries, total

    # --- Update (excludes operational_status_id — see change_status) ------------------
    def update_circuit(
        self,
        circuit_id: uuid.UUID,
        *,
        bay_number: str | None = None,
        voltage_level_id: int | None = None,
        line_type_id: int | None = None,
        is_interconnector: bool | None = None,
        remarks: str | None = ...,
        actor_user_id: uuid.UUID,
    ) -> Circuit:
        circuit = self.repo.get_circuit_by_id(circuit_id)
        if circuit is None:
            raise NotFoundError(f"Circuit {circuit_id} not found")

        changed = False

        if bay_number is not None and bay_number != circuit.bay_number:
            self._audit_field_change(
                circuit_id=circuit_id,
                field_name="bay_number",
                old_value=circuit.bay_number,
                new_value=bay_number,
                actor_user_id=actor_user_id,
            )
            circuit.bay_number = bay_number
            changed = True

        if voltage_level_id is not None and voltage_level_id != circuit.voltage_level_id:
            if self.reference_data.get_voltage_level(voltage_level_id) is None:
                raise ReferenceDataNotFoundError("voltage_level_id", voltage_level_id)
            self._audit_field_change(
                circuit_id=circuit_id,
                field_name="voltage_level_id",
                old_value=circuit.voltage_level_id,
                new_value=voltage_level_id,
                actor_user_id=actor_user_id,
            )
            circuit.voltage_level_id = voltage_level_id
            changed = True

        if line_type_id is not None and line_type_id != circuit.line_type_id:
            if self.reference_data.get_line_type(line_type_id) is None:
                raise ReferenceDataNotFoundError("line_type_id", line_type_id)
            self._audit_field_change(
                circuit_id=circuit_id,
                field_name="line_type_id",
                old_value=circuit.line_type_id,
                new_value=line_type_id,
                actor_user_id=actor_user_id,
            )
            circuit.line_type_id = line_type_id
            changed = True

        if is_interconnector is not None and is_interconnector != circuit.is_interconnector:
            self._audit_field_change(
                circuit_id=circuit_id,
                field_name="is_interconnector",
                old_value=circuit.is_interconnector,
                new_value=is_interconnector,
                actor_user_id=actor_user_id,
            )
            circuit.is_interconnector = is_interconnector
            changed = True

        if remarks is not ... and remarks != circuit.remarks:
            self._audit_field_change(
                circuit_id=circuit_id,
                field_name="remarks",
                old_value=circuit.remarks,
                new_value=remarks,
                actor_user_id=actor_user_id,
            )
            circuit.remarks = remarks
            changed = True

        if changed:
            circuit.updated_by_user_id = actor_user_id
            self.db.flush()

        return circuit

    # --- Status change (separate from update_circuit) --------------------------------
    def change_status(
        self,
        circuit_id: uuid.UUID,
        *,
        operational_status_id: int,
        change_reason: str | None,
        actor_user_id: uuid.UUID,
    ) -> Circuit:
        circuit = self.repo.get_circuit_by_id(circuit_id)
        if circuit is None:
            raise NotFoundError(f"Circuit {circuit_id} not found")

        current_code = self._require_operational_status(circuit.operational_status_id)
        target_code = self._require_operational_status(operational_status_id)

        if operational_status_id == circuit.operational_status_id:
            return circuit  # idempotent no-op, no audit row

        if target_code == _ACTIVE_STATUS_CODE:
            # Deletion/correction policy (Phase 3 follow-up): a circuit may
            # be temporarily incomplete while its terminals are being
            # corrected (update_terminal never blocks on this), but it may
            # not (re)enter Active with fewer than two active terminals —
            # the same completeness rule (equipment-registry-module.md §9
            # rule 5) enforced at the activation boundary instead.
            active_terminal_count = self.repo.count_active_terminals(circuit_id)
            if active_terminal_count < _MINIMUM_TERMINALS:
                raise InsufficientActiveTerminalsForActivationError(active_terminal_count)

        self._audit_field_change(
            circuit_id=circuit_id,
            field_name="operational_status_id",
            old_value=current_code,
            new_value=target_code,
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        circuit.operational_status_id = operational_status_id
        circuit.updated_by_user_id = actor_user_id
        self.db.flush()
        return circuit

    # --- Read ---------------------------------------------------------------------
    def _terminal_summaries(self, terminals: list[CircuitTerminal]) -> list[CircuitTerminalSummary]:
        display = self.repo.get_voltage_yard_display_data({t.voltage_yard_id for t in terminals})
        summaries: list[CircuitTerminalSummary] = []
        for terminal in terminals:
            info = display.get(terminal.voltage_yard_id)
            summaries.append(
                CircuitTerminalSummary(
                    circuit_terminal_id=terminal.circuit_terminal_id,
                    voltage_yard_id=terminal.voltage_yard_id,
                    substation_id=info.substation_id if info else uuid.UUID(int=0),
                    substation_mnemonic=info.substation_mnemonic if info else "",
                    substation_official_name=info.substation_official_name if info else "",
                    voltage_level_id=info.voltage_level_id if info else 0,
                    voltage_level_label=info.voltage_level_label if info else "",
                    breaker_number=terminal.breaker_number,
                    commissioning_date=terminal.commissioning_date,
                    remarks=terminal.remarks,
                    operational_status_id=terminal.operational_status_id,
                    created_at=terminal.created_at,
                    updated_at=terminal.updated_at,
                )
            )
        return summaries

    def get_circuit(self, circuit_id: uuid.UUID) -> CircuitDetail | None:
        circuit = self.repo.get_circuit_by_id(circuit_id)
        if circuit is None:
            return None
        # Detail view shows every terminal regardless of status — this page
        # is this module's own audit/history view (deletion/correction
        # policy, Phase 3 follow-up). The computed circuit_name, however,
        # reflects only the current, corrected picture: it excludes
        # ENTERED_IN_ERROR terminals, exactly like list_circuits' own
        # summary computation (repo.list_terminals_for_circuits).
        terminals = self.repo.list_terminals(circuit_id)
        terminal_summaries = self._terminal_summaries(terminals)
        entered_in_error_id = self._entered_in_error_status_id()
        active_mnemonics = [
            t.substation_mnemonic
            for t in terminal_summaries
            if t.operational_status_id != entered_in_error_id
        ]
        circuit_name = self._compute_circuit_name(active_mnemonics)
        return CircuitDetail(
            circuit_id=circuit.circuit_id,
            bay_number=circuit.bay_number,
            circuit_name=circuit_name,
            voltage_level_id=circuit.voltage_level_id,
            line_type_id=circuit.line_type_id,
            operational_status_id=circuit.operational_status_id,
            is_interconnector=circuit.is_interconnector,
            remarks=circuit.remarks,
            created_at=circuit.created_at,
            updated_at=circuit.updated_at,
            created_by=self._resolve_user(circuit.created_by_user_id),
            updated_by=self._resolve_user(circuit.updated_by_user_id),
            terminals=terminal_summaries,
        )

    def list_circuits(
        self,
        *,
        page: int,
        page_size: int,
        substation_id: uuid.UUID | None = None,
        voltage_level_id: int | None = None,
        line_type_id: int | None = None,
        operational_status_id: int | None = None,
        is_interconnector: bool | None = None,
        search: str | None = None,
        include_entered_in_error: bool = False,
    ) -> tuple[list[CircuitSummary], int]:
        items, total = self.repo.list_circuits(
            offset=(page - 1) * page_size,
            limit=page_size,
            substation_id=substation_id,
            voltage_level_id=voltage_level_id,
            line_type_id=line_type_id,
            operational_status_id=operational_status_id,
            is_interconnector=is_interconnector,
            search=search,
            include_entered_in_error=include_entered_in_error,
        )
        terminals_by_circuit = self.repo.list_terminals_for_circuits({c.circuit_id for c in items})
        all_voltage_yard_ids = {
            t.voltage_yard_id for terminals in terminals_by_circuit.values() for t in terminals
        }
        display = self.repo.get_voltage_yard_display_data(all_voltage_yard_ids)

        summaries: list[CircuitSummary] = []
        for circuit in items:
            terminals = terminals_by_circuit.get(circuit.circuit_id, [])
            mnemonics = [
                display[t.voltage_yard_id].substation_mnemonic
                for t in terminals
                if t.voltage_yard_id in display
            ]
            summaries.append(
                CircuitSummary(
                    circuit_id=circuit.circuit_id,
                    bay_number=circuit.bay_number,
                    circuit_name=self._compute_circuit_name(mnemonics),
                    voltage_level_id=circuit.voltage_level_id,
                    line_type_id=circuit.line_type_id,
                    operational_status_id=circuit.operational_status_id,
                    is_interconnector=circuit.is_interconnector,
                    terminal_count=len(terminals),
                )
            )
        return summaries, total

    def list_terminals(self, circuit_id: uuid.UUID) -> list[CircuitTerminalSummary]:
        return self._terminal_summaries(self.repo.list_terminals(circuit_id))

    def list_audit_log(
        self, circuit_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[CircuitAuditLogEntry], int]:
        items, total = self.repo.list_audit_log(
            circuit_id, offset=(page - 1) * page_size, limit=page_size
        )
        entries = [
            CircuitAuditLogEntry(
                log_id=e.log_id,
                field_name=e.field_name,
                old_value=e.old_value,
                new_value=e.new_value,
                changed_at=e.changed_at,
                changed_by=self._resolve_user(e.changed_by_user_id),
                change_reason=e.change_reason,
            )
            for e in items
        ]
        return entries, total

    # --- Transformer (Phase 3.5) ----------------------------------------------------
    def _audit_transformer_field_change(
        self,
        *,
        transformer_id: uuid.UUID,
        field_name: str,
        old_value: object,
        new_value: object,
        actor_user_id: uuid.UUID,
        change_reason: str | None = None,
    ) -> None:
        self.repo.add_transformer_audit_log(
            TransformerAuditLog(
                transformer_id=transformer_id,
                field_name=field_name,
                old_value=None if old_value is None else str(old_value),
                new_value=None if new_value is None else str(new_value),
                changed_by_user_id=actor_user_id,
                change_reason=change_reason,
            )
        )

    def _switchyard_label(
        self, voltage_yard_id: uuid.UUID, display: dict[uuid.UUID, VoltageYardDisplayData]
    ) -> str:
        info = display.get(voltage_yard_id)
        if info is None:
            return str(voltage_yard_id)
        return self._compute_voltage_yard_label(info.substation_mnemonic, info.voltage_level_label)

    def _compute_transformer_short_name(
        self, hv_voltage_level_id: int, transformer_number: str
    ) -> str:
        """TNB engineering short-name convention (Transformer Registry
        spec) — prefix determined by the HV side's nominal voltage. Falls
        back to "T" for any voltage level not in the documented table,
        rather than raising: this is a display convenience derived from
        data that has already passed all real validation, not itself a
        validation gate."""
        hv_level = self.reference_data.get_voltage_level(hv_voltage_level_id)
        nominal_kv = hv_level.nominal_kv if hv_level is not None else None
        prefix = (
            _TRANSFORMER_SHORT_NAME_PREFIX_BY_NOMINAL_KV.get(int(nominal_kv))
            if nominal_kv is not None
            else None
        ) or "T"
        return f"{prefix}{transformer_number}"

    def _require_yard_belongs_to_substation(
        self,
        *,
        side: str,
        yard: SubstationVoltageYard,
        substation_id: uuid.UUID,
        selected_substation_mnemonic: str,
    ) -> None:
        """UAT correction: a transformer's HV and LV switchyards must both
        belong to the substation it is being created at — transformers are
        not modeled as spanning substations (Malaysian grid domain rule)."""
        if yard.substation_id == substation_id:
            return
        display = self.repo.get_voltage_yard_display_data({yard.voltage_yard_id})
        yard_label = self._switchyard_label(yard.voltage_yard_id, display)
        yard_substation = self.repo.get_substation_by_id(yard.substation_id)
        yard_substation_mnemonic = (
            yard_substation.mnemonic if yard_substation is not None else str(yard.substation_id)
        )
        raise TransformerYardSubstationMismatchError(
            side, yard_label, yard_substation_mnemonic, selected_substation_mnemonic
        )

    def create_transformer(
        self,
        *,
        substation_id: uuid.UUID,
        transformer_number: str,
        hv_switchyard_id: uuid.UUID,
        hv_breaker_number: str,
        lv_switchyard_id: uuid.UUID,
        lv_breaker_number: str,
        capacity_mva: float | None,
        commissioning_date: date | None,
        operational_status_id: int,
        transformer_type: str | None,
        manufacturer: str | None,
        remarks: str | None,
        actor_user_id: uuid.UUID,
    ) -> Transformer:
        status_code = self._require_operational_status(operational_status_id)
        if status_code not in _ALLOWED_INITIAL_STATUS_CODES:
            raise InvalidTransformerInitialStatusError(status_code)

        substation = self.repo.get_substation_by_id(substation_id)
        if substation is None:
            raise SubstationNotFoundError(substation_id)

        hv_yard = self._require_voltage_yard(hv_switchyard_id)
        lv_yard = self._require_voltage_yard(lv_switchyard_id)

        # UAT correction: both switchyards must belong to the selected
        # substation — a transformer is substation-owned equipment, never
        # modeled as spanning two substations.
        self._require_yard_belongs_to_substation(
            side="HV",
            yard=hv_yard,
            substation_id=substation_id,
            selected_substation_mnemonic=substation.mnemonic,
        )
        self._require_yard_belongs_to_substation(
            side="LV",
            yard=lv_yard,
            substation_id=substation_id,
            selected_substation_mnemonic=substation.mnemonic,
        )

        if hv_yard.voltage_yard_id == lv_yard.voltage_yard_id:
            display = self.repo.get_voltage_yard_display_data({hv_yard.voltage_yard_id})
            raise SameSwitchyardTerminalsError(
                self._switchyard_label(hv_yard.voltage_yard_id, display)
            )

        hv_level = self.reference_data.get_voltage_level(hv_yard.voltage_level_id)
        lv_level = self.reference_data.get_voltage_level(lv_yard.voltage_level_id)
        # Both resolve: _require_voltage_yard already confirmed each yard
        # exists, and a SubstationVoltageYard's voltage_level_id FK can
        # never point at a missing reference row.
        assert hv_level is not None and lv_level is not None
        if hv_level.nominal_kv <= lv_level.nominal_kv:
            display = self.repo.get_voltage_yard_display_data(
                {hv_yard.voltage_yard_id, lv_yard.voltage_yard_id}
            )
            raise InvalidTransformerVoltageOrderError(
                self._switchyard_label(hv_yard.voltage_yard_id, display),
                self._switchyard_label(lv_yard.voltage_yard_id, display),
            )

        existing = self.repo.find_transformer_by_yard_pair_and_number(
            substation_id=substation_id,
            hv_switchyard_id=hv_switchyard_id,
            lv_switchyard_id=lv_switchyard_id,
            transformer_number=transformer_number,
        )
        if existing is not None:
            raise DuplicateTransformerError(transformer_number, substation.mnemonic)

        transformer = self.repo.add_transformer(
            Transformer(
                transformer_id=uuid.uuid4(),
                substation_id=substation_id,
                transformer_number=transformer_number,
                capacity_mva=capacity_mva,
                commissioning_date=commissioning_date,
                operational_status_id=operational_status_id,
                transformer_type=transformer_type,
                manufacturer=manufacturer,
                remarks=remarks,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )
        # No audit row for creation itself — accountability is already
        # captured by created_by_user_id/created_at directly on the row
        # (CLAUDE.md §5.4), matching Circuit's own precedent.
        self.repo.add_transformer_terminal(
            TransformerTerminal(
                transformer_terminal_id=uuid.uuid4(),
                transformer_id=transformer.transformer_id,
                side="HV",
                voltage_yard_id=hv_switchyard_id,
                breaker_number=hv_breaker_number,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )
        self.repo.add_transformer_terminal(
            TransformerTerminal(
                transformer_terminal_id=uuid.uuid4(),
                transformer_id=transformer.transformer_id,
                side="LV",
                voltage_yard_id=lv_switchyard_id,
                breaker_number=lv_breaker_number,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )
        return transformer

    def update_transformer(
        self,
        transformer_id: uuid.UUID,
        *,
        transformer_number: str | None = None,
        hv_breaker_number: str | None = None,
        lv_breaker_number: str | None = None,
        capacity_mva: float | None = ...,
        commissioning_date: date | None = ...,
        operational_status_id: int | None = None,
        transformer_type: str | None = ...,
        manufacturer: str | None = ...,
        remarks: str | None = ...,
        actor_user_id: uuid.UUID,
    ) -> Transformer:
        """Neither the transformer's `substation_id` nor the switchyard each
        terminal connects to is editable here — only `transformer_number`,
        each terminal's `breaker_number`, and the transformer's own
        metadata. Re-pointing a transformer to a different substation would
        change its physical identity (UAT correction: transformers are
        substation-owned equipment), which this phase treats as a new
        transformer, not an edit. `operational_status_id` is a plain field
        here, not a separate status-change endpoint like `Circuit`'s — no
        transition-legality graph is asserted for `Transformer` (not
        requested by this phase's spec; CLAUDE.md — Claude must not invent
        business rules)."""
        transformer = self.repo.get_transformer_by_id(transformer_id)
        if transformer is None:
            raise NotFoundError(f"Transformer {transformer_id} not found")

        changed = False

        if transformer_number is not None and transformer_number != transformer.transformer_number:
            # Uniqueness (UAT correction #2) is scoped to this transformer's
            # own substation + HV/LV switchyard pair, not the whole
            # substation — switchyards are immutable after creation (Business
            # Rule 6), so the existing terminals' voltage_yard_id values are
            # this transformer's permanent pair for the purpose of this check.
            hv_terminal = self.repo.get_transformer_terminal_by_side(transformer_id, "HV")
            lv_terminal = self.repo.get_transformer_terminal_by_side(transformer_id, "LV")
            assert hv_terminal is not None and lv_terminal is not None
            existing = self.repo.find_transformer_by_yard_pair_and_number(
                substation_id=transformer.substation_id,
                hv_switchyard_id=hv_terminal.voltage_yard_id,
                lv_switchyard_id=lv_terminal.voltage_yard_id,
                transformer_number=transformer_number,
                exclude_transformer_id=transformer_id,
            )
            if existing is not None:
                substation = self.repo.get_substation_by_id(transformer.substation_id)
                substation_mnemonic = (
                    substation.mnemonic
                    if substation is not None
                    else str(transformer.substation_id)
                )
                raise DuplicateTransformerError(transformer_number, substation_mnemonic)
            self._audit_transformer_field_change(
                transformer_id=transformer_id,
                field_name="transformer_number",
                old_value=transformer.transformer_number,
                new_value=transformer_number,
                actor_user_id=actor_user_id,
            )
            transformer.transformer_number = transformer_number
            changed = True

        if capacity_mva is not ... and capacity_mva != transformer.capacity_mva:
            self._audit_transformer_field_change(
                transformer_id=transformer_id,
                field_name="capacity_mva",
                old_value=transformer.capacity_mva,
                new_value=capacity_mva,
                actor_user_id=actor_user_id,
            )
            transformer.capacity_mva = capacity_mva
            changed = True

        if commissioning_date is not ... and commissioning_date != transformer.commissioning_date:
            self._audit_transformer_field_change(
                transformer_id=transformer_id,
                field_name="commissioning_date",
                old_value=transformer.commissioning_date,
                new_value=commissioning_date,
                actor_user_id=actor_user_id,
            )
            transformer.commissioning_date = commissioning_date
            changed = True

        if (
            operational_status_id is not None
            and operational_status_id != transformer.operational_status_id
        ):
            old_code = self._require_operational_status(transformer.operational_status_id)
            new_code = self._require_operational_status(operational_status_id)
            self._audit_transformer_field_change(
                transformer_id=transformer_id,
                field_name="operational_status_id",
                old_value=old_code,
                new_value=new_code,
                actor_user_id=actor_user_id,
            )
            transformer.operational_status_id = operational_status_id
            changed = True

        if transformer_type is not ... and transformer_type != transformer.transformer_type:
            self._audit_transformer_field_change(
                transformer_id=transformer_id,
                field_name="transformer_type",
                old_value=transformer.transformer_type,
                new_value=transformer_type,
                actor_user_id=actor_user_id,
            )
            transformer.transformer_type = transformer_type
            changed = True

        if manufacturer is not ... and manufacturer != transformer.manufacturer:
            self._audit_transformer_field_change(
                transformer_id=transformer_id,
                field_name="manufacturer",
                old_value=transformer.manufacturer,
                new_value=manufacturer,
                actor_user_id=actor_user_id,
            )
            transformer.manufacturer = manufacturer
            changed = True

        if remarks is not ... and remarks != transformer.remarks:
            self._audit_transformer_field_change(
                transformer_id=transformer_id,
                field_name="remarks",
                old_value=transformer.remarks,
                new_value=remarks,
                actor_user_id=actor_user_id,
            )
            transformer.remarks = remarks
            changed = True

        if hv_breaker_number is not None:
            hv_terminal = self.repo.get_transformer_terminal_by_side(transformer_id, "HV")
            if hv_terminal is not None and hv_breaker_number != hv_terminal.breaker_number:
                self._audit_transformer_field_change(
                    transformer_id=transformer_id,
                    field_name="hv_breaker_number",
                    old_value=hv_terminal.breaker_number,
                    new_value=hv_breaker_number,
                    actor_user_id=actor_user_id,
                )
                hv_terminal.breaker_number = hv_breaker_number
                hv_terminal.updated_by_user_id = actor_user_id
                changed = True

        if lv_breaker_number is not None:
            lv_terminal = self.repo.get_transformer_terminal_by_side(transformer_id, "LV")
            if lv_terminal is not None and lv_breaker_number != lv_terminal.breaker_number:
                self._audit_transformer_field_change(
                    transformer_id=transformer_id,
                    field_name="lv_breaker_number",
                    old_value=lv_terminal.breaker_number,
                    new_value=lv_breaker_number,
                    actor_user_id=actor_user_id,
                )
                lv_terminal.breaker_number = lv_breaker_number
                lv_terminal.updated_by_user_id = actor_user_id
                changed = True

        if changed:
            transformer.updated_by_user_id = actor_user_id
            self.db.flush()

        return transformer

    def _transformer_terminal_summaries(
        self, terminals: list[TransformerTerminal]
    ) -> list[TransformerTerminalSummary]:
        display = self.repo.get_voltage_yard_display_data({t.voltage_yard_id for t in terminals})
        summaries: list[TransformerTerminalSummary] = []
        for terminal in terminals:
            info = display.get(terminal.voltage_yard_id)
            summaries.append(
                TransformerTerminalSummary(
                    transformer_terminal_id=terminal.transformer_terminal_id,
                    side=terminal.side,
                    voltage_yard_id=terminal.voltage_yard_id,
                    substation_id=info.substation_id if info else uuid.UUID(int=0),
                    substation_mnemonic=info.substation_mnemonic if info else "",
                    substation_official_name=info.substation_official_name if info else "",
                    voltage_level_id=info.voltage_level_id if info else 0,
                    voltage_level_label=info.voltage_level_label if info else "",
                    breaker_number=terminal.breaker_number,
                )
            )
        return summaries

    def get_transformer(self, transformer_id: uuid.UUID) -> TransformerDetail | None:
        transformer = self.repo.get_transformer_by_id(transformer_id)
        if transformer is None:
            return None
        terminals = self.repo.list_transformer_terminals(transformer_id)
        terminal_summaries = self._transformer_terminal_summaries(terminals)
        hv_summary = next((t for t in terminal_summaries if t.side == "HV"), None)
        generated_short_name = (
            self._compute_transformer_short_name(
                hv_summary.voltage_level_id, transformer.transformer_number
            )
            if hv_summary is not None
            else transformer.transformer_number
        )
        substation = self.repo.get_substation_by_id(transformer.substation_id)
        return TransformerDetail(
            transformer_id=transformer.transformer_id,
            substation_id=transformer.substation_id,
            substation_mnemonic=substation.mnemonic if substation is not None else "",
            substation_official_name=substation.official_name if substation is not None else "",
            transformer_number=transformer.transformer_number,
            generated_short_name=generated_short_name,
            capacity_mva=transformer.capacity_mva,
            commissioning_date=transformer.commissioning_date,
            operational_status_id=transformer.operational_status_id,
            transformer_type=transformer.transformer_type,
            manufacturer=transformer.manufacturer,
            remarks=transformer.remarks,
            created_at=transformer.created_at,
            updated_at=transformer.updated_at,
            created_by=self._resolve_user(transformer.created_by_user_id),
            updated_by=self._resolve_user(transformer.updated_by_user_id),
            terminals=terminal_summaries,
        )

    def list_transformers(
        self,
        *,
        page: int,
        page_size: int,
        substation_id: uuid.UUID | None = None,
        operational_status_id: int | None = None,
        search: str | None = None,
        include_entered_in_error: bool = False,
    ) -> tuple[list[TransformerSummary], int]:
        items, total = self.repo.list_transformers(
            offset=(page - 1) * page_size,
            limit=page_size,
            substation_id=substation_id,
            operational_status_id=operational_status_id,
            search=search,
            include_entered_in_error=include_entered_in_error,
        )
        terminals_by_transformer = self.repo.list_transformer_terminals_for_transformers(
            {t.transformer_id for t in items}
        )
        all_voltage_yard_ids = {
            term.voltage_yard_id
            for terminals in terminals_by_transformer.values()
            for term in terminals
        }
        display = self.repo.get_voltage_yard_display_data(all_voltage_yard_ids)
        substations = self.repo.get_substations_by_ids({t.substation_id for t in items})

        summaries: list[TransformerSummary] = []
        for transformer in items:
            terminals = terminals_by_transformer.get(transformer.transformer_id, [])
            hv_terminal = next((t for t in terminals if t.side == "HV"), None)
            lv_terminal = next((t for t in terminals if t.side == "LV"), None)
            hv_info = display.get(hv_terminal.voltage_yard_id) if hv_terminal else None
            lv_info = display.get(lv_terminal.voltage_yard_id) if lv_terminal else None
            generated_short_name = (
                self._compute_transformer_short_name(
                    hv_info.voltage_level_id, transformer.transformer_number
                )
                if hv_info is not None
                else transformer.transformer_number
            )
            substation = substations.get(transformer.substation_id)
            summaries.append(
                TransformerSummary(
                    transformer_id=transformer.transformer_id,
                    substation_id=transformer.substation_id,
                    substation_mnemonic=substation.mnemonic if substation is not None else "",
                    substation_official_name=(
                        substation.official_name if substation is not None else ""
                    ),
                    transformer_number=transformer.transformer_number,
                    generated_short_name=generated_short_name,
                    hv_voltage_level_label=hv_info.voltage_level_label if hv_info else "",
                    lv_voltage_level_label=lv_info.voltage_level_label if lv_info else "",
                    capacity_mva=transformer.capacity_mva,
                    operational_status_id=transformer.operational_status_id,
                )
            )
        return summaries, total

    def list_transformer_audit_log(
        self, transformer_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[TransformerAuditLogEntry], int]:
        items, total = self.repo.list_transformer_audit_log(
            transformer_id, offset=(page - 1) * page_size, limit=page_size
        )
        entries = [
            TransformerAuditLogEntry(
                log_id=e.log_id,
                field_name=e.field_name,
                old_value=e.old_value,
                new_value=e.new_value,
                changed_at=e.changed_at,
                changed_by=self._resolve_user(e.changed_by_user_id),
                change_reason=e.change_reason,
            )
            for e in items
        ]
        return entries, total
