"""The shared `Finding` value contract (CLAUDE.md A6; ADR-018; module
document §2) — reusable, by design, by every current and future detector
(ADR-022's own Detector Framework), the Continuous Evaluation Engine, and
this module's own policy-resolution service.

**A `Finding` is transient, never persisted at Draft time** (module
document §8: "Draft-time findings are computed live and are not
persisted"). No `finding` table exists in this sprint, deliberately — a
`Finding` is only ever captured permanently as part of a future
`PublicationRecord` (out of this sprint's scope). This module therefore
carries no ORM import, no database session, and no persistence behaviour
at all — `Finding` is a plain, frozen Pydantic value object, not an
SQLAlchemy model.

**Canonical finding types (module document §3; this sprint's own
instructions §5):** exactly the finding-source categories already named,
by name, in the finalized architecture — no detailed subtypes are
invented, and no category is added merely because a future detector might
plausibly want one. `CRITICAL_INFRASTRUCTURE_PROTECTION` is named here
because ADR-018/§3 already names it as one of the eight finding sources
this pack anticipates — including the enum value is not the same as
"enabling Critical Infrastructure behaviour," which remains entirely
unimplemented (no Critical Infrastructure module exists; nothing in this
sprint reads or reacts to that category specially).

**Canonical severities (module document §3):** `Information`, `Advisory`,
`Warning`, `Critical` — the exact four-level scale ADR-018 and the
architecture name, spelled out in full (not abbreviated to "Info"), since
this is the literal wording the authoritative documents use and the
literal value `PublicationTreatmentPolicy` rows are keyed against.

No embedded publication-treatment decision lives on `Finding` itself —
`resolve_publication_treatment` (service.py) is the one shared path that
resolves treatment, per finding, never a bespoke per-detector decision
(ADR-018's own central rule). `Finding` carries no stable identity/
deduplication key — none is required, since findings are recomputed live,
never diffed against a persisted prior finding, in this sprint's scope.
"""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, ConfigDict


class Severity(enum.StrEnum):
    """Detection-time classification, assigned by whichever evaluation
    logic detected the finding — never administrative configuration
    (module document §3). Never reordered or renamed once shipped, since
    every `PublicationTreatmentPolicy` row is keyed against these exact
    values."""

    INFORMATION = "INFORMATION"
    ADVISORY = "ADVISORY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class FindingType(enum.StrEnum):
    """The closed set of finding-source categories the finalized
    architecture already names (module document §3; ADR-019's own
    structural/composition distinction for Boundary Pocket). Adding a
    category here without a corresponding architecture decision naming it
    would be inventing a finding this sprint has no mandate to invent."""

    MW_TOLERANCE_DEVIATION = "MW_TOLERANCE_DEVIATION"
    ALSF_CAPABILITY_ABSENCE = "ALSF_CAPABILITY_ABSENCE"
    SENSITIVE_CUSTOMER_ASSOCIATION = "SENSITIVE_CUSTOMER_ASSOCIATION"
    TOPOLOGY_REGISTRY_CHANGE = "TOPOLOGY_REGISTRY_CHANGE"
    BOUNDARY_POCKET_STRUCTURAL = "BOUNDARY_POCKET_STRUCTURAL"
    BOUNDARY_POCKET_COMPOSITION = "BOUNDARY_POCKET_COMPOSITION"
    CROSS_SCHEME_OVERLAP = "CROSS_SCHEME_OVERLAP"
    CRITICAL_INFRASTRUCTURE_PROTECTION = "CRITICAL_INFRASTRUCTURE_PROTECTION"


class SchemeType(enum.StrEnum):
    """Every Defence Scheme type this policy layer governs — UFLS, UVLS,
    *and* EMLS (ADR-018's own "every finding a Defence Scheme Version
    accumulates, regardless of source" — unlike Stage Setting Registry,
    which is UFLS/UVLS-only, publication governance is scheme-agnostic
    across all three)."""

    UFLS = "UFLS"
    UVLS = "UVLS"
    EMLS = "EMLS"


class Finding(BaseModel):
    """One detected issue against a specific Scheme Version (or a specific
    assignment within it) — module document §2. Immutable (frozen) value
    semantics: a `Finding` is a fact about one evaluation moment, never
    mutated after construction.

    `source` is the identity of whichever detector produced this finding —
    ADR-022's own `detector_id`, which "becomes `Finding.source`" per that
    ADR's own Decision text. Not modeled as an enum: detectors are
    registered dynamically (within this platform's own static, compile-time
    registration model, ADR-022), so their identities are not a fixed,
    architecture-named set the way `FindingType`/`Severity` are.

    `affected_object_type`/`affected_object_id` name the concrete
    engineering object a finding is about (e.g. `"substation"` /
    a substation id; `"transformer_terminal"` / a terminal id) — plain
    strings, not a closed enum, since the set of referenceable object
    types is a property of each scheme module's own domain model, not
    something this shared contract can enumerate without duplicating or
    anticipating scheme-module detail this sprint does not implement.

    `scheme_type`/`scheme_version_id` are optional context, supplied by
    whichever caller constructed this `Finding` when that context is known
    (e.g. `evaluateFindings(scheme_version_id, ...)`, out of this sprint's
    scope) — `None` when unknown or not yet applicable.

    `evidence` is optional, structured, finding-specific detail (e.g. a
    critical asset's own `condition_description`, module document §3) —
    a free-form mapping, since its shape is inherently detector-specific
    and this contract does not, and should not, enumerate every detector's
    own evidence shape.

    No `acknowledgement_required`/`treatment` field: whether a finding
    requires acknowledgement, or is blocked, is *derived* by
    `resolve_publication_treatment`, never stored on the finding itself
    (module document §4; this sprint's own instructions §4).
    """

    model_config = ConfigDict(frozen=True)

    finding_type: FindingType
    severity: Severity
    source: str
    description: str
    affected_object_type: str
    affected_object_id: str
    scheme_type: SchemeType | None = None
    scheme_version_id: str | None = None
    evidence: dict[str, Any] | None = None
