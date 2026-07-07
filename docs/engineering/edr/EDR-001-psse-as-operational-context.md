# EDR-001: PSS®E as Operational Context, Not Engineering Truth

- **Status:** Accepted
- **Governing document:** [01-engineering-philosophy.md](../01-engineering-philosophy.md) §6 (Layer 2), §9 (Design Principle 9)
- **Related:** `docs/adr/ADR-003-psse-topology-and-load-snapshot-separation.md` (the corresponding software architecture decision)

---

## Background

PSS®E is the authoritative tool for simulating and analyzing the transmission network's electrical behaviour — load flow, stability, and the studies that determine what a defence scheme needs to achieve. GridDefence imports PSS®E's network topology and load data so that engineers designing and maintaining schemes always have accurate, current information about the real network to work against.

The question this decision resolves: once PSS®E data is inside GridDefence, what authority does it carry? Does an imported network fact — a bus, a branch, a load figure — become part of GridDefence's engineering truth in its own right, on the same footing as the Engineering Registries or a Published Scheme? Or does it remain something else — informative, but not authoritative?

This question matters because PSS®E data changes far more often than engineering registries or published schemes do. A load snapshot might be imported daily; a topology import happens whenever the physical network changes. If that constantly-changing data carried the same authority as a Published Scheme, every import would be a potential, silent threat to the stability of every scheme relying on it.

## Decision

**PSS®E data — network topology and load snapshots — is Operational Context. It informs engineering decisions. It never becomes, or automatically produces, an engineering decision itself.**

Concretely: an engineer designing or reviewing a scheme may consult the latest PSS®E topology and load data freely, and GridDefence may compute and display recommendations derived from it (an expected MW figure, a candidate Load Pocket boundary). None of that information is ever written into a scheme automatically. A scheme's content changes only when an engineer, exercising engineering judgement, explicitly decides to change it.

## Rationale

**PSS®E answers a different question than a scheme answers.** PSS®E tells you what the network looks like and how it is loaded, right now. A scheme tells you what should be done if a disturbance occurs. These are related, but they are not the same fact, and conflating them would misrepresent both — treating a snapshot as if it were a decision, and treating a decision as if it needed to track the network's every fluctuation.

**Frequency of change is not the same as importance.** PSS®E data is imported often precisely because it is useful to have current information often. That frequency is a strength for Operational Context and would be a liability for engineering truth — an engineering record that changed as often as a load snapshot would be impossible to trust as a stable operational reference.

**This preserves both engineering rigor and operational agility.** Engineers can import PSS®E data as often as operationally useful — even multiple times a day — without ever putting a Published Scheme's stability at risk. Conversely, a Published Scheme remains fully current in the sense that matters (an engineer can always consult the latest PSS®E data when deciding whether the scheme needs review), without needing to literally change every time new data arrives.

## Consequences

**Positive:**
- Engineers gain unrestricted, low-stakes access to the most current network information available, since consulting it never has an unintended side effect on any scheme.
- Published Schemes remain stable and reliable operational references regardless of how often PSS®E data is refreshed.
- The distinction gives Continuous Validation (see [06-validation-philosophy.md](../06-validation-philosophy.md)) a clean job: compare Operational Context against Engineering Decisions and report the difference, never resolve it.

**Negative / trade-offs:**
- An engineer must always take one additional, deliberate step to convert a PSS®E-informed recommendation into part of a scheme — this is by design, not an oversight, but it does mean nothing about scheme content is ever "automatic," even when the underlying data hasn't meaningfully changed.
- The platform must maintain a permanent, indefinitely-growing history of Operational Context (every topology and load snapshot ever imported), since a scheme approved using a specific snapshot must remain reproducible against that same snapshot indefinitely.
