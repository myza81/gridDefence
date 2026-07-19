"""GM Zone Options refinement — replace the twelve `gm_zone.code` values
with the Project Owner's authoritative engineering codes.

Only `code` (and, incidentally, no change to `label` — display names are
unchanged) is remapped, one-for-one by the zone each row already
represents. `gm_zone_id` (the actual FK target of `substation.gm_zone_id`,
per CLAUDE.md A5 — reference tables use surrogate SMALLINT keys, never a
business identifier, as their primary key) is never touched, so every
pre-existing `substation.gm_zone_id` reference remains valid across this
migration with no backfill or data loss.

Old code -> new engineering code (identical `label`, hence unambiguous):
    ALOR_SETAR   -> KEDP  (Alor Setar)
    BUTTERWORTH  -> PPNG  (Butterworth)
    IPOH         -> PERK  (Ipoh)
    SELANGOR     -> SELG  (Selangor)
    KUALA_LUMPUR -> KLUM  (Kuala Lumpur)
    SEREMBAN     -> NSEM  (Seremban)
    AYER_KEROH   -> MLKA  (Ayer Keroh)
    KLUANG       -> JOH2  (Kluang)
    JOHOR_BAHRU  -> JOH1  (Johor Bahru)
    KUANTAN      -> PHNG  (Kuantan)
    DUNGUN       -> TERG  (Dungun)
    KOTA_BHARU   -> KELN  (Kota Bharu)

No old code collides with any new code, so every `UPDATE` below is safe
against the `uq_gm_zone_code` unique constraint regardless of statement
order. A row seeded out-of-band under some other `code` is left untouched
— `app/reference_data/seed.py`'s own idempotent `_seed_gm_zones` will add
any of the twelve new rows still missing on next seed run, exactly like
any other reference-table backfill.

Revision ID: 0023_gm_zone_engineering_codes
Revises: 0022_ufls
Create Date: 2026-07-17
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0023_gm_zone_engineering_codes"
down_revision: Union[str, None] = "0022_ufls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (old_code, new_code, label) — label is unchanged, included only so the
# `UPDATE` can double-check it is remapping the row it thinks it is.
_CODE_REMAP: list[tuple[str, str, str]] = [
    ("ALOR_SETAR", "KEDP", "Alor Setar"),
    ("BUTTERWORTH", "PPNG", "Butterworth"),
    ("IPOH", "PERK", "Ipoh"),
    ("SELANGOR", "SELG", "Selangor"),
    ("KUALA_LUMPUR", "KLUM", "Kuala Lumpur"),
    ("SEREMBAN", "NSEM", "Seremban"),
    ("AYER_KEROH", "MLKA", "Ayer Keroh"),
    ("KLUANG", "JOH2", "Kluang"),
    ("JOHOR_BAHRU", "JOH1", "Johor Bahru"),
    ("KUANTAN", "PHNG", "Kuantan"),
    ("DUNGUN", "TERG", "Dungun"),
    ("KOTA_BHARU", "KELN", "Kota Bharu"),
]

_gm_zone = sa.table(
    "gm_zone",
    sa.column("code", sa.String),
    sa.column("label", sa.String),
)


def upgrade() -> None:
    for old_code, new_code, label in _CODE_REMAP:
        op.execute(
            _gm_zone.update()
            .where(_gm_zone.c.code == old_code)
            .where(_gm_zone.c.label == label)
            .values(code=new_code)
        )


def downgrade() -> None:
    for old_code, new_code, label in _CODE_REMAP:
        op.execute(
            _gm_zone.update()
            .where(_gm_zone.c.code == new_code)
            .where(_gm_zone.c.label == label)
            .values(code=old_code)
        )
