"""Idempotent seed data for Core Platform reference tables.

Per docs/architecture/implementation-plan.md §6 and
docs/architecture/substation-registry.md §6.

Source values:
- voltage_level: the four voltage classes named in substation-registry.md
  §6 (500/275/230/132 kV).
- region: the illustrative region groupings named in substation-registry.md
  §6 ("e.g. Northern, Central, Southern, Eastern"), matching the legacy
  MVP's North/Central/South/East grouping (Codebase Discovery Report).
- grid_owner: the six ownership classes named explicitly in
  implementation-plan.md §6 ("TNB/DC/LSS/IPP/LPC/Tie-Line").
- operational_status: the six lifecycle states named in substation-registry.md
  §6 and its lifecycle diagram (§10-equivalent) — Planned, Under
  Construction, Active, Mothballed, Decommissioned, Retired.
- state: substation-registry.md §6 describes this only as "the 11
  Peninsular Malaysia states + Federal Territories" with no exact
  enumerated list anywhere in the architecture documents. The 13 rows below
  (11 states + 2 Federal Territories relevant to Peninsular Malaysia) are
  this script's own reasonable, low-stakes assumption, not an architectural
  decision — see Phase 1's final report ("Assumptions Made").

NOTE — a documented, out-of-scope-for-this-script inconsistency: this
module intentionally does NOT create a `grid` reference table (e.g. KEDP,
PPNG, ...) even though implementation-plan.md §6's prose mentions "the
MVP's grid codes." substation-registry.md's canonical schema (the
authoritative source per this phase's required reading) defines no `grid`
table — only region/state/grid_owner/voltage_level/operational_status,
exactly matching this file's scope. See Phase 1's final report
("Architectural issues encountered") for the full explanation.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.reference_data.models import GridOwner, OperationalStatus, Region, State, VoltageLevel

logger = logging.getLogger(__name__)

VOLTAGE_LEVELS: list[dict[str, object]] = [
    {"label": "500kV", "nominal_kv": 500, "sort_order": 1},
    {"label": "275kV", "nominal_kv": 275, "sort_order": 2},
    {"label": "230kV", "nominal_kv": 230, "sort_order": 3},
    {"label": "132kV", "nominal_kv": 132, "sort_order": 4},
]

REGIONS: list[dict[str, str]] = [
    {"code": "NORTH", "label": "Northern"},
    {"code": "CENTRAL", "label": "Central"},
    {"code": "SOUTH", "label": "Southern"},
    {"code": "EAST", "label": "Eastern"},
]

# Assumption (see module docstring) — the 11 Peninsular Malaysia states plus
# the two Federal Territories located within Peninsular Malaysia.
STATES: list[dict[str, str]] = [
    {"code": "JHR", "label": "Johor"},
    {"code": "KDH", "label": "Kedah"},
    {"code": "KTN", "label": "Kelantan"},
    {"code": "MLK", "label": "Melaka"},
    {"code": "NSN", "label": "Negeri Sembilan"},
    {"code": "PHG", "label": "Pahang"},
    {"code": "PRK", "label": "Perak"},
    {"code": "PLS", "label": "Perlis"},
    {"code": "PNG", "label": "Pulau Pinang"},
    {"code": "SEL", "label": "Selangor"},
    {"code": "TRG", "label": "Terengganu"},
    {"code": "KUL", "label": "W.P. Kuala Lumpur"},
    {"code": "PJY", "label": "W.P. Putrajaya"},
]

GRID_OWNERS: list[dict[str, str]] = [
    {"code": "TNB", "label": "Tenaga Nasional Berhad (TNB)"},
    {"code": "DC", "label": "Data Centre (DC)"},
    {"code": "LSS", "label": "Large Scale Solar (LSS)"},
    {"code": "IPP", "label": "Independent Power Producer (IPP)"},
    {"code": "LPC", "label": "Large Power Consumer (LPC)"},
    {"code": "TIE_LINE", "label": "Tie-Line"},
]

OPERATIONAL_STATUSES: list[dict[str, object]] = [
    {"code": "PLANNED", "label": "Planned", "is_terminal": False},
    {"code": "UNDER_CONSTRUCTION", "label": "Under Construction", "is_terminal": False},
    {"code": "ACTIVE", "label": "Active", "is_terminal": False},
    {"code": "MOTHBALLED", "label": "Mothballed", "is_terminal": False},
    {"code": "DECOMMISSIONED", "label": "Decommissioned", "is_terminal": True},
    {"code": "RETIRED", "label": "Retired", "is_terminal": True},
]


def _seed_voltage_levels(db: Session) -> int:
    existing = {vl.label for vl in db.query(VoltageLevel).all()}
    created = 0
    for row in VOLTAGE_LEVELS:
        if row["label"] in existing:
            continue
        db.add(VoltageLevel(**row))
        created += 1
    return created


def _seed_regions(db: Session) -> int:
    existing = {r.code for r in db.query(Region).all()}
    created = 0
    for row in REGIONS:
        if row["code"] in existing:
            continue
        db.add(Region(**row))
        created += 1
    return created


def _seed_states(db: Session) -> int:
    existing = {s.code for s in db.query(State).all()}
    created = 0
    for row in STATES:
        if row["code"] in existing:
            continue
        db.add(State(**row))
        created += 1
    return created


def _seed_grid_owners(db: Session) -> int:
    existing = {g.code for g in db.query(GridOwner).all()}
    created = 0
    for row in GRID_OWNERS:
        if row["code"] in existing:
            continue
        db.add(GridOwner(**row))
        created += 1
    return created


def _seed_operational_statuses(db: Session) -> int:
    existing = {o.code for o in db.query(OperationalStatus).all()}
    created = 0
    for row in OPERATIONAL_STATUSES:
        if row["code"] in existing:
            continue
        db.add(OperationalStatus(**row))
        created += 1
    return created


def run_seed(db: Session) -> dict[str, int]:
    """Idempotently seed every Core Platform reference table. Safe to call
    on every startup/deploy — rows already present (matched by their unique
    `code`/`label`) are left untouched, never duplicated or overwritten.
    """
    counts = {
        "voltage_level": _seed_voltage_levels(db),
        "region": _seed_regions(db),
        "state": _seed_states(db),
        "grid_owner": _seed_grid_owners(db),
        "operational_status": _seed_operational_statuses(db),
    }
    db.commit()
    logger.info("Reference data seed complete: %s", counts)
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
