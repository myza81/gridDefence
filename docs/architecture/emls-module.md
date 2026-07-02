# EMLS Module Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document follows the Canonical Module Architecture Document Template (CLAUDE.md **A8**).

Related documents: [system-overview.md](system-overview.md), [domain-model.md](domain-model.md), [substation-registry.md](substation-registry.md), [psse-integration-module.md](psse-integration-module.md), [network-model-module.md](network-model-module.md), [ufls-module.md](ufls-module.md) and [uvls-module.md](uvls-module.md) (structural references this document adapts), [critical-infrastructure-module.md](critical-infrastructure-module.md), [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md), [ADR-000](../adr/ADR-000-architecture-principles.md) through [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md).

> **On reuse:** EMLS is the third Defence Scheme module built against GridDefence's established pattern language, and the one that departs furthest from UFLS/UVLS's shape, because it solves a genuinely different problem: **manual, human-invoked** shedding, not automatic threshold-triggered shedding. Everywhere the underlying concern is the same regardless of trigger mechanism — version lifecycle, MW capture, audit, change reasons, Rule 3/4-equivalent ownership, the Cross-Scheme Compliance interface — this document reuses the established structure directly. Everywhere manual invocation genuinely changes the engineering problem — no threshold, no time delay, priority ordering instead of severity ordering, and a materially different judgment about pocket/island assignment and Rule 2 — this document diverges deliberately, with reasoning stated explicitly. §7.1 summarizes exactly which is which, now against both prior schemes.

---

## 1. Module Overview

Emergency Manual Load Shedding (EMLS) is a Defence Scheme module: the engineering system of record for the design, approval, versioning, and audit of the pre-planned, prioritized load-shedding scheme a system operator manually invokes during a declared grid emergency that automatic UFLS/UVLS response cannot, or should not, resolve on its own.

Unlike UFLS and UVLS, EMLS has **no automatic trigger**. There is no frequency or voltage threshold to cross, no relay armed to a physical quantity, and no time delay to coordinate — a human operator decides, in the moment, whether and how much to invoke. What EMLS's engineering design provides is not a trigger condition but a **priority order**: a pre-approved, ranked sequence of what to shed first, second, and so on, so that when an operator must act quickly under real emergency conditions, the decision of *what* has already been made carefully in advance, and only the decision of *whether/how much* remains theirs to make in the moment.

---

## 2. Purpose

To provide a single, versioned, auditable source of truth for the EMLS scheme's engineering design, so that:

- Every EMLS scheme version that has ever been in force is permanently reconstructable (CLAUDE.md §5.2) — precisely because this is the plan operators rely on during real emergencies, its governance rigor must be at least as strong as UFLS/UVLS's, not weaker, despite (indeed *because of*) its manual nature.
- Priority ordering is represented as what it actually is — a ranked sequence for human decision support — rather than forced into a threshold/stage shape that implies an automatic trigger that does not exist.
- Engineers designing a version get accurate, current recommended MW figures from PSS/E Integration, and (commonly, unlike UVLS) island analysis from Network Model, without either being mistaken for approved data.
- Exactly one EMLS scheme version governs the live grid at any moment.
- Cross-Scheme Compliance can check EMLS against UFLS, UVLS, and future schemes through the same interface shape every Defence Scheme module exposes.

---

## 3. Responsibilities

EMLS owns:

- ✓ EMLS scheme identity (`EmlsScheme`)
- ✓ EMLS scheme versions and their lifecycle
- ✓ EMLS priority groups (§7.2) — the manual-invocation analog of UFLS/UVLS's threshold-triggered stages
- ✓ Manual shed blocks, grouping direct assignments within a priority group
- ✓ Direct (substation-level) assignments
- ✓ Pocket/island-based assignments — a commonly-used mechanism for EMLS, not a rare one (§7.5)
- ✓ Approved MW values, once captured
- ✓ Human-entered change reasons
- ✓ Its own audit trail (`emls_audit_log`, CLAUDE.md A4)

---

## 4. Non-Responsibilities

EMLS does **not** own:

- ✗ Substation name, mnemonic, voltage level, region, state, owner, or coordinates — owned by the Substation Registry.
- ✗ Topology structure, load, or voltage/generation data — owned by PSS/E Integration.
- ✗ Connectivity graph construction or island/pocket detection — owned by Network Model.
- ✗ Critical-infrastructure classification — owned by Critical Infrastructure.
- ✗ Cross-scheme compliance checking logic (Rule 1, Rule 2) — owned by Cross-Scheme Compliance; EMLS exposes what it needs via a read-only service interface (§13).
- ✗ Physical equipment/relay master data — reserved for a future Equipment Registry; the same temporary free-text placeholder pattern applies.
- ✗ Identity, authentication, roles, or permissions — owned by IAM.
- ✗ **No frequency threshold, no voltage threshold, no time delay.** These are automatic-trigger concepts that do not apply to a manually-invoked scheme, and are deliberately absent from EMLS's data model rather than present-but-unused.
- ✗ UFLS or UVLS data, business rules, or assignments.
- ✗ **Real-time operator invocation and execution tracking — answering Question 10, explicitly out of scope.** This module is the engineering **design and record of intent**: which substations belong to which priority group, at what approved MW, under what version. It does not record "Operator X invoked Priority Group 2 at 14:32 on a specific date, under declared emergency Y" — that is real-time operational/SCADA-adjacent data, structurally analogous to how UFLS/UVLS exclude real-time relay execution from their own scope (CLAUDE.md §4 non-responsibility already established for both). EMLS's manual nature makes this boundary especially important to state explicitly, since "manual" could otherwise be mistaken to imply this module tracks manual actions — it does not (§17).

---

## 5. Owned Entities

| Entity | Description |
|---|---|
| `EmlsScheme` | The stable identity an EMLS scheme's versions belong to. |
| `EmlsSchemeVersion` | The versioned aggregate root, belonging to exactly one `EmlsScheme`. |
| `EmlsPriorityGroup` | An ordered tier of substations/load an operator may manually invoke for shedding — the EMLS analog of a UFLS/UVLS stage, with no threshold or time delay (§7.1–§7.3). |
| `EmlsShedBlock` | A named quantum of load defined within a priority group, grouping one or more direct assignments. |
| `EmlsDirectAssignment` | A direct, substation-level assignment within a shed block. |
| `EmlsPocketAssignment` | A topology-derived (island/"pocket") assignment within a priority group — a commonly-used mechanism for EMLS (§7.5), unlike UVLS. |
| `EmlsPocketAssignmentSubstation` | Normalized child of `EmlsPocketAssignment` — captured substation set and per-substation MW. |
| `EmlsChangeReason` | A curated, human-entered explanation of one changed assignment, required before a version leaves Draft. |
| `emls_audit_log` | EMLS's own audit trail (CLAUDE.md A4). |

---

## 6. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| Substation | Master Data (Substation Registry) | `substation_id` (UUID) only |
| `TopologyVersion`, `LoadSnapshot` | PSS/E Integration | `source_load_snapshot_id` — traceability pointer only |
| `IslandAnalysisResult`, `ManualOverride` | Network Model | `source_analysis_result_id`, `source_override_id` — traceability pointers only, used routinely (§7.5), unlike UVLS |
| User | Core Platform (IAM) | `user_id` (UUID) only, fallback `external_principal_id` + provider per [ADR-002](../adr/ADR-002-identity-and-access-management.md) |
| Role / Permission | Core Platform (IAM) | Not referenced by foreign key; authorization via IAM's service layer |

EMLS never stores substation metadata, topology structure, raw load/generation figures, connectivity graph/island-detection logic, or critical-asset classification.

---

## 7. Domain Model

```
EmlsScheme (1) ──── (many) EmlsSchemeVersion
EmlsSchemeVersion (1) ──── (many) EmlsPriorityGroup
EmlsPriorityGroup (1) ──── (many) EmlsShedBlock ──── (many) EmlsDirectAssignment
EmlsPriorityGroup (1) ──── (many) EmlsPocketAssignment ──── (many) EmlsPocketAssignmentSubstation
EmlsSchemeVersion (1) ──── (many) EmlsChangeReason

EmlsDirectAssignment           ──── references ───▶ Substation.substation_id        (Master Data, external)
EmlsPocketAssignmentSubstation ──── references ───▶ Substation.substation_id        (Master Data, external)
EmlsDirectAssignment           ──── traceability ─▶ LoadSnapshot.load_snapshot_id    (PSS/E Integration, external, optional)
EmlsPocketAssignment           ──── traceability ─▶ IslandAnalysisResult.analysis_result_id,
                                                     ManualOverride.override_id      (Network Model, external, optional)
EmlsSchemeVersion / EmlsPriorityGroup / assignments / change reasons
                                ──── references ───▶ User.user_id                   (Core Platform/IAM, external)
```

An `EmlsSchemeVersion` is the unit of approval and activation, identical in kind to UFLS/UVLS. No arrow points from EMLS's tables toward UFLS's, UVLS's, or Cross-Scheme Compliance's tables — that boundary is crossed only through service interfaces (§13).

### 7.1 How EMLS Differs from UFLS and UVLS

