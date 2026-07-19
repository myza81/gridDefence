"""API contract tests for the read-only Publication Records router
(`publication_records_router`) — no write routes exist by design;
`PublicationRecord` rows are seeded here directly through the in-process
`PublicationRecordService`, exactly as a future scheme module's own
Publish action would, never through HTTP (this sprint's own instructions
§14/§15).
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.findings_publication_governance.bootstrap import (
    run_bootstrap as bootstrap_findings_publication_governance,
)
from app.modules.findings_publication_governance.findings import Severity
from app.modules.findings_publication_governance.service import (
    PublicationRecordService,
)
from app.modules.findings_publication_governance.tests.synthetic_scheme import (
    synthetic_acknowledgement,
    synthetic_finding,
    synthetic_publication_request,
)
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _admin_setup(client: TestClient, db_session: Session) -> tuple[str, uuid.UUID]:
    settings = get_settings()
    bootstrap_iam(db_session)
    bootstrap_findings_publication_governance(db_session)
    token = _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)
    admin_user = IAMService(db_session).repo.get_user_by_username(settings.bootstrap_admin_username)
    return token, admin_user.user_id


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


def _seed_publication_record(
    db_session: Session, *, admin_user_id: uuid.UUID, scheme_type: str = "UFLS", **overrides: object
) -> uuid.UUID:
    finding = synthetic_finding(severity=Severity.ADVISORY)
    request = synthetic_publication_request(
        published_by_user_id=admin_user_id,
        scheme_type=scheme_type,  # type: ignore[arg-type]
        findings=[finding],
        **overrides,
    )
    service = PublicationRecordService(db_session)
    result = service.evaluate_and_record_publication(request)
    db_session.commit()
    return result.publication_record_id


# --- Authentication -------------------------------------------------------------------


def test_list_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/publication-records")
    assert response.status_code == 401


def test_detail_requires_authentication(client: TestClient) -> None:
    response = client.get(f"/api/v1/publication-records/{uuid.uuid4()}")
    assert response.status_code == 401


# --- Permission enforcement -------------------------------------------------------------


def test_list_open_to_any_authenticated_user(client: TestClient, db_session: Session) -> None:
    token, admin_user_id = _admin_setup(client, db_session)
    _seed_publication_record(db_session, admin_user_id=admin_user_id)

    _create_user_with_role(db_session, username="viewer_user", role_name="Viewer")
    viewer_token = _login(client, "viewer_user", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {viewer_token}"}

    response = client.get("/api/v1/publication-records", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_detail_requires_view_audit_permission(client: TestClient, db_session: Session) -> None:
    token, admin_user_id = _admin_setup(client, db_session)
    record_id = _seed_publication_record(db_session, admin_user_id=admin_user_id)

    _create_user_with_role(db_session, username="engineer_user", role_name="Engineer")
    engineer_token = _login(client, "engineer_user", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {engineer_token}"}

    response = client.get(f"/api/v1/publication-records/{record_id}", headers=headers)
    assert response.status_code == 403


def test_administrator_can_view_full_detail(client: TestClient, db_session: Session) -> None:
    token, admin_user_id = _admin_setup(client, db_session)
    record_id = _seed_publication_record(db_session, admin_user_id=admin_user_id)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(f"/api/v1/publication-records/{record_id}", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["publication_record_id"] == str(record_id)
    assert body["published_by"]["user_id"] == str(admin_user_id)
    assert len(body["findings"]) == 1


# --- List filters, pagination, ordering -------------------------------------------------


def test_list_filters_by_scheme_type(client: TestClient, db_session: Session) -> None:
    token, admin_user_id = _admin_setup(client, db_session)
    _seed_publication_record(db_session, admin_user_id=admin_user_id, scheme_type="UFLS")
    _seed_publication_record(db_session, admin_user_id=admin_user_id, scheme_type="UVLS")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/api/v1/publication-records", headers=headers, params={"scheme_type": "UVLS"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["scheme_type"] == "UVLS"


def test_list_filters_by_scheme_version_id(client: TestClient, db_session: Session) -> None:
    token, admin_user_id = _admin_setup(client, db_session)
    _seed_publication_record(db_session, admin_user_id=admin_user_id)
    target_version_id = uuid.uuid4()
    _seed_publication_record(
        db_session, admin_user_id=admin_user_id, scheme_version_id=target_version_id
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/api/v1/publication-records",
        headers=headers,
        params={"scheme_version_id": str(target_version_id)},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["scheme_version_id"] == str(target_version_id)


def test_list_pagination(client: TestClient, db_session: Session) -> None:
    token, admin_user_id = _admin_setup(client, db_session)
    for _ in range(3):
        _seed_publication_record(db_session, admin_user_id=admin_user_id)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(
        "/api/v1/publication-records", headers=headers, params={"page": 1, "page_size": 2}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_list_summary_omits_publisher_identity(client: TestClient, db_session: Session) -> None:
    """List (broad-read) shape deliberately omits publisher identity and
    full evidence — this sprint's own instructions §15."""
    token, admin_user_id = _admin_setup(client, db_session)
    _seed_publication_record(db_session, admin_user_id=admin_user_id)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/publication-records", headers=headers)
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert "published_by" not in item
    assert "findings" not in item


