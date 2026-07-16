"""Continuous Evaluation's own exclusively-owned RQ job (ADR-023: "one
shared queue... owned exclusively by the Continuous Evaluation Engine
module"). Runs on the same worker process as PSS/E Integration's own job
(`app/worker.py`, updated this sprint to listen on both named queues) —
no new worker/infrastructure component, per this sprint's own explicit
scope boundary.

`refresh_evaluation_projection` is the plain, RQ-serializable job
function `ContinuousEvaluationService._enqueue_refresh_job` submits via
the shared `ExecutionEngine` abstraction (`app.core.execution`) — never
called directly by application code. Arguments are plain strings/ints
(stable identifiers), never ORM objects or Pydantic models, per this
sprint's own instructions §14. It opens its own database session (the
standard RQ job / `bootstrap.py` pattern already used elsewhere in this
codebase — see `app.modules.engineering_parameters.bootstrap.main`),
reconstructs `ContinuousEvaluationService` the exact same way any other
caller would, and delegates every actual state transition/evaluation
decision to `ContinuousEvaluationService.run_refresh_worker_cycle` — this
function itself contains no detector logic, no generation-comparison
logic, no projection-state logic of its own.
"""

from __future__ import annotations

import logging
import uuid

from app.db.session import SessionLocal
from app.modules.continuous_evaluation.schemas import EvaluationTarget
from app.modules.findings_publication_governance.findings import SchemeType

logger = logging.getLogger(__name__)

CONTINUOUS_EVALUATION_QUEUE_NAME = "continuous_evaluation"


def refresh_evaluation_projection(
    scheme_type: str,
    scheme_version_id: str,
    requested_generation: int,
    trigger: str,
    correlation_id: str | None,
) -> None:
    # Local import: `service.py` enqueues this exact function, so a
    # module-level import here would create an import cycle
    # (service -> worker -> service). Standard, minimal break of that
    # cycle — see this module's own docstring.
    from app.modules.continuous_evaluation.service import ContinuousEvaluationService

    db = SessionLocal()
    try:
        service = ContinuousEvaluationService(db)
        target = EvaluationTarget(
            scheme_type=SchemeType(scheme_type),
            scheme_version_id=uuid.UUID(scheme_version_id),
        )
        service.run_refresh_worker_cycle(
            target,
            requested_generation=requested_generation,
            trigger=trigger,
            correlation_id=uuid.UUID(correlation_id) if correlation_id else None,
        )
    except Exception:
        db.rollback()
        logger.exception(
            "Continuous Evaluation refresh worker failed for %s/%s", scheme_type, scheme_version_id
        )
        raise
    finally:
        db.close()
