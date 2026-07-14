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
from sqlalchemy.orm import Session, aliased

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
from app.modules.substation_registry.models import Substation
from app.reference_data.models import OperationalStatus, VoltageLevel

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


def _entered_in_error_status_id_subquery():
    """Resolves the `ENTERED_IN_ERROR` reference row's id by its stable
    `code`, as a scalar subquery — used to exclude corrected records from
    default list views (Equipment Registry deletion/correction policy,
    Phase 3 follow-up) without the repository layer hardcoding a numeric
    id that depends on seed insertion order."""
    return (
        select(OperationalStatus.operational_status_id)
        .where(OperationalStatus.code == "ENTERED_IN_ERROR")
        .scalar_subquery()
    )


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
        substation_id: uuid.UUID | None = None,
        voltage_level_id: int | None = None,
        line_type_id: int | None = None,
        operational_status_id: int | None = None,
        is_interconnector: bool | None = None,
        search: str | None = None,
        include_entered_in_error: bool = False,
    ) -> tuple[list[Circuit], int]:
        for filter_value in (voltage_level_id, line_type_id, operational_status_id):
            if filter_value is not None and not _in_smallint_range(filter_value):
                return [], 0

        stmt = select(Circuit)
        if not include_entered_in_error and operational_status_id is None:
            # Deletion/correction policy (Phase 3 follow-up): a mistakenly-
            # created circuit is hidden from default views, never hard-
            # deleted (CLAUDE.md §11.6) — still reachable directly by id
            # (get_circuit), and via this same list with the flag set. An
            # explicit operational_status_id filter is a more specific ask
            # than "give me the default view" and is never overridden by
            # this default exclusion (e.g. filtering for Entered in Error
            # rows directly must actually return them).
            stmt = stmt.where(
                Circuit.operational_status_id != _entered_in_error_status_id_subquery()
            )
        if substation_id is not None:
            # "Engineering Connectivity" (Substation Detail page): a circuit
            # is connected to a substation iff at least one of its
            # terminals' switchyards belongs to that substation — derived
            # from Circuit/CircuitTerminal/Substation, never PSS/E data
            # (docs/architecture/equipment-registry-module.md's Engineering
            # Connectivity addendum).
            connected_circuit_ids = (
                select(CircuitTerminal.circuit_id)
                .join(
                    SubstationVoltageYard,
                    SubstationVoltageYard.voltage_yard_id == CircuitTerminal.voltage_yard_id,
                )
                .where(SubstationVoltageYard.substation_id == substation_id)
            )
            stmt = stmt.where(Circuit.circuit_id.in_(connected_circuit_ids))
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

    def list_all_circuit_terminals(self) -> list[CircuitTerminal]:
        """Every Circuit Terminal across every substation, unfiltered and
        unpaginated — mirrors `list_all_transformer_terminals` exactly, for
        the same cross-module-picker reason (Foundation Hardening Sprint
        A.1's Boundary Pocket diagnostic evaluator: opening points are
        selected *across* circuits/substations, not within one
        already-selected Circuit, unlike `list_terminals` above). Acceptable
        unpaginated for a modestly-sized, manually-maintained equipment
        registry (CLAUDE.md §21)."""
        stmt = select(CircuitTerminal).order_by(CircuitTerminal.circuit_id)
        return list(self.db.execute(stmt).scalars().all())

    def list_terminals_for_circuits(
        self, circuit_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, list[CircuitTerminal]]:
        """Batch-fetches terminals for several circuits in one query — used
        by `list_circuits` (the summary/list view) to compute `circuit_name`
        and `terminal_count`. Deliberately excludes `ENTERED_IN_ERROR`
        terminals: the list view's name/count should reflect the current,
        corrected picture of each circuit, not a mistaken terminal that has
        since been corrected. `get_circuit`'s own single-circuit terminal
        fetch (`list_terminals`) is unfiltered — the detail page is this
        module's audit/history view and shows every terminal regardless of
        status (Equipment Registry deletion/correction policy)."""
        if not circuit_ids:
            return {}
        stmt = (
            select(CircuitTerminal)
            .where(
                CircuitTerminal.circuit_id.in_(circuit_ids),
                CircuitTerminal.operational_status_id != _entered_in_error_status_id_subquery(),
            )
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

    def count_active_terminals(self, circuit_id: uuid.UUID) -> int:
        """Excludes `ENTERED_IN_ERROR` terminals — backs the activation
        guard (a circuit may not transition to `ACTIVE` with fewer than two
        active terminals; deletion/correction policy, Phase 3 follow-up)."""
        stmt = (
            select(func.count())
            .select_from(CircuitTerminal)
            .where(
                CircuitTerminal.circuit_id == circuit_id,
                CircuitTerminal.operational_status_id != _entered_in_error_status_id_subquery(),
            )
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
        self,
        *,
        substation_id: uuid.UUID | None = None,
        include_entered_in_error: bool = False,
    ) -> list[SubstationVoltageYard]:
        stmt = select(SubstationVoltageYard)
        if substation_id is not None:
            stmt = stmt.where(SubstationVoltageYard.substation_id == substation_id)
        if not include_entered_in_error:
            # Deletion/correction policy (Phase 3 follow-up): hidden from
            # default views (including the Add Terminal/Create Transformer
            # switchyard pickers), never hard-deleted.
            stmt = stmt.where(
                SubstationVoltageYard.operational_status_id
                != _entered_in_error_status_id_subquery()
            )
        return list(self.db.execute(stmt).scalars().all())

    def count_active_circuit_terminal_references(self, voltage_yard_id: uuid.UUID) -> int:
        """Counts `CircuitTerminal` rows at this switchyard whose own
        status, and whose parent `Circuit`'s status, are both not
        `ENTERED_IN_ERROR` — backs the reference-protection check on
        correcting a switchyard (deletion/correction policy point 5)."""
        stmt = (
            select(func.count())
            .select_from(CircuitTerminal)
            .join(Circuit, Circuit.circuit_id == CircuitTerminal.circuit_id)
            .where(
                CircuitTerminal.voltage_yard_id == voltage_yard_id,
                CircuitTerminal.operational_status_id != _entered_in_error_status_id_subquery(),
                Circuit.operational_status_id != _entered_in_error_status_id_subquery(),
            )
        )
        return self.db.execute(stmt).scalar_one()

    def count_active_transformer_terminal_references(self, voltage_yard_id: uuid.UUID) -> int:
        """Counts `TransformerTerminal` rows at this switchyard whose
        parent `Transformer` is not `ENTERED_IN_ERROR` —
        `TransformerTerminal` itself carries no independent status (a
        mistaken transformer is corrected as a whole, never per-terminal;
        see `Transformer`'s own model docstring)."""
        stmt = (
            select(func.count())
            .select_from(TransformerTerminal)
            .join(Transformer, Transformer.transformer_id == TransformerTerminal.transformer_id)
            .where(
                TransformerTerminal.voltage_yard_id == voltage_yard_id,
                Transformer.operational_status_id != _entered_in_error_status_id_subquery(),
            )
        )
        return self.db.execute(stmt).scalar_one()

    # --- SubstationVoltageYardAuditLog (Phase 3 follow-up) ---------------------------
    def add_voltage_yard_audit_log(
        self, entry: SubstationVoltageYardAuditLog
    ) -> SubstationVoltageYardAuditLog:
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_voltage_yard_audit_log(
        self, voltage_yard_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[SubstationVoltageYardAuditLog], int]:
        total = self.db.execute(
            select(func.count())
            .select_from(SubstationVoltageYardAuditLog)
            .where(SubstationVoltageYardAuditLog.voltage_yard_id == voltage_yard_id)
        ).scalar_one()

        stmt = (
            select(SubstationVoltageYardAuditLog)
            .where(SubstationVoltageYardAuditLog.voltage_yard_id == voltage_yard_id)
            .order_by(SubstationVoltageYardAuditLog.changed_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

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

    def get_substations_by_ids(self, substation_ids: set[uuid.UUID]) -> dict[uuid.UUID, Substation]:
        """Batch-resolves substations for display (e.g. a transformer list's
        substation mnemonic/name column) — avoids one query per row (N+1),
        mirroring `get_voltage_yard_display_data`'s own batch pattern."""
        if not substation_ids:
            return {}
        stmt = select(Substation).where(Substation.substation_id.in_(substation_ids))
        return {s.substation_id: s for s in self.db.execute(stmt).scalars().all()}

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

    # --- Transformer (Phase 3.5) --------------------------------------------------
    def get_transformer_by_id(self, transformer_id: uuid.UUID) -> Transformer | None:
        return self.db.get(Transformer, transformer_id)

    def add_transformer(self, transformer: Transformer) -> Transformer:
        self.db.add(transformer)
        self.db.flush()
        return transformer

    def list_transformers(
        self,
        *,
        offset: int,
        limit: int,
        substation_id: uuid.UUID | None = None,
        operational_status_id: int | None = None,
        search: str | None = None,
        include_entered_in_error: bool = False,
    ) -> tuple[list[Transformer], int]:
        if operational_status_id is not None and not _in_smallint_range(operational_status_id):
            return [], 0

        stmt = select(Transformer)
        if not include_entered_in_error and operational_status_id is None:
            # Deletion/correction policy (Phase 3 follow-up): a mistakenly-
            # created transformer is hidden from default views, never
            # hard-deleted (CLAUDE.md §11.6) — still reachable directly by
            # id (get_transformer), and via this same list with the flag set.
            # An explicit operational_status_id filter bypasses this default
            # exclusion, same reasoning as list_circuits.
            stmt = stmt.where(
                Transformer.operational_status_id != _entered_in_error_status_id_subquery()
            )
        if substation_id is not None:
            stmt = stmt.where(Transformer.substation_id == substation_id)
        if operational_status_id is not None:
            stmt = stmt.where(Transformer.operational_status_id == operational_status_id)
        if search:
            # `substation_id` now lives directly on `Transformer` (UAT
            # correction), so a substation-mnemonic/name search resolves via
            # a simple subquery on `Substation` alone — no longer needs to
            # go through `TransformerTerminal`/`SubstationVoltageYard`.
            pattern = f"%{search.lower()}%"
            matching_substation_ids = select(Substation.substation_id).where(
                func.lower(Substation.mnemonic).like(pattern)
                | func.lower(Substation.official_name).like(pattern)
            )
            stmt = stmt.where(
                func.lower(Transformer.transformer_number).like(pattern)
                | Transformer.substation_id.in_(matching_substation_ids)
            )

        total = self.db.execute(
            select(func.count()).select_from(
                stmt.with_only_columns(Transformer.transformer_id).subquery()
            )
        ).scalar_one()

        stmt = stmt.order_by(Transformer.transformer_number).offset(offset).limit(limit)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    # --- TransformerTerminal --------------------------------------------------------
    def add_transformer_terminal(self, terminal: TransformerTerminal) -> TransformerTerminal:
        self.db.add(terminal)
        self.db.flush()
        return terminal

    def list_transformer_terminals(self, transformer_id: uuid.UUID) -> list[TransformerTerminal]:
        stmt = (
            select(TransformerTerminal)
            .where(TransformerTerminal.transformer_id == transformer_id)
            .order_by(TransformerTerminal.side)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_all_transformer_terminals(self) -> list[TransformerTerminal]:
        """Every Transformer Terminal across every substation, unfiltered
        and unpaginated — for cross-module pickers that need full identity
        without requiring a substation/transformer to be chosen first
        (e.g. the Sensitive Customer Registry's multi-select, ADR-013).
        Acceptable unpaginated for a modestly-sized, manually-maintained
        equipment registry (CLAUDE.md §21), mirroring this module's own
        `list_facility_sectors`-style "list all" precedent elsewhere in
        this codebase."""
        stmt = select(TransformerTerminal).order_by(TransformerTerminal.transformer_id)
        return list(self.db.execute(stmt).scalars().all())

    def list_transformer_terminals_for_transformers(
        self, transformer_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, list[TransformerTerminal]]:
        """Batch-fetches terminals for several transformers in one query —
        used by list views to avoid one query per row (N+1), mirroring
        `list_terminals_for_circuits`."""
        if not transformer_ids:
            return {}
        stmt = (
            select(TransformerTerminal)
            .where(TransformerTerminal.transformer_id.in_(transformer_ids))
            .order_by(TransformerTerminal.side)
        )
        by_transformer: dict[uuid.UUID, list[TransformerTerminal]] = {}
        for terminal in self.db.execute(stmt).scalars().all():
            by_transformer.setdefault(terminal.transformer_id, []).append(terminal)
        return by_transformer

    def get_transformer_terminal_by_id(
        self, transformer_terminal_id: uuid.UUID
    ) -> TransformerTerminal | None:
        """Single-terminal lookup by its own PK — added for cross-module
        callers (e.g. the Automatic Load Shedding Functionality Registry)
        that reference one `TransformerTerminal` by id, mirroring
        `get_terminal_by_id`'s identical role for `CircuitTerminal`."""
        return self.db.get(TransformerTerminal, transformer_terminal_id)

    def get_transformer_terminal_by_side(
        self, transformer_id: uuid.UUID, side: str
    ) -> TransformerTerminal | None:
        stmt = select(TransformerTerminal).where(
            TransformerTerminal.transformer_id == transformer_id,
            TransformerTerminal.side == side,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def find_transformer_by_yard_pair_and_number(
        self,
        *,
        substation_id: uuid.UUID,
        hv_switchyard_id: uuid.UUID,
        lv_switchyard_id: uuid.UUID,
        transformer_number: str,
        exclude_transformer_id: uuid.UUID | None = None,
    ) -> Transformer | None:
        """Identity check backing `DuplicateTransformerError` (UAT
        correction #2) — uniqueness is `(substation_id, hv_switchyard_id,
        lv_switchyard_id, transformer_number)`, not `(substation_id,
        transformer_number)` alone, since the same transformer number is
        legitimately reused across different transformation pairs at one
        substation (e.g. a "1" on the 275/132kV pair and a separate "1" on
        the 132/33kV pair). Not expressible as a raw single-table `UNIQUE`
        constraint — `hv_switchyard_id`/`lv_switchyard_id` live on two child
        `TransformerTerminal` rows, joined here via `aliased` exactly like
        the module's original, pre-UAT-correction-#1 design. `exclude_transformer_id`
        lets `update_transformer` re-run this check against every *other*
        transformer when a transformer_number changes (the transformer being
        edited must not collide with itself).

        UAT correction #3: excludes `ENTERED_IN_ERROR` transformers —
        deletion/correction policy (Phase 3 follow-up) treats a corrected
        record as "not a real engineering asset," and default list views
        already hide it accordingly. Before this fix, a mistakenly-created
        transformer that was corrected to `ENTERED_IN_ERROR` permanently
        occupied its `(substation, HV yard, LV yard, number)` identity,
        rejecting a legitimate re-creation with the same identity even
        though the corrected record was invisible everywhere else. The
        corrected transformer row itself is never deleted — only excluded
        from this uniqueness check — so it remains reachable by id and
        fully audit-visible."""
        hv_terminal = aliased(TransformerTerminal)
        lv_terminal = aliased(TransformerTerminal)
        stmt = (
            select(Transformer)
            .join(
                hv_terminal,
                (hv_terminal.transformer_id == Transformer.transformer_id)
                & (hv_terminal.side == "HV"),
            )
            .join(
                lv_terminal,
                (lv_terminal.transformer_id == Transformer.transformer_id)
                & (lv_terminal.side == "LV"),
            )
            .where(
                Transformer.substation_id == substation_id,
                Transformer.transformer_number == transformer_number,
                hv_terminal.voltage_yard_id == hv_switchyard_id,
                lv_terminal.voltage_yard_id == lv_switchyard_id,
                Transformer.operational_status_id != _entered_in_error_status_id_subquery(),
            )
        )
        if exclude_transformer_id is not None:
            stmt = stmt.where(Transformer.transformer_id != exclude_transformer_id)
        return self.db.execute(stmt).scalars().first()

    # --- TransformerAuditLog ---------------------------------------------------------
    def add_transformer_audit_log(self, entry: TransformerAuditLog) -> TransformerAuditLog:
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_transformer_audit_log(
        self, transformer_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[TransformerAuditLog], int]:
        total = self.db.execute(
            select(func.count())
            .select_from(TransformerAuditLog)
            .where(TransformerAuditLog.transformer_id == transformer_id)
        ).scalar_one()

        stmt = (
            select(TransformerAuditLog)
            .where(TransformerAuditLog.transformer_id == transformer_id)
            .order_by(TransformerAuditLog.changed_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total
