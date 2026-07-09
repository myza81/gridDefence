"""PSS/E Integration API DTOs (CLAUDE.md A6 — API DTO layer). Persistence
models are never returned directly (CLAUDE.md A9).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.iam.schemas import UserSummary
from app.modules.psse_integration.bus_classification import BusClassification
from app.modules.psse_integration.correlated_operational_model import CorrelationStatus


class ParsedBusRow(BaseModel):
    """One PSS/E bus record, exactly as the parser produced it — no
    engineering translation, no registry correlation (Operational Context
    Inspector, §8.9e). Mirrors `raw_parser.ParsedBus` field-for-field.

    `bus_classification` (Phase 7A, EDR-007 §4) is `ParsedBus`'s own
    read-only property — a naming-pattern classification derived from
    `bus_name`, never a registry correlation decision (that remains
    `service.py`'s `_match_substation_for_bus`, exposed separately via
    `matched_bus_count`/`unmatched_bus_count` on `PreviewResult`).

    `in_service`/`substation_id`/`substation_mnemonic`/`voltage_yard_id`/
    `correlation_status` (Phase 7C, Correlated Operational Model) are
    Preview-time enrichment — computed by `service.py`'s
    `_enrich_buses_for_preview`, never by the parser. All default to
    `None` so this schema remains valid for a plain, unenriched `ParsedBus`
    (e.g. a load-only case's always-empty bus list)."""

    model_config = ConfigDict(from_attributes=True)

    bus_number: int
    bus_name: str | None
    base_kv: float
    ide: int
    area: int | None
    zone: int | None
    owner: int | None
    voltage_mag: float | None
    voltage_angle: float | None
    bus_classification: BusClassification
    in_service: bool | None = None
    substation_id: uuid.UUID | None = None
    substation_mnemonic: str | None = None
    voltage_yard_id: uuid.UUID | None = None
    correlation_status: CorrelationStatus | None = None


class ParsedLoadRow(BaseModel):
    """Mirrors `raw_parser.ParsedLoad` field-for-field (§8.9e). `owner`
    (Phase 7A, EDR-007 §7.3) is PSS/E's own raw Owner field, carried
    through faithfully — never interpreted or classified here."""

    model_config = ConfigDict(from_attributes=True)

    bus_number: int
    load_id: str
    status: bool
    p_mw: float
    q_mvar: float
    owner: int | None


class ParsedGeneratorRow(BaseModel):
    """Mirrors `raw_parser.ParsedGenerator` field-for-field (§8.9e)."""

    model_config = ConfigDict(from_attributes=True)

    bus_number: int
    gen_id: str
    p_gen: float
    q_gen: float
    p_max: float | None
    p_min: float | None
    q_max: float | None
    q_min: float | None
    status: bool


class ParsedBranchRow(BaseModel):
    """Mirrors `raw_parser.ParsedBranch` field-for-field (§8.9e)."""

    model_config = ConfigDict(from_attributes=True)

    from_bus: int
    to_bus: int
    ckt_id: str
    r: float
    x: float
    b: float
    rate_a: float | None
    rate_b: float | None
    rate_c: float | None
    status: bool


class ParsedTransformerRow(BaseModel):
    """Mirrors `raw_parser.ParsedTransformer` field-for-field (§8.9e)."""

    model_config = ConfigDict(from_attributes=True)

    from_bus: int
    to_bus: int
    tertiary_bus: int | None
    ckt_id: str
    r: float
    x: float
    rate_a: float | None
    status: bool


class BusIdentityMismatchRow(BaseModel):
    """One Bus Number present on both the active topology and the
    incoming load-only case's own bus references, with a differing Bus
    Name and/or nominal voltage (Phase 7B; EDR-007 Engineering Principle
    12). Reported for engineering review — never auto-resolved."""

    bus_number: int
    active_bus_name: str | None
    incoming_bus_name: str | None
    active_base_kv: float
    incoming_base_kv: float
    mismatch_reason: str


class LoadSyncValidationSummary(BaseModel):
    """Load-only Snapshot Synchronisation validation summary (Phase 7B;
    EDR-007 Engineering Principle 12 — Bus Number is the sole correlation
    key; `operational-snapshot-architecture.md` §9 Topology Independence).
    Populated only for a `LOAD_ONLY` preview against an existing Current
    topology; `None` otherwise (a full-topology import establishes its own
    topology rather than synchronising against one)."""

    total_load_records: int
    total_distinct_load_buses: int
    matched_load_buses: int
    unmatched_load_buses: int
    missing_topology_buses: int
    identity_mismatch_buses: int
    unmatched_load_bus_numbers: list[int]
    missing_topology_bus_numbers: list[int]
    identity_mismatches: list[BusIdentityMismatchRow]


class PreviewResult(BaseModel):
    """Zero-persistence preview report (psse-integration-module.md §8.9).
    Never backed by a database row — this is a pure computation result.

    `from_attributes=True` lets the router build this directly from
    `PsseIntegrationService.preview()`'s plain `PreviewResultData` return
    value (Preview now executes synchronously, in-request — Phase 5B
    execution-model refinement; see psse-integration-module.md §8.9a),
    mirroring `BatchSummary`'s own domain-object-to-schema pattern below.

    `buses`/`branches`/`transformers`/`loads`/`generators` (Operational
    Context Inspector, §8.9e) are the same `ParsedCase` lists Preview
    already builds in memory — never re-parsed, never separately queried,
    never persisted. They exist so the Inspector can present exactly what
    the parser produced, without a second request.
    """

    model_config = ConfigDict(from_attributes=True)

    import_type: str
    # Network-size fields (Phase 6 engineering presentation refinement,
    # §8.9b) — read directly off the parsed RAW case, never recomputed or
    # separately queried. `raw_version` may be `None` (best-effort; a
    # load-only file's header is often absent, psse-integration-module.md
    # §8.7).
    raw_version: int | None
    bus_count: int
    branch_count: int
    transformer_count: int
    load_count: int
    generator_count: int
    computed_signature: str | None
    topology_reused: bool
    matched_bus_count: int
    unmatched_bus_count: int
    coverage_percent: float
    warnings: list[str]
    # Operational Context Inspector fields (§8.9e) — additive.
    source_file_reference: str
    base_mva: float | None
    buses: list[ParsedBusRow]
    branches: list[ParsedBranchRow]
    transformers: list[ParsedTransformerRow]
    loads: list[ParsedLoadRow]
    generators: list[ParsedGeneratorRow]
    # RAW File Information (Phase 7 discovery-support enhancement, §8.9f) —
    # header metadata read directly off the parsed `ParsedCase`, purely for
    # engineering visibility during Preview; never persisted, never used in
    # any engineering calculation. All three are best-effort and may be
    # `None`, same as `raw_version`.
    frequency_hz: float | None
    case_description: str | None
    raw_created: str | None
    # Load-only Snapshot Synchronisation validation (Phase 7B) — `None` for
    # FULL_TOPOLOGY_WITH_LOAD, and for LOAD_ONLY when no Current
    # TopologyVersion exists yet to synchronise against.
    sync_validation: LoadSyncValidationSummary | None = None


class FindingGroup(BaseModel):
    """One category of Commit engineering findings, aggregated (Phase 6.1
    engineering presentation refinement, §8.9d) — never a new engineering
    fact, only a grouping of the same messages `RawFileImportBatch.warnings`
    already carries, by the category each was already known to be at the
    point it was recorded."""

    category: str
    group: str
    count: int
    summary: str
    details: list[str]


class BatchSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_id: uuid.UUID
    source_file_reference: str
    imported_by: UserSummary
    import_type: str
    status: str
    computed_signature: str | None
    topology_version_id: uuid.UUID | None
    load_snapshot_id: uuid.UUID | None
    warnings: list[dict]
    fatal_error: str | None
    created_at: datetime
    # Phase 6.1 engineering presentation refinement (§8.9d) — additive.
    finding_groups: list[FindingGroup]
    # Registry matching counts: populated only for a single batch's own
    # detail view (PsseIntegrationService.get_batch_summary), left `None`
    # for list rows to avoid an extra query per row (CLAUDE.md §21).
    matched_count: int | None = None
    unmatched_count: int | None = None
    coverage_percent: float | None = None


class BatchPage(BaseModel):
    items: list[BatchSummary]
    page: int
    page_size: int
    total: int


class ActivateRequest(BaseModel):
    change_reason: str


class TopologyVersionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    topology_version_id: uuid.UUID
    signature: str
    status: str
    created_from_batch_id: uuid.UUID
    promoted_at: datetime | None
    superseded_at: datetime | None
    created_at: datetime
    bus_count: int
    branch_count: int
    transformer_count: int


class TopologyVersionPage(BaseModel):
    items: list[TopologyVersionSummary]
    page: int
    page_size: int
    total: int


class LoadSnapshotSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    load_snapshot_id: uuid.UUID
    topology_version_id: uuid.UUID
    status: str
    promoted_at: datetime | None
    superseded_at: datetime | None
    created_at: datetime
    load_count: int
    generator_count: int


class LoadSnapshotPage(BaseModel):
    items: list[LoadSnapshotSummary]
    page: int
    page_size: int
    total: int


class CurrentStatus(BaseModel):
    current_topology_version: TopologyVersionSummary | None
    current_load_snapshot: LoadSnapshotSummary | None


class EquipmentTopologyMapEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    map_id: uuid.UUID
    topology_version_id: uuid.UUID
    circuit_terminal_id: uuid.UUID
    circuit_id: uuid.UUID
    circuit_bay_number: str
    substation_mnemonic: str
    topology_branch_id: int | None
    topology_transformer_id: int | None
    match_outcome: str
    discrepancy_resolution: str | None
    resolved_by: UserSummary | None
    resolved_at: datetime | None
    created_at: datetime


class EquipmentTopologyMapPage(BaseModel):
    items: list[EquipmentTopologyMapEntry]
    page: int
    page_size: int
    total: int


class DiscrepancyResolveRequest(BaseModel):
    resolution: str  # "accepted" | "rejected"
    change_reason: str


class CircuitCorrelation(BaseModel):
    """Union-of-terminals resolution for one `Circuit` (ADR-007 §6, §10) —
    the interface Network Model calls to translate a scheme's `Circuit`
    reference into native PSS/E elements."""

    circuit_id: uuid.UUID
    topology_version_id: uuid.UUID
    terminals: list[EquipmentTopologyMapEntry]
    fully_resolved: bool


# --- Correlated Operational Model (Phase 7C) -----------------------------------
#
# Read models only — never persisted, never a new source of truth
# (operational-correlation-architecture.md §9 Separation of Ownership).
# Each combines already-owned Operational Snapshot data (`psse_integration`)
# with already-owned Engineering Registry data (Substation Registry /
# Equipment Registry), related through `correlation_status`
# (correlated_operational_model.py). This is the intended, preferred
# engineering-consumption surface for future Defence Scheme modules,
# dashboards, and analytics — mirroring `CircuitCorrelation`'s own,
# already-accepted shape above, generalized across every operational
# object type.


class OperationalBusView(BaseModel):
    """Operational Bus, correlated against Substation Registry.

    `bus_classification` (Phase 7A) and `correlation_status` are related
    but distinct: `FICTITIOUS_BUS` always yields `OUTSIDE_CURRENT_SCOPE`
    regardless of any incidental Substation match (EDR-007 §4.6/§4.7)."""

    model_config = ConfigDict(from_attributes=True)

    topology_version_id: uuid.UUID
    bus_number: int
    bus_name: str | None
    bus_classification: BusClassification
    in_service: bool | None
    substation_id: uuid.UUID | None
    substation_mnemonic: str | None
    voltage_yard_id: uuid.UUID | None
    correlation_status: CorrelationStatus


class OperationalBusViewPage(BaseModel):
    items: list[OperationalBusView]
    page: int
    page_size: int
    total: int


class BusCorrelationRefreshSummary(BaseModel):
    """Result of an explicit Bus -> Substation Registry correlation
    refresh (Phase 7D; UAT finding — correlation was previously computed
    only once, at commit time). Updates only the correlation link
    (`TopologyBus.substation_id`) against Substation Registry's current
    state — never topology facts, never RAW-derived operational data,
    never Engineering Registry records."""

    topology_version_id: uuid.UUID
    buses_processed: int
    buses_correlated: int
    buses_unmatched: int
    buses_outside_scope: int
    updated_count: int


class OperationalBranchView(BaseModel):
    """Operational Branch, correlated against the Line Connectivity
    Registry (`Circuit`/`CircuitTerminal`, via the already-existing
    `EquipmentTopologyMap`) — never a new correlation mechanism, only this
    phase's shared status vocabulary applied to it."""

    model_config = ConfigDict(from_attributes=True)

    topology_version_id: uuid.UUID
    topology_branch_id: int
    from_bus_number: int
    to_bus_number: int
    ckt_id: str
    in_service: bool | None
    circuit_id: uuid.UUID | None
    circuit_bay_number: str | None
    correlation_status: CorrelationStatus


class OperationalBranchViewPage(BaseModel):
    items: list[OperationalBranchView]
    page: int
    page_size: int
    total: int


class OperationalTransformerView(BaseModel):
    """Operational Transformer, correlated via the same
    `EquipmentTopologyMap`/Circuit mechanism as `OperationalBranchView` —
    PSS/E TRANSFORMER DATA rows already participate in `_run_matching`'s
    Circuit-terminal matching (ADR-007's "union of terminals" resolution).
    This phase does not introduce a separate correlation to
    `equipment_registry.Transformer`/`TransformerTerminal` (the
    substation-transformer registry) — no existing wiring connects PSS/E
    operational transformers to that registry, and building one would be
    new correlation logic beyond this phase's read-model scope."""

    model_config = ConfigDict(from_attributes=True)

    topology_version_id: uuid.UUID
    topology_transformer_id: int
    from_bus_number: int
    to_bus_number: int
    tertiary_bus_number: int | None
    ckt_id: str
    in_service: bool | None
    circuit_id: uuid.UUID | None
    circuit_bay_number: str | None
    correlation_status: CorrelationStatus


class OperationalTransformerViewPage(BaseModel):
    items: list[OperationalTransformerView]
    page: int
    page_size: int
    total: int


class OperationalLoadView(BaseModel):
    """Operational Load, enriched with its Bus's own Substation/Switchyard
    context (not a separate correlation target — inherited from the Bus
    it sits on) plus deliberate, always-`None` extension points for a
    future Sensitive Customer Registry (`relevance_classification`) and
    Load categorisation (`load_category`, EDR-007 §7.3's T/F/N/X-series,
    deferred per phase-7-implementation-spec.md §6/§17). `correlation_status`
    reflects Load's own primary correlation target — Sensitive Customer
    Registry — which does not exist yet (operational-correlation-
    architecture.md §4: "not yet applicable"), so it is always
    `OUTSIDE_CURRENT_SCOPE` today; this is an honest scope statement, not a
    finding requiring review."""

    model_config = ConfigDict(from_attributes=True)

    load_snapshot_id: uuid.UUID
    bus_number: int
    load_id: str
    p_mw: float
    q_mvar: float
    owner: int | None
    load_category: str | None
    substation_id: uuid.UUID | None
    substation_mnemonic: str | None
    voltage_yard_id: uuid.UUID | None
    relevance_classification: str | None
    correlation_status: CorrelationStatus


class OperationalLoadViewPage(BaseModel):
    items: list[OperationalLoadView]
    page: int
    page_size: int
    total: int


class JobStatus(BaseModel):
    job_id: str
    status: str  # queued | started | finished | failed
    result: dict | None = None
    error: str | None = None
