# UFLS Module Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document follows the Canonical Module Architecture Document Template (CLAUDE.md **A8**), which replaces all earlier module documentation checklists.

Related documents: [system-overview.md](system-overview.md), [domain-model.md](domain-model.md), [substation-registry.md](substation-registry.md), [psse-integration-module.md](psse-integration-module.md), [network-model-module.md](network-model-module.md), [ADR-000](../adr/ADR-000-architecture-principles.md), [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md), [ADR-002](../adr/ADR-002-identity-and-access-management.md), [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md).

> Numeric examples in this document (frequency thresholds, time delays, MW figures) are **illustrative only**. Actual values are engineering policy data, stored and versioned in the database per CLAUDE.md **A7** — never hardcoded, and not asserted here as real grid code figures.

> **Revision note:** this is a substantial upgrade of the original UFLS design, informed by the Codebase Discovery Report for the legacy MVP and by the now-stable [PSS/E Integration](psse-integration-module.md) and [Network Model](network-model-module.md) module designs. The original design's core lifecycle and ownership principles are preserved; the assignment model, MW treatment, and cross-module integration points are substantially expanded. See the closing summary for what was preserved, redesigned, and discarded.

> **Implementation status:** UFLS is now implemented. [ufls-architecture.md](ufls-architecture.md) is the authoritative as-built module architecture document (CLAUDE.md A8 template) — it supersedes this document's §7/§8 exactly as described below, and additionally documents the concrete Shared Defence-Scheme Platform composition, database design, API contract, and test coverage that did not exist when this document was written. This document remains the authoritative pre-implementation source for everything §7/§8 do not cover (§1-6, §9 minus lifecycle, §10, §12-18).

> **Status update (Engineering Scheme Architecture Pack, six-workshop conclusions).** §7 (Domain Model — assignment model, MW treatment) and §8 (Lifecycle/State Model) below are **superseded**, not rewritten. `UflsSchemeVersion`'s lifecycle is now `Draft → Published → Superseded | Entered in Error` ([ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md), [EDR-009](../engineering/edr/EDR-009-grid-defence-scheme-lifecycle-realignment.md)), not the six-state Canonical Version Lifecycle described below. Stage threshold/order/delay fields are now owned by a separate, reusable Stage Setting Set ([stage-setting-set-architecture.md](stage-setting-set-architecture.md), [ADR-016](../adr/ADR-016-stage-setting-set-as-reusable-versioned-entity.md)), not embedded directly on `UflsStage` as §7.1–§7.3/§11 describe. Pocket assignment now resolves opening points via `CircuitTerminal` selection and Network Model's `traverse` primitive ([boundary-pocket-architecture.md](boundary-pocket-architecture.md), [ADR-017](../adr/ADR-017-boundary-pocket-assignment-architecture.md)), not `analyzeIsland`/`IslandAnalysisResult`/`ManualOverride` as §7.5 describes. `equipment_reference`'s Open Questions 1–2 are resolved — Equipment Registry now exists; a direct assignment references `transformer_terminal_id` directly ([shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §3.1). Cross-Scheme Compliance's `getProtectedAssignments`-consuming gate (§13, §17) is now [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md), gated once at Publish, not at separate Approval/Activation checkpoints. See [ufls-engineering-philosophy.md](ufls-engineering-philosophy.md) for what remains genuinely UFLS-specific under the new model. §1–§6, §9 (minus lifecycle-specific rules), §10, §12–§18 below remain the authoritative source for UFLS's ownership, non-responsibilities, referenced entities, Rule 3/4-equivalents, security, and testing priorities, and are **not** superseded by this update.

---

## 1. Module Overview

Under Frequency Load Shedding (UFLS) is a Defence Scheme module: it is the engineering system of record for the design, approval, versioning, and audit of the UFLS scheme protecting Peninsular Malaysia's transmission grid against under-frequency collapse.

UFLS defines, in successive **stages**, how much load is shed and where, as system frequency falls below defined thresholds — either by directly assigning specific substations, or by defining a topology-derived **pocket** (an electrical island) to be shed as a unit. This module owns the *engineering design* of that scheme — scheme identity, versions, stages, thresholds, and both kinds of assignment — as a versioned, auditable record. It does not own the substations it assigns load to (Substation Registry), the network topology or load data used to compute recommendations (PSS/E Integration), the island/connectivity analysis behind pocket assignments (Network Model), or real-time relay tripping (out of scope, §4).

---

## 2. Purpose

To provide a single, versioned, auditable source of truth for the UFLS scheme's engineering design, so that:

- Every UFLS scheme version that has ever been in force is permanently reconstructable (CLAUDE.md §5.2, Immutable Engineering History).
- Every assignment — direct or pocket-based — is traceable to a specific, approved scheme version, and to the network data that informed it, without that traceability ever becoming a live dependency capable of changing an approved figure.
- Exactly one UFLS scheme version governs the live grid at any moment (CLAUDE.md A3).
- Engineers designing a version get accurate, current recommended MW figures from PSS/E Integration and Network Model, while the version remains in Draft/Under Review — without those figures ever being mistaken for approved data.
- Downstream consumers (protection engineers deploying relay settings, auditors, future simulation tooling, a future Cross-Scheme Compliance capability) can retrieve the authoritative current or historical UFLS design without ambiguity, and without needing direct access to UFLS's tables.

