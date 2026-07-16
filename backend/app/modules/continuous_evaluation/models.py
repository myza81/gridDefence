"""Continuous Evaluation persistence models (CLAUDE.md A6 — Persistence
Model layer; Shared Platform Sprint 6).

`EvaluationProjection` is the disposable, non-authoritative background-
refresh projection continuous-evaluation-architecture.md §3.1 describes
(mechanism 4: "Disposable cached projections for performance"). It is
never the source of engineering truth, never referenced by
`PublicationRecord` (findings_publication_governance's own immutable
evidence), and carries no foreign key into any scheme-version table
(none exists — CLAUDE.md A2/F2). It may be replaced, refreshed, or
regenerated at any time; only the transient `EvaluationResult` snapshot
it stores is ever displayed, never treated as authoritative.

Identity (this sprint's own instructions §6): `(scheme_type,
scheme_version_id)` — one current projection per logical evaluation
target, enforced by a database-level unique index. No evaluation
scenario/scope dimension: neither ADR-023 nor continuous-evaluation-
architecture.md documents scenario-specific background projections.

`generation` is the invalidation counter this sprint's own instructions
§16 require for safe concurrency: incremented on every
`request_refresh`; the background worker compares the generation it
started with against the row's current generation before writing
`CURRENT`, so a newer invalidation that arrived mid-recalculation can
never be silently lost (see `service.py`'s own module docstring for the
full algorithm).

`last_result_snapshot` (JSON) freezes the most recent *successful*
`EvaluationResult` — preserved across a subsequent STALE/RECALCULATING/
FAILED transition (this sprint's own instructions §22), so a UI can
always show the last known-good result alongside an honest status,
never blank just because a refresh is pending or failed.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base
from app.modules.continuous_evaluation.schemas import ProjectionStatus
from app.modules.findings_publication_governance.findings import SchemeType

# JSONB on PostgreSQL (indexable, binary-stored), plain JSON elsewhere —
# mirrors findings_publication_governance/models.py's own established
# portable-JSON precedent exactly.
_JsonVariant = JSON().with_variant(JSONB(), "postgresql")


def _sql_in_list(values: list[str]) -> str:
    """See findings_publication_governance/models.py's own identical
    helper docstring — duplicated here (not imported) since it is a
    private, per-module convention, not a shared utility (CLAUDE.md A1)."""
    return "(" + ",".join(f"'{value}'" for value in values) + ")"


_SCHEME_TYPE_VALUES = _sql_in_list([s.value for s in SchemeType])
_STATUS_VALUES = _sql_in_list([s.value for s in ProjectionStatus])


class EvaluationProjection(Base):
    __tablename__ = "continuous_evaluation_projection"

    projection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    scheme_type: Mapped[str] = mapped_column(String(10), nullable=False)
    scheme_version_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recalculation_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recalculation_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recalculation_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Frozen snapshot of the most recent *successful* EvaluationResult
    # (schemas.py) — `result_schema_version` allows a future migration to
    # reinterpret older snapshots correctly if this shape ever evolves,
    # mirroring PublicationRecord.evidence_schema_version's own precedent.
    last_result_snapshot: Mapped[dict | None] = mapped_column(_JsonVariant, nullable=True)
    result_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            f"scheme_type IN {_SCHEME_TYPE_VALUES}", name="ck_ce_projection_scheme_type"
        ),
        CheckConstraint(f"status IN {_STATUS_VALUES}", name="ck_ce_projection_status"),
        CheckConstraint("generation > 0", name="ck_ce_projection_generation_positive"),
        Index("uq_ce_projection_target", "scheme_type", "scheme_version_id", unique=True),
        Index("ix_ce_projection_status", "status"),
    )
