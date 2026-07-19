"""Stage Setting Registry API DTOs (CLAUDE.md A6 — API DTO layer).
Persistence models are never exposed directly (CLAUDE.md §13).

Business-rule validation (lifecycle transitions, monotonicity, scope
rules, mandatory reasons) is enforced at the service layer, not here —
mirrors every other module's own established separation between
Pydantic request-shape validation and domain business rules
(`app/shared/exceptions.py`'s own docstring).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.modules.iam.schemas import UserSummary
from app.shared.pagination import Page

SchemeType = Literal["UFLS", "UVLS"]
StageSettingSetStatus = Literal["DRAFT", "PUBLISHED", "ENTERED_IN_ERROR"]


class StageSettingSetCreate(BaseModel):
    """Creates a new Draft — `status` is never accepted from the caller;
    every new Stage Setting Set starts `DRAFT` (module document §6)."""

    scheme_type: SchemeType
    description: str | None = None


class StageSettingSetUpdate(BaseModel):
    """Draft metadata only — `scheme_type` and `status` are immutable
    through this endpoint (module document §8); lifecycle transitions have
    their own dedicated actions (publish / enter-in-error)."""

    description: str | None = None
    change_reason: str | None = None


class StageSettingSetEnterInErrorRequest(BaseModel):
    change_reason: str


class StageSettingCreate(BaseModel):
    """Creates a new stage (a `StageSetting` row) — identity, order, and
    (UVLS only) region scope. Carries no threshold or time delay: those
    belong to the stage's own `StageSettingTrigger` row(s), added
    separately once the stage exists (ADR-025) — a stage may not be
    published with zero triggers, but it may be created, briefly, with
    none, exactly mirroring the existing "a Stage Setting Set may exist
    with zero stages while still Draft" allowance one level up."""

    stage_order: int = Field(ge=1)
    region_scope_id: int | None = None
    change_reason: str | None = None


class StageSettingUpdate(BaseModel):
    """`stage_order` is never accepted here — reordering is a dedicated
    action (module document §8) to avoid a generic update silently
    reshuffling the whole set's ordering. `region_scope_id` is optional and
    partial (`exclude_unset`, mirroring
    `AutomaticLoadSheddingFunctionalityService.update_metadata`'s own
    established sentinel-default pattern): omitting it leaves it unchanged,
    while explicitly sending `"region_scope_id": null` clears it (UVLS
    reverting a stage to the grid-wide null scope). Threshold/time delay
    are never accepted here — those are trigger-level fields (ADR-025)."""

    region_scope_id: int | None = None
    change_reason: str | None = None


class StageSettingReorderRequest(BaseModel):
    """Reorders exactly one region-scope group at a time (`region_scope_id`
    identifies which group — `null` for the grid-wide/UFLS group).
    `ordered_stage_setting_ids` must be exactly that group's current
    membership, in the caller's desired new order (module document §8;
    §7 rule 4's own per-scope monotonicity grouping)."""

    region_scope_id: int | None = None
    ordered_stage_setting_ids: list[uuid.UUID]
    change_reason: str | None = None


class StageSettingTriggerCreate(BaseModel):
    """`threshold_unit` is never accepted here — it is derived from the
    grandparent Stage Setting Set's own `scheme_type` (module document
    §9). `trigger_order` is caller-supplied, unique within the parent
    stage (ADR-025)."""

    trigger_order: int = Field(ge=1)
    threshold_value: float = Field(gt=0)
    time_delay_ms: int = Field(ge=0)
    change_reason: str | None = None


class StageSettingTriggerUpdate(BaseModel):
    """`trigger_order` is never accepted here — reordering is a dedicated
    action, mirroring `StageSettingUpdate`'s own reasoning."""

    threshold_value: float | None = Field(default=None, gt=0)
    time_delay_ms: int | None = Field(default=None, ge=0)
    change_reason: str | None = None


class StageSettingTriggerReorderRequest(BaseModel):
    """Reorders every trigger of exactly one stage. `ordered_trigger_ids`
    must be exactly that stage's current trigger membership, in the
    caller's desired new order (ADR-025)."""

    ordered_trigger_ids: list[uuid.UUID]
    change_reason: str | None = None


class StageSettingTriggerDetail(BaseModel):
    stage_setting_trigger_id: uuid.UUID
    stage_setting_id: uuid.UUID
    trigger_order: int
    threshold_value: float
    threshold_unit: str
    time_delay_ms: int


class StageSettingDetail(BaseModel):
    stage_setting_id: uuid.UUID
    stage_setting_set_id: uuid.UUID
    stage_order: int
    region_scope_id: int | None
    triggers: list[StageSettingTriggerDetail]


class StageSettingSetSummary(BaseModel):
    stage_setting_set_id: uuid.UUID
    scheme_type: SchemeType
    description: str | None
    status: StageSettingSetStatus
    setting_count: int
    updated_at: datetime


StageSettingSetPage = Page[StageSettingSetSummary]


class StageSettingSetDetail(BaseModel):
    stage_setting_set_id: uuid.UUID
    scheme_type: SchemeType
    description: str | None
    status: StageSettingSetStatus
    settings: list[StageSettingDetail]
    created_at: datetime
    updated_at: datetime
    created_by: UserSummary | None
    updated_by: UserSummary | None


class StageSettingRegistryAuditLogEntry(BaseModel):
    log_id: int
    subject_type: Literal["STAGE_SETTING_SET", "STAGE_SETTING", "STAGE_SETTING_TRIGGER"]
    stage_setting_set_id: uuid.UUID | None
    stage_setting_id: uuid.UUID | None
    stage_setting_trigger_id: uuid.UUID | None
    action: str
    old_value: str | None
    new_value: str | None
    changed_at: datetime
    changed_by: UserSummary | None
    change_reason: str | None


StageSettingRegistryAuditLogPage = Page[StageSettingRegistryAuditLogEntry]
