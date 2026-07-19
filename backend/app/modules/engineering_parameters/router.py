"""Engineering Parameter Configuration router (CLAUDE.md §14) — HTTP,
request validation, authentication only. No business logic — every
handler delegates to `EngineeringParameterService`.

Read endpoints (`list`, `get`) require only authentication
(`get_current_user`) — ADR-021: "Read is broadly available (any
authenticated user...)". Write (`set`) requires the elevated
`engineering_parameters.manage` permission (ADR-021 §4.1's own reasoning,
mirrored here: changing a platform-wide policy value is a platform
administration action, not an ordinary scheme-design action). The
audit-log endpoint is gated behind the same elevated permission as write —
a deliberate deviation from this codebase's usual "audit log open to any
authenticated user" precedent (e.g. Substation Registry's own
`/audit-log`), justified explicitly in
docs/architecture/engineering-parameter-configuration-architecture.md §12
and ADR-021's own §4.1 cross-reference to
findings-and-publication-governance-architecture.md §13's "audit log
access is itself access-controlled."
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.engineering_parameters.dependencies import get_engineering_parameter_service
from app.modules.engineering_parameters.exceptions import AppError, NotFoundError
from app.modules.engineering_parameters.schemas import (
    EngineeringParameterAuditLogPage,
    EngineeringParameterDetail,
    EngineeringParameterSetRequest,
)
from app.modules.engineering_parameters.service import EngineeringParameterService
from app.modules.iam.dependencies import get_current_user, require_permission
from app.modules.iam.models import User

router = APIRouter(prefix="/engineering-parameters", tags=["engineering-parameters"])


def _error_response(exc: AppError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code, detail={"code": exc.code, "message": exc.message})


@router.get("", response_model=list[EngineeringParameterDetail])
def list_parameters(
    service: EngineeringParameterService = Depends(get_engineering_parameter_service),
    _current_user: User = Depends(get_current_user),
) -> list[EngineeringParameterDetail]:
    return service.list_parameters()


@router.get("/{parameter_key}", response_model=EngineeringParameterDetail)
def get_parameter(
    parameter_key: str,
    service: EngineeringParameterService = Depends(get_engineering_parameter_service),
    _current_user: User = Depends(get_current_user),
) -> EngineeringParameterDetail:
    detail = service.get_parameter(parameter_key)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Engineering parameter not found")
    return detail


@router.put("/{parameter_key}", response_model=EngineeringParameterDetail)
def set_parameter(
    parameter_key: str,
    payload: EngineeringParameterSetRequest,
    service: EngineeringParameterService = Depends(get_engineering_parameter_service),
    actor: User = Depends(require_permission("engineering_parameters.manage")),
) -> EngineeringParameterDetail:
    try:
        service.set_parameter_value(
            parameter_key,
            value=payload.value,
            unit=payload.unit,
            description=payload.description,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_parameter(parameter_key)
    assert detail is not None
    return detail


@router.get("/{parameter_key}/audit-log", response_model=EngineeringParameterAuditLogPage)
def list_audit_log(
    parameter_key: str,
    page: int = 1,
    page_size: int = 50,
    service: EngineeringParameterService = Depends(get_engineering_parameter_service),
    _actor: User = Depends(require_permission("engineering_parameters.manage")),
) -> EngineeringParameterAuditLogPage:
    try:
        items, total = service.list_audit_log(parameter_key, page=page, page_size=page_size)
    except AppError as exc:
        raise _error_response(exc) from exc
    return EngineeringParameterAuditLogPage(items=items, page=page, page_size=page_size, total=total)
