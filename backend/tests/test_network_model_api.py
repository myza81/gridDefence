"""API contract tests for the static Network Model's router
(docs/architecture/network-model-module.md, Phase 5) — exercises the full
Router -> Service -> Repository stack through HTTP, mirroring
backend/tests/test_equipment_registry_api.py's pattern.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.equipment_registry.bootstrap import run_bootstrap as bootstrap_equipment_registry
from app.modules.equipment_registry.service import EquipmentRegistryService, TerminalInput
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
from app.modules.network_model.bootstrap import run_bootstrap as bootstrap_network_model
from app.modules.substation_registry.bootstrap import run_bootstrap as bootstrap_substations
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


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _seed_reference_data(db_session: Session) -> dict[str, int]:
    run_seed(db_session)
    db_session.commit()
    return {
        "voltage_level_id": db_session.query(VoltageLevel)
        .filter_by(label="500kV")
        .one()
        .voltage_level_id,
        "line_type_id": db_session.query(LineType).filter_by(code="OVERHEAD").one().line_type_id,
        "operational_status_id": db_session.query(OperationalStatus)
        .filter_by(code="ACTIVE")
        .one()
        .operational_status_id,
        "region_id": db_session.query(Region).filter_by(code="NORTH").one().region_id,
        "gm_zone_id": db_session.query(GmZone).filter_by(code="KEDP").one().gm_zone_id,
        "state_id": db_session.query(State).filter_by(code="SEL").one().state_id,
        "grid_owner_id": db_session.query(GridOwner).filter_by(code="TNB").one().grid_owner_id,
    }


def _admin_setup(client: TestClient, db_session: Session) -> tuple[str, uuid.UUID]:
    settings = get_settings()
    admin = bootstrap_iam(db_session)
    bootstrap_substations(db_session)
    bootstrap_equipment_registry(db_session)
    bootstrap_network_model(db_session)
    token = _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)
    return token, admin.user_id


def _create_two_terminal_network(
    db_session: Session, ref: dict[str, int], actor_user_id: uuid.UUID
) -> tuple[dict[str, uuid.UUID], uuid.UUID]:
    """Real PKLG/IGBK substations, one voltage yard each, and one
    connecting circuit — enough to exercise every read endpoint end to
    end. Returns (substation_ids, circuit_id)."""
    substation_service = SubstationService(db_session)
    equipment_service = EquipmentRegistryService(db_session)

    substation_ids: dict[str, uuid.UUID] = {}
    voltage_yard_ids: dict[str, uuid.UUID] = {}
    for mnemonic in ("PKLG", "IGBK"):
        substation = substation_service.create_substation(
            mnemonic=mnemonic,
            official_name=f"{mnemonic} Substation",
            region_id=ref["region_id"],
            gm_zone_id=ref["gm_zone_id"],
            state_id=ref["state_id"],
            grid_owner_id=ref["grid_owner_id"],
            operational_status_id=ref["operational_status_id"],
            psse_bus_number=None,
            latitude=None,
            longitude=None,
            commissioned_date=None,
            remarks=None,
            actor_user_id=actor_user_id,
        )
        substation_ids[mnemonic] = substation.substation_id
        yard = equipment_service.create_voltage_yard(
            substation_id=substation.substation_id,
            voltage_level_id=ref["voltage_level_id"],
            actor_user_id=actor_user_id,
        )
        voltage_yard_ids[mnemonic] = yard.voltage_yard_id

    circuit = equipment_service.create_circuit(
        bay_number="Line 1",
        voltage_level_id=ref["voltage_level_id"],
        line_type_id=ref["line_type_id"],
        operational_status_id=ref["operational_status_id"],
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L11"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["IGBK"], breaker_number="L12"),
        ],
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    return substation_ids, circuit.circuit_id


# --- Authentication ---------------------------------------------------------------


def test_overview_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/network-model/overview")
    assert response.status_code == 401


def test_connectivity_requires_authentication(client: TestClient) -> None:
    response = client.get(f"/api/v1/network-model/substations/{uuid.uuid4()}/connectivity")
    assert response.status_code == 401


def test_traverse_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/network-model/traverse", json={"start_substation_id": str(uuid.uuid4())}
    )
    assert response.status_code == 401


# --- Any authenticated user may read (no dedicated permission gate) --------------


def test_any_authenticated_user_may_read_overview(client: TestClient, db_session: Session) -> None:
    bootstrap_iam(db_session)
    iam = IAMService(db_session)
    iam.create_user(
        username="no_permissions_at_all",
        display_name="No Permissions",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    token = _login(client, "no_permissions_at_all", "correct-horse-battery")

    response = client.get(
        "/api/v1/network-model/overview", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "substation_count": 0,
        "circuit_count": 0,
        "tee_off_circuit_count": 0,
        "transformer_count": 0,
    }


# --- Full read flow ----------------------------------------------------------------


def _commit_matching_operational_snapshot(
    db_session: Session, actor_user_id: uuid.UUID
) -> uuid.UUID:
    """Phase 7E — traversal now reads the Operational Snapshot, not the
    registry `Circuit` `_create_two_terminal_network` builds. Commits and
    activates a matching PSS/E RAW (same PKLG132/IGBK132 bus names, so
    `_match_substation_for_bus` correlates each Bus to the same
    Substations `_create_two_terminal_network` already registered)
    directly via the service layer — mirrors how this file's own
    `_create_two_terminal_network` already calls `EquipmentRegistryService`/
    `SubstationService` directly for setup, not through HTTP."""
    from app.modules.psse_integration.service import PsseIntegrationService

    raw = """0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.0,0.0
