"""Sensitive Customer Registry router (CLAUDE.md §14) — HTTP, request
validation, authentication only. No business logic — every handler
delegates to `SensitiveCustomerRegistryService`.

Permission model (corrected, task Correction 1): read endpoints require
`sensitive_customer_registry.read` (Administrator + Engineer, NOT open to
every authenticated user — module document §15's stricter read-access
recommendation). Facility mutation (create/edit/lifecycle) requires
`sensitive_customer_registry.write` (Administrator only). Reference-data
administration requires `sensitive_customer_registry.manage_reference_data`
(Administrator only).

Route ordering: `/facilities/summary` and `/facilities/batch-lookup` and
`/facilities/by-transformer-terminal/{terminal_id}` are declared before
`/facilities/{facility_id}` so FastAPI does not attempt to parse a literal
path segment as a UUID.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.iam.dependencies import require_permission
from app.modules.iam.models import User
from app.modules.sensitive_customer_registry.dependencies import (
    get_sensitive_customer_registry_service,
)
from app.modules.sensitive_customer_registry.exceptions import AppError, NotFoundError
from app.modules.sensitive_customer_registry.schemas import (
    BatchLookupRequest,
    BatchLookupResponse,
    FacilitySectorCreate,
    FacilitySectorSummary,
    FacilitySectorUpdate,
    LifecycleStatus,
    SensitiveFacilityAuditLogPage,
    SensitiveFacilityCreate,
    SensitiveFacilityDetail,
    SensitiveFacilityLifecycleRequest,
    SensitiveFacilityPage,
    SensitiveFacilitySummary,
    SensitiveFacilitySummaryCounts,
    SensitiveFacilityTerminalsUpdate,
    SensitiveFacilityUpdate,
    SensitivityClassificationCreate,
    SensitivityClassificationSummary,
    SensitivityClassificationUpdate,
    TransformerTerminalResolution,
)
from app.modules.sensitive_customer_registry.service import SensitiveCustomerRegistryService

router = APIRouter(
    prefix="/sensitive-customer-registry",
    tags=["sensitive-customer-registry"],
)

_READ = "sensitive_customer_registry.read"
_WRITE = "sensitive_customer_registry.write"
_MANAGE_REFERENCE_DATA = "sensitive_customer_registry.manage_reference_data"


def _error_response(exc: AppError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code, detail={"code": exc.code, "message": exc.message})


# --- Facilities ----------------------------------------------------------------


@router.get("/facilities", response_model=SensitiveFacilityPage)
def list_facilities(
    page: int = 1,
    page_size: int = 50,
    facility_sector_id: int | None = None,
    sensitivity_classification_id: int | None = None,
    lifecycle_status: LifecycleStatus | None = None,
    transformer_terminal_id: uuid.UUID | None = None,
    transformer_terminal_resolution: TransformerTerminalResolution | None = None,
    substation_id: uuid.UUID | None = None,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    _actor: User = Depends(require_permission(_READ)),
) -> SensitiveFacilityPage:
    items, total = service.list_facilities(
        page=page,
        page_size=page_size,
        facility_sector_id=facility_sector_id,
        sensitivity_classification_id=sensitivity_classification_id,
        lifecycle_status=lifecycle_status,
        transformer_terminal_id=transformer_terminal_id,
        transformer_terminal_resolution=transformer_terminal_resolution,
        substation_id=substation_id,
    )
    return SensitiveFacilityPage(items=items, page=page, page_size=page_size, total=total)


@router.post(
    "/facilities", response_model=SensitiveFacilityDetail, status_code=status.HTTP_201_CREATED
)
def create_facility(
    payload: SensitiveFacilityCreate,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    actor: User = Depends(require_permission(_WRITE)),
) -> SensitiveFacilityDetail:
    try:
        facility = service.create_facility(
            name=payload.name,
            facility_sector_id=payload.facility_sector_id,
            sensitivity_classification_id=payload.sensitivity_classification_id,
            transformer_terminal_ids=payload.transformer_terminal_ids,
            remarks=payload.remarks,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    return detail


@router.get("/facilities/summary", response_model=SensitiveFacilitySummaryCounts)
def get_summary(
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    _actor: User = Depends(require_permission(_READ)),
) -> SensitiveFacilitySummaryCounts:
    return service.get_summary_counts()


@router.post("/facilities/batch-lookup", response_model=BatchLookupResponse)
def batch_lookup(
    payload: BatchLookupRequest,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    _actor: User = Depends(require_permission(_READ)),
) -> BatchLookupResponse:
    results = service.get_sensitive_facilities_for_transformer_terminals(
        set(payload.transformer_terminal_ids)
    )
    return BatchLookupResponse(results=results)


@router.get(
    "/facilities/by-transformer-terminal/{transformer_terminal_id}",
    response_model=list[SensitiveFacilitySummary],
)
def get_facilities_for_transformer_terminal(
    transformer_terminal_id: uuid.UUID,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    _actor: User = Depends(require_permission(_READ)),
) -> list[SensitiveFacilitySummary]:
    return service.get_sensitive_facilities_for_transformer_terminal(transformer_terminal_id)


@router.get("/facilities/{facility_id}", response_model=SensitiveFacilityDetail)
def get_facility(
    facility_id: uuid.UUID,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    _actor: User = Depends(require_permission(_READ)),
) -> SensitiveFacilityDetail:
    detail = service.get_facility_detail(facility_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sensitive facility not found")
    return detail


@router.patch("/facilities/{facility_id}", response_model=SensitiveFacilityDetail)
def update_facility(
    facility_id: uuid.UUID,
    payload: SensitiveFacilityUpdate,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    actor: User = Depends(require_permission(_WRITE)),
) -> SensitiveFacilityDetail:
    fields = payload.model_dump(exclude={"change_reason"}, exclude_unset=True)
    try:
        service.update_metadata(
            facility_id,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
            **fields,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_facility_detail(facility_id)
    assert detail is not None
    return detail


@router.put("/facilities/{facility_id}/terminals", response_model=SensitiveFacilityDetail)
def set_facility_terminals(
    facility_id: uuid.UUID,
    payload: SensitiveFacilityTerminalsUpdate,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    actor: User = Depends(require_permission(_WRITE)),
) -> SensitiveFacilityDetail:
    """Replaces the full set of currently associated Transformer Terminals
    (ADR-013 decision 3) — never a partial add/remove of one at a time.
    The service layer diffs the requested set against the current set and
    writes one audit row per actual change."""
    try:
        service.set_terminal_associations(
            facility_id,
            transformer_terminal_ids=payload.transformer_terminal_ids,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_facility_detail(facility_id)
    assert detail is not None
    return detail


@router.post("/facilities/{facility_id}/archive", response_model=SensitiveFacilityDetail)
def archive_facility(
    facility_id: uuid.UUID,
    payload: SensitiveFacilityLifecycleRequest,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    actor: User = Depends(require_permission(_WRITE)),
) -> SensitiveFacilityDetail:
    try:
        service.archive(
            facility_id, change_reason=payload.change_reason, actor_user_id=actor.user_id
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_facility_detail(facility_id)
    assert detail is not None
    return detail


@router.post("/facilities/{facility_id}/reactivate", response_model=SensitiveFacilityDetail)
def reactivate_facility(
    facility_id: uuid.UUID,
    payload: SensitiveFacilityLifecycleRequest,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    actor: User = Depends(require_permission(_WRITE)),
) -> SensitiveFacilityDetail:
    try:
        service.reactivate(
            facility_id, change_reason=payload.change_reason, actor_user_id=actor.user_id
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_facility_detail(facility_id)
    assert detail is not None
    return detail


@router.post("/facilities/{facility_id}/entered-in-error", response_model=SensitiveFacilityDetail)
def mark_facility_entered_in_error(
    facility_id: uuid.UUID,
    payload: SensitiveFacilityLifecycleRequest,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    actor: User = Depends(require_permission(_WRITE)),
) -> SensitiveFacilityDetail:
    try:
        service.mark_entered_in_error(
            facility_id, change_reason=payload.change_reason, actor_user_id=actor.user_id
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_facility_detail(facility_id)
    assert detail is not None
    return detail


@router.get("/facilities/{facility_id}/audit-log", response_model=SensitiveFacilityAuditLogPage)
def list_facility_audit_log(
    facility_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    _actor: User = Depends(require_permission(_READ)),
) -> SensitiveFacilityAuditLogPage:
    if service.get_facility_detail(facility_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Sensitive facility not found")
    items, total = service.list_facility_audit_log(facility_id, page=page, page_size=page_size)
    return SensitiveFacilityAuditLogPage(items=items, page=page, page_size=page_size, total=total)


# --- Reference data: Facility Sector --------------------------------------------


@router.get("/reference-data/facility-sectors", response_model=list[FacilitySectorSummary])
def list_facility_sectors(
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    _actor: User = Depends(require_permission(_READ)),
) -> list[FacilitySectorSummary]:
    return [FacilitySectorSummary.model_validate(s) for s in service.list_facility_sectors()]


@router.post(
    "/reference-data/facility-sectors",
    response_model=FacilitySectorSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_facility_sector(
    payload: FacilitySectorCreate,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    actor: User = Depends(require_permission(_MANAGE_REFERENCE_DATA)),
) -> FacilitySectorSummary:
    try:
        sector = service.create_facility_sector(
            code=payload.code,
            label=payload.label,
            sort_order=payload.sort_order,
            description=payload.description,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()
    return FacilitySectorSummary.model_validate(sector)


@router.patch(
    "/reference-data/facility-sectors/{facility_sector_id}",
    response_model=FacilitySectorSummary,
)
def update_facility_sector(
    facility_sector_id: int,
    payload: FacilitySectorUpdate,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    actor: User = Depends(require_permission(_MANAGE_REFERENCE_DATA)),
) -> FacilitySectorSummary:
    fields = payload.model_dump(exclude={"change_reason"}, exclude_unset=True)
    try:
        sector = service.update_facility_sector(
            facility_sector_id,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
            **fields,
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()
    return FacilitySectorSummary.model_validate(sector)


# --- Reference data: Sensitivity Classification ---------------------------------


@router.get(
    "/reference-data/sensitivity-classifications",
    response_model=list[SensitivityClassificationSummary],
)
def list_sensitivity_classifications(
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    _actor: User = Depends(require_permission(_READ)),
) -> list[SensitivityClassificationSummary]:
    return [
        SensitivityClassificationSummary.model_validate(c)
        for c in service.list_sensitivity_classifications()
    ]


@router.post(
    "/reference-data/sensitivity-classifications",
    response_model=SensitivityClassificationSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_sensitivity_classification(
    payload: SensitivityClassificationCreate,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    actor: User = Depends(require_permission(_MANAGE_REFERENCE_DATA)),
) -> SensitivityClassificationSummary:
    try:
        classification = service.create_sensitivity_classification(
            code=payload.code,
            label=payload.label,
            sort_order=payload.sort_order,
            description=payload.description,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()
    return SensitivityClassificationSummary.model_validate(classification)


@router.patch(
    "/reference-data/sensitivity-classifications/{sensitivity_classification_id}",
    response_model=SensitivityClassificationSummary,
)
def update_sensitivity_classification(
    sensitivity_classification_id: int,
    payload: SensitivityClassificationUpdate,
    service: SensitiveCustomerRegistryService = Depends(get_sensitive_customer_registry_service),
    actor: User = Depends(require_permission(_MANAGE_REFERENCE_DATA)),
) -> SensitivityClassificationSummary:
    fields = payload.model_dump(exclude={"change_reason"}, exclude_unset=True)
    try:
        classification = service.update_sensitivity_classification(
            sensitivity_classification_id,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
            **fields,
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()
    return SensitivityClassificationSummary.model_validate(classification)
