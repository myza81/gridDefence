"""API contract tests for Substation Registry's router —
docs/architecture/substation-registry.md §13, CLAUDE.md A9/A11. Exercises
the full Router -> Service -> Repository stack through HTTP.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
from app.modules.substation_registry.bootstrap import run_bootstrap as bootstrap_registry
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
        "region_id": db_session.query(Region).filter_by(code="NORTH").one().region_id,
        "gm_zone_id": db_session.query(GmZone).filter_by(code="ALOR_SETAR").one().gm_zone_id,
        "state_id": db_session.query(State).filter_by(code="SEL").one().state_id,
        "grid_owner_id": db_session.query(GridOwner).filter_by(code="TNB").one().grid_owner_id,
        "operational_status_id": db_session.query(OperationalStatus)
        .filter_by(code="ACTIVE")
        .one()
        .operational_status_id,
    }


def _admin_token(client: TestClient, db_session: Session) -> str:
    settings = get_settings()
    bootstrap_iam(db_session)
    bootstrap_registry(db_session)
    return _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)


def test_create_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/substations", json={})
    assert response.status_code == 401


def test_list_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/substations")
    assert response.status_code == 401


def test_create_without_substation_registry_write_is_forbidden(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
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
        "/api/v1/substations",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "mnemonic": "SUB1",
            "official_name": "Substation One",
            **ref,
        },
    )
    assert response.status_code == 403


def test_any_authenticated_user_may_list_and_read_without_substation_registry_read(
    client: TestClient, db_session: Session
) -> None:
    """substation-registry.md §10: read is open to all authenticated users
    — no permission grant beyond authentication is required."""
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

    response = client.get("/api/v1/substations", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_full_create_read_update_flow(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/substations",
        headers=headers,
        json={
            "mnemonic": "SUB1",
            "official_name": "Substation One",
            **ref,
        },
    )
    assert create_response.status_code == 201, create_response.text
    body = create_response.json()
    assert body["mnemonic"] == "SUB1"
    assert body["created_by"]["username"] == get_settings().bootstrap_admin_username
    substation_id = body["substation_id"]

    get_response = client.get(f"/api/v1/substations/{substation_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["official_name"] == "Substation One"

    update_response = client.patch(
        f"/api/v1/substations/{substation_id}",
        headers=headers,
        json={"mnemonic": "SUB1NEW"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["mnemonic"] == "SUB1NEW"

    aliases_response = client.get(f"/api/v1/substations/{substation_id}/aliases", headers=headers)
    assert aliases_response.status_code == 200
    assert aliases_response.json()[0]["alias_mnemonic"] == "SUB1"

    audit_response = client.get(f"/api/v1/substations/{substation_id}/audit-log", headers=headers)
    assert audit_response.status_code == 200
    assert audit_response.json()["total"] == 1
    assert audit_response.json()["items"][0]["field_name"] == "mnemonic"


def test_duplicate_mnemonic_returns_400(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"mnemonic": "DUP1", "official_name": "First", **ref}
    first = client.post("/api/v1/substations", headers=headers, json=payload)
    assert first.status_code == 201

    payload["official_name"] = "Second"
    second = client.post("/api/v1/substations", headers=headers, json=payload)
    assert second.status_code == 400
    assert second.json()["detail"]["code"] == "validation_error"


def test_rename_back_to_own_historical_mnemonic_is_allowed(
    client: TestClient, db_session: Session
) -> None:
    """UAT regression: SIDS -> SIDST -> SIDS on the same substation must
    succeed. Previously rejected because the historical-mnemonic check did
    not distinguish "owned by this substation" from "owned by any
    substation"."""
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/substations",
        headers=headers,
        json={"mnemonic": "SIDS", "official_name": "Sungai Sidas", **ref},
    )
    assert create_response.status_code == 201, create_response.text
    substation_id = create_response.json()["substation_id"]

    rename_away = client.patch(
        f"/api/v1/substations/{substation_id}", headers=headers, json={"mnemonic": "SIDST"}
    )
    assert rename_away.status_code == 200, rename_away.text

    rename_back = client.patch(
        f"/api/v1/substations/{substation_id}", headers=headers, json={"mnemonic": "SIDS"}
    )
    assert rename_back.status_code == 200, rename_back.text
    assert rename_back.json()["mnemonic"] == "SIDS"


