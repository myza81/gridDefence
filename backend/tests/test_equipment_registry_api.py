"""API contract tests for Equipment Registry's Circuit/CircuitTerminal/
SubstationVoltageYard router — docs/architecture/equipment-registry-module.md
§12, §7.5a, CLAUDE.md A9/A11. Exercises the full Router -> Service ->
Repository stack through HTTP, mirroring
backend/tests/test_substation_registry_api.py's pattern.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.equipment_registry.bootstrap import run_bootstrap as bootstrap_equipment_registry
from app.modules.equipment_registry.service import EquipmentRegistryService
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
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
        "second_voltage_level_id": db_session.query(VoltageLevel)
        .filter_by(label="132kV")
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
    """Returns (bearer_token, admin_user_id) for the bootstrap Administrator.

    `admin_user_id` is a real `uuid.UUID`, not a string — it is passed
    straight through to service-layer calls (`actor_user_id=...`), which
    expect a `uuid.UUID`. SQLite's Uuid type processor requires the Python
    value to already be a `uuid.UUID` object (unlike PostgreSQL's native
    UUID type, which is more permissive) — stringifying it here caused
    every service-layer call built on top of this helper to fail only
    under SQLite.
    """
    settings = get_settings()
    admin = bootstrap_iam(db_session)
    bootstrap_substations(db_session)
    bootstrap_equipment_registry(db_session)
    token = _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)
    return token, admin.user_id


def _create_substations_and_yards(
    db_session: Session, ref: dict[str, int], actor_user_id: uuid.UUID
) -> tuple[dict[str, str], dict[str, str]]:
    """Real Substation Registry records plus one default voltage yard each,
    created through the real service layers (never inserted directly) so
    circuit terminals have something valid to reference
    (equipment-registry-module.md §7.5a; ADR-008). Returns
    (substation_ids, voltage_yard_ids), both keyed by mnemonic."""
    substation_service = SubstationService(db_session)
    equipment_service = EquipmentRegistryService(db_session)
    substation_ids: dict[str, str] = {}
    voltage_yard_ids: dict[str, str] = {}
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
        substation_ids[mnemonic] = str(substation.substation_id)
        yard = equipment_service.create_voltage_yard(
            substation_id=substation.substation_id,
            voltage_level_id=ref["voltage_level_id"],
            actor_user_id=actor_user_id,
        )
        voltage_yard_ids[mnemonic] = str(yard.voltage_yard_id)
    db_session.commit()
    return substation_ids, voltage_yard_ids


def _circuit_payload(ref: dict[str, int], voltage_yard_ids: dict[str, str], **overrides) -> dict:
    payload = {
        "bay_number": "Line 1",
        "voltage_level_id": ref["voltage_level_id"],
        "line_type_id": ref["line_type_id"],
        "operational_status_id": ref["operational_status_id"],
        "is_interconnector": False,
        "remarks": None,
        "terminals": [
            {"voltage_yard_id": voltage_yard_ids["PKLG"], "breaker_number": "L25"},
            {"voltage_yard_id": voltage_yard_ids["IGBK"], "breaker_number": "805"},
        ],
    }
    payload.update(overrides)
    return payload


def test_create_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/circuits", json={})
    assert response.status_code == 401


def test_list_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/circuits")
    assert response.status_code == 401


def test_create_without_equipment_registry_write_is_forbidden(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    _admin_login_token, admin_id = _admin_setup(client, db_session)
    _substation_ids, voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    iam = IAMService(db_session)
    iam.create_user(
        username="viewer_only",
        display_name="Viewer Only",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    token = _login(client, "viewer_only", "correct-horse-battery")

    response = client.post(
        "/api/v1/circuits",
        headers={"Authorization": f"Bearer {token}"},
        json=_circuit_payload(ref, voltage_yard_ids),
    )
    assert response.status_code == 403


def test_any_authenticated_user_may_list_without_equipment_registry_read(
    client: TestClient, db_session: Session
) -> None:
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

    response = client.get("/api/v1/circuits", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_full_create_read_update_flow(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    _substation_ids, voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    create_response = client.post(
        "/api/v1/circuits", headers=headers, json=_circuit_payload(ref, voltage_yard_ids)
    )
    assert create_response.status_code == 201, create_response.text
    body = create_response.json()
    assert body["bay_number"] == "Line 1"
    # Canonical route name: sorted terminal mnemonics only, never
    # bay_number (Phase 3 close-out) — "IGBK" sorts before "PKLG".
    assert body["circuit_name"] == "IGBK–PKLG"
    assert len(body["terminals"]) == 2
    assert body["terminals"][0]["voltage_level_label"] == "500kV"
    assert body["created_by"]["username"] == get_settings().bootstrap_admin_username
    circuit_id = body["circuit_id"]

    get_response = client.get(f"/api/v1/circuits/{circuit_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["circuit_name"] == "IGBK–PKLG"

    update_response = client.patch(
        f"/api/v1/circuits/{circuit_id}",
        headers=headers,
        json={"bay_number": "Line 1A", "line_type_id": ref["line_type_id"]},
    )
    assert update_response.status_code == 200
    assert update_response.json()["bay_number"] == "Line 1A"

    terminals_response = client.get(f"/api/v1/circuits/{circuit_id}/terminals", headers=headers)
    assert terminals_response.status_code == 200
    assert len(terminals_response.json()) == 2

    audit_response = client.get(f"/api/v1/circuits/{circuit_id}/audit-log", headers=headers)
    assert audit_response.status_code == 200
    assert audit_response.json()["total"] == 1
    assert audit_response.json()["items"][0]["field_name"] == "bay_number"


def test_insufficient_terminals_returns_400(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    _substation_ids, voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    payload = _circuit_payload(
        ref,
        voltage_yard_ids,
        terminals=[{"voltage_yard_id": voltage_yard_ids["PKLG"], "breaker_number": "L25"}],
    )
    response = client.post("/api/v1/circuits", headers=headers, json=payload)
    # Pydantic's min_length=2 rejects this at the schema layer (422), before
    # it ever reaches the service-layer InsufficientTerminalsError (400) —
    # both layers enforce the same rule, defense in depth.
    assert response.status_code == 422


def test_duplicate_terminal_voltage_yard_returns_400(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    _substation_ids, voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    payload = _circuit_payload(
        ref,
        voltage_yard_ids,
        terminals=[
            {"voltage_yard_id": voltage_yard_ids["PKLG"], "breaker_number": "L25"},
            {"voltage_yard_id": voltage_yard_ids["PKLG"], "breaker_number": "L26"},
        ],
    )
    response = client.post("/api/v1/circuits", headers=headers, json=payload)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


def test_add_terminal_endpoint_extends_circuit_to_a_tee_off(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    _substation_ids, voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    third_substation = SubstationService(db_session).create_substation(
        mnemonic="NKST",
        official_name="NKST Substation",
        region_id=ref["region_id"],
        state_id=ref["state_id"],
        grid_owner_id=ref["grid_owner_id"],
        operational_status_id=ref["operational_status_id"],
        psse_bus_number=None,
        latitude=None,
        longitude=None,
        commissioned_date=None,
        remarks=None,
        actor_user_id=admin_id,
    )
    third_yard = EquipmentRegistryService(db_session).create_voltage_yard(
        substation_id=third_substation.substation_id,
        voltage_level_id=ref["voltage_level_id"],
        actor_user_id=admin_id,
    )
    db_session.commit()

    create_response = client.post(
        "/api/v1/circuits", headers=headers, json=_circuit_payload(ref, voltage_yard_ids)
    )
    circuit_id = create_response.json()["circuit_id"]

    add_response = client.post(
        f"/api/v1/circuits/{circuit_id}/terminals",
        headers=headers,
        json={"voltage_yard_id": str(third_yard.voltage_yard_id), "breaker_number": "N1"},
    )
    assert add_response.status_code == 201, add_response.text
    assert len(add_response.json()["terminals"]) == 3


def test_update_terminal_endpoint(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    _substation_ids, voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    create_response = client.post(
        "/api/v1/circuits", headers=headers, json=_circuit_payload(ref, voltage_yard_ids)
    )
    body = create_response.json()
    circuit_id = body["circuit_id"]
    terminal_id = body["terminals"][0]["circuit_terminal_id"]

    update_response = client.patch(
        f"/api/v1/circuits/{circuit_id}/terminals/{terminal_id}",
        headers=headers,
        json={"breaker_number": "L99", "commissioning_date": "2020-01-15"},
    )
    assert update_response.status_code == 200, update_response.text
    updated_terminal = next(
        t for t in update_response.json()["terminals"] if t["circuit_terminal_id"] == terminal_id
    )
    assert updated_terminal["breaker_number"] == "L99"
    assert updated_terminal["commissioning_date"] == "2020-01-15"

    audit_response = client.get(f"/api/v1/circuits/{circuit_id}/audit-log", headers=headers)
    field_names = {e["field_name"] for e in audit_response.json()["items"]}
    assert "terminal_breaker_number" in field_names
    assert "terminal_commissioning_date" in field_names


def test_get_unknown_circuit_returns_404(client: TestClient, db_session: Session) -> None:
    token, _admin_id = _admin_setup(client, db_session)
    response = client.get(
        "/api/v1/circuits/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_status_change_endpoint(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    _substation_ids, voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    mothballed_status_id = (
        db_session.query(OperationalStatus).filter_by(code="MOTHBALLED").one().operational_status_id
    )

    create_response = client.post(
        "/api/v1/circuits", headers=headers, json=_circuit_payload(ref, voltage_yard_ids)
    )
    circuit_id = create_response.json()["circuit_id"]

    status_response = client.post(
        f"/api/v1/circuits/{circuit_id}/status",
        headers=headers,
        json={"operational_status_id": mothballed_status_id, "change_reason": "Planned outage"},
    )
    assert status_response.status_code == 200
    assert status_response.json()["operational_status_id"] == mothballed_status_id


def test_search_and_filter(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    _substation_ids, voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    client.post("/api/v1/circuits", headers=headers, json=_circuit_payload(ref, voltage_yard_ids))

    search_response = client.get("/api/v1/circuits?search=PKLG", headers=headers)
    assert search_response.status_code == 200
    assert search_response.json()["total"] == 1

    no_match_response = client.get("/api/v1/circuits?search=NOPE", headers=headers)
    assert no_match_response.status_code == 200
    assert no_match_response.json()["total"] == 0

    filter_response = client.get(
        f"/api/v1/circuits?voltage_level_id={ref['voltage_level_id']}", headers=headers
    )
    assert filter_response.status_code == 200
    assert filter_response.json()["total"] == 1


def test_no_delete_endpoint_exists(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    _substation_ids, voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    create_response = client.post(
        "/api/v1/circuits", headers=headers, json=_circuit_payload(ref, voltage_yard_ids)
    )
    circuit_id = create_response.json()["circuit_id"]

    response = client.delete(f"/api/v1/circuits/{circuit_id}", headers=headers)
    assert response.status_code == 405


# --- Substation Voltage Yards (Phase 3 UAT fix package; ADR-008) -----------------------


def test_list_voltage_yards_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/voltage-yards")
    assert response.status_code == 401


def test_create_voltage_yard_without_write_is_forbidden(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    _token, admin_id = _admin_setup(client, db_session)
    substation_ids, _voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    iam = IAMService(db_session)
    iam.create_user(
        username="viewer_only_2",
        display_name="Viewer Only 2",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    token = _login(client, "viewer_only_2", "correct-horse-battery")

    response = client.post(
        "/api/v1/voltage-yards",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "substation_id": substation_ids["PKLG"],
            "voltage_level_id": ref["second_voltage_level_id"],
        },
    )
    assert response.status_code == 403


def test_multi_voltage_substation_via_api(client: TestClient, db_session: Session) -> None:
    """docs/architecture/equipment-registry-module.md §7.5a's own example:
    a substation with both a 500kV-equivalent and a 132kV-equivalent yard,
    both independently selectable as circuit terminals."""
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    substation_ids, voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    create_yard_response = client.post(
        "/api/v1/voltage-yards",
        headers=headers,
        json={
            "substation_id": substation_ids["PKLG"],
            "voltage_level_id": ref["second_voltage_level_id"],
        },
    )
    assert create_yard_response.status_code == 201, create_yard_response.text
    second_yard = create_yard_response.json()
    assert second_yard["display_label"] == "PKLG — 132kV"

    list_response = client.get(
        f"/api/v1/voltage-yards?substation_id={substation_ids['PKLG']}", headers=headers
    )
    assert list_response.status_code == 200
    labels = {y["display_label"] for y in list_response.json()}
    assert labels == {"PKLG — 500kV", "PKLG — 132kV"}

    duplicate_response = client.post(
        "/api/v1/voltage-yards",
        headers=headers,
        json={
            "substation_id": substation_ids["PKLG"],
            "voltage_level_id": ref["second_voltage_level_id"],
        },
    )
    assert duplicate_response.status_code == 400
    duplicate_body = duplicate_response.json()
    assert duplicate_body["detail"]["code"] == "validation_error"
    # UAT regression: the message must be human-readable — "PKLG" and
    # "132kV", not the raw substation UUID and internal voltage_level_id
    # (e.g. "voltage level '4'", which gives no way to know what that
    # means).
    assert "PKLG" in duplicate_body["detail"]["message"]
    assert "132kV" in duplicate_body["detail"]["message"]
    assert str(ref["second_voltage_level_id"]) not in duplicate_body["detail"]["message"]

    # Rule 6 (yard-, not substation-, scoped uniqueness) still allows two
    # different substations' yards at the SAME (non-default) voltage level
    # on one circuit. (A circuit terminating twice at the same substation
    # via two DIFFERENT voltage levels is no longer constructible once rule
    # 6a requires every terminal to match the circuit's own voltage level —
    # see ADR-008's addendum; exercised separately below.)
    igbk_132kv_yard = client.post(
        "/api/v1/voltage-yards",
        headers=headers,
        json={
            "substation_id": substation_ids["IGBK"],
            "voltage_level_id": ref["second_voltage_level_id"],
        },
    ).json()

    circuit_payload = _circuit_payload(
        ref,
        voltage_yard_ids,
        voltage_level_id=ref["second_voltage_level_id"],
        terminals=[
            {"voltage_yard_id": second_yard["voltage_yard_id"], "breaker_number": "L1"},
            {"voltage_yard_id": igbk_132kv_yard["voltage_yard_id"], "breaker_number": "L2"},
        ],
    )
    circuit_response = client.post("/api/v1/circuits", headers=headers, json=circuit_payload)
    assert circuit_response.status_code == 201, circuit_response.text
    assert len(circuit_response.json()["terminals"]) == 2


# --- Terminal voltage-level guardrail (Phase 3 UAT follow-up; rule 6a) -------------------


def test_create_circuit_rejects_a_terminal_at_a_different_voltage_level(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    substation_ids, voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    mismatched_yard = client.post(
        "/api/v1/voltage-yards",
        headers=headers,
        json={
            "substation_id": substation_ids["IGBK"],
            "voltage_level_id": ref["second_voltage_level_id"],
        },
    ).json()

    payload = _circuit_payload(
        ref,
        voltage_yard_ids,
        terminals=[
            {"voltage_yard_id": voltage_yard_ids["PKLG"], "breaker_number": "L1"},
            {"voltage_yard_id": mismatched_yard["voltage_yard_id"], "breaker_number": "L2"},
        ],
    )
    response = client.post("/api/v1/circuits", headers=headers, json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["code"] == "validation_error"
    assert "132kV" in body["detail"]["message"]
    assert "500kV" in body["detail"]["message"]


def test_add_terminal_rejects_a_voltage_yard_at_a_different_voltage_level(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    substation_ids, voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    create_response = client.post(
        "/api/v1/circuits", headers=headers, json=_circuit_payload(ref, voltage_yard_ids)
    )
    circuit_id = create_response.json()["circuit_id"]

    third_substation = SubstationService(db_session).create_substation(
        mnemonic="NKST2",
        official_name="NKST2 Substation",
        region_id=ref["region_id"],
        state_id=ref["state_id"],
        grid_owner_id=ref["grid_owner_id"],
        operational_status_id=ref["operational_status_id"],
        psse_bus_number=None,
        latitude=None,
        longitude=None,
        commissioned_date=None,
        remarks=None,
        actor_user_id=admin_id,
    )
    mismatched_yard = EquipmentRegistryService(db_session).create_voltage_yard(
        substation_id=third_substation.substation_id,
        voltage_level_id=ref["second_voltage_level_id"],
        actor_user_id=admin_id,
    )
    db_session.commit()

    response = client.post(
        f"/api/v1/circuits/{circuit_id}/terminals",
        headers=headers,
        json={"voltage_yard_id": str(mismatched_yard.voltage_yard_id), "breaker_number": "N1"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


# --- SubstationVoltageYard metadata (Phase 3 UAT follow-up) ------------------------------


def test_create_voltage_yard_with_metadata(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    substation_ids, _voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    response = client.post(
        "/api/v1/voltage-yards",
        headers=headers,
        json={
            "substation_id": substation_ids["IGBK"],
            "voltage_level_id": ref["second_voltage_level_id"],
            "commissioning_date": "2020-06-01",
            "latitude": 3.140853,
            "longitude": 101.693207,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["commissioning_date"] == "2020-06-01"
    assert body["latitude"] == pytest.approx(3.140853)
    assert body["longitude"] == pytest.approx(101.693207)


def test_create_voltage_yard_with_latitude_but_no_longitude_returns_400(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    substation_ids, _voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    response = client.post(
        "/api/v1/voltage-yards",
        headers=headers,
        json={
            "substation_id": substation_ids["IGBK"],
            "voltage_level_id": ref["second_voltage_level_id"],
            "latitude": 3.14,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


def test_create_voltage_yard_with_out_of_range_latitude_returns_422(
    client: TestClient, db_session: Session
) -> None:
    """Range is enforced at the API DTO layer (Pydantic `Field(ge=-90,
    le=90)`) — a structural validation error (422), not a business-rule
    rejection (400)."""
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    substation_ids, _voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    response = client.post(
        "/api/v1/voltage-yards",
        headers=headers,
        json={
            "substation_id": substation_ids["IGBK"],
            "voltage_level_id": ref["second_voltage_level_id"],
            "latitude": 95.0,
            "longitude": 101.7,
        },
    )
    assert response.status_code == 422


def test_update_voltage_yard_metadata(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    _substation_ids, voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    response = client.patch(
        f"/api/v1/voltage-yards/{voltage_yard_ids['PKLG']}",
        headers=headers,
        json={"commissioning_date": "2021-03-15", "latitude": 3.0, "longitude": 101.5},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["commissioning_date"] == "2021-03-15"
    assert body["latitude"] == pytest.approx(3.0)
    assert body["longitude"] == pytest.approx(101.5)

    get_response = client.get(
        f"/api/v1/voltage-yards?substation_id={_substation_ids['PKLG']}", headers=headers
    )
    matching = next(
        y for y in get_response.json() if y["voltage_yard_id"] == voltage_yard_ids["PKLG"]
    )
    assert matching["commissioning_date"] == "2021-03-15"


def test_update_voltage_yard_without_write_is_forbidden(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    _token, admin_id = _admin_setup(client, db_session)
    _substation_ids, voltage_yard_ids = _create_substations_and_yards(db_session, ref, admin_id)

    iam = IAMService(db_session)
    iam.create_user(
        username="viewer_only_3",
        display_name="Viewer Only 3",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    token = _login(client, "viewer_only_3", "correct-horse-battery")

    response = client.patch(
        f"/api/v1/voltage-yards/{voltage_yard_ids['PKLG']}",
        headers={"Authorization": f"Bearer {token}"},
        json={"commissioning_date": "2021-03-15"},
    )
    assert response.status_code == 403


def test_update_unknown_voltage_yard_returns_400(client: TestClient, db_session: Session) -> None:
    token, _admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.patch(
        f"/api/v1/voltage-yards/{uuid.uuid4()}",
        headers=headers,
        json={"commissioning_date": "2021-03-15"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"
