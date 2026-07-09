"""API contract tests for PSS/E Integration's router — docs/architecture/
psse-integration-module.md §12/§8a/§8.9a/§8.9c, CLAUDE.md A9/A11. Exercises
the full Router -> Service -> Repository stack through HTTP, mirroring
backend/tests/test_equipment_registry_api.py's pattern.

**Preview executes synchronously, in-request** (execution-model refinement,
§8.9a) — it calls `PsseIntegrationService` directly through the same
request-scoped `get_db` session every other synchronous endpoint uses, so
no job-wrapper monkeypatching is needed for it at all.

**Commit's execution mode is configurable** (Phase 6 — Execution Engine,
§8.9c). `execution_mode` defaults to "direct" — no Redis, no RQ, no worker
process — which is what most of these tests exercise implicitly via
`_submit_commit`'s generic 200-or-202 handling. A handful of tests force
`execution_mode="queue"` explicitly to prove that path still works
unchanged (Redis+RQ, via `fakeredis` when `RQ_ASYNC=false` — set globally
in backend/conftest.py — so no real Redis server or worker is needed even
for those). The job wrapper's own `SessionLocal`
(app/modules/psse_integration/jobs.py) is monkeypatched to the same engine
the test's `db_session` fixture uses in both modes, so the job's writes are
visible to this test's own HTTP assertions afterward.
"""

from __future__ import annotations

import io
import uuid

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
from app.modules.psse_integration import jobs as jobs_module
from app.modules.psse_integration.bootstrap import run_bootstrap as bootstrap_psse_integration

_FULL_TOPOLOGY_RAW = b"""0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.02,0.0
200,'IGBK132',132.0,1,1,1,1,1.01,-1.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'1',0.001,0.01,0.0002
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""

# Same topology, plus two generators — for the generator-count defect fix
# (Phase 6 UAT: `generator_count` was hardcoded to 0 regardless of actual
# NetworkGenerator rows).
_FULL_TOPOLOGY_WITH_GENERATORS_RAW = b"""0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.02,0.0
200,'IGBK132',132.0,1,1,1,1,1.01,-1.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
100,'1',50.0,10.0
200,'1',30.0,5.0
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'1',0.001,0.01,0.0002
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""


@pytest.fixture(autouse=True)
def _use_test_engine_for_jobs(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    test_session_factory = sessionmaker(
        bind=db_session.bind, autoflush=False, autocommit=False, future=True
    )
    monkeypatch.setattr(jobs_module, "SessionLocal", test_session_factory)


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _admin_setup(client: TestClient, db_session: Session) -> str:
    settings = get_settings()
    bootstrap_iam(db_session)
    bootstrap_psse_integration(db_session)
    return _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)


def _viewer_only_token(client: TestClient, db_session: Session, username: str) -> str:
    iam = IAMService(db_session)
    iam.create_user(
        username=username,
        display_name=username,
        email=None,
        password="correct-horse-battery",
        actor_user_id=None,
    )
    db_session.commit()
    return _login(client, username, "correct-horse-battery")


def _submit_commit(
    client: TestClient,
    headers: dict,
    filename: str = "case1.raw",
    content: bytes = _FULL_TOPOLOGY_RAW,
) -> dict:
    """Submits Commit and returns the resulting batch dict regardless of
    execution mode (§8.9c): Direct mode (default) responds `200` with the
    result immediately; Queue mode responds `202` with a job id, polled via
    `GET .../jobs/{job_id}` exactly as before this refactor."""
    response = client.post(
        "/api/v1/psse-integration/imports/commit",
        headers=headers,
        files={"file": (filename, io.BytesIO(content), "text/plain")},
    )
    assert response.status_code in (200, 202), response.text
    if response.status_code == 200:
        return response.json()

    job_id = response.json()["job_id"]
    status_response = client.get(f"/api/v1/psse-integration/imports/jobs/{job_id}", headers=headers)
    assert status_response.status_code == 200, status_response.text
    body = status_response.json()
    assert body["status"] == "finished", body
    return body["result"]


def _use_queue_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "execution_mode", "queue")


