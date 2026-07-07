# EDR-002: Engineering Schemes Are Version Controlled Independently of PSS®E Snapshots

- **Status:** Accepted
- **Governing document:** [01-engineering-philosophy.md](../01-engineering-philosophy.md) §8 (Version Control Philosophy)
- **Related:** [EDR-001](EDR-001-psse-as-operational-context.md); `docs/adr/ADR-003-psse-topology-and-load-snapshot-separation.md`

---

## Background

A Grid Defence Scheme and a PSS®E snapshot are both, in a loose sense, "versioned" — each new import produces a new snapshot; each review-and-publish cycle produces a new scheme version. It would be possible to design the system so that a scheme is versioned *in lockstep with* the PSS®E data that informed it — for example, treating a new PSS®E import as automatically opening a new scheme revision, or requiring a scheme to reference a specific snapshot to remain valid.

This decision resolves the question directly: should a scheme's version history be tied to PSS®E's own import history, or should the two evolve completely independently of each other?

## Decision

**A Grid Defence Scheme's version history (Working Draft → Scheme Review → Published Scheme → Archived Scheme) is entirely independent of PSS®E's own import history. A new PSS®E import never creates, requires, or forces a new scheme version.**

A scheme may remain Published, unchanged, through dozens or hundreds of subsequent PSS®E imports. Conversely, an engineer may open a new Working Draft for reasons that have nothing to do with a recent import (a policy change, a newly available strategy, a correction to a registry). The two version histories run on their own separate clocks.

## Rationale

**They version for different reasons, at different rates.** PSS®E data is imported to keep Operational Context current — this can reasonably happen very frequently. A scheme is versioned to record a deliberate engineering decision about defence strategy — this should happen only when an engineer has actually made such a decision. Tying the two together would force one of them to adopt the other's rhythm, which fits neither.

**Reproducibility requires the two to be separable.** To answer "what did the scheme say, and what network condition informed it, at the time of a specific past decision," the scheme's history and the PSS®E history each need to be independently, precisely queryable — and then correlated only at the specific moments an engineer actually captured a value from one into the other. If the two histories were merged or forced to move together, this kind of precise historical reconstruction would become far harder, if not impossible.

**A scheme's stability must not depend on import cadence.** If a new PSS®E import could force open a scheme revision, then how often PSS®E data happened to be refreshed would silently control how often schemes appeared to change — an operational detail dictating engineering process, backwards from how it should work. Continuous Validation (see [06-validation-philosophy.md](../06-validation-philosophy.md)) exists specifically so that PSS®E imports can inform engineers about relevant changes without needing to touch scheme versioning at all.

## Consequences

**Positive:**
- A Published Scheme remains exactly what it was published as, for as long as it remains Published, regardless of how many PSS®E imports occur in the meantime — a stable operational reference.
- Historical reconstruction (what did we know, and what did we decide, at a given point in time) remains precise, because scheme history and PSS®E history are each preserved on their own terms.
- Engineers can review PSS®E data as often as they like for situational awareness without triggering unwanted scheme churn.

**Negative / trade-offs:**
- The system must actively resist the temptation to make PSS®E imports "convenient triggers" for scheme review — Continuous Validation deliberately produces a finding for an engineer to consider, never an automatic revision, which requires discipline to preserve as the system grows.
- Two independent histories mean an engineer must explicitly decide when the two intersect (i.e., when to capture a PSS®E-informed value into a scheme) — there is no automatic reconciliation, by design.
