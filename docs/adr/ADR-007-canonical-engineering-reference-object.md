# ADR-007: Canonical Engineering Reference Object

- **Status:** Accepted
- **Date:** 2026-07-05
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1, §5.3, §8, §11.2, §20, §21, A1, A2, A5)
- **Depends on:** [ADR-000](ADR-000-architecture-principles.md), [ADR-001](ADR-001-modular-monolith-and-module-communication.md), [ADR-002](ADR-002-identity-and-access-management.md), [ADR-003](ADR-003-psse-topology-and-load-snapshot-separation.md), [ADR-006](ADR-006-connectivity-registry-vs-psse-topology-architecture.md)
- **Affects:** [docs/architecture/equipment-registry-module.md](../architecture/equipment-registry-module.md) §7.4, §7.5, §7.7, §7.8 (all require revision once this decision is implemented), [docs/architecture/equipment-registry-connectivity-validation.md](../architecture/equipment-registry-connectivity-validation.md) (this ADR refines and, where they conflict, supersedes that document's tentative naming and field placement — see §3), [docs/architecture/psse-integration-module.md](../architecture/psse-integration-module.md) §17, [docs/architecture/network-model-module.md](../architecture/network-model-module.md), [docs/architecture/ufls-module.md](../architecture/ufls-module.md)/[uvls-module.md](../architecture/uvls-module.md)/[emls-module.md](../architecture/emls-module.md) (assignment target), [docs/architecture/implementation-plan.md](../architecture/implementation-plan.md) (Phase 3/4 sequencing)
- **Informed by:** the workflow scenarios supplied with this decision request (relay wiring, scheme assignment, double-circuit spur, multi tee-off, terminal-specific breakers, PSS/E discrepancy); [equipment-registry-connectivity-validation.md](../architecture/equipment-registry-connectivity-validation.md)'s gap analysis; [equipment-registry-module.md](../architecture/equipment-registry-module.md) §9 rule 7's already-ratified rule that a relay's controlled equipment must belong to the same substation as the relay itself — a constraint this ADR found to be directly load-bearing for the decision below, not incidental to it.

---

## 1. Problem Statement

[ADR-006](ADR-006-connectivity-registry-vs-psse-topology-architecture.md) decided *who owns what* (Equipment Registry owns identity/metadata; PSS/E Integration owns electrical topology; Network Model owns connectivity analysis) and rejected a separate Connectivity Registry. The [connectivity validation](../architecture/equipment-registry-connectivity-validation.md) that followed found that Equipment Registry's documented shape (`IncomingBranchDetail`) could not actually deliver on that ownership as written, and recommended refining it into a circuit-level entity plus a per-terminal entity.

Neither document answered a question that must be settled before any future module can be built against Equipment Registry with confidence: **when a relay is wired, when a defence scheme is designed, when PSS/E topology is correlated, when compliance is checked, or when a dashboard aggregates network state, which single kind of object do all of these modules point at?** Without an explicit answer, each future module is free to invent its own answer independently — one referencing `equipment_id`, another inventing its own "line" concept, another referencing a bay string — silently recreating the exact fragmentation ADR-006 was written to prevent, just one level down. This ADR exists to foreclose that outcome before Phase 3 implementation begins, while there is still no code or migrated data to reconcile.

---

## 2. Business Context

- **Relay Registry** (in this document, this means Equipment Registry's own `Relay`/`RelayControlledEquipment` model — see §3's terminology note; no separate Relay Registry module exists or is proposed) needs to record, precisely, which physical equipment a relay trips. Physical relays operate physical breakers at one physical location — this is not a modelling nicety, it is what a relay *is*.
- **UFLS/UVLS/EMLS assignment** needs an object an engineer can select once, during scheme design, that represents "this line" as a coherent whole — not a collection of per-substation fragments the engineer must remember to assign together.
- **PSS/E topology mapping** needs a matching target precise enough to correlate against real PSS/E structural data (buses/branches, which are themselves inherently endpoint-specific) without losing information at either end of a circuit.
- **Pocket-load analysis** (Network Model) needs, ultimately, a *set of PSS/E branch/transformer elements* to treat as open — whatever object a scheme assignment references must resolve to that set unambiguously and deterministically.
- **Compliance checking** and **Dashboard reporting** both need a stable, human-legible unit to report against ("Line 1 is currently assigned to UFLS Stage 3") — fragmenting this into per-terminal detail would make every report noisier without adding engineering value.
- **Future engineering modules** (SPS/RAS, Black Start, Islanding Strategy, Restoration Planning — CLAUDE.md §3/§27) will all, eventually, need to say "this line" or "this equipment" in their own assignment data. Getting this reference object right once, now, avoids every one of those future modules re-deriving the same answer independently.

---

## 3. Terminology Clarification

| Term | Definition, as used in this ADR |
|---|---|
| **Circuit** | A physical transmission line as a coherent whole, connecting two (or, for a tee-off, more than two) substations — the engineering-level unit a scheme designer thinks and speaks in terms of ("Line 1"). Not itself a PSS/E concept; a GridDefence/Equipment Registry concept. |
| **Feeder** | In conventional utility usage, a distribution-level circuit (typically 11–33kV) carrying power from a substation directly to load. GridDefence's own reference data supports only transmission-class voltages (132/230/275/500kV — confirmed in `backend/app/reference_data/seed.py`); GridDefence has no distribution-level concept anywhere in its domain. Using "Feeder" here would import a voltage-class connotation that does not apply to anything GridDefence models. Evaluated, not assumed — see §8. |
| **Bay** | A substation's local slot/position for a piece of switchgear or a line termination. In this document's refined model, a **Bay Number** (see below) is the human-facing designator distinguishing one circuit from another between the same pair of substations (e.g. "Line 1" vs "Line 2") — it is a property of the *circuit*, not of one terminal alone (both ends of "Line 1" are, by convention, called "Line 1"). |
| **Breaker** | The physical switching device that actually opens/closes a circuit. A **Breaker Number** (e.g. `L25`, `805`, `Z1230`) is local to one substation's own numbering convention and is **terminal-specific** — the same circuit's breaker at each end may (and typically does) carry a completely different, independently-assigned identifier. |
| **Terminal** | One substation's end of a circuit. A two-terminal circuit has exactly two; a tee-off has three or more. This is the physically precise unit at which a relay is wired and at which PSS/E correlation naturally occurs. |
| **Line** | Used informally, interchangeably with Circuit, in engineering speech (as in the worked examples: "PKLG–IGBK Line 1"). Not a distinct architectural concept from Circuit in this ADR — see §8 for why "Circuit" rather than "Line" is nonetheless recommended as the formal domain name. |
| **Equipment** | The existing common identity backbone (equipment-registry-module.md §7.1) shared by every physical asset type — transformers, circuit terminals, and relays alike. Circuit and Circuit Terminal (§6) are new specializations layered on top of this existing backbone, not a replacement for it. |
| **Connectivity** | The *electrical* fact of what is connected to what, as derived exclusively from PSS/E topology (ADR-006 §6-§7) — never asserted directly by Equipment Registry, which asserts *declared*, human-curated circuit membership instead (a related but explicitly distinct concept — see §9). |
| **Protection device / relay** | A physical device, wired to specific equipment at its own substation, that can trip a breaker under configured conditions. Its physical wiring is Master Data (Equipment Registry); the scheme-specific threshold that configures *when* it acts is scheme-owned data (equipment-registry-module.md §7.5) — unchanged by this ADR. |

**On bay number vs. breaker number, restated precisely, correcting a detail from the prior connectivity validation:** the connectivity validation document treated both the circuit/bay identifier and the breaker number as terminal-scoped fields on a single per-terminal entity. Re-examining this ADR's own worked clarification — *"Bay number means Line 1, Line 2, Line 3"* — shows that bay number is properly a **circuit-level** fact (both PKLG's and IGBK's engineers call the same physical line "Line 1"; it is not independently assigned per terminal), while breaker number remains genuinely **terminal-level**. This ADR corrects that placement: bay number moves to the Circuit entity; breaker number remains on the per-terminal entity. This is a refinement of the connectivity validation's proposal, not a reversal of it — the two-entity shape (a circuit-level object plus a terminal-level object) is unchanged; only which entity owns which field is corrected.

---

## 4. Candidate Reference Objects

Evaluated against: Relay Registry, Defence Scheme Assignment, PSS/E Mapping, Compliance Engine, Dashboard, future modules.

### A. Circuit (alone — no terminal-level object at all)

Matches how engineers select and reason about a line during scheme design; a natural, stable unit for Compliance and Dashboard reporting. **Fails** for Relay Registry: cannot express which terminal's breaker a given relay actually operates, and cannot honour the already-ratified same-substation relay constraint (equipment-registry-module.md §9 rule 7) without an implicit, undeclared assumption about which end is meant. **Fails** to give PSS/E mapping the granularity real PSS/E structural data (inherently per-bus/per-branch-end) requires. Circuit alone is necessary but not sufficient.

### B. Feeder

Structurally identical to Circuit (same entity shape, different name) — the evaluation above applies unchanged. As a *name*, evaluated separately in §8 and found unsuitable for this domain.

### C. Circuit Terminal (alone — no circuit-level grouping object above it)

Physically precise; correctly scoped for Relay Registry and for matching individual PSS/E structural elements. **Fails** for Defence Scheme Assignment, Compliance, and Dashboard: forces an engineer designing a scheme to separately track and correctly co-assign every terminal of a line (two for an ordinary circuit, three or more for a tee-off) with nothing in the model itself preventing an incomplete or inconsistent assignment across those terminals. Loses the natural, single unit of engineering intent ("assign Line 1") the worked example explicitly describes. Terminal alone is necessary but not sufficient.

### D. Bay

As currently used in equipment-registry-module.md, `bay_id` is effectively a computed label on the terminal-level row, not a distinct entity. Adopting "Bay" as the canonical object would be functionally equivalent to Option C (Circuit Terminal alone) under a different name, with the same shortfall. Rejected as a distinct candidate for the same reason as C; retained only as a field name (§6, §12).

### E. Breaker

The most physically granular candidate — closest to what a relay actually operates. Correct as a *field* (`breaker_number`, terminal-scoped) but unsuitable as the canonical cross-module reference object: it over-specifies scheme assignment and dashboard reporting with hardware detail no engineer needs at that level (a bay may, in some substation configurations, involve more than one breaker — e.g. breaker-and-a-half schemes — which would force every consumer to reason about multiplicity that is irrelevant to their own concern). Rejected as the canonical object; retained as a field.

### F. Generic Equipment (the existing `Equipment` backbone alone, with no circuit-level or terminal-level specialization at all)

Already exists, already unifies every physical asset type under one `equipment_id`. Suffers exactly the gap the connectivity validation already found in `IncomingBranchDetail`: no structural link between two substations' independently-created rows for the same physical circuit, no natural circuit-level unit for scheme assignment. Necessary as the underlying backbone (Circuit Terminal remains an `Equipment` specialization, §6) but not sufficient on its own.

### G. Hybrid Model

Recommended — see §5 and §6. Neither a pure circuit-level nor a pure terminal-level object satisfies every consumer; the two are not competing answers to the same question, they are correct answers to two different questions ("what line is this, for scheme design" vs. "which specific breaker does this relay operate"), and both questions are real. A hybrid is not a compromise reached by default — it is the only option, of the six pure candidates evaluated above, that does not fail at least one consumer outright.

---

## 5. Workflow Validation

**Workflow A — Relay wiring.** Relay A lives at PKLG (`Equipment.substation_id = PKLG`). It is wired to PKLG's own Circuit Terminal for Line 1 — not to the Circuit as a whole, and not to IGBK's terminal, which the existing same-substation constraint (equipment-registry-module.md §9 rule 7) already forbids. This is not merely permitted by the hybrid model — the already-ratified constraint makes it the only consistent choice. **Validated.**

**Workflow B — Scheme assignment.** UFLS lists feeders wired to relay assignments by resolving each wired Circuit Terminal up to its owning Circuit (`CircuitTerminal.circuit_id`, a single foreign-key traversal) — presenting the engineer with a de-duplicated list of Circuits, not raw terminals. The engineer selects PKLG–IGBK Line 1 as **one Circuit reference** in the scheme's own assignment data. **Validated.**

**Workflow C — Double circuit spur.** Line 1 and Line 2 are two distinct Circuits (distinct `bay_number` values, "1" and "2"), each independently selected. Each Circuit resolves, via its own terminals' PSS/E correlation (§6), to its own PSS/E branch. The scheme assignment's effective cut-set is the union of both Circuits' resolved branches; Network Model determines from that union that the IGBK/NKST pocket becomes isolated when both open. **Validated** — no special-casing required for "more than one Circuit assigned together."

**Workflow D — Multi tee-off.** Modelled as one Circuit with three Circuit Terminals (ABBA, SMRK, NLAI). A user viewing SMRK sees SMRK's own `CircuitTerminal` row, which references the same `circuit_id` as ABBA's and NLAI's rows — so "is SMRK part of the same registered circuit as ABBA and NLAI" is answered directly by Equipment Registry's own data (a single foreign-key traversal, Circuit → all its Terminals), with no dependency on Network Model or PSS/E for this specific question. This refines a point the connectivity validation left open (§ Workflow 2 in that document deferred *all* corridor visibility to Network Model): the narrow "who else shares my registered circuit" question is Equipment Registry's own to answer; the broader "what is the full electrical corridor topology beyond what has been jointly registered as one circuit" question remains Network Model's, unchanged. **Validated**, with this clarification.

**Workflow E — Terminal-specific breaker.** PKLG's Circuit Terminal carries `breaker_number = L25`; IGBK's carries `breaker_number = 805`; both terminals share the same `circuit_id` and the same circuit-level `bay_number = "Line 1"`. **Validated directly** by the corrected field placement in §3.

**Workflow F — PSS/E discrepancy.** Unchanged from ADR-006 §8–§9, now stated at the correct granularity: matching occurs per Circuit Terminal (its bay-derived identifier against the imported `TopologyVersion`), producing clean-match, unmatched, or discrepancy outcomes per terminal; neither side is ever automatically overwritten; resolution requires an authenticated, audited engineering decision. **Validated**, no change to the underlying rule.

---

## 6. Recommended Domain Model Boundary

- **What future modules should reference, in general:** **Circuit** — the canonical object for any module expressing "this line," as a whole, in its own owned data.
- **What users select during defence scheme design:** **Circuit.** An engineer assigns "PKLG–IGBK Line 1" as a single reference; the scheme module never stores or requires per-terminal detail itself.
- **What Relay Registry (Equipment Registry's own relay model) should reference:** **Circuit Terminal** — physically precise, and the only choice consistent with the existing same-substation constraint (equipment-registry-module.md §9 rule 7).
- **What PSS/E `EquipmentTopologyMap` should reference:** **Circuit Terminal**, directly — bay-identifier matching is inherently per-terminal (§3, §5 Workflow F). A Circuit's own effective PSS/E correlation (the set of branch/transformer elements it maps to, for Network Model's cut-set purposes) is the **union** of its terminals' individual `EquipmentTopologyMap` entries, resolved at query time, not stored redundantly on the Circuit itself.
- **What Compliance should reference:** **Circuit** — compliance rules reason about assigned lines, not substation-specific wiring detail.
- **What Dashboard should aggregate:** **Circuit**, as the primary reporting unit, optionally drilling into its Circuit Terminals for detail views (e.g. "show me both ends' breaker numbers for Line 1") — never the reverse (Dashboard should not need to reconstruct "which Circuit is this terminal part of" as a derived, ad hoc computation; the foreign key already makes it a direct lookup).

---

## 7. Relationship to Equipment Registry

**Yes — Equipment Registry should expose this canonical object directly**, as a first-class extension of its existing domain model, not a new module (reaffirming ADR-006 §6-§7).

- **Circuit** is a new entity, sibling to the existing `LoadTransformerDetail`/`AutoTransformerDetail`/`RelayDetail` detail tables conceptually, but distinct in kind: it does not sit directly on one `Equipment` row (equipment-registry-module.md §7.1's "exactly one detail row per `Equipment` row" pattern does not apply to it), because a Circuit is not itself one piece of equipment — it is the grouping object above two or more terminals, each of which *is* its own `Equipment` row.
- **Circuit Terminal** (renamed and generalized from `IncomingBranchDetail`, superseding the connectivity validation's placeholder name `CircuitTerminalDetail`) *is* a per-`Equipment`-row detail table, following the existing pattern exactly: one `Equipment` row (type `IncomingBranch`, unchanged discriminator) per terminal, one `CircuitTerminal` detail row per `Equipment` row, carrying `circuit_id` (FK to the new Circuit entity) and this terminal's own `breaker_number`.
- **Voltage level:** owned by the Circuit entity as its own `voltage_level_id` (FK to existing Core Platform reference data — no new reference table needed, §4/§ Key Findings of the connectivity validation), distinct from, and not required to equal, either terminal substation's own overall `voltage_level_id` (a substation may host multiple voltage classes).
- **Line type:** owned by the Circuit entity as `line_type_id`, referencing a new, small reference table (`Overhead`/`Cable`/`Submarine`/`Hybrid`), following the exact pattern already established for `voltage_level`.
- **Bay number** (the circuit/line designator, "Line 1"/"Line 2"): owned by the Circuit entity (§3's corrected placement).
- **Substation:** each Circuit Terminal references exactly one `Substation.substation_id` via the underlying `Equipment` backbone, unchanged from today's design.

No additional module or abstraction beyond these two entities, layered inside Equipment Registry's existing boundary, is required.

---

## 8. Naming Recommendation

Evaluated: `Circuit`, `Feeder`, `Line Feeder`, `Circuit Feeder`, `Registered Circuit`, `Registered Feeder`, `Equipment Circuit`.

- **Feeder / Line Feeder / Circuit Feeder / Registered Feeder** — rejected. As established in §3, "Feeder" carries a distribution-voltage connotation that does not correspond to anything in GridDefence's domain (transmission-only, 132–500kV — confirmed by GridDefence's own seeded reference data). Compounding it with "Line" or "Circuit" does not resolve the mismatch, it obscures it; a reader familiar with utility terminology would reasonably expect a "Feeder" to be a distribution asset, and would be wrong every time in GridDefence's context.
- **Equipment Circuit** — rejected as redundant. Every entity in this module is already "equipment" by virtue of living inside Equipment Registry; prefixing the word adds length without adding clarity (CLAUDE.md §20 — prefer explicit names, but this is not a case where the plain name is ambiguous).
- **Registered Circuit / Registered Feeder** — the "Registered" qualifier is a reasonable instinct (it would distinguish this entity from PSS/E's own `TopologyBranch`, a genuinely different concept for a related physical thing), but is unnecessary in practice: `TopologyBranch` already carries its own distinct, unambiguous name from a different module (PSS/E Integration), and no other entity in this codebase uses a similar "Registered X" qualifying pattern (Substation, Equipment, Relay all stand unqualified). Introducing the pattern here alone would be inconsistent with established naming convention elsewhere in this series.
- **Circuit** — **recommended.** Already GridDefence's own established vocabulary (`ckt_id` has been part of the domain since `IncomingBranchDetail` was first specified); technically accurate for a transmission-level asset; consistent, unqualified naming matching every other entity in this module (`Equipment`, `Relay`, `Substation`). Its **instances** should continue to be labelled using real engineering convention ("Line 1," "Line 2," via the `bay_number` field, §3) — the entity's formal name and its human-facing label are not required to be the same word, and forcing them to match (by naming the entity "Line" or "Feeder") is not necessary for usability.

**Recommendation: `Circuit` (entity), `CircuitTerminal` (per-terminal entity, "Detail" suffix dropped relative to the connectivity validation's placeholder name — it is being elevated to a genuine, independently referenced domain object by this ADR, not left as a satellite detail table).**

---

## 9. Source of Truth

| Fact | Owner |
|---|---|
| Canonical reference object identity (`circuit_id`) | Equipment Registry (`Circuit`) |
| Bay number ("Line 1"/"Line 2") | Equipment Registry (`Circuit.bay_number`) — corrected from the connectivity validation's terminal-level placement, §3 |
| Breaker number | Equipment Registry (`CircuitTerminal.breaker_number`) — terminal-specific, unchanged in principle from the connectivity validation |
| Voltage level | Core Platform reference data (`voltage_level`), referenced by `Circuit.voltage_level_id` — not owned by Equipment Registry, only referenced, exactly as Substation Registry already does |
| Line type | New Core Platform-style reference table (`line_type`), referenced by `Circuit.line_type_id` |
| Substation terminal references | Equipment Registry (`CircuitTerminal` → `Equipment.substation_id` → Substation Registry, by foreign key only, never copied) |
| PSS/E bus/branch mapping | PSS/E Integration (`EquipmentTopologyMap`, matched per `CircuitTerminal`, §6) |
| Spur/pocket/island determination | Network Model, computed exclusively from PSS/E Integration's data — never from Equipment Registry, unchanged from ADR-006 |

---

## 10. Decision

**Future GridDefence modules shall reference `Circuit` as the canonical engineering object for defence-scheme assignment, compliance checking, and dashboard reporting.**

**Relay wiring and PSS/E topology correlation shall reference `CircuitTerminal`** — the per-substation terminal of a `Circuit` — as the physically precise object those two concerns require.

Every `CircuitTerminal` resolves to exactly one owning `Circuit` (`circuit_id`, a mandatory foreign key). A `Circuit`'s effective correlation to PSS/E topology, for any purpose requiring it (principally Network Model's cut-set construction), is the union of its `CircuitTerminal`s' individual `EquipmentTopologyMap` entries — computed by traversal, never separately stored on `Circuit` itself, to avoid a second, redundant place that correlation could drift out of sync.

Both entities are owned by, and remain internal to, Equipment Registry — this decision does not create a new module, and does not revisit ADR-006's ownership conclusions.

---

## 11. Consequences

**Positive:**
- Every future module (SPS/RAS, Black Start, Islanding Strategy, Restoration Planning, and any not yet named) inherits a single, already-settled answer to "what do I reference for a line" instead of independently re-deriving one.
- The Relay/PSS/E-mapping precision requirement and the scheme-design/reporting simplicity requirement are both satisfied fully, rather than compromised against each other — because they were never actually in conflict once recognised as two different questions.
- Corrects a real field-placement error from the connectivity validation (bay number's ownership) before any schema or code exists to make that correction costly.
- Directly resolves Workflow D (multi tee-off visibility) more cleanly than the connectivity validation had — the "who shares my registered circuit" question is now answered by Equipment Registry alone, with no Network Model dependency for that specific, common case.

**Negative / trade-offs:**
- Two entities (`Circuit`, `CircuitTerminal`) must now be understood together to fully model what was previously described as a single row — a small, deliberate increase in conceptual surface area, in exchange for correctness the single-row model could not deliver.
- `EquipmentTopologyMap`'s design (§6, §9) now carries an explicit aggregation responsibility (union-of-terminals resolution for a Circuit) that must be specified precisely when that module is actually built — this ADR states the rule but does not design the mechanism, consistent with this task's scope.
- Every reference in `equipment-registry-module.md` to `IncomingBranchDetail`, and the equipment-level scheme-assignment migration path it sketches in §7.8, now needs revision to reflect `Circuit`/`CircuitTerminal` and the `circuit_id`-based assignment target — tracked explicitly in §12, not assumed to happen automatically.

---

## 12. Required Refinements Before Phase 3 Implementation

1. Introduce the `Circuit` entity (identity, `bay_number`, `voltage_level_id`, `line_type_id`, `is_interconnector`, lifecycle/status, remarks) as a new Equipment Registry-owned entity.
2. Introduce the `CircuitTerminal` entity (one per `Equipment` row of type `IncomingBranch`; `circuit_id` FK; `breaker_number`; commissioning date) as the generalized, renamed successor to `IncomingBranchDetail`.
3. Formally rename/generalize `IncomingBranchDetail` → `CircuitTerminal` in `equipment-registry-module.md` §7.4, §11, and every cross-reference to it elsewhere in that document.
4. Add the `line_type` reference table (`Overhead`/`Cable`/`Submarine`/`Hybrid`), following the existing `voltage_level` pattern.
5. Define `EquipmentTopologyMap`'s target as `CircuitTerminal` (not `Equipment` generically, not `Circuit`), including the union-of-terminals aggregation rule for resolving a `Circuit`'s full PSS/E correlation (`equipment-registry-module.md` §7.7, `psse-integration-module.md` §17).
6. Define the relay-to-reference-object relationship explicitly: `RelayControlledEquipment` continues to reference `Equipment` rows as it does today, but its documentation must state plainly that, for circuit-type equipment, this always means a `CircuitTerminal`-backed `Equipment` row at the relay's own substation — never a `Circuit` directly (`equipment-registry-module.md` §7.5, §9 rule 7).
7. Define the defence-scheme assignment target explicitly as `circuit_id` for circuit-type assignments, refining the generic `equipment_id`-based migration path already sketched in `equipment-registry-module.md` §7.8 (non-circuit equipment, e.g. transformers referenced directly, continues to use plain `equipment_id`, unaffected by this refinement).
8. Update `network-model-module.md` to state, explicitly, that a scheme assignment's cut-set input is resolved from one or more `Circuit` references via the union-of-terminals rule in item 5 — not left implicit.

None of these refinements require a new module, reverse ADR-006, or require any change to Substation Registry, PSS/E Integration's `TopologyVersion`/`LoadSnapshot` design, or Network Model's own analysis algorithms.

---

## 13. Open Questions

1. Does a tee-off `Circuit` (three or more terminals) always mean "all terminals open together" when referenced by a scheme assignment, or must a scheme be able to reference a *subset* of a tee-off's terminals independently? This ADR's model does not yet resolve that case and it has real engineering significance (opening one leg of a three-way tee is not equivalent to opening all three).
2. Should `bay_number` uniqueness be scoped per substation-pair, per substation, or be allowed to repeat globally with the `Circuit`'s own terminal set providing the true disambiguation? Left for schema design, not resolved here.
3. Is a tee point that is not itself a real Substation Registry entity (e.g. a pole-mounted physical tap with no associated substation) a real near-term requirement? Carried forward, unresolved, from the connectivity validation.
4. Should the `Circuit`/`CircuitTerminal` names recommended in §8 be checked against actual Malaysian/TNB grid-engineering usage before being finalized in a module-document revision, given naming was explicitly scoped as an engineering-usage decision rather than a purely architectural one?
5. `domain-model.md` §4's still-stale "Network Model Domain" description, already flagged as an open item in ADR-006, remains open and is not addressed by this ADR either.
6. This ADR corrects the connectivity validation's bay-number/breaker-number field placement (§3). Should the connectivity validation document itself be amended to match, or left as a superseded historical record with this ADR as the authoritative correction? This ADR does not decide that housekeeping question — flagged for whoever next revises either document.
