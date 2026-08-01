"""Substation Registry router (CLAUDE.md §14) — HTTP, request validation,
authentication only. No business logic — every handler delegates to
`SubstationService`.

Read endpoints require only authentication (`get_current_user`), not the
`substation_registry.read` permission — substation-registry.md §10 states
plainly: "Read: open to all authenticated modules/users; this is reference
data, not sensitive." `substation_registry.read` is still registered and
seeded (implementation-plan.md Phase 2) as catalog data for future,
finer-grained use by other modules, but nothing in this router currently
gates on it — see Phase 2's final report ("Assumptions made") for the full
reasoning. Write endpoints (create/update/status-change) require
`substation_registry.write`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.iam.dependencies import get_current_user, require_permission
from app.modules.iam.models import User
from app.modules.substation_registry.dependencies import get_substation_service
from app.modules.substation_registry.exceptions import AppError, NotFoundError, ValidationAppError
from app.modules.substation_registry.schemas import (
    SubstationAliasSummary,
    SubstationAuditLogPage,
    SubstationCreate,
    SubstationDetail,
    SubstationMapResponse,
    SubstationPage,
    SubstationStatusChange,
    SubstationUpdate,
)
from app.modules.substation_registry.service import SubstationService

router = APIRouter(prefix="/substations", tags=["substation-registry"])


def _error_response(exc: AppError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code, detail={"code": exc.code, "message": exc.message})


@router.get("", response_model=SubstationPage)
def list_substations(
    page: int = 1,
    page_size: int = 50,
    region_id: int | None = None,
    gm_zone_id: int | None = None,
    state_id: int | None = None,
    grid_owner_id: int | None = None,
    operational_status_id: int | None = None,
    search: str | None = None,
    service: SubstationService = Depends(get_substation_service),
    _current_user: User = Depends(get_current_user),
) -> SubstationPage:
    items, total = service.list_substations(
        page=page,
        page_size=page_size,
        region_id=region_id,
        gm_zone_id=gm_zone_id,
        state_id=state_id,
        grid_owner_id=grid_owner_id,
        operational_status_id=operational_status_id,
        search=search,
    )
    return SubstationPage(items=items, page=page, page_size=page_size, total=total)


@router.post("", response_model=SubstationDetail, status_code=status.HTTP_201_CREATED)
def create_substation(
    payload: SubstationCreate,
    service: SubstationService = Depends(get_substation_service),
    actor: User = Depends(require_permission("substation_registry.write")),
) -> SubstationDetail:
    try:
        substation = service.create_substation(
            mnemonic=payload.mnemonic,
            official_name=payload.official_name,
            region_id=payload.region_id,
            gm_zone_id=payload.gm_zone_id,
            state_id=payload.state_id,
            grid_owner_id=payload.grid_owner_id,
            operational_status_id=payload.operational_status_id,
            psse_bus_number=payload.psse_bus_number,
            latitude=payload.latitude,
            longitude=payload.longitude,
            commissioned_date=payload.commissioned_date,
            remarks=payload.remarks,
            actor_user_id=actor.user_id,
        )
    except ValidationAppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_substation(substation.substation_id)
    assert detail is not None
    return detail


@router.get("/map", response_model=SubstationMapResponse)
def list_substation_map(
    region_id: int | None = None,
    gm_zone_id: int | None = None,
    state_id: int | None = None,
    grid_owner_id: int | None = None,
    operational_status_id: int | None = None,
    search: str | None = None,
    service: SubstationService = Depends(get_substation_service),
    _current_user: User = Depends(get_current_user),
) -> SubstationMapResponse:
    """Read-only geographic projection for the Substation map view (Phase E.1).

    Same filter surface as the list endpoint (so the table and map never
    drift). Returns every matching record unpaginated with the authoritative
    Substation coordinate plus mapped/missing counts; reads are open to any
    authenticated user, exactly like the list (substation-registry.md §10 —
    reference data, not sensitive). Declared before `/{substation_id}` so
    "map" is never parsed as a substation id.
    """
    features, mapped, missing = service.list_map_features(
        region_id=region_id,
        gm_zone_id=gm_zone_id,
        state_id=state_id,
        grid_owner_id=grid_owner_id,
        operational_status_id=operational_status_id,
        search=search,
    )
    return SubstationMapResponse(
        items=features, mapped_count=mapped, missing_coordinate_count=missing, total=len(features)
    )


@router.get("/{substation_id}", response_model=SubstationDetail)
def get_substation(
    substation_id: uuid.UUID,
    service: SubstationService = Depends(get_substation_service),
    _current_user: User = Depends(get_current_user),
) -> SubstationDetail:
    detail = service.get_substation(substation_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Substation not found")
    return detail


@router.patch("/{substation_id}", response_model=SubstationDetail)
def update_substation(
    substation_id: uuid.UUID,
    payload: SubstationUpdate,
    service: SubstationService = Depends(get_substation_service),
    actor: User = Depends(require_permission("substation_registry.write")),
) -> SubstationDetail:
    fields = payload.model_dump(exclude_unset=True)
    try:
        service.update_substation(substation_id, actor_user_id=actor.user_id, **fields)
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_substation(substation_id)
    assert detail is not None
    return detail


@router.post("/{substation_id}/status", response_model=SubstationDetail)
def change_status(
    substation_id: uuid.UUID,
    payload: SubstationStatusChange,
    service: SubstationService = Depends(get_substation_service),
    actor: User = Depends(require_permission("substation_registry.write")),
) -> SubstationDetail:
    try:
        service.change_status(
            substation_id,
            operational_status_id=payload.operational_status_id,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_substation(substation_id)
    assert detail is not None
    return detail


@router.get("/{substation_id}/aliases", response_model=list[SubstationAliasSummary])
def list_aliases(
    substation_id: uuid.UUID,
    service: SubstationService = Depends(get_substation_service),
    _current_user: User = Depends(get_current_user),
) -> list[SubstationAliasSummary]:
    if service.get_substation(substation_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Substation not found")
    return service.list_aliases(substation_id)


@router.get("/{substation_id}/audit-log", response_model=SubstationAuditLogPage)
def list_audit_log(
    substation_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    service: SubstationService = Depends(get_substation_service),
    _current_user: User = Depends(get_current_user),
) -> SubstationAuditLogPage:
    if service.get_substation(substation_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Substation not found")
    items, total = service.list_audit_log(substation_id, page=page, page_size=page_size)
    return SubstationAuditLogPage(items=items, page=page, page_size=page_size, total=total)
