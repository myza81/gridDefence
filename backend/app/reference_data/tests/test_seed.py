"""Reference data seed idempotency — Phase 1's mandated test list.

Also serves as regression coverage for the SQLite-dialect autoincrement fix
in app/reference_data/models.py (`_ReferenceKey` dialect variant): before
that fix, a second insert against these primary keys failed under SQLite
with a NOT NULL constraint violation.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.reference_data.models import (
    GmZone,
    GridOwner,
    LineType,
    OperationalStatus,
    Region,
    State,
    TransformerBreakerNumberingConvention,
    VoltageLevel,
)
from app.reference_data.seed import (
    GM_ZONES,
    GRID_OWNERS,
    LINE_TYPES,
    OPERATIONAL_STATUSES,
    REGIONS,
    STATES,
    TRANSFORMER_BREAKER_NUMBERING_CONVENTIONS,
    VOLTAGE_LEVELS,
    run_seed,
)


def test_first_run_creates_every_documented_row(db_session: Session) -> None:
    counts = run_seed(db_session)

    assert counts == {
        "voltage_level": len(VOLTAGE_LEVELS),
        "region": len(REGIONS),
        "gm_zone": len(GM_ZONES),
        "state": len(STATES),
        "grid_owner": len(GRID_OWNERS),
        "operational_status": len(OPERATIONAL_STATUSES),
        "line_type": len(LINE_TYPES),
        "transformer_breaker_numbering_convention": len(TRANSFORMER_BREAKER_NUMBERING_CONVENTIONS),
    }
    assert db_session.query(VoltageLevel).count() == len(VOLTAGE_LEVELS)
    assert db_session.query(Region).count() == len(REGIONS)
    assert db_session.query(GmZone).count() == len(GM_ZONES)
    assert db_session.query(State).count() == len(STATES)
    assert db_session.query(GridOwner).count() == len(GRID_OWNERS)
    assert db_session.query(OperationalStatus).count() == len(OPERATIONAL_STATUSES)
    assert db_session.query(LineType).count() == len(LINE_TYPES)
    assert db_session.query(TransformerBreakerNumberingConvention).count() == len(
        TRANSFORMER_BREAKER_NUMBERING_CONVENTIONS
    )


def test_seed_includes_thailand_and_singapore_states(db_session: Session) -> None:
    run_seed(db_session)
    codes = {s.code for s in db_session.query(State).all()}
    assert "THA" in codes
    assert "SGP" in codes
    assert db_session.query(State).filter_by(code="THA").one().label == "Thailand"
    assert db_session.query(State).filter_by(code="SGP").one().label == "Singapore"
    # The pre-existing Malaysian states remain present and unchanged.
    assert {"JHR", "SEL", "PJY"} <= codes


def test_second_run_creates_nothing_and_does_not_duplicate(db_session: Session) -> None:
    run_seed(db_session)
    second_counts = run_seed(db_session)

    assert second_counts == {
        "voltage_level": 0,
        "region": 0,
        "gm_zone": 0,
        "state": 0,
        "grid_owner": 0,
        "operational_status": 0,
        "line_type": 0,
        "transformer_breaker_numbering_convention": 0,
    }
    # Row counts are unchanged, not doubled.
    assert db_session.query(VoltageLevel).count() == len(VOLTAGE_LEVELS)
    assert db_session.query(Region).count() == len(REGIONS)
    assert db_session.query(GmZone).count() == len(GM_ZONES)
    assert db_session.query(State).count() == len(STATES)
    assert db_session.query(GridOwner).count() == len(GRID_OWNERS)
    assert db_session.query(OperationalStatus).count() == len(OPERATIONAL_STATUSES)
    assert db_session.query(LineType).count() == len(LINE_TYPES)
    assert db_session.query(TransformerBreakerNumberingConvention).count() == len(
        TRANSFORMER_BREAKER_NUMBERING_CONVENTIONS
    )


def test_seeded_voltage_levels_match_substation_registry_md(db_session: Session) -> None:
    run_seed(db_session)

    labels = {vl.label for vl in db_session.query(VoltageLevel).all()}
    # 33kV/22kV/11kV added by Phase 3.5 (Transformer Registry) — LV-side
    # distribution voltage classes needed by the transformer short-name
    # convention (132/33kV, 132/11kV, etc.).
    assert labels == {"500kV", "275kV", "230kV", "132kV", "33kV", "22kV", "11kV"}


def test_seeded_line_types_match_equipment_registry_module_md(db_session: Session) -> None:
    run_seed(db_session)

    labels = {lt.label for lt in db_session.query(LineType).all()}
    assert labels == {"Overhead Line", "Cable", "Submarine", "Hybrid"}


def test_seeded_gm_zones_match_the_project_owners_documented_list(db_session: Session) -> None:
    run_seed(db_session)

    labels = {z.label for z in db_session.query(GmZone).all()}
    assert labels == {
        "Alor Setar",
        "Butterworth",
        "Ipoh",
        "Selangor",
        "Kuala Lumpur",
        "Seremban",
        "Ayer Keroh",
        "Kluang",
        "Johor Bahru",
        "Kuantan",
        "Dungun",
        "Kota Bharu",
    }
    # The Project Owner's authoritative engineering GM Zone codes
    # (migration 0023_gm_zone_engineering_codes remaps the original
    # descriptive codes to these one-for-one by label; labels are
    # unchanged). Pinning the exact code -> label mapping here — not just
    # the label set — is what makes GridDefence's reference data a stable
    # contract the Legacy Migration Workbench can resolve GM Zones against
    # by engineering code; a future regression that reverts any code is
    # caught by this assertion.
    code_by_label = {z.label: z.code for z in db_session.query(GmZone).all()}
    assert code_by_label == {
        "Johor Bahru": "JOH1",
        "Kluang": "JOH2",
        "Alor Setar": "KEDP",
        "Kota Bharu": "KELN",
        "Kuala Lumpur": "KLUM",
        "Ayer Keroh": "MLKA",
        "Seremban": "NSEM",
        "Ipoh": "PERK",
        "Kuantan": "PHNG",
        "Butterworth": "PPNG",
        "Selangor": "SELG",
        "Dungun": "TERG",
    }
    # GM Zone codes are independent of, and never derived from, region
    # codes — no `region_id`/`region_code` column exists on `gm_zone` at
    # all (Region and GM Zone "must remain separate").
    assert "region_id" not in {c.name for c in GmZone.__table__.columns}


def test_seeded_transformer_breaker_numbering_conventions_match_the_tnb_convention(
    db_session: Session,
) -> None:
    run_seed(db_session)

    voltage_level_id_by_label = {
        vl.label: vl.voltage_level_id for vl in db_session.query(VoltageLevel).all()
    }
    rows = db_session.query(TransformerBreakerNumberingConvention).all()
    patterns_by_pair_side = {
        (row.hv_voltage_level_id, row.lv_voltage_level_id, row.side): (row.pattern, row.is_standard)
        for row in rows
    }

    def pair(hv_label: str, lv_label: str, side: str) -> tuple[str | None, bool]:
        return patterns_by_pair_side[
            (voltage_level_id_by_label[hv_label], voltage_level_id_by_label[lv_label], side)
        ]

    assert pair("500kV", "275kV", "HV") == (None, False)
    assert pair("500kV", "275kV", "LV") == ("T{N}0", True)
    assert pair("275kV", "132kV", "HV") == ("H{N}0", True)
    assert pair("275kV", "132kV", "LV") == ("{N}80", True)
    assert pair("132kV", "33kV", "HV") == ("{N}10", True)
    assert pair("132kV", "33kV", "LV") == ("{N}T0", True)
    assert pair("132kV", "22kV", "HV") == ("{N}10", True)
    assert pair("132kV", "22kV", "LV") == ("{N}T0", True)
    assert pair("132kV", "11kV", "HV") == ("{N}10", True)
    assert pair("132kV", "11kV", "LV") == ("3{N}", True)


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
        "gm_zone": 0,
        "state": 0,
        "grid_owner": 0,
        "operational_status": 0,
        "line_type": len(LINE_TYPES),
        "transformer_breaker_numbering_convention": 0,
    }
    assert db_session.query(LineType).count() == len(LINE_TYPES)


def test_seed_backfills_gm_zones(db_session: Session) -> None:
    """Same backfill guarantee as `line_type` above, for the newest
    reference table: a database seeded before this table existed must have
    it fully populated by a later re-run, with every other table untouched."""
    run_seed(db_session)
    db_session.query(GmZone).delete()
    db_session.commit()
    assert db_session.query(GmZone).count() == 0

    counts = run_seed(db_session)

    assert counts == {
        "voltage_level": 0,
        "region": 0,
        "gm_zone": len(GM_ZONES),
        "state": 0,
        "grid_owner": 0,
        "operational_status": 0,
        "line_type": 0,
        "transformer_breaker_numbering_convention": 0,
    }
    assert db_session.query(GmZone).count() == len(GM_ZONES)
    assert db_session.query(Region).count() == len(REGIONS)


def test_seed_backfills_transformer_breaker_numbering_conventions(db_session: Session) -> None:
    """Same backfill guarantee as `line_type` above, for the newest
    reference table: a database seeded before this table existed must have
    it fully populated by a later re-run, with every other table untouched."""
    run_seed(db_session)
    db_session.query(TransformerBreakerNumberingConvention).delete()
    db_session.commit()
    assert db_session.query(TransformerBreakerNumberingConvention).count() == 0

    counts = run_seed(db_session)

    assert counts == {
        "voltage_level": 0,
        "region": 0,
        "gm_zone": 0,
        "state": 0,
        "grid_owner": 0,
        "operational_status": 0,
        "line_type": 0,
        "transformer_breaker_numbering_convention": len(TRANSFORMER_BREAKER_NUMBERING_CONVENTIONS),
    }
    assert db_session.query(TransformerBreakerNumberingConvention).count() == len(
        TRANSFORMER_BREAKER_NUMBERING_CONVENTIONS
    )
    assert db_session.query(VoltageLevel).count() == len(VOLTAGE_LEVELS)
