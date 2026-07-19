"""Engineering Parameter Configuration repository layer (CLAUDE.md §14) —
pure persistence access. No business rules, no permission checks, no
audit-reason validation live here — that is `service.py`'s responsibility.

This repository touches exactly one module's own tables
(`engineering_parameter`, `engineering_parameter_audit_log`) — no
cross-module repository imports, per CLAUDE.md A1.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.engineering_parameters.models import (
    EngineeringParameter,
    EngineeringParameterAuditLog,
)


class EngineeringParameterRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- EngineeringParameter -------------------------------------------------
    def add(self, parameter: EngineeringParameter) -> EngineeringParameter:
        self.db.add(parameter)
        self.db.flush()
        return parameter

    def get_by_key(self, parameter_key: str) -> EngineeringParameter | None:
        return self.db.get(EngineeringParameter, parameter_key)

    def list_all(self) -> list[EngineeringParameter]:
        stmt = select(EngineeringParameter).order_by(EngineeringParameter.parameter_key)
        return list(self.db.execute(stmt).scalars().all())

    # --- EngineeringParameterAuditLog ------------------------------------------
    def add_audit_log(
        self, entry: EngineeringParameterAuditLog
    ) -> EngineeringParameterAuditLog:
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_audit_log(
        self, parameter_key: str, *, offset: int, limit: int
    ) -> tuple[list[EngineeringParameterAuditLog], int]:
        total = self.db.execute(
            select(func.count())
            .select_from(EngineeringParameterAuditLog)
            .where(EngineeringParameterAuditLog.parameter_key == parameter_key)
        ).scalar_one()

        stmt = (
            select(EngineeringParameterAuditLog)
            .where(EngineeringParameterAuditLog.parameter_key == parameter_key)
            # `log_id.desc()` is a deliberate tie-breaker: SQLite's
            # `CURRENT_TIMESTAMP` has only second-level precision, so two
            # audit entries written within the same second would otherwise
            # sort in an unspecified order relative to each other.
            .order_by(
                EngineeringParameterAuditLog.changed_at.desc(),
                EngineeringParameterAuditLog.log_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total
