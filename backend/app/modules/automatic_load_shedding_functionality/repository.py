"""Automatic Load Shedding Functionality Registry repository layer
(CLAUDE.md §14) — pure persistence access. No business rules, no
permission checks, no audit writing live here — that is `service.py`'s
responsibility.

This repository touches exactly one module's own tables
(`automatic_load_shedding_functionality`,
`automatic_load_shedding_functionality_audit_log`) — no cross-module
repository imports, per CLAUDE.md A1 and this module's own explicit
constraint. Filtering by substation/voltage-level (attributes this module
does not itself store, per module document §4) is resolved by the service
layer composing this repository's own-column filters with read-only calls
to `EquipmentRegistryService` — never by a cross-module SQL join here.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.automatic_load_shedding_functionality.models import (
    AutomaticLoadSheddingFunctionality,
    AutomaticLoadSheddingFunctionalityAuditLog,
)


class AutomaticLoadSheddingFunctionalityRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- AutomaticLoadSheddingFunctionality ----------------------------------------
    def add(
        self, functionality: AutomaticLoadSheddingFunctionality
    ) -> AutomaticLoadSheddingFunctionality:
        self.db.add(functionality)
        self.db.flush()
        return functionality

    def get_by_id(self, functionality_id: uuid.UUID) -> AutomaticLoadSheddingFunctionality | None:
        return self.db.get(AutomaticLoadSheddingFunctionality, functionality_id)

    def get_active_by_circuit_terminal(
        self, circuit_terminal_id: uuid.UUID
    ) -> AutomaticLoadSheddingFunctionality | None:
        """The one non-decommissioned record for this terminal, if any —
        mirrors the partial unique index (module document §9 rule 2)."""
        stmt = select(AutomaticLoadSheddingFunctionality).where(
            AutomaticLoadSheddingFunctionality.circuit_terminal_id == circuit_terminal_id,
            AutomaticLoadSheddingFunctionality.lifecycle_status != "DECOMMISSIONED",
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_active_by_transformer_terminal(
        self, transformer_terminal_id: uuid.UUID
    ) -> AutomaticLoadSheddingFunctionality | None:
        stmt = select(AutomaticLoadSheddingFunctionality).where(
            AutomaticLoadSheddingFunctionality.transformer_terminal_id == transformer_terminal_id,
            AutomaticLoadSheddingFunctionality.lifecycle_status != "DECOMMISSIONED",
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(
        self,
        *,
        target_type: str | None = None,
        ufls_function: bool | None = None,
        uvls_function: bool | None = None,
        lifecycle_status: str | None = None,
    ) -> list[AutomaticLoadSheddingFunctionality]:
        """Filters only on this module's own columns — substation/voltage-
        level/bay-label filtering, and the computed Available/Assigned/
        Decommissioned display status, are resolved by the service layer
        (module docstring). `lifecycle_status` here is the raw, persisted
        existence flag (`ACTIVE`/`DECOMMISSIONED`), never the three-value
        display status. Unpaginated by design: pagination happens at the
        service layer, after cross-module enrichment, since the
        substation/voltage-level/display-status filters (when supplied)
        can only be applied after that enrichment — acceptable for a
        manually-maintained, modestly-sized static registry (CLAUDE.md
        §21)."""
        stmt = select(AutomaticLoadSheddingFunctionality)
        if target_type is not None:
            stmt = stmt.where(AutomaticLoadSheddingFunctionality.target_type == target_type)
        if ufls_function is not None:
            stmt = stmt.where(AutomaticLoadSheddingFunctionality.ufls_function == ufls_function)
        if uvls_function is not None:
            stmt = stmt.where(AutomaticLoadSheddingFunctionality.uvls_function == uvls_function)
        if lifecycle_status is not None:
            stmt = stmt.where(
                AutomaticLoadSheddingFunctionality.lifecycle_status == lifecycle_status
            )
        stmt = stmt.order_by(AutomaticLoadSheddingFunctionality.updated_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    # --- AutomaticLoadSheddingFunctionalityAuditLog --------------------------------
    def add_audit_log(
        self, entry: AutomaticLoadSheddingFunctionalityAuditLog
    ) -> AutomaticLoadSheddingFunctionalityAuditLog:
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_audit_log(
        self, functionality_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[AutomaticLoadSheddingFunctionalityAuditLog], int]:
        total = self.db.execute(
            select(func.count())
            .select_from(AutomaticLoadSheddingFunctionalityAuditLog)
            .where(AutomaticLoadSheddingFunctionalityAuditLog.functionality_id == functionality_id)
        ).scalar_one()

        stmt = (
            select(AutomaticLoadSheddingFunctionalityAuditLog)
            .where(AutomaticLoadSheddingFunctionalityAuditLog.functionality_id == functionality_id)
            .order_by(AutomaticLoadSheddingFunctionalityAuditLog.changed_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total
