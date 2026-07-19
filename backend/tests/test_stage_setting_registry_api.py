"""API contract tests for the Stage Setting Registry's router — exercises
the full Router -> Service -> Repository stack through HTTP, mirroring
backend/tests/test_engineering_parameters_api.py's pattern.

Stage creation and trigger creation are two separate calls (ADR-025) — a
stage (`.../settings`) carries only `stage_order` and (UVLS only)
`region_scope_id`; a trigger (`.../settings/{stage_setting_id}/triggers`)
carries `trigger_order`, `threshold_value`, and `time_delay_ms`.
`_add_stage_with_trigger` below is the shared one-stage-one-trigger
convenience most tests need.
"""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
from app.modules.stage_setting_registry.bootstrap import (
    run_bootstrap as bootstrap_stage_setting_registry,
)
from app.reference_data.models import Region
from app.reference_data.seed import run_seed


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _admin_setup(client: TestClient, db_session: Session) -> str:
    settings = get_settings()
    bootstrap_iam(db_session)
    bootstrap_stage_setting_registry(db_session)
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


def _region_ids(db_session: Session) -> dict[str, int]:
    run_seed(db_session)
    db_session.commit()
    return {r.code: r.region_id for r in db_session.query(Region).all()}


def _add_stage(
    client: TestClient,
    headers: dict[str, str],
    stage_setting_set_id: str,
    *,
    stage_order: int,
    region_scope_id: int | None = None,
) -> dict:
    response = client.post(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/settings",
        headers=headers,
        json={"stage_order": stage_order, "region_scope_id": region_scope_id},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _add_trigger(
    client: TestClient,
    headers: dict[str, str],
    stage_setting_set_id: str,
    stage_setting_id: str,
    *,
    trigger_order: int = 1,
    threshold_value: float,
    time_delay_ms: int,
) -> dict:
    response = client.post(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/settings/{stage_setting_id}/triggers",
        headers=headers,
        json={
            "trigger_order": trigger_order,
            "threshold_value": threshold_value,
            "time_delay_ms": time_delay_ms,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _add_stage_with_trigger(
    client: TestClient,
    headers: dict[str, str],
    stage_setting_set_id: str,
    *,
    stage_order: int,
    threshold_value: float,
    time_delay_ms: int,
    region_scope_id: int | None = None,
) -> dict:
    stage = _add_stage(
        client,
        headers,
        stage_setting_set_id,
        stage_order=stage_order,
        region_scope_id=region_scope_id,
    )
    _add_trigger(
        client,
        headers,
        stage_setting_set_id,
        stage["stage_setting_id"],
        threshold_value=threshold_value,
        time_delay_ms=time_delay_ms,
    )
    return stage


# --- Authentication -------------------------------------------------------------------


def test_list_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/stage-setting-sets")
    assert response.status_code == 401


def test_create_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/stage-setting-sets", json={"scheme_type": "UFLS", "description": None}
    )
    assert response.status_code == 401


# --- Permission enforcement -------------------------------------------------------------


def test_read_open_to_any_authenticated_user(client: TestClient, db_session: Session) -> None:
    """No specific permission is enforced on read endpoints — mirrors the
    Substation Registry/ALSF/Engineering Parameter Configuration
    precedent."""
    bootstrap_iam(db_session)
    bootstrap_stage_setting_registry(db_session)
    _create_user_with_role(db_session, username="viewer_user", role_name="Viewer")
    token = _login(client, "viewer_user", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/v1/stage-setting-sets", headers=headers)
    assert response.status_code == 200


def test_create_requires_manage_permission(client: TestClient, db_session: Session) -> None:
    bootstrap_iam(db_session)
    bootstrap_stage_setting_registry(db_session)
    _create_user_with_role(db_session, username="viewer_user", role_name="Viewer")
    token = _login(client, "viewer_user", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": None},
    )
    assert response.status_code == 403


def test_publish_requires_publish_permission_not_merely_manage(
    client: TestClient, db_session: Session
) -> None:
    """Engineer holds `.manage` (may create/edit Drafts) but not
    `.publish` — this sprint's own instruction: "Do not assume that every
    user who may edit a Draft may also publish it."""
    bootstrap_iam(db_session)
    bootstrap_stage_setting_registry(db_session)
    _create_user_with_role(db_session, username="engineer_user", role_name="Engineer")
    token = _login(client, "engineer_user", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": None},
    )
    assert create_response.status_code == 201, create_response.text
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]

    _add_stage_with_trigger(
        client,
        headers,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
    )

    publish_response = client.post(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/publish", headers=headers
    )
    assert publish_response.status_code == 403


def test_enter_in_error_requires_dedicated_permission(
    client: TestClient, db_session: Session
) -> None:
    bootstrap_iam(db_session)
    bootstrap_stage_setting_registry(db_session)
    _create_user_with_role(db_session, username="engineer_user", role_name="Engineer")
    token = _login(client, "engineer_user", "correct-horse-battery")
    headers = {"Authorization": f"Bearer {token}"}

    admin_token = _admin_setup(client, db_session)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=admin_headers,
        json={"scheme_type": "UFLS", "description": None},
    )
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]
    _add_stage_with_trigger(
        client,
        admin_headers,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
    )
    client.post(f"/api/v1/stage-setting-sets/{stage_setting_set_id}/publish", headers=admin_headers)

    response = client.post(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/enter-in-error",
        headers=headers,
        json={"change_reason": "Mistake"},
    )
    assert response.status_code == 403


