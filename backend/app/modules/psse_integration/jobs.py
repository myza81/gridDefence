"""RQ job wrapper for PSS/E Integration Commit (implementation-plan.md §4;
psse-integration-module.md §18) — the only place in this module that opens
its own database session, since RQ jobs run in a worker process outside any
FastAPI request context (`app.worker`'s own process, not `app.db.session
.get_db`'s request-scoped generator).

Preview has no job wrapper: it executes synchronously, in-request, directly
against `PsseIntegrationService` (execution-model refinement — §8.9a; it
never persists anything, so it never needed a worker-process session).

Business logic never lives here — the wrapper is a thin adapter: open a
session, call into `PsseIntegrationService`, serialize the result into a
JSON-safe dict (kept plain-dict rather than pickled ORM objects so
`router.py`'s `JobStatus.result` stays a stable, inspectable shape), and
close the session. Errors are not caught here: letting them propagate marks
the RQ job `failed`, and `Job.exc_info` carries the traceback for
`router.py`'s job-status endpoint to surface via `JobStatus.error`.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.db.session import SessionLocal
from app.modules.psse_integration.service import PsseIntegrationService


def _batch_result(batch: Any) -> dict[str, Any]:
    return {
        "batch_id": str(batch.batch_id),
        "source_file_reference": batch.source_file_reference,
        "import_type": batch.import_type,
        "status": batch.status,
        "computed_signature": batch.computed_signature,
        "topology_version_id": (
            str(batch.topology_version_id) if batch.topology_version_id else None
        ),
        "load_snapshot_id": (str(batch.load_snapshot_id) if batch.load_snapshot_id else None),
        "warnings": batch.warnings,
        "fatal_error": batch.fatal_error,
    }


def run_commit_job(
    file_content: str, source_file_reference: str, actor_user_id: str
) -> dict[str, Any]:
    db = SessionLocal()
    try:
        service = PsseIntegrationService(db)
        batch = service.commit(file_content, source_file_reference, uuid.UUID(actor_user_id))
        db.commit()
        return _batch_result(batch)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
