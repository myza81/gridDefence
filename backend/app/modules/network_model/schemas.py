"""Network Model API DTOs (CLAUDE.md A6 — API DTO layer).

Per `docs/engineering/04-domain-model.md`, every shape here describes an
*engineering relationship* (which substations connect, which equipment
belongs where) — never a database row shape. Persistence models
(Equipment Registry's `Circuit`/`CircuitTerminal`/`Transformer`, Substation
Registry's `Substation`) are never returned directly (CLAUDE.md A9).
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class TerminalOnCircuit(BaseModel):
    """One terminal of a connecting line, at one substation."""

    circuit_terminal_id: uuid.UUID
    substation_id: uuid.UUID
    substation_mnemonic: str
    voltage_yard_id: uuid.UUID
    breaker_number: str


class ConnectingLine(BaseModel):
    """One transmission line (`Circuit`) connecting two or more substations
    — engineering-relationship shape, not a persistence row. `is_tee_off`
    is `True` whenever more than two terminals exist (equipment-registry-
    module.md §7.5: "an ordinary circuit has exactly two ... a tee-off has
    three or more"), per this phase's explicit requirement to support
    multi-terminal configurations from the outset."""

    circuit_id: uuid.UUID
    bay_number: str
    circuit_name: str
    voltage_level_label: str
    line_type_label: str
    operational_status_code: str
    is_tee_off: bool
    terminals: list[TerminalOnCircuit]


class NeighbourSubstation(BaseModel):
    """One electrically-neighbouring substation, reached via one specific
    connecting line. A substation with several parallel lines to the same
    neighbour appears once per line — the caller can de-duplicate by
    `substation_id` if only the distinct neighbour set is wanted (see
    `list_substation_neighbours`, which does exactly that)."""

    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    via_circuit_id: uuid.UUID
    via_circuit_name: str
    via_bay_number: str


class ElectricalNeighbour(BaseModel):
    """One distinct neighbouring substation — deduplicated across however
    many parallel lines connect to it (contrast with `NeighbourSubstation`,
    which is per-line). Answers docs/engineering/03-system-workflow.md's
    "Electrical Neighbours" question directly, without the caller needing
    to de-duplicate `SubstationConnectivity.neighbours` themselves."""

    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    connecting_line_count: int


class SubstationConnectivity(BaseModel):
    """Answers: which substations are connected to this one, and via which
    transmission lines — docs/engineering/03-system-workflow.md's
    "Electrical Neighbours" / "Substation Connectivity" engineering
    question."""

    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    connected_lines: list[ConnectingLine]
    neighbours: list[NeighbourSubstation]


class TransformerBay(BaseModel):
    """One transformer bay at a substation (Equipment Registry's
    `Transformer`, read-only)."""

    transformer_id: uuid.UUID
    transformer_number: str
    generated_short_name: str
    hv_voltage_level_label: str
    lv_voltage_level_label: str
    capacity_mva: float | None
    operational_status_code: str


class LineBay(BaseModel):
    """One line bay (a `CircuitTerminal`) at a substation, and the line it
    terminates."""

    circuit_terminal_id: uuid.UUID
    circuit_id: uuid.UUID
    circuit_bay_number: str
    circuit_name: str
    breaker_number: str
    voltage_level_label: str
    operational_status_code: str


class SubstationEquipment(BaseModel):
    """Answers: which equipment belongs to this substation, grouped by
    engineering function (transformer bays vs. line bays) — docs/
    engineering/03-system-workflow.md's "Equipment Relationships"
    question."""

    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    transformer_bays: list[TransformerBay]
    line_bays: list[LineBay]


class NetworkOverview(BaseModel):
    """A summary of the static network model's size — never current
    loading, current breaker status, or current topology state, all of
    which belong to future, PSS/E-informed phases (out of this phase's
    scope by explicit instruction)."""

    substation_count: int
    circuit_count: int
    tee_off_circuit_count: int
    transformer_count: int


class TraversalRequest(BaseModel):
    """Basic engineering traversal input. `excluded_circuit_ids` models
    "these lines are open" — the underlying capability a future load-pocket
    or boundary-analysis feature would build on; this phase implements only
    the traversal itself, never pocket/boundary identification (explicitly
    out of scope)."""

    start_substation_id: uuid.UUID
    excluded_circuit_ids: list[uuid.UUID] = []
    max_depth: int | None = None


class ReachableSubstation(BaseModel):
    substation_id: uuid.UUID
    substation_mnemonic: str
    depth: int


class TraversalResult(BaseModel):
    start_substation_id: uuid.UUID
    excluded_circuit_ids: list[uuid.UUID]
    reachable_substations: list[ReachableSubstation]