| Aspect | Shared structurally (identical pattern, reused as-is) | Different by design |
|---|---|---|
| Version lifecycle, immutability, auto-supersede | Identical to both UFLS and UVLS | — |
| MW capture mechanism | Identical to both | — |
| Audit trail, change-reason pattern | Identical to both | — |
| `getProtectedAssignments` interface shape | Identical to both (§13) | — |
| Rule 3/4-equivalent (version-internal overlap, IPP/LSS exclusion) | Owned identically, same mechanism | — |
| Automatic trigger (threshold, time delay) | — | **Absent entirely.** No frequency or voltage field, no `time_delay_ms` — replaced by `priority_order` (§7.2, §7.3) |
| Grouping terminology | — | "Priority Group," not "Stage" — deliberately named to avoid implying an automatic threshold trigger that does not exist (§7.2) |
| Pocket/island assignment usage | — | Commonly used, like UFLS — unlike UVLS's rare/edge-case treatment, for reasons specific to EMLS's broader emergency scope (§7.5) |
| Rule 2 (critical-infrastructure) severity | — | Deliberately **not** weakened relative to UFLS/UVLS despite manual invocation (§9, Question 4) — reasoning below |
| Real-time invocation tracking | — | Explicitly out of scope for all three schemes, but stated with particular emphasis here given EMLS's manual nature could otherwise mislead (§4) |

### 7.2 Priority Groups — Answering Questions 1 and 2

**EMLS uses "Priority Group," not "stage," "block," or "priority tier" as a standalone term** — "Priority Group" names the concept precisely (an ordered *group* of substations/load, ranked by *priority* of invocation) without borrowing "stage," which in UFLS/UVLS specifically connotes an automatically-triggered event at a measured threshold. Reusing "stage" for EMLS would misleadingly suggest a trigger condition exists. "Block" is reserved, as in UFLS/UVLS, for the grouping *within* a priority group (`EmlsShedBlock`), preserving that layer of the established hierarchy.

**How priority groups differ from UFLS/UVLS stages (Question 1):** a `UflsStage`/`UvlsStage` is defined by *what physical condition triggers it* (a frequency or voltage threshold) and *when, after that condition is met, it acts* (a time delay). An `EmlsPriorityGroup` has neither — it is defined purely by **where it sits in the invocation order** (`priority_order`, ascending — Priority Group 1 is invoked first, representing the least operationally consequential load an operator would shed before escalating; higher-numbered groups are invoked only as the emergency deepens and progressively more MW must be shed) and, optionally, **guidance for when a human should consider invoking it** (`invocation_guidance`, free text — e.g. "invoke only after Priority Groups 1–2 have been exhausted and system remains in a declared emergency state"). This guidance is descriptive, human-facing context, not a machine-evaluated trigger condition — it exists to inform operator judgment, not to replace it.

A `target_shed_mw` field is retained on `EmlsPriorityGroup`, identical in purpose to UFLS/UVLS's — a priority group still represents "if invoked, approximately this much MW would be shed," useful for planning and compliance-checking even without an automatic trigger.

### 7.3 Priority Ordering vs. Threshold Ordering

Because there is no physical quantity to compare, EMLS has no equivalent of UFLS/UVLS's threshold-monotonicity validation rule (frequency/voltage strictly decreasing as `stage_order` increases). EMLS requires only that `priority_order` values are **unique** within a version — an unambiguous invocation sequence — with no comparison against a measured quantity, since none exists (§9, §10).

### 7.4 Manual Shedding Priority Representation — Answering Question 5

Represented entirely through `priority_order` (the ranking) plus `invocation_guidance` (the human-readable context for when a group is operationally appropriate to invoke) on `EmlsPriorityGroup` — no threshold, no delay, no automatic classification. This is deliberately the simplest possible representation that still captures what actually matters for a manually-invoked scheme: an unambiguous order, and enough context for a human to exercise sound judgment about when to act.

### 7.5 Pocket/Island Assignment — Answering Question 7

