"""Stage Setting Registry repository layer (CLAUDE.md §14) — pure
persistence access. No business rules, no permission checks, no lifecycle
validation live here — that is `service.py`'s responsibility.

This repository touches exactly one module's own tables
(`stage_setting_set`, `stage_setting`, `stage_setting_trigger` — ADR-025 —
and `stage_setting_registry_audit_log`) — no cross-module repository
imports, per CLAUDE.md A1.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.stage_setting_registry.models import (
    StageSetting,
    StageSettingRegistryAuditLog,
    StageSettingSet,
    StageSettingTrigger,
)


class StageSettingRegistryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- StageSettingSet --------------------------------------------------------
    def add_set(self, stage_setting_set: StageSettingSet) -> StageSettingSet:
        self.db.add(stage_setting_set)
        self.db.flush()
        return stage_setting_set

    def get_set_by_id(self, stage_setting_set_id: uuid.UUID) -> StageSettingSet | None:
        return self.db.get(StageSettingSet, stage_setting_set_id)

    def list_sets(
        self, *, scheme_type: str | None = None, status: str | None = None
    ) -> list[StageSettingSet]:
        stmt = select(StageSettingSet)
        if scheme_type is not None:
            stmt = stmt.where(StageSettingSet.scheme_type == scheme_type)
        if status is not None:
            stmt = stmt.where(StageSettingSet.status == status)
        stmt = stmt.order_by(StageSettingSet.created_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def delete_set(self, stage_setting_set: StageSettingSet) -> None:
        """Hard delete — legitimate only while `Draft` (enforced by the
        service layer, never here), and only after every owned
        `StageSetting` child row has already been deleted explicitly in
        this same transaction (CLAUDE.md §11.7 — no `ON DELETE CASCADE`
        on engineering entities). ADR-024."""
        self.db.delete(stage_setting_set)
        self.db.flush()

    # --- StageSetting -------------------------------------------------------------
    def add_setting(self, setting: StageSetting) -> StageSetting:
        self.db.add(setting)
        self.db.flush()
        return setting

    def get_setting_by_id(self, stage_setting_id: uuid.UUID) -> StageSetting | None:
        return self.db.get(StageSetting, stage_setting_id)

    def list_settings(self, stage_setting_set_id: uuid.UUID) -> list[StageSetting]:
        """Deterministic ordering (CLAUDE.md A9): grid-wide/null-scope
        rows first, then grouped by region scope, ordered by `stage_order`
        within each group."""
        stmt = (
            select(StageSetting)
            .where(StageSetting.stage_setting_set_id == stage_setting_set_id)
            .order_by(StageSetting.region_scope_id.nulls_first(), StageSetting.stage_order)
        )
        return list(self.db.execute(stmt).scalars().all())

    def delete_setting(self, setting: StageSetting) -> None:
        """Hard delete — legitimate only while the parent Stage Setting Set
        is still `Draft` (enforced by the service layer, never here), and
        only after every owned `StageSettingTrigger` child row has already
        been deleted explicitly in this same transaction (CLAUDE.md
        §11.7 — no `ON DELETE CASCADE`; ADR-025). A Draft child row carries
        no historical weight of its own, mirroring ADR-015's own "Drafts
        may be deleted" reasoning for Scheme Version Drafts, applied here
        to one stage within an otherwise-still-Draft set."""
        self.db.delete(setting)
        self.db.flush()

    # --- StageSettingTrigger (ADR-025) ---------------------------------------------
    def add_trigger(self, trigger: StageSettingTrigger) -> StageSettingTrigger:
        self.db.add(trigger)
        self.db.flush()
        return trigger

    def get_trigger_by_id(self, stage_setting_trigger_id: uuid.UUID) -> StageSettingTrigger | None:
        return self.db.get(StageSettingTrigger, stage_setting_trigger_id)

    def list_triggers(self, stage_setting_id: uuid.UUID) -> list[StageSettingTrigger]:
        """Deterministic ordering (CLAUDE.md A9): by `trigger_order` within
        the parent stage."""
        stmt = (
            select(StageSettingTrigger)
            .where(StageSettingTrigger.stage_setting_id == stage_setting_id)
            .order_by(StageSettingTrigger.trigger_order)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_triggers_for_settings(
        self, stage_setting_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[StageSettingTrigger]]:
        """Batched variant of `list_triggers` for rendering a whole Stage
        Setting Set's worth of stages without one query per stage."""
        if not stage_setting_ids:
            return {}
        stmt = (
            select(StageSettingTrigger)
            .where(StageSettingTrigger.stage_setting_id.in_(stage_setting_ids))
            .order_by(StageSettingTrigger.stage_setting_id, StageSettingTrigger.trigger_order)
        )
        by_stage: dict[uuid.UUID, list[StageSettingTrigger]] = {
            sid: [] for sid in stage_setting_ids
        }
        for trigger in self.db.execute(stmt).scalars().all():
            by_stage.setdefault(trigger.stage_setting_id, []).append(trigger)
        return by_stage

    def delete_trigger(self, trigger: StageSettingTrigger) -> None:
        """Hard delete — legitimate only while the parent Stage Setting Set
        is still `Draft` (enforced by the service layer, never here). A
        Draft trigger carries no historical weight of its own — same
        reasoning as `delete_setting` (ADR-025)."""
        self.db.delete(trigger)
        self.db.flush()

    # --- StageSettingRegistryAuditLog ----------------------------------------------
    def add_audit_log(self, entry: StageSettingRegistryAuditLog) -> StageSettingRegistryAuditLog:
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_audit_log(
        self, stage_setting_set_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[StageSettingRegistryAuditLog], int]:
        total = self.db.execute(
            select(func.count())
            .select_from(StageSettingRegistryAuditLog)
            .where(StageSettingRegistryAuditLog.stage_setting_set_id == stage_setting_set_id)
        ).scalar_one()

        stmt = (
            select(StageSettingRegistryAuditLog)
            .where(StageSettingRegistryAuditLog.stage_setting_set_id == stage_setting_set_id)
            .order_by(
                StageSettingRegistryAuditLog.changed_at.desc(),
                StageSettingRegistryAuditLog.log_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total