# --- Draft deletion (ADR-024) -----------------------------------------------------------


def test_delete_requires_authentication(client: TestClient) -> None:
    response = client.delete(f"/api/v1/stage-setting-sets/{uuid.uuid4()}")
    assert response.status_code == 401


def test_delete_requires_manage_permission(client: TestClient, db_session: Session) -> None:
    admin_token = _admin_setup(client, db_session)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=admin_headers,
        json={"scheme_type": "UFLS", "description": None},
    )
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]

    _create_user_with_role(db_session, username="viewer_user", role_name="Viewer")
    viewer_token = _login(client, "viewer_user", "correct-horse-battery")
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    response = client.delete(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}", headers=viewer_headers
    )
    assert response.status_code == 403

    # Untouched — still retrievable.
    get_response = client.get(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}", headers=admin_headers
    )
    assert get_response.status_code == 200


def test_delete_missing_set_is_404(client: TestClient, db_session: Session) -> None:
    admin_token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.delete(f"/api/v1/stage-setting-sets/{uuid.uuid4()}", headers=headers)
    assert response.status_code == 404


def test_delete_published_set_is_400_not_500(client: TestClient, db_session: Session) -> None:
    admin_token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {admin_token}"}

    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": None},
    )
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]
    _add_stage_with_trigger(
        client,
        headers,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
    )
    client.post(f"/api/v1/stage-setting-sets/{stage_setting_set_id}/publish", headers=headers)

    response = client.delete(f"/api/v1/stage-setting-sets/{stage_setting_set_id}", headers=headers)
    assert response.status_code == 400
    body = response.json()
    assert "code" in body["detail"]
    assert "message" in body["detail"]

    # Never physically deleted — remains a permanent engineering record.
    get_response = client.get(f"/api/v1/stage-setting-sets/{stage_setting_set_id}", headers=headers)
    assert get_response.status_code == 200


def test_delete_draft_succeeds_and_removes_from_list(
    client: TestClient, db_session: Session
) -> None:
    admin_token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {admin_token}"}

    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": "Deletable via API"},
    )
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]

    delete_response = client.delete(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}", headers=headers
    )
    assert delete_response.status_code == 204

    get_response = client.get(f"/api/v1/stage-setting-sets/{stage_setting_set_id}", headers=headers)
    assert get_response.status_code == 404

    list_response = client.get("/api/v1/stage-setting-sets", headers=headers)
    ids = {item["stage_setting_set_id"] for item in list_response.json()["items"]}
    assert stage_setting_set_id not in ids


def test_audit_log_open_to_any_authenticated_user(client: TestClient, db_session: Session) -> None:
    """Deliberately the *default* precedent (Substation Registry/ALSF),
    not Engineering Parameter Configuration's own documented exception —
    stage-setting-set-architecture.md does not call for a stricter gate."""
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": None},
    )
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]

    _create_user_with_role(db_session, username="viewer_user", role_name="Viewer")
    viewer_token = _login(client, "viewer_user", "correct-horse-battery")
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    response = client.get(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/audit-log", headers=viewer_headers
    )
    assert response.status_code == 200


