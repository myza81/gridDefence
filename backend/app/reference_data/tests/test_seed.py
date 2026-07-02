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
    OperationalStatus,
    Region,
    State,
    VoltageLevel,
)
from app.reference_data.seed import (
    GRID_OWNERS,
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
    }
    assert db_session.query(VoltageLevel).count() == len(VOLTAGE_LEVELS)
    assert db_session.query(Region).count() == len(REGIONS)
    assert db_session.query(State).count() == len(STATES)
    assert db_session.query(GridOwner).count() == len(GRID_OWNERS)
    assert db_session.query(OperationalStatus).count() == len(OPERATIONAL_STATUSES)


def test_second_run_creates_nothing_and_does_not_duplicate(db_session: Session) -> None:
    run_seed(db_session)
    second_counts = run_seed(db_session)

    assert second_counts == {
        "voltage_level": 0,
        "region": 0,
        "state": 0,
        "grid_owner": 0,
        "operational_status": 0,
    }
    # Row counts are unchanged, not doubled.
    assert db_session.query(VoltageLevel).count() == len(VOLTAGE_LEVELS)
    assert db_session.query(Region).count() == len(REGIONS)
    assert db_session.query(State).count() == len(STATES)
    assert db_session.query(GridOwner).count() == len(GRID_OWNERS)
    assert db_session.query(OperationalStatus).count() == len(OPERATIONAL_STATUSES)


def test_seeded_voltage_levels_match_substation_registry_md(db_session: Session) -> None:
    run_seed(db_session)

    labels = {vl.label for vl in db_session.query(VoltageLevel).all()}
    assert labels == {"500kV", "275kV", "230kV", "132kV"}


def test_seed_is_safe_to_run_against_a_partially_seeded_table(db_session: Session) -> None:
    """A row inserted out-of-band (matching a documented code/label) is
    recognised as already-present, not duplicated."""
    db_session.add(GridOwner(code="TNB", label="Tenaga Nasional Berhad (TNB)"))
    db_session.commit()

    counts = run_seed(db_session)

    assert counts["grid_owner"] == len(GRID_OWNERS) - 1
    assert db_session.query(GridOwner).count() == len(GRID_OWNERS)
