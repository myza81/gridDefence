"""API contract tests for the Transformer Registry router (Phase 3.5) —
equipment-registry-module.md's Transformer Registry section, ADR-008's
Transformer Registry addendum and its UAT-correction addendum (transformers
are substation-owned equipment, never modeled as spanning two substations).
Exercises the full Router -> Service -> Repository stack through HTTP,
mirroring test_equipment_registry_api.py's own pattern.
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
        "hv_voltage_level_id": db_session.query(VoltageLevel)
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
        "gm_zone_id": db_session.query(GmZone).filter_by(code="ALOR_SETAR").one().gm_zone_id,
        "state_id": db_session.query(State).filter_by(code="SEL").one().state_id,
        "grid_owner_id": db_session.query(GridOwner).filter_by(code="TNB").one().grid_owner_id,
    }


def _admin_setup(client: TestClient, db_session: Session) -> tuple[str, uuid.UUID]:
    """See test_equipment_registry_api.py's own docstring for why
    `admin_user_id` must be a real `uuid.UUID`, not a string."""
    settings = get_settings()
    admin = bootstrap_iam(db_session)
    bootstrap_substations(db_session)
    bootstrap_equipment_registry(db_session)
    token = _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)
    return token, admin.user_id


def _create_substations_and_switchyards(
    db_session: Session, ref: dict[str, int], actor_user_id: uuid.UUID
) -> dict[str, str]:
    """Two real Substation Registry records, each with one HV (500kV) and
    one LV (132kV) SubstationVoltageYard — enough to build a real,
    substation-owned HV/LV transformer, and to test the cross-substation
    rejection rule. Returns substation ids keyed by mnemonic, and
    switchyard ids keyed "{mnemonic}_hv"/"{mnemonic}_lv"."""
    substation_service = SubstationService(db_session)
    equipment_service = EquipmentRegistryService(db_session)
    ids: dict[str, str] = {}
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
        hv_yard = equipment_service.create_voltage_yard(
            substation_id=substation.substation_id,
            voltage_level_id=ref["hv_voltage_level_id"],
            actor_user_id=actor_user_id,
        )
        lv_yard = equipment_service.create_voltage_yard(
            substation_id=substation.substation_id,
            voltage_level_id=ref["lv_voltage_level_id"],
            actor_user_id=actor_user_id,
        )
        ids[mnemonic] = str(substation.substation_id)
        ids[f"{mnemonic}_hv"] = str(hv_yard.voltage_yard_id)
        ids[f"{mnemonic}_lv"] = str(lv_yard.voltage_yard_id)
    db_session.commit()
    return ids


def _transformer_payload(ref: dict[str, int], ids: dict[str, str], **overrides) -> dict:
    """Default payload is substation-first and internally consistent: both
    HV and LV switchyards belong to the same selected substation (PKLG) —
    the UAT-corrected, only-legal shape."""
    payload = {
        "substation_id": ids["PKLG"],
        "transformer_number": "1",
        "hv_switchyard_id": ids["PKLG_hv"],
        "hv_breaker_number": "H10",
        "lv_switchyard_id": ids["PKLG_lv"],
        "lv_breaker_number": "110",
        "capacity_mva": 90,
        "commissioning_date": None,
        "operational_status_id": ref["operational_status_id"],
        "transformer_type": None,
        "manufacturer": None,
        "remarks": None,
    }
    payload.update(overrides)
    return payload


def test_create_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/transformers", json={})
    assert response.status_code == 401


def test_list_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/transformers")
    assert response.status_code == 401


def test_create_without_equipment_registry_write_is_forbidden(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    _admin_token, admin_id = _admin_setup(client, db_session)
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

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
        "/api/v1/transformers",
        headers={"Authorization": f"Bearer {token}"},
        json=_transformer_payload(ref, ids),
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

    response = client.get("/api/v1/transformers", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_full_create_read_update_flow(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

    create_response = client.post(
        "/api/v1/transformers", headers=headers, json=_transformer_payload(ref, ids)
    )
    assert create_response.status_code == 201, create_response.text
    body = create_response.json()
    assert body["transformer_number"] == "1"
    # UAT correction: substation context is a first-class part of every
    # transformer read response, not derivable only via terminal-substation
    # joins.
    assert body["substation_id"] == ids["PKLG"]
    assert body["substation_mnemonic"] == "PKLG"
    assert body["substation_official_name"] == "PKLG Substation"
    # HV side is 500kV -> "XGT" prefix (TNB convention).
    assert body["generated_short_name"] == "XGT1"
    assert len(body["terminals"]) == 2
    assert {t["side"] for t in body["terminals"]} == {"HV", "LV"}
    assert body["created_by"]["username"] == get_settings().bootstrap_admin_username
    transformer_id = body["transformer_id"]

    get_response = client.get(f"/api/v1/transformers/{transformer_id}", headers=headers)
    assert get_response.status_code == 200
    assert get_response.json()["generated_short_name"] == "XGT1"
    assert get_response.json()["substation_mnemonic"] == "PKLG"

    update_response = client.patch(
        f"/api/v1/transformers/{transformer_id}",
        headers=headers,
        json={"manufacturer": "Siemens", "hv_breaker_number": "H99"},
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert updated["manufacturer"] == "Siemens"
    # substation_id is immutable — no field to change it even exists on
    # TransformerUpdate; the substation shown after update is unchanged.
    assert updated["substation_id"] == ids["PKLG"]
    hv_terminal = next(t for t in updated["terminals"] if t["side"] == "HV")
    assert hv_terminal["breaker_number"] == "H99"

    audit_response = client.get(f"/api/v1/transformers/{transformer_id}/audit-log", headers=headers)
    assert audit_response.status_code == 200
    field_names = {e["field_name"] for e in audit_response.json()["items"]}
    assert field_names == {"manufacturer", "hv_breaker_number"}


def test_same_switchyard_for_hv_and_lv_returns_400(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

    payload = _transformer_payload(ref, ids, lv_switchyard_id=ids["PKLG_hv"])
    response = client.post("/api/v1/transformers", headers=headers, json=payload)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


def test_reversed_hv_lv_voltage_order_returns_400(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

    # Swap HV/LV switchyards within the same substation (PKLG) — 132kV as
    # HV, 500kV as LV — isolating the voltage-order rule from the separate
    # cross-substation rule exercised below.
    payload = _transformer_payload(
        ref,
        ids,
        hv_switchyard_id=ids["PKLG_lv"],
        lv_switchyard_id=ids["PKLG_hv"],
    )
    response = client.post("/api/v1/transformers", headers=headers, json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["code"] == "validation_error"
    assert "132kV" in body["detail"]["message"]
    assert "500kV" in body["detail"]["message"]


def test_cross_substation_hv_lv_returns_400(client: TestClient, db_session: Session) -> None:
    """UAT blocker fix: a transformer is substation-owned equipment. Here
    the selected substation is PKLG but the LV switchyard belongs to IGBK
    — must be rejected, never silently accepted."""
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

    payload = _transformer_payload(ref, ids, lv_switchyard_id=ids["IGBK_lv"])
    response = client.post("/api/v1/transformers", headers=headers, json=payload)
    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["code"] == "validation_error"
    assert "PKLG" in body["detail"]["message"]
    assert "IGBK" in body["detail"]["message"]


def test_duplicate_transformer_identity_returns_400_with_human_readable_message(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

    payload = _transformer_payload(ref, ids)
    first = client.post("/api/v1/transformers", headers=headers, json=payload)
    assert first.status_code == 201, first.text

    second = client.post("/api/v1/transformers", headers=headers, json=payload)
    assert second.status_code == 400
    body = second.json()
    assert body["detail"]["code"] == "validation_error"
    assert "1" in body["detail"]["message"]
    assert "PKLG" in body["detail"]["message"]


def test_entered_in_error_transformer_does_not_block_recreating_the_same_identity(
    client: TestClient, db_session: Session
) -> None:
    """UAT regression: a transformer corrected to `ENTERED_IN_ERROR` must
    not permanently reserve its `(substation, HV yard, LV yard, number)`
    identity — the corrected record is hidden from default views but was
    still counted by the uniqueness check, wrongly blocking a legitimate
    re-creation with the same identity."""
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

    mistaken = client.post(
        "/api/v1/transformers", headers=headers, json=_transformer_payload(ref, ids)
    )
    assert mistaken.status_code == 201, mistaken.text

    entered_in_error_status_id = (
        db_session.query(OperationalStatus)
        .filter_by(code="ENTERED_IN_ERROR")
        .one()
        .operational_status_id
    )
    correction = client.patch(
        f"/api/v1/transformers/{mistaken.json()['transformer_id']}",
        headers=headers,
        json={"operational_status_id": entered_in_error_status_id},
    )
    assert correction.status_code == 200, correction.text

    recreated = client.post(
        "/api/v1/transformers", headers=headers, json=_transformer_payload(ref, ids)
    )
    assert recreated.status_code == 201, recreated.text
    assert recreated.json()["transformer_id"] != mistaken.json()["transformer_id"]

    # The corrected record is preserved, not deleted — still reachable
    # directly by id.
    still_visible = client.get(
        f"/api/v1/transformers/{mistaken.json()['transformer_id']}", headers=headers
    )
    assert still_visible.status_code == 200
    assert still_visible.json()["operational_status_id"] == entered_in_error_status_id


def test_same_transformer_number_across_different_hv_lv_pairs_is_allowed(
    client: TestClient, db_session: Session
) -> None:
    """UAT regression: a substation's "Transformer Bay 1" on its 500/132kV
    pair and a separate "Transformer Bay 1" on its 132/33kV pair are both
    legitimate — uniqueness is scoped to the HV/LV switchyard pair, not the
    whole substation."""
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

    first = client.post(
        "/api/v1/transformers", headers=headers, json=_transformer_payload(ref, ids)
    )
    assert first.status_code == 201, first.text

    equipment_service = EquipmentRegistryService(db_session)
    tertiary_voltage_level_id = (
        db_session.query(VoltageLevel).filter_by(label="33kV").one().voltage_level_id
    )
    tertiary_yard = equipment_service.create_voltage_yard(
        substation_id=uuid.UUID(ids["PKLG"]),
        voltage_level_id=tertiary_voltage_level_id,
        actor_user_id=admin_id,
    )
    db_session.commit()

    second = client.post(
        "/api/v1/transformers",
        headers=headers,
        json=_transformer_payload(
            ref,
            ids,
            hv_switchyard_id=ids["PKLG_lv"],
            lv_switchyard_id=str(tertiary_yard.voltage_yard_id),
        ),
    )
    assert second.status_code == 201, second.text


def test_parallel_transformers_at_the_same_substation_are_allowed(
    client: TestClient, db_session: Session
) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

    first = client.post(
        "/api/v1/transformers", headers=headers, json=_transformer_payload(ref, ids)
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/transformers",
        headers=headers,
        json=_transformer_payload(ref, ids, transformer_number="2"),
    )
    assert second.status_code == 201
    assert second.json()["generated_short_name"] == "XGT2"


def test_same_transformer_number_at_a_different_substation_is_allowed(
    client: TestClient, db_session: Session
) -> None:
    """The uniqueness rule is scoped to (substation_id, transformer_number)
    — the same transformer number at a different substation is a separate,
    legitimate identity."""
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

    first = client.post(
        "/api/v1/transformers", headers=headers, json=_transformer_payload(ref, ids)
    )
    assert first.status_code == 201

    second_payload = _transformer_payload(
        ref,
        ids,
        substation_id=ids["IGBK"],
        hv_switchyard_id=ids["IGBK_hv"],
        lv_switchyard_id=ids["IGBK_lv"],
    )
    second = client.post("/api/v1/transformers", headers=headers, json=second_payload)
    assert second.status_code == 201, second.text
    assert second.json()["substation_mnemonic"] == "IGBK"


def test_renaming_a_transformer_to_collide_via_patch_returns_400(
    client: TestClient, db_session: Session
) -> None:
    """`update_transformer` previously performed no uniqueness check at all
    — renaming one transformer's number to collide with another transformer
    on the same HV/LV pair must be rejected via `PATCH`, exactly like
    creation is via `POST`."""
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

    first = client.post(
        "/api/v1/transformers", headers=headers, json=_transformer_payload(ref, ids)
    )
    assert first.status_code == 201

    second = client.post(
        "/api/v1/transformers",
        headers=headers,
        json=_transformer_payload(ref, ids, transformer_number="2"),
    )
    assert second.status_code == 201

    patch_response = client.patch(
        f"/api/v1/transformers/{second.json()['transformer_id']}",
        headers=headers,
        json={"transformer_number": "1"},
    )
    assert patch_response.status_code == 400
    body = patch_response.json()
    assert body["detail"]["code"] == "validation_error"
    assert "PKLG" in body["detail"]["message"]


def test_override_breaker_number_is_never_rejected(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

    payload = _transformer_payload(
        ref, ids, hv_breaker_number="ANYTHING-GOES", lv_breaker_number="123-ABC"
    )
    response = client.post("/api/v1/transformers", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    terminals = {t["side"]: t["breaker_number"] for t in response.json()["terminals"]}
    assert terminals == {"HV": "ANYTHING-GOES", "LV": "123-ABC"}


def test_search_and_filter(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

    client.post("/api/v1/transformers", headers=headers, json=_transformer_payload(ref, ids))

    search_response = client.get("/api/v1/transformers?search=PKLG", headers=headers)
    assert search_response.status_code == 200
    assert search_response.json()["total"] == 1

    no_match_response = client.get("/api/v1/transformers?search=NOPE", headers=headers)
    assert no_match_response.status_code == 200
    assert no_match_response.json()["total"] == 0

    filter_response = client.get(
        f"/api/v1/transformers?operational_status_id={ref['operational_status_id']}",
        headers=headers,
    )
    assert filter_response.status_code == 200
    assert filter_response.json()["total"] == 1


def test_filter_by_substation_id(client: TestClient, db_session: Session) -> None:
    """From a substation's own perspective: "which transformers are
    installed here" — the exact UAT-reported requirement, at the API
    contract level."""
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

    client.post("/api/v1/transformers", headers=headers, json=_transformer_payload(ref, ids))
    client.post(
        "/api/v1/transformers",
        headers=headers,
        json=_transformer_payload(
            ref,
            ids,
            substation_id=ids["IGBK"],
            hv_switchyard_id=ids["IGBK_hv"],
            lv_switchyard_id=ids["IGBK_lv"],
        ),
    )

    pklg_response = client.get(f"/api/v1/transformers?substation_id={ids['PKLG']}", headers=headers)
    assert pklg_response.status_code == 200
    pklg_body = pklg_response.json()
    assert pklg_body["total"] == 1
    assert pklg_body["items"][0]["substation_mnemonic"] == "PKLG"

    igbk_response = client.get(f"/api/v1/transformers?substation_id={ids['IGBK']}", headers=headers)
    assert igbk_response.status_code == 200
    assert igbk_response.json()["total"] == 1
    assert igbk_response.json()["items"][0]["substation_mnemonic"] == "IGBK"


def test_get_unknown_transformer_returns_404(client: TestClient, db_session: Session) -> None:
    token, _admin_id = _admin_setup(client, db_session)
    response = client.get(
        "/api/v1/transformers/00000000-0000-0000-0000-000000000000",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 404


def test_no_delete_endpoint_exists(client: TestClient, db_session: Session) -> None:
    ref = _seed_reference_data(db_session)
    token, admin_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    ids = _create_substations_and_switchyards(db_session, ref, admin_id)

    create_response = client.post(
        "/api/v1/transformers", headers=headers, json=_transformer_payload(ref, ids)
    )
    transformer_id = create_response.json()["transformer_id"]

    response = client.delete(f"/api/v1/transformers/{transformer_id}", headers=headers)
    assert response.status_code == 405
