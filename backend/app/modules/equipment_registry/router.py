"""Equipment Registry router (CLAUDE.md §14) — HTTP, request validation,
authentication only. No business logic — every handler delegates to
`EquipmentRegistryService`.

Read endpoints require only authentication (`get_current_user`), not the
`equipment_registry.read` permission — mirroring Substation Registry's own
precedent (substation_registry/router.py): this is engineering reference
data, not sensitive (equipment-registry-module.md §15). Write endpoints
(create/update/status-change/add-terminal/update-terminal/create-voltage-yard)
require `equipment_registry.write`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.equipment_registry.dependencies import get_equipment_registry_service
from app.modules.equipment_registry.exceptions import AppError, NotFoundError, ValidationAppError
from app.modules.equipment_registry.schemas import (
    CircuitAuditLogPage,
    CircuitCreate,
    CircuitDetail,
    CircuitPage,
    CircuitStatusChange,
    CircuitTerminalAdd,
    CircuitTerminalSummary,
    CircuitTerminalUpdate,
    CircuitUpdate,
    VoltageYardCreate,
    VoltageYardSummary,
    VoltageYardUpdate,
)
from app.modules.equipment_registry.service import EquipmentRegistryService, TerminalInput
from app.modules.iam.dependencies import get_current_user, require_permission
from app.modules.iam.models import User

router = APIRouter(prefix="/circuits", tags=["equipment-registry"])
voltage_yard_router = APIRouter(prefix="/voltage-yards", tags=["equipment-registry"])


def _error_response(exc: AppError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code, detail={"code": exc.code, "message": exc.message})


@router.get("", response_model=CircuitPage)
def list_circuits(
    page: int = 1,
    page_size: int = 50,
    voltage_level_id: int | None = None,
    line_type_id: int | None = None,
    operational_status_id: int | None = None,
    is_interconnector: bool | None = None,
    search: str | None = None,
    service: EquipmentRegistryService = Depends(get_equipment_registry_service),
    _current_user: User = Depends(get_current_user),
) -> CircuitPage:
    items, total = service.list_circuits(
        page=page,
        page_size=page_size,
        voltage_level_id=voltage_level_id,
        line_type_id=line_type_id,
        operational_status_id=operational_status_id,
        is_interconnector=is_interconnector,
        search=search,
    )
    return CircuitPage(items=items, page=page, page_size=page_size, total=total)


@router.post("", response_model=CircuitDetail, status_code=status.HTTP_201_CREATED)
def create_circuit(
    payload: CircuitCreate,
    service: EquipmentRegistryService = Depends(get_equipment_registry_service),
    actor: User = Depends(require_permission("equipment_registry.write")),
) -> CircuitDetail:
    try:
        circuit = service.create_circuit(
            bay_number=payload.bay_number,
            voltage_level_id=payload.voltage_level_id,
            line_type_id=payload.line_type_id,
            operational_status_id=payload.operational_status_id,
            is_interconnector=payload.is_interconnector,
            remarks=payload.remarks,
            terminals=[
                TerminalInput(
                    voltage_yard_id=t.voltage_yard_id,
                    breaker_number=t.breaker_number,
                    commissioning_date=t.commissioning_date,
                    remarks=t.remarks,
                )
                for t in payload.terminals
            ],
            actor_user_id=actor.user_id,
        )
    except ValidationAppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_circuit(circuit.circuit_id)
    assert detail is not None
    return detail


@router.get("/{circuit_id}", response_model=CircuitDetail)
def get_circuit(
    circuit_id: uuid.UUID,
    service: EquipmentRegistryService = Depends(get_equipment_registry_service),
    _current_user: User = Depends(get_current_user),
) -> CircuitDetail:
    detail = service.get_circuit(circuit_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Circuit not found")
    return detail


@router.patch("/{circuit_id}", response_model=CircuitDetail)
def update_circuit(
    circuit_id: uuid.UUID,
    payload: CircuitUpdate,
    service: EquipmentRegistryService = Depends(get_equipment_registry_service),
    actor: User = Depends(require_permission("equipment_registry.write")),
) -> CircuitDetail:
    fields = payload.model_dump(exclude_unset=True)
    try:
        service.update_circuit(circuit_id, actor_user_id=actor.user_id, **fields)
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_circuit(circuit_id)
    assert detail is not None
    return detail


@router.post("/{circuit_id}/status", response_model=CircuitDetail)
def change_status(
    circuit_id: uuid.UUID,
    payload: CircuitStatusChange,
    service: EquipmentRegistryService = Depends(get_equipment_registry_service),
    actor: User = Depends(require_permission("equipment_registry.write")),
) -> CircuitDetail:
    try:
        service.change_status(
            circuit_id,
            operational_status_id=payload.operational_status_id,
            change_reason=payload.change_reason,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_circuit(circuit_id)
    assert detail is not None
    return detail


@router.get("/{circuit_id}/terminals", response_model=list[CircuitTerminalSummary])
def list_terminals(
    circuit_id: uuid.UUID,
    service: EquipmentRegistryService = Depends(get_equipment_registry_service),
    _current_user: User = Depends(get_current_user),
) -> list[CircuitTerminalSummary]:
    if service.get_circuit(circuit_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Circuit not found")
    return service.list_terminals(circuit_id)


@router.post(
    "/{circuit_id}/terminals",
    response_model=CircuitDetail,
    status_code=status.HTTP_201_CREATED,
)
def add_terminal(
    circuit_id: uuid.UUID,
    payload: CircuitTerminalAdd,
    service: EquipmentRegistryService = Depends(get_equipment_registry_service),
    actor: User = Depends(require_permission("equipment_registry.write")),
) -> CircuitDetail:
    try:
        service.add_terminal(
            circuit_id,
            voltage_yard_id=payload.voltage_yard_id,
            breaker_number=payload.breaker_number,
            commissioning_date=payload.commissioning_date,
            remarks=payload.remarks,
            actor_user_id=actor.user_id,
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_circuit(circuit_id)
    assert detail is not None
    return detail


@router.patch("/{circuit_id}/terminals/{circuit_terminal_id}", response_model=CircuitDetail)
def update_terminal(
    circuit_id: uuid.UUID,
    circuit_terminal_id: uuid.UUID,
    payload: CircuitTerminalUpdate,
    service: EquipmentRegistryService = Depends(get_equipment_registry_service),
    actor: User = Depends(require_permission("equipment_registry.write")),
) -> CircuitDetail:
    fields = payload.model_dump(exclude_unset=True)
    try:
        service.update_terminal(
            circuit_id, circuit_terminal_id, actor_user_id=actor.user_id, **fields
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    detail = service.get_circuit(circuit_id)
    assert detail is not None
    return detail


@router.get("/{circuit_id}/audit-log", response_model=CircuitAuditLogPage)
def list_audit_log(
    circuit_id: uuid.UUID,
    page: int = 1,
    page_size: int = 50,
    service: EquipmentRegistryService = Depends(get_equipment_registry_service),
    _current_user: User = Depends(get_current_user),
) -> CircuitAuditLogPage:
    if service.get_circuit(circuit_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Circuit not found")
    items, total = service.list_audit_log(circuit_id, page=page, page_size=page_size)
    return CircuitAuditLogPage(items=items, page=page, page_size=page_size, total=total)


# --- Substation Voltage Yards (equipment-registry-module.md §7.5a; ADR-008) -----------


@voltage_yard_router.get("", response_model=list[VoltageYardSummary])
def list_voltage_yards(
    substation_id: uuid.UUID | None = None,
    service: EquipmentRegistryService = Depends(get_equipment_registry_service),
    _current_user: User = Depends(get_current_user),
) -> list[VoltageYardSummary]:
    return service.list_voltage_yards(substation_id=substation_id)


@voltage_yard_router.post(
    "", response_model=VoltageYardSummary, status_code=status.HTTP_201_CREATED
)
def create_voltage_yard(
    payload: VoltageYardCreate,
    service: EquipmentRegistryService = Depends(get_equipment_registry_service),
    actor: User = Depends(require_permission("equipment_registry.write")),
) -> VoltageYardSummary:
    try:
        yard = service.create_voltage_yard(
            substation_id=payload.substation_id,
            voltage_level_id=payload.voltage_level_id,
            commissioning_date=payload.commissioning_date,
            latitude=payload.latitude,
            longitude=payload.longitude,
            actor_user_id=actor.user_id,
        )
    except ValidationAppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    summaries = service.list_voltage_yards(substation_id=yard.substation_id)
    match = next((s for s in summaries if s.voltage_yard_id == yard.voltage_yard_id), None)
    assert match is not None
    return match


@voltage_yard_router.patch("/{voltage_yard_id}", response_model=VoltageYardSummary)
def update_voltage_yard(
    voltage_yard_id: uuid.UUID,
    payload: VoltageYardUpdate,
    service: EquipmentRegistryService = Depends(get_equipment_registry_service),
    actor: User = Depends(require_permission("equipment_registry.write")),
) -> VoltageYardSummary:
    fields = payload.model_dump(exclude_unset=True)
    try:
        yard = service.update_voltage_yard(voltage_yard_id, actor_user_id=actor.user_id, **fields)
    except ValidationAppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    summaries = service.list_voltage_yards(substation_id=yard.substation_id)
    match = next((s for s in summaries if s.voltage_yard_id == yard.voltage_yard_id), None)
    assert match is not None
    return match
