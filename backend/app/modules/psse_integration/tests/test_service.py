"""Tests for PsseIntegrationService's business rules — preview zero-
persistence, commit (topology reuse vs. new), activation atomicity/
lifecycle, EquipmentTopologyMap matching (incl. ENTERED_IN_ERROR exclusion),
and discrepancy resolution.

Uses small, hand-constructed RAW content strings (not the large real sample
files — those are exercised by test_raw_parser.py) so each test's fixture
data is easy to read and reason about.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.psse_integration.exceptions import (
    BatchNotActivatableError,
    DiscrepancyAlreadyResolvedError,
    NoCurrentTopologyVersionError,
    NotFoundError,
)
from app.modules.psse_integration.models import TopologyVersion
from app.modules.psse_integration.service import (
    PsseIntegrationService,
    _aggregate_findings,
    _categorize_parser_warning,
)
from app.modules.psse_integration.tests.conftest import CircuitFixture, ReferenceIds

# One bus (PKLG132) matches the `substation_ids`/`voltage_yard_ids` fixture's
# real PKLG substation; the other (UNKN132) matches nothing registered —
# deliberately, to exercise the "unmatched_bus" finding category (§8.9d).
_ONE_MATCHED_ONE_UNMATCHED_BUS_RAW = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.02,0.0
200,'UNKN132',132.0,1,1,1,1,1.01,-1.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'1',0.001,0.01,0.0002
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""

_FULL_TOPOLOGY_RAW = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.02,0.0
200,'IGBK132',132.0,1,1,1,1,1.01,-1.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'1',0.001,0.01,0.0002
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""

# Same topology as _FULL_TOPOLOGY_RAW, plus two generators — for the
# generator-count defect fix (§8.9d UAT finding): NetworkGenerator rows
# were always persisted correctly; only their summary count was wrong.
_FULL_TOPOLOGY_WITH_GENERATORS_RAW = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.02,0.0
200,'IGBK132',132.0,1,1,1,1,1.01,-1.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
100,'1',50.0,10.0
200,'1',30.0,5.0
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'1',0.001,0.01,0.0002
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""

# A structurally different case (extra bus + branch) — a distinct signature
# from _FULL_TOPOLOGY_RAW, for supersession tests.
_FULL_TOPOLOGY_RAW_V2 = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.02,0.0
200,'IGBK132',132.0,1,1,1,1,1.01,-1.0
300,'NKST132',132.0,1,1,1,1,1.00,-2.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'1',0.001,0.01,0.0002
200,300,'1',0.002,0.02,0.0003
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""

_LOAD_ONLY_RAW = """0 / END OF SYSTEM-WIDE DATA, BEGIN LOAD DATA
100,'1',1,1,1,15.0,7.0
200,'1',1,1,1,20.0,10.0
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
Q
"""


@pytest.fixture()
def service(db_session: Session) -> PsseIntegrationService:
    return PsseIntegrationService(db_session)


# --- Preview (zero persistence) -----------------------------------------------------


def test_preview_full_topology_is_zero_persistence(
    db_session: Session, service: PsseIntegrationService
) -> None:
    result = service.preview(_FULL_TOPOLOGY_RAW, "case1.raw")
    assert result.import_type == "FULL_TOPOLOGY_WITH_LOAD"
    assert result.topology_reused is False
    assert db_session.query(TopologyVersion).count() == 0


def test_preview_reports_network_size_read_from_the_already_parsed_case(
    service: PsseIntegrationService,
) -> None:
    """Phase 6 engineering presentation refinement (§8.9b) — network-size
    fields are read directly off the parsed case, never recomputed."""
    result = service.preview(_FULL_TOPOLOGY_RAW, "case1.raw")
    assert result.raw_version == 34
    assert result.bus_count == 2
    assert result.branch_count == 1
    assert result.transformer_count == 0
    assert result.load_count == 0
    assert result.generator_count == 0


def test_preview_full_topology_carries_parsed_records_for_inspector(
    service: PsseIntegrationService,
) -> None:
    """Operational Context Inspector (§8.9e) — the Inspector presents the
    same parsed records Preview already produced; this asserts they pass
    through unchanged (no re-parsing, no transformation, no invented
    fields)."""
    result = service.preview(_FULL_TOPOLOGY_RAW, "case1.raw")
    assert result.source_file_reference == "case1.raw"
    assert result.base_mva == 100.0
    assert len(result.buses) == 2
    assert result.buses[0].bus_number == 100
    assert result.buses[0].bus_name == "PKLG132"
    assert len(result.branches) == 1
    assert result.branches[0].from_bus == 100
    assert result.branches[0].to_bus == 200
    assert result.transformers == []
    assert result.loads == []
    assert result.generators == []


def test_preview_full_topology_with_generators_carries_parsed_generator_records(
    service: PsseIntegrationService,
) -> None:
    result = service.preview(_FULL_TOPOLOGY_WITH_GENERATORS_RAW, "case2.raw")
    assert len(result.generators) == 2
    assert result.generators[0].bus_number == 100
    assert result.generators[0].p_gen == 50.0


def test_preview_load_only_without_current_topology_reports_unmatched(
    service: PsseIntegrationService,
) -> None:
    result = service.preview(_LOAD_ONLY_RAW, "loads1.raw")
    assert result.import_type == "LOAD_ONLY"
    assert result.unmatched_bus_count == 2
    assert any("No Current TopologyVersion" in w for w in result.warnings)


def test_preview_load_only_network_size_has_no_topology_fields_and_no_raw_version(
    service: PsseIntegrationService,
) -> None:
    """A load-only file asserts no structural data (§8.7) and often has no
    header line at all — `raw_version` is best-effort and may be `None`."""
    result = service.preview(_LOAD_ONLY_RAW, "loads1.raw")
    assert result.raw_version is None
    assert result.bus_count == 0
    assert result.branch_count == 0
    assert result.transformer_count == 0
    assert result.load_count == 2
    assert result.generator_count == 0


def test_preview_load_only_carries_parsed_load_records_and_no_base_mva(
    service: PsseIntegrationService,
) -> None:
    """A load-only file's header is often absent (§8.7) — `base_mva` is
    best-effort and may be `None`, same as `raw_version`."""
    result = service.preview(_LOAD_ONLY_RAW, "loads1.raw")
    assert result.base_mva is None
    assert result.source_file_reference == "loads1.raw"
    assert len(result.loads) == 2
    assert result.loads[0].bus_number == 100
    assert result.loads[0].p_mw == 15.0
    assert result.buses == []


def test_preview_reports_topology_reuse_after_a_real_commit(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()

    result = service.preview(_FULL_TOPOLOGY_RAW, "case1-again.raw")
    assert result.topology_reused is True


# --- Commit: new vs. reused topology -------------------------------------------------


def test_commit_full_topology_creates_new_topology_version_and_load_snapshot(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    voltage_yard_ids: dict[str, uuid.UUID],
) -> None:
    # `voltage_yard_ids` (via `substation_ids`) provisions real PKLG/IGBK
    # substations so both parsed buses match cleanly — otherwise every bus
    # would warn "did not match any substation" and the batch would land
    # on CompletedWithWarnings instead, which is not what this test is
    # about (that path is covered separately).
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()

    assert batch.status == "Completed"
    assert batch.import_type == "FULL_TOPOLOGY_WITH_LOAD"
    topology = service.repo.get_topology_version_by_id(batch.topology_version_id)
    assert topology is not None
    assert topology.status == "Imported"
    snapshot = service.repo.get_load_snapshot_by_id(batch.load_snapshot_id)
    assert snapshot is not None
    assert snapshot.status == "Imported"
    assert len(service.repo.list_topology_buses(topology.topology_version_id)) == 2
    assert len(service.repo.list_topology_branches(topology.topology_version_id)) == 1


# --- Generator count defect fix (Phase 6 UAT) -------------------------------------


def test_counts_for_load_snapshot_reports_the_actual_generator_count(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    voltage_yard_ids: dict[str, uuid.UUID],
) -> None:
    """Root cause: `counts_for_load_snapshot` returned a hardcoded `0` for
    generators regardless of how many were actually persisted. Verified
    here against a snapshot that genuinely has two `NetworkGenerator` rows."""
    batch = service.commit(_FULL_TOPOLOGY_WITH_GENERATORS_RAW, "case-gen.raw", actor_user_id)
    db_session.commit()

    assert len(service.repo.list_network_generators(batch.load_snapshot_id)) == 2

    load_count, generator_count = service.counts_for_load_snapshot(batch.load_snapshot_id)
    assert generator_count == 2
    assert load_count == 0  # this fixture has no LOAD DATA records, only generators


def test_counts_for_load_snapshot_reports_zero_when_there_are_no_generators(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    voltage_yard_ids: dict[str, uuid.UUID],
) -> None:
    """Regression guard: a snapshot with genuinely zero generators must
    still correctly report `0`, not merely by coincidence of the old bug."""
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()

    assert service.repo.list_network_generators(batch.load_snapshot_id) == []
    _load_count, generator_count = service.counts_for_load_snapshot(batch.load_snapshot_id)
    assert generator_count == 0


def test_get_load_snapshot_summary_reports_the_correct_generator_count(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    voltage_yard_ids: dict[str, uuid.UUID],
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_WITH_GENERATORS_RAW, "case-gen.raw", actor_user_id)
    db_session.commit()

    summary = service.get_load_snapshot_summary(batch.load_snapshot_id)
    assert summary.generator_count == 2


def test_get_current_status_summary_reports_the_correct_generator_count(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    voltage_yard_ids: dict[str, uuid.UUID],
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_WITH_GENERATORS_RAW, "case-gen.raw", actor_user_id)
    db_session.commit()
    service.activate(batch.batch_id, change_reason="Go live", actor_user_id=actor_user_id)
    db_session.commit()

    status = service.get_current_status_summary()
    assert status.current_load_snapshot is not None
    assert status.current_load_snapshot.generator_count == 2


# --- Engineering findings aggregation and Registry Matching (§8.9d) ---------------


def test_commit_full_topology_registry_matching_is_100_percent_when_everything_matches(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    voltage_yard_ids: dict[str, uuid.UUID],
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()

    summary = service.get_batch_summary(batch.batch_id)
    assert summary.matched_count == 2
    assert summary.unmatched_count == 0
    assert summary.coverage_percent == 100.0
    assert summary.finding_groups == []


def test_commit_full_topology_tags_and_aggregates_an_unmatched_bus_finding(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    voltage_yard_ids: dict[str, uuid.UUID],
) -> None:
    batch = service.commit(_ONE_MATCHED_ONE_UNMATCHED_BUS_RAW, "case2.raw", actor_user_id)
    db_session.commit()

    assert batch.status == "CompletedWithWarnings"

    summary = service.get_batch_summary(batch.batch_id)
    assert summary.matched_count == 1
    assert summary.unmatched_count == 1
    assert summary.coverage_percent == 50.0

    assert len(summary.finding_groups) == 1
    group = summary.finding_groups[0]
    assert group.category == "unmatched_bus"
    assert group.group == "engineering_review_required"
    assert group.count == 1
    assert "1 bus could not be matched" in group.summary
    assert group.details == ["Bus 200 did not match any substation."]


def test_list_batch_summaries_does_not_compute_registry_matching_counts(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    voltage_yard_ids: dict[str, uuid.UUID],
) -> None:
    """No extra per-row query for the list view (CLAUDE.md §21) — only a
    single batch's own detail view computes matched/unmatched/coverage."""
    service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()

    summaries, _total = service.list_batch_summaries(page=1, page_size=10)
    assert len(summaries) == 1
    assert summaries[0].matched_count is None
    assert summaries[0].unmatched_count is None
    assert summaries[0].coverage_percent is None
    # finding_groups is cheap (grouping already-loaded warnings) and is
    # still populated for list rows.
    assert summaries[0].finding_groups == []


