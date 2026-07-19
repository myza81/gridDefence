"""Stage Setting Registry business errors (CLAUDE.md A9 — structured, not
ad hoc)."""

from __future__ import annotations

from app.shared.exceptions import AppError, NotFoundError, ValidationAppError

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationAppError",
    "StageSettingSetNotFoundError",
    "StageSettingNotFoundError",
    "StageSettingTriggerNotFoundError",
    "InvalidSchemeTypeError",
    "StageSettingSetNotDraftError",
    "InvalidLifecycleTransitionError",
    "EnterInErrorReasonRequiredError",
    "RegionScopeNotAllowedError",
    "RegionScopeRequiredError",
    "RegionNotFoundError",
    "DuplicateStageOrderError",
    "DuplicateTriggerOrderError",
    "DuplicateTriggerPairError",
    "InvalidThresholdValueError",
    "InvalidTimeDelayError",
    "EmptyStageSettingSetPublicationError",
    "EmptyStageTriggersPublicationError",
    "ThresholdMonotonicityError",
    "ReorderSetMismatchError",
    "ReorderTriggerSetMismatchError",
    "StageSettingSetReferencedError",
]


class StageSettingSetNotFoundError(NotFoundError):
    def __init__(self, stage_setting_set_id: object) -> None:
        super().__init__(f"Stage Setting Set '{stage_setting_set_id}' not found.")


class StageSettingNotFoundError(NotFoundError):
    def __init__(self, stage_setting_id: object) -> None:
        super().__init__(f"Stage Setting '{stage_setting_id}' not found.")


class StageSettingTriggerNotFoundError(NotFoundError):
    def __init__(self, stage_setting_trigger_id: object) -> None:
        super().__init__(f"Stage Setting Trigger '{stage_setting_trigger_id}' not found.")


class InvalidSchemeTypeError(ValidationAppError):
    def __init__(self, scheme_type: str) -> None:
        super().__init__(
            f"Unsupported scheme_type '{scheme_type}' — the Stage Setting Registry only "
            "recognizes UFLS and UVLS (stage-setting-set-architecture.md §2; EMLS has no "
            "Stage Setting Set)."
        )


class StageSettingSetNotDraftError(ValidationAppError):
    """Module document §6: only `Draft` Stage Setting Sets, and their
    settings, may be edited."""

    def __init__(self, stage_setting_set_id: object, current_status: str) -> None:
        super().__init__(
            f"Stage Setting Set '{stage_setting_set_id}' is '{current_status}', not 'DRAFT' — "
            "it is immutable and cannot be edited (stage-setting-set-architecture.md §6)."
        )


class InvalidLifecycleTransitionError(ValidationAppError):
    def __init__(self, current_status: str, target_status: str) -> None:
        super().__init__(
            f"Cannot transition a Stage Setting Set from '{current_status}' to "
            f"'{target_status}' — not a permitted transition "
            "(stage-setting-set-architecture.md §6)."
        )


class EnterInErrorReasonRequiredError(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "A change_reason is required when marking a Stage Setting Set Entered in Error "
            "(stage-setting-set-architecture.md §6, §12)."
        )


class RegionScopeNotAllowedError(ValidationAppError):
    """Module document §4/§8: a UFLS Stage Setting must never carry a
    region scope."""

    def __init__(self) -> None:
        super().__init__(
            "region_scope_id is not permitted for a UFLS Stage Setting — UFLS has no regional "
            "scoping (stage-setting-set-architecture.md §4)."
        )


class RegionScopeRequiredError(ValidationAppError):
    """Not currently raised (UVLS's own region scope is optional — `NULL`
    is the valid, grid-wide "no scope" group) — retained for completeness
    should a future scheme type require a mandatory scope."""

    def __init__(self) -> None:
        super().__init__("region_scope_id is required for this scheme type.")


