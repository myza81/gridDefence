"""Network Model router (CLAUDE.md §14) — HTTP, request validation,
authentication only. No business logic — every handler delegates to
`NetworkModelService`.

All endpoints are read-only (this phase implements a static connectivity
model — no write path exists or is planned for it). Every endpoint
requires only authentication (`get_current_user`), not the
`network_model.read` permission — mirrors Equipment Registry's and
Substation Registry's own precedent for read access to engineering
reference data: the permission is registered as catalog data
(bootstrap.py) for possible future finer-grained use, but no endpoint
currently gates on it.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.iam.dependencies import get_current_user
from app.modules.iam.models import User
from app.modules.network_model.dependencies import get_network_model_service
from app.modules.network_model.exceptions import AppError, NotFoundError
from app.modules.network_model.schemas import (
    ElectricalNeighbour,
    NetworkOverview,
    SubstationConnectivity,
    SubstationEquipment,
    TraversalRequest,
    TraversalResult,
)
from app.modules.network_model.service import NetworkModelService

router = APIRouter(prefix="/network-model", tags=["network-model"])


def _error_response(exc: AppError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code, detail={"code": exc.code, "message": exc.message})


@router.get("/overview", response_model=NetworkOverview)
def get_overview(
    service: NetworkModelService = Depends(get_network_model_service),
    _current_user: User = Depends(get_current_user),
) -> NetworkOverview:
    return service.get_overview()


@router.get(
    "/substations/{substation_id}/connectivity",
    response_model=SubstationConnectivity,
)
def get_substation_connectivity(
    substation_id: uuid.UUID,
    service: NetworkModelService = Depends(get_network_model_service),
    _current_user: User = Depends(get_current_user),
) -> SubstationConnectivity:
    try:
        return service.get_substation_connectivity(substation_id)
    except AppError as exc:
        raise _error_response(exc) from exc


@router.get(
    "/substations/{substation_id}/equipment",
    response_model=SubstationEquipment,
)
def get_substation_equipment(
    substation_id: uuid.UUID,
    service: NetworkModelService = Depends(get_network_model_service),
    _current_user: User = Depends(get_current_user),
) -> SubstationEquipment:
    try:
        return service.get_substation_equipment(substation_id)
    except AppError as exc:
        raise _error_response(exc) from exc


@router.get(
    "/substations/{substation_id}/neighbours",
    response_model=list[ElectricalNeighbour],
)
def list_substation_neighbours(
    substation_id: uuid.UUID,
    service: NetworkModelService = Depends(get_network_model_service),
    _current_user: User = Depends(get_current_user),
) -> list[ElectricalNeighbour]:
    try:
        return service.list_substation_neighbours(substation_id)
    except AppError as exc:
        raise _error_response(exc) from exc


@router.post("/traverse", response_model=TraversalResult)
def traverse(
    request: TraversalRequest,
    service: NetworkModelService = Depends(get_network_model_service),
    _current_user: User = Depends(get_current_user),
) -> TraversalResult:
    try:
        return service.traverse(request)
    except AppError as exc:
        raise _error_response(exc) from exc
