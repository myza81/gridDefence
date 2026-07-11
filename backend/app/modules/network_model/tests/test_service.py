"""Service-layer tests for `NetworkModelService` — connectivity, equipment
relationships, neighbours, overview, and traversal, including the
three-terminal tee-off configuration and incomplete-registry behaviour
this phase's architecture explicitly requires.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.network_model.exceptions import (
    NoCurrentTopologyVersionError,
    SubstationNotFoundError,
    TopologyVersionNotFoundError,
)
from app.modules.network_model.schemas import TraversalRequest
from app.modules.network_model.service import NetworkModelService
from app.modules.network_model.tests.conftest import (
    CircuitIds,
    OperationalCircuitCorrelation,
    ReferenceIds,
)

# --- Substation connectivity ----------------------------------------------------


def test_connectivity_for_two_terminal_circuit_reports_both_sides(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    circuit_ids: CircuitIds,
) -> None:
    service = NetworkModelService(db_session)
    connectivity = service.get_substation_connectivity(substation_ids["PKLG"])

    line = next(
        line
        for line in connectivity.connected_lines
        if line.circuit_id == circuit_ids.two_terminal_circuit_id
    )
    assert line.is_tee_off is False
    assert {t.substation_mnemonic for t in line.terminals} == {"PKLG", "IGBK"}
    assert line.circuit_name == "IGBK–PKLG"

    neighbour_mnemonics = {n.substation_mnemonic for n in connectivity.neighbours}
    assert "IGBK" in neighbour_mnemonics


def test_connectivity_for_tee_off_circuit_reports_all_three_terminals(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    circuit_ids: CircuitIds,
) -> None:
    service = NetworkModelService(db_session)
    connectivity = service.get_substation_connectivity(substation_ids["PKLG"])

    tee_off = next(
        line
        for line in connectivity.connected_lines
        if line.circuit_id == circuit_ids.tee_off_circuit_id
    )
    assert tee_off.is_tee_off is True
    assert len(tee_off.terminals) == 3
    assert {t.substation_mnemonic for t in tee_off.terminals} == {"PKLG", "IGBK", "NKST"}

    # PKLG's neighbours via the tee-off must include both other legs.
    via_tee_off = {
        n.substation_mnemonic
        for n in connectivity.neighbours
        if n.via_circuit_id == circuit_ids.tee_off_circuit_id
    }
    assert via_tee_off == {"IGBK", "NKST"}


def test_connectivity_for_unregistered_substation_raises_not_found(
    db_session: Session,
) -> None:
    service = NetworkModelService(db_session)
    with pytest.raises(SubstationNotFoundError):
        service.get_substation_connectivity(uuid.uuid4())


def test_connectivity_for_substation_with_no_circuits_is_empty_not_an_error(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    circuit_ids: CircuitIds,
) -> None:
    """ABBA has no circuits at all (conftest.py) — a registered substation
    with nothing connected to it yet is a valid state, not a failure."""
    service = NetworkModelService(db_session)
    connectivity = service.get_substation_connectivity(substation_ids["ABBA"])
    assert connectivity.connected_lines == []
    assert connectivity.neighbours == []


# --- Neighbours (deduplicated) ---------------------------------------------------


def test_list_neighbours_deduplicates_across_multiple_lines(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    circuit_ids: CircuitIds,
) -> None:
    """PKLG connects to IGBK via both the two-terminal circuit and the
    tee-off — IGBK must appear exactly once, with connecting_line_count=2."""
    service = NetworkModelService(db_session)
    neighbours = service.list_substation_neighbours(substation_ids["PKLG"])

    igbk = next(n for n in neighbours if n.substation_mnemonic == "IGBK")
    assert igbk.connecting_line_count == 2

    nkst = next(n for n in neighbours if n.substation_mnemonic == "NKST")
    assert nkst.connecting_line_count == 1


def test_list_neighbours_for_unconnected_substation_is_empty(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    circuit_ids: CircuitIds,
) -> None:
    service = NetworkModelService(db_session)
    assert service.list_substation_neighbours(substation_ids["ABBA"]) == []


# --- Equipment relationships ------------------------------------------------------


def test_equipment_groups_transformer_and_line_bays(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    circuit_ids: CircuitIds,
    transformer_id: uuid.UUID,
) -> None:
    service = NetworkModelService(db_session)
    equipment = service.get_substation_equipment(substation_ids["PKLG"])

    assert len(equipment.transformer_bays) == 1
    bay = equipment.transformer_bays[0]
    assert bay.transformer_id == transformer_id
    # HV yard is at 500kV -> "XGT" prefix (equipment_registry.service's own
    # _TRANSFORMER_SHORT_NAME_PREFIX_BY_NOMINAL_KV convention).
    assert bay.generated_short_name == "XGT1"
    assert bay.hv_voltage_level_label == "500kV"
    assert bay.lv_voltage_level_label == "132kV"

    # Two circuits terminate at PKLG (two-terminal + tee-off) => two line bays.
    assert len(equipment.line_bays) == 2


def test_equipment_for_substation_with_nothing_registered_is_empty(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    circuit_ids: CircuitIds,
) -> None:
    service = NetworkModelService(db_session)
    equipment = service.get_substation_equipment(substation_ids["ABBA"])
    assert equipment.transformer_bays == []
    assert equipment.line_bays == []


def test_equipment_for_unregistered_substation_raises_not_found(db_session: Session) -> None:
    service = NetworkModelService(db_session)
    with pytest.raises(SubstationNotFoundError):
        service.get_substation_equipment(uuid.uuid4())


# --- Overview ----------------------------------------------------------------------


def test_overview_on_empty_registry_is_all_zero(
    db_session: Session, reference_ids: ReferenceIds
) -> None:
    """An empty (but reference-data-seeded) registry is a valid starting
    state for this platform, not an error — the network grows into place
    over time."""
    service = NetworkModelService(db_session)
    overview = service.get_overview()
    assert overview.substation_count == 0
    assert overview.circuit_count == 0
    assert overview.tee_off_circuit_count == 0
    assert overview.transformer_count == 0


def test_overview_counts_reflect_registered_data(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    circuit_ids: CircuitIds,
    transformer_id: uuid.UUID,
) -> None:
    service = NetworkModelService(db_session)
    overview = service.get_overview()
    assert overview.substation_count == 4
    assert overview.circuit_count == 2
    assert overview.tee_off_circuit_count == 1
    assert overview.transformer_count == 1


# --- Traversal (Phase 7E — Operational Snapshot traversal migration) ----------------
#
# `operational_topology_version_id` builds a real, committed, activated Operational
# Snapshot (via `PsseIntegrationService.commit()`/`.activate()`) mirroring
# `circuit_ids`' own PKLG-IGBK-NKST-ABBA topology: Bus 100/200/300/400, Branch
# 100-200 (ckt_id '1') and 200-300 (ckt_id '2'), ABBA isolated. The traversal
# graph is now built exclusively from this Operational Snapshot — Equipment
# Registry is consulted only where a test explicitly needs to prove the
# `excluded_circuit_ids` -> Operational edge correlation translation.


def test_traversal_reaches_all_connected_substations(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    operational_topology_version_id: uuid.UUID,
) -> None:
    service = NetworkModelService(db_session)
    result = service.traverse(TraversalRequest(start_substation_id=substation_ids["PKLG"]))
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"PKLG", "IGBK", "NKST"}
    # ABBA is isolated (no Branch at all) and must not be reachable.
    assert "ABBA" not in reached

    start = next(r for r in result.reachable_substations if r.substation_mnemonic == "PKLG")
    assert start.depth == 0
    assert result.topology_version_id == operational_topology_version_id


def test_traversal_respects_excluded_circuit_ids(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    operational_topology_with_correlated_circuits: OperationalCircuitCorrelation,
) -> None:
    """Excluding the (registry) Circuit that correlates to the IGBK-NKST
    Branch leaves only the PKLG-IGBK Branch — NKST becomes unreachable,
    modelling "this line is open." Proves the `excluded_circuit_ids`
    Line-Connectivity-Registry-facing parameter still works, translated
    via `EquipmentTopologyMap` correlation into the Operational edge it
    resolves to for this TopologyVersion."""
    service = NetworkModelService(db_session)
    result = service.traverse(
        TraversalRequest(
            start_substation_id=substation_ids["PKLG"],
            excluded_circuit_ids=[
                operational_topology_with_correlated_circuits.igbk_nkst_circuit_id
            ],
        )
    )
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"PKLG", "IGBK"}


def test_traversal_excluding_all_correlated_circuits_reaches_only_the_start(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    operational_topology_with_correlated_circuits: OperationalCircuitCorrelation,
) -> None:
    service = NetworkModelService(db_session)
    result = service.traverse(
        TraversalRequest(
            start_substation_id=substation_ids["PKLG"],
            excluded_circuit_ids=[
                operational_topology_with_correlated_circuits.pklg_igbk_circuit_id,
                operational_topology_with_correlated_circuits.igbk_nkst_circuit_id,
            ],
        )
    )
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"PKLG"}


def test_traversal_excluding_an_uncorrelated_circuit_excludes_nothing(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    operational_topology_version_id: uuid.UUID,
) -> None:
    """Operational Correlation is optional enrichment only — a Circuit
    that has never been matched against this TopologyVersion (no
    `EquipmentTopologyMap` entry at all) gracefully excludes nothing,
    rather than raising or silently breaking the whole traversal."""
    service = NetworkModelService(db_session)
    result = service.traverse(
        TraversalRequest(
            start_substation_id=substation_ids["PKLG"],
            excluded_circuit_ids=[uuid.uuid4()],
        )
    )
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"PKLG", "IGBK", "NKST"}


def test_traversal_respects_max_depth(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    operational_topology_version_id: uuid.UUID,
) -> None:
    service = NetworkModelService(db_session)
    result = service.traverse(
        TraversalRequest(start_substation_id=substation_ids["PKLG"], max_depth=0)
    )
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"PKLG"}


def test_traversal_from_isolated_substation_reaches_only_itself(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    operational_topology_version_id: uuid.UUID,
) -> None:
    service = NetworkModelService(db_session)
    result = service.traverse(TraversalRequest(start_substation_id=substation_ids["ABBA"]))
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"ABBA"}


def test_traversal_from_unregistered_substation_raises_not_found(db_session: Session) -> None:
    service = NetworkModelService(db_session)
    with pytest.raises(SubstationNotFoundError):
        service.traverse(TraversalRequest(start_substation_id=uuid.uuid4()))


def test_traversal_on_completely_empty_registry_raises_not_found(
    db_session: Session, reference_ids: ReferenceIds
) -> None:
    """No substations registered at all yet — a request naming a specific,
    nonexistent substation is still a 404, never a crash. The substation
    check happens before Operational Snapshot resolution, so this remains
    a 404 even though there is also no Current TopologyVersion."""
    service = NetworkModelService(db_session)
    with pytest.raises(SubstationNotFoundError):
        service.traverse(TraversalRequest(start_substation_id=uuid.uuid4()))


def test_traversal_with_no_current_topology_version_raises_validation_error(
    db_session: Session, substation_ids: dict[str, uuid.UUID]
) -> None:
    """Snapshot Awareness — a registered Substation exists, but no PSS/E
    RAW has ever been imported/activated: traversal cannot silently
    proceed with no Operational Snapshot to read."""
    service = NetworkModelService(db_session)
    with pytest.raises(NoCurrentTopologyVersionError):
        service.traverse(TraversalRequest(start_substation_id=substation_ids["PKLG"]))


def test_traversal_start_substation_with_no_correlated_bus_still_reaches_itself(
    db_session: Session,
    reference_ids: ReferenceIds,
    operational_topology_version_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> None:
    """A registered Substation not yet correlated to any Bus in the
    current snapshot (never appears in `_OPERATIONAL_TOPOLOGY_RAW`) still
    always reaches itself, preserving the pre-migration invariant "a
    substation is always reachable from itself" even with zero
    Operational Snapshot participation."""
    from app.modules.substation_registry.service import SubstationService

    sub_service = SubstationService(db_session)
    new_substation = sub_service.create_substation(
        mnemonic="ZZZZ",
        official_name="Unmigrated Substation",
        region_id=reference_ids.region_id,
        gm_zone_id=reference_ids.gm_zone_id,
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

    service = NetworkModelService(db_session)
    result = service.traverse(TraversalRequest(start_substation_id=new_substation.substation_id))
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"ZZZZ"}
    assert result.reachable_substations[0].depth == 0


# --- Entered-in-error exclusion --------------------------------------------------


def test_entered_in_error_circuit_is_excluded_from_connectivity(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    circuit_ids: CircuitIds,
    reference_ids: ReferenceIds,
    actor_user_id: uuid.UUID,
) -> None:
    from app.modules.equipment_registry.service import EquipmentRegistryService

    equipment_service = EquipmentRegistryService(db_session)
    equipment_service.change_status(
        circuit_ids.two_terminal_circuit_id,
        operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
        change_reason="Test: entered in error",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service = NetworkModelService(db_session)
    connectivity = service.get_substation_connectivity(substation_ids["PKLG"])
    assert circuit_ids.two_terminal_circuit_id not in {
        line.circuit_id for line in connectivity.connected_lines
    }


def test_entered_in_error_circuit_is_excluded_from_connectivity_but_not_from_traversal(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    operational_topology_with_correlated_circuits: OperationalCircuitCorrelation,
    reference_ids: ReferenceIds,
    actor_user_id: uuid.UUID,
) -> None:
    """Registry-level `ENTERED_IN_ERROR` correction (CLAUDE.md §11.6) is
    Engineering Registry metadata — traversal itself must never depend on
    it (this phase's own core principle). Marking the PKLG-IGBK Circuit
    `ENTERED_IN_ERROR` correctly removes it from
    `get_substation_connectivity` (registry-sourced, unaffected by this
    migration), but the PKLG-IGBK *Operational* Branch remains fully
    traversable — the two are now genuinely independent facts.
    `excluded_circuit_ids` (see `test_traversal_respects_excluded_circuit_ids`)
    remains the only way to actually exclude the operational line, and it
    is always an explicit, deliberate request, never an automatic
    consequence of a registry status change."""
    from app.modules.equipment_registry.service import EquipmentRegistryService

    equipment_service = EquipmentRegistryService(db_session)
    equipment_service.change_status(
        operational_topology_with_correlated_circuits.pklg_igbk_circuit_id,
        operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
        change_reason="Test: entered in error",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service = NetworkModelService(db_session)
    connectivity = service.get_substation_connectivity(substation_ids["PKLG"])
    assert operational_topology_with_correlated_circuits.pklg_igbk_circuit_id not in {
        line.circuit_id for line in connectivity.connected_lines
    }

    result = service.traverse(TraversalRequest(start_substation_id=substation_ids["PKLG"]))
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"PKLG", "IGBK", "NKST"}


# --- Phase 7E required coverage: Operational Snapshot traversal specifics -----------


def test_traversal_works_with_zero_line_connectivity_registry_data(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    operational_topology_version_id: uuid.UUID,
) -> None:
    """Traversal must still function if no Line Connectivity metadata
    exists at all. `operational_topology_version_id` deliberately
    registers zero Circuits/CircuitTerminals — this test asserts that
    fact explicitly, rather than leaving it merely implicit in the other
    traversal tests."""
    service = NetworkModelService(db_session)
    assert service.repo.list_active_circuit_ids() == []

    result = service.traverse(TraversalRequest(start_substation_id=substation_ids["PKLG"]))
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"PKLG", "IGBK", "NKST"}


def test_traversal_passes_through_fictitious_bus_naturally(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> None:
    """EDR-007 §4.6/§4.7 — Fictitious Buses remain Operational Topology
    and participate in traversal exactly like any other Bus; they are
    never skipped. Bus 999 'SDAOFIC' sits between PKLG and IGBK,
    mirroring EDR-007 §5.4 Pattern B (a Fictitious Bus at a junction)."""
    from app.modules.psse_integration.service import PsseIntegrationService

    raw = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.0,0.0
200,'IGBK132',132.0,1,1,1,1,1.0,0.0
999,'SDAOFIC',132.0,1,1,1,1,1.0,0.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,999,'1',0.0001,0.001,0.0
999,200,'1',0.0001,0.001,0.0
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""
    service = PsseIntegrationService(db_session)
    batch = service.commit(raw, "fictitious.raw", actor_user_id)
    db_session.commit()
    service.activate(
        batch.batch_id, change_reason="fictitious bus fixture", actor_user_id=actor_user_id
    )
    db_session.commit()

    network_service = NetworkModelService(db_session)
    result = network_service.traverse(TraversalRequest(start_substation_id=substation_ids["PKLG"]))
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    # IGBK is reachable *through* the Fictitious Bus, proving it was
    # traversed, not skipped.
    assert reached == {"PKLG", "IGBK"}
    # PKLG -> SDAOFIC -> IGBK is two Bus-level hops, confirming the
    # Fictitious Bus was not collapsed away or bypassed.
    igbk = next(r for r in result.reachable_substations if r.substation_mnemonic == "IGBK")
    assert igbk.depth == 2


def test_traversal_preserves_split_switchyard_topology_without_collapsing(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    reference_ids: ReferenceIds,
    actor_user_id: uuid.UUID,
) -> None:
    """EDR-007 §4.5 — a Split Switchyard Bus pair (same mnemonic, nominal
    voltage, and a single-letter suffix) both correlate to the *same*
    Substation, but remain two distinct Operational Buses; traversal must
    never collapse or simplify them into one node. Bus 501 'BLPS132L'
    connects only to PKLG; Bus 502 'BLPS132R' connects only to NKST —
    deliberately no Branch directly between the two split halves."""
    from app.modules.psse_integration.service import PsseIntegrationService
    from app.modules.substation_registry.service import SubstationService

    sub_service = SubstationService(db_session)
    sub_service.create_substation(
        mnemonic="BLPS",
        official_name="BLPS Substation",
        region_id=reference_ids.region_id,
        gm_zone_id=reference_ids.gm_zone_id,
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

    raw = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.0,0.0
300,'NKST132',132.0,1,1,1,1,1.0,0.0
501,'BLPS132L',132.0,1,1,1,1,1.0,0.0
502,'BLPS132R',132.0,1,1,1,1,1.0,0.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,501,'1',0.001,0.01,0.0002
300,502,'1',0.001,0.01,0.0002
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""
    service = PsseIntegrationService(db_session)
    batch = service.commit(raw, "split-switchyard.raw", actor_user_id)
    db_session.commit()
    service.activate(
        batch.batch_id, change_reason="split switchyard fixture", actor_user_id=actor_user_id
    )
    db_session.commit()

    network_service = NetworkModelService(db_session)
    result = network_service.traverse(TraversalRequest(start_substation_id=substation_ids["PKLG"]))
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    # BLPS is reachable via BLPS132L, but NKST is NOT reachable from
    # PKLG — if the split pair had been incorrectly collapsed into one
    # node, NKST would also (wrongly) become reachable through BLPS132R.
    assert reached == {"PKLG", "BLPS"}
    assert "NKST" not in reached


def test_traversal_does_not_cross_disconnected_islands(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    operational_topology_version_id: uuid.UUID,
) -> None:
    """PKLG-IGBK-NKST form one connected cluster; ABBA is a second,
    disconnected island (no Branch at all connects it to the rest).
    Traversal from either side must never reach the other."""
    service = NetworkModelService(db_session)

    from_pklg = service.traverse(TraversalRequest(start_substation_id=substation_ids["PKLG"]))
    assert {r.substation_mnemonic for r in from_pklg.reachable_substations} == {
        "PKLG",
        "IGBK",
        "NKST",
    }

    from_abba = service.traverse(TraversalRequest(start_substation_id=substation_ids["ABBA"]))
    assert {r.substation_mnemonic for r in from_abba.reachable_substations} == {"ABBA"}


def test_traversal_respects_branch_in_service_state(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> None:
    """Branch Traversal requirement — "Branch status shall continue to
    respect Operational Snapshot state." A Branch parsed with STAT=0 (out
    of service) must not contribute a graph edge, even though it remains
    a structurally valid Operational Branch."""
    from app.modules.psse_integration.service import PsseIntegrationService

    padding = ",".join(["0"] * 18)
    raw = f"""0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.0,0.0
