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


# --- IAM Completion Sprint: user status lifecycle -------------------------------------


def _create_second_administrator(db_session: Session, actor_user_id: uuid.UUID) -> str:
    """A second real Administrator (own username/password), via the same
    service-layer path the UI itself uses — returns the username."""
    service = IAMService(db_session)
    user = service.create_user(
        username="second_admin",
        display_name="Second Admin",
        email=None,
        password="correct-horse-battery",
        actor_user_id=actor_user_id,
    )
    admin_role = service.repo.get_role_by_name("Administrator")
    assert admin_role is not None
    service.assign_role_to_user(
        user_id=user.user_id, role_id=admin_role.role_id, actor_user_id=actor_user_id
    )
    db_session.commit()
    return "second_admin"


def test_change_user_status_requires_iam_user_manage_permission(
    client: TestClient, db_session: Session
) -> None:
    """A user holding the (permission-less, by default) Engineer role is
    denied, mirroring the existing create-user permission test exactly."""
    run_bootstrap(db_session)
    service = IAMService(db_session)
    target = service.create_user(
        username="target_user",
        display_name="Target User",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    engineer_role = service.repo.get_role_by_name("Engineer")
    assert engineer_role is not None
    actor = service.create_user(
        username="plain_engineer",
        display_name="Plain Engineer",
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    service.assign_role_to_user(
        user_id=actor.user_id, role_id=engineer_role.role_id, actor_user_id=None
    )
    db_session.commit()
    token = _login(client, "plain_engineer", "correct-horse-battery")

    response = client.post(
        f"/api/v1/users/{target.user_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "suspended", "change_reason": "attempt"},
    )

    assert response.status_code == 403


def test_change_user_status_succeeds_for_administrator(
    client: TestClient, db_session: Session
) -> None:
    settings = get_settings()
    admin = run_bootstrap(db_session)
    service = IAMService(db_session)
    target = service.create_user(
        username="target_user",
        display_name="Target User",
        email=None,
        password="correct-horse-battery",
        actor_user_id=admin.user_id,
    )
    db_session.commit()
    token = _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)

    response = client.post(
        f"/api/v1/users/{target.user_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "suspended", "change_reason": "Leaving the team"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "suspended"


def test_change_user_status_without_reason_is_rejected(
    client: TestClient, db_session: Session
) -> None:
    settings = get_settings()
    admin = run_bootstrap(db_session)
    service = IAMService(db_session)
    target = service.create_user(
        username="target_user",
        display_name="Target User",
        email=None,
        password="correct-horse-battery",
        actor_user_id=admin.user_id,
    )
    db_session.commit()
    token = _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)

    response = client.post(
        f"/api/v1/users/{target.user_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "suspended", "change_reason": ""},
    )

    assert response.status_code == 422  # Pydantic min_length=1 request-shape rejection


def test_change_user_status_returns_typed_error_for_last_administrator(
    client: TestClient, db_session: Session
) -> None:
    settings = get_settings()
    admin = run_bootstrap(db_session)
    token = _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)

    response = client.post(
        f"/api/v1/users/{admin.user_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "deactivated", "change_reason": "attempt"},
    )

    assert response.status_code == 400
    body = response.json()
    assert body["detail"]["code"] == "validation_error"
    assert "active Administrator" in body["detail"]["message"]


def test_change_user_status_allowed_once_a_second_administrator_exists(
    client: TestClient, db_session: Session
) -> None:
    settings = get_settings()
    admin = run_bootstrap(db_session)
    _create_second_administrator(db_session, admin.user_id)
    token = _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)

    response = client.post(
        f"/api/v1/users/{admin.user_id}/status",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "deactivated", "change_reason": "recovery account retired"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "deactivated"


def test_suspended_user_cannot_login(client: TestClient, db_session: Session) -> None:
    settings = get_settings()
    admin = run_bootstrap(db_session)
    service = IAMService(db_session)
    target = service.create_user(
        username="target_user",
        display_name="Target User",
        email=None,
        password="correct-horse-battery",
        actor_user_id=admin.user_id,
    )
    db_session.commit()
    admin_token = _login(
        client, settings.bootstrap_admin_username, settings.bootstrap_admin_password
    )
    client.post(
        f"/api/v1/users/{target.user_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "suspended", "change_reason": "temp"},
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "target_user", "password": "correct-horse-battery"},
    )

    assert response.status_code == 400


