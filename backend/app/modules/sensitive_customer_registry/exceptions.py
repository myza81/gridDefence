"""Sensitive Customer Registry business errors (CLAUDE.md A9 — structured,
not ad hoc). Mirrors the shared `AppError`/`NotFoundError`/`ValidationAppError`
hierarchy every other module in this codebase already uses — no new HTTP
status mapping is introduced (router.py maps `NotFoundError` to 404 and
every other `AppError` to 400, exactly as ALSF's own router does)."""

from __future__ import annotations

from app.shared.exceptions import AppError, NotFoundError, ValidationAppError

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationAppError",
    "SensitiveFacilityNotFoundError",
    "TransformerTerminalNotFoundError",
    "FacilitySectorNotFoundError",
    "FacilitySectorInactiveError",
    "FacilitySectorCodeImmutableError",
    "SensitivityClassificationNotFoundError",
    "SensitivityClassificationInactiveError",
    "SensitivityClassificationCodeImmutableError",
    "ReferenceDataNotSeededError",
    "FacilityEnteredInErrorImmutableError",
    "InvalidLifecycleTransitionError",
    "LifecycleReasonRequiredError",
    "ReassignmentReasonRequiredError",
]


class SensitiveFacilityNotFoundError(NotFoundError):
    def __init__(self, facility_id: object) -> None:
        super().__init__(f"Sensitive facility '{facility_id}' not found.")


class TransformerTerminalNotFoundError(ValidationAppError):
    def __init__(self, transformer_terminal_id: object) -> None:
        super().__init__(
            f"Transformer terminal '{transformer_terminal_id}' does not exist in the "
            "Equipment Registry."
        )


class FacilitySectorNotFoundError(NotFoundError):
    def __init__(self, facility_sector_id: object) -> None:
        super().__init__(f"Facility sector '{facility_sector_id}' not found.")


class FacilitySectorInactiveError(ValidationAppError):
    """A new facility, or a facility being reassigned, may not select an
    inactive reference value — existing facilities already pointing to it
    remain untouched (implementation spec §6)."""

    def __init__(self, facility_sector_id: object) -> None:
        super().__init__(
            f"Facility sector '{facility_sector_id}' is inactive and cannot be assigned to a "
            "new or reassigned facility."
        )


class FacilitySectorCodeImmutableError(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "Facility sector 'code' is immutable after creation — it is the stable identifier "
            "audit history and external consumers key against. Edit 'label' instead."
        )


class SensitivityClassificationNotFoundError(NotFoundError):
    def __init__(self, sensitivity_classification_id: object) -> None:
        super().__init__(f"Sensitivity classification '{sensitivity_classification_id}' not found.")


class SensitivityClassificationInactiveError(ValidationAppError):
    def __init__(self, sensitivity_classification_id: object) -> None:
        super().__init__(
            f"Sensitivity classification '{sensitivity_classification_id}' is inactive and "
            "cannot be assigned to a new or reassigned facility."
        )


class SensitivityClassificationCodeImmutableError(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "Sensitivity classification 'code' is immutable after creation — it is the stable "
            "identifier audit history and external consumers key against. Edit 'label' instead."
        )


class ReferenceDataNotSeededError(ValidationAppError):
    """Fail-loud guard (implementation spec §13, Correction 6) — surfaced
    instead of a generic FK violation or an opaque 500 when
    `facility_sector`/`sensitivity_classification` have never been seeded."""

    def __init__(self) -> None:
        super().__init__(
            "Sensitive Customer Registry reference data has not been seeded. Run "
            "'python -m app.modules.sensitive_customer_registry.seed' against this database "
            "before creating a Sensitive Facility record."
        )


class FacilityEnteredInErrorImmutableError(ValidationAppError):
    """`Entered in Error` is terminal — no transition out, no metadata edit
    (module document §8; implementation spec §7)."""

    def __init__(self, facility_id: object) -> None:
        super().__init__(
            f"Sensitive facility '{facility_id}' is entered in error and cannot be edited or "
            "transitioned further — entered-in-error records are permanently terminal."
        )


class InvalidLifecycleTransitionError(ValidationAppError):
    def __init__(self, *, from_status: str, to_status: str) -> None:
        super().__init__(
            f"Transition from '{from_status}' to '{to_status}' is not permitted "
            "(sensitive-customer-registry-module.md §8)."
        )


class LifecycleReasonRequiredError(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "A non-empty change_reason is required for every lifecycle transition "
            "(sensitive-customer-registry-module.md §10)."
        )


class ReassignmentReasonRequiredError(ValidationAppError):
    """Correction 5, generalised by ADR-013 decision 3 — any change to a
    Transformer Terminal association (adding one, removing one, or both in
    the same call) requires a mandatory reason, upgraded from ALSF's
    optional-reason-on-metadata-edit convention (implementation spec §6)."""

    def __init__(self) -> None:
        super().__init__(
            "A non-empty change_reason is required when changing a sensitive facility's "
            "Transformer Terminal associations (sensitive-customer-registry-module.md §14)."
        )
