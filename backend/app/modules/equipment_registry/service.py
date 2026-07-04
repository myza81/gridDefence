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
    DuplicateVoltageYardError,
    InsufficientTerminalsError,
    InvalidGeolocationPairError,
    InvalidInitialStatusError,
    NotFoundError,
    ReferenceDataNotFoundError,
    SubstationNotFoundError,
    TerminalVoltageLevelMismatchError,
    VoltageYardNotFoundError,
)
from app.modules.equipment_registry.models import (
    Circuit,
    CircuitTerminal,
    EquipmentRegistryAuditLog,
    SubstationVoltageYard,
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
    VoltageYardSummary,
)
from app.modules.iam.schemas import UserSummary
from app.modules.iam.service import IAMService
from app.reference_data.repository import ReferenceDataRepository

# "Create: always starts as Planned or Active" — mirrors the same
# creation-time exception already established for Substation Registry
# (substation_registry/service.py), since equipment-registry-module.md §8
# reuses the same operational_status *values*.
_ALLOWED_INITIAL_STATUS_CODES = {"PLANNED", "ACTIVE"}
_MINIMUM_TERMINALS = 2


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

    def _require_voltage_yard(self, voltage_yard_id: uuid.UUID) -> SubstationVoltageYard:
        voltage_yard = self.repo.get_voltage_yard_by_id(voltage_yard_id)
        if voltage_yard is None:
            raise VoltageYardNotFoundError(voltage_yard_id)
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
            self._require_voltage_yard_matches_circuit_level(
                voltage_yard, circuit_voltage_level_id
            )

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
        for terminal in terminals:
            self.repo.add_terminal(
                CircuitTerminal(
                    circuit_terminal_id=uuid.uuid4(),
                    circuit_id=circuit.circuit_id,
                    voltage_yard_id=terminal.voltage_yard_id,
                    breaker_number=terminal.breaker_number,
                    commissioning_date=terminal.commissioning_date,
                    remarks=terminal.remarks,
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

    # --- Update terminal (breaker_number / commissioning_date / remarks) -------------
    def update_terminal(
        self,
        circuit_id: uuid.UUID,
        circuit_terminal_id: uuid.UUID,
        *,
        breaker_number: str | None = None,
        commissioning_date: date | None = ...,
        remarks: str | None = ...,
        actor_user_id: uuid.UUID,
    ) -> CircuitTerminal:
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
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )

    # --- Update voltage yard metadata (commissioning_date/latitude/longitude only —
    # the substation/voltage level a yard represents are immutable after creation) ----
    def update_voltage_yard(
        self,
        voltage_yard_id: uuid.UUID,
        *,
        commissioning_date: date | None = ...,
        latitude: float | None = ...,
        longitude: float | None = ...,
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

        if changed:
            yard.updated_by_user_id = actor_user_id
            self.db.flush()

        return yard

    def list_voltage_yards(
        self, *, substation_id: uuid.UUID | None = None
    ) -> list[VoltageYardSummary]:
        yards = self.repo.list_voltage_yards(substation_id=substation_id)
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
        )

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
                    created_at=terminal.created_at,
                    updated_at=terminal.updated_at,
                )
            )
        return summaries

    def get_circuit(self, circuit_id: uuid.UUID) -> CircuitDetail | None:
        circuit = self.repo.get_circuit_by_id(circuit_id)
        if circuit is None:
            return None
        terminals = self.repo.list_terminals(circuit_id)
        terminal_summaries = self._terminal_summaries(terminals)
        circuit_name = self._compute_circuit_name(
            [t.substation_mnemonic for t in terminal_summaries]
        )
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
        voltage_level_id: int | None = None,
        line_type_id: int | None = None,
        operational_status_id: int | None = None,
        is_interconnector: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[CircuitSummary], int]:
        items, total = self.repo.list_circuits(
            offset=(page - 1) * page_size,
            limit=page_size,
            voltage_level_id=voltage_level_id,
            line_type_id=line_type_id,
            operational_status_id=operational_status_id,
            is_interconnector=is_interconnector,
            search=search,
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
