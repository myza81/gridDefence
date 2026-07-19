"""Fixtures shared by every Findings and Publication Governance test."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.iam.service import IAMService


@pytest.fixture()
def actor_user_id(db_session: Session) -> uuid.UUID:
    """A plain, locally-authenticated IAM user — the service layer itself
    does not check permissions (that is the router/dependency layer's own
    job, per CLAUDE.md §14), so no specific grant is needed for
    service-level tests."""
    iam = IAMService(db_session)
    user = iam.create_user(
        username="publication_governance_editor",
        display_name="Publication Governance Editor",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    return user.user_id
