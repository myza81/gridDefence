"""Automatic Load Shedding Functionality Registry router (CLAUDE.md §14) —
HTTP, request validation, authentication only. No business logic — every
handler delegates to `AutomaticLoadSheddingFunctionalityService`.

Read endpoints require only authentication (`get_current_user`), mirroring
Equipment Registry's and Substation Registry's own precedent for
engineering reference data — `automatic_load_shedding_functionality.read`
is still registered as catalog data (bootstrap.py) for possible future
finer-grained use. Write endpoints (create/update/decommission) require
`automatic_load_shedding_functionality.write`. Status Model Refinement
(engineering refinement) removed the `/activate` and `/deactivate`
endpoints entirely — Available/Assigned are now always computed, never
manually set, and `/decommission` is the only lifecycle transition left.

Route ordering: `/candidates` and `/capability-check` are declared before
`/{functionality_id}` so FastAPI does not attempt to parse either literal
segment as a UUID path parameter.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.automatic_load_shedding_functionality.dependencies import (
    get_automatic_load_shedding_functionality_service,
)
from app.modules.automatic_load_shedding_functionality.exceptions import AppError, NotFoundError
from app.modules.automatic_load_shedding_functionality.schemas import (
    CandidateTerminalList,
    CapabilityCheckResponse,
    FunctionalityAuditLogPage,
    FunctionalityCreate,
    FunctionalityDecommissionRequest,
    FunctionalityDetail,
    FunctionalityPage,
    FunctionalityStatus,
    FunctionalityUpdate,
    SchemeType,
    TargetType,
)
from app.modules.automatic_load_shedding_functionality.service import (
    AutomaticLoadSheddingFunctionalityService,
)
from app.modules.iam.dependencies import get_current_user, require_permission
from app.modules.iam.models import User

router = APIRouter(
    prefix="/automatic-load-shedding-functionality",
    tags=["automatic-load-shedding-functionality"],
)


def _error_response(exc: AppError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code, detail={"code": exc.code, "message": exc.message})


@router.get("", response_model=FunctionalityPage)
def list_functionality(
    page: int = 1,
    page_size: int = 50,
    target_type: TargetType | None = None,
    ufls_function: bool | None = None,
    uvls_function: bool | None = None,
    status_filter: FunctionalityStatus | None = None,
    substation_id: uuid.UUID | None = None,
    voltage_level_id: int | None = None,
    service: AutomaticLoadSheddingFunctionalityService = Depends(
        get_automatic_load_shedding_functionality_service
    ),
    _current_user: User = Depends(get_current_user),
) -> FunctionalityPage:
    items, total = service.list_functionality(
        page=page,
        page_size=page_size,
        target_type=target_type,
        ufls_function=ufls_function,
        uvls_function=uvls_function,
        status=status_filter,
        substation_id=substation_id,
        voltage_level_id=voltage_level_id,
    )
    return FunctionalityPage(items=items, page=page, page_size=page_size, total=total)


@router.post("", response_model=FunctionalityDetail, status_code=status.HTTP_201_CREATED)
def create_functionality(
    payload: FunctionalityCreate,
    service: AutomaticLoadSheddingFunctionalityService = Depends(
        get_automatic_load_shedding_functionality_service
    ),
    actor: User = Depends(require_permission("automatic_load_shedding_functionality.write")),
) -> FunctionalityDetail:
    try:
        functionality = service.create(
            target_type=payload.target_type,
            circuit_terminal_id=payload.circuit_terminal_id,
            transformer_terminal_id=payload.transformer_terminal_id,
            ufls_function=payload.ufls_function,
            uvls_function=payload.uvls_function,
            relay_make=payload.relay_make,
            relay_model=payload.relay_model,
            remarks=payload.remarks,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_detail(functionality.id)
    assert detail is not None
    return detail


@router.get("/candidates", response_model=CandidateTerminalList)
def list_candidates(
    scheme_type: SchemeType,
    substation_id: uuid.UUID | None = None,
    target_type: TargetType | None = None,
    voltage_level_id: int | None = None,
    service: AutomaticLoadSheddingFunctionalityService = Depends(
        get_automatic_load_shedding_functionality_service
    ),
    _current_user: User = Depends(get_current_user),
) -> CandidateTerminalList:
    items = service.list_candidate_terminals(
        scheme_type=scheme_type,
        substation_id=substation_id,
        target_type=target_type,
        voltage_level_id=voltage_level_id,
    )
    return CandidateTerminalList(items=items, total=len(items))


@router.get("/capability-check", response_model=CapabilityCheckResponse)
def check_capability(
    scheme_type: SchemeType,
    circuit_terminal_id: uuid.UUID | None = None,
    transformer_terminal_id: uuid.UUID | None = None,
    service: AutomaticLoadSheddingFunctionalityService = Depends(
        get_automatic_load_shedding_functionality_service
    ),
    _current_user: User = Depends(get_current_user),
) -> CapabilityCheckResponse:
    if scheme_type == "UFLS":
        capable = service.is_ufls_capable(
            circuit_terminal_id=circuit_terminal_id,
            transformer_terminal_id=transformer_terminal_id,
        )
    else:
        capable = service.is_uvls_capable(
            circuit_terminal_id=circuit_terminal_id,
            transformer_terminal_id=transformer_terminal_id,
        )
    return CapabilityCheckResponse(capable=capable)


@router.get("/{functionality_id}", response_model=FunctionalityDetail)
def get_functionality(
    functionality_id: uuid.UUID,
    service: AutomaticLoadSheddingFunctionalityService = Depends(
        get_automatic_load_shedding_functionality_service
    ),
    _current_user: User = Depends(get_current_user),
) -> FunctionalityDetail:
    detail = service.get_detail(functionality_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Functionality record not found")
    return detail


@router.patch("/{functionality_id}", response_model=FunctionalityDetail)
def update_functionality(
    functionality_id: uuid.UUID,
    payload: FunctionalityUpdate,
    service: AutomaticLoadSheddingFunctionalityService = Depends(
        get_automatic_load_shedding_functionality_service
    ),
    actor: User = Depends(require_permission("automatic_load_shedding_functionality.write")),
) -> FunctionalityDetail:
    fields = payload.model_dump(exclude={"change_reason"}, exclude_unset=True)
    try:
        service.update_metadata(
            functionality_id,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
            **fields,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_detail(functionality_id)
    assert detail is not None
    return detail


@router.post("/{functionality_id}/decommission", response_model=FunctionalityDetail)
def decommission_functionality(
    functionality_id: uuid.UUID,
    payload: FunctionalityDecommissionRequest,
    service: AutomaticLoadSheddingFunctionalityService = Depends(
        get_automatic_load_shedding_functionality_service
    ),
    actor: User = Depends(require_permission("automatic_load_shedding_functionality.write")),
) -> FunctionalityDetail:
    try:
        service.decommission(
            functionality_id, change_reason=payload.change_reason, actor_user_id=actor.user_id
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_detail(functionality_id)
    assert detail is not None
    return detail


@router.get("/{functionality_id}/audit-log", response_model=FunctionalityAuditLogPage)
def list_audit_log(
    functionality_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    service: AutomaticLoadSheddingFunctionalityService = Depends(
        get_automatic_load_shedding_functionality_service
    ),
    _current_user: User = Depends(get_current_user),
) -> FunctionalityAuditLogPage:
    if service.get_detail(functionality_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Functionality record not found")
    items, total = service.list_audit_log(functionality_id, page=page, page_size=page_size)
    return FunctionalityAuditLogPage(items=items, page=page, page_size=page_size, total=total)
