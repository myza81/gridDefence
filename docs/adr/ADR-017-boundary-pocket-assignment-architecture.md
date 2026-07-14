# ADR-017: Boundary Pocket Assignment Architecture

- **Status:** Accepted
- **Date:** 2026-07-12
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1, A1, A2, A13)
- **Governing engineering reference:** [EDR-010](../engineering/edr/EDR-010-boundary-pocket-as-engineering-identity.md) (the engineering "why" this ADR realizes as software architecture)
- **Depends on:** [ADR-006](ADR-006-connectivity-registry-vs-psse-topology-architecture.md), [ADR-007](ADR-007-canonical-engineering-reference-object.md), [ADR-003](ADR-003-psse-topology-and-load-snapshot-separation.md)
- **Affects:** [docs/architecture/network-model-module.md](../architecture/network-model-module.md) §5, §7, §9 rule 11, §13 (receives a status note clarifying relationship, not a rewrite), [docs/architecture/ufls-module.md](../architecture/ufls-module.md) §7.5, [docs/architecture/uvls-module.md](../architecture/uvls-module.md) §7.4, [docs/architecture/emls-module.md](../architecture/emls-module.md) §7.5 (each receives a status note)

---

## Context — Required Repository Reconciliation Report

Per this task's explicit instruction, this section is a full reconciliation of every existing document and implementation touching boundary/pocket concepts, before any new decision is made.

### 1. The current authoritative definition of a boundary pocket

There is no single current authoritative definition. Two independent, non-overlapping designs exist:

- **[`network-model-module.md`](../architecture/network-model-module.md) §1–§18 (original design, never implemented):** a pocket is the output of `analyzeIsland(topology_version_id, load_snapshot_id, cut_set)` — a **computed** `IslandAnalysisResult` given an already-chosen `CutSetDefinition` (a set of PSS/E-native `topology_branch_id`/`topology_transformer_id` elements to treat as open). The *input* (which elements to cut) is assumed already decided before this interface is called; the module answers only "what becomes isolated if these are opened," and persists the answer, immutably, as a recommendation a scheme module may later capture.
- **[`network-model-module.md`](../architecture/network-model-module.md) §19 (Phase 5/7E, actually built):** no pocket or island concept exists at all. What is built is `traverse(start_substation_id, excluded_circuit_ids, max_depth, topology_version_id)` — a generic, parameterised breadth-first reachability primitive over PSS/E Integration's Operational Snapshot (`TopologyBus`/`TopologyBranch`/`TopologyTransformer`, per Phase 7E's migration). It answers "what is reachable from here, given these lines are excluded" — a strictly more general, and strictly less complete, question than "is this a valid, isolated pocket." `traverse` never classifies a result as an island, never validates completeness, and never persists anything.

**Neither design is currently authoritative for the workshops' accepted engineering behaviour**, and this is the central finding this ADR must resolve.

### 2. Whether the engineering identity stored today is Circuit, Circuit Terminal, or another object

Neither, precisely, in either existing design:

- The unbuilt `CutSetDefinition` (§5, §11) stores PSS/E-**native** element ids (`topology_branch_id`/`topology_transformer_id`) — not Equipment Registry identity at all. [`network-model-module.md`](../architecture/network-model-module.md) §9 rule 11 (added post-ADR-007) clarifies that a `Circuit`-level assignment is *resolved* to this native element set **upstream**, via PSS/E Integration's `EquipmentTopologyMap`, before Network Model's interface is ever called — Network Model's own tables never reference `Circuit`/`CircuitTerminal` directly, by explicit design (ADR-006 §7, ADR-007 §6/§9).
- The built `traverse`'s `excluded_circuit_ids` parameter **does** accept Equipment Registry `Circuit` ids directly, translated internally (via the same `EquipmentTopologyMap`) to Operational Branch/Transformer elements for the traversal itself (§19.4, §19.9).
- **In both designs, resolution happens at whole-`Circuit` granularity, never `CircuitTerminal` granularity.** [`network-model-module.md`](../architecture/network-model-module.md) §9 rule 11's own Open Question 1, unresolved since it was written, states this precisely: "today's model has no defined way for a scheme assignment to reference a *subset* of a tee-off's terminals... only whole-`Circuit` resolution (all terminals' elements, unioned) is currently possible."

### 3. How opening ends are represented

- In `traverse`: as `excluded_circuit_ids` — a list of whole `Circuit` ids. Opening a `Circuit` excludes *all* of its `CircuitTerminal`-correlated Operational Branch/Transformer elements, at every substation the `Circuit` touches, simultaneously. There is no way to open only one end of a two-terminal line, and no way to open only one leg of a three-or-more-terminal tee-off `Circuit`.
- In `CutSetDefinition` (unbuilt): as raw PSS/E-native element ids, with the same whole-`Circuit`-resolution limitation imposed one layer up, at the point a scheme module would translate a `Circuit` selection into this shape.

