"""Fixtures shared by every Shared Defence Scheme Platform test."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.iam.service import IAMService


@pytest.fixture()
def actor_user_id(db_session: Session) -> uuid.UUID:
    """A plain, locally-authenticated IAM user — the service layer itself
    does not check permissions (CLAUDE.md §14), so no specific grant is
    needed for these service-level tests."""
    iam = IAMService(db_session)
    user = iam.create_user(
        username="scheme_platform_tester",
        display_name="Scheme Platform Tester",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    return user.user_id
