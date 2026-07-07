"""Tests for the RQ job wrapper (jobs.py) — Commit only.

Preview has no job wrapper (execution-model refinement,
psse-integration-module.md §8.9a — it runs synchronously, in-request,
directly against `PsseIntegrationService`); its own coverage lives in
`test_service.py`'s `test_preview_*` tests, exercised through the same
`db_session` fixture every other synchronous service call already uses.

The Commit job wrapper opens its own `SessionLocal()` session — the real,
module-level `SessionLocal` bound to the application's configured database
engine, since RQ jobs run in a worker process outside any FastAPI request
context. For these tests, that module-level `SessionLocal` is monkeypatched
to a sessionmaker bound to the *same engine* the `db_session` fixture
already uses, so the job's writes are visible to the test's own assertions
(and, for the shared-connection in-memory SQLite case, are the same
underlying connection entirely).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.modules.psse_integration import jobs as jobs_module
from app.modules.psse_integration.exceptions import NoCurrentTopologyVersionError
from app.modules.psse_integration.models import RawFileImportBatch

_FULL_TOPOLOGY_RAW = """0,100.0,34,0,1,50.0
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

_LOAD_ONLY_RAW = """0 / END OF SYSTEM-WIDE DATA, BEGIN LOAD DATA
100,'1',1,1,1,15.0,7.0
0 / END OF LOAD DATA, BEGIN GENERATOR DATA
Q
"""


@pytest.fixture(autouse=True)
def _use_test_engine_for_jobs(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    test_session_factory = sessionmaker(
        bind=db_session.bind, autoflush=False, autocommit=False, future=True
    )
    monkeypatch.setattr(jobs_module, "SessionLocal", test_session_factory)


def test_run_commit_job_persists_and_returns_batch_summary(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    result = jobs_module.run_commit_job(_FULL_TOPOLOGY_RAW, "case1.raw", str(actor_user_id))
    assert result["import_type"] == "FULL_TOPOLOGY_WITH_LOAD"
    assert result["status"] in ("Completed", "CompletedWithWarnings")

    batch = db_session.get(RawFileImportBatch, uuid.UUID(result["batch_id"]))
    assert batch is not None
    assert batch.source_file_reference == "case1.raw"


def test_run_commit_job_propagates_business_errors_for_rq_to_mark_failed(
    actor_user_id: uuid.UUID,
) -> None:
    with pytest.raises(NoCurrentTopologyVersionError):
        jobs_module.run_commit_job(_LOAD_ONLY_RAW, "loads.raw", str(actor_user_id))


def test_run_commit_job_rolls_back_on_error(db_session: Session, actor_user_id: uuid.UUID) -> None:
    with pytest.raises(NoCurrentTopologyVersionError):
        jobs_module.run_commit_job(_LOAD_ONLY_RAW, "loads.raw", str(actor_user_id))
    # No partial batch row should have been left behind.
    assert db_session.query(RawFileImportBatch).count() == 0
