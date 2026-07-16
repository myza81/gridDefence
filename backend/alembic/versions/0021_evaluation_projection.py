"""Continuous Evaluation — disposable Evaluation Projection (Shared
Platform Sprint 6; ADR-023; continuous-evaluation-architecture.md §3.1).

Creates `continuous_evaluation_projection` only — the disposable,
non-authoritative background-refresh cache described by
continuous-evaluation-architecture.md §3.1 ("Disposable cached
projections for performance"). One row per `(scheme_type,
scheme_version_id)` evaluation target (this sprint's own instructions
§6), enforced by a unique index.

Does **not** create: an authoritative `finding` table, a `detector`
table, a `scheme_version` table (no generic shared table exists, and
none is created here — a future scheme module remains the sole owner of
its own version table), an event-bus table (ADR-023 defines no message
broker — events are transient value objects, never persisted), or any
`publication_record` duplication. `PublicationRecord`
(findings_publication_governance) remains entirely untouched and does
not reference this table.

`scheme_version_id` is deliberately **not** a foreign key — CLAUDE.md
A2/F2's dependency direction; no scheme-version table exists to
reference. `generation` is the invalidation counter used to detect a
newer refresh request arriving during an in-flight recalculation (this
sprint's own instructions §16) — `CHECK (generation > 0)`.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

# revision identifiers, used by Alembic. Kept within the 32-character
# `alembic_version.version_num` column limit (verified against a real
# PostgreSQL database this sprint — the fuller
# "0021_continuous_evaluation_projection" id does not fit).
revision: str = "0021_evaluation_projection"
down_revision: Union[str, None] = "0020_publication_record"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SCHEME_TYPE_VALUES = "('UFLS','UVLS','EMLS')"
_STATUS_VALUES = "('CURRENT','STALE','RECALCULATING','FAILED')"

# JSONB on PostgreSQL, plain JSON elsewhere — mirrors
# `0020_publication_record.py`'s own established portable-JSON precedent.
_json_type = sa.JSON().with_variant(JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "continuous_evaluation_projection",
        sa.Column("projection_id", sa.Uuid(), nullable=False),
        sa.Column("scheme_type", sa.String(length=10), nullable=False),
        sa.Column("scheme_version_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recalculation_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recalculation_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recalculation_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_result_snapshot", _json_type, nullable=True),
        sa.Column("result_schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("projection_id"),
        sa.CheckConstraint(
            f"scheme_type IN {_SCHEME_TYPE_VALUES}", name="ck_ce_projection_scheme_type"
        ),
        sa.CheckConstraint(f"status IN {_STATUS_VALUES}", name="ck_ce_projection_status"),
        sa.CheckConstraint("generation > 0", name="ck_ce_projection_generation_positive"),
    )
    op.create_index(
        "uq_ce_projection_target",
        "continuous_evaluation_projection",
        ["scheme_type", "scheme_version_id"],
        unique=True,
    )
    op.create_index("ix_ce_projection_status", "continuous_evaluation_projection", ["status"])


def downgrade() -> None:
    op.drop_index("ix_ce_projection_status", table_name="continuous_evaluation_projection")
    op.drop_index("uq_ce_projection_target", table_name="continuous_evaluation_projection")
    op.drop_table("continuous_evaluation_projection")
