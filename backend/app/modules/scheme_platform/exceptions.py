"""Shared Defence Scheme Platform business errors (CLAUDE.md A9 —
structured, not ad hoc). Every future concrete scheme module (UFLS, UVLS,
EMLS, and beyond) reuses these directly rather than inventing its own
lifecycle-error vocabulary."""

from __future__ import annotations

from typing import Any

from app.shared.exceptions import AppError, NotFoundError, ValidationAppError

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationAppError",
    "IllegalLifecycleTransitionError",
    "DraftDeletionNotPermittedError",
    "EnteredInErrorReasonRequiredError",
    "PublishedVersionAlreadyExistsError",
]


class IllegalLifecycleTransitionError(ValidationAppError):
    """Raised by `lifecycle.validate_transition` — the requested
    transition is not one of ADR-015's own four named transitions."""

    def __init__(self, current: Any, target: Any) -> None:
        super().__init__(
            f"Illegal Scheme Version lifecycle transition: '{current}' -> '{target}' "
            "(ADR-015 permits exactly Draft->Published, Published->Superseded, "
            "Published->Entered in Error, Superseded->Entered in Error)."
        )


class DraftDeletionNotPermittedError(ValidationAppError):
    """Raised when deletion is attempted against a version that is not
    `Draft` — ADR-015: "Drafts may be deleted... an abandoned Draft is
    neither [approved nor historical]." Every other lifecycle state is
    immutable/permanent, per CLAUDE.md §5.2."""

    def __init__(self, version_id: Any, status: Any) -> None:
        super().__init__(
            f"Scheme Version '{version_id}' cannot be deleted: only Draft versions may be "
            f"deleted, and this version's status is '{status}'."
        )


class EnteredInErrorReasonRequiredError(ValidationAppError):
    """ADR-015: "Administrative correction — mandatory reason required.\""""

    def __init__(self) -> None:
        super().__init__(
            "A non-empty reason is required to mark a Scheme Version Entered in Error (ADR-015)."
        )


class PublishedVersionAlreadyExistsError(ValidationAppError):
    """Defensive guard: `publish()` expects the caller to have already
    identified (and will supersede) any currently-Published version for
    the same scheme. Raised only if the caller's own orchestration
    invariant is violated (this shared service never discovers a second
    Published version on its own — that would require querying a
    concrete module's own table, which this shared platform does not
    own)."""

    def __init__(self, scheme_id: Any) -> None:
        super().__init__(
            f"Scheme '{scheme_id}' already has a Published version that must be "
            "superseded before/while publishing a new one."
        )
