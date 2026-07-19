"""API contract tests for the Sensitive Customer Registry's router —
exercises the full Router -> Service -> Repository stack through HTTP,
mirroring backend/tests/test_automatic_load_shedding_functionality_api.py's
pattern.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.equipment_registry.bootstrap import run_bootstrap as bootstrap_equipment_registry
from app.modules.equipment_registry.service import EquipmentRegistryService
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
from app.modules.sensitive_customer_registry.bootstrap import run_bootstrap as bootstrap_scr
from app.modules.sensitive_customer_registry.seed import run_seed as seed_scr_reference_data
from app.modules.substation_registry.bootstrap import run_bootstrap as bootstrap_substations
from app.modules.substation_registry.service import SubstationService
from app.reference_data.models import (
    GmZone,
    GridOwner,
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
        "lv_voltage_level_id": db_session.query(VoltageLevel)
        .filter_by(label="132kV")
        .one()
        .voltage_level_id,
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
    bootstrap_scr(db_session)
    token = _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)
    return token, admin.user_id


def _seed_scr_reference_data(db_session: Session) -> dict[str, int]:
    seed_scr_reference_data(db_session)
    db_session.commit()
    from app.modules.sensitive_customer_registry.models import (
        FacilitySector,
        SensitivityClassification,
    )

    return {
        "healthcare_sector_id": db_session.query(FacilitySector)
        .filter_by(code="HEALTHCARE")
        .one()
        .id,
        "high_classification_id": db_session.query(SensitivityClassification)
        .filter_by(code="HIGH")
        .one()
        .id,
    }


def _create_transformer_terminal(
    db_session: Session, ref: dict[str, int], actor_user_id: uuid.UUID
) -> uuid.UUID:
    substation_service = SubstationService(db_session)
    equipment_service = EquipmentRegistryService(db_session)

    substation = substation_service.create_substation(
        mnemonic="PKLG",
        official_name="Pekan Lama Substation",
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
    hv_yard = equipment_service.create_voltage_yard(
        substation_id=substation.substation_id,
        voltage_level_id=ref["voltage_level_id"],
        actor_user_id=actor_user_id,
    )
    lv_yard = equipment_service.create_voltage_yard(
        substation_id=substation.substation_id,
        voltage_level_id=ref["lv_voltage_level_id"],
        actor_user_id=actor_user_id,
    )
    transformer = equipment_service.create_transformer(
        substation_id=substation.substation_id,
        transformer_number="1",
        hv_switchyard_id=hv_yard.voltage_yard_id,
        hv_breaker_number="T11",
        lv_switchyard_id=lv_yard.voltage_yard_id,
        lv_breaker_number="T12",
        capacity_mva=150,
        commissioning_date=None,
        operational_status_id=ref["operational_status_id"],
        transformer_type=None,
        manufacturer=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = equipment_service.get_transformer(transformer.transformer_id)
    assert detail is not None
    return next(t.transformer_terminal_id for t in detail.terminals if t.side == "HV")


# --- Authentication --------------------------------------------------------------------


def test_list_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/sensitive-customer-registry/facilities")
    assert response.status_code == 401


def test_create_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        json={"name": "Hospital", "facility_sector_id": 1, "sensitivity_classification_id": 1},
    )
    assert response.status_code == 401


# --- Permission enforcement (Correction 1 — Administrator-only mutation) ---------------


def test_read_requires_read_permission_not_open_to_any_authenticated_user(
    client: TestClient, db_session: Session
) -> None:
    """Unlike ALSF, `.read` is gated (module document §15) — a bare
    authenticated user with no permission grant must be rejected."""
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
        "/api/v1/sensitive-customer-registry/facilities",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_engineer_cannot_create_facility(client: TestClient, db_session: Session) -> None:
    """The corrected permission model's central regression test — an
    Engineer holding only `sensitive_customer_registry.read` must be
    rejected from every mutation endpoint."""
    bootstrap_iam(db_session)
    bootstrap_scr(db_session)
    iam = IAMService(db_session)
    engineer_role = next(r for r in iam.list_roles() if r.name == "Engineer")
    user = iam.create_user(
        username="engineer1",
        display_name="Engineer One",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    iam.assign_role_to_user(user_id=user.user_id, role_id=engineer_role.role_id, actor_user_id=None)
    db_session.commit()
    token = _login(client, "engineer1", "correct-horse-battery")

    response = client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Hospital", "facility_sector_id": 1, "sensitivity_classification_id": 1},
    )
    assert response.status_code == 403


def test_engineer_can_read_list_audit_batch_lookup_and_summary(
    client: TestClient, db_session: Session
) -> None:
    """Full read-capability matrix for Engineer (task's own permission
    table): list, audit history, lookup/batch-lookup, and summary metrics
    are all Yes for Engineer — every read endpoint must accept the same
    Engineer session."""
    token, admin_id = _admin_setup(client, db_session)
    admin_headers = {"Authorization": f"Bearer {token}"}
    scr_ref = _seed_scr_reference_data(db_session)
    create_response = client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        headers=admin_headers,
        json={
            "name": "Hospital Kuala Lumpur",
            "facility_sector_id": scr_ref["healthcare_sector_id"],
            "sensitivity_classification_id": scr_ref["high_classification_id"],
        },
    )
    facility_id = create_response.json()["id"]

    iam = IAMService(db_session)
    engineer_role = next(r for r in iam.list_roles() if r.name == "Engineer")
    user = iam.create_user(
        username="engineer1",
        display_name="Engineer One",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    iam.assign_role_to_user(user_id=user.user_id, role_id=engineer_role.role_id, actor_user_id=None)
    db_session.commit()
    engineer_headers = {
        "Authorization": f"Bearer {_login(client, 'engineer1', 'correct-horse-battery')}"
    }

    assert (
        client.get(
            "/api/v1/sensitive-customer-registry/facilities", headers=engineer_headers
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"/api/v1/sensitive-customer-registry/facilities/{facility_id}/audit-log",
            headers=engineer_headers,
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/sensitive-customer-registry/facilities/batch-lookup",
            headers=engineer_headers,
            json={"transformer_terminal_ids": []},
        ).status_code
        == 200
    )
    assert (
        client.get(
            "/api/v1/sensitive-customer-registry/facilities/summary", headers=engineer_headers
        ).status_code
        == 200
    )


def test_engineer_cannot_perform_lifecycle_actions(client: TestClient, db_session: Session) -> None:
    """Archive/reactivate/entered-in-error are Administrator-only (task's
    own permission table) — verified at the API boundary, not merely
    inferred from `create` sharing the same permission code."""
    token, admin_id = _admin_setup(client, db_session)
    admin_headers = {"Authorization": f"Bearer {token}"}
    scr_ref = _seed_scr_reference_data(db_session)
    create_response = client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        headers=admin_headers,
        json={
            "name": "Hospital Kuala Lumpur",
            "facility_sector_id": scr_ref["healthcare_sector_id"],
            "sensitivity_classification_id": scr_ref["high_classification_id"],
        },
    )
    facility_id = create_response.json()["id"]

    iam = IAMService(db_session)
    engineer_role = next(r for r in iam.list_roles() if r.name == "Engineer")
    user = iam.create_user(
        username="engineer1",
        display_name="Engineer One",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    iam.assign_role_to_user(user_id=user.user_id, role_id=engineer_role.role_id, actor_user_id=None)
    db_session.commit()
    engineer_headers = {
        "Authorization": f"Bearer {_login(client, 'engineer1', 'correct-horse-battery')}"
    }

    for action in ("archive", "reactivate", "entered-in-error"):
        response = client.post(
            f"/api/v1/sensitive-customer-registry/facilities/{facility_id}/{action}",
            headers=engineer_headers,
            json={"change_reason": "Attempted by Engineer"},
        )
        assert response.status_code == 403, f"{action} should be Administrator-only"

    update_response = client.patch(
        f"/api/v1/sensitive-customer-registry/facilities/{facility_id}",
        headers=engineer_headers,
        json={"name": "Attempted rename"},
    )
    assert update_response.status_code == 403


def test_create_against_unseeded_reference_data_is_400(
    client: TestClient, db_session: Session
) -> None:
    token, _admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        headers=headers,
        json={"name": "Hospital", "facility_sector_id": 1, "sensitivity_classification_id": 1},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


# --- Full CRUD + lifecycle flow ---------------------------------------------------------


def test_full_crud_and_lifecycle_flow(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    scr_ref = _seed_scr_reference_data(db_session)
    terminal_id = _create_transformer_terminal(db_session, ref, admin_id)

    create_response = client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        headers=headers,
        json={
            "name": "Hospital Kuala Lumpur",
            "facility_sector_id": scr_ref["healthcare_sector_id"],
            "sensitivity_classification_id": scr_ref["high_classification_id"],
            "transformer_terminal_ids": [str(terminal_id)],
        },
    )
    assert create_response.status_code == 201, create_response.text
    body = create_response.json()
    facility_id = body["id"]
    assert body["lifecycle_status"] == "ACTIVE"
    assert body["transformer_terminal_resolution"] == "RESOLVED"
    assert len(body["transformer_terminals"]) == 1
    assert body["transformer_terminals"][0]["substation_mnemonic"] == "PKLG"

    get_response = client.get(
        f"/api/v1/sensitive-customer-registry/facilities/{facility_id}", headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "Hospital Kuala Lumpur"

    list_response = client.get("/api/v1/sensitive-customer-registry/facilities", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    audit_response = client.get(
        f"/api/v1/sensitive-customer-registry/facilities/{facility_id}/audit-log", headers=headers
    )
    assert audit_response.status_code == 200
    assert audit_response.json()["total"] == 1  # created

    archive_response = client.post(
        f"/api/v1/sensitive-customer-registry/facilities/{facility_id}/archive",
        headers=headers,
        json={"change_reason": "Facility closed"},
    )
    assert archive_response.status_code == 200
    assert archive_response.json()["lifecycle_status"] == "ARCHIVED"

    reactivate_response = client.post(
        f"/api/v1/sensitive-customer-registry/facilities/{facility_id}/reactivate",
        headers=headers,
        json={"change_reason": "Facility reopened"},
    )
    assert reactivate_response.status_code == 200
    assert reactivate_response.json()["lifecycle_status"] == "ACTIVE"

    eie_response = client.post(
        f"/api/v1/sensitive-customer-registry/facilities/{facility_id}/entered-in-error",
        headers=headers,
        json={"change_reason": "Duplicate record"},
    )
    assert eie_response.status_code == 200
    assert eie_response.json()["lifecycle_status"] == "ENTERED_IN_ERROR"


def test_archive_without_reason_is_400(client: TestClient, db_session: Session) -> None:
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    scr_ref = _seed_scr_reference_data(db_session)

    create_response = client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        headers=headers,
        json={
            "name": "Hospital Kuala Lumpur",
            "facility_sector_id": scr_ref["healthcare_sector_id"],
            "sensitivity_classification_id": scr_ref["high_classification_id"],
        },
    )
    facility_id = create_response.json()["id"]

    response = client.post(
        f"/api/v1/sensitive-customer-registry/facilities/{facility_id}/archive",
        headers=headers,
        json={},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


def test_entered_in_error_then_further_transition_is_400(
    client: TestClient, db_session: Session
) -> None:
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    scr_ref = _seed_scr_reference_data(db_session)

    create_response = client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        headers=headers,
        json={
            "name": "Hospital Kuala Lumpur",
            "facility_sector_id": scr_ref["healthcare_sector_id"],
            "sensitivity_classification_id": scr_ref["high_classification_id"],
        },
    )
    facility_id = create_response.json()["id"]

    first = client.post(
        f"/api/v1/sensitive-customer-registry/facilities/{facility_id}/entered-in-error",
        headers=headers,
        json={"change_reason": "Duplicate record"},
    )
    assert first.status_code == 200

    second = client.post(
        f"/api/v1/sensitive-customer-registry/facilities/{facility_id}/archive",
        headers=headers,
        json={"change_reason": "Attempted archive"},
    )
    assert second.status_code == 400
    assert second.json()["detail"]["code"] == "validation_error"


def test_set_terminals_without_reason_is_400(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    scr_ref = _seed_scr_reference_data(db_session)
    terminal_id = _create_transformer_terminal(db_session, ref, admin_id)

    create_response = client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        headers=headers,
        json={
            "name": "Hospital Kuala Lumpur",
            "facility_sector_id": scr_ref["healthcare_sector_id"],
            "sensitivity_classification_id": scr_ref["high_classification_id"],
        },
    )
    facility_id = create_response.json()["id"]

    response = client.put(
        f"/api/v1/sensitive-customer-registry/facilities/{facility_id}/terminals",
        headers=headers,
        json={"transformer_terminal_ids": [str(terminal_id)]},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


def test_set_terminals_with_reason_succeeds_and_is_audited(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    scr_ref = _seed_scr_reference_data(db_session)
    terminal_id = _create_transformer_terminal(db_session, ref, admin_id)

    create_response = client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        headers=headers,
        json={
            "name": "Hospital Kuala Lumpur",
            "facility_sector_id": scr_ref["healthcare_sector_id"],
            "sensitivity_classification_id": scr_ref["high_classification_id"],
        },
    )
    facility_id = create_response.json()["id"]

    response = client.put(
        f"/api/v1/sensitive-customer-registry/facilities/{facility_id}/terminals",
        headers=headers,
        json={
            "transformer_terminal_ids": [str(terminal_id)],
            "change_reason": "Supply point confirmed after site survey",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["transformer_terminals"]) == 1
    assert body["transformer_terminals"][0]["transformer_terminal_id"] == str(terminal_id)
    assert body["transformer_terminal_resolution"] == "RESOLVED"

    audit_response = client.get(
        f"/api/v1/sensitive-customer-registry/facilities/{facility_id}/audit-log", headers=headers
    )
    entries = audit_response.json()["items"]
    addition = next(
        e
        for e in entries
        if e["field_name"] == "transformer_terminal_id" and e["new_value"] == str(terminal_id)
    )
    assert addition["change_reason"] == "Supply point confirmed after site survey"


def test_engineer_cannot_set_terminals(client: TestClient, db_session: Session) -> None:
    token, admin_id = _admin_setup(client, db_session)
    admin_headers = {"Authorization": f"Bearer {token}"}
    scr_ref = _seed_scr_reference_data(db_session)
    create_response = client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        headers=admin_headers,
        json={
            "name": "Hospital Kuala Lumpur",
            "facility_sector_id": scr_ref["healthcare_sector_id"],
            "sensitivity_classification_id": scr_ref["high_classification_id"],
        },
    )
    facility_id = create_response.json()["id"]

    iam = IAMService(db_session)
    engineer_role = next(r for r in iam.list_roles() if r.name == "Engineer")
    user = iam.create_user(
        username="engineer1",
        display_name="Engineer One",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    iam.assign_role_to_user(user_id=user.user_id, role_id=engineer_role.role_id, actor_user_id=None)
    db_session.commit()
    engineer_headers = {
        "Authorization": f"Bearer {_login(client, 'engineer1', 'correct-horse-battery')}"
    }

    response = client.put(
        f"/api/v1/sensitive-customer-registry/facilities/{facility_id}/terminals",
        headers=engineer_headers,
        json={"transformer_terminal_ids": [], "change_reason": "Attempted by Engineer"},
    )
    assert response.status_code == 403


def test_multiple_facilities_may_share_one_terminal_via_api(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    scr_ref = _seed_scr_reference_data(db_session)
    terminal_id = _create_transformer_terminal(db_session, ref, admin_id)

    for name in ("Hospital Kuala Lumpur", "Adjacent Government Building"):
        response = client.post(
            "/api/v1/sensitive-customer-registry/facilities",
            headers=headers,
            json={
                "name": name,
                "facility_sector_id": scr_ref["healthcare_sector_id"],
                "sensitivity_classification_id": scr_ref["high_classification_id"],
                "transformer_terminal_ids": [str(terminal_id)],
            },
        )
        assert response.status_code == 201

    list_response = client.get("/api/v1/sensitive-customer-registry/facilities", headers=headers)
    assert list_response.json()["total"] == 2


def test_facility_may_be_created_with_multiple_terminals_via_api(
    client: TestClient, db_session: Session
) -> None:
    """ADR-013 — the Project-Owner-approved refinement: a facility may be
    associated with more than one currently active Transformer Terminal."""
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    scr_ref = _seed_scr_reference_data(db_session)
    equipment_service = EquipmentRegistryService(db_session)
    substation_service = SubstationService(db_session)

    first_terminal_id = _create_transformer_terminal(db_session, ref, admin_id)
    # A second, distinct transformer at a new substation — reuses the
    # helper's own substation/transformer creation for a genuinely
    # different terminal id.
    substation = substation_service.create_substation(
        mnemonic="SGBK",
        official_name="Sungai Buloh Substation",
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
        actor_user_id=admin_id,
    )
    hv_yard = equipment_service.create_voltage_yard(
        substation_id=substation.substation_id,
        voltage_level_id=ref["voltage_level_id"],
        actor_user_id=admin_id,
    )
    lv_yard = equipment_service.create_voltage_yard(
        substation_id=substation.substation_id,
        voltage_level_id=ref["lv_voltage_level_id"],
        actor_user_id=admin_id,
    )
    transformer = equipment_service.create_transformer(
        substation_id=substation.substation_id,
        transformer_number="1",
        hv_switchyard_id=hv_yard.voltage_yard_id,
        hv_breaker_number="T11",
        lv_switchyard_id=lv_yard.voltage_yard_id,
        lv_breaker_number="T12",
        capacity_mva=150,
        commissioning_date=None,
        operational_status_id=ref["operational_status_id"],
        transformer_type=None,
        manufacturer=None,
        remarks=None,
        actor_user_id=admin_id,
    )
    db_session.commit()
    detail = equipment_service.get_transformer(transformer.transformer_id)
    assert detail is not None
    second_terminal_id = next(t.transformer_terminal_id for t in detail.terminals if t.side == "HV")

    create_response = client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        headers=headers,
        json={
            "name": "Dual-Fed Hospital",
            "facility_sector_id": scr_ref["healthcare_sector_id"],
            "sensitivity_classification_id": scr_ref["high_classification_id"],
            "transformer_terminal_ids": [str(first_terminal_id), str(second_terminal_id)],
        },
    )
    assert create_response.status_code == 201, create_response.text
    body = create_response.json()
    associated_ids = {t["transformer_terminal_id"] for t in body["transformer_terminals"]}
    assert associated_ids == {str(first_terminal_id), str(second_terminal_id)}
    assert body["transformer_terminal_resolution"] == "RESOLVED"


def test_batch_lookup_endpoint(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    scr_ref = _seed_scr_reference_data(db_session)
    terminal_id = _create_transformer_terminal(db_session, ref, admin_id)

    client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        headers=headers,
        json={
            "name": "Hospital Kuala Lumpur",
            "facility_sector_id": scr_ref["healthcare_sector_id"],
            "sensitivity_classification_id": scr_ref["high_classification_id"],
            "transformer_terminal_ids": [str(terminal_id)],
        },
    )

    unknown_id = str(uuid.uuid4())
    response = client.post(
        "/api/v1/sensitive-customer-registry/facilities/batch-lookup",
        headers=headers,
        json={"transformer_terminal_ids": [str(terminal_id), unknown_id]},
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results[str(terminal_id)]) == 1
    assert results[unknown_id] == []


def test_batch_lookup_deduplicates_repeated_terminal_ids(
    client: TestClient, db_session: Session
) -> None:
    """A batch request listing the same Transformer Terminal ID more than
    once must behave deterministically — one key in the response, still
    reflecting every Active facility on that terminal, never a duplicated
    or inflated result."""
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    scr_ref = _seed_scr_reference_data(db_session)
    terminal_id = _create_transformer_terminal(db_session, ref, admin_id)

    client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        headers=headers,
        json={
            "name": "Hospital Kuala Lumpur",
            "facility_sector_id": scr_ref["healthcare_sector_id"],
            "sensitivity_classification_id": scr_ref["high_classification_id"],
            "transformer_terminal_ids": [str(terminal_id)],
        },
    )

    response = client.post(
        "/api/v1/sensitive-customer-registry/facilities/batch-lookup",
        headers=headers,
        json={"transformer_terminal_ids": [str(terminal_id), str(terminal_id), str(terminal_id)]},
    )
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert len(results[str(terminal_id)]) == 1


def test_batch_lookup_rejects_oversized_request(client: TestClient, db_session: Session) -> None:
    """The batch-lookup request body is bounded (2000 entries) — a
    pathologically large list is rejected as a 422 request-validation
    error before ever reaching the service layer."""
    token, _admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    too_many = [str(uuid.uuid4()) for _ in range(2001)]
    response = client.post(
        "/api/v1/sensitive-customer-registry/facilities/batch-lookup",
        headers=headers,
        json={"transformer_terminal_ids": too_many},
    )
    assert response.status_code == 422


def test_batch_lookup_empty_list_returns_empty_mapping(
    client: TestClient, db_session: Session
) -> None:
    """An empty batch request is a legitimate, non-exceptional call — it
    returns `200` with an empty mapping, not a validation error."""
    token, _admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/sensitive-customer-registry/facilities/batch-lookup",
        headers=headers,
        json={"transformer_terminal_ids": []},
    )
    assert response.status_code == 200
    assert response.json()["results"] == {}


def test_summary_endpoint(client: TestClient, db_session: Session) -> None:
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    scr_ref = _seed_scr_reference_data(db_session)

    client.post(
        "/api/v1/sensitive-customer-registry/facilities",
        headers=headers,
        json={
            "name": "Hospital Kuala Lumpur",
            "facility_sector_id": scr_ref["healthcare_sector_id"],
            "sensitivity_classification_id": scr_ref["high_classification_id"],
        },
    )

    response = client.get("/api/v1/sensitive-customer-registry/facilities/summary", headers=headers)
    assert response.status_code == 200
    assert response.json()["active_count"] == 1


def test_reference_data_admin_requires_manage_permission_not_write(
    client: TestClient, db_session: Session
) -> None:
    """`.write` alone (facility mutation) must not grant reference-data
    administration — the two are deliberately separate permissions."""
    bootstrap_iam(db_session)
    bootstrap_scr(db_session)
    iam = IAMService(db_session)
    user = iam.create_user(
        username="write_only",
        display_name="Write Only",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    role = iam.create_role(name="Facility Writer Only (test)", description=None, actor_user_id=None)
    iam.grant_permission_to_role(
        role_id=role.role_id,
        permission_id="sensitive_customer_registry.write",
        actor_user_id=None,
    )
    iam.assign_role_to_user(user_id=user.user_id, role_id=role.role_id, actor_user_id=None)
    db_session.commit()
    token = _login(client, "write_only", "correct-horse-battery")

    response = client.post(
        "/api/v1/sensitive-customer-registry/reference-data/facility-sectors",
        headers={"Authorization": f"Bearer {token}"},
        json={"code": "NEW_SECTOR", "label": "New Sector"},
    )
    assert response.status_code == 403


def test_reference_data_no_delete_endpoint_exists(client: TestClient, db_session: Session) -> None:
    token, _admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    _seed_scr_reference_data(db_session)

    response = client.delete(
        "/api/v1/sensitive-customer-registry/reference-data/facility-sectors/1", headers=headers
    )
    assert response.status_code in (404, 405)


def test_facility_sector_administration_flow(client: TestClient, db_session: Session) -> None:
    token, _admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    _seed_scr_reference_data(db_session)

    create_response = client.post(
        "/api/v1/sensitive-customer-registry/reference-data/facility-sectors",
        headers=headers,
        json={"code": "EDUCATION", "label": "Education", "sort_order": 9},
    )
    assert create_response.status_code == 201
    sector_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/sensitive-customer-registry/reference-data/facility-sectors/{sector_id}",
        headers=headers,
        json={"label": "Education & Training", "is_active": True},
    )
    assert update_response.status_code == 200
    assert update_response.json()["label"] == "Education & Training"

    list_response = client.get(
        "/api/v1/sensitive-customer-registry/reference-data/facility-sectors", headers=headers
    )
    assert list_response.status_code == 200
    assert any(s["code"] == "EDUCATION" for s in list_response.json())