### 4. How the pocket is derived

- `traverse` derives reachability via breadth-first search from a starting substation (seeded from every currently-correlated Bus for that substation), respecting excluded elements and each element's in-service state from the Current `LoadSnapshot`. It returns every substation reached, at what bus-hop depth — **not** a partitioned "inside the boundary" vs. "outside the boundary" answer. A caller supplying a boundary and a starting point still has to interpret the reachable set themselves.
- `IslandAnalysisResult` (unbuilt) would derive its answer via an unspecified "island/reachability detection" algorithm, computing "the resulting isolated substation set(s)" directly.

### 5. How inside/outside membership is determined

**Not defined by either design as it stands.** `traverse` answers "reachable from X, given these exclusions" — this is the correct primitive for computing a pocket's contents (a pocket's substation set is exactly the set reachable from any of its own substations without crossing an opened boundary, and *not* reachable from a designated "rest of grid" reference point without crossing that same boundary), but no existing code or document actually performs this two-sided reachability comparison, states which substation anchors "the rest of the grid," or classifies whether a given selection produces a genuinely bounded, isolated set at all. [`network-model-module.md`](../architecture/network-model-module.md) §19.7 lists "Load pocket / boundary identification" explicitly as an unbuilt **future extension** that would "consume `traverse` as a primitive" — confirming this gap is known and named, not an oversight this ADR is discovering fresh.

### 6. What baseline information is currently preserved

**None, for either design, because neither has been built against a scheme module.** The unbuilt design's `IslandAnalysisResult` would be immutable and reproducible against its exact `(TopologyVersion, LoadSnapshot, CutSetDefinition)` triple (§9 rule 3) — but this describes reproducibility of the *computation*, not preservation of "the pocket's composition as accepted at assignment time" for later comparison, which is the specific baseline the six workshops require. No design to date specifies this comparison mechanism.

### 7. What topology-change verification already exists

None, specific to pockets. The general Continuous Validation philosophy (01-engineering-philosophy.md §7) exists at the engineering-principle level; [`network-model-module.md`](../architecture/network-model-module.md) §8.4 describes a bounded, on-demand recomputation trigger for cut-sets referenced by non-terminal (Draft/Under Review) scheme assignments specifically — but this is a recomputation trigger for the unbuilt design, not a composition-comparison mechanism, and does not exist in the built `traverse` primitive, which is stateless and persists nothing to compare against.

### 8. Where documents or code disagree

