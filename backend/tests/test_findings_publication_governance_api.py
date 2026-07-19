"""API contract tests for the Findings and Publication Governance policy
router — exercises the full Router -> Service -> Repository stack through
HTTP, mirroring backend/tests/test_stage_setting_registry_api.py's pattern.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.findings_publication_governance.bootstrap import (
    run_bootstrap as bootstrap_findings_publication_governance,
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
    bootstrap_findings_publication_governance(db_session)
    return _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)


def _create_user_with_role(db_session: Session, *, username: str, role_name: str) -> None:
    iam = IAMService(db_session)
    iam.create_user(
        username=username,
        display_name=username,
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    role = next(r for r in iam.list_roles() if r.name == role_name)
    iam.assign_role_to_user(
        user_id=iam.repo.get_user_by_username(username).user_id,
        role_id=role.role_id,
        actor_user_id=None,
    )
    db_session.commit()


def _get_baseline_id(client: TestClient, headers: dict[str, str], severity: str) -> str:
    response = client.get(
        "/api/v1/publication-treatment-policies", headers=headers, params={"severity": severity}
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    baseline = next(i for i in items if i["finding_type"] is None and i["scheme_type"] is None)
    return baseline["policy_id"]


# --- Authentication -------------------------------------------------------------------


def test_list_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/publication-treatment-policies")
    assert response.status_code == 401


def test_create_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/publication-treatment-policies",
        json={"severity": "WARNING", "treatment": "BLOCK", "change_reason": "x"},
    )
    assert response.status_code == 401


# --- Permission enforcement -------------------------------------------------------------


def test_read_open_to_any_authenticated_user(client: TestClient, db_session: Session) -> None:
    bootstrap_iam(db_session)
    bootstrap_findings_publication_governance(db_session)
    _create_user_with_role(db_session, username="viewer_user", role_name="Viewer")
    token = _login(client, "viewer_user", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/publication-treatment-policies", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 4


def test_create_requires_manage_policy_permission(client: TestClient, db_session: Session) -> None:
    bootstrap_iam(db_session)
    bootstrap_findings_publication_governance(db_session)
    _create_user_with_role(db_session, username="engineer_user", role_name="Engineer")
    token = _login(client, "engineer_user", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/publication-treatment-policies",
        headers=headers,
        json={
            "severity": "WARNING",
            "finding_type": "MW_TOLERANCE_DEVIATION",
            "treatment": "BLOCK",
            "change_reason": "Should be forbidden.",
        },
    )
    assert response.status_code == 403


def test_update_requires_manage_policy_permission(client: TestClient, db_session: Session) -> None:
    admin_token = _admin_setup(client, db_session)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    policy_id = _get_baseline_id(client, admin_headers, "ADVISORY")

    _create_user_with_role(db_session, username="engineer_user", role_name="Engineer")
    token = _login(client, "engineer_user", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.patch(
        f"/api/v1/publication-treatment-policies/{policy_id}",
        headers=headers,
        json={"treatment": "BLOCK", "change_reason": "Should be forbidden."},
    )
    assert response.status_code == 403


def test_remove_requires_manage_policy_permission(client: TestClient, db_session: Session) -> None:
    admin_token = _admin_setup(client, db_session)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post(
        "/api/v1/publication-treatment-policies",
        headers=admin_headers,
        json={
            "severity": "WARNING",
            "finding_type": "MW_TOLERANCE_DEVIATION",
            "treatment": "BLOCK",
            "change_reason": "Override to later attempt removing as non-admin.",
        },
    )
    policy_id = create_response.json()["policy_id"]

    _create_user_with_role(db_session, username="engineer_user", role_name="Engineer")
    token = _login(client, "engineer_user", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        f"/api/v1/publication-treatment-policies/{policy_id}/remove",
        headers=headers,
        json={"change_reason": "Should be forbidden."},
    )
    assert response.status_code == 403


def test_audit_log_requires_view_audit_permission(client: TestClient, db_session: Session) -> None:
    admin_token = _admin_setup(client, db_session)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    policy_id = _get_baseline_id(client, admin_headers, "ADVISORY")

    _create_user_with_role(db_session, username="engineer_user", role_name="Engineer")
    token = _login(client, "engineer_user", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        f"/api/v1/publication-treatment-policies/{policy_id}/audit-log", headers=headers
    )
    assert response.status_code == 403


def test_administrator_can_view_audit_log(client: TestClient, db_session: Session) -> None:
    admin_token = _admin_setup(client, db_session)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    policy_id = _get_baseline_id(client, admin_headers, "ADVISORY")

    response = client.get(
        f"/api/v1/publication-treatment-policies/{policy_id}/audit-log", headers=admin_headers
    )
    assert response.status_code == 200
    assert response.json()["total"] == 1


# --- Request validation and error mapping ------------------------------------------------


def test_create_rejects_unsupported_severity_at_request_validation(
    client: TestClient, db_session: Session
) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/v1/publication-treatment-policies",
        headers=headers,
        json={"severity": "EXTREME", "treatment": "BLOCK", "change_reason": "x"},
    )
    assert response.status_code == 422


def test_create_rejects_unsupported_treatment_at_request_validation(
    client: TestClient, db_session: Session
) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/v1/publication-treatment-policies",
        headers=headers,
        json={"severity": "WARNING", "treatment": "IGNORE", "change_reason": "x"},
    )
    assert response.status_code == 422


def test_create_duplicate_baseline_is_400(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/v1/publication-treatment-policies",
        headers=headers,
        json={
            "severity": "CRITICAL",
            "treatment": "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
            "change_reason": "Attempt duplicate.",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


def test_get_unknown_policy_is_404(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(
        "/api/v1/publication-treatment-policies/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert response.status_code == 404


def test_update_without_reason_is_422(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    policy_id = _get_baseline_id(client, headers, "ADVISORY")

    response = client.patch(
        f"/api/v1/publication-treatment-policies/{policy_id}",
        headers=headers,
        json={"treatment": "BLOCK"},
    )
    assert response.status_code == 422


def test_remove_baseline_is_400(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    policy_id = _get_baseline_id(client, headers, "CRITICAL")

    response = client.post(
        f"/api/v1/publication-treatment-policies/{policy_id}/remove",
        headers=headers,
        json={"change_reason": "Attempt to remove baseline."},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


# --- List filters and deterministic ordering ----------------------------------------------


def test_list_filters_by_severity(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/api/v1/publication-treatment-policies", headers=headers, params={"severity": "CRITICAL"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["severity"] == "CRITICAL"


def test_list_ordering_is_deterministic_across_repeated_calls(
    client: TestClient, db_session: Session
) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    first = client.get("/api/v1/publication-treatment-policies", headers=headers)
    second = client.get("/api/v1/publication-treatment-policies", headers=headers)
    first_ids = [i["policy_id"] for i in first.json()["items"]]
    second_ids = [i["policy_id"] for i in second.json()["items"]]
    assert first_ids == second_ids


# --- Complete successful create/update/remove lifecycle -----------------------------------


def test_complete_override_lifecycle(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/publication-treatment-policies",
        headers=headers,
        json={
            "severity": "WARNING",
            "finding_type": "MW_TOLERANCE_DEVIATION",
            "treatment": "BLOCK",
            "change_reason": "Tightening MW deviation handling globally.",
        },
    )
    assert create_response.status_code == 201, create_response.text
    policy_id = create_response.json()["policy_id"]
    assert create_response.json()["finding_type"] == "MW_TOLERANCE_DEVIATION"
    assert create_response.json()["scheme_type"] is None

    update_response = client.patch(
        f"/api/v1/publication-treatment-policies/{policy_id}",
        headers=headers,
        json={
            "treatment": "ALLOW_WITH_ACKNOWLEDGEMENT",
            "change_reason": "Relaxing after review.",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["treatment"] == "ALLOW_WITH_ACKNOWLEDGEMENT"

    audit_response = client.get(
        f"/api/v1/publication-treatment-policies/{policy_id}/audit-log", headers=headers
    )
    assert audit_response.status_code == 200
    assert audit_response.json()["total"] == 2  # created, treatment_changed

    remove_response = client.post(
        f"/api/v1/publication-treatment-policies/{policy_id}/remove",
        headers=headers,
        json={"change_reason": "No longer needed."},
    )
    assert remove_response.status_code == 204

    get_response = client.get(
        f"/api/v1/publication-treatment-policies/{policy_id}", headers=headers
    )
    assert get_response.status_code == 404

    # Audit history survives removal.
    audit_after_removal = client.get(
        f"/api/v1/publication-treatment-policies/{policy_id}/audit-log", headers=headers
    )
    assert audit_after_removal.status_code == 200
    assert audit_after_removal.json()["total"] == 3  # created, treatment_changed, removed
