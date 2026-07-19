"""Fixtures shared by every UFLS test.

Builds real Substation Registry, Equipment Registry, PSS/E Integration,
Automatic Load Shedding Functionality, and Stage Setting Registry records
through their own service layers (never constructed directly —
CLAUDE.md A1): one PKLG-IGBK two-terminal circuit (committed and
activated as an Operational Snapshot, so `evaluate_boundary` has a real
topology to reason about), one transformer at PKLG with both terminals
registered as ALSF-capable (so direct-assignment tests exercise the
"eligible, no finding" path by default; a test wanting the ALSF-absent
finding path skips registering it), and one Published, grid-wide UFLS
Stage Setting Set with two stage settings.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session

from app.modules.automatic_load_shedding_functionality.bootstrap import (
    run_bootstrap as bootstrap_alsf,
)
from app.modules.automatic_load_shedding_functionality.service import (
    AutomaticLoadSheddingFunctionalityService,
)
from app.modules.equipment_registry.bootstrap import run_bootstrap as bootstrap_equipment_registry
from app.modules.equipment_registry.service import EquipmentRegistryService, TerminalInput
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
from app.modules.network_model.bootstrap import run_bootstrap as bootstrap_network_model
from app.modules.psse_integration.service import PsseIntegrationService
from app.modules.stage_setting_registry.bootstrap import (
    run_bootstrap as bootstrap_stage_setting_registry,
)
from app.modules.stage_setting_registry.service import StageSettingRegistryService
from app.modules.substation_registry.service import SubstationService
from app.modules.ufls.bootstrap import run_bootstrap as bootstrap_ufls
from app.modules.ufls.service import UflsService
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

_TOPOLOGY_RAW = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.0,0.0
200,'IGBK132',132.0,1,1,1,1,1.0,0.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'1',0.001,0.01,0.0002
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""


@dataclass
class ReferenceIds:
    voltage_level_id: int
    lv_voltage_level_id: int
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
    voltage_level = db_session.query(VoltageLevel).filter_by(label="132kV").one()
    lv_voltage_level = db_session.query(VoltageLevel).filter_by(label="33kV").one()
    line_type = db_session.query(LineType).filter_by(code="OVERHEAD").one()
    region = db_session.query(Region).filter_by(code="NORTH").one()
    gm_zone = db_session.query(GmZone).filter_by(code="KEDP").one()
    state = db_session.query(State).filter_by(code="SEL").one()
    grid_owner = db_session.query(GridOwner).filter_by(code="TNB").one()
    statuses = {s.code: s.operational_status_id for s in db_session.query(OperationalStatus).all()}
    return ReferenceIds(
        voltage_level_id=voltage_level.voltage_level_id,
        lv_voltage_level_id=lv_voltage_level.voltage_level_id,
        line_type_id=line_type.line_type_id,
        status_id_by_code=statuses,
        region_id=region.region_id,
        gm_zone_id=gm_zone.gm_zone_id,
        state_id=state.state_id,
        grid_owner_id=grid_owner.grid_owner_id,
    )


@pytest.fixture()
def bootstrapped_permissions(db_session: Session) -> None:
    bootstrap_iam(db_session)
    bootstrap_equipment_registry(db_session)
    bootstrap_network_model(db_session)
    bootstrap_alsf(db_session)
    bootstrap_stage_setting_registry(db_session)
    bootstrap_ufls(db_session)


@pytest.fixture()
def actor_user_id(db_session: Session, bootstrapped_permissions: None) -> uuid.UUID:
    iam = IAMService(db_session)
    user = iam.create_user(
        username="ufls_editor",
        display_name="UFLS Test Actor",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    role = next(r for r in iam.list_roles() if r.name == "Administrator")
    iam.assign_role_to_user(user_id=user.user_id, role_id=role.role_id, actor_user_id=None)
    db_session.commit()
    return user.user_id


@dataclass
class Fixture:
    topology_version_id: uuid.UUID
    pklg_igbk_circuit_terminal_ids: list[uuid.UUID]
    transformer_terminal_id: uuid.UUID
    igbk_transformer_terminal_id: uuid.UUID
    substation_id: uuid.UUID
    stage_setting_set_id: uuid.UUID
    stage_setting_ids: list[uuid.UUID]


@pytest.fixture()
def ufls_fixture(
    db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
) -> Fixture:
    substation_service = SubstationService(db_session)
    equipment_service = EquipmentRegistryService(db_session)
    alsf_service = AutomaticLoadSheddingFunctionalityService(db_session)

    substation_ids: dict[str, uuid.UUID] = {}
    for mnemonic in ["PKLG", "IGBK"]:
        substation = substation_service.create_substation(
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
        substation_ids[mnemonic] = substation.substation_id
    db_session.commit()

    yard_ids: dict[str, uuid.UUID] = {}
    for mnemonic, substation_id in substation_ids.items():
        yard = equipment_service.create_voltage_yard(
            substation_id=substation_id,
            voltage_level_id=reference_ids.voltage_level_id,
            actor_user_id=actor_user_id,
        )
        yard_ids[mnemonic] = yard.voltage_yard_id
    db_session.commit()

    circuit = equipment_service.create_circuit(
        bay_number="1",
        voltage_level_id=reference_ids.voltage_level_id,
        line_type_id=reference_ids.line_type_id,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=yard_ids["PKLG"], breaker_number="CB1"),
            TerminalInput(voltage_yard_id=yard_ids["IGBK"], breaker_number="CB2"),
        ],
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    psse_service = PsseIntegrationService(db_session)
    batch = psse_service.commit(_TOPOLOGY_RAW, "ufls-fixture.raw", actor_user_id)
    db_session.commit()
    psse_service.activate(
        batch.batch_id, change_reason="test baseline", actor_user_id=actor_user_id
    )
    db_session.commit()

    circuit_terminal_ids = [
        t.circuit_terminal_id for t in equipment_service.repo.list_terminals(circuit.circuit_id)
    ]
    for circuit_terminal_id in circuit_terminal_ids:
        alsf_service.create(
            target_type="CIRCUIT_TERMINAL",
            circuit_terminal_id=circuit_terminal_id,
            transformer_terminal_id=None,
            ufls_function=True,
            uvls_function=False,
            relay_make=None,
            relay_model=None,
            remarks=None,
            actor_user_id=actor_user_id,
        )
    db_session.commit()

    lv_yard = equipment_service.create_voltage_yard(
        substation_id=substation_ids["PKLG"],
        voltage_level_id=reference_ids.lv_voltage_level_id,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    transformer = equipment_service.create_transformer(
        substation_id=substation_ids["PKLG"],
        transformer_number="1",
        hv_switchyard_id=yard_ids["PKLG"],
        hv_breaker_number="T11",
        lv_switchyard_id=lv_yard.voltage_yard_id,
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
    lv_terminal = next(
        t
        for t in equipment_service.repo.list_transformer_terminals(transformer.transformer_id)
        if t.side == "LV"
    )
    alsf_service.create(
        target_type="TRANSFORMER_TERMINAL",
        circuit_terminal_id=None,
        transformer_terminal_id=lv_terminal.transformer_terminal_id,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    igbk_lv_yard = equipment_service.create_voltage_yard(
        substation_id=substation_ids["IGBK"],
        voltage_level_id=reference_ids.lv_voltage_level_id,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    igbk_transformer = equipment_service.create_transformer(
        substation_id=substation_ids["IGBK"],
        transformer_number="1",
        hv_switchyard_id=yard_ids["IGBK"],
        hv_breaker_number="T21",
        lv_switchyard_id=igbk_lv_yard.voltage_yard_id,
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
    igbk_lv_terminal = next(
        t
        for t in equipment_service.repo.list_transformer_terminals(igbk_transformer.transformer_id)
        if t.side == "LV"
    )
    alsf_service.create(
        target_type="TRANSFORMER_TERMINAL",
        circuit_terminal_id=None,
        transformer_terminal_id=igbk_lv_terminal.transformer_terminal_id,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    stage_registry = StageSettingRegistryService(db_session)
    stage_set = stage_registry.create_draft(
        scheme_type="UFLS", description="UFLS test set", actor_user_id=actor_user_id
    )
    db_session.commit()
    setting_1 = stage_registry.add_stage(
        stage_set.stage_setting_set_id,
        stage_order=1,
        region_scope_id=None,
        actor_user_id=actor_user_id,
    )
    stage_registry.add_trigger(
        stage_set.stage_setting_set_id,
        setting_1.stage_setting_id,
        trigger_order=1,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    setting_2 = stage_registry.add_stage(
        stage_set.stage_setting_set_id,
        stage_order=2,
        region_scope_id=None,
        actor_user_id=actor_user_id,
    )
    stage_registry.add_trigger(
        stage_set.stage_setting_set_id,
        setting_2.stage_setting_id,
        trigger_order=1,
        threshold_value=49.0,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    stage_registry.publish(stage_set.stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    return Fixture(
        topology_version_id=batch.topology_version_id,
        pklg_igbk_circuit_terminal_ids=circuit_terminal_ids,
        transformer_terminal_id=lv_terminal.transformer_terminal_id,
        igbk_transformer_terminal_id=igbk_lv_terminal.transformer_terminal_id,
        substation_id=substation_ids["PKLG"],
        stage_setting_set_id=stage_set.stage_setting_set_id,
        stage_setting_ids=[setting_1.stage_setting_id, setting_2.stage_setting_id],
    )


@pytest.fixture()
def ufls_service(db_session: Session) -> UflsService:
    return UflsService(db_session)
