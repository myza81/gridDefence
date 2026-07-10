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
    would just be a different yard); commissioning_date/latitude/longitude
    may be changed, as may `operational_status_id` (deletion/correction
    policy, Phase 3 follow-up — corrects a mistakenly-created switchyard by
    setting it to Entered in Error, never a hard delete).
    """

    commissioning_date: date | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    operational_status_id: int | None = None
    change_reason: str | None = None


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
    operational_status_id: int


class VoltageYardAuditLogEntry(BaseModel):
    log_id: int
    field_name: str
    old_value: str | None
    new_value: str | None
    changed_at: datetime
    changed_by: UserSummary | None
    change_reason: str | None


VoltageYardAuditLogPage = Page[VoltageYardAuditLogEntry]


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
    `commissioning_date` are (task must-fix items 1–2), as is
    `operational_status_id` (deletion/correction policy, Phase 3 follow-up
    — corrects a mistakenly-added terminal by setting it to Entered in
    Error, never a hard delete; never blocked, even if it would leave the
    parent circuit with fewer than two active terminals)."""

    breaker_number: str | None = Field(default=None, min_length=1, max_length=20)
    commissioning_date: date | None = None
    remarks: str | None = None
    operational_status_id: int | None = None


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
    operational_status_id: int
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


class CircuitTerminalIdentity(BaseModel):
    """Full engineering identity of one `CircuitTerminal` — its owning
    Substation, voltage level, and the `Circuit` it belongs to (route name
    + bay/circuit number) — composed read-only from already-owned data
    (`Circuit.circuit_name`, computed once by `get_circuit`, never
    re-derived here) for cross-module callers (e.g. the Automatic Load
    Shedding Functionality Registry, ADR-011) that need to display or
    select a specific Bay Terminal unambiguously, without duplicating any
    Equipment Registry fact as stored data of their own."""

    circuit_terminal_id: uuid.UUID
    circuit_id: uuid.UUID
    circuit_name: str
    bay_number: str
    breaker_number: str
    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    voltage_level_id: int
    voltage_level_label: str


class TransformerTerminalIdentity(BaseModel):
    """Mirrors `CircuitTerminalIdentity` for `TransformerTerminal` — the
    owning `Transformer`'s generated short name and transformer number,
    plus the terminal's own HV/LV side, composed from `get_transformer`'s
    already-computed `generated_short_name` (never re-derived here)."""

    transformer_terminal_id: uuid.UUID
    transformer_id: uuid.UUID
    generated_short_name: str
    transformer_number: str
    side: str
    breaker_number: str
    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    voltage_level_id: int
    voltage_level_label: str


class CircuitAuditLogEntry(BaseModel):
    log_id: int
    field_name: str
    old_value: str | None
    new_value: str | None
    changed_at: datetime
    changed_by: UserSummary | None
    change_reason: str | None


CircuitAuditLogPage = Page[CircuitAuditLogEntry]


# --- Transformer Registry (Phase 3.5) ------------------------------------------------


class TransformerCreate(BaseModel):
    """Substation-first (UAT correction): `substation_id` is mandatory and
    explicit — a transformer is substation-owned equipment, never modeled
    as spanning two substations. Both `hv_switchyard_id` and
    `lv_switchyard_id` must resolve to a switchyard under this same
    `substation_id` (enforced at the service layer).

    The HV/LV switchyards and their breaker numbers are supplied as
    explicit, named fields — not a generic `terminals` list like
    `CircuitCreate` — because a transformer always has exactly one HV and
    one LV terminal, never a variable-length tee-off (equipment-registry-
    module.md's Transformer Registry section; ADR-008 addendum). This is
    an API-shape choice only: the persistence layer still stores each side
    as its own `TransformerTerminal` row internally, for the same
    tertiary-extensibility reason `CircuitTerminal` uses its own table
    rather than columns on `Circuit`.
    """

    substation_id: uuid.UUID
    transformer_number: str = Field(min_length=1, max_length=20)
    hv_switchyard_id: uuid.UUID
    hv_breaker_number: str = Field(min_length=1, max_length=20)
    lv_switchyard_id: uuid.UUID
    lv_breaker_number: str = Field(min_length=1, max_length=20)
    capacity_mva: float | None = Field(default=None, gt=0)
    commissioning_date: date | None = None
    operational_status_id: int
    transformer_type: str | None = Field(default=None, max_length=50)
    manufacturer: str | None = Field(default=None, max_length=100)
    remarks: str | None = None


class TransformerUpdate(BaseModel):
    """Partial update — only supplied fields change. The switchyard each
    terminal connects to is not editable after creation (re-pointing a
    terminal is a materially different operation — mirrors
    `CircuitTerminalUpdate`'s own precedent); only each terminal's
    `breaker_number`, plus the transformer's own metadata, may change.
    """

    transformer_number: str | None = Field(default=None, min_length=1, max_length=20)
    hv_breaker_number: str | None = Field(default=None, min_length=1, max_length=20)
    lv_breaker_number: str | None = Field(default=None, min_length=1, max_length=20)
    capacity_mva: float | None = Field(default=None, gt=0)
    commissioning_date: date | None = None
    operational_status_id: int | None = None
    transformer_type: str | None = None
    manufacturer: str | None = None
    remarks: str | None = None


class TransformerTerminalSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    transformer_terminal_id: uuid.UUID
    side: str
    voltage_yard_id: uuid.UUID
    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    voltage_level_id: int
    voltage_level_label: str
    breaker_number: str


class TransformerSummary(BaseModel):
    """Row shape for the list view — Substation / Short Name / Voltage
    Transformation / Capacity / Status, per the Transformer Registry's
    canonical presentation (UAT correction: substation is now a first-class
    column, not implied indirectly via HV/LV switchyard mnemonics)."""

    transformer_id: uuid.UUID
    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    transformer_number: str
    # Computed, not stored — see Transformer's model docstring and the
    # ADR-008 addendum.
    generated_short_name: str
    hv_voltage_level_label: str
    lv_voltage_level_label: str
    capacity_mva: float | None
    operational_status_id: int


TransformerPage = Page[TransformerSummary]


class TransformerDetail(BaseModel):
    """Full detail view — includes the parent substation, resolved
    accountability, and both terminals."""

    transformer_id: uuid.UUID
    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    transformer_number: str
    generated_short_name: str
    capacity_mva: float | None
    commissioning_date: date | None
    operational_status_id: int
    transformer_type: str | None
    manufacturer: str | None
    remarks: str | None
    created_at: datetime
    updated_at: datetime
    created_by: UserSummary | None
    updated_by: UserSummary | None
    terminals: list[TransformerTerminalSummary]


class TransformerAuditLogEntry(BaseModel):
    log_id: int
    field_name: str
    old_value: str | None
    new_value: str | None
    changed_at: datetime
    changed_by: UserSummary | None
    change_reason: str | None


TransformerAuditLogPage = Page[TransformerAuditLogEntry]