**Pocket/island assignment is a commonly-used, primary-tier mechanism for EMLS, standing alongside direct assignment much as it does for UFLS — not demoted to a rare edge case as it is for UVLS.** The reasoning differs from UFLS's own justification but reaches a similar conclusion: EMLS's scope is not limited to frequency-balance emergencies the way UFLS is, nor to localized voltage-support emergencies the way UVLS is — it is invoked for *any* declared grid emergency an operator judges warrants manual load shedding, which routinely includes scenarios where **deliberately islanding a stressed section of the grid is itself the appropriate emergency response** (a classic emergency-operations technique to prevent cascading failure by controlled separation, rather than an incidental side effect an engineer must guard against, as it can be for UVLS's narrower voltage-support concern, §7.4 of [uvls-module.md](uvls-module.md)). Where used, `EmlsPocketAssignment` follows the exact same structure, capture semantics, and Network Model integration already established in [ufls-module.md](ufls-module.md) §7.5.

### 7.6 Approved MW Snapshot — Answering Question 6

**Structurally identical to [ufls-module.md](ufls-module.md) §7.6 and [uvls-module.md](uvls-module.md) §7.6, with no adaptation needed.** `approved_mw` is null while Draft/Under Review, captured exactly once at the Under Review → Approved transition, immutable thereafter, alongside a traceability pointer that is descriptive metadata only. MW capture semantics do not depend on how a scheme is triggered — automatic or manual makes no difference here.

### 7.7 Cross-Scheme Compliance Participation — Answering Questions 3 and 4

**Question 3 — should EMLS participate in Rule 1:** **Yes.** A substation locked into UFLS's or UVLS's protected automatic-response stages, if also freely available in an EMLS priority group, creates a genuine coordination risk: an operator under emergency pressure could manually shed a substation the system is simultaneously relying on for automatic frequency/voltage stability, without realizing the conflict. EMLS exposes `getProtectedAssignments` using the identical generic interface every scheme exposes (§13); the specific engineering judgment of *which* EMLS priority groups warrant an `is_protected` classification is EMLS's own configuration decision, likely to differ in typical *pattern* from UFLS/UVLS (fewer groups marked protected, given EMLS's broader and lower-frequency-of-use nature) but identical in *mechanism* — no special-casing on the Cross-Scheme Compliance side.

**Question 4 — should Rule 2 block or only warn for EMLS, given its manual nature:** **This document recommends against weakening Rule 2 for EMLS — a `Prohibited` critical asset should hard-block at Approval/Activation exactly as it does for UFLS/UVLS**, not merely warn. The reasoning: EMLS's manual invocation adds a *second*, complementary layer of protection (human judgment at the moment of the actual emergency) — it does not replace the *first* layer (rigorous design-time validation that a genuinely life-safety-critical substation is never even made available for an operator to select). If anything, the case for design-time rigor is *stronger* here, not weaker: an operator making rapid decisions under severe, real-time emergency pressure is not a reliable substitute for careful upfront engineering review, and the stakes of an operator mistakenly shedding a `Prohibited` asset during a genuine crisis are at least as high as an equivalent UFLS/UVLS mistake, arguably higher given the compressed decision time. `ConditionallyAllowed` assets, by contrast, are arguably **more naturally suited** to EMLS than to UFLS/UVLS: a human operator, at the moment of invocation, is exactly positioned to evaluate whether a stated condition (e.g. "confirmed alternate supply available") is actually met — the `condition_description` becomes genuinely actionable real-time guidance, not just a design-time acknowledgment. This severity-vs-manual-nature tradeoff is a genuine policy question, not a purely technical one, and is flagged for explicit Project Owner ratification (closing summary) rather than treated as settled by this document alone.

---

## 8. Lifecycle / State Model

Every `EmlsSchemeVersion` follows the Canonical Version Lifecycle (CLAUDE.md **A3**) without exception, identical to [ufls-module.md](ufls-module.md) §8 and [uvls-module.md](uvls-module.md) §8:

```
Draft → Under Review → Approved → Active → Superseded → Archived
```

- **Only one Active `EmlsSchemeVersion` may exist per `EmlsScheme` at any time.**
- **Activating a new version automatically supersedes the previous Active version.**
- **Approved and Active versions are immutable.**
- **Corrections always create a new version.**
- Both halves of an activation are recorded as a single correlated audit event (§14).

**Manual invocation at execution time does not imply casual design-time governance.** EMLS's version lifecycle carries exactly the same rigor as UFLS/UVLS's, precisely because it is the plan operators fall back on during real emergencies — arguably the version most in need of careful, unhurried design-time review, since it is least likely to be revisited under the pressure of the moment it is actually used.

**`Superseded → Active` reactivation remains an open question**, carried forward unresolved from [ufls-module.md](ufls-module.md)/[uvls-module.md](uvls-module.md) — see closing summary.

---

## 9. Business Rules

