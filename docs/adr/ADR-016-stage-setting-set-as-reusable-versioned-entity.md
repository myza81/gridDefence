# ADR-016: Stage Setting Set as a Reusable, Independently-Versioned Entity

- **Status:** Accepted
- **Date:** 2026-07-12
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1 Single Source of Truth, A13)
- **Depends on:** [ADR-015](ADR-015-defence-scheme-version-lifecycle-simplification.md) (Stage Setting Set uses the same four-state lifecycle shape, applied to a different entity)
- **Affects:** [docs/architecture/ufls-module.md](../architecture/ufls-module.md) §7.1–§7.3, §11 (stage threshold/order/delay fields, currently embedded directly on `UflsStage`), [docs/architecture/uvls-module.md](../architecture/uvls-module.md) §7.2–§7.3, §11 (same, plus region scoping)
- **Informed by:** six Project Owner engineering-discovery workshops on the shared Defence Scheme domain model

---

## Context

[`ufls-module.md`](../architecture/ufls-module.md) §11 and [`uvls-module.md`](../architecture/uvls-module.md) §11 model each stage's threshold, time delay, and order as columns owned directly by `UflsStage`/`UvlsStage`, a child row of exactly one `UflsSchemeVersion`/`UvlsSchemeVersion`. Under that design, two scheme versions that happen to use an identical stage structure (the same thresholds, the same delays, the same ordering) each store their own independent copy of that structure — there is no way to say "these two versions share the same stage design" as a first-class fact, only that their independently-owned rows happen to have equal values.

The six workshops concluded that UFLS and UVLS should each define stage structure through a separate, reusable **Stage Setting Set** — an entity with its own identity, its own lifecycle, and its own history, referenced by (not owned by) a Scheme Version, and shareable across multiple Scheme Versions of the same scheme type. EMLS does not use a Stage Setting Set (see [EDR-009](../engineering/edr/EDR-009-grid-defence-scheme-lifecycle-realignment.md)'s companion Shared Defence Scheme Domain Model for why EMLS's priority groups are structurally different).

This ADR decides how that concept is realized.

## Decision

**A Stage Setting Set is a standalone, versioned entity, owned by the scheme type it belongs to (UFLS or UVLS), never owned by or nested inside a Scheme Version.** A Scheme Version *references* a Stage Setting Set by id; it does not embed one.

