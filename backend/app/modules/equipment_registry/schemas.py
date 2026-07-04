"""Equipment Registry API DTOs (CLAUDE.md A6 — API DTO layer).

Persistence models are never exposed directly (CLAUDE.md §13) — every
response shape here is a distinct Pydantic schema.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.iam.schemas import UserSummary
from app.shared.pagination import Page


class VoltageYardCreate(BaseModel):
    substation_id: uuid.UUID
    voltage_level_id: int
    # Yard-level metadata (Phase 3 UAT follow-up) — optional, and
    # deliberately never on Substation; see models.py's SubstationVoltageYard
    # docstring.
    commissioning_date: date | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class VoltageYardUpdate(BaseModel):
    """Partial update of a voltage yard's metadata — the substation and
    voltage level a yard represents are not editable after creation (that
    would just be a different yard); only commissioning_date/latitude/
    longitude may be changed.
    """

    commissioning_date: date | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class VoltageYardSummary(BaseModel):
    """Row shape for terminal-selection dropdowns and the Substation Detail
    page's voltage yard list — carries enough resolved context to render
    "PKLG — 275kV" without a second round trip."""

    voltage_yard_id: uuid.UUID
    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    voltage_level_id: int
    voltage_level_label: str
    # Computed, not stored (equipment-registry-module.md §7.5a).
    display_label: str
    commissioning_date: date | None
    latitude: float | None
    longitude: float | None


class CircuitTerminalCreate(BaseModel):
    voltage_yard_id: uuid.UUID
    breaker_number: str = Field(min_length=1, max_length=20)
    commissioning_date: date | None = None
    remarks: str | None = None


class CircuitCreate(BaseModel):
    bay_number: str = Field(min_length=1, max_length=20)
    voltage_level_id: int
    line_type_id: int
    operational_status_id: int
    is_interconnector: bool = False
    remarks: str | None = None
    # A circuit must have at least two terminals to be created
    # (equipment-registry-module.md §9 rule 5) — supplied atomically so no
    # transiently-incomplete circuit is ever persisted.
    terminals: list[CircuitTerminalCreate] = Field(min_length=2)


class CircuitUpdate(BaseModel):
    """Partial update — every field optional; only supplied fields change.

    `operational_status_id` is deliberately excluded — status changes go
    through the dedicated status-change endpoint, mirroring Substation
    Registry's own separation (substation_registry/schemas.py).
    """

    bay_number: str | None = Field(default=None, min_length=1, max_length=20)
    voltage_level_id: int | None = None
    line_type_id: int | None = None
    is_interconnector: bool | None = None
    remarks: str | None = None


class CircuitStatusChange(BaseModel):
    operational_status_id: int
    change_reason: str | None = None


class CircuitTerminalAdd(BaseModel):
    """Adds one additional terminal to an existing circuit — e.g. extending
    a two-terminal line into a tee-off (equipment-registry-module.md §7.5,
    §7.13 Scenario B).
    """

    voltage_yard_id: uuid.UUID
    breaker_number: str = Field(min_length=1, max_length=20)
    commissioning_date: date | None = None
    remarks: str | None = None


class CircuitTerminalUpdate(BaseModel):
    """Partial update of an existing terminal's mutable fields — the
    voltage yard a terminal connects to is not editable after creation
    (Phase 3 UAT fix package scope); `breaker_number` and
    `commissioning_date` are (task must-fix items 1–2)."""

    breaker_number: str | None = Field(default=None, min_length=1, max_length=20)
    commissioning_date: date | None = None
    remarks: str | None = None


class CircuitTerminalSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    circuit_terminal_id: uuid.UUID
    voltage_yard_id: uuid.UUID
    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    voltage_level_id: int
    voltage_level_label: str
    breaker_number: str
    commissioning_date: date | None
    remarks: str | None
    created_at: datetime
    updated_at: datetime


class CircuitSummary(BaseModel):
    """Row shape for the list view (TanStack Table)."""

    circuit_id: uuid.UUID
    bay_number: str
    # Computed display value derived from terminal substation mnemonics +
    # bay_number (equipment-registry-module.md §7.4) — never stored, so it
    # can never drift out of sync with the terminals it names.
    circuit_name: str
    voltage_level_id: int
    line_type_id: int
    operational_status_id: int
    is_interconnector: bool
    terminal_count: int


CircuitPage = Page[CircuitSummary]


class CircuitDetail(BaseModel):
    """Full detail view — includes resolved accountability and terminals."""

    circuit_id: uuid.UUID
    bay_number: str
    circuit_name: str
    voltage_level_id: int
    line_type_id: int
    operational_status_id: int
    is_interconnector: bool
    remarks: str | None
    created_at: datetime
    updated_at: datetime
    created_by: UserSummary | None
    updated_by: UserSummary | None
    terminals: list[CircuitTerminalSummary]


class CircuitAuditLogEntry(BaseModel):
    log_id: int
    field_name: str
    old_value: str | None
    new_value: str | None
    changed_at: datetime
    changed_by: UserSummary | None
    change_reason: str | None


CircuitAuditLogPage = Page[CircuitAuditLogEntry]
