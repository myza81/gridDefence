"""Network Model API DTOs (CLAUDE.md A6 — API DTO layer).

Per `docs/engineering/04-domain-model.md`, every shape here describes an
*engineering relationship* (which substations connect, which equipment
belongs where) — never a database row shape. Persistence models
(Equipment Registry's `Circuit`/`CircuitTerminal`/`Transformer`, Substation
Registry's `Substation`) are never returned directly (CLAUDE.md A9).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.modules.psse_integration.schemas import (
    OperationalBranchView,
    OperationalBusView,
    OperationalTransformerView,
)


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
    out of scope).

    `topology_version_id` (Phase 7E, Snapshot Awareness) selects which
    Operational Snapshot to traverse — omitted means "whichever
    `TopologyVersion` is currently Current." `excluded_circuit_ids` remains
    a Line Connectivity Registry-facing convenience: it is translated,
    internally, into the Operational Branch/Transformer elements that
    Circuit currently correlates to (via `EquipmentTopologyMap`) for the
    `TopologyVersion` being traversed — a Circuit with no correlation for
    that snapshot simply excludes nothing (Operational Correlation is
    optional enrichment only; traversal itself never depends on it)."""

    start_substation_id: uuid.UUID
    excluded_circuit_ids: list[uuid.UUID] = []
    max_depth: int | None = None
    topology_version_id: uuid.UUID | None = None


class ReachableSubstation(BaseModel):
    substation_id: uuid.UUID
    substation_mnemonic: str
    depth: int


class TraversalResult(BaseModel):
    start_substation_id: uuid.UUID
    excluded_circuit_ids: list[uuid.UUID]
    reachable_substations: list[ReachableSubstation]
    # Phase 7E — the Operational Snapshot actually traversed, always
    # resolved and reported explicitly (never silently mixed across
    # snapshots, per Snapshot Awareness).
    topology_version_id: uuid.UUID


# --- Phase 7F — Operational Snapshot Verification Workspace ------------------------
#
# Engineering verification only (docs/architecture/network-model-module.md
# §19.10; docs/architecture/operational-correlation-architecture.md §4.1,
# §4.2 — Operational Switchyard, Operational Projections). This section
# introduces no new traversal algorithm: every DTO below is either reused
# verbatim from `psse_integration.schemas` (`OperationalBusView`/
# `OperationalBranchView`/`OperationalTransformerView` — the same
# Correlated Operational Model view models Phase 7C already built, never a
# parallel set of view models for this page) or a lightweight aggregation
# computed directly from one Bus-level BFS traversal's own result (depths,
# parent edges, reached-component edge set) — never a second graph, never a
# recomputed correlation.


class SnapshotSummary(BaseModel):
    """Section 1 — a plain restatement of whichever `TopologyVersion`/
    `LoadSnapshot` are currently Current, for engineering orientation before
    running a path verification. Sourced from `PsseIntegrationService.
    get_current_status_summary()` (unchanged, reused as-is) — this DTO only
    reshapes that existing response into this page's own flat field list."""

    topology_version_id: uuid.UUID | None
    topology_version_status: str | None
    load_snapshot_id: uuid.UUID | None
    load_snapshot_status: str | None
    import_date: datetime | None
    bus_count: int
    branch_count: int
    transformer_count: int
    load_count: int
    generator_count: int


class PathVerificationRequest(BaseModel):
    """Section 2 input. `start_voltage_yard_id` (Switchyard) is optional —
    omitted means every Bus currently correlated to `start_substation_id`
    seeds the traversal (identical seeding to `TraversalRequest`); supplied
    means only the Buses correlated to that one Switchyard seed it (EDR-007
    §4.4 — a Switchyard Bus's own voltage level scopes it to one of a
    Substation's several Switchyards). No `excluded_circuit_ids`: this
    workspace verifies the Operational Snapshot exactly as it exists (per
    this phase's own Engineering Philosophy), it does not model hypothetical
    what-if exclusions — that remains the existing Network Traversal page's
    own, unchanged purpose."""

    start_substation_id: uuid.UUID
    start_voltage_yard_id: uuid.UUID | None = None
    max_depth: int | None = None
    topology_version_id: uuid.UUID | None = None


class PathStep(BaseModel):
    """Section 2 — one edge of the BFS spanning tree actually walked to
    first reach `to_bus_number`, in traversal order. Reconstructed directly
    from the same BFS this module's `traverse()` already performs
    (`_build_bus_adjacency_map`, unchanged) — parent-edge tracking is
    additive bookkeeping around that existing algorithm, not a different
    one."""

    depth: int
    from_bus_number: int
    from_bus_name: str | None
    to_bus_number: int
    to_bus_name: str | None
    edge_type: Literal["BRANCH", "TRANSFORMER"]
    ckt_id: str
    topology_branch_id: int | None
    topology_transformer_id: int | None


