# UVLS Module Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document follows the Canonical Module Architecture Document Template (CLAUDE.md **A8**).

Related documents: [system-overview.md](system-overview.md), [domain-model.md](domain-model.md), [substation-registry.md](substation-registry.md), [psse-integration-module.md](psse-integration-module.md), [network-model-module.md](network-model-module.md), [ufls-module.md](ufls-module.md) (the structural template this document adapts), [critical-infrastructure-module.md](critical-infrastructure-module.md), [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md), [ADR-000](../adr/ADR-000-architecture-principles.md) through [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md).

> Numeric examples in this document (voltage thresholds, time delays, MW figures) are **illustrative only**. Actual values are engineering policy data, stored and versioned in the database per CLAUDE.md **A7**.

> **On reuse:** UVLS is structurally the second Defence Scheme module built against GridDefence's established pattern language. Everywhere the underlying engineering problem is genuinely the same shape as UFLS's — version lifecycle, MW capture, audit, change reasons, Rule 3/4-equivalent ownership, the Cross-Scheme Compliance interface — this document reuses [ufls-module.md](ufls-module.md)'s structure directly, not just its style. Everywhere under-voltage shedding is a genuinely different engineering problem from under-frequency shedding — threshold locality, stage scoping, the role of topology-based islanding — this document deliberately diverges, with the reasoning stated explicitly rather than silently copied. §7.1 summarizes exactly which is which.

---

## 1. Module Overview

Under Voltage Load Shedding (UVLS) is a Defence Scheme module: the engineering system of record for the design, approval, versioning, and audit of the UVLS scheme protecting Peninsular Malaysia's transmission grid against voltage collapse.

Unlike frequency, which is a single system-wide quantity, voltage is fundamentally **local** — a voltage sag reflects a reactive-power deficiency concentrated in a specific area of the grid, not a uniform system-wide condition. UVLS defines, in successive **stages**, how much load is shed and where, as bus voltage falls below defined thresholds — thresholds that are naturally scoped to the region experiencing the voltage problem, not applied uniformly nationwide the way UFLS's frequency thresholds are. This module owns the *engineering design* of that scheme; it does not own the substations it assigns load to, the network/load data used to compute recommendations, the connectivity analysis behind any island-based assignment, or real-time relay tripping.

---

## 2. Purpose

To provide a single, versioned, auditable source of truth for the UVLS scheme's engineering design, so that:

- Every UVLS scheme version that has ever been in force is permanently reconstructable (CLAUDE.md §5.2).
- Voltage thresholds are represented and validated in a way that reflects their genuinely local, region-scoped character, rather than being forced into UFLS's system-wide threshold shape.
- Engineers designing a version get accurate, current recommended MW and voltage figures from PSS/E Integration, and — where genuinely applicable — island analysis from Network Model, without either being mistaken for approved data.
- Exactly one UVLS scheme version governs the live grid at any moment.
- Cross-Scheme Compliance can check UVLS against UFLS, EMLS, and future schemes through the same interface shape every Defence Scheme module exposes, with no special-casing required on the compliance side.

---

## 3. Responsibilities

UVLS owns:

- ✓ UVLS scheme identity (`UvlsScheme`)
- ✓ UVLS scheme versions and their lifecycle
- ✓ UVLS stages, their voltage thresholds, time delays, and (where applicable) regional scoping
- ✓ Direct (substation-level) assignments
- ✓ Pocket/island-based assignments, as a supported but expected-to-be-rare mechanism (§7.4)
- ✓ Approved MW values, once captured
- ✓ Human-entered change reasons
- ✓ Its own audit trail (`uvls_audit_log`, CLAUDE.md A4)

---

## 4. Non-Responsibilities

UVLS does **not** own:

- ✗ Substation name, mnemonic, voltage level, region, state, owner, or coordinates — owned by the Substation Registry. UVLS references a substation only by `substation_id`.
- ✗ Topology structure, load, or bus voltage data — owned by PSS/E Integration. UVLS references a `LoadSnapshot` only as a traceability pointer.
- ✗ Connectivity graph construction or island/pocket detection — owned by Network Model.
- ✗ Critical-infrastructure classification — owned by Critical Infrastructure; UVLS never duplicates it.
- ✗ Cross-scheme compliance checking (Rule 1, Rule 2) — owned by Cross-Scheme Compliance; UVLS exposes what that module needs via a read-only service interface (§13) without owning the cross-checking logic itself.
- ✗ Physical equipment/relay master data — reserved for a future Equipment Registry; UVLS may hold the same temporary free-text placeholder pattern already established in [ufls-module.md](ufls-module.md) §7.4.
- ✗ Identity, authentication, roles, or permissions — owned by IAM.
- ✗ Real-time relay execution, SCADA control, or field voltage-regulation equipment (automatic voltage regulators, capacitor banks, tap-changers) — UVLS is the engineering **design and record of intent**; deploying it onto physical relays, and the separate real-time voltage-control apparatus that operates alongside UVLS, are both out of scope.
- ✗ UFLS or EMLS data, business rules, or assignments — each is its own independent bounded context.
- ✗ **Definition or ownership of regional/voltage-control-area boundaries.** UVLS references Core Platform's existing `region` reference data (already used by the Substation Registry) read-only, for stage scoping (§7.2) — it does not define a new geographic/electrical zoning concept of its own. Introducing a purpose-built "Voltage Control Area" concept, if regions prove too coarse in practice, is a deferred decision (§18).

