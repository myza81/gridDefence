"""Continuous Evaluation Engine value contracts (CLAUDE.md A6 — Domain
Model / DTO layer; this sprint's own instructions §8-9).

These are plain, frozen Pydantic value objects — never ORM models, never
a generic `SchemeVersion` table, never an unbounded dictionary acting as
an undocumented service locator. `EvaluationRequest` carries the shared
context every detector may need (scheme type, scheme-version id, snapshot
references) plus *named, typed* optional sub-contexts for whichever
detector-specific input this sprint's one detector needs (`mw_inputs`).
A future detector adds its own sibling field (e.g. `alsf_inputs`) — this
grows additively, never by redesigning the shared shape (this sprint's
own instructions §8: "must support synthetic fixtures now and real scheme
adapters later without redesign").

No persisted evaluation projection exists in this sprint (see
`service.py`'s own module docstring for the full rationale) — there is
therefore no `status` field here; a synchronously-returned
`EvaluationResult` is, by construction, always current at the moment it
is returned.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from app.modules.findings_publication_governance.findings import Finding, SchemeType


class MwAssignmentGroupInput(BaseModel):
    """One MW-bearing group to check for tolerance deviation — a UFLS/UVLS
    "stage" or an EMLS "priority group", named generically here since the
    shared engine speaks in engineering terms common to every scheme type,
    not any one scheme module's own vocabulary (continuous-evaluation-
    architecture.md §7; scheme-future-extensibility.md).

    `reference_mw` is the external-study-approved target MW for this
    group; `current_mw` is the actual/current assigned MW derived from the
    evaluation snapshot being checked. Both are supplied by a future scheme
    adapter or synthetic test fixture — this contract never queries a real
    assignment table itself (this sprint's own instructions §15)."""

    model_config = ConfigDict(frozen=True)

    group_id: str
    group_label: str
    reference_mw: Decimal
    current_mw: Decimal


class MwEvaluationInputs(BaseModel):
    """The MW tolerance detector's own typed input sub-contract."""

    model_config = ConfigDict(frozen=True)

    groups: list[MwAssignmentGroupInput]

    @model_validator(mode="after")
    def _no_duplicate_group_ids(self) -> MwEvaluationInputs:
        seen: set[str] = set()
        for group in self.groups:
            if group.group_id in seen:
                raise ValueError(f"Duplicate MW group_id '{group.group_id}' in evaluation input.")
            seen.add(group.group_id)
        return self


class EvaluationRequest(BaseModel):
    """An immutable evaluation request (this sprint's own instructions
    §8). `evaluation_snapshot_id`/`topology_version_id`/`load_snapshot_id`
    are opaque identifiers — no FK, no lookup — carried only so a result
    can be traced back to the inputs it was computed from."""

    model_config = ConfigDict(frozen=True)

    scheme_type: SchemeType
    scheme_version_id: uuid.UUID
    evaluation_snapshot_id: uuid.UUID | None = None
    topology_version_id: uuid.UUID | None = None
    load_snapshot_id: uuid.UUID | None = None
    trigger: str | None = None
    mw_inputs: MwEvaluationInputs | None = None


class DetectorExecutionSummary(BaseModel):
    """A generic, detector-agnostic record of one detector's own
    execution — the engine may assemble this without knowing anything
    about what a given detector's findings mean (this sprint's own
    instructions §10)."""

    model_config = ConfigDict(frozen=True)

    detector_id: str
    finding_count: int


class EvaluationResult(BaseModel):
    """The stable evaluation result contract (this sprint's own
    instructions §9). Transient — never persisted in this sprint. Carries
    no Publication Treatment decision, no publication eligibility, no
    scheme lifecycle state: those remain the independent concern of
    `findings_publication_governance`'s own policy service, resolved
    later against this result's own `findings`.

    Computed MW metrics are conveyed as structured evidence on each raised
    MW finding, not as a separate top-level field — see `service.py`'s own
    module docstring for why."""

    model_config = ConfigDict(frozen=True)

    scheme_type: SchemeType
    scheme_version_id: uuid.UUID
    evaluation_snapshot_id: uuid.UUID | None
    topology_version_id: uuid.UUID | None
    load_snapshot_id: uuid.UUID | None
    evaluated_at: datetime
    detector_summaries: list[DetectorExecutionSummary]
    findings: list[Finding]


# --- Sprint 6: background refresh, projection, and platform-event contracts ----


class ProjectionStatus(enum.StrEnum):
    """Exactly the four statuses continuous-evaluation-architecture.md
    §3.1 names — no invented fifth state. `FAILED` is explicitly
    documented there ("status: Current, Stale, Recalculating, Failed"),
    so it is used directly rather than folding failure into `STALE` plus
    metadata."""

    CURRENT = "CURRENT"
    STALE = "STALE"
    RECALCULATING = "RECALCULATING"
    FAILED = "FAILED"


class EvaluationTarget(BaseModel):
    """The minimal identity of one evaluation projection (this sprint's
    own instructions §6, §13): scheme type plus scheme-version id, no
    evaluation scenario/scope — neither ADR-023 nor continuous-evaluation-
    architecture.md documents scenario-specific background projections,
    unlike a Draft's own per-user snapshot selection (§5), which is an
    on-demand, synchronous-evaluation-only concept, not a background-
    projection one."""

    model_config = ConfigDict(frozen=True)

    scheme_type: SchemeType
    scheme_version_id: uuid.UUID


class ChangeDescriptor(BaseModel):
    """The platform event value contract realizing ADR-023's own
    `change_descriptor` — a stable envelope, not one Python class per
    event type (this sprint's own instructions §10). `descriptor` is the
    dot-namespaced `module.resource.action` identifier ADR-023/platform-
    event-architecture.md §9 defines; `source_module`/`source_entity_type`/
    `source_entity_id`/`occurred_at`/`reason` are carried "for audit/
    observability... and forward-compatibility," exactly as ADR-023's own
    Decision text describes, never as a mechanism the consumer branches on
    today. `correlation_id` is the one traceability field this sprint
    adds, letting a background refresh be traced back to the event that
    requested it (this sprint's own instructions §10, §21) — no separate
    causation id, no payload schema version, no arbitrary payload
    dictionary: none of those are documented anywhere in ADR-023 or
    platform-event-architecture.md, and inventing them would reintroduce
    exactly the complexity ADR-023 deliberately rejected (its own
    Alternatives Considered, option 4)."""

    model_config = ConfigDict(frozen=True)

    descriptor: str
    source_module: str
    source_entity_type: str | None = None
    source_entity_id: str | None = None
    occurred_at: datetime
    reason: str | None = None
    correlation_id: uuid.UUID | None = None

    @field_validator("descriptor")
    @classmethod
    def _validate_descriptor_shape(cls, value: str) -> str:
        segments = value.split(".")
        if len(segments) < 3 or any(not segment for segment in segments):
            raise ValueError(
                "descriptor must use the 'module.resource.action' dot-namespaced "
                f"convention (platform-event-architecture.md §9), got '{value}'."
            )
        return value


class RefreshRequestResult(BaseModel):
    """The stable result of one `request_refresh`/`notify_source_data_changed`
    call (this sprint's own instructions §17) — never runs evaluation
    inline; only reports the resulting projection state and whether a new
    background job was actually enqueued (as opposed to coalesced into an
    already-in-flight recalculation, see `service.py`'s own module
    docstring)."""

    model_config = ConfigDict(frozen=True)

    scheme_type: SchemeType
    scheme_version_id: uuid.UUID
    status: ProjectionStatus
    generation: int
    enqueued: bool
    job_id: str | None


class ProjectionDetail(BaseModel):
    """The read-only projection DTO reconstructed from storage (this
    sprint's own instructions §19) — disposable and non-authoritative.
    `last_result` is the most recent *successful* `EvaluationResult`
    (preserved across a subsequent STALE/RECALCULATING/FAILED transition,
    per this sprint's own instructions §22: "preserve the last successful
    projection evidence if architecture permits") — `None` only if no
    evaluation has ever completed successfully for this target."""

    model_config = ConfigDict(frozen=True)

    scheme_type: SchemeType
    scheme_version_id: uuid.UUID
    status: ProjectionStatus
    generation: int
    last_result: EvaluationResult | None
    evaluated_at: datetime | None
    recalculation_requested_at: datetime | None
    recalculation_started_at: datetime | None
    recalculation_completed_at: datetime | None
    last_error: str | None
    last_error_at: datetime | None
    created_at: datetime
    updated_at: datetime