def test_login_succeeds_again_after_reactivation(client: TestClient, db_session: Session) -> None:
    settings = get_settings()
    admin = run_bootstrap(db_session)
    service = IAMService(db_session)
    target = service.create_user(
        username="target_user",
        display_name="Target User",
        email=None,
        password="correct-horse-battery",
        actor_user_id=admin.user_id,
    )
    db_session.commit()
    admin_token = _login(
        client, settings.bootstrap_admin_username, settings.bootstrap_admin_password
    )
    client.post(
        f"/api/v1/users/{target.user_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "suspended", "change_reason": "temp"},
    )
    client.post(
        f"/api/v1/users/{target.user_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "active", "change_reason": "back"},
    )

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "target_user", "password": "correct-horse-battery"},
    )

    assert response.status_code == 200


def test_an_existing_token_is_rejected_on_the_next_request_after_suspension(
    client: TestClient, db_session: Session
) -> None:
    """The central Part 3 behaviour: `get_current_user` re-checks current
    `User.status` from the database on every request — it never trusts a
    previously-issued token's own claim of identity as proof of current
    authorization. No token blacklist is needed for this to hold."""
    settings = get_settings()
    admin = run_bootstrap(db_session)
    service = IAMService(db_session)
    target = service.create_user(
        username="target_user",
        display_name="Target User",
        email=None,
        password="correct-horse-battery",
        actor_user_id=admin.user_id,
    )
    db_session.commit()
    target_token = _login(client, "target_user", "correct-horse-battery")

    # The token is valid and usable before suspension.
    pre_response = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {target_token}"}
    )
    assert pre_response.status_code == 200

    admin_token = _login(
        client, settings.bootstrap_admin_username, settings.bootstrap_admin_password
    )
    suspend_response = client.post(
        f"/api/v1/users/{target.user_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "suspended", "change_reason": "temp"},
    )
    assert suspend_response.status_code == 200

    # The exact same, still cryptographically-valid, not-yet-expired
    # token is now rejected — proving status is re-checked per request.
    post_response = client.get(
        "/api/v1/users/me", headers={"Authorization": f"Bearer {target_token}"}
    )
    assert post_response.status_code == 401


def test_full_recovery_account_retirement_workflow(client: TestClient, db_session: Session) -> None:
    """End-to-end walk of the exact recovery-account workflow this sprint
    exists to enable, against a disposable test database — never against
    real recovered development accounts. Mirrors Part 7's own 11 steps in
    order.
    """
    settings = get_settings()

    # 1. Administrator A exists and is the only active Administrator.
    admin_a = run_bootstrap(db_session)
    token_a = _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)
    admin_role = IAMService(db_session).repo.get_role_by_name("Administrator")
    assert admin_role is not None
    admin_role_id = str(admin_role.role_id)

    # 2. Attempt to revoke Administrator from A -> rejected.
    revoke_response = client.delete(
        f"/api/v1/users/{admin_a.user_id}/roles/{admin_role_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert revoke_response.status_code == 400

    # 3. Attempt to suspend A -> rejected.
    suspend_a_response = client.post(
        f"/api/v1/users/{admin_a.user_id}/status",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"status": "suspended", "change_reason": "attempt"},
    )
    assert suspend_a_response.status_code == 400

    # 4. Attempt to deactivate A -> rejected.
    deactivate_a_response = client.post(
        f"/api/v1/users/{admin_a.user_id}/status",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"status": "deactivated", "change_reason": "attempt"},
    )
    assert deactivate_a_response.status_code == 400

    # 5. Create User B.
    create_b_response = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "username": "recovery_replacement_admin",
            "display_name": "Replacement Administrator",
            "password": "correct-horse-battery-staple",
        },
    )
    assert create_b_response.status_code == 201
    user_b_id = create_b_response.json()["user_id"]

    # 6. Assign Administrator to B.
    grant_response = client.post(
        f"/api/v1/users/{user_b_id}/roles",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"role_id": admin_role_id},
    )
    assert grant_response.status_code == 201

    # 7. Confirm B can log in.
    token_b = _login(client, "recovery_replacement_admin", "correct-horse-battery-staple")
    assert token_b

    # 8. Revoke Administrator from A -> allowed (B now covers the invariant).
    revoke_a_response = client.delete(
        f"/api/v1/users/{admin_a.user_id}/roles/{admin_role_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert revoke_a_response.status_code == 204

    # 9. Suspend or deactivate A -> allowed.
    deactivate_a_now_response = client.post(
        f"/api/v1/users/{admin_a.user_id}/status",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"status": "deactivated", "change_reason": "recovery account retired"},
    )
    assert deactivate_a_now_response.status_code == 200
    assert deactivate_a_now_response.json()["status"] == "deactivated"

    # 10. Confirm A cannot log in.
    login_a_response = client.post(
        "/api/v1/auth/login",
        json={
            "username": settings.bootstrap_admin_username,
            "password": settings.bootstrap_admin_password,
        },
    )
    assert login_a_response.status_code == 400

    # 11. Confirm B remains able to manage users.
    list_users_response = client.get(
        "/api/v1/users", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert list_users_response.status_code == 200