---

## 5. Owned Entities

| Entity | Description |
|---|---|
| `UvlsScheme` | The stable identity a UVLS scheme's versions belong to. |
| `UvlsSchemeVersion` | The versioned aggregate root, belonging to exactly one `UvlsScheme`. |
| `UvlsStage` | One voltage-triggered shedding stage within a scheme version, optionally scoped to a region (§7.2), including its own `is_protected` classification consumed by `getProtectedAssignments()` (§13). |
| `UvlsLoadBlock` | A named quantum of load defined within a stage, grouping one or more direct assignments. |
| `UvlsDirectAssignment` | A direct, substation-level assignment within a load block — the primary, expected assignment mechanism for UVLS (§7.4). |
| `UvlsPocketAssignment` | A topology-derived (island/"pocket") assignment within a stage — supported for schema consistency, expected to be rarely used (§7.4). |
| `UvlsPocketAssignmentSubstation` | Normalized child of `UvlsPocketAssignment` — captured substation set and per-substation MW. |
| `UvlsChangeReason` | A curated, human-entered explanation of one changed assignment, required before a version leaves Draft. |
| `uvls_audit_log` | UVLS's own audit trail (CLAUDE.md A4), covering all owned entities above. |

---

## 6. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| Substation | Master Data (Substation Registry) | `substation_id` (UUID) only |
| Region | Core Platform (reference data) | `region_id`, read-only, for optional stage scoping (§7.2) — the only reference-data lookup UVLS consults directly, unlike UFLS, which needed none |
| `TopologyVersion`, `LoadSnapshot`, `LoadSnapshotBusState` | PSS/E Integration | `source_load_snapshot_id` — traceability pointer only (§7.5, §7.6); `LoadSnapshotBusState`'s voltage magnitude is consulted live during Draft/Under Review, never persisted |
| `IslandAnalysisResult`, `ManualOverride` | Network Model | `source_analysis_result_id`, `source_override_id` — traceability pointers only, used only where a pocket assignment is actually created (§7.4) |
| User | Core Platform (IAM) | `user_id` (UUID) only, with fallback `external_principal_id` + provider per [ADR-002](../adr/ADR-002-identity-and-access-management.md) |
| Role / Permission | Core Platform (IAM) | Not referenced by foreign key; authorization checks via IAM's service layer |

UVLS never stores substation name, mnemonic, voltage level, owner, or coordinates; never stores topology structure or raw load/voltage figures; never stores connectivity graph or island-detection logic; never stores critical-asset classification.

---

## 7. Domain Model

```
UvlsScheme (1) ──── (many) UvlsSchemeVersion
UvlsSchemeVersion (1) ──── (many) UvlsStage ──── references (read-only, optional) ──▶ Region.region_id (Core Platform, external)
UvlsStage (1) ──── (many) UvlsLoadBlock ──── (many) UvlsDirectAssignment
UvlsStage (1) ──── (many) UvlsPocketAssignment ──── (many) UvlsPocketAssignmentSubstation
UvlsSchemeVersion (1) ──── (many) UvlsChangeReason

UvlsDirectAssignment           ──── references ───▶ Substation.substation_id        (Master Data, external)
UvlsPocketAssignmentSubstation ──── references ───▶ Substation.substation_id        (Master Data, external)
UvlsDirectAssignment           ──── traceability ─▶ LoadSnapshot.load_snapshot_id    (PSS/E Integration, external, optional)
UvlsPocketAssignment           ──── traceability ─▶ IslandAnalysisResult.analysis_result_id,
                                                     ManualOverride.override_id      (Network Model, external, optional)
UvlsSchemeVersion / UvlsStage / assignments / change reasons
                                ──── references ───▶ User.user_id                   (Core Platform/IAM, external)
```

A `UvlsSchemeVersion` is the unit of approval and activation, exactly as in UFLS. No arrow points from UVLS's tables toward UFLS's, EMLS's, or Cross-Scheme Compliance's tables — that boundary is crossed only through service interfaces (§13).

### 7.1 How UVLS Differs from UFLS

