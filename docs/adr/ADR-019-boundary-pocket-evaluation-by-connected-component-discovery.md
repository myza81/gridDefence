# ADR-019: Boundary Pocket Evaluation by Connected-Component Discovery

- **Status:** Accepted
- **Date:** 2026-07-14
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1, §5.5, A1, A2, A13)
- **Governing engineering reference:** [EDR-010](../engineering/edr/EDR-010-boundary-pocket-as-engineering-identity.md) (unchanged — this ADR corrects a software mechanism, not the engineering intent EDR-010 already states correctly)
- **Supersedes (partially):** [ADR-017](ADR-017-boundary-pocket-assignment-architecture.md)'s "Derivation and completeness" section only — every other decision in ADR-017 remains in force (see "Relationship to ADR-017", below). ADR-017 itself is left unedited, per CLAUDE.md A13.
- **Affects:** [boundary-pocket-architecture.md](../architecture/boundary-pocket-architecture.md) §5–§11, §13, §14, §16 (rewritten to describe the corrected mechanism as current); [network-model-module.md](../architecture/network-model-module.md) §9, §19 (status note); [engineering-workspace-architecture.md](../architecture/engineering-workspace-architecture.md) (status note — Pocket Builder UX terminology); [continuous-evaluation-architecture.md](../architecture/continuous-evaluation-architecture.md) (status note); [shared-defence-scheme-domain-model.md](../architecture/shared-defence-scheme-domain-model.md) (status note); [scheme-data-consumption-matrix.md](../architecture/scheme-data-consumption-matrix.md) (ALSF-ownership clarification); [ufls-engineering-philosophy.md](../architecture/ufls-engineering-philosophy.md), [uvls-engineering-philosophy.md](../architecture/uvls-engineering-philosophy.md), [emls-engineering-philosophy.md](../architecture/emls-engineering-philosophy.md) (ALSF-ownership clarification)

---

## Context

Foundation Hardening Sprint A implemented `evaluateBoundary` exactly as ADR-017 specified: two `traverse()` calls — one from an engineer-nominated "inside substation," one from a configured "rest of grid" reference substation — checked for disjointness of the two reachable sets. Sprint A.1 built a diagnostic UI over this contract and exercised it against real dev PostgreSQL data.

A follow-on engineering review (Boundary Pocket Engineering Validation Investigation, then Workshop 7B — Boundary Pocket Engineering Philosophy Reconciliation) compared this built mechanism against [EDR-010](../engineering/edr/EDR-010-boundary-pocket-as-engineering-identity.md), the engineering document ADR-017 exists to realize as software. The finding:

**EDR-010 never mentions an "inside substation" or a "rest of grid" reference anywhere.** EDR-010 states a Boundary Pocket is "the set of substations that becomes electrically isolated when a specific, engineer-selected set of line-terminal or circuit-terminal switching points is opened" — a statement about what the *topology itself* produces once the selected points are opened, not a statement that the engineer must additionally nominate one substation as "inside" and another as "the rest of the grid" for the system to compare.

"Inside substation" and "rest of grid reference" were ADR-017's own **algorithmic choice** for how to compute EDR-010's requirement using the already-built `traverse` primitive (ADR-017 "Derivation and completeness," step 2: "call `traverse` twice... once from a substation inside the candidate boundary... and once from a fixed, externally-supplied 'rest of grid' reference substation"). This choice was technically valid — it does correctly detect *whether the nominated inside substation is separable from the nominated reference* — but it answers a narrower question than the engineering workflow requires:

- It requires the engineer to already know, and correctly name, which substation is "inside" before the system can confirm anything — but constructing a Boundary Pocket is precisely the exercise of *discovering* what becomes isolated, not confirming a pre-guessed answer.
- It reports only whether *one* nominated substation is separable — never whether the selected opening points create two, three, or more separate islands, a result the two-seed mechanism cannot express at all (a substation is either in the "inside" set, the "rest of grid" set, or — if the two overlap — neither classification is meaningful).
- It depends on a configured "rest of grid" anchor substation that has no engineering meaning of its own — it exists only as an artifact of how the two-seed comparison is computed, and its removal, misconfiguration, or poor choice (e.g., a network with no single obvious high-voltage reference bus) was a real, flagged, unresolved risk in ADR-017 itself (ADR-017 Consequences, "the 'rest of grid' reference substation... is a genuine open implementation question this ADR does not resolve").

