"""Read-only persistence access for Core Platform reference/lookup tables.

No write methods — reference data is populated exclusively by
`app/reference_data/seed.py` (CLAUDE.md §11.3), never by request handlers.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.reference_data.models import (
    GridOwner,
    LineType,
    OperationalStatus,
    Region,
    State,
    VoltageLevel,
)

# Reference-table primary keys are SMALLINT on PostgreSQL (CLAUDE.md A5,
# _ReferenceKey in models.py) — max 32767, always positive (GENERATED ALWAYS
# AS IDENTITY starting at 1). A caller-supplied id outside this range can
# never match a real row; treating it as "not found" here (rather than
# letting it reach the database) avoids a raw, unhandled
# psycopg.errors.NumericValueOutOfRange surfacing as a 500 on PostgreSQL —
# a real behavioural difference from SQLite, whose flexible INTEGER typing
# accepts any Python int and simply returns no row instead. Found via
# PostgreSQL verification (Phase 2 follow-up), invisible under SQLite.
_SMALLINT_MAX = 32767


def _in_smallint_range(value: int) -> bool:
    return 1 <= value <= _SMALLINT_MAX


class ReferenceDataRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_voltage_levels(self) -> list[VoltageLevel]:
        stmt = select(VoltageLevel).order_by(VoltageLevel.sort_order, VoltageLevel.label)
        return list(self.db.execute(stmt).scalars().all())

    def list_regions(self) -> list[Region]:
        return list(self.db.execute(select(Region).order_by(Region.label)).scalars().all())

    def list_states(self) -> list[State]:
        return list(self.db.execute(select(State).order_by(State.label)).scalars().all())

    def list_grid_owners(self) -> list[GridOwner]:
        return list(self.db.execute(select(GridOwner).order_by(GridOwner.label)).scalars().all())

    def list_operational_statuses(self) -> list[OperationalStatus]:
        stmt = select(OperationalStatus).order_by(OperationalStatus.label)
        return list(self.db.execute(stmt).scalars().all())

    def list_line_types(self) -> list[LineType]:
        stmt = select(LineType).order_by(LineType.label)
        return list(self.db.execute(stmt).scalars().all())

    def get_voltage_level(self, voltage_level_id: int) -> VoltageLevel | None:
        if not _in_smallint_range(voltage_level_id):
            return None
        return self.db.get(VoltageLevel, voltage_level_id)

    def get_region(self, region_id: int) -> Region | None:
        if not _in_smallint_range(region_id):
            return None
        return self.db.get(Region, region_id)

    def get_state(self, state_id: int) -> State | None:
        if not _in_smallint_range(state_id):
            return None
        return self.db.get(State, state_id)

    def get_grid_owner(self, grid_owner_id: int) -> GridOwner | None:
        if not _in_smallint_range(grid_owner_id):
            return None
        return self.db.get(GridOwner, grid_owner_id)

    def get_operational_status(self, operational_status_id: int) -> OperationalStatus | None:
        if not _in_smallint_range(operational_status_id):
            return None
        return self.db.get(OperationalStatus, operational_status_id)

    def get_line_type(self, line_type_id: int) -> LineType | None:
        if not _in_smallint_range(line_type_id):
            return None
        return self.db.get(LineType, line_type_id)
