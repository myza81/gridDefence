"""Substation Registry repository layer (CLAUDE.md §14) — pure persistence
access. No business rules, no permission checks, no audit writing live here
— that is `service.py`'s responsibility.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.substation_registry.models import (
    Substation,
    SubstationAlias,
    SubstationAuditLog,
)


class SubstationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Substation -----------------------------------------------------------
    def get_by_id(self, substation_id: uuid.UUID) -> Substation | None:
        return self.db.get(Substation, substation_id)

    def get_by_mnemonic_ci(self, mnemonic: str) -> Substation | None:
        stmt = select(Substation).where(func.lower(Substation.mnemonic) == mnemonic.lower())
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_name_ci(self, official_name: str) -> Substation | None:
        stmt = select(Substation).where(
            func.lower(Substation.official_name) == official_name.lower()
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_psse_bus_number(self, psse_bus_number: int) -> Substation | None:
        stmt = select(Substation).where(Substation.psse_bus_number == psse_bus_number)
        return self.db.execute(stmt).scalar_one_or_none()

    def add(self, substation: Substation) -> Substation:
        self.db.add(substation)
        self.db.flush()
        return substation

    def list_substations(
        self,
        *,
        offset: int,
        limit: int,
        region_id: int | None = None,
        state_id: int | None = None,
        grid_owner_id: int | None = None,
        operational_status_id: int | None = None,
        search: str | None = None,
    ) -> tuple[list[Substation], int]:
        stmt = select(Substation)
        if region_id is not None:
            stmt = stmt.where(Substation.region_id == region_id)
        if state_id is not None:
            stmt = stmt.where(Substation.state_id == state_id)
        if grid_owner_id is not None:
            stmt = stmt.where(Substation.grid_owner_id == grid_owner_id)
        if operational_status_id is not None:
            stmt = stmt.where(Substation.operational_status_id == operational_status_id)
        if search:
            pattern = f"%{search.lower()}%"
            stmt = stmt.where(
                func.lower(Substation.mnemonic).like(pattern)
                | func.lower(Substation.official_name).like(pattern)
            )

        total = self.db.execute(
            select(func.count()).select_from(
                stmt.with_only_columns(Substation.substation_id).subquery()
            )
        ).scalar_one()

        stmt = stmt.order_by(Substation.official_name).offset(offset).limit(limit)
        items = list(self.db.execute(stmt).scalars().all())
        return items, total

    # --- SubstationAlias --------------------------------------------------------
    def add_alias(self, alias: SubstationAlias) -> SubstationAlias:
        self.db.add(alias)
        self.db.flush()
        return alias

    def list_aliases(self, substation_id: uuid.UUID) -> list[SubstationAlias]:
        stmt = (
            select(SubstationAlias)
            .where(SubstationAlias.substation_id == substation_id)
            .order_by(SubstationAlias.valid_from)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_latest_alias(self, substation_id: uuid.UUID) -> SubstationAlias | None:
        stmt = (
            select(SubstationAlias)
            .where(SubstationAlias.substation_id == substation_id)
            .order_by(SubstationAlias.valid_from.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def find_alias_mnemonic_owner_ci(self, mnemonic: str) -> uuid.UUID | None:
        """Returns the `substation_id` that historically held this mnemonic
        (case-insensitive), or `None` if no `substation_alias` row matches.
        A mnemonic is permanently reserved to whichever substation first
        held it (substation-registry.md §8 rule 1) — the caller uses this
        to distinguish "reserved by a different substation" (reject) from
        "reserved by this same substation" (allow reuse)."""
        stmt = select(SubstationAlias.substation_id).where(
            func.lower(SubstationAlias.alias_mnemonic) == mnemonic.lower()
        )
        return self.db.execute(stmt).scalars().first()

    # --- SubstationAuditLog -------------------------------------------------------
    def add_audit_log(self, entry: SubstationAuditLog) -> SubstationAuditLog:
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_audit_log(
        self, substation_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[SubstationAuditLog], int]:
        total = self.db.execute(
            select(func.count())
            .select_from(SubstationAuditLog)
            .where(SubstationAuditLog.substation_id == substation_id)
        ).scalar_one()

        stmt = (
            select(SubstationAuditLog)
            .where(SubstationAuditLog.substation_id == substation_id)
            .order_by(SubstationAuditLog.changed_at.desc())
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total
