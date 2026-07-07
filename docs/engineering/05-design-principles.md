# GridDefence Engineering Design Principles

These are the twelve principles that govern GridDefence's architecture, expanding [01-engineering-philosophy.md](01-engineering-philosophy.md) §10's ten founding principles into full explanations, with two further principles (support-module scope, extensibility) drawn from that same document's §9 and §11. Every architecture decision, every module design, and every line of code in GridDefence must be checked against this list. A design that violates one of these principles is wrong, regardless of how convenient it is to build.

---

## 1. Engineering judgement is never automated

**Principle.** No part of GridDefence decides, on an engineer's behalf, what a Grid Defence Scheme should contain.

**Explanation.** GridDefence can compute, compare, and surface information — the expected load a Shedding Action would remove, whether a piece of equipment's capability has changed, whether a scheme's assumptions still hold — but it never selects a Shedding Action, never assembles a Stage, and never decides that a scheme should change. Those are acts of engineering judgement, and engineering judgement belongs to the engineer.

**Why this matters.** A Grid Defence Scheme's correctness ultimately rests on human accountability. If the software ever assembled part of a scheme on its own, no engineer could honestly say they designed it, and the chain of engineering responsibility that makes the scheme trustworthy would be broken.

**Example.** GridDefence can tell an engineer "this bay's capability is confirmed and its expected contribution under the selected snapshot is 45 MW" — it never adds that bay to a Stage by itself.

---

## 2. External engineering studies determine the defence strategy

**Principle.** GridDefence never performs the power system studies that determine what a defence scheme should achieve — required shedding quantum, frequency/voltage thresholds, stability margins.

**Explanation.** Those studies are performed with dedicated simulation tools (PSS®E and equivalent) and the professional judgement of system planning engineers, entirely outside GridDefence. GridDefence's role begins once that engineering requirement already exists.

**Why this matters.** Conflating "what should the scheme achieve" with "how is the scheme implemented and maintained" would make GridDefence responsible for a class of engineering correctness it was never designed, validated, or intended to provide.

**Example.** The required UFLS shedding quantum (e.g. 60% of a 10,000 MW system) is a number an external study produces; GridDefence receives it as a design target, never derives it.

---

## 3. GridDefence manages engineering implementation, not engineering calculation

**Principle.** GridDefence's job is to record, structure, and govern how an already-determined engineering decision is implemented — which bays, which stages, which thresholds — not to calculate any of those values itself.

**Explanation.** This is the practical consequence of Principle 2: once a study has determined a requirement, GridDefence provides the structure (Schemes, Stages, Shedding Actions) and the supporting information (registries, PSS®E context) an engineer needs to turn that requirement into an executable, governed scheme.

**Why this matters.** Keeping this boundary sharp is what lets GridDefence remain a reliable system of record — its outputs are exactly what engineers put into it, never a value it derived on its own that nobody explicitly checked.

**Example.** GridDefence stores and enforces that Stage 1 trips at 49.2 Hz with a 200 ms delay because an engineer entered those values, informed by an external study — it does not compute what that threshold should be.

---

## 4. Every engineering decision must be traceable

**Principle.** Every action that changes a scheme's engineering content or its lifecycle state must be attributable to a specific engineer, at a specific time, for a stated reason.

**Explanation.** Traceability is not a logging afterthought — it is the mechanism that lets any future reader answer "why does the scheme say this" with a real, specific answer rather than a guess.

**Why this matters.** Grid Defence Schemes govern real operational behaviour; when something goes wrong (or right) during a real disturbance, the ability to reconstruct exactly who decided what, and why, is not optional.

**Example.** A Stage's threshold value carries the identity of the engineer who set it, when, and — where a change is being made — the stated engineering reason for the change.

---

## 5. Every published scheme must be reproducible

**Principle.** It must always be possible to reconstruct exactly what a Published Scheme said, and exactly what network and load conditions informed it, at any point in its history.

**Explanation.** Reproducibility depends on two things working together: the scheme's own immutability once published (Principle 4's traceable history), and the fact that any PSS®E information that informed a decision at approval time is captured, not left as a live reference that could later change underneath it.

**Why this matters.** An investigation into a past disturbance, or an audit of a past decision, is only meaningful if "what the scheme said at the time" is a fact, not an approximation.

**Example.** If an approved MW figure was informed by a specific PSS®E Load Snapshot at the time of approval, that figure and the reference to which snapshot informed it are both preserved permanently — even after that snapshot itself is superseded.

---

## 6. Every engineering action must be auditable

**Principle.** Beyond scheme content itself, every meaningful engineering action anywhere in GridDefence — a registry correction, a validation finding's resolution, a review decision — leaves a permanent, append-only record.

**Explanation.** Auditability is broader than scheme traceability (Principle 4): it applies to the registries (Engineering Knowledge) and to the validation process itself, not only to the schemes they support.

**Why this matters.** GridDefence is the authoritative engineering repository for a safety-relevant system. An engineering record that can be silently altered with no trace is not an authoritative record.

**Example.** Correcting a mistakenly-entered piece of equipment in a registry does not erase the mistake — it records the correction, permanently, alongside the original entry.

---

## 7. Engineering decisions are version controlled, and dynamic operational data must never overwrite them

**Principle.** A Grid Defence Scheme evolves only through its own formal lifecycle (Working Draft → Scheme Review → Published Scheme → Archived Scheme); a new PSS®E import never, by itself, creates a new scheme version or changes an existing one.

