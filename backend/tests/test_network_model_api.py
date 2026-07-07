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


def test_full_read_flow(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    substation_ids, circuit_id = _create_two_terminal_network(db_session, ref, admin_id)

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
    reached = {r["substation_mnemonic"] for r in traverse_response.json()["reachable_substations"]}
    assert reached == {"PKLG", "IGBK"}


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
