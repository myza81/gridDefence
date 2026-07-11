"""Fixtures shared by every Sensitive Customer Registry test. Builds real
Substation Registry / Equipment Registry records through their own service
layers (never constructed directly — CLAUDE.md A1): one substation, an HV
and LV voltage yard, and two real `Transformer`s (each with an HV/LV
terminal pair) — enough Transformer Terminals to exercise reassignment and
the "multiple facilities may share one terminal" rule (the deliberate
inverse of ALSF's own per-terminal uniqueness rule).
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
from app.modules.sensitive_customer_registry.bootstrap import (
    run_bootstrap as bootstrap_sensitive_customer_registry,
)
from app.modules.sensitive_customer_registry.seed import (
    run_seed as seed_sensitive_customer_registry,
)
from app.modules.substation_registry.service import SubstationService
from app.reference_data.models import (
    GmZone,
    GridOwner,
    OperationalStatus,
    Region,
    State,
    VoltageLevel,
)
from app.reference_data.seed import run_seed as seed_reference_data


@dataclass
class ReferenceIds:
    voltage_level_id: int
    lv_voltage_level_id: int
    status_id_by_code: dict[str, int]
    region_id: int
    gm_zone_id: int
    state_id: int
    grid_owner_id: int


@pytest.fixture()
def reference_ids(db_session: Session) -> ReferenceIds:
    seed_reference_data(db_session)
    db_session.commit()

    voltage_level = db_session.query(VoltageLevel).filter_by(label="500kV").one()
    lv_voltage_level = db_session.query(VoltageLevel).filter_by(label="132kV").one()
    region = db_session.query(Region).filter_by(code="NORTH").one()
    gm_zone = db_session.query(GmZone).filter_by(code="ALOR_SETAR").one()
    state = db_session.query(State).filter_by(code="SEL").one()
    grid_owner = db_session.query(GridOwner).filter_by(code="TNB").one()
    statuses = {s.code: s.operational_status_id for s in db_session.query(OperationalStatus).all()}

    return ReferenceIds(
        voltage_level_id=voltage_level.voltage_level_id,
        lv_voltage_level_id=lv_voltage_level.voltage_level_id,
        status_id_by_code=statuses,
        region_id=region.region_id,
        gm_zone_id=gm_zone.gm_zone_id,
        state_id=state.state_id,
        grid_owner_id=grid_owner.grid_owner_id,
    )


@pytest.fixture()
def actor_user_id(db_session: Session) -> uuid.UUID:
    """A locally-authenticated IAM user holding this module's own
    `sensitive_customer_registry.write`/`.manage_reference_data`
    permissions (Administrator-tier, per the corrected permission model —
    task Correction 1), plus Equipment Registry's write permission (used
    only by fixture setup, to create real transformers directly through
    their own service layer)."""
    iam = IAMService(db_session)
    user = iam.create_user(
        username="scr_admin",
        display_name="SCR Administrator",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    role = iam.create_role(
        name="Sensitive Customer Registry Administrator (test)",
        description=None,
        actor_user_id=None,
    )
    for permission_id, label, module_scope in (
        (
            "sensitive_customer_registry.write",
            "Manage sensitive customer registry records",
            "sensitive_customer_registry",
        ),
        (
            "sensitive_customer_registry.manage_reference_data",
            "Manage sensitive customer registry reference data",
            "sensitive_customer_registry",
        ),
        (
            "sensitive_customer_registry.read",
            "Read sensitive customer registry records",
            "sensitive_customer_registry",
        ),
        ("equipment_registry.write", "Manage transformers", "equipment_registry"),
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
def reader_user_id(db_session: Session) -> uuid.UUID:
    """An Engineer-tier user holding only `sensitive_customer_registry.read`
    — used to prove Engineer never receives mutation permissions (task
    Correction 1)."""
    iam = IAMService(db_session)
    user = iam.create_user(
        username="scr_engineer",
        display_name="SCR Engineer",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    role = iam.create_role(
        name="Sensitive Customer Registry Reader (test)", description=None, actor_user_id=None
    )
    iam.register_permission(
        permission_id="sensitive_customer_registry.read",
        label="Read sensitive customer registry records",
        description=None,
        module_scope="sensitive_customer_registry",
    )
    iam.grant_permission_to_role(
        role_id=role.role_id,
        permission_id="sensitive_customer_registry.read",
        actor_user_id=None,
    )
    iam.assign_role_to_user(user_id=user.user_id, role_id=role.role_id, actor_user_id=None)
    db_session.commit()
    return user.user_id


@pytest.fixture()
def substation_id(
    db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
) -> uuid.UUID:
    service = SubstationService(db_session)
    substation = service.create_substation(
        mnemonic="PKLG",
        official_name="Pekan Lama Substation",
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
    db_session.commit()
    return substation.substation_id


@pytest.fixture()
def voltage_yard_ids(
    db_session: Session,
    reference_ids: ReferenceIds,
    substation_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> dict[str, uuid.UUID]:
    service = EquipmentRegistryService(db_session)
    hv_yard = service.create_voltage_yard(
        substation_id=substation_id,
        voltage_level_id=reference_ids.voltage_level_id,
        actor_user_id=actor_user_id,
    )
    lv_yard = service.create_voltage_yard(
        substation_id=substation_id,
        voltage_level_id=reference_ids.lv_voltage_level_id,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    return {"HV": hv_yard.voltage_yard_id, "LV": lv_yard.voltage_yard_id}


@dataclass
class TransformerTerminals:
    transformer_id: uuid.UUID
    hv_terminal_id: uuid.UUID
    lv_terminal_id: uuid.UUID


def _create_transformer(
    db_session: Session,
    *,
    reference_ids: ReferenceIds,
    substation_id: uuid.UUID,
    voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
    transformer_number: str,
) -> TransformerTerminals:
    service = EquipmentRegistryService(db_session)
    transformer = service.create_transformer(
        substation_id=substation_id,
        transformer_number=transformer_number,
        hv_switchyard_id=voltage_yard_ids["HV"],
        hv_breaker_number=f"T{transformer_number}1",
        lv_switchyard_id=voltage_yard_ids["LV"],
        lv_breaker_number=f"T{transformer_number}2",
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
def transformer_terminals(
    db_session: Session,
    reference_ids: ReferenceIds,
    substation_id: uuid.UUID,
    voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> TransformerTerminals:
    return _create_transformer(
        db_session,
        reference_ids=reference_ids,
        substation_id=substation_id,
        voltage_yard_ids=voltage_yard_ids,
        actor_user_id=actor_user_id,
        transformer_number="1",
    )


@pytest.fixture()
def second_transformer_terminals(
    db_session: Session,
    reference_ids: ReferenceIds,
    substation_id: uuid.UUID,
    voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> TransformerTerminals:
    """A second transformer at the same substation — used for reassignment
    tests and to prove Equipment Registry existence validation is real."""
    return _create_transformer(
        db_session,
        reference_ids=reference_ids,
        substation_id=substation_id,
        voltage_yard_ids=voltage_yard_ids,
        actor_user_id=actor_user_id,
        transformer_number="2",
    )


@dataclass
class ScrReferenceIds:
    healthcare_sector_id: int
    transport_sector_id: int
    high_classification_id: int
    medium_classification_id: int


@pytest.fixture()
def scr_reference_ids(db_session: Session) -> ScrReferenceIds:
    counts = seed_sensitive_customer_registry(db_session)
    assert counts["facility_sector"] == 8
    assert counts["sensitivity_classification"] == 3
    db_session.commit()

    from app.modules.sensitive_customer_registry.models import (
        FacilitySector,
        SensitivityClassification,
    )

    healthcare = db_session.query(FacilitySector).filter_by(code="HEALTHCARE").one()
    transport = db_session.query(FacilitySector).filter_by(code="TRANSPORT").one()
    high = db_session.query(SensitivityClassification).filter_by(code="HIGH").one()
    medium = db_session.query(SensitivityClassification).filter_by(code="MEDIUM").one()

    return ScrReferenceIds(
        healthcare_sector_id=healthcare.id,
        transport_sector_id=transport.id,
        high_classification_id=high.id,
        medium_classification_id=medium.id,
    )


@pytest.fixture()
def bootstrapped_permissions(db_session: Session) -> None:
    bootstrap_iam(db_session)
    bootstrap_equipment_registry(db_session)
    bootstrap_sensitive_customer_registry(db_session)
