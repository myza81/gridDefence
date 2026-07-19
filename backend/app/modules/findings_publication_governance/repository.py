"""Findings and Publication Governance repository layer (CLAUDE.md §14) —
pure persistence access. No business rules, no permission checks, no
precedence resolution logic, no audit writing live here — that is
`service.py`'s responsibility. `PublicationRecordRepository` additionally
has no *update or delete* methods for `PublicationRecord` or any of its
child evidence rows — immutability is enforced structurally, by this
class simply never exposing the operation (this sprint's own instructions
§5, §16), not by a runtime check.

This repository touches exactly this module's own tables
(`publication_treatment_policy`, `publication_treatment_policy_audit_log`,
`publication_record`, `publication_record_finding`,
`publication_record_prerequisite`, `publication_record_acknowledgement`)
— no cross-module repository imports, per CLAUDE.md A1.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.findings_publication_governance.models import (
    PublicationRecord,
    PublicationRecordAcknowledgement,
    PublicationRecordFinding,
    PublicationRecordPrerequisite,
    PublicationTreatmentPolicy,
    PublicationTreatmentPolicyAuditLog,
)


class PublicationTreatmentPolicyRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- PublicationTreatmentPolicy ------------------------------------------------
    def add(self, policy: PublicationTreatmentPolicy) -> PublicationTreatmentPolicy:
        self.db.add(policy)
        self.db.flush()
        return policy

    def get_by_id(self, policy_id: uuid.UUID) -> PublicationTreatmentPolicy | None:
        return self.db.get(PublicationTreatmentPolicy, policy_id)

    def find_policy(
        self, *, severity: str, finding_type: str | None, scheme_type: str | None
    ) -> PublicationTreatmentPolicy | None:
        """Exact-key lookup for one precedence level — at most one row can
        ever match, guaranteed by this table's own four partial unique
        indexes (models.py), so resolution never depends on row order."""
        stmt = select(PublicationTreatmentPolicy).where(
            PublicationTreatmentPolicy.severity == severity,
            PublicationTreatmentPolicy.finding_type == finding_type,
            PublicationTreatmentPolicy.scheme_type == scheme_type,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(
        self,
        *,
        severity: str | None = None,
        finding_type: str | None = None,
        scheme_type: str | None = None,
        treatment: str | None = None,
    ) -> list[PublicationTreatmentPolicy]:
        stmt = select(PublicationTreatmentPolicy)
        if severity is not None:
            stmt = stmt.where(PublicationTreatmentPolicy.severity == severity)
        if finding_type is not None:
            stmt = stmt.where(PublicationTreatmentPolicy.finding_type == finding_type)
        if scheme_type is not None:
            stmt = stmt.where(PublicationTreatmentPolicy.scheme_type == scheme_type)
        if treatment is not None:
            stmt = stmt.where(PublicationTreatmentPolicy.treatment == treatment)
        stmt = stmt.order_by(
            PublicationTreatmentPolicy.severity,
            PublicationTreatmentPolicy.finding_type,
            PublicationTreatmentPolicy.scheme_type,
        )
        return list(self.db.execute(stmt).scalars().all())

    def delete(self, policy: PublicationTreatmentPolicy) -> None:
        self.db.delete(policy)
        self.db.flush()

    # --- PublicationTreatmentPolicyAuditLog ----------------------------------------
    def add_audit_log(
        self, entry: PublicationTreatmentPolicyAuditLog
    ) -> PublicationTreatmentPolicyAuditLog:
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_audit_log(
        self, policy_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[PublicationTreatmentPolicyAuditLog], int]:
        """Queries by `policy_id` directly — deliberately not gated on the
        policy still existing (models.py's own docstring: `policy_id` is
        not a foreign key precisely so a removed override's audit history
        remains queryable)."""
        total = self.db.execute(
            select(func.count())
            .select_from(PublicationTreatmentPolicyAuditLog)
            .where(PublicationTreatmentPolicyAuditLog.policy_id == policy_id)
        ).scalar_one()

        stmt = (
            select(PublicationTreatmentPolicyAuditLog)
            .where(PublicationTreatmentPolicyAuditLog.policy_id == policy_id)
            .order_by(
                PublicationTreatmentPolicyAuditLog.changed_at.desc(),
                PublicationTreatmentPolicyAuditLog.log_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total


class PublicationRecordRepository:
    """No update/delete methods anywhere in this class — see module
    docstring. `add_aggregate` is the only write path, inserting the
    parent row and all of its child evidence rows in one call (still no
    commit — `service.py`'s own transaction-boundary discipline)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    # --- PublicationRecord (immutable — insert and read only) --------------------
    def add_aggregate(
        self,
        record: PublicationRecord,
        *,
        findings: list[PublicationRecordFinding],
        prerequisites: list[PublicationRecordPrerequisite],
        acknowledgements: list[PublicationRecordAcknowledgement],
    ) -> PublicationRecord:
        self.db.add(record)
        self.db.flush()  # assigns record.publication_record_id before children reference it

        for finding in findings:
            finding.publication_record_id = record.publication_record_id
            self.db.add(finding)
        for prerequisite in prerequisites:
            prerequisite.publication_record_id = record.publication_record_id
            self.db.add(prerequisite)
        # Findings must actually exist in the database before any
        # acknowledgement referencing them via the composite
        # (publication_record_id, finding_index) foreign key can be
        # inserted (models.py's own genuine same-aggregate FK) — flushed
        # here, deterministically, rather than relying on SQLAlchemy's own
        # cross-table dependency sort for a constraint declared only via
        # `ForeignKeyConstraint` metadata (not an ORM `relationship()`,
        # per this codebase's own established no-`relationship()`
        # convention). PostgreSQL enforces this ordering; SQLite's own
        # default lack of FK enforcement made this invisible there —
        # found via this sprint's own PostgreSQL verification pass.
        self.db.flush()

        for acknowledgement in acknowledgements:
            acknowledgement.publication_record_id = record.publication_record_id
            self.db.add(acknowledgement)
        self.db.flush()
        return record

    def get_by_id(self, publication_record_id: uuid.UUID) -> PublicationRecord | None:
        return self.db.get(PublicationRecord, publication_record_id)

    def get_by_event_id(self, publication_event_id: uuid.UUID) -> PublicationRecord | None:
        """Duplicate-publication-event detection (this sprint's own
        chosen concurrency-identity approach — service.py's own module
        docstring)."""
        stmt = select(PublicationRecord).where(
            PublicationRecord.publication_event_id == publication_event_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(
        self,
        *,
        scheme_type: str | None = None,
        scheme_version_id: uuid.UUID | None = None,
        offset: int,
        limit: int,
    ) -> tuple[list[PublicationRecord], int]:
        stmt = select(PublicationRecord)
        if scheme_type is not None:
            stmt = stmt.where(PublicationRecord.scheme_type == scheme_type)
        if scheme_version_id is not None:
            stmt = stmt.where(PublicationRecord.scheme_version_id == scheme_version_id)

        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

        stmt = (
            stmt.order_by(
                PublicationRecord.published_at.desc(), PublicationRecord.publication_record_id
            )
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    # --- Frozen child evidence (read only) ---------------------------------------
    def list_findings(self, publication_record_id: uuid.UUID) -> list[PublicationRecordFinding]:
        stmt = (
            select(PublicationRecordFinding)
            .where(PublicationRecordFinding.publication_record_id == publication_record_id)
            .order_by(PublicationRecordFinding.finding_index)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_prerequisites(
        self, publication_record_id: uuid.UUID
    ) -> list[PublicationRecordPrerequisite]:
        stmt = (
            select(PublicationRecordPrerequisite)
            .where(PublicationRecordPrerequisite.publication_record_id == publication_record_id)
            .order_by(PublicationRecordPrerequisite.prerequisite_index)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_acknowledgements(
        self, publication_record_id: uuid.UUID
    ) -> list[PublicationRecordAcknowledgement]:
        stmt = (
            select(PublicationRecordAcknowledgement)
            .where(PublicationRecordAcknowledgement.publication_record_id == publication_record_id)
            .order_by(PublicationRecordAcknowledgement.finding_index)
        )
        return list(self.db.execute(stmt).scalars().all())
