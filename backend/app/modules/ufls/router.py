"""UFLS router (CLAUDE.md §14) — HTTP, request validation, authentication
only. No business logic — every handler delegates to `UflsService`.

Read endpoints require only authentication (`get_current_user`), mirroring
Stage Setting Registry's own precedent for engineering registry/scheme
data. Draft-editing endpoints (scheme/Draft creation, stage and
assignment mutation, Draft metadata update/deletion) require
`ufls.manage`. `publish` and `enter-in-error` each require their own
dedicated, more privileged permission — mirroring
stage_setting_registry.router's own "a user who may edit a Draft is not
assumed to also be trusted to publish or correct it" precedent
(bootstrap.py).
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.findings_publication_governance.publication import AcknowledgementInput
from app.modules.iam.dependencies import get_current_user, require_permission
from app.modules.iam.models import User
from app.modules.ufls.dependencies import get_ufls_service
from app.modules.ufls.exceptions import AppError, NotFoundError
from app.modules.ufls.schemas import (
    EnterInErrorRequest,
    PublicationReviewResult,
    PublishRequest,
    PublishResult,
    UflsDirectAssignmentCreateRequest,
    UflsDirectAssignmentDetail,
    UflsDirectAssignmentMoveRequest,
    UflsPocketAssignmentCreateRequest,
    UflsPocketAssignmentDetail,
    UflsSchemeCreateRequest,
    UflsSchemeDetail,
    UflsSchemeSummary,
    UflsSchemeVersionCreateRequest,
    UflsSchemeVersionDetail,
    UflsSchemeVersionMetadataUpdateRequest,
    UflsSchemeVersionSummary,
    UflsStageCreateRequest,
    UflsStageDetail,
    UflsStageUpdateRequest,
    UflsVersionEngineeringSummary,
)
from app.modules.ufls.service import UflsService

router = APIRouter(prefix="/ufls", tags=["ufls"])


def _error_response(exc: AppError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code, detail={"code": exc.code, "message": exc.message})


# --- UflsScheme ------------------------------------------------------------------
@router.get("/schemes", response_model=list[UflsSchemeSummary])
def list_schemes(
    service: UflsService = Depends(get_ufls_service),
    _current_user: User = Depends(get_current_user),
) -> list[UflsSchemeSummary]:
    return [service.to_scheme_summary(s) for s in service.list_schemes()]


@router.post("/schemes", response_model=UflsSchemeDetail, status_code=status.HTTP_201_CREATED)
def create_scheme(
    payload: UflsSchemeCreateRequest,
    service: UflsService = Depends(get_ufls_service),
    actor: User = Depends(require_permission("ufls.manage")),
) -> UflsSchemeDetail:
    try:
        scheme = service.create_scheme(
            name=payload.name, description=payload.description, actor_user_id=actor.user_id
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()
    return service.to_scheme_detail(scheme)


@router.get("/schemes/{ufls_scheme_id}", response_model=UflsSchemeDetail)
def get_scheme(
    ufls_scheme_id: uuid.UUID,
    service: UflsService = Depends(get_ufls_service),
    _current_user: User = Depends(get_current_user),
) -> UflsSchemeDetail:
    try:
        scheme = service.get_scheme(ufls_scheme_id)
    except AppError as exc:
        raise _error_response(exc) from exc
    return service.to_scheme_detail(scheme)


@router.get("/schemes/{ufls_scheme_id}/versions", response_model=list[UflsSchemeVersionSummary])
def list_scheme_versions(
    ufls_scheme_id: uuid.UUID,
    service: UflsService = Depends(get_ufls_service),
    _current_user: User = Depends(get_current_user),
) -> list[UflsSchemeVersionSummary]:
    try:
        versions = service.list_scheme_versions(ufls_scheme_id)
    except AppError as exc:
        raise _error_response(exc) from exc
    return [service.to_version_summary(v) for v in versions]


@router.post(
    "/schemes/{ufls_scheme_id}/versions",
    response_model=UflsSchemeVersionDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_draft_version(
    ufls_scheme_id: uuid.UUID,
    payload: UflsSchemeVersionCreateRequest,
    service: UflsService = Depends(get_ufls_service),
    actor: User = Depends(require_permission("ufls.manage")),
) -> UflsSchemeVersionDetail:
    try:
        version = service.create_draft_version(
            ufls_scheme_id,
            copied_from_version_id=payload.copied_from_version_id,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()
    return service.to_version_detail(version)


# --- UflsSchemeVersion -------------------------------------------------------------
@router.get("/versions/{version_id}", response_model=UflsSchemeVersionDetail)
def get_version(
    version_id: uuid.UUID,
    service: UflsService = Depends(get_ufls_service),
    _current_user: User = Depends(get_current_user),
) -> UflsSchemeVersionDetail:
    try:
        version = service.get_version(version_id)
    except AppError as exc:
        raise _error_response(exc) from exc
    return service.to_version_detail(version)


@router.patch("/versions/{version_id}", response_model=UflsSchemeVersionDetail)
def update_version_metadata(
    version_id: uuid.UUID,
    payload: UflsSchemeVersionMetadataUpdateRequest,
    service: UflsService = Depends(get_ufls_service),
    actor: User = Depends(require_permission("ufls.manage")),
) -> UflsSchemeVersionDetail:
    try:
        version = service.update_version_metadata(
            version_id,
            stage_setting_set_id=payload.stage_setting_set_id,
            study_reference=payload.study_reference,
            effective_date=payload.effective_date,
            topology_version_id=payload.topology_version_id,
            load_snapshot_id=payload.load_snapshot_id,
            engineering_remarks=payload.engineering_remarks,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()
    return service.to_version_detail(version)


@router.delete("/versions/{version_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_draft_version(
    version_id: uuid.UUID,
    service: UflsService = Depends(get_ufls_service),
    actor: User = Depends(require_permission("ufls.manage")),
) -> None:
    try:
        service.delete_draft_version(version_id, actor_user_id=actor.user_id)
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()


@router.post("/versions/{version_id}/enter-in-error", response_model=UflsSchemeVersionDetail)
def enter_in_error(
    version_id: uuid.UUID,
    payload: EnterInErrorRequest,
    service: UflsService = Depends(get_ufls_service),
    actor: User = Depends(require_permission("ufls.enter_in_error")),
) -> UflsSchemeVersionDetail:
    try:
        version = service.enter_in_error(
            version_id, reason=payload.reason, actor_user_id=actor.user_id
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()
    return service.to_version_detail(version)


# --- UflsStage ---------------------------------------------------------------------
@router.get("/versions/{version_id}/stages", response_model=list[UflsStageDetail])
def list_stages(
    version_id: uuid.UUID,
    service: UflsService = Depends(get_ufls_service),
    _current_user: User = Depends(get_current_user),
) -> list[UflsStageDetail]:
    try:
        stages = service.list_stages(version_id)
    except AppError as exc:
        raise _error_response(exc) from exc
    return [service.to_stage_detail(s) for s in stages]


@router.post(
    "/versions/{version_id}/stages",
    response_model=UflsStageDetail,
    status_code=status.HTTP_201_CREATED,
)
def add_stage(
    version_id: uuid.UUID,
    payload: UflsStageCreateRequest,
    service: UflsService = Depends(get_ufls_service),
    actor: User = Depends(require_permission("ufls.manage")),
) -> UflsStageDetail:
    try:
        stage = service.add_stage(
            version_id,
            stage_setting_id=payload.stage_setting_id,
            target_mw=payload.target_mw,
            engineering_remarks=payload.engineering_remarks,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()
    return service.to_stage_detail(stage)


@router.patch("/stages/{ufls_stage_id}", response_model=UflsStageDetail)
def update_stage(
    ufls_stage_id: uuid.UUID,
    payload: UflsStageUpdateRequest,
    service: UflsService = Depends(get_ufls_service),
    actor: User = Depends(require_permission("ufls.manage")),
) -> UflsStageDetail:
    try:
        stage = service.update_stage(
            ufls_stage_id,
            target_mw=payload.target_mw,
            engineering_remarks=payload.engineering_remarks,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()
    return service.to_stage_detail(stage)


@router.delete("/stages/{ufls_stage_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_stage(
    ufls_stage_id: uuid.UUID,
    service: UflsService = Depends(get_ufls_service),
    actor: User = Depends(require_permission("ufls.manage")),
) -> None:
    try:
        service.remove_stage(ufls_stage_id, actor_user_id=actor.user_id)
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()


# --- Direct Assignments -------------------------------------------------------------
@router.get(
    "/stages/{ufls_stage_id}/direct-assignments", response_model=list[UflsDirectAssignmentDetail]
)
def list_direct_assignments(
    ufls_stage_id: uuid.UUID,
    service: UflsService = Depends(get_ufls_service),
    _current_user: User = Depends(get_current_user),
) -> list[UflsDirectAssignmentDetail]:
    try:
        assignments = service.list_direct_assignments(ufls_stage_id)
    except AppError as exc:
        raise _error_response(exc) from exc
    return [service.to_direct_assignment_detail(a) for a in assignments]


@router.post(
    "/stages/{ufls_stage_id}/direct-assignments",
    response_model=UflsDirectAssignmentDetail,
    status_code=status.HTTP_201_CREATED,
)
def add_direct_assignment(
    ufls_stage_id: uuid.UUID,
    payload: UflsDirectAssignmentCreateRequest,
    service: UflsService = Depends(get_ufls_service),
    actor: User = Depends(require_permission("ufls.manage")),
) -> UflsDirectAssignmentDetail:
    try:
        assignment = service.add_direct_assignment(
            ufls_stage_id,
            transformer_terminal_id=payload.transformer_terminal_id,
            remarks=payload.remarks,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()
    return service.to_direct_assignment_detail(assignment)


@router.patch("/direct-assignments/{assignment_id}/move", response_model=UflsDirectAssignmentDetail)
def move_direct_assignment(
    assignment_id: uuid.UUID,
    payload: UflsDirectAssignmentMoveRequest,
    service: UflsService = Depends(get_ufls_service),
    actor: User = Depends(require_permission("ufls.manage")),
) -> UflsDirectAssignmentDetail:
    try:
        assignment = service.move_direct_assignment(
            assignment_id,
            target_ufls_stage_id=payload.target_ufls_stage_id,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()
    return service.to_direct_assignment_detail(assignment)


@router.delete("/direct-assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_direct_assignment(
    assignment_id: uuid.UUID,
    service: UflsService = Depends(get_ufls_service),
    actor: User = Depends(require_permission("ufls.manage")),
) -> None:
    try:
        service.remove_direct_assignment(assignment_id, actor_user_id=actor.user_id)
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()


# --- Pocket Assignments -------------------------------------------------------------
@router.get(
    "/stages/{ufls_stage_id}/pocket-assignments", response_model=list[UflsPocketAssignmentDetail]
)
def list_pocket_assignments(
    ufls_stage_id: uuid.UUID,
    service: UflsService = Depends(get_ufls_service),
    _current_user: User = Depends(get_current_user),
) -> list[UflsPocketAssignmentDetail]:
    try:
        assignments = service.list_pocket_assignments(ufls_stage_id)
    except AppError as exc:
        raise _error_response(exc) from exc
    return [service.to_pocket_assignment_detail(a) for a in assignments]


@router.post(
    "/stages/{ufls_stage_id}/pocket-assignments",
    response_model=UflsPocketAssignmentDetail,
    status_code=status.HTTP_201_CREATED,
)
def add_pocket_assignment(
    ufls_stage_id: uuid.UUID,
    payload: UflsPocketAssignmentCreateRequest,
    service: UflsService = Depends(get_ufls_service),
    actor: User = Depends(require_permission("ufls.manage")),
) -> UflsPocketAssignmentDetail:
    try:
        assignment = service.add_pocket_assignment(
            ufls_stage_id,
            circuit_terminal_ids=payload.circuit_terminal_ids,
            remarks=payload.remarks,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()
    return service.to_pocket_assignment_detail(assignment)


@router.delete("/pocket-assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_pocket_assignment(
    assignment_id: uuid.UUID,
    service: UflsService = Depends(get_ufls_service),
    actor: User = Depends(require_permission("ufls.manage")),
) -> None:
    try:
        service.remove_pocket_assignment(assignment_id, actor_user_id=actor.user_id)
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()


# --- Engineering summaries and Publication (task §9, §8) ---------------------------
@router.get("/versions/{version_id}/summary", response_model=UflsVersionEngineeringSummary)
def get_engineering_summary(
    version_id: uuid.UUID,
    service: UflsService = Depends(get_ufls_service),
    _current_user: User = Depends(get_current_user),
) -> UflsVersionEngineeringSummary:
    try:
        return service.get_engineering_summary(version_id)
    except AppError as exc:
        raise _error_response(exc) from exc


@router.get("/versions/{version_id}/publication-review", response_model=PublicationReviewResult)
def get_publication_review(
    version_id: uuid.UUID,
    service: UflsService = Depends(get_ufls_service),
    _current_user: User = Depends(get_current_user),
) -> PublicationReviewResult:
    try:
        return service.to_publication_review_result(version_id)
    except AppError as exc:
        raise _error_response(exc) from exc


@router.post("/versions/{version_id}/publish", response_model=PublishResult)
def publish(
    version_id: uuid.UUID,
    payload: PublishRequest,
    service: UflsService = Depends(get_ufls_service),
    actor: User = Depends(require_permission("ufls.publish")),
) -> PublishResult:
    try:
        publication_result = service.publish(
            version_id,
            publication_event_id=payload.publication_event_id,
            acknowledgements=[
                AcknowledgementInput(
                    finding_index=a.finding_index,
                    acknowledged_by_user_id=actor.user_id,
                    justification=a.justification,
                )
                for a in payload.acknowledgements
            ],
            remarks=payload.remarks,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()
    return service.to_publish_result(publication_result)
