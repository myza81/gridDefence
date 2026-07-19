"""Engineering Parameter Configuration API DTOs (CLAUDE.md A6 — API DTO
layer). Persistence models are never exposed directly (CLAUDE.md §13).

Business-rule validation (mandatory `change_reason`, per-`parameter_key`
value validation) is enforced at the service layer, not here — mirrors
every other module's own established separation between Pydantic
request-shape validation and domain business rules
(`app/shared/exceptions.py`'s own docstring).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.iam.schemas import UserSummary
from app.shared.pagination import Page


class EngineeringParameterSetRequest(BaseModel):
    """Request body for `PUT /engineering-parameters/{key}` — an upsert:
    creates the parameter if it does not yet exist, otherwise updates its
    current value (module document §8's "current-value-plus-audit-log").
    `change_reason` is mandatory in both cases — even the very first value
    a parameter is ever given is an audited engineering decision, not an
    unreasoned default."""

    value: str
    unit: str | None = Field(default=None, max_length=50)
    description: str | None = None
    change_reason: str


class EngineeringParameterDetail(BaseModel):
    parameter_key: str
    value: str
    unit: str | None
    description: str | None
    updated_at: datetime
    updated_by: UserSummary | None


class EngineeringParameterAuditLogEntry(BaseModel):
    log_id: int
    parameter_key: str
    old_value: str | None
    new_value: str | None
    changed_at: datetime
    changed_by: UserSummary | None
    change_reason: str | None


EngineeringParameterAuditLogPage = Page[EngineeringParameterAuditLogEntry]