1. Only one `EmlsSchemeVersion` may hold status `Active` per `EmlsScheme` at any time.
2. Activating a version supersedes the current Active version automatically and atomically.
3. Approved and Active versions are immutable; any change requires a new version.
4. Within a scheme version, `priority_order` values are unique — there is no monotonicity-against-a-physical-quantity rule, since no threshold exists to compare against (§7.3).
5. A shed block belongs to exactly one priority group; a direct assignment belongs to exactly one shed block and references exactly one substation. A pocket assignment belongs to exactly one priority group.
6. A substation may be referenced by multiple direct assignments, and may appear in multiple pocket assignments, within the same version, across different priority groups.
7. **A substation may not simultaneously be assigned via a direct assignment and appear in any pocket assignment's substation set within the same scheme version** — the Rule 3 equivalent, version-internal, owned fully by EMLS.
8. **A substation whose Substation Registry `grid_owner` classification is Independent Power Producer, Large Scale Solar, or an equivalent excluded ownership classification may not be assigned via any direct or pocket assignment** — the Rule 4 equivalent, owned fully by EMLS.
9. Recommended MW (Draft/Under Review) and Approved MW are structurally distinct; `approved_mw` is set only at the Under Review → Approved transition and never recomputed afterward.
10. A traceability pointer to a `LoadSnapshot`, `IslandAnalysisResult`, or `ManualOverride` is descriptive metadata only.
11. Engineering approval actions require an authenticated, named IAM user.
12. New assignments must reference a substation whose current `operational_status` is not Decommissioned or Retired; not retroactive.
13. Deleting a priority group, shed block, or assignment is only possible while the owning version is in Draft.
14. A `EmlsChangeReason` row is required for every assignment that is new, revised, or removed relative to the comparison version, before the version may transition Draft → Under Review.
15. EMLS's own tables contain no foreign key into UFLS's, UVLS's, or any future scheme module's schema.
16. EMLS must call Cross-Scheme Compliance's `checkCompliance` at Submit for Review, Approval, and Activation, obeying its returned `blocks_transition` value exactly — **including for `Prohibited`-severity Rule 2 findings**, which hard-block EMLS exactly as they do UFLS/UVLS (§7.7, Question 4).
17. A priority group may be marked `is_protected` for Rule 1 purposes as engineering policy configuration; the mechanism is identical to UFLS/UVLS, and the specific classification per group is EMLS's own configuration decision (§7.7, Question 3).
18. This module records no real-time invocation or execution events — it is a design-time record of intent only (§4, Question 10).

---

## 10. Validation Rules

- `priority_order` must be a positive integer, unique within its scheme version.
- **No threshold-range or monotonicity validation applies** — there is no physical quantity to validate against (§7.3, §9 rule 4), unlike UFLS's `frequency_threshold_hz` range check or UVLS's region-scoped `voltage_threshold_pu` ordering check.
- A direct assignment's `substation_id` must reference an existing Substation Registry record.
- A pocket assignment's `source_analysis_result_id` must reference an existing Network Model `IslandAnalysisResult`; `source_override_id`, if present, must reference an `Active` `ManualOverride` against that same result.
- `approved_mw` must be null while a version is Draft or Under Review, and non-null for every assignment before a version may transition Under Review → Approved.
- Rule 7 (direct/pocket overlap) and Rule 8 (excluded ownership) are validated at assignment-creation time and re-validated at the Draft → Under Review transition.
- A scheme version cannot be submitted for review with zero priority groups, or a priority group with zero assignments (direct or pocket).
- A `EmlsChangeReason` must have a non-empty reason.

---

## 11. Database Design (Concept)

Conceptual only — no migrations are defined here.

| Table (conceptual) | Key columns (conceptual) | Notes |
|---|---|---|
| `emls_scheme` | `emls_scheme_id` (UUID PK), `name`, `description`, `created_at` | Stable identity anchor. |
| `emls_scheme_version` | `emls_scheme_version_id` (UUID PK), `emls_scheme_id` (FK), `version_label`, `status`, `compared_to_version_id` (nullable, self-referencing), `superseded_by_version_id` (nullable, self-referencing), `created_by_user_id`, `updated_by_user_id`, `approved_by_user_id` (nullable), `approved_at` (nullable), `activated_by_user_id` (nullable), `activated_at` (nullable), `created_at`, `updated_at` | Only one row per `emls_scheme_id` may hold `status = 'Active'`. |
| `emls_priority_group` | `emls_priority_group_id` (UUID PK), `emls_scheme_version_id` (FK), `priority_order`, `label`, `target_shed_mw` (nullable), `invocation_guidance` (text), `is_protected` (boolean, for Rule 1, §9 rule 17) | Unique on (`emls_scheme_version_id`, `priority_order`). **No** `frequency_threshold_hz`/`voltage_threshold_pu`/`time_delay_ms` columns — deliberately absent, not nulled-out (§7.2). |
| `emls_shed_block` | `emls_shed_block_id` (UUID PK), `emls_priority_group_id` (FK), `block_label`, `target_mw` (nullable) | |
| `emls_direct_assignment` | `emls_direct_assignment_id` (UUID PK), `emls_shed_block_id` (FK), `substation_id` (FK, external), `equipment_reference` (text, temporary placeholder), `approved_mw` (nullable), `source_load_snapshot_id` (FK, external, nullable), `remarks` | Identical shape to `ufls_direct_assignment`/`uvls_direct_assignment`. |
| `emls_pocket_assignment` | `emls_pocket_assignment_id` (UUID PK), `emls_priority_group_id` (FK), `source_analysis_result_id` (FK, external), `source_override_id` (FK, external, nullable), `approved_total_mw` (nullable) | Identical shape to UFLS's; expected to be populated routinely, unlike UVLS's (§7.5). |
| `emls_pocket_assignment_substation` | `id` (BIGINT PK), `emls_pocket_assignment_id` (FK), `substation_id` (FK, external), `approved_mw` (nullable) | Normalized, not JSON. |
| `emls_change_reason` | `emls_change_reason_id` (UUID PK), `emls_scheme_version_id` (FK), `emls_direct_assignment_id` (FK, external nullable), `emls_pocket_assignment_id` (FK, external nullable), `change_type`, `reason`, `created_by_user_id`, `created_at` | Exactly one of the two assignment FKs set per row. |
| `emls_audit_log` | `log_id` (BIGINT PK), `entity_type`, `entity_id`, `field_name`, `old_value`, `new_value`, `changed_at`, `changed_by_user_id`, `change_reason` | Owned per CLAUDE.md A4. |

