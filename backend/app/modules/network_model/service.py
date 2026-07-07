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

from app.modules.equipment_registry.models import CircuitTerminal
from app.modules.network_model.exceptions import SubstationNotFoundError
from app.modules.network_model.repository import NetworkModelRepository
from app.modules.network_model.schemas import (
    ConnectingLine,
    ElectricalNeighbour,
    LineBay,
    NeighbourSubstation,
    NetworkOverview,
    ReachableSubstation,
    SubstationConnectivity,
    SubstationEquipment,
    TerminalOnCircuit,
    TransformerBay,
    TraversalRequest,
    TraversalResult,
)
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


class NetworkModelService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = NetworkModelRepository(db)
        self.reference_data = ReferenceDataRepository(db)

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

    # --- Traversal -------------------------------------------------------------

    def _build_adjacency_map(
        self, excluded_circuit_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, set[uuid.UUID]]:
        """Builds an undirected adjacency map over substation ids from
        every active circuit's terminal set, one query for the whole
        network (`list_all_active_terminals`) rather than one per
        substation. A tee-off circuit's three-or-more terminal substations
        are made mutually adjacent to each other directly — modelled as
        one multi-way electrical connection, never as a chain of pairwise
        edges (which would misrepresent which substations are actually
        directly connected through it).

        A terminal whose substation cannot currently be resolved is
        simply excluded from this circuit's substation set — the
        remaining, resolvable terminals of that circuit are still wired up
        to each other. An entirely unresolvable circuit (e.g. every
        terminal's substation unknown) safely contributes no edges."""
        terminals = self.repo.list_all_active_terminals()

        by_circuit: dict[uuid.UUID, list[CircuitTerminal]] = {}
        for terminal in terminals:
            if terminal.circuit_id in excluded_circuit_ids:
                continue
            by_circuit.setdefault(terminal.circuit_id, []).append(terminal)

        adjacency: dict[uuid.UUID, set[uuid.UUID]] = {}
        for circuit_terminals in by_circuit.values():
            substation_ids: set[uuid.UUID] = set()
            for terminal in circuit_terminals:
                sub_id = self.repo.get_substation_id_for_voltage_yard(terminal.voltage_yard_id)
                if sub_id is not None:
                    substation_ids.add(sub_id)

            for one_side in substation_ids:
                for other_side in substation_ids:
                    if one_side != other_side:
                        adjacency.setdefault(one_side, set()).add(other_side)

        return adjacency

    def traverse(self, request: TraversalRequest) -> TraversalResult:
        """Generic, parameterised breadth-first traversal over the static
        connectivity graph — deliberately not an island-detection or
        load-pocket feature (both remain out of this phase's scope). It
        answers only "which substations are reachable from here, given
        these lines are excluded" — the primitive a future boundary or
        load-pocket analysis would be built on top of, not that analysis
        itself."""
        if self.repo.get_substation_by_id(request.start_substation_id) is None:
            raise SubstationNotFoundError(request.start_substation_id)

        excluded = set(request.excluded_circuit_ids)
        adjacency = self._build_adjacency_map(excluded)

        depths: dict[uuid.UUID, int] = {request.start_substation_id: 0}
        queue: deque[uuid.UUID] = deque([request.start_substation_id])

        while queue:
            current = queue.popleft()
            current_depth = depths[current]
            if request.max_depth is not None and current_depth >= request.max_depth:
                continue
            for neighbour_id in adjacency.get(current, ()):
                if neighbour_id not in depths:
                    depths[neighbour_id] = current_depth + 1
                    queue.append(neighbour_id)

        reachable: list[ReachableSubstation] = []
        for sub_id, depth in depths.items():
            substation = self.repo.get_substation_by_id(sub_id)
            if substation is None:
                # A substation reachable through connectivity data that has
                # since been removed/unresolvable — unknown, not an error;
                # simply omitted rather than surfaced with placeholder data.
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
            excluded_circuit_ids=list(excluded),
            reachable_substations=reachable,
        )
