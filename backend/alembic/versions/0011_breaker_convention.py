"""Transformer breaker-numbering convention as reference data.

Adds `transformer_breaker_numbering_convention`, a new Core Platform
reference table keyed by `(hv_voltage_level_id, lv_voltage_level_id, side)`.
Moves the transformer breaker-number *suggestion* convention out of a
hardcoded TypeScript table
(`frontend/src/modules/equipment_registry/transformerBreakerSuggestion.ts`)
so it is auditable, seedable, and maintainable without a frontend code
change — per equipment-registry-module.md's Transformer Registry Business
Rule 7 and CLAUDE.md §11.3/A7 (engineering parameters belong in the
database, not source code).

This remains display-only suggestion data, never backend-validated —
`TransformerTerminal.breaker_number` is unaffected, still free text with no
format check (Business Rule 7, unchanged).

Data is seeded separately by `app/reference_data/seed.py` (migrations create
schema, seeding is a separate manual step, per this project's established
convention — see 0009_correction_status.py's identical note).

Revision ID: 0011_breaker_convention
Revises: 0010_transformer_yard_pair
Create Date: 2026-07-06
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011_breaker_convention"
down_revision: Union[str, None] = "0010_transformer_yard_pair"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transformer_breaker_numbering_convention",
        sa.Column("convention_id", sa.SmallInteger(), autoincrement=True, nullable=False),
        sa.Column("hv_voltage_level_id", sa.SmallInteger(), nullable=False),
        sa.Column("lv_voltage_level_id", sa.SmallInteger(), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("pattern", sa.String(length=20), nullable=True),
        sa.Column("is_standard", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("convention_id"),
        sa.ForeignKeyConstraint(
            ["hv_voltage_level_id"], ["voltage_level.voltage_level_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["lv_voltage_level_id"], ["voltage_level.voltage_level_id"], ondelete="RESTRICT"
        ),
        sa.CheckConstraint("side IN ('HV', 'LV')", name="ck_transformer_breaker_convention_side"),
        sa.UniqueConstraint(
            "hv_voltage_level_id",
            "lv_voltage_level_id",
            "side",
            name="uq_transformer_breaker_convention_pair_side",
        ),
    )
    op.create_index(
        "ix_transformer_breaker_convention_hv",
        "transformer_breaker_numbering_convention",
        ["hv_voltage_level_id"],
    )
    op.create_index(
        "ix_transformer_breaker_convention_lv",
        "transformer_breaker_numbering_convention",
        ["lv_voltage_level_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_transformer_breaker_convention_lv",
        table_name="transformer_breaker_numbering_convention",
    )
    op.drop_index(
        "ix_transformer_breaker_convention_hv",
        table_name="transformer_breaker_numbering_convention",
    )
    op.drop_table("transformer_breaker_numbering_convention")
