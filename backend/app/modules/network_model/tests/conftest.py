"""Fixtures shared by every Network Model test.

Builds real Substation Registry and Equipment Registry records through
their own service layers (never constructed directly — CLAUDE.md A1),
including one ordinary two-terminal circuit, one three-terminal tee-off
circuit, and one transformer — enough to exercise connectivity,
equipment relationships, neighbours, and traversal, including the
tee-off/multi-terminal configurations this phase's tests are required to
cover.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy.orm import Session

from app.modules.equipment_registry.bootstrap import run_bootstrap as bootstrap_equipment_registry
from app.modules.equipment_registry.service import EquipmentRegistryService, TerminalInput
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
from app.modules.network_model.bootstrap import run_bootstrap as bootstrap_network_model
from app.modules.substation_registry.service import SubstationService
from app.reference_data.models import (
    GmZone,
    GridOwner,
    LineType,
    OperationalStatus,
    Region,
    State,
    VoltageLevel,
)
from app.reference_data.seed import run_seed


@dataclass
class ReferenceIds:
    voltage_level_id: int
    second_voltage_level_id: int
    line_type_id: int
    status_id_by_code: dict[str, int]
    region_id: int
    gm_zone_id: int
    state_id: int
    grid_owner_id: int


@pytest.fixture()
def reference_ids(db_session: Session) -> ReferenceIds:
    run_seed(db_session)
    db_session.commit()

    voltage_level = db_session.query(VoltageLevel).filter_by(label="500kV").one()
    second_voltage_level = db_session.query(VoltageLevel).filter_by(label="132kV").one()
    line_type = db_session.query(LineType).filter_by(code="OVERHEAD").one()
    region = db_session.query(Region).filter_by(code="NORTH").one()
    gm_zone = db_session.query(GmZone).filter_by(code="ALOR_SETAR").one()
    state = db_session.query(State).filter_by(code="SEL").one()
    grid_owner = db_session.query(GridOwner).filter_by(code="TNB").one()
    statuses = {s.code: s.operational_status_id for s in db_session.query(OperationalStatus).all()}

    return ReferenceIds(
        voltage_level_id=voltage_level.voltage_level_id,
        second_voltage_level_id=second_voltage_level.voltage_level_id,
        line_type_id=line_type.line_type_id,
        status_id_by_code=statuses,
        region_id=region.region_id,
        gm_zone_id=gm_zone.gm_zone_id,
        state_id=state.state_id,
        grid_owner_id=grid_owner.grid_owner_id,
    )


@pytest.fixture()
def actor_user_id(db_session: Session) -> uuid.UUID:
    iam = IAMService(db_session)
    user = iam.create_user(
        username="network_model_editor",
        display_name="Network Model Test Actor",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    return user.user_id


@pytest.fixture()
def substation_ids(
    db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    """PKLG/IGBK/NKST for an ordinary two-terminal circuit plus a
    three-way tee-off among all three; ABBA is left deliberately
    unconnected (zero circuits, zero transformers) to exercise the
    incomplete-registry / "empty is valid" behaviour this phase's
    architecture requires."""
    service = SubstationService(db_session)
    mnemonics = ["PKLG", "IGBK", "NKST", "ABBA"]
    ids: dict[str, uuid.UUID] = {}
    for mnemonic in mnemonics:
        substation = service.create_substation(
            mnemonic=mnemonic,
            official_name=f"{mnemonic} Substation",
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
        ids[mnemonic] = substation.substation_id
    db_session.commit()
    return ids


@pytest.fixture()
def voltage_yard_ids(
    db_session: Session,
    reference_ids: ReferenceIds,
    substation_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> dict[str, uuid.UUID]:
    service = EquipmentRegistryService(db_session)
    ids: dict[str, uuid.UUID] = {}
    for mnemonic, substation_id in substation_ids.items():
        yard = service.create_voltage_yard(
            substation_id=substation_id,
            voltage_level_id=reference_ids.voltage_level_id,
            actor_user_id=actor_user_id,
        )
        ids[mnemonic] = yard.voltage_yard_id
    db_session.commit()
    return ids


@pytest.fixture()
def lv_voltage_yard_ids(
    db_session: Session,
    reference_ids: ReferenceIds,
    substation_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> dict[str, uuid.UUID]:
    """LV-side yard, PKLG only — enough for one transformer fixture."""
    service = EquipmentRegistryService(db_session)
    yard = service.create_voltage_yard(
        substation_id=substation_ids["PKLG"],
        voltage_level_id=reference_ids.second_voltage_level_id,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    return {"PKLG": yard.voltage_yard_id}


@dataclass
class CircuitIds:
    two_terminal_circuit_id: uuid.UUID
    tee_off_circuit_id: uuid.UUID


@pytest.fixture()
def circuit_ids(
    db_session: Session,
    reference_ids: ReferenceIds,
    voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> CircuitIds:
    """One ordinary PKLG-IGBK two-terminal circuit, and one PKLG-IGBK-NKST
    three-terminal tee-off — the two shapes every connectivity/traversal
    test in this module must handle without assuming exactly two
    terminals."""
    service = EquipmentRegistryService(db_session)

    two_terminal = service.create_circuit(
        bay_number="Line 1",
        voltage_level_id=reference_ids.voltage_level_id,
        line_type_id=reference_ids.line_type_id,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L11"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["IGBK"], breaker_number="L12"),
        ],
        actor_user_id=actor_user_id,
    )

    tee_off = service.create_circuit(
        bay_number="Line 2",
        voltage_level_id=reference_ids.voltage_level_id,
        line_type_id=reference_ids.line_type_id,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L21"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["IGBK"], breaker_number="L22"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["NKST"], breaker_number="L23"),
        ],
        actor_user_id=actor_user_id,
    )

    db_session.commit()
    return CircuitIds(
        two_terminal_circuit_id=two_terminal.circuit_id, tee_off_circuit_id=tee_off.circuit_id
    )


@pytest.fixture()
def transformer_id(
    db_session: Session,
    reference_ids: ReferenceIds,
    substation_ids: dict[str, uuid.UUID],
    voltage_yard_ids: dict[str, uuid.UUID],
    lv_voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> uuid.UUID:
    service = EquipmentRegistryService(db_session)
    transformer = service.create_transformer(
        substation_id=substation_ids["PKLG"],
        transformer_number="1",
        hv_switchyard_id=voltage_yard_ids["PKLG"],
        hv_breaker_number="T11",
        lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
        lv_breaker_number="T12",
        capacity_mva=150,
        commissioning_date=None,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        transformer_type=None,
        manufacturer=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    return transformer.transformer_id


@pytest.fixture()
def bootstrapped_network_model_permissions(db_session: Session) -> None:
    bootstrap_iam(db_session)
    bootstrap_equipment_registry(db_session)
    bootstrap_network_model(db_session)


# --- Operational Snapshot fixtures (Phase 7E — traversal migration) -----------------
#
# The traversal engine now reads TopologyBus/TopologyBranch/TopologyTransformer
# (PSS/E Integration's own tables) rather than Circuit/CircuitTerminal. These
# fixtures build a real Operational Snapshot via `PsseIntegrationService.commit()`
# (never constructed directly — CLAUDE.md A1), using the same PKLG/IGBK/NKST/ABBA
# mnemonics `substation_ids` already registers, so `_match_substation_for_bus`
# correlates each Bus to the same Substation these tests already know by name.

_OPERATIONAL_TOPOLOGY_RAW = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.0,0.0
200,'IGBK132',132.0,1,1,1,1,1.0,0.0
300,'NKST132',132.0,1,1,1,1,1.0,0.0
400,'ABBA132',132.0,1,1,1,1,1.0,0.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'1',0.001,0.01,0.0002
200,300,'2',0.001,0.01,0.0002
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""


@pytest.fixture()
def operational_topology_version_id(
    db_session: Session,
    substation_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> uuid.UUID:
    """The Operational Snapshot equivalent of `circuit_ids`' registry-only
    PKLG-IGBK-NKST-ABBA topology: Bus 100/200/300/400 for PKLG/IGBK/NKST/
    ABBA, Branch 100-200 and 200-300 (a simple chain — PKLG-IGBK-NKST all
    connected). ABBA (bus 400) is deliberately isolated, no Branch at all
    — mirrors `circuit_ids`' own "ABBA has zero circuits" design.
    Committed and activated, so it is the Current TopologyVersion."""
    from app.modules.psse_integration.service import PsseIntegrationService

    service = PsseIntegrationService(db_session)
    batch = service.commit(_OPERATIONAL_TOPOLOGY_RAW, "network-model-traversal.raw", actor_user_id)
    db_session.commit()
    service.activate(batch.batch_id, change_reason="test baseline", actor_user_id=actor_user_id)
    db_session.commit()
    return batch.topology_version_id


@dataclass
class OperationalCircuitCorrelation:
    topology_version_id: uuid.UUID
    pklg_igbk_circuit_id: uuid.UUID
    igbk_nkst_circuit_id: uuid.UUID


@pytest.fixture()
def operational_topology_with_correlated_circuits(
    db_session: Session,
    operational_topology_version_id: uuid.UUID,
    reference_ids: ReferenceIds,
    voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> OperationalCircuitCorrelation:
    """Registers two real Circuits — bay_number '1' (PKLG-IGBK), bay_number
    '2' (IGBK-NKST) — matching `operational_topology_version_id`'s own
    Branch `ckt_id`s exactly, then recomputes `EquipmentTopologyMap`
    correlation against it (`_run_matching` only runs automatically at
    commit time for a *new* TopologyVersion; these Circuits are
    registered afterward, so an explicit recompute is needed, exactly as
    `psse_integration`'s own `recompute_matching` is designed for). This
    is what `traverse()`'s `excluded_circuit_ids` -> Operational edge
    translation needs to have something concrete to exclude."""
    from app.modules.psse_integration.service import PsseIntegrationService

    eq_service = EquipmentRegistryService(db_session)
    pklg_igbk = eq_service.create_circuit(
        bay_number="1",
        voltage_level_id=reference_ids.voltage_level_id,
        line_type_id=reference_ids.line_type_id,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="CB1"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["IGBK"], breaker_number="CB2"),
        ],
        actor_user_id=actor_user_id,
    )
    igbk_nkst = eq_service.create_circuit(
        bay_number="2",
        voltage_level_id=reference_ids.voltage_level_id,
        line_type_id=reference_ids.line_type_id,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=voltage_yard_ids["IGBK"], breaker_number="CB3"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["NKST"], breaker_number="CB4"),
        ],
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    psse_service = PsseIntegrationService(db_session)
    psse_service.recompute_matching(operational_topology_version_id, actor_user_id=actor_user_id)
    db_session.commit()

    return OperationalCircuitCorrelation(
        topology_version_id=operational_topology_version_id,
        pklg_igbk_circuit_id=pklg_igbk.circuit_id,
        igbk_nkst_circuit_id=igbk_nkst.circuit_id,
    )


@dataclass
class OperationalTeeOffCorrelation:
    """Foundation Hardening Sprint A — one three-terminal tee-off Circuit
    (PKLG/IGBK/NKST, mirroring `circuit_ids.tee_off_circuit_id`'s own
    registry-only shape) correlated against `operational_topology_version_id`'s
    Branch 100-200 (ckt_id '1') / Branch 200-300 (ckt_id '2') chain — the
    fixture `test_traversal_respects_excluded_circuit_terminal_ids_on_a_tee_off`
    needs to prove that excluding one specific `CircuitTerminal` (a single
    leg) excludes only that leg's own correlated Branch, never the other
    leg's, unlike whole-`Circuit` exclusion (which excludes both, since
    every terminal on the Circuit resolves to *some* correlated element —
    see `matching.compute_matches`'s own "one candidate per terminal,
    scoped to sibling terminals on the same Circuit" algorithm)."""

    topology_version_id: uuid.UUID
    tee_off_circuit_id: uuid.UUID
    pklg_terminal_id: uuid.UUID
    igbk_terminal_id: uuid.UUID
    nkst_terminal_id: uuid.UUID


@pytest.fixture()
def operational_topology_with_correlated_tee_off_circuit(
    db_session: Session,
    operational_topology_version_id: uuid.UUID,
    reference_ids: ReferenceIds,
    voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> OperationalTeeOffCorrelation:
    """A single tee-off Circuit spanning PKLG/IGBK/NKST — deliberately the
    *only* Circuit registered against this snapshot (unlike
    `operational_topology_with_correlated_circuits`'s two separate ordinary
    Circuits), so each terminal's own correlation is unambiguous:
    - PKLG's terminal's only candidate element is Branch 100-200 (its only
      "another terminal of this Circuit's substation" neighbour is IGBK).
    - NKST's terminal's only candidate element is Branch 200-300.
    - IGBK's terminal (the tee's own hub) has *two* candidates (both
      Branches connect IGBK to another leg's substation) and no `ckt_id`
      match against this Circuit's own `bay_number` — genuinely ambiguous,
      so it resolves to no correlation at all, exactly as
      `matching.compute_matches` documents.
    """
    from app.modules.psse_integration.service import PsseIntegrationService

    eq_service = EquipmentRegistryService(db_session)
    tee_off = eq_service.create_circuit(
        bay_number="Tee 1",
        voltage_level_id=reference_ids.voltage_level_id,
        line_type_id=reference_ids.line_type_id,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="T1"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["IGBK"], breaker_number="T2"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["NKST"], breaker_number="T3"),
        ],
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    psse_service = PsseIntegrationService(db_session)
    psse_service.recompute_matching(operational_topology_version_id, actor_user_id=actor_user_id)
    db_session.commit()

    terminals_by_yard = {
        t.voltage_yard_id: t for t in eq_service.repo.list_terminals(tee_off.circuit_id)
    }
    return OperationalTeeOffCorrelation(
        topology_version_id=operational_topology_version_id,
        tee_off_circuit_id=tee_off.circuit_id,
        pklg_terminal_id=terminals_by_yard[voltage_yard_ids["PKLG"]].circuit_terminal_id,
        igbk_terminal_id=terminals_by_yard[voltage_yard_ids["IGBK"]].circuit_terminal_id,
        nkst_terminal_id=terminals_by_yard[voltage_yard_ids["NKST"]].circuit_terminal_id,
    )


# --- Foundation Hardening Sprint C — connected-component discovery fixtures ------
#
# Self-contained: each fixture below registers its own fresh Substations and
# commits its own fresh Operational Snapshot, deliberately independent of
# `substation_ids`/`operational_topology_version_id` above, so a real
# parallel-circuit or disconnected-secondary-cluster topology can be built
# without affecting any existing traversal/tee-off test's own PKLG-IGBK-
# NKST-ABBA fixture.


def _create_test_substations(
    db_session: Session,
    reference_ids: ReferenceIds,
    actor_user_id: uuid.UUID,
    mnemonics: list[str],
) -> dict[str, uuid.UUID]:
    substation_service = SubstationService(db_session)
    ids: dict[str, uuid.UUID] = {}
    for mnemonic in mnemonics:
        substation = substation_service.create_substation(
            mnemonic=mnemonic,
            official_name=f"{mnemonic} Substation",
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
        ids[mnemonic] = substation.substation_id
    db_session.commit()
    return ids


def _branch_line(from_bus: int, to_bus: int, ckt_id: str, *, in_service: bool = True) -> str:
    """Builds a PSS/E RAW branch data line with an explicit `ST` (status)
    field at index 24 — `raw_parser.py`'s own `ParsedBranch.status` field
    position — so a deliberately out-of-service parallel circuit can be
    constructed directly via import, exactly as a real RAW case would
    encode it, rather than writing to `LoadSnapshotElementState` by hand."""
    fields = [str(from_bus), str(to_bus), f"'{ckt_id}'", "0.001", "0.01", "0.0002"]
    fields += [""] * (24 - len(fields))
    fields.append("1" if in_service else "0")
    return ",".join(fields)


@dataclass
class ParallelCircuitFixture:
    """PKLG(bus 100)-IGBK(bus 200), joined by two parallel registry
    Circuits (bay `1`/breaker `C1x`, bay `2`/breaker `C2x`), each
    correlated to its own Operational Branch — mirroring the real
    two-parallel-132kV-line configuration this pack's own UAT
    investigation found in practice (Foundation Hardening Sprint A.1)."""

    topology_version_id: uuid.UUID
    substation_ids: dict[str, uuid.UUID]
    circuit_1_pklg_terminal_id: uuid.UUID
    circuit_2_pklg_terminal_id: uuid.UUID


def _build_parallel_circuit_fixture(
    db_session: Session,
    reference_ids: ReferenceIds,
    actor_user_id: uuid.UUID,
    *,
    second_branch_in_service: bool,
) -> ParallelCircuitFixture:
    from app.modules.psse_integration.service import PsseIntegrationService

    substation_ids = _create_test_substations(
        db_session, reference_ids, actor_user_id, ["PKLG", "IGBK"]
    )

    raw = (
        "0,100.0,34,0,1,50.0\n"
        "0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA\n"
        "100,'PKLG132',132.0,1,1,1,1,1.0,0.0\n"
        "200,'IGBK132',132.0,1,1,1,1,1.0,0.0\n"
        "0 / END OF BUS DATA, BEGIN LOAD DATA\n"
        "0 / END OF LOAD DATA, BEGIN GENERATOR DATA\n"
        "0 / END OF GENERATOR DATA, BEGIN BRANCH DATA\n"
        f"{_branch_line(100, 200, '1', in_service=True)}\n"
        f"{_branch_line(100, 200, '2', in_service=second_branch_in_service)}\n"
        "0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA\n"
        "0 / END OF TRANSFORMER DATA, BEGIN AREA DATA\n"
        "Q\n"
    )

    psse_service = PsseIntegrationService(db_session)
    batch = psse_service.commit(raw, "network-model-parallel-circuit.raw", actor_user_id)
    db_session.commit()
    psse_service.activate(
        batch.batch_id, change_reason="test baseline", actor_user_id=actor_user_id
    )
    db_session.commit()

    equipment_service = EquipmentRegistryService(db_session)
    pklg_yard = equipment_service.create_voltage_yard(
        substation_id=substation_ids["PKLG"],
        voltage_level_id=reference_ids.voltage_level_id,
        actor_user_id=actor_user_id,
    )
    igbk_yard = equipment_service.create_voltage_yard(
        substation_id=substation_ids["IGBK"],
        voltage_level_id=reference_ids.voltage_level_id,
        actor_user_id=actor_user_id,
    )
    circuit_1 = equipment_service.create_circuit(
        bay_number="1",
        voltage_level_id=reference_ids.voltage_level_id,
        line_type_id=reference_ids.line_type_id,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=pklg_yard.voltage_yard_id, breaker_number="C11"),
            TerminalInput(voltage_yard_id=igbk_yard.voltage_yard_id, breaker_number="C12"),
        ],
        actor_user_id=actor_user_id,
    )
    circuit_2 = equipment_service.create_circuit(
        bay_number="2",
        voltage_level_id=reference_ids.voltage_level_id,
        line_type_id=reference_ids.line_type_id,
        operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=pklg_yard.voltage_yard_id, breaker_number="C21"),
            TerminalInput(voltage_yard_id=igbk_yard.voltage_yard_id, breaker_number="C22"),
        ],
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    psse_service.recompute_matching(batch.topology_version_id, actor_user_id=actor_user_id)
    db_session.commit()

    circuit_1_pklg_terminal = next(
        t
        for t in equipment_service.repo.list_terminals(circuit_1.circuit_id)
        if t.voltage_yard_id == pklg_yard.voltage_yard_id
    )
    circuit_2_pklg_terminal = next(
        t
        for t in equipment_service.repo.list_terminals(circuit_2.circuit_id)
        if t.voltage_yard_id == pklg_yard.voltage_yard_id
    )

    return ParallelCircuitFixture(
        topology_version_id=batch.topology_version_id,
        substation_ids=substation_ids,
        circuit_1_pklg_terminal_id=circuit_1_pklg_terminal.circuit_terminal_id,
        circuit_2_pklg_terminal_id=circuit_2_pklg_terminal.circuit_terminal_id,
    )