| Aspect | Shared structurally (same pattern, reused as-is) | Different by design (same category of concern, genuinely different content) |
|---|---|---|
| Version lifecycle | Full six-state Canonical Version Lifecycle, auto-supersede, immutability rules — identical | — |
| MW capture | Recommended-during-Draft vs. captured-at-Approval, traceability pointers, never a live dependency — identical mechanism | — |
| Audit trail, change-reason pattern | Identical shape and rules | — |
| Direct assignment model | Load block → direct assignment shape identical | Direct assignment is UVLS's **primary and dominant** mechanism (§7.4), whereas for UFLS both direct and pocket assignment are commonly used |
| Rule 3/4-equivalent (version-internal overlap, IPP/LSS exclusion) | Owned identically, by UVLS itself, using the same Substation Registry `grid_owner` lookup | — |
| `getProtectedAssignments` interface shape | Identical contract — a hard requirement for Cross-Scheme Compliance's generic fan-out (§13) | — |
| Threshold physical meaning and unit | — | Frequency (Hz, system-wide, no locality) vs. voltage (p.u., inherently local — §7.2, §7.3) |
| Stage scoping | — | UFLS stages are always grid-wide; UVLS stages are optionally region-scoped (§7.2) |
| Pocket/island assignment usage | Schema and mechanism identical | Expected usage differs sharply — common for UFLS, rare/edge-case for UVLS, for genuine engineering reasons (§7.4) |
| Draft-time recommendation data consumed | Recommended MW, identical | UVLS additionally consults live bus voltage magnitude from the Current `LoadSnapshot` (§7.5) — UFLS has no equivalent need, since frequency isn't a per-bus quantity |
| `getProtectedAssignments` `is_protected` classification | Identical stored field (`UvlsStage.is_protected`) and mechanism to UFLS's `UflsStage.is_protected` — engineering policy configuration, UVLS's own business data (§7.2) | — |

### 7.2 Voltage Threshold Model and Stage Scoping

**Unit — answering Question 1:** each `UvlsStage` carries a `voltage_threshold_pu`: the bus voltage, expressed in **per-unit relative to the substation's own nominal voltage**, at or below which the stage is armed to trip. Per-unit is preferred over an absolute kV threshold because it normalizes across the Substation Registry's diverse voltage classes (500/275/230/132 kV, per [substation-registry.md](substation-registry.md) §6) — a `0.90 p.u.` threshold means the same *relative* severity whether applied to a 500 kV or a 132 kV bus, whereas an absolute kV figure would need to be re-derived per voltage class. This matches the convention already implied by the legacy MVP's own threshold field, whose help text distinguished "Hz for UFLS; p.u. for UVLS." A display layer may still show the equivalent absolute kV value (derivable from the referenced substation's `voltage_level`, resolved read-only from Substation Registry) for engineer convenience — this is a display-only derivation, not a second stored value (CLAUDE.md A12).

**Stage scoping — answering Question 2:** UVLS stages are **regional, not bus-level, not voltage-class-based, and not purely generic.** Each `UvlsStage` carries an optional `region_scope_id`, a read-only reference to Core Platform's existing `region` lookup:
- If set, the stage's threshold and assignments apply only within that region's voltage-stressed area — reflecting the reality that a voltage problem in the Northern region is a materially different event from one in the Southern region, and coordinating shedding across a whole nation for what is fundamentally a local phenomenon would be engineering-incorrect.
- If null, the stage applies grid-wide — supported for schemes or planning scenarios where a genuinely national threshold is appropriate, or during early-stage scheme design before regional differentiation is finalized.
- **Not bus-level:** subdividing stages down to individual buses would be operationally unwieldy as a *stage* concept — bus-level granularity is already expressed at the *assignment* level (which specific substation is assigned), not by fragmenting the stage structure itself.
- **Not voltage-class-based:** grouping stages by nominal voltage class (500kV vs 132kV) was considered and rejected — voltage sag characteristics cluster by *geography* (reactive power flow patterns, transmission distance, local generation loss), not by a substation's voltage class. Two substations at the same voltage class in different regions can have entirely unrelated voltage conditions.

A version may freely mix regionally-scoped and grid-wide stages.

Each stage also carries an `is_protected` flag — ordinary engineering policy configuration, owned and set by UVLS as its own business data, identical in mechanism to [ufls-module.md](ufls-module.md) §7.1's `UflsStage.is_protected`. This is the field `getProtectedAssignments()` (§13) reads to classify each returned assignment for Cross-Scheme Compliance's Rule 1, without UVLS ever needing to know that UFLS, EMLS, or any other scheme exists (§9, rules 15–17).

### 7.3 How Voltage Thresholds Differ from UFLS Frequency Thresholds — Answering Question 3