def _upload_preview(client: TestClient, headers: dict, filename: str = "case1.raw") -> dict:
    """Preview executes synchronously (§8.9a) — a direct 200 with the
    `PreviewResult` body, never a job to poll."""
    response = client.post(
        "/api/v1/psse-integration/imports/preview",
        headers=headers,
        files={"file": (filename, io.BytesIO(_FULL_TOPOLOGY_RAW), "text/plain")},
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- Authentication / authorization --------------------------------------------------


def test_preview_requires_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/v1/psse-integration/imports/preview",
        files={"file": ("x.raw", io.BytesIO(b"Q\n"), "text/plain")},
    )
    assert response.status_code == 401


def test_preview_without_import_permission_is_forbidden(
    client: TestClient, db_session: Session
) -> None:
    bootstrap_iam(db_session)
    token = _viewer_only_token(client, db_session, "viewer1")
    response = client.post(
        "/api/v1/psse-integration/imports/preview",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("x.raw", io.BytesIO(b"Q\n"), "text/plain")},
    )
    assert response.status_code == 403


def test_preview_response_includes_parsed_records_for_inspector(
    client: TestClient, db_session: Session
) -> None:
    """Operational Context Inspector (§8.9e) — `PreviewResult.model_validate`
    picks up the new parsed-record fields automatically, with zero router.py
    changes, confirming the schema/service extension is sufficient on its
    own."""
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    result = _upload_preview(client, headers)
    assert result["source_file_reference"] == "case1.raw"
    assert result["base_mva"] == 100.0
    assert len(result["buses"]) == 2
    assert result["buses"][0]["bus_number"] == 100
    assert len(result["branches"]) == 1
    assert result["transformers"] == []
    assert result["loads"] == []
    assert result["generators"] == []


def test_preview_response_includes_raw_file_information(
    client: TestClient, db_session: Session
) -> None:
    """RAW File Information (Phase 7 discovery-support enhancement, §8.9f)
    — header metadata is included in the same Preview response, with zero
    router.py changes. This fixture's header has no case-identification
    title lines or writer comment, so those two fields are gracefully
    `None`."""
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    result = _upload_preview(client, headers)
    assert result["frequency_hz"] == 50.0
    assert result["case_description"] is None
    assert result["raw_created"] is None


def test_preview_response_includes_bus_classification(
    client: TestClient, db_session: Session
) -> None:
    """Operational Bus classification (Phase 7A, EDR-007 §4) — a
    naming-pattern classification exposed alongside every parsed Bus
    record in the same Preview response, with zero router.py changes."""
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    result = _upload_preview(client, headers)
    assert len(result["buses"]) == 2
    assert all(bus["bus_classification"] == "SWITCHYARD_BUS" for bus in result["buses"])


# --- Preview execution model (§8.9a) ---------------------------------------------


def test_preview_executes_synchronously_with_no_job_to_poll(
    client: TestClient, db_session: Session
) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    result = _upload_preview(client, headers)
    assert result["import_type"] == "FULL_TOPOLOGY_WITH_LOAD"
    # No job_id is returned at all — there is nothing to poll.
    assert "job_id" not in result


def test_preview_of_an_empty_file_returns_a_structured_400_not_a_failed_job(
    client: TestClient, db_session: Session
) -> None:
    # Only genuinely empty content is a hard parse failure (raw_parser.py's
    # own "garbage is tolerated, not fatal" rule, test_raw_parser.py) — the
    # point here is that the failure now surfaces as a structured HTTP error
    # response, never as a "failed" job someone has to poll for.
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/psse-integration/imports/preview",
        headers=headers,
        files={"file": ("empty.raw", io.BytesIO(b""), "text/plain")},
    )
    assert response.status_code == 400, response.text
    assert response.json()["detail"]["code"] == "validation_error"


# --- Commit execution mode (Phase 6 — Execution Engine, §8.9c) --------------------


def test_commit_completes_directly_in_default_direct_mode_with_no_job_to_poll(
    client: TestClient, db_session: Session
) -> None:
    """Direct mode is the default (app.core.config.Settings.execution_mode)
    — Commit responds 200 immediately, exactly like Preview, with no job id
    anywhere in the response."""
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/psse-integration/imports/commit",
        headers=headers,
        files={"file": ("case1.raw", io.BytesIO(_FULL_TOPOLOGY_RAW), "text/plain")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] in ("Completed", "CompletedWithWarnings")
    assert "job_id" not in body