200,'IGBK132',132.0,1,1,1,1,1.0,0.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'1',0.001,0.01,0.0002
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""
    service = PsseIntegrationService(db_session)
    batch = service.commit(raw, "network-model-api-test.raw", actor_user_id)
    db_session.commit()
    service.activate(batch.batch_id, change_reason="API test baseline", actor_user_id=actor_user_id)
    db_session.commit()
    return batch.topology_version_id


def test_full_read_flow(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    substation_ids, circuit_id = _create_two_terminal_network(db_session, ref, admin_id)
    topology_version_id = _commit_matching_operational_snapshot(db_session, admin_id)

    overview_response = client.get("/api/v1/network-model/overview", headers=headers)
    assert overview_response.status_code == 200
    assert overview_response.json()["substation_count"] == 2
    assert overview_response.json()["circuit_count"] == 1

    connectivity_response = client.get(
        f"/api/v1/network-model/substations/{substation_ids['PKLG']}/connectivity",
        headers=headers,
    )
    assert connectivity_response.status_code == 200
    body = connectivity_response.json()
    assert body["substation_mnemonic"] == "PKLG"
    assert len(body["connected_lines"]) == 1
    assert body["connected_lines"][0]["circuit_id"] == str(circuit_id)
    assert body["connected_lines"][0]["is_tee_off"] is False

    neighbours_response = client.get(
        f"/api/v1/network-model/substations/{substation_ids['PKLG']}/neighbours",
        headers=headers,
    )
    assert neighbours_response.status_code == 200
    assert [n["substation_mnemonic"] for n in neighbours_response.json()] == ["IGBK"]

    equipment_response = client.get(
        f"/api/v1/network-model/substations/{substation_ids['PKLG']}/equipment",
        headers=headers,
    )
    assert equipment_response.status_code == 200
    assert len(equipment_response.json()["line_bays"]) == 1
    assert equipment_response.json()["transformer_bays"] == []

    traverse_response = client.post(
        "/api/v1/network-model/traverse",
        headers=headers,
        json={"start_substation_id": str(substation_ids["PKLG"])},
    )
    assert traverse_response.status_code == 200
    traverse_body = traverse_response.json()
    reached = {r["substation_mnemonic"] for r in traverse_body["reachable_substations"]}
    assert reached == {"PKLG", "IGBK"}
    assert traverse_body["topology_version_id"] == str(topology_version_id)


def test_connectivity_for_unregistered_substation_is_404(
    client: TestClient, db_session: Session
) -> None:
    _seed_reference_data(db_session)
    token, _admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        f"/api/v1/network-model/substations/{uuid.uuid4()}/connectivity", headers=headers
    )
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"