## Decision

**`evaluateBoundary` is corrected to whole-graph connected-component discovery.** The engineer selects only `CircuitTerminal` opening points — never an "inside substation," a pocket name, a "rest of grid" reference, or an expected substation set. The stored engineering identity remains only the selected `CircuitTerminal` ids (unchanged from ADR-017); every consequence of opening them is derived, never persisted as engineering truth.

### The engineering question, restated

> Which new electrical islands are created when these selected Circuit Terminals are opened, relative to the active Main Grid?

— not "can one nominated inside substation be separated from one nominated reference substation."

### Evaluation model

1. Load the active topology (the Bus/Branch/Transformer graph for the evaluation snapshot) before any selected opening point is applied.
2. Determine the baseline connected-component partition of that graph.
3. Confirm the baseline has exactly one substantial connected component — the Main Grid.
4. If the baseline has more than one substantial component, report this as abnormal baseline evidence, independent of whatever opening points were selected.
5. Resolve the selected opening points to their correlated Operational Branch/Transformer elements (per-terminal, via `EquipmentTopologyMap` — Sprint A's own correlation mechanism, unmodified) and remove those edges from the graph.
6. Recompute connected components across the **full post-opening graph** — never two independently-seeded reachability searches.
7. Identify the surviving Main Grid by continuity from the baseline Main Grid.
8. Treat every other post-opening component that shares Buses with the baseline Main Grid as a newly isolated island.
9. Report **all** isolated islands found — not only one nominated component, and never automatically rejected for being "too many."
10. Derive each island's current Substation composition for this report only; never persist it as engineering truth.

### Main Grid identification

The Main Grid is defined, deterministically, as the **largest connected component of the baseline topology graph, by Bus count**, with a deterministic tie-break (lowest minimum Bus Number) for the rare case of an exact size tie. This is the standard power-system convention for identifying the dominant synchronous system among whatever else a snapshot happens to contain (unmigrated spurs, de-energised fragments, genuinely separate pre-existing islands).

This is an explicit, justified policy choice, not a silent default: a real transmission network's baseline is expected to have exactly one substantial Main Grid; when it does not, `baseline_has_single_main_grid = false` surfaces this as evidence to the engineer, rather than the evaluation silently picking a side. There is no rest-of-grid override, configuration value, or per-request anchor of any kind in the corrected mechanism — `Settings.rest_of_grid_reference_substation_mnemonic` and the per-request `rest_of_grid_substation_id` override are removed entirely, not deprecated, along with their two dedicated exception types.

A single unconnected/uncorrelated Substation sitting in its own trivial baseline component (an unmigrated substation, a not-yet-imported spur) is tolerated as ordinary registry noise, not flagged as an abnormal grid-split condition — only a baseline component reaching a meaningful Substation count besides the Main Grid itself counts toward `baseline_has_single_main_grid = false`.

### Multiple islands, redundant openings, and topology change

- **Multiple islands are a first-class, expected result**, not an edge case to guard against: zero, one, or many isolated islands may result from a given selection, and every one is reported in full.
- **Boundary completeness is redefined**: a boundary is effective if and only if it creates at least one new isolated island. If none is created, the boundary is incomplete/ineffective, reported with a deterministic reason and enough evidence (baseline/post-opening component counts) to help the engineer identify what connectivity remains — never silently rejected without explanation.
- **A redundant selected opening point** (one whose exclusion is already implied by another selection) does not change the isolated-island result, and is not automatically rejected — it is topology evidence (an uncorrelated-terminal report, an unchanged island composition) that a future scheme module's own findings logic may use to raise a finding. This capability does not itself raise scheme findings.
- **A later topology change never redesigns the selected `CircuitTerminal` set.** The stored opening points are unchanged; only the derived island result may change, merge, split, or disappear on re-evaluation. This is always re-derived and reported, never auto-redesigned — the same "no automatic redesign" principle ADR-017 already established, now correctly applied to a result that may legitimately be plural.

### ALSF ownership (unaffected, restated for clarity)

Boundary evaluation is topology-only and must never query or reason about Automatic Load Shedding Functionality (ALSF) — this was already true under ADR-017 and remains true under this correction. For future scheme validation: UFLS and UVLS will require every selected direct `TransformerTerminal` or boundary `CircuitTerminal` opening point to have applicable ALSF capability, checked by the consuming scheme module at assignment-validation time, never here; EMLS does not require ALSF on its opening points; ALSF equipment inside a derived isolated island is irrelevant to boundary formation for every scheme type.

### API contract

`POST /network-model/boundary-pocket-evaluations`:

**Request** — `circuit_terminal_ids` (required) and an optional `topology_version_id` (defaulting to Current). No `inside_substation_id`, no `rest_of_grid_substation_id`.

**Response** (`BoundaryPocketEvaluation`) — `topology_version_id`; `baseline_component_count`, `baseline_main_grid_substation_count`, `baseline_has_single_main_grid`; `post_opening_component_count`, `is_boundary_effective`; `isolated_islands` (each with its own list of `{substation_id, substation_mnemonic}`); `circuit_terminal_ids` (echoed); `uncorrelated_circuit_terminal_ids`; `reason`. No MW, ALSF, Sensitive Customer, scheme validity, publication treatment, or persistent finding of any kind.

### Non-persistence

This remains a stateless, read-only, synchronous computation, exactly as ADR-017 established — no new database table or migration was required or added. Whole-graph connected-component discovery is composed entirely from `traverse`'s own existing graph-construction primitive (`_build_bus_adjacency_map`, unmodified) plus a new in-memory BFS-based partition; `traverse`'s own `excluded_circuit_ids`/`excluded_circuit_terminal_ids` behaviour, and every other caller of that primitive, is untouched and unregressed.

## Relationship to ADR-017

**Superseded — ADR-017's "Derivation and completeness" section only**, specifically: the two-`traverse()`-call mechanism (step 2), the disjointness-based completeness test (steps 3–4), and the single-nominated-substation derived-contents framing (step 5). The "rest of grid" open implementation question ADR-017 itself flagged (Consequences) is resolved by this ADR — not by choosing an anchor, but by removing the need for one.

**Preserved, unchanged, and still in force:**
- **Opening-point identity** — a Boundary Pocket's opening points are `CircuitTerminal` ids, per-terminal, never whole `Circuit` ids (ADR-017 "Opening-point identity"). This ADR does not revisit this decision at all.
- **Topology-derived consequences, never persisted** — the derived substation/island contents are always recomputed live, never the stored source of truth (ADR-017 "What the scheme module stores"). This ADR strengthens this principle (now explicitly "every island," not just "the inside set") without changing it.
- **No manual override** — there remains no automated result for an engineer's judgement to override; the engineer's selection is the input, the evaluation is a report, not a suggestion (ADR-017 Rationale). This ADR's correction does not introduce one.
- **No new database tables, no async infrastructure** — the capability remains new orchestration logic layered on `traverse`'s existing primitives, not a build-out of the unbuilt `CutSetDefinition`/`IslandAnalysisResult`/`ManualOverride` design (ADR-017 "Relationship to Network Model's unbuilt design"). That design remains available as a future extension, unaffected by this ADR.
- **Per-terminal `EquipmentTopologyMap` correlation** — verified already sufficient in Sprint A; this ADR extends its consumption (reporting uncorrelated selections explicitly) but does not change the correlation mechanism itself.

### Why "inside substation / rest of grid" was technically valid but narrower than required

The two-seed mechanism is not *incorrect* as a test of one specific, narrower claim: given a correctly-nominated inside substation and a correctly-chosen rest-of-grid anchor, disjoint reachability from both genuinely does prove that the nominated inside substation is isolated. The defect is one of **scope, not correctness**: it requires the answer (which substation is "inside") as an input to compute the answer, provides no way to express "these opening points split the grid into three pieces, not two," and introduces a configuration dependency (the rest-of-grid anchor) with no engineering referent of its own. Whole-graph connected-component discovery answers the same underlying physical question — "what does opening these points do to the network's connectivity" — without requiring the engineer to pre-guess the shape of the answer, and without any configuration anchor at all.

## Rationale

**Connected-component discovery is the standard, general algorithm for exactly this class of question**, and is not a heavier computation than the two-seed mechanism it replaces — both are a small number of BFS passes over the same graph `traverse` already constructs; this correction adds no new performance risk (CLAUDE.md §21) and no new infrastructure.

**Removing the rest-of-grid configuration closes a flagged, unresolved risk rather than deferring it further.** ADR-017 explicitly named "choosing a rest-of-grid anchor, and handling a network where no single such bus exists for every study" as a genuine open implementation question it did not resolve. This ADR resolves it by removing the need for the concept entirely, rather than attempting to specify a better default.

**Reporting every isolated island, not only one, is required by the engineering workflow the workshops confirmed.** An engineer constructing a boundary by selecting opening points cannot always know in advance how many pieces the selection will split the grid into; a mechanism that can only ever confirm or deny one pre-nominated piece systematically hides this information from exactly the person who most needs it.

## Consequences

**Positive:**
- Closes ADR-017's own flagged "rest of grid reference substation" open question by removing the concept, rather than leaving it as permanent deployment-specific configuration risk.
- Enables multi-island reporting, a capability the workshops require and the prior mechanism could not express at all.
- Removes an entire category of configuration/misconfiguration surface (`REST_OF_GRID_REFERENCE_SUBSTATION_MNEMONIC`, two dedicated exception types, a per-request override) with no loss of correctness for the single-island case it previously handled.
- No new database tables, no async infrastructure, no change to `traverse`'s own tested, stable public contract — consistent with ADR-017's own "Positive" consequences, preserved.

**Negative / trade-offs:**
- "Largest baseline component = Main Grid" is a deterministic policy choice, not a law of physics; a deployment with two genuinely comparable large synchronous islands during an abnormal real system split would have Main Grid identity depend on the documented tie-break. `baseline_has_single_main_grid = false` surfaces this exact condition as evidence before any opening-point interpretation is attempted, which is the intended mitigation, not a further algorithm change.
- Every consumer of the prior contract (the Sprint A.1 diagnostic evaluator's frontend, and any future scheme-module design notes referencing "inside substation"/"rest of grid") must be updated to the corrected terminology and response shape — a one-time migration cost, paid in full as part of this ADR's own implementation, not deferred.
- [boundary-pocket-architecture.md](../architecture/boundary-pocket-architecture.md) now has three layered "Status update" notes at its head (Sprint A, Sprint A.1, this correction) rather than a single clean narrative — an accepted cost of preserving the document's own history rather than silently rewriting it, consistent with this pack's established additive-status-note practice.

---

## Alternatives Considered

1. **Whole-graph connected-component discovery, per-terminal opening-point identity unchanged, Main Grid = largest baseline component (as decided above).** **Adopted.** Directly answers the engineering question EDR-010 actually asks, removes a flagged configuration risk, and requires no new infrastructure beyond what ADR-017 already built.

2. **Keep the two-seed mechanism, but let the engineer additionally nominate which side is "inside" per evaluation, with the option to see both sides' reachable sets.** **Rejected.** Still requires the engineer to pre-guess the answer the system exists to discover, and still cannot report more than a two-way split — does not close the actual gap the workshops identified.

3. **Keep the two-seed mechanism for the common single-island case, and add a separate whole-graph mode only when the engineer explicitly asks for "multi-island analysis."** **Rejected.** Two mechanisms answering conceptually the same question, permanently, is more implementation surface than one correct mechanism; CLAUDE.md §21 favours the simpler, uniformly-correct design over a mode-switched compromise.

4. **Retain a rest-of-grid anchor concept, but make it optional and auto-detected (e.g., "the largest component") rather than removed.** **Effectively adopted as an implementation detail, not as a user-facing concept.** The Main Grid identification policy in this ADR *is* an auto-detected anchor internally — the distinction that matters is that it is never a configuration value, never engineer-supplied, and never named "rest of grid" in the contract or the UI; it is purely an internal deterministic tie-break exposed only as evidence (`baseline_has_single_main_grid`), never as an input.
