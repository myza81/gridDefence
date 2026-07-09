"""network_load: add owner column.

Phase 7A (EDR-007 §7.3; docs/architecture/phase-7-operational-snapshot-
correlation-implementation-spec.md §6/§15) — PSS/E's own `OWNER` field is
now parsed (`raw_parser.ParsedLoad.owner`) and persisted here, verbatim,
never interpreted or classified. Nullable, since the abbreviated load-only
RAW shape (raw_parser.py module docstring point 3) has no `OWNER` field at
all.

Hand-written and manually reviewed, mirroring 0012_psse_integration.py's
own review discipline. Additive only — no existing column, constraint, or
table is altered.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0013_network_load_owner"
down_revision: Union[str, None] = "0012_psse_integration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("network_load", sa.Column("owner", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("network_load", "owner")
