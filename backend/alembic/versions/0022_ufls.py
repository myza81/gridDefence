"""UFLS Scheme Module — first concrete consumer of the Shared
Defence-Scheme Platform (docs/architecture/ufls-architecture.md).

Creates `ufls_scheme`, `ufls_scheme_version`, `ufls_stage`,
`ufls_direct_assignment`, `ufls_pocket_assignment`,
`ufls_pocket_assignment_opening_point`, `ufls_audit_log`.

Does **not** create a table for `scheme_platform`'s own
`SchemeVersionMixin` (`__abstract__ = True` — never a table of its own).
`ufls_scheme_version` inherits the mixin's shared columns directly.

No `ufls_load_block` table — superseded (shared-defence-scheme-domain-
model.md §3.1: Direct Assignments attach directly to a stage, no
grouping layer). No `approved_mw`/MW-capture column anywhere — superseded
(current/actual MW is always resolved live via Continuous Evaluation,
never stored as Scheme Data, per shared-defence-scheme-domain-model.md
§2, §11).

Cross-module foreign keys (`transformer_terminal`, `circuit_terminal`,
`stage_setting_set`, `stage_setting`, `user`) are all `ON DELETE
RESTRICT`, per CLAUDE.md §11.7/A2. `topology_version_id`/
`load_snapshot_id` on `ufls_scheme_version` are deliberately **not**
foreign keys — opaque traceability pointers only (CLAUDE.md A2/F2).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022_ufls"
down_revision: Union[str, None] = "0021_evaluation_projection"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_LIFECYCLE_STATUS_VALUES = "('DRAFT','PUBLISHED','SUPERSEDED','ENTERED_IN_ERROR')"


def upgrade() -> None:
    op.create_table(
        "ufls_scheme",
        sa.Column("ufls_scheme_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("updated_by_user_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("ufls_scheme_id"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.user_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["user.user_id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("name", name="uq_ufls_scheme_name"),
    )

    op.create_table(
        "ufls_scheme_version",
        sa.Column("version_id", sa.Uuid(), nullable=False),
        sa.Column("scheme_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=20), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entered_in_error_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("entered_in_error_reason", sa.Text(), nullable=True),
        sa.Column("engineering_remarks", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("published_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("entered_in_error_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("stage_setting_set_id", sa.Uuid(), nullable=True),
        sa.Column("study_reference", sa.String(length=300), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("topology_version_id", sa.Uuid(), nullable=True),
        sa.Column("load_snapshot_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("version_id"),
        sa.ForeignKeyConstraint(["scheme_id"], ["ufls_scheme.ufls_scheme_id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["stage_setting_set_id"],
            ["stage_setting_set.stage_setting_set_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"], ["user.user_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["entered_in_error_by_user_id"], ["user.user_id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint(
            f"lifecycle_status IN {_LIFECYCLE_STATUS_VALUES}",
            name="ck_ufls_scheme_version_lifecycle_status",
        ),
    )
    op.create_index("ix_ufls_scheme_version_scheme_id", "ufls_scheme_version", ["scheme_id"])
    op.create_index(
        "uq_ufls_scheme_version_number",
        "ufls_scheme_version",
        ["scheme_id", "version_number"],
        unique=True,
    )

    op.create_table(
        "ufls_stage",
        sa.Column("ufls_stage_id", sa.Uuid(), nullable=False),
        sa.Column("scheme_version_id", sa.Uuid(), nullable=False),
        sa.Column("stage_setting_id", sa.Uuid(), nullable=False),
        sa.Column("target_mw", sa.Numeric(10, 3), nullable=True),
        sa.Column("engineering_remarks", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("ufls_stage_id"),
        sa.ForeignKeyConstraint(
            ["scheme_version_id"], ["ufls_scheme_version.version_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["stage_setting_id"], ["stage_setting.stage_setting_id"], ondelete="RESTRICT"
        ),
    )
    op.create_index("ix_ufls_stage_scheme_version_id", "ufls_stage", ["scheme_version_id"])
    op.create_index(
        "uq_ufls_stage_setting",
        "ufls_stage",
        ["scheme_version_id", "stage_setting_id"],
        unique=True,
    )

    op.create_table(
        "ufls_direct_assignment",
        sa.Column("ufls_direct_assignment_id", sa.Uuid(), nullable=False),
        sa.Column("ufls_stage_id", sa.Uuid(), nullable=False),
        sa.Column("scheme_version_id", sa.Uuid(), nullable=False),
        sa.Column("transformer_terminal_id", sa.Uuid(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("ufls_direct_assignment_id"),
        sa.ForeignKeyConstraint(
            ["ufls_stage_id"], ["ufls_stage.ufls_stage_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["scheme_version_id"], ["ufls_scheme_version.version_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["transformer_terminal_id"],
            ["transformer_terminal.transformer_terminal_id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_ufls_direct_assignment_stage_id", "ufls_direct_assignment", ["ufls_stage_id"]
    )
    op.create_index(
        "uq_ufls_direct_assignment_terminal_per_version",
        "ufls_direct_assignment",
        ["scheme_version_id", "transformer_terminal_id"],
        unique=True,
    )

    op.create_table(
        "ufls_pocket_assignment",
        sa.Column("ufls_pocket_assignment_id", sa.Uuid(), nullable=False),
        sa.Column("ufls_stage_id", sa.Uuid(), nullable=False),
        sa.Column("scheme_version_id", sa.Uuid(), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("ufls_pocket_assignment_id"),
        sa.ForeignKeyConstraint(
            ["ufls_stage_id"], ["ufls_stage.ufls_stage_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["scheme_version_id"], ["ufls_scheme_version.version_id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_ufls_pocket_assignment_stage_id", "ufls_pocket_assignment", ["ufls_stage_id"]
    )

    op.create_table(
        "ufls_pocket_assignment_opening_point",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ufls_pocket_assignment_id", sa.Uuid(), nullable=False),
        sa.Column("circuit_terminal_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["ufls_pocket_assignment_id"],
            ["ufls_pocket_assignment.ufls_pocket_assignment_id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["circuit_terminal_id"],
            ["circuit_terminal.circuit_terminal_id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "uq_ufls_pocket_opening_point",
        "ufls_pocket_assignment_opening_point",
        ["ufls_pocket_assignment_id", "circuit_terminal_id"],
        unique=True,
    )

    op.create_table(
        "ufls_audit_log",
        sa.Column("log_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column(
            "changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("changed_by_user_id", sa.Uuid(), nullable=True),
        sa.PrimaryKeyConstraint("log_id"),
        sa.ForeignKeyConstraint(
            ["changed_by_user_id"], ["user.user_id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_ufls_audit_log_entity",
        "ufls_audit_log",
        ["entity_type", "entity_id", "changed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_ufls_audit_log_entity", table_name="ufls_audit_log")
    op.drop_table("ufls_audit_log")

    op.drop_index(
        "uq_ufls_pocket_opening_point", table_name="ufls_pocket_assignment_opening_point"
    )
    op.drop_table("ufls_pocket_assignment_opening_point")

    op.drop_index("ix_ufls_pocket_assignment_stage_id", table_name="ufls_pocket_assignment")
    op.drop_table("ufls_pocket_assignment")

    op.drop_index(
        "uq_ufls_direct_assignment_terminal_per_version", table_name="ufls_direct_assignment"
    )
    op.drop_index("ix_ufls_direct_assignment_stage_id", table_name="ufls_direct_assignment")
    op.drop_table("ufls_direct_assignment")

    op.drop_index("uq_ufls_stage_setting", table_name="ufls_stage")
    op.drop_index("ix_ufls_stage_scheme_version_id", table_name="ufls_stage")
    op.drop_table("ufls_stage")

    op.drop_index("uq_ufls_scheme_version_number", table_name="ufls_scheme_version")
    op.drop_index("ix_ufls_scheme_version_scheme_id", table_name="ufls_scheme_version")
    op.drop_table("ufls_scheme_version")

    op.drop_table("ufls_scheme")
