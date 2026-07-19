# ADR-015: Defence Scheme Version Lifecycle Simplification

- **Status:** Accepted
- **Date:** 2026-07-12
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (A3 Canonical Version Lifecycle, A13 ADR requirement for versioning changes)
- **Governing engineering reference:** [EDR-009](../engineering/edr/EDR-009-grid-defence-scheme-lifecycle-realignment.md) (the engineering "why" this ADR realizes as software architecture)
- **Depends on:** [ADR-010](ADR-010-engineering-decision-support-philosophy.md) (this ADR extends ADR-010's classification reasoning to a domain ADR-010 itself reserved for the full Canonical Version Lifecycle; it does not reopen ADR-010's classification rule itself)
- **Affects:** [docs/architecture/ufls-module.md](../architecture/ufls-module.md) §8, [docs/architecture/uvls-module.md](../architecture/uvls-module.md) §8, [docs/architecture/emls-module.md](../architecture/emls-module.md) §8 (each receives a status note, not a rewrite — see Consequences), [docs/architecture/domain-model.md](../architecture/domain-model.md) §5, [docs/architecture/system-overview.md](../architecture/system-overview.md) §8, [docs/architecture/implementation-plan.md](../architecture/implementation-plan.md) Phases 6–8
- **Supersedes (scoped):** the applicability of `.claude/CLAUDE.md` A3's six-state Canonical Version Lifecycle to Defence Scheme Version entities specifically (UFLS/UVLS/EMLS and future SPS/RAS, Black Start, Islanding Strategy, Restoration Planning scheme versions). A3 itself, and its applicability to every other versioned entity in the platform, is entirely unaffected — this is a narrow, named carve-out for one domain, not a revision of A3's general-purpose default.
- **Informed by:** six Project Owner engineering-discovery workshops covering UFLS/UVLS/EMLS's shared philosophy, domain model, workflow, governance, data consumption, and future extensibility.

---

## Context

CLAUDE.md A3 defines the platform's general-purpose Canonical Version Lifecycle: `Draft → Under Review → Approved → Active → Superseded → Archived`. [`ufls-module.md`](../architecture/ufls-module.md) §8 adopted this lifecycle in full for `UflsSchemeVersion`, and [`uvls-module.md`](../architecture/uvls-module.md)/[`emls-module.md`](../architecture/emls-module.md) followed the same pattern by explicit design (each states it is "structurally identical" to UFLS's own lifecycle). [`domain-model.md`](../architecture/domain-model.md) §5 documents this as the Defence Scheme domain's versioning rule. None of the three scheme modules has been implemented in code — this remains architecture-only design, never yet built against.

Six engineering-discovery workshops with the Project Owner produced a four-state model instead — `Draft → Published → Superseded | Entered in Error` — ratified as the correct engineering model in [EDR-009](../engineering/edr/EDR-009-grid-defence-scheme-lifecycle-realignment.md). Per CLAUDE.md A13, any change to versioning standards requires an ADR before adoption. This ADR is that decision.

## Decision

**A Defence Scheme Version's lifecycle is:**

```text
        ┌───────┐
   ┌───▶│ Draft │
   │    └───┬───┘
   │        │ Publish
   │        ▼
   │   ┌───────────┐
   │   │ Published │──────────────┐
   │   └─────┬─────┘              │
   │         │ superseded by      │ Entered in Error
   │         │ a new Publish      │ (correction)
   │         ▼                    ▼
   │   ┌────────────┐      ┌─────────────────┐
   └───┤ Superseded │      │ Entered in Error │
Publish└──────┬─────┘      └─────────────────┘
(new Draft,   │
 see below)   │ Entered in Error (correction)
              ▼
       ┌─────────────────┐
       │ Entered in Error │
       └─────────────────┘
```

| From | To | Trigger |
|---|---|---|
| `Draft` | `Published` | Publish (see Publication Prerequisites, below) |
| `Published` | `Superseded` | Automatic, atomic, as the direct consequence of a new version being Published for the same scheme |
| `Published` | `Entered in Error` | Administrative correction — mandatory reason required |
| `Superseded` | `Entered in Error` | Administrative correction — mandatory reason required |

