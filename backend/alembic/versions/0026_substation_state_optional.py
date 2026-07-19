"""Make substation.state_id optional (ADR-026).

State (Malaysian state) is an administrative classification, not part of a
Substation's engineering identity — which is electrical/operational
(mnemonic, voltage yards, connectivity). This migration relaxes
`substation.state_id` from `NOT NULL` to nullable so State can be omitted
at creation, added later, or cleared later.

Preserves all existing data: no row is touched, no value is rewritten, no
placeholder/"Unknown" is inserted. Every existing substation keeps its
current `state_id`; only the column's nullability changes. The FK to
`state(state_id)` (`ON DELETE RESTRICT`) and the `ix_substation_state`
index are unchanged — a filter by a specific `state_id` still works, and a
row with `state_id IS NULL` simply does not match such a filter.

`region_id`, `gm_zone_id`, and `grid_owner_id` remain `NOT NULL` — State
alone is administrative rather than identity-bearing (ADR-026).

Uses batch mode so the same migration applies on both PostgreSQL and
SQLite (SQLite has no native `ALTER COLUMN`), mirroring this project's
other structural migrations (e.g. 0025_stage_setting_trigger).

Revision ID: 0026_substation_state_optional
Revises: 0025_stage_setting_trigger
Create Date: 2026-07-18
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0026_substation_state_optional"
down_revision: Union[str, None] = "0025_stage_setting_trigger"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("substation") as batch_op:
        batch_op.alter_column("state_id", existing_type=sa.SmallInteger(), nullable=True)


def downgrade() -> None:
    # Reinstating NOT NULL requires every row to have a state_id. Any row
    # created (or cleared) while State was optional may legitimately hold
    # NULL, so this downgrade would fail against such data — that is
    # correct and expected (the constraint genuinely cannot be reimposed
    # without a data decision the Project Owner must make), never silently
    # backfilled with a placeholder here.
    with op.batch_alter_table("substation") as batch_op:
        batch_op.alter_column("state_id", existing_type=sa.SmallInteger(), nullable=False)
