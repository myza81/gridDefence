"""Correlated Operational Model — pure correlation-status logic (Phase 7C).

Governing references: `operational-correlation-architecture.md` (Operational
Correlation as its own architectural layer, distinct from both Operational
Snapshot and Engineering Registry — §4 Correlation Domain, §5
Responsibilities, §8 Engineering Validation); `operational-snapshot-
architecture.md` §8 (Engineering Validation — "detecting inconsistencies,
requiring Engineering Review where identity cannot be established");
`phase-7-operational-snapshot-correlation-implementation-spec.md` §7
(Correlation Status concepts) and §10 (Correlated Operational Model).

This module holds only the pure, database-free correlation-status
computation — mirroring `bus_classification.py`/`matching.py`/
`load_sync_validation.py`'s own established style (no ORM, no I/O). The
actual read models (`OperationalBusView` etc.) are Pydantic response DTOs
defined in `schemas.py`, manually assembled by `service.py` from
already-persisted data (`TopologyBus.substation_id`, `EquipmentTopologyMap`),
exactly mirroring `_map_entry_summary`'s/`_batch_summary`'s own established
pattern for anything requiring joined data — this module supplies only the
status-decision logic those assembly methods call.

Correlated Operational Model never creates, infers, or writes Operational
Snapshot data or Engineering Registry data (operational-correlation-
architecture.md §5, §9 Separation of Ownership) — it only classifies an
already-known relationship (or its absence) into one shared vocabulary.
"""

from __future__ import annotations

from typing import Literal

from app.modules.psse_integration.bus_classification import BusClassification
from app.modules.psse_integration.matching import MatchOutcome

CorrelationStatus = Literal[
    "CORRELATED",
    "UNMATCHED_OPERATIONAL",
    "UNMATCHED_REGISTRY",
    "AMBIGUOUS",
    "OUTSIDE_CURRENT_SCOPE",
    "ENGINEERING_REVIEW_REQUIRED",
]


def bus_correlation_status(
    bus_classification: BusClassification, substation_id: object | None
) -> CorrelationStatus:
    """Operational Bus -> Substation Registry correlation status.

    EDR-007 §4.6/§4.7 and Engineering Principle 6 (§9) explicitly conclude
    that Fictitious Buses "are not engineering assets" and that
    "GridDefence should not attempt to correlate Fictitious Buses with any
    Engineering Registry object" — this is not a correlation failure to
    flag for review, it is a bus GridDefence never expected to correlate in
    the first place, hence `OUTSIDE_CURRENT_SCOPE` rather than
    `UNMATCHED_OPERATIONAL`.

    No equivalent explicit conclusion exists in EDR-007 for Blank-named or
    Other-non-conforming Bus (Phase 7A's own deterministic catch-all
    categories, added for classifier totality — not EDR-007-native
    categories), so no special-casing is invented for them here: they are
    evaluated exactly like a Switchyard/Split Switchyard Bus — correlated
    if a Substation match exists, otherwise unmatched.

    Bus-level matching (`_match_substation_for_bus`) is an exact,
    non-ambiguous lookup by construction (phase-7-implementation-spec.md
    §7) — there is no `AMBIGUOUS` outcome for a Bus.
    """
    if bus_classification == "FICTITIOUS_BUS":
        return "OUTSIDE_CURRENT_SCOPE"
    return "CORRELATED" if substation_id is not None else "UNMATCHED_OPERATIONAL"


def equipment_correlation_status(
    match_outcome: MatchOutcome | None,
    *,
    has_single_candidate: bool,
    discrepancy_resolution: str | None,
) -> CorrelationStatus:
    """Operational Branch/Transformer -> Line Connectivity Registry (Circuit/
    CircuitTerminal, via `EquipmentTopologyMap`) correlation status.

    `EquipmentTopologyMap` entries are built from the registry
    `CircuitTerminal`'s own perspective (`matching.compute_matches`), so an
    operational Branch/Transformer id that appears on no entry at all was
    never a candidate for any terminal — `match_outcome=None` here means
    exactly that: `UNMATCHED_OPERATIONAL`.

    `matching.py`'s own algorithm already distinguishes, within its
    `discrepancy` outcome, "exactly one candidate, but its `ckt_id` didn't
    confirm the pairing" (`has_single_candidate=True` — a single, specific
    pairing a human can quickly confirm) from "two or more candidates and
    none matched by `ckt_id`" (`has_single_candidate=False` — genuinely
    ambiguous, no single pairing to even present). This function gives
    those two already-distinct algorithm branches their own place in the
    shared vocabulary (`ENGINEERING_REVIEW_REQUIRED` vs. `AMBIGUOUS`) —
    it does not change `matching.py`'s own decision, only names it.

    A resolved discrepancy (`resolve_discrepancy`, psse-integration-
    module.md §8a.5) already recorded an engineer's own decision:
    "accepted" confirms the pairing (`CORRELATED`); "rejected" confirms it
    is not a valid pairing (`UNMATCHED_REGISTRY` — the registry object has
    no confirmed operational counterpart).
    """
    if match_outcome is None:
        return "UNMATCHED_OPERATIONAL"
    if match_outcome == "clean_match":
        return "CORRELATED"
    if match_outcome == "unmatched":
        return "UNMATCHED_REGISTRY"
    # discrepancy
    if discrepancy_resolution == "accepted":
        return "CORRELATED"
    if discrepancy_resolution == "rejected":
        return "UNMATCHED_REGISTRY"
    return "ENGINEERING_REVIEW_REQUIRED" if has_single_candidate else "AMBIGUOUS"
