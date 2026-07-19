"""UFLS business errors (CLAUDE.md A9 — structured, not ad hoc)."""

from __future__ import annotations

from typing import Any

from app.shared.exceptions import AppError, NotFoundError, ValidationAppError

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationAppError",
    "UflsSchemeNotFoundError",
    "UflsSchemeVersionNotFoundError",
    "UflsStageNotFoundError",
    "UflsDirectAssignmentNotFoundError",
    "UflsPocketAssignmentNotFoundError",
    "VersionNotEditableError",
    "StageSettingSetNotFoundError",
    "StageSettingSetNotPublishedError",
    "StageSettingSetSchemeTypeMismatchError",
    "StageSettingNotInSelectedSetError",
    "SubstationNotEligibleForAssignmentError",
    "TerminalAlreadyAssignedError",
    "DirectAndPocketOverlapError",
    "IneffectiveBoundaryError",
    "InvalidTerminalReferenceError",
    "NoStageSettingSetSelectedError",
]


class UflsSchemeNotFoundError(NotFoundError):
    def __init__(self, ufls_scheme_id: Any) -> None:
        super().__init__(f"UFLS scheme '{ufls_scheme_id}' not found.")


class UflsSchemeVersionNotFoundError(NotFoundError):
    def __init__(self, version_id: Any) -> None:
        super().__init__(f"UFLS scheme version '{version_id}' not found.")


class UflsStageNotFoundError(NotFoundError):
    def __init__(self, ufls_stage_id: Any) -> None:
        super().__init__(f"UFLS stage '{ufls_stage_id}' not found.")


class UflsDirectAssignmentNotFoundError(NotFoundError):
    def __init__(self, assignment_id: Any) -> None:
        super().__init__(f"UFLS direct assignment '{assignment_id}' not found.")


class UflsPocketAssignmentNotFoundError(NotFoundError):
    def __init__(self, assignment_id: Any) -> None:
        super().__init__(f"UFLS pocket assignment '{assignment_id}' not found.")


class VersionNotEditableError(ValidationAppError):
    """Only a `Draft` version may have its stages/assignments/metadata
    edited or deleted (ADR-015; ufls-module.md §9 rule 13, corrected to
    the four-state model)."""

    def __init__(self, version_id: Any, status: Any) -> None:
        super().__init__(
            f"UFLS scheme version '{version_id}' is not editable: its status is "
            f"'{status}', not Draft."
        )


class StageSettingSetNotFoundError(NotFoundError):
    """Raised when a version's own `stage_setting_set_id` selection does
    not resolve to any existing Stage Setting Set — a body-supplied
    foreign reference that fails to resolve, mapped to 404, mirroring
    `UflsStageNotFoundError`'s own precedent for
    `move_direct_assignment`'s `target_ufls_stage_id`."""

    def __init__(self, stage_setting_set_id: Any) -> None:
        super().__init__(f"Stage Setting Set '{stage_setting_set_id}' not found.")


class StageSettingSetNotPublishedError(ValidationAppError):
    """ADR-024 (Selection-Time Validation Correction): a Scheme Version
    may select only a Published Stage Setting Set of the matching scheme
    type — Draft and Entered in Error are both rejected at selection
    time, never deferred to the Publish-time
    `UFLS_STAGE_SETTING_SET_PUBLISHED` prerequisite alone
    (stage-setting-set-architecture.md §6)."""

    def __init__(self, stage_setting_set_id: Any, status: Any) -> None:
        super().__init__(
            f"Stage Setting Set '{stage_setting_set_id}' is '{status}', not 'PUBLISHED' — "
            "only a Published Stage Setting Set may be selected (ADR-024)."
        )


class StageSettingSetSchemeTypeMismatchError(ValidationAppError):
    """stage-setting-set-architecture.md §5: "A UFLS version must never
    reference a UVLS Stage Setting Set, and vice versa.\""""

    def __init__(self, stage_setting_set_id: Any, scheme_type: Any) -> None:
        super().__init__(
            f"Stage Setting Set '{stage_setting_set_id}' has scheme_type '{scheme_type}', "
            "not 'UFLS'."
        )


class StageSettingNotInSelectedSetError(ValidationAppError):
    def __init__(self, stage_setting_id: Any, stage_setting_set_id: Any) -> None:
        super().__init__(
            f"Stage Setting '{stage_setting_id}' does not belong to this version's own "
            f"selected Stage Setting Set '{stage_setting_set_id}'."
        )


class SubstationNotEligibleForAssignmentError(ValidationAppError):
    """ufls-module.md §9 rules 8/12 (corrected): excluded grid-owner
    classification, or a decommissioned/retired/entered-in-error
    operational status."""

    def __init__(self, substation_id: Any, reason: str) -> None:
        super().__init__(f"Substation '{substation_id}' is not eligible for assignment: {reason}")


class TerminalAlreadyAssignedError(ValidationAppError):
    def __init__(self, transformer_terminal_id: Any) -> None:
        super().__init__(
            f"Transformer Terminal '{transformer_terminal_id}' is already assigned "
            "elsewhere within this scheme version."
        )


class DirectAndPocketOverlapError(ValidationAppError):
    """ufls-module.md §9 rule 7: a substation may not simultaneously be a
    direct assignment and appear within any pocket assignment's derived
    substation set, within the same version."""

    def __init__(self, substation_id: Any) -> None:
        super().__init__(
            f"Substation '{substation_id}' is both directly assigned and part of a "
            "Boundary Pocket's isolated island within this scheme version."
        )


class IneffectiveBoundaryError(ValidationAppError):
    """boundary-pocket-architecture.md §7: "An ineffective evaluation
    result can never be committed to a Scheme Version's assignment
    universe.\""""

    def __init__(self) -> None:
        super().__init__(
            "This Boundary Pocket opening-point selection forms no isolated island "
            "(is_boundary_effective=false) and cannot be assigned."
        )


class InvalidTerminalReferenceError(ValidationAppError):
    def __init__(self, terminal_id: Any) -> None:
        super().__init__(f"Terminal '{terminal_id}' does not exist in Equipment Registry.")


class NoStageSettingSetSelectedError(ValidationAppError):
    def __init__(self) -> None:
        super().__init__("This version has not selected a Stage Setting Set yet.")
