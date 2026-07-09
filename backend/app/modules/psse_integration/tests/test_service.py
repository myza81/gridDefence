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

from app.modules.psse_integration.correlated_operational_model import equipment_correlation_status
from app.modules.psse_integration.exceptions import (
    BatchNotActivatableError,
    DiscrepancyAlreadyResolvedError,
    NoCurrentTopologyVersionError,
    NotFoundError,
)
from app.modules.psse_integration.models import TopologyBus, TopologyVersion
from app.modules.psse_integration.raw_parser import ParsedBus, ParsedCase, ParsedLoad
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

# Same PKLG<->IGBK bus pair as _FULL_TOPOLOGY_RAW, but with TWO branches between
# them, neither ckt_id ('2'/'3') matching `pklg_igbk_circuit`'s own bay_number
# ('1') — matching.py's own "two or more candidates, none match by ckt_id" branch
# (genuinely ambiguous; Phase 7D UAT follow-up, Finding 2).
_AMBIGUOUS_BRANCH_RAW = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.02,0.0
200,'IGBK132',132.0,1,1,1,1,1.01,-1.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'2',0.001,0.01,0.0002
100,200,'3',0.002,0.02,0.0003
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
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


def test_preview_reports_header_metadata_read_from_the_already_parsed_case(
    service: PsseIntegrationService,
) -> None:
    """Phase 7 discovery-support enhancement (§8.9f) — RAW File Information
    is read directly off the parsed case, never recomputed or re-parsed.
    This fixture's header has no case-identification title lines or writer
    comment, so `case_description`/`raw_created` are gracefully `None`."""
    result = service.preview(_FULL_TOPOLOGY_RAW, "case1.raw")
    assert result.frequency_hz == 50.0
    assert result.case_description is None
    assert result.raw_created is None


def test_preview_reports_case_description_and_raw_created_when_present(
    service: PsseIntegrationService,
) -> None:
    content = (
        "0,100.0,34,0,1,50.0     / PSS(R)E 34 RAW created by rawd34  WED, FEB 11 2026  14:43\n"
        "OPERATION STUDY\n"
        "CPF_03 JAN 2025\n"
        "0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA\n"
        "100,'PKLG132',132.0,1,1,1,1,1.02,0.0\n"
        "0 / END OF BUS DATA, BEGIN LOAD DATA\n"
        "0 / END OF LOAD DATA, BEGIN GENERATOR DATA\n"
        "0 / END OF GENERATOR DATA, BEGIN BRANCH DATA\n"
        "0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA\n"
        "0 / END OF TRANSFORMER DATA, BEGIN AREA DATA\nQ\n"
    )
    result = service.preview(content, "case2.raw")
    assert result.case_description == "CPF_03 JAN 2025"
    assert result.raw_created == "WED, FEB 11 2026 14:43"


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


def test_preview_load_only_has_no_header_metadata(
    service: PsseIntegrationService,
) -> None:
    """A load-only file's header is often absent entirely (§8.7) — RAW
    File Information fields are gracefully `None`, same as `raw_version`
    (Phase 7 discovery-support enhancement, §8.9f)."""
    result = service.preview(_LOAD_ONLY_RAW, "loads1.raw")
    assert result.frequency_hz is None
    assert result.case_description is None
    assert result.raw_created is None


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
    # `_LOAD_ONLY_RAW` uses the abbreviated 7-field LOAD DATA shape, which
    # has no OWNER field at all (Phase 7A, EDR-007 §7.3) — persisted as
    # `None`, never a parse or commit failure.
    assert all(load.owner is None for load in loads)


# --- Load Owner persistence (Phase 7A, EDR-007 §7.3) ----------------------------------

_FULL_TOPOLOGY_WITH_LOAD_OWNER_RAW = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.02,0.0
200,'IGBK132',132.0,1,1,1,1,1.01,-1.0
0 / END OF BUS DATA, BEGIN LOAD DATA
100,'1',1,1,1,15.0,7.0,0.0,0.0,0.0,0.0,99,1,0,0.0,0.0,0
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'1',0.001,0.01,0.0002
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""


def test_commit_full_topology_persists_load_owner(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    voltage_yard_ids: dict[str, uuid.UUID],
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_WITH_LOAD_OWNER_RAW, "case-owner.raw", actor_user_id)
    db_session.commit()

    loads = service.repo.list_network_loads(batch.load_snapshot_id)
    assert len(loads) == 1
    assert loads[0].owner == 99


