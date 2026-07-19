"""Findings and Publication Governance persistence models (CLAUDE.md A6 —
Persistence Model layer). Shape per
docs/architecture/findings-and-publication-governance-architecture.md §2,
§4, §4.2, §12 (ADR-018).

Sprint 3 persisted `PublicationTreatmentPolicy` and its own audit log —
the governed-findings *policy* layer. Sprint 4 adds `PublicationRecord`
and its three frozen-evidence child tables (`PublicationRecordFinding`,
`PublicationRecordPrerequisite`, `PublicationRecordAcknowledgement`) — the
permanent, immutable evidence of one completed Publish action (module
document §2, §2.1, §8). `Finding` itself (findings.py) remains a
transient value contract, never a table (module document §8) — every
`PublicationRecordFinding` row is a *frozen copy* of a `Finding`'s field
values at the moment of Publish, not a reference to it. Continuous
Evaluation, detector execution, and every real UFLS/UVLS/EMLS Scheme
Version table remain explicitly out of scope (future sprints).

`PublicationRecord.scheme_version_id`/`topology_version_id`/
`load_snapshot_id` are deliberately **not** foreign keys — CLAUDE.md
A2/F2's dependency direction means Shared Platform never depends on a
scheme module's own tables (which do not exist yet regardless), and this
module's own cross-module identity model already treats such references
as opaque, unenforced UUIDs (mirrors `Finding.scheme_version_id`'s own
precedent in findings.py, and `psse_integration`'s own `topology_version_
id`/`load_snapshot_id` naming exactly).

`created_by_user_id`/`updated_by_user_id`/`changed_by_user_id` are real,
nullable foreign keys to IAM's `user.user_id` (ADR-002), referenced by
table-name string — no cross-module Python import needed (CLAUDE.md A1).
Nullable only for the bootstrap-seed exception (this module's own
`bootstrap.py`, which seeds the four architecture-approved severity
baselines — module document §4.2 — with `actor_user_id=None`), mirroring
`engineering_parameters/models.py`'s own documented precedent exactly.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base
from app.modules.findings_publication_governance.findings import FindingType, SchemeType, Severity

# JSONB on PostgreSQL (indexable, binary-stored), plain JSON elsewhere —
# mirrors `psse_integration/models.py`'s own established portable-JSON
# precedent exactly.
_JsonVariant = JSON().with_variant(JSONB(), "postgresql")


class PublicationTreatment(enum.StrEnum):
    """Module document §4 — the exact three treatment concepts the
    architecture names, no more. `Ignore`/`Suppress`/`Waive`/`Auto-approve`
    are deliberately never introduced (this sprint's own instructions §6)."""

    BLOCK = "BLOCK"
    ALLOW_WITH_ACKNOWLEDGEMENT = "ALLOW_WITH_ACKNOWLEDGEMENT"
    ALLOW_WITHOUT_ACKNOWLEDGEMENT = "ALLOW_WITHOUT_ACKNOWLEDGEMENT"


def _sql_in_list(values: list[str] | tuple[str, ...]) -> str:
    """Renders an explicit `('A','B','C')` SQL literal list — not relying
    on Python's own tuple `repr()` — so every `CHECK` constraint below
    stays as plainly auditable as the hand-written literal lists already
    used elsewhere in this codebase (e.g.
    `stage_setting_registry/models.py`'s own `scheme_type IN
    ('UFLS','UVLS')`), while still deriving from the single canonical enum
    so the constraint can never drift from `findings.py`'s own values."""
    return "(" + ",".join(f"'{value}'" for value in values) + ")"


_SEVERITY_VALUES = _sql_in_list([s.value for s in Severity])
_FINDING_TYPE_VALUES = _sql_in_list([f.value for f in FindingType])
_SCHEME_TYPE_VALUES = _sql_in_list([s.value for s in SchemeType])
_TREATMENT_VALUES = _sql_in_list([t.value for t in PublicationTreatment])


class PublicationTreatmentPolicy(Base):
    """The administratively-configured mapping from a finding's severity
    (mandatory) — and, optionally, its finding type and/or scheme type —
    to publication treatment (module document §2, §4).

    **Precedence key shape** (module document §4, §4.2; resolved by
    `service.py`'s own `resolve_publication_treatment`): every row is keyed
    by `severity` (always) plus two independently-optional narrowing
    columns, `finding_type` and `scheme_type`. `NULL` in either column
    means "applies regardless of that dimension" — a row with both `NULL`
    is a *global severity baseline* (module document §4.2's four shipped
    rows); a row with one or both populated is a progressively more
    specific override. See `service.py`'s own module docstring for the
    full four-level resolution order and its architectural justification.

    Four partial unique indexes (`__table_args__`, below), not one plain
    composite `UNIQUE` constraint, enforce "at most one policy per
    precedence level" correctly — a single composite constraint would
    treat every `NULL` as distinct from every other `NULL` (the identical
    lesson already documented in
    `app/modules/stage_setting_registry/models.py`), silently permitting
    duplicate global baselines or duplicate overrides.

    `policy_id` is a UUID PK (CLAUDE.md A5) — unlike `EngineeringParameter`'s
    stable natural key, a policy row here is genuinely created and (for
    overrides only — never the four baselines) removed over time, the same
    shape of business-entity lifecycle `StageSettingSet` already has.
    """

    __tablename__ = "publication_treatment_policy"

    policy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    finding_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scheme_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    treatment: Mapped[str] = mapped_column(String(40), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        CheckConstraint(f"severity IN {_SEVERITY_VALUES}", name="ck_publication_policy_severity"),
        CheckConstraint(
            f"finding_type IS NULL OR finding_type IN {_FINDING_TYPE_VALUES}",
            name="ck_publication_policy_finding_type",
        ),
        CheckConstraint(
            f"scheme_type IS NULL OR scheme_type IN {_SCHEME_TYPE_VALUES}",
            name="ck_publication_policy_scheme_type",
        ),
        CheckConstraint(
            f"treatment IN {_TREATMENT_VALUES}", name="ck_publication_policy_treatment"
        ),
        # Level 4 — global severity baseline: one row per severity.
        Index(
            "uq_publication_policy_baseline",
            "severity",
            unique=True,
            postgresql_where=text("finding_type IS NULL AND scheme_type IS NULL"),
            sqlite_where=text("finding_type IS NULL AND scheme_type IS NULL"),
        ),
        # Level 3 — scheme-specific severity override (finding-type-agnostic).
        Index(
            "uq_publication_policy_scheme_severity",
            "severity",
            "scheme_type",
            unique=True,
            postgresql_where=text("finding_type IS NULL AND scheme_type IS NOT NULL"),
            sqlite_where=text("finding_type IS NULL AND scheme_type IS NOT NULL"),
        ),
        # Level 2 — global finding-type override (scheme-agnostic).
        Index(
            "uq_publication_policy_finding_type",
            "severity",
            "finding_type",
            unique=True,
            postgresql_where=text("finding_type IS NOT NULL AND scheme_type IS NULL"),
            sqlite_where=text("finding_type IS NOT NULL AND scheme_type IS NULL"),
        ),
        # Level 1 — scheme-specific + finding-type-specific override (most specific).
        Index(
            "uq_publication_policy_scheme_finding_type",
            "severity",
            "finding_type",
            "scheme_type",
            unique=True,
            postgresql_where=text("finding_type IS NOT NULL AND scheme_type IS NOT NULL"),
            sqlite_where=text("finding_type IS NOT NULL AND scheme_type IS NOT NULL"),
        ),
        Index("ix_publication_policy_severity", "severity"),
        Index("ix_publication_policy_finding_type", "finding_type"),
        Index("ix_publication_policy_scheme_type", "scheme_type"),
    )


class PublicationTreatmentPolicyAuditLog(Base):
    """Append-only audit trail for `PublicationTreatmentPolicy` (module
    document §12; CLAUDE.md A4) — owned exclusively by this module.

    `policy_id` is deliberately **not** a foreign key — mirrors
    `StageSettingRegistryAuditLog.stage_setting_id`'s own precedent: a
    removed override's audit history must survive its row being physically
    deleted (this sprint's own instructions §11: "audit evidence must
    survive removal of an override"). `severity`/`finding_type`/
    `scheme_type` are snapshotted onto every audit row for the same
    reason — reconstructing "which logical policy this was" must not
    depend on the policy row still existing.
    """

    __tablename__ = "publication_treatment_policy_audit_log"

    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    policy_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    finding_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    scheme_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "action IN ('created','treatment_changed','removed')",
            name="ck_publication_policy_audit_action",
        ),
        Index("ix_publication_policy_audit_policy_time", "policy_id", changed_at.desc()),
    )


