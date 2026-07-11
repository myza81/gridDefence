"""Sensitive Customer Registry API DTOs (CLAUDE.md A6 — API DTO layer).
Persistence models are never exposed directly (CLAUDE.md §13).

Business-rule validation (reference-data existence/activation, reassignment
reason requirements, lifecycle transition legality) is enforced at the
service layer, not here — mirrors every other module's own separation
between Pydantic request-shape validation and domain business rules.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.iam.schemas import UserSummary
from app.shared.pagination import Page

LifecycleStatus = Literal["ACTIVE", "ARCHIVED", "ENTERED_IN_ERROR"]

# Correction 4, generalised by ADR-013 — three independently-surfaced
# facts, never conflated with `lifecycle_status` (implementation spec §9):
#   NOT_ASSIGNED — no Transformer Terminal is currently associated (facility
#                  aggregate only — never used on a single association row,
#                  since a row's existence means it was assigned).
#   RESOLVED     — the associated terminal is set and Equipment Registry
#                  currently resolves it.
#   UNRESOLVED   — the associated terminal is set but Equipment Registry
#                  could not resolve it right now (stale/archived/
#                  decommissioned/entered-in-error terminal). The facility
#                  is never omitted from any read as a result — this field
#                  surfaces the condition instead.
#
# Since ADR-013, a facility may have several associations, each
# independently RESOLVED or UNRESOLVED (see
# `SensitiveFacilityTerminalAssociation`). The facility-level aggregate
# (used on `SensitiveFacilitySummary`/`SensitiveFacilityDetail` for list
# filtering) is: NOT_ASSIGNED if there are no associations; RESOLVED if
# every association is resolved; UNRESOLVED if at least one is not.
TransformerTerminalResolution = Literal["NOT_ASSIGNED", "RESOLVED", "UNRESOLVED"]

# Per-association resolution never reports NOT_ASSIGNED — a row only
# exists because it was assigned.
AssociationResolution = Literal["RESOLVED", "UNRESOLVED"]


class SensitiveFacilityTerminalAssociation(BaseModel):
    """One currently active supply-point association (ADR-013). Substation/
    voltage/transformer/side identity is reported as separate fields —
    never a pre-composed display string (CLAUDE.md A12) — mirroring the
    facility-level fields this replaces. All identity fields are `None`
    only when `resolution` is `UNRESOLVED`."""

    transformer_terminal_id: uuid.UUID
    resolution: AssociationResolution
    substation_id: uuid.UUID | None
    substation_mnemonic: str | None
    substation_official_name: str | None
    voltage_level_label: str | None
    bay_label: str | None
    side: str | None


# --- Reference data: FacilitySector / SensitivityClassification -------------


class FacilitySectorCreate(BaseModel):
    code: str = Field(max_length=50)
    label: str = Field(max_length=150)
    sort_order: int = 0
    description: str | None = None


class FacilitySectorUpdate(BaseModel):
    """`code` is deliberately absent — immutable after creation
    (implementation spec §8)."""

    label: str | None = Field(default=None, max_length=150)
    sort_order: int | None = None
    description: str | None = Field(default=None)
    is_active: bool | None = None
    change_reason: str | None = None


class FacilitySectorSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    label: str
    sort_order: int
    description: str | None
    is_active: bool


class SensitivityClassificationCreate(BaseModel):
    code: str = Field(max_length=50)
    label: str = Field(max_length=150)
    sort_order: int = 0
    description: str | None = None


class SensitivityClassificationUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=150)
    sort_order: int | None = None
    description: str | None = Field(default=None)
    is_active: bool | None = None
    change_reason: str | None = None


class SensitivityClassificationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    label: str
    sort_order: int
    description: str | None
    is_active: bool


# --- SensitiveFacility --------------------------------------------------------


class SensitiveFacilityCreate(BaseModel):
    name: str = Field(max_length=255)
    facility_sector_id: int
    sensitivity_classification_id: int
    transformer_terminal_ids: list[uuid.UUID] = Field(default_factory=list)
    remarks: str | None = None


class SensitiveFacilityUpdate(BaseModel):
    """Partial metadata update — never `lifecycle_status` (dedicated,
    reasoned lifecycle endpoints exist for that, module document §8;
    implementation spec §10) and, since ADR-013, never Transformer
    Terminal associations either — those are edited exclusively through
    `SensitiveFacilityTerminalsUpdate` / `PUT .../terminals` below, since a
    set-replacement operation does not fit this partial-field-update
    shape's per-field `_UNSET` semantics."""

    name: str | None = Field(default=None, max_length=255)
    facility_sector_id: int | None = None
    sensitivity_classification_id: int | None = None
    remarks: str | None = None
    change_reason: str | None = None


