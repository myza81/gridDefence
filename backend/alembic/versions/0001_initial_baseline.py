"""Initial baseline — establishes the migration chain.

No-op by design: Phase 0 (Repository Foundation) creates no domain tables.
The first real schema migration lands with Phase 1 (IAM + Core Reference
Data), per docs/architecture/implementation-plan.md.

Revision ID: 0001_initial_baseline
Revises:
Create Date: 2026-07-02
"""
from typing import Sequence, Union

# revision identifiers, used by Alembic.
revision: str = "0001_initial_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op — establishes the migration chain's root revision."""
    pass


def downgrade() -> None:
    """No-op."""
    pass
