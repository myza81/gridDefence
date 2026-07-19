"""Tests for `SchemeVersionMixin`'s own database-level constraints,
exercised against the synthetic concrete model."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.scheme_platform.lifecycle import SchemeVersionLifecycleStatus
from app.modules.scheme_platform.tests.synthetic_scheme_version import SyntheticSchemeVersion


class TestLifecycleStatusCheckConstraint:
    def test_a_valid_status_is_accepted(self, db_session: Session) -> None:
        version = SyntheticSchemeVersion(
            scheme_id=uuid.uuid4(),
            version_number=1,
            lifecycle_status=SchemeVersionLifecycleStatus.DRAFT.value,
        )
        db_session.add(version)
        db_session.flush()  # must not raise

    def test_an_invalid_status_is_rejected_by_the_database(self, db_session: Session) -> None:
        version = SyntheticSchemeVersion(
            scheme_id=uuid.uuid4(), version_number=1, lifecycle_status="UNDER_REVIEW"
        )
        db_session.add(version)
        with pytest.raises(IntegrityError):
            db_session.flush()


class TestDefaultStatusIsDraft:
    def test_omitting_lifecycle_status_defaults_to_draft(self, db_session: Session) -> None:
        version = SyntheticSchemeVersion(scheme_id=uuid.uuid4(), version_number=1)
        db_session.add(version)
        db_session.flush()
        assert version.lifecycle_status == SchemeVersionLifecycleStatus.DRAFT.value
