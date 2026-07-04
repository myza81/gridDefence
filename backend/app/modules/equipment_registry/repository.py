"""Equipment Registry repository layer (CLAUDE.md §14) — pure persistence
access. No business rules, no permission checks, no audit writing live here
— that is `service.py`'s responsibility.

`Substation` (from `app.modules.substation_registry.models`) and
`VoltageLevel` (from `app.reference_data.models`) are imported read-only,
for search/filter joins and batch-resolving terminal display data only —
never written to. This is the read-only cross-module join CLAUDE.md F6 and
DEVELOPMENT.md §7a explicitly permit for query optimisation/reporting; it
is not a substitute for calling Substation Registry's own service layer for
any business decision (none is made here).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.equipment_registry.models import (
    Circuit,
    CircuitTerminal,
    EquipmentRegistryAuditLog,
    SubstationVoltageYard,
)
from app.modules.substation_registry.models import Substation
from app.reference_data.models import VoltageLevel

# Reference-table primary keys are SMALLINT on PostgreSQL (CLAUDE.md A5) —
# max 32767. A caller-supplied filter value outside this range can never
# match a real row; short-circuiting to "no results" here, rather than
# letting it reach the database, avoids a raw
# psycopg.errors.NumericValueOutOfRange surfacing from a filtered list
# query — the same real PostgreSQL-only behaviour (invisible under SQLite's
# flexible typing) already found and fixed for single-row lookups in
# app/reference_data/repository.py's Phase 2 follow-up.
_SMALLINT_MAX = 32767


def _in_smallint_range(value: int) -> bool:
    return 1 <= value <= _SMALLINT_MAX


@dataclass
class VoltageYardDisplayData:
    """Resolved, read-only display data for one `SubstationVoltageYard` —
    never stored, always computed at query time (equipment-registry-module.md
    §7.5a)."""

    voltage_yard_id: uuid.UUID
    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    voltage_level_id: int
    voltage_level_label: str


class EquipmentRegistryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Circuit ----------------------------------------------------------------
    def get_circuit_by_id(self, circuit_id: uuid.UUID) -> Circuit | None:
        return self.db.get(Circuit, circuit_id)

    def add_circuit(self, circuit: Circuit) -> Circuit:
        self.db.add(circuit)
        self.db.flush()
        return circuit

    def list_circuits(
        self,
        *,
        offset: int,
        limit: int,
        voltage_level_id: int | None = None,
        line_type_id: int | None = None,
        operational_status_id: int | None = None,
        is_interconnector: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[Circuit], int]:
        for filter_value in (voltage_level_id, line_type_id, operational_status_id):
            if filter_value is not None and not _in_smallint_range(filter_value):
                return [], 0

        stmt = select(Circuit)
        if voltage_level_id is not None:
            stmt = stmt.where(Circuit.voltage_level_id == voltage_level_id)
        if line_type_id is not None:
            stmt = stmt.where(Circuit.line_type_id == line_type_id)
        if operational_status_id is not None:
            stmt = stmt.where(Circuit.operational_status_id == operational_status_id)
        if is_interconnector is not None:
            stmt = stmt.where(Circuit.is_interconnector == is_interconnector)
        if search:
            pattern = f"%{search.lower()}%"
            matching_circuit_ids = (
                select(CircuitTerminal.circuit_id)
                .join(
                    SubstationVoltageYard,
                    SubstationVoltageYard.voltage_yard_id == CircuitTerminal.voltage_yard_id,
                )
                .join(Substation, Substation.substation_id == SubstationVoltageYard.substation_id)
                .where(
                    func.lower(Substation.mnemonic).like(pattern)
                    | func.lower(Substation.official_name).like(pattern)
                )
            )
            stmt = stmt.where(
                func.lower(Circuit.bay_number).like(pattern)
                | Circuit.circuit_id.in_(matching_circuit_ids)
            )

        total = self.db.execute(
            select(func.count()).select_from(stmt.with_only_columns(Circuit.circuit_id).subquery())
        ).scalar_one()

        stmt = stmt.order_by(Circuit.bay_number).offset(offset).limit(limit)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    # --- CircuitTerminal ----------------------------------------------------------
    def add_terminal(self, terminal: CircuitTerminal) -> CircuitTerminal:
        self.db.add(terminal)
        self.db.flush()
        return terminal

    def get_terminal_by_id(self, circuit_terminal_id: uuid.UUID) -> CircuitTerminal | None:
        return self.db.get(CircuitTerminal, circuit_terminal_id)

    def list_terminals(self, circuit_id: uuid.UUID) -> list[CircuitTerminal]:
        stmt = (
            select(CircuitTerminal)
            .where(CircuitTerminal.circuit_id == circuit_id)
            .order_by(CircuitTerminal.created_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_terminals_for_circuits(
        self, circuit_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, list[CircuitTerminal]]:
        """Batch-fetches terminals for several circuits in one query — used
        by list views to avoid one query per row (N+1)."""
        if not circuit_ids:
            return {}
        stmt = (
            select(CircuitTerminal)
            .where(CircuitTerminal.circuit_id.in_(circuit_ids))
            .order_by(CircuitTerminal.created_at)
        )
        by_circuit: dict[uuid.UUID, list[CircuitTerminal]] = {}
        for terminal in self.db.execute(stmt).scalars().all():
            by_circuit.setdefault(terminal.circuit_id, []).append(terminal)
        return by_circuit

    def terminal_exists_for_voltage_yard(
        self, circuit_id: uuid.UUID, voltage_yard_id: uuid.UUID
    ) -> bool:
        stmt = select(CircuitTerminal.circuit_terminal_id).where(
            CircuitTerminal.circuit_id == circuit_id,
            CircuitTerminal.voltage_yard_id == voltage_yard_id,
        )
        return self.db.execute(stmt).first() is not None

    def count_terminals(self, circuit_id: uuid.UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(CircuitTerminal)
            .where(CircuitTerminal.circuit_id == circuit_id)
        )
        return self.db.execute(stmt).scalar_one()

    # --- SubstationVoltageYard ----------------------------------------------------
    def add_voltage_yard(self, voltage_yard: SubstationVoltageYard) -> SubstationVoltageYard:
        self.db.add(voltage_yard)
        self.db.flush()
        return voltage_yard

    def get_voltage_yard_by_id(self, voltage_yard_id: uuid.UUID) -> SubstationVoltageYard | None:
        return self.db.get(SubstationVoltageYard, voltage_yard_id)

    def voltage_yard_exists_for_substation_and_level(
        self, substation_id: uuid.UUID, voltage_level_id: int
    ) -> bool:
        stmt = select(SubstationVoltageYard.voltage_yard_id).where(
            SubstationVoltageYard.substation_id == substation_id,
            SubstationVoltageYard.voltage_level_id == voltage_level_id,
        )
        return self.db.execute(stmt).first() is not None

    def list_voltage_yards(
        self, *, substation_id: uuid.UUID | None = None
    ) -> list[SubstationVoltageYard]:
        stmt = select(SubstationVoltageYard)
        if substation_id is not None:
            stmt = stmt.where(SubstationVoltageYard.substation_id == substation_id)
        return list(self.db.execute(stmt).scalars().all())

    def get_voltage_yard_display_data(
        self, voltage_yard_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, VoltageYardDisplayData]:
        """Batch-resolves voltage yards to their substation mnemonic/name
        and voltage level label for display — computed at query time, never
        stored (equipment-registry-module.md §7.5a)."""
        if not voltage_yard_ids:
            return {}
        stmt = (
            select(SubstationVoltageYard, Substation, VoltageLevel)
            .join(Substation, Substation.substation_id == SubstationVoltageYard.substation_id)
            .join(
                VoltageLevel,
                VoltageLevel.voltage_level_id == SubstationVoltageYard.voltage_level_id,
            )
            .where(SubstationVoltageYard.voltage_yard_id.in_(voltage_yard_ids))
        )
        result: dict[uuid.UUID, VoltageYardDisplayData] = {}
        for yard, substation, voltage_level in self.db.execute(stmt).all():
            result[yard.voltage_yard_id] = VoltageYardDisplayData(
                voltage_yard_id=yard.voltage_yard_id,
                substation_id=substation.substation_id,
                substation_mnemonic=substation.mnemonic,
                substation_official_name=substation.official_name,
                voltage_level_id=voltage_level.voltage_level_id,
                voltage_level_label=voltage_level.label,
            )
        return result

    # --- Read-only substation/voltage-level resolution (display only, no duplication) --
    def substation_exists(self, substation_id: uuid.UUID) -> bool:
        return self.db.get(Substation, substation_id) is not None

    def get_substation_by_id(self, substation_id: uuid.UUID) -> Substation | None:
        return self.db.get(Substation, substation_id)

    def voltage_level_exists(self, voltage_level_id: int) -> bool:
        if not _in_smallint_range(voltage_level_id):
            return False
        return self.db.get(VoltageLevel, voltage_level_id) is not None

    # --- EquipmentRegistryAuditLog --------------------------------------------------
    def add_audit_log(self, entry: EquipmentRegistryAuditLog) -> EquipmentRegistryAuditLog:
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_audit_log(
        self, circuit_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[EquipmentRegistryAuditLog], int]:
        total = self.db.execute(
            select(func.count())
            .select_from(EquipmentRegistryAuditLog)
            .where(EquipmentRegistryAuditLog.circuit_id == circuit_id)
        ).scalar_one()

        stmt = (
            select(EquipmentRegistryAuditLog)
            .where(EquipmentRegistryAuditLog.circuit_id == circuit_id)
            .order_by(EquipmentRegistryAuditLog.changed_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total