def test_aggregate_findings_groups_many_individual_messages_into_one_summary() -> None:
    """The scenario this refinement exists for: hundreds/thousands of
    individual per-occurrence messages collapse into one categorized,
    counted group — never rendered as a flat list of that size."""
    warnings = [
        {"category": "unmatched_bus", "message": f"Bus {n} did not match any substation."}
        for n in range(1087)
    ]

    groups = _aggregate_findings(warnings)

    assert len(groups) == 1
    assert groups[0].category == "unmatched_bus"
    assert groups[0].count == 1087
    assert groups[0].summary == (
        "1087 buses could not be matched to the current Substation Registry."
    )
    assert len(groups[0].details) == 1087


def test_aggregate_findings_summarizes_unrecognized_sections_as_parser_notices() -> None:
    warnings = [
        {
            "category": _categorize_parser_warning(message),
            "message": message,
        }
        for message in [
            "Section 'OWNER DATA' is not recognized by this parser — its data (if any) "
            "was skipped.",
            "Section 'SWITCHED SHUNT DATA' is not recognized by this parser — its data "
            "(if any) was skipped.",
        ]
    ]

    groups = _aggregate_findings(warnings)

    assert len(groups) == 1
    assert groups[0].category == "unrecognized_section"
    assert groups[0].group == "parser_notices"
    assert groups[0].count == 2
    assert "2 unsupported RAW sections were detected" in groups[0].summary
    assert "currently not required by GridDefence and were safely ignored" in groups[0].summary