No other transition is legal. In particular:
- **There is no `Under Review` state.** Everything that happened during "Under Review" under the six-state model — content freezing from the drafting team's own further casual edits, mandatory findings review, change-reason documentation — is absorbed into Draft itself, made rigorous by the Findings and Publication Governance architecture (a separate document in this pack) rather than by a separate named state.
- **There is no `Approved` state distinct from `Published`.** A version does not sit, immutable, "approved but not yet governing the grid." The single decision — Publish — is simultaneously what the six-state model called Approval and Activation. See Rationale.
- **There is no `Archived` state.** `Superseded` and `Entered in Error` are both already permanent, queryable, terminal states; a further "Archived" state added no behaviour the six-state model's own module documents ever specified beyond "retained for long-term historical record" — which `Superseded`/`Entered in Error` already guarantee under CLAUDE.md §5.2 regardless.
- **Drafts may be deleted.** A Draft that has never been Published carries no historical weight — CLAUDE.md §5.2's immutable-history guarantee protects records that have actually governed the grid or were seriously reviewed as candidates to; an abandoned Draft is neither. This is a genuine, deliberate difference from the six-state model, which never permitted hard deletion of any lifecycle state.
- **Only one Published version may exist per scheme at a time.** Publishing a new version supersedes the currently Published version for that scheme atomically, as a single service-layer operation — unchanged in substance from the six-state model's equivalent "only one Active version" rule.
- **A copied version starts as Draft**, regardless of the lifecycle state of the version it was copied from.

### Publication prerequisites (what "Under Review" and "Approved" used to gate, now gated at Publish)

A version may be Published only when:
- Every **structural publication prerequisite** is satisfied (see the Findings and Publication Governance architecture — missing scheme identity, missing required Stage Setting Set, incomplete stage structure, missing target MW, a stage with no shedding action, an invalid/incomplete Boundary Pocket, a broken authoritative reference, or an inability to perform the mandatory fresh publication evaluation). These always block Publication; no administrative policy can configure them away.
- A **mandatory fresh evaluation** has run against the version, exactly as the old "Approval" and "Activation" checkpoints each separately re-ran validation — collapsed here into the one Publish action, not removed.
- Any finding whose configured publication treatment is `Block` has been resolved; any finding whose treatment is `Allow with mandatory acknowledgement` has been acknowledged with a non-empty justification by the publishing Administrator.
- The publishing user is an authenticated, named Administrator (CLAUDE.md A10) — mirroring the six-state model's own "engineering approval actions require an authenticated, named IAM user" rule, unweakened.

### Reactivation

The six-state model's open, unresolved `Superseded → Active` reactivation question (flagged in [`ufls-module.md`](../architecture/ufls-module.md) §8/closing summary, carried forward unresolved by UVLS and EMLS) is restated, not resolved, under this model as `Superseded → Published` reactivation. This ADR does not decide it — it remains an explicitly open question, now scoped to the four-state model instead of the six-state one.

## Rationale

**This is ADR-010's own philosophy, extended to a domain ADR-010 explicitly reserved for the heavier lifecycle — a deliberate extension, not an accidental erosion.** ADR-010 drew a hard line: "Approved Engineering Policy... requires the full Canonical Version Lifecycle... this is not the pattern this ADR is relaxing." [EDR-009](../engineering/edr/EDR-009-grid-defence-scheme-lifecycle-realignment.md) records the Project Owner's engineering conclusion that this line should move — Defence Scheme Version data remains, in every substantive sense, Approved Engineering Policy (it governs real load-shedding behaviour once Published; it is never merely consulted, unlike a `LoadSnapshot` or `IslandAnalysisResult`), but the *shape* of the lifecycle that governs it now follows ADR-010's own "one rigorous decision point, evidence gathered beforehand" pattern instead of the multi-gate model. This ADR is the formal instrument that authorizes that move — CLAUDE.md A13 requires it explicitly, and it would be a misclassification (exactly what ADR-010 itself warns against) to make this change silently inside a module document.

**Nothing that mattered in "Under Review" or "Approved" disappears — it moves into Draft, made continuous instead of gated.** The six-state model's "Under Review" existed to freeze content and surface findings to reviewers; "Approved" existed to capture MW and lock in immutability before Activation. Under the four-state model: findings are visible continuously throughout Draft (per the Continuous Evaluation architecture), a mandatory fresh evaluation still runs at the one gate that matters (Publish), and MW/pocket-composition capture still happens exactly once, at that same gate — nothing about rigor is removed, only the separate named states that previously carried it are collapsed into one.

**Deletable Drafts is a genuine, narrow exception to CLAUDE.md §5.2, justified by what a Draft actually is.** CLAUDE.md §5.2 protects "approved engineering records" and "historical records" — a Draft that was never Published was never either. Permitting deletion here does not create a precedent for any other versioned entity in the platform; it is scoped explicitly to pre-Publication Defence Scheme Version Drafts, and only because EDR-009's workshops confirmed this matches actual engineering practice (an abandoned scheme design in progress carries no more historical weight than an abandoned Word document draft would).