# --- Load-only Snapshot Synchronisation validation (Phase 7B) -------------------------
# EDR-007 Engineering Principle 12 — Bus Number is the sole correlation key. Uses
# `_FULL_TOPOLOGY_RAW` (buses 100 'PKLG132'/200 'IGBK132', both 132.0 kV) as the active
# topology throughout.

_LOAD_ONLY_RAW_BUS_100_ONLY = """0 / END OF SYSTEM-WIDE DATA, BEGIN LOAD DATA
100,'1',1,1,1,15.0,7.0
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
Q
"""

_MALFORMED_RAW = ""


def _activate_full_topology(
    service: PsseIntegrationService, db_session: Session, actor_user_id: uuid.UUID
):
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()
    service.activate(batch.batch_id, change_reason="initial", actor_user_id=actor_user_id)
    db_session.commit()
    return batch


def test_preview_load_only_sync_validation_all_buses_matching(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    _activate_full_topology(service, db_session, actor_user_id)

    result = service.preview(_LOAD_ONLY_RAW, "loads1.raw")

    assert result.sync_validation is not None
    assert result.sync_validation.total_load_records == 2
    assert result.sync_validation.total_distinct_load_buses == 2
    assert result.sync_validation.matched_load_buses == 2
    assert result.sync_validation.unmatched_load_buses == 0
    assert result.sync_validation.missing_topology_buses == 0
    assert result.sync_validation.identity_mismatch_buses == 0


def test_preview_load_only_sync_validation_none_without_current_topology(
    service: PsseIntegrationService,
) -> None:
    result = service.preview(_LOAD_ONLY_RAW, "loads1.raw")
    assert result.sync_validation is None


def test_preview_load_only_sync_validation_flags_missing_topology_bus(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    """Requirement 2 — a topology bus that previously had load (in the
    topology's own previously Current LoadSnapshot) but is absent from
    this new load-only file."""
    _activate_full_topology(service, db_session, actor_user_id)
    load_batch = service.commit(_LOAD_ONLY_RAW, "loads1.raw", actor_user_id)
    db_session.commit()
    service.activate(load_batch.batch_id, change_reason="loads", actor_user_id=actor_user_id)
    db_session.commit()

    result = service.preview(_LOAD_ONLY_RAW_BUS_100_ONLY, "loads2.raw")

    assert result.sync_validation is not None
    assert result.sync_validation.missing_topology_buses == 1
    assert result.sync_validation.missing_topology_bus_numbers == [200]


def test_commit_load_only_flags_missing_topology_bus_as_finding(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    _activate_full_topology(service, db_session, actor_user_id)
    load_batch = service.commit(_LOAD_ONLY_RAW, "loads1.raw", actor_user_id)
    db_session.commit()
    service.activate(load_batch.batch_id, change_reason="loads", actor_user_id=actor_user_id)
    db_session.commit()

    batch2 = service.commit(_LOAD_ONLY_RAW_BUS_100_ONLY, "loads2.raw", actor_user_id)
    db_session.commit()

    entries = [w for w in batch2.warnings if w["category"] == "missing_topology_load_bus"]
    assert len(entries) == 1
    assert "200" in entries[0]["message"]

    summary = service.get_batch_summary(batch2.batch_id)
    group = next(g for g in summary.finding_groups if g.category == "missing_topology_load_bus")
    assert group.count == 1


def test_validate_load_only_sync_detects_bus_name_mismatch(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    """Requirement 3 — Bus Number matches, but Bus Name differs. A genuine
    load-only RAW (the only real-file shape this project has observed —
    raw_parser.py's module docstring) carries zero BUS DATA records, so it
    can never itself supply a Bus Name to compare; `parse_raw`'s own
    `is_full_topology` detection would in fact route any file with
    non-empty BUS DATA to the FULL_TOPOLOGY_WITH_LOAD path, not this one.
    This test therefore exercises the service's own `_validate_load_only_sync`
    helper directly, with a hand-built `ParsedCase` carrying a bus
    reference — the same pattern the pure `load_sync_validation` module's
    own unit tests use, per this phase's explicit synthetic-fixture
    guidance."""
    _activate_full_topology(service, db_session, actor_user_id)
    current_topology = service.repo.get_current_topology_version()
    assert current_topology is not None

    case = ParsedCase(
        buses=[
            ParsedBus(
                bus_number=100,
                bus_name="RENAMED_BUS",
                base_kv=132.0,
                ide=1,
                area=1,
                zone=1,
                owner=1,
            )
        ],
        loads=[ParsedLoad(bus_number=100, load_id="1", status=True, p_mw=15.0, q_mvar=7.0)],
    )

    result = service._validate_load_only_sync(case, current_topology)

    assert len(result.identity_mismatches) == 1
    mismatch = result.identity_mismatches[0]
    assert mismatch.bus_number == 100
    assert mismatch.active_bus_name == "PKLG132"
    assert mismatch.incoming_bus_name == "RENAMED_BUS"
    assert mismatch.mismatch_reason == "bus_name"


def test_validate_load_only_sync_detects_voltage_mismatch(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    """Requirement 3 — Bus Number matches, but nominal voltage differs."""
    _activate_full_topology(service, db_session, actor_user_id)
    current_topology = service.repo.get_current_topology_version()
    assert current_topology is not None

    case = ParsedCase(
        buses=[
            ParsedBus(
                bus_number=100, bus_name="PKLG132", base_kv=110.0, ide=1, area=1, zone=1, owner=1
            )
        ],
        loads=[ParsedLoad(bus_number=100, load_id="1", status=True, p_mw=15.0, q_mvar=7.0)],
    )

    result = service._validate_load_only_sync(case, current_topology)

    assert len(result.identity_mismatches) == 1
    assert result.identity_mismatches[0].mismatch_reason == "base_kv"


def test_commit_load_only_does_not_modify_active_topology(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    """Core Rule — a load-only RAW file must not redefine Operational
    Topology (operational-snapshot-architecture.md §9 Topology
    Independence)."""
    full_batch = _activate_full_topology(service, db_session, actor_user_id)
    before = {
        bus.bus_number: (bus.bus_name, bus.base_kv)
        for bus in db_session.query(TopologyBus)
        .filter(TopologyBus.topology_version_id == full_batch.topology_version_id)
        .all()
    }

    service.commit(_LOAD_ONLY_RAW, "loads1.raw", actor_user_id)
    db_session.commit()

    after = {
        bus.bus_number: (bus.bus_name, bus.base_kv)
        for bus in db_session.query(TopologyBus)
        .filter(TopologyBus.topology_version_id == full_batch.topology_version_id)
        .all()
    }
    assert before == after
    assert db_session.query(TopologyVersion).count() == 1


def test_commit_parse_error_is_distinct_from_sync_validation_and_raised_before_it(
    service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    """Parser failures (fatal, RawFileParseError) must remain distinct from
    engineering correlation/synchronisation issues (non-fatal, routed to
    review as warnings) — psse-integration-module.md §8.9d."""
    from app.modules.psse_integration.exceptions import RawFileParseError

    with pytest.raises(RawFileParseError):
        service.commit(_MALFORMED_RAW, "empty.raw", actor_user_id)


def test_commit_full_topology_import_still_works_unaffected_by_sync_validation(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    """Regression guard — a full RAW import never touches Load-only
    Snapshot Synchronisation validation at all; `sync_validation` is a
    LOAD_ONLY-only concept."""
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()
    assert batch.import_type == "FULL_TOPOLOGY_WITH_LOAD"
    assert batch.status in ("Completed", "CompletedWithWarnings")

    preview = service.preview(_FULL_TOPOLOGY_RAW, "case1.raw")
    assert preview.sync_validation is None


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


# --- Correlated Operational Model (Phase 7C) ------------------------------------------
# `_FULL_TOPOLOGY_RAW`: buses 100 'PKLG132'/200 'IGBK132', both 132.0 kV, ide=1
# (in-service). `pklg_igbk_circuit`/`voltage_yard_ids`/`substation_ids` register real
# PKLG/IGBK Substation Registry + Equipment Registry data. Not every Correlation
# Status value is exercised end-to-end through the full commit/DB pipeline here
# (e.g. AMBIGUOUS needs a genuinely multi-candidate tee-off scenario) — those are
# already covered directly against the pure function in
# test_correlated_operational_model.py, per this phase's own "use synthetic
# fixtures where easier" guidance; this section exercises what is realistically
# reachable end-to-end.


def test_get_operational_bus_views_correlated_with_substation_and_switchyard(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    substation_ids: dict[str, uuid.UUID],
) -> None:
    from app.modules.equipment_registry.service import EquipmentRegistryService
    from app.reference_data.models import VoltageLevel

    voltage_level_132kv = db_session.query(VoltageLevel).filter_by(label="132kV").one()
    EquipmentRegistryService(db_session).create_voltage_yard(
        substation_id=substation_ids["PKLG"],
        voltage_level_id=voltage_level_132kv.voltage_level_id,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()
    service.activate(batch.batch_id, change_reason="initial", actor_user_id=actor_user_id)
    db_session.commit()

    views, total = service.get_operational_bus_views(
        batch.topology_version_id, page=1, page_size=50
    )
    assert total == 2
    pklg_view = next(v for v in views if v.bus_number == 100)
    assert pklg_view.bus_name == "PKLG132"
    assert pklg_view.bus_classification == "SWITCHYARD_BUS"
    assert pklg_view.correlation_status == "CORRELATED"
    assert pklg_view.substation_id == substation_ids["PKLG"]
    assert pklg_view.substation_mnemonic == "PKLG"
    assert pklg_view.voltage_yard_id is not None
    assert pklg_view.in_service is True


def test_get_operational_bus_view_unmatched_operational_when_no_substation_registered(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    substation_ids: dict[str, uuid.UUID],
) -> None:
    """`_ONE_MATCHED_ONE_UNMATCHED_BUS_RAW`'s bus 200 ('UNKN132') has no
    registered "UNKN" substation, even with `substation_ids` seeding
    PKLG/IGBK/NKST."""
    batch = service.commit(_ONE_MATCHED_ONE_UNMATCHED_BUS_RAW, "case1.raw", actor_user_id)
    db_session.commit()

    view = service.get_operational_bus_view(batch.topology_version_id, 200)
    assert view.correlation_status == "UNMATCHED_OPERATIONAL"
    assert view.substation_id is None
    assert view.substation_mnemonic is None


def test_get_operational_bus_view_outside_current_scope_for_fictitious_bus(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    fictitious_raw = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'SDAOFIC',33.0,1,1,1,1,1.0,0.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""
    batch = service.commit(fictitious_raw, "case-fic.raw", actor_user_id)
    db_session.commit()

    view = service.get_operational_bus_view(batch.topology_version_id, 100)
    assert view.bus_classification == "FICTITIOUS_BUS"
    assert view.correlation_status == "OUTSIDE_CURRENT_SCOPE"


def test_get_operational_bus_view_in_service_false_for_isolated_bus(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    isolated_bus_raw = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,4,1,1,1,1.0,0.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""
    batch = service.commit(isolated_bus_raw, "case-isolated.raw", actor_user_id)
    db_session.commit()
    service.activate(batch.batch_id, change_reason="initial", actor_user_id=actor_user_id)
    db_session.commit()

    view = service.get_operational_bus_view(batch.topology_version_id, 100)
    assert view.in_service is False


def test_get_operational_bus_view_raises_for_unknown_bus_number(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()
    with pytest.raises(NotFoundError):
        service.get_operational_bus_view(batch.topology_version_id, 999)


def test_get_operational_bus_views_raises_for_unknown_topology_version(
    service: PsseIntegrationService,
) -> None:
    with pytest.raises(NotFoundError):
        service.get_operational_bus_views(uuid.uuid4(), page=1, page_size=50)


def test_get_operational_branch_views_correlated_on_clean_match(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    pklg_igbk_circuit: CircuitFixture,
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()
    service.activate(batch.batch_id, change_reason="initial", actor_user_id=actor_user_id)
    db_session.commit()

    views, total = service.get_operational_branch_views(
        batch.topology_version_id, page=1, page_size=50
    )
    assert total == 1
    view = views[0]
    assert view.from_bus_number == 100
    assert view.to_bus_number == 200
    assert view.correlation_status == "CORRELATED"
    assert view.circuit_id == pklg_igbk_circuit.circuit_id
    assert view.circuit_bay_number == "1"
    assert view.in_service is True


def test_get_operational_branch_views_engineering_review_required_on_single_candidate_discrepancy(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    pklg_igbk_circuit: CircuitFixture,
) -> None:
    """A single plausible candidate exists (PKLG<->IGBK), but its `ckt_id`
    doesn't confirm the pairing — matching.py's own `len(candidates) == 1`
    discrepancy branch — a specific pairing a human can quickly confirm."""
    mismatched_raw = _FULL_TOPOLOGY_RAW.replace("100,200,'1'", "100,200,'9'")
    batch = service.commit(mismatched_raw, "case-mismatch.raw", actor_user_id)
    db_session.commit()

    views, _ = service.get_operational_branch_views(batch.topology_version_id, page=1, page_size=50)
    assert views[0].correlation_status == "ENGINEERING_REVIEW_REQUIRED"
    assert views[0].circuit_id == pklg_igbk_circuit.circuit_id


def test_get_operational_branch_views_correlated_after_accepted_discrepancy(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    pklg_igbk_circuit: CircuitFixture,
) -> None:
    mismatched_raw = _FULL_TOPOLOGY_RAW.replace("100,200,'1'", "100,200,'9'")
    batch = service.commit(mismatched_raw, "case-mismatch.raw", actor_user_id)
    db_session.commit()
    entries, _ = service.list_map_entries(
        topology_version_id=batch.topology_version_id, page=1, page_size=50
    )
    # Both terminals of this 2-terminal circuit independently produce a
    # map entry referencing the same branch — resolve both, so the
    # branch's own "best of" status isn't masked by one still-pending
    # entry (`_element_correlation`'s own documented simplification).
    for entry in entries:
        service.resolve_discrepancy(
            entry.map_id,
            resolution="accepted",
            change_reason="confirmed",
            actor_user_id=actor_user_id,
        )
    db_session.commit()

    views, _ = service.get_operational_branch_views(batch.topology_version_id, page=1, page_size=50)
    assert views[0].correlation_status == "CORRELATED"


def test_get_operational_branch_views_unmatched_registry_after_rejected_discrepancy(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    pklg_igbk_circuit: CircuitFixture,
) -> None:
    mismatched_raw = _FULL_TOPOLOGY_RAW.replace("100,200,'1'", "100,200,'9'")
    batch = service.commit(mismatched_raw, "case-mismatch.raw", actor_user_id)
    db_session.commit()
    entries, _ = service.list_map_entries(
        topology_version_id=batch.topology_version_id, page=1, page_size=50
    )
    for entry in entries:
        service.resolve_discrepancy(
            entry.map_id,
            resolution="rejected",
            change_reason="not a real pairing",
            actor_user_id=actor_user_id,
        )
    db_session.commit()

    views, _ = service.get_operational_branch_views(batch.topology_version_id, page=1, page_size=50)
    assert views[0].correlation_status == "UNMATCHED_REGISTRY"


def test_get_operational_branch_views_unmatched_operational_when_no_map_entry(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    pklg_igbk_circuit: CircuitFixture,
) -> None:
    """`_FULL_TOPOLOGY_RAW_V2` adds bus 300 'NKST132' and branch 200-300 —
    no `CircuitTerminal` is registered at NKST (`pklg_igbk_circuit` only
    covers PKLG/IGBK), so no `EquipmentTopologyMap` entry ever references
    this second branch at all."""
    batch = service.commit(_FULL_TOPOLOGY_RAW_V2, "case-v2.raw", actor_user_id)
    db_session.commit()

    views, total = service.get_operational_branch_views(
        batch.topology_version_id, page=1, page_size=50
    )
    assert total == 2
    extra_branch = next(v for v in views if v.to_bus_number == 300)
    assert extra_branch.correlation_status == "UNMATCHED_OPERATIONAL"
    assert extra_branch.circuit_id is None
    pklg_igbk_branch = next(v for v in views if v.to_bus_number == 200)
    assert pklg_igbk_branch.correlation_status == "CORRELATED"


def test_get_operational_transformer_views_empty_when_no_transformers(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()

    views, total = service.get_operational_transformer_views(
        batch.topology_version_id, page=1, page_size=50
    )
    assert views == []
    assert total == 0


def test_get_operational_load_views_always_outside_current_scope_with_substation_context(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    substation_ids: dict[str, uuid.UUID],
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_WITH_LOAD_OWNER_RAW, "case-owner.raw", actor_user_id)
    db_session.commit()

    views, total = service.get_operational_load_views(batch.load_snapshot_id, page=1, page_size=50)
    assert total == 1
    view = views[0]
    assert view.bus_number == 100
    assert view.owner == 99
    assert view.load_category is None
    assert view.relevance_classification is None
    assert view.correlation_status == "OUTSIDE_CURRENT_SCOPE"
    assert view.substation_id == substation_ids["PKLG"]
    assert view.substation_mnemonic == "PKLG"


def test_get_operational_load_views_raises_for_unknown_load_snapshot(
    service: PsseIntegrationService,
) -> None:
    with pytest.raises(NotFoundError):
        service.get_operational_load_views(uuid.uuid4(), page=1, page_size=50)


# --- Bus Correlation Refresh (Phase 7D UAT follow-up, Finding 1) ----------------------
# `_FULL_TOPOLOGY_RAW`: buses 100 'PKLG132'/200 'IGBK132', both 132.0 kV. Deliberately
# does NOT use the `substation_ids`/`voltage_yard_ids` fixtures (which auto-register
# PKLG/IGBK immediately) — these tests control exactly when a Substation is created,
# to reproduce the UAT finding: correlation computed at commit time does not pick up
# a Substation registered afterward, until an explicit refresh is requested.


def test_refresh_bus_correlation_leaves_unmatched_bus_unchanged_before_registry_update(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()

    summary = service.refresh_bus_correlation(batch.topology_version_id, actor_user_id)
    db_session.commit()

    assert summary.buses_processed == 2
    assert summary.buses_correlated == 0
    assert summary.buses_unmatched == 2
    assert summary.buses_outside_scope == 0
    assert summary.updated_count == 0
    view = service.get_operational_bus_view(batch.topology_version_id, 100)
    assert view.correlation_status == "UNMATCHED_OPERATIONAL"


def test_refresh_bus_correlation_correlates_bus_after_substation_registered(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    reference_ids: ReferenceIds,
) -> None:
    """The full flow the UAT finding describes: commit (unmatched) -> create/correct
    Substation Registry -> refresh correlation -> bus becomes correlated."""
    from app.modules.substation_registry.service import SubstationService

    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()
    before_view = service.get_operational_bus_view(batch.topology_version_id, 100)
    assert before_view.correlation_status == "UNMATCHED_OPERATIONAL"
    before_bus_facts = (before_view.bus_number, before_view.bus_name)

    sub_service = SubstationService(db_session)
    pklg = sub_service.create_substation(
        mnemonic="PKLG",
        official_name="PKLG Substation",
        region_id=reference_ids.region_id,
        state_id=reference_ids.state_id,
        grid_owner_id=reference_ids.grid_owner_id,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        psse_bus_number=None,
        latitude=None,
        longitude=None,
        commissioned_date=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    summary = service.refresh_bus_correlation(batch.topology_version_id, actor_user_id)
    db_session.commit()

    assert summary.buses_processed == 2
    assert summary.buses_correlated == 1
    assert summary.buses_unmatched == 1
    assert summary.updated_count == 1

    after_view = service.get_operational_bus_view(batch.topology_version_id, 100)
    assert after_view.correlation_status == "CORRELATED"
    assert after_view.substation_id == pklg.substation_id
    assert after_view.substation_mnemonic == "PKLG"
    # Topology facts (RAW-derived) unchanged by the refresh.
    assert (after_view.bus_number, after_view.bus_name) == before_bus_facts
    # Registry facts unchanged by the refresh — the Substation this test itself
    # created is exactly as created, never modified by refresh_bus_correlation.
    reloaded_pklg = sub_service.get_substation(pklg.substation_id)
    assert reloaded_pklg.mnemonic == "PKLG"
    assert reloaded_pklg.official_name == "PKLG Substation"


def test_refresh_bus_correlation_does_not_modify_topology_bus_structural_fields(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()
    before = {
        b.bus_number: (b.bus_name, float(b.base_kv))
        for b in db_session.query(TopologyBus)
        .filter(TopologyBus.topology_version_id == batch.topology_version_id)
        .all()
    }

    service.refresh_bus_correlation(batch.topology_version_id, actor_user_id)
    db_session.commit()

    after = {
        b.bus_number: (b.bus_name, float(b.base_kv))
        for b in db_session.query(TopologyBus)
        .filter(TopologyBus.topology_version_id == batch.topology_version_id)
        .all()
    }
    assert before == after


def test_refresh_bus_correlation_outside_scope_count_for_fictitious_bus(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    fictitious_raw = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'SDAOFIC',33.0,1,1,1,1,1.0,0.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""
    batch = service.commit(fictitious_raw, "case-fic.raw", actor_user_id)
    db_session.commit()

    summary = service.refresh_bus_correlation(batch.topology_version_id, actor_user_id)
    db_session.commit()

    assert summary.buses_processed == 1
    assert summary.buses_outside_scope == 1
    assert summary.buses_correlated == 0
    assert summary.buses_unmatched == 0


def test_refresh_bus_correlation_is_audited(
    db_session: Session, service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    batch = service.commit(_FULL_TOPOLOGY_RAW, "case1.raw", actor_user_id)
    db_session.commit()

    service.refresh_bus_correlation(batch.topology_version_id, actor_user_id)
    db_session.commit()

    entries, total = service.repo.list_audit_log(
        "TopologyVersion", str(batch.topology_version_id), offset=0, limit=50
    )
    refresh_entries = [e for e in entries if e.event_type == "operational_correlation_refreshed"]
    assert len(refresh_entries) == 1
    assert refresh_entries[0].changed_by_user_id == actor_user_id
    assert refresh_entries[0].change_reason == (
        "Bus correlation refresh: 0 of 2 bus(es) updated "
        "(0 correlated, 2 unmatched, 0 outside current scope)"
    )


def test_refresh_bus_correlation_raises_for_unknown_topology_version(
    service: PsseIntegrationService, actor_user_id: uuid.UUID
) -> None:
    with pytest.raises(NotFoundError):
        service.refresh_bus_correlation(uuid.uuid4(), actor_user_id)


# --- AMBIGUOUS Correlation Status — end-to-end integration (Phase 7D, Finding 2) ------


def test_ambiguous_correlation_status_from_real_persisted_multi_candidate_discrepancy(
    db_session: Session,
    service: PsseIntegrationService,
    actor_user_id: uuid.UUID,
    pklg_igbk_circuit: CircuitFixture,
) -> None:
    """Genuine, persisted, multi-candidate discrepancy — not a synthetic
    call to the pure function in isolation (that already exists in
    test_correlated_operational_model.py). Commits a real RAW file with
    two real Branches between the same substation pair as a real,
    registered Circuit, neither branch's ckt_id matching the Circuit's own
    bay_number, via `PsseIntegrationService.commit()` — the same commit
    path every real import uses — then reads the result back via
    `service.list_map_entries()`, the same service method backing the
    existing `GET /topology-versions/{id}/equipment-map` API endpoint
    users already consume for reviewing correlation discrepancies."""
    batch = service.commit(_AMBIGUOUS_BRANCH_RAW, "case-ambiguous.raw", actor_user_id)
    db_session.commit()

    entries, total = service.list_map_entries(
        topology_version_id=batch.topology_version_id, page=1, page_size=50
    )
    assert total == 2  # one entry per circuit terminal (PKLG, IGBK)
    assert all(e.match_outcome == "discrepancy" for e in entries)
    # matching.py's own "two or more candidates, none match by ckt_id" branch
    # never attributes the discrepancy to one specific element (unlike the
    # single-candidate case) — both element ids are null on every entry.
    assert all(e.topology_branch_id is None for e in entries)
    assert all(e.topology_transformer_id is None for e in entries)

    for entry in entries:
        has_single_candidate = (
            entry.topology_branch_id is not None or entry.topology_transformer_id is not None
        )
        status = equipment_correlation_status(
            entry.match_outcome,
            has_single_candidate=has_single_candidate,
            discrepancy_resolution=entry.discrepancy_resolution,
        )
        assert status == "AMBIGUOUS"

    # Documented, honest limitation (not silently glossed over): because
    # neither map entry references a *specific* branch, `OperationalBranchView`
    # — which groups entries by the branch they resolved to — cannot attribute
    # AMBIGUOUS to either individual real Branch; both correctly show
    # UNMATCHED_OPERATIONAL from their own narrow perspective (no entry
    # points at them specifically). AMBIGUOUS is a Circuit-terminal-level
    # fact here, surfaced via the EquipmentTopologyMap/equipment-map API
    # path, exactly as this phase's own scope note anticipated ("if
    # ambiguity is only possible for branch/transformer EquipmentTopologyMap
    # matching, test that path").
    branch_views, _ = service.get_operational_branch_views(
        batch.topology_version_id, page=1, page_size=50
    )
    assert len(branch_views) == 2
    assert all(v.correlation_status == "UNMATCHED_OPERATIONAL" for v in branch_views)
