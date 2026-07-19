"""Tests for the shared repository query helpers, exercised against the
synthetic concrete model."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.scheme_platform.lifecycle import SchemeVersionLifecycleStatus
from app.modules.scheme_platform.repository import (
    get_current_published,
    get_next_version_number,
    list_versions,
)
from app.modules.scheme_platform.tests.synthetic_scheme_version import SyntheticSchemeVersion


def _make(scheme_id: uuid.UUID, version_number: int, status: SchemeVersionLifecycleStatus):
    return SyntheticSchemeVersion(
        scheme_id=scheme_id, version_number=version_number, lifecycle_status=status.value
    )


class TestGetNextVersionNumber:
    def test_returns_one_when_no_version_exists(self, db_session: Session) -> None:
        scheme_id = uuid.uuid4()
        assert get_next_version_number(db_session, SyntheticSchemeVersion, scheme_id) == 1

    def test_returns_max_plus_one(self, db_session: Session) -> None:
        scheme_id = uuid.uuid4()
        db_session.add(_make(scheme_id, 1, SchemeVersionLifecycleStatus.SUPERSEDED))
        db_session.add(_make(scheme_id, 2, SchemeVersionLifecycleStatus.PUBLISHED))
        db_session.flush()
        assert get_next_version_number(db_session, SyntheticSchemeVersion, scheme_id) == 3

    def test_is_scoped_per_scheme(self, db_session: Session) -> None:
        scheme_a, scheme_b = uuid.uuid4(), uuid.uuid4()
        db_session.add(_make(scheme_a, 1, SchemeVersionLifecycleStatus.PUBLISHED))
        db_session.add(_make(scheme_a, 2, SchemeVersionLifecycleStatus.PUBLISHED))
        db_session.flush()
        assert get_next_version_number(db_session, SyntheticSchemeVersion, scheme_b) == 1


class TestGetCurrentPublished:
    def test_returns_none_when_no_published_version_exists(self, db_session: Session) -> None:
        scheme_id = uuid.uuid4()
        db_session.add(_make(scheme_id, 1, SchemeVersionLifecycleStatus.DRAFT))
        db_session.flush()
        assert get_current_published(db_session, SyntheticSchemeVersion, scheme_id) is None

    def test_returns_the_one_published_version(self, db_session: Session) -> None:
        scheme_id = uuid.uuid4()
        db_session.add(_make(scheme_id, 1, SchemeVersionLifecycleStatus.SUPERSEDED))
        published = _make(scheme_id, 2, SchemeVersionLifecycleStatus.PUBLISHED)
        db_session.add(published)
        db_session.flush()
        result = get_current_published(db_session, SyntheticSchemeVersion, scheme_id)
        assert result is not None
        assert result.version_id == published.version_id

    def test_ignores_other_schemes_own_published_version(self, db_session: Session) -> None:
        scheme_a, scheme_b = uuid.uuid4(), uuid.uuid4()
        db_session.add(_make(scheme_a, 1, SchemeVersionLifecycleStatus.PUBLISHED))
        db_session.flush()
        assert get_current_published(db_session, SyntheticSchemeVersion, scheme_b) is None


class TestListVersions:
    def test_returns_versions_newest_first(self, db_session: Session) -> None:
        scheme_id = uuid.uuid4()
        db_session.add(_make(scheme_id, 1, SchemeVersionLifecycleStatus.SUPERSEDED))
        db_session.add(_make(scheme_id, 3, SchemeVersionLifecycleStatus.PUBLISHED))
        db_session.add(_make(scheme_id, 2, SchemeVersionLifecycleStatus.SUPERSEDED))
        db_session.flush()
        versions = list_versions(db_session, SyntheticSchemeVersion, scheme_id)
        assert [v.version_number for v in versions] == [3, 2, 1]

    def test_empty_list_when_no_versions_exist(self, db_session: Session) -> None:
        assert list_versions(db_session, SyntheticSchemeVersion, uuid.uuid4()) == []
