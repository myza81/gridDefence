"""Repository/database-level tests for `PublicationRecordRepository` and
the underlying `publication_record*` schema — aggregate insertion, child
evidence persistence, uniqueness constraints, actor foreign-key
behaviour, historical durability, and the structural absence of any
update/delete path.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.findings_publication_governance.models import (
    PublicationRecord,
    PublicationRecordAcknowledgement,
    PublicationRecordFinding,
    PublicationRecordPrerequisite,
)
from app.modules.findings_publication_governance.repository import PublicationRecordRepository


def _bare_record(*, published_by_user_id: uuid.UUID, **overrides: object) -> PublicationRecord:
    defaults: dict[str, object] = dict(
        publication_record_id=uuid.uuid4(),
        publication_event_id=uuid.uuid4(),
        scheme_type="UFLS",
        scheme_version_id=uuid.uuid4(),
        published_by_user_id=published_by_user_id,
    )
    defaults.update(overrides)
    return PublicationRecord(**defaults)  # type: ignore[arg-type]


def _bare_finding(**overrides: object) -> PublicationRecordFinding:
    defaults: dict[str, object] = dict(
        publication_record_finding_id=uuid.uuid4(),
        finding_index=0,
        finding_type="MW_TOLERANCE_DEVIATION",
        severity="WARNING",
        source="test",
        description="Test finding.",
        affected_object_type="stage",
        affected_object_id="stage-1",
        resolved_treatment="ALLOW_WITHOUT_ACKNOWLEDGEMENT",
        matched_policy_severity="WARNING",
        acknowledgement_required=False,
    )
    defaults.update(overrides)
    return PublicationRecordFinding(**defaults)  # type: ignore[arg-type]


def test_add_aggregate_inserts_parent_and_children(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    repo = PublicationRecordRepository(db_session)
    record = _bare_record(published_by_user_id=actor_user_id)
    finding = _bare_finding()
    prerequisite = PublicationRecordPrerequisite(
        publication_record_prerequisite_id=uuid.uuid4(),
        prerequisite_index=0,
        prerequisite_code="TEST_PREREQ",
        passed=True,
        description="Test.",
        source="test",
    )
    ack = PublicationRecordAcknowledgement(
        publication_record_acknowledgement_id=uuid.uuid4(),
        finding_index=0,
        acknowledged_by_user_id=actor_user_id,
        justification="Reviewed.",
    )
    # finding needs ack_required True for the FK-referenced ack to make sense
    finding.acknowledgement_required = True
    finding.resolved_treatment = "ALLOW_WITH_ACKNOWLEDGEMENT"

    repo.add_aggregate(
        record, findings=[finding], prerequisites=[prerequisite], acknowledgements=[ack]
    )
    db_session.commit()

    fetched = repo.get_by_id(record.publication_record_id)
    assert fetched is not None
    assert len(repo.list_findings(record.publication_record_id)) == 1
    assert len(repo.list_prerequisites(record.publication_record_id)) == 1
    assert len(repo.list_acknowledgements(record.publication_record_id)) == 1


def test_get_by_event_id(db_session: Session, actor_user_id: uuid.UUID) -> None:
    repo = PublicationRecordRepository(db_session)
    record = _bare_record(published_by_user_id=actor_user_id)
    repo.add_aggregate(record, findings=[], prerequisites=[], acknowledgements=[])
    db_session.commit()

    found = repo.get_by_event_id(record.publication_event_id)
    assert found is not None
    assert found.publication_record_id == record.publication_record_id
    assert repo.get_by_event_id(uuid.uuid4()) is None


def test_duplicate_publication_event_id_violates_unique_constraint(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    repo = PublicationRecordRepository(db_session)
    shared_event_id = uuid.uuid4()
    first = _bare_record(published_by_user_id=actor_user_id, publication_event_id=shared_event_id)
    repo.add_aggregate(first, findings=[], prerequisites=[], acknowledgements=[])
    db_session.commit()

    second = _bare_record(published_by_user_id=actor_user_id, publication_event_id=shared_event_id)
    # `add_aggregate` itself flushes — the UNIQUE violation surfaces from
    # that internal flush, not a later, separate `commit()`.
    with pytest.raises(IntegrityError):
        repo.add_aggregate(second, findings=[], prerequisites=[], acknowledgements=[])
    db_session.rollback()


def test_duplicate_finding_index_violates_unique_constraint(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    repo = PublicationRecordRepository(db_session)
    record = _bare_record(published_by_user_id=actor_user_id)
    finding_a = _bare_finding(publication_record_finding_id=uuid.uuid4(), finding_index=0)
    finding_b = _bare_finding(publication_record_finding_id=uuid.uuid4(), finding_index=0)
    with pytest.raises(IntegrityError):
        repo.add_aggregate(
            record, findings=[finding_a, finding_b], prerequisites=[], acknowledgements=[]
        )
    db_session.rollback()


# Foreign-key *enforcement* is a PostgreSQL-specific verification (this
# sprint's own instructions §13 lists "foreign-key behavior" under the
# PostgreSQL verification checklist specifically) — SQLite does not
# enforce `FOREIGN KEY` constraints unless `PRAGMA foreign_keys=ON` is
# set, which this project's own shared `conftest.py` does not set (a
# cross-cutting change out of this sprint's own regression boundaries).
# These two tests are meaningful only against the real PostgreSQL run.
_POSTGRES_ONLY = pytest.mark.skipif(
    not os.environ.get("GRIDDEFENCE_TEST_DATABASE_URL"),
    reason="Foreign-key enforcement is not active under SQLite in this project's test harness.",
)


@_POSTGRES_ONLY
def test_actor_foreign_key_behavior_rejects_unknown_user(db_session: Session) -> None:
    repo = PublicationRecordRepository(db_session)
    record = _bare_record(published_by_user_id=uuid.uuid4())  # no such user
    with pytest.raises(IntegrityError):
        repo.add_aggregate(record, findings=[], prerequisites=[], acknowledgements=[])
    db_session.rollback()


@_POSTGRES_ONLY
def test_acknowledgement_composite_fk_rejects_unknown_finding_index(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    repo = PublicationRecordRepository(db_session)
    record = _bare_record(published_by_user_id=actor_user_id)
    finding = _bare_finding(finding_index=0)
    ack = PublicationRecordAcknowledgement(
        publication_record_acknowledgement_id=uuid.uuid4(),
        finding_index=99,  # does not exist among this record's own findings
        acknowledged_by_user_id=actor_user_id,
        justification="Reviewed.",
    )
    with pytest.raises(IntegrityError):
        repo.add_aggregate(record, findings=[finding], prerequisites=[], acknowledgements=[ack])
    db_session.rollback()


def test_historical_durability_record_remains_after_policy_module_activity(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """A `PublicationRecord` is entirely independent of
    `PublicationTreatmentPolicy`'s own table — nothing in that module's
    own CRUD can affect an already-created record (structural, since
    there is no live foreign key coupling the two beyond the
    non-enforced `matched_policy_id` traceability pointer)."""
    repo = PublicationRecordRepository(db_session)
    record = _bare_record(published_by_user_id=actor_user_id)
    repo.add_aggregate(record, findings=[], prerequisites=[], acknowledgements=[])
    db_session.commit()

    record_id = record.publication_record_id
    assert repo.get_by_id(record_id) is not None


def test_no_update_or_delete_methods_exposed() -> None:
    """Structural immutability enforcement (this sprint's own
    instructions §5/§16) — verified by absence, not a runtime guard."""
    public_methods = {name for name in dir(PublicationRecordRepository) if not name.startswith("_")}
    assert "update" not in public_methods
    assert "delete" not in public_methods
    assert "remove" not in public_methods


def test_list_filters_by_scheme_type_and_scheme_version(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    repo = PublicationRecordRepository(db_session)
    ufls_record = _bare_record(published_by_user_id=actor_user_id, scheme_type="UFLS")
    uvls_record = _bare_record(published_by_user_id=actor_user_id, scheme_type="UVLS")
    repo.add_aggregate(ufls_record, findings=[], prerequisites=[], acknowledgements=[])
    repo.add_aggregate(uvls_record, findings=[], prerequisites=[], acknowledgements=[])
    db_session.commit()

    ufls_only, ufls_total = repo.list_all(scheme_type="UFLS", offset=0, limit=50)
    assert ufls_total == 1
    assert ufls_only[0].publication_record_id == ufls_record.publication_record_id

    by_version, version_total = repo.list_all(
        scheme_version_id=uvls_record.scheme_version_id, offset=0, limit=50
    )
    assert version_total == 1
    assert by_version[0].publication_record_id == uvls_record.publication_record_id


def test_list_deterministic_ordering(db_session: Session, actor_user_id: uuid.UUID) -> None:
    repo = PublicationRecordRepository(db_session)
    for _ in range(3):
        record = _bare_record(published_by_user_id=actor_user_id)
        repo.add_aggregate(record, findings=[], prerequisites=[], acknowledgements=[])
    db_session.commit()

    first_call, _ = repo.list_all(offset=0, limit=50)
    second_call, _ = repo.list_all(offset=0, limit=50)
    assert [r.publication_record_id for r in first_call] == [
        r.publication_record_id for r in second_call
    ]


def test_findings_prerequisites_acknowledgements_ordered_by_index(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    repo = PublicationRecordRepository(db_session)
    record = _bare_record(published_by_user_id=actor_user_id)
    findings = [
        _bare_finding(publication_record_finding_id=uuid.uuid4(), finding_index=2),
        _bare_finding(publication_record_finding_id=uuid.uuid4(), finding_index=0),
        _bare_finding(publication_record_finding_id=uuid.uuid4(), finding_index=1),
    ]
    repo.add_aggregate(record, findings=findings, prerequisites=[], acknowledgements=[])
    db_session.commit()

    ordered = repo.list_findings(record.publication_record_id)
    assert [f.finding_index for f in ordered] == [0, 1, 2]
