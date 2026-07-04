"""Fixtures shared by every Equipment Registry test.

Seeds Core Platform reference data, provisions a locally-authenticated IAM
user holding `equipment_registry.write`, creates a handful of real
Substation Registry records (via `SubstationService`, never constructed
directly — CLAUDE.md A1), and a default `SubstationVoltageYard` per
substation (via `EquipmentRegistryService.create_voltage_yard`) for circuit
terminals to reference (equipment-registry-module.md §7.5a; ADR-008).

Test databases are created via `Base.metadata.create_all()`
(backend/conftest.py), not via `alembic upgrade head` — the migration's own
data-backfill logic (0005_substation_voltage_yard.py) is therefore verified
separately, directly against a real, persistent PostgreSQL database with
real pre-existing data (see this phase's implementation report), not by
this test suite.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session

from app.modules.equipment_registry.bootstrap import run_bootstrap as bootstrap_equipment_registry
from app.modules.equipment_registry.service import EquipmentRegistryService
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
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
    line_type_id: int
    status_id_by_code: dict[str, int]
    # Substation-creation prerequisites, reused from Substation Registry's
    # own reference data (never duplicated — CLAUDE.md §5.1).
    region_id: int
    state_id: int
    grid_owner_id: int


@pytest.fixture()
def reference_ids(db_session: Session) -> ReferenceIds:
    run_seed(db_session)
    db_session.commit()

    voltage_level = db_session.query(VoltageLevel).filter_by(label="500kV").one()
    line_type = db_session.query(LineType).filter_by(code="OVERHEAD").one()
    region = db_session.query(Region).filter_by(code="NORTH").one()
    state = db_session.query(State).filter_by(code="SEL").one()
    grid_owner = db_session.query(GridOwner).filter_by(code="TNB").one()
    statuses = {s.code: s.operational_status_id for s in db_session.query(OperationalStatus).all()}

    return ReferenceIds(
        voltage_level_id=voltage_level.voltage_level_id,
        line_type_id=line_type.line_type_id,
        status_id_by_code=statuses,
        region_id=region.region_id,
        state_id=state.state_id,
        grid_owner_id=grid_owner.grid_owner_id,
    )


@pytest.fixture()
def second_voltage_level_id(db_session: Session, reference_ids: ReferenceIds) -> int:
    """A voltage level distinct from `reference_ids.voltage_level_id`
    (500kV) — used to exercise a genuinely multi-voltage substation
    (equipment-registry-module.md §7.5a's own PKLG 275kV/132kV example)."""
    voltage_level = db_session.query(VoltageLevel).filter_by(label="132kV").one()
    return voltage_level.voltage_level_id


@pytest.fixture()
def actor_user_id(db_session: Session) -> uuid.UUID:
    """A locally-authenticated IAM user holding `equipment_registry.write`,
    via IAM's own service layer (never a local/duplicated user table)."""
    iam = IAMService(db_session)
    user = iam.create_user(
        username="circuit_editor",
        display_name="Circuit Editor",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    role = iam.create_role(
        name="Equipment Registry Editor (test)", description=None, actor_user_id=None
    )
    iam.register_permission(
        permission_id="equipment_registry.write",
        label="Manage circuits",
        description=None,
        module_scope="equipment_registry",
    )
    iam.grant_permission_to_role(
        role_id=role.role_id, permission_id="equipment_registry.write", actor_user_id=None
    )
    iam.assign_role_to_user(user_id=user.user_id, role_id=role.role_id, actor_user_id=None)
    db_session.commit()
    return user.user_id


@pytest.fixture()
def substation_ids(
    db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    """Four real Substation Registry records — enough for a two-terminal
    circuit test and a three-terminal tee-off test in the same module."""
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
    """One default `SubstationVoltageYard` per fixture substation, at
    `reference_ids.voltage_level_id` (500kV) — mirrors what
    0005_substation_voltage_yard.py's data backfill does for real,
    pre-existing substations."""
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
def bootstrapped_equipment_registry_permissions(db_session: Session) -> None:
    """Runs Equipment Registry's own permission-registration bootstrap
    against an IAM database that has already run IAM's own bootstrap."""
    bootstrap_iam(db_session)
    bootstrap_equipment_registry(db_session)
