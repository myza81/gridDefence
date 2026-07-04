"""Transformer Registry UAT correction #2: transformer-number uniqueness is
no longer scoped to `(substation_id, transformer_number)` alone — that key,
added by an earlier UAT correction (0008_transformer_registry), incorrectly
collapses every transformation level at a substation into one shared
bay-number namespace. Real Malaysian grid practice numbers transformer bays
*per transformation pair*: a substation legitimately has a "Transformer Bay
1" on its 275/132kV pair *and a separate* "Transformer Bay 1" on its
132/33kV pair, which the old constraint wrongly rejected.

This migration only drops the now-incorrect `uq_transformer_substation_number`
constraint. No replacement single-table constraint is added: the corrected
uniqueness key is `(substation_id, hv_switchyard_id, lv_switchyard_id,
transformer_number)`, and the two switchyard ids live on the child
`transformer_terminal` rows, not on `transformer` itself — expressing this as
a raw database constraint would require denormalizing both switchyard ids
onto `transformer`, which was considered and rejected (see the ADR-008
addendum's second UAT-correction entry and `models.py`'s `Transformer`
docstring for the full reasoning). Uniqueness is instead enforced at the
service layer (`EquipmentRegistryService.create_transformer`/
`update_transformer`), mirroring this table's original, pre-UAT-correction-#1
design.

No column changes and no data backfill — this is a constraint-only change.

Revision ID: 0010_transformer_yard_pair
Revises: 0009_correction_status
Create Date: 2026-07-05

Downgrade note: re-adding `uq_transformer_substation_number` will fail if any
data was created under the corrected rule that violates it (i.e. two
transformers at the same substation sharing a transformer_number across
different HV/LV pairs) — an expected, documented migration-reversibility
caveat, not a bug in this migration.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0010_transformer_yard_pair"
down_revision: Union[str, None] = "0009_correction_status"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_transformer_substation_number", "transformer", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint(
        "uq_transformer_substation_number", "transformer", ["substation_id", "transformer_number"]
    )
