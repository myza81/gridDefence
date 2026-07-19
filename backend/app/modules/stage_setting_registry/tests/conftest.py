"""Fixtures shared by every Stage Setting Registry test."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.iam.service import IAMService
from app.reference_data.models import Region
from app.reference_data.seed import run_seed


@pytest.fixture()
def actor_user_id(db_session: Session) -> uuid.UUID:
    """A plain, locally-authenticated IAM user — the service layer itself
    does not check permissions (that is the router/dependency layer's own
    job, per CLAUDE.md §14), so no specific grant is needed for
    service-level tests."""
    iam = IAMService(db_session)
    user = iam.create_user(
        username="stage_setting_editor",
        display_name="Stage Setting Editor",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    return user.user_id


@pytest.fixture()
def region_ids(db_session: Session) -> dict[str, int]:
    run_seed(db_session)
    db_session.commit()
    regions = db_session.query(Region).order_by(Region.code).all()
    return {r.code: r.region_id for r in regions}
