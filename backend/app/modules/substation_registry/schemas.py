"""Substation Registry API DTOs (CLAUDE.md A6 — API DTO layer).

Persistence models are never exposed directly (CLAUDE.md §13) — every
response shape here is a distinct Pydantic schema.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.iam.schemas import UserSummary
from app.shared.pagination import Page


class SubstationCreate(BaseModel):
    mnemonic: str = Field(min_length=1, max_length=10)
    official_name: str = Field(min_length=1, max_length=150)
    region_id: int
    # GM Zone — organizational maintenance responsibility, independent of
    # region_id (substation-registry.md GM Zone status update). Required,
    # exactly like region_id — every Substation shall reference exactly
    # one GM Zone.
    gm_zone_id: int
    # State is an administrative attribute, not part of engineering
    # identity — optional (ADR-026). Omit it, or send an explicit value;
    # both are valid at creation.
    state_id: int | None = None
    grid_owner_id: int
    operational_status_id: int
    psse_bus_number: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    commissioned_date: date | None = None
    remarks: str | None = None


class SubstationUpdate(BaseModel):
    """Partial update — every field optional; only supplied fields change.

    A `mnemonic` change is handled specially by the service layer (an alias
    record is written for the retired value, never overwritten in place —
    substation-registry.md §8 rule 1).
    """

    mnemonic: str | None = Field(default=None, min_length=1, max_length=10)
    official_name: str | None = Field(default=None, min_length=1, max_length=150)
    region_id: int | None = None
    gm_zone_id: int | None = None
    # State is optional (ADR-026). Because the router forwards only
    # client-supplied fields (`model_dump(exclude_unset=True)`), the service
    # distinguishes "state_id omitted → leave unchanged" from "state_id sent
    # as null → clear it" and "state_id sent as an int → set it". A null is
    # therefore a valid, meaningful value here (unlike region/gm_zone/
    # grid_owner, which remain never-null).
    state_id: int | None = None
    grid_owner_id: int | None = None
    psse_bus_number: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    commissioned_date: date | None = None
    remarks: str | None = None


class SubstationStatusChange(BaseModel):
    operational_status_id: int
    change_reason: str | None = None


class SubstationSummary(BaseModel):
    """Row shape for the list view (TanStack Table)."""

    model_config = ConfigDict(from_attributes=True)

    substation_id: uuid.UUID
    mnemonic: str
    official_name: str
    region_id: int
    gm_zone_id: int
    # State is optional (ADR-026) — the field is always present in the
    # response, but is `null` for a substation that has no State assigned.
    state_id: int | None
    grid_owner_id: int
    operational_status_id: int
    psse_bus_number: int | None


SubstationPage = Page[SubstationSummary]


class SubstationMapFeature(BaseModel):
    """Lightweight geographic projection of one substation (Phase E.1 map).

    The authoritative substation coordinate is `Substation.latitude/longitude`
    (Substation Registry owns geography — ADR-008; switchyard coordinates are
    per-yard GIS metadata and are NOT substation geography). Because the DB
    enforces the geolocation pair + range check, a persisted coordinate is
    either both-present-and-valid or both-null, so `coordinate_status` is
    `present` or `missing` (incomplete/invalid cannot persist).
    """

    substation_id: uuid.UUID
    mnemonic: str
    official_name: str
    operational_status_id: int
    region_id: int
    gm_zone_id: int
    state_id: int | None
    grid_owner_id: int
    latitude: float | None
    longitude: float | None
    coordinate_status: str  # "present" | "missing"


class SubstationMapResponse(BaseModel):
    """All substations matching the (registry-shared) filters, unpaginated,
    plus mapped/missing coordinate counts so the map can honestly account for
    records without usable coordinates rather than silently dropping them."""

    items: list[SubstationMapFeature]
    mapped_count: int
    missing_coordinate_count: int
    total: int


class SubstationDetail(BaseModel):
    """Full detail view — includes resolved accountability (getUser,
    iam-module.md §13), never raw UUIDs alone.
    """

    model_config = ConfigDict(from_attributes=True)

    substation_id: uuid.UUID
    mnemonic: str
    official_name: str
    region_id: int
    gm_zone_id: int
    # State is optional (ADR-026) — `null` when no State is assigned.
    state_id: int | None
    grid_owner_id: int
    operational_status_id: int
    psse_bus_number: int | None
    latitude: float | None
    longitude: float | None
    commissioned_date: date | None
    remarks: str | None
    created_at: datetime
    updated_at: datetime
    created_by: UserSummary | None
    updated_by: UserSummary | None


class SubstationAliasSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    alias_id: int
    alias_mnemonic: str | None
    alias_name: str | None
    valid_from: datetime
    valid_to: datetime | None


class SubstationAuditLogEntry(BaseModel):
    log_id: int
    field_name: str
    old_value: str | None
    new_value: str | None
    changed_at: datetime
    changed_by: UserSummary | None
    change_reason: str | None


SubstationAuditLogPage = Page[SubstationAuditLogEntry]
