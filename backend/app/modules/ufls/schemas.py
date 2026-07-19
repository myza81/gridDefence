"""UFLS API DTOs (CLAUDE.md A6 — API DTO layer). Persistence models are
never exposed directly. Extends `scheme_platform.schemas`' own shared
base shapes rather than duplicating the lifecycle/version fields.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from app.modules.scheme_platform.schemas import (
    SchemeVersionDetailBase,
    SchemeVersionSummaryBase,
)


# --- UflsScheme ------------------------------------------------------------------
class UflsSchemeCreateRequest(BaseModel):
    name: str
    description: str | None = None


class UflsSchemeSummary(BaseModel):
    ufls_scheme_id: uuid.UUID
    name: str
    description: str | None
    published_version_number: int | None
    latest_draft_version_number: int | None


class UflsSchemeDetail(BaseModel):
    ufls_scheme_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


# --- UflsSchemeVersion -------------------------------------------------------------
class UflsSchemeVersionCreateRequest(BaseModel):
    """Creates a new Draft. `copied_from_version_id`, if supplied, copies
    the metadata/structure per shared-defence-scheme-domain-model.md §5
    (never Publication status, acknowledgements, or historical
    findings)."""

    copied_from_version_id: uuid.UUID | None = None


class UflsSchemeVersionMetadataUpdateRequest(BaseModel):
    stage_setting_set_id: uuid.UUID | None = None
    study_reference: str | None = None
    effective_date: date | None = None
    topology_version_id: uuid.UUID | None = None
    load_snapshot_id: uuid.UUID | None = None
    engineering_remarks: str | None = None


class UflsSchemeVersionSummary(SchemeVersionSummaryBase):
    ufls_scheme_id: uuid.UUID


class UflsSchemeVersionDetail(SchemeVersionDetailBase):
    ufls_scheme_id: uuid.UUID
    stage_setting_set_id: uuid.UUID | None
    study_reference: str | None
    effective_date: date | None
    topology_version_id: uuid.UUID | None
    load_snapshot_id: uuid.UUID | None


class EnterInErrorRequest(BaseModel):
    reason: str


# --- UflsStage ---------------------------------------------------------------------
class UflsStageCreateRequest(BaseModel):
    stage_setting_id: uuid.UUID
    target_mw: Decimal | None = None
    engineering_remarks: str | None = None


class UflsStageUpdateRequest(BaseModel):
    target_mw: Decimal | None = None
    engineering_remarks: str | None = None


class UflsStageTriggerSummary(BaseModel):
    """One independent frequency-time operating criterion for this stage
    (Stage Setting Registry's own `StageSettingTrigger` — ADR-025).
    Selecting a stage gives a UFLS Scheme Version access to every trigger
    configured under it; no UFLS assignment is duplicated because a stage
    carries more than one."""

    stage_setting_trigger_id: uuid.UUID
    trigger_order: int
    threshold_value: Decimal
    threshold_unit: str
    time_delay_ms: int


class UflsStageDetail(BaseModel):
    ufls_stage_id: uuid.UUID
    scheme_version_id: uuid.UUID
    stage_setting_id: uuid.UUID
    stage_order: int
    triggers: list[UflsStageTriggerSummary]
    target_mw: Decimal | None
    engineering_remarks: str | None
    direct_assignment_count: int
    pocket_assignment_count: int


# --- Direct Assignments -------------------------------------------------------------
class UflsDirectAssignmentCreateRequest(BaseModel):
    transformer_terminal_id: uuid.UUID
    remarks: str | None = None


class UflsDirectAssignmentMoveRequest(BaseModel):
    target_ufls_stage_id: uuid.UUID


class UflsDirectAssignmentDetail(BaseModel):
    ufls_direct_assignment_id: uuid.UUID
    ufls_stage_id: uuid.UUID
    transformer_terminal_id: uuid.UUID
    substation_id: uuid.UUID
    substation_mnemonic: str
    remarks: str | None
    created_at: datetime


# --- Pocket Assignments -------------------------------------------------------------
class UflsPocketAssignmentCreateRequest(BaseModel):
    circuit_terminal_ids: list[uuid.UUID] = Field(min_length=1)
    remarks: str | None = None


class UflsPocketAssignmentDetail(BaseModel):
    ufls_pocket_assignment_id: uuid.UUID
    ufls_stage_id: uuid.UUID
    circuit_terminal_ids: list[uuid.UUID]
    remarks: str | None
    created_at: datetime


# --- Summaries (task §9) ------------------------------------------------------------
class UflsStageMwSummary(BaseModel):
    ufls_stage_id: uuid.UUID
    stage_order: int
    target_mw: Decimal | None
    direct_assignment_count: int
    pocket_assignment_count: int


class UflsVersionEngineeringSummary(BaseModel):
    """Descriptive calculations over entered/referenced data only — never
    presented as automatic engineering approval (task §9)."""

    scheme_version_id: uuid.UUID
    total_target_mw: Decimal
    stage_summaries: list[UflsStageMwSummary]
    direct_assignment_count: int
    pocket_assignment_count: int
    distinct_substation_count: int
    unresolved_finding_count: int
    sensitive_customer_finding_count: int
    alsf_finding_count: int


# --- Publication review (task §8) --------------------------------------------------
class PublicationPrerequisiteSummary(BaseModel):
    prerequisite_code: str
    passed: bool
    description: str
    affected_object_type: str | None
    affected_object_id: str | None


class PublicationReviewResult(BaseModel):
    """The read-only "would this version be publishable right now"
    preview — never itself a publish action."""

    scheme_version_id: uuid.UUID
    prerequisites: list[PublicationPrerequisiteSummary]
    all_prerequisites_passed: bool
    findings: list[dict[str, Any]]


class PublishAcknowledgementInput(BaseModel):
    finding_index: int
    justification: str


class PublishRequest(BaseModel):
    publication_event_id: uuid.UUID
    acknowledgements: list[PublishAcknowledgementInput] = Field(default_factory=list)
    remarks: str | None = None


class PublishResult(BaseModel):
    publication_record_id: uuid.UUID
    scheme_version_id: uuid.UUID
    published_at: datetime
    finding_count: int
    acknowledgement_count: int
