"""Fixtures shared by every PSS/E Integration test.

Mirrors app/modules/equipment_registry/tests/conftest.py's own pattern:
seeds Core Platform reference data, provisions a locally-authenticated IAM
user holding this module's own permissions, and creates real Substation
Registry / Equipment Registry records (via their own service layers, never
constructed directly — CLAUDE.md A1) for topology-to-equipment matching
tests to exercise against.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session

from app.modules.equipment_registry.service import EquipmentRegistryService, TerminalInput
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
    line_type = db_session.query(LineType).filter_by(code="OVERHEAD").one()
    region = db_session.query(Region).filter_by(code="NORTH").one()
    gm_zone = db_session.query(GmZone).filter_by(code="ALOR_SETAR").one()
    state = db_session.query(State).filter_by(code="SEL").one()
    grid_owner = db_session.query(GridOwner).filter_by(code="TNB").one()
    statuses = {s.code: s.operational_status_id for s in db_session.query(OperationalStatus).all()}

    return ReferenceIds(
        voltage_level_id=voltage_level.voltage_level_id,
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
    permissions, via IAM's own service layer (never a local/duplicated
    user table)."""
    iam = IAMService(db_session)
    user = iam.create_user(
        username="psse_importer",
        display_name="PSS/E Importer",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    role = iam.create_role(name="PSS/E Importer (test)", description=None, actor_user_id=None)
    for permission_id in ("psse_integration.import", "psse_integration.activate"):
        iam.register_permission(
            permission_id=permission_id,
            label=permission_id,
            description=None,
            module_scope="psse_integration",
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
    """Real Substation Registry records whose mnemonics match the bus-name
    prefixes actually observed in the sample RAW files, so the substation-
    matching heuristic (`_match_substation_for_bus`) has something real to
    match against."""
    service = SubstationService(db_session)
    mnemonics = ["PKLG", "IGBK", "NKST"]
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


@dataclass
class CircuitFixture:
    circuit_id: uuid.UUID
    bay_number: str
    terminal_ids: dict[str, uuid.UUID]  # keyed by substation mnemonic


@pytest.fixture()
def pklg_igbk_circuit(
    db_session: Session,
    reference_ids: ReferenceIds,
    voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> CircuitFixture:
    """A real two-terminal `Circuit` (PKLG <-> IGBK, `ckt_id`-equivalent
    `bay_number` "1") — an `EquipmentTopologyMap` matching candidate for a
    `TopologyBranch`/`TopologyTransformer` with the same endpoints."""
    service = EquipmentRegistryService(db_session)
    circuit = service.create_circuit(
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
    db_session.commit()
    terminals = service.list_terminals(circuit.circuit_id)
    terminal_by_mnemonic = {}
    for terminal in terminals:
        for mnemonic, yard_id in voltage_yard_ids.items():
            if terminal.voltage_yard_id == yard_id:
                terminal_by_mnemonic[mnemonic] = terminal.circuit_terminal_id
    return CircuitFixture(
        circuit_id=circuit.circuit_id,
        bay_number=circuit.bay_number,
        terminal_ids=terminal_by_mnemonic,
    )
