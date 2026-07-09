"""Tests for Load-only Snapshot Synchronisation validation
(load_sync_validation.py; Phase 7B; EDR-007 Engineering Principle 12). A
pure function — no database, no ORM — so these tests exercise
`validate_load_only_synchronization` directly against synthetic fixtures,
per this phase's own testing guidance."""

from __future__ import annotations

from app.modules.psse_integration.load_sync_validation import (
    ActiveTopologyBusRef,
    validate_load_only_synchronization,
)

_ACTIVE_BUSES = [
    ActiveTopologyBusRef(bus_number=100, bus_name="ABBA132", base_kv=132.0),
    ActiveTopologyBusRef(bus_number=200, bus_name="BLPS132L", base_kv=132.0),
    ActiveTopologyBusRef(bus_number=300, bus_name="SDAOFIC", base_kv=33.0),
]


def test_all_load_buses_matching_active_topology() -> None:
    result = validate_load_only_synchronization(
        load_bus_numbers=[100, 200, 300],
        active_topology_buses=_ACTIVE_BUSES,
    )
    assert result.total_load_records == 3
    assert result.total_distinct_load_buses == 3
    assert result.matched_load_buses == 3
    assert result.unmatched_load_bus_numbers == []
    assert result.missing_topology_bus_numbers == []
    assert result.identity_mismatches == []


def test_load_bus_missing_from_active_topology_is_flagged() -> None:
    result = validate_load_only_synchronization(
        load_bus_numbers=[100, 999],
        active_topology_buses=_ACTIVE_BUSES,
    )
    assert result.matched_load_buses == 1
    assert result.unmatched_load_bus_numbers == [999]


def test_load_records_at_the_same_bus_count_once_toward_distinct_buses() -> None:
    result = validate_load_only_synchronization(
        load_bus_numbers=[100, 100, 200],
        active_topology_buses=_ACTIVE_BUSES,
    )
    assert result.total_load_records == 3
    assert result.total_distinct_load_buses == 2
    assert result.matched_load_buses == 2


def test_active_topology_bus_missing_from_load_only_raw_is_flagged() -> None:
    """Requirement 2 — a bus that previously had load (per the topology's
    own previously Current LoadSnapshot) but is absent from this new
    load-only file's own loads."""
    result = validate_load_only_synchronization(
        load_bus_numbers=[100],
        active_topology_buses=_ACTIVE_BUSES,
        previously_loaded_bus_numbers={100, 200, 300},
    )
    assert result.missing_topology_bus_numbers == [200, 300]


def test_no_previous_load_snapshot_means_nothing_is_reported_missing() -> None:
    result = validate_load_only_synchronization(
        load_bus_numbers=[100],
        active_topology_buses=_ACTIVE_BUSES,
        previously_loaded_bus_numbers=None,
    )
    assert result.missing_topology_bus_numbers == []


def test_bus_number_matching_but_bus_name_mismatch_is_flagged() -> None:
    """Requirement 3 — Bus Number exists on both sides, but the incoming
    file's own Bus Name differs from the active topology's."""
    incoming = [ActiveTopologyBusRef(bus_number=100, bus_name="DIFFERENT_NAME", base_kv=132.0)]
    result = validate_load_only_synchronization(
        load_bus_numbers=[100],
        active_topology_buses=_ACTIVE_BUSES,
        incoming_bus_references=incoming,
    )
    assert len(result.identity_mismatches) == 1
    mismatch = result.identity_mismatches[0]
    assert mismatch.bus_number == 100
    assert mismatch.active_bus_name == "ABBA132"
    assert mismatch.incoming_bus_name == "DIFFERENT_NAME"
    assert mismatch.mismatch_reason == "bus_name"


def test_bus_number_matching_but_voltage_mismatch_is_flagged() -> None:
    """Requirement 3 — Bus Number exists on both sides, but the incoming
    file's own nominal voltage differs from the active topology's."""
    incoming = [ActiveTopologyBusRef(bus_number=100, bus_name="ABBA132", base_kv=110.0)]
    result = validate_load_only_synchronization(
        load_bus_numbers=[100],
        active_topology_buses=_ACTIVE_BUSES,
        incoming_bus_references=incoming,
    )
    assert len(result.identity_mismatches) == 1
    mismatch = result.identity_mismatches[0]
    assert mismatch.active_base_kv == 132.0
    assert mismatch.incoming_base_kv == 110.0
    assert mismatch.mismatch_reason == "base_kv"


def test_bus_name_and_voltage_both_mismatched_is_flagged_once_with_combined_reason() -> None:
    incoming = [ActiveTopologyBusRef(bus_number=100, bus_name="DIFFERENT_NAME", base_kv=110.0)]
    result = validate_load_only_synchronization(
        load_bus_numbers=[100],
        active_topology_buses=_ACTIVE_BUSES,
        incoming_bus_references=incoming,
    )
    assert len(result.identity_mismatches) == 1
    assert result.identity_mismatches[0].mismatch_reason == "bus_name,base_kv"


def test_identical_incoming_bus_reference_is_not_flagged() -> None:
    incoming = [ActiveTopologyBusRef(bus_number=100, bus_name="ABBA132", base_kv=132.0)]
    result = validate_load_only_synchronization(
        load_bus_numbers=[100],
        active_topology_buses=_ACTIVE_BUSES,
        incoming_bus_references=incoming,
    )
    assert result.identity_mismatches == []


def test_bus_name_comparison_is_case_and_whitespace_insensitive() -> None:
    incoming = [ActiveTopologyBusRef(bus_number=100, bus_name="  abba132  ", base_kv=132.0)]
    result = validate_load_only_synchronization(
        load_bus_numbers=[100],
        active_topology_buses=_ACTIVE_BUSES,
        incoming_bus_references=incoming,
    )
    assert result.identity_mismatches == []


def test_no_incoming_bus_references_means_no_identity_mismatch_is_possible() -> None:
    """A genuine load-only RAW (the only real-file shape observed by this
    project — raw_parser.py's module docstring) carries zero BUS DATA
    records, so it can never itself supply identity data to compare —
    this is expected, not a defect."""
    result = validate_load_only_synchronization(
        load_bus_numbers=[100, 200, 300],
        active_topology_buses=_ACTIVE_BUSES,
        incoming_bus_references=[],
    )
    assert result.identity_mismatches == []


def test_incoming_bus_reference_for_a_bus_not_in_the_active_topology_is_ignored() -> None:
    """Identity mismatch is only meaningful for a Bus Number the active
    topology already knows — an incoming reference to an unrelated bus
    number is not itself a mismatch (it may simply be an unrelated bus the
    file happens to also mention)."""
    incoming = [ActiveTopologyBusRef(bus_number=999, bus_name="UNRELATED", base_kv=33.0)]
    result = validate_load_only_synchronization(
        load_bus_numbers=[100],
        active_topology_buses=_ACTIVE_BUSES,
        incoming_bus_references=incoming,
    )
    assert result.identity_mismatches == []
