"""API contract tests for the Automatic Load Shedding Functionality
Registry's router — exercises the full Router -> Service -> Repository
stack through HTTP, mirroring backend/tests/test_network_model_api.py's
pattern.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.automatic_load_shedding_functionality.bootstrap import (
    run_bootstrap as bootstrap_alsf,
)
from app.modules.equipment_registry.bootstrap import run_bootstrap as bootstrap_equipment_registry
from app.modules.equipment_registry.service import EquipmentRegistryService, TerminalInput
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
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
        "gm_zone_id": db_session.query(GmZone).filter_by(code="ALOR_SETAR").one().gm_zone_id,
        "state_id": db_session.query(State).filter_by(code="SEL").one().state_id,
        "grid_owner_id": db_session.query(GridOwner).filter_by(code="TNB").one().grid_owner_id,
    }


def _admin_setup(client: TestClient, db_session: Session) -> tuple[str, uuid.UUID]:
    settings = get_settings()
    admin = bootstrap_iam(db_session)
    bootstrap_substations(db_session)
    bootstrap_equipment_registry(db_session)
    bootstrap_alsf(db_session)
    token = _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)
    return token, admin.user_id


def _create_two_terminal_circuit(
    db_session: Session, ref: dict[str, int], actor_user_id: uuid.UUID
) -> tuple[dict[str, uuid.UUID], uuid.UUID]:
    """Real PKLG/IGBK substations, one voltage yard each, and one connecting
    circuit — returns (circuit_terminal_ids by mnemonic, circuit_id)."""
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
        bay_number="1",
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

    detail = equipment_service.get_circuit(circuit.circuit_id)
    assert detail is not None
    terminal_ids = {t.substation_mnemonic: t.circuit_terminal_id for t in detail.terminals}
    return terminal_ids, circuit.circuit_id


# --- Authentication -------------------------------------------------------------------


def test_list_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/automatic-load-shedding-functionality")
    assert response.status_code == 401


def test_create_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/automatic-load-shedding-functionality",
        json={"target_type": "CIRCUIT_TERMINAL", "circuit_terminal_id": str(uuid.uuid4())},
    )
    assert response.status_code == 401


# --- Permission enforcement -------------------------------------------------------------


def test_create_requires_write_permission(client: TestClient, db_session: Session) -> None:
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

    response = client.post(
        "/api/v1/automatic-load-shedding-functionality",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_type": "CIRCUIT_TERMINAL", "circuit_terminal_id": str(uuid.uuid4())},
    )
    assert response.status_code == 403


# --- Full read/write flow --------------------------------------------------------------


def test_full_crud_and_lifecycle_flow(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    terminal_ids, _circuit_id = _create_two_terminal_circuit(db_session, ref, admin_id)

    create_response = client.post(
        "/api/v1/automatic-load-shedding-functionality",
        headers=headers,
        json={
            "target_type": "CIRCUIT_TERMINAL",
            "circuit_terminal_id": str(terminal_ids["PKLG"]),
            "ufls_function": True,
            "uvls_function": False,
        },
    )
    assert create_response.status_code == 201, create_response.text
    body = create_response.json()
    functionality_id = body["id"]
    # Status Model Refinement: every new record is Available (no other
    # scheme currently references it — UFLS/UVLS do not exist yet).
    assert body["status"] == "AVAILABLE"
    assert body["substation_mnemonic"] == "PKLG"

    get_response = client.get(
        f"/api/v1/automatic-load-shedding-functionality/{functionality_id}", headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["ufls_function"] is True
    assert get_response.json()["status"] == "AVAILABLE"

    list_response = client.get("/api/v1/automatic-load-shedding-functionality", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    audit_response = client.get(
        f"/api/v1/automatic-load-shedding-functionality/{functionality_id}/audit-log",
        headers=headers,
    )
    assert audit_response.status_code == 200
    assert audit_response.json()["total"] == 1  # created

    decommission_response = client.post(
        f"/api/v1/automatic-load-shedding-functionality/{functionality_id}/decommission",
        headers=headers,
        json={"change_reason": "Bay dismantled"},
    )
    assert decommission_response.status_code == 200
    assert decommission_response.json()["status"] == "DECOMMISSIONED"


def test_decommission_without_reason_is_400(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    terminal_ids, _circuit_id = _create_two_terminal_circuit(db_session, ref, admin_id)

    create_response = client.post(
        "/api/v1/automatic-load-shedding-functionality",
        headers=headers,
        json={
            "target_type": "CIRCUIT_TERMINAL",
            "circuit_terminal_id": str(terminal_ids["PKLG"]),
            "ufls_function": True,
        },
    )
    functionality_id = create_response.json()["id"]

    response = client.post(
        f"/api/v1/automatic-load-shedding-functionality/{functionality_id}/decommission",
        headers=headers,
        json={},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


def test_create_for_unknown_terminal_is_400(client: TestClient, db_session: Session) -> None:
    _seed_reference_data(db_session)
    token, _admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/automatic-load-shedding-functionality",
        headers=headers,
        json={
            "target_type": "CIRCUIT_TERMINAL",
            "circuit_terminal_id": str(uuid.uuid4()),
            "ufls_function": True,
        },
    )
    assert response.status_code == 400


def test_candidates_endpoint_rejects_emls_at_request_validation(
    client: TestClient, db_session: Session
) -> None:
    """EMLS is not a member of the `SchemeType` Literal — FastAPI rejects
    it as a 422 request-validation error before the service layer is ever
    reached."""
    _seed_reference_data(db_session)
    token, _admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/api/v1/automatic-load-shedding-functionality/candidates",
        headers=headers,
        params={"scheme_type": "EMLS"},
    )
    assert response.status_code == 422


def test_candidates_and_capability_check_endpoints(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    terminal_ids, _circuit_id = _create_two_terminal_circuit(db_session, ref, admin_id)

    create_response = client.post(
        "/api/v1/automatic-load-shedding-functionality",
        headers=headers,
        json={
            "target_type": "CIRCUIT_TERMINAL",
            "circuit_terminal_id": str(terminal_ids["PKLG"]),
            "ufls_function": True,
        },
    )
    assert create_response.json()["status"] == "AVAILABLE"

    candidates_response = client.get(
        "/api/v1/automatic-load-shedding-functionality/candidates",
        headers=headers,
        params={"scheme_type": "UFLS"},
    )
    assert candidates_response.status_code == 200
    assert candidates_response.json()["total"] == 1

    capability_response = client.get(
        "/api/v1/automatic-load-shedding-functionality/capability-check",
        headers=headers,
        params={"scheme_type": "UFLS", "circuit_terminal_id": str(terminal_ids["PKLG"])},
    )
    assert capability_response.status_code == 200
    assert capability_response.json()["capable"] is True


def test_activate_and_deactivate_endpoints_no_longer_exist(
    client: TestClient, db_session: Session
) -> None:
    """Status Model Refinement — Available/Assigned are always computed,
    never manually set, so these endpoints were removed entirely rather
    than deprecated in place."""
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    terminal_ids, _circuit_id = _create_two_terminal_circuit(db_session, ref, admin_id)

    create_response = client.post(
        "/api/v1/automatic-load-shedding-functionality",
        headers=headers,
        json={
            "target_type": "CIRCUIT_TERMINAL",
            "circuit_terminal_id": str(terminal_ids["PKLG"]),
            "ufls_function": True,
        },
    )
    functionality_id = create_response.json()["id"]

    for action in ("activate", "deactivate"):
        response = client.post(
            f"/api/v1/automatic-load-shedding-functionality/{functionality_id}/{action}",
            headers=headers,
            json={},
        )
        assert response.status_code == 404


def test_decommissioning_twice_is_400(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    terminal_ids, _circuit_id = _create_two_terminal_circuit(db_session, ref, admin_id)

    create_response = client.post(
        "/api/v1/automatic-load-shedding-functionality",
        headers=headers,
        json={
            "target_type": "CIRCUIT_TERMINAL",
            "circuit_terminal_id": str(terminal_ids["PKLG"]),
            "ufls_function": True,
        },
    )
    functionality_id = create_response.json()["id"]

    first = client.post(
        f"/api/v1/automatic-load-shedding-functionality/{functionality_id}/decommission",
        headers=headers,
        json={"change_reason": "Bay dismantled"},
    )
    assert first.status_code == 200
    assert first.json()["status"] == "DECOMMISSIONED"

    second = client.post(
        f"/api/v1/automatic-load-shedding-functionality/{functionality_id}/decommission",
        headers=headers,
        json={"change_reason": "Bay dismantled again"},
    )
    assert second.status_code == 400
    assert second.json()["detail"]["code"] == "validation_error"