class PublicationRecord(Base):
    """The permanent, immutable record of one completed Publish action —
    the engineering evidence that supported the decision to publish
    (module document §2, §2.1). **Not Scheme Data** — Publication
    Evidence, owned by this capability, never by the scheme module whose
    version it documents (scheme-engineering-principles.md §11).

    Immutable after creation (this sprint's own instructions §5): no
    update or delete service operation exists anywhere in this module
    (service.py), and none should ever be added — a `PublicationRecord`
    records that publication happened; later scheme lifecycle actions
    (Superseded, Entered in Error) must never rewrite that historical
    fact. There is deliberately no Entered-in-Error (or any other)
    lifecycle for `PublicationRecord` itself — the architecture defines
    none, and none is invented here.

    `publication_event_id` is the caller-supplied idempotency key (see
    `service.py`'s own module docstring for the full concurrency-identity
    reasoning) — unique, so the same publish attempt submitted twice
    (e.g. a network retry) is rejected rather than silently duplicated.
    """

    __tablename__ = "publication_record"

    publication_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publication_event_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    scheme_type: Mapped[str] = mapped_column(String(10), nullable=False)
    scheme_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    published_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Opaque, unenforced cross-module references — see module docstring.
    topology_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    load_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    # A version tag for this row's own frozen-evidence shape (child table
    # columns, JSON evidence structure) — not an engineering lifecycle
    # version. Lets a future migration reinterpret older records
    # correctly if the evidence shape itself ever needs to evolve.
    evidence_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        CheckConstraint(
            f"scheme_type IN {_SCHEME_TYPE_VALUES}", name="ck_publication_record_scheme_type"
        ),
        Index("uq_publication_record_event", "publication_event_id", unique=True),
        Index("ix_publication_record_scheme_type", "scheme_type"),
        Index("ix_publication_record_scheme_version", "scheme_version_id"),
        Index("ix_publication_record_published_at", "published_at"),
    )


