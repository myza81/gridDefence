# Boundary Pocket Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (A6, A8). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md). Realizes [ADR-017](../adr/ADR-017-boundary-pocket-assignment-architecture.md), which contains the full required repository reconciliation report — read that ADR first; this document is the architecture built from its decision, and does not repeat the reconciliation itself.

Related: [EDR-010](../engineering/edr/EDR-010-boundary-pocket-as-engineering-identity.md), [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md), [network-model-module.md](network-model-module.md) §19 (the `traverse` primitive this architecture builds on, unmodified), [equipment-registry-module.md](equipment-registry-module.md) §7.5 (`CircuitTerminal`).

**Status update (Foundation Hardening Sprint A — IMPLEMENTED).** The Network Model foundation this document requires is now built: `EquipmentTopologyMap` was verified to already support per-`CircuitTerminal` correlation (it is keyed one row per `(topology_version_id, circuit_terminal_id)` — no PSS/E Integration change was required, only a Network Model query at that existing granularity), `traverse` gained an additive `excluded_circuit_terminal_ids` parameter (§6, below), a real `evaluateBoundary` service method and `POST /network-model/boundary-pocket-evaluations` endpoint now exist (§10, §11), and the "rest of grid" reference substation (§7) is real, environment-driven configuration (`Settings.rest_of_grid_reference_substation_mnemonic`), with a per-request override. See `backend/app/modules/network_model/service.py` (`evaluate_boundary`, `_resolve_excluded_operational_edges_by_terminals`, `_resolve_rest_of_grid_substation_id`) and its test suite. This sprint built only the Network Model foundation — no Boundary Pocket entity, Scheme module, Engineering Workspace, or Evaluation Engine was implemented; every other section below remains architecture, not yet consumed by a scheme module.

**Status update (Foundation Hardening Sprint A.1 — diagnostic evaluator, IMPLEMENTED).** A transient, read-only diagnostic UI now exists for manual engineering UAT of `evaluateBoundary`, ahead of Sprint B's Engineering Workspace: `frontend/src/modules/network_model/pages/BoundaryPocketEvaluatorPage.tsx`, routed at `/network-model/boundary-pocket-evaluator`. **This is not the future Pocket Builder** (§15 "Visual Boundary Pocket construction UI" remains a separate, undesigned Engineering Workspace concern) — it creates no Boundary Pocket entity, no Scheme Version, no assignment, and no engineering finding; every evaluation is transient and freely repeatable, exactly mirroring the existing Network Traversal page's own "engineering exploration tool, not a scheme calculation" framing. It consumes the unchanged `evaluateBoundary` contract as-is. One small, additive read-only contract was added to support it: Equipment Registry's `GET /circuit-terminals` (mirrors the existing `GET /transformer-terminals` precedent — a cross-network Circuit Terminal browse/search surface; the existing path-nested `/circuits/{id}/terminals` is unchanged).

