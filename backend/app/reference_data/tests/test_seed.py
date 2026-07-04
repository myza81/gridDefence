"""Reference data seed idempotency — Phase 1's mandated test list.

Also serves as regression coverage for the SQLite-dialect autoincrement fix
in app/reference_data/models.py (`_ReferenceKey` dialect variant): before
that fix, a second insert against these primary keys failed under SQLite
with a NOT NULL constraint violation.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.reference_data.models import (
    GridOwner,
    LineType,
    OperationalStatus,
    Region,
    State,
    VoltageLevel,
)
from app.reference_data.seed import (
    GRID_OWNERS,
    LINE_TYPES,
    OPERATIONAL_STATUSES,
    REGIONS,
    STATES,
    VOLTAGE_LEVELS,
    run_seed,
)


def test_first_run_creates_every_documented_row(db_session: Session) -> None:
    counts = run_seed(db_session)

    assert counts == {
        "voltage_level": len(VOLTAGE_LEVELS),
        "region": len(REGIONS),
        "state": len(STATES),
        "grid_owner": len(GRID_OWNERS),
        "operational_status": len(OPERATIONAL_STATUSES),
        "line_type": len(LINE_TYPES),
    }
    assert db_session.query(VoltageLevel).count() == len(VOLTAGE_LEVELS)
    assert db_session.query(Region).count() == len(REGIONS)
    assert db_session.query(State).count() == len(STATES)
    assert db_session.query(GridOwner).count() == len(GRID_OWNERS)
    assert db_session.query(OperationalStatus).count() == len(OPERATIONAL_STATUSES)
    assert db_session.query(LineType).count() == len(LINE_TYPES)


def test_second_run_creates_nothing_and_does_not_duplicate(db_session: Session) -> None:
    run_seed(db_session)
    second_counts = run_seed(db_session)

    assert second_counts == {
        "voltage_level": 0,
        "region": 0,
        "state": 0,
        "grid_owner": 0,
        "operational_status": 0,
        "line_type": 0,
    }
    # Row counts are unchanged, not doubled.
    assert db_session.query(VoltageLevel).count() == len(VOLTAGE_LEVELS)
    assert db_session.query(Region).count() == len(REGIONS)
    assert db_session.query(State).count() == len(STATES)
    assert db_session.query(GridOwner).count() == len(GRID_OWNERS)
    assert db_session.query(OperationalStatus).count() == len(OPERATIONAL_STATUSES)
    assert db_session.query(LineType).count() == len(LINE_TYPES)


def test_seeded_voltage_levels_match_substation_registry_md(db_session: Session) -> None:
    run_seed(db_session)

    labels = {vl.label for vl in db_session.query(VoltageLevel).all()}
    assert labels == {"500kV", "275kV", "230kV", "132kV"}


def test_seeded_line_types_match_equipment_registry_module_md(db_session: Session) -> None:
    run_seed(db_session)

    labels = {lt.label for lt in db_session.query(LineType).all()}
    assert labels == {"Overhead Line", "Cable", "Submarine", "Hybrid"}


def test_seed_is_safe_to_run_against_a_partially_seeded_table(db_session: Session) -> None:
    """A row inserted out-of-band (matching a documented code/label) is
    recognised as already-present, not duplicated."""
    db_session.add(GridOwner(code="TNB", label="Tenaga Nasional Berhad (TNB)"))
    db_session.commit()

    counts = run_seed(db_session)

    assert counts["grid_owner"] == len(GRID_OWNERS) - 1
    assert db_session.query(GridOwner).count() == len(GRID_OWNERS)


def test_seed_backfills_a_table_added_by_a_later_phase(db_session: Session) -> None:
    """Regression test for a Phase 3 UAT incident: a database seeded by an
    earlier version of this script (before `line_type` existed) has every
    other reference table fully populated but `line_type` empty. Re-running
    `run_seed` — exactly the fix applied to the affected dev database — must
    backfill only the newly-introduced table, leaving the rest untouched."""
    run_seed(db_session)
    db_session.query(LineType).delete()
    db_session.commit()
    assert db_session.query(LineType).count() == 0

    counts = run_seed(db_session)

    assert counts == {
        "voltage_level": 0,
        "region": 0,
        "state": 0,
        "grid_owner": 0,
        "operational_status": 0,
        "line_type": len(LINE_TYPES),
    }
    assert db_session.query(LineType).count() == len(LINE_TYPES)
    assert db_session.query(VoltageLevel).count() == len(VOLTAGE_LEVELS)