**Cross-module constraints:** all foreign keys into `substation`, `load_snapshot`, `island_analysis_result`/`manual_override`, and `user` are `ON DELETE RESTRICT`. EMLS tables are written exclusively by EMLS's own service layer.

---

## 12. API Contract (Concept)

APIs are external/UI-facing contracts (CLAUDE.md §13, A9); conceptual resource shape only, structurally identical to [ufls-module.md](ufls-module.md) §12/[uvls-module.md](uvls-module.md) §12:

- `emls-schemes`, `emls-scheme-versions`, nested `priority-groups`/`shed-blocks`/`direct-assignments`/`pocket-assignments`, `change-reasons`, and lifecycle transition actions.
- `.../priority-groups/{id}/recommended` — read-only, resolved live against PSS/E Integration/Network Model, explicitly labeled as advisory, never conflated with `approved_mw`. No threshold/voltage field exists to include here, unlike UVLS's equivalent endpoint.
- No endpoint accepts or returns a threshold or time-delay value — their absence is enforced by the contract, not merely by convention.

**Contract requirements and data contracts:** identical to [ufls-module.md](ufls-module.md) §12 (CLAUDE.md A9, A6).

---

## 13. Service Interfaces

Per CLAUDE.md A1:

**EMLS exposes, for other modules to consume:**
- A read-only query interface for the current Active version and its structure.
- A read-only interface for a substation's EMLS assignment history across versions.
- **`getProtectedAssignments(scope)` — answering Question 8.** Identical contract shape to UFLS's and UVLS's interface of the same name — a hard requirement of Cross-Scheme Compliance's generic fan-out (§7.7, Question 3), not a stylistic choice.

**EMLS consumes, from other modules' service layers — never their repositories directly:**
- From Substation Registry: existence/validity checks, `grid_owner` lookups (Rule 8), read-enrichment.
- From PSS/E Integration: recommended-MW resolution, during Draft/Under Review and once more at Approval to capture `approved_mw`.
- From Network Model: `analyzeIsland`/`getEffectiveIsland`, used routinely (§7.5), not just occasionally.
- From Core Platform (IAM): authorization checks, user lookups.
- **From Cross-Scheme Compliance:** `checkCompliance(subject_scheme='EMLS', subject_version_id, comparison_scope, checkpoint, triggered_by_user_id)`, called at Submit for Review, Approval, and Activation, obeying `blocks_transition` exactly, with no weakening for `Prohibited`-severity Rule 2 findings (§7.7, §9 rule 16). EMLS stores only the returned `check_run_id` as a traceability pointer.

EMLS never calls another module's repository directly, and no other module writes to an EMLS-owned table, per CLAUDE.md A1 and [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md).

---

## 14. Audit Requirements

Per CLAUDE.md §5.4 and A4, structurally identical to [ufls-module.md](ufls-module.md) §14:

- Every create, update, and delete of a priority group, shed block, or assignment is recorded with who, when, what changed, and why.
- Lifecycle state transitions, including activation's correlated dual event, are first-class audit events.
- MW capture at Approval is audited explicitly, recording the source `load_snapshot_id`/`analysis_result_id`/`override_id`.
- Compliance check outcomes are audited at Approval and Activation, including the specific case of a `Prohibited`-severity Rule 2 block, which — given EMLS's emergency-planning stakes — warrants prominent visibility in any audit review, not just routine logging.
- `EmlsChangeReason` entries are part of the durable engineering record, distinct from the technical field-diff audit log.
- Audit history is append-only and never modified; audit log access is itself access-controlled.

---

