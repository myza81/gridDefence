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
    voltage_level_id: int
    region_id: int
    state_id: int
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
    voltage_level_id: int | None = None
    region_id: int | None = None
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
    voltage_level_id: int
    region_id: int
    state_id: int
    grid_owner_id: int
    operational_status_id: int
    psse_bus_number: int | None


SubstationPage = Page[SubstationSummary]


class SubstationDetail(BaseModel):
    """Full detail view — includes resolved accountability (getUser,
    iam-module.md §13), never raw UUIDs alone.
    """

    model_config = ConfigDict(from_attributes=True)

    substation_id: uuid.UUID
    mnemonic: str
    official_name: str
    voltage_level_id: int
    region_id: int
    state_id: int
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
