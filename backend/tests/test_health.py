"""Phase 0 smoke test: the app starts and the unversioned health check works."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "environment" in body


def test_health_is_not_under_the_versioned_api_prefix() -> None:
    """Health checks are infrastructure, not a business API — unversioned by design."""
    response = client.get("/api/v1/health")

    assert response.status_code == 404