## 15. Security Considerations

Identical role structure to [ufls-module.md](ufls-module.md) §15 and [uvls-module.md](uvls-module.md) §15 — **Editor**, **Reviewer**, **Approver**, **Activator** — with one strengthened recommendation specific to EMLS:

- All engineering approval actions require an authenticated, named IAM user.
- **Segregation of duties (Draft editor ≠ sole Approver) is recommended with particular emphasis for EMLS.** Because this scheme is the plan operators execute during genuine emergencies with limited opportunity for real-time correction, an unchecked single-author approval carries especially high consequence — this document recommends this be weighted more heavily than the equivalent "recommended, not mandated" guidance already given for UFLS/UVLS, though it remains an IAM role-configuration policy decision, not a hard architectural constraint imposed here.
- Requesting a recommendation requires no elevated permission beyond Editor.
- Read access to Active/Approved/Superseded/Archived versions is broader than write access; Draft/Under Review content may be restricted to the drafting/reviewing team.
- All GridDefence engineering data is sensitive by default; TLS required outside local development.

---

## 16. Testing Requirements

Per CLAUDE.md §18 and A11, in priority order:

1. **Business rule tests** — single-Active-version-per-scheme enforcement; atomic activate-and-supersede; immutability of Approved/Active versions; Rule 7/Rule 8 enforcement; **priority-order uniqueness (not monotonicity)** — verifying no threshold-comparison logic is accidentally applied where none should exist; MW capture-at-approval correctness; **explicit confirmation that a `Prohibited`-severity Rule 2 finding hard-blocks EMLS exactly as it does UFLS/UVLS**, given the deliberate decision not to weaken this (§7.7, §9 rule 16) — this is the single most important business-rule test in this module, precisely because it is the one a future maintainer might be tempted to relax "because EMLS is manual."
2. **Engineering calculation / validation tests** — recommended-MW resolution correctness; pocket-assignment analysis correctness, exercised more heavily than for UVLS given routine usage (§7.5); change-reason-required-before-review enforcement.
3. **API contract tests** — request/response schema conformance, confirming no threshold/delay fields are exposed anywhere in the contract; authorization enforcement.
4. **Database migration tests** — required once actual migrations are authored.
5. **UI behaviour tests** — required once an EMLS frontend exists; must confirm the frontend displays recommended MW as advisory only, and presents `invocation_guidance` as human decision-support text, never as a machine-evaluated condition (CLAUDE.md A12).

---

## 17. Future Extensions

