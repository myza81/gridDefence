# EDR-010: A Boundary Pocket Is an Engineer-Selected, Continuously-Verified Electrical Completeness Concept

- **Status:** Accepted
- **Governing document:** [01-engineering-philosophy.md](../01-engineering-philosophy.md) §5 Step 6 (Strategy B — Boundary Line Shedding), §7 (Continuous Validation)
- **Related:** [EDR-005](EDR-005-bay-as-engineering-identity.md) (the sibling decision for direct bay-level assignment identity — this EDR is its boundary-shedding counterpart); `docs/adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md`; `docs/adr/ADR-007-canonical-engineering-reference-object.md`; `docs/adr/ADR-017-boundary-pocket-assignment-architecture.md` (the corresponding software architecture decision)

---

## Background

01-engineering-philosophy.md §5 Step 6 describes "Strategy B — Boundary Line Shedding": "engineers may isolate an entire electrical pocket... Open: Line Alpha–Beta; Line Romeo–Charlie. The enclosed network is disconnected as one block." No document to date has stated precisely what engineering object a "boundary line" refers to, how completeness of the enclosed pocket is verified, or how a scheme preserves enough information to notice that a pocket's composition has changed since it was assigned.

[`network-model-module.md`](../../architecture/network-model-module.md) independently designed a `CutSetDefinition`/`IslandAnalysisResult`/`ManualOverride` model for this same engineering idea, built against PSS/E Integration's topology data. That design remains, per that document's own §19 Phase 5 reconciliation note, **entirely unbuilt** — what Phase 5 actually delivered instead is a generic, PSS/E-Operational-Snapshot-sourced reachability primitive (`traverse`) with no notion of "pocket," "island," or "boundary completeness" at all. This EDR resolves what a Boundary Pocket engineering concept actually is, informed by the six workshops, without inventing new behaviour the workshops did not describe.

## Decision

**A Boundary Pocket is the set of substations that becomes electrically isolated when a specific, engineer-selected set of line-terminal or circuit-terminal switching points is opened.** Its engineering identity is the selected set of opening points, not the resulting substation set — the substation set is *derived*, continuously, from the selected opening points against current network connectivity, and can therefore change over time even though the engineer's original selection does not.

- **The engineer selects exact opening points** — Circuit Terminals (per [EDR-005](EDR-005-bay-as-engineering-identity.md) and [equipment-registry-module.md](../../architecture/equipment-registry-module.md) §7.5, the terminal identity already owned by Equipment Registry) at which a line is to be opened. This is a selection of *switching points*, not a free-hand drawing of a boundary on a map.
- **The system continuously evaluates whether the selected set forms a complete electrical pocket.** A "complete" pocket is one where the selected opening points, if actually opened, genuinely isolate a well-defined substation set from the rest of the network — no ambiguous partial isolation, no still-connected escape path.
- **An incomplete boundary is a structural, non-assignable candidate.** It cannot be assigned to a stage or priority group. This is a completeness check, not an engineering-judgement warning — it is either a valid pocket or it is not yet one.
- **Once complete, the engineer may assign the pocket to a stage, or continue adding boundary terminals** (e.g. to shrink or grow the enclosed set), with the completeness re-evaluated after every change.
- **The scheme preserves the selected boundary identities — the opening points themselves — as the engineering intent**, not merely the substation set that happened to result at assignment time.
- **The scheme also preserves enough baseline information to compare current pocket composition against the originally accepted composition.** Because the substation set is derived, not stored as the source of truth, a later network change (a new interconnection, a decommissioned line) can change what a given set of opening points actually isolates. The scheme must be able to say, later: "this pocket's composition at assignment time was X; it is now Y" — without needing to have frozen X into an approved figure the way `approved_mw` is frozen.
- **A topology change that makes the pocket ineffective, or materially changes its composition, is a finding — never an automatic redesign.** Consistent with EDR-004: GridDefence reports; it does not resolve.

## Rationale