- [`network-model-module.md`](../architecture/network-model-module.md) §1–§18 (unbuilt) vs. §19 (built): a genuine, already-flagged-in-document naming and scope collision (§19's own opening reconciliation notes, "Phase 5 — naming/scope tension, flagged for review, not silently resolved"), predating this ADR and not resolved by it beyond what those notes already state.
- [`domain-model.md`](../architecture/domain-model.md) §4 and [`system-overview.md`](../architecture/system-overview.md) list "Network Model — Planned (Phase 5)" as owning `CutSetDefinition`/`IslandAnalysisResult`/`ManualOverride` — both now stale relative to §19's own "remains unbuilt" admission; both require a status note (this pack's Roadmap Corrections document), not a rewrite.
- [`ufls-module.md`](../architecture/ufls-module.md) §7.5, [`uvls-module.md`](../architecture/uvls-module.md) §7.4, and [`emls-module.md`](../architecture/emls-module.md) §7.5 each describe pocket assignments as consuming `analyzeIsland`/`IslandAnalysisResult`/`ManualOverride` — the unbuilt design — with no reference to `traverse` at all (all three predate Phase 5). None of the three describes engineer-driven, incremental boundary construction with continuous completeness feedback (the workshops' accepted behaviour); all three assume the pocket/island is already fully computed and merely *captured* by the scheme module.

## Decision

**Boundary Pocket assignment is built as a new, dedicated capability layered directly on top of the already-built `traverse` primitive — not on the unbuilt `CutSetDefinition`/`IslandAnalysisResult`/`ManualOverride` design, and not by extending `traverse` itself.**

### Opening-point identity

A Boundary Pocket's opening points are `CircuitTerminal` ids (Equipment Registry, per [EDR-010](../engineering/edr/EDR-010-boundary-pocket-as-engineering-identity.md) and [ADR-007](ADR-007-canonical-engineering-reference-object.md)) — **not** whole `Circuit` ids. This is a deliberate, explicit departure from both existing designs' whole-`Circuit`-only resolution (§2–§3 above), required because the workshops' accepted behaviour ("the engineer selects exact line-terminal or circuit-terminal switching points") cannot be expressed at whole-`Circuit` granularity for a tee-off. Closing [`network-model-module.md`](../architecture/network-model-module.md)'s own long-standing ADR-007 Open Question 1 is a prerequisite of this decision, not a follow-on nicety — see Consequences.

### Derivation and completeness

A new, read-only orchestration capability (owned by whichever module coordinates a scheme's Draft-time recommendation flow, per [`network-model-module.md`](../architecture/network-model-module.md) §13's own existing framing — today the scheme module itself; a shared helper if more than one scheme module needs it, per CLAUDE.md §21) performs:

1. Resolve the engineer's selected `CircuitTerminal` set to the Operational Branch/Transformer elements they correlate to for the `TopologyVersion` being evaluated (via `EquipmentTopologyMap`, exactly as `excluded_circuit_ids` already does for whole Circuits) — but at per-terminal granularity, opening only the specific terminal-side connection selected, not the whole `Circuit` it belongs to.
2. Call `traverse` twice: once from a substation inside the candidate boundary (any substation the engineer has indicated is meant to be enclosed), and once from a fixed, externally-supplied "rest of grid" reference substation (a configurable anchor, not invented by this ADR — see Open Question, below), both with the same opening-point exclusions applied.
3. **A candidate boundary is complete** if and only if the two reachable sets are disjoint, and the "inside" reachable set is non-empty and finite (does not include the "rest of grid" anchor). This is the concrete, mechanical realization of EDR-010's completeness requirement, built entirely from `traverse`'s existing, unmodified contract — no change to `traverse`'s own interface or behaviour is required.
4. **An incomplete boundary** (the two reachable sets overlap, or the "inside" set is empty) is reported as such and is not assignable, per EDR-010.
5. The resulting "inside" substation set is the pocket's derived contents — recomputed, live, every time the boundary is evaluated, never itself the stored source of truth (EDR-010).

### What the scheme module stores

A scheme module's pocket assignment (`UflsPocketAssignment`-equivalent, per the Shared Defence Scheme Domain Model) stores:
- The selected `CircuitTerminal` id set — the engineering intent, per EDR-010, and the only part of a pocket assignment CLAUDE.md §5.2 requires to be immutable once Published.
- A **captured baseline**: the derived substation set and `topology_version_id` at the moment of Publication — not a live dependency, exactly mirroring the existing `approved_mw`/`source_load_snapshot_id` capture pattern already established for direct assignments in [`ufls-module.md`](../architecture/ufls-module.md) §7.6. This baseline is what later composition comparisons (Continuous Evaluation) diff against.
- No traceability pointer to `IslandAnalysisResult`/`ManualOverride` (that design remains unbuilt and is not depended upon by this decision) or to any `traverse` call (which is stateless and persists nothing to point to).

### Relationship to Network Model's unbuilt design

This ADR **does not build, and does not require building**, `CutSetDefinition`/`IslandAnalysisResult`/`ManualOverride`. If a future need arises for durable, reproducible, cached analysis results independent of any one scheme module's own capture (e.g. a Dashboard "show all currently valid pockets" view, or heavy-graph async computation at national-grid scale per [`network-model-module.md`](../architecture/network-model-module.md) §18's own risk table), that design remains available as a **future extension layered underneath** this ADR's own boundary-construction/completeness logic, exactly as [`network-model-module.md`](../architecture/network-model-module.md) §19's own "Proposed (not implemented) resolution" already anticipated — this ADR does not foreclose it, and does not implement it now.

## Rationale

**Building on `traverse` rather than the unbuilt design avoids building unneeded infrastructure to satisfy a requirement `traverse` can already answer.** `traverse`'s own philosophy (§19.4: "a generic, parameterised reachability primitive... deliberately the same shape of question a future load-pocket, boundary, or visualization capability would need answered, without this phase building any of those capabilities itself") explicitly names Boundary Pocket construction as the intended future consumer. Building the unbuilt `CutSetDefinition`/`IslandAnalysisResult` design instead — a heavier, async-job-backed, durably-cached analysis-result model — for a capability `traverse` already structurally supports would be premature infrastructure (CLAUDE.md §21) relative to what the workshops' accepted behaviour actually requires: continuous, cheap, synchronous completeness feedback as an engineer incrementally builds a boundary, not a durable, async-computed, cross-scheme-shareable analysis catalog.

