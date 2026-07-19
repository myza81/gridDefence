"""Add Thailand and Singapore as State reference options.

Adds two neighbouring interconnected-system States — THA (Thailand) and
SGP (Singapore) — so future engineering records may reference them. This is
a reference-data-only migration: it inserts two rows into ``state`` and
touches no existing State, Substation, or Voltage Yard record.

Idempotent by ``code``: only codes not already present are inserted, so this
migration composes safely with ``app.reference_data.seed.run_seed`` (which
seeds the same rows on a fresh database).

Revision ID: 0027_thailand_singapore_states
Revises: 0026_substation_state_optional
Create Date: 2026-07-18
"""

from __future__ import annotations

from typing import Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0027_thailand_singapore_states"
down_revision: Union[str, None] = "0026_substation_state_optional"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


_NEW_STATES = [
    {"code": "THA", "label": "Thailand"},
    {"code": "SGP", "label": "Singapore"},
]

_state = sa.table(
    "state",
    sa.column("code", sa.String),
    sa.column("label", sa.String),
)


def upgrade() -> None:
    bind = op.get_bind()
    existing = {row[0] for row in bind.execute(sa.text("SELECT code FROM state"))}
    to_insert = [row for row in _NEW_STATES if row["code"] not in existing]
    if to_insert:
        op.bulk_insert(_state, to_insert)


def downgrade() -> None:
    op.execute(_state.delete().where(_state.c.code.in_([row["code"] for row in _NEW_STATES])))