class SensitiveFacilityTerminalsUpdate(BaseModel):
    """Replaces the full set of a facility's currently associated
    Transformer Terminals in one call (ADR-013 decision 3). The service
    layer diffs this target set against the current set and writes one
    audit row per actual addition or removal — never one opaque bulk
    event. `change_reason` is mandatory whenever the set actually changes
    (continuing Correction 5's reassignment-reason discipline); a no-op
    call (target set equals current set) requires no reason."""

    transformer_terminal_ids: list[uuid.UUID]
    change_reason: str | None = None


class SensitiveFacilityLifecycleRequest(BaseModel):
    """Used by the archive / reactivate / entered-in-error endpoints. A
    non-empty `change_reason` is required for every transition (module
    document §10) — enforced at the service layer, not by Pydantic, so the
    same structured-error shape is used as every other business rule."""

    change_reason: str | None = None


class SensitiveFacilitySummary(BaseModel):
    """Row shape for the list view. `transformer_terminal_resolution`
    (facility-level aggregate, ADR-013) and `lifecycle_status` are always
    reported independently — a facility is never omitted from this shape
    merely because a Transformer Terminal cannot currently be resolved
    (Correction 4). `transformer_terminals` always carries the full
    per-association detail — the aggregate is a filtering convenience,
    never a substitute for it (Correction 4's "never silently omit or
    collapse" rule, applied per association since ADR-013)."""

    id: uuid.UUID
    name: str
    facility_sector: FacilitySectorSummary
    sensitivity_classification: SensitivityClassificationSummary
    transformer_terminals: list[SensitiveFacilityTerminalAssociation]
    transformer_terminal_resolution: TransformerTerminalResolution
    lifecycle_status: LifecycleStatus
    updated_at: datetime


SensitiveFacilityPage = Page[SensitiveFacilitySummary]


class SensitiveFacilityDetail(BaseModel):
    id: uuid.UUID
    name: str
    facility_sector: FacilitySectorSummary
    sensitivity_classification: SensitivityClassificationSummary
    transformer_terminals: list[SensitiveFacilityTerminalAssociation]
    transformer_terminal_resolution: TransformerTerminalResolution
    lifecycle_status: LifecycleStatus
    remarks: str | None
    created_at: datetime
    updated_at: datetime
    created_by: UserSummary | None
    updated_by: UserSummary | None


class SensitiveFacilityAuditLogEntry(BaseModel):
    log_id: int
    field_name: str
    old_value: str | None
    new_value: str | None
    changed_at: datetime
    changed_by: UserSummary | None
    change_reason: str | None


SensitiveFacilityAuditLogPage = Page[SensitiveFacilityAuditLogEntry]


# --- Batch lookup / summary (implementation spec §9, §11) -------------------


class BatchLookupRequest(BaseModel):
    """`POST`, not `GET` — a boundary-pocket terminal set can exceed a safe
    URL query-string length (implementation spec §10). Bounded at 2000
    entries — generous headroom over the "500+ realistic boundary-pocket
    size" figure the implementation spec exercises (§9), while still
    rejecting a pathologically large request body outright rather than
    accepting an unbounded list. An empty list is explicitly allowed and
    returns an empty mapping (service-layer behaviour, tested) rather than
    a validation error — a caller that resolved zero terminal IDs is a
    legitimate, non-exceptional case."""

    transformer_terminal_ids: list[uuid.UUID] = Field(max_length=2000)


class BatchLookupResponse(BaseModel):
    """`results` maps every requested Transformer Terminal ID to its
    (possibly empty) list of Active facilities — completeness-by-
    construction, no partial-failure mode (implementation spec §9)."""

    results: dict[uuid.UUID, list[SensitiveFacilitySummary]]


class SensitiveFacilitySummaryCounts(BaseModel):
    """Descriptive-only dashboard metrics (implementation spec §11) — never
    implies scheme eligibility, compliance, blocking, or operational
    safety."""

    active_count: int
    archived_count: int
    entered_in_error_count: int
    by_sector: dict[str, int]
    by_sensitivity_classification: dict[str, int]
    unresolved_terminal_count: int
