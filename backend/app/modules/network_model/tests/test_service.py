"""Service-layer tests for `NetworkModelService` — connectivity, equipment
relationships, neighbours, overview, and traversal, including the
three-terminal tee-off configuration and incomplete-registry behaviour
this phase's architecture explicitly requires.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.network_model.exceptions import SubstationNotFoundError
from app.modules.network_model.schemas import TraversalRequest
from app.modules.network_model.service import NetworkModelService
from app.modules.network_model.tests.conftest import CircuitIds, ReferenceIds

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


# --- Traversal -----------------------------------------------------------------------


def test_traversal_reaches_all_connected_substations(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    circuit_ids: CircuitIds,
) -> None:
    service = NetworkModelService(db_session)
    result = service.traverse(TraversalRequest(start_substation_id=substation_ids["PKLG"]))
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"PKLG", "IGBK", "NKST"}
    # ABBA is isolated (no circuits) and must not be reachable.
    assert "ABBA" not in reached

    start = next(r for r in result.reachable_substations if r.substation_mnemonic == "PKLG")
    assert start.depth == 0


def test_traversal_respects_excluded_circuit_ids(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    circuit_ids: CircuitIds,
) -> None:
    """Excluding the tee-off leaves only the ordinary PKLG-IGBK circuit —
    NKST becomes unreachable, modelling "this line is open"."""
    service = NetworkModelService(db_session)
    result = service.traverse(
        TraversalRequest(
            start_substation_id=substation_ids["PKLG"],
            excluded_circuit_ids=[circuit_ids.tee_off_circuit_id],
        )
    )
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"PKLG", "IGBK"}


def test_traversal_excluding_all_circuits_reaches_only_the_start(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    circuit_ids: CircuitIds,
) -> None:
    service = NetworkModelService(db_session)
    result = service.traverse(
        TraversalRequest(
            start_substation_id=substation_ids["PKLG"],
            excluded_circuit_ids=[
                circuit_ids.two_terminal_circuit_id,
                circuit_ids.tee_off_circuit_id,
            ],
        )
    )
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"PKLG"}


def test_traversal_respects_max_depth(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    circuit_ids: CircuitIds,
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
    circuit_ids: CircuitIds,
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
    nonexistent substation is still a 404, never a crash."""
    service = NetworkModelService(db_session)
    with pytest.raises(SubstationNotFoundError):
        service.traverse(TraversalRequest(start_substation_id=uuid.uuid4()))


# --- Entered-in-error exclusion --------------------------------------------------


def test_entered_in_error_circuit_is_excluded_from_connectivity_and_traversal(
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

    # PKLG-IGBK is still connected via the tee-off, but excluding both
    # circuits should leave IGBK/NKST unreachable from PKLG.
    result = service.traverse(
        TraversalRequest(
            start_substation_id=substation_ids["PKLG"],
            excluded_circuit_ids=[circuit_ids.tee_off_circuit_id],
        )
    )
    reached = {r.substation_mnemonic for r in result.reachable_substations}
    assert reached == {"PKLG"}
