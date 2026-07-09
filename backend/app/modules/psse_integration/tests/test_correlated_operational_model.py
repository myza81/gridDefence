"""Tests for Correlated Operational Model's pure correlation-status logic
(correlated_operational_model.py; Phase 7C). No database, no ORM — these
exercise `bus_correlation_status`/`equipment_correlation_status` directly."""

from __future__ import annotations

import uuid

from app.modules.psse_integration.correlated_operational_model import (
    bus_correlation_status,
    equipment_correlation_status,
)

_SOME_SUBSTATION_ID = uuid.uuid4()


def test_bus_correlated_when_substation_matched() -> None:
    assert bus_correlation_status("SWITCHYARD_BUS", _SOME_SUBSTATION_ID) == "CORRELATED"
    assert bus_correlation_status("SPLIT_SWITCHYARD_BUS", _SOME_SUBSTATION_ID) == "CORRELATED"


def test_bus_unmatched_operational_when_no_substation_matched() -> None:
    assert bus_correlation_status("SWITCHYARD_BUS", None) == "UNMATCHED_OPERATIONAL"
    assert bus_correlation_status("OTHER_NON_CONFORMING_BUS", None) == "UNMATCHED_OPERATIONAL"
    assert bus_correlation_status("BLANK_NAMED_BUS", None) == "UNMATCHED_OPERATIONAL"


def test_fictitious_bus_is_outside_current_scope_regardless_of_substation_match() -> None:
    """EDR-007 §4.6/§4.7, Engineering Principle 6 — GridDefence should not
    attempt to correlate Fictitious Buses at all; this is a scope
    boundary, not a failed match."""
    assert bus_correlation_status("FICTITIOUS_BUS", None) == "OUTSIDE_CURRENT_SCOPE"
    assert bus_correlation_status("FICTITIOUS_BUS", _SOME_SUBSTATION_ID) == "OUTSIDE_CURRENT_SCOPE"


def test_other_non_conforming_and_blank_named_bus_are_not_special_cased() -> None:
    """No EDR-007 conclusion carves these out the way it does for
    Fictitious Bus — evaluated exactly like any other bus."""
    assert bus_correlation_status("OTHER_NON_CONFORMING_BUS", _SOME_SUBSTATION_ID) == "CORRELATED"
    assert bus_correlation_status("BLANK_NAMED_BUS", _SOME_SUBSTATION_ID) == "CORRELATED"


def test_equipment_unmatched_operational_when_no_map_entry_references_the_element() -> None:
    assert (
        equipment_correlation_status(None, has_single_candidate=False, discrepancy_resolution=None)
        == "UNMATCHED_OPERATIONAL"
    )


def test_equipment_correlated_on_clean_match() -> None:
    assert (
        equipment_correlation_status(
            "clean_match", has_single_candidate=True, discrepancy_resolution=None
        )
        == "CORRELATED"
    )


def test_equipment_unmatched_registry_when_terminal_has_no_operational_counterpart() -> None:
    assert (
        equipment_correlation_status(
            "unmatched", has_single_candidate=False, discrepancy_resolution=None
        )
        == "UNMATCHED_REGISTRY"
    )


def test_equipment_ambiguous_when_discrepancy_has_multiple_candidates_and_unresolved() -> None:
    assert (
        equipment_correlation_status(
            "discrepancy", has_single_candidate=False, discrepancy_resolution=None
        )
        == "AMBIGUOUS"
    )


def test_equipment_engineering_review_required_when_discrepancy_has_single_candidate() -> None:
    assert (
        equipment_correlation_status(
            "discrepancy", has_single_candidate=True, discrepancy_resolution=None
        )
        == "ENGINEERING_REVIEW_REQUIRED"
    )


def test_equipment_correlated_when_discrepancy_accepted() -> None:
    assert (
        equipment_correlation_status(
            "discrepancy", has_single_candidate=True, discrepancy_resolution="accepted"
        )
        == "CORRELATED"
    )
    assert (
        equipment_correlation_status(
            "discrepancy", has_single_candidate=False, discrepancy_resolution="accepted"
        )
        == "CORRELATED"
    )


def test_equipment_unmatched_registry_when_discrepancy_rejected() -> None:
    assert (
        equipment_correlation_status(
            "discrepancy", has_single_candidate=True, discrepancy_resolution="rejected"
        )
        == "UNMATCHED_REGISTRY"
    )
