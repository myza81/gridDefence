# EDR-004: GridDefence Supports Engineering Decisions Instead of Automating Them

- **Status:** Accepted
- **Governing document:** [01-engineering-philosophy.md](../01-engineering-philosophy.md) §2, §10 (Principle 1, Principle 10)
- **Related:** [05-design-principles.md](../05-design-principles.md); [06-validation-philosophy.md](../06-validation-philosophy.md); `docs/adr/ADR-010-engineering-decision-support-philosophy.md` (the corresponding software architecture decision)

---

## Background

A large portion of what GridDefence does — comparing scheme assumptions against current network data, checking equipment capability, filtering sensitive customers, computing expected load contributions — is technically capable of being taken one step further into full automation. It would be technically possible, for example, to have GridDefence automatically remove an invalid Shedding Action when its underlying equipment disappears from the topology, or to have it automatically select replacement loads to keep a stage's shedding total on target.

This decision resolves, once and for all, whether GridDefence should move in that direction as it matures, or whether it should remain, permanently, a tool that supports engineering judgement rather than one that exercises it.

## Decision

**GridDefence is, and will remain, an engineering decision-support platform. It does not automate engineering judgement, at any point, for any reason — including cases where automation would be technically straightforward or superficially convenient.**

Every capability GridDefence provides is built to end at the point where information becomes available for an engineer to act on. No capability is extended past that point to also take the action itself.

## Rationale

**Grid Defence Schemes carry real operational stakes.** A Grid Defence Scheme's purpose is to protect the transmission system during a major disturbance. Errors in such a scheme are not abstract — they can mean a scheme fails to isolate the intended pocket, sheds a sensitive customer it should have protected, or fails to execute because the equipment it references is no longer capable. A system that could silently make a decision as consequential as this, without a human specifically deciding it, is not a safer system — it is one where accountability for the decision has quietly disappeared.

**Automation cannot substitute for engineering context an algorithm does not have.** An engineer designing a scheme brings knowledge no automated rule can fully capture — operational policy nuance, awareness of planned future network changes, judgement about acceptable risk in a specific region or season. Even a very sophisticated automated response would be making decisions based on a narrower view of the situation than the engineer actually has.

**A system that reports honestly is more trustworthy than one that acts confidently.** If GridDefence only ever reports what it finds, an engineer can trust that report completely, because there is no possibility the system has already "helpfully" adjusted something based on that same finding. The moment a system starts resolving its own findings, every future report becomes something the engineer must also double-check for hidden side effects.

**This principle scales safely; automation would not.** As GridDefence adds more registries, more schemes, and more validation checks over time, its role stays exactly the same at every step: gather information, compare, report. Adding automated responses would require a new, careful safety argument for every new capability added — an ever-growing surface area of risk that decision support entirely avoids.

## Consequences

**Positive:**
- Every engineering outcome GridDefence contributes to remains traceable to a specific human decision, satisfying the traceability and auditability principles this entire platform is built around ([05-design-principles.md](../05-design-principles.md), Principles 4 and 6).
- The platform can grow — new registries, new schemes, new validation checks — without ever needing to re-litigate whether a new capability is "safe enough" to automate, because none of them are ever automated in the first place.
- Engineers retain full ownership of, and confidence in, every scheme GridDefence helps them maintain.

**Negative / trade-offs:**
- Some genuinely low-risk, repetitive engineering tasks will always require an explicit human action in GridDefence, even where an automated shortcut might seem safe in isolation — this is an accepted cost, not an oversight to be optimized away later.
- The platform's usefulness depends on engineers actually reviewing what it reports; a report nobody reads carries no more value than no report at all. This risk is addressed by making findings clearly visible and persistent (see [06-validation-philosophy.md](../06-validation-philosophy.md)), not by having the system act in the engineer's place when a report goes unread.