---

## 3. Responsibilities

UFLS owns:

- ✓ UFLS scheme identity (`UflsScheme` — the stable anchor a sequence of versions belongs to)
- ✓ UFLS scheme versions and their lifecycle
- ✓ UFLS stages, and their frequency thresholds and time delays
- ✓ Direct (substation-level) assignments
- ✓ Pocket/island-based assignments
- ✓ Approved MW values, once captured
- ✓ Human-entered change reasons
- ✓ Its own audit trail (`ufls_audit_log`, per CLAUDE.md A4)

(This mirrors and extends the ownership example already given in CLAUDE.md §8.)

---

## 4. Non-Responsibilities

UFLS does **not** own:

- ✗ Substation name, mnemonic, voltage level, region, state, owner, or coordinates — owned by the Substation Registry (CLAUDE.md §8). UFLS references a substation only by `substation_id`.
- ✗ Topology structure or load/generation data — owned by [PSS/E Integration](psse-integration-module.md). UFLS references a `LoadSnapshot` only as a traceability pointer (§9).
- ✗ Connectivity graph construction or island/pocket detection — owned by [Network Model](network-model-module.md). UFLS references an `IslandAnalysisResult`/`ManualOverride` only as a traceability pointer (§9).
- ✗ Physical equipment/relay master data — reserved for a future Equipment Registry. UFLS may hold a temporary, clearly-labeled free-text placeholder pending that module (§7.4, Open Question 1/2).
- ✗ Identity, authentication, roles, or permissions — owned by IAM (Core Platform domain, [ADR-002](../adr/ADR-002-identity-and-access-management.md)). UFLS references actors only by `user_id`.
- ✗ Real-time relay execution, SCADA control, or field device communication. UFLS is the engineering **design and record of intent** for the scheme; deploying that design onto physical protection relays is a separate, out-of-scope operational process.
- ✗ Real-time frequency telemetry or measurement — a future SCADA/EMS integration concern (CLAUDE.md §27).
- ✗ UVLS or EMLS data, business rules, or assignments — each is its own independent bounded context.
- ✗ Cross-scheme compliance logic (checking UFLS against UVLS/EMLS) and critical-substation protection logic — these require a future Cross-Scheme Compliance capability and Critical Infrastructure module respectively. UFLS exposes what those capabilities need via a read-only service interface (§13) without owning the cross-checking logic itself.
- ✗ Centralized audit storage — UFLS audits only its own records (CLAUDE.md A4).

---

## 5. Owned Entities

| Entity | Description |
|---|---|
| `UflsScheme` | The stable identity a UFLS scheme's versions belong to (e.g. "Peninsular Malaysia UFLS Scheme"). Rarely changes; exists so "only one Active version" is scoped correctly even if GridDefence ever needs more than one distinct UFLS scheme (e.g. a future separate regional scheme) without a discriminator-flag workaround. |
| `UflsSchemeVersion` | The versioned aggregate root: one complete, coherent UFLS scheme design as of a point in time, belonging to exactly one `UflsScheme`. |
| `UflsStage` | One frequency-triggered shedding stage within a scheme version, including its own `is_protected` classification (§7.1) consumed by `getProtectedAssignments()` (§13). |
| `UflsLoadBlock` | A named quantum of load defined within a stage, grouping one or more direct assignments. |
| `UflsDirectAssignment` | A direct, substation-level assignment within a load block — the equivalent of the legacy MVP's transformer-bay assignment, before Equipment Registry exists (§7.4). |
| `UflsPocketAssignment` | A topology-derived (island/"pocket") assignment within a stage, referencing a Network Model analysis result. |
| `UflsPocketAssignmentSubstation` | Normalized child of `UflsPocketAssignment` — the captured substation set and per-substation MW for a pocket. |
| `UflsChangeReason` | A curated, human-entered explanation of one changed assignment (new/revised/removed) relative to a comparison version, required before a version leaves Draft (§7.6). |
| `ufls_audit_log` | UFLS's own audit trail (CLAUDE.md A4), covering all owned entities above. |

---

## 6. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| Substation | Master Data (Substation Registry) | `substation_id` (UUID) only — no attributes copied |
| `TopologyVersion`, `LoadSnapshot` | PSS/E Integration | `source_load_snapshot_id` — traceability pointer only, never a live dependency (§9) |
| `IslandAnalysisResult`, `ManualOverride` | Network Model | `source_analysis_result_id`, `source_override_id` — traceability pointers only, never a live dependency (§9) |
| Operational Status, Voltage Level, Region, State, Grid Owner | Core Platform (reference data) | Not referenced directly except `grid_owner`, read via Substation Registry's service interface for Rule 4-equivalent validation (§9) |
| User | Core Platform (IAM) | `user_id` (UUID) only, for `created_by_user_id`, `updated_by_user_id`, `approved_by_user_id`, `activated_by_user_id`, and change-reason/audit attribution; fallback `external_principal_id` + provider per [ADR-002](../adr/ADR-002-identity-and-access-management.md) |
| Role / Permission | Core Platform (IAM) | Not referenced by foreign key; authorization checks are performed by calling IAM's service layer at request time (CLAUDE.md A1) |