@pytest.fixture()
def parallel_circuits_both_in_service(
    db_session: Session,
    reference_ids: ReferenceIds,
    actor_user_id: uuid.UUID,
) -> ParallelCircuitFixture:
    """Both parallel PKLG-IGBK circuits genuinely in service — excluding
    only one must not isolate (the other still carries the connection);
    excluding both must isolate."""
    return _build_parallel_circuit_fixture(
        db_session, reference_ids, actor_user_id, second_branch_in_service=True
    )


@pytest.fixture()
def parallel_circuits_one_already_out_of_service(
    db_session: Session,
    reference_ids: ReferenceIds,
    actor_user_id: uuid.UUID,
) -> ParallelCircuitFixture:
    """Circuit `2`'s own Operational Branch is already out of service in
    the Current `LoadSnapshot` (set directly via the RAW import's own
    `ST` field, exactly as a real case would encode it) — mirrors the
    real PKLG-IGBK production topology this pack's own UAT investigation
    found (Foundation Hardening Sprint A.1): excluding only Circuit `1`
    (the one genuinely in-service path) must already isolate, since
    Circuit `2` was never contributing an edge regardless of any
    exclusion."""
    return _build_parallel_circuit_fixture(
        db_session, reference_ids, actor_user_id, second_branch_in_service=False
    )


