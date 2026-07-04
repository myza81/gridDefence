"""Read-only API DTOs for Core Platform reference/lookup tables
(CLAUDE.md A6 — API DTO layer). No write schemas: reference data management
is a future, admin-only surface (substation-registry.md §13), not built here.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class VoltageLevelSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    voltage_level_id: int
    label: str
    nominal_kv: float
    sort_order: int


class RegionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    region_id: int
    code: str
    label: str


class StateSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state_id: int
    code: str
    label: str


class GridOwnerSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    grid_owner_id: int
    code: str
    label: str


class OperationalStatusSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    operational_status_id: int
    code: str
    label: str
    is_terminal: bool


class LineTypeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    line_type_id: int
    code: str
    label: str


class TransformerBreakerNumberingConventionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    convention_id: int
    hv_voltage_level_id: int
    lv_voltage_level_id: int
    side: str
    pattern: str | None
    is_standard: bool
    notes: str | None
