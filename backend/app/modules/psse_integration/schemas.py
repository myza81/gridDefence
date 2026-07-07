"""PSS/E Integration API DTOs (CLAUDE.md A6 — API DTO layer). Persistence
models are never returned directly (CLAUDE.md A9).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.iam.schemas import UserSummary


class ParsedBusRow(BaseModel):
    """One PSS/E bus record, exactly as the parser produced it — no
    engineering translation, no registry correlation (Operational Context
    Inspector, §8.9e). Mirrors `raw_parser.ParsedBus` field-for-field."""

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


class ParsedLoadRow(BaseModel):
    """Mirrors `raw_parser.ParsedLoad` field-for-field (§8.9e)."""

    model_config = ConfigDict(from_attributes=True)

    bus_number: int
    load_id: str
    status: bool
    p_mw: float
    q_mvar: float


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


class JobStatus(BaseModel):
    job_id: str
    status: str  # queued | started | finished | failed
    result: dict | None = None
    error: str | None = None
