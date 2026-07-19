# EDR-009: Grid Defence Scheme Lifecycle Is Draft, Published, Superseded, or Entered in Error

- **Status:** Accepted
- **Governing document:** [01-engineering-philosophy.md](../01-engineering-philosophy.md) §5 Step 8 (Review, Publish and Maintain), §8 (Version Control Philosophy)
- **Related:** [EDR-002](EDR-002-scheme-versioning-independent-of-psse.md) (unaffected — this decision does not change the relationship between scheme versioning and PSS/E import history); `docs/adr/ADR-010-engineering-decision-support-philosophy.md`; `docs/adr/ADR-015-defence-scheme-version-lifecycle-simplification.md` (the corresponding software architecture decision this EDR is realized by)

---

## Background

Six engineering-discovery workshops with the Project Owner, covering UFLS, UVLS, and EMLS's shared philosophy, domain model, workflow, governance, data consumption, and future extensibility, converged on a scheme version lifecycle of exactly four states:

```text
Draft
Published
Superseded
Entered in Error
```

This is narrower than the six-state lifecycle ([`ufls-module.md`](../../architecture/ufls-module.md) §8, [`uvls-module.md`](../../architecture/uvls-module.md) §8, [`emls-module.md`](../../architecture/emls-module.md) §8, and [`domain-model.md`](../../architecture/domain-model.md) §5) architected for Defence Scheme Version data under CLAUDE.md A3 (the Canonical Version Lifecycle: `Draft → Under Review → Approved → Active → Superseded → Archived`), which those three module documents, though never implemented in code, describe in full.

This decision resolves which of the two is the correct engineering model going forward, and records why.

## Decision

**A Grid Defence Scheme Version's engineering lifecycle has exactly four states: Draft, Published, Superseded, and Entered in Error.** There is no separate "Under Review" state and no separate "Approved" state distinct from "Published"/"Active."

- **Draft** is where all engineering work happens — designing stages (or priority groups), selecting shedding actions, reviewing findings, resolving warnings, and iterating. Review and approval are things that happen *within* Draft, as informational, evidence-gathering activity an engineer consults before deciding to publish — not separate formal states the record must pass through.
- **Published** is the single, atomic, human-authorized decision that makes a version the one governing the live grid. Publishing a version atomically supersedes whichever version was previously Published for that scheme.
- **Superseded** is what a Published version becomes once a newer version is Published in its place. It remains permanently, historically readable.
- **Entered in Error** is the correction mechanism for a Published or Superseded version that should never have governed the grid — mirroring the correction pattern already established elsewhere in this codebase's engineering registries (e.g. Equipment Registry's `ENTERED_IN_ERROR` operational status), rather than inventing a scheme-specific equivalent.

## Rationale

**This is a realignment with 01-engineering-philosophy.md, not a departure from it.** This document — the authoritative Engineering Reference Library entry that governs every other document per its own opening statement — has never described a UFLS/UVLS/EMLS scheme version as passing through a separate "Under Review" state before a separate "Approved" state before a separate "Active" state. §5 Step 8 says only: "the scheme enters the engineering review process. Before publication, metadata is recorded... Every published version becomes part of the permanent engineering record." §8 speaks of "formal reviews" as the mechanism by which schemes evolve, and refers throughout to "Published Scheme" and "Archived Scheme" as the two durable outcomes. The six-state Canonical Version Lifecycle was a *later, architecture-level* elaboration (CLAUDE.md A3), applied to Defence Scheme Version data when [`ufls-module.md`](../../architecture/ufls-module.md) was first designed — a reasonable generalization at the time, but one this EDR now finds added workflow machinery beyond what the governing engineering philosophy itself specified.

