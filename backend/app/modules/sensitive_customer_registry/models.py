"""Sensitive Customer Registry persistence models (CLAUDE.md A6 —
Persistence Model layer). Shape per
docs/architecture/sensitive-customer-registry-module.md §5, §7, §11 and
docs/architecture/sensitive-customer-registry-implementation-spec.md §5
(ADR-012).

This module owns exactly one entity family: `SensitiveFacility` (one
physical facility, e.g. "Hospital Kuala Lumpur"), its two module-owned
reference tables (`FacilitySector`, `SensitivityClassification`), and its
own shared audit log. It is **not** a customer-relationship-management
system, not a billing system, not a GIS (EDR-008) — and it must never
contain any GridDefence/scheme-specific vocabulary (ADR-012 decision 5):
no "scheme," "stage," "UFLS," "UVLS," or "EMLS" appears anywhere below.

`transformer_terminal` (from `app.modules.equipment_registry.models`) is
imported read-only here, exactly as it already is elsewhere in this
codebase — this module never writes to Equipment Registry's tables
(CLAUDE.md A1; module document §4). Unlike the Automatic Load Shedding
Functionality Registry, this module references **only** Transformer
Terminal — there is no Circuit Terminal reference at all (module document
§6; implementation spec §5.1). The association is many-to-many via
`SensitiveFacilityTransformerTerminal` (ADR-013): a facility may have zero,
one, or many currently active associated terminals (a facility may be
registered before any supply point is confirmed).

Cardinality is the deliberate inverse of ALSF in both directions: **many**
`SensitiveFacility` rows may reference the same Transformer Terminal (a
single bay might supply both a hospital and an adjacent government
building, module document §7, §9 rule 3), and (since ADR-013) one facility
may itself reference many terminals — no uniqueness constraint exists
beyond the association table's own composite primary key. A future
implementer must not copy ALSF's partial-unique-index pattern here by
analogy (implementation spec §5.1).

`created_by_user_id`/`updated_by_user_id`/`changed_by_user_id` are real
foreign keys to IAM's `user.user_id` (ADR-002), referenced by table-name
string — no cross-module Python import needed (CLAUDE.md A1).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# PostgreSQL (production) gets a genuine SMALLINT surrogate key for
# reference data (CLAUDE.md A5, mirroring app/reference_data/models.py's
# own `_ReferenceKey`). SQLite (this project's default test engine) only
# grants its rowid-autoincrement behaviour to a column literally typed
# INTEGER PRIMARY KEY, not SMALLINT — so other dialects fall back to plain
# INTEGER via this variant. Replicated locally rather than imported from
# Core Platform's own reference_data package, since FacilitySector/
# SensitivityClassification are module-owned reference data, not Core
# Platform's (ADR-012 decision 3; implementation spec §4).
_ReferenceKey = Integer().with_variant(SmallInteger(), "postgresql")


class FacilitySector(Base):
    """Module-owned reference data (CLAUDE.md §11.3) — the broad category
    of facility (Healthcare; Security, Defence & Emergency Services;
    Government & Public Administration; Transport; Utilities; Strategic &
    Economic Infrastructure; Special or Protected Customers; Other
    Sensitive Consumer). Genuinely admin-editable — a deliberate departure
    from Core Platform's read-only-seeded reference tables (implementation
    spec §8) — so a new sector can be added, and an existing one relabeled
    or retired, without a code deployment (CLAUDE.md A7).

    `code` is the stable, immutable machine key every historical audit row
    and any future non-GridDefence consumer keys against; `label` is the
    human-facing, freely renamable display text (implementation spec §8).
    """

    __tablename__ = "facility_sector"

    id: Mapped[int] = mapped_column(_ReferenceKey, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(150), nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Nullable — unlike SensitiveFacility's own accountability columns,
    # since these rows may be created by the unattended seed script
    # (implementation spec §13) with no real IAM actor. Every edit made
    # through the service layer (create_facility_sector/
    # update_facility_sector) always supplies a real, authenticated actor;
    # NULL means "system-seeded baseline value," never "unknown editor."
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )


class SensitivityClassification(Base):
    """Module-owned reference data — an ordered engineering-importance tier
    (High/Medium/Low today). `sort_order` is semantically meaningful here
    (unlike `FacilitySector.sort_order`, which is display ordering only):
    lower `sort_order` means higher sensitivity, so a future consumer can
    reason about "at least Medium sensitivity" without hardcoding tier
    semantics into their own code (module document §7.2).

    Classification is a plain engineering fact — it must never itself
    encode blocking, warning, stage, approval, or override behaviour
    (EDR-008; ADR-012 decision 4). No column on this table, or on
    `SensitiveFacility` below, expresses any such meaning.
    """

    __tablename__ = "sensitivity_classification"

    id: Mapped[int] = mapped_column(_ReferenceKey, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(150), nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    # Nullable — same reasoning as FacilitySector above (seed-created rows
    # have no real IAM actor).
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )


class SensitiveFacility(Base):
    """One record per physical facility (module document §5, §7.3;
    EDR-008) — never an administrative body that could correspond to many
    unrelated physical locations (module doc §7.4). `name` is free text,
    deliberately not a controlled vocabulary (no uniqueness constraint —
    two distinct facilities may share a name).

    Supply-point association with Transformer Terminal now lives on the
    separate `SensitiveFacilityTransformerTerminal` table below, not as a
    column on this class (ADR-013, amending ADR-012 decision 2) — a
    facility may currently be associated with zero, one, or many
    Transformer Terminals. See `SensitiveFacilityTransformerTerminal` for
    the association's own shape and rationale.

    `lifecycle_status` is this module's own, small, CHECK-constrained
    vocabulary — deliberately `ACTIVE`/`ARCHIVED`/`ENTERED_IN_ERROR`, never
    ALSF's `DECOMMISSIONED` terminology (module document §8; task
    instruction). Current-state master data with a full audit trail, not
    the Canonical Version Lifecycle (CLAUDE.md A3), mirroring
    `Circuit`/`Transformer`/ALSF's own classification (CLAUDE.md §11.5).
    """

    __tablename__ = "sensitive_facility"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    facility_sector_id: Mapped[int] = mapped_column(
        _ReferenceKey, ForeignKey("facility_sector.id", ondelete="RESTRICT"), nullable=False
    )
    sensitivity_classification_id: Mapped[int] = mapped_column(
        _ReferenceKey,
        ForeignKey("sensitivity_classification.id", ondelete="RESTRICT"),
        nullable=False,
    )

    lifecycle_status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")

    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "lifecycle_status IN ('ACTIVE','ARCHIVED','ENTERED_IN_ERROR')",
            name="ck_scr_facility_lifecycle_status",
        ),
        Index("ix_scr_facility_sector", "facility_sector_id"),
        Index("ix_scr_facility_sensitivity_classification", "sensitivity_classification_id"),
        Index("ix_scr_facility_lifecycle_status", "lifecycle_status"),
    )


class SensitiveFacilityTransformerTerminal(Base):
    """The association of one `SensitiveFacility` with one currently active
    Transformer Terminal supply point (ADR-013, amending ADR-012
    decision 2). One facility may have many associated terminals; one
    terminal may supply many facilities (the deliberate inverse of ALSF's
    own per-terminal uniqueness rule — no uniqueness constraint exists
    beyond the composite primary key itself).

    Current-state only — mirrors IAM's own `RolePermission` grant pattern
    (simple add/remove, no validity window), not `UserRole`'s
    `revoked_at`-based historical-retention pattern (ADR-013 decision 1).
    This is deliberate: a *removed* association is deleted from this table
    outright; the fact that it existed, when it was added, when it was
    removed, by whom, and why is preserved only in
    `SensitiveCustomerRegistryAuditLog`, never here. This table answers
    "what is currently associated," not "what was ever associated."

    `added_by_user_id` is **not nullable** (unlike `RolePermission.
    granted_by_user_id`) — every association is created through the
    service layer's `set_terminal_associations` by a real, authenticated
    administrator; this table is never seed-populated.
    """

    __tablename__ = "sensitive_facility_transformer_terminal"

    facility_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sensitive_facility.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    transformer_terminal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transformer_terminal.transformer_terminal_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    added_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (Index("ix_scr_facility_terminal_terminal", "transformer_terminal_id"),)


class SensitiveCustomerRegistryAuditLog(Base):
    """Single, shared, append-only audit trail "covering every owned
    entity" (module document §5) — `SensitiveFacility`, `FacilitySector`,
    and `SensitivityClassification` alike, rather than one table per
    entity. Polymorphic via three mutually-exclusive nullable foreign keys
    plus a `subject_type` discriminator, extending ALSF's own
    two-arm target-type XOR technique (`ck_alsf_target_xor`) to three arms
    (implementation spec §5.4).

    One row per changed field (mirroring every other audit log in this
    codebase), never a bulk single-row diff. `change_reason` is nullable at
    the schema level — mandatory-reason enforcement for lifecycle
    transitions and Transformer Terminal reassignment is a **service-layer**
    rule (implementation spec §6, §7), not a column constraint, since this
    same table also carries optional-reason field edits.
    """

    __tablename__ = "sensitive_customer_registry_audit_log"

    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject_type: Mapped[str] = mapped_column(String(30), nullable=False)

    sensitive_facility_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("sensitive_facility.id", ondelete="RESTRICT"),
        nullable=True,
    )
    facility_sector_id: Mapped[int | None] = mapped_column(
        _ReferenceKey, ForeignKey("facility_sector.id", ondelete="RESTRICT"), nullable=True
    )
    sensitivity_classification_id: Mapped[int | None] = mapped_column(
        _ReferenceKey,
        ForeignKey("sensitivity_classification.id", ondelete="RESTRICT"),
        nullable=True,
    )

    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "subject_type IN ('SENSITIVE_FACILITY','FACILITY_SECTOR','SENSITIVITY_CLASSIFICATION')",
            name="ck_scr_audit_subject_type",
        ),
        # Exactly one subject FK per row, matching subject_type — the
        # three-arm extension of ALSF's own XOR pattern (module docstring).
        CheckConstraint(
            "(subject_type = 'SENSITIVE_FACILITY' AND sensitive_facility_id IS NOT NULL "
            "AND facility_sector_id IS NULL AND sensitivity_classification_id IS NULL) "
            "OR "
            "(subject_type = 'FACILITY_SECTOR' AND facility_sector_id IS NOT NULL "
            "AND sensitive_facility_id IS NULL AND sensitivity_classification_id IS NULL) "
            "OR "
            "(subject_type = 'SENSITIVITY_CLASSIFICATION' "
            "AND sensitivity_classification_id IS NOT NULL "
            "AND sensitive_facility_id IS NULL AND facility_sector_id IS NULL)",
            name="ck_scr_audit_subject_xor",
        ),
        Index("ix_scr_audit_facility_time", "sensitive_facility_id", changed_at.desc()),
        Index("ix_scr_audit_sector_time", "facility_sector_id", changed_at.desc()),
        Index(
            "ix_scr_audit_classification_time",
            "sensitivity_classification_id",
            changed_at.desc(),
        ),
        Index("ix_scr_audit_subject_type", "subject_type"),
    )
