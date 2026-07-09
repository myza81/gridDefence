"""Network Model repository layer (CLAUDE.md §14) — pure, read-only
persistence access. No business rules, no permission checks live here —
that is `service.py`'s responsibility.

Per this phase's explicit architecture ("The Network Model should
reference existing entities wherever practical. Do not duplicate registry
information."), this module owns **no tables of its own**. Every query
here reads Equipment Registry's, Substation Registry's, and (Phase 7E)
PSS/E Integration's models directly — read-only, never written to —
mirroring the exact cross-module read-only-model-import pattern already
established by `psse_integration/repository.py` for the same kind of
composition.

**Phase 7E — Operational Snapshot traversal migration:** the traversal
graph (`NetworkModelService.traverse`) now reads `TopologyBus`/
`TopologyBranch`/`TopologyTransformer`/`LoadSnapshotElementState`/
`EquipmentTopologyMap` from `psse_integration`'s own tables, exactly as
this module already reads Equipment Registry's tables — the same
established pattern, extended to a second module. The "Engineering
queries" section below (`SubstationConnectivity`/`SubstationEquipment`/
`ElectricalNeighbour`/`NetworkOverview`) is unaffected — those remain
sourced from Equipment/Substation Registry, since they describe
*registered equipment identity* (breaker numbers, bay numbers, circuit
names) that only exists there, not in the Operational Snapshot.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.equipment_registry.models import (
    Circuit,
    CircuitTerminal,
    SubstationVoltageYard,
    Transformer,
    TransformerTerminal,
)
from app.modules.psse_integration.models import (
    EquipmentTopologyMap,
    LoadSnapshot,
    LoadSnapshotElementState,
    TopologyBranch,
    TopologyBus,
    TopologyTransformer,
    TopologyVersion,
)
from app.modules.substation_registry.models import Substation
from app.reference_data.models import OperationalStatus


def _entered_in_error_status_id_subquery():
    """Mirrors `equipment_registry.repository`'s and `psse_integration
    .repository`'s own helper of the same name — resolves
    `ENTERED_IN_ERROR`'s id by its stable `code`, never a hardcoded numeric
    id."""
    return (
        select(OperationalStatus.operational_status_id)
        .where(OperationalStatus.code == "ENTERED_IN_ERROR")
        .scalar_subquery()
    )


class NetworkModelRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Substation Registry (read-only, cross-module) ---------------------------
    def get_substation_by_id(self, substation_id: uuid.UUID) -> Substation | None:
        return self.db.get(Substation, substation_id)

    def count_substations(self) -> int:
        return self.db.execute(select(func.count()).select_from(Substation)).scalar_one()

    # --- Equipment Registry (read-only, cross-module) -----------------------------
    def get_circuit_by_id(self, circuit_id: uuid.UUID) -> Circuit | None:
        return self.db.get(Circuit, circuit_id)

    def list_active_circuit_terminals_for_substation(
        self, substation_id: uuid.UUID
    ) -> list[CircuitTerminal]:
        """Every non-`ENTERED_IN_ERROR` `CircuitTerminal` whose voltage yard
        belongs to this substation, excluding terminals whose parent
        `Circuit` is itself `ENTERED_IN_ERROR` — mirrors the exact
        exclusion pattern already established in
        `psse_integration.repository.list_active_circuit_terminals`."""
        stmt = (
            select(CircuitTerminal)
            .join(
                SubstationVoltageYard,
                SubstationVoltageYard.voltage_yard_id == CircuitTerminal.voltage_yard_id,
            )
            .join(Circuit, Circuit.circuit_id == CircuitTerminal.circuit_id)
            .where(
                SubstationVoltageYard.substation_id == substation_id,
                CircuitTerminal.operational_status_id != _entered_in_error_status_id_subquery(),
                Circuit.operational_status_id != _entered_in_error_status_id_subquery(),
            )
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_active_terminals_for_circuit(self, circuit_id: uuid.UUID) -> list[CircuitTerminal]:
        """Every non-`ENTERED_IN_ERROR` terminal of one circuit — two for an
        ordinary line, three or more for a tee-off (equipment-registry-
        module.md §7.5). Never assumes exactly two."""
        stmt = select(CircuitTerminal).where(
            CircuitTerminal.circuit_id == circuit_id,
            CircuitTerminal.operational_status_id != _entered_in_error_status_id_subquery(),
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_voltage_yard(self, voltage_yard_id: uuid.UUID) -> SubstationVoltageYard | None:
        return self.db.get(SubstationVoltageYard, voltage_yard_id)

    def get_substation_id_for_voltage_yard(self, voltage_yard_id: uuid.UUID) -> uuid.UUID | None:
        yard = self.get_voltage_yard(voltage_yard_id)
        return yard.substation_id if yard is not None else None

    def list_active_transformers_for_substation(
        self, substation_id: uuid.UUID
    ) -> list[Transformer]:
        stmt = select(Transformer).where(
            Transformer.substation_id == substation_id,
            Transformer.operational_status_id != _entered_in_error_status_id_subquery(),
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_terminals_for_transformer(
        self, transformer_id: uuid.UUID
    ) -> list[TransformerTerminal]:
        stmt = select(TransformerTerminal).where(
            TransformerTerminal.transformer_id == transformer_id
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_active_circuits(self) -> int:
        stmt = (
            select(func.count())
            .select_from(Circuit)
            .where(Circuit.operational_status_id != _entered_in_error_status_id_subquery())
        )
        return self.db.execute(stmt).scalar_one()

    def count_active_transformers(self) -> int:
        stmt = (
            select(func.count())
            .select_from(Transformer)
            .where(Transformer.operational_status_id != _entered_in_error_status_id_subquery())
        )
        return self.db.execute(stmt).scalar_one()

    def list_active_circuit_ids(self) -> list[uuid.UUID]:
        stmt = select(Circuit.circuit_id).where(
            Circuit.operational_status_id != _entered_in_error_status_id_subquery()
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_all_active_terminals(self) -> list[CircuitTerminal]:
        """Every non-`ENTERED_IN_ERROR` terminal in the whole registry,
        whose parent `Circuit` is also not `ENTERED_IN_ERROR` — the full
        edge list `NetworkModelService`'s traversal algorithm builds its
        adjacency map from. Loaded once per traversal call; the registry is
        not large enough at any currently anticipated scale to warrant a
        more elaborate incremental-loading strategy (CLAUDE.md §21 —
        avoid premature optimisation)."""
        stmt = (
            select(CircuitTerminal)
            .join(Circuit, Circuit.circuit_id == CircuitTerminal.circuit_id)
            .where(
                CircuitTerminal.operational_status_id != _entered_in_error_status_id_subquery(),
                Circuit.operational_status_id != _entered_in_error_status_id_subquery(),
            )
        )
        return list(self.db.execute(stmt).scalars().all())

    # --- PSS/E Integration / Operational Snapshot (read-only, cross-module,
    # Phase 7E) --------------------------------------------------------------------
    def get_current_topology_version(self) -> TopologyVersion | None:
        stmt = select(TopologyVersion).where(TopologyVersion.status == "Current")
        return self.db.execute(stmt).scalar_one_or_none()

    def get_topology_version_by_id(self, topology_version_id: uuid.UUID) -> TopologyVersion | None:
        return self.db.get(TopologyVersion, topology_version_id)

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

    def get_current_load_snapshot_for_topology(
        self, topology_version_id: uuid.UUID
    ) -> LoadSnapshot | None:
        """Mirrors `psse_integration.repository`'s own method of the same
        name — the traversal engine's "respect Operational Snapshot
        in-service state" requirement (Branch Traversal) needs whichever
        `LoadSnapshot` is Current for the topology being traversed, never
        an arbitrary or historical one."""
        stmt = select(LoadSnapshot).where(
            LoadSnapshot.topology_version_id == topology_version_id,
            LoadSnapshot.status == "Current",
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_load_snapshot_element_states(
        self, load_snapshot_id: uuid.UUID
    ) -> list[LoadSnapshotElementState]:
        stmt = select(LoadSnapshotElementState).where(
            LoadSnapshotElementState.load_snapshot_id == load_snapshot_id
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_substations_by_ids(self, substation_ids: list[uuid.UUID]) -> list[Substation]:
        """Bulk read for the traversal result's substation-level output
        (mnemonic display for every reached substation in one query, not
        one query per substation)."""
        if not substation_ids:
            return []
        stmt = select(Substation).where(Substation.substation_id.in_(substation_ids))
        return list(self.db.execute(stmt).scalars().all())

    def list_circuit_terminals_for_circuits(
        self, circuit_ids: list[uuid.UUID]
    ) -> list[CircuitTerminal]:
        """`excluded_circuit_ids` (a Line Connectivity Registry concept)
        needs each excluded Circuit's own terminals to translate the
        exclusion into Operational Snapshot edges, via
        `EquipmentTopologyMap` correlation — see
        `NetworkModelService._resolve_excluded_operational_edges`."""
        if not circuit_ids:
            return []
        stmt = select(CircuitTerminal).where(CircuitTerminal.circuit_id.in_(circuit_ids))
        return list(self.db.execute(stmt).scalars().all())

    def list_map_entries_for_topology_version(
        self, topology_version_id: uuid.UUID
    ) -> list[EquipmentTopologyMap]:
        stmt = select(EquipmentTopologyMap).where(
            EquipmentTopologyMap.topology_version_id == topology_version_id
        )
        return list(self.db.execute(stmt).scalars().all())
