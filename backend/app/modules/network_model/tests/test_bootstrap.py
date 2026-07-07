"""Tests for Network Model's permission-catalog registration
(app/modules/network_model/bootstrap.py) — iam-module.md §7.3.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.iam.bootstrap import run_bootstrap as bootstrap_iam
from app.modules.iam.service import IAMService
from app.modules.network_model.bootstrap import run_bootstrap


def test_registers_read_permission(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    permission_ids = {p.permission_id for p in service.list_permissions()}
    assert "network_model.read" in permission_ids


def test_is_idempotent(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)
    run_bootstrap(db_session)  # second run must not duplicate or error

    service = IAMService(db_session)
    permission_ids = [p.permission_id for p in service.list_permissions()]
    assert permission_ids.count("network_model.read") == 1


def test_all_three_baseline_roles_receive_read(db_session: Session) -> None:
    bootstrap_iam(db_session)
    run_bootstrap(db_session)

    service = IAMService(db_session)
    for role_name in ("Administrator", "Engineer", "Viewer"):
        role = next(r for r in service.list_roles() if r.name == role_name)
        grants = {p.permission_id for p in service.list_role_permissions(role.role_id)}
        assert "network_model.read" in grants


def test_running_before_iam_bootstrap_does_not_error(db_session: Session) -> None:
    run_bootstrap(db_session)  # IAM bootstrap has NOT run yet

    service = IAMService(db_session)
    permission_ids = {p.permission_id for p in service.list_permissions()}
    assert "network_model.read" in permission_ids