class PublicationRecordFinding(Base):
    """One frozen `Finding` — copied field-by-field at the moment of
    Publish, never a live reference (this sprint's own instructions §9:
    "Do not rely on recalculating treatment from future policy state").

    `finding_index` is the deterministic, publication-local identity this
    sprint introduces for matching acknowledgements (`Finding` itself has
    none — findings.py's own docstring) — unique within one
    `publication_record_id`, meaningless outside it.

    `resolved_treatment` plus `matched_policy_*` freeze *both* the
    decision and the exact policy scope that produced it, so the record
    remains fully interpretable even if the matching
    `PublicationTreatmentPolicy` row is later changed or removed (this
    sprint's own instructions §9) — `matched_policy_id` is retained only
    as a traceability pointer, never the sole source of truth.
    """

    __tablename__ = "publication_record_finding"

    publication_record_finding_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publication_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("publication_record.publication_record_id", ondelete="RESTRICT"),
        nullable=False,
    )
    finding_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # --- Frozen Finding fields (findings.py's own Finding contract) -------------
    finding_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_object_type: Mapped[str] = mapped_column(String(100), nullable=False)
    affected_object_id: Mapped[str] = mapped_column(String(200), nullable=False)
    evidence: Mapped[dict | None] = mapped_column(_JsonVariant, nullable=True)

    # --- Frozen policy-resolution outcome ---------------------------------------
    resolved_treatment: Mapped[str] = mapped_column(String(40), nullable=False)
    matched_policy_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    matched_policy_severity: Mapped[str] = mapped_column(String(20), nullable=False)
    matched_policy_finding_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    matched_policy_scheme_type: Mapped[str | None] = mapped_column(String(10), nullable=True)
    acknowledgement_required: Mapped[bool] = mapped_column(Boolean, nullable=False)

    __table_args__ = (
        CheckConstraint(
            f"finding_type IN {_FINDING_TYPE_VALUES}", name="ck_publication_record_finding_type"
        ),
        CheckConstraint(
            f"severity IN {_SEVERITY_VALUES}", name="ck_publication_record_finding_severity"
        ),
        CheckConstraint(
            f"resolved_treatment IN {_TREATMENT_VALUES}",
            name="ck_publication_record_finding_treatment",
        ),
        CheckConstraint(
            f"matched_policy_severity IN {_SEVERITY_VALUES}",
            name="ck_publication_record_finding_matched_severity",
        ),
        Index(
            "uq_publication_record_finding_index",
            "publication_record_id",
            "finding_index",
            unique=True,
        ),
        Index("ix_publication_record_finding_record", "publication_record_id"),
    )


