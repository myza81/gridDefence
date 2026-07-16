"""Continuous Evaluation persistence access (CLAUDE.md §14) — pure
persistence, no business rules, no transition validation, no generation
comparison, no EvaluationRequest construction, no detector execution, no
job enqueueing (this sprint's own instructions §20). All of that lives in
`service.py`.

`get_by_target(..., for_update=True)` issues `SELECT ... FOR UPDATE`
(PostgreSQL: genuine row-level locking, serializing concurrent
`request_refresh`/worker-claim calls against the same target; SQLite:
accepted as a no-op — this project's own established convention, per
`findings_publication_governance/repository.py`'s own precedent of
tests that are PostgreSQL-only where SQLite cannot validate the
behaviour, this sprint's own instructions §20, §28).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.continuous_evaluation.models import EvaluationProjection


class EvaluationProjectionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_target(
        self, scheme_type: str, scheme_version_id: uuid.UUID, *, for_update: bool = False
    ) -> EvaluationProjection | None:
        stmt = select(EvaluationProjection).where(
            EvaluationProjection.scheme_type == scheme_type,
            EvaluationProjection.scheme_version_id == scheme_version_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, projection: EvaluationProjection) -> EvaluationProjection:
        self.db.add(projection)
        self.db.flush()
        return projection

    def save(self, projection: EvaluationProjection) -> EvaluationProjection:
        self.db.flush()
        return projection