def test_commit_in_direct_mode_never_touches_redis_or_rq(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The success criterion this refactor exists for: a developer with no
    Redis running at all can still complete Commit, because Direct mode
    never calls into app.core.queue in the first place."""

    def _fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("Direct mode must never touch app.core.queue.get_redis_connection")

    monkeypatch.setattr("app.core.queue.get_redis_connection", _fail_if_called)

    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        "/api/v1/psse-integration/imports/commit",
        headers=headers,
        files={"file": ("case1.raw", io.BytesIO(_FULL_TOPOLOGY_RAW), "text/plain")},
    )
    assert response.status_code == 200, response.text


def test_commit_via_queue_mode_still_returns_202_and_polls_to_completion(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Queue mode remains fully supported — unchanged 202 + job id + poll,
    for deployments that opt into it."""
    _use_queue_mode(monkeypatch)
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/psse-integration/imports/commit",
        headers=headers,
        files={"file": ("case1.raw", io.BytesIO(_FULL_TOPOLOGY_RAW), "text/plain")},
    )
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]

    status_response = client.get(f"/api/v1/psse-integration/imports/jobs/{job_id}", headers=headers)
    assert status_response.status_code == 200, status_response.text
    body = status_response.json()
    assert body["status"] == "finished", body
    assert body["result"]["status"] in ("Completed", "CompletedWithWarnings")