## Consequences

**Positive:**
- Four states and four transitions replace six states and (per the six-state model's own module documents) an equivalent-or-larger transition set, without losing any rigor — a simpler mental model for engineers designing schemes and for future implementers alike.
- Aligns the architecture with 01-engineering-philosophy.md's own, simpler "Draft → review → Published" language (EDR-009), closing a gap between the authoritative engineering document and its architectural elaboration that had existed since [`ufls-module.md`](../architecture/ufls-module.md) was first written.
- Gives the Findings and Publication Governance architecture (a companion document in this pack) a clean, single gate to attach to, rather than needing to define different behaviour at two separate gates (Approval and Activation) as the six-state model's own compliance-checkpoint design required.

**Negative / trade-offs:**
- [`ufls-module.md`](../architecture/ufls-module.md) §8, [`uvls-module.md`](../architecture/uvls-module.md) §8, and [`emls-module.md`](../architecture/emls-module.md) §8 are now superseded and must not be implemented as written. This ADR does **not** rewrite those sections — per CLAUDE.md §5.2 and this project's established practice (the same practice already applied when [ADR-009](ADR-009-substation-voltage-level-deprecation.md) added a pointer note to substation-registry.md rather than rewriting it, and when ADR-014 did the same for the Substation lifecycle), a short status note is added atop each pointing to this ADR and EDR-009, leaving the original six-state design fully legible as historical record. The rest of each document (§1–§7, §9 minus the lifecycle-specific rules, §10–§18) remains substantively valid and is the foundation the Shared Defence Scheme Domain Model (a companion document in this pack) builds from.
- [`domain-model.md`](../architecture/domain-model.md) §5's "Versioning" subsection and [`system-overview.md`](../architecture/system-overview.md) §8's classification guidance both need an equivalent status note — added by this pack, not a rewrite.
- [`implementation-plan.md`](../architecture/implementation-plan.md) Phases 6–8 (UFLS/UVLS/EMLS) describe "a full Draft → Under Review → Approved → Active workflow" as their acceptance criteria — this is now inaccurate and is corrected in this pack's Roadmap Corrections document, not rewritten in place, preserving the historical record of what was originally planned.
- A future implementer building Cross-Scheme-Compliance-equivalent gating (now folded into the Findings and Publication Governance architecture) must design against a single Publish checkpoint, not the Approval/Activation pair [ADR-004](ADR-004-cross-scheme-compliance-mechanism.md) originally specified — [ADR-018](ADR-018-findings-severity-and-publication-governance-separation.md) addresses this directly.
- Deletable Drafts require careful service-layer implementation to ensure a Draft's *findings*, if any were ever computed and cached, are also cleanly discarded — a minor implementation-completeness risk flagged for the Codex foundation-readiness audit, not resolved here.

---

## Alternatives Considered

1. **Four-state model exactly as decided above.** **Adopted.** Matches the Project Owner's ratified engineering conclusion (EDR-009), extends ADR-010's own validated philosophy rather than inventing a new one, and requires no new lifecycle machinery beyond what Findings and Publication Governance already needs to build.

2. **Keep the six-state model, treat the four-state workshop conclusions as informal guidance only.** **Rejected.** CLAUDE.md A13 requires an ADR for any versioning change; treating a ratified Project Owner engineering conclusion as non-binding guidance would itself violate CLAUDE.md's own precedence rules (F1 — Project Vision & Engineering Principles rank above CLAUDE.md Standards, which rank above Accepted ADRs). The six workshops are exactly the kind of Project-Owner-level engineering conclusion F1 places above architecture-document-level decisions like A3's original application to this domain.

3. **Retain "Under Review" as an optional, skippable state (Draft → [Under Review] → Published), rather than removing it outright.** **Rejected.** An optional state that is always skipped in practice (per the workshops' own description of actual engineering behaviour) is dead architecture — it would need to be built, tested, and maintained for a transition path nothing is expected to use, violating CLAUDE.md §21's guidance against premature/unused generality.

4. **Rename `Approved`/`Active` to `Published` but keep both as distinct states (five-state model).** **Rejected.** This would preserve exactly the gap EDR-009 identifies as unjustified by actual engineering practice — a version sitting "approved" but not yet governing the grid answers a question the workshops found engineers do not ask. Retaining it "just in case" is the same premature-generality concern as Alternative 3.
