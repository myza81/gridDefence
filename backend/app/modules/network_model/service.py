"""Network Model service layer (CLAUDE.md §14) — orchestration and the
traversal algorithm. All business rules for this module live here; the
repository is a pure persistence-access layer and the router is a pure
HTTP boundary.

Incomplete-registry tolerance (explicit architecture requirement for this
phase): the transmission network is registered incrementally, substation
by substation, circuit by circuit. This service must never assume the
registry is complete.

- A substation that has not been registered yet is "not found" for a
  request that names it explicitly (a genuine 404), but its *absence*
  from someone else's connectivity or traversal result is simply treated
  as "not yet known" — it never raises, and it never appears in output.
- A registered substation with no circuits or transformers yet entered is
  a completely valid state: it simply has empty connectivity/equipment
  lists, not an error.
- Any reference this service resolves (a terminal's substation, a
  transformer's HV/LV voltage level) that cannot currently be resolved is
  treated as *unknown*, not *invalid* — the affected item is omitted from
  the returned relationship rather than raising. Referential integrity at
  the database level (NOT NULL + FK RESTRICT) means this should not
  normally occur for terminals that do exist, but the service does not
  assume it: the network this module describes grows as engineering data
  is added, and every read must degrade gracefully rather than fail
  outright.
"""

from __future__ import annotations

import uuid
from collections import deque

from sqlalchemy.orm import Session

from app.modules.network_model.exceptions import (
    CircuitTerminalNotFoundError,
    NoCurrentTopologyVersionError,
    SubstationNotFoundError,
    TopologyVersionNotFoundError,
    VoltageYardNotFoundError,
    VoltageYardSubstationMismatchError,
)
from app.modules.network_model.repository import NetworkModelRepository
from app.modules.network_model.schemas import (
    BoundaryPocketEvaluation,
    BoundaryPocketEvaluationRequest,
    BusProjectionEntry,
    ConnectingLine,
    CorrelationCounts,
    CorrelationSummary,
    ElectricalNeighbour,
    IslandSubstation,
    IsolatedIsland,
    LineBay,
    NeighbourSubstation,
    NetworkOverview,
    OperationalProjections,
    PathBus,
    PathStep,
    PathVerificationRequest,
    ReachableSubstation,
    SnapshotSummary,
    SubstationConnectivity,
    SubstationEquipment,
    SwitchyardProjectionEntry,
    TerminalOnCircuit,
    TransformerBay,
    TraversalRequest,
    TraversalResult,
    TraversalStatistics,
    TraversalVerificationResult,
)
from app.modules.psse_integration.correlated_operational_model import CorrelationStatus
from app.modules.psse_integration.models import TopologyBranch, TopologyBus, TopologyTransformer
from app.modules.psse_integration.service import PsseIntegrationService
from app.reference_data.repository import ReferenceDataRepository

# Same TNB engineering short-name convention as
# `equipment_registry.service._TRANSFORMER_SHORT_NAME_PREFIX_BY_NOMINAL_KV`,
# replicated rather than imported: it is that module's private,
# service-internal presentational logic, not a shared utility (mirrors how
# this whole module replicates `_compute_circuit_name` for the same reason).
_TRANSFORMER_SHORT_NAME_PREFIX_BY_NOMINAL_KV: dict[int, str] = {
    500: "XGT",
    275: "SGT",
    230: "SGT",
    132: "T",
    33: "T",
    22: "T",
    11: "T",
}

# ADR-019 §"Main Grid identification" — a single unconnected/uncorrelated
# Substation (or Bus) sitting in its own trivial baseline component is
# ordinary registry noise (an unmigrated substation, a not-yet-imported
# spur, a Fictitious/Blank-named Bus), not an abnormal grid-split
# condition. A baseline component reaching this many correlated
# Substations, besides the Main Grid itself, is treated as a genuine,
# worth-flagging pre-existing multi-component condition
# (`baseline_has_single_main_grid`).
_MEANINGFUL_COMPONENT_MIN_SUBSTATIONS = 2


