"""UFLS persistence models (CLAUDE.md A6 — Persistence Model layer).
Shape per docs/architecture/ufls-module.md §5 (owned entities, as
corrected by the Engineering Scheme Architecture Pack — see
docs/architecture/ufls-architecture.md for the exact reconciliation),
docs/architecture/shared-defence-scheme-domain-model.md §2-§3, ADR-015,
ADR-016.

`UflsSchemeVersion` composes `scheme_platform.models.SchemeVersionMixin`
for every shared lifecycle/version column (version_id, version_number,
lifecycle_status, publish/supersede/entered-in-error metadata,
engineering_remarks, timestamps) and adds only what is genuinely UFLS's
own: `scheme_id` (this module's own FK — deliberately excluded from the
shared mixin, per its own docstring), `stage_setting_set_id` (the
selected, version-wide Stage Setting Set — ADR-016), and the engineering
basis fields (`study_reference`, `topology_version_id`,
`load_snapshot_id`, `effective_date`).

**No `approved_mw`/MW-capture field exists anywhere in this file.** The
old `ufls-module.md` §7.6 design (capture `approved_mw` once, at
Approval) is superseded — the current model
(shared-defence-scheme-domain-model.md §2, §11) stores only external-study
`target_mw` per stage; current/actual MW is always resolved live via
Continuous Evaluation, never stored as Scheme Data, at any lifecycle
stage, including Published.

**No `UflsLoadBlock` table exists.** The old grouping layer between a
Stage and its Direct Assignments is superseded — Direct Assignments
attach directly to a `UflsStage` (shared-defence-scheme-domain-model.md
§3.1), matching Boundary Pocket Assignments' own existing shape exactly.

`scheme_version_id` is denormalized onto both assignment tables purely to
support the database-level uniqueness constraints Rule 7/8-equivalent and
"a Transformer Terminal may appear only once per version" require without
a multi-table join — a deliberate, minimal denormalization for constraint
enforcement (CLAUDE.md §11.8), not a duplicated source of truth (it is
never independently written; `service.py` always sets it from the owning
stage's own version at creation time).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.scheme_platform.models import (
    SchemeVersionMixin,
    scheme_version_lifecycle_check_sql,
)


class UflsScheme(Base):
    """The stable identity a UFLS scheme's versions belong to
    (ufls-module.md §5) — e.g. "Peninsular Malaysia UFLS Scheme." Rarely
    changes; exists so "only one Published version" (ADR-015) is scoped
    correctly even if a future, genuinely separate regional UFLS scheme
    is ever needed, without a discriminator-flag workaround."""

    __tablename__ = "ufls_scheme"

    ufls_scheme_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

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


class UflsSchemeVersion(SchemeVersionMixin, Base):
    """The versioned aggregate root — one complete, coherent UFLS scheme
    design as of a point in time (shared-defence-scheme-domain-model.md
    §2). Composes `SchemeVersionMixin` for every shared lifecycle column;
    see this module's own docstring for exactly what is added here."""

    __tablename__ = "ufls_scheme_version"

    scheme_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ufls_scheme.ufls_scheme_id", ondelete="RESTRICT"),
        nullable=False,
    )

    # The version-wide selected Stage Setting Set (ADR-016) — nullable
    # only until the engineer selects one during Draft; a structural
    # Publication prerequisite requires it be set and Published before
    # this version may Publish (service.py).
    stage_setting_set_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stage_setting_set.stage_setting_set_id", ondelete="RESTRICT"),
        nullable=True,
    )

    # --- Engineering basis (task §3) — external-study references only,
    # never a calculated value (scheme-engineering-principles.md §1) -----------
    study_reference: Mapped[str | None] = mapped_column(String(300), nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Opaque traceability pointers — the evaluation snapshot this Draft is
    # currently viewed/evaluated against (continuous-evaluation-
    # architecture.md §5). Deliberately not foreign keys (CLAUDE.md
    # A2/F2 — UFLS never depends on PSS/E Integration's own tables).
    topology_version_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    load_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            scheme_version_lifecycle_check_sql(), name="ck_ufls_scheme_version_lifecycle_status"
        ),
        Index("ix_ufls_scheme_version_scheme_id", "scheme_id"),
        Index("uq_ufls_scheme_version_number", "scheme_id", "version_number", unique=True),
    )


