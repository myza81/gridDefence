"""PSS/E Integration repository layer (CLAUDE.md §14) — pure persistence
access. No business rules, no permission checks, no audit writing live here
— that is `service.py`'s responsibility.

`Substation` (Substation Registry) and `CircuitTerminal`/`Circuit`/
`Transformer` (Equipment Registry) are imported read-only, exactly as
`equipment_registry/repository.py` already imports `Substation` — this is
the established, existing pattern in this codebase for a module's own
repository reading another module's models directly for business-logic
lookups (as opposed to CLAUDE.md F6's narrower "reporting/dashboard join"
carve-out). This module never writes to any of these tables.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.equipment_registry.models import (
    Circuit,
    CircuitTerminal,
    SubstationVoltageYard,
    Transformer,
)
from app.modules.psse_integration.models import (
    EquipmentTopologyMap,
    LoadSnapshot,
    LoadSnapshotBusState,
    LoadSnapshotElementState,
    NetworkGenerator,
    NetworkLoad,
    PsseImportAuditLog,
    RawFileImportBatch,
    TopologyBranch,
    TopologyBus,
    TopologyTransformer,
    TopologyVersion,
)
from app.modules.substation_registry.models import Substation
from app.reference_data.models import OperationalStatus, VoltageLevel


def _entered_in_error_status_id_subquery():
    """Mirrors `equipment_registry.repository`'s own helper of the same
    name — resolves `ENTERED_IN_ERROR`'s id by its stable `code`, never a
    hardcoded numeric id (deletion/correction policy)."""
    return (
        select(OperationalStatus.operational_status_id)
        .where(OperationalStatus.code == "ENTERED_IN_ERROR")
        .scalar_subquery()
    )


class PsseIntegrationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- RawFileImportBatch --------------------------------------------------
    def add_batch(self, batch: RawFileImportBatch) -> RawFileImportBatch:
        self.db.add(batch)
        self.db.flush()
        return batch

    def get_batch_by_id(self, batch_id: uuid.UUID) -> RawFileImportBatch | None:
        return self.db.get(RawFileImportBatch, batch_id)

    def list_batches(
        self, *, offset: int, limit: int, status: str | None = None
    ) -> tuple[list[RawFileImportBatch], int]:
        stmt = select(RawFileImportBatch)
        if status is not None:
            stmt = stmt.where(RawFileImportBatch.status == status)
        total = self.db.execute(
            select(func.count()).select_from(
                stmt.with_only_columns(RawFileImportBatch.batch_id).subquery()
            )
        ).scalar_one()
        stmt = stmt.order_by(RawFileImportBatch.created_at.desc()).offset(offset).limit(limit)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    # --- TopologyVersion -------------------------------------------------------
    def add_topology_version(self, version: TopologyVersion) -> TopologyVersion:
        self.db.add(version)
        self.db.flush()
        return version

    def get_topology_version_by_id(self, topology_version_id: uuid.UUID) -> TopologyVersion | None:
        return self.db.get(TopologyVersion, topology_version_id)

    def find_topology_version_by_signature(self, signature: str) -> TopologyVersion | None:
        stmt = select(TopologyVersion).where(TopologyVersion.signature == signature)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_current_topology_version(self) -> TopologyVersion | None:
        stmt = select(TopologyVersion).where(TopologyVersion.status == "Current")
        return self.db.execute(stmt).scalar_one_or_none()

    def list_topology_versions(
        self, *, offset: int, limit: int
    ) -> tuple[list[TopologyVersion], int]:
        total = self.db.execute(select(func.count()).select_from(TopologyVersion)).scalar_one()
        stmt = (
            select(TopologyVersion)
            .order_by(TopologyVersion.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    # --- TopologyBus/Branch/Transformer ----------------------------------------
    # Batch variants (Phase 4.1 stabilization): a full-topology commit can
    # involve thousands of rows per entity type; `add_all()` + a single
    # `flush()` issues one round trip per *type* instead of one per *row*,
    # while still populating every row's PK in place (the caller reads
    # `.topology_bus_id`/etc. off the same objects immediately afterward).
    def add_topology_buses(self, buses: list[TopologyBus]) -> None:
        self.db.add_all(buses)
        self.db.flush()

    def add_topology_branches(self, branches: list[TopologyBranch]) -> None:
        self.db.add_all(branches)
        self.db.flush()

    def add_topology_transformers(self, transformers: list[TopologyTransformer]) -> None:
        self.db.add_all(transformers)
        self.db.flush()

    def get_topology_bus_by_number(
        self, topology_version_id: uuid.UUID, bus_number: int
    ) -> TopologyBus | None:
        stmt = select(TopologyBus).where(
            TopologyBus.topology_version_id == topology_version_id,
            TopologyBus.bus_number == bus_number,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_topology_buses(self, topology_version_id: uuid.UUID) -> list[TopologyBus]:
        stmt = select(TopologyBus).where(TopologyBus.topology_version_id == topology_version_id)
        return list(self.db.execute(stmt).scalars().all())

    def list_topology_branches(self, topology_version_id: uuid.UUID) -> list[TopologyBranch]:
        stmt = select(TopologyBranch).where(
            TopologyBranch.topology_version_id == topology_version_id
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_topology_transformers(
        self, topology_version_id: uuid.UUID
    ) -> list[TopologyTransformer]:
        stmt = select(TopologyTransformer).where(
            TopologyTransformer.topology_version_id == topology_version_id
        )
        return list(self.db.execute(stmt).scalars().all())

    # --- LoadSnapshot ------------------------------------------------------------
    def add_load_snapshot(self, snapshot: LoadSnapshot) -> LoadSnapshot:
        self.db.add(snapshot)
        self.db.flush()
        return snapshot

    def get_load_snapshot_by_id(self, load_snapshot_id: uuid.UUID) -> LoadSnapshot | None:
        return self.db.get(LoadSnapshot, load_snapshot_id)

    def get_current_load_snapshot(self) -> LoadSnapshot | None:
        stmt = select(LoadSnapshot).where(LoadSnapshot.status == "Current")
        return self.db.execute(stmt).scalar_one_or_none()

    def get_current_load_snapshot_for_topology(
        self, topology_version_id: uuid.UUID
    ) -> LoadSnapshot | None:
        """Phase 7C — the Correlated Operational Model's own default
        "which LoadSnapshot's operational state (in-service/energization)
        should a Bus/Branch/Transformer view read" resolution, scoped to
        one `TopologyVersion` (a Current LoadSnapshot always belongs to
        the Current TopologyVersion, ADR-003, but a caller may ask about a
        historical TopologyVersion, which by definition has none)."""
        stmt = select(LoadSnapshot).where(
            LoadSnapshot.topology_version_id == topology_version_id,
            LoadSnapshot.status == "Current",
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_load_snapshot_as_of(self, as_of: datetime) -> LoadSnapshot | None:
        """Resolves "what was Current as of timestamp T" via each record's
        own `promoted_at`/`superseded_at` window (psse-integration-module.md
        §8.11, Workflow 8) — never by replaying the audit log."""
        stmt = select(LoadSnapshot).where(
            LoadSnapshot.promoted_at.is_not(None),
            LoadSnapshot.promoted_at <= as_of,
            (LoadSnapshot.superseded_at.is_(None)) | (LoadSnapshot.superseded_at > as_of),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_load_snapshots(
        self, *, offset: int, limit: int, topology_version_id: uuid.UUID | None = None
    ) -> tuple[list[LoadSnapshot], int]:
        stmt = select(LoadSnapshot)
        if topology_version_id is not None:
            stmt = stmt.where(LoadSnapshot.topology_version_id == topology_version_id)
        total = self.db.execute(
            select(func.count()).select_from(
                stmt.with_only_columns(LoadSnapshot.load_snapshot_id).subquery()
            )
        ).scalar_one()
        stmt = stmt.order_by(LoadSnapshot.created_at.desc()).offset(offset).limit(limit)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def add_load_snapshot_bus_state(self, state: LoadSnapshotBusState) -> LoadSnapshotBusState:
        self.db.add(state)
        return state

    def add_load_snapshot_element_state(
        self, state: LoadSnapshotElementState
    ) -> LoadSnapshotElementState:
        self.db.add(state)
        return state

    def list_load_snapshot_bus_states(
        self, load_snapshot_id: uuid.UUID
    ) -> list[LoadSnapshotBusState]:
        """Phase 7C — bulk read for the Correlated Operational Model's
        Bus view (one query for every Bus's `in_service` state in this
        snapshot, never one query per Bus)."""
        stmt = select(LoadSnapshotBusState).where(
            LoadSnapshotBusState.load_snapshot_id == load_snapshot_id
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_load_snapshot_element_states(
        self, load_snapshot_id: uuid.UUID
    ) -> list[LoadSnapshotElementState]:
        """Phase 7C — bulk read for the Correlated Operational Model's
        Branch/Transformer views (one query, never one per element)."""
        stmt = select(LoadSnapshotElementState).where(
            LoadSnapshotElementState.load_snapshot_id == load_snapshot_id
        )
        return list(self.db.execute(stmt).scalars().all())

    def add_network_load(self, load: NetworkLoad) -> NetworkLoad:
        self.db.add(load)
        return load

    def add_network_generator(self, generator: NetworkGenerator) -> NetworkGenerator:
        self.db.add(generator)
        return generator

    def list_network_loads(self, load_snapshot_id: uuid.UUID) -> list[NetworkLoad]:
        stmt = select(NetworkLoad).where(NetworkLoad.load_snapshot_id == load_snapshot_id)
        return list(self.db.execute(stmt).scalars().all())

    def list_network_generators(self, load_snapshot_id: uuid.UUID) -> list[NetworkGenerator]:
        stmt = select(NetworkGenerator).where(NetworkGenerator.load_snapshot_id == load_snapshot_id)
        return list(self.db.execute(stmt).scalars().all())

    # --- Substation Registry (read-only, cross-module) --------------------------
    def find_substation_by_mnemonic_ci(self, mnemonic: str) -> Substation | None:
        stmt = select(Substation).where(func.lower(Substation.mnemonic) == mnemonic.lower())
        return self.db.execute(stmt).scalar_one_or_none()

    def list_substations_by_ids(self, substation_ids: list[uuid.UUID]) -> list[Substation]:
        """Phase 7C — bulk read for the Correlated Operational Model
        (mnemonic display for every already-matched Bus in one query, not
        one query per Bus). Empty input returns an empty list without a
        round trip."""
        if not substation_ids:
            return []
        stmt = select(Substation).where(Substation.substation_id.in_(substation_ids))
        return list(self.db.execute(stmt).scalars().all())

    # --- Equipment Registry (read-only, cross-module) ----------------------------
    def list_voltage_yards_by_substation_ids(
        self, substation_ids: list[uuid.UUID]
    ) -> list[SubstationVoltageYard]:
        """Phase 7C — "correlated Switchyard" resolution for the
        Correlated Operational Model's Bus view: bulk-fetches every
        `SubstationVoltageYard` for the given Substations in one query,
        excluding `ENTERED_IN_ERROR` (mirrors `list_active_circuit_terminals`'
        own exclusion). The caller matches a Bus's own `base_kv` against
        `VoltageLevel.nominal_kv` (via `list_voltage_levels`) to pick the
        specific yard."""
        if not substation_ids:
            return []
        stmt = select(SubstationVoltageYard).where(
            SubstationVoltageYard.substation_id.in_(substation_ids),
            SubstationVoltageYard.operational_status_id != _entered_in_error_status_id_subquery(),
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_voltage_levels(self) -> list[VoltageLevel]:
        """Phase 7C — the whole (small) reference table, fetched once per
        request rather than looked up per Bus."""
        return list(self.db.execute(select(VoltageLevel)).scalars().all())

    def list_circuit_terminals_by_ids(
        self, circuit_terminal_ids: list[uuid.UUID]
    ) -> list[CircuitTerminal]:
        """Phase 7C — bulk read for the Correlated Operational Model's
        Branch/Transformer views (one query for every referenced
        `CircuitTerminal`, not one per `EquipmentTopologyMap` entry — see
        `_map_entry_summary`'s own per-entry lookup, which this
        deliberately does not repeat here)."""
        if not circuit_terminal_ids:
            return []
        stmt = select(CircuitTerminal).where(
            CircuitTerminal.circuit_terminal_id.in_(circuit_terminal_ids)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_circuits_by_ids(self, circuit_ids: list[uuid.UUID]) -> list[Circuit]:
        """Phase 7C — bulk read, paired with `list_circuit_terminals_by_ids`."""
        if not circuit_ids:
            return []
        stmt = select(Circuit).where(Circuit.circuit_id.in_(circuit_ids))
        return list(self.db.execute(stmt).scalars().all())

    def list_active_circuit_terminals(self) -> list[CircuitTerminal]:
        """Every `CircuitTerminal` eligible as an `EquipmentTopologyMap`
        matching candidate — excludes `ENTERED_IN_ERROR` terminals and
        terminals whose parent `Circuit` is itself `ENTERED_IN_ERROR`
        (psse-integration-module.md §8a.7, §9 rule 15)."""
        stmt = (
            select(CircuitTerminal)
            .join(Circuit, Circuit.circuit_id == CircuitTerminal.circuit_id)
            .where(
                CircuitTerminal.operational_status_id != _entered_in_error_status_id_subquery(),
                Circuit.operational_status_id != _entered_in_error_status_id_subquery(),
            )
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_circuit_terminal_by_id(self, circuit_terminal_id: uuid.UUID) -> CircuitTerminal | None:
        return self.db.get(CircuitTerminal, circuit_terminal_id)

    def get_circuit_by_id(self, circuit_id: uuid.UUID) -> Circuit | None:
        return self.db.get(Circuit, circuit_id)

    def list_circuit_terminals_for_circuit(self, circuit_id: uuid.UUID) -> list[CircuitTerminal]:
        stmt = select(CircuitTerminal).where(CircuitTerminal.circuit_id == circuit_id)
        return list(self.db.execute(stmt).scalars().all())

    def get_transformer_by_id(self, transformer_id: uuid.UUID) -> Transformer | None:
        return self.db.get(Transformer, transformer_id)

    # --- EquipmentTopologyMap -----------------------------------------------------
    def get_map_entry(
        self, topology_version_id: uuid.UUID, circuit_terminal_id: uuid.UUID
    ) -> EquipmentTopologyMap | None:
        stmt = select(EquipmentTopologyMap).where(
            EquipmentTopologyMap.topology_version_id == topology_version_id,
            EquipmentTopologyMap.circuit_terminal_id == circuit_terminal_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_map_entry_by_id(self, map_id: uuid.UUID) -> EquipmentTopologyMap | None:
        return self.db.get(EquipmentTopologyMap, map_id)

    def add_map_entry(self, entry: EquipmentTopologyMap) -> EquipmentTopologyMap:
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_map_entries(
        self,
        *,
        topology_version_id: uuid.UUID,
        offset: int,
        limit: int,
        match_outcome: str | None = None,
    ) -> tuple[list[EquipmentTopologyMap], int]:
        stmt = select(EquipmentTopologyMap).where(
            EquipmentTopologyMap.topology_version_id == topology_version_id
        )
        if match_outcome is not None:
            stmt = stmt.where(EquipmentTopologyMap.match_outcome == match_outcome)
        total = self.db.execute(
            select(func.count()).select_from(
                stmt.with_only_columns(EquipmentTopologyMap.map_id).subquery()
            )
        ).scalar_one()
        stmt = stmt.order_by(EquipmentTopologyMap.created_at.desc()).offset(offset).limit(limit)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    def list_all_map_entries(self, topology_version_id: uuid.UUID) -> list[EquipmentTopologyMap]:
        """Phase 7C — every `EquipmentTopologyMap` entry for one
        `TopologyVersion`, unpaginated (mirrors `list_topology_buses`'s own
        "list all for this topology version" shape) — the Correlated
        Operational Model's Branch/Transformer views need the whole set at
        once, to group by `topology_branch_id`/`topology_transformer_id`
        in a single pass rather than one query per element."""
        stmt = select(EquipmentTopologyMap).where(
            EquipmentTopologyMap.topology_version_id == topology_version_id
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_map_entries_for_circuit(
        self, topology_version_id: uuid.UUID, circuit_id: uuid.UUID
    ) -> list[EquipmentTopologyMap]:
        """Union-of-terminals resolution (ADR-007 §6, §10) — every map entry
        for this `Circuit`'s own `CircuitTerminal`s within one
        `TopologyVersion`."""
        stmt = (
            select(EquipmentTopologyMap)
            .join(
                CircuitTerminal,
                CircuitTerminal.circuit_terminal_id == EquipmentTopologyMap.circuit_terminal_id,
            )
            .where(
                EquipmentTopologyMap.topology_version_id == topology_version_id,
                CircuitTerminal.circuit_id == circuit_id,
            )
        )
        return list(self.db.execute(stmt).scalars().all())

    # --- PsseImportAuditLog -------------------------------------------------------
    def add_audit_log(self, entry: PsseImportAuditLog) -> PsseImportAuditLog:
        self.db.add(entry)
        return entry

    def list_audit_log(
        self, entity_type: str, entity_id: str, *, offset: int, limit: int
    ) -> tuple[list[PsseImportAuditLog], int]:
        stmt = select(PsseImportAuditLog).where(
            PsseImportAuditLog.entity_type == entity_type,
            PsseImportAuditLog.entity_id == entity_id,
        )
        total = self.db.execute(
            select(func.count()).select_from(
                stmt.with_only_columns(PsseImportAuditLog.log_id).subquery()
            )
        ).scalar_one()
        stmt = stmt.order_by(PsseImportAuditLog.changed_at.desc()).offset(offset).limit(limit)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total
