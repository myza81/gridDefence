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
    BoundaryPocketEvaluation,
    BoundaryPocketEvaluationRequest,
    ElectricalNeighbour,
    NetworkOverview,
    PathVerificationRequest,
    SnapshotSummary,
    SubstationConnectivity,
    SubstationEquipment,
    TraversalRequest,
    TraversalResult,
    TraversalVerificationResult,
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


# --- Foundation Hardening Sprint A — Boundary Pocket foundation -------------------
#
# docs/architecture/boundary-pocket-architecture.md §10 — always synchronous, no
# job/polling shape, no persistence endpoint of its own (this capability never
# persists a Boundary Pocket; a future Defence Scheme module's own
# assignment-creation endpoint would call `evaluateBoundary` internally, as a
# service-layer call, not by proxying through this HTTP endpoint).


@router.post("/boundary-pocket-evaluations", response_model=BoundaryPocketEvaluation)
def evaluate_boundary(
    request: BoundaryPocketEvaluationRequest,
    service: NetworkModelService = Depends(get_network_model_service),
    _current_user: User = Depends(get_current_user),
) -> BoundaryPocketEvaluation:
    try:
        return service.evaluate_boundary(request)
    except AppError as exc:
        raise _error_response(exc) from exc


# --- Phase 7F — Operational Snapshot Verification Workspace (independent of
# the Network Traversal endpoint above, which is unchanged) -----------------


@router.get("/verification/snapshot-summary", response_model=SnapshotSummary)
def get_snapshot_summary(
    service: NetworkModelService = Depends(get_network_model_service),
    _current_user: User = Depends(get_current_user),
) -> SnapshotSummary:
    return service.get_snapshot_summary()


@router.post("/verification/traverse", response_model=TraversalVerificationResult)
def verify_path(
    request: PathVerificationRequest,
    service: NetworkModelService = Depends(get_network_model_service),
    _current_user: User = Depends(get_current_user),
) -> TraversalVerificationResult:
    try:
        return service.verify_path(request)
    except AppError as exc:
        raise _error_response(exc) from exc
