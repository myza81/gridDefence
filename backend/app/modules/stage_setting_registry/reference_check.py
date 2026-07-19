"""Read-only reference-check interface consumed by
`StageSettingRegistryService.delete_draft` (ADR-024) to determine whether
a Draft Stage Setting Set is currently referenced by any UFLS or UVLS
Scheme Version before permitting its deletion.

This module owns the *interface* only (a small `Protocol`) plus the
default, composition-time wiring of each scheme module's own concrete
implementation — it never queries `ufls_scheme_version` (or a future
`uvls_scheme_version`) directly (CLAUDE.md A1: modules communicate through
service-layer interfaces, never another module's repository). The
dependency direction this protects: `stage_setting_registry`'s own core
files (`models.py`, `repository.py`, and `service.py`'s own business
logic) never import `app.modules.ufls` at module load time — only this
file's own `build_default_reference_checkers` does, and only lazily,
inside a function body, mirroring `app.modules.ufls.evaluation.
register_provider`'s own established lazy-import pattern in this
codebase (necessary here too: `UflsService` already imports
`StageSettingRegistryService`, so a module-level import in the other
direction would be circular).

UVLS has no persistence module yet — its own checker is simply absent
from the default registry until one exists, exactly mirroring
`continuous_evaluation.provider.build_default_provider_registry`'s own
"empty until a real scheme module registers itself" convention. This is
not a stub; there is nothing to stub against yet. Once a `uvls` module
exists, its own equivalent checker is added here with one additional
dict entry — nothing else in this module or in
`StageSettingRegistryService` needs to change shape to accommodate it.
"""

from __future__ import annotations

import uuid
from typing import Protocol

from sqlalchemy.orm import Session


class SchemeVersionReferenceChecker(Protocol):
    """One scheme module's own answer to "how many of my own Scheme
    Versions currently reference this Stage Setting Set" — implemented by
    that module's own service layer, using its own repository
    (CLAUDE.md A1), never queried by the Stage Setting Registry
    directly."""

    def count_references(self, stage_setting_set_id: uuid.UUID) -> int: ...


class _UflsReferenceChecker:
    def __init__(self, db: Session) -> None:
        self._db = db

    def count_references(self, stage_setting_set_id: uuid.UUID) -> int:
        from app.modules.ufls.service import UflsService

        return UflsService(self._db).count_versions_referencing_stage_setting_set(
            stage_setting_set_id
        )


def build_default_reference_checkers(db: Session) -> dict[str, SchemeVersionReferenceChecker]:
    """The production default — one checker per scheme type whose own
    persistence module currently exists. Called fresh by
    `StageSettingRegistryService.__init__` unless a caller (a test)
    injects its own, mirroring every other module's own
    `build_default_*`/injectable-override pattern already established in
    this codebase (e.g. `continuous_evaluation.detectors.registration.
    build_default_registry`)."""
    return {"UFLS": _UflsReferenceChecker(db)}