class RegionNotFoundError(ValidationAppError):
    def __init__(self, region_id: object) -> None:
        super().__init__(f"Region '{region_id}' does not exist in Core Platform reference data.")


class DuplicateStageOrderError(ValidationAppError):
    """Module document §7 rule 4 — `stage_order` unique within the same
    region scope (including the grid-wide null-scope group)."""

    def __init__(self, stage_order: int) -> None:
        super().__init__(
            f"stage_order {stage_order} is already used within this Stage Setting Set's "
            "region scope (stage-setting-set-architecture.md §7 rule 4)."
        )


class DuplicateTriggerOrderError(ValidationAppError):
    """ADR-025 business rule 2 — `trigger_order` unique within its parent
    `StageSetting` (stage)."""

    def __init__(self, trigger_order: int) -> None:
        super().__init__(
            f"trigger_order {trigger_order} is already used within this stage (ADR-025)."
        )


class DuplicateTriggerPairError(ValidationAppError):
    """ADR-025 business rule 3 — the same (threshold_value, time_delay_ms)
    pair configured twice under one stage is a data-entry error, not a
    second real operating criterion."""

    def __init__(self, threshold_value: object, time_delay_ms: object) -> None:
        super().__init__(
            f"A trigger with threshold_value={threshold_value} and "
            f"time_delay_ms={time_delay_ms} already exists for this stage — duplicate "
            "operating criteria are not permitted (ADR-025)."
        )


class InvalidThresholdValueError(ValidationAppError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid threshold value: {reason}")


class InvalidTimeDelayError(ValidationAppError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid time_delay_ms: {reason}")


class EmptyStageSettingSetPublicationError(ValidationAppError):
    """Module document §7 rule 5: a Stage Setting Set with zero
    `StageSetting` rows may not be Published."""

    def __init__(self) -> None:
        super().__init__(
            "A Stage Setting Set with no Stage Settings cannot be published "
            "(stage-setting-set-architecture.md §7 rule 5)."
        )


class EmptyStageTriggersPublicationError(ValidationAppError):
    """ADR-025 business rule 1 — every stage must own at least one trigger
    before the owning Stage Setting Set may be Published."""

    def __init__(self, stage_setting_id: object) -> None:
        super().__init__(
            f"Stage '{stage_setting_id}' has no operating criteria (triggers) — a stage "
            "cannot be published with zero triggers (ADR-025)."
        )


class ThresholdMonotonicityError(ValidationAppError):
    """Module document §7 rule 4, as amended by ADR-025 — each stage's most
    severe trigger's threshold value must strictly decrease as stage_order
    increases, within the same region scope."""

    def __init__(self, scope_description: str) -> None:
        super().__init__(
            f"Each stage's most severe trigger threshold must strictly decrease as "
            f"stage_order increases within {scope_description} "
            "(stage-setting-set-architecture.md §7 rule 4; ADR-025)."
        )


class ReorderSetMismatchError(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "The supplied ordering must include every current Stage Setting in this Stage "
            "Setting Set exactly once — no missing, extra, or duplicate ids."
        )


class ReorderTriggerSetMismatchError(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "The supplied ordering must include every current trigger of this stage exactly "
            "once — no missing, extra, or duplicate ids (ADR-025)."
        )


class StageSettingSetReferencedError(ValidationAppError):
    """ADR-024: a Draft Stage Setting Set may not be deleted while
    referenced by any UFLS or UVLS Scheme Version, regardless of that
    version's own lifecycle state — checked via each scheme module's own
    read-only reference-check interface (`reference_check.py`), backed by
    the database's own `ON DELETE RESTRICT` constraints as the final
    guarantee."""

    def __init__(self, stage_setting_set_id: object, reference_count: int) -> None:
        super().__init__(
            f"Stage Setting Set '{stage_setting_set_id}' cannot be deleted — it is "
            f"referenced by {reference_count} Scheme Version(s) (ADR-024)."
        )