- **Identity:** a Stage Setting Set has its own stable id, a human-readable description, and belongs to exactly one scheme type (`UFLS` or `UVLS`) — never shared across scheme types, and never referenced by a UFLS version from a UVLS Stage Setting Set or vice versa (mirroring the existing "a UFLS version must never reference a UVLS setting set" rule the six workshops stated explicitly).
- **Contents:** an ordered collection of stage settings. For UFLS: `stage_order`, `frequency_threshold_hz`, `time_delay_ms`. For UVLS: `stage_order`, `voltage_threshold_pu`, `time_delay_ms`, and (per [`uvls-module.md`](../architecture/uvls-module.md) §7.2's already-accepted regional-scoping reasoning, carried forward unchanged) an optional `region_scope_id`.
- **Lifecycle:** `Draft → Published → Entered in Error` — three states, not four. There is no `Superseded` state for a Stage Setting Set specifically, because superseding is not something a Stage Setting Set does to itself; a Scheme Version becomes Superseded (per ADR-015), and a Stage Setting Set simply continues to exist, referenced by however many historical Scheme Versions used it, whether or not a newer Stage Setting Set has since been created. A Stage Setting Set is:
  - **editable while `Draft`** — free to add, remove, or reorder stage settings;
  - **immutable once `Published`** — matching the same rigor a Published Scheme Version requires, since a Stage Setting Set referenced by a live scheme must not silently change under it;
  - **may later be marked `Entered in Error`** — the same correction mechanism as everywhere else in this pack, for a Stage Setting Set that should never have been published (e.g. a data-entry mistake), never a hard delete.
- **Reuse:** a Published Stage Setting Set may be referenced by any number of Scheme Versions of the same scheme type, concurrently or across time. Referencing does not copy — a Scheme Version's stage structure, for a staged scheme, is defined entirely by which Stage Setting Set it references plus that version's own per-stage target MW and assignments (see the Shared Defence Scheme Domain Model's "Version stage" concept).
- **Immutability boundary:** a Stage Setting Set's own immutability (once Published) protects its *structure* — the ordered thresholds and delays. It does not, and cannot, protect the Scheme Versions that reference it from becoming incomplete if a referenced Stage Setting Set is later marked `Entered in Error` — see Validation Rules, below.

### Validation rules

- A Published staged Scheme Version must reference a Published (not Draft, not Entered in Error) Stage Setting Set of the matching scheme type.
- A Scheme Version may only reference an `Entered in Error` Stage Setting Set if that reference predates the correction — i.e. correcting a Stage Setting Set to `Entered in Error` never retroactively invalidates a Scheme Version that already referenced it while it was Published (CLAUDE.md §5.2), but it does become a structural publication prerequisite failure for any *not-yet-Published* Draft still referencing it, and a continuous-evaluation finding for any currently-Published version that referenced it (see the Continuous Evaluation architecture).
- Every stage in the Scheme Version's referenced Stage Setting Set must have a corresponding Version Stage row with a target MW and at least one shedding action before the version may be Published (per ADR-015's structural publication prerequisites) — the same completeness rule [`ufls-module.md`](../architecture/ufls-module.md) §9's original rule 12-equivalent ("a scheme version cannot be submitted for review with zero stages, or a stage with zero assignments") already stated, restated against the new two-entity shape.

## Rationale

**Separating "what the stages are" from "what is assigned to them" mirrors a real engineering distinction the six workshops surfaced.** A UFLS engineer designing a new scheme version frequently starts from an *already-settled* stage structure (the frequency thresholds and delays are typically stable, reviewed and re-reviewed policy, changed rarely) and spends most design effort on *assignments* (which substations belong to which stage this time, given the current network). The old, embedded-per-version model forced every new Scheme Version to re-specify stage structure from scratch (or via version-copying, which the six workshops' own "Version copying" rules already treat as a separate, explicit mechanism) even when nothing about the thresholds had actually changed. A separate, reusable Stage Setting Set lets the *stable* part of the design (thresholds/delays) and the *changeable* part (assignments, target MW) evolve on genuinely independent timelines — the same reasoning [EDR-002](../engineering/edr/EDR-002-scheme-versioning-independent-of-psse.md) already applied to keep scheme versioning independent of PSS/E import cadence, now applied a second time to keep stage-structure versioning independent of assignment-design cadence.

**A Stage Setting Set requires its own lifecycle, not a shortcut through the Scheme Version's, because it is referenced by (potentially) many versions at once.** If a Stage Setting Set's immutability were merely inherited from "whichever version currently references it," two Scheme Versions sharing one Stage Setting Set could disagree about whether that shared structure is still editable — a genuine data-integrity hazard. Giving it its own three-state lifecycle (`Draft → Published → Entered in Error`) resolves this cleanly: it is editable only while nothing has yet committed to depending on it (`Draft`), and once any Scheme Version might reference it, it must already be immutable (`Published`) — which is exactly why a Scheme Version's Publication prerequisite (above) requires the referenced Stage Setting Set to already be Published, never merely Draft.

**No `Superseded` state avoids inventing a meaning for "this Stage Setting Set is superseded" that the workshops never described.** A Scheme Version becomes Superseded when a newer version is Published for the same scheme (ADR-015) — a well-defined, single-scheme-at-a-time concept. A Stage Setting Set has no equivalent single-owner relationship to supersede against; it can be referenced by many Scheme Versions simultaneously, so "a newer Stage Setting Set exists" does not mean "this one is no longer valid" the way a newer Scheme Version genuinely does supersede an older one. Introducing a `Superseded` state here would either be permanently unused (premature generality, CLAUDE.md §21) or would need its own, separately-invented trigger condition the six workshops did not specify — this ADR does not invent one.

## Consequences

**Positive:**
- Removes duplicated stage-structure data across Scheme Versions that genuinely share the same design, matching CLAUDE.md §5.1 (Single Source of Truth) more faithfully than the fully-embedded model did.
- Gives UFLS and UVLS engineers a natural way to reuse a settled stage design across successive scheme revisions without re-specifying thresholds every time — directly reflecting the workshops' own description of real design practice.
- Cleanly separates two independently-changing concerns (stage structure vs. assignment design) onto two independently-lifecycled entities, avoiding the awkward "which part of this version changed" ambiguity the fully-embedded model invited.

**Negative / trade-offs:**
- Introduces a genuinely new entity and a genuinely new reference relationship not present in the original [`ufls-module.md`](../architecture/ufls-module.md)/[`uvls-module.md`](../architecture/uvls-module.md) designs — those documents' §7.1–§7.3/§11 sections describing stage fields as directly-owned columns are now superseded for this specific aspect (status note, not rewrite — the rest of each stage's field-level meaning, e.g. what `frequency_threshold_hz` *means* and how it validates, is entirely unaffected and carries forward unchanged into the new Version Stage concept).
- A Scheme Version's completeness now depends on an external reference (its Stage Setting Set) remaining Published and unmodified — a new failure mode (a referenced Stage Setting Set entering `Entered in Error` after a Draft has already started referencing it) that the fully-embedded model could not have, and that the Continuous Evaluation architecture must explicitly account for.
- EMLS's deliberate exclusion from this concept (unchanged from the workshops' own conclusion, and consistent with [`emls-module.md`](../architecture/emls-module.md) §7.2's existing "Priority Group... has neither" reasoning) must be stated explicitly wherever Stage Setting Set is introduced, to avoid a future implementer assuming it applies uniformly to all three scheme types.

---

## Alternatives Considered

1. **Stage Setting Set as a standalone, referenced, three-state-lifecycle entity, exactly as decided above.** **Adopted.** Matches the workshops' own conclusion, mirrors ADR-015's lifecycle philosophy at a smaller scale, and resolves the stage-structure-reuse gap without inventing unneeded machinery.

2. **Keep stage structure embedded per-version, but add a "clone stage structure from another version" convenience action.** **Rejected.** This still leaves two versions with genuinely duplicated (copied, not shared) stage data — CLAUDE.md §5.1 concerns remain, and the workshops explicitly described *reuse*, not merely *convenient copying*, as the desired behaviour.

3. **Give Stage Setting Set the full four-state lifecycle (including `Superseded`), for consistency with Scheme Version.** **Rejected**, per Rationale above — `Superseded` has no well-defined trigger for an entity that may be referenced by many owners simultaneously; forcing consistency here would mean inventing behaviour the workshops did not specify.
