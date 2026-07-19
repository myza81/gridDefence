"""Idempotent seed data for Core Platform reference tables.

Per docs/architecture/implementation-plan.md §6 and
docs/architecture/substation-registry.md §6.

Source values:
- voltage_level: the four voltage classes named in substation-registry.md
  §6 (500/275/230/132 kV).
- region: the illustrative region groupings named in substation-registry.md
  §6 ("e.g. Northern, Central, Southern, Eastern"), matching the legacy
  MVP's North/Central/South/East grouping (Codebase Discovery Report).
- gm_zone: the twelve Grid Maintenance Zones named explicitly by the
  Project Owner for the Substation Registry GM Zone enhancement — purely
  organizational (maintenance responsibility), independent of `region`.
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

logger = logging.getLogger(__name__)

VOLTAGE_LEVELS: list[dict[str, object]] = [
    {"label": "500kV", "nominal_kv": 500, "sort_order": 1},
    {"label": "275kV", "nominal_kv": 275, "sort_order": 2},
    {"label": "230kV", "nominal_kv": 230, "sort_order": 3},
    {"label": "132kV", "nominal_kv": 132, "sort_order": 4},
    # Added by Phase 3.5 (Transformer Registry) — the LV-side distribution
    # voltage classes named explicitly in the transformer short-name/breaker
    # convention (132/33kV, 132/11kV, etc.); no substation or circuit in
    # this project has needed one until a transformer's LV side did.
    {"label": "33kV", "nominal_kv": 33, "sort_order": 5},
    {"label": "22kV", "nominal_kv": 22, "sort_order": 6},
    {"label": "11kV", "nominal_kv": 11, "sort_order": 7},
]

REGIONS: list[dict[str, str]] = [
    {"code": "NORTH", "label": "Northern"},
    {"code": "CENTRAL", "label": "Central"},
    {"code": "SOUTH", "label": "Southern"},
    {"code": "EAST", "label": "Eastern"},
]

# Added by the Substation Registry GM Zone enhancement (Project Owner-
# approved) — Grid Maintenance Zone, the organizational maintenance zone
# responsible for a substation. Independent of `region` (a grid-planning
# grouping); a `Region` typically contains several GM Zones (the
# illustrative mapping the Project Owner supplied: Northern -> Alor Setar/
# Butterworth/Ipoh, Central -> Selangor/Kuala Lumpur, Southern -> Seremban/
# Ayer Keroh/Kluang/Johor Bahru, East Coast -> Kuantan/Dungun/Kota Bharu).
# That Region grouping is not enforced by any FK or constraint — GM Zone
# and Region remain two independently-assigned attributes on Substation,
# per the Project Owner's explicit instruction that they "must remain
# separate."
#
# Codes below are the Project Owner's authoritative GM Zone engineering
# codes (GM Zone Options refinement, superseding this table's original
# descriptive `code` values below one-for-one by `label` — migration
# 0023_gm_zone_engineering_codes remaps every pre-existing `gm_zone` row
# in place, so `gm_zone_id` and every `substation.gm_zone_id` FK reference
# are unaffected).
GM_ZONES: list[dict[str, str]] = [
    {"code": "JOH1", "label": "Johor Bahru"},
    {"code": "JOH2", "label": "Kluang"},
    {"code": "KEDP", "label": "Alor Setar"},
    {"code": "KELN", "label": "Kota Bharu"},
    {"code": "KLUM", "label": "Kuala Lumpur"},
    {"code": "MLKA", "label": "Ayer Keroh"},
    {"code": "NSEM", "label": "Seremban"},
    {"code": "PERK", "label": "Ipoh"},
    {"code": "PHNG", "label": "Kuantan"},
    {"code": "PPNG", "label": "Butterworth"},
    {"code": "SELG", "label": "Selangor"},
    {"code": "TERG", "label": "Dungun"},
]

# Assumption (see module docstring) — the 11 Peninsular Malaysia states plus
# the two Federal Territories located within Peninsular Malaysia, plus the two
# neighbouring interconnected systems (Thailand, Singapore) added as ordinary
# State options so records at the northern/southern grid boundaries may
# reference them. These remain flat State reference rows — no Country/Nation
# hierarchy is introduced (they are added by migration
# 0027_thailand_singapore_states for already-deployed databases; this list
# keeps a fresh-database seed and the idempotent baseline in sync).
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
    {"code": "THA", "label": "Thailand"},
    {"code": "SGP", "label": "Singapore"},
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
    # Added by the Equipment Registry deletion/correction policy (Phase 3
    # follow-up) — represents a mistakenly-created record, not a real piece
    # of equipment reaching genuine end-of-life (that remains
    # DECOMMISSIONED/RETIRED, unaffected). Used by SubstationVoltageYard,
    # CircuitTerminal, Circuit, and Transformer as the correction mechanism
    # replacing hard delete (CLAUDE.md §11.6).
    {"code": "ENTERED_IN_ERROR", "label": "Entered in Error", "is_terminal": True},
]

# Added by Phase 3 (Equipment Registry) — the four construction types named
# explicitly in docs/architecture/equipment-registry-module.md §7.4, §7.6.
LINE_TYPES: list[dict[str, str]] = [
    {"code": "OVERHEAD", "label": "Overhead Line"},
    {"code": "CABLE", "label": "Cable"},
    {"code": "SUBMARINE", "label": "Submarine"},
    {"code": "HYBRID", "label": "Hybrid"},
]

# Added by the Transformer Registry breaker-numbering-convention-as-
# reference-data correction — the TNB convention previously hardcoded in
# frontend/src/modules/equipment_registry/transformerBreakerSuggestion.ts
# (equipment-registry-module.md Transformer Registry Business Rule 7).
# `hv_label`/`lv_label` are resolved to `voltage_level_id` at seed time, not
# stored directly — this table's own FK columns are the persisted form.
# `pattern=None` (500kV HV side) means no automatic suggestion exists;
# `{N}` is replaced with the transformer/bay number by the frontend.
TRANSFORMER_BREAKER_NUMBERING_CONVENTIONS: list[dict[str, object]] = [
    {
        "hv_label": "500kV",
        "lv_label": "275kV",
        "side": "HV",
        "pattern": None,
        "is_standard": False,
        "notes": "Non-standard — no automatic suggestion for the 500kV side.",
    },
    {
        "hv_label": "500kV",
        "lv_label": "275kV",
        "side": "LV",
        "pattern": "T{N}0",
        "is_standard": True,
        "notes": None,
    },
    {
        "hv_label": "275kV",
        "lv_label": "132kV",
        "side": "HV",
        "pattern": "H{N}0",
        "is_standard": True,
        "notes": None,
    },
    {
        "hv_label": "275kV",
        "lv_label": "132kV",
        "side": "LV",
        "pattern": "{N}80",
        "is_standard": True,
        "notes": None,
    },
    {
        "hv_label": "132kV",
        "lv_label": "33kV",
        "side": "HV",
        "pattern": "{N}10",
        "is_standard": True,
        "notes": None,
    },
    {
        "hv_label": "132kV",
        "lv_label": "33kV",
        "side": "LV",
        "pattern": "{N}T0",
        "is_standard": True,
        "notes": None,
    },
    {
        "hv_label": "132kV",
        "lv_label": "22kV",
        "side": "HV",
        "pattern": "{N}10",
        "is_standard": True,
        "notes": None,
    },
    {
        "hv_label": "132kV",
        "lv_label": "22kV",
        "side": "LV",
        "pattern": "{N}T0",
        "is_standard": True,
        "notes": None,
    },
    {
        "hv_label": "132kV",
        "lv_label": "11kV",
        "side": "HV",
        "pattern": "{N}10",
        "is_standard": True,
        "notes": None,
    },
    {
        "hv_label": "132kV",
        "lv_label": "11kV",
        "side": "LV",
        "pattern": "3{N}",
        "is_standard": True,
        "notes": None,
    },
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


def _seed_gm_zones(db: Session) -> int:
    existing = {z.code for z in db.query(GmZone).all()}
    created = 0
    for row in GM_ZONES:
        if row["code"] in existing:
            continue
        db.add(GmZone(**row))
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


def _seed_line_types(db: Session) -> int:
    existing = {lt.code for lt in db.query(LineType).all()}
    created = 0
    for row in LINE_TYPES:
        if row["code"] in existing:
            continue
        db.add(LineType(**row))
        created += 1
    return created


def _seed_transformer_breaker_numbering_conventions(db: Session) -> int:
    """Depends on `voltage_level` already being seeded and flushed —
    `run_seed` below calls `db.flush()` after `_seed_voltage_levels` and
    before this function specifically so a same-call, first-ever seed run
    can resolve `hv_label`/`lv_label` to real ids (this project's session is
    `autoflush=False`, app/db/session.py, so this cannot be left implicit)."""
    voltage_level_id_by_label = {
        vl.label: vl.voltage_level_id for vl in db.query(VoltageLevel).all()
    }
    existing = {
        (c.hv_voltage_level_id, c.lv_voltage_level_id, c.side)
        for c in db.query(TransformerBreakerNumberingConvention).all()
    }
    created = 0
    for row in TRANSFORMER_BREAKER_NUMBERING_CONVENTIONS:
        hv_voltage_level_id = voltage_level_id_by_label[row["hv_label"]]
        lv_voltage_level_id = voltage_level_id_by_label[row["lv_label"]]
        key = (hv_voltage_level_id, lv_voltage_level_id, row["side"])
        if key in existing:
            continue
        db.add(
            TransformerBreakerNumberingConvention(
                hv_voltage_level_id=hv_voltage_level_id,
                lv_voltage_level_id=lv_voltage_level_id,
                side=row["side"],
                pattern=row["pattern"],
                is_standard=row["is_standard"],
                notes=row["notes"],
            )
        )
        created += 1
    return created


def run_seed(db: Session) -> dict[str, int]:
    """Idempotently seed every Core Platform reference table. Safe to call
    on every startup/deploy — rows already present (matched by their unique
    `code`/`label`, or `(hv_voltage_level_id, lv_voltage_level_id, side)` for
    the transformer breaker-numbering convention) are left untouched, never
    duplicated or overwritten.
    """
    voltage_level_count = _seed_voltage_levels(db)
    # `SessionLocal` is configured with `autoflush=False` (app/db/session.py)
    # — unlike every other seed function here,
    # `_seed_transformer_breaker_numbering_conventions` below depends on
    # `voltage_level` rows added by the call just above being visible to its
    # own `db.query(VoltageLevel)` lookup. An explicit flush (not a commit —
    # the whole seed run stays one transaction) makes them visible without
    # relying on autoflush, which this project's session deliberately
    # disables.
    db.flush()
    counts = {
        "voltage_level": voltage_level_count,
        "region": _seed_regions(db),
        "gm_zone": _seed_gm_zones(db),
        "state": _seed_states(db),
        "grid_owner": _seed_grid_owners(db),
        "operational_status": _seed_operational_statuses(db),
        "line_type": _seed_line_types(db),
        "transformer_breaker_numbering_convention": _seed_transformer_breaker_numbering_conventions(
            db
        ),
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
