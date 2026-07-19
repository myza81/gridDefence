# ADR-020: Stage Setting Registry as a Standalone Shared Module

- **Status:** Accepted — implemented (Shared Platform Sprint 2)
- **Date:** 2026-07-15
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1 Single Source of Truth, §21, A1, A2, A5, A13)
- **Depends on:** [ADR-016](ADR-016-stage-setting-set-as-reusable-versioned-entity.md) (this ADR resolves the one question ADR-016 explicitly left open — the concept's own module ownership — without reopening any of ADR-016's own decisions about the entity's shape or lifecycle)
- **Affects:** [docs/architecture/stage-setting-set-architecture.md](../architecture/stage-setting-set-architecture.md) §12 (resolved, updated in place — see Consequences), [docs/architecture/shared-defence-scheme-domain-model.md](../architecture/shared-defence-scheme-domain-model.md) (unaffected — the reference relationship it already describes is agnostic to which module owns the referenced side), [docs/architecture/scheme-data-consumption-matrix.md](../architecture/scheme-data-consumption-matrix.md) (gains a new row)
- **Informed by:** the Shared Defence-Scheme Platform Implementation Readiness Review, which identified this as the one architectural decision genuinely blocking Stage Setting Set implementation

---

## Context

[ADR-016](ADR-016-stage-setting-set-as-reusable-versioned-entity.md) decided a Stage Setting Set is a standalone, versioned, referenced-not-owned entity — but explicitly declined to decide *which module's codebase* it lives in. [`stage-setting-set-architecture.md`](../architecture/stage-setting-set-architecture.md) §12 states this plainly: audit ownership is "a shared library/service pattern, or duplicated per UFLS/UVLS exactly as their own audit logs are already separately owned — an implementation decision left open, not resolved here."

This is not a cosmetic gap. Before a single migration can be written, someone must decide: does `stage_setting_set`/`stage_setting` live in one new module referenced by both UFLS and UVLS, or does each scheme module get its own copy of the table, the service logic, and the audit log? The two options produce genuinely different code, genuinely different migrations, and genuinely different long-term maintenance shape — this is a real architectural fork, not an implementation detail either path could absorb later without rework.

## Decision

**Stage Setting Set is owned by a new, standalone module — the Stage Setting Registry — never duplicated inside UFLS or UVLS.**

The Stage Setting Registry:
- owns `StageSettingSet` and `StageSetting` exactly as [`stage-setting-set-architecture.md`](../architecture/stage-setting-set-architecture.md) §3 already specifies, with no change to either entity's own shape, fields, or lifecycle;
- owns its own audit log (`stage_setting_registry_audit_log`), per CLAUDE.md A4 — every module owns its own audit trail; resolving the ownership question this way makes this a normal application of an already-existing rule, not an exception to it;
- exposes exactly the read-only service interfaces [`stage-setting-set-architecture.md`](../architecture/stage-setting-set-architecture.md) §11 already specifies (current Published sets by scheme type; which Scheme Versions reference a given set) to UFLS and UVLS, consumed via CLAUDE.md A1's service-layer-only discipline — neither scheme module ever queries `stage_setting_set`/`stage_setting` directly;
- sits in the domain hierarchy (CLAUDE.md §7) alongside, but distinct from, Reference Data: it is a genuine business entity with a UUID primary key and its own audited lifecycle (CLAUDE.md A5's own example list — "Substation; Scheme; Scheme Version; Assignment" — names exactly this shape), never a SMALLINT/INTEGER lookup row; it is not folded into the `reference_data` module, whose own pattern (Region, State, GmZone, GridOwner, VoltageLevel) is unaudited, idempotently-seeded, rarely-changing catalog data, a materially different shape from a Draft-editable, Published-immutable, Entered-in-Error-correctable business entity.

**Rejected: duplicating ownership inside UFLS and UVLS.**

## Rationale

**The two scheme types' Stage Setting Set concepts are the same entity wearing two hats, not two different entities that happen to look similar.** Both are: an ordered collection of `(stage_order, threshold, time_delay_ms)` tuples; both follow the identical `Draft → Published → Entered in Error` three-state lifecycle (ADR-016); both are immutable once Published for the identical reason (referenced by potentially many Scheme Versions at once); both require the identical `stage_order` uniqueness and threshold-monotonicity validation shape. The only genuine differences — UFLS's threshold is a frequency in Hz with grid-wide monotonicity, UVLS's is a per-unit voltage with monotonicity scoped per region — are exactly the kind of small, parameterizable variation a single `scheme_type` discriminator column and an optional `region_scope_id` column already express cleanly (`stage-setting-set-architecture.md` §9's own conceptual schema already models it this way). Duplicating this structure into two independent modules would not create two genuinely different bounded contexts; it would create two copies of one bounded context, immediately out of sync the first time either one's lifecycle logic needed a bug fix.

**CLAUDE.md §5.1 (Single Source of Truth) applies directly, not by analogy.** "Every engineering entity has exactly one owner. Other modules reference it. They never duplicate it." A Stage Setting Set referenced by both a UFLS version and a UVLS version (at different times, never simultaneously per scheme-type scoping, but by the same underlying reusable concept) is precisely the scenario this principle exists to prevent from splitting into two owners. Choosing duplication here would be the same category of mistake CLAUDE.md §8's own worked example warns against (a scheme module owning what should be Master/Reference Data) — the mistake is smaller in blast radius here than duplicating Substation identity would be, but it is the same mistake in kind.

**A shared module is also the more future-extensible choice, not merely the more disciplined one today.** [`scheme-future-extensibility.md`](../architecture/scheme-future-extensibility.md) §1 already accommodates SPS/RAS as future staged schemes without redesign; a standalone Stage Setting Registry means a third or fourth staged scheme type reuses the same module directly (a new `scheme_type` value plus, if genuinely needed, a new optional scoping column), exactly the "reuse shared platform capabilities, introduce only what is genuinely different" discipline [`scheme-future-extensibility.md`](../architecture/scheme-future-extensibility.md) §6 already requires. Duplicated-per-module ownership would instead require a *third* copy for a *third* scheme type, compounding the drift risk this ADR avoids rather than resolving it once.

**Why the rejected option should not be adopted:** duplication inside UFLS and UVLS was rejected specifically because it fails the one test CLAUDE.md §5.1 exists to apply — "does this data genuinely belong to more than one owner, or does it only look that way because no one has separated it out yet." Stage Setting Set fails that test: its lifecycle, its validation shape, and its reuse-across-versions purpose are identical in kind between UFLS and UVLS, differing only in two small, parameterizable fields. Duplication would also directly contradict [ADR-016](ADR-016-stage-setting-set-as-reusable-versioned-entity.md)'s own Rationale, which already reasons about "a Stage Setting Set referenced by potentially many Scheme Versions" as a *single* entity's own lifecycle concern — a design that presupposes single ownership, even though ADR-016 stopped short of naming which module holds it.

## Consequences

**Positive:**
- Closes the one remaining ambiguity blocking Stage Setting Set implementation, with no change to ADR-016's own decisions about the entity's shape, lifecycle, or reference relationship.
- One implementation, one test suite, one audit log, one migration path — no drift risk between a UFLS copy and a UVLS copy of the same lifecycle logic.
- Directly reusable by a third staged scheme type in the future, with no redesign.

**Negative / trade-offs:**
- Introduces one new backend module (`app/modules/stage_setting_registry/`) that would not otherwise exist yet at this point in the roadmap — a small, deliberate addition to the module count, justified by the reasoning above rather than by convenience.
- UFLS and UVLS must each call into a module they do not own for a concept central to their own scheme design (stage structure) — an ordinary cross-module read dependency (CLAUDE.md A1), not a new kind of coupling this codebase has not already used successfully (e.g. every scheme module's own dependency on Substation Registry and Equipment Registry).
- [`stage-setting-set-architecture.md`](../architecture/stage-setting-set-architecture.md) §12's own "left open, not resolved here" language is now stale and is updated in place with a pointer to this ADR (status note, not a rewrite of the rest of that document, which required no other change).

---

## Alternatives Considered

1. **Standalone shared module (Stage Setting Registry), as decided above.** **Adopted.** Matches CLAUDE.md §5.1 directly, avoids duplicated lifecycle logic, and is the more future-extensible choice for a third staged scheme type.

2. **Duplicated ownership inside UFLS and UVLS, each owning its own `stage_setting_set` table and lifecycle logic.** **Rejected.** Fails the Single-Source-of-Truth test (Rationale, above); guarantees drift risk between two copies of the same lifecycle machinery; contradicts ADR-016's own single-entity framing; does not extend cleanly to a future third staged scheme type without a third copy.

3. **Fold Stage Setting Set into the existing `reference_data` module, alongside Region/GmZone/VoltageLevel.** **Rejected, not seriously considered as equivalent to Option A.** `reference_data`'s existing pattern is unaudited, idempotently-seeded, SMALLINT/INTEGER-keyed lookup data (CLAUDE.md A5's own "Reference tables... do not require UUIDs" category) — a materially different shape from a UUID-keyed, Draft-editable, audited business entity with its own three-state lifecycle. Overloading `reference_data` with this shape would blur a distinction CLAUDE.md A5 draws deliberately.
