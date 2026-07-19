"""Findings and Publication Governance router (CLAUDE.md §14) — HTTP,
request validation, authentication only. No business logic — every
handler delegates to `PublicationTreatmentPolicyService`/
`PublicationRecordService`.

Read endpoints (`list`, `get`) require only authentication
(`get_current_user`) — module document §10: "publication-treatment-
policies — read (broad)". Mutation endpoints require
`findings_publication_governance.manage_policy` (Administrator-only, per
module document §4.1's own elevated-tier precedent — ordinary scheme
editors never change publication governance). The audit-log endpoint
requires its own separate `findings_publication_governance.view_audit`
permission, per this sprint's own explicit permission model.

Removal is a dedicated `POST .../remove` action, not a bare `DELETE` —
mirrors `stage_setting_registry`'s/`automatic_load_shedding_functionality`'s
own precedent for any lifecycle action that requires a mandatory reason
(a `DELETE` request body is unreliable across HTTP clients/proxies).

No resolution endpoint is exposed — this sprint's own instructions §13:
"Do not expose a public resolution endpoint merely because the service
has a resolution method." `resolve_publication_treatment` is an in-process
service interface for future backend consumers only.

**Publication Records (Sprint 4)** — `publication_records_router`, below.
Read-only: `evaluate_and_record_publication` is an internal service
operation, never reachable via HTTP (this sprint's own instructions §14/
§15 — "Do not expose the internal publication command directly to
ordinary API callers"; a future scheme module's own Publish endpoint
calls it in-process). List returns a summary shape (no publisher
identity, no evidence) gated by the broad `.read` permission; detail
returns the complete frozen evidence, gated by the same restrictive
`.view_audit` permission already used for policy audit history (this
sprint's own instructions §15: "use the most restrictive documented
precedent for immutable audit evidence").
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.findings_publication_governance.dependencies import (
    get_publication_record_service,
    get_publication_treatment_policy_service,
)
from app.modules.findings_publication_governance.exceptions import AppError, NotFoundError
from app.modules.findings_publication_governance.schemas import (
    FindingType,
    PolicyAuditLogPage,
    PolicyCreate,
    PolicyDetail,
    PolicyPage,
    PolicyRemoveRequest,
    PolicyUpdate,
    PublicationRecordDetail,
    PublicationRecordPage,
    PublicationTreatment,
    SchemeType,
    Severity,
)
from app.modules.findings_publication_governance.service import (
    PublicationRecordService,
    PublicationTreatmentPolicyService,
)
from app.modules.iam.dependencies import get_current_user, require_permission
from app.modules.iam.models import User

router = APIRouter(
    prefix="/publication-treatment-policies", tags=["findings-publication-governance"]
)
publication_records_router = APIRouter(
    prefix="/publication-records", tags=["findings-publication-governance"]
)


def _error_response(exc: AppError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code, detail={"code": exc.code, "message": exc.message})


@router.get("", response_model=PolicyPage)
def list_policies(
    page: int = 1,
    page_size: int = 50,
    severity: Severity | None = None,
    finding_type: FindingType | None = None,
    scheme_type: SchemeType | None = None,
    treatment: PublicationTreatment | None = None,
    service: PublicationTreatmentPolicyService = Depends(get_publication_treatment_policy_service),
    _current_user: User = Depends(get_current_user),
) -> PolicyPage:
    items = service.list_policies(
        severity=severity, finding_type=finding_type, scheme_type=scheme_type, treatment=treatment
    )
    offset = (page - 1) * page_size
    page_items = items[offset : offset + page_size]
    return PolicyPage(items=page_items, page=page, page_size=page_size, total=len(items))


@router.post("", response_model=PolicyDetail, status_code=status.HTTP_201_CREATED)
def create_policy(
    payload: PolicyCreate,
    service: PublicationTreatmentPolicyService = Depends(get_publication_treatment_policy_service),
    actor: User = Depends(require_permission("findings_publication_governance.manage_policy")),
) -> PolicyDetail:
    try:
        policy = service.create_policy(
            severity=payload.severity,
            finding_type=payload.finding_type,
            scheme_type=payload.scheme_type,
            treatment=payload.treatment,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_policy(policy.policy_id)
    assert detail is not None
    return detail


@router.get("/{policy_id}", response_model=PolicyDetail)
def get_policy(
    policy_id: uuid.UUID,
    service: PublicationTreatmentPolicyService = Depends(get_publication_treatment_policy_service),
    _current_user: User = Depends(get_current_user),
) -> PolicyDetail:
    detail = service.get_policy(policy_id)
    if detail is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="Publication Treatment Policy not found"
        )
    return detail


@router.patch("/{policy_id}", response_model=PolicyDetail)
def update_policy(
    policy_id: uuid.UUID,
    payload: PolicyUpdate,
    service: PublicationTreatmentPolicyService = Depends(get_publication_treatment_policy_service),
    actor: User = Depends(require_permission("findings_publication_governance.manage_policy")),
) -> PolicyDetail:
    try:
        service.update_treatment(
            policy_id,
            treatment=payload.treatment,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_policy(policy_id)
    assert detail is not None
    return detail


@router.post("/{policy_id}/remove", status_code=status.HTTP_204_NO_CONTENT)
def remove_policy(
    policy_id: uuid.UUID,
    payload: PolicyRemoveRequest,
    service: PublicationTreatmentPolicyService = Depends(get_publication_treatment_policy_service),
    actor: User = Depends(require_permission("findings_publication_governance.manage_policy")),
) -> None:
    try:
        service.remove_policy(
            policy_id, change_reason=payload.change_reason, actor_user_id=actor.user_id
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()


@router.get("/{policy_id}/audit-log", response_model=PolicyAuditLogPage)
def list_audit_log(
    policy_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    service: PublicationTreatmentPolicyService = Depends(get_publication_treatment_policy_service),
    _actor: User = Depends(require_permission("findings_publication_governance.view_audit")),
) -> PolicyAuditLogPage:
    items, total = service.list_audit_log(policy_id, page=page, page_size=page_size)
    return PolicyAuditLogPage(items=items, page=page, page_size=page_size, total=total)


# --- Publication Records (Sprint 4) — read-only ---------------------------------------


@publication_records_router.get("", response_model=PublicationRecordPage)
def list_publication_records(
    page: int = 1,
    page_size: int = 50,
    scheme_type: SchemeType | None = None,
    scheme_version_id: uuid.UUID | None = None,
    service: PublicationRecordService = Depends(get_publication_record_service),
    _current_user: User = Depends(get_current_user),
) -> PublicationRecordPage:
    items, total = service.list_publication_records(
        scheme_type=scheme_type, scheme_version_id=scheme_version_id, page=page, page_size=page_size
    )
    return PublicationRecordPage(items=items, page=page, page_size=page_size, total=total)


@publication_records_router.get("/{publication_record_id}", response_model=PublicationRecordDetail)
def get_publication_record(
    publication_record_id: uuid.UUID,
    service: PublicationRecordService = Depends(get_publication_record_service),
    _actor: User = Depends(require_permission("findings_publication_governance.view_audit")),
) -> PublicationRecordDetail:
    detail = service.get_publication_record(publication_record_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Publication Record not found")
    return detail