| | UFLS frequency threshold | UVLS voltage threshold |
|---|---|---|
| Unit | Hz, absolute | p.u., relative to local nominal voltage |
| Locality | System-wide — one value describes the whole interconnected grid at any instant | Local — varies by region/bus; two regions can have materially different voltage conditions simultaneously |
| Physical cause | Generation–load imbalance (system-wide) | Reactive power/voltage support deficiency (localized) |
| Stage scoping | Always grid-wide | Optionally region-scoped (§7.2) |
| Ordering rule | Thresholds strictly decrease as `stage_order` increases, across the whole version | Thresholds strictly decrease as `stage_order` increases, but only **within the same region scope** — stages in different regions are not compared against each other (§9, §10) |

Time delay (`time_delay_ms`) is structurally identical between the two schemes — the coordination-margin rationale (avoiding nuisance tripping on a transient dip) applies equally to a voltage transient as to a frequency transient, so this concept is reused verbatim, not reinterpreted.

### 7.4 Direct and Pocket/Island Assignment — Answering Question 4

**Direct assignment** (§7.4 in [ufls-module.md](ufls-module.md), reused structurally without change) is UVLS's **primary and dominant** assignment mechanism. Voltage sag mitigation is fundamentally a problem of reducing local demand in the affected area — a direct, substation-by-substation reduction of load in the voltage-deficient zone is the natural engineering response.

**Pocket/island assignment is supported in this module's schema for architectural consistency with UFLS and to avoid a structural gap for edge cases, but is expected to be used rarely, if at all, and is treated as an optional, secondary mechanism, not a primary one.** The reasoning: UFLS's islanding technique works because isolating any electrically self-sufficient chunk of the grid helps a *system-wide* frequency imbalance regardless of where that island is. UVLS's problem is the opposite shape — a *local* voltage deficiency, which electrical isolation can actually **worsen**, not help, if the isolated island is cut off from external transmission paths that were supplying it reactive power support. There may be narrow, genuine exceptions (e.g. a weak radial sub-transmission configuration where isolating a specific load pocket is a deliberate, engineered response to a local voltage collapse scenario), which is why the mechanism remains available rather than removed outright — but it should never be treated as UVLS's default or expected tool the way it is for UFLS. Where used, `UvlsPocketAssignment` follows the exact same structure, capture semantics, and Network Model integration as [ufls-module.md](ufls-module.md) §7.5, unchanged.

### 7.5 Consuming PSS/E LoadSnapshot and Voltage Data — Answering Question 5

UVLS consumes PSS/E Integration's Current `LoadSnapshot` in two ways during Draft/Under Review, one shared with UFLS and one UVLS-specific:

- **Recommended MW** (shared mechanism, §7.6, identical to [ufls-module.md](ufls-module.md) §7.6) — resolved live for a candidate direct assignment, never persisted until Approval.
- **Live bus voltage magnitude** (UVLS-specific) — a candidate assignment's substation can be checked against the Current `LoadSnapshot`'s `LoadSnapshotBusState.voltage_mag` (owned by PSS/E Integration, [psse-integration-module.md](psse-integration-module.md) §5) to show the engineer whether that substation is *actually* experiencing depressed voltage in the current network state — directly informing which substations belong in a given region-scoped stage. This has no UFLS equivalent, since frequency is not a per-bus quantity worth querying individually. This is consumed read-only, live, and is never stored in UVLS's own tables — it is display/decision-support information only, exactly like recommended MW, and is subject to the same CLAUDE.md A12 boundary (informative, never authoritative). This module doc does not modify [psse-integration-module.md](psse-integration-module.md)'s own service interface list; it notes that module's existing `LoadSnapshotBusState` data already supports this read, and that formally naming a `getVoltageMagnitude`-style method is a natural, small extension worth adding there when PSS/E Integration is next revisited (§18) — not a new module dependency, just a more precise interface name for a read that entity already supports.

### 7.6 Approved MW Snapshot — Answering Question 6

**Structurally identical to [ufls-module.md](ufls-module.md) §7.6, with no adaptation needed.** MW is MW, regardless of what physical condition triggered the shedding — there is no engineering reason for capture semantics to differ between a frequency-triggered and a voltage-triggered assignment. `approved_mw` is null while Draft/Under Review, captured exactly once at the Under Review → Approved transition, immutable thereafter, alongside a `source_load_snapshot_id` (direct) or `source_analysis_result_id`/`source_override_id` (pocket, where used) traceability pointer that is descriptive metadata only, never a live dependency.

---

## 8. Lifecycle / State Model

Every `UvlsSchemeVersion` follows the Canonical Version Lifecycle (CLAUDE.md **A3**) without exception, identical in every respect to [ufls-module.md](ufls-module.md) §8:

```
Draft → Under Review → Approved → Active → Superseded → Archived
```

- **Only one Active `UvlsSchemeVersion` may exist per `UvlsScheme` at any time.**
- **Activating a new version automatically supersedes the previous Active version**, as a single atomic operation.
- **Approved and Active versions are immutable.**
- **Corrections always create a new version.**
- Both halves of an activation are recorded as a single correlated audit event (§14).