UFLS never stores substation name, mnemonic, voltage, region, state, owner, or coordinates; never stores topology structure or raw load/generation figures; never stores connectivity graph or island-detection logic. All of these are resolved at read time via the owning module's service interface, or (for reporting/dashboards only) a read-only join per CLAUDE.md A1 — never by persisting a copy.

---

## 7. Domain Model

```
UflsScheme (1) ──── (many) UflsSchemeVersion
UflsSchemeVersion (1) ──── (many) UflsStage
UflsStage (1) ──── (many) UflsLoadBlock ──── (many) UflsDirectAssignment
UflsStage (1) ──── (many) UflsPocketAssignment ──── (many) UflsPocketAssignmentSubstation
UflsSchemeVersion (1) ──── (many) UflsChangeReason

UflsDirectAssignment           ──── references ───▶ Substation.substation_id        (Master Data, external)
UflsPocketAssignmentSubstation ──── references ───▶ Substation.substation_id        (Master Data, external)
UflsDirectAssignment           ──── traceability ─▶ LoadSnapshot.load_snapshot_id    (PSS/E Integration, external, optional)
UflsPocketAssignment           ──── traceability ─▶ IslandAnalysisResult.analysis_result_id,
                                                     ManualOverride.override_id      (Network Model, external, optional)
UflsSchemeVersion / UflsStage / assignments / change reasons
                                ──── references ───▶ User.user_id                   (Core Platform/IAM, external)
```

A `UflsSchemeVersion` is the unit of approval and activation. Editing, reviewing, approving, and activating always happen at the version level — no child entity is independently versioned; it only exists within the version that owns it. **Traceability pointers to PSS/E Integration and Network Model are descriptive metadata, never live foreign keys that an approved figure continues to track** (§9) — this is the structural mechanism that satisfies "no silent updates to Approved/Active versions."

### 7.1 UFLS Stages

A **Stage** represents one frequency-triggered shedding event within a scheme version. Each stage has an explicit `stage_order` (ascending), a frequency threshold, and a time delay (§7.2, §7.3), and may contain any mix of direct assignments (grouped in load blocks) and pocket assignments.

Each stage also carries an `is_protected` flag — ordinary engineering policy configuration, owned and set by UFLS as its own business data, marking whether this stage's assignments should be treated as protected for cross-scheme conflict purposes. This is the field `getProtectedAssignments()` (§13) reads to classify each returned assignment; it exists so that Cross-Scheme Compliance can evaluate Rule 1 without UFLS ever needing to know that UVLS, EMLS, or any other scheme exists (§9, rules 15–16).

### 7.2 Frequency Thresholds

Unchanged from the original design: each stage carries a `frequency_threshold_hz` value, stored as versioned engineering parameter data (CLAUDE.md A7). Within a version, thresholds must be unique and strictly decreasing as `stage_order` increases (§9).

### 7.3 Time Delays

Unchanged: each stage carries a `time_delay_ms` value (≥ 0), stored per stage.

### 7.4 Direct Assignment Model

A **Direct Assignment** links a substation to a load block, representing "all UFLS-relevant load shed at this substation for this block" — the equivalent of the legacy MVP's transformer-bay assignment.

**Open Question 1 — how to represent direct assignments before Equipment Registry exists:** a direct assignment references `substation_id` only (Master Data). There is no equipment-level (transformer/breaker) granularity yet, because no Equipment Registry exists. UFLS may store a free-text `equipment_reference` field (e.g. a feeder or breaker identifier) as its own, clearly-labeled, **temporary placeholder** — explicitly permitted by this module's scope (§4) as a deferred concern, not a claim of equipment ownership.

**Open Question 2 — how to represent equipment-level assignments once Equipment Registry exists:** when a future Equipment Registry module is built, a migration should add a nullable `equipment_id` foreign key to `UflsDirectAssignment`, and a data migration should attempt to resolve existing `equipment_reference` free-text values against the new registry (flagging unresolved ones for manual reconciliation, mirroring the "unmatched" reporting pattern already established in [psse-integration-module.md](psse-integration-module.md)). The free-text field is retained afterward as a legacy/fallback display value, not removed outright, to avoid losing historical assignments' original recorded intent. This is deliberately **not** designed further today — introducing a speculative `equipment_id` column against a module that doesn't exist yet would be premature abstraction (CLAUDE.md §26).

### 7.5 Pocket/Island Assignment Model

