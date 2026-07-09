"""Service-layer tests for Phase 7F's Operational Snapshot Verification
Workspace (`NetworkModelService.get_snapshot_summary`/`verify_path`) —
independent of, and never modifying, `traverse()`'s own existing behaviour
(see `test_service.py` for that regression coverage, unchanged by this
file).

Topology fixture: PKLG132(100)-IGBK132(200)-NKST132(300) chain (Branch '1',
Branch '2'), plus an inter-bus Transformer '1' from PKLG132(100) to
PKLG500(101) — one substation with two Switchyards. PKLG/IGBK/NKST/ABBA are
registered Substations (conftest's `substation_ids`); PKLG/IGBK/NKST/ABBA
each have a 500kV Switchyard (`voltage_yard_ids`) and PKLG alone additionally
has a 132kV Switchyard (`lv_voltage_yard_ids`) — so PKLG132/PKLG500 both
correlate to a registered Switchyard, while IGBK132/NKST132 correlate to a
registered Substation but *not* a registered Switchyard (no 132kV yard
registered for them) — the exact "Operational Switchyard implied, not yet
registered" gap this workspace exists to surface.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.network_model.exceptions import (
    SubstationNotFoundError,
    VoltageYardNotFoundError,
    VoltageYardSubstationMismatchError,
)
from app.modules.network_model.schemas import PathVerificationRequest
from app.modules.network_model.service import NetworkModelService
from app.modules.psse_integration.service import PsseIntegrationService

_TRANSFORMER_CROSSING_RAW = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.0,0.0
101,'PKLG500',500.0,1,1,1,1,1.0,0.0
200,'IGBK132',132.0,1,1,1,1,1.0,0.0
300,'NKST132',132.0,1,1,1,1,1.0,0.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'1',0.001,0.01,0.0002
200,300,'2',0.001,0.01,0.0002
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
100,101,0,'1',1,1,1,0.0,0.0,2,'',1
0.0,0.05,100.0
1.0,132.0,0.0,150.0,150.0,150.0,0,1,1.0,1.0
1.0,500.0
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""


@pytest.fixture()
def transformer_crossing_topology_version_id(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> uuid.UUID:
    service = PsseIntegrationService(db_session)
    batch = service.commit(
        _TRANSFORMER_CROSSING_RAW, "verification-workspace-test.raw", actor_user_id
    )
    db_session.commit()
    service.activate(batch.batch_id, change_reason="test baseline", actor_user_id=actor_user_id)
    db_session.commit()
    return batch.topology_version_id


def _service(db_session: Session) -> NetworkModelService:
    return NetworkModelService(db_session)


# --- Snapshot Summary --------------------------------------------------------------


def test_snapshot_summary_reports_current_topology_and_load_snapshot(
    db_session: Session,
    transformer_crossing_topology_version_id: uuid.UUID,
) -> None:
    summary = _service(db_session).get_snapshot_summary()
    assert summary.topology_version_id == transformer_crossing_topology_version_id
    assert summary.topology_version_status == "Current"
    assert summary.bus_count == 4
    assert summary.branch_count == 2
    assert summary.transformer_count == 1
    assert summary.import_date is not None


def test_snapshot_summary_with_no_current_topology_is_all_none_not_an_error(
    db_session: Session,
) -> None:
    summary = _service(db_session).get_snapshot_summary()
    assert summary.topology_version_id is None
    assert summary.bus_count == 0


# --- Path verification --------------------------------------------------------------


def test_path_verification_walks_the_full_chain(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    transformer_crossing_topology_version_id: uuid.UUID,
) -> None:
    result = _service(db_session).verify_path(
        PathVerificationRequest(start_substation_id=substation_ids["PKLG"])
    )
    reached_bus_numbers = {b.bus.bus_number for b in result.buses}
    assert reached_bus_numbers == {100, 101, 200, 300}

    depth_by_bus = {b.bus.bus_number: b.depth for b in result.buses}
    # PKLG132(100) and PKLG500(101) both correlate to PKLG — both seed at
    # depth 0 simultaneously (a multi-voltage Substation's own Buses are
    # collectively "itself," the same multi-source seeding `traverse()`
    # already establishes) — the Transformer connecting them is never
    # walked as a path step under whole-Substation seeding for exactly
    # this reason; see `test_path_step_crosses_inter_bus_transformer` for
    # the Switchyard-scoped case where it is.
    assert depth_by_bus[100] == 0
    assert depth_by_bus[101] == 0
    assert depth_by_bus[200] == 1
    assert depth_by_bus[300] == 2


def test_path_steps_name_every_branch_crossed(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    transformer_crossing_topology_version_id: uuid.UUID,
) -> None:
    result = _service(db_session).verify_path(
        PathVerificationRequest(start_substation_id=substation_ids["PKLG"])
    )
    branch_steps = {
        (step.from_bus_number, step.to_bus_number): step
        for step in result.path_steps
        if step.edge_type == "BRANCH"
    }
    assert (100, 200) in branch_steps
    assert branch_steps[100, 200].ckt_id == "1"
    assert (200, 300) in branch_steps
    assert branch_steps[200, 300].ckt_id == "2"


def test_path_step_crosses_inter_bus_transformer(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    voltage_yard_ids: dict[str, uuid.UUID],
    transformer_crossing_topology_version_id: uuid.UUID,
) -> None:
    """The engineer must be able to verify every transformer crossing
    (task Section 2's own explicit requirement). Scoped to PKLG's 500kV
    Switchyard specifically, so the Transformer to PKLG's 132kV bus is
    actually walked as a path step rather than both ends starting as
    seeds (see `test_path_verification_walks_the_full_chain`)."""
    result = _service(db_session).verify_path(
        PathVerificationRequest(
            start_substation_id=substation_ids["PKLG"],
            start_voltage_yard_id=voltage_yard_ids["PKLG"],
        )
    )
    transformer_steps = [step for step in result.path_steps if step.edge_type == "TRANSFORMER"]
    assert len(transformer_steps) == 1
    step = transformer_steps[0]
    assert {step.from_bus_number, step.to_bus_number} == {100, 101}
    assert step.ckt_id == "1"
    assert step.topology_transformer_id is not None
    assert step.topology_branch_id is None


def test_traversed_transformers_view_reports_voltage_crossing(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    transformer_crossing_topology_version_id: uuid.UUID,
) -> None:
    result = _service(db_session).verify_path(
        PathVerificationRequest(start_substation_id=substation_ids["PKLG"])
    )
    assert len(result.transformers) == 1
    transformer_view = result.transformers[0]
    assert {transformer_view.from_bus_number, transformer_view.to_bus_number} == {100, 101}


def test_path_verification_scoped_to_one_switchyard_seeds_only_that_voltage(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    voltage_yard_ids: dict[str, uuid.UUID],
    transformer_crossing_topology_version_id: uuid.UUID,
) -> None:
    """Starting Switchyard = PKLG's 500kV yard (bus 101 only) — must not
    seed from PKLG's 132kV bus (100) as well."""
    result = _service(db_session).verify_path(
        PathVerificationRequest(
            start_substation_id=substation_ids["PKLG"],
            start_voltage_yard_id=voltage_yard_ids["PKLG"],
        )
    )
    depth_by_bus = {b.bus.bus_number: b.depth for b in result.buses}
    assert depth_by_bus[101] == 0
    assert 100 in depth_by_bus and depth_by_bus[100] == 1


def test_path_verification_unknown_substation_raises(db_session: Session) -> None:
    with pytest.raises(SubstationNotFoundError):
        _service(db_session).verify_path(PathVerificationRequest(start_substation_id=uuid.uuid4()))


def test_path_verification_unknown_voltage_yard_raises(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    transformer_crossing_topology_version_id: uuid.UUID,
) -> None:
    with pytest.raises(VoltageYardNotFoundError):
        _service(db_session).verify_path(
            PathVerificationRequest(
                start_substation_id=substation_ids["PKLG"],
                start_voltage_yard_id=uuid.uuid4(),
            )
        )


def test_path_verification_voltage_yard_from_different_substation_raises(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    voltage_yard_ids: dict[str, uuid.UUID],
    transformer_crossing_topology_version_id: uuid.UUID,
) -> None:
    with pytest.raises(VoltageYardSubstationMismatchError):
        _service(db_session).verify_path(
            PathVerificationRequest(
                start_substation_id=substation_ids["PKLG"],
                start_voltage_yard_id=voltage_yard_ids["IGBK"],
            )
        )


# --- Statistics ------------------------------------------------------------------


def test_statistics_count_operational_vs_registered_gap(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    voltage_yard_ids: dict[str, uuid.UUID],
    lv_voltage_yard_ids: dict[str, uuid.UUID],
    transformer_crossing_topology_version_id: uuid.UUID,
) -> None:
    """PKLG132/PKLG500 correlate to registered Switchyards; IGBK132/NKST132
    correlate only to a registered Substation, not a registered Switchyard
    (no 132kV yard registered for IGBK/NKST) — the statistics must show
    this gap explicitly, not collapse it away."""
    result = _service(db_session).verify_path(
        PathVerificationRequest(start_substation_id=substation_ids["PKLG"])
    )
    stats = result.statistics
    assert stats.operational_buses_traversed == 4
    assert stats.operational_branches_traversed == 2
    assert stats.operational_transformers_traversed == 1
    # 4 distinct (substation, base_kv) groupings: PKLG132, PKLG500, IGBK132, NKST132.
    assert stats.operational_switchyards_traversed == 4
    assert stats.registered_substations_correlated == 3  # PKLG, IGBK, NKST
    # Only PKLG132 and PKLG500 resolve to an actual registered SubstationVoltageYard.
    assert stats.registered_switchyards_correlated == 2


# --- Correlation summary ----------------------------------------------------------


def test_correlation_summary_buckets_bus_correlation(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    transformer_crossing_topology_version_id: uuid.UUID,
) -> None:
    result = _service(db_session).verify_path(
        PathVerificationRequest(start_substation_id=substation_ids["PKLG"])
    )
    bus_summary = result.correlation_summary.bus
    assert bus_summary.total == 4
    assert bus_summary.correlated == 4  # every bus matched a Substation by mnemonic prefix
    assert bus_summary.unmatched == 0
    assert bus_summary.outside_scope == 0


def test_correlation_summary_reports_unmatched_branches_and_transformers(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    transformer_crossing_topology_version_id: uuid.UUID,
) -> None:
    """No Circuit is registered against this snapshot at all, so every
    Branch/Transformer is UNMATCHED_OPERATIONAL — the summary must report
    this, not silently show zero."""
    result = _service(db_session).verify_path(
        PathVerificationRequest(start_substation_id=substation_ids["PKLG"])
    )
    branch_summary = result.correlation_summary.branch
    assert branch_summary.total == 2
    assert branch_summary.correlated == 0
    assert branch_summary.unmatched == 2

    transformer_summary = result.correlation_summary.transformer
    assert transformer_summary.total == 1
    assert transformer_summary.unmatched == 1


# --- Projections -------------------------------------------------------------------


def test_projections_are_consistent_with_one_traversal(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    voltage_yard_ids: dict[str, uuid.UUID],
    lv_voltage_yard_ids: dict[str, uuid.UUID],
    transformer_crossing_topology_version_id: uuid.UUID,
) -> None:
    """Bus/Switchyard/Substation projections must all originate from the
    same traversal — cross-check their counts/depths agree rather than
    independently re-deriving them."""
    result = _service(db_session).verify_path(
        PathVerificationRequest(start_substation_id=substation_ids["PKLG"])
    )
    projections = result.projections

    assert len(projections.bus_projection) == 4
    assert {e.bus_number for e in projections.bus_projection} == {100, 101, 200, 300}

    assert len(projections.switchyard_projection) == 4
    switchyard_by_key = {
        (e.substation_mnemonic, e.base_kv): e for e in projections.switchyard_projection
    }
    assert ("PKLG", 132.0) in switchyard_by_key
    assert switchyard_by_key["PKLG", 132.0].voltage_yard_id is not None
    assert ("PKLG", 500.0) in switchyard_by_key
    assert switchyard_by_key["PKLG", 500.0].voltage_yard_id is not None
    assert ("IGBK", 132.0) in switchyard_by_key
    assert switchyard_by_key["IGBK", 132.0].voltage_yard_id is None

    substation_mnemonics = {e.substation_mnemonic for e in projections.substation_projection}
    assert substation_mnemonics == {"PKLG", "IGBK", "NKST"}

    # Bus projection's own minimum depth per substation must match the
    # substation projection's depth exactly (same underlying BFS result).
    bus_depth_by_number = {e.bus_number: e.depth for e in projections.bus_projection}
    igbk_bus_depth = bus_depth_by_number[200]
    igbk_substation_depth = next(
        e.depth for e in projections.substation_projection if e.substation_mnemonic == "IGBK"
    )
    assert igbk_bus_depth == igbk_substation_depth


def test_switchyard_projection_matches_traversed_switchyard_statistic(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    transformer_crossing_topology_version_id: uuid.UUID,
) -> None:
    result = _service(db_session).verify_path(
        PathVerificationRequest(start_substation_id=substation_ids["PKLG"])
    )
    assert (
        len(result.projections.switchyard_projection)
        == result.statistics.operational_switchyards_traversed
    )


def test_substation_projection_always_includes_start_substation_at_depth_zero(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    transformer_crossing_topology_version_id: uuid.UUID,
) -> None:
    result = _service(db_session).verify_path(
        PathVerificationRequest(start_substation_id=substation_ids["PKLG"])
    )
    start = next(
        e for e in result.projections.substation_projection if e.substation_mnemonic == "PKLG"
    )
    assert start.depth == 0
