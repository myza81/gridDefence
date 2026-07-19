"""Fixtures shared by every Engineering Parameter Configuration test."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.iam.service import IAMService


@pytest.fixture()
def actor_user_id(db_session: Session) -> uuid.UUID:
    """A locally-authenticated IAM user holding this module's own
    `engineering_parameters.manage` permission."""
    iam = IAMService(db_session)
    user = iam.create_user(
        username="engineering_parameters_editor",
        display_name="Engineering Parameters Editor",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    role = iam.create_role(
        name="Engineering Parameters Editor (test)",
        description=None,
        actor_user_id=None,
    )
    iam.register_permission(
        permission_id="engineering_parameters.manage",
        label="Manage engineering parameter values",
        description=None,
        module_scope="engineering_parameters",
    )
    iam.grant_permission_to_role(
        role_id=role.role_id, permission_id="engineering_parameters.manage", actor_user_id=None
    )
    iam.assign_role_to_user(user_id=user.user_id, role_id=role.role_id, actor_user_id=None)
    db_session.commit()
    return user.user_id