**Review and approval are not gates; they are the confidence-gathering an engineer already does before deciding to publish.** [ADR-010](../../adr/ADR-010-engineering-decision-support-philosophy.md) already established this reasoning for Engineering Source/Computed Data (a PSS/E import, an island analysis): "Activation is the engineering decision; review is informational... there is no additional 'Approve this import' or 'Approve this analysis' stage layered on top of it." The six workshops conclude the same reasoning applies to Defence Scheme Version data too — a genuinely deliberate extension of ADR-010's own philosophy to a second kind of data, not an accident of scope-creep. What differs from ADR-010's original scope is that Defence Scheme Version data remains **Approved Engineering Policy** in every substantive sense (it governs real load-shedding behaviour once Published) — it is not being reclassified as Engineering Source/Computed Data. Only the *shape* of the lifecycle changes: the rigor ADR-010 demands of a single-checkpoint decision (automated validation, complete audit traceability, one explicit human authorized decision point, immutability once created, retained queryable history) is now the model for Publication too, replacing the multi-gate approval machinery with a single, well-evidenced decision supported by continuously-updated findings (see the Findings and Publication Governance architecture this pack introduces).

**A separate "Approved but not yet Active" state answers a question engineers do not actually ask.** The six-state model allows a version to sit Approved, immutable, but not governing the grid, for an arbitrary period before a second Activation action promotes it. In practice, per the workshops, an engineer does not experience "approving" a scheme design as a distinct moment from "publishing" it — the decision to finalize a scheme design *is* the decision to make it govern the grid. Separating the two invites exactly the kind of process-for-its-own-sake EDR-004 already warns against ("some genuinely low-risk, repetitive engineering tasks will always require an explicit human action... this is an accepted cost, not an oversight" — the corollary is that GridDefence should not *add* process where the underlying engineering reality does not require it).

**"Entered in Error" is a more honest name than "discard" for a mistaken Published version.** A Published scheme version that should never have existed (a data-entry mistake, a version published against the wrong scheme) is not "cancelled" or "unpublished" — CLAUDE.md §5.2 (Immutable Engineering History) forbids retroactively treating a version as if it had never governed the grid if it, in fact, did for some period. `Entered in Error` records the correction honestly: the record remains, permanently, marked as a mistake, exactly the same engineering honesty this codebase already applies everywhere else a correction is needed without a genuine hard delete.

## Consequences

**Positive:**
- Removes two states (`Under Review`, `Approved`) that 01-engineering-philosophy.md never actually specified, bringing the architecture back into alignment with the authoritative engineering document that governs it.
- Gives Publication the same single-decision-point rigor ADR-010 already validated for PSS/E import Activation and Network Model analysis — a pattern with one working precedent in this codebase, not an unproven design.
- Findings and publication governance (see the corresponding architecture document) absorb the work the old "Under Review" and "Approved" states existed to gate — nothing about engineering rigor is lost, only the separate named states that previously carried it.
- Simplifies every scheme module's state machine to four states and, per the workshops, exactly the transitions needed for a scheme actually is used, in practice, to move through.

**Negative / trade-offs:**
- [`ufls-module.md`](../../architecture/ufls-module.md), [`uvls-module.md`](../../architecture/uvls-module.md), and [`emls-module.md`](../../architecture/emls-module.md) were written in detail around the six-state model, none of it ever implemented in code. That detail is not wasted — entity ownership, non-responsibilities, the recommended-vs-approved-MW capture pattern, Rule 3/4-equivalent business rules, and service-interface shape all remain valid and are carried forward by this pack's Shared Defence Scheme Domain Model — but their own §8 (Lifecycle/State Model) sections are now superseded and must be read as historical design record, not current direction, per a status note added to each (not a rewrite).
- A future maintainer reading only [`ufls-module.md`](../../architecture/ufls-module.md) without also reading this EDR and its corresponding ADR could mistakenly implement the six-state model — the status notes exist specifically to prevent this.
- `Superseded → Active`-equivalent reactivation, an open question already carried forward unresolved across all three module documents, is reframed under the four-state model as `Superseded → Published` — the same open question, restated, not newly introduced or newly resolved by this EDR.
