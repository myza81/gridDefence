"""API contract tests for the UFLS router — exercises the full
Router -> Service -> Repository stack through HTTP, mirroring
backend/tests/test_stage_setting_registry_api.py's own pattern.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
from app.modules.ufls.bootstrap import run_bootstrap as bootstrap_ufls


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _admin_setup(client: TestClient, db_session: Session) -> str:
    settings = get_settings()
    bootstrap_iam(db_session)
    bootstrap_ufls(db_session)
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


# --- Authentication -------------------------------------------------------------------


def test_list_schemes_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/ufls/schemes")
    assert response.status_code == 401


def test_create_scheme_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/v1/ufls/schemes", json={"name": "Test", "description": None})
    assert response.status_code == 401


# --- Permission enforcement -------------------------------------------------------------


def test_read_open_to_any_authenticated_user(client: TestClient, db_session: Session) -> None:
    bootstrap_iam(db_session)
    bootstrap_ufls(db_session)
    _create_user_with_role(db_session, username="viewer_user", role_name="Viewer")
    token = _login(client, "viewer_user", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/ufls/schemes", headers=headers)
    assert response.status_code == 200
    assert response.json() == []


def test_create_scheme_requires_manage_permission(client: TestClient, db_session: Session) -> None:
    bootstrap_iam(db_session)
    bootstrap_ufls(db_session)
    _create_user_with_role(db_session, username="viewer_user", role_name="Viewer")
    token = _login(client, "viewer_user", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/ufls/schemes", headers=headers, json={"name": "Test", "description": None}
    )
    assert response.status_code == 403


def test_publish_requires_publish_permission_not_just_manage(
    client: TestClient, db_session: Session
) -> None:
    bootstrap_iam(db_session)
    bootstrap_ufls(db_session)
    _create_user_with_role(db_session, username="engineer_user", role_name="Engineer")
    token = _login(client, "engineer_user", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/ufls/schemes",
        headers=headers,
        json={"name": "Engineer Scheme", "description": None},
    )
    assert create_response.status_code == 201
    scheme_id = create_response.json()["ufls_scheme_id"]

    version_response = client.post(
        f"/api/v1/ufls/schemes/{scheme_id}/versions",
        headers=headers,
        json={"copied_from_version_id": None},
    )
    assert version_response.status_code == 201
    version_id = version_response.json()["version_id"]

    publish_response = client.post(
        f"/api/v1/ufls/versions/{version_id}/publish",
        headers=headers,
        json={
            "publication_event_id": "11111111-1111-1111-1111-111111111111",
            "acknowledgements": [],
        },
    )
    assert publish_response.status_code == 403


# --- End-to-end scheme/draft lifecycle flow ---------------------------------------------


def test_create_scheme_and_draft_version_flow(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/ufls/schemes", headers=headers, json={"name": "E2E Scheme", "description": "desc"}
    )
    assert create_response.status_code == 201, create_response.text
    scheme = create_response.json()
    assert scheme["name"] == "E2E Scheme"

    list_response = client.get("/api/v1/ufls/schemes", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    version_response = client.post(
        f"/api/v1/ufls/schemes/{scheme['ufls_scheme_id']}/versions",
        headers=headers,
        json={"copied_from_version_id": None},
    )
    assert version_response.status_code == 201, version_response.text
    version = version_response.json()
    assert version["version_number"] == 1
    assert version["lifecycle_status"] == "DRAFT"

    review_response = client.get(
        f"/api/v1/ufls/versions/{version['version_id']}/publication-review", headers=headers
    )
    assert review_response.status_code == 200
    review = review_response.json()
    assert review["all_prerequisites_passed"] is False  # no Stage Setting Set selected yet

    delete_response = client.delete(
        f"/api/v1/ufls/versions/{version['version_id']}", headers=headers
    )
    assert delete_response.status_code == 204
