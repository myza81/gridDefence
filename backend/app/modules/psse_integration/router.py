"""PSS/E Integration router (CLAUDE.md §14) — HTTP, request validation,
authentication only. No business logic — every handler delegates to
`PsseIntegrationService` directly, or, for Commit specifically, to an RQ
job wrapper (`jobs.py`) submitted through the Execution Engine
(`app.core.execution`).

Read endpoints require only authentication (`get_current_user`) — this is
engineering reference/audit data, not a write surface. Preview/commit
require `psse_integration.import`; activation requires the more privileged
`psse_integration.activate` (Phase 4 requirement: "Activate must be
explicit, privileged, atomic, and audited").

**Preview executes synchronously, in-request** (execution-model refinement
— psse-integration-module.md §8.9a). Preview is zero-persistence,
read-only validation work measured (Phase 4.1 stabilization report) at
~150-300ms for a real, full-scale RAW file — well within normal request
latency — so it no longer depends on Redis/RQ at all.

**Commit's execution mechanism is configurable** (Phase 6 refinement,
§8.9c) via the Execution Engine — "direct" (default; runs in-process, no
Redis/RQ) or "queue" (Redis+RQ, unchanged from before this refactor). This
module never imports `redis`/`rq`/`app.core.queue` directly — only
`app.core.execution`'s engine-agnostic interface. The engineering result of
a Commit (persistence, validation, Equipment Correlation, Current Topology
update) is identical either way; only how its completion is reported back
(immediately vs. a job to poll) differs.
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import JSONResponse

from app.core.execution import ExecutionEngine, ExecutionUnavailableError, get_execution_engine
from app.modules.iam.dependencies import get_current_user, require_permission
from app.modules.iam.models import User
from app.modules.psse_integration.dependencies import get_psse_integration_service
from app.modules.psse_integration.exceptions import AppError, NotFoundError, UnknownJobError
from app.modules.psse_integration.jobs import run_commit_job
from app.modules.psse_integration.schemas import (
    ActivateRequest,
    BatchPage,
    BatchSummary,
    BusCorrelationRefreshSummary,
    CircuitCorrelation,
    CurrentStatus,
    DiscrepancyResolveRequest,
    EquipmentTopologyMapEntry,
    EquipmentTopologyMapPage,
    JobStatus,
    LoadSnapshotPage,
    LoadSnapshotSummary,
    OperationalBranchViewPage,
    OperationalBusView,
    OperationalBusViewPage,
    OperationalLoadViewPage,
    OperationalTransformerViewPage,
    PreviewResult,
    TopologyVersionPage,
    TopologyVersionSummary,
)
from app.modules.psse_integration.service import PsseIntegrationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/psse-integration", tags=["psse-integration"])


def _error_response(exc: AppError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code, detail={"code": exc.code, "message": exc.message})


# --- Preview (synchronous, zero-persistence; §8.9a) -------------------------------


@router.post("/imports/preview", response_model=PreviewResult)
def submit_preview(
    file: Annotated[UploadFile, File(...)],
    actor: User = Depends(require_permission("psse_integration.import")),
    service: PsseIntegrationService = Depends(get_psse_integration_service),
) -> PreviewResult:
    # Plain `def` handler: FastAPI runs it in its worker threadpool, and a
    # sync body lets the upload be read via the underlying file object
    # directly (`file.file.read()`) rather than the async `UploadFile.read()`
    # Commit's own upload path still needs (`_read_text`, below) — no
    # threadpool offload trick or new dependency required for this.
    content = file.file.read().decode("utf-8", errors="replace")
    try:
        result = service.preview(content, file.filename or "unknown.raw")
    except AppError as exc:
        raise _error_response(exc) from exc
    return PreviewResult.model_validate(result)


# --- Commit (execution mode configurable; implementation-plan.md §4, §8.9c) -------


@router.post("/imports/commit")
def submit_commit(
    file: Annotated[UploadFile, File(...)],
    actor: User = Depends(require_permission("psse_integration.import")),
    engine: ExecutionEngine = Depends(get_execution_engine),
) -> Response:
    # Plain `def` handler, reading the upload via the underlying file
    # object directly (mirrors Preview, §8.9a) — Direct mode's own commit
    # work (up to ~1 second, §8.9a) runs in FastAPI's worker threadpool,
    # never blocking the event loop.
    content = file.file.read().decode("utf-8", errors="replace")
    try:
        outcome = engine.submit(
            run_commit_job, content, file.filename or "unknown.raw", str(actor.user_id)
        )
    except ExecutionUnavailableError as exc:
        logger.error("Commit could not be queued — execution engine unavailable: %s", exc)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "queue_unavailable",
                "message": (
                    "Import could not be queued because the background import service is "
                    "currently unavailable. Please try again shortly."
                ),
            },
        ) from exc

    if not outcome.completed:
        # Queue mode: unchanged shape — a job id to poll via GET .../jobs/{id}.
        return JSONResponse(
            status_code=status.HTTP_202_ACCEPTED, content={"job_id": outcome.job_id}
        )

    # Direct mode (default): the result is already available — return it
    # immediately, mirroring Preview's own synchronous response shape.
    if outcome.error is not None:
        if isinstance(outcome.error, AppError):
            raise _error_response(outcome.error) from outcome.error
        raise outcome.error
    return JSONResponse(status_code=status.HTTP_200_OK, content=outcome.result)


@router.get("/imports/jobs/{job_id}", response_model=JobStatus)
def get_job_status(
    job_id: str,
    _current_user: User = Depends(get_current_user),
    engine: ExecutionEngine = Depends(get_execution_engine),
) -> JobStatus:
    outcome = engine.fetch(job_id)
    if outcome is None:
        raise _error_response(UnknownJobError(job_id))
    if not outcome.completed:
        return JobStatus(job_id=job_id, status="started", result=None, error=None)
    if outcome.error is not None:
        return JobStatus(job_id=job_id, status="failed", result=None, error=str(outcome.error))
    return JobStatus(job_id=job_id, status="finished", result=outcome.result, error=None)


# --- Import batches (audit history; Workflow 8, §8.11) ----------------------------


@router.get("/imports/batches", response_model=BatchPage)
def list_batches(
    page: int = 1,
    page_size: int = 50,
    status_filter: str | None = None,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    _current_user: User = Depends(get_current_user),
) -> BatchPage:
    items, total = service.list_batch_summaries(
        page=page, page_size=page_size, status=status_filter
    )
    return BatchPage(items=items, page=page, page_size=page_size, total=total)


@router.get("/imports/batches/{batch_id}", response_model=BatchSummary)
def get_batch(
    batch_id: uuid.UUID,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    _current_user: User = Depends(get_current_user),
) -> BatchSummary:
    try:
        return service.get_batch_summary(batch_id)
    except AppError as exc:
        raise _error_response(exc) from exc


@router.post("/imports/batches/{batch_id}/activate", response_model=BatchSummary)
def activate_batch(
    batch_id: uuid.UUID,
    payload: ActivateRequest,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    actor: User = Depends(require_permission("psse_integration.activate")),
) -> BatchSummary:
    try:
        service.activate(batch_id, change_reason=payload.change_reason, actor_user_id=actor.user_id)
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    return service.get_batch_summary(batch_id)


# --- TopologyVersion / LoadSnapshot history and current status --------------------


@router.get("/topology-versions", response_model=TopologyVersionPage)
def list_topology_versions(
    page: int = 1,
    page_size: int = 50,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    _current_user: User = Depends(get_current_user),
) -> TopologyVersionPage:
    items, total = service.list_topology_version_summaries(page=page, page_size=page_size)
    return TopologyVersionPage(items=items, page=page, page_size=page_size, total=total)


@router.get("/topology-versions/{topology_version_id}", response_model=TopologyVersionSummary)
def get_topology_version(
    topology_version_id: uuid.UUID,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    _current_user: User = Depends(get_current_user),
) -> TopologyVersionSummary:
    try:
        return service.get_topology_version_summary(topology_version_id)
    except AppError as exc:
        raise _error_response(exc) from exc


@router.post("/topology-versions/{topology_version_id}/recompute-matching")
def recompute_matching(
    topology_version_id: uuid.UUID,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    actor: User = Depends(require_permission("psse_integration.import")),
) -> dict[str, str]:
    try:
        service.recompute_matching(topology_version_id, actor_user_id=actor.user_id)
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    return {"status": "recomputed"}


@router.get("/load-snapshots", response_model=LoadSnapshotPage)
def list_load_snapshots(
    page: int = 1,
    page_size: int = 50,
    topology_version_id: uuid.UUID | None = None,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    _current_user: User = Depends(get_current_user),
) -> LoadSnapshotPage:
    items, total = service.list_load_snapshot_summaries(
        page=page, page_size=page_size, topology_version_id=topology_version_id
    )
    return LoadSnapshotPage(items=items, page=page, page_size=page_size, total=total)


@router.get("/load-snapshots/{load_snapshot_id}", response_model=LoadSnapshotSummary)
def get_load_snapshot(
    load_snapshot_id: uuid.UUID,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    _current_user: User = Depends(get_current_user),
) -> LoadSnapshotSummary:
    try:
        return service.get_load_snapshot_summary(load_snapshot_id)
    except AppError as exc:
        raise _error_response(exc) from exc


@router.get("/current-status", response_model=CurrentStatus)
def get_current_status(
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    _current_user: User = Depends(get_current_user),
) -> CurrentStatus:
    return service.get_current_status_summary()


# --- EquipmentTopologyMap review (§8a) ---------------------------------------------


@router.get(
    "/topology-versions/{topology_version_id}/equipment-map",
    response_model=EquipmentTopologyMapPage,
)
def list_equipment_map(
    topology_version_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    match_outcome: str | None = None,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    _current_user: User = Depends(get_current_user),
) -> EquipmentTopologyMapPage:
    items, total = service.list_map_entry_summaries(
        topology_version_id=topology_version_id,
        page=page,
        page_size=page_size,
        match_outcome=match_outcome,
    )
    return EquipmentTopologyMapPage(items=items, page=page, page_size=page_size, total=total)


@router.post("/equipment-map/{map_id}/resolve", response_model=EquipmentTopologyMapEntry)
def resolve_discrepancy(
    map_id: uuid.UUID,
    payload: DiscrepancyResolveRequest,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    actor: User = Depends(require_permission("psse_integration.import")),
) -> EquipmentTopologyMapEntry:
    try:
        entry = service.resolve_discrepancy(
            map_id,
            resolution=payload.resolution,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    return entry


@router.get("/circuits/{circuit_id}/correlation", response_model=CircuitCorrelation)
def get_circuit_correlation(
    circuit_id: uuid.UUID,
    topology_version_id: uuid.UUID,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    _current_user: User = Depends(get_current_user),
) -> CircuitCorrelation:
    try:
        return service.get_circuit_correlation(circuit_id, topology_version_id)
    except AppError as exc:
        raise _error_response(exc) from exc


# --- Correlated Operational Model (Phase 7C/7D) -------------------------------------
#
# Read-only — the intended, preferred engineering-consumption API for
# future Defence Scheme modules, dashboards, and analytics
# (operational-correlation-architecture.md §5, §6). Authentication only,
# exactly like every other read endpoint in this router; this is
# engineering reference data, not a write surface.
#
# The one exception is `refresh-correlation` below (Phase 7D) — it updates
# only the correlation link (`TopologyBus.substation_id`), never topology
# facts or registry records, and requires `psse_integration.import`
# exactly like `recompute-matching` above (its Branch/Transformer-level
# counterpart) — both are explicit, audited maintenance operations, not
# passive reads.


@router.post(
    "/topology-versions/{topology_version_id}/operational-model/refresh-correlation",
    response_model=BusCorrelationRefreshSummary,
)
def refresh_bus_correlation(
    topology_version_id: uuid.UUID,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    actor: User = Depends(require_permission("psse_integration.import")),
) -> BusCorrelationRefreshSummary:
    try:
        summary = service.refresh_bus_correlation(topology_version_id, actor_user_id=actor.user_id)
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    return summary


@router.get(
    "/topology-versions/{topology_version_id}/operational-model/buses",
    response_model=OperationalBusViewPage,
)
def list_operational_bus_views(
    topology_version_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    _current_user: User = Depends(get_current_user),
) -> OperationalBusViewPage:
    try:
        items, total = service.get_operational_bus_views(
            topology_version_id, page=page, page_size=page_size
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    return OperationalBusViewPage(items=items, page=page, page_size=page_size, total=total)


@router.get(
    "/topology-versions/{topology_version_id}/operational-model/buses/{bus_number}",
    response_model=OperationalBusView,
)
def get_operational_bus_view(
    topology_version_id: uuid.UUID,
    bus_number: int,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    _current_user: User = Depends(get_current_user),
) -> OperationalBusView:
    try:
        return service.get_operational_bus_view(topology_version_id, bus_number)
    except AppError as exc:
        raise _error_response(exc) from exc


@router.get(
    "/topology-versions/{topology_version_id}/operational-model/branches",
    response_model=OperationalBranchViewPage,
)
def list_operational_branch_views(
    topology_version_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    _current_user: User = Depends(get_current_user),
) -> OperationalBranchViewPage:
    try:
        items, total = service.get_operational_branch_views(
            topology_version_id, page=page, page_size=page_size
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    return OperationalBranchViewPage(items=items, page=page, page_size=page_size, total=total)


@router.get(
    "/topology-versions/{topology_version_id}/operational-model/transformers",
    response_model=OperationalTransformerViewPage,
)
def list_operational_transformer_views(
    topology_version_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    _current_user: User = Depends(get_current_user),
) -> OperationalTransformerViewPage:
    try:
        items, total = service.get_operational_transformer_views(
            topology_version_id, page=page, page_size=page_size
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    return OperationalTransformerViewPage(items=items, page=page, page_size=page_size, total=total)


@router.get(
    "/load-snapshots/{load_snapshot_id}/operational-model/loads",
    response_model=OperationalLoadViewPage,
)
def list_operational_load_views(
    load_snapshot_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    service: PsseIntegrationService = Depends(get_psse_integration_service),
    _current_user: User = Depends(get_current_user),
) -> OperationalLoadViewPage:
    try:
        items, total = service.get_operational_load_views(
            load_snapshot_id, page=page, page_size=page_size
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    return OperationalLoadViewPage(items=items, page=page, page_size=page_size, total=total)