**Status update ([ADR-019](../adr/ADR-019-boundary-pocket-evaluation-by-connected-component-discovery.md) — Foundation Hardening Sprint C, IMPLEMENTED, corrects Sprint A/A.1 above).** Engineering review found that Sprint A's mechanism — two `traverse()` calls, from an engineer-nominated "inside substation" and a configured "rest of grid" reference substation, checked for disjointness — answers a narrower question than [EDR-010](../engineering/edr/EDR-010-boundary-pocket-as-engineering-identity.md) actually asks. EDR-010 never mentions an "inside substation" or a "rest of grid" reference at all; both were ADR-017's own algorithmic choice, not an engineering requirement. **`evaluateBoundary` is corrected to whole-graph connected-component discovery**, per ADR-019: the engineer selects only `CircuitTerminal` opening points — never a nominated inside substation, pocket name, rest-of-grid reference, or expected substation set. The Main Grid (baseline largest connected component) and every isolated island (a post-opening component that split off from it) are discovered from the topology itself and reported in full — zero, one, or many. `inside_substation_id`, `rest_of_grid_substation_id`, and `Settings.rest_of_grid_reference_substation_mnemonic` are removed entirely, not deprecated. §5, §6, §7, §9, §10, §11, §14, and §16 below describe the corrected mechanism as current; ADR-019 records the full "why," including why the removed mechanism was technically valid but narrower than the engineering workflow requires. ADR-017 itself is preserved unedited — only its "Derivation and completeness" section is superseded; its other decisions (per-terminal `CircuitTerminal` opening-point identity, building on `traverse`'s graph-construction primitive rather than the unbuilt `CutSetDefinition`/`IslandAnalysisResult`/`ManualOverride` design, no manual override, no persistence of derived contents as Scheme Data) remain in force and are carried forward unchanged below.

---

## 1. Purpose

To let an engineer construct a Boundary Pocket assignment by selecting exact Circuit Terminal opening points, receive continuous feedback on whether the selection is a complete, valid pocket, and — once Published — leave enough baseline evidence in that Publication's own record to detect, later, whether the pocket's real composition has changed.

## 2. Scope

Consumed by any Defence Scheme module that supports Boundary Pocket assignments (UFLS routinely, EMLS routinely, UVLS rarely — per each scheme's own [Engineering Philosophy](scheme-engineering-principles.md) document and unchanged judgement already recorded in [`ufls-module.md`](ufls-module.md) §7.5, [`uvls-module.md`](uvls-module.md) §7.4, [`emls-module.md`](emls-module.md) §7.5). Owns no scheme data itself — a scheme module's own Boundary Pocket assignment row is that module's own owned data, exactly as [`network-model-module.md`](network-model-module.md) §9 rule 8's decoupling principle already requires for any topology-aware capability.

## 3. Owned Entities

None. This capability is orchestration logic, not a new database-backed module — it composes `traverse` (owned by Network Model, [`network-model-module.md`](network-model-module.md) §19, unmodified) and `EquipmentTopologyMap` (owned by PSS/E Integration, unmodified) at read time, and returns a derived result. This mirrors the existing precedent of `network_model`'s own service layer being a pure read-only composition over other modules' data ([`network-model-module.md`](network-model-module.md) §19.2).

**Implementation placement (Foundation Hardening Sprint A):** `evaluateBoundary` was implemented directly inside `NetworkModelService`/`NetworkModelRouter`, not as a separate cross-cutting orchestration package sitting alongside Network Model — it belongs to the Network Model module, per this sprint's own explicit instruction. This is a placement decision only, not a change to any of this document's engineering behaviour: it still owns no entity, still creates no Boundary Pocket assignment, still raises no finding, and still consumes `EquipmentTopologyMap` and `CircuitTerminal`/Substation existence data exactly as this document already specifies — only *which module's codebase* the composition lives in changed, from an implied separate layer to Network Model itself. §11's service-interface description is updated accordingly.

## 4. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| `CircuitTerminal` | Equipment Registry | `circuit_terminal_id` — the opening-point identity ([EDR-010](../engineering/edr/EDR-010-boundary-pocket-as-engineering-identity.md)) |
| `TopologyBus`/`TopologyBranch`/`TopologyTransformer`, `LoadSnapshotElementState` | PSS/E Integration | Read-only, via `traverse`'s own graph-construction primitive, never directly |
| `EquipmentTopologyMap` | PSS/E Integration | Read-only, for per-terminal correlation resolution (§6) |
| Substation | Substation Registry | `substation_id` — the baseline Main Grid's and every derived isolated island's Substation membership (§7); never a nominated "inside"/"rest of grid" anchor (removed, ADR-019) |

## 5. Domain Model

```
CircuitTerminal (Equipment Registry, external, read-only)
        │
        ▼ per-terminal EquipmentTopologyMap resolution (§6)
Operational Branch/Transformer elements (PSS/E Integration, external, read-only)
        │
        ▼ excluded from the full-graph Bus adjacency (§7)
Baseline connected components (no opening points applied)
        │
        ▼ identify the largest component — the Main Grid (§7)
Post-opening connected components (opening points' correlated elements excluded)
        │
        ▼ every component that split off from the baseline Main Grid
            is a newly isolated island (zero, one, or many)
                       │
                       ▼
            BoundaryPocketEvaluation
   (baseline Main Grid status + every isolated island, or none)
                       │
                       ▼ (if assigned, at Publication)
        Scheme module's own BoundaryPocketAssignment
        (owned by UFLS/UVLS/EMLS — Scheme Data — the selected
         CircuitTerminal set as engineering intent only)
                       │
                       ▼ (at the moment of Publication)
        Findings and Publication Governance's own PublicationRecord
        (Publication Evidence — the derived isolated-island substation
         sets and topology_version_id captured at that moment, immutable)
```

No arrow points from this capability toward any scheme module's own tables — a `BoundaryPocketEvaluation` is a transient, stateless computation result, never persisted by this capability itself. The derived substation sets only ever come to rest in a `PublicationRecord`, never in the scheme module's own `BoundaryPocketAssignment` row — see §8 for the full Scheme Data / Publication Evidence split.

## 6. Per-Terminal Opening-Point Resolution

Each selected `CircuitTerminal` is resolved to the Operational Branch/Transformer element(s) it correlates to, for the `TopologyVersion` being evaluated, via `EquipmentTopologyMap` — the same correlation mechanism `traverse`'s existing `excluded_circuit_ids` parameter already uses at whole-`Circuit` granularity ([`network-model-module.md`](network-model-module.md) §19.4, §19.9), applied here at the individual terminal's own side of the connection only.

**Verified (Foundation Hardening Sprint A): `EquipmentTopologyMap` already supports per-terminal correlation resolution.** It is keyed one row per `(topology_version_id, circuit_terminal_id)` (`psse_integration.models.EquipmentTopologyMap`) — no PSS/E Integration change was required. The gap was entirely on Network Model's own side: `traverse`'s only exclusion parameter (`excluded_circuit_ids`) resolved a *whole* Circuit's terminals, which is correct for an ordinary two-terminal Circuit but over-broad for a tee-off (opening one leg excluded every leg's correlated element). This is now closed: `traverse` gained an additive `excluded_circuit_terminal_ids` parameter, and `evaluateBoundary` (§7, §10, §11) accepts `circuit_terminal_ids` directly, each resolved independently via a query scoped to exactly the terminals supplied — never by resolving their shared Circuit. See `NetworkModelService._resolve_excluded_operational_edges_by_terminals` and `NetworkModelRepository.list_map_entries_for_terminals`.

A `CircuitTerminal` with no correlation for the `TopologyVersion` being evaluated excludes nothing for that terminal specifically — gracefully, never an error, mirroring `traverse`'s own existing "uncorrelated Circuit excludes nothing" tolerance (§19.9). **Corrected (ADR-019):** unlike `traverse`, this is not merely tolerated silently — every uncorrelated selected terminal is reported back explicitly, in `uncorrelated_circuit_terminal_ids` (§10), so the engineer can see which of their selections had no effect, deterministically, without needing to infer it from the island result alone.

## 7. Completeness Evaluation (corrected, ADR-019 — connected-component discovery)

**The engineering question this evaluation answers is: "Which new electrical islands are created when these selected Circuit Terminals are opened, relative to the active Main Grid?"** — not "can one nominated inside substation be separated from one nominated reference substation." The engineer supplies only the selected `CircuitTerminal` opening points; no inside substation, no pocket name, no rest-of-grid reference, and no expected substation set is ever supplied or nominated.

Given a candidate opening-point set:

1. Load the active topology (the Bus/Branch/Transformer graph for the evaluation snapshot) before any opening point is applied.
2. Partition it into connected components — the **baseline**.
3. Confirm the baseline has exactly one substantial Main Grid (the largest component, §"Main Grid identification", below).
4. If the baseline has more than one substantial component, report this as abnormal baseline evidence (`baseline_has_single_main_grid = false`) — independent of whatever opening points were selected.
5. Resolve the selected opening points to their correlated Operational Branch/Transformer elements (§6) and remove those edges from the graph.
6. Recompute connected components across the **full post-opening graph** — never two independently-seeded reachability searches.
7. Identify the surviving Main Grid by continuity from the baseline Main Grid (the post-opening component containing the baseline Main Grid's anchor Bus).
8. Every other post-opening component that shares Buses with the baseline Main Grid is a newly isolated island.
9. Report **every** isolated island — zero, one, or many — never only one nominated component, and never automatically rejected for being "too many."
10. Derive each island's current Substation membership for this report only; nothing here is Scheme Data (§8).

**A boundary is effective (`is_boundary_effective = true`) if and only if at least one isolated island was formed** (step 8 produced a non-empty result). If none was formed, the boundary is incomplete/ineffective — reported with a deterministic `reason` and enough evidence (baseline/post-opening component counts) to help the engineer identify what connectivity remains, never silently rejected without explanation.

**A redundant selected opening point (one whose exclusion is already implied by another selected point) is a finding, not an automatic rejection** — the isolated-island result is computed and reported exactly as if the redundant point were absent; this capability does not itself raise the finding (no scheme engineering finding is implemented here), only exposes the topology evidence (`uncorrelated_circuit_terminal_ids`, island composition) that a future scheme module's own findings logic can use to detect it.

**An ineffective evaluation result can never be committed to a Scheme Version's assignment universe.** Only an evaluation that forms at least one isolated island may become a Boundary Pocket assignment — enforced at the service layer, not only in the UI ([engineering-workspace-architecture.md](engineering-workspace-architecture.md) §5.2). This holds at every point in a pocket's lifecycle, not only during initial construction: an engineer may iterate freely on a candidate boundary inside the Pocket Builder while it is ineffective, but nothing about that iteration is ever part of Scheme Data until the evaluation forms at least one island. There is no state in which an ineffective boundary is assignable-but-flagged.

This is a live, stateless, synchronous computation — cheap enough (whole-graph connected-component discovery over a few thousand Buses, the same order of cost as `traverse`'s own BFS, §19) to re-run on every boundary edit during Draft, with no caching or async job infrastructure required. It is re-run identically for Continuous Evaluation's own composition-change detection (§9). A topology change never redesigns the selected `CircuitTerminal` set — only the derived island result may change, merge, split, or disappear; this is always re-derived and reported, never auto-redesigned.

### Main Grid identification

**The Main Grid is the largest connected component of the baseline (pre-opening) topology graph, by Bus count** — the standard power-system convention for identifying the dominant synchronous system among whatever else the current snapshot happens to contain (unmigrated spurs, de-energised fragments, genuinely separate pre-existing islands), with a deterministic tie-break (lowest minimum Bus Number) for the rare case of an exact size tie. This is a deliberate, explicit policy choice recorded in [ADR-019](../adr/ADR-019-boundary-pocket-evaluation-by-connected-component-discovery.md) — not an accidental default. There is no rest-of-grid override, configuration, or per-request anchor of any kind; the prior Sprint A mechanism (`Settings.rest_of_grid_reference_substation_mnemonic`, `rest_of_grid_substation_id`) is removed entirely, not deprecated.

A single unconnected/uncorrelated Substation sitting in its own trivial baseline component (an unmigrated substation, a not-yet-imported spur) is ordinary registry noise, not an abnormal grid-split condition — only a baseline component reaching a meaningful Substation count besides the Main Grid itself counts toward `baseline_has_single_main_grid = false`.

## 8. What Is Stored — Scheme Data vs. Publication Evidence

Per [scheme-engineering-principles.md](scheme-engineering-principles.md) §11, these are two distinct, non-interchangeable stores. Neither substitutes for the other, and nothing described here is ever duplicated between them.

**Scheme Data (stored by the consuming scheme module, on the `BoundaryPocketAssignment` itself):**
- The selected `CircuitTerminal` id set — immutable once the owning Scheme Version is Published, exactly as any other Published assignment data. This is the entire content of a Boundary Pocket assignment as Scheme Data. Nothing else is stored here — no derived substation set, no topology reference, no MW.
- No pointer to `IslandAnalysisResult` or `ManualOverride` — this capability does not use, and does not require, that unbuilt design ([ADR-017](../adr/ADR-017-boundary-pocket-assignment-architecture.md) Decision).

**Publication Evidence (captured, once, into that Publication's own `PublicationRecord` — [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §2):**
- The derived isolated-island substation set(s) and the `topology_version_id` they were derived against, as they stood at the moment of Publication — descriptive, immutable audit evidence, never a live dependency, mirroring [`ufls-module.md`](ufls-module.md) §7.6's existing `approved_mw`/`source_load_snapshot_id` capture pattern exactly, but now understood to live in the `PublicationRecord`, never on the `BoundaryPocketAssignment` row.
- This baseline is never read by, and never influences, any live evaluation of the Boundary Pocket ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §7's evaluation-vs-evidence separation) — it exists solely so a reviewer can later answer "what did this pocket look like when it was approved for Publication," never to help compute what it looks like now.

## 9. Continuous Evaluation

**This section describes re-evaluation of a Boundary Pocket that was already effective (formed at least one isolated island) at the moment it was committed to the assignment universe** (§7, above; an ineffective result is never committed in the first place). Every finding below therefore concerns a pocket that has since drifted out of validity due to a later network change — never a pocket that was assignable while ineffective. This is the same "assignments never disappear automatically because a source fact changes" principle ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §2) applied to Boundary Pocket validity specifically: the assignment remains, and a finding is raised.

Re-running §7's evaluation against the current Operational Snapshot, for a Published version's Scheme-Data `CircuitTerminal` set (§8), and diffing the result against the baseline captured in that version's own `PublicationRecord` (§8), produces:
- A **structural finding** if the boundary is no longer effective at all (the selected opening points no longer isolate anything) — Critical severity, per [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md).
- A **composition finding** if the boundary remains effective but the derived isolated-island substation set(s) differ from the `PublicationRecord`'s captured baseline (a substation entered or left an island, or an island merged/split, due to a network change) — severity determined by the evaluation logic (e.g. scaled by how much MW the changed substations represent), never hardcoded here.

This comparison reads the `PublicationRecord`'s baseline; it never writes to it — a `PublicationRecord` is immutable once created ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §8) and is never updated to reflect a later re-evaluation, no matter how many composition findings accumulate afterward.

See [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) for the full evaluation model this feeds into.

## 10. API Contract (Implemented, Foundation Hardening Sprint C — ADR-019)

- `POST /network-model/boundary-pocket-evaluations` — accepts only `circuit_terminal_ids` (the selected opening points) and an optional `topology_version_id` (defaulting to Current). No inside substation, no rest-of-grid substation — both removed. Returns a `BoundaryPocketEvaluation`:
  - `topology_version_id` — the snapshot actually evaluated.
  - `baseline_component_count`, `baseline_main_grid_substation_count`, `baseline_has_single_main_grid` — baseline (pre-opening) topology status, evidence rather than a pass/fail gate (§7 "Main Grid identification").
  - `post_opening_component_count`, `is_boundary_effective` — post-opening topology status.
  - `isolated_islands` — every isolated island formed, each with its own authoritative Substation identities (`substation_id`, `substation_mnemonic`); empty if none formed.
  - `circuit_terminal_ids` — the selected opening points, echoed back.
  - `uncorrelated_circuit_terminal_ids` — selected terminals that produced no correlation for this snapshot (§6) — reported, never silently dropped, never a request error.
  - `reason` — a deterministic, human-readable explanation of the result.
  - Deliberately excludes MW, ALSF, Sensitive Customer, scheme validity, publication treatment, or any persistent finding — this remains a pure topology evaluation (§13's ALSF note, below).
  - Always synchronous — no job/polling shape, unlike PSS/E Integration's import workflow. Implemented on Network Model's own router (`app/modules/network_model/router.py`), not a new module.
- No persistence endpoint of its own — a future scheme module's own assignment-creation endpoint calls `NetworkModelService.evaluate_boundary` internally (a service-layer call, not a separate HTTP round-trip from the frontend) as part of validating and capturing a Boundary Pocket assignment. No such scheme module exists yet (out of scope for this sprint).

## 11. Service Interfaces (Implemented, Foundation Hardening Sprint C — ADR-019)

- `NetworkModelService.evaluate_boundary(BoundaryPocketEvaluationRequest) → BoundaryPocketEvaluation` — the primary interface, to be consumed by every future Defence Scheme module's own Boundary Pocket assignment workflow and by Continuous Evaluation, once built.
- Consumes, from Network Model's own repository layer (this capability lives inside Network Model itself, not as an external consumer of it): `traverse`'s own graph-construction primitive (`_build_bus_adjacency_map`, unmodified — `traverse`'s own `excluded_circuit_ids`/`excluded_circuit_terminal_ids` behaviour is untouched and unregressed); a new whole-graph connected-component partition (`_compute_bus_components`) and Main Grid identification (`_identify_main_grid`), composed with that same adjacency primitive rather than a second graph; `EquipmentTopologyMap` per-terminal correlation resolution, extended to also report uncorrelated selections (`_resolve_boundary_exclusions`); `CircuitTerminal` existence validation (`_validate_circuit_terminals_exist`, unchanged — still a genuine request error for a nonexistent terminal, distinct from the tolerated "uncorrelated" case). No `get_settings`/`rest_of_grid_reference_substation_mnemonic` dependency remains — the prior `_resolve_rest_of_grid_substation_id` method and its two exception types are removed entirely.

## 12. Audit Requirements

This capability itself computes and logs (not audits, per the CLAUDE.md §16 distinction already applied consistently to `IslandAnalysisResult`/`traverse` throughout this document series) — it is a deterministic, automated calculation, not a human decision. The audit-relevant events are split across two owners, matching the Scheme Data / Publication Evidence split in §8: the consuming scheme module owns creating, editing, or removing a Boundary Pocket assignment (Scheme Data changes, its own audit log); Findings and Publication Governance owns capturing the baseline into the `PublicationRecord` at the moment of Publish, as part of `recordPublication` ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §11–§12) — the scheme module's own Publish action triggers this capture but does not itself store the result. This mirrors [`network-model-module.md`](network-model-module.md) §14's existing `IslandAnalysisResult` computation vs. `ManualOverride` decision split, with the roles inverted here (there is no `ManualOverride`-equivalent human override in this design, per [ADR-017](../adr/ADR-017-boundary-pocket-assignment-architecture.md) Rationale — the engineer's selection *is* the input, not a correction to a computed suggestion).

## 13. Security Considerations

- `evaluateBoundary` requires no elevated permission beyond whatever permission the calling scheme module's own Draft-editing action already requires — it produces only a recommendation with no persistent authority, mirroring `analyzeIsland`'s own recommended security posture in [`network-model-module.md`](network-model-module.md) §15.
- All GridDefence engineering data, including Boundary Pocket evaluations, is sensitive by default (CLAUDE.md A10); TLS required outside local development.

### ALSF ownership (out of scope for this capability)

Boundary Pocket evaluation is **topology-only** — it must never query or reason about Automatic Load Shedding Functionality (ALSF) capability, and does not do so anywhere in §6/§7's mechanism. ALSF applicability is a **future scheme-validation concern**, owned entirely by the consuming scheme module, not by this capability:
- **UFLS/UVLS** will require every selected direct `TransformerTerminal` or boundary `CircuitTerminal` opening point to have applicable ALSF capability, at the point a scheme module validates a candidate assignment — never at evaluation time here.
- **EMLS** does not require ALSF on its opening points at all (manual/emergency operation, per [`emls-engineering-philosophy.md`](emls-engineering-philosophy.md)).
- ALSF equipment *inside* an isolated island (as opposed to *on* a selected opening point) is irrelevant to boundary formation entirely, for every scheme type — boundary formation is a pure connectivity question; what happens to load inside the resulting island is a separate, later scheme concern.
See [scheme-data-consumption-matrix.md](scheme-data-consumption-matrix.md) and each scheme's own Engineering Philosophy document for the authoritative statement of this boundary.

## 14. Testing Requirements

Per CLAUDE.md §18/A11: baseline single-Main-Grid detection; no-new-component (ineffective) classification; single-island and multiple-island formation; parallel-circuit behaviour (excluding one of several in-service paths does not isolate, excluding the last does); an already-out-of-service path is respected from the active snapshot; a redundant selected opening point does not change the isolated-island result; an uncorrelated `CircuitTerminal` is reported deterministically, never silently dropped; a pre-existing, abnormal multi-component baseline is exposed as evidence; determinism (the same opening-point set, evaluated against the same snapshot, always yields the same result); a structural test confirming this capability persists nothing of its own and holds no foreign key into any scheme module's schema.

**Implemented (Foundation Hardening Sprint C — ADR-019):** `backend/app/modules/network_model/tests/test_service.py` covers all eleven scenarios above (baseline single Main Grid; no-opening-points ineffective; one isolated island via a tee-off leg; two isolated islands via two separate ordinary Circuits; parallel circuits both in service — excluding one does not isolate, excluding both does; parallel circuits with one already out of service — excluding the remaining path alone already isolates; a redundant duplicate opening point on the same Circuit; an uncorrelated tee-off hub terminal; a genuinely disconnected pre-existing baseline cluster; determinism across repeated calls with the same request; no ORM session mutation (`db_session.new`/`dirty`/`deleted`) after evaluation) plus a nonexistent-`CircuitTerminal` rejection test. `backend/tests/test_network_model_api.py` covers authentication, the full HTTP flow with the new response shape, the no-opening-points-is-ineffective case, and unknown-terminal 404 handling. Verified against both SQLite and a real PostgreSQL database. The baseline-diff detection (composition finding vs. structural finding, §9) and the persistence/foreign-key structural test are not yet applicable — they depend on a scheme module's own `PublicationRecord`/assignment tables, which do not exist yet (out of this sprint's scope).

## 15. Future Extensions

- Layering the unbuilt `CutSetDefinition`/`IslandAnalysisResult`/`ManualOverride` design underneath this capability, for durable, cross-scheme-shareable, async-computed analysis results at national-grid scale — remains available, not required, per [ADR-017](../adr/ADR-017-boundary-pocket-assignment-architecture.md) Decision.
- Visual Boundary Pocket construction UI (map-based terminal selection, live-highlighted derived substation set) — an [Engineering Workspace Architecture](engineering-workspace-architecture.md) concern, not designed here.

## 16. Risks and Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| ~~`EquipmentTopologyMap`'s current correlation granularity may not support per-terminal resolution~~ | **Resolved (Foundation Hardening Sprint A).** Verified already per-terminal-keyed; no PSS/E Integration change needed. | Closed — retained only as a historical record of this item's resolution |
| ~~No "rest of grid" reference substation is currently designated anywhere in the architecture~~ | **Superseded, not merely resolved (ADR-019, Foundation Hardening Sprint C).** The mechanism this risk was about (a configured/overridable rest-of-grid anchor) is removed entirely, not resolved on its own terms — the corrected mechanism has no such anchor at all; the Main Grid is discovered from the baseline topology (§7 "Main Grid identification"). | Closed — retained only as a historical record of why the original mechanism was replaced, not extended |
| Whole-graph connected-component discovery over every Bus in the snapshot, on every evaluation | Slow Draft-time feedback at very large (national-grid) scale | Cheap in practice for realistic snapshot sizes (a few thousand Buses) — the same order of cost as `traverse`'s own BFS. Monitor in practice before adding caching/async infrastructure, per CLAUDE.md §21; do not add it pre-emptively |
| "Largest baseline component = Main Grid" is a deterministic but still a policy choice, not a law of physics — a deployment with two genuinely comparable large synchronous islands (rare, but possible during a real system split) would have its Main Grid identity depend on this tie-break | Could misidentify which side is "the Main Grid" for that specific abnormal snapshot | `baseline_has_single_main_grid = false` already surfaces this exact condition as abnormal evidence before any opening-point interpretation is attempted — an engineer reviewing that flag before trusting an evaluation's Main Grid choice is the intended mitigation, not a further algorithm change; revisit only if this proves insufficient in practice |