class NetworkModelService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = NetworkModelRepository(db)
        self.reference_data = ReferenceDataRepository(db)
        # Phase 7F — Operational Snapshot Verification Workspace calls
        # PSS/E Integration's own service layer (CLAUDE.md A1: modules
        # communicate through in-process service interfaces) for the
        # Correlated Operational Model view-building it already owns
        # (`OperationalBusView`/`OperationalBranchView`/
        # `OperationalTransformerView`, "correlated Switchyard" resolution,
        # current-status summary) — never a second implementation of that
        # correlation logic inside this module.
        self.psse_service = PsseIntegrationService(db)

    # --- Presentational helpers (replicated from equipment_registry.service) -----

    @staticmethod
    def _compute_circuit_name(mnemonics: list[str]) -> str:
        """Identical formula to
        `equipment_registry.service.EquipmentRegistryService._compute_circuit_name`
        — sorted, case-insensitive, en-dash-joined terminal mnemonics.
        Deliberately excludes any terminal whose substation could not be
        resolved (incomplete-data tolerance): a circuit with an
        unresolvable terminal still gets a name from whatever terminals
        *are* resolvable, rather than failing to compute a name at all."""
        return "–".join(sorted(mnemonics, key=str.casefold))

    @staticmethod
    def _compute_transformer_short_name(nominal_kv: float | None, transformer_number: str) -> str:
        """Identical formula to
        `equipment_registry.service.EquipmentRegistryService._compute_transformer_short_name`,
        taking the HV side's nominal voltage directly rather than a
        voltage-level id (the caller has already resolved it, or found it
        unresolvable, one layer up)."""
        prefix = (
            _TRANSFORMER_SHORT_NAME_PREFIX_BY_NOMINAL_KV.get(int(nominal_kv))
            if nominal_kv is not None
            else None
        ) or "T"
        return f"{prefix}{transformer_number}"

    # --- Engineering queries -------------------------------------------------------

    def get_substation_connectivity(self, substation_id: uuid.UUID) -> SubstationConnectivity:
        substation = self.repo.get_substation_by_id(substation_id)
        if substation is None:
            raise SubstationNotFoundError(substation_id)

        own_terminals = self.repo.list_active_circuit_terminals_for_substation(substation_id)

        seen_circuit_ids: set[uuid.UUID] = set()
        connected_lines: list[ConnectingLine] = []
        neighbours: list[NeighbourSubstation] = []

        for own_terminal in own_terminals:
            if own_terminal.circuit_id in seen_circuit_ids:
                continue
            seen_circuit_ids.add(own_terminal.circuit_id)

            circuit = self.repo.get_circuit_by_id(own_terminal.circuit_id)
            if circuit is None:
                # Referentially impossible under FK RESTRICT, but a missing
                # parent is "unknown", not a reason to fail the whole
                # connectivity query for every other line.
                continue

            all_terminals = self.repo.list_active_terminals_for_circuit(own_terminal.circuit_id)
            resolved = [
                (terminal, self.repo.get_substation_by_id(sub_id) if sub_id is not None else None)
                for terminal, sub_id in (
                    (t, self.repo.get_substation_id_for_voltage_yard(t.voltage_yard_id))
                    for t in all_terminals
                )
            ]

            known_mnemonics = [sub.mnemonic for _, sub in resolved if sub is not None]
            circuit_name = self._compute_circuit_name(known_mnemonics)

            terminal_dtos = [
                TerminalOnCircuit(
                    circuit_terminal_id=terminal.circuit_terminal_id,
                    substation_id=sub.substation_id,
                    substation_mnemonic=sub.mnemonic,
                    voltage_yard_id=terminal.voltage_yard_id,
                    breaker_number=terminal.breaker_number,
                )
                for terminal, sub in resolved
                if sub is not None
            ]

            voltage_level = self.reference_data.get_voltage_level(circuit.voltage_level_id)
            line_type = self.reference_data.get_line_type(circuit.line_type_id)
            status = self.reference_data.get_operational_status(circuit.operational_status_id)

            connected_lines.append(
                ConnectingLine(
                    circuit_id=circuit.circuit_id,
                    bay_number=circuit.bay_number,
                    circuit_name=circuit_name,
                    voltage_level_label=voltage_level.label if voltage_level is not None else "",
                    line_type_label=line_type.label if line_type is not None else "",
                    operational_status_code=status.code if status is not None else "",
                    # is_tee_off counts every terminal actually on the circuit
                    # (all_terminals), not just the ones whose substation
                    # happened to resolve — a tee-off with one
                    # not-yet-resolvable leg is still a tee-off.
                    is_tee_off=len(all_terminals) > 2,
                    terminals=terminal_dtos,
                )
            )

            for _terminal, sub in resolved:
                if sub is not None and sub.substation_id != substation_id:
                    neighbours.append(
                        NeighbourSubstation(
                            substation_id=sub.substation_id,
                            substation_mnemonic=sub.mnemonic,
                            substation_official_name=sub.official_name,
                            via_circuit_id=circuit.circuit_id,
                            via_circuit_name=circuit_name,
                            via_bay_number=circuit.bay_number,
                        )
                    )

        return SubstationConnectivity(
            substation_id=substation.substation_id,
            substation_mnemonic=substation.mnemonic,
            substation_official_name=substation.official_name,
            connected_lines=connected_lines,
            neighbours=neighbours,
        )

    def list_substation_neighbours(self, substation_id: uuid.UUID) -> list[ElectricalNeighbour]:
        """De-duplicated view of `get_substation_connectivity`'s
        per-line `neighbours` list — one entry per distinct neighbouring
        substation, however many parallel lines connect to it."""
        connectivity = self.get_substation_connectivity(substation_id)

        counts: dict[uuid.UUID, int] = {}
        details: dict[uuid.UUID, NeighbourSubstation] = {}
        for neighbour in connectivity.neighbours:
            counts[neighbour.substation_id] = counts.get(neighbour.substation_id, 0) + 1
            details[neighbour.substation_id] = neighbour

        result = [
            ElectricalNeighbour(
                substation_id=sub_id,
                substation_mnemonic=details[sub_id].substation_mnemonic,
                substation_official_name=details[sub_id].substation_official_name,
                connecting_line_count=count,
            )
            for sub_id, count in counts.items()
        ]
        result.sort(key=lambda neighbour: neighbour.substation_mnemonic.casefold())
        return result

    def get_substation_equipment(self, substation_id: uuid.UUID) -> SubstationEquipment:
        substation = self.repo.get_substation_by_id(substation_id)
        if substation is None:
            raise SubstationNotFoundError(substation_id)

        transformer_bays: list[TransformerBay] = []
        for transformer in self.repo.list_active_transformers_for_substation(substation_id):
            terminals = self.repo.list_terminals_for_transformer(transformer.transformer_id)
            hv_terminal = next((t for t in terminals if t.side == "HV"), None)
            lv_terminal = next((t for t in terminals if t.side == "LV"), None)

            hv_yard = (
                self.repo.get_voltage_yard(hv_terminal.voltage_yard_id)
                if hv_terminal is not None
                else None
            )
            lv_yard = (
                self.repo.get_voltage_yard(lv_terminal.voltage_yard_id)
                if lv_terminal is not None
                else None
            )
            hv_level = (
                self.reference_data.get_voltage_level(hv_yard.voltage_level_id)
                if hv_yard is not None
                else None
            )
            lv_level = (
                self.reference_data.get_voltage_level(lv_yard.voltage_level_id)
                if lv_yard is not None
                else None
            )
            status = self.reference_data.get_operational_status(transformer.operational_status_id)

            transformer_bays.append(
                TransformerBay(
                    transformer_id=transformer.transformer_id,
                    transformer_number=transformer.transformer_number,
                    generated_short_name=self._compute_transformer_short_name(
                        hv_level.nominal_kv if hv_level is not None else None,
                        transformer.transformer_number,
                    ),
                    hv_voltage_level_label=hv_level.label if hv_level is not None else "",
                    lv_voltage_level_label=lv_level.label if lv_level is not None else "",
                    capacity_mva=(
                        float(transformer.capacity_mva)
                        if transformer.capacity_mva is not None
                        else None
                    ),
                    operational_status_code=status.code if status is not None else "",
                )
            )

        line_bays: list[LineBay] = []
        for own_terminal in self.repo.list_active_circuit_terminals_for_substation(substation_id):
            circuit = self.repo.get_circuit_by_id(own_terminal.circuit_id)
            if circuit is None:
                continue

            all_terminals = self.repo.list_active_terminals_for_circuit(own_terminal.circuit_id)
            known_mnemonics = [
                sub.mnemonic
                for sub in (
                    self.repo.get_substation_by_id(sub_id) if sub_id is not None else None
                    for sub_id in (
                        self.repo.get_substation_id_for_voltage_yard(t.voltage_yard_id)
                        for t in all_terminals
                    )
                )
                if sub is not None
            ]
            circuit_name = self._compute_circuit_name(known_mnemonics)
            voltage_level = self.reference_data.get_voltage_level(circuit.voltage_level_id)
            status = self.reference_data.get_operational_status(circuit.operational_status_id)

            line_bays.append(
                LineBay(
                    circuit_terminal_id=own_terminal.circuit_terminal_id,
                    circuit_id=circuit.circuit_id,
                    circuit_bay_number=circuit.bay_number,
                    circuit_name=circuit_name,
                    breaker_number=own_terminal.breaker_number,
                    voltage_level_label=voltage_level.label if voltage_level is not None else "",
                    operational_status_code=status.code if status is not None else "",
                )
            )

        return SubstationEquipment(
            substation_id=substation.substation_id,
            substation_mnemonic=substation.mnemonic,
            substation_official_name=substation.official_name,
            transformer_bays=transformer_bays,
            line_bays=line_bays,
        )

    def get_overview(self) -> NetworkOverview:
        """A summary of whatever has been registered so far — zero rows in
        an empty or freshly-seeded registry is a valid answer, not an
        error state."""
        tee_off_count = 0
        for circuit_id in self.repo.list_active_circuit_ids():
            if len(self.repo.list_active_terminals_for_circuit(circuit_id)) > 2:
                tee_off_count += 1

        return NetworkOverview(
            substation_count=self.repo.count_substations(),
            circuit_count=self.repo.count_active_circuits(),
            tee_off_circuit_count=tee_off_count,
            transformer_count=self.repo.count_active_transformers(),
        )

    # --- Traversal (Phase 7E — Operational Snapshot traversal migration) -------
    #
    # The graph itself is now built exclusively from `TopologyBus`/
    # `TopologyBranch`/`TopologyTransformer` (Operational Snapshot,
    # ADR-003) — never from Line Connectivity Registry. This answers
    # "how is the operational network connected," which only the
    # Operational Snapshot can answer (operational-snapshot-architecture.md,
    # operational-correlation-architecture.md). The *public* traversal API
    # (`TraversalRequest`/`TraversalResult`, substation-in/substation-out)
    # is unchanged from before this migration — existing consumers (e.g.
    # the frontend's Network Traversal page) do not need to know the graph
    # now originates from PSS/E Integration's tables rather than Equipment
    # Registry's. Bus Number (never Substation) is the traversal node
    # identity internally; Substation is resolved only at the edges (start
    # and result), via the Bus's own `substation_id` correlation — optional
    # enrichment the traversal's own reachability computation never
    # depends on (a bus with no correlated Substation still participates
    # fully in the graph; it is simply invisible at the substation-shaped
    # *output* layer, exactly as EDR-007 requires for Fictitious Buses).

    def _resolve_topology_version(
        self, requested_topology_version_id: uuid.UUID | None
    ) -> uuid.UUID:
        """Snapshot Awareness: an explicit `topology_version_id` is used
        verbatim (404 if it does not exist); omitted means the Current
        `TopologyVersion` (400 if none exists yet). Never silently mixes
        snapshots — exactly one `TopologyVersion` is resolved, once, per
        traversal call."""
        if requested_topology_version_id is not None:
            version = self.repo.get_topology_version_by_id(requested_topology_version_id)
            if version is None:
                raise TopologyVersionNotFoundError(requested_topology_version_id)
            return version.topology_version_id

        current = self.repo.get_current_topology_version()
        if current is None:
            raise NoCurrentTopologyVersionError()
        return current.topology_version_id

    def _in_service_element_ids(
        self, topology_version_id: uuid.UUID
    ) -> tuple[dict[int, bool], dict[int, bool]]:
        """Branch Traversal / Transformer Traversal requirement: "Branch
        status shall continue to respect Operational Snapshot state."
        Reads the topology's own Current `LoadSnapshot`'s per-element
        in-service state, if one exists. An element with no recorded state
        (or no LoadSnapshot at all yet) defaults to in-service — the same
        graceful, "unknown is not the same as false" tolerance this
        module's docstring already establishes for incomplete data,
        applied here to Operational Snapshot state instead of registry
        completeness."""
        snapshot = self.repo.get_current_load_snapshot_for_topology(topology_version_id)
        if snapshot is None:
            return {}, {}
        branch_in_service: dict[int, bool] = {}
        transformer_in_service: dict[int, bool] = {}
        for state in self.repo.list_load_snapshot_element_states(snapshot.load_snapshot_id):
            if state.topology_branch_id is not None:
                branch_in_service[state.topology_branch_id] = state.in_service
            elif state.topology_transformer_id is not None:
                transformer_in_service[state.topology_transformer_id] = state.in_service
        return branch_in_service, transformer_in_service

    def _resolve_excluded_operational_edges(
        self, excluded_circuit_ids: set[uuid.UUID], topology_version_id: uuid.UUID
    ) -> tuple[set[int], set[int]]:
        """Translates the registry-facing `excluded_circuit_ids`
        convenience parameter into the Operational Branch/Transformer
        elements those Circuits currently correlate to, via
        `EquipmentTopologyMap`, for the `TopologyVersion` being traversed.
        Operational Correlation is optional enrichment only (operational-
        correlation-architecture.md §5) — a Circuit with no correlation
        for this snapshot (never imported against it, or the correlation
        is itself ambiguous/unmatched) simply excludes nothing; this never
        raises and never blocks the underlying reachability computation."""
        if not excluded_circuit_ids:
            return set(), set()

        terminals = self.repo.list_circuit_terminals_for_circuits(list(excluded_circuit_ids))
        excluded_terminal_ids = {t.circuit_terminal_id for t in terminals}
        if not excluded_terminal_ids:
            return set(), set()

        excluded_branch_ids: set[int] = set()
        excluded_transformer_ids: set[int] = set()
        for entry in self.repo.list_map_entries_for_topology_version(topology_version_id):
            if entry.circuit_terminal_id not in excluded_terminal_ids:
                continue
            if entry.topology_branch_id is not None:
                excluded_branch_ids.add(entry.topology_branch_id)
            if entry.topology_transformer_id is not None:
                excluded_transformer_ids.add(entry.topology_transformer_id)
        return excluded_branch_ids, excluded_transformer_ids

    def _resolve_excluded_operational_edges_by_terminals(
        self, circuit_terminal_ids: set[uuid.UUID], topology_version_id: uuid.UUID
    ) -> tuple[set[int], set[int]]:
        """Circuit Terminal opening-point translation (Foundation
        Hardening Sprint A; boundary-pocket-architecture.md §6) — the
        direct, per-terminal analogue of
        `_resolve_excluded_operational_edges`, which only ever resolves a
        *whole* Circuit's terminals. Boundary Pocket construction opens
        specific Circuit Terminals — engineering switching points — not
        necessarily every terminal on their Circuit: on a tee-off Circuit,
        opening only one leg must exclude only that leg's own correlated
        element, never the other legs' (network-model-module.md §9 rule
        11's own tee-off subset gap; boundary-pocket-architecture.md §6).
        `EquipmentTopologyMap` is already keyed one row per
        `(topology_version_id, circuit_terminal_id)`, so no new
        correlation mechanism was required — only a query scoped to the
        individual terminals supplied, rather than every terminal of their
        shared Circuit. An uncorrelated terminal excludes nothing,
        gracefully, mirroring every other correlation-optional tolerance
        this module already establishes."""
        if not circuit_terminal_ids:
            return set(), set()

        excluded_branch_ids: set[int] = set()
        excluded_transformer_ids: set[int] = set()
        for entry in self.repo.list_map_entries_for_terminals(
            list(circuit_terminal_ids), topology_version_id
        ):
            if entry.topology_branch_id is not None:
                excluded_branch_ids.add(entry.topology_branch_id)
            if entry.topology_transformer_id is not None:
                excluded_transformer_ids.add(entry.topology_transformer_id)
        return excluded_branch_ids, excluded_transformer_ids

    def _validate_circuit_terminals_exist(self, circuit_terminal_ids: list[uuid.UUID]) -> None:
        """Foundation Hardening Sprint A — a caller-supplied opening point
        must name a real `CircuitTerminal`. This is a genuine request
        error (`CircuitTerminalNotFoundError`), distinct from the
        "uncorrelated terminal excludes nothing" tolerance a terminal that
        exists but has no `EquipmentTopologyMap` entry for this snapshot
        receives — that terminal is real, just not yet correlated;
        a terminal id that does not exist at all can never be a real
        engineering opening point and is rejected outright."""
        if not circuit_terminal_ids:
            return
        found_ids = {
            t.circuit_terminal_id
            for t in self.repo.list_circuit_terminals_by_ids(circuit_terminal_ids)
        }
        for circuit_terminal_id in circuit_terminal_ids:
            if circuit_terminal_id not in found_ids:
                raise CircuitTerminalNotFoundError(circuit_terminal_id)

    def _resolve_boundary_exclusions(
        self, circuit_terminal_ids: list[uuid.UUID], topology_version_id: uuid.UUID
    ) -> tuple[set[int], set[int], list[uuid.UUID]]:
        """ADR-019 — resolves the selected opening points to their
        correlated Operational Branch/Transformer elements (per-terminal,
        via `EquipmentTopologyMap` — Foundation Hardening Sprint A's own
        correlation mechanism, unmodified), and additionally reports
        which selected terminals produced no correlation at all. This is
        evidence surfaced to the engineer (`uncorrelated_circuit_terminal_ids`),
        never a silent gap and never a request error — a terminal that
        exists but is not yet correlated for this snapshot is a valid,
        tolerated input (`CircuitTerminalNotFoundError`, raised by
        `_validate_circuit_terminals_exist` separately, is reserved for a
        terminal that does not exist at all)."""
        if not circuit_terminal_ids:
            return set(), set(), []

        correlated_terminal_ids: set[uuid.UUID] = set()
        excluded_branch_ids: set[int] = set()
        excluded_transformer_ids: set[int] = set()
        for entry in self.repo.list_map_entries_for_terminals(
            list(set(circuit_terminal_ids)), topology_version_id
        ):
            if entry.topology_branch_id is None and entry.topology_transformer_id is None:
                continue
            correlated_terminal_ids.add(entry.circuit_terminal_id)
            if entry.topology_branch_id is not None:
                excluded_branch_ids.add(entry.topology_branch_id)
            if entry.topology_transformer_id is not None:
                excluded_transformer_ids.add(entry.topology_transformer_id)

        uncorrelated = [
            terminal_id
            for terminal_id in circuit_terminal_ids
            if terminal_id not in correlated_terminal_ids
        ]
        return excluded_branch_ids, excluded_transformer_ids, uncorrelated

    @staticmethod
    def _compute_bus_components(
        buses: list[TopologyBus], adjacency: dict[int, set[int]]
    ) -> list[set[int]]:
        """ADR-019 — partitions every Bus Number in `buses` into its
        connected component via BFS: whole-graph component discovery,
        not two independently-seeded reachability traversals (the
        ADR-017 mechanism this supersedes). A Bus with no in-service,
        non-excluded edge at all is still its own single-Bus component,
        never omitted — every Bus in `buses` appears in exactly one
        returned component, satisfying EDR-007's "never skip a Bus"
        tolerance exactly as `_build_bus_adjacency_map` already does.
        Components are returned in a fully deterministic order — sorted
        by descending size, then by ascending minimum Bus Number — the
        same ordering `evaluate_boundary` relies on to identify the Main
        Grid deterministically (see `_identify_main_grid`)."""
        all_bus_numbers = {bus.bus_number for bus in buses}
        visited: set[int] = set()
        components: list[set[int]] = []
        for start in sorted(all_bus_numbers):
            if start in visited:
                continue
            component: set[int] = set()
            queue: deque[int] = deque([start])
            visited.add(start)
            while queue:
                current = queue.popleft()
                component.add(current)
                for neighbour in adjacency.get(current, ()):
                    if neighbour not in visited:
                        visited.add(neighbour)
                        queue.append(neighbour)
            components.append(component)
        components.sort(key=lambda component: (-len(component), min(component)))
        return components

    @staticmethod
    def _identify_main_grid(components: list[set[int]]) -> tuple[set[int], list[set[int]]]:
        """ADR-019 §"Main Grid identification": the Main Grid is defined,
        deterministically, as the **largest** connected component of the
        baseline (pre-opening) topology graph, by Bus count — the
        standard power-system convention for identifying the dominant
        synchronous system among whatever else the current snapshot
        happens to contain (unmigrated spurs, de-energised fragments,
        genuinely separate pre-existing islands). `components` is already
        sorted largest-first by `_compute_bus_components`, so the Main
        Grid is simply the first entry; every other entry is baseline
        evidence only (see `baseline_has_single_main_grid`) — never
        itself reported as a "newly isolated island," a term reserved for
        components created by the selected opening points."""
        if not components:
            return set(), []
        return components[0], components[1:]

    def _bus_numbers_to_substation_ids(
        self, bus_numbers: set[int], bus_by_number: dict[int, TopologyBus]
    ) -> set[uuid.UUID]:
        return {
            bus_by_number[number].substation_id
            for number in bus_numbers
            if number in bus_by_number and bus_by_number[number].substation_id is not None
        }

    def _bus_numbers_to_island_substations(
        self, bus_numbers: set[int], bus_by_number: dict[int, TopologyBus]
    ) -> list[IslandSubstation]:
        substation_ids = self._bus_numbers_to_substation_ids(bus_numbers, bus_by_number)
        if not substation_ids:
            return []
        substations_by_id = {
            s.substation_id: s for s in self.repo.list_substations_by_ids(list(substation_ids))
        }
        result = [
            IslandSubstation(substation_id=sid, substation_mnemonic=substations_by_id[sid].mnemonic)
            for sid in substation_ids
            if sid in substations_by_id
        ]
        result.sort(key=lambda item: item.substation_mnemonic.casefold())
        return result

    def _bfs_substation_depths(
        self,
        start_substation_id: uuid.UUID,
        buses: list[TopologyBus],
        adjacency: dict[int, set[int]],
        max_depth: int | None,
    ) -> dict[uuid.UUID, int]:
        """Shared bus-level BFS + substation-depth reduction — the exact
        reachability computation `traverse()` already performs (§19.4,
        unmodified), factored out so Boundary Pocket completeness
        evaluation (`evaluate_boundary`, boundary-pocket-architecture.md
        §7) can run it twice — once from the candidate "inside" substation,
        once from the "rest of grid" anchor — against one shared adjacency
        map, without duplicating the algorithm. Multi-source seed and
        "start substation always present at depth 0" behaviour are
        unchanged from `traverse()`'s own pre-existing logic."""
        seed_bus_numbers = [
            bus.bus_number for bus in buses if bus.substation_id == start_substation_id
        ]

        depths: dict[int, int] = dict.fromkeys(seed_bus_numbers, 0)
        queue: deque[int] = deque(seed_bus_numbers)

        while queue:
            current = queue.popleft()
            current_depth = depths[current]
            if max_depth is not None and current_depth >= max_depth:
                continue
            for neighbour_bus_number in adjacency.get(current, ()):
                if neighbour_bus_number not in depths:
                    depths[neighbour_bus_number] = current_depth + 1
                    queue.append(neighbour_bus_number)

        bus_by_number = {bus.bus_number: bus for bus in buses}
        substation_depth: dict[uuid.UUID, int] = {start_substation_id: 0}
        for bus_number, depth in depths.items():
            bus = bus_by_number.get(bus_number)
            if bus is None or bus.substation_id is None:
                continue
            existing = substation_depth.get(bus.substation_id)
            if existing is None or depth < existing:
                substation_depth[bus.substation_id] = depth
        return substation_depth

    @staticmethod
    def _build_bus_adjacency_map(
        buses: list[TopologyBus],
        branches: list[TopologyBranch],
        transformers: list[TopologyTransformer],
        *,
        branch_in_service: dict[int, bool],
        transformer_in_service: dict[int, bool],
        excluded_branch_ids: set[int],
        excluded_transformer_ids: set[int],
    ) -> dict[int, set[int]]:
        """Undirected adjacency map over Bus Number, built from every
        in-service, non-excluded Operational Branch and Operational
        Transformer in one `TopologyVersion` — the direct Operational
        Snapshot analogue of the pre-migration Circuit-terminal adjacency
        map. A 3-winding Transformer's tertiary bus is wired mutually
        adjacent to both the HV and LV bus (the same "multi-way
        connection, never a chain of pairwise edges" principle the
        pre-migration tee-off handling already established, here applied
        naturally to Operational Transformers instead of tee-off Circuits
        — Transformer Traversal's own "cross voltage levels" requirement).
        No Bus is ever skipped because of its own `bus_classification`
        (Fictitious, Blank-named, etc.) — this function has no knowledge
        of classification at all; every Bus in `buses` is graph-eligible,
        satisfying EDR-007's "traverse Fictitious Buses naturally"."""
        bus_number_by_id = {bus.topology_bus_id: bus.bus_number for bus in buses}

        adjacency: dict[int, set[int]] = {}

        def _connect(*topology_bus_ids: int | None) -> None:
            numbers = {
                bus_number_by_id[i]
                for i in topology_bus_ids
                if i is not None and i in bus_number_by_id
            }
            for one_side in numbers:
                for other_side in numbers:
                    if one_side != other_side:
                        adjacency.setdefault(one_side, set()).add(other_side)

        for branch in branches:
            if branch.topology_branch_id in excluded_branch_ids:
                continue
            if branch_in_service.get(branch.topology_branch_id, True) is False:
                continue
            _connect(branch.from_bus_id, branch.to_bus_id)

        for transformer in transformers:
            if transformer.topology_transformer_id in excluded_transformer_ids:
                continue
            if transformer_in_service.get(transformer.topology_transformer_id, True) is False:
                continue
            _connect(transformer.from_bus_id, transformer.to_bus_id, transformer.tertiary_bus_id)

        return adjacency

    def traverse(self, request: TraversalRequest) -> TraversalResult:
        """Generic, parameterised breadth-first traversal over the
        Operational Snapshot connectivity graph — deliberately not an
        island-detection or load-pocket feature (both remain out of this
        phase's scope). It answers only "which substations are reachable
        from here, given these lines are excluded" — the primitive a
        future boundary or load-pocket analysis would be built on top of,
        not that analysis itself. The request/response shape is
        substation-in/substation-out, unchanged from before this phase's
        migration; only the underlying graph source changed."""
        if self.repo.get_substation_by_id(request.start_substation_id) is None:
            raise SubstationNotFoundError(request.start_substation_id)

        topology_version_id = self._resolve_topology_version(request.topology_version_id)

        buses = self.repo.list_topology_buses(topology_version_id)
        branches = self.repo.list_topology_branches(topology_version_id)
        transformers = self.repo.list_topology_transformers(topology_version_id)
        branch_in_service, transformer_in_service = self._in_service_element_ids(
            topology_version_id
        )
        excluded_branch_ids, excluded_transformer_ids = self._resolve_excluded_operational_edges(
            set(request.excluded_circuit_ids), topology_version_id
        )
        # Foundation Hardening Sprint A — Circuit Terminal opening points
        # (finer than whole-Circuit exclusion) combine additively with
        # `excluded_circuit_ids`'s own resolved elements.
        term_excluded_branch_ids, term_excluded_transformer_ids = (
            self._resolve_excluded_operational_edges_by_terminals(
                set(request.excluded_circuit_terminal_ids), topology_version_id
            )
        )
        excluded_branch_ids |= term_excluded_branch_ids
        excluded_transformer_ids |= term_excluded_transformer_ids

        adjacency = self._build_bus_adjacency_map(
            buses,
            branches,
            transformers,
            branch_in_service=branch_in_service,
            transformer_in_service=transformer_in_service,
            excluded_branch_ids=excluded_branch_ids,
            excluded_transformer_ids=excluded_transformer_ids,
        )

        # Multi-source seed, "start substation always present at depth 0,"
        # and bus-to-substation depth reduction are all performed by the
        # shared `_bfs_substation_depths` helper (also used by
        # `evaluate_boundary`, Foundation Hardening Sprint A) — identical
        # behaviour to this method's own pre-existing inline computation.
        substation_depth = self._bfs_substation_depths(
            request.start_substation_id, buses, adjacency, request.max_depth
        )

        substations_by_id = {
            s.substation_id: s for s in self.repo.list_substations_by_ids(list(substation_depth))
        }
        reachable: list[ReachableSubstation] = []
        for sub_id, depth in substation_depth.items():
            substation = substations_by_id.get(sub_id)
            if substation is None:
                # Referentially impossible under FK RESTRICT for a
                # Substation actually correlated on a TopologyBus, but the
                # start Substation was already validated to exist above —
                # never re-raise, simply omit (this module's own
                # established "unknown, not invalid" tolerance).
                continue
            reachable.append(
                ReachableSubstation(
                    substation_id=sub_id,
                    substation_mnemonic=substation.mnemonic,
                    depth=depth,
                )
            )
        reachable.sort(key=lambda item: (item.depth, item.substation_mnemonic.casefold()))

        return TraversalResult(
            start_substation_id=request.start_substation_id,
            excluded_circuit_ids=list(request.excluded_circuit_ids),
            excluded_circuit_terminal_ids=list(request.excluded_circuit_terminal_ids),
            reachable_substations=reachable,
            topology_version_id=topology_version_id,
        )

    # --- Foundation Hardening Sprint C — Boundary Pocket evaluation by ---------
    # connected-component discovery (ADR-019) --------------------------------
    #
    # `evaluateBoundary` (boundary-pocket-architecture.md §7, §10, §11, as
    # corrected by ADR-019) — Network Model orchestration only. It composes
    # `_resolve_topology_version`, `_resolve_boundary_exclusions`,
    # `_build_bus_adjacency_map`, `_compute_bus_components`, and
    # `_identify_main_grid` (all above) to discover every Substation group
    # that splits off from the baseline Main Grid once the selected opening
    # points are treated as open — never two independently-nominated
    # reachability seeds (the ADR-017 mechanism this supersedes). It creates
    # no Boundary Pocket entity, no Scheme assignment, and no engineering
    # finding — every one of those remains a future Defence Scheme module's
    # own concern (boundary-pocket-architecture.md §3, §8).

    def evaluate_boundary(
        self, request: BoundaryPocketEvaluationRequest
    ) -> BoundaryPocketEvaluation:
        """boundary-pocket-architecture.md §7's Completeness Evaluation, per
        ADR-019. Answers "which new electrical islands are created when
        these selected Circuit Terminals are opened, relative to the
        active Main Grid" — never "can one nominated substation be
        separated from one nominated reference." No inside substation, no
        rest-of-grid override: the Main Grid is discovered from the
        baseline (pre-opening) topology itself, and every group of
        Substations that splits off from it as a direct result of the
        selected opening points is reported, not only one. Always a live,
        stateless, synchronous computation — no caching, no async job
        infrastructure; whole-graph connected-component discovery over a
        few thousand Buses is cheap enough to re-run on every boundary
        edit during Draft, exactly mirroring `traverse()`'s own
        performance characteristics."""
        topology_version_id = self._resolve_topology_version(request.topology_version_id)

        self._validate_circuit_terminals_exist(request.circuit_terminal_ids)

        excluded_branch_ids, excluded_transformer_ids, uncorrelated_terminal_ids = (
            self._resolve_boundary_exclusions(request.circuit_terminal_ids, topology_version_id)
        )

        buses = self.repo.list_topology_buses(topology_version_id)
        branches = self.repo.list_topology_branches(topology_version_id)
        transformers = self.repo.list_topology_transformers(topology_version_id)
        branch_in_service, transformer_in_service = self._in_service_element_ids(
            topology_version_id
        )
        bus_by_number = {bus.bus_number: bus for bus in buses}

        # --- Baseline (no opening points applied) — establishes the Main
        # Grid this evaluation compares against, and surfaces any
        # pre-existing, abnormal multi-component condition as evidence,
        # independent of whatever opening points were selected.
        baseline_adjacency = self._build_bus_adjacency_map(
            buses,
            branches,
            transformers,
            branch_in_service=branch_in_service,
            transformer_in_service=transformer_in_service,
            excluded_branch_ids=set(),
            excluded_transformer_ids=set(),
        )
        baseline_components = self._compute_bus_components(buses, baseline_adjacency)
        main_grid_bus_numbers, other_baseline_components = self._identify_main_grid(
            baseline_components
        )
        main_grid_anchor = min(main_grid_bus_numbers) if main_grid_bus_numbers else None
        baseline_main_grid_substations = self._bus_numbers_to_substation_ids(
            main_grid_bus_numbers, bus_by_number
        )
        baseline_has_single_main_grid = not any(
            len(self._bus_numbers_to_substation_ids(component, bus_by_number))
            >= _MEANINGFUL_COMPONENT_MIN_SUBSTATIONS
            for component in other_baseline_components
        )

        # --- Post-opening — the same graph, with the selected opening
        # points' correlated elements additionally excluded.
        post_opening_adjacency = self._build_bus_adjacency_map(
            buses,
            branches,
            transformers,
            branch_in_service=branch_in_service,
            transformer_in_service=transformer_in_service,
            excluded_branch_ids=excluded_branch_ids,
            excluded_transformer_ids=excluded_transformer_ids,
        )
        post_opening_components = self._compute_bus_components(buses, post_opening_adjacency)

        surviving_main_grid_component: set[int] = next(
            (
                component
                for component in post_opening_components
                if main_grid_anchor is not None and main_grid_anchor in component
            ),
            set(),
        )

        # Every post-opening component that (a) is not the surviving Main
        # Grid itself, and (b) actually shares Buses with the *baseline*
        # Main Grid, is a newly isolated island — a component neither
        # condition holds for was already separate before any opening was
        # applied (baseline evidence only, never a "newly isolated" claim).
        isolated_islands: list[IsolatedIsland] = []
        for component in post_opening_components:
            if component == surviving_main_grid_component:
                continue
            split_off_bus_numbers = component & main_grid_bus_numbers
            if not split_off_bus_numbers:
                continue
            island_substations = self._bus_numbers_to_island_substations(
                split_off_bus_numbers, bus_by_number
            )
            if island_substations:
                isolated_islands.append(IsolatedIsland(substations=island_substations))

        isolated_islands.sort(
            key=lambda island: (
                -len(island.substations),
                island.substations[0].substation_mnemonic.casefold(),
            )
        )

        is_boundary_effective = len(isolated_islands) > 0
        if is_boundary_effective:
            island_word = "island" if len(isolated_islands) == 1 else "islands"
            reason = (
                f"{len(isolated_islands)} new isolated {island_word} formed relative to the "
                "Main Grid."
            )
        else:
            reason = (
                "No new island was formed — the selected opening points do not disconnect any "
                "part of the Main Grid under the current snapshot."
            )

        return BoundaryPocketEvaluation(
            topology_version_id=topology_version_id,
            baseline_component_count=len(baseline_components),
            baseline_main_grid_substation_count=len(baseline_main_grid_substations),
            baseline_has_single_main_grid=baseline_has_single_main_grid,
            post_opening_component_count=len(post_opening_components),
            is_boundary_effective=is_boundary_effective,
            isolated_islands=isolated_islands,
            circuit_terminal_ids=list(request.circuit_terminal_ids),
            uncorrelated_circuit_terminal_ids=uncorrelated_terminal_ids,
            reason=reason,
        )

    # --- Phase 7F — Operational Snapshot Verification Workspace ----------------
    #
    # An engineering diagnostic surface, independent of `traverse()` and the
    # existing Network Traversal page (both above, unchanged). It exists to
    # let an engineer verify that the Operational Snapshot faithfully
    # represents the imported PSS/E network, before that snapshot becomes
    # the foundation of UFLS/UVLS/EMLS/Heatmap/Analytics (docs/architecture/
    # network-model-module.md §19.10). Bus-level BFS remains the
    # authoritative computation — `verify_path` reuses
    # `_build_bus_adjacency_map` unchanged and performs the same reachability
    # decision `traverse()` does; it only adds parent-edge bookkeeping and
    # projects the one resulting BFS depth map into several engineering
    # views (Operational Projections, operational-correlation-
    # architecture.md §4.2), never a second graph or a second correlation
    # mechanism.

    def get_snapshot_summary(self) -> SnapshotSummary:
        """Section 1 — Snapshot Summary. Delegates entirely to PSS/E
        Integration's own `get_current_status_summary` (unchanged); this
        method only reshapes that existing response into this workspace's
        flat field list."""
        status = self.psse_service.get_current_status_summary()
        topology = status.current_topology_version
        snapshot = status.current_load_snapshot
        return SnapshotSummary(
            topology_version_id=topology.topology_version_id if topology is not None else None,
            topology_version_status=topology.status if topology is not None else None,
            load_snapshot_id=snapshot.load_snapshot_id if snapshot is not None else None,
            load_snapshot_status=snapshot.status if snapshot is not None else None,
            import_date=topology.created_at if topology is not None else None,
            bus_count=topology.bus_count if topology is not None else 0,
            branch_count=topology.branch_count if topology is not None else 0,
            transformer_count=topology.transformer_count if topology is not None else 0,
            load_count=snapshot.load_count if snapshot is not None else 0,
            generator_count=snapshot.generator_count if snapshot is not None else 0,
        )

    @staticmethod
    def _build_bus_edge_index(
        buses: list[TopologyBus],
        branches: list[TopologyBranch],
        transformers: list[TopologyTransformer],
        *,
        branch_in_service: dict[int, bool],
        transformer_in_service: dict[int, bool],
    ) -> dict[tuple[int, int], list[tuple[str, int]]]:
        """Maps each unordered Bus Number pair to every in-service
        Operational Branch/Transformer edge connecting them.
        `_build_bus_adjacency_map` (unchanged, still the sole basis for the
        reachability decision itself) only needs to know *that* two buses
        are connected; this index additionally records *which* edge(s)
        connect them, purely so Section 2's path can name the specific
        Branch/Transformer crossed at each step. Never consulted to decide
        reachability — only to label an edge the BFS has already walked."""
        bus_number_by_id = {bus.topology_bus_id: bus.bus_number for bus in buses}
        index: dict[tuple[int, int], list[tuple[str, int]]] = {}

        def _add(bus_a: int | None, bus_b: int | None, edge_type: str, edge_id: int) -> None:
            if bus_a is None or bus_b is None or bus_a == bus_b:
                return
            key = (bus_a, bus_b) if bus_a < bus_b else (bus_b, bus_a)
            index.setdefault(key, []).append((edge_type, edge_id))

        for branch in branches:
            if branch_in_service.get(branch.topology_branch_id, True) is False:
                continue
            _add(
                bus_number_by_id.get(branch.from_bus_id),
                bus_number_by_id.get(branch.to_bus_id),
                "BRANCH",
                branch.topology_branch_id,
            )

        for transformer in transformers:
            if transformer_in_service.get(transformer.topology_transformer_id, True) is False:
                continue
            hv = bus_number_by_id.get(transformer.from_bus_id)
            lv = bus_number_by_id.get(transformer.to_bus_id)
            tertiary = (
                bus_number_by_id.get(transformer.tertiary_bus_id)
                if transformer.tertiary_bus_id is not None
                else None
            )
            _add(hv, lv, "TRANSFORMER", transformer.topology_transformer_id)
            if tertiary is not None:
                _add(hv, tertiary, "TRANSFORMER", transformer.topology_transformer_id)
                _add(lv, tertiary, "TRANSFORMER", transformer.topology_transformer_id)

        return index

    @staticmethod
    def _bucket_correlation_counts(statuses: list[CorrelationStatus]) -> CorrelationCounts:
        """Section 7 — buckets the shared Correlated Operational Model
        vocabulary (`CorrelationStatus`) into the three-tier funnel this
        workspace's Correlation Summary displays. `CORRELATED` and
        `OUTSIDE_CURRENT_SCOPE` map straight across; every other status
        (`UNMATCHED_OPERATIONAL`/`UNMATCHED_REGISTRY`/`AMBIGUOUS`/
        `ENGINEERING_REVIEW_REQUIRED`) is a form of "not yet correlated,"
        bucketed together for this summary view — the precise status
        remains visible per-item in Sections 3-5."""
        total = len(statuses)
        correlated = sum(1 for s in statuses if s == "CORRELATED")
        outside_scope = sum(1 for s in statuses if s == "OUTSIDE_CURRENT_SCOPE")
        return CorrelationCounts(
            total=total,
            correlated=correlated,
            unmatched=total - correlated - outside_scope,
            outside_scope=outside_scope,
        )

    def verify_path(self, request: PathVerificationRequest) -> TraversalVerificationResult:
        """Section 2 ("Electrical Path Verification") and every section
        derived from it (3-8). Reuses `_resolve_topology_version`,
        `_in_service_element_ids`, and `_build_bus_adjacency_map` exactly as
        `traverse()` does, and performs the identical Bus-level BFS
        reachability computation — extended, additively, with parent-edge
        bookkeeping (`_build_bus_edge_index`) so the path itself can be
        reconstructed. Every list and summary in the response is read off
        this one BFS result; nothing here re-traverses or re-derives
        connectivity independently, and Bus/Branch/Transformer correlation
        is always obtained from PSS/E Integration's own service methods
        (`get_operational_*_views_for_*`) — never recomputed here."""
        substation = self.repo.get_substation_by_id(request.start_substation_id)
        if substation is None:
            raise SubstationNotFoundError(request.start_substation_id)

        topology_version_id = self._resolve_topology_version(request.topology_version_id)

        buses = self.repo.list_topology_buses(topology_version_id)
        branches = self.repo.list_topology_branches(topology_version_id)
        transformers = self.repo.list_topology_transformers(topology_version_id)
        branch_in_service, transformer_in_service = self._in_service_element_ids(
            topology_version_id
        )

        adjacency = self._build_bus_adjacency_map(
            buses,
            branches,
            transformers,
            branch_in_service=branch_in_service,
            transformer_in_service=transformer_in_service,
            excluded_branch_ids=set(),
            excluded_transformer_ids=set(),
        )
        edge_index = self._build_bus_edge_index(
            buses,
            branches,
            transformers,
            branch_in_service=branch_in_service,
            transformer_in_service=transformer_in_service,
        )

        # --- Seed resolution: whole Substation, or one Switchyard within it
        start_voltage_yard_id = request.start_voltage_yard_id
        if start_voltage_yard_id is not None:
            yard = self.repo.get_voltage_yard(start_voltage_yard_id)
            if yard is None:
                raise VoltageYardNotFoundError(start_voltage_yard_id)
            if yard.substation_id != request.start_substation_id:
                raise VoltageYardSubstationMismatchError(
                    start_voltage_yard_id, request.start_substation_id
                )
            voltage_level = self.reference_data.get_voltage_level(yard.voltage_level_id)
            target_base_kv = float(voltage_level.nominal_kv) if voltage_level is not None else None
            seed_bus_numbers = [
                bus.bus_number
                for bus in buses
                if bus.substation_id == request.start_substation_id
                and target_base_kv is not None
                and float(bus.base_kv) == target_base_kv
            ]
        else:
            seed_bus_numbers = [
                bus.bus_number for bus in buses if bus.substation_id == request.start_substation_id
            ]

        # --- Bus-level BFS, extended with parent-edge tracking (additive;
        # the reachability decision itself is identical to `traverse()`'s)
        bus_by_number = {bus.bus_number: bus for bus in buses}
        branch_by_id = {b.topology_branch_id: b for b in branches}
        transformer_by_id = {t.topology_transformer_id: t for t in transformers}

        depths: dict[int, int] = dict.fromkeys(seed_bus_numbers, 0)
        parent_step: dict[int, PathStep] = {}
        queue: deque[int] = deque(seed_bus_numbers)

        while queue:
            current = queue.popleft()
            current_depth = depths[current]
            if request.max_depth is not None and current_depth >= request.max_depth:
                continue
            for neighbour in adjacency.get(current, ()):
                if neighbour in depths:
                    continue
                depths[neighbour] = current_depth + 1
                queue.append(neighbour)

                key = (current, neighbour) if current < neighbour else (neighbour, current)
                edges = edge_index.get(key, [])
                if not edges:
                    # Defensive only — `adjacency` and `edge_index` are
                    # built from the same branch/transformer lists, so
                    # every adjacency edge has a corresponding index entry.
                    # This module's own "unknown, not invalid" tolerance:
                    # skip labelling rather than raise.
                    continue
                edge_type, edge_id = edges[0]
                branch = branch_by_id.get(edge_id) if edge_type == "BRANCH" else None
                transformer = transformer_by_id.get(edge_id) if edge_type == "TRANSFORMER" else None
                ckt_id = (
                    branch.ckt_id
                    if branch is not None
                    else (transformer.ckt_id if transformer is not None else "")
                )
                from_bus = bus_by_number.get(current)
                to_bus = bus_by_number.get(neighbour)
                parent_step[neighbour] = PathStep(
                    depth=current_depth + 1,
                    from_bus_number=current,
                    from_bus_name=from_bus.bus_name if from_bus is not None else None,
                    to_bus_number=neighbour,
                    to_bus_name=to_bus.bus_name if to_bus is not None else None,
                    edge_type=edge_type,  # type: ignore[arg-type]
                    ckt_id=ckt_id,
                    topology_branch_id=edge_id if edge_type == "BRANCH" else None,
                    topology_transformer_id=edge_id if edge_type == "TRANSFORMER" else None,
                )

        path_steps = sorted(
            parent_step.values(),
            key=lambda step: (step.depth, step.from_bus_number, step.to_bus_number),
        )

        # --- Section 4/5: every Branch/Transformer edge within the reached
        # component (not only BFS-tree edges) — mirrors the pre-Phase-7E
        # frontend's own "every line whose both ends are reachable" filter,
        # now applied to the Operational Snapshot graph instead of Registry
        # circuits.
        bus_number_by_id = {bus.topology_bus_id: bus.bus_number for bus in buses}
        traversed_branch_ids = [
            b.topology_branch_id
            for b in branches
            if branch_in_service.get(b.topology_branch_id, True)
            and bus_number_by_id.get(b.from_bus_id) in depths
            and bus_number_by_id.get(b.to_bus_id) in depths
        ]
        traversed_transformer_ids = [
            t.topology_transformer_id
            for t in transformers
            if transformer_in_service.get(t.topology_transformer_id, True)
            and bus_number_by_id.get(t.from_bus_id) in depths
            and bus_number_by_id.get(t.to_bus_id) in depths
        ]

        # --- Sections 3-5: Bus/Branch/Transformer views, obtained from
        # PSS/E Integration's own service (its existing Correlated
        # Operational Model builders), scoped to this traversal's reached
        # elements — never recomputed here.
        bus_views = self.psse_service.get_operational_bus_views_for_numbers(
            topology_version_id, list(depths.keys())
        )
        bus_view_by_number = {v.bus_number: v for v in bus_views}
        path_buses = [
            PathBus(
                depth=depths[number],
                base_kv=float(bus_by_number[number].base_kv),
                bus=bus_view_by_number[number],
            )
            for number in sorted(depths, key=lambda n: (depths[n], n))
            if number in bus_view_by_number and number in bus_by_number
        ]
        branch_views = self.psse_service.get_operational_branch_views_for_ids(
            topology_version_id, traversed_branch_ids
        )
        transformer_views = self.psse_service.get_operational_transformer_views_for_ids(
            topology_version_id, traversed_transformer_ids
        )

        # --- Section 8: Operational Projections, all read off `depths` —
        # no recomputation, no second graph.
        switchyard_groups: dict[tuple[uuid.UUID, float], list[int]] = {}
        for number in depths:
            bus = bus_by_number.get(number)
            if bus is None or bus.substation_id is None:
                continue
            switchyard_groups.setdefault((bus.substation_id, float(bus.base_kv)), []).append(number)

        substation_depth: dict[uuid.UUID, int] = {request.start_substation_id: 0}
        for number, depth in depths.items():
            bus = bus_by_number.get(number)
            if bus is None or bus.substation_id is None:
                continue
            existing = substation_depth.get(bus.substation_id)
            if existing is None or depth < existing:
                substation_depth[bus.substation_id] = depth

        substations_by_id = {
            s.substation_id: s
            for s in self.repo.list_substations_by_ids(
                list(set(substation_depth) | {sub_id for sub_id, _ in switchyard_groups})
            )
        }

        bus_projection = [
            BusProjectionEntry(
                bus_number=number,
                bus_name=bus_by_number[number].bus_name if number in bus_by_number else None,
                depth=depth,
            )
            for number, depth in sorted(depths.items(), key=lambda kv: (kv[1], kv[0]))
        ]

        switchyard_projection: list[SwitchyardProjectionEntry] = []
        for (sub_id, base_kv), bus_numbers_in_group in switchyard_groups.items():
            substation_row = substations_by_id.get(sub_id)
            if substation_row is None:
                continue
            sample_view = bus_view_by_number.get(bus_numbers_in_group[0])
            switchyard_projection.append(
                SwitchyardProjectionEntry(
                    substation_id=sub_id,
                    substation_mnemonic=substation_row.mnemonic,
                    base_kv=base_kv,
                    voltage_yard_id=sample_view.voltage_yard_id
                    if sample_view is not None
                    else None,
                    depth=min(depths[n] for n in bus_numbers_in_group),
                    bus_count=len(bus_numbers_in_group),
                )
            )
        switchyard_projection.sort(
            key=lambda e: (e.depth, e.substation_mnemonic.casefold(), e.base_kv)
        )

        substation_projection = [
            ReachableSubstation(
                substation_id=sub_id,
                substation_mnemonic=substations_by_id[sub_id].mnemonic,
                depth=depth,
            )
            for sub_id, depth in substation_depth.items()
            if sub_id in substations_by_id
        ]
        substation_projection.sort(
            key=lambda item: (item.depth, item.substation_mnemonic.casefold())
        )

        statistics = TraversalStatistics(
            operational_buses_traversed=len(depths),
            operational_branches_traversed=len(branch_views),
            operational_transformers_traversed=len(transformer_views),
            operational_switchyards_traversed=len(switchyard_projection),
            registered_substations_correlated=len(substation_projection),
            registered_switchyards_correlated=len(
                {e.voltage_yard_id for e in switchyard_projection if e.voltage_yard_id is not None}
            ),
        )

        correlation_summary = CorrelationSummary(
            bus=self._bucket_correlation_counts([v.bus.correlation_status for v in path_buses]),
            branch=self._bucket_correlation_counts([v.correlation_status for v in branch_views]),
            transformer=self._bucket_correlation_counts(
                [v.correlation_status for v in transformer_views]
            ),
        )

        return TraversalVerificationResult(
            start_substation_id=request.start_substation_id,
            start_voltage_yard_id=start_voltage_yard_id,
            topology_version_id=topology_version_id,
            path_steps=path_steps,
            buses=path_buses,
            branches=branch_views,
            transformers=transformer_views,
            statistics=statistics,
            correlation_summary=correlation_summary,
            projections=OperationalProjections(
                bus_projection=bus_projection,
                switchyard_projection=switchyard_projection,
                substation_projection=substation_projection,
            ),
        )
