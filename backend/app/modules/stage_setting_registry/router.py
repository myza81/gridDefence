"""Stage Setting Registry router (CLAUDE.md §14) — HTTP, request
validation, authentication only. No business logic — every handler
delegates to `StageSettingRegistryService`.

Read endpoints (`list`, `get`, settings list, triggers list, audit log)
require only authentication (`get_current_user`), mirroring Substation
Registry's, ALSF's, and Engineering Parameter Configuration's own
precedent for engineering reference/registry data — `stage_setting_registry
.read` is still registered as catalog data (bootstrap.py) for possible
future finer-grained use. Draft-editing endpoints require
`stage_setting_registry.manage`. `publish` and `enter-in-error` each
require their own dedicated, more privileged permission — mirroring
findings-and-publication-governance-architecture.md §6's own "Only
Administrators may publish" precedent, generalized here (a user who may
edit a Draft is not assumed to also be trusted to publish or correct it).

**Two-level stage structure (ADR-025).** A "setting" (existing URL segment,
unchanged for minimal diff) is a stage — `StageSetting` — which owns one or
more nested "triggers" (`StageSettingTrigger`), each an independent
frequency/voltage-time operating criterion for that same stage. Creating a
stage no longer accepts a threshold or time delay; those are added
separately via the nested trigger endpoints once the stage exists.

Route ordering: `/settings/reorder` is declared before
`/settings/{stage_setting_id}`, and `/settings/{stage_setting_id}/triggers
/reorder` is declared before `/settings/{stage_setting_id}/triggers/
{stage_setting_trigger_id}`, so FastAPI does not attempt to parse the
literal `reorder` segment as a UUID path parameter.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.iam.dependencies import get_current_user, require_permission
from app.modules.iam.models import User
from app.modules.stage_setting_registry.dependencies import get_stage_setting_registry_service
from app.modules.stage_setting_registry.exceptions import AppError, NotFoundError
from app.modules.stage_setting_registry.schemas import (
    SchemeType,
    StageSettingCreate,
    StageSettingDetail,
    StageSettingRegistryAuditLogPage,
    StageSettingReorderRequest,
    StageSettingSetCreate,
    StageSettingSetDetail,
    StageSettingSetEnterInErrorRequest,
    StageSettingSetPage,
    StageSettingSetStatus,
    StageSettingSetUpdate,
    StageSettingTriggerCreate,
    StageSettingTriggerDetail,
    StageSettingTriggerReorderRequest,
    StageSettingTriggerUpdate,
    StageSettingUpdate,
)
from app.modules.stage_setting_registry.service import StageSettingRegistryService

router = APIRouter(prefix="/stage-setting-sets", tags=["stage-setting-registry"])


def _error_response(exc: AppError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code, detail={"code": exc.code, "message": exc.message})


@router.get("", response_model=StageSettingSetPage)
def list_stage_setting_sets(
    page: int = 1,
    page_size: int = 50,
    scheme_type: SchemeType | None = None,
    status_filter: StageSettingSetStatus | None = None,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    _current_user: User = Depends(get_current_user),
) -> StageSettingSetPage:
    items = service.list_sets(scheme_type=scheme_type, status=status_filter)
    offset = (page - 1) * page_size
    page_items = items[offset : offset + page_size]
    return StageSettingSetPage(items=page_items, page=page, page_size=page_size, total=len(items))


@router.post("", response_model=StageSettingSetDetail, status_code=status.HTTP_201_CREATED)
def create_stage_setting_set(
    payload: StageSettingSetCreate,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    actor: User = Depends(require_permission("stage_setting_registry.manage")),
) -> StageSettingSetDetail:
    try:
        stage_setting_set = service.create_draft(
            scheme_type=payload.scheme_type,
            description=payload.description,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_set(stage_setting_set.stage_setting_set_id)
    assert detail is not None
    return detail


@router.get("/{stage_setting_set_id}", response_model=StageSettingSetDetail)
def get_stage_setting_set(
    stage_setting_set_id: uuid.UUID,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    _current_user: User = Depends(get_current_user),
) -> StageSettingSetDetail:
    detail = service.get_set(stage_setting_set_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Stage Setting Set not found")
    return detail


@router.patch("/{stage_setting_set_id}", response_model=StageSettingSetDetail)
def update_stage_setting_set(
    stage_setting_set_id: uuid.UUID,
    payload: StageSettingSetUpdate,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    actor: User = Depends(require_permission("stage_setting_registry.manage")),
) -> StageSettingSetDetail:
    fields = payload.model_dump(exclude={"change_reason"}, exclude_unset=True)
    try:
        service.update_draft_metadata(
            stage_setting_set_id,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
            **fields,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_set(stage_setting_set_id)
    assert detail is not None
    return detail


@router.delete("/{stage_setting_set_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stage_setting_set(
    stage_setting_set_id: uuid.UUID,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    actor: User = Depends(require_permission("stage_setting_registry.manage")),
) -> None:
    """ADR-024: physical deletion, Draft only. Returns a structured 404
    if the set does not exist, and a structured 409-equivalent (via
    `_error_response`'s own `ValidationAppError` mapping) if it is not
    Draft or is currently referenced by any UFLS/UVLS Scheme Version —
    never a raw database `IntegrityError`."""
    try:
        service.delete_draft(stage_setting_set_id, actor_user_id=actor.user_id)
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()


# --- Stages (StageSetting) — ADR-025 ---------------------------------------------


@router.get("/{stage_setting_set_id}/settings", response_model=list[StageSettingDetail])
def list_settings(
    stage_setting_set_id: uuid.UUID,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    _current_user: User = Depends(get_current_user),
) -> list[StageSettingDetail]:
    try:
        return service.list_settings(stage_setting_set_id)
    except AppError as exc:
        raise _error_response(exc) from exc


@router.post(
    "/{stage_setting_set_id}/settings",
    response_model=StageSettingDetail,
    status_code=status.HTTP_201_CREATED,
)
def add_stage(
    stage_setting_set_id: uuid.UUID,
    payload: StageSettingCreate,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    actor: User = Depends(require_permission("stage_setting_registry.manage")),
) -> StageSettingDetail:
    try:
        setting = service.add_stage(
            stage_setting_set_id,
            stage_order=payload.stage_order,
            region_scope_id=payload.region_scope_id,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_setting(setting.stage_setting_id)
    assert detail is not None
    return detail


@router.post("/{stage_setting_set_id}/settings/reorder", response_model=list[StageSettingDetail])
def reorder_settings(
    stage_setting_set_id: uuid.UUID,
    payload: StageSettingReorderRequest,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    actor: User = Depends(require_permission("stage_setting_registry.manage")),
) -> list[StageSettingDetail]:
    try:
        service.reorder_stages(
            stage_setting_set_id,
            region_scope_id=payload.region_scope_id,
            ordered_stage_setting_ids=payload.ordered_stage_setting_ids,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    return service.list_settings(stage_setting_set_id)


@router.patch(
    "/{stage_setting_set_id}/settings/{stage_setting_id}", response_model=StageSettingDetail
)
def update_stage(
    stage_setting_set_id: uuid.UUID,
    stage_setting_id: uuid.UUID,
    payload: StageSettingUpdate,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    actor: User = Depends(require_permission("stage_setting_registry.manage")),
) -> StageSettingDetail:
    fields = payload.model_dump(exclude={"change_reason"}, exclude_unset=True)
    try:
        service.update_stage(
            stage_setting_set_id,
            stage_setting_id,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
            **fields,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_setting(stage_setting_id)
    assert detail is not None
    return detail


@router.delete(
    "/{stage_setting_set_id}/settings/{stage_setting_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_stage(
    stage_setting_set_id: uuid.UUID,
    stage_setting_id: uuid.UUID,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    actor: User = Depends(require_permission("stage_setting_registry.manage")),
) -> None:
    try:
        service.remove_stage(stage_setting_set_id, stage_setting_id, actor_user_id=actor.user_id)
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()


# --- Triggers (StageSettingTrigger) — ADR-025 -------------------------------------


@router.get(
    "/{stage_setting_set_id}/settings/{stage_setting_id}/triggers",
    response_model=list[StageSettingTriggerDetail],
)
def list_triggers(
    stage_setting_set_id: uuid.UUID,
    stage_setting_id: uuid.UUID,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    _current_user: User = Depends(get_current_user),
) -> list[StageSettingTriggerDetail]:
    try:
        return service.list_triggers(stage_setting_set_id, stage_setting_id)
    except AppError as exc:
        raise _error_response(exc) from exc


@router.post(
    "/{stage_setting_set_id}/settings/{stage_setting_id}/triggers",
    response_model=StageSettingTriggerDetail,
    status_code=status.HTTP_201_CREATED,
)
def add_trigger(
    stage_setting_set_id: uuid.UUID,
    stage_setting_id: uuid.UUID,
    payload: StageSettingTriggerCreate,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    actor: User = Depends(require_permission("stage_setting_registry.manage")),
) -> StageSettingTriggerDetail:
    try:
        trigger = service.add_trigger(
            stage_setting_set_id,
            stage_setting_id,
            trigger_order=payload.trigger_order,
            threshold_value=payload.threshold_value,
            time_delay_ms=payload.time_delay_ms,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_trigger(trigger.stage_setting_trigger_id)
    assert detail is not None
    return detail


@router.post(
    "/{stage_setting_set_id}/settings/{stage_setting_id}/triggers/reorder",
    response_model=list[StageSettingTriggerDetail],
)
def reorder_triggers(
    stage_setting_set_id: uuid.UUID,
    stage_setting_id: uuid.UUID,
    payload: StageSettingTriggerReorderRequest,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    actor: User = Depends(require_permission("stage_setting_registry.manage")),
) -> list[StageSettingTriggerDetail]:
    try:
        service.reorder_triggers(
            stage_setting_set_id,
            stage_setting_id,
            ordered_trigger_ids=payload.ordered_trigger_ids,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    return service.list_triggers(stage_setting_set_id, stage_setting_id)


@router.patch(
    "/{stage_setting_set_id}/settings/{stage_setting_id}/triggers/{stage_setting_trigger_id}",
    response_model=StageSettingTriggerDetail,
)
def update_trigger(
    stage_setting_set_id: uuid.UUID,
    stage_setting_id: uuid.UUID,
    stage_setting_trigger_id: uuid.UUID,
    payload: StageSettingTriggerUpdate,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    actor: User = Depends(require_permission("stage_setting_registry.manage")),
) -> StageSettingTriggerDetail:
    fields = payload.model_dump(exclude={"change_reason"}, exclude_unset=True)
    try:
        service.update_trigger(
            stage_setting_set_id,
            stage_setting_id,
            stage_setting_trigger_id,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
            **fields,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_trigger(stage_setting_trigger_id)
    assert detail is not None
    return detail


@router.delete(
    "/{stage_setting_set_id}/settings/{stage_setting_id}/triggers/{stage_setting_trigger_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_trigger(
    stage_setting_set_id: uuid.UUID,
    stage_setting_id: uuid.UUID,
    stage_setting_trigger_id: uuid.UUID,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    actor: User = Depends(require_permission("stage_setting_registry.manage")),
) -> None:
    try:
        service.remove_trigger(
            stage_setting_set_id,
            stage_setting_id,
            stage_setting_trigger_id,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc
    service.db.commit()


# --- Lifecycle ---------------------------------------------------------------------


@router.post("/{stage_setting_set_id}/publish", response_model=StageSettingSetDetail)
def publish_stage_setting_set(
    stage_setting_set_id: uuid.UUID,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    actor: User = Depends(require_permission("stage_setting_registry.publish")),
) -> StageSettingSetDetail:
    try:
        service.publish(stage_setting_set_id, actor_user_id=actor.user_id)
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_set(stage_setting_set_id)
    assert detail is not None
    return detail


@router.post("/{stage_setting_set_id}/enter-in-error", response_model=StageSettingSetDetail)
def enter_in_error(
    stage_setting_set_id: uuid.UUID,
    payload: StageSettingSetEnterInErrorRequest,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    actor: User = Depends(require_permission("stage_setting_registry.enter_in_error")),
) -> StageSettingSetDetail:
    try:
        service.enter_in_error(
            stage_setting_set_id, change_reason=payload.change_reason, actor_user_id=actor.user_id
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_set(stage_setting_set_id)
    assert detail is not None
    return detail


@router.get("/{stage_setting_set_id}/audit-log", response_model=StageSettingRegistryAuditLogPage)
def list_audit_log(
    stage_setting_set_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    service: StageSettingRegistryService = Depends(get_stage_setting_registry_service),
    _current_user: User = Depends(get_current_user),
) -> StageSettingRegistryAuditLogPage:
    try:
        items, total = service.list_audit_log(stage_setting_set_id, page=page, page_size=page_size)
    except AppError as exc:
        raise _error_response(exc) from exc
    return StageSettingRegistryAuditLogPage(
        items=items, page=page, page_size=page_size, total=total
    )