A **Pocket Assignment** represents a topology-derived shedding group: "if these boundary branches were opened, this set of substations becomes isolated and is shed as a unit." It belongs directly to a `UflsStage` (not a load block — the pocket's substation set is already the natural grouping unit).

A pocket assignment is built by calling Network Model's `analyzeIsland(...)` service interface (during Draft/Under Review) to obtain a candidate isolated substation set and its aggregate recommended MW, optionally refined by a `ManualOverride` an engineer has created against that result (per [network-model-module.md](network-model-module.md) §13). UFLS stores:
- `source_analysis_result_id` — always, a traceability pointer to the `IslandAnalysisResult` that was used.
- `source_override_id` — only if a `ManualOverride` was applied instead of the raw computed result.
- The captured substation set and per-substation MW (`UflsPocketAssignmentSubstation` rows), once Approved (§7.6).

**Open Question 4 — how pocket assignments store traceability to Network Model:** exactly as above — a pointer to the specific `analysis_result_id` (and `override_id`, if applicable) used at capture time. UFLS does not separately store `load_snapshot_id`/`topology_version_id` for pocket assignments, since `IslandAnalysisResult` already records both — tracing further back is a one-hop lookup into Network Model, avoiding redundant duplication of the same fact in two modules.

### 7.6 Load MW Treatment — Recommended vs. Approved

**Open Question 6 — how Draft/Under Review recommended MW differs from Approved MW:**

- **While a version is Draft or Under Review**, MW is never stored in UFLS's own tables. It is resolved **live**, on demand, by calling PSS/E Integration's recommended-MW interface (for direct assignments) or Network Model's `analyzeIsland`/`getEffectiveIsland` interface (for pocket assignments) against the Current `LoadSnapshot`. This value is displayed as a **recommendation** — advisory, not persisted, not authoritative (CLAUDE.md A12 — this is exactly the boundary between a backend-owned recommendation and a frontend-owned display, and it applies equally to a Draft-time recommendation resolved by one backend module for another).
- **At the moment a version transitions Under Review → Approved**, the recommended value for every assignment is resolved one final time and captured into that assignment's own `approved_mw` field (an engineer may adjust the figure at this point, reflecting engineering judgment — the captured value is what gets stored, whether it matches the raw recommendation exactly or not). From this point on, `approved_mw` is immutable (CLAUDE.md §5.2), and the traceability pointer (`source_load_snapshot_id`, `source_analysis_result_id`/`source_override_id`) is fixed alongside it, purely as descriptive metadata.
- **Open Question 3 — how UFLS stores approved MW while retaining traceability:** exactly this split — `approved_mw` (the real, immutable, owned figure) plus a nullable traceability pointer (never a live dependency). A superseded `LoadSnapshot` or a recomputed `IslandAnalysisResult` can never change `approved_mw`, because nothing in UFLS's schema depends on PSS/E Integration's or Network Model's *current* state to resolve it — only the one-time capture event did, and that event is over.

### 7.7 Change Reasons

**Open Question 5 — how human change reasons are modeled:** as a dedicated owned entity, `UflsChangeReason`, not merely a free-text field on the generic audit log. One row per assignment that is new, revised, or removed relative to a designated comparison version (typically the current Active version, mirroring the legacy MVP's pre-publish diff pattern), each requiring a mandatory reason, created before the owning version may leave Draft (§9). This is deliberately richer than the field-level `ufls_audit_log` — it is curated engineering documentation intended for a human reviewer, not a technical change record (see §14 for how the two remain distinct).

---

## 8. Lifecycle / State Model

Every `UflsSchemeVersion` follows the Canonical Version Lifecycle (CLAUDE.md **A3**) without exception:

```
Draft → Under Review → Approved → Active → Superseded → Archived
```

| State | Editable? | Meaning |
|---|---|---|
| Draft | Yes | Being authored; may be freely edited by its owning team. MW is always resolved live as a recommendation (§7.6); no `approved_mw` is set yet. |
| Under Review | Locked except to reviewers/administrators | Submitted for engineering review; content frozen from the drafting team's perspective. `UflsChangeReason` rows must already exist for every changed assignment (§9). |
| Approved | No (immutable) | `approved_mw` is captured for every assignment at the moment this transition occurs (§7.6); reviewed and formally approved; not yet governing the live grid. |
| Active | No (immutable) | The single version currently governing the live grid, for its `UflsScheme`. |
| Superseded | No (immutable) | Was previously Active; replaced by a newer Active version. Remains queryable. |
| Archived | No (immutable) | Retained for long-term historical record. Remains queryable. |

**Module-specific rules, binding for UFLS (elaborating CLAUDE.md A3):**

- **Only one Active `UflsSchemeVersion` may exist per `UflsScheme` at any time.**
- **Activating a new version automatically supersedes the previous Active version of the same `UflsScheme`**, as a single atomic service-layer operation. There is no standalone "deactivate" operation — a version only leaves Active as the direct consequence of another version being activated.
- **Approved and Active versions are immutable.** No stage, assignment, threshold, or MW value may change once a version reaches Approved.
- **Corrections always create a new version** (a new Draft, typically cloned from the version being corrected).
- Both halves of an activation are recorded as a single correlated audit event (§14).

**Open Question 8 — rollback/unpublish vs. forward-only:** the legacy MVP's `unpublish()` (reverting Active → Draft and restoring the previous version) is **not** carried forward as designed, because it contradicts CLAUDE.md §5.2 (Immutable Engineering History) — an "unpublish" implies a version that genuinely governed the grid for a period is retroactively treated as if it hadn't been active, which erodes historical honesty. **Recommendation (not yet adopted — see closing summary):** if an emergency fast-revert capability is operationally required, model it as **reactivating a Superseded version** — i.e., allow `Superseded → Active` as an additional transition, alongside the existing `Approved → Active`. This is not an "undo": the flawed version's history as having been Active remains fully intact and queryable; reactivating an already-approved historical version is simply another forward activation event, auto-superseding the flawed version exactly like any other activation. This preserves forward-only historical integrity while solving the same operational need. Because this amends the Canonical Version Lifecycle itself (CLAUDE.md A3), which governs every versioned module, it cannot be decided unilaterally in this document — it requires its own ADR (see closing summary).

---

## 9. Business Rules

1. Only one `UflsSchemeVersion` may hold status `Active` per `UflsScheme` at any time (§8).
2. Activating a version supersedes the current Active version (of the same `UflsScheme`) automatically and atomically.
3. Approved and Active versions are immutable; any change requires a new version (CLAUDE.md §5.2).
4. Within a scheme version, `stage_order` values are unique and stage `frequency_threshold_hz` values must strictly decrease as `stage_order` increases.
5. A load block belongs to exactly one stage; a direct assignment belongs to exactly one load block and references exactly one substation. A pocket assignment belongs to exactly one stage.
6. A substation may be referenced by multiple direct assignments (across different blocks/stages), and may appear in multiple pocket assignments' substation sets, within the same version.
7. **A substation may not simultaneously be assigned via a direct assignment and appear in any pocket assignment's substation set within the same scheme version.** This is a hard block, always enforced, never configurable — the direct MVP-discovered "Rule 3" equivalent, now correctly recognized as version-internal (not cross-scheme) and therefore fully owned by UFLS itself.
8. **A substation whose Substation Registry `grid_owner` classification is Independent Power Producer or Large Scale Solar (or an equivalent excluded ownership classification) may not be assigned via any direct or pocket assignment.** Hard block, always enforced — the MVP-discovered "Rule 4" equivalent, resolved via a read-only lookup against Substation Registry (§13), not by duplicating ownership data.
9. **Recommended MW (Draft/Under Review) and Approved MW are structurally distinct** (§7.6). No assignment's `approved_mw` is ever set except at the Under Review → Approved transition, and once set, it is never recomputed from PSS/E Integration or Network Model's current state.
10. **A traceability pointer to a `LoadSnapshot`, `IslandAnalysisResult`, or `ManualOverride` is descriptive metadata only.** UFLS's own tables contain no live foreign key whose resolution could change an Approved version's stored MW — this is the structural guarantee behind "no silent updates to Approved/Active versions."
11. Engineering approval actions (Draft → Under Review → Approved, and Approved → Active) require an authenticated, named IAM user (CLAUDE.md A10).
12. New assignments created in a Draft or Under Review version must reference a substation whose current `operational_status` is not Decommissioned or Retired. This restriction does not apply retroactively to already-Approved/Active/Superseded/Archived assignments.
13. Deleting a stage, load block, or assignment is only possible while the owning version is in Draft.
14. A `UflsChangeReason` row is required for every assignment that is new, revised, or removed relative to the version's designated comparison version, before the version may transition Draft → Under Review.
15. UFLS's own tables contain no foreign key into UVLS's, EMLS's, or any future scheme module's schema, and vice versa — cross-scheme concerns are resolved only through service-interface calls (§13), never through direct table coupling.
16. Each `UflsStage` carries its own `is_protected` classification, set by UFLS as ordinary engineering policy configuration — this is UFLS's own business data (§7.1), not a value computed or supplied by Cross-Scheme Compliance or any other module. It is exposed, read-only, through `getProtectedAssignments()` (§13); no other module writes to it.

---

## 10. Validation Rules

- `frequency_threshold_hz` must fall within a policy-defined valid range for a 50 Hz system (the range is engineering parameter data per CLAUDE.md A7).
- `time_delay_ms` must be `>= 0`.
- `stage_order` must be unique within its scheme version; `frequency_threshold_hz` must be unique within its scheme version and strictly decreasing as `stage_order` increases.
- A direct assignment's `substation_id` must reference an existing Substation Registry record.
- A pocket assignment's `source_analysis_result_id` must reference an existing Network Model `IslandAnalysisResult`; `source_override_id`, if present, must reference an `Active` `ManualOverride` against that same result.
- `approved_mw` must be null while a version is Draft or Under Review, and must be non-null (set) for every assignment before a version may transition Under Review → Approved — this is the structural enforcement of §9, rule 9.
- Rule 7 (direct/pocket overlap) and Rule 8 (excluded ownership) are validated at assignment-creation time and re-validated at the Draft → Under Review transition.
- A scheme version cannot be submitted for review with zero stages, or a stage with zero assignments (direct or pocket) across it.
- A `UflsChangeReason` must have a non-empty reason.

---

## 11. Database Design (Concept)

Conceptual only — no migrations are defined here.

| Table (conceptual) | Key columns (conceptual) | Notes |
|---|---|---|
| `ufls_scheme` | `ufls_scheme_id` (UUID PK), `name`, `description`, `created_at` | Stable identity anchor (§5). |
| `ufls_scheme_version` | `ufls_scheme_version_id` (UUID PK), `ufls_scheme_id` (FK), `version_label`, `status`, `compared_to_version_id` (nullable, self-referencing — the version change reasons were diffed against), `superseded_by_version_id` (nullable, self-referencing), `created_by_user_id`, `updated_by_user_id`, `approved_by_user_id` (nullable), `approved_at` (nullable), `activated_by_user_id` (nullable), `activated_at` (nullable), `created_at`, `updated_at` | Only one row per `ufls_scheme_id` may hold `status = 'Active'` — enforced at the service layer, reinforced by a partial unique index where practical. |
| `ufls_stage` | `ufls_stage_id` (UUID PK), `ufls_scheme_version_id` (FK), `stage_order`, `frequency_threshold_hz`, `time_delay_ms`, `target_shed_mw` (nullable), `is_protected` (boolean, default `false`), `description` | Unique on (`ufls_scheme_version_id`, `stage_order`) and (`ufls_scheme_version_id`, `frequency_threshold_hz`). `is_protected` is UFLS-owned business data consumed by `getProtectedAssignments()` (§9 rule 16, §13). |
| `ufls_load_block` | `ufls_load_block_id` (UUID PK), `ufls_stage_id` (FK), `block_label`, `target_mw` (nullable) | Groups direct assignments only. |
| `ufls_direct_assignment` | `ufls_direct_assignment_id` (UUID PK), `ufls_load_block_id` (FK), `substation_id` (FK, external), `equipment_reference` (text, temporary placeholder — §7.4), `approved_mw` (nullable), `source_load_snapshot_id` (FK, external, nullable), `remarks` | `approved_mw`/`source_load_snapshot_id` set only at Approval (§7.6, §9 rule 9). |
| `ufls_pocket_assignment` | `ufls_pocket_assignment_id` (UUID PK), `ufls_stage_id` (FK), `source_analysis_result_id` (FK, external), `source_override_id` (FK, external, nullable), `approved_total_mw` (nullable) | Belongs directly to a stage, not a load block (§7.5). |
| `ufls_pocket_assignment_substation` | `id` (BIGINT PK), `ufls_pocket_assignment_id` (FK), `substation_id` (FK, external), `approved_mw` (nullable) | Normalized, not a JSON array (consistent with the pattern already established in [network-model-module.md](network-model-module.md) §11). |
| `ufls_change_reason` | `ufls_change_reason_id` (UUID PK), `ufls_scheme_version_id` (FK), `ufls_direct_assignment_id` (FK, external nullable), `ufls_pocket_assignment_id` (FK, external nullable), `change_type` (new \| revised \| removed), `reason`, `created_by_user_id`, `created_at` | Exactly one of `ufls_direct_assignment_id`/`ufls_pocket_assignment_id` set per row (CHECK constraint, mirroring the XOR pattern used in [psse-integration-module.md](psse-integration-module.md) and [network-model-module.md](network-model-module.md)). |
| `ufls_audit_log` | `log_id` (BIGINT PK), `entity_type`, `entity_id`, `field_name`, `old_value`, `new_value`, `changed_at`, `changed_by_user_id`, `change_reason` | Owned per CLAUDE.md A4; captures field-level changes and lifecycle transitions as first-class events (§14). |

**Cross-module constraints:** all foreign keys from UFLS tables into `substation` (Master Data), `load_snapshot` (PSS/E Integration), `island_analysis_result`/`manual_override` (Network Model), and `user` (IAM) are `ON DELETE RESTRICT`. UFLS tables are written to exclusively by UFLS's own service layer (CLAUDE.md A1, [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md)).

---

## 12. API Contract (Concept)

APIs are external/UI-facing contracts (CLAUDE.md §13, A9); conceptual resource shape only.

- `ufls-schemes`, `ufls-scheme-versions` — list/retrieve, with status filter.
- `.../stages`, `.../load-blocks`, `.../direct-assignments`, `.../pocket-assignments` — nested read/write access, writes permitted only while the owning version is Draft.
- `.../direct-assignments/{id}/recommended-mw`, `.../pocket-assignments/{id}/recommended` — read-only, always resolved live against PSS/E Integration/Network Model's Current data; never cached as an authoritative value; explicitly labeled "recommended" in the response shape so a client cannot confuse it with `approved_mw`.
- `.../change-reasons` — submit/list change reasons for a Draft version; required before the "submit for review" transition succeeds.
- Lifecycle transition actions (submit for review, approve, activate) as explicit resource-oriented actions, each requiring a reason where applicable and resulting in an audit event (§14). The "approve" action is the one that atomically captures `approved_mw` for every assignment (§7.6, §9 rule 9).

**Contract requirements (CLAUDE.md A9):** pagination/filtering/sorting for collection endpoints; structured error responses; authentication/authorization per endpoint; audit-relevant actions flagged (all writes and lifecycle transitions).

**Read enrichment, not duplication:** an assignment response may include a resolved, read-time summary of its substation(s) for display convenience, fetched at request time and never persisted in a UFLS table (§6).

**Data contracts:** standard three-layer separation (CLAUDE.md A6).

---

## 13. Service Interfaces

Per CLAUDE.md A1 (module communication via in-process service-layer interfaces):

**UFLS exposes, for other modules to consume:**
- A read-only query interface for the current Active version and its structure — for Dashboard and future Audit/Analytics reporting.
- A read-only interface for a substation's UFLS assignment history across versions — for audit and reporting.
- **`getProtectedAssignments(scope)`** — a read-only interface returning the set of substations currently assigned in a given scope (e.g. all Active-version assignments, or a specified subset of "protected" stages). Each returned assignment is tagged with its owning stage's stored `is_protected` value (§7.1, §9 rule 16, §11) — UFLS's own business data, not something computed on the fly by the caller or supplied by Cross-Scheme Compliance. **Open Question 7 — how UFLS exposes data to a future Cross-Scheme Compliance capability without violating module boundaries:** this is the answer. A future Cross-Scheme Compliance capability (whether a dedicated module or logic embedded per scheme module) calls this interface on UFLS, and the equivalent interface on UVLS/EMLS, and cross-checks the results itself. This is a standard service-to-service call under CLAUDE.md A1's primary communication mechanism — not the narrow reporting-only join exception — so it requires no special dispensation and no direct table coupling between scheme modules. UFLS's own tables never reference UVLS/EMLS (§9, rule 15); the compliance logic and the fan-out across scheme modules live entirely in the consuming capability.

**UFLS consumes, from other modules' service layers — never their repositories directly:**
- From Master Data (Substation Registry): substation existence/validity checks, `grid_owner` lookups for Rule 8 (§9), and read-enrichment lookups (§12).
- From PSS/E Integration: the recommended-MW interface, called only while resolving a Draft/Under Review direct assignment's recommendation, and once more at Approval to capture `approved_mw`.
- From Network Model: `analyzeIsland`/`getEffectiveIsland`, called while building or reviewing a pocket assignment, and once more at Approval to capture `approved_mw`.
- From Core Platform (IAM): authorization checks for every write and lifecycle-transition operation; user lookups for audit attribution.

UFLS never calls another module's repository layer directly, and no other module writes to a UFLS-owned table, per CLAUDE.md A1 and [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md). Read-only cross-module SQL joins are permitted only for reporting/dashboard purposes, never as a substitute for the service calls above.

---

## 14. Audit Requirements

Per CLAUDE.md §5.4 and A4, UFLS owns and writes its own audit log (`ufls_audit_log`), covering every owned entity in §5.

- Every create, update, and delete of a stage, load block, or assignment is recorded with who, when, what changed, and why (a required reason for any change to a version that has left Draft).
- **Lifecycle state transitions are recorded as first-class audit events.**
- **Activation is audited as a single correlated event** covering both halves of the transition (§8).
- **MW capture at Approval is audited explicitly**, recording the source `load_snapshot_id`/`analysis_result_id`/`override_id` alongside the captured value for every assignment — this is the cross-module audit consideration that [psse-integration-module.md](psse-integration-module.md) §14 and [network-model-module.md](network-model-module.md) §14 both flagged as "enabled but not written by" those modules; UFLS is the module that writes it, closing that loop.
- `UflsChangeReason` entries are themselves part of the durable engineering record (not merely audit metadata) — they are reviewed by approvers as engineering documentation, distinct from the technical field-diff audit log (§7.7).
- Audit history is append-only and never modified (CLAUDE.md A4, §16).
- Audit log access is itself access-controlled (CLAUDE.md A10).

---

## 15. Security Considerations

- All engineering approval actions require an authenticated, named IAM user (CLAUDE.md A10).
- Authorization is role-based via IAM. Recommended minimum role separation for UFLS (unchanged from the original design):
  - **Editor** — may create/edit a Draft version's structure, including requesting recommendations from PSS/E Integration/Network Model.
  - **Reviewer** — may move a version through Under Review.
  - **Approver** — elevated privilege; may Approve a version (triggering MW capture).
  - **Activator** — elevated privilege; may Activate an Approved version.
- **Segregation of duties is recommended**, not assumed by default: the Draft editor should not be the sole Approver, given the safety-critical nature of a grid-wide UFLS scheme.
- Requesting a recommendation (PSS/E Integration/Network Model calls) requires no elevated permission beyond Editor — it has no persistent authoritative effect.
- Read access to Active/Approved/Superseded/Archived versions is broader than write access; Draft/Under Review content may be restricted to the drafting/reviewing team.
- All GridDefence engineering data is sensitive by default (CLAUDE.md A10); TLS required outside local development.

---

## 16. Testing Requirements

Per CLAUDE.md §18 and A11, in priority order:

1. **Business rule tests** — single-Active-version-per-scheme enforcement; atomic activate-and-supersede; immutability of Approved/Active versions; Rule 7 (direct/pocket overlap) and Rule 8 (excluded ownership) enforcement; MW capture-at-approval correctness (verifying `approved_mw` is null before Approval and immutable after, with no residual live dependency on PSS/E Integration or Network Model's current state).
2. **Engineering calculation / validation tests** — stage ordering/threshold monotonicity; recommended-MW resolution correctness against PSS/E Integration and Network Model's service interfaces; change-reason-required-before-review enforcement.
3. **API contract tests** — request/response schema conformance (including that recommended vs. approved MW are never conflated in a response shape); authorization enforcement per endpoint.
4. **Database migration tests** — required once actual migrations are authored.
5. **UI behaviour tests** — required once a UFLS frontend exists; must confirm the frontend only ever displays recommended MW as advisory during Draft/Under Review and never computes or asserts it as approved (CLAUDE.md A12).

Business rules and engineering calculations must not be merged without accompanying tests (CLAUDE.md A11).

---

## 17. Future Extensions

- **Equipment Registry migration** — replace `equipment_reference` free text with a real `equipment_id` foreign key once that module exists (§7.4, Open Question 2).
- **Rate-of-change-of-frequency (df/dt / ROCOF) supplementary stages** — extends `UflsStage`, not a new module.
- **PSS/E simulation export** — using the Substation Registry's `psse_bus_number` to export approved UFLS scheme versions for power system simulation studies, beyond the recommended-MW consumption already designed here.
- **Cross-Scheme Compliance module** — formalizes the enforcement policy (warn/block modes, per-stage protection configuration) built on top of the `getProtectedAssignments` interface already exposed (§13).
- **Critical Infrastructure module** — once it exists, Rule 2-equivalent (critical-substation protection) enforcement follows the same read-only-lookup pattern already established for Rule 8 (§9).
- **Shared Rule 7/8 validation logic** — factor the direct/pocket-overlap and excluded-ownership checks into a reusable utility once UVLS/EMLS are built, to avoid three independently-maintained implementations (§18).
- **Adaptive/simulation-informed UFLS design** — any future analytics-driven proposal still enters as a new Draft version subject to the same full lifecycle; analytics never bypasses engineering approval.
- **Superseded → Active reactivation** — pending the ADR described in §8/closing summary.

---

## 18. Risks and Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| A recommendation viewed during Draft becomes stale by the time Approval occurs (Current `LoadSnapshot`/analysis superseded in between) | The captured `approved_mw` could reflect an outdated view if not re-resolved | Resolve the recommendation fresh at the moment of Approval itself (§7.6), not from a cached Draft-time value — this is already the mandated design, not merely a suggestion |
| Rule 7/Rule 8 validation logic re-implemented independently in UVLS and EMLS | Drift between three implementations of what should be identical logic | Factor into a shared utility once a second scheme module is built (§17) — not urgent with only UFLS built today, but flag before UVLS begins |
| An Active version's assignment references a substation later decommissioned | The live scheme references a retired asset; FK remains valid (historical integrity preserved) but is operationally stale | A future Audit and Analytics health-check report should flag this, rather than blocking or retroactively altering the Active version (unchanged from original design) |
| No enforced segregation of duties between drafting and approving | A single user could draft and approve a safety-critical change unchecked | Configure IAM roles so Approver/Activator differ from the primary Draft editor, as organisational policy (§15) |
| `Superseded → Active` reactivation (§8), if adopted, interacts with a Draft that assumed the reactivated version would stay Superseded | Potential confusion during an emergency revert about which version is the basis for in-progress Draft work | Flagged as an open risk pending the ADR decision (closing summary) — not resolved by this document |
| Frequency threshold/time-delay validation range bounds hardcoded in application code | Silently violates CLAUDE.md A7 | Store as versioned engineering parameter data, not an application constant (unchanged from original design) |

---

## MVP Behaviours Preserved

- The Version → Stage → Assignment hierarchy shape, with auto-supersede-on-activation.
- Only one Active version at a time — now correctly scoped per `UflsScheme` rather than a hardcoded scheme-type flag.
- A curated, reason-required change log at review time (`UflsChangeReason`), directly modeled on the legacy MVP's `LoadSheddingChangeLog` pattern.
- **Rule 3** (direct/pocket overlap, hard block) and **Rule 4** (excluded ownership, hard block) — both recognized as version-internal, self-contained rules and encoded directly as UFLS's own business rules (§9, rules 7–8), fully resolving two of the four business rules flagged as open in the Codebase Discovery Report.
- Pocket/island-based shedding as a first-class assignment type alongside direct assignment.
- Substation-level MW figures informed by real, imported network load data.

## MVP Behaviours Redesigned

- MW treatment: from a live, cached, recomputable value tied to "the current snapshot" → explicit recommended-during-Draft vs. captured-and-immutable-at-Approval, with descriptive traceability pointers instead of live dependencies (§7.6, §9).
- Version lifecycle: from a 3-state model (draft/active/deactivated) → the full 6-state Canonical Version Lifecycle.
- Topology/pocket analysis: from logic embedded directly in the load-shedding model → fully owned by Network Model, consumed by UFLS through a service interface only (§9, rule 15).
- Relay/equipment concept: from a first-class model → deferred as a temporary, explicitly-labeled free-text placeholder pending Equipment Registry, with a defined migration path (§7.4).
- Manual island override: from living on the pocket assignment itself → owned by Network Model as `ManualOverride`, referenced by UFLS only via a traceability pointer (§7.5).

## MVP Behaviours Discarded

- `unpublish()` as a distinct reverse/rollback operation — not carried forward as designed, because it contradicts CLAUDE.md §5.2. A forward-only reactivation model is recommended in its place, pending its own ADR (§8).
- A single combined topology+load snapshot model — already discarded at the PSS/E Integration layer ([ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md)), reaffirmed here by UFLS's clean separation of `source_load_snapshot_id` (direct assignments) from `source_analysis_result_id` (pocket assignments).
- JSON-blob storage of isolated/manual substation sets — replaced by normalized, FK-enforced child tables (`ufls_pocket_assignment_substation`), consistent with the same choice already made in [network-model-module.md](network-model-module.md).

## Architectural Decisions Still Requiring an ADR

1. **Whether to amend the Canonical Version Lifecycle (CLAUDE.md A3)** to permit `Superseded → Active` reactivation as a forward-only emergency-revert mechanism (§8, Open Question 8). This affects every versioned module, not only UFLS, and must be decided at the CLAUDE.md/A3 level.
2. **Cross-Scheme Compliance module** — the formal enforcement policy (warn/block modes, protected-stage configuration) built on top of `getProtectedAssignments` (§13, §17). This document defines the mechanism; it does not define the policy.
3. **Critical Infrastructure module** — where critical-asset data lives and how Rule 2-equivalent protection is enforced (§17).
4. **Equipment Registry** — needed before Open Question 2's migration path (§7.4) becomes concrete.
5. **Shared Rule 7/8 validation utility** — a lower-stakes implementation decision, but worth deciding before UVLS is built rather than after (§17, §18).
