"""Stage Setting Registry — audit log FK correction (ADR-024).

`stage_setting_registry_audit_log.stage_setting_set_id` was created
(`0018_stage_setting_registry`) as a hard `ON DELETE RESTRICT` foreign
key, on the assumption at the time that a `StageSettingSet` row itself
would never be physically deleted (only individual `StageSetting` child
rows could be, while Draft — `stage_setting_id` on this same table was
already, deliberately, never made a foreign key for exactly this reason;
see `models.py`'s own docstring). ADR-024 now permits a Draft
`StageSettingSet` to be physically deleted, which the old constraint
would make impossible the moment its own deletion is audited (the audit
row referencing it would itself become an un-droppable blocker via
`RESTRICT`). This migration corrects `stage_setting_set_id` to the same
treatment `stage_setting_id` already has: a plain, non-foreign-key UUID
column, so a "deleted" audit entry survives its own subject's deletion —
its own captured `old_value` (scheme type, description, setting count)
is what a reader relies on afterward, not a live join back to a row that
may no longer exist.

Does not edit `0018_stage_setting_registry` in place (CLAUDE.md's own
established convention — never edit a previously-shipped migration);
this is an additive correction on top of it.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0024_ssr_audit_fk_correction"
down_revision: Union[str, None] = "0023_gm_zone_engineering_codes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT_NAME = "stage_setting_registry_audit_log_stage_setting_set_id_fkey"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT_NAME, "stage_setting_registry_audit_log", type_="foreignkey")


def downgrade() -> None:
    op.create_foreign_key(
        _CONSTRAINT_NAME,
        "stage_setting_registry_audit_log",
        "stage_setting_set",
        ["stage_setting_set_id"],
        ["stage_setting_set_id"],
        ondelete="RESTRICT",
    )
