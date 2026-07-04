"""Phase 3 UAT follow-up: add optional metadata to SubstationVoltageYard —
commissioning_date, latitude, longitude. Deliberately on the voltage yard,
not the parent Substation: a multi-voltage site may have yards commissioned
at different dates with slightly different GIS coordinates. Also adds
updated_at/updated_by_user_id for edit accountability, mirroring
CircuitTerminal's own precedent (0005_substation_voltage_yard.py).

No data backfill for the three new metadata columns — every existing row
gets NULL, which remains valid (all three are optional; the geo-pair CHECK
constraint permits both-null). updated_at/updated_by_user_id ARE backfilled,
from created_at/created_by_user_id, since no edit has happened yet for any
existing row (identical reasoning to 0005's own circuit_terminal backfill).

Reversible: downgrade() drops the CHECK constraints, the updated_at/
updated_by_user_id FK/columns, and the three metadata columns, in the
reverse order they were added.

Revision ID: 0007_voltage_yard_metadata
Revises: 0006_deprecate_substation_vlevel
Create Date: 2026-07-04
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007_voltage_yard_metadata"
down_revision: Union[str, None] = "0006_deprecate_substation_vlevel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "substation_voltage_yard", sa.Column("commissioning_date", sa.Date(), nullable=True)
    )
    op.add_column(
        "substation_voltage_yard", sa.Column("latitude", sa.Numeric(9, 6), nullable=True)
    )
    op.add_column(
        "substation_voltage_yard", sa.Column("longitude", sa.Numeric(9, 6), nullable=True)
    )
    op.create_check_constraint(
        "ck_voltage_yard_lat_range",
        "substation_voltage_yard",
        "latitude IS NULL OR (latitude BETWEEN -90 AND 90)",
    )
    op.create_check_constraint(
        "ck_voltage_yard_lon_range",
        "substation_voltage_yard",
        "longitude IS NULL OR (longitude BETWEEN -180 AND 180)",
    )
    op.create_check_constraint(
        "ck_voltage_yard_geo_pair",
        "substation_voltage_yard",
        "(latitude IS NULL AND longitude IS NULL) OR "
        "(latitude IS NOT NULL AND longitude IS NOT NULL)",
    )

    op.add_column(
        "substation_voltage_yard",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "substation_voltage_yard", sa.Column("updated_by_user_id", sa.Uuid(), nullable=True)
    )
    op.execute(
        "UPDATE substation_voltage_yard SET updated_at = created_at, "
        "updated_by_user_id = created_by_user_id"
    )
    op.alter_column(
        "substation_voltage_yard",
        "updated_at",
        nullable=False,
        server_default=sa.func.now(),
    )
    op.alter_column("substation_voltage_yard", "updated_by_user_id", nullable=False)
    op.create_foreign_key(
        "substation_voltage_yard_updated_by_user_id_fkey",
        "substation_voltage_yard",
        "user",
        ["updated_by_user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint(
        "substation_voltage_yard_updated_by_user_id_fkey",
        "substation_voltage_yard",
        type_="foreignkey",
    )
    op.drop_column("substation_voltage_yard", "updated_by_user_id")
    op.drop_column("substation_voltage_yard", "updated_at")

    op.drop_constraint("ck_voltage_yard_geo_pair", "substation_voltage_yard", type_="check")
    op.drop_constraint("ck_voltage_yard_lon_range", "substation_voltage_yard", type_="check")
    op.drop_constraint("ck_voltage_yard_lat_range", "substation_voltage_yard", type_="check")
    op.drop_column("substation_voltage_yard", "longitude")
    op.drop_column("substation_voltage_yard", "latitude")
    op.drop_column("substation_voltage_yard", "commissioning_date")