200,'IGBK132',132.0,1,1,1,1,1.0,0.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'1',0.001,0.01,0.0002,{padding},0
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""
    service = PsseIntegrationService(db_session)
    batch = service.commit(raw, "out-of-service.raw", actor_user_id)
    db_session.commit()
    service.activate(batch.batch_id, change_reason="oos fixture", actor_user_id=actor_user_id)
    db_session.commit()

    network_service = NetworkModelService(db_session)
    result = network_service.traverse(TraversalRequest(start_substation_id=substation_ids["PKLG"]))
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"PKLG"}
    assert "IGBK" not in reached


def test_traversal_transformer_crosses_voltage_levels(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> None:
    """Transformer Traversal requirement — Operational Transformers
    participate naturally in graph traversal and must support crossing
    voltage levels, with no Equipment Registry Transformer required. Bus
    100 'PKLG132' (132kV) and Bus 200 'IGBK033' (33kV) are two *different*
    Substations, connected only by an Operational Transformer — never a
    Branch — so IGBK is reachable from PKLG if, and only if, the
    Transformer itself contributed a working graph edge."""
    from app.modules.psse_integration.service import PsseIntegrationService

    raw = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.0,0.0
200,'IGBK033',33.0,1,1,1,1,1.0,0.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
100,200,0,'1',1,1,1,1.0,0.0,0.0,0,1,0,1,1.0,0.0,0.0,0.0,1.0,0,0,0,1.0,0.0
0.0,0.05
1.0,0,150.0,150.0,150.0,0,0,1.0,0.0,1.0,1.0,0,1.0,1.0,0,1.0
1.0,0,150.0,150.0,150.0,0,0,1.0,0.0,1.0,1.0,0,1.0,1.0,0,1.0
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""
    service = PsseIntegrationService(db_session)
    batch = service.commit(raw, "transformer.raw", actor_user_id)
    db_session.commit()
    service.activate(
        batch.batch_id, change_reason="transformer fixture", actor_user_id=actor_user_id
    )
    db_session.commit()

    transformers = service.repo.list_topology_transformers(batch.topology_version_id)
    assert len(transformers) == 1
    assert transformers[0].tertiary_bus_id is None  # 2-winding

    network_service = NetworkModelService(db_session)
    result = network_service.traverse(TraversalRequest(start_substation_id=substation_ids["PKLG"]))
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"PKLG", "IGBK"}
    igbk = next(r for r in result.reachable_substations if r.substation_mnemonic == "IGBK")
    assert igbk.depth == 1


