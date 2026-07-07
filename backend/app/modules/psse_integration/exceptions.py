"""PSS/E Integration business errors (CLAUDE.md A9 — structured, not ad hoc)."""

from __future__ import annotations

from app.shared.exceptions import AppError, NotFoundError, ValidationAppError

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationAppError",
    "RawFileParseError",
    "NoCurrentTopologyVersionError",
    "BatchNotActivatableError",
    "UnknownJobError",
    "DiscrepancyAlreadyResolvedError",
]


class RawFileParseError(ValidationAppError):
    """The uploaded file could not be parsed at all (malformed content,
    unsupported format) or failed validation with zero matched buses/loads
    (psse-integration-module.md §8.8, Workflow 5)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class NoCurrentTopologyVersionError(ValidationAppError):
    """A load-only import (Workflow 4) requires an existing Current
    `TopologyVersion` to target — there is none yet (e.g. this is the very
    first import, and it contains no bus data)."""

    def __init__(self) -> None:
        super().__init__(
            "A load-only RAW file was submitted, but no Current TopologyVersion exists yet — "
            "the first import into GridDefence must contain full topology data "
            "(psse-integration-module.md §8.7)."
        )


class BatchNotActivatableError(ValidationAppError):
    """A batch can only be activated if its status is `Completed` or
    `CompletedWithWarnings` — a `Failed` batch has nothing to activate
    (psse-integration-module.md §8.8, §10)."""

    def __init__(self, status: str) -> None:
        super().__init__(
            f"A batch with status '{status}' cannot be activated — only 'Completed' or "
            "'CompletedWithWarnings' batches may be activated."
        )


class UnknownJobError(NotFoundError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"Import job '{job_id}' not found or has expired.")


class DiscrepancyAlreadyResolvedError(ValidationAppError):
    """An `EquipmentTopologyMap` entry that has already been resolved
    (accepted/rejected) cannot be resolved again — resolution is a
    one-time, audited engineering decision (psse-integration-module.md
    §8a.5)."""

    def __init__(self) -> None:
        super().__init__(
            "This EquipmentTopologyMap entry has already been resolved — a resolution is a "
            "one-time engineering decision and cannot be changed here."
        )
