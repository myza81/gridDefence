"""Fixtures shared by every Substation Registry test.

Seeds Core Platform reference data (Phase 1's idempotent seed script) and
provisions a locally-authenticated IAM user holding `substation_registry
.write`, so business-rule tests can exercise `SubstationService` exactly as
a real actor would, without duplicating IAM setup in every test module.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session

from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
from app.modules.substation_registry.bootstrap import run_bootstrap as bootstrap_permissions
from app.reference_data.models import GridOwner, OperationalStatus, Region, State, VoltageLevel
from app.reference_data.seed import run_seed


@dataclass
class ReferenceIds:
    voltage_level_id: int
    region_id: int
    state_id: int
    grid_owner_id: int
    status_id_by_code: dict[str, int]


@pytest.fixture()
def reference_ids(db_session: Session) -> ReferenceIds:
    run_seed(db_session)
    db_session.commit()

    voltage_level = db_session.query(VoltageLevel).filter_by(label="500kV").one()
    region = db_session.query(Region).filter_by(code="NORTH").one()
    state = db_session.query(State).filter_by(code="SEL").one()
    grid_owner = db_session.query(GridOwner).filter_by(code="TNB").one()
    statuses = {s.code: s.operational_status_id for s in db_session.query(OperationalStatus).all()}

    return ReferenceIds(
        voltage_level_id=voltage_level.voltage_level_id,
        region_id=region.region_id,
        state_id=state.state_id,
        grid_owner_id=grid_owner.grid_owner_id,
        status_id_by_code=statuses,
    )


@pytest.fixture()
def actor_user_id(db_session: Session) -> uuid.UUID:
    """A locally-authenticated IAM user holding `substation_registry.write`,
    via IAM's own service layer (never a local/duplicated user table —
    CLAUDE.md A1, ADR-002)."""
    iam = IAMService(db_session)
    user = iam.create_user(
        username="registry_editor",
        display_name="Registry Editor",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    role = iam.create_role(
        name="Substation Registry Editor (test)", description=None, actor_user_id=None
    )
    iam.register_permission(
        permission_id="substation_registry.write",
        label="Manage substations",
        description=None,
        module_scope="substation_registry",
    )
    iam.grant_permission_to_role(
        role_id=role.role_id, permission_id="substation_registry.write", actor_user_id=None
    )
    iam.assign_role_to_user(user_id=user.user_id, role_id=role.role_id, actor_user_id=None)
    db_session.commit()
    return user.user_id


@pytest.fixture()
def bootstrapped_registry_permissions(db_session: Session) -> None:
    """Runs Substation Registry's own permission-registration bootstrap
    against an IAM database that has already run IAM's own bootstrap."""
    bootstrap_iam(db_session)
    bootstrap_permissions(db_session)