def test_traversal_against_explicit_non_current_topology_version(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    operational_topology_version_id: uuid.UUID,
    actor_user_id: uuid.UUID,
) -> None:
    """Snapshot Awareness — an explicit `topology_version_id` selects a
    specific Operational Snapshot, even one that is no longer Current,
    without mixing it with whatever import happened afterward."""
    from app.modules.psse_integration.service import PsseIntegrationService

    second_raw = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.0,0.0
200,'IGBK132',132.0,1,1,1,1,1.0,0.0
300,'NKST132',132.0,1,1,1,1,1.0,0.0
400,'ABBA132',132.0,1,1,1,1,1.0,0.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'1',0.001,0.01,0.0002
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""
    service = PsseIntegrationService(db_session)
    batch2 = service.commit(second_raw, "second-topology.raw", actor_user_id)
    db_session.commit()
    service.activate(batch2.batch_id, change_reason="supersede", actor_user_id=actor_user_id)
    db_session.commit()

    network_service = NetworkModelService(db_session)

    # Current topology (the second one) has no 200-300 Branch -> NKST unreachable.
    current_result = network_service.traverse(
        TraversalRequest(start_substation_id=substation_ids["PKLG"])
    )
    assert {r.substation_mnemonic for r in current_result.reachable_substations} == {
        "PKLG",
        "IGBK",
    }
    assert current_result.topology_version_id == batch2.topology_version_id

    # The original (now historical/Superseded) topology still has the
    # 200-300 Branch -> NKST reachable, selected explicitly by id.
    historical_result = network_service.traverse(
        TraversalRequest(
            start_substation_id=substation_ids["PKLG"],
            topology_version_id=operational_topology_version_id,
        )
    )
    assert {r.substation_mnemonic for r in historical_result.reachable_substations} == {
        "PKLG",
        "IGBK",
        "NKST",
    }
    assert historical_result.topology_version_id == operational_topology_version_id


def test_traversal_with_unknown_explicit_topology_version_raises_not_found(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    operational_topology_version_id: uuid.UUID,
) -> None:
    service = NetworkModelService(db_session)
    with pytest.raises(TopologyVersionNotFoundError):
        service.traverse(
            TraversalRequest(
                start_substation_id=substation_ids["PKLG"], topology_version_id=uuid.uuid4()
            )
        )