def test_another_substation_cannot_claim_a_historical_mnemonic_returns_400(
    client: TestClient, db_session: Session
) -> None:
    """UAT regression: Substation A's retired mnemonic SIDS must remain
    permanently reserved to A — Substation B may never claim it, even
    though A no longer currently uses it."""
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    substation_a = client.post(
        "/api/v1/substations",
        headers=headers,
        json={"mnemonic": "SIDS", "official_name": "Substation A", **ref},
    )
    assert substation_a.status_code == 201
    client.patch(
        f"/api/v1/substations/{substation_a.json()['substation_id']}",
        headers=headers,
        json={"mnemonic": "SIDST"},
    )

    substation_b = client.post(
        "/api/v1/substations",
        headers=headers,
        json={"mnemonic": "SIDS", "official_name": "Substation B", **ref},
    )
    assert substation_b.status_code == 400
    assert substation_b.json()["detail"]["code"] == "validation_error"


def test_get_unknown_substation_returns_404(client: TestClient, db_session: Session) -> None:
    token = _admin_token(client, db_session)
    response = client.get(
        "/api/v1/substations/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_status_change_endpoint_enforces_transition_legality(
    client: TestClient, db_session: Session
) -> None:
    """Per ADR-014: a Substation may only start as Under Construction or
    Active; Under Construction -> Decommissioned directly, and Active ->
    Under Construction, are both illegal; Under Construction -> Active is
    a legal transition."""
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    decommissioned_status_id = (
        db_session.query(OperationalStatus)
        .filter_by(code="DECOMMISSIONED")
        .one()
        .operational_status_id
    )
    under_construction_status_id = (
        db_session.query(OperationalStatus)
        .filter_by(code="UNDER_CONSTRUCTION")
        .one()
        .operational_status_id
    )
    active_status_id = ref["operational_status_id"]

    create_response = client.post(
        "/api/v1/substations",
        headers=headers,
        json={
            "mnemonic": "SUB2",
            "official_name": "Substation Two",
            **{**ref, "operational_status_id": under_construction_status_id},
        },
    )
    assert create_response.status_code == 201
    substation_id = create_response.json()["substation_id"]

    illegal_decommission_response = client.post(
        f"/api/v1/substations/{substation_id}/status",
        headers=headers,
        json={"operational_status_id": decommissioned_status_id},
    )
    assert illegal_decommission_response.status_code == 400

    legal_response = client.post(
        f"/api/v1/substations/{substation_id}/status",
        headers=headers,
        json={"operational_status_id": active_status_id, "change_reason": "Commissioned"},
    )
    assert legal_response.status_code == 200
    assert legal_response.json()["operational_status_id"] == active_status_id

    illegal_return_to_under_construction_response = client.post(
        f"/api/v1/substations/{substation_id}/status",
        headers=headers,
        json={"operational_status_id": under_construction_status_id},
    )
    assert illegal_return_to_under_construction_response.status_code == 400


def test_no_delete_endpoint_exists(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/substations",
        headers=headers,
        json={"mnemonic": "SUB3", "official_name": "Substation Three", **ref},
    )
    substation_id = create_response.json()["substation_id"]

    response = client.delete(f"/api/v1/substations/{substation_id}", headers=headers)
    assert response.status_code == 405


# --- GM Zone (organizational metadata, independent of Region) -------------------------


def test_create_substation_without_gm_zone_returns_400(
    client: TestClient, db_session: Session
) -> None:
    """GM Zone is unconditionally required, exactly like region_id/
    state_id/grid_owner_id — a request missing it is rejected regardless
    of the target operational status."""
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    payload = {"mnemonic": "GMZ1", "official_name": "GM Zone Test One", **ref}
    del payload["gm_zone_id"]
    response = client.post("/api/v1/substations", headers=headers, json=payload)
    assert response.status_code == 422


