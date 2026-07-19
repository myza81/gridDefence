"""Stage Setting Registry persistence models (CLAUDE.md A6 — Persistence
Model layer). Shape per docs/architecture/stage-setting-set-architecture.md
§3, §6, §8, §9 (ADR-016, ADR-020) and, for `StageSettingTrigger`
specifically, ADR-025.

This module owns `StageSettingSet`, `StageSetting`, and
`StageSettingTrigger` — the reusable, independently-versioned stage
structure UFLS and UVLS both reference by id, never duplicate. It is a
standalone, shared Core Platform module
([ADR-020](../../../../docs/adr/ADR-020-stage-setting-registry-as-standalone-shared-module.md)),
never owned by, or embedded inside, UFLS or UVLS.

**Two-level stage structure (ADR-025):** a `StageSetting` is one shedding
stage (identity, `stage_order`, region scope); it owns one or more
`StageSettingTrigger` rows, each an independent frequency/voltage-time
operating criterion for that same stage. `UflsStage.stage_setting_id`
(and any future `UvlsStage` equivalent) references the parent
`StageSetting` — the stage — never an individual trigger, since UFLS/UVLS
assignments belong to the stage, not to one of its operating criteria.

`created_by_user_id`/`updated_by_user_id`/`changed_by_user_id` are real
foreign keys to IAM's `user.user_id` (ADR-002), referenced by table-name
string — no cross-module Python import needed (CLAUDE.md A1).

**Uniqueness/monotonicity scoping (stage-setting-set-architecture.md §7
rule 4, as amended by ADR-025):** `stage_order` must be unique — and each
stage's most severe trigger's threshold value strictly decreasing — *within
the same region scope*, "including the grid-wide null-scope group treated
as its own scope." A single `UNIQUE(stage_setting_set_id, region_scope_id,
stage_order)` constraint cannot express this correctly on its own: standard
SQL treats every `NULL` as distinct from every other `NULL` for uniqueness
purposes, so it would never actually reject two UFLS rows (both
`region_scope_id IS NULL`) sharing the same `stage_order`. Two partial
unique indexes, below, resolve this precisely: one scoped to
`region_scope_id IS NULL` (the grid-wide/UFLS group, treated as its own
single scope), one scoped to `region_scope_id IS NOT NULL` (each concrete
UVLS region, keyed by its own id) — mirroring the exact
`postgresql_where`/`sqlite_where` dual-index technique already established
in `app/modules/automatic_load_shedding_functionality/models.py`.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class StageSettingSet(Base):
    """The stable identity, description, and lifecycle-governed container
    for one ordered stage structure, belonging to exactly one scheme type
    (module document §3).

    `scheme_type` is set at creation and never changed thereafter by this
    module's own service layer (module document §8: "immutable once any
    `StageSetting` row exists against it" is the documented floor; treating
    it as immutable from creation is a stricter, safe implementation choice
    within that floor, not a departure from it — it avoids the edge case of
    a zero-setting Draft silently changing scheme type mid-design).

    No `published_at`/`published_by_user_id`/`entered_in_error_reason`
    columns — module document §9's own conceptual schema lists only
    `status`, `created_by_user_id`, `updated_by_user_id`, `created_at`,
    `updated_at`. Who/when/why for every transition (including Publish and
    Entered-in-Error) is the audit log's job (§12), not a duplicated column
    on the entity itself — mirrors
    `AutomaticLoadSheddingFunctionality`'s own precedent (no
    `decommission_reason` column; the reason lives only in its audit log).
    """

    __tablename__ = "stage_setting_set"

    stage_setting_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scheme_type: Mapped[str] = mapped_column(String(10), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT")

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
        CheckConstraint("scheme_type IN ('UFLS','UVLS')", name="ck_stage_setting_set_scheme_type"),
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','ENTERED_IN_ERROR')",
            name="ck_stage_setting_set_status",
        ),
        Index("ix_stage_setting_set_scheme_type", "scheme_type"),
        Index("ix_stage_setting_set_status", "status"),
    )


class StageSetting(Base):
    """One ordered shedding stage within a Stage Setting Set — `stage_order`
    and (UVLS only) an optional region scope (module document §3). Owns one
    or more `StageSettingTrigger` rows, each an independent frequency/
    voltage-time operating criterion for this same stage (ADR-025) — a
    stage no longer carries a threshold or time delay directly; those
    belong to its trigger(s).

    `region_scope_id` is UVLS-only — must be `NULL` for every UFLS setting
    (module document §4: "unchanged from `uvls-module.md` §7.2's own
    region-scoping reasoning"). This cross-table invariant (it depends on
    the *parent* `StageSettingSet.scheme_type`, not any column on this
    table) cannot be expressed as a portable `CHECK` constraint here and is
    enforced at the service layer only — module document §5's own "Enforced
    at the service layer... and reinforced by a database CHECK/foreign-key
    scoping where practical" already acknowledges DB-level enforcement is
    not always the achievable half of this pattern.
    """

    __tablename__ = "stage_setting"

    stage_setting_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    stage_setting_set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stage_setting_set.stage_setting_set_id", ondelete="RESTRICT"),
        nullable=False,
    )
    stage_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    region_scope_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("region.region_id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        # Two partial unique indexes — see module docstring for why a
        # single UNIQUE(stage_setting_set_id, region_scope_id, stage_order)
        # cannot correctly express "unique per scope, including the
        # grid-wide null-scope group treated as its own scope."
        Index(
            "uq_stage_setting_order_no_scope",
            "stage_setting_set_id",
            "stage_order",
            unique=True,
            postgresql_where=text("region_scope_id IS NULL"),
            sqlite_where=text("region_scope_id IS NULL"),
        ),
        Index(
            "uq_stage_setting_order_scoped",
            "stage_setting_set_id",
            "region_scope_id",
            "stage_order",
            unique=True,
            postgresql_where=text("region_scope_id IS NOT NULL"),
            sqlite_where=text("region_scope_id IS NOT NULL"),
        ),
        Index("ix_stage_setting_set", "stage_setting_set_id"),
        Index("ix_stage_setting_region_scope", "region_scope_id"),
    )


class StageSettingTrigger(Base):
    """One independent frequency/voltage-time operating criterion for a
    shedding stage (ADR-025) — the entity `docs/engineering/glossary.md`'s
    own Stage definition names "triggered at a specific frequency or
    voltage threshold." A `StageSetting` (the stage) owns one or more of
    these; satisfaction of any one configured trigger constitutes operation
    of that same stage (ADR-025's own "operating semantics" — recorded
    here, never evaluated or simulated by this module).

    `threshold_value` is `Numeric`, not a binary float — an exact decimal
    type for an engineering threshold, mirroring
    `Transformer.capacity_mva`'s own `Numeric(8, 2)` precedent
    (`app/modules/equipment_registry/models.py`). `threshold_unit` is a
    denormalized display convenience *derived from the grandparent
    `StageSettingSet`'s own `scheme_type`* ("Hz" for UFLS, "p.u." for
    UVLS — the exact terminology already established in `uvls-module.md`
    §7.2/§7.3), set by the service layer at creation time, never
    independently supplied by a caller.

    No ordering or monotonicity relationship is enforced between triggers
    within the same stage (ADR-025 business rule 6) — only that
    `trigger_order` and the (`threshold_value`, `time_delay_ms`) pair are
    each unique within the parent stage (data-entry-error prevention, not
    an engineering judgement this module makes on the engineer's behalf).
    """

    __tablename__ = "stage_setting_trigger"

    stage_setting_trigger_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    stage_setting_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("stage_setting.stage_setting_id", ondelete="RESTRICT"),
        nullable=False,
    )
    trigger_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    # `Numeric`, not `Float`/`Double` — see class docstring.
    threshold_value: Mapped[float] = mapped_column(Numeric(9, 4), nullable=False)
    threshold_unit: Mapped[str] = mapped_column(String(10), nullable=False)
    time_delay_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "time_delay_ms >= 0", name="ck_stage_setting_trigger_time_delay_non_negative"
        ),
        # Definitional, not policy (mirrors ADR-021's own "a percentage
        # value must lie in (0, 100) is definitional, not policy"
        # reasoning): a frequency or per-unit voltage magnitude is a
        # non-negative physical quantity by definition — this is not a
        # judgment-based engineering threshold range (which this module
        # deliberately does not invent, per this sprint's own instructions).
        CheckConstraint("threshold_value > 0", name="ck_stage_setting_trigger_threshold_positive"),
        Index(
            "uq_stage_setting_trigger_order",
            "stage_setting_id",
            "trigger_order",
            unique=True,
        ),
        # ADR-025 business rule 3 — the same (threshold, delay) pair
        # configured twice under one stage is a data-entry error, not a
        # second real operating criterion.
        Index(
            "uq_stage_setting_trigger_pair",
            "stage_setting_id",
            "threshold_value",
            "time_delay_ms",
            unique=True,
        ),
        Index("ix_stage_setting_trigger_stage", "stage_setting_id"),
    )


class StageSettingRegistryAuditLog(Base):
    """Append-only audit trail for the Stage Setting Registry (module
    document §12; CLAUDE.md A4) — owned exclusively by this module, never
    shared with, or duplicated inside, UFLS's or UVLS's own audit logs.

    Polymorphic across all three owned entities (`StageSettingSet`,
    `StageSetting`, and `StageSettingTrigger` — ADR-025), mirroring
    `SensitiveCustomerRegistryAuditLog`'s own established polymorphic-audit
    pattern (`subject_type` discriminator, nullable per-entity columns).
    None of `stage_setting_set_id`, `stage_setting_id`, or
    `stage_setting_trigger_id` is a foreign key — a removed `StageSetting`
    or `StageSettingTrigger` row (module document §8: settings/triggers may
    be removed while the parent set is Draft) and a physically deleted
    `StageSettingSet` Draft itself (ADR-024) must all leave their own audit
    history intact after the row they describe no longer exists. A
    "deleted"/"removed" entry's own captured `old_value` (identifying
    metadata at time of deletion) is what a reader relies on afterward,
    never a live join back to a row that may be gone
    (`0024_stage_setting_registry_audit_fk_correction` dropped the
    `stage_setting_set_id` foreign key `0018_stage_setting_registry`
    originally created, once ADR-024 made that constraint incompatible with
    Draft deletion; `stage_setting_trigger_id` is never a foreign key from
    the start, for the identical reason, applied from ADR-025 onward).
    """

    __tablename__ = "stage_setting_registry_audit_log"

    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # Deliberately not a foreign key (see class docstring, ADR-024) — a
    # deleted StageSettingSet's own audit history must survive its row
    # being physically deleted.
    stage_setting_set_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    # Deliberately not a foreign key (see class docstring) — a removed
    # StageSetting's own audit history must survive its row being deleted.
    stage_setting_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    # Deliberately not a foreign key (see class docstring, ADR-025) — a
    # removed StageSettingTrigger's own audit history must survive its row
    # being deleted.
    stage_setting_trigger_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "subject_type IN ('STAGE_SETTING_SET','STAGE_SETTING','STAGE_SETTING_TRIGGER')",
            name="ck_ssr_audit_subject_type",
        ),
        Index("ix_ssr_audit_set_time", "stage_setting_set_id", changed_at.desc()),
    )
