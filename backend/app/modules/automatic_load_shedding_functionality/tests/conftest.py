"""Fixtures shared by every Automatic Load Shedding Functionality Registry
test. Builds real Substation Registry / Equipment Registry records through
their own service layers (never constructed directly — CLAUDE.md A1): two
substations, a voltage yard each, a real two-terminal `Circuit`, and a real
`Transformer` — enough Bay Terminals to exercise both `target_type`
branches this module supports.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session

from app.modules.automatic_load_shedding_functionality.bootstrap import (
    run_bootstrap as bootstrap_automatic_load_shedding_functionality,
)
from app.modules.equipment_registry.bootstrap import run_bootstrap as bootstrap_equipment_registry
from app.modules.equipment_registry.service import EquipmentRegistryService, TerminalInput
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
from app.modules.substation_registry.service import SubstationService
from app.reference_data.models import (
    GmZone,
    GridOwner,
    LineType,
    OperationalStatus,
    Region,
    State,
    VoltageLevel,
)
from app.reference_data.seed import run_seed


@dataclass
class ReferenceIds:
    voltage_level_id: int
    second_voltage_level_id: int
    line_type_id: int
    status_id_by_code: dict[str, int]
    region_id: int
    gm_zone_id: int
    state_id: int
    grid_owner_id: int


@pytest.fixture()
def reference_ids(db_session: Session) -> ReferenceIds:
    run_seed(db_session)
    db_session.commit()

    voltage_level = db_session.query(VoltageLevel).filter_by(label="500kV").one()
    second_voltage_level = db_session.query(VoltageLevel).filter_by(label="132kV").one()
    line_type = db_session.query(LineType).filter_by(code="OVERHEAD").one()
    region = db_session.query(Region).filter_by(code="NORTH").one()
    gm_zone = db_session.query(GmZone).filter_by(code="KEDP").one()
    state = db_session.query(State).filter_by(code="SEL").one()
    grid_owner = db_session.query(GridOwner).filter_by(code="TNB").one()
    statuses = {s.code: s.operational_status_id for s in db_session.query(OperationalStatus).all()}

    return ReferenceIds(
        voltage_level_id=voltage_level.voltage_level_id,
        second_voltage_level_id=second_voltage_level.voltage_level_id,
        line_type_id=line_type.line_type_id,
        status_id_by_code=statuses,
        region_id=region.region_id,
        gm_zone_id=gm_zone.gm_zone_id,
        state_id=state.state_id,
        grid_owner_id=grid_owner.grid_owner_id,
    )


@pytest.fixture()
def actor_user_id(db_session: Session) -> uuid.UUID:
    """A locally-authenticated IAM user holding this module's own
    `automatic_load_shedding_functionality.write` permission, plus
    Equipment Registry's write permission (used only by fixture setup, to
    create real circuits/transformers directly through their own service
    layer)."""
    iam = IAMService(db_session)
    user = iam.create_user(
        username="alsf_editor",
        display_name="ALSF Editor",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    role = iam.create_role(
        name="Automatic Load Shedding Functionality Editor (test)",
        description=None,
        actor_user_id=None,
    )
    for permission_id, label, module_scope in (
        (
            "automatic_load_shedding_functionality.write",
            "Manage automatic load shedding functionality records",
            "automatic_load_shedding_functionality",
        ),
        ("equipment_registry.write", "Manage circuits", "equipment_registry"),
    ):
        iam.register_permission(
            permission_id=permission_id, label=label, description=None, module_scope=module_scope
        )
        iam.grant_permission_to_role(
            role_id=role.role_id, permission_id=permission_id, actor_user_id=None
        )
    iam.assign_role_to_user(user_id=user.user_id, role_id=role.role_id, actor_user_id=None)
    db_session.commit()
    return user.user_id


@pytest.fixture()
def substation_ids(
    db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    service = SubstationService(db_session)
    mnemonics = ["PKLG", "IGBK"]
    ids: dict[str, uuid.UUID] = {}
    for mnemonic in mnemonics:
        substation = service.create_substation(
            mnemonic=mnemonic,
            official_name=f"{mnemonic} Substation",
            region_id=reference_ids.region_id,
            gm_zone_id=reference_ids.gm_zone_id,
            state_id=reference_ids.state_id,
            grid_owner_id=reference_ids.grid_owner_id,
            operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
            psse_bus_number=None,
            latitude=None,
            longitude=None,
            commissioned_date=None,
            remarks=None,
            actor_user_id=actor_user_id,
        )
        ids[mnemonic] = substation.substation_id
    db_session.commit()
    return ids


@pytest.fixture()
def voltage_yard_ids(
    db_session: Session,
    reference_ids: ReferenceIds,
    substation_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> dict[str, uuid.UUID]:
    service = EquipmentRegistryService(db_session)
    ids: dict[str, uuid.UUID] = {}
    for mnemonic, substation_id in substation_ids.items():
        yard = service.create_voltage_yard(
            substation_id=substation_id,
            voltage_level_id=reference_ids.voltage_level_id,
            actor_user_id=actor_user_id,
        )
        ids[mnemonic] = yard.voltage_yard_id
    db_session.commit()
    return ids


@pytest.fixture()
def lv_voltage_yard_ids(
    db_session: Session,
    reference_ids: ReferenceIds,
    substation_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> dict[str, uuid.UUID]:
    """PKLG-only LV yard, for the transformer fixture."""
    service = EquipmentRegistryService(db_session)
    yard = service.create_voltage_yard(
        substation_id=substation_ids["PKLG"],
        voltage_level_id=reference_ids.second_voltage_level_id,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    return {"PKLG": yard.voltage_yard_id}


@dataclass
class CircuitTerminals:
    circuit_id: uuid.UUID
    pklg_terminal_id: uuid.UUID
    igbk_terminal_id: uuid.UUID


@pytest.fixture()
def circuit_terminals(
    db_session: Session,
    reference_ids: ReferenceIds,
    voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> CircuitTerminals:
    """A real, two-terminal `Circuit` (PKLG-IGBK) — the `CircuitTerminal`
    Bay Terminals this module's `target_type=CIRCUIT_TERMINAL` records
    reference."""
    service = EquipmentRegistryService(db_session)
    circuit = service.create_circuit(
        bay_number="1",
        voltage_level_id=reference_ids.voltage_level_id,
        line_type_id=reference_ids.line_type_id,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L11"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["IGBK"], breaker_number="L12"),
        ],
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_circuit(circuit.circuit_id)
    assert detail is not None
    by_mnemonic = {t.substation_mnemonic: t.circuit_terminal_id for t in detail.terminals}
    return CircuitTerminals(
        circuit_id=circuit.circuit_id,
        pklg_terminal_id=by_mnemonic["PKLG"],
        igbk_terminal_id=by_mnemonic["IGBK"],
    )


@dataclass
class TransformerTerminals:
    transformer_id: uuid.UUID
    hv_terminal_id: uuid.UUID
    lv_terminal_id: uuid.UUID


@pytest.fixture()
def transformer_terminals(
    db_session: Session,
    reference_ids: ReferenceIds,
    substation_ids: dict[str, uuid.UUID],
    voltage_yard_ids: dict[str, uuid.UUID],
    lv_voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> TransformerTerminals:
    """A real PKLG `Transformer` — the `TransformerTerminal` Bay Terminals
    this module's `target_type=TRANSFORMER_TERMINAL` records reference."""
    service = EquipmentRegistryService(db_session)
    transformer = service.create_transformer(
        substation_id=substation_ids["PKLG"],
        transformer_number="1",
        hv_switchyard_id=voltage_yard_ids["PKLG"],
        hv_breaker_number="T11",
        lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
        lv_breaker_number="T12",
        capacity_mva=150,
        commissioning_date=None,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        transformer_type=None,
        manufacturer=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_transformer(transformer.transformer_id)
    assert detail is not None
    by_side = {t.side: t.transformer_terminal_id for t in detail.terminals}
    return TransformerTerminals(
        transformer_id=transformer.transformer_id,
        hv_terminal_id=by_side["HV"],
        lv_terminal_id=by_side["LV"],
    )


@pytest.fixture()
def second_circuit_terminals(
    db_session: Session,
    reference_ids: ReferenceIds,
    voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> CircuitTerminals:
    """A second, parallel PKLG-IGBK `Circuit` at the same voltage level as
    `circuit_terminals` (bay_number "2" instead of "1") — used to confirm
    two Bay Terminals at the same substation and voltage level are always
    displayed with a distinct `bay_label` (engineering refinement: Complete
    Engineering Identity Display)."""
    service = EquipmentRegistryService(db_session)
    circuit = service.create_circuit(
        bay_number="2",
        voltage_level_id=reference_ids.voltage_level_id,
        line_type_id=reference_ids.line_type_id,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L21"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["IGBK"], breaker_number="L22"),
        ],
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_circuit(circuit.circuit_id)
    assert detail is not None
    by_mnemonic = {t.substation_mnemonic: t.circuit_terminal_id for t in detail.terminals}
    return CircuitTerminals(
        circuit_id=circuit.circuit_id,
        pklg_terminal_id=by_mnemonic["PKLG"],
        igbk_terminal_id=by_mnemonic["IGBK"],
    )


@pytest.fixture()
def second_transformer_terminals(
    db_session: Session,
    reference_ids: ReferenceIds,
    substation_ids: dict[str, uuid.UUID],
    voltage_yard_ids: dict[str, uuid.UUID],
    lv_voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> TransformerTerminals:
    """A second PKLG `Transformer` at the same HV/LV voltage levels as
    `transformer_terminals` (transformer_number "2" instead of "1") — used
    to confirm two Bay Terminals at the same substation and voltage level
    are always displayed with a distinct `bay_label`."""
    service = EquipmentRegistryService(db_session)
    transformer = service.create_transformer(
        substation_id=substation_ids["PKLG"],
        transformer_number="2",
        hv_switchyard_id=voltage_yard_ids["PKLG"],
        hv_breaker_number="T21",
        lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
        lv_breaker_number="T22",
        capacity_mva=150,
        commissioning_date=None,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        transformer_type=None,
        manufacturer=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_transformer(transformer.transformer_id)
    assert detail is not None
    by_side = {t.side: t.transformer_terminal_id for t in detail.terminals}
    return TransformerTerminals(
        transformer_id=transformer.transformer_id,
        hv_terminal_id=by_side["HV"],
        lv_terminal_id=by_side["LV"],
    )


@pytest.fixture()
def bootstrapped_permissions(db_session: Session) -> None:
    bootstrap_iam(db_session)
    bootstrap_equipment_registry(db_session)
    bootstrap_automatic_load_shedding_functionality(db_session)