def test_aggregate_findings_falls_back_gracefully_for_warnings_with_no_category() -> None:
    """A batch committed before this refinement stored warnings as plain
    `{"message": ...}` dicts, with no `"category"` key at all — must still
    aggregate without raising, never lose the message itself."""
    warnings = [{"message": "Bus 999 did not match any substation."}]

    groups = _aggregate_findings(warnings)

    assert len(groups) == 1
    assert groups[0].details == ["Bus 999 did not match any substation."]


def test_committing_identical_content_twice_reuses_the_same_topology_version(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    batch1 = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()
    batch2 = service.commit(_FULL_TOPOLOGY_RAW, "case1-resubmit.raw", actor_user_id)
    db_session.commit()

    assert batch1.topology_version_id == batch2.topology_version_id
    assert db_session.query(TopologyVersion).count() == 1
    # A second, independent LoadSnapshot is still created against the
    # reused TopologyVersion.
    assert batch1.load_snapshot_id != batch2.load_snapshot_id


def test_committing_structurally_different_content_creates_a_second_topology_version(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    batch1 = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()
    batch2 = service.commit(_FULL_TOPOLOGY_RAW_V2, "case2.raw", actor_user_id)
    db_session.commit()

    assert batch1.topology_version_id != batch2.topology_version_id
    assert db_session.query(TopologyVersion).count() == 2


def test_commit_load_only_without_current_topology_raises(
    service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    with pytest.raises(NoCurrentTopologyVersionError):
        service.commit(_LOAD_ONLY_RAW, "loads1.raw", actor_user_id)


def test_commit_load_only_against_current_topology_creates_snapshot_only(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    full_batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()
    service.activate(full_batch.batch_id, change_reason="initial", actor_user_id=actor_user_id)
    db_session.commit()

    topology_count_before = db_session.query(TopologyVersion).count()
    load_batch = service.commit(_LOAD_ONLY_RAW, "loads1.raw", actor_user_id)
    db_session.commit()

    assert load_batch.import_type == "LOAD_ONLY"
    assert load_batch.topology_version_id == full_batch.topology_version_id
    assert db_session.query(TopologyVersion).count() == topology_count_before  # no new topology
    snapshot = service.repo.get_load_snapshot_by_id(load_batch.load_snapshot_id)
    assert snapshot is not None
    loads = service.repo.list_network_loads(load_batch.load_snapshot_id)
    assert len(loads) == 2


# --- Activate: atomicity and lifecycle ------------------------------------------------


def test_activate_promotes_topology_and_snapshot_to_current(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()

    service.activate(batch.batch_id, change_reason="go live", actor_user_id=actor_user_id)
    db_session.commit()

    topology = service.repo.get_topology_version_by_id(batch.topology_version_id)
    snapshot = service.repo.get_load_snapshot_by_id(batch.load_snapshot_id)
    assert topology.status == "Current"
    assert topology.promoted_at is not None
    assert snapshot.status == "Current"
    assert snapshot.promoted_at is not None


def test_activating_a_second_topology_supersedes_the_first(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    batch1 = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()
    service.activate(batch1.batch_id, change_reason="v1 live", actor_user_id=actor_user_id)
    db_session.commit()

    batch2 = service.commit(_FULL_TOPOLOGY_RAW_V2, "case2.raw", actor_user_id)
    db_session.commit()
    service.activate(batch2.batch_id, change_reason="v2 live", actor_user_id=actor_user_id)
    db_session.commit()

    topology1 = service.repo.get_topology_version_by_id(batch1.topology_version_id)
    topology2 = service.repo.get_topology_version_by_id(batch2.topology_version_id)
    assert topology1.status == "Superseded"
    assert topology1.superseded_at is not None
    assert topology2.status == "Current"

    current = service.repo.get_current_topology_version()
    assert current.topology_version_id == topology2.topology_version_id


def test_activate_rejects_a_batch_that_is_not_completed(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    batch.status = "Parsing"  # simulate an in-progress/failed batch
    db_session.commit()

    with pytest.raises(BatchNotActivatableError):
        service.activate(batch.batch_id, change_reason="too soon", actor_user_id=actor_user_id)


def test_activate_unknown_batch_raises_not_found(
    service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    with pytest.raises(NotFoundError):
        service.activate(uuid.uuid4(), change_reason="x", actor_user_id=actor_user_id)


# --- EquipmentTopologyMap matching -----------------------------------------------------


def test_commit_computes_clean_match_for_a_real_matching_circuit(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    pklg_igbk_circuit: CircuitFixture,
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()

    entries, total = service.list_map_entries(
        topology_version_id=batch.topology_version_id, page=1, page_size=50
    )
    assert total == 2  # one row per circuit terminal
    outcomes = {e.match_outcome for e in entries}
    assert outcomes == {"clean_match"}
    terminal_ids = {e.circuit_terminal_id for e in entries}
    assert terminal_ids == set(pklg_igbk_circuit.terminal_ids.values())


def test_entered_in_error_terminal_is_excluded_from_matching(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    pklg_igbk_circuit: CircuitFixture,
    reference_ids: ReferenceIds,
) -> None:
    from app.modules.equipment_registry.service import EquipmentRegistryService

    equipment_service = EquipmentRegistryService(db_session)
    entered_in_error_id = reference_ids.status_id_by_code["ENTERED_IN_ERROR"]
    equipment_service.update_terminal(
        pklg_igbk_circuit.circuit_id,
        pklg_igbk_circuit.terminal_ids["PKLG"],
        operational_status_id=entered_in_error_id,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()

    entries, total = service.list_map_entries(
        topology_version_id=batch.topology_version_id, page=1, page_size=50
    )
    # The excluded PKLG terminal gets no map entry at all. IGBK's terminal
    # is still a matching candidate itself, but its only counterpart
    # (PKLG) is now excluded, so it has zero candidate elements left and
    # resolves to "unmatched" rather than "clean_match".
    assert total == 1
    assert entries[0].circuit_terminal_id == pklg_igbk_circuit.terminal_ids["IGBK"]
    assert entries[0].match_outcome == "unmatched"


def test_resolve_discrepancy_records_decision_and_rejects_second_resolution(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    pklg_igbk_circuit: CircuitFixture,
) -> None:
    # A branch with a mismatched ckt_id produces a discrepancy, not a clean match.
    mismatched_raw = _FULL_TOPOLOGY_RAW.replace("100,200,'1'", "100,200,'9'")
    batch = service.commit(mismatched_raw, "case-mismatch.raw", actor_user_id)
    db_session.commit()

    entries, _ = service.list_map_entries(
        topology_version_id=batch.topology_version_id, page=1, page_size=50
    )
    assert all(e.match_outcome == "discrepancy" for e in entries)

    entry = entries[0]
    resolved = service.resolve_discrepancy(
        entry.map_id,
        resolution="accepted",
        change_reason="confirmed real network change",
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    assert resolved.discrepancy_resolution == "accepted"

    with pytest.raises(DiscrepancyAlreadyResolvedError):
        service.resolve_discrepancy(
            entry.map_id,
            resolution="rejected",
            change_reason="second attempt",
            actor_user_id=actor_user_id,
        )


def test_circuit_correlation_is_fully_resolved_when_all_terminals_clean_match(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    pklg_igbk_circuit: CircuitFixture,
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()

    correlation = service.get_circuit_correlation(
        pklg_igbk_circuit.circuit_id, batch.topology_version_id
    )
    assert correlation.fully_resolved is True
    assert len(correlation.terminals) == 2
