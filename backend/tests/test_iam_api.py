"""API contract tests for IAM's router — docs/architecture/iam-module.md §12,
CLAUDE.md A9/A11. Exercises the full Router -> Service -> Repository stack
through HTTP, not just the service layer in isolation.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.iam.bootstrap import run_bootstrap
from app.modules.iam.security import issue_access_token
from app.modules.iam.service import IAMService


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_login_with_valid_credentials_returns_a_bearer_token(
    client: TestClient, db_session: Session
) -> None:
    settings = get_settings()
    run_bootstrap(db_session)

    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.bootstrap_admin_username,
            "password": settings.bootstrap_admin_password,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == settings.bootstrap_admin_username
    # UserCredential must never appear in any response shape.
    assert "password" not in body["user"]
    assert "password_hash" not in body["user"]


def test_login_with_invalid_credentials_returns_400(
    client: TestClient, db_session: Session
) -> None:
    run_bootstrap(db_session)

    response = client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "definitely-wrong"}
    )

    assert response.status_code == 400


def test_users_me_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401


def test_users_me_rejects_a_forged_token(client: TestClient) -> None:
    response = client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-real-token"})

    assert response.status_code == 401


def test_users_me_returns_the_authenticated_user(client: TestClient, db_session: Session) -> None:
    settings = get_settings()
    run_bootstrap(db_session)
    token = _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)

    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["username"] == settings.bootstrap_admin_username


def test_create_user_without_iam_user_manage_permission_is_forbidden(
    client: TestClient, db_session: Session
) -> None:
    """A locally-created user with no roles at all must be fail-closed
    denied (§9 rule 11), not merely unauthenticated."""
    service = IAMService(db_session)
    service.create_user(
        username="plain_engineer",
        display_name="Plain Engineer",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    token = _login(client, "plain_engineer", "correct-horse-battery")

    response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "another_user",
            "display_name": "Another User",
            "password": "another-password",
        },
    )

    assert response.status_code == 403


def test_create_user_with_iam_user_manage_permission_succeeds(
    client: TestClient, db_session: Session
) -> None:
    settings = get_settings()
    run_bootstrap(db_session)
    token = _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)

    response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "username": "new_engineer",
            "display_name": "New Engineer",
            "email": "new.engineer@example.com",
            "password": "correct-horse-battery",
        },
    )

    assert response.status_code == 201
    assert response.json()["username"] == "new_engineer"


def test_a_user_may_always_view_their_own_roles(client: TestClient, db_session: Session) -> None:
    service = IAMService(db_session)
    user = service.create_user(
        username="self_viewer",
        display_name="Self Viewer",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    token = _login(client, "self_viewer", "correct-horse-battery")

    response = client.get(
        f"/api/v1/users/{user.user_id}/roles", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json() == []


def test_a_user_cannot_view_another_users_roles_without_iam_user_manage(
    client: TestClient, db_session: Session
) -> None:
    service = IAMService(db_session)
    user_a = service.create_user(
        username="user_a",
        display_name="User A",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    user_b = service.create_user(
        username="user_b",
        display_name="User B",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    token = _login(client, "user_a", "correct-horse-battery")

    response = client.get(
        f"/api/v1/users/{user_b.user_id}/roles", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert user_a.user_id != user_b.user_id


def test_expired_signature_is_rejected(client: TestClient, db_session: Session) -> None:
    """A token signed for a user_id that no longer exists must not
    authenticate (covers tampering/replay against a deleted account)."""
    forged_token = issue_access_token(uuid.uuid4())

    response = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {forged_token}"})

    assert response.status_code == 401
