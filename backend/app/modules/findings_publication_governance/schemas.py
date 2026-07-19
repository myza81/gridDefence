"""Findings and Publication Governance API DTOs (CLAUDE.md A6 — API DTO
layer). Persistence models are never exposed directly (CLAUDE.md §13).

Business-rule validation (precedence-key immutability, baseline
protection, mandatory reason) is enforced at the service layer, not here —
mirrors every other module's own established separation between Pydantic
request-shape validation and domain business rules.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.modules.iam.schemas import UserSummary
from app.shared.pagination import Page

Severity = Literal["INFORMATION", "ADVISORY", "WARNING", "CRITICAL"]
FindingType = Literal[
    "MW_TOLERANCE_DEVIATION",
    "ALSF_CAPABILITY_ABSENCE",
    "SENSITIVE_CUSTOMER_ASSOCIATION",
    "TOPOLOGY_REGISTRY_CHANGE",
    "BOUNDARY_POCKET_STRUCTURAL",
    "BOUNDARY_POCKET_COMPOSITION",
    "CROSS_SCHEME_OVERLAP",
    "CRITICAL_INFRASTRUCTURE_PROTECTION",
]
SchemeType = Literal["UFLS", "UVLS", "EMLS"]
PublicationTreatment = Literal[
    "BLOCK", "ALLOW_WITH_ACKNOWLEDGEMENT", "ALLOW_WITHOUT_ACKNOWLEDGEMENT"
]


class PolicyCreate(BaseModel):
    """Creates a new policy row. `finding_type`/`scheme_type` omitted (or
    `null`) mean "applies regardless of that dimension" — a brand-new
    global severity baseline is only ever accepted here if one does not
    already exist for that severity (module document §4.2's four rows are
    already seeded by bootstrap; in ordinary operation this endpoint
    creates *overrides*)."""

    severity: Severity
    finding_type: FindingType | None = None
    scheme_type: SchemeType | None = None
    treatment: PublicationTreatment
    change_reason: str


class PolicyUpdate(BaseModel):
    """Only `treatment` may be changed — `severity`/`finding_type`/
    `scheme_type` identify *which* policy this is (module document §4;
    this sprint's own instructions §9)."""

    treatment: PublicationTreatment
    change_reason: str


class PolicyRemoveRequest(BaseModel):
    change_reason: str


class PolicyDetail(BaseModel):
    policy_id: uuid.UUID
    severity: Severity
    finding_type: FindingType | None
    scheme_type: SchemeType | None
    treatment: PublicationTreatment
    created_at: datetime
    updated_at: datetime
    created_by: UserSummary | None
    updated_by: UserSummary | None


PolicyPage = Page[PolicyDetail]


class PolicyAuditLogEntry(BaseModel):
    log_id: int
    policy_id: uuid.UUID | None
    severity: Severity
    finding_type: FindingType | None
    scheme_type: SchemeType | None
    action: Literal["created", "treatment_changed", "removed"]
    old_value: str | None
    new_value: str | None
    changed_at: datetime
    changed_by: UserSummary | None
    change_reason: str | None


PolicyAuditLogPage = Page[PolicyAuditLogEntry]


class FrozenFindingEvidence(BaseModel):
    """One frozen `Finding`, exactly as it stood at the moment of Publish
    (models.py's own `PublicationRecordFinding`)."""

    finding_index: int
    finding_type: FindingType
    severity: Severity
    source: str
    description: str
    affected_object_type: str
    affected_object_id: str
    evidence: dict | None
    resolved_treatment: PublicationTreatment
    matched_policy_id: uuid.UUID | None
    matched_policy_severity: Severity
    matched_policy_finding_type: FindingType | None
    matched_policy_scheme_type: SchemeType | None
    acknowledgement_required: bool


class FrozenPrerequisiteEvidence(BaseModel):
    prerequisite_index: int
    prerequisite_code: str
    passed: bool
    description: str
    affected_object_type: str | None
    affected_object_id: str | None
    evidence: dict | None
    source: str


class FrozenAcknowledgementEvidence(BaseModel):
    finding_index: int
    acknowledged_by: UserSummary | None
    acknowledged_at: datetime
    justification: str


class PublicationRecordSummary(BaseModel):
    """List shape — deliberately omits publisher identity and full
    evidence (this sprint's own instructions §15: reuse the most
    restrictive documented precedent for immutable audit evidence; full
    detail is gated behind a separate, more restrictive permission)."""

    publication_record_id: uuid.UUID
    scheme_type: SchemeType
    scheme_version_id: uuid.UUID
    published_at: datetime
    finding_count: int


PublicationRecordPage = Page[PublicationRecordSummary]


class PublicationRecordDetail(BaseModel):
    """Full immutable evidence — every field required to reconstruct why
    publication was allowed (module document §2.1), gated behind
    `findings_publication_governance.view_audit`."""

    publication_record_id: uuid.UUID
    publication_event_id: uuid.UUID
    scheme_type: SchemeType
    scheme_version_id: uuid.UUID
    published_by: UserSummary | None
    published_at: datetime
    topology_version_id: uuid.UUID | None
    load_snapshot_id: uuid.UUID | None
    remarks: str | None
    evidence_schema_version: int
    findings: list[FrozenFindingEvidence]
    prerequisites: list[FrozenPrerequisiteEvidence]
    acknowledgements: list[FrozenAcknowledgementEvidence]