# --- Request validation and error mapping ------------------------------------------------


def test_create_rejects_unsupported_scheme_type_at_request_validation(
    client: TestClient, db_session: Session
) -> None:
    """EMLS is not a member of the `SchemeType` Literal — FastAPI rejects
    it as a 422 before the service layer is ever reached."""
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "EMLS", "description": None},
    )
    assert response.status_code == 422


def test_get_unknown_set_is_404(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(
        "/api/v1/stage-setting-sets/00000000-0000-0000-0000-000000000000", headers=headers
    )
    assert response.status_code == 404


def test_add_stage_rejects_ufls_region_scope_as_400(
    client: TestClient, db_session: Session
) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": None},
    )
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]

    response = client.post(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/settings",
        headers=headers,
        json={"stage_order": 1, "region_scope_id": 1},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


def test_add_trigger_rejects_non_positive_threshold_at_request_validation(
    client: TestClient, db_session: Session
) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": None},
    )
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]
    stage = _add_stage(client, headers, stage_setting_set_id, stage_order=1)

    response = client.post(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/settings/{stage['stage_setting_id']}/triggers",
        headers=headers,
        json={"trigger_order": 1, "threshold_value": 0, "time_delay_ms": 100},
    )
    assert response.status_code == 422


def test_add_trigger_rejects_duplicate_pair_as_400(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": None},
    )
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]
    stage = _add_stage(client, headers, stage_setting_set_id, stage_order=8)
    _add_trigger(
        client,
        headers,
        stage_setting_set_id,
        stage["stage_setting_id"],
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
    )

    response = client.post(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/settings/{stage['stage_setting_id']}/triggers",
        headers=headers,
        json={"trigger_order": 2, "threshold_value": 48.1, "time_delay_ms": 0},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


def test_publish_empty_set_is_400(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": None},
    )
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]

    response = client.post(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/publish", headers=headers
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


def test_publish_stage_with_zero_triggers_is_400(client: TestClient, db_session: Session) -> None:
    """ADR-025: a stage with no triggers blocks publication, even if
    other stages are fully configured."""
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": None},
    )
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]
    _add_stage_with_trigger(
        client,
        headers,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
    )
    _add_stage(client, headers, stage_setting_set_id, stage_order=2)  # no trigger

    response = client.post(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/publish", headers=headers
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "validation_error"


def test_enter_in_error_without_reason_is_422(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": None},
    )
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]
    _add_stage_with_trigger(
        client,
        headers,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
    )
    client.post(f"/api/v1/stage-setting-sets/{stage_setting_set_id}/publish", headers=headers)

    response = client.post(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/enter-in-error",
        headers=headers,
        json={},
    )
    assert response.status_code == 422


# --- List filters and deterministic ordering ----------------------------------------------


def test_list_filters_by_scheme_type(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": "UFLS set"},
    )
    client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UVLS", "description": "UVLS set"},
    )

    response = client.get(
        "/api/v1/stage-setting-sets", headers=headers, params={"scheme_type": "UFLS"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["scheme_type"] == "UFLS"


def test_list_settings_deterministic_ordering(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": None},
    )
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]

    # Insert out of order — response must always come back ordered by
    # stage_order (CLAUDE.md A9 deterministic ordering).
    _add_stage(client, headers, stage_setting_set_id, stage_order=2)
    _add_stage(client, headers, stage_setting_set_id, stage_order=1)

    response = client.get(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/settings", headers=headers
    )
    assert response.status_code == 200
    orders = [s["stage_order"] for s in response.json()]
    assert orders == [1, 2]


def test_list_triggers_deterministic_ordering(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": None},
    )
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]
    stage = _add_stage(client, headers, stage_setting_set_id, stage_order=8)

    _add_trigger(
        client,
        headers,
        stage_setting_set_id,
        stage["stage_setting_id"],
        trigger_order=2,
        threshold_value=49.3,
        time_delay_ms=60000,
    )
    _add_trigger(
        client,
        headers,
        stage_setting_set_id,
        stage["stage_setting_id"],
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
    )

    response = client.get(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/settings/{stage['stage_setting_id']}/triggers",
        headers=headers,
    )
    assert response.status_code == 200
    orders = [t["trigger_order"] for t in response.json()]
    assert orders == [1, 2]


