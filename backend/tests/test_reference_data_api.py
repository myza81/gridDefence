"""API contract tests for the Core Platform reference-data router —
backend/app/reference_data/router.py. Any authenticated user may list
reference data (no permission gate beyond authentication).
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.reference_data.seed import (
    TRANSFORMER_BREAKER_NUMBERING_CONVENTIONS,
    run_seed,
)


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def _admin_token(client: TestClient, db_session: Session) -> str:
    settings = get_settings()
    bootstrap_iam(db_session)
    return _login(client, settings.bootstrap_admin_username, settings.bootstrap_admin_password)


def test_transformer_breaker_numbering_conventions_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/reference-data/transformer-breaker-numbering-conventions")
    assert response.status_code == 401


def test_transformer_breaker_numbering_conventions_returns_every_seeded_row(
    client: TestClient, db_session: Session
) -> None:
    run_seed(db_session)
    token = _admin_token(client, db_session)

    response = client.get(
        "/api/v1/reference-data/transformer-breaker-numbering-conventions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) == len(TRANSFORMER_BREAKER_NUMBERING_CONVENTIONS)

    # 500/275kV HV side: non-standard, no automatic suggestion.
    non_standard = next(row for row in body if row["side"] == "HV" and row["pattern"] is None)
    assert non_standard["is_standard"] is False
    assert non_standard["notes"] is not None

    # 275/132kV LV side: {N}80 — a real, standard pattern.
    standard = next(row for row in body if row["pattern"] == "{N}80")
    assert standard["side"] == "LV"
    assert standard["is_standard"] is True

    # Every row references real voltage_level ids, not raw text.
    for row in body:
        assert isinstance(row["hv_voltage_level_id"], int)
        assert isinstance(row["lv_voltage_level_id"], int)
        assert row["side"] in ("HV", "LV")
