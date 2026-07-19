"""Shared Defence Scheme Version lifecycle service (CLAUDE.md §14 —
business rules, transactions, orchestration).

`SchemeVersionLifecycleService` is the reusable lifecycle engine every
concrete future scheme module (UFLS, UVLS, EMLS, and beyond) composes
with — never a generic runtime-polymorphic "Scheme" abstraction
(scheme-future-extensibility.md: "This pack deliberately does not build
a single, generic 'Assignment' or 'Scheme' abstraction... all inherit
from identically"). It operates on any concrete model built from
`SchemeVersionMixin`, passed in by the caller; it never queries a
concrete module's own table structure beyond the shared mixin's own
attributes, and never contains scheme-specific engineering logic (no
stage/priority-group/assignment awareness of any kind).

**What this service does not do** (each remains the concrete module's
own responsibility, composed alongside this service in the same
transaction):
- Run structural Publication prerequisites, resolve Publication
  Treatment, or create a `PublicationRecord` — that is
  `findings_publication_governance.service.PublicationRecordService.
  evaluate_and_record_publication`, already built (Sprint 4); this
  service's own `publish()` only performs the Scheme Version entity's
  own state transition, called *alongside* that existing orchestration,
  never duplicating it.
- Copy scheme-specific structure (stages, priority groups, assignments)
  when copying a version — shared-defence-scheme-domain-model.md §5's
  own copy list is genuinely scheme-specific data this platform does not
  own. `create_draft()` covers only the lifecycle/metadata portion of a
  copy (starting the new row as `Draft`, per §5's own rule); the
  concrete module's own service copies its own structural data
  separately, in the same transaction.
- Any engineering calculation of any kind (CLAUDE.md §21; this sprint's
  own explicit scope boundary).

Flush-only, never commits — mirrors every other module's own established
transaction-boundary discipline (the concrete module's own caller commits
once, itself, alongside its own writes).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.modules.continuous_evaluation.schemas import ChangeDescriptor
from app.modules.continuous_evaluation.service import ContinuousEvaluationService
from app.modules.scheme_platform.exceptions import (
    DraftDeletionNotPermittedError,
    EnteredInErrorReasonRequiredError,
)
from app.modules.scheme_platform.lifecycle import SchemeVersionLifecycleStatus, validate_transition
from app.modules.scheme_platform.models import SchemeVersionMixin
from app.modules.scheme_platform.repository import get_next_version_number


def build_lifecycle_change_descriptor(
    *,
    source_module: str,
    version_id: uuid.UUID,
    action: str,
    reason: str | None = None,
) -> ChangeDescriptor:
    """Constructs a correctly-shaped `ChangeDescriptor` (ADR-023;
    platform-event-architecture.md §9's own `module.resource.action`
    convention) for one lifecycle transition — reusable by any concrete
    module, carrying no engineering-specific payload (this sprint's own
    instructions §9). `source_module` is supplied by the caller (e.g.
    `"ufls"`), never hardcoded here — this shared platform has no module
    identity of its own to report."""
    return ChangeDescriptor(
        descriptor=f"{source_module}.scheme_version.{action}",
        source_module=source_module,
        source_entity_type="scheme_version",
        source_entity_id=str(version_id),
        occurred_at=datetime.now(UTC),
        reason=reason,
    )


class SchemeVersionLifecycleService:
    def __init__(
        self,
        db: Session,
        *,
        source_module: str,
        continuous_evaluation: ContinuousEvaluationService | None = None,
    ) -> None:
        """`source_module` names the concrete calling module (e.g.
        `"ufls"`) — used only to build correctly-namespaced platform
        event descriptors (ADR-023 §9); this service owns no table and
        has no module identity of its own.

        `continuous_evaluation` is an injectable override, defaulting to
        a plain `ContinuousEvaluationService(db)` — the same test-only
        seam every Continuous Evaluation test already uses (Sprint 6),
        letting this module's own tests verify the exact
        `ChangeDescriptor` shape passed to `notify_source_data_changed`
        without needing a real `AffectedSchemeResolver` registered."""
        self.db = db
        self.source_module = source_module
        self.continuous_evaluation = continuous_evaluation or ContinuousEvaluationService(db)

    # --- Draft creation -----------------------------------------------------------
    def create_draft(
        self,
        version: SchemeVersionMixin,
        *,
        model_class: type[SchemeVersionMixin],
        scheme_id: uuid.UUID,
    ) -> SchemeVersionMixin:
        """Populates the shared lifecycle/metadata fields on a new,
        caller-constructed `version` instance — `version_number`
        (computed, sequential per scheme) and `lifecycle_status = DRAFT`.
        The caller constructs `version` itself (its own concrete model,
        with its own scheme-specific fields already set) and is
        responsible for adding it to the session; this method only
        stamps the shared fields and publishes the platform event."""
        version.version_number = get_next_version_number(self.db, model_class, scheme_id)
        version.lifecycle_status = SchemeVersionLifecycleStatus.DRAFT.value
        self.db.flush()
        self._notify(version.version_id, action="draft_created")
        return version

    # --- Delete (Draft only) -------------------------------------------------------
    def delete_draft(self, version: SchemeVersionMixin) -> None:
        """ADR-015: "Drafts may be deleted" — every other lifecycle
        state is immutable/permanent (CLAUDE.md §5.2). The caller
        performs the actual `db.delete(version)`/removal of any
        scheme-specific child rows; this method only enforces the
        lifecycle precondition."""
        if version.lifecycle_status != SchemeVersionLifecycleStatus.DRAFT.value:
            raise DraftDeletionNotPermittedError(version.version_id, version.lifecycle_status)

    # --- Publish --------------------------------------------------------------------
    def publish(
        self,
        version: SchemeVersionMixin,
        *,
        previous_published: SchemeVersionMixin | None,
        actor_user_id: uuid.UUID,
    ) -> None:
        """The Scheme Version entity's own Draft -> Published transition,
        atomically superseding `previous_published` (ADR-015: "Publishing
        a new version atomically supersedes the currently Published
        version for that scheme"). Does **not** run structural Publication
        prerequisites, resolve Publication Treatment, or create a
        `PublicationRecord` — the caller orchestrates
        `PublicationRecordService.evaluate_and_record_publication`
        alongside this call, in the same transaction (see this module's
        own docstring)."""
        validate_transition(
            SchemeVersionLifecycleStatus(version.lifecycle_status),
            SchemeVersionLifecycleStatus.PUBLISHED,
        )
        now = datetime.now(UTC)
        version.lifecycle_status = SchemeVersionLifecycleStatus.PUBLISHED.value
        version.published_at = now
        version.published_by_user_id = actor_user_id

        if previous_published is not None:
            self.supersede(previous_published)

        self.db.flush()
        self._notify(version.version_id, action="published")

    def supersede(self, version: SchemeVersionMixin) -> None:
        """`Published -> Superseded` — automatic, atomic, always the
        direct consequence of a new version being Published for the same
        scheme (ADR-015). Not intended to be called directly by a
        concrete module except via `publish()`'s own orchestration
        above; exposed as its own method so `publish()` and any future
        administrative-correction path can share one implementation."""
        validate_transition(
            SchemeVersionLifecycleStatus(version.lifecycle_status),
            SchemeVersionLifecycleStatus.SUPERSEDED,
        )
        version.lifecycle_status = SchemeVersionLifecycleStatus.SUPERSEDED.value
        version.superseded_at = datetime.now(UTC)
        self.db.flush()
        self._notify(version.version_id, action="superseded")

    # --- Entered in Error -----------------------------------------------------------
    def enter_in_error(
        self,
        version: SchemeVersionMixin,
        *,
        reason: str,
        actor_user_id: uuid.UUID,
    ) -> None:
        """`Published|Superseded -> Entered in Error` — administrative
        correction, mandatory reason (ADR-015). Terminal: no further
        transition is legal afterward."""
        if not reason or not reason.strip():
            raise EnteredInErrorReasonRequiredError()
        validate_transition(
            SchemeVersionLifecycleStatus(version.lifecycle_status),
            SchemeVersionLifecycleStatus.ENTERED_IN_ERROR,
        )
        version.lifecycle_status = SchemeVersionLifecycleStatus.ENTERED_IN_ERROR.value
        version.entered_in_error_at = datetime.now(UTC)
        version.entered_in_error_reason = reason
        version.entered_in_error_by_user_id = actor_user_id
        self.db.flush()
        self._notify(version.version_id, action="entered_in_error", reason=reason)

    # --- Platform event integration (ADR-023) ---------------------------------------
    def _notify(self, version_id: uuid.UUID, *, action: str, reason: str | None = None) -> None:
        descriptor = build_lifecycle_change_descriptor(
            source_module=self.source_module, version_id=version_id, action=action, reason=reason
        )
        self.continuous_evaluation.notify_source_data_changed(descriptor)
