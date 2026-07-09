# Network Model Module Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document follows the Canonical Module Architecture Document Template (CLAUDE.md **A8**).

Related documents: [system-overview.md](system-overview.md), [domain-model.md](domain-model.md), [substation-registry.md](substation-registry.md), [equipment-registry-module.md](equipment-registry-module.md) (Phase 3, complete — owns `Circuit`/`CircuitTerminal` identity, the object a future scheme assignment references), [psse-integration-module.md](psse-integration-module.md), [ufls-module.md](ufls-module.md), [ADR-000](../adr/ADR-000-architecture-principles.md), [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md), [ADR-002](../adr/ADR-002-identity-and-access-management.md), [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md), [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md), [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md) (specifies that a `Circuit`-level scheme assignment resolves to a cut-set via the union of its `CircuitTerminal`s' PSS/E correlations — see §9 rule 11, §13).

**Reconciliation note (post-Phase-3):** this document predates Equipment Registry's Phase 3 implementation and ADR-006/ADR-007, and some of it still described Equipment Registry as future/unbuilt. Equipment Registry is now complete (`Circuit`/`CircuitTerminal`/`Transformer`/`TransformerTerminal`/`SubstationVoltageYard`). This revision corrects those references and adds the ADR-007-mandated note on how a `Circuit`-level assignment resolves to this module's own `CutSetDefinition` input (§9 rule 11, §13) — it does not redesign `CutSetDefinition`, `IslandAnalysisResult`, or any analysis algorithm, all of which remain exactly as originally specified.

**Reconciliation note (Phase 5 — naming/scope tension, flagged for review, not silently resolved):** Phase 5 implemented a backend module also named `network_model` (`backend/app/modules/network_model/`), but it is **not** the module described by §1–§18 below. This section records what was actually built, why it was built under this name despite the apparent overlap, and how the two designs are intended to relate going forward. Nothing in §1–§18 has been changed, redesigned, or implemented against by Phase 5 — `CutSetDefinition`, `IslandAnalysisResult`, `ManualOverride`, and the PSS/E-topology-analysis capability they describe remain exactly as originally specified, and remain entirely unbuilt.

- **What Phase 5 actually built:** a static, PSS/E-independent electrical connectivity model, derived directly and exclusively from Substation Registry and Equipment Registry (`Substation`, `SubstationVoltageYard`, `Circuit`/`CircuitTerminal`, `Transformer`/`TransformerTerminal`). It owns no tables of its own — it is a pure read-only query/composition service layer (`NetworkModelRepository`/`NetworkModelService`) — and answers four engineering questions: substation connectivity (which lines connect to a substation, and to which neighbouring substations), equipment relationships (a substation's transformer bays and line bays, grouped by function), electrical neighbours (the deduplicated neighbouring-substation set), and a generic, parameterised graph traversal (breadth-first reachability from a starting substation, with an `excluded_circuit_ids` parameter modelling "these lines are open" and an optional `max_depth`). It explicitly does **not** perform island/pocket detection, does not compute cut-sets, and does not read PSS/E Integration's `TopologyVersion`/`LoadSnapshot` data at all — see [`docs/architecture/psse-integration-module.md`](psse-integration-module.md) for how that data remains fully separate.
- **Why this is not a contradiction of the Engineering Reference Library:** [`docs/engineering/04-domain-model.md`](../engineering/04-domain-model.md) and [`docs/engineering/02-engineering-concepts.md`](../engineering/02-engineering-concepts.md) never use the phrase "Network Model" — they describe a **Line Connectivity Registry** as part of Engineering Knowledge Layer 1, explicitly independent of PSS/E, built from Substation Registry and Equipment Registry. Phase 5's static model is the first software-side realization of that concept. The name `network_model` was chosen because it is the literal slot [`implementation-plan.md`](implementation-plan.md) reserves for Phase 5, not because it was intended to mean the same thing as this document's pre-existing "Network Model."
- **Why the naming collision was not resolved by renaming or rewriting either side:** Phase 5's own governing instructions required documenting, not silently implementing, any architectural adjustment that touches previously-reviewed design. Renaming this document's module (or Phase 5's) is exactly that kind of adjustment — a decision for the Project Owner / ChatGPT-as-architect to make (CLAUDE.md §23, A14), not one to be resolved unilaterally inside an implementation pass.
- **Proposed (not implemented) resolution, for review:** treat the static model built in Phase 5 as the *foundation* layer, and this document's `CutSetDefinition`/`IslandAnalysisResult`/`ManualOverride` design as a **future extension layered on top of it**, once PSS/E Integration's `EquipmentTopologyMap` correlation (§9 rule 11 below) lets a `Circuit`-level cut-set element be related back to the static model's own `Circuit` references. Concretely, this would mean: (a) renaming this document's capability to something unambiguous — e.g. "Topology Analysis" or "Island Detection" — freeing "Network Model" to mean the static, registry-derived connectivity graph consistently across the codebase and this documentation set; or (b) treating the static model as an internal building block that a renamed analysis module composes with PSS/E-native data. Either way, **`getConnectivityGraph`'s base-connectivity view (§13) becomes a strong candidate to be re-derived from the static model's traversal primitive instead of being built as a second, independent connectivity representation** — but this too is a proposal for review, not a change made here. No code, schema, or interface in §1–§18 has been altered to anticipate this.
- **Documentation of what Phase 5 did build** — its domain, engineering relationships, traversal philosophy, and future extension points — lives in a new §19 below, appended rather than interleaved with §1–§18 so the original, still-fully-valid PSS/E-analysis design remains legible on its own.

**Reconciliation note (Operational Snapshot pivot — Architecture Synchronization Sprint):** [EDR-007](../engineering/edr/EDR-007-phase-7-operational-identity-mapping.md) and [operational-snapshot-architecture.md](operational-snapshot-architecture.md) establish that **Operational Snapshot is authoritative for current electrical topology and current connectivity**; Engineering Registries (Substation Registry, Equipment Registry, and by extension the Line Connectivity Registry concept realized in Equipment Registry's own `Circuit`/`CircuitTerminal` records) remain authoritative for curated engineering identity and metadata only. This resolves the "Proposed (not implemented) resolution" above in one specific direction, without implementing it: the static model Phase 5 built (§19) is confirmed as a **metadata/correlation support layer**, not an independent or authoritative source of current operational topology — it answers "what is this substation's declared connectivity, per Equipment Registry," which is a genuinely useful, legitimate question, but not the same question as "what is currently electrically connected," which only Operational Snapshot can answer. §19's own §19.7 Future Extension Points already named the mechanism (`EquipmentTopologyMap` correlation back to PSS/E-native topology) that would let the static model's `Circuit` references be correlated against Operational Snapshot rather than stand alone; this note confirms that direction as the intended one, going forward. **No code, schema, or interface is changed by this note** — `network_model`'s current service layer continues to answer its four questions exactly as built, from Equipment Registry data, until this direction is actually implemented under its own reviewed change.

**Reconciliation note (Phase 7E — Operational Snapshot traversal migration, IMPLEMENTED):** the direction confirmed above is now built, for the traversal primitive specifically. `NetworkModelService.traverse` (§19.4, revised below) now builds its connectivity graph exclusively from PSS/E Integration's `TopologyBus`/`TopologyBranch`/`TopologyTransformer` (ADR-003) — never from Equipment Registry's `Circuit`/`CircuitTerminal` — answering "what is currently electrically connected" from the only domain that can answer it. The other three questions this module answers (`SubstationConnectivity`, `SubstationEquipment`, `ElectricalNeighbour`) are **unchanged, still Equipment/Substation-Registry-sourced** — they describe *registered* equipment identity and metadata (breaker numbers, bay numbers, circuit names) that exists only in the Registry, not a claim about current operational connectivity, so there was nothing to migrate for them. The public `traverse` request/response shape (`TraversalRequest`/`TraversalResult`) is substation-in/substation-out, unchanged from before this migration, plus one small, unavoidable addition: an optional `topology_version_id` request field and a required `topology_version_id` response field (Snapshot Awareness — see §19.4). See §19.9 for the full migration record.

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
- ✗ Equipment identity — owned by **Equipment Registry** (Master Data, Phase 3, complete: `Circuit`/`CircuitTerminal`/`Transformer`/`TransformerTerminal`). Network Model's own graph edges remain PSS/E-native `TopologyBranch`/`TopologyTransformer` references, unchanged by Equipment Registry's existence — a `Circuit`-level scheme assignment is translated into those native references *before* it reaches Network Model, via PSS/E Integration's `EquipmentTopologyMap` (see §9 rule 11, §13; [psse-integration-module.md](psse-integration-module.md) §8a). Network Model itself never references `Circuit`/`CircuitTerminal` directly and must never acquire a connectivity-analysis capability inside Equipment Registry (ADR-006 §7, unchanged).
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
| `Circuit`/`CircuitTerminal` | Master Data (Equipment Registry, Phase 3) | **Not referenced directly by any Network Model table.** A scheme assignment's `Circuit` reference is resolved to native `topology_branch_id`/`topology_transformer_id` elements *before* it reaches this module's `analyzeIsland`/`CutSetDefinition` interface, via PSS/E Integration's `EquipmentTopologyMap` (§9 rule 11, §13) — see [psse-integration-module.md](psse-integration-module.md) §8a. |
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
11. **A scheme assignment made at `Circuit` granularity resolves to a `CutSetDefinition`'s member elements via the union of that `Circuit`'s `CircuitTerminal`s' individual PSS/E correlations** (ADR-007 §6, §10, §12 item 8) — never by Network Model referencing `Circuit`/`CircuitTerminal` directly (rule 8 above is not weakened by this). Concretely: the calling scheme module (or an intermediating service) first calls PSS/E Integration's `Circuit`-resolution interface ([psse-integration-module.md](psse-integration-module.md) §13, §8a) to obtain the set of native `topology_branch_id`/`topology_transformer_id` elements that `Circuit` currently maps to, *then* supplies that resolved element set to Network Model's own `analyzeIsland`/`CutSetDefinition` interface (§13) exactly as it already accepts any other element list — no new parameter shape or analysis logic is required on Network Model's side for this. **Open implication, not resolved here (ADR-007 Open Question 1):** a tee-off `Circuit` has three or more `CircuitTerminal`s; today's model has no defined way for a scheme assignment to reference a *subset* of a tee-off's terminals (e.g. "open only the ABBA leg, not SMRK or NLAI") — only whole-`Circuit` resolution (all terminals' elements, unioned) is currently possible. If per-terminal-subset assignment becomes a real requirement, it needs its own architecture decision before Network Model's cut-set-resolution contract can support it; this document does not invent that mechanism.

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

**How a `Circuit`-level assignment becomes a `cut_set` (ADR-007, §9 rule 11):** `analyzeIsland`'s `cut_set` parameter remains, unchanged, a list of native `topology_branch_id`/`topology_transformer_id` elements — Network Model's own interface is not modified by Equipment Registry's existence. The translation from "the scheme designer selected `Circuit` PKLG–IGBK Line 1" to that native element list happens **upstream of this interface**, in PSS/E Integration's own `Circuit`-resolution interface ([psse-integration-module.md](psse-integration-module.md) §13, §8a), which resolves a `Circuit` to the union of its `CircuitTerminal`s' matched `EquipmentTopologyMap` entries. Whichever module orchestrates a scheme's Draft/Under-Review recommendation flow (today, this would be the scheme module itself; a shared orchestration helper may emerge once more than one scheme module needs this, per CLAUDE.md §21) is responsible for that upstream resolution call before invoking `analyzeIsland` — Network Model does not perform it and does not need to know a `Circuit` exists.

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

1. **Business rule tests** — determinism (same triple + algorithm version always yields the same result); immutability of `IslandAnalysisResult`; correct single-Active-override enforcement and supersession; a structural/architectural test confirming no Network Model table has a foreign key into any scheme module's schema (§9, rule 8) — unweakened by rule 11's `Circuit`-resolution note, since that resolution happens entirely upstream, in PSS/E Integration, before Network Model's own interface is ever called (§13). `EquipmentTopologyMap` matching/classification correctness is PSS/E Integration's own testing responsibility (psse-integration-module.md §16), not retested here.
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
- **Per-terminal-subset `Circuit` assignment** — today, a `Circuit`-level assignment always resolves to the union of *all* its `CircuitTerminal`s (§9 rule 11); supporting a scheme assignment against a *subset* of a tee-off `Circuit`'s terminals is an open question (ADR-007 Open Question 1) with no defined mechanism yet — ADR-level work, not a Network Model implementation detail.
- **Direct `CutSetDefinition` reference to `Circuit`/`CircuitTerminal`** (superseded framing) — an earlier version of this document speculated that `CutSetDefinition` elements might eventually reference "formal equipment records... in addition to PSS/E-native topology elements." ADR-006/ADR-007 have since settled this: `CutSetDefinition` remains PSS/E-native only; `Circuit`-level resolution happens upstream, via PSS/E Integration's `EquipmentTopologyMap` (§9 rule 11, §13). This bullet is retained only to record that the earlier framing is superseded, not as a live option.

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
| A `Circuit`-level assignment's cut-set resolution (§9 rule 11) depends on PSS/E Integration's `EquipmentTopologyMap`, which does not exist yet | Until it is built, a scheme module cannot cleanly go from "assign to Circuit PKLG–IGBK Line 1" to a computed pocket without an engineer manually cross-referencing PSS/E element ids by hand | Sequence `EquipmentTopologyMap` explicitly as part of Phase 4 (see [implementation-plan.md](implementation-plan.md)), not left as an open-ended future extension — mirrors ADR-006 §12's identical risk/mitigation |
| Tee-off `Circuit` per-terminal-subset assignment (§17) remains an open architectural question | A scheme module cannot today express "open only one leg of a three-way tee," which may understate what the model can represent for a real tee-off network configuration | Treat as an explicit open item requiring its own decision before being needed (ADR-007 Open Question 1) — do not silently assume whole-`Circuit`-only resolution is permanently sufficient |

---

## 19. Phase 5 Addendum — The Static Network Model (As Built)

This section documents the module actually implemented in Phase 5, per the reconciliation note above. It is additive: it does not modify §1–§18.

### 19.1 Purpose and Scope

The static Network Model answers "how is the transmission network electrically connected" using only data that already exists in Substation Registry and Equipment Registry — no PSS/E import, no engineering calculation, no scheme awareness. It is the software-side Line Connectivity Registry described by the Engineering Reference Library ([`docs/engineering/02-engineering-concepts.md`](../engineering/02-engineering-concepts.md), [`docs/engineering/04-domain-model.md`](../engineering/04-domain-model.md)).

### 19.2 Owned Entities

None. This module owns no database tables and required no migration. Every query it runs reads Substation Registry's `Substation`, Equipment Registry's `SubstationVoltageYard`/`Circuit`/`CircuitTerminal`/`Transformer`/`TransformerTerminal`, and (Phase 7E) PSS/E Integration's `TopologyVersion`/`TopologyBus`/`TopologyBranch`/`TopologyTransformer`/`LoadSnapshot`/`LoadSnapshotElementState`/`EquipmentTopologyMap` models directly, read-only — the same cross-module read-only-model-import pattern PSS/E Integration's own repository already established for the same kind of composition (CLAUDE.md A1's reporting/query-optimisation exception), now extended to a second module.

### 19.3 Engineering Relationships (Domain Model)

```
Substation (Substation Registry, external, read-only)
Circuit / CircuitTerminal (Equipment Registry, external, read-only)
Transformer / TransformerTerminal (Equipment Registry, external, read-only)
        │
        ▼
SubstationConnectivity — one substation's connected lines and neighbouring substations,
                         derived by grouping that substation's active CircuitTerminals by circuit_id
        │
        ├── ConnectingLine (one per Circuit; is_tee_off = more than two terminals)
        │        └── TerminalOnCircuit (one per CircuitTerminal on that Circuit)
        │
        └── NeighbourSubstation (one per other-substation terminal, per connecting line)

ElectricalNeighbour — SubstationConnectivity.neighbours, deduplicated to one row
                      per distinct neighbouring substation

SubstationEquipment — one substation's TransformerBay and LineBay lists, grouped by
                      engineering function

NetworkOverview — registry-wide counts (substations, circuits, tee-off circuits, transformers)

TopologyBus / TopologyBranch / TopologyTransformer (PSS/E Integration, external, read-only,
                                                     Phase 7E)
        │
        ▼
TraversalResult — breadth-first reachability from a starting substation, over an
                  adjacency map built from the Current (or explicitly requested)
                  Operational Snapshot's Bus/Branch/Transformer graph — never from
                  Circuit/CircuitTerminal (Phase 7E; see §19.4, §19.9)
```

Every shape above is a DTO (`app/modules/network_model/schemas.py`), never a persistence row — consistent with CLAUDE.md A6 and the Engineering Reference Library's own framing of these as engineering relationships, not database tables.

**Tee-off / multi-terminal handling:** a `Circuit` with more than two active `CircuitTerminal` rows is a tee-off. It is modelled as one multi-way connection — all of its terminal substations are mutually adjacent to each other through it — never as a chain of pairwise edges, and never assumed to have exactly two terminals anywhere in this module's code or tests.

**Transformers never span substations** (ADR-008's UAT correction: both a `Transformer`'s `TransformerTerminal` rows resolve to the same `substation_id`). Only `Circuit`/`CircuitTerminal` model inter-substation connectivity; this module's traversal graph is built exclusively from circuit terminals.

### 19.4 Traversal Philosophy

`traverse(start_substation_id, excluded_circuit_ids, max_depth, topology_version_id)` is a **generic, parameterised reachability primitive**, not an island-detection or load-pocket feature. It answers only "which substations are reachable from here, given these specific lines are treated as open" — deliberately the same shape of question a future load-pocket, boundary, or visualization capability would need answered, without this phase building any of those capabilities itself (explicitly out of scope). It performs no automatic topology analysis: it never decides on its own which lines to exclude, never classifies a result as an "island" or "pocket," and never persists a result — every call is a fresh, stateless query.

**Phase 7E — graph source.** The connectivity graph itself is built exclusively from the Operational Snapshot (`TopologyBus`/`TopologyBranch`/`TopologyTransformer`, ADR-003) for one specific `TopologyVersion` — the Current one if `topology_version_id` is omitted, or the explicitly named one otherwise (Snapshot Awareness — never silently mixes two snapshots in one call). Bus Number is the traversal node identity internally, exactly as the Operational Snapshot itself defines it; Substation is resolved only at the two edges of a call — the starting Substation is seeded from every Bus currently correlated to it (a multi-voltage Substation may have more than one), and each reached Bus is mapped back to its own correlated Substation, if any, purely for the response's substation-shaped output. A Bus with no correlated Substation (Fictitious, Blank-named, or simply not yet matched) still participates fully in the graph — it contributes edges like any other Bus — it is only absent from the *output*, never treated as a reason to stop or fail. `excluded_circuit_ids` remains a Registry-facing convenience: it is translated, per call, into whichever Operational Branch/Transformer elements that Circuit currently correlates to (via `EquipmentTopologyMap`, for the `TopologyVersion` being traversed) — a Circuit with no correlation for that snapshot excludes nothing, gracefully, never an error. Branch/Transformer in-service state (`LoadSnapshotElementState`, from the topology's own Current `LoadSnapshot`) is respected — an out-of-service element contributes no edge — with an element that has no recorded state at all defaulting to in-service (the same "unknown, not invalid" tolerance §19.5 already establishes, applied here to Operational Snapshot state).

**What did not change:** the request/response shape remains substation-in/substation-out; `SubstationConnectivity`/`SubstationEquipment`/`ElectricalNeighbour`/`NetworkOverview` remain entirely Registry-sourced (see the Phase 7E reconciliation note above); no island/pocket/boundary analysis was added; existing callers (the frontend's Network Traversal page) required no changes. See §19.9 for the full migration record, including why this was judged the correct, minimal-impact design.

### 19.5 Incomplete-Registry Tolerance

The transmission network is expected to be registered incrementally. This module never assumes registry completeness:

- A named-but-nonexistent substation is a 404 (`SubstationNotFoundError`) for the one request that named it — never for its *absence* from someone else's result.
- A registered substation with no circuits or transformers yet entered returns empty connectivity/equipment lists — a valid state, not an error.
- Any reference this module cannot currently resolve (e.g. a terminal whose substation lookup fails) is treated as unknown and omitted from output, never raised as an error. Database-level referential integrity (NOT NULL + FK RESTRICT) means this should not occur for real data, but the service does not depend on that assumption to avoid crashing.
- `GET /network-model/overview` against an empty (or freshly-seeded) registry returns all-zero counts, not an error.

### 19.6 Service Interfaces (API)

All read-only, gated only by authentication (mirrors Equipment Registry's and Substation Registry's own precedent for engineering reference data — CLAUDE.md A10's "sensitive by default" is satisfied by requiring authentication; no finer-grained permission currently gates any of these reads). `network_model.read` is registered in IAM's permission catalog (`bootstrap.py`) for possible future finer-grained use, granted to all three baseline roles, exactly as Equipment Registry's own `*.read` permission is.

- `GET /network-model/overview` → `NetworkOverview`
- `GET /network-model/substations/{substation_id}/connectivity` → `SubstationConnectivity`
- `GET /network-model/substations/{substation_id}/equipment` → `SubstationEquipment`
- `GET /network-model/substations/{substation_id}/neighbours` → `list[ElectricalNeighbour]`
- `POST /network-model/traverse` → `TraversalResult` (POST because it accepts a request body: `start_substation_id`, `excluded_circuit_ids`, `max_depth`, `topology_version_id` [Phase 7E, optional])

### 19.7 Future Extension Points

- ~~**Foundation for the reconciliation proposal in the note above**~~ — **done, Phase 7E**: `traverse` now builds its graph from PSS/E Integration's Operational Snapshot, correlated back to Substation Registry via `TopologyBus.substation_id` and to Equipment Registry via `EquipmentTopologyMap` (for `excluded_circuit_ids` translation only). `SubstationConnectivity`/`SubstationEquipment`/`ElectricalNeighbour` remain Registry-sourced (§19.9) — extending them the same way remains a future, separately-decided extension, not implied by this one.
- **Load pocket / boundary identification** — would consume `traverse` as a primitive (supplying a candidate `excluded_circuit_ids` boundary and inspecting the resulting reachable set), not by extending this module's own scope. Now inherits Phase 7E's Operational Snapshot accuracy for free.
- **Network visualization** — a future frontend or Dashboard capability can render `SubstationConnectivity`/`NetworkOverview` output directly; this module never renders anything itself (CLAUDE.md A12).
- **Graceful growth** — no change is required as the registry (or the Operational Snapshot) grows; every query already operates over "whatever is currently registered/imported," per §19.5.
- **Bus-level Correlated Operational Model views** (Phase 7C, `psse_integration`'s own `OperationalBusView`/`OperationalBranchView`/`OperationalTransformerView`/`OperationalLoadView`) remain a separate, lower-level surface than this module's substation-shaped traversal — a future capability needing Bus-level detail (not just substation reachability) should consume those directly, not by extending `traverse`'s own response shape. See §19.10 for how this relates to Operational Projections generally, including the not-yet-implemented Switchyard-level projection.

### 19.8 Testing

Comprehensive backend tests exist at `app/modules/network_model/tests/` (service-layer: connectivity, tee-off/multi-terminal, neighbours, equipment, overview — all Registry-sourced and unchanged by Phase 7E; traversal — now Operational-Snapshot-sourced, covering reachability, `excluded_circuit_ids` correlation translation including the "uncorrelated Circuit excludes nothing" case, `max_depth`, `ENTERED_IN_ERROR` Registry/traversal independence, zero-Line-Connectivity-Registry-data, Fictitious Bus traversal, Split Switchyard non-collapsing, disconnected islands, Branch in-service state, Transformer voltage-level crossing, explicit/Current `topology_version_id` selection, and `NoCurrentTopologyVersionError`/`TopologyVersionNotFoundError`; bootstrap) and `backend/tests/test_network_model_api.py` (authentication, open-read authorization, full read flow including a real committed/activated Operational Snapshot, 404/400 handling for traversal's own new failure modes). See the Phase 5 implementation report and the Phase 7E implementation report for the full test summaries.

### 19.9 Phase 7E — Operational Snapshot Traversal Migration

**Objective:** change `traverse`'s authoritative topology source from Line Connectivity Registry (`Circuit`/`CircuitTerminal`) to Operational Snapshot (`TopologyBus`/`TopologyBranch`/`TopologyTransformer`, ADR-003) — a change of *where the graph comes from*, not of what engineering question `traverse` answers or what its callers receive.

**Why the public API stayed (almost entirely) stable.** `traverse`'s callers — today, only the frontend's Network Traversal page — think in terms of Substations, not Buses: "what is reachable from this substation." Operational Snapshot, correlated via EDR-007, is Bus-native: a Substation may correlate to zero, one, or several Buses (a multi-voltage Substation has one Bus per Switchyard), and not every Bus correlates to a Substation at all (Fictitious, Blank-named, or simply unmatched Buses). Rather than push this Bus/Substation distinction onto every caller, the migration keeps the request/response shape substation-in/substation-out: `start_substation_id` is resolved internally to every Bus currently correlated to it (multi-source seed, all at depth 0 — a multi-voltage Substation's own Buses are collectively "itself"), and each *reached* Bus is mapped back to its own correlated Substation, if any, only at the point of building the response. A Bus with no correlated Substation still fully participates in the graph (it is a real electrical path, per EDR-007's Fictitious Bus conclusions) — it is simply invisible at the substation-shaped output layer, exactly as a Fictitious Bus's "no Engineering Registry object" fact would predict.

**The one unavoidable, additive API change: Snapshot Awareness.** A registry-only graph has no notion of "which snapshot" — it was always simply "the current registry state." An Operational Snapshot graph must specify *which* `TopologyVersion` (there can be many, only one Current). `TraversalRequest` therefore gained one new, optional field (`topology_version_id`, defaulting to Current) and `TraversalResult` gained one new, always-populated field (`topology_version_id`, reporting which snapshot was actually traversed) — additive, non-breaking for any caller that does not set or read it, and the only field-level change this migration required.

**`excluded_circuit_ids` — kept, reinterpreted, never broken.** This parameter is inherently Registry-facing (a Circuit is what a user names when they mean "this physical line"). It is translated, internally, into whichever Operational Branch/Transformer elements that Circuit currently correlates to for the `TopologyVersion` being traversed, via the already-existing `EquipmentTopologyMap` (Phase 4/6, ADR-006). A Circuit with no correlation for that snapshot (never imported against it, or its correlation is itself ambiguous/unmatched) excludes nothing — gracefully, never an error — satisfying the explicit requirement that traversal must still function with no Line Connectivity metadata, or no correlation, at all.

**Branch/Transformer in-service state — new, and intentional.** Line Connectivity Registry's `Circuit` has no notion of "in service" (only an administrative `operational_status_id` — ACTIVE/MOTHBALLED/etc., a Registry lifecycle concept, not an electrical one). Operational Snapshot's `LoadSnapshotElementState.in_service` does carry this fact. `traverse` now respects it: an out-of-service Branch/Transformer contributes no edge. This is a genuine, deliberate behavioural addition (not merely a data-source swap) — required explicitly by this phase's own "Branch Traversal" requirement — and is a strictly more electrically accurate answer to "how is the network connected right now" than the pre-migration graph could ever give, since Registry status was never a reliable proxy for in-service state.

**A genuine, documented decoupling: Registry `ENTERED_IN_ERROR` no longer implies traversal exclusion.** Before this migration, a Circuit's Registry status had no traversal effect at all (traversal only ever read `CircuitTerminal`s, filtered by status, at graph-build time) — so this is not a regression, but it is worth stating plainly now that the two are visibly, architecturally separate: correcting a Circuit's Registry record (e.g. marking it `ENTERED_IN_ERROR`) removes it from `SubstationConnectivity` (Registry-sourced, unaffected by this migration) but has **no automatic effect** on the Operational Branch's own traversability — the physical line the Operational Snapshot describes may still be there and in service, independent of a Registry correction. To actually exclude an operational line, `excluded_circuit_ids` (or, in the future, direct Operational Snapshot state) must be used explicitly. This is the direct, intended consequence of "Traversal itself must never depend upon registry metadata."

**What was deliberately not migrated.** `SubstationConnectivity`, `SubstationEquipment`, and `ElectricalNeighbour` remain entirely Equipment/Substation-Registry-sourced. They describe *registered* equipment identity and metadata (breaker numbers, bay numbers, circuit names, tee-off structure as registered) that exists only in the Registry — Operational Snapshot has no equivalent facts to source them from, so there was no "topology source" to swap for these three. `NetworkOverview`'s counts likewise remain Registry-derived (substation/circuit/transformer counts as *registered*, not as operationally present) — deliberately out of this migration's scope, since it answers a Registry-completeness question, not a connectivity question.

### 19.10 Operational Projections — Bus, Switchyard, and Substation Presentation

A manual UAT of Network Traversal (post-Phase 7E) found the substation-shaped output — correct, and confirmed correct by direct reproduction against real data — nonetheless engineering-counterintuitive in cases where the Operational Bus graph passes through a long chain of real, correctly-classified switchyard buses that have no Substation Registry correlation (EDR-007 §4.4 Switchyard Bus, §4.6 Fictitious Bus). This section records the resulting architectural clarification. It documents a concept; it does not change `traverse`'s behaviour.

**Bus-level BFS remains the authoritative computation.** Nothing in this section revises §19.4: Bus Number is, and remains, the traversal node identity; the graph is, and remains, built exclusively from the Operational Snapshot (`TopologyBus`/`TopologyBranch`/`TopologyTransformer`) for one `TopologyVersion`. A "hop" is, and remains, one edge between two Operational Buses — never a Substation-to-Substation or Circuit-to-Circuit unit of distance. This computation is not in question and is not proposed to change.

**The result is one Correlated Operational Model output, which may be projected at more than one granularity** (`operational-correlation-architecture.md` §4.2, Operational Projections):

- **Bus-level view** — the raw BFS result: every reached Bus and its bus-hop depth. This is the traversal's own native shape.
- **Switchyard-level view** — reached Buses grouped by Operational Switchyard (`operational-correlation-architecture.md` §4.1), showing which of a Substation's voltage levels were reached, and at what bus-hop depth, without collapsing intermediate unregistered switchyard buses out of the picture entirely.
- **Substation-level summary** — the current, already-implemented projection: reached Buses reduced to their correlated Substation by minimum depth. This remains a legitimate, useful projection for engineers who want the coarse view — it is not deprecated by this section.

These three are views over the same one BFS result, not three different computations that could disagree with one another (`operational-correlation-architecture.md` §4.2). None of them is a new source of truth, and producing more than one of them from a single `traverse` call would not duplicate the Operational Snapshot or the Engineering Registry.

**Current state.** The implemented API and the frontend's Network Traversal page expose only the substation-level projection today (`TraversalResult.reachable_substations`). This is a known, deliberate scope boundary of the Phase 7E migration (§19.4, §19.9) — not an oversight this section corrects, and not a defect this section reports. Bus-level detail already exists as a separate, lower-level surface (§19.7 — `OperationalBusView` and its siblings); a Switchyard-level projection does not yet exist anywhere in the implementation.

**Guidance for future UX work.** Whenever bus-hop depth is shown to an engineer — today or in any future projection — it must not be presented, worded, or visually implied as substation-hop or line-hop distance. A reported depth of "11" is only meaningful once it is clear which graph it was measured over; conflating the two units is what made the UAT's correct result read as anomalous. This is a presentation caution for future design work, not an implementation prescription — this document does not specify how, or whether, a Switchyard-level or richer Bus-level projection should be built into `traverse`'s response shape, only that doing so would be a legitimate, additive extension of an existing, correctly-scoped computation, not a departure from it.

---

## Recommended Next Architecture Document

**UFLS module refinement.**

[ufls-module.md](ufls-module.md) §7.4 (Assignment Model) currently models a UFLS assignment as a simple substation + MW pair with a free-text feeder identifier, and its §7.5 (Load MW Treatment) predates both [psse-integration-module.md](psse-integration-module.md)'s recommended-MW service interface and this document's pocket/island analysis interface. Both interfaces now exist and are stable enough to design against. Refining UFLS to properly model pocket-based assignments (consuming `IslandAnalysisResult`/`ManualOverride` via Network Model's service interface, and direct transformer-bay assignments consuming PSS/E Integration's recommended-MW interface) closes the gap the Codebase Discovery Report flagged as UFLS's most significant missing capability relative to the legacy MVP, and gives UVLS/EMLS a complete, validated template to follow rather than a partial one.

**Cross-Scheme Compliance module** remains the single highest-severity *open* architectural risk from the discovery report (the tension between per-module bounded contexts and Rule 1/2's need to check across UFLS/UVLS/EMLS) and should not be deferred indefinitely — but it is independent of Network Model's design and can be sequenced either immediately after UFLS's refinement or in parallel with it.

**Equipment Registry** and **Critical Infrastructure** modules remain important but are not blocked by, or blocking, this document, for the same reasons already given in [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md) and [psse-integration-module.md](psse-integration-module.md)'s equivalent recommendations.
