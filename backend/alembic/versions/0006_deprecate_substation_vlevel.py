"""Deprecate Substation.voltage_level_id (ADR-009): make it nullable and stop
enforcing it going forward. A substation's voltage level(s) are now
represented exclusively through SubstationVoltageYard (ADR-008) — this
column is retained, unmodified, as inert legacy data (no row's existing
value is touched or cleared) so historical/administrative reference remains
possible without a harder, less reversible column-drop migration.

No data backfill is needed or performed: every existing row already has a
real value from before this change; only new rows created after this
migration are expected to have a NULL value here, since Substation Create no
longer accepts or requires this field (see app/modules/substation_registry/
schemas.py, service.py).

Reversible: `downgrade()` re-adds the NOT NULL constraint directly. This
will fail if any row created after `upgrade()` has a NULL value — expected
and acceptable, matching this migration's own conservative, no-silent-data-
loss philosophy (see 0005_substation_voltage_yard.py for the same pattern
applied to a data-bearing change; this migration is constraint-only).

Revision ID: 0006_deprecate_substation_vlevel
Revises: 0005_substation_voltage_yard
Create Date: 2026-07-06

Note: the revision id is abbreviated to "vlevel" (not "voltage_level") to
stay within alembic_version.version_num's VARCHAR(32) limit — every prior
revision id in this series is at or under 32 characters for the same
reason (0004_equipment_registry_circuits is exactly 32); the full,
unabbreviated name is used everywhere else (module docstring, ADR-009).
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006_deprecate_substation_vlevel"
down_revision: Union[str, None] = "0005_substation_voltage_yard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("substation", "voltage_level_id", nullable=True)


def downgrade() -> None:
    op.alter_column("substation", "voltage_level_id", nullable=False)