**Per-terminal opening-point granularity is not optional — it is the literal engineering behaviour the workshops require.** "The engineer selects exact line-terminal or circuit-terminal switching points" cannot be satisfied by whole-`Circuit` resolution for any tee-off configuration; a workaround (e.g. requiring the engineer to select the whole `Circuit` and accept that all its legs open together) would silently misrepresent what boundary the engineer actually intended, for exactly the class of network configuration ([`network-model-module.md`](../architecture/network-model-module.md)'s own tee-off handling, §19.3) this codebase already models carefully elsewhere.

**Two-directional `traverse` calls, not a single-call heuristic, are required for a correct completeness answer.** A single `traverse` from inside the candidate boundary, checked only for "does it stay bounded" (e.g. by a `max_depth` limit or a substation-count heuristic), cannot reliably distinguish "genuinely isolated" from "very large but still technically isolated" from "not isolated, but the search happened to stop early." Comparing reachability from *both* sides of the candidate boundary against the same exclusion set is the standard, correct way to test cut-set validity, and requires no new primitive beyond `traverse`'s existing, already-tested contract.

**Not implementing `ManualOverride` now is consistent with the workshops' own explicit exclusion: "The application does not automatically redesign the boundary."** `ManualOverride`'s original purpose was letting an engineer's judgement replace an automatically-computed island result. Under this ADR, the boundary is never automatically computed in the first place — the engineer selects opening points directly; the system only reports whether that selection is complete. There is no automated result to override.

## Consequences

**Positive:**
- Requires no new database tables in Network Model, no async job infrastructure, and no change to `traverse`'s own tested, stable public contract — the entire capability is new orchestration logic layered on top of existing, working primitives.
- Directly closes [`network-model-module.md`](../architecture/network-model-module.md)'s own long-standing ADR-007 Open Question 1, which had been carried forward unresolved since Phase 4.
- Gives Continuous Evaluation (a companion document in this pack) a well-defined, cheap-to-recompute basis for pocket-composition-change findings: re-run the same two-directional `traverse` comparison against the current Operational Snapshot and diff against the captured baseline.

**Negative / trade-offs:**
- The "rest of grid" reference substation used for the second `traverse` call (§ Derivation and completeness, step 2) is a genuine open implementation question this ADR does not resolve — a fixed, well-known high-voltage reference bus is the likely answer, but choosing one, and handling a network where no single such bus exists for every study, is deferred to implementation design, flagged explicitly for the Codex foundation-readiness audit.
- Per-terminal `EquipmentTopologyMap` resolution (rather than whole-`Circuit`) is new correlation-matching work PSS/E Integration's existing `EquipmentTopologyMap` may or may not already support at that granularity — this must be verified, not assumed, before implementation begins (also flagged for the audit).
- [`ufls-module.md`](../architecture/ufls-module.md) §7.5, [`uvls-module.md`](../architecture/uvls-module.md) §7.4, and [`emls-module.md`](../architecture/emls-module.md) §7.5's descriptions of pocket assignment consuming `analyzeIsland`/`IslandAnalysisResult`/`ManualOverride` are now superseded for the *mechanism* (not the underlying engineering judgement about when pocket assignment is common vs. rare per scheme type, which this ADR does not revisit) — status notes, not rewrites, per the same practice as ADR-015/016.
- [`network-model-module.md`](../architecture/network-model-module.md) §1–§18's `CutSetDefinition`/`IslandAnalysisResult`/`ManualOverride` design remains fully valid, unbuilt, potential future work — this ADR's own existence must be cross-referenced from that document so a future reader does not mistake the unbuilt design for the current plan (status note).

---

## Alternatives Considered

1. **Build Boundary Pocket construction as new orchestration logic on top of `traverse`, per-`CircuitTerminal` opening-point granularity, as decided above.** **Adopted.** Reuses proven infrastructure, satisfies the workshops' exact engineering requirement, and closes a genuinely blocking open question ([`network-model-module.md`](../architecture/network-model-module.md) ADR-007 Open Question 1) as a necessary side effect.

2. **Build the original, unbuilt `CutSetDefinition`/`IslandAnalysisResult`/`ManualOverride` design first, then layer per-terminal boundary construction on top of it.** **Rejected, for now.** This is a legitimate future path (see Decision, "Relationship to Network Model's unbuilt design") but is materially more infrastructure than the workshops' accepted behaviour requires today — durable async-cached analysis results solve a scale/reuse problem no current requirement names. Building it now would be premature relative to CLAUDE.md §21.

3. **Extend `traverse` itself with a new "detect pocket" mode.** **Rejected.** `traverse`'s own documented philosophy is a deliberately generic, unopinionated reachability primitive (§19.4) — folding pocket-completeness semantics directly into it would couple a general-purpose primitive to one specific consumer's business logic, the same anti-pattern CLAUDE.md A1/[ADR-001](ADR-001-modular-monolith-and-module-communication.md) already guard against for cross-module coupling generally.

4. **Retain whole-`Circuit` opening-point granularity, deferring the tee-off subset problem indefinitely.** **Rejected.** This would not satisfy the workshops' explicit accepted behaviour ("exact line-terminal or circuit-terminal switching points") for any real tee-off configuration, and would silently misrepresent engineer intent for a class of network topology this codebase already models carefully (Equipment Registry's own tee-off handling).