**This is a specialization of Continuous Validation (§7), applied to the one engineering concept the existing architecture never fully closed the loop on.** 01-engineering-philosophy.md §7 already establishes that PSS/E imports are compared against existing defence schemes, and discrepancies are reported, never auto-resolved. A Boundary Pocket is exactly the kind of assignment where "the underlying facts changed" is both especially consequential (a pocket that no longer isolates what it once did could mean shedding the wrong set of substations, or failing to isolate anything at all) and especially easy to miss without an explicit completeness/composition-tracking mechanism — which is precisely why the workshops singled it out for explicit resolution.

**Selecting switching points, not substations, matches how a protection engineer actually thinks about boundary shedding.** 01-engineering-philosophy.md's own example — "Open: Line Alpha–Beta; Line Romeo–Charlie" — names *lines to open*, not *substations to include*. The substation set is a consequence of which lines are opened, not an independent choice. Modeling the substation set as the stored source of truth (as an earlier design direction might have) would silently invert this relationship and make the scheme's "true" record something other than what the engineer actually decided.

**Circuit Terminal, not a new object, is the correct opening-point identity.** [EDR-005](EDR-005-bay-as-engineering-identity.md) already settled that a Bay's engineering identity is the terminal object (`CircuitTerminal`/`TransformerTerminal`), not a generic "Equipment" backbone. A "line-terminal or circuit-terminal switching point," per the workshops' own accepted-behaviour wording, is exactly this same object — Equipment Registry's `CircuitTerminal`, already the canonical engineering reference object for a line's per-substation connection point ([ADR-007](../../adr/ADR-007-canonical-engineering-reference-object.md)). No new engineering identity is invented by this EDR.

**Completeness must be evaluated, not assumed, because an incomplete boundary is not a smaller pocket — it is not a pocket at all.** A partially-selected boundary (e.g. one of a three-way tee-off's three legs opened, the other two still closed) does not isolate a well-defined set — some substations may remain reachable through the unopened legs. Treating this as "assignable, just with an unusually large resulting set" would silently misrepresent an engineering error as a valid, if imprecise, choice. The system must distinguish "not yet a pocket" from "a pocket," structurally, before assignment is even offered.

**"Fewer than two terminals opened is never a pocket" generalizes correctly to tee-off circuits.** [`network-model-module.md`](../../architecture/network-model-module.md) §9 rule 11's Open Question 1 already flags that today's connectivity tooling can only resolve a `Circuit` as a whole (union of all its terminals), not a subset of a tee-off's three-or-more terminals. This EDR does not resolve that implementation gap — see [ADR-017](../../adr/ADR-017-boundary-pocket-assignment-architecture.md) — but the engineering *concept* itself (opening points as identity, completeness as a structural gate) is unaffected by whether today's tooling can yet resolve every possible opening-point combination; it simply means some genuinely valid boundary configurations may not yet be constructible until that gap is closed.

## Consequences

**Positive:**
- Closes the one 01-engineering-philosophy.md §5 Step 6 concept ("Boundary Line Shedding") that previously had no precise engineering-identity answer anywhere in the architecture series.
- Reuses Equipment Registry's existing `CircuitTerminal` identity exactly as EDR-005 and ADR-007 already established it — no new engineering identity, no new Master Data ownership question.
- Gives Continuous Validation (§7) a concrete, well-defined thing to compare over time for boundary-based assignments, closing a real gap: previously, only direct bay-level assignments had an obvious "does this equipment still exist" check; a pocket's *composition* had no defined baseline to check against at all.

**Negative / trade-offs:**
- This EDR does not, by itself, resolve how the substation set is *computed* from a set of opening points (an algorithmic/software question) — it states the engineering concept precisely enough for [ADR-017](../../adr/ADR-017-boundary-pocket-assignment-architecture.md) to design the computation against, without prescribing the computation itself.
- The tee-off per-terminal-subset gap (`network-model-module.md` ADR-007 Open Question 1) remains open; this EDR sharpens why it matters (a real class of valid boundary configurations cannot yet be expressed) without closing it.
- "Materially changes its composition" is, deliberately, left as a finding-worthy condition rather than a precisely-quantified threshold here — the exact sensitivity (any change vs. a substantive change) is an implementation/policy detail for the Findings and Publication Governance architecture, not an engineering identity question this EDR needs to answer.
