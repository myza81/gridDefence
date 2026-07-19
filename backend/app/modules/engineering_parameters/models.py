"""Engineering Parameter Configuration persistence models (CLAUDE.md A6 —
Persistence Model layer). Shape per
docs/architecture/engineering-parameter-configuration-architecture.md
§5, §11 (ADR-021).

This module owns exactly one entity family: the current, audited value of
every named, platform-wide engineering parameter (e.g. the Continuous
Evaluation Engine's MW tolerance). It is **not** Reference Data
(`app/reference_data/`) — ADR-021's own "Why not Reference Data" — every
row here is individually audited and individually write-gated, unlike
Reference Data's idempotently-seeded, unaudited lookup rows.

`updated_by_user_id`/`changed_by_user_id` are real foreign keys to IAM's
`user.user_id` (ADR-002), referenced by table-name string — no cross-module
Python import needed (CLAUDE.md A1). Both are nullable only for the
bootstrap-seed exception (this module's own `bootstrap.py`, which seeds the
one architecture-approved parameter — `mw_tolerance_percentage` — with
`actor_user_id=None`, mirroring every other module's own bootstrap
convention for `grant_permission_to_role`, and IAMAuditLog's own documented
"nullable only for the bootstrap exception").
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EngineeringParameter(Base):
    """One row per named engineering parameter — its current value only
    (module document §8: current-value-plus-audit-log, never a Draft/
    Published lifecycle; a tolerance value has no in-progress editable
    state to model).

    `parameter_key` is the primary key — a short, stable, code-referenced
    string identity (CLAUDE.md A5's own "reference and lookup tables...
    do not require UUIDs unless there is a specific architectural
    reason" allowance, applied here exactly as `Permission.permission_id`
    already does for IAM's own small, code-referenced catalog). This
    table is deliberately schema-stable: adding a future parameter is a
    new row, never a new column (module document §17).

    `value` is stored as `String` rather than a numeric column so this
    table never needs a schema change to accommodate a future
    non-numeric parameter (module document §5: "value (numeric or
    string, per parameter)"). Per-`parameter_key` type/range validation
    (module document §10) is enforced at the service layer, not here —
    this table has no way to know, structurally, which key expects what
    shape of value.
    """

    __tablename__ = "engineering_parameter"

    parameter_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )


class EngineeringParameterAuditLog(Base):
    """Append-only record of changes to an `EngineeringParameter`'s value
    (module document §14; CLAUDE.md A4). One row per value change,
    including the initial creation (`old_value IS NULL`) — mirrors
    `AutomaticLoadSheddingFunctionalityAuditLog`'s own "created" audit
    convention, applied here to the single `value` field this module's
    entity actually has.
    """

    __tablename__ = "engineering_parameter_audit_log"

    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    parameter_key: Mapped[str] = mapped_column(
        String(100),
        ForeignKey("engineering_parameter.parameter_key", ondelete="RESTRICT"),
        nullable=False,
    )
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_engineering_parameter_audit_key_time", "parameter_key", changed_at.desc()),
    )