def test_commit_returns_503_when_the_queue_is_unavailable_in_queue_mode(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Direct mode (default) never depends on Redis at all (see above);
    Queue mode still does, and must fail as a clear, structured 503 rather
    than an unhandled 500 if the queue cannot be reached."""
    _use_queue_mode(monkeypatch)
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    def _raise_connection_error(*args: object, **kwargs: object) -> None:
        raise redis.exceptions.ConnectionError("Connection refused")

    monkeypatch.setattr("app.core.execution.enqueue", _raise_connection_error)

    response = client.post(
        "/api/v1/psse-integration/imports/commit",
        headers=headers,
        files={"file": ("case1.raw", io.BytesIO(_FULL_TOPOLOGY_RAW), "text/plain")},
    )
    assert response.status_code == 503, response.text
    assert response.json()["detail"]["code"] == "queue_unavailable"


def test_list_batches_requires_only_authentication(client: TestClient, db_session: Session) -> None:
    bootstrap_iam(db_session)
    token = _viewer_only_token(client, db_session, "viewer2")
    response = client.get(
        "/api/v1/psse-integration/imports/batches", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_activate_without_activate_permission_is_forbidden(
    client: TestClient, db_session: Session
) -> None:
    admin_token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {admin_token}"}
    result = _submit_commit(client, headers)

    engineer_token = _viewer_only_token(client, db_session, "engineer_no_activate")
    response = client.post(
        f"/api/v1/psse-integration/imports/batches/{result['batch_id']}/activate",
        headers={"Authorization": f"Bearer {engineer_token}"},
        json={"change_reason": "trying anyway"},
    )
    assert response.status_code == 403


# --- Full preview -> commit -> activate flow ------------------------------------------


def test_full_preview_commit_activate_flow(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    preview_result = _upload_preview(client, headers)
    assert preview_result["import_type"] == "FULL_TOPOLOGY_WITH_LOAD"
    assert preview_result["topology_reused"] is False

    commit_result = _submit_commit(client, headers)
    batch_id = commit_result["batch_id"]
    assert commit_result["status"] in ("Completed", "CompletedWithWarnings")

    list_response = client.get("/api/v1/psse-integration/imports/batches", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    get_response = client.get(
        f"/api/v1/psse-integration/imports/batches/{batch_id}", headers=headers
    )
    assert get_response.status_code == 200
    assert get_response.json()["imported_by"]["username"] == get_settings().bootstrap_admin_username

    activate_response = client.post(
        f"/api/v1/psse-integration/imports/batches/{batch_id}/activate",
        headers=headers,
        json={"change_reason": "Go live"},
    )
    assert activate_response.status_code == 200, activate_response.text
    assert activate_response.json()["status"] in ("Completed", "CompletedWithWarnings")

    current_response = client.get("/api/v1/psse-integration/current-status", headers=headers)
    assert current_response.status_code == 200
    current_body = current_response.json()
    assert current_body["current_topology_version"]["status"] == "Current"
    assert current_body["current_load_snapshot"]["status"] == "Current"
    # This fixture has no GENERATOR DATA records — zero must genuinely mean
    # zero, not merely be a coincidence of the fixed defect (§8.9d UAT).
    assert current_body["current_load_snapshot"]["generator_count"] == 0

    topology_version_id = current_body["current_topology_version"]["topology_version_id"]
    tv_response = client.get(
        f"/api/v1/psse-integration/topology-versions/{topology_version_id}", headers=headers
    )
    assert tv_response.status_code == 200
    assert tv_response.json()["bus_count"] == 2
    assert tv_response.json()["branch_count"] == 1

    map_response = client.get(
        f"/api/v1/psse-integration/topology-versions/{topology_version_id}/equipment-map",
        headers=headers,
    )
    assert map_response.status_code == 200
    assert map_response.json()["total"] == 0  # no Equipment Registry circuits exist yet


def test_current_status_and_load_snapshot_apis_report_the_actual_generator_count(
    client: TestClient, db_session: Session
) -> None:
    """Generator-count defect fix (Phase 6 UAT): `NetworkGenerator` rows
    were always persisted correctly; only `generator_count` in API
    responses was wrong (hardcoded to 0). Verified here through the real
    HTTP API, with a snapshot that genuinely has two generators."""
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/v1/psse-integration/imports/commit",
        headers=headers,
        files={
            "file": ("case-gen.raw", io.BytesIO(_FULL_TOPOLOGY_WITH_GENERATORS_RAW), "text/plain")
        },
    )
    assert response.status_code == 200, response.text
    batch = response.json()

    activate_response = client.post(
        f"/api/v1/psse-integration/imports/batches/{batch['batch_id']}/activate",
        headers=headers,
        json={"change_reason": "Go live"},
    )
    assert activate_response.status_code == 200, activate_response.text

    load_snapshot_id = batch["load_snapshot_id"]
    load_snapshot_response = client.get(
        f"/api/v1/psse-integration/load-snapshots/{load_snapshot_id}", headers=headers
    )
    assert load_snapshot_response.status_code == 200
    assert load_snapshot_response.json()["generator_count"] == 2

    current_response = client.get("/api/v1/psse-integration/current-status", headers=headers)
    assert current_response.status_code == 200
    assert current_response.json()["current_load_snapshot"]["generator_count"] == 2


def test_activate_unknown_batch_returns_404(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        f"/api/v1/psse-integration/imports/batches/{uuid.uuid4()}/activate",
        headers=headers,
        json={"change_reason": "x"},
    )
    assert response.status_code == 404


def test_get_unknown_batch_returns_404(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(
        f"/api/v1/psse-integration/imports/batches/{uuid.uuid4()}", headers=headers
    )
    assert response.status_code == 404


def test_get_unknown_job_returns_404(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(
        "/api/v1/psse-integration/imports/jobs/00000000-0000-0000-0000-000000000000",
        headers=headers,
    )
    assert response.status_code == 404


# --- Correlated Operational Model (Phase 7C) ---------------------------------------


def test_preview_response_includes_bus_correlation_fields(
    client: TestClient, db_session: Session
) -> None:
    """Correlated Operational Model Preview enrichment (Phase 7C) — Bus-
    level correlation status is computed at Preview time (zero
    persistence) and exposed alongside every parsed Bus record, with zero
    Substation Registry data seeded in this test's own database."""
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}

    result = _upload_preview(client, headers)
    assert len(result["buses"]) == 2
    for bus in result["buses"]:
        assert bus["correlation_status"] == "UNMATCHED_OPERATIONAL"
        assert bus["substation_id"] is None
        assert bus["in_service"] is True