class PathBus(BaseModel):
    """Section 3 — one `OperationalBusView` (reused verbatim from
    `psse_integration.schemas`, never redefined) at its BFS-tree depth.
    `depth` and `base_kv` are the only fields this page adds — `base_kv` is
    structural Operational Snapshot data (`TopologyBus.base_kv`) this
    workspace needs for engineering verification but `OperationalBusView`
    itself does not carry (it correlates against the Registry, which has no
    per-bus voltage field of its own); everything else is the Correlated
    Operational Model's own, existing Bus projection, unchanged."""

    depth: int
    base_kv: float
    bus: OperationalBusView


class TraversalStatistics(BaseModel):
    """Section 6. The "Operational X Traversed" fields count over the raw
    Operational Snapshot graph reached by this traversal; the "Registered X
    Correlated" fields count how many of those already correlate to an
    Engineering Registry object. The gap between the two is itself the
    verification signal this workspace exists to surface (network-model-
    module.md §19.10)."""

    operational_buses_traversed: int
    operational_branches_traversed: int
    operational_transformers_traversed: int
    # Distinct (substation, voltage level) groupings implied by reached,
    # Substation-correlated Buses — i.e. Operational Switchyards
    # (operational-correlation-architecture.md §4.1), whether or not each
    # one also has a registered `SubstationVoltageYard` row yet.
    operational_switchyards_traversed: int
    registered_substations_correlated: int
    # Of `operational_switchyards_traversed`, how many actually resolve to
    # a registered `SubstationVoltageYard` (Switchyard) row.
    registered_switchyards_correlated: int


class CorrelationCounts(BaseModel):
    """Section 7 — one row of the "Operational Objects -> Correlated ->
    Unmatched -> Outside Scope" funnel. `unmatched` intentionally buckets
    every `CorrelationStatus` other than `CORRELATED`/`OUTSIDE_CURRENT_SCOPE`
    (`UNMATCHED_OPERATIONAL`/`UNMATCHED_REGISTRY`/`AMBIGUOUS`/
    `ENGINEERING_REVIEW_REQUIRED`) into this summary view's single
    "needs attention" bucket — the full, unbucketed status remains visible
    per-item in Sections 3-5 (`correlation_status` on each `OperationalBusView`/
    `OperationalBranchView`/`OperationalTransformerView`)."""

    total: int
    correlated: int
    unmatched: int
    outside_scope: int


class CorrelationSummary(BaseModel):
    bus: CorrelationCounts
    branch: CorrelationCounts
    transformer: CorrelationCounts


class BusProjectionEntry(BaseModel):
    """Section 8 — Operational Bus Projection: the traversal's own, native
    granularity."""

    bus_number: int
    bus_name: str | None
    depth: int


class SwitchyardProjectionEntry(BaseModel):
    """Section 8 — Operational Switchyard Projection: reached buses grouped
    by Operational Switchyard (operational-correlation-architecture.md
    §4.1) — i.e. by (Substation, voltage level), regardless of whether a
    registered `SubstationVoltageYard` row exists for that grouping yet
    (`voltage_yard_id` is `None` when it does not — an honest verification
    finding, not an error)."""

    substation_id: uuid.UUID
    substation_mnemonic: str
    base_kv: float
    voltage_yard_id: uuid.UUID | None
    depth: int
    bus_count: int


class OperationalProjections(BaseModel):
    """Section 8 — Bus, Switchyard, and Substation projections, all three
    read directly off the one BFS depth map this traversal already computed
    (operational-correlation-architecture.md §4.2, Operational Projections).
    `substation_projection` reuses `ReachableSubstation` verbatim — the same
    DTO `traverse()` already returns — rather than a fourth, parallel shape
    for the same concept."""

    bus_projection: list[BusProjectionEntry]
    switchyard_projection: list[SwitchyardProjectionEntry]
    substation_projection: list[ReachableSubstation]


class TraversalVerificationResult(BaseModel):
    """The full Phase 7F verification response — Sections 2-8 in one
    payload, all derived from the single traversal computation performed by
    `NetworkModelService.verify_path` (no recalculation, no separate graph,
    per this phase's explicit constraint)."""

    start_substation_id: uuid.UUID
    start_voltage_yard_id: uuid.UUID | None
    topology_version_id: uuid.UUID
    path_steps: list[PathStep]
    buses: list[PathBus]
    branches: list[OperationalBranchView]
    transformers: list[OperationalTransformerView]
    statistics: TraversalStatistics
    correlation_summary: CorrelationSummary
    projections: OperationalProjections