class UflsStage(Base):
    """One frequency-triggered shedding stage within a version
    (shared-defence-scheme-domain-model.md §2.2). References exactly one
    `StageSetting` row from the version's own selected Stage Setting
    Set — threshold, time delay, and stage order are Stage Setting
    Registry's own owned data (ADR-016), never duplicated here."""

    __tablename__ = "ufls_stage"

    ufls_stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scheme_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ufls_scheme_version.version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    stage_setting_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stage_setting.stage_setting_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # External-study input, engineer-entered — never calculated
    # (shared-defence-scheme-domain-model.md §2).
    target_mw: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    engineering_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_ufls_stage_scheme_version_id", "scheme_version_id"),
        Index("uq_ufls_stage_setting", "scheme_version_id", "stage_setting_id", unique=True),
    )


class UflsDirectAssignment(Base):
    """A direct, Transformer-Terminal-level assignment attached directly
    to a `UflsStage` (shared-defence-scheme-domain-model.md §3.1 — no
    load-block grouping layer). References the authoritative Transformer
    Terminal identity from Equipment Registry directly — never a
    free-text placeholder (Equipment Registry now exists; the old
    `ufls-module.md` §7.4 Open Questions are resolved)."""

    __tablename__ = "ufls_direct_assignment"

    ufls_direct_assignment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ufls_stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ufls_stage.ufls_stage_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Denormalized from the owning stage's own version — see module
    # docstring for why.
    scheme_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ufls_scheme_version.version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    transformer_terminal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transformer_terminal.transformer_terminal_id", ondelete="RESTRICT"),
        nullable=False,
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_ufls_direct_assignment_stage_id", "ufls_stage_id"),
        # ufls-module.md §9 rule 6/7 (as corrected): a Transformer Terminal
        # may appear only once within the same Scheme Version, across all
        # stages.
        Index(
            "uq_ufls_direct_assignment_terminal_per_version",
            "scheme_version_id",
            "transformer_terminal_id",
            unique=True,
        ),
    )


class UflsPocketAssignment(Base):
    """A topology-derived Boundary Pocket assignment attached directly to
    a `UflsStage` (boundary-pocket-architecture.md §8). Stores only the
    selected `CircuitTerminal` opening-point set as engineering intent —
    no derived substation set, no topology reference, no MW (all of that
    is either live-derived or, at Publication, captured into the
    `PublicationRecord` instead, never here)."""

    __tablename__ = "ufls_pocket_assignment"

    ufls_pocket_assignment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ufls_stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ufls_stage.ufls_stage_id", ondelete="RESTRICT"),
        nullable=False,
    )
    scheme_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ufls_scheme_version.version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("ix_ufls_pocket_assignment_stage_id", "ufls_stage_id"),)


class UflsPocketAssignmentOpeningPoint(Base):
    """One selected `CircuitTerminal` opening point within a
    `UflsPocketAssignment` — normalized, not a JSON array (mirrors the
    established `network_model`/pocket-evaluation precedent)."""

    __tablename__ = "ufls_pocket_assignment_opening_point"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ufls_pocket_assignment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ufls_pocket_assignment.ufls_pocket_assignment_id", ondelete="RESTRICT"),
        nullable=False,
    )
    circuit_terminal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("circuit_terminal.circuit_terminal_id", ondelete="RESTRICT"),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "uq_ufls_pocket_opening_point",
            "ufls_pocket_assignment_id",
            "circuit_terminal_id",
            unique=True,
        ),
    )


class UflsAuditLog(Base):
    """UFLS's own append-only audit trail (CLAUDE.md A4) — covering every
    owned entity above, including lifecycle transitions (delegated to
    `scheme_platform`'s own service, audited here by UFLS's own service
    layer wrapping each call)."""

    __tablename__ = "ufls_audit_log"

    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (Index("ix_ufls_audit_log_entity", "entity_type", "entity_id", "changed_at"),)