class PublicationRecordPrerequisite(Base):
    """One frozen structural-prerequisite check result (this sprint's own
    instructions §6 — the generic contract a future scheme module
    supplies, `publication.py`'s own `PublicationPrerequisiteResult`).
    Only ever `passed=True` in a real `PublicationRecord` — a failed
    prerequisite unconditionally blocks publication before any record is
    created (module document §5) — the column exists for structural
    completeness and defensive clarity, not because a failed row is ever
    expected to be persisted."""

    __tablename__ = "publication_record_prerequisite"

    publication_record_prerequisite_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publication_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("publication_record.publication_record_id", ondelete="RESTRICT"),
        nullable=False,
    )
    prerequisite_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    prerequisite_code: Mapped[str] = mapped_column(String(100), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    affected_object_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    affected_object_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    evidence: Mapped[dict | None] = mapped_column(_JsonVariant, nullable=True)
    source: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        Index(
            "uq_publication_record_prerequisite_index",
            "publication_record_id",
            "prerequisite_index",
            unique=True,
        ),
        Index("ix_publication_record_prerequisite_record", "publication_record_id"),
    )


class PublicationRecordAcknowledgement(Base):
    """One frozen acknowledgement (module document §6) for exactly one
    `PublicationRecordFinding` in the *same* publication — never a
    standalone, mutable, pending-approval table (this sprint's own
    instructions §10). The composite foreign key into
    `publication_record_finding` (below) enforces, at the database level,
    that an acknowledgement can only ever reference a finding that
    actually exists within this same `PublicationRecord` — genuine
    same-aggregate referential integrity, not a cross-module reference."""

    __tablename__ = "publication_record_acknowledgement"

    publication_record_acknowledgement_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    publication_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("publication_record.publication_record_id", ondelete="RESTRICT"),
        nullable=False,
    )
    finding_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    acknowledged_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    acknowledged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    justification: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        ForeignKeyConstraint(
            ["publication_record_id", "finding_index"],
            [
                "publication_record_finding.publication_record_id",
                "publication_record_finding.finding_index",
            ],
            ondelete="RESTRICT",
        ),
        Index(
            "uq_publication_record_ack_finding",
            "publication_record_id",
            "finding_index",
            unique=True,
        ),
        Index("ix_publication_record_ack_record", "publication_record_id"),
    )
