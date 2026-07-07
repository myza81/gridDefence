# EDR-003: The Relay Registry Models Grid Defence Capability, Not Detailed Relay Asset Management

- **Status:** Accepted
- **Governing document:** [01-engineering-philosophy.md](../01-engineering-philosophy.md) §5 (Step 5)
- **Related:** [02-engineering-concepts.md](../02-engineering-concepts.md) — Relay Registry, Grid Defence Capability

---

## Background

Relays and their associated tripping arrangements are complex physical assets with a great deal of potentially recordable detail: manufacturer, model, firmware version, serial number, settings files, maintenance history, commissioning records, and more. A conventional relay asset management system would treat all of this as its core subject matter.

GridDefence needs *something* about relays and tripping capability, because a Grid Defence Scheme cannot assign load shedding to a bay that has no way to actually execute the trip. The question this decision resolves: should GridDefence's Relay Registry be a general-purpose relay asset management system (modeling all of the above), or should it be scoped to something narrower?

## Decision

**The Relay Registry answers exactly one engineering question: can this bay or switching point be operated by a Grid Defence Scheme? It is not a general-purpose relay asset management system.**

The registry's authoritative content is the capability answer itself — yes or no, for a given bay. Manufacturer, model, firmware, and similar asset details may be recorded as secondary, optional metadata, but they are never required, and they are never the reason the registry exists.

## Rationale

**GridDefence needs a capability answer, not an asset inventory.** Every step in the scheme design workflow that touches the Relay Registry (Step 5, [03-system-workflow.md](../03-system-workflow.md)) asks the same question: can this equipment execute a defence action? Nothing in that workflow needs to know the relay's firmware version to answer it. Building a full asset management data model would answer a question nobody in this workflow is actually asking.

**Scope discipline keeps engineering data honest.** If the Relay Registry tried to be both a capability answer and a full asset record, it would need to be maintained to two different standards of rigor and completeness by two different kinds of stakeholders (a Grid Defence engineer needs the capability answer to be always current and correct; a maintenance engineer would need the asset detail to be complete). Conflating the two risks neither being done well.

**This mirrors how GridDefence treats every other registry.** Each Engineering Knowledge registry (Substation, Equipment, Line Connectivity, Sensitive Customer) is scoped to the specific engineering question the platform actually needs answered, not to being an exhaustive record of everything that could theoretically be known about the underlying physical asset. The Relay Registry follows the same discipline.

**A narrower registry is a more trustworthy registry.** An engineer relying on the Relay Registry's capability answer needs to trust it completely, every time. A registry with a narrow, clearly-stated purpose is far easier to keep accurate and complete than one asked to be everything to everyone.

## Consequences

**Positive:**
- The Relay Registry stays focused, maintainable, and trustworthy for the one question every Shedding Action depends on.
- GridDefence avoids duplicating functionality that a dedicated relay/protection asset management system (outside GridDefence's scope) would do far more completely.
- Optional metadata fields remain genuinely optional — no engineer is blocked from recording a capability answer because a firmware version is unknown.

**Negative / trade-offs:**
- GridDefence cannot answer detailed relay asset questions (maintenance due dates, firmware compliance, settings history) — those remain the responsibility of whatever system does own relay asset management, outside this platform.
- If a future need genuinely requires deeper relay asset detail inside GridDefence, that is a new, separate engineering question requiring its own decision — it should not be retrofitted into the Relay Registry's existing, narrowly-scoped purpose.
