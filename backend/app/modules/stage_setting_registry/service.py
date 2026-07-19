"""Stage Setting Registry service layer (CLAUDE.md §14) — business rules,
transactions, orchestration, and audit writing live here, and only here
(CLAUDE.md A1: this module's own tables are written to exclusively by this
layer).

Cross-module reads go through `ReferenceDataRepository` directly — Core
Platform reference data has no service layer of its own and is already
consumed this way by every other module (e.g.
`SubstationService._require_reference_data`,
`app/modules/substation_registry/service.py`), not a deviation from
CLAUDE.md A1's module-communication discipline, which governs *business*
modules' own owned data.

Lifecycle (module document §6, mirroring ADR-015's own Scheme Version
precedent, from which ADR-016 explicitly derives this entity's lifecycle):

    DRAFT -> PUBLISHED -> ENTERED_IN_ERROR

`ENTERED_IN_ERROR` is reachable only from `PUBLISHED`, never directly from
`DRAFT` — ADR-016's own Decision text ties Entered-in-Error specifically to
"a Stage Setting Set that **should never have been published**," the same
framing ADR-015 uses for Scheme Version, where the transition table lists
only `Published -> Entered in Error` and `Superseded -> Entered in Error`,
never `Draft -> Entered in Error`. An abandoned, never-published Draft
carries no historical weight to correct (ADR-015's own "Drafts may be
deleted" reasoning) — and, per ADR-024, this module *does* implement Draft
deletion (`delete_draft`), applying that same reasoning to this entity on
its own terms (ADR-015's own exception is explicitly scoped to Defence
Scheme Version Drafts and does not, by itself, authorize this). Deletion
is legal only from `DRAFT`, never from `PUBLISHED` or `ENTERED_IN_ERROR`,
and is blocked if any UFLS/UVLS Scheme Version references the set — see
`reference_check.py` and `delete_draft`'s own docstring.

**Two-level stage structure (ADR-025).** A `StageSetting` (a stage) owns
one or more `StageSettingTrigger` rows (an independent frequency/
voltage-time operating criterion each). This module's method names reflect
that split: `add_stage`/`update_stage`/`remove_stage`/`reorder_stages`
operate on `StageSetting`; `add_trigger`/`update_trigger`/`remove_trigger`/
`reorder_triggers` operate on `StageSettingTrigger`. Both remain editable
only while the owning Stage Setting Set is `DRAFT`, exactly as before.

Threshold range validation against a "policy-defined valid range...
engineering parameter data" (module document §8) is deliberately **not**
implemented here: no such parameter exists yet in Engineering Parameter
Configuration (Sprint 1 seeded only `mw_tolerance_percentage`), and this
sprint's own instructions forbid inventing threshold defaults or ranges,
and forbid assuming an Engineering Parameter Configuration dependency that
is not already documented. This module validates threshold *structure*
only (a positive decimal number) today — reading a real policy-defined
range is a well-scoped future addition via
`EngineeringParameterService.get_parameter_value`, once such a parameter
actually exists, not invented here.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.iam.schemas import UserSummary
from app.modules.iam.service import IAMService
from app.modules.stage_setting_registry.exceptions import (
    DuplicateStageOrderError,
    DuplicateTriggerOrderError,
    DuplicateTriggerPairError,
    EmptyStageSettingSetPublicationError,
    EmptyStageTriggersPublicationError,
    EnterInErrorReasonRequiredError,
    InvalidLifecycleTransitionError,
    InvalidSchemeTypeError,
    InvalidThresholdValueError,
    InvalidTimeDelayError,
    RegionNotFoundError,
    RegionScopeNotAllowedError,
    ReorderSetMismatchError,
    ReorderTriggerSetMismatchError,
    StageSettingNotFoundError,
    StageSettingSetNotDraftError,
    StageSettingSetNotFoundError,
    StageSettingSetReferencedError,
    StageSettingTriggerNotFoundError,
    ThresholdMonotonicityError,
)
from app.modules.stage_setting_registry.models import (
    StageSetting,
    StageSettingRegistryAuditLog,
    StageSettingSet,
    StageSettingTrigger,
)
from app.modules.stage_setting_registry.reference_check import (
    SchemeVersionReferenceChecker,
    build_default_reference_checkers,
)
from app.modules.stage_setting_registry.repository import StageSettingRegistryRepository
from app.modules.stage_setting_registry.schemas import (
    StageSettingDetail,
    StageSettingRegistryAuditLogEntry,
    StageSettingSetDetail,
    StageSettingSetSummary,
    StageSettingTriggerDetail,
)
from app.reference_data.repository import ReferenceDataRepository

_VALID_SCHEME_TYPES = {"UFLS", "UVLS"}

# module document §9 — "denormalized display convenience, derived from
# scheme_type" — the exact terminology already established in
# uvls-module.md §7.2/§7.3 ("Hz for UFLS; p.u. for UVLS").
_THRESHOLD_UNIT_BY_SCHEME_TYPE = {"UFLS": "Hz", "UVLS": "p.u."}

# Closed transition allow-list (module document §6) — see module docstring
# for why ENTERED_IN_ERROR is reachable only from PUBLISHED.
_TRANSITIONS: dict[str, set[str]] = {
    "DRAFT": {"PUBLISHED"},
    "PUBLISHED": {"ENTERED_IN_ERROR"},
    "ENTERED_IN_ERROR": set(),
}


class StageSettingRegistryService:
    def __init__(
        self,
        db: Session,
        *,
        reference_checkers: dict[str, SchemeVersionReferenceChecker] | None = None,
    ) -> None:
        self.db = db
        self.repo = StageSettingRegistryRepository(db)
        self.reference_data = ReferenceDataRepository(db)
        self.iam = IAMService(db)
        # `reference_checkers` is an injectable override — production
        # callers never pass it (composition-only, `build_default_
        # reference_checkers`); this module's own tests use it to exercise
        # `delete_draft`'s own reference-blocking logic without needing a
        # real UFLS fixture (`reference_check.py`, ADR-024).
        self.reference_checkers = reference_checkers or build_default_reference_checkers(db)

    # --- internal helpers -----------------------------------------------------
    def _audit(
        self,
        *,
        subject_type: str,
        stage_setting_set_id: uuid.UUID | None,
        stage_setting_id: uuid.UUID | None = None,
        stage_setting_trigger_id: uuid.UUID | None = None,
        action: str,
        old_value: str | None,
        new_value: str | None,
        actor_user_id: uuid.UUID,
        change_reason: str | None = None,
    ) -> None:
        self.repo.add_audit_log(
            StageSettingRegistryAuditLog(
                subject_type=subject_type,
                stage_setting_set_id=stage_setting_set_id,
                stage_setting_id=stage_setting_id,
                stage_setting_trigger_id=stage_setting_trigger_id,
                action=action,
                old_value=old_value,
                new_value=new_value,
                changed_by_user_id=actor_user_id,
                change_reason=change_reason,
            )
        )

    def _resolve_user(self, user_id: uuid.UUID | None) -> UserSummary | None:
        if user_id is None:
            return None
        return self.iam.get_user(user_id)

    def _require_set(self, stage_setting_set_id: uuid.UUID) -> StageSettingSet:
        stage_setting_set = self.repo.get_set_by_id(stage_setting_set_id)
        if stage_setting_set is None:
            raise StageSettingSetNotFoundError(stage_setting_set_id)
        return stage_setting_set

    def _require_draft(self, stage_setting_set: StageSettingSet) -> None:
        if stage_setting_set.status != "DRAFT":
            raise StageSettingSetNotDraftError(
                stage_setting_set.stage_setting_set_id, stage_setting_set.status
            )

    def _require_stage(
        self, stage_setting_set_id: uuid.UUID, stage_setting_id: uuid.UUID
    ) -> StageSetting:
        setting = self.repo.get_setting_by_id(stage_setting_id)
        if setting is None or setting.stage_setting_set_id != stage_setting_set_id:
            raise StageSettingNotFoundError(stage_setting_id)
        return setting

    def _require_trigger(
        self, stage_setting_id: uuid.UUID, stage_setting_trigger_id: uuid.UUID
    ) -> StageSettingTrigger:
        trigger = self.repo.get_trigger_by_id(stage_setting_trigger_id)
        if trigger is None or trigger.stage_setting_id != stage_setting_id:
            raise StageSettingTriggerNotFoundError(stage_setting_trigger_id)
        return trigger

    def _check_transition(self, current_status: str, target_status: str) -> None:
        if target_status not in _TRANSITIONS.get(current_status, set()):
            raise InvalidLifecycleTransitionError(current_status, target_status)

    def _validate_region_scope(self, scheme_type: str, region_scope_id: int | None) -> None:
        if scheme_type == "UFLS":
            if region_scope_id is not None:
                raise RegionScopeNotAllowedError()
            return
        if region_scope_id is not None and self.reference_data.get_region(region_scope_id) is None:
            raise RegionNotFoundError(region_scope_id)

    def _validate_threshold(self, threshold_value: float) -> None:
        if threshold_value is None or threshold_value <= 0:
            raise InvalidThresholdValueError(
                "must be a positive number — a frequency or per-unit voltage magnitude is a "
                "non-negative physical quantity by definition."
            )

    def _validate_time_delay(self, time_delay_ms: int) -> None:
        if time_delay_ms is None or time_delay_ms < 0:
            raise InvalidTimeDelayError("must be >= 0 (stage-setting-set-architecture.md §8).")

    def _check_duplicate_stage_order(
        self,
        existing: list[StageSetting],
        *,
        region_scope_id: int | None,
        stage_order: int,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        for setting in existing:
            if exclude_id is not None and setting.stage_setting_id == exclude_id:
                continue
            if setting.region_scope_id == region_scope_id and setting.stage_order == stage_order:
                raise DuplicateStageOrderError(stage_order)

    def _check_duplicate_trigger_order(
        self,
        existing: list[StageSettingTrigger],
        *,
        trigger_order: int,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        for trigger in existing:
            if exclude_id is not None and trigger.stage_setting_trigger_id == exclude_id:
                continue
            if trigger.trigger_order == trigger_order:
                raise DuplicateTriggerOrderError(trigger_order)

    def _check_duplicate_trigger_pair(
        self,
        existing: list[StageSettingTrigger],
        *,
        threshold_value: float,
        time_delay_ms: int,
        exclude_id: uuid.UUID | None = None,
    ) -> None:
        for trigger in existing:
            if exclude_id is not None and trigger.stage_setting_trigger_id == exclude_id:
                continue
            if (
                float(trigger.threshold_value) == float(threshold_value)
                and trigger.time_delay_ms == time_delay_ms
            ):
                raise DuplicateTriggerPairError(threshold_value, time_delay_ms)

    def _to_trigger_detail(self, trigger: StageSettingTrigger) -> StageSettingTriggerDetail:
        return StageSettingTriggerDetail(
            stage_setting_trigger_id=trigger.stage_setting_trigger_id,
            stage_setting_id=trigger.stage_setting_id,
            trigger_order=trigger.trigger_order,
            threshold_value=trigger.threshold_value,
            threshold_unit=trigger.threshold_unit,
            time_delay_ms=trigger.time_delay_ms,
        )

    def _to_setting_detail(
        self, setting: StageSetting, triggers: list[StageSettingTrigger]
    ) -> StageSettingDetail:
        return StageSettingDetail(
            stage_setting_id=setting.stage_setting_id,
            stage_setting_set_id=setting.stage_setting_set_id,
            stage_order=setting.stage_order,
            region_scope_id=setting.region_scope_id,
            triggers=[self._to_trigger_detail(t) for t in triggers],
        )

    def _list_setting_details(self, stage_setting_set_id: uuid.UUID) -> list[StageSettingDetail]:
        settings = self.repo.list_settings(stage_setting_set_id)
        triggers_by_stage = self.repo.list_triggers_for_settings(
            [s.stage_setting_id for s in settings]
        )
        return [
            self._to_setting_detail(s, triggers_by_stage.get(s.stage_setting_id, []))
            for s in settings
        ]

    def _to_set_detail(
        self, stage_setting_set: StageSettingSet, settings: list[StageSettingDetail]
    ) -> StageSettingSetDetail:
        return StageSettingSetDetail(
            stage_setting_set_id=stage_setting_set.stage_setting_set_id,
            scheme_type=stage_setting_set.scheme_type,
            description=stage_setting_set.description,
            status=stage_setting_set.status,
            settings=settings,
            created_at=stage_setting_set.created_at,
            updated_at=stage_setting_set.updated_at,
            created_by=self._resolve_user(stage_setting_set.created_by_user_id),
            updated_by=self._resolve_user(stage_setting_set.updated_by_user_id),
        )

    def _to_set_summary(
        self, stage_setting_set: StageSettingSet, setting_count: int
    ) -> StageSettingSetSummary:
        return StageSettingSetSummary(
            stage_setting_set_id=stage_setting_set.stage_setting_set_id,
            scheme_type=stage_setting_set.scheme_type,
            description=stage_setting_set.description,
            status=stage_setting_set.status,
            setting_count=setting_count,
            updated_at=stage_setting_set.updated_at,
        )

    # --- Draft creation and metadata --------------------------------------------
    def create_draft(
        self, *, scheme_type: str, description: str | None, actor_user_id: uuid.UUID
    ) -> StageSettingSet:
        if scheme_type not in _VALID_SCHEME_TYPES:
            raise InvalidSchemeTypeError(scheme_type)

        stage_setting_set = self.repo.add_set(
            StageSettingSet(
                stage_setting_set_id=uuid.uuid4(),
                scheme_type=scheme_type,
                description=description,
                status="DRAFT",
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )
        self._audit(
            subject_type="STAGE_SETTING_SET",
            stage_setting_set_id=stage_setting_set.stage_setting_set_id,
            action="created",
            old_value=None,
            new_value=f"scheme_type={scheme_type}",
            actor_user_id=actor_user_id,
        )
        return stage_setting_set

    def update_draft_metadata(
        self,
        stage_setting_set_id: uuid.UUID,
        *,
        description: str | None = ...,  # type: ignore[assignment]
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> StageSettingSet:
        stage_setting_set = self._require_set(stage_setting_set_id)
        self._require_draft(stage_setting_set)

        if description is not ... and description != stage_setting_set.description:
            self._audit(
                subject_type="STAGE_SETTING_SET",
                stage_setting_set_id=stage_setting_set_id,
                action="description_changed",
                old_value=stage_setting_set.description,
                new_value=description,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            stage_setting_set.description = description
            stage_setting_set.updated_by_user_id = actor_user_id
            self.db.flush()

        return stage_setting_set

    def delete_draft(
        self,
        stage_setting_set_id: uuid.UUID,
        *,
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> None:
        """ADR-024: physical deletion, legal only while `DRAFT` — a
        never-Published Stage Setting Set carries no historical weight
        (ADR-015's own reasoning, applied here on this entity's own
        terms; `Published`/`Entered in Error` remain permanently
        undeletable, unaffected by this method). Blocked if referenced by
        any UFLS or UVLS Scheme Version, regardless of that version's own
        lifecycle state — checked via this scheme type's own registered
        `SchemeVersionReferenceChecker` (`reference_check.py`), never a
        direct cross-module repository query (CLAUDE.md A1). The
        database's own `ON DELETE RESTRICT` constraints on
        `stage_setting_set_id`/`stage_setting_id`/`stage_setting_trigger_id`
        remain the final integrity guarantee regardless of this pre-check.

        Owned `StageSettingTrigger` rows are deleted first, then their
        owning `StageSetting` rows, then the parent `StageSettingSet` —
        CLAUDE.md §11.7 prohibits `ON DELETE CASCADE` on engineering
        entities; this method performs every deletion itself, in this
        same transaction, never one via the other (ADR-025 extends
        ADR-024's own two-level version of this rule to three)."""
        stage_setting_set = self._require_set(stage_setting_set_id)
        self._require_draft(stage_setting_set)

        checker = self.reference_checkers.get(stage_setting_set.scheme_type)
        if checker is not None:
            reference_count = checker.count_references(stage_setting_set_id)
            if reference_count > 0:
                raise StageSettingSetReferencedError(stage_setting_set_id, reference_count)

        settings = self.repo.list_settings(stage_setting_set_id)
        triggers_by_stage = self.repo.list_triggers_for_settings(
            [s.stage_setting_id for s in settings]
        )
        total_triggers = sum(len(v) for v in triggers_by_stage.values())
        self._audit(
            subject_type="STAGE_SETTING_SET",
            stage_setting_set_id=stage_setting_set_id,
            action="deleted",
            old_value=(
                f"scheme_type={stage_setting_set.scheme_type}, "
                f"description={stage_setting_set.description}, "
                f"setting_count={len(settings)}, trigger_count={total_triggers}"
            ),
            new_value=None,
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        for setting in settings:
            for trigger in triggers_by_stage.get(setting.stage_setting_id, []):
                self.repo.delete_trigger(trigger)
            self.repo.delete_setting(setting)
        self.repo.delete_set(stage_setting_set)

    # --- Stages: add / update / remove / reorder (ADR-025) ----------------------
    def add_stage(
        self,
        stage_setting_set_id: uuid.UUID,
        *,
        stage_order: int,
        region_scope_id: int | None,
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> StageSetting:
        stage_setting_set = self._require_set(stage_setting_set_id)
        self._require_draft(stage_setting_set)
        self._validate_region_scope(stage_setting_set.scheme_type, region_scope_id)

        existing = self.repo.list_settings(stage_setting_set_id)
        self._check_duplicate_stage_order(
            existing, region_scope_id=region_scope_id, stage_order=stage_order
        )

        setting = self.repo.add_setting(
            StageSetting(
                stage_setting_id=uuid.uuid4(),
                stage_setting_set_id=stage_setting_set_id,
                stage_order=stage_order,
                region_scope_id=region_scope_id,
            )
        )
        self._audit(
            subject_type="STAGE_SETTING",
            stage_setting_set_id=stage_setting_set_id,
            stage_setting_id=setting.stage_setting_id,
            action="created",
            old_value=None,
            new_value=f"stage_order={stage_order}, region_scope_id={region_scope_id}",
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        return setting

    def update_stage(
        self,
        stage_setting_set_id: uuid.UUID,
        stage_setting_id: uuid.UUID,
        *,
        region_scope_id: int | None = ...,  # type: ignore[assignment]
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> StageSetting:
        stage_setting_set = self._require_set(stage_setting_set_id)
        self._require_draft(stage_setting_set)
        setting = self._require_stage(stage_setting_set_id, stage_setting_id)

        if region_scope_id is not ... and region_scope_id != setting.region_scope_id:
            self._validate_region_scope(stage_setting_set.scheme_type, region_scope_id)
            existing = self.repo.list_settings(stage_setting_set_id)
            self._check_duplicate_stage_order(
                existing,
                region_scope_id=region_scope_id,
                stage_order=setting.stage_order,
                exclude_id=stage_setting_id,
            )
            self._audit(
                subject_type="STAGE_SETTING",
                stage_setting_set_id=stage_setting_set_id,
                stage_setting_id=stage_setting_id,
                action="region_scope_changed",
                old_value=str(setting.region_scope_id),
                new_value=str(region_scope_id),
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            setting.region_scope_id = region_scope_id
            self.db.flush()

        return setting

    def remove_stage(
        self,
        stage_setting_set_id: uuid.UUID,
        stage_setting_id: uuid.UUID,
        *,
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> None:
        """Removes a stage and, explicitly (no `ON DELETE CASCADE`,
        CLAUDE.md §11.7), every trigger it owns, in this same
        transaction."""
        stage_setting_set = self._require_set(stage_setting_set_id)
        self._require_draft(stage_setting_set)
        setting = self._require_stage(stage_setting_set_id, stage_setting_id)
        triggers = self.repo.list_triggers(stage_setting_id)

        self._audit(
            subject_type="STAGE_SETTING",
            stage_setting_set_id=stage_setting_set_id,
            stage_setting_id=stage_setting_id,
            action="removed",
            old_value=(
                f"stage_order={setting.stage_order}, region_scope_id={setting.region_scope_id}, "
                f"trigger_count={len(triggers)}"
            ),
            new_value=None,
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        for trigger in triggers:
            self.repo.delete_trigger(trigger)
        self.repo.delete_setting(setting)

    def reorder_stages(
        self,
        stage_setting_set_id: uuid.UUID,
        *,
        region_scope_id: int | None,
        ordered_stage_setting_ids: list[uuid.UUID],
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> list[StageSetting]:
        """Reorders exactly one region-scope group at a time (module
        document §7 rule 4's own per-scope monotonicity grouping — see
        this module's own models.py docstring for why ordering is scoped,
        not global). The supplied id list must be exactly this scope
        group's current membership, in the caller's desired new order."""
        stage_setting_set = self._require_set(stage_setting_set_id)
        self._require_draft(stage_setting_set)

        current = [
            s
            for s in self.repo.list_settings(stage_setting_set_id)
            if s.region_scope_id == region_scope_id
        ]
        current_ids = {s.stage_setting_id for s in current}
        if set(ordered_stage_setting_ids) != current_ids or len(ordered_stage_setting_ids) != len(
            current_ids
        ):
            raise ReorderSetMismatchError()

        by_id = {s.stage_setting_id: s for s in current}
        old_order_map = {s.stage_setting_id: s.stage_order for s in current}

        # Two-phase update: bump to guaranteed-unique temporary *negative*
        # values first (never colliding with any real stage_order, which
        # is always >= 1 — Pydantic's own `Field(ge=1)`), so no
        # intermediate UPDATE ever collides with the current or final
        # ordering under this scope group's own unique index. Negative
        # sentinels, not a large positive offset: `stage_order` is a
        # `SmallInteger` (PostgreSQL SMALLINT, max 32767) — a naive
        # `+ 100_000` offset overflows that range and raises
        # `NumericValueOutOfRange` on PostgreSQL (invisible under SQLite's
        # flexible typing; found via this sprint's own PostgreSQL
        # verification pass, mirroring `reference_data/repository.py`'s
        # own documented SMALLINT-range lesson).
        for index, setting in enumerate(current, start=1):
            setting.stage_order = -index
        self.db.flush()

        for index, setting_id in enumerate(ordered_stage_setting_ids, start=1):
            by_id[setting_id].stage_order = index
        self.db.flush()

        old_value = ",".join(f"{sid}:{old_order_map[sid]}" for sid in ordered_stage_setting_ids)
        new_value = ",".join(
            f"{sid}:{idx}" for idx, sid in enumerate(ordered_stage_setting_ids, start=1)
        )
        self._audit(
            subject_type="STAGE_SETTING_SET",
            stage_setting_set_id=stage_setting_set_id,
            action="settings_reordered",
            old_value=old_value,
            new_value=new_value,
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        return [by_id[sid] for sid in ordered_stage_setting_ids]

    # --- Triggers: add / update / remove / reorder (ADR-025) --------------------
    def add_trigger(
        self,
        stage_setting_set_id: uuid.UUID,
        stage_setting_id: uuid.UUID,
        *,
        trigger_order: int,
        threshold_value: float,
        time_delay_ms: int,
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> StageSettingTrigger:
        stage_setting_set = self._require_set(stage_setting_set_id)
        self._require_draft(stage_setting_set)
        self._require_stage(stage_setting_set_id, stage_setting_id)
        self._validate_threshold(threshold_value)
        self._validate_time_delay(time_delay_ms)

        existing = self.repo.list_triggers(stage_setting_id)
        self._check_duplicate_trigger_order(existing, trigger_order=trigger_order)
        self._check_duplicate_trigger_pair(
            existing, threshold_value=threshold_value, time_delay_ms=time_delay_ms
        )

        trigger = self.repo.add_trigger(
            StageSettingTrigger(
                stage_setting_trigger_id=uuid.uuid4(),
                stage_setting_id=stage_setting_id,
                trigger_order=trigger_order,
                threshold_value=threshold_value,
                threshold_unit=_THRESHOLD_UNIT_BY_SCHEME_TYPE[stage_setting_set.scheme_type],
                time_delay_ms=time_delay_ms,
            )
        )
        self._audit(
            subject_type="STAGE_SETTING_TRIGGER",
            stage_setting_set_id=stage_setting_set_id,
            stage_setting_id=stage_setting_id,
            stage_setting_trigger_id=trigger.stage_setting_trigger_id,
            action="created",
            old_value=None,
            new_value=(
                f"trigger_order={trigger_order}, threshold_value={threshold_value}, "
                f"time_delay_ms={time_delay_ms}"
            ),
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        return trigger

    def update_trigger(
        self,
        stage_setting_set_id: uuid.UUID,
        stage_setting_id: uuid.UUID,
        stage_setting_trigger_id: uuid.UUID,
        *,
        threshold_value: float | None = ...,  # type: ignore[assignment]
        time_delay_ms: int | None = ...,  # type: ignore[assignment]
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> StageSettingTrigger:
        stage_setting_set = self._require_set(stage_setting_set_id)
        self._require_draft(stage_setting_set)
        self._require_stage(stage_setting_set_id, stage_setting_id)
        trigger = self._require_trigger(stage_setting_id, stage_setting_trigger_id)

        new_threshold = trigger.threshold_value if threshold_value is ... else threshold_value
        new_delay = trigger.time_delay_ms if time_delay_ms is ... else time_delay_ms

        if (threshold_value is not ... and threshold_value != trigger.threshold_value) or (
            time_delay_ms is not ... and time_delay_ms != trigger.time_delay_ms
        ):
            if threshold_value is not ...:
                self._validate_threshold(threshold_value)
            if time_delay_ms is not ...:
                self._validate_time_delay(time_delay_ms)
            existing = self.repo.list_triggers(stage_setting_id)
            self._check_duplicate_trigger_pair(
                existing,
                threshold_value=new_threshold,
                time_delay_ms=new_delay,
                exclude_id=stage_setting_trigger_id,
            )

        if threshold_value is not ... and threshold_value != trigger.threshold_value:
            self._audit(
                subject_type="STAGE_SETTING_TRIGGER",
                stage_setting_set_id=stage_setting_set_id,
                stage_setting_id=stage_setting_id,
                stage_setting_trigger_id=stage_setting_trigger_id,
                action="threshold_value_changed",
                old_value=str(trigger.threshold_value),
                new_value=str(threshold_value),
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            trigger.threshold_value = threshold_value

        if time_delay_ms is not ... and time_delay_ms != trigger.time_delay_ms:
            self._audit(
                subject_type="STAGE_SETTING_TRIGGER",
                stage_setting_set_id=stage_setting_set_id,
                stage_setting_id=stage_setting_id,
                stage_setting_trigger_id=stage_setting_trigger_id,
                action="time_delay_ms_changed",
                old_value=str(trigger.time_delay_ms),
                new_value=str(time_delay_ms),
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            trigger.time_delay_ms = time_delay_ms

        self.db.flush()
        return trigger

    def remove_trigger(
        self,
        stage_setting_set_id: uuid.UUID,
        stage_setting_id: uuid.UUID,
        stage_setting_trigger_id: uuid.UUID,
        *,
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> None:
        stage_setting_set = self._require_set(stage_setting_set_id)
        self._require_draft(stage_setting_set)
        self._require_stage(stage_setting_set_id, stage_setting_id)
        trigger = self._require_trigger(stage_setting_id, stage_setting_trigger_id)

        self._audit(
            subject_type="STAGE_SETTING_TRIGGER",
            stage_setting_set_id=stage_setting_set_id,
            stage_setting_id=stage_setting_id,
            stage_setting_trigger_id=stage_setting_trigger_id,
            action="removed",
            old_value=(
                f"trigger_order={trigger.trigger_order}, "
                f"threshold_value={trigger.threshold_value}, "
                f"time_delay_ms={trigger.time_delay_ms}"
            ),
            new_value=None,
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        self.repo.delete_trigger(trigger)

    def reorder_triggers(
        self,
        stage_setting_set_id: uuid.UUID,
        stage_setting_id: uuid.UUID,
        *,
        ordered_trigger_ids: list[uuid.UUID],
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> list[StageSettingTrigger]:
        stage_setting_set = self._require_set(stage_setting_set_id)
        self._require_draft(stage_setting_set)
        self._require_stage(stage_setting_set_id, stage_setting_id)

        current = self.repo.list_triggers(stage_setting_id)
        current_ids = {t.stage_setting_trigger_id for t in current}
        if set(ordered_trigger_ids) != current_ids or len(ordered_trigger_ids) != len(current_ids):
            raise ReorderTriggerSetMismatchError()

        by_id = {t.stage_setting_trigger_id: t for t in current}
        old_order_map = {t.stage_setting_trigger_id: t.trigger_order for t in current}

        # Two-phase update via negative sentinels — same reasoning as
        # `reorder_stages` above (never colliding with a real, always
        # `>= 1`, `trigger_order`, and never overflowing `SmallInteger`).
        for index, trigger in enumerate(current, start=1):
            trigger.trigger_order = -index
        self.db.flush()

        for index, trigger_id in enumerate(ordered_trigger_ids, start=1):
            by_id[trigger_id].trigger_order = index
        self.db.flush()

        old_value = ",".join(f"{tid}:{old_order_map[tid]}" for tid in ordered_trigger_ids)
        new_value = ",".join(f"{tid}:{idx}" for idx, tid in enumerate(ordered_trigger_ids, start=1))
        self._audit(
            subject_type="STAGE_SETTING",
            stage_setting_set_id=stage_setting_set_id,
            stage_setting_id=stage_setting_id,
            action="triggers_reordered",
            old_value=old_value,
            new_value=new_value,
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        return [by_id[tid] for tid in ordered_trigger_ids]

    # --- Lifecycle: publish / enter-in-error ------------------------------------
    def publish(
        self, stage_setting_set_id: uuid.UUID, *, actor_user_id: uuid.UUID
    ) -> StageSettingSet:
        """Atomic publication (module document §7 rules 4/5, ADR-025
        business rule 1): validates the *complete* stage structure —
        non-empty, no duplicate stage_order within any scope group, every
        stage owns at least one trigger, strictly-decreasing
        most-severe-trigger-threshold monotonicity within each scope
        group — before making any change. No row-locking is required:
        unlike a single-current-version invariant (e.g. IAM's
        last-active-Administrator safeguard), this module's own
        architecture explicitly permits many Stage Setting Sets of the same
        scheme type to be simultaneously Published (module document §6 —
        "referenceable by any number of Scheme Versions... concurrently or
        across time"; ADR-016's own Rationale for why there is no
        `Superseded` state). A plain re-check of `status == DRAFT` inside
        this method's own transaction is the same, sufficient pattern every
        other lifecycle transition in this codebase already uses (e.g.
        `AutomaticLoadSheddingFunctionalityService.decommission`)."""
        stage_setting_set = self._require_set(stage_setting_set_id)
        self._check_transition(stage_setting_set.status, "PUBLISHED")

        settings = self.repo.list_settings(stage_setting_set_id)
        if not settings:
            raise EmptyStageSettingSetPublicationError()

        triggers_by_stage = self.repo.list_triggers_for_settings(
            [s.stage_setting_id for s in settings]
        )
        for setting in settings:
            if not triggers_by_stage.get(setting.stage_setting_id):
                raise EmptyStageTriggersPublicationError(setting.stage_setting_id)

        groups: dict[int | None, list[StageSetting]] = {}
        for setting in settings:
            groups.setdefault(setting.region_scope_id, []).append(setting)

        for scope_key, group in groups.items():
            if stage_setting_set.scheme_type == "UFLS" and scope_key is not None:
                # Defensive re-check — structurally should never happen,
                # since add_stage/update_stage already forbid this.
                raise RegionScopeNotAllowedError()

            group_sorted = sorted(group, key=lambda s: s.stage_order)
            orders = [s.stage_order for s in group_sorted]
            if len(orders) != len(set(orders)):
                raise DuplicateStageOrderError(orders[0])

            # ADR-025: each stage's representative value for monotonicity
            # is its most severe (numerically lowest) trigger threshold.
            most_severe = {
                s.stage_setting_id: min(
                    float(t.threshold_value) for t in triggers_by_stage[s.stage_setting_id]
                )
                for s in group_sorted
            }

            scope_description = (
                "the grid-wide scope" if scope_key is None else f"region scope {scope_key}"
            )
            for current_setting, next_setting in zip(group_sorted, group_sorted[1:], strict=False):
                if not (
                    most_severe[current_setting.stage_setting_id]
                    > most_severe[next_setting.stage_setting_id]
                ):
                    raise ThresholdMonotonicityError(scope_description)

        old_status = stage_setting_set.status
        stage_setting_set.status = "PUBLISHED"
        stage_setting_set.updated_by_user_id = actor_user_id
        self._audit(
            subject_type="STAGE_SETTING_SET",
            stage_setting_set_id=stage_setting_set_id,
            action="published",
            old_value=old_status,
            new_value="PUBLISHED",
            actor_user_id=actor_user_id,
        )
        self.db.flush()
        return stage_setting_set

    def enter_in_error(
        self, stage_setting_set_id: uuid.UUID, *, change_reason: str, actor_user_id: uuid.UUID
    ) -> StageSettingSet:
        if not change_reason or not change_reason.strip():
            raise EnterInErrorReasonRequiredError()

        stage_setting_set = self._require_set(stage_setting_set_id)
        self._check_transition(stage_setting_set.status, "ENTERED_IN_ERROR")

        old_status = stage_setting_set.status
        stage_setting_set.status = "ENTERED_IN_ERROR"
        stage_setting_set.updated_by_user_id = actor_user_id
        self._audit(
            subject_type="STAGE_SETTING_SET",
            stage_setting_set_id=stage_setting_set_id,
            action="entered_in_error",
            old_value=old_status,
            new_value="ENTERED_IN_ERROR",
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        self.db.flush()
        return stage_setting_set

    # --- Read ---------------------------------------------------------------------
    def get_set(self, stage_setting_set_id: uuid.UUID) -> StageSettingSetDetail | None:
        stage_setting_set = self.repo.get_set_by_id(stage_setting_set_id)
        if stage_setting_set is None:
            return None
        return self._to_set_detail(
            stage_setting_set, self._list_setting_details(stage_setting_set_id)
        )

    def list_sets(
        self, *, scheme_type: str | None = None, status: str | None = None
    ) -> list[StageSettingSetSummary]:
        sets = self.repo.list_sets(scheme_type=scheme_type, status=status)
        return [
            self._to_set_summary(s, len(self.repo.list_settings(s.stage_setting_set_id)))
            for s in sets
        ]

    def list_settings(self, stage_setting_set_id: uuid.UUID) -> list[StageSettingDetail]:
        self._require_set(stage_setting_set_id)
        return self._list_setting_details(stage_setting_set_id)

    def get_setting(self, stage_setting_id: uuid.UUID) -> StageSettingDetail | None:
        setting = self.repo.get_setting_by_id(stage_setting_id)
        if setting is None:
            return None
        return self._to_setting_detail(setting, self.repo.list_triggers(stage_setting_id))

    def list_triggers(
        self, stage_setting_set_id: uuid.UUID, stage_setting_id: uuid.UUID
    ) -> list[StageSettingTriggerDetail]:
        self._require_stage(stage_setting_set_id, stage_setting_id)
        return [self._to_trigger_detail(t) for t in self.repo.list_triggers(stage_setting_id)]

    def get_trigger(self, stage_setting_trigger_id: uuid.UUID) -> StageSettingTriggerDetail | None:
        trigger = self.repo.get_trigger_by_id(stage_setting_trigger_id)
        return self._to_trigger_detail(trigger) if trigger else None

    def list_audit_log(
        self, stage_setting_set_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[StageSettingRegistryAuditLogEntry], int]:
        self._require_set(stage_setting_set_id)
        items, total = self.repo.list_audit_log(
            stage_setting_set_id, offset=(page - 1) * page_size, limit=page_size
        )
        entries = [
            StageSettingRegistryAuditLogEntry(
                log_id=e.log_id,
                subject_type=e.subject_type,
                stage_setting_set_id=e.stage_setting_set_id,
                stage_setting_id=e.stage_setting_id,
                stage_setting_trigger_id=e.stage_setting_trigger_id,
                action=e.action,
                old_value=e.old_value,
                new_value=e.new_value,
                changed_at=e.changed_at,
                changed_by=self._resolve_user(e.changed_by_user_id),
                change_reason=e.change_reason,
            )
            for e in items
        ]
        return entries, total

    # --- Service interfaces for future scheme modules (ADR-020 §11) -------------
    def list_published(self, *, scheme_type: str) -> list[StageSettingSetDetail]:
        """Read-only interface for UFLS/UVLS's own Engineering Workspace
        Stage Setting Set selection step (module document §11) — the
        current set of Published Stage Setting Sets, filtered by scheme
        type."""
        if scheme_type not in _VALID_SCHEME_TYPES:
            raise InvalidSchemeTypeError(scheme_type)
        sets = self.repo.list_sets(scheme_type=scheme_type, status="PUBLISHED")
        return [
            self._to_set_detail(s, self._list_setting_details(s.stage_setting_set_id)) for s in sets
        ]