def test_list_substations_filters_by_gm_zone(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    other_gm_zone_id = (
        db_session.query(GmZone).filter(GmZone.gm_zone_id != ref["gm_zone_id"]).first().gm_zone_id
    )

    client.post(
        "/api/v1/substations",
        headers=headers,
        json={"mnemonic": "GMZ3", "official_name": "GM Zone Test Three", **ref},
    )
    client.post(
        "/api/v1/substations",
        headers=headers,
        json={
            "mnemonic": "GMZ4",
            "official_name": "GM Zone Test Four",
            **{**ref, "gm_zone_id": other_gm_zone_id},
        },
    )

    response = client.get(f"/api/v1/substations?gm_zone_id={ref['gm_zone_id']}", headers=headers)
    assert response.status_code == 200
    mnemonics = {item["mnemonic"] for item in response.json()["items"]}
    assert "GMZ3" in mnemonics
    assert "GMZ4" not in mnemonics


def test_gm_zone_is_editable_via_update_and_audited(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    other_gm_zone_id = (
        db_session.query(GmZone).filter(GmZone.gm_zone_id != ref["gm_zone_id"]).first().gm_zone_id
    )

    create_response = client.post(
        "/api/v1/substations",
        headers=headers,
        json={"mnemonic": "GMZ5", "official_name": "GM Zone Test Five", **ref},
    )
    substation_id = create_response.json()["substation_id"]

    update_response = client.patch(
        f"/api/v1/substations/{substation_id}",
        headers=headers,
        json={"gm_zone_id": other_gm_zone_id},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["gm_zone_id"] == other_gm_zone_id

    audit_response = client.get(f"/api/v1/substations/{substation_id}/audit-log", headers=headers)
    assert audit_response.status_code == 200
    entries = audit_response.json()["items"]
    assert any(e["field_name"] == "gm_zone_id" for e in entries)


def test_gm_zone_id_null_in_update_is_treated_as_not_supplied(
    client: TestClient, db_session: Session
) -> None:
    """gm_zone_id can no longer be legally cleared — `null` in an update
    payload is treated exactly like an omitted field (leaves the current
    value unchanged), mirroring region_id/state_id/grid_owner_id's own
    long-standing behaviour for the same reason."""
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/substations",
        headers=headers,
        json={"mnemonic": "GMZ6", "official_name": "GM Zone Test Six", **ref},
    )
    substation_id = create_response.json()["substation_id"]

    response = client.patch(
        f"/api/v1/substations/{substation_id}", headers=headers, json={"gm_zone_id": None}
    )
    assert response.status_code == 200, response.text
    assert response.json()["gm_zone_id"] == ref["gm_zone_id"]


# --- Region / State / Grid Owner editing (UAT: previously frontend-only gap) ----------


def test_region_is_editable_via_update_and_audited(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    other_region_id = (
        db_session.query(Region).filter(Region.region_id != ref["region_id"]).first().region_id
    )

    create_response = client.post(
        "/api/v1/substations",
        headers=headers,
        json={"mnemonic": "ORG1", "official_name": "Organizational Metadata Test One", **ref},
    )
    substation_id = create_response.json()["substation_id"]

    update_response = client.patch(
        f"/api/v1/substations/{substation_id}",
        headers=headers,
        json={"region_id": other_region_id},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["region_id"] == other_region_id

    audit_response = client.get(f"/api/v1/substations/{substation_id}/audit-log", headers=headers)
    entries = audit_response.json()["items"]
    assert any(e["field_name"] == "region_id" for e in entries)


def test_state_is_editable_via_update_and_audited(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    other_state_id = (
        db_session.query(State).filter(State.state_id != ref["state_id"]).first().state_id
    )

    create_response = client.post(
        "/api/v1/substations",
        headers=headers,
        json={"mnemonic": "ORG2", "official_name": "Organizational Metadata Test Two", **ref},
    )
    substation_id = create_response.json()["substation_id"]

    update_response = client.patch(
        f"/api/v1/substations/{substation_id}",
        headers=headers,
        json={"state_id": other_state_id},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["state_id"] == other_state_id

    audit_response = client.get(f"/api/v1/substations/{substation_id}/audit-log", headers=headers)
    entries = audit_response.json()["items"]
    assert any(e["field_name"] == "state_id" for e in entries)


def test_grid_owner_is_editable_via_update_and_audited(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    other_grid_owner_id = (
        db_session.query(GridOwner)
        .filter(GridOwner.grid_owner_id != ref["grid_owner_id"])
        .first()
        .grid_owner_id
    )

    create_response = client.post(
        "/api/v1/substations",
        headers=headers,
        json={"mnemonic": "ORG3", "official_name": "Organizational Metadata Test Three", **ref},
    )
    substation_id = create_response.json()["substation_id"]

    update_response = client.patch(
        f"/api/v1/substations/{substation_id}",
        headers=headers,
        json={"grid_owner_id": other_grid_owner_id},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["grid_owner_id"] == other_grid_owner_id

    audit_response = client.get(f"/api/v1/substations/{substation_id}/audit-log", headers=headers)
    entries = audit_response.json()["items"]
    assert any(e["field_name"] == "grid_owner_id" for e in entries)


def test_region_state_grid_owner_and_gm_zone_are_independently_editable_via_api(
    client: TestClient, db_session: Session
) -> None:
    """All four organizational fields may change in one request, each
    audited separately — no derivation or coupling between them."""
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    other_region_id = (
        db_session.query(Region).filter(Region.region_id != ref["region_id"]).first().region_id
    )
    other_gm_zone_id = (
        db_session.query(GmZone).filter(GmZone.gm_zone_id != ref["gm_zone_id"]).first().gm_zone_id
    )
    other_state_id = (
        db_session.query(State).filter(State.state_id != ref["state_id"]).first().state_id
    )
    other_grid_owner_id = (
        db_session.query(GridOwner)
        .filter(GridOwner.grid_owner_id != ref["grid_owner_id"])
        .first()
        .grid_owner_id
    )

    create_response = client.post(
        "/api/v1/substations",
        headers=headers,
        json={"mnemonic": "ORG4", "official_name": "Organizational Metadata Test Four", **ref},
    )
    substation_id = create_response.json()["substation_id"]

    update_response = client.patch(
        f"/api/v1/substations/{substation_id}",
        headers=headers,
        json={
            "region_id": other_region_id,
            "gm_zone_id": other_gm_zone_id,
            "state_id": other_state_id,
            "grid_owner_id": other_grid_owner_id,
        },
    )
    assert update_response.status_code == 200, update_response.text
    body = update_response.json()
    assert body["region_id"] == other_region_id
    assert body["gm_zone_id"] == other_gm_zone_id
    assert body["state_id"] == other_state_id
    assert body["grid_owner_id"] == other_grid_owner_id

    audit_response = client.get(f"/api/v1/substations/{substation_id}/audit-log", headers=headers)
    field_names = {e["field_name"] for e in audit_response.json()["items"]}
    assert field_names == {"region_id", "gm_zone_id", "state_id", "grid_owner_id"}


def test_update_without_substation_registry_write_is_forbidden(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token = _admin_token(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post(
        "/api/v1/substations",
        headers=headers,
        json={"mnemonic": "ORG5", "official_name": "Organizational Metadata Test Five", **ref},
    )
    substation_id = create_response.json()["substation_id"]

    iam = IAMService(db_session)
    iam.create_user(
        username="viewer_only_2",
        display_name="Viewer Only Two",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    viewer_token = _login(client, "viewer_only_2", "correct-horse-battery")

    response = client.patch(
        f"/api/v1/substations/{substation_id}",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"region_id": ref["region_id"]},
    )
    assert response.status_code == 403