**Superseded → Active reactivation remains an open question**, carried forward unresolved from [ufls-module.md](ufls-module.md) §8/closing summary — it is a CLAUDE.md A3-level decision affecting every versioned module, not something this document (or UFLS's) can decide unilaterally. See closing summary.

---

## 9. Business Rules

1. Only one `UvlsSchemeVersion` may hold status `Active` per `UvlsScheme` at any time.
2. Activating a version supersedes the current Active version (of the same `UvlsScheme`) automatically and atomically.
3. Approved and Active versions are immutable; any change requires a new version.
4. Within a scheme version, `stage_order` values are unique **within the same `region_scope_id` (including the "grid-wide, null scope" group treated as its own scope)**, and `voltage_threshold_pu` values must strictly decrease as `stage_order` increases **within that same scope** — stages in different regions are never compared against each other (§7.2, §7.3).
5. A load block belongs to exactly one stage; a direct assignment belongs to exactly one load block and references exactly one substation. A pocket assignment belongs to exactly one stage.
6. A substation may be referenced by multiple direct assignments, and may appear in multiple pocket assignments, within the same version.
7. **A substation may not simultaneously be assigned via a direct assignment and appear in any pocket assignment's substation set within the same scheme version** — the Rule 3 equivalent, version-internal, owned fully by UVLS (identical to [ufls-module.md](ufls-module.md) §9, rule 7).
8. **A substation whose Substation Registry `grid_owner` classification is Independent Power Producer, Large Scale Solar, or an equivalent excluded ownership classification may not be assigned via any direct or pocket assignment** — the Rule 4 equivalent, resolved via read-only lookup against Substation Registry, owned fully by UVLS (identical to [ufls-module.md](ufls-module.md) §9, rule 8).
9. Recommended MW/voltage data (Draft/Under Review) and Approved MW are structurally distinct; `approved_mw` is set only at the Under Review → Approved transition and never recomputed afterward.
10. A traceability pointer to a `LoadSnapshot`, `IslandAnalysisResult`, or `ManualOverride` is descriptive metadata only — never a live dependency capable of changing an Approved version's stored data.
11. Engineering approval actions require an authenticated, named IAM user.
12. New assignments must reference a substation whose current `operational_status` is not Decommissioned or Retired; this restriction does not apply retroactively to already-Approved/Active/Superseded/Archived assignments.
13. Deleting a stage, load block, or assignment is only possible while the owning version is in Draft.
14. A `UvlsChangeReason` row is required for every assignment that is new, revised, or removed relative to the version's comparison version, before the version may transition Draft → Under Review.
15. UVLS's own tables contain no foreign key into UFLS's, EMLS's, or any future scheme module's schema — cross-scheme concerns are resolved only through Cross-Scheme Compliance's service interfaces (§13).
16. UVLS must call Cross-Scheme Compliance's `checkCompliance` at Submit for Review, Approval, and Activation, obeying its returned `blocks_transition` value exactly as specified in [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md) §9 rule 2 and §13 — UVLS does not independently reinterpret or override that outcome.
17. Each `UvlsStage` carries its own `is_protected` classification, set by UVLS as ordinary engineering policy configuration — this is UVLS's own business data (§7.2), not a value computed or supplied by Cross-Scheme Compliance or any other module. It is exposed, read-only, through `getProtectedAssignments()` (§13); no other module writes to it.

---

## 10. Validation Rules

- `voltage_threshold_pu` must fall within a policy-defined valid range for per-unit voltage (the range is engineering parameter data per CLAUDE.md A7, not a hardcoded bound).
- `time_delay_ms` must be `>= 0`.
- `stage_order` must be unique within `(scheme_version, region_scope)`; `voltage_threshold_pu` must be unique and strictly decreasing as `stage_order` increases, within that same `(scheme_version, region_scope)` grouping (§9, rule 4).
- A direct assignment's `substation_id` must reference an existing Substation Registry record.
- A pocket assignment's `source_analysis_result_id` must reference an existing Network Model `IslandAnalysisResult`; `source_override_id`, if present, must reference an `Active` `ManualOverride` against that same result.
- `approved_mw` must be null while a version is Draft or Under Review, and non-null for every assignment before a version may transition Under Review → Approved.
- Rule 7 (direct/pocket overlap) and Rule 8 (excluded ownership) are validated at assignment-creation time and re-validated at the Draft → Under Review transition.
- A scheme version cannot be submitted for review with zero stages, or a stage with zero assignments.
- A `UvlsChangeReason` must have a non-empty reason.
- If `region_scope_id` is set on a stage, it must reference an existing, valid Core Platform `region` row.

---

## 11. Database Design (Concept)

Conceptual only — no migrations are defined here.

| Table (conceptual) | Key columns (conceptual) | Notes |
|---|---|---|
| `uvls_scheme` | `uvls_scheme_id` (UUID PK), `name`, `description`, `created_at` | Stable identity anchor. |
| `uvls_scheme_version` | `uvls_scheme_version_id` (UUID PK), `uvls_scheme_id` (FK), `version_label`, `status`, `compared_to_version_id` (nullable, self-referencing), `superseded_by_version_id` (nullable, self-referencing), `created_by_user_id`, `updated_by_user_id`, `approved_by_user_id` (nullable), `approved_at` (nullable), `activated_by_user_id` (nullable), `activated_at` (nullable), `created_at`, `updated_at` | Only one row per `uvls_scheme_id` may hold `status = 'Active'`. |
| `uvls_stage` | `uvls_stage_id` (UUID PK), `uvls_scheme_version_id` (FK), `region_scope_id` (FK, external to Core Platform, nullable), `stage_order`, `voltage_threshold_pu`, `time_delay_ms`, `target_shed_mw` (nullable), `is_protected` (boolean, default `false`), `description` | Unique on (`uvls_scheme_version_id`, `region_scope_id`, `stage_order`) and (`uvls_scheme_version_id`, `region_scope_id`, `voltage_threshold_pu`) — region-scoped, not version-scoped alone (§9, rule 4; differs from [ufls-module.md](ufls-module.md) §11's simpler `(version, stage_order)` uniqueness). `is_protected` is UVLS-owned business data consumed by `getProtectedAssignments()` (§9 rule 17, §13). |
| `uvls_load_block` | `uvls_load_block_id` (UUID PK), `uvls_stage_id` (FK), `block_label`, `target_mw` (nullable) | |
| `uvls_direct_assignment` | `uvls_direct_assignment_id` (UUID PK), `uvls_load_block_id` (FK), `substation_id` (FK, external), `equipment_reference` (text, temporary placeholder), `approved_mw` (nullable), `source_load_snapshot_id` (FK, external, nullable), `remarks` | Identical shape to `ufls_direct_assignment`. |
| `uvls_pocket_assignment` | `uvls_pocket_assignment_id` (UUID PK), `uvls_stage_id` (FK), `source_analysis_result_id` (FK, external), `source_override_id` (FK, external, nullable), `approved_total_mw` (nullable) | Identical shape to `ufls_pocket_assignment`; expected to be sparsely populated (§7.4). |
| `uvls_pocket_assignment_substation` | `id` (BIGINT PK), `uvls_pocket_assignment_id` (FK), `substation_id` (FK, external), `approved_mw` (nullable) | Normalized, not JSON. |
| `uvls_change_reason` | `uvls_change_reason_id` (UUID PK), `uvls_scheme_version_id` (FK), `uvls_direct_assignment_id` (FK, external nullable), `uvls_pocket_assignment_id` (FK, external nullable), `change_type`, `reason`, `created_by_user_id`, `created_at` | Exactly one of the two assignment FKs set per row (CHECK constraint). |
| `uvls_audit_log` | `log_id` (BIGINT PK), `entity_type`, `entity_id`, `field_name`, `old_value`, `new_value`, `changed_at`, `changed_by_user_id`, `change_reason` | Owned per CLAUDE.md A4. |

**Cross-module constraints:** all foreign keys into `substation`, `region`, `load_snapshot`, `island_analysis_result`/`manual_override`, and `user` are `ON DELETE RESTRICT`. UVLS tables are written exclusively by UVLS's own service layer.

---

## 12. API Contract (Concept)

APIs are external/UI-facing contracts (CLAUDE.md §13, A9); conceptual resource shape only, structurally identical to [ufls-module.md](ufls-module.md) §12 with one addition:

- `uvls-schemes`, `uvls-scheme-versions`, nested `stages`/`load-blocks`/`direct-assignments`/`pocket-assignments`, `change-reasons`, and lifecycle transition actions — identical shape to UFLS's equivalents.
- `.../stages/{id}/recommended` — read-only, resolved live, now returning **both** recommended MW and current bus voltage magnitude per candidate substation (§7.5), explicitly labeled as advisory, never conflated with `approved_mw`.
- Stage-related endpoints accept and return `region_scope_id` where applicable, defaulting to grid-wide (null) if omitted.

**Contract requirements and data contracts:** identical to [ufls-module.md](ufls-module.md) §12 (CLAUDE.md A9, A6).

---

## 13. Service Interfaces

Per CLAUDE.md A1:

**UVLS exposes, for other modules to consume:**
- A read-only query interface for the current Active version and its structure.
- A read-only interface for a substation's UVLS assignment history across versions.
- **`getProtectedAssignments(scope)` — answering Question 7.** Identical contract shape to [ufls-module.md](ufls-module.md) §13's interface of the same name: substations currently assigned in a given scope, each tagged with its owning stage's stored `UvlsStage.is_protected` value (§7.2, §9 rule 17, §11) — UVLS's own business data, not something computed on the fly by the caller or supplied by Cross-Scheme Compliance. This identity of shape is not a stylistic choice — it is a hard requirement of [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md)'s Rule 1/Rule 2 algorithms (§13 of that document), which fan out to every Defence Scheme module using one generic call pattern. Any deviation in shape would require Cross-Scheme Compliance to special-case UVLS, which would violate its own decoupling design.

**UVLS consumes, from other modules' service layers — never their repositories directly:**
- From Substation Registry: existence/validity checks, `grid_owner` lookups (Rule 8), read-enrichment.
- From PSS/E Integration: recommended-MW resolution, and live bus voltage magnitude resolution (§7.5) — both during Draft/Under Review and once more at Approval to capture `approved_mw`.
- From Network Model: `analyzeIsland`/`getEffectiveIsland`, only when a pocket assignment is actually being built (§7.4).
- From Core Platform (IAM): authorization checks, user lookups.
- **From Cross-Scheme Compliance:** `checkCompliance(subject_scheme='UVLS', subject_version_id, comparison_scope, checkpoint, triggered_by_user_id)`, called at Submit for Review, Approval, and Activation, exactly as specified in [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md) §13. UVLS stores only the returned `check_run_id` as a traceability pointer in its own audit log — never a copy of findings (§14).

UVLS never calls another module's repository directly, and no other module writes to a UVLS-owned table, per CLAUDE.md A1 and [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md).

---

## 14. Audit Requirements

Per CLAUDE.md §5.4 and A4, structurally identical to [ufls-module.md](ufls-module.md) §14:

- Every create, update, and delete of a stage, load block, or assignment is recorded with who, when, what changed, and why.
- Lifecycle state transitions, including activation's correlated dual event, are first-class audit events.
- MW capture at Approval is audited explicitly, recording the source `load_snapshot_id`/`analysis_result_id`/`override_id`.
- **Compliance check outcomes are audited at Approval and Activation**, recording the `check_run_id` from Cross-Scheme Compliance, and — where the version proceeded despite a `Warn`-severity finding — the mandatory acknowledgment reason, per [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md) §9 rule 9.
- `UvlsChangeReason` entries are part of the durable engineering record, distinct from the technical field-diff audit log.
- Audit history is append-only and never modified; audit log access is itself access-controlled.

---

## 15. Security Considerations

Identical role structure and reasoning to [ufls-module.md](ufls-module.md) §15:

- All engineering approval actions require an authenticated, named IAM user.
- Recommended minimum role separation: **Editor**, **Reviewer**, **Approver**, **Activator**.
- Segregation of duties (Draft editor ≠ sole Approver) is recommended, not assumed by default.
- Requesting a recommendation (PSS/E Integration/Network Model calls, including the voltage-magnitude read) requires no elevated permission beyond Editor.
- Read access to Active/Approved/Superseded/Archived versions is broader than write access; Draft/Under Review content may be restricted to the drafting/reviewing team.
- All GridDefence engineering data is sensitive by default; TLS required outside local development.

---

## 16. Testing Requirements

Per CLAUDE.md §18 and A11, in priority order:

1. **Business rule tests** — single-Active-version-per-scheme enforcement; atomic activate-and-supersede; immutability of Approved/Active versions; Rule 7/Rule 8 enforcement; **region-scoped threshold monotonicity** (a case UFLS's own test suite does not need, since UFLS has no region scoping) — verifying stages in different regions are correctly *not* compared against each other; MW capture-at-approval correctness.
2. **Engineering calculation / validation tests** — voltage-threshold range validation; recommended-MW and voltage-magnitude resolution correctness against PSS/E Integration; change-reason-required-before-review enforcement.
3. **API contract tests** — request/response schema conformance, including that the recommendation endpoint correctly returns both MW and voltage magnitude without conflating either with `approved_mw`; authorization enforcement.
4. **Database migration tests** — required once actual migrations are authored.
5. **UI behaviour tests** — required once a UVLS frontend exists; must confirm the frontend displays recommended MW/voltage as advisory only and never computes or asserts approved data (CLAUDE.md A12).

---

## 17. Future Extensions

- **Equipment Registry migration** — identical deferral to [ufls-module.md](ufls-module.md) §17.
- **Formal `getVoltageMagnitude` interface naming on PSS/E Integration** (§7.5) — a small, precise addition to that module's already-existing data surface, not a new dependency.
- **Dedicated Voltage Control Area concept** — if Core Platform's `region` reference data proves too coarse for real UVLS coordination in practice, a purpose-built zoning concept could replace `region_scope_id` without changing this module's core ownership (§18).
- **Structured criteria for when pocket/island assignment is engineering-appropriate for UVLS** — currently a documented judgment call (§7.4); could be formalized further if real usage patterns emerge.
- **PSS/E simulation export**, **shared Rule 7/8 validation utility**, **adaptive/simulation-informed design** — identical Future Extensions to [ufls-module.md](ufls-module.md) §17, now with two consuming schemes (UFLS, UVLS) making the shared-utility extension more concretely worthwhile.

---

## 18. Risks and Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| Region scoping reused from Core Platform's coarse `region` lookup may be too coarse for real voltage-coordination needs | Two genuinely distinct voltage-stress sub-areas within the same broad region could be forced into one scope, or conversely a scope could be too broad to be useful | Monitor in practice; a dedicated Voltage Control Area concept is the documented escalation path (§17), not adopted preemptively |
| Pocket/island assignment, though rare, remains fully modeled and could be misused by an engineer unfamiliar with the reasoning in §7.4 | A UVLS pocket assignment could inadvertently worsen a voltage condition by isolating a supply-dependent area | Recommend UI/documentation guidance surfacing the §7.4 reasoning directly to the engineer at the point of creating a pocket assignment, not just in this architecture document |
| Region-scoped threshold ordering (§9, rule 4) is a materially more complex validation rule than UFLS's simple version-wide ordering | Higher risk of an incorrect implementation silently comparing thresholds across regions | Prioritize the region-scoped monotonicity test explicitly (§16) as a first-class business rule test, not an afterthought |
| Cross-Scheme Compliance's generic fan-out (§13) depends on UVLS's `getProtectedAssignments` shape staying identical to UFLS's over time | Any future UVLS-specific evolution of that interface could silently break Cross-Scheme Compliance's Rule 1/2 algorithms | Treat interface-shape parity with UFLS as an explicit contract, not an implementation detail — changes require coordinated review with [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md) |
| MW/voltage recommendation viewed during Draft becomes stale by Approval | Captured `approved_mw` could reflect an outdated view if not re-resolved | Resolve fresh at the moment of Approval itself, exactly as already mandated in [ufls-module.md](ufls-module.md) §18 |

---

## MVP Behaviours Preserved

- The Version → Stage → Assignment hierarchy shape, with auto-supersede-on-activation — identical to UFLS, now confirmed to generalize to a second scheme.
- Direct assignment as the dominant mechanism — this matches the legacy MVP's actual observed usage pattern for UVLS even though its schema technically allowed pocket bays for any scheme type without distinction.
- Rule 3 (direct/pocket overlap) and Rule 4 (excluded ownership) as version-internal, UVLS-owned business rules.
- The per-unit voltage threshold convention, already implied by the legacy MVP's own field help text ("p.u. for UVLS"), now made structurally real rather than just a label.
- A curated, reason-required change log at review time.

## MVP Behaviours Redesigned

- **Threshold locality is now a first-class structural concept.** The legacy MVP stored UVLS thresholds in the same flat, version-wide structure as UFLS, with no representation of voltage's inherently regional character. GridDefence's `region_scope_id` and region-scoped monotonicity validation (§7.2, §9 rule 4) is a genuine architectural improvement, not a port.
- **Pocket/island assignment is explicitly demoted from an equally-available mechanism (as the MVP modeled it, identically for all scheme types) to a documented, rare, secondary mechanism for UVLS specifically** (§7.4), with the underlying engineering reasoning made explicit rather than left implicit in usage patterns alone.
- MW treatment: recommended-during-Draft vs. captured-at-Approval, identical to UFLS's own redesign from the MVP's live-cached MW model.
- **UVLS now consults live bus voltage magnitude, not just MW, during Draft** — a genuinely new capability the legacy MVP's undifferentiated `NetworkSnapshot` model made awkward to express cleanly, now natural given PSS/E Integration's `LoadSnapshotBusState` separation.

## MVP Behaviours Discarded

- The combined topology+load snapshot model — already discarded at the PSS/E Integration layer, reaffirmed here.
- JSON-blob storage of isolated/manual substation sets — replaced by normalized, FK-enforced child tables, consistent with UFLS and Network Model.
- Treating UVLS as structurally identical to UFLS in every respect (the MVP's shared-table, scheme-type-discriminator design) — superseded by UVLS being a fully independent bounded context that happens to share a pattern language with UFLS, not a shared schema.

## Architectural Decisions Still Requiring an ADR

1. **`Superseded → Active` reactivation** (carried forward, unresolved, from [ufls-module.md](ufls-module.md) §8/closing summary) — affects every versioned module including UVLS; still requires its own ADR amending CLAUDE.md A3.
2. **Whether Core Platform's `region` reference data is sufficient long-term for UVLS's stage scoping, or whether a dedicated Voltage Control Area Master Data concept is needed** (§7.2, §17, §18) — not urgent today, but should be revisited once real UVLS design activity provides evidence either way.
3. **Whether pocket/island assignment should remain in UVLS's schema indefinitely, or be removed if real usage confirms it is never actually used** (§7.4) — a lower-stakes decision than the other two, but worth a deliberate, documented choice once operational experience exists, rather than carrying an unused mechanism forward by default.