# --- Complete successful lifecycle ---------------------------------------------------------


def test_complete_ufls_lifecycle(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UFLS", "description": "5-stage UFLS design"},
    )
    assert create_response.status_code == 201, create_response.text
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]
    assert create_response.json()["status"] == "DRAFT"

    stage = _add_stage(client, headers, stage_setting_set_id, stage_order=1)
    stage_setting_id = stage["stage_setting_id"]

    trigger = _add_trigger(
        client,
        headers,
        stage_setting_set_id,
        stage_setting_id,
        threshold_value=49.5,
        time_delay_ms=100,
    )
    assert trigger["threshold_unit"] == "Hz"
    trigger_id = trigger["stage_setting_trigger_id"]

    update_response = client.patch(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/settings/{stage_setting_id}/triggers/{trigger_id}",
        headers=headers,
        json={"time_delay_ms": 150, "change_reason": "Coordination margin adjustment"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["time_delay_ms"] == 150

    # A second, independent operating criterion for the same stage — the
    # worked UAT example's own shape (fast trip + slower backup trip).
    second_trigger = _add_trigger(
        client,
        headers,
        stage_setting_set_id,
        stage_setting_id,
        trigger_order=2,
        threshold_value=48.1,
        time_delay_ms=0,
    )
    assert second_trigger["trigger_order"] == 2

    get_stage_response = client.get(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/settings/{stage_setting_id}/triggers",
        headers=headers,
    )
    assert len(get_stage_response.json()) == 2

    _add_stage_with_trigger(
        client,
        headers,
        stage_setting_set_id,
        stage_order=2,
        threshold_value=47.5,
        time_delay_ms=200,
    )

    publish_response = client.post(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/publish", headers=headers
    )
    assert publish_response.status_code == 200, publish_response.text
    assert publish_response.json()["status"] == "PUBLISHED"
    published_stage = next(
        s for s in publish_response.json()["settings"] if s["stage_setting_id"] == stage_setting_id
    )
    assert len(published_stage["triggers"]) == 2

    # Immutable now.
    blocked_response = client.post(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/settings",
        headers=headers,
        json={"stage_order": 3},
    )
    assert blocked_response.status_code == 400

    enter_in_error_response = client.post(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/enter-in-error",
        headers=headers,
        json={"change_reason": "Superseded by a corrected design"},
    )
    assert enter_in_error_response.status_code == 200
    assert enter_in_error_response.json()["status"] == "ENTERED_IN_ERROR"

    audit_response = client.get(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/audit-log", headers=headers
    )
    assert audit_response.status_code == 200
    # created (set), stage created x2, trigger created x3, trigger updated,
    # published, entered_in_error.
    assert audit_response.json()["total"] >= 8


def test_complete_uvls_lifecycle_with_region_scope(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    region_ids = _region_ids(db_session)

    create_response = client.post(
        "/api/v1/stage-setting-sets",
        headers=headers,
        json={"scheme_type": "UVLS", "description": "Regional UVLS design"},
    )
    stage_setting_set_id = create_response.json()["stage_setting_set_id"]

    stage = _add_stage(
        client,
        headers,
        stage_setting_set_id,
        stage_order=1,
        region_scope_id=region_ids["NORTH"],
    )
    assert stage["region_scope_id"] == region_ids["NORTH"]

    trigger = _add_trigger(
        client,
        headers,
        stage_setting_set_id,
        stage["stage_setting_id"],
        threshold_value=0.90,
        time_delay_ms=500,
    )
    assert trigger["threshold_unit"] == "p.u."

    _add_stage_with_trigger(
        client,
        headers,
        stage_setting_set_id,
        stage_order=2,
        threshold_value=0.85,
        time_delay_ms=700,
        region_scope_id=region_ids["NORTH"],
    )

    publish_response = client.post(
        f"/api/v1/stage-setting-sets/{stage_setting_set_id}/publish", headers=headers
    )
    assert publish_response.status_code == 200, publish_response.text
