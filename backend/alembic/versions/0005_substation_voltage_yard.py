"""Equipment Registry Phase 3 UAT fix package (ADR-008): substation_voltage_yard,
and circuit_terminal connects to a voltage yard instead of a substation
directly; circuit_terminal gains updated_at/updated_by_user_id for terminal
editability (Phase 3 UAT must-fix items 1-2, docs/architecture/
equipment-registry-module.md §7.5a).

Hand-written and manually reviewed, verified directly against the real,
persistent local PostgreSQL dev database (`engineering_platform`) rather
than a SQLite stand-in — a real PostgreSQL instance was reachable in the
environment this migration was authored in (DEVELOPMENT.md §8's SQLite
stand-in applies only "if no PostgreSQL instance is reachable"). The data
backfill below uses `gen_random_uuid()`, a PostgreSQL-only builtin (core
since PostgreSQL 13) — this migration is PostgreSQL-only by design, matching
every other migration in this series (CLAUDE.md A5's UUID primary keys were
never intended to be portable to SQLite outside the test suite's own
`Base.metadata.create_all()` stand-in, which does not run migration files
at all).

Data backfill strategy (documented per this task's explicit instruction):
- `Substation.voltage_level_id` is a real, NOT NULL column on every existing
  substation row (substation-registry.md §6) — the "no reliable
  voltage_level exists" fallback this task anticipated was not needed.
- Exactly one default `substation_voltage_yard` row is created per existing
  substation, using that substation's own `voltage_level_id`. A substation
  that turns out to have equipment at a second voltage level gets a second
  yard added later, through the ordinary `POST /voltage-yards` endpoint —
  this migration only backfills the one yard implied by data that already
  existed before this change.
- Every existing `circuit_terminal` row is repointed at the single default
  yard belonging to its own `substation_id` — unambiguous, since step 2
  created exactly one yard per substation. No existing circuit_terminal row
  is dropped or loses its `breaker_number`/`commissioning_date`/`remarks`.

Reversible: `downgrade()` restores `circuit_terminal.substation_id` by
joining back through `substation_voltage_yard`, which is always possible
since that relationship is never ambiguous in either direction for this
migration's own backfilled data. (A future edit that adds a *second*
voltage yard to a substation and then re-points an existing terminal at it
would not be perfectly reversible by this downgrade if that terminal's
substation is re-derived from the *new* yard rather than the original one —
this is expected: downgrade restores this migration's own change, not
every change made after it, consistent with Alembic's own linear model.)

Revision ID: 0005_substation_voltage_yard
Revises: 0004_equipment_registry_circuits
Create Date: 2026-07-06
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_substation_voltage_yard"
down_revision: Union[str, None] = "0004_equipment_registry_circuits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. New table.
    op.create_table(
        "substation_voltage_yard",
        sa.Column("voltage_yard_id", sa.Uuid(), nullable=False),
        sa.Column("substation_id", sa.Uuid(), nullable=False),
        sa.Column("voltage_level_id", sa.SmallInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("voltage_yard_id"),
        sa.UniqueConstraint("substation_id", "voltage_level_id", name="uq_substation_voltage_yard"),
        sa.ForeignKeyConstraint(
            ["substation_id"], ["substation.substation_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["voltage_level_id"], ["voltage_level.voltage_level_id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["user.user_id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_substation_voltage_yard_substation", "substation_voltage_yard", ["substation_id"]
    )
    op.create_index(
        "ix_substation_voltage_yard_voltage_level",
        "substation_voltage_yard",
        ["voltage_level_id"],
    )

    # 2. Backfill: one default yard per existing substation (see module
    # docstring, "Data backfill strategy").
    op.execute(
        """
        INSERT INTO substation_voltage_yard
            (voltage_yard_id, substation_id, voltage_level_id, created_at, created_by_user_id)
        SELECT gen_random_uuid(), substation_id, voltage_level_id, created_at, created_by_user_id
        FROM substation
        """
    )

    # 3. Add voltage_yard_id to circuit_terminal, nullable until backfilled.
    op.add_column("circuit_terminal", sa.Column("voltage_yard_id", sa.Uuid(), nullable=True))

    # 4. Backfill existing circuit_terminal rows via their (still-present)
    # substation_id, resolved to the single default yard created in step 2.
    op.execute(
        """
        UPDATE circuit_terminal AS ct
        SET voltage_yard_id = svy.voltage_yard_id
        FROM substation_voltage_yard AS svy
        WHERE svy.substation_id = ct.substation_id
        """
    )
    op.alter_column("circuit_terminal", "voltage_yard_id", nullable=False)

    # 5. Drop the old substation-based FK/unique constraint/index, then the
    # substation_id column itself (exact names confirmed against the live
    # dev database's pg_constraint/pg_indexes before writing this migration).
    op.drop_constraint(
        "circuit_terminal_substation_id_fkey", "circuit_terminal", type_="foreignkey"
    )
    op.drop_constraint("uq_circuit_terminal_substation", "circuit_terminal", type_="unique")
    op.drop_index("ix_circuit_terminal_substation", table_name="circuit_terminal")
    op.drop_column("circuit_terminal", "substation_id")

    # 6. New FK + unique constraint + index for voltage_yard_id.
    op.create_foreign_key(
        "circuit_terminal_voltage_yard_id_fkey",
        "circuit_terminal",
        "substation_voltage_yard",
        ["voltage_yard_id"],
        ["voltage_yard_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_circuit_terminal_voltage_yard", "circuit_terminal", ["circuit_id", "voltage_yard_id"]
    )
    op.create_index("ix_circuit_terminal_voltage_yard", "circuit_terminal", ["voltage_yard_id"])

    # 7. Terminal editability (Phase 3 UAT must-fix items 1-2): add
    # updated_at/updated_by_user_id, backfilled from created_at/
    # created_by_user_id for existing rows (no edit has happened yet, so the
    # creation event is also, truthfully, the most recent "update").
    op.add_column(
        "circuit_terminal", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("circuit_terminal", sa.Column("updated_by_user_id", sa.Uuid(), nullable=True))
    op.execute(
        "UPDATE circuit_terminal SET updated_at = created_at, "
        "updated_by_user_id = created_by_user_id"
    )
    op.alter_column("circuit_terminal", "updated_at", nullable=False, server_default=sa.func.now())
    op.alter_column("circuit_terminal", "updated_by_user_id", nullable=False)
    op.create_foreign_key(
        "circuit_terminal_updated_by_user_id_fkey",
        "circuit_terminal",
        "user",
        ["updated_by_user_id"],
        ["user_id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # Reverse of step 7.
    op.drop_constraint(
        "circuit_terminal_updated_by_user_id_fkey", "circuit_terminal", type_="foreignkey"
    )
    op.drop_column("circuit_terminal", "updated_by_user_id")
    op.drop_column("circuit_terminal", "updated_at")

    # Reverse of steps 5-6: restore substation_id, backfilled via a join
    # back through substation_voltage_yard (see module docstring).
    op.drop_index("ix_circuit_terminal_voltage_yard", table_name="circuit_terminal")
    op.drop_constraint("uq_circuit_terminal_voltage_yard", "circuit_terminal", type_="unique")
    op.drop_constraint(
        "circuit_terminal_voltage_yard_id_fkey", "circuit_terminal", type_="foreignkey"
    )

    op.add_column("circuit_terminal", sa.Column("substation_id", sa.Uuid(), nullable=True))
    op.execute(
        """
        UPDATE circuit_terminal AS ct
        SET substation_id = svy.substation_id
        FROM substation_voltage_yard AS svy
        WHERE svy.voltage_yard_id = ct.voltage_yard_id
        """
    )
    op.alter_column("circuit_terminal", "substation_id", nullable=False)
    op.create_foreign_key(
        "circuit_terminal_substation_id_fkey",
        "circuit_terminal",
        "substation",
        ["substation_id"],
        ["substation_id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_circuit_terminal_substation", "circuit_terminal", ["circuit_id", "substation_id"]
    )
    op.create_index("ix_circuit_terminal_substation", "circuit_terminal", ["substation_id"])

    op.drop_column("circuit_terminal", "voltage_yard_id")

    # 1. Drop the new table.
    op.drop_index("ix_substation_voltage_yard_voltage_level", table_name="substation_voltage_yard")
    op.drop_index("ix_substation_voltage_yard_substation", table_name="substation_voltage_yard")
    op.drop_table("substation_voltage_yard")