- **Real-time emergency invocation tracking** (§4, Question 10) — a future, explicitly separate operational/SCADA-adjacent capability that would record actual operator invocation events (who invoked which priority group, when, under what declared emergency), referencing this module's Active version and priority groups by ID, read-only. Not designed here; this module remains the engineering design record only.
- **Operator-facing condition evaluation tooling** — surfacing `condition_description` from `ConditionallyAllowed` critical assets (via Critical Infrastructure, through Cross-Scheme Compliance's Rule 2 findings) as actionable, real-time guidance at the moment of invocation, building on the observation in §7.7 that EMLS is unusually well-suited to this pattern.
- **Controlled-islanding-specific planning tools**, given EMLS's routine reliance on pocket/island assignment (§7.5) — potential future Network Model extensions for scenario planning around deliberate emergency separation.
- Equipment Registry migration, PSS/E simulation export, shared Rule 7/8 validation utility, adaptive/simulation-informed design — identical Future Extensions already listed in [ufls-module.md](ufls-module.md) §17 and [uvls-module.md](uvls-module.md) §17, now with three consuming schemes making the shared-utility extension increasingly worthwhile.

---

## 18. Risks and Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| A future maintainer weakens Rule 2 enforcement for EMLS, reasoning "it's manual, so a human will catch it" | Reintroduces exactly the risk §7.7's deliberate decision exists to prevent | Treat the "`Prohibited` always hard-blocks EMLS" business rule test (§16) as non-negotiable; require any change to this behaviour to go through the Project Owner ratification this document already recommends (closing summary), not a routine code change |
| The design-time-rigor-vs-real-time-flexibility tradeoff in Rule 2 (§7.7, Question 4) is a genuine values decision, not purely a technical one | If left as only this document's recommendation, it could be silently overridden later without the same level of consideration | Recommend explicit Project Owner ratification, formalized via ADR (closing summary) |
| `getProtectedAssignments`'s `is_protected` classification is now explicitly modeled as a stored column here (`emls_priority_group.is_protected`), but was only described as response-shape metadata, not a stored field, in [ufls-module.md](ufls-module.md)'s and [uvls-module.md](uvls-module.md)'s own database design sections | A future implementer could build UFLS/UVLS without a comparable stored column, creating an inconsistency across the three scheme modules that share this interface | Recommend a follow-up consistency pass adding an equivalent stored `is_protected` column to `ufls_stage` and `uvls_stage`, so all three Defence Scheme modules represent this classification the same concrete way, not just the same interface shape |
| EMLS's broader "any declared emergency" scope makes its priority groups inherently harder to validate mechanically than UFLS/UVLS's threshold-defined stages | Priority groups could be poorly specified (vague `invocation_guidance`) without any automatic check catching it, since there is no physical quantity to validate | Recommend `invocation_guidance` be treated as a required (not merely optional) field in practice, even though this document does not make it a hard validation rule, given its outsized importance for a manually-judged scheme |
| Pocket/island assignment being routine for EMLS (unlike UVLS) could be misapplied if engineers assume uniform treatment across all three scheme modules | An engineer moving from UVLS design work to EMLS design work could under- or over-use pocket assignment based on the wrong scheme's convention | Recommend this differentiated treatment be made explicit in engineer-facing documentation/training, not left only to this architecture document |

---

## MVP Behaviours Preserved

- The Version → Priority-Group → Assignment hierarchy shape (adapted terminology), with auto-supersede-on-activation — confirmed to generalize to a third scheme with a genuinely different trigger mechanism.
- EMLS's exemption from requiring a threshold setting — the legacy MVP's `LoadSheddingStage.clean()` already exempted EMLS stages from the "must have ≥1 setting" rule; GridDefence carries this forward and makes it structural (no threshold column exists at all) rather than an exemption on an otherwise-shared model.
- Rule 3 (direct/pocket overlap) and Rule 4 (excluded ownership) as version-internal, EMLS-owned business rules.

## MVP Behaviours Redesigned

- **"Stage" is renamed to "Priority Group."** The legacy MVP reused the same `LoadSheddingStage` model for EMLS as for UFLS/UVLS, with `frequency_threshold_hz`/`time_delay_ms` fields simply left unused/exempted for EMLS rows. GridDefence makes this an explicitly different, separately-named concept with no unused fields, reflecting that EMLS's grouping is fundamentally a priority ranking, not a threshold trigger, structurally rather than by convention.
- **The MVP's default EMLS alert configuration had empty `protected_stages`/`critical_restricted_stages` lists** (per the Codebase Discovery Report's `LoadSheddingAlertConfig.get_or_create_defaults()` finding — UFLS defaulted to `[1,2,3]`, EMLS to `[]`), effectively opting EMLS out of Rule 1/Rule 2 checking by default. **This default is redesigned here: EMLS participates in Cross-Scheme Compliance's Rule 1/Rule 2 mechanism structurally, using the identical interface and enforcement as UFLS/UVLS** (§7.7). Only the *content* of which priority groups are marked protected may, in practice, still end up sparse for EMLS's lower tiers — the *mechanism* is never opted out.
- MW treatment: recommended-during-Draft vs. captured-at-Approval, identical redesign to UFLS/UVLS's own departure from the MVP's live-cached MW model.
- Pocket/island assignment treatment is now differentiated per scheme based on genuine engineering reasoning (common for UFLS and EMLS, rare for UVLS), rather than uniformly available as the MVP modeled it for all three scheme types without distinction.

## MVP Behaviours Discarded

- The combined topology+load snapshot model — already discarded at the PSS/E Integration layer, reaffirmed here.
- JSON-blob storage of isolated/manual substation sets — replaced by normalized, FK-enforced child tables.
- Treating EMLS as structurally identical to UFLS/UVLS via a shared table with unused threshold fields — superseded by EMLS being a fully independent bounded context with a data model that has no threshold concept to begin with, not one that simply ignores it.

## Architectural Decisions Still Requiring an ADR

1. **`Superseded → Active` reactivation** (carried forward, unresolved, from [ufls-module.md](ufls-module.md)/[uvls-module.md](uvls-module.md)) — affects every versioned module including EMLS; still requires its own ADR amending CLAUDE.md A3.
2. **Whether Rule 2's "no weakening for manually-invoked schemes" stance (§7.7, Question 4) should be formally ratified as platform-wide policy.** This document recommends against weakening it, but the underlying tradeoff — design-time rigor vs. real-time operational flexibility during a genuine emergency — is a values decision with real operational consequences, and deserves explicit Project Owner sign-off via ADR rather than resting solely on this module document's recommendation.
3. **Whether and how real-time emergency invocation tracking (§4, §17, Question 10) should eventually become its own module**, and how it would reference EMLS's version/priority-group data without violating this module's own read-only-reference boundary — not urgent today, but a genuine future architectural decision, similar in kind to how Critical Infrastructure and Equipment Registry were flagged as needed before they were built.
