"""API contract tests for Engineering Parameter Configuration's router —
exercises the full Router -> Service -> Repository stack through HTTP,
mirroring backend/tests/test_automatic_load_shedding_functionality_api.py's
pattern.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.engineering_parameters.bootstrap import (
    run_bootstrap as bootstrap_engineering_parameters,
)
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _admin_setup(client: TestClient, db_session: Session) -> str:
    settings = get_settings()
    bootstrap_iam(db_session)
    bootstrap_engineering_parameters(db_session)
    return _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)


# --- Authentication -------------------------------------------------------------------


def test_list_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/engineering-parameters")
    assert response.status_code == 401


def test_get_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/engineering-parameters/mw_tolerance_percentage")
    assert response.status_code == 401


def test_set_requires_authentication(client: TestClient) -> None:
    response = client.put(
        "/api/v1/engineering-parameters/mw_tolerance_percentage",
        json={"value": "10", "change_reason": "test"},
    )
    assert response.status_code == 401


# --- Permission enforcement -------------------------------------------------------------


def test_set_requires_manage_permission(client: TestClient, db_session: Session) -> None:
    bootstrap_iam(db_session)
    bootstrap_engineering_parameters(db_session)
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

    response = client.put(
        "/api/v1/engineering-parameters/mw_tolerance_percentage",
        headers={"Authorization": f"Bearer {token}"},
        json={"value": "12", "change_reason": "test"},
    )
    assert response.status_code == 403


def test_audit_log_requires_manage_permission_not_merely_authentication(
    client: TestClient, db_session: Session
) -> None:
    """ADR-021's own deliberate deviation from this codebase's usual
    "audit log open to any authenticated user" precedent — engineering-
    parameter-configuration-architecture.md §12."""
    bootstrap_iam(db_session)
    bootstrap_engineering_parameters(db_session)
    iam = IAMService(db_session)
    iam.create_user(
        username="read_only_engineer",
        display_name="Read Only Engineer",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    engineer_role = next(r for r in iam.list_roles() if r.name == "Engineer")
    iam.assign_role_to_user(
        user_id=iam.repo.get_user_by_username("read_only_engineer").user_id,
        role_id=engineer_role.role_id,
        actor_user_id=None,
    )
    db_session.commit()
    token = _login(client, "read_only_engineer", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {token}"}

    # GET the parameter itself only requires authentication — succeeds.
    get_response = client.get(
        "/api/v1/engineering-parameters/mw_tolerance_percentage", headers=headers
    )
    assert get_response.status_code == 200

    # The audit log requires the elevated permission — Engineer lacks it.
    audit_response = client.get(
        "/api/v1/engineering-parameters/mw_tolerance_percentage/audit-log", headers=headers
    )
    assert audit_response.status_code == 403


# --- Bootstrap seeding is visible through the API --------------------------------------


def test_bootstrap_seeds_the_approved_mw_tolerance_parameter(
    client: TestClient, db_session: Session
) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    list_response = client.get("/api/v1/engineering-parameters", headers=headers)
    assert list_response.status_code == 200
    items = list_response.json()
    assert len(items) == 1
    assert items[0]["parameter_key"] == "mw_tolerance_percentage"
    assert items[0]["value"] == "10"
    assert items[0]["unit"] == "percent"


# --- Full read/write/audit flow ---------------------------------------------------------


def test_full_set_get_and_audit_log_flow(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    set_response = client.put(
        "/api/v1/engineering-parameters/mw_tolerance_percentage",
        headers=headers,
        json={
            "value": "12",
            "unit": "percent",
            "change_reason": "Widened after engineering review.",
        },
    )
    assert set_response.status_code == 200, set_response.text
    body = set_response.json()
    assert body["value"] == "12"
    assert body["updated_by"]["username"] == get_settings().bootstrap_admin_username

    get_response = client.get(
        "/api/v1/engineering-parameters/mw_tolerance_percentage", headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["value"] == "12"

    audit_response = client.get(
        "/api/v1/engineering-parameters/mw_tolerance_percentage/audit-log", headers=headers
    )
    assert audit_response.status_code == 200
    audit_body = audit_response.json()
    # bootstrap seed (creation) + this test's own update.
    assert audit_body["total"] == 2
    assert audit_body["items"][0]["new_value"] == "12"
    assert audit_body["items"][0]["old_value"] == "10"
    assert audit_body["items"][0]["change_reason"] == "Widened after engineering review."


def test_set_without_change_reason_is_422(client: TestClient, db_session: Session) -> None:
    """`change_reason` is a required (non-optional) field on the request
    schema — FastAPI/Pydantic rejects its absence before the service layer
    is ever reached."""
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.put(
        "/api/v1/engineering-parameters/mw_tolerance_percentage",
        headers=headers,
        json={"value": "12"},
    )
    assert response.status_code == 422


def test_set_with_blank_change_reason_is_400(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.put(
        "/api/v1/engineering-parameters/mw_tolerance_percentage",
        headers=headers,
        json={"value": "12", "change_reason": "   "},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


def test_set_invalid_value_is_400(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.put(
        "/api/v1/engineering-parameters/mw_tolerance_percentage",
        headers=headers,
        json={"value": "not-a-number", "change_reason": "test"},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


def test_get_unknown_parameter_is_404(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/engineering-parameters/does_not_exist", headers=headers)
    assert response.status_code == 404


def test_audit_log_for_unknown_parameter_is_404(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/api/v1/engineering-parameters/does_not_exist/audit-log", headers=headers
    )
    assert response.status_code == 404


def test_set_creates_a_new_parameter_not_yet_seeded(
    client: TestClient, db_session: Session
) -> None:
    """PUT is an upsert (module document §8) — a brand-new
    `parameter_key` is created, not rejected as not-found."""
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.put(
        "/api/v1/engineering-parameters/some_future_parameter",
        headers=headers,
        json={"value": "freeform", "change_reason": "test"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["value"] == "freeform"