def test_traverse_from_unregistered_substation_is_404(
    client: TestClient, db_session: Session
) -> None:
    _seed_reference_data(db_session)
    token, _admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/network-model/traverse",
        headers=headers,
        json={"start_substation_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


# --- Phase 7E: Operational Snapshot traversal, Snapshot Awareness -------------------


def test_traverse_with_no_current_topology_version_is_400(
    client: TestClient, db_session: Session
) -> None:
    """A registered Substation exists, but no PSS/E RAW has ever been
    imported/activated — traversal cannot silently proceed with no
    Operational Snapshot to read (validation error, not a crash)."""
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    substation_ids, _circuit_id = _create_two_terminal_network(db_session, ref, admin_id)

    response = client.post(
        "/api/v1/network-model/traverse",
        headers=headers,
        json={"start_substation_id": str(substation_ids["PKLG"])},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


def test_traverse_with_unknown_explicit_topology_version_is_404(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    substation_ids, _circuit_id = _create_two_terminal_network(db_session, ref, admin_id)
    _commit_matching_operational_snapshot(db_session, admin_id)

    response = client.post(
        "/api/v1/network-model/traverse",
        headers=headers,
        json={
            "start_substation_id": str(substation_ids["PKLG"]),
            "topology_version_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 404


# --- Phase 7F: Operational Snapshot Verification Workspace --------------------------


def test_snapshot_summary_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/network-model/verification/snapshot-summary")
    assert response.status_code == 401


def test_verify_path_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/network-model/verification/traverse",
        json={"start_substation_id": str(uuid.uuid4())},
    )
    assert response.status_code == 401


def test_snapshot_summary_reports_current_topology(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    _create_two_terminal_network(db_session, ref, admin_id)
    topology_version_id = _commit_matching_operational_snapshot(db_session, admin_id)

    response = client.get("/api/v1/network-model/verification/snapshot-summary", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["topology_version_id"] == str(topology_version_id)
    assert body["bus_count"] == 2
    assert body["branch_count"] == 1


def test_verify_path_full_flow(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    substation_ids, _circuit_id = _create_two_terminal_network(db_session, ref, admin_id)
    topology_version_id = _commit_matching_operational_snapshot(db_session, admin_id)

    response = client.post(
        "/api/v1/network-model/verification/traverse",
        headers=headers,
        json={"start_substation_id": str(substation_ids["PKLG"])},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["topology_version_id"] == str(topology_version_id)
    reached_mnemonics = {b["bus"]["substation_mnemonic"] for b in body["buses"]}
    assert reached_mnemonics == {"PKLG", "IGBK"}
    assert body["statistics"]["operational_buses_traversed"] == 2
    assert len(body["projections"]["substation_projection"]) == 2


def test_verify_path_from_unregistered_substation_is_404(
    client: TestClient, db_session: Session
) -> None:
    _seed_reference_data(db_session)
    token, _admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/network-model/verification/traverse",
        headers=headers,
        json={"start_substation_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


# --- Foundation Hardening Sprint A: Boundary Pocket foundation ----------------------


def test_boundary_pocket_evaluation_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/network-model/boundary-pocket-evaluations",
        json={"circuit_terminal_ids": []},
    )
    assert response.status_code == 401


def test_boundary_pocket_evaluation_full_flow(client: TestClient, db_session: Session) -> None:
    """Excluding PKLG's own `CircuitTerminal` on the PKLG-IGBK circuit
    splits IGBK off from the baseline Main Grid — one isolated island,
    {IGBK} — end to end through the real HTTP router. No inside
    substation, no rest-of-grid override (ADR-019): the Main Grid and
    every isolated island are discovered from the topology itself."""
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    substation_ids, circuit_id = _create_two_terminal_network(db_session, ref, admin_id)
    topology_version_id = _commit_matching_operational_snapshot(db_session, admin_id)

    equipment_service = EquipmentRegistryService(db_session)
    pklg_terminal_id = next(
        t.circuit_terminal_id
        for t in equipment_service.repo.list_terminals(circuit_id)
        if equipment_service.repo.get_voltage_yard_by_id(t.voltage_yard_id).substation_id
        == substation_ids["PKLG"]
    )

    response = client.post(
        "/api/v1/network-model/boundary-pocket-evaluations",
        headers=headers,
        json={"circuit_terminal_ids": [str(pklg_terminal_id)]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_boundary_effective"] is True
    assert len(body["isolated_islands"]) == 1
    island_mnemonics = {
        s["substation_mnemonic"] for s in body["isolated_islands"][0]["substations"]
    }
    assert island_mnemonics == {"IGBK"}
    assert body["topology_version_id"] == str(topology_version_id)
    assert body["baseline_has_single_main_grid"] is True


def test_boundary_pocket_evaluation_no_opening_points_is_ineffective(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    _create_two_terminal_network(db_session, ref, admin_id)
    _commit_matching_operational_snapshot(db_session, admin_id)

    response = client.post(
        "/api/v1/network-model/boundary-pocket-evaluations",
        headers=headers,
        json={"circuit_terminal_ids": []},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_boundary_effective"] is False
    assert body["isolated_islands"] == []


def test_boundary_pocket_evaluation_unknown_circuit_terminal_is_404(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    _create_two_terminal_network(db_session, ref, admin_id)
    _commit_matching_operational_snapshot(db_session, admin_id)

    response = client.post(
        "/api/v1/network-model/boundary-pocket-evaluations",
        headers=headers,
        json={"circuit_terminal_ids": [str(uuid.uuid4())]},
    )
    assert response.status_code == 404


def test_verify_path_with_unknown_voltage_yard_is_404(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    substation_ids, _circuit_id = _create_two_terminal_network(db_session, ref, admin_id)
    _commit_matching_operational_snapshot(db_session, admin_id)

    response = client.post(
        "/api/v1/network-model/verification/traverse",
        headers=headers,
        json={
            "start_substation_id": str(substation_ids["PKLG"]),
            "start_voltage_yard_id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 404