@dataclass
class DisconnectedBaselineFixture:
    """Main Grid: PKLG(100)-IGBK(200). A genuinely separate, pre-existing
    secondary cluster: AAAA(500)-BBBB(600) — structurally disconnected
    from PKLG/IGBK from the very start, before any opening point is ever
    selected. Used to verify `baseline_has_single_main_grid`/
    `baseline_component_count` correctly surface this as evidence,
    without ever calling AAAA/BBBB a "newly isolated island" (they were
    never part of the baseline Main Grid to begin with)."""

    topology_version_id: uuid.UUID
    substation_ids: dict[str, uuid.UUID]


@pytest.fixture()
def disconnected_baseline_topology(
    db_session: Session,
    reference_ids: ReferenceIds,
    actor_user_id: uuid.UUID,
) -> DisconnectedBaselineFixture:
    from app.modules.psse_integration.service import PsseIntegrationService

    substation_ids = _create_test_substations(
        db_session, reference_ids, actor_user_id, ["PKLG", "IGBK", "AAAA", "BBBB"]
    )

    raw = (
        "0,100.0,34,0,1,50.0\n"
        "0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA\n"
        "100,'PKLG132',132.0,1,1,1,1,1.0,0.0\n"
        "200,'IGBK132',132.0,1,1,1,1,1.0,0.0\n"
        "500,'AAAA132',132.0,1,1,1,1,1.0,0.0\n"
        "600,'BBBB132',132.0,1,1,1,1,1.0,0.0\n"
        "0 / END OF BUS DATA, BEGIN LOAD DATA\n"
        "0 / END OF LOAD DATA, BEGIN GENERATOR DATA\n"
        "0 / END OF GENERATOR DATA, BEGIN BRANCH DATA\n"
        "100,200,'1',0.001,0.01,0.0002\n"
        "500,600,'1',0.001,0.01,0.0002\n"
        "0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA\n"
        "0 / END OF TRANSFORMER DATA, BEGIN AREA DATA\n"
        "Q\n"
    )

    psse_service = PsseIntegrationService(db_session)
    batch = psse_service.commit(raw, "network-model-disconnected-baseline.raw", actor_user_id)
    db_session.commit()
    psse_service.activate(
        batch.batch_id, change_reason="test baseline", actor_user_id=actor_user_id
    )
    db_session.commit()

    return DisconnectedBaselineFixture(
        topology_version_id=batch.topology_version_id,
        substation_ids=substation_ids,
    )
