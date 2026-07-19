"""Publication-orchestration value contracts (CLAUDE.md A6) — the typed,
non-ORM data shapes a future scheme module uses to invoke the shared
publication service, and the shared service uses to report structural
prerequisites and acknowledgement evidence back.

None of these are persisted directly — `service.py`'s own
`evaluate_and_record_publication` freezes their field values into the
`PublicationRecord` aggregate (models.py). Like `Finding` (findings.py),
every contract here is a frozen Pydantic value object: no ORM import, no
database session, no persistence behaviour.

**Generic publication prerequisite contract** (this sprint's own
instructions §6): `PublicationPrerequisiteResult` is deliberately
scheme-agnostic — it carries a `prerequisite_code`, a `passed` boolean, a
description, optional affected-object context, and optional structured
evidence, exactly the shape a future UFLS/UVLS/EMLS module's own
structural-prerequisite checks (ADR-015's own Publication Prerequisites,
carried forward unchanged in
findings-and-publication-governance-architecture.md §5) already produce
without this module needing to know that scheme module's own table
structure. No scheme-specific subclass exists — every future scheme
module returns the same shape.

**Deterministic publication-local finding identity** (this sprint's own
instructions §10): `Finding` deliberately has no persisted deduplication
key (findings.py's own docstring). `AcknowledgementInput.finding_index` is
the *publication-local* identity this sprint introduces instead — the
0-based position of the finding it acknowledges within this same
request's own `findings` list, meaningful only for the duration of one
publication attempt, never a permanent global finding identity.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.modules.findings_publication_governance.findings import Finding, SchemeType


class PublicationPrerequisiteResult(BaseModel):
    """One structural publication prerequisite check result, supplied by
    the owning scheme module (ADR-015's own Publication Prerequisites —
    missing scheme identity, a missing/non-Published Stage Setting Set,
    incomplete stage structure, etc. — module document §5: "never
    findings... Publication is structurally unavailable until... corrected,
    for every Administrator, unconditionally"). `passed=False` for even one
    prerequisite unconditionally blocks publication — this contract
    carries no independent "blocking/non-blocking" flag, since structural
    prerequisites are always unconditionally blocking by architecture, not
    a policy-configurable severity/treatment question (module document
    §5's own "never... subject to configurable treatment")."""

    model_config = ConfigDict(frozen=True)

    prerequisite_code: str
    passed: bool
    description: str
    affected_object_type: str | None = None
    affected_object_id: str | None = None
    evidence: dict[str, Any] | None = None
    source: str


class AcknowledgementInput(BaseModel):
    """Acknowledgement evidence for exactly one Finding requiring it
    (module document §6) — supplied by the publishing Administrator at
    the moment of Publish, never a standalone, mutable, pending-approval
    record (this sprint's own instructions §10)."""

    model_config = ConfigDict(frozen=True)

    finding_index: int = Field(ge=0)
    acknowledged_by_user_id: uuid.UUID
    justification: str
    acknowledged_at: datetime | None = None


class PublicationRequest(BaseModel):
    """Everything the shared publication service legitimately needs from
    a future scheme module's own Publish action — never an ORM model,
    never a scheme-specific repository handle (this sprint's own
    instructions §7).

    `publication_event_id` is the caller-supplied idempotency key (this
    sprint's own chosen concurrency-identity approach — see
    `service.py`'s own module docstring for the full reasoning): the same
    value submitted twice (e.g. a network retry) is rejected as a
    duplicate rather than silently recording a second `PublicationRecord`.

    `scheme_version_id` is an opaque, cross-module identifier (CLAUDE.md
    A2/F2's dependency direction: Shared Platform never depends on, and
    therefore holds no foreign key into, any scheme module's own tables,
    which do not exist yet regardless). `topology_version_id`/
    `load_snapshot_id` are the same kind of opaque reference, matching
    `operational-snapshot-architecture.md`'s own established terminology
    — recorded as historical evidence, never enforced or dereferenced by
    this module.
    """

    model_config = ConfigDict(frozen=True)

    publication_event_id: uuid.UUID
    scheme_type: SchemeType
    scheme_version_id: uuid.UUID
    published_by_user_id: uuid.UUID
    findings: list[Finding] = Field(default_factory=list)
    prerequisites: list[PublicationPrerequisiteResult] = Field(default_factory=list)
    acknowledgements: list[AcknowledgementInput] = Field(default_factory=list)
    topology_version_id: uuid.UUID | None = None
    load_snapshot_id: uuid.UUID | None = None
    remarks: str | None = None


class PublicationResult(BaseModel):
    """The stable result of a successful `evaluate_and_record_publication`
    call — a thin confirmation, not the full frozen evidence (mirrors
    every other sprint's own "thin write result, rich separate read
    detail" pattern, e.g. `StageSettingRegistryService.create_draft`).
    Full evidence is retrieved afterward via
    `PublicationRecordService.get_publication_record`."""

    model_config = ConfigDict(frozen=True)

    publication_record_id: uuid.UUID
    scheme_type: SchemeType
    scheme_version_id: uuid.UUID
    published_at: datetime
    finding_count: int
    acknowledgement_count: int
