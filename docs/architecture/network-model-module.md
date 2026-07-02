# Network Model Module Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document follows the Canonical Module Architecture Document Template (CLAUDE.md **A8**).

Related documents: [system-overview.md](system-overview.md), [domain-model.md](domain-model.md), [substation-registry.md](substation-registry.md), [psse-integration-module.md](psse-integration-module.md), [ufls-module.md](ufls-module.md), [ADR-000](../adr/ADR-000-architecture-principles.md), [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md), [ADR-002](../adr/ADR-002-identity-and-access-management.md), [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md).

---

## 1. Module Overview

Network Model is the analysis module that answers connectivity and reachability questions about the transmission grid — most importantly, "if these specific branches or transformers were opened, which substations become electrically isolated, and how much load would that isolate?" It owns no source data of its own; it derives everything from the immutable `TopologyVersion`/`LoadSnapshot` data owned by [PSS/E Integration](psse-integration-module.md), per [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md).

This module is the direct answer to the gap identified when PSS/E Integration was designed: topology-based ("pocket") load shedding is proven, already-used functionality (confirmed by the Codebase Discovery Report of the legacy MVP), but PSS/E Integration deliberately excludes topology *analysis* from its own scope (`psse-integration-module.md` §4) so that analysis logic has one clear, reusable owner instead of being duplicated inside each scheme module.

---

## 2. Purpose

To provide a single, reusable, reproducible network analysis capability — connectivity graph construction, island/pocket detection, and reachability analysis — that:

- Any scheme module (UFLS, UVLS, EMLS today; SPS/RAS, Black Start, Islanding Strategy, Restoration Planning in the future, per CLAUDE.md §3/§27) can consume without re-implementing graph algorithms.
- Produces recommendations, never authoritative engineering data — a computed or overridden island/pocket result only becomes real engineering data once a scheme module explicitly captures it (mirroring the pattern already established between PSS/E Integration and UFLS's MW treatment).
- Is always reproducible: a given result can be traced back to the exact `TopologyVersion` and `LoadSnapshot` it was computed against, forever.
- Lets an engineer override a computed result with full audit traceability, since automated topology analysis will not always match an engineer's judgment about how an island should actually be defined for shedding purposes.

---

## 3. Responsibilities

Network Model owns:

- ✓ Topology analysis (connectivity graph construction from PSS/E Integration's structural + per-snapshot state data)
- ✓ Island detection (finding electrically isolated sets of substations under a specified set of open branches/transformers)
- ✓ Pocket detection (the same island-detection capability applied to the load-shedding "what gets isolated if we cut these boundary branches" question)
- ✓ Network reachability analysis (general connectivity queries between buses/substations)
- ✓ Disconnected island identification (finding pre-existing, structurally isolated parts of the network — a data-quality check, modeled as the degenerate case of island detection with no additional cuts specified)
- ✓ Topology-derived grouping (collapsing the bus-level graph to a substation-level connectivity view)
- ✓ Analysis results (`IslandAnalysisResult`, durable and reproducible)
- ✓ Analysis cache/read models (avoiding redundant recomputation for identical inputs)
- ✓ The manual engineering override model for computed island/pocket sets (`ManualOverride`)

---

## 4. Non-Responsibilities

Network Model does **not** own:

- ✗ RAW file parsing — owned by PSS/E Integration.
- ✗ PSS/E import workflow — owned by PSS/E Integration.
- ✗ `TopologyVersion` persistence — owned by PSS/E Integration; Network Model reads it read-only.
- ✗ `LoadSnapshot` persistence — owned by PSS/E Integration; Network Model reads it read-only.
- ✗ Substation master data — owned by the Substation Registry; Network Model references substations only by `substation_id`.
- ✗ Scheme assignments (stages, transformer bays, pocket assignments as *scheme* data) — owned by UFLS/UVLS/EMLS. Network Model computes and stores *analysis results*; a scheme module's decision to use a given result for a specific stage is that scheme module's own owned data, never Network Model's.
- ✗ Approved UFLS/UVLS/EMLS data — Network Model's results are always recommendations until a scheme module explicitly captures them (§9).
- ✗ Equipment identity — reserved for a future Equipment Registry; Network Model's graph edges remain PSS/E-native `TopologyBranch`/`TopologyTransformer` references until that module exists.
- ✗ Identity, authentication, or authorization — owned by IAM; Network Model references actors only by `user_id`.
- ✗ Dashboard/reporting presentation — Dashboard reads Network Model's data read-only; it is never written to by Dashboard, and never computes connectivity/island logic itself (CLAUDE.md A12 — this is an authoritative engineering calculation, so it belongs here, not in the frontend).

---

## 5. Owned Entities

| Entity | Description |
|---|---|
| `CutSetDefinition` | An immutable, content-addressed definition of which topology elements (branches/transformers) are treated as open/cut for an analysis. An empty cut-set is valid and represents a base-topology connectivity check. |
| `IslandAnalysisResult` | The durable, reproducible output of running island/reachability detection for one `(TopologyVersion, LoadSnapshot, CutSetDefinition)` triple: the resulting isolated substation set(s), their aggregate MW (sourced from the referenced `LoadSnapshot`), and the algorithm version used. |
| `IslandAnalysisResultSubstation` | Normalized child of `IslandAnalysisResult` — one row per substation in the computed isolated set, with its contributed MW. Modeled as a proper FK-enforced table rather than a JSON blob (see §11 design note). |
| `ManualOverride` | An engineer's override of a specific `IslandAnalysisResult`'s substation membership. References, but never mutates, the computed result it overrides. |
| `ManualOverrideSubstation` | Normalized child of `ManualOverride` — the engineer-specified substation set. |
| `network_model_audit_log` | Network Model's own audit trail (CLAUDE.md A4), covering `ManualOverride` events as engineering audit, and analysis computation as operational logging (§14). |

**Design note — normalized substation sets, not JSON blobs:** the legacy MVP stored isolated/manual substation sets as JSON arrays (`topology_cache.isolated_substations`, `manual_substations`). GridDefence deliberately normalizes these into child tables with real foreign keys to Substation Registry, per CLAUDE.md §11.2 ("all relationships shall be enforced through foreign keys," "orphan records are not permitted") and §11.8 (database-enforced constraints). This also lets referential integrity catch a substation reference that would otherwise silently rot inside an opaque JSON array.

**Connectivity graph is not a persisted engineering entity.** The bus/branch-level graph used internally to run island detection is treated as a derivable, recomputable performance aid — not durable engineering data. It may be cached (e.g. in Redis) for performance, but only `IslandAnalysisResult` (the answer) is durable, versioned PostgreSQL data. This mirrors CLAUDE.md §21's guidance to avoid persisting what can be cheaply and deterministically recomputed, while keeping the actual result — the thing engineers and scheme modules rely on — fully durable and reproducible.

---

## 6. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| `TopologyVersion`, `TopologyBus`, `TopologyBranch`, `TopologyTransformer` | PSS/E Integration | Read-only, via `topology_version_id` and its structural child records — never copied or duplicated |
| `LoadSnapshot`, `LoadSnapshotBusState`, `LoadSnapshotElementState`, `NetworkLoad`, `NetworkGenerator` | PSS/E Integration | Read-only, via `load_snapshot_id` — supplies in-service state (for graph filtering) and MW figures (for result aggregation) |
| Substation | Master Data (Substation Registry) | `substation_id` (UUID) only, on `IslandAnalysisResultSubstation` and `ManualOverrideSubstation` |
| (future) Equipment | Master Data (future Equipment Registry) | Not yet referenced — deferred, same as PSS/E Integration's own deferral (see [psse-integration-module.md](psse-integration-module.md) §17) |
| User | Core Platform (IAM) | `user_id` (UUID) on `ManualOverride.created_by_user_id`; fallback per [ADR-002](../adr/ADR-002-identity-and-access-management.md) |

---

## 7. Domain Model

```
TopologyVersion (PSS/E Integration, external, read-only)
LoadSnapshot    (PSS/E Integration, external, read-only)
        │                    │
        └──────────┬─────────┘
                    ▼
            CutSetDefinition (owned; immutable; content-addressed per topology_version)
                    │
                    ▼
            IslandAnalysisResult (owned; immutable; pinned to exactly one
                                   TopologyVersion + LoadSnapshot + CutSetDefinition)
                    │
                    ├──── (many) IslandAnalysisResultSubstation ──▶ Substation.substation_id (external)
                    │
                    └──── (0..1 Active) ManualOverride (owned)
                                   │
                                   └──── (many) ManualOverrideSubstation ──▶ Substation.substation_id (external)

IslandAnalysisResult ◄──── referenced by (read-only, external) ──── UFLS / UVLS / EMLS
                                   pocket assignment data (owned by the scheme module, NOT by Network Model)
```

**No arrow points from Network Model toward any scheme module.** This is deliberate — see §9, rule 8 (decoupling from scheme modules).

---

## 8. Lifecycle / State Model

### 8.1 CutSetDefinition

Immutable once created. Content-addressed: a hash of its member element ids (scoped to one `topology_version_id`) determines identity, so requesting the "same" cut-set twice against the same topology reuses the existing definition rather than creating a duplicate.

### 8.2 IslandAnalysisResult

```
Computing → Computed | Failed
```

A lightweight lifecycle for tracking an async computation job (§13, requirement 9), not an approval workflow (see §9, rule 1, for why this is not the Canonical Version Lifecycle). Once `Computed`, a result is permanent and immutable — it is never marked "stale" or superseded by a later analysis, because it is pinned to an exact, unchanging `(TopologyVersion, LoadSnapshot, CutSetDefinition)` triple and will always be the correct historical answer for that triple. A newer `LoadSnapshot` produces an entirely new `IslandAnalysisResult` row; it never invalidates or replaces an older one.

### 8.3 ManualOverride

```
Active → Superseded (if replaced by a newer override for the same result)
```

At most one `Active` override may exist per `IslandAnalysisResult` at a time. The **effective** island for any consumer is: the active override's substation set if one exists, otherwise the computed result's substation set. Superseded overrides are retained, immutable, for audit history.

### 8.4 Recomputation on New LoadSnapshot Activation

Recomputation is **on-demand by default**, not automatic and unbounded. When PSS/E Integration activates a new Current `LoadSnapshot` (or `TopologyVersion`), Network Model does not eagerly recompute every historical `CutSetDefinition` — that would be unbounded, wasteful work against a catalog that only grows.

Instead: PSS/E Integration's activation service, after committing its own transaction, may call Network Model's service interface to enqueue a background refresh (Redis/RQ, §13, requirement 9) **scoped only to cut-sets currently referenced by non-terminal (Draft/Under Review) scheme assignments** — a bounded, relevant set. This keeps recommendations reasonably fresh for engineers actively designing a version, without recomputing analysis history that no one will ever look at again. This is a direct in-process service-layer call (CLAUDE.md A1), not a new event-bus mechanism — introducing a formal domain-event/pub-sub infrastructure is noted as a Future Extension (§17) if this direct-call pattern proves limiting.

This recomputation, however it is triggered, **only ever produces new `IslandAnalysisResult` rows**. It never touches an Approved or Active scheme version's already-captured data (§9, rule 9).

---

## 9. Business Rules

1. `IslandAnalysisResult` is **not** governed by the Canonical Version Lifecycle (CLAUDE.md A3) — analysis results are automated, deterministic computations, not approved engineering policy requiring human review.
2. Network Model never writes to `TopologyVersion` or `LoadSnapshot` tables — read-only reference only (CLAUDE.md A1, [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md)).
3. Every `IslandAnalysisResult` is derived purely and deterministically from its `(topology_version_id, load_snapshot_id, cut_set_id)` triple (CLAUDE.md §5.5) plus the recorded `algorithm_version` — the same triple, analyzed with the same algorithm version, always yields the same result.
4. A `CutSetDefinition` with a non-empty set of cut elements models the load-shedding "what becomes isolated if these boundary branches open" question directly (requirement 3 — supports the pocket-shedding workflow found in the legacy MVP). An empty cut-set models a base-topology data-quality check.
5. **Computed island/pocket results are recommendations until captured by a scheme module.** No `IslandAnalysisResult` or `ManualOverride` is ever, by itself, approved engineering data.
6. Engineers may create a `ManualOverride` against any `IslandAnalysisResult`; only one `Active` override may exist per result at a time.
7. Every `ManualOverride` is fully audited: who, when, why (a reason is mandatory), and the resulting substation set (§14).
8. **Network Model's own tables contain no foreign key to any scheme module's owned entities.** Coupling flows only one direction — a scheme module may reference an `IslandAnalysisResult` or `ManualOverride` id, but Network Model never references a `UflsStage`, `UflsAssignment`, or equivalent. This keeps the analysis engine reusable by any future topology-aware module (SPS/RAS, Black Start, Islanding Strategy, Restoration Planning — CLAUDE.md §3/§27) without modification.
9. **Approved scheme versions must not silently change when network analysis is recomputed.** A scheme module may treat Network Model's results as a recommendation only while its own version is Draft or Under Review; at Approval, the scheme module must explicitly capture the substation set and MW into its own owned data, exactly mirroring the pattern already established between PSS/E Integration and UFLS ([psse-integration-module.md](psse-integration-module.md) §9, rule 9; [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md)). A scheme module **may** store a traceability pointer (`source_island_analysis_result_id` or `source_manual_override_id`) as descriptive metadata — never as a live dependency.
10. Heavy graph construction and island-detection computation are designed to run as async background jobs (Redis/RQ per CLAUDE.md's stack); synchronous request paths only enqueue work or serve already-cached, already-computed results.

---

## 10. Validation Rules

- Every member element of a `CutSetDefinition` must belong to the same `topology_version_id` being analyzed — a cut-set cannot mix elements from two different topology versions.
- An empty `CutSetDefinition` is valid (§9, rule 4).
- A `ManualOverride`'s substation set must reference only substations that exist in the Substation Registry — Network Model validates the reference resolves, but never validates or duplicates the substation's own attributes (that remains Substation Registry's responsibility).
- A `ManualOverride` requires a non-empty reason.
- `topology_version_id` and `load_snapshot_id` supplied to an analysis request must reference existing PSS/E Integration records; Network Model validates the reference resolves but does not re-validate PSS/E Integration's own data quality (that is PSS/E Integration's responsibility, per its own validation rules).
- Any recomputation triggered by a `LoadSnapshot` activation (§8.4) must be scoped to cut-sets referenced by non-terminal scheme assignments only — never a blanket recompute of the full historical catalog.

---

## 11. Database Design (Concept)

Conceptual only — no migrations are defined here.

| Table (conceptual) | Key columns (conceptual) | Notes |
|---|---|---|
| `cut_set_definition` | `cut_set_id` (UUID PK), `topology_version_id` (FK, external), `content_hash` (unique per topology_version_id), `created_at` | Immutable; content-addressed for dedup/cache reuse. |
| `cut_set_element` | `id` (BIGINT PK), `cut_set_id` (FK), `topology_branch_id` (FK, nullable, external), `topology_transformer_id` (FK, nullable, external) | Exactly one of branch/transformer set per row (mirrors PSS/E Integration's `LoadSnapshotElementState` XOR pattern). |
| `island_analysis_result` | `analysis_result_id` (UUID PK), `topology_version_id` (FK, external), `load_snapshot_id` (FK, external), `cut_set_id` (FK), `status`, `algorithm_version`, `computed_at` | Immutable once `Computed`; pinned to its exact input triple. |
| `island_analysis_result_substation` | `id` (BIGINT PK), `analysis_result_id` (FK), `substation_id` (FK, external, `ON DELETE RESTRICT`), `contributed_mw` | Normalized, not JSON (§5 design note). |
| `manual_override` | `override_id` (UUID PK), `analysis_result_id` (FK), `status`, `reason`, `created_by_user_id` (FK, external), `created_at`, `superseded_at` | One `Active` per `analysis_result_id` (§8.3). |
| `manual_override_substation` | `id` (BIGINT PK), `override_id` (FK), `substation_id` (FK, external, `ON DELETE RESTRICT`) | Normalized, not JSON. |
| `network_model_audit_log` | `log_id` (BIGINT PK), `entity_type`, `entity_id`, `event_type`, `changed_at`, `changed_by_user_id`, `change_reason` | Owned per CLAUDE.md A4; primarily `ManualOverride` events (§14). |

All foreign keys into PSS/E Integration's and Substation Registry's tables are `ON DELETE RESTRICT`, and Network Model writes exclusively through its own service layer (CLAUDE.md A1, [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md)) — no other module writes to these tables.

---

## 12. API Contract (Concept)

APIs are external/UI-facing contracts (CLAUDE.md §13, A9); conceptual resource shape only.

- `island-analyses` — request an analysis (`topology_version_id`, `load_snapshot_id`, cut-set element list); returns a cached result immediately if one already exists for that exact triple, otherwise enqueues a background computation and returns a job/result reference to poll. Retrieve a specific result by id.
- `manual-overrides` — create an override against a specific `analysis_result_id` (requires reason); list overrides for a result; supersede an existing override.
- `connectivity` (read-only) — returns a display-ready node/edge graph for a given `topology_version_id` + `load_snapshot_id`, filtered to in-service elements, for Dashboard visualization (§17). No cut-set applied — this is the base connectivity view, distinct from an island analysis.

Unlike PSS/E Integration's import workflow, there is no separate preview/commit split here: computing an `IslandAnalysisResult` has no approval-relevant side effect (it is a recommendation by construction, per §9 rule 5), so it is always safe to persist/cache directly.

**Contract requirements (CLAUDE.md A9):** pagination/filtering for list endpoints; structured error responses; authentication/authorization requirements per endpoint (§15); audit-relevant actions flagged (`manual-overrides` writes are audit-relevant; `island-analyses` reads are not).

**Data contracts:** standard three-layer separation (CLAUDE.md A6) — persistence models, domain models, and API DTOs are distinct.

---

## 13. Service Interfaces

Per CLAUDE.md A1 (module communication via in-process service-layer interfaces):

**Network Model exposes, for other modules to consume:**
- `analyzeIsland(topology_version_id, load_snapshot_id, cut_set) → IslandAnalysisResult` — compute-or-retrieve-cached, potentially async/job-backed. **This is the primary interface UFLS/UVLS/EMLS use** to preview a candidate pocket assignment during Draft/Under Review, and to resolve a recommended MW figure for it.
- `getEffectiveIsland(analysis_result_id) → substations + MW` — resolves the computed result, applying any Active `ManualOverride` if present.
- `createManualOverride(analysis_result_id, substations, reason, user_id) → ManualOverride`.
- `getConnectivityGraph(topology_version_id, load_snapshot_id) → nodes + edges` — for Dashboard visualization (§17) and future contingency-analysis extensions.

**Network Model consumes, from other modules' service layers — never their repositories directly:**
- From PSS/E Integration: structural topology data (buses/branches/transformers) and per-snapshot state/load data (in-service flags, P/Q figures), used to build the connectivity graph and compute aggregate MW.
- From Substation Registry: substation existence validation for override substation sets.
- From Core Platform (IAM): authorization checks for override creation; user lookups for audit attribution.

**How UFLS/UVLS/EMLS consume pocket results, without coupling Network Model to them:** a scheme module calls `analyzeIsland(...)` (and `getEffectiveIsland(...)` if an override exists) to obtain a recommended substation set and MW for a candidate pocket, while its own version is Draft/Under Review. The scheme module stores this as its own owned assignment data (e.g. a `UflsPocketAssignment`), optionally recording the `analysis_result_id`/`override_id` as a traceability pointer. At Approval, the scheme module captures the substation set and MW into its own immutable data — Network Model is never queried again for that specific assignment's approved figures, and Network Model has no knowledge that a `UflsStage` exists at all. This is the concrete mechanism that satisfies requirement 6 (avoid coupling Network Model to scheme modules) while still satisfying requirement 10 (Network Model provides the service interface scheme modules need).

---

## 14. Audit Requirements

Per CLAUDE.md §5.4 and A4, and per CLAUDE.md §16's explicit distinction between logging (operational diagnostics) and audit (engineering traceability):

- **`ManualOverride` creation and supersession are audited** (not merely logged): who, when, why (mandatory reason), and the before/after effective substation set — this is a human engineering decision with downstream consequences, squarely within CLAUDE.md §5.4's "who/when/why/what changed."
- **`IslandAnalysisResult` computation is logged, not audited** in the strict CLAUDE.md §16 sense — it is an automated, deterministic calculation, not a human decision. It is still recorded (for operational diagnostics and reproducibility lookup), but does not carry the same engineering-accountability weight as a `ManualOverride`.
- Audit history is append-only and never modified (CLAUDE.md A4).
- Audit log access is itself access-controlled (CLAUDE.md A10).
- When a scheme module captures a substation set/MW informed by an `IslandAnalysisResult` or `ManualOverride` at Approval time, that module's own audit log should record the source id — a cross-module audit consideration this module enables but does not itself write, exactly mirroring [psse-integration-module.md](psse-integration-module.md) §14.

---

## 15. Security Considerations

- All GridDefence engineering data, including network analysis results, is sensitive by default (CLAUDE.md A10); TLS required outside local development.
- **Requesting an analysis** (`analyzeIsland`) may reasonably be available broadly to authenticated engineering users, since it produces only a recommendation with no persistent authority.
- **Creating a `ManualOverride`** is recommended to require the same "Editor"-tier permission as scheme module drafting (mirroring [ufls-module.md](ufls-module.md) §15), given that an override directly shapes what an engineer may go on to approve downstream — this is not a read-only action and should not be available to every reader.
- Read access to analysis results and connectivity graphs is broader than write access, consistent with CLAUDE.md A10's "sensitive by default, gated by authentication" baseline.

---

## 16. Testing Requirements

Per CLAUDE.md §18 and A11, in priority order:

1. **Business rule tests** — determinism (same triple + algorithm version always yields the same result); immutability of `IslandAnalysisResult`; correct single-Active-override enforcement and supersession; a structural/architectural test confirming no Network Model table has a foreign key into any scheme module's schema (§9, rule 8).
2. **Engineering calculation / validation tests** — graph construction correctness (in-service filtering from `LoadSnapshotBusState`/`LoadSnapshotElementState`, cut-set exclusion applied regardless of a cut element's actual in-service status); island/reachability algorithm correctness against known topology fixtures; MW aggregation correctness.
3. **API contract tests** — request/response schema conformance; authorization enforcement per endpoint (§12, §15); correct cache-hit vs. new-computation behavior for repeated identical requests.
4. **Database migration tests** — required once actual migrations are authored (out of scope for this document).
5. **UI behaviour tests** — required once a Network Model-consuming frontend exists; must confirm the frontend only ever renders results/overrides and never computes connectivity or island membership itself (CLAUDE.md A12).

Business rules and engineering calculations must not be merged without accompanying tests (CLAUDE.md A11).

---

## 17. Future Extensions

- **Visual network analysis dashboards** — `getConnectivityGraph` is already designed as a read-only, display-ready interface (§13) so a future Dashboard capability can render network topology and computed islands (e.g. via ECharts graph/geo components per CLAUDE.md's frontend stack) purely by consuming Network Model's output, never computing it client-side (CLAUDE.md A12).
- **Reuse by future topology-aware modules** — SPS/RAS, Black Start, Islanding Strategy, and Restoration Planning (CLAUDE.md §3/§27) are all natural future consumers of the same `analyzeIsland`/`getConnectivityGraph` interfaces, without any change to Network Model itself, by design (§9, rule 8).
- **Contingency (N-1) analysis** — a natural extension of the existing cut-set mechanism (systematically analyzing single-element outages), reusing the same underlying graph-construction and result-storage design.
- **Formal domain-event mechanism for recomputation triggering** — the current direct-service-call-enqueues-a-job pattern (§8.4) is intentionally simple; if it proves limiting as more modules need to react to `LoadSnapshot` activation, a proper event/message mechanism could be introduced — this is new infrastructure, not assumed today (CLAUDE.md §21, avoid premature optimisation).
- **Equipment Registry linkage** — once a future Equipment Registry exists, `CutSetDefinition` elements could reference formal equipment records in addition to PSS/E-native topology elements, mirroring the same deferral already noted in PSS/E Integration's own Future Extensions.

---

## 18. Risks and Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| Algorithm changes over time (island-detection logic improves/changes) | Old `IslandAnalysisResult` rows remain historically valid under the algorithm version they were computed with, but new requests could silently use different logic without anyone noticing a discrepancy | `algorithm_version` is already recorded on every result (§11); surface it wherever a result is displayed, and treat any algorithm change as requiring a documented decision (ADR if it affects reproducibility guarantees) |
| Unbounded growth of near-duplicate `CutSetDefinition`/`IslandAnalysisResult` rows during iterative scheme design (many similar draft attempts) | Storage growth, cache-lookup overhead | Content-addressed dedup on `CutSetDefinition` (§11) already mitigates this; monitor in practice before adding further mitigation |
| National-grid-scale graphs (thousands of buses) computed synchronously | Slow/blocked requests, echoing the Codebase Discovery Report's finding about the legacy MVP's synchronous heavy computation | Async background jobs (Redis/RQ) for analysis computation are mandated, not optional (§9, rule 10) |
| Ad hoc cross-module reads of Network Model's data beyond the reporting-only exception | Erodes module boundary enforcement (ADR-001), complicates future service extraction | Route any read that informs a business decision through Network Model's service interface (§13); reserve raw joins strictly for reporting/dashboards |
| `ManualOverride` used to route around a computed result an engineer simply disagrees with, without adequate scrutiny | Weakens the credibility of automated analysis as a check on manual judgment | Recommend the same elevated permission tier as scheme drafting (§15), and ensure the mandatory reason field is enforced, not optional |
| Recomputation-on-activation (§8.4) scope creep — a well-intentioned engineer widening the "non-terminal assignments" trigger scope over time | Reintroduces the unbounded-recompute risk this design was built to avoid | Keep the recomputation trigger's scope as a reviewed, explicit business rule (§9, rule 10; §10), not an implementation detail left to drift |

---

## Recommended Next Architecture Document

**UFLS module refinement.**

[ufls-module.md](ufls-module.md) §7.4 (Assignment Model) currently models a UFLS assignment as a simple substation + MW pair with a free-text feeder identifier, and its §7.5 (Load MW Treatment) predates both [psse-integration-module.md](psse-integration-module.md)'s recommended-MW service interface and this document's pocket/island analysis interface. Both interfaces now exist and are stable enough to design against. Refining UFLS to properly model pocket-based assignments (consuming `IslandAnalysisResult`/`ManualOverride` via Network Model's service interface, and direct transformer-bay assignments consuming PSS/E Integration's recommended-MW interface) closes the gap the Codebase Discovery Report flagged as UFLS's most significant missing capability relative to the legacy MVP, and gives UVLS/EMLS a complete, validated template to follow rather than a partial one.

**Cross-Scheme Compliance module** remains the single highest-severity *open* architectural risk from the discovery report (the tension between per-module bounded contexts and Rule 1/2's need to check across UFLS/UVLS/EMLS) and should not be deferred indefinitely — but it is independent of Network Model's design and can be sequenced either immediately after UFLS's refinement or in parallel with it.

**Equipment Registry** and **Critical Infrastructure** modules remain important but are not blocked by, or blocking, this document, for the same reasons already given in [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md) and [psse-integration-module.md](psse-integration-module.md)'s equivalent recommendations.