# --- Not-found / malformed identifiers ------------------------------------------------


def test_detail_not_found(client: TestClient, db_session: Session) -> None:
    token, _admin_user_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get(f"/api/v1/publication-records/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


def test_detail_malformed_identifier(client: TestClient, db_session: Session) -> None:
    token, _admin_user_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/publication-records/not-a-uuid", headers=headers)
    assert response.status_code == 422


# --- No write routes exposed -------------------------------------------------------------


def test_no_post_route(client: TestClient, db_session: Session) -> None:
    token, _admin_user_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/api/v1/publication-records", headers=headers, json={})
    assert response.status_code in (404, 405)


def test_no_patch_route(client: TestClient, db_session: Session) -> None:
    token, admin_user_id = _admin_setup(client, db_session)
    record_id = _seed_publication_record(db_session, admin_user_id=admin_user_id)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.patch(f"/api/v1/publication-records/{record_id}", headers=headers, json={})
    assert response.status_code in (404, 405)


def test_no_delete_route(client: TestClient, db_session: Session) -> None:
    token, admin_user_id = _admin_setup(client, db_session)
    record_id = _seed_publication_record(db_session, admin_user_id=admin_user_id)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.delete(f"/api/v1/publication-records/{record_id}", headers=headers)
    assert response.status_code in (404, 405)


# --- Complete evidence in detail response -----------------------------------------------


def test_detail_includes_complete_frozen_evidence(client: TestClient, db_session: Session) -> None:
    token, admin_user_id = _admin_setup(client, db_session)
    finding = synthetic_finding(severity=Severity.WARNING)
    ack = synthetic_acknowledgement(0, acknowledged_by_user_id=admin_user_id)
    request = synthetic_publication_request(
        published_by_user_id=admin_user_id, findings=[finding], acknowledgements=[ack]
    )
    service = PublicationRecordService(db_session)
    result = service.evaluate_and_record_publication(request)
    db_session.commit()

    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(
        f"/api/v1/publication-records/{result.publication_record_id}", headers=headers
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["findings"]) == 1
    assert body["findings"][0]["resolved_treatment"] == "ALLOW_WITH_ACKNOWLEDGEMENT"
    assert len(body["acknowledgements"]) == 1
    assert body["acknowledgements"][0]["justification"]
    assert len(body["prerequisites"]) == 1


# --- Sprint 3 regression: publication-treatment-policies unaffected ----------------------


def test_sprint_3_policy_endpoints_still_work(client: TestClient, db_session: Session) -> None:
    token, _admin_user_id = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/api/v1/publication-treatment-policies", headers=headers)
    assert response.status_code == 200
    assert response.json()["total"] == 4