**Explanation.** These are two sides of the same rule. Operational Context changes on its own schedule — potentially every day — while a scheme's engineering content should only change when an engineer makes a deliberate decision to change it. If operational data could silently modify a published scheme, "version controlled" would be a label without substance.

**Why this matters.** This is the principle that lets a Published Scheme be trusted as a stable operational reference even while the network underneath it keeps changing. See [01-engineering-philosophy.md](01-engineering-philosophy.md) §8, "PSS®E snapshots are temporary operational references. Engineering schemes are permanent engineering documents."

**Example.** Importing a new PSS®E snapshot that changes the expected load through a shed transformer bay never edits the Published Scheme's approved figure — it produces a Validation finding for an engineer to consider.

---

## 8. Engineering registries are authoritative references

**Principle.** The Engineering Knowledge registries (Substation, Equipment, Line Connectivity, Relay, Sensitive Customer) are the single source of truth for the physical engineering environment — nothing else in the system is permitted to assert a competing answer to the same question.

**Explanation.** When Operational Context (PSS®E-derived) appears to disagree with a registry — for example, imported topology implying a circuit's far end has changed from what the registry declares — the registry is not silently overwritten. The disagreement becomes a finding an engineer resolves explicitly, updating the registry themselves if the change is confirmed real.

**Why this matters.** Without this rule, two different parts of the system could each claim to know "what equipment exists," with no way to know which one is right at any given moment.

**Example.** Whether a given bay has Grid Defence Capability is answered by the Relay Registry — not inferred, approximated, or overridden by any other part of the system.

---

## 9. PSS®E provides operational context, not engineering authority

**Principle.** Imported PSS®E data — topology and load snapshots — informs engineering decisions; it never itself becomes, or automatically alters, an engineering decision.

**Explanation.** PSS®E answers "what does the network look like, and how is it loaded, right now" — a genuinely important question, but a different one from "what should the defence scheme do." Only an engineer, acting deliberately, converts a PSS®E-informed recommendation into part of a scheme.

**Why this matters.** This is what allows GridDefence to import PSS®E data as often as needed — even multiple times a day — without that frequency of change ever threatening the stability of an already-published scheme. See [EDR-001](edr/EDR-001-psse-as-operational-context.md) for the full reasoning.

**Example.** A recommended MW figure shown while an engineer is drafting a scheme is clearly advisory; it becomes a real, approved figure only at the moment the engineer explicitly captures it during Scheme Review and Publication.

---

## 10. Validation reports impacts; engineers decide the response

**Principle.** GridDefence's continuous validation process only ever surfaces engineering impacts — a removed transformer, a removed line, an invalidated assignment, a materially changed expected load. It never redesigns, approves, or rejects a scheme on its own.

**Explanation.** Validation is deliberately one-directional: information flows from Operational Context to the engineer; a decision flows back from the engineer to the scheme, never automatically.

**Why this matters.** This is the principle that most directly protects Principle 1 (engineering judgement is never automated) in the one place automation would be most tempting — a validated, quantified impact finding could easily be mistaken for a decision if the system were allowed to act on it directly.

**Example.** GridDefence detecting that a shed transformer no longer exists in the latest topology produces a clearly-flagged finding against the affected scheme; it never removes, modifies, or flags the scheme as invalid on its own authority. See [06-validation-philosophy.md](06-validation-philosophy.md) for the full treatment of this principle.

---

## 11. Supporting modules never become engineering authority

**Principle.** Reporting, dashboards, heatmaps, analytics, historical comparisons, and similar capabilities consume information from the core engineering system — they never originate engineering truth of their own.

**Explanation.** A supporting module may compute a derived view (a load heatmap, a compliance summary, a trend chart), but that view is always a read-only composition of what the core system (registries, PSS®E integration, scheme management, validation) already knows. If a supporting module needs information that doesn't already exist as engineering data or a validated computation, that is a gap in the core system to be addressed there — not a reason for the supporting module to invent its own answer.

**Why this matters.** Once a supporting module is allowed to originate its own engineering facts, the platform has two potential sources of truth for the same question, exactly the failure mode every other principle in this document exists to prevent.

**Example.** A dashboard may display "12 schemes currently reference substations affected by yesterday's topology import" — a derived, read-only summary — but it never becomes the record of which schemes are affected; that record lives in the core validation process. See [07-future-roadmap.md](07-future-roadmap.md) for the full Core Platform / Supporting Modules distinction.

---

## 12. Architecture must remain extensible

**Principle.** New registries, new defence schemes, new validation checks, and new supporting modules must be able to join GridDefence without requiring a redesign of what already exists.

**Explanation.** GridDefence's long-term value depends on outliving the specific set of schemes and registries it starts with. UFLS, UVLS, and EMLS today; future schemes tomorrow; new engineering knowledge registries as new engineering questions arise. Each addition should fit the same shape as what came before it — its own registry, its own scheme, its own bounded engineering concern — never a special case bolted on top of an exception to the existing model.

**Why this matters.** An architecture that requires rework every time something new is added does not actually protect engineering knowledge over the long term — it accumulates risk with every extension instead of accommodating it.

**Example.** A future Special Protection Scheme (SPS) module should be able to reuse the same Scheme Lifecycle, the same registries, and the same validation philosophy already established for UFLS/UVLS/EMLS, without any of those existing schemes needing to change to make room for it.