def test_operational_bus_views_endpoint_returns_correlation_status(
    client: TestClient, db_session: Session
) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    batch = _submit_commit(client, headers)
    topology_version_id = batch["topology_version_id"]

    response = client.get(
        f"/api/v1/psse-integration/topology-versions/{topology_version_id}/operational-model/buses",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert {bus["bus_number"] for bus in body["items"]} == {100, 200}
    assert all(bus["correlation_status"] == "UNMATCHED_OPERATIONAL" for bus in body["items"])


def test_operational_bus_views_endpoint_requires_authentication(client: TestClient) -> None:
    response = client.get(
        f"/api/v1/psse-integration/topology-versions/{uuid.uuid4()}/operational-model/buses"
    )
    assert response.status_code == 401


def test_operational_bus_view_endpoint_single_bus(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    batch = _submit_commit(client, headers)
    topology_version_id = batch["topology_version_id"]

    response = client.get(
        f"/api/v1/psse-integration/topology-versions/{topology_version_id}"
        "/operational-model/buses/100",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["bus_number"] == 100


def test_operational_bus_view_endpoint_unknown_bus_returns_404(
    client: TestClient, db_session: Session
) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    batch = _submit_commit(client, headers)
    topology_version_id = batch["topology_version_id"]

    response = client.get(
        f"/api/v1/psse-integration/topology-versions/{topology_version_id}"
        "/operational-model/buses/999",
        headers=headers,
    )
    assert response.status_code == 404


def test_operational_branch_views_endpoint(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    batch = _submit_commit(client, headers)
    topology_version_id = batch["topology_version_id"]

    response = client.get(
        f"/api/v1/psse-integration/topology-versions/{topology_version_id}"
        "/operational-model/branches",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["from_bus_number"] == 100
    assert body["items"][0]["correlation_status"] == "UNMATCHED_OPERATIONAL"


def test_operational_transformer_views_endpoint(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    batch = _submit_commit(client, headers)
    topology_version_id = batch["topology_version_id"]

    response = client.get(
        f"/api/v1/psse-integration/topology-versions/{topology_version_id}"
        "/operational-model/transformers",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "page": 1, "page_size": 50, "total": 0}


def test_operational_load_views_endpoint(client: TestClient, db_session: Session) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    batch = _submit_commit(client, headers)
    load_snapshot_id = batch["load_snapshot_id"]

    response = client.get(
        f"/api/v1/psse-integration/load-snapshots/{load_snapshot_id}/operational-model/loads",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 0


def test_operational_load_views_endpoint_unknown_snapshot_returns_404(
    client: TestClient, db_session: Session
) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get(
        f"/api/v1/psse-integration/load-snapshots/{uuid.uuid4()}/operational-model/loads",
        headers=headers,
    )
    assert response.status_code == 404


# --- Bus Correlation Refresh (Phase 7D UAT follow-up, Finding 1) ---------------------


def test_refresh_bus_correlation_endpoint_returns_summary(
    client: TestClient, db_session: Session
) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    batch = _submit_commit(client, headers)
    topology_version_id = batch["topology_version_id"]

    response = client.post(
        f"/api/v1/psse-integration/topology-versions/{topology_version_id}"
        "/operational-model/refresh-correlation",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["topology_version_id"] == topology_version_id
    assert body["buses_processed"] == 2
    assert body["buses_correlated"] == 0
    assert body["buses_unmatched"] == 2
    assert body["buses_outside_scope"] == 0
    assert body["updated_count"] == 0


def test_refresh_bus_correlation_endpoint_requires_authentication(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/psse-integration/topology-versions/{uuid.uuid4()}"
        "/operational-model/refresh-correlation"
    )
    assert response.status_code == 401


def test_refresh_bus_correlation_endpoint_without_import_permission_is_forbidden(
    client: TestClient, db_session: Session
) -> None:
    bootstrap_iam(db_session)
    token = _viewer_only_token(client, db_session, "viewer1")
    response = client.post(
        f"/api/v1/psse-integration/topology-versions/{uuid.uuid4()}"
        "/operational-model/refresh-correlation",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_refresh_bus_correlation_endpoint_unknown_topology_version_returns_404(
    client: TestClient, db_session: Session
) -> None:
    token = _admin_setup(client, db_session)
    headers = {"Authorization": f"Bearer {token}"}
    response = client.post(
        f"/api/v1/psse-integration/topology-versions/{uuid.uuid4()}"
        "/operational-model/refresh-correlation",
        headers=headers,
    )
    assert response.status_code == 404


# --- AMBIGUOUS Correlation Status — API integration (Phase 7D, Finding 2) -----------

_AMBIGUOUS_BRANCH_RAW = b"""0,100.0,34,0,1,50.0
0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA
100,'PKLG132',132.0,1,1,1,1,1.02,0.0
200,'IGBK132',132.0,1,1,1,1,1.01,-1.0
0 / END OF BUS DATA, BEGIN LOAD DATA
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
0 / END OF GENERATOR DATA, BEGIN BRANCH DATA
100,200,'2',0.001,0.01,0.0002
100,200,'3',0.002,0.02,0.0003
0 / END OF BRANCH DATA, BEGIN TRANSFORMER DATA
0 / END OF TRANSFORMER DATA, BEGIN AREA DATA
Q
"""


def test_ambiguous_discrepancy_visible_through_the_equipment_map_api(
    client: TestClient, db_session: Session
) -> None:
    """Same real, persisted multi-candidate scenario as
    test_service.py::test_ambiguous_correlation_status_from_real_persisted_multi_candidate_discrepancy,
    verified through the actual HTTP API path (`GET .../equipment-map`) a
    user's browser calls, not just the service layer directly."""
    from app.modules.equipment_registry.service import EquipmentRegistryService, TerminalInput
    from app.modules.substation_registry.service import SubstationService
    from app.reference_data.models import (
        GridOwner,
        LineType,
        OperationalStatus,
        Region,
        State,
        VoltageLevel,
    )
    from app.reference_data.seed import run_seed

    admin_user = bootstrap_iam(db_session)
    bootstrap_psse_integration(db_session)
    settings = get_settings()
    token = _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)
    headers = {"Authorization": f"Bearer {token}"}
    admin_user_id = admin_user.user_id

    run_seed(db_session)
    db_session.commit()
    voltage_level = db_session.query(VoltageLevel).filter_by(label="500kV").one()
    line_type = db_session.query(LineType).filter_by(code="OVERHEAD").one()
    region = db_session.query(Region).filter_by(code="NORTH").one()
    state = db_session.query(State).filter_by(code="SEL").one()
    grid_owner = db_session.query(GridOwner).filter_by(code="TNB").one()
    active_status_id = (
        db_session.query(OperationalStatus).filter_by(code="ACTIVE").one().operational_status_id
    )

    sub_service = SubstationService(db_session)
    eq_service = EquipmentRegistryService(db_session)
    pklg = sub_service.create_substation(
        mnemonic="PKLG",
        official_name="PKLG Substation",
        region_id=region.region_id,
        state_id=state.state_id,
        grid_owner_id=grid_owner.grid_owner_id,
        operational_status_id=active_status_id,
        psse_bus_number=None,
        latitude=None,
        longitude=None,
        commissioned_date=None,
        remarks=None,
        actor_user_id=admin_user_id,
    )
    igbk = sub_service.create_substation(
        mnemonic="IGBK",
        official_name="IGBK Substation",
        region_id=region.region_id,
        state_id=state.state_id,
        grid_owner_id=grid_owner.grid_owner_id,
        operational_status_id=active_status_id,
        psse_bus_number=None,
        latitude=None,
        longitude=None,
        commissioned_date=None,
        remarks=None,
        actor_user_id=admin_user_id,
    )
    db_session.commit()
    pklg_yard = eq_service.create_voltage_yard(
        substation_id=pklg.substation_id,
        voltage_level_id=voltage_level.voltage_level_id,
        actor_user_id=admin_user_id,
    )
    igbk_yard = eq_service.create_voltage_yard(
        substation_id=igbk.substation_id,
        voltage_level_id=voltage_level.voltage_level_id,
        actor_user_id=admin_user_id,
    )
    db_session.commit()
    eq_service.create_circuit(
        bay_number="1",
        voltage_level_id=voltage_level.voltage_level_id,
        line_type_id=line_type.line_type_id,
        operational_status_id=active_status_id,
        is_interconnector=False,
        remarks=None,
        terminals=[
            TerminalInput(voltage_yard_id=pklg_yard.voltage_yard_id, breaker_number="CB1"),
            TerminalInput(voltage_yard_id=igbk_yard.voltage_yard_id, breaker_number="CB2"),
        ],
        actor_user_id=admin_user_id,
    )
    db_session.commit()

    batch = _submit_commit(client, headers, content=_AMBIGUOUS_BRANCH_RAW)
    topology_version_id = batch["topology_version_id"]

    response = client.get(
        f"/api/v1/psse-integration/topology-versions/{topology_version_id}/equipment-map",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 2
    assert all(item["match_outcome"] == "discrepancy" for item in items)
    assert all(item["topology_branch_id"] is None for item in items)
    assert all(item["topology_transformer_id"] is None for item in items)
