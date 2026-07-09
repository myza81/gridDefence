"""Fixtures shared by every Network Model test.

Builds real Substation Registry and Equipment Registry records through
their own service layers (never constructed directly — CLAUDE.md A1),
including one ordinary two-terminal circuit, one three-terminal tee-off
circuit, and one transformer — enough to exercise connectivity,
equipment relationships, neighbours, and traversal, including the
tee-off/multi-terminal configurations this phase's tests are required to
cover.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session

from app.modules.equipment_registry.bootstrap import run_bootstrap as bootstrap_equipment_registry
from app.modules.equipment_registry.service import EquipmentRegistryService, TerminalInput
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
from app.modules.network_model.bootstrap import run_bootstrap as bootstrap_network_model
from app.modules.substation_registry.service import SubstationService
from app.reference_data.models import (
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
    state = db_session.query(State).filter_by(code="SEL").one()
    grid_owner = db_session.query(GridOwner).filter_by(code="TNB").one()
    statuses = {s.code: s.operational_status_id for s in db_session.query(OperationalStatus).all()}

    return ReferenceIds(
        voltage_level_id=voltage_level.voltage_level_id,
        second_voltage_level_id=second_voltage_level.voltage_level_id,
        line_type_id=line_type.line_type_id,
        status_id_by_code=statuses,
        region_id=region.region_id,
        state_id=state.state_id,
        grid_owner_id=grid_owner.grid_owner_id,
    )


@pytest.fixture()
def actor_user_id(db_session: Session) -> uuid.UUID:
    iam = IAMService(db_session)
    user = iam.create_user(
        username="network_model_editor",
        display_name="Network Model Test Actor",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    return user.user_id


@pytest.fixture()
def substation_ids(
    db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    """PKLG/IGBK/NKST for an ordinary two-terminal circuit plus a
    three-way tee-off among all three; ABBA is left deliberately
    unconnected (zero circuits, zero transformers) to exercise the
    incomplete-registry / "empty is valid" behaviour this phase's
    architecture requires."""
    service = SubstationService(db_session)
    mnemonics = ["PKLG", "IGBK", "NKST", "ABBA"]
    ids: dict[str, uuid.UUID] = {}
    for mnemonic in mnemonics:
        substation = service.create_substation(
            mnemonic=mnemonic,
            official_name=f"{mnemonic} Substation",
            region_id=reference_ids.region_id,
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
    """LV-side yard, PKLG only — enough for one transformer fixture."""
    service = EquipmentRegistryService(db_session)
    yard = service.create_voltage_yard(
        substation_id=substation_ids["PKLG"],
        voltage_level_id=reference_ids.second_voltage_level_id,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    return {"PKLG": yard.voltage_yard_id}


@dataclass
class CircuitIds:
    two_terminal_circuit_id: uuid.UUID
    tee_off_circuit_id: uuid.UUID


@pytest.fixture()
def circuit_ids(
    db_session: Session,
    reference_ids: ReferenceIds,
    voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> CircuitIds:
    """One ordinary PKLG-IGBK two-terminal circuit, and one PKLG-IGBK-NKST
    three-terminal tee-off — the two shapes every connectivity/traversal
    test in this module must handle without assuming exactly two
    terminals."""
    service = EquipmentRegistryService(db_session)

    two_terminal = service.create_circuit(
        bay_number="Line 1",
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

    tee_off = service.create_circuit(
        bay_number="Line 2",
        voltage_level_id=reference_ids.voltage_level_id,
        line_type_id=reference_ids.line_type_id,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L21"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["IGBK"], breaker_number="L22"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["NKST"], breaker_number="L23"),
        ],
        actor_user_id=actor_user_id,
    )

    db_session.commit()
    return CircuitIds(
        two_terminal_circuit_id=two_terminal.circuit_id, tee_off_circuit_id=tee_off.circuit_id
    )


@pytest.fixture()
def transformer_id(
    db_session: Session,
    reference_ids: ReferenceIds,
    substation_ids: dict[str, uuid.UUID],
    voltage_yard_ids: dict[str, uuid.UUID],
    lv_voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> uuid.UUID:
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
    return transformer.transformer_id


@pytest.fixture()
def bootstrapped_network_model_permissions(db_session: Session) -> None:
    bootstrap_iam(db_session)
    bootstrap_equipment_registry(db_session)
    bootstrap_network_model(db_session)


# --- Operational Snapshot fixtures (Phase 7E — traversal migration) -----------------
#
# The traversal engine now reads TopologyBus/TopologyBranch/TopologyTransformer
# (PSS/E Integration's own tables) rather than Circuit/CircuitTerminal. These
# fixtures build a real Operational Snapshot via `PsseIntegrationService.commit()`
# (never constructed directly — CLAUDE.md A1), using the same PKLG/IGBK/NKST/ABBA
# mnemonics `substation_ids` already registers, so `_match_substation_for_bus`
# correlates each Bus to the same Substation these tests already know by name.

_OPERATIONAL_TOPOLOGY_RAW = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.0,0.0
200,'IGBK132',132.0,1,1,1,1,1.0,0.0
300,'NKST132',132.0,1,1,1,1,1.0,0.0
400,'ABBA132',132.0,1,1,1,1,1.0,0.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'1',0.001,0.01,0.0002
200,300,'2',0.001,0.01,0.0002
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""


@pytest.fixture()
def operational_topology_version_id(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> uuid.UUID:
    """The Operational Snapshot equivalent of `circuit_ids`' registry-only
    PKLG-IGBK-NKST-ABBA topology: Bus 100/200/300/400 for PKLG/IGBK/NKST/
    ABBA, Branch 100-200 and 200-300 (a simple chain — PKLG-IGBK-NKST all
    connected). ABBA (bus 400) is deliberately isolated, no Branch at all
    — mirrors `circuit_ids`' own "ABBA has zero circuits" design.
    Committed and activated, so it is the Current TopologyVersion."""
    from app.modules.psse_integration.service import PsseIntegrationService

    service = PsseIntegrationService(db_session)
    batch = service.commit(_OPERATIONAL_TOPOLOGY_RAW, "network-model-traversal.raw", actor_user_id)
    db_session.commit()
    service.activate(batch.batch_id, change_reason="test baseline", actor_user_id=actor_user_id)
    db_session.commit()
    return batch.topology_version_id


@dataclass
class OperationalCircuitCorrelation:
    topology_version_id: uuid.UUID
    pklg_igbk_circuit_id: uuid.UUID
    igbk_nkst_circuit_id: uuid.UUID


@pytest.fixture()
def operational_topology_with_correlated_circuits(
    db_session: Session,
    operational_topology_version_id: uuid.UUID,
    reference_ids: ReferenceIds,
    voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> OperationalCircuitCorrelation:
    """Registers two real Circuits — bay_number '1' (PKLG-IGBK), bay_number
    '2' (IGBK-NKST) — matching `operational_topology_version_id`'s own
    Branch `ckt_id`s exactly, then recomputes `EquipmentTopologyMap`
    correlation against it (`_run_matching` only runs automatically at
    commit time for a *new* TopologyVersion; these Circuits are
    registered afterward, so an explicit recompute is needed, exactly as
    `psse_integration`'s own `recompute_matching` is designed for). This
    is what `traverse()`'s `excluded_circuit_ids` -> Operational edge
    translation needs to have something concrete to exclude."""
    from app.modules.psse_integration.service import PsseIntegrationService

    eq_service = EquipmentRegistryService(db_session)
    pklg_igbk = eq_service.create_circuit(
        bay_number="1",
        voltage_level_id=reference_ids.voltage_level_id,
        line_type_id=reference_ids.line_type_id,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="CB1"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["IGBK"], breaker_number="CB2"),
        ],
        actor_user_id=actor_user_id,
    )
    igbk_nkst = eq_service.create_circuit(
        bay_number="2",
        voltage_level_id=reference_ids.voltage_level_id,
        line_type_id=reference_ids.line_type_id,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=voltage_yard_ids["IGBK"], breaker_number="CB3"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["NKST"], breaker_number="CB4"),
        ],
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    psse_service = PsseIntegrationService(db_session)
    psse_service.recompute_matching(operational_topology_version_id, actor_user_id=actor_user_id)
    db_session.commit()

    return OperationalCircuitCorrelation(
        topology_version_id=operational_topology_version_id,
        pklg_igbk_circuit_id=pklg_igbk.circuit_id,
        igbk_nkst_circuit_id=igbk_nkst.circuit_id,
    )
