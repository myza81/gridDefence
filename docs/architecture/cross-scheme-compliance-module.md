# Cross-Scheme Compliance Module Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document follows the Canonical Module Architecture Document Template (CLAUDE.md **A8**).

Related documents: [system-overview.md](system-overview.md), [domain-model.md](domain-model.md), [ufls-module.md](ufls-module.md), [critical-infrastructure-module.md](critical-infrastructure-module.md), [ADR-000](../adr/ADR-000-architecture-principles.md), [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md), [ADR-002](../adr/ADR-002-identity-and-access-management.md), [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) (the decision this document formalizes).

---

## 1. Module Overview

Cross-Scheme Compliance is the module that answers questions no single Defence Scheme module can answer about itself: does this UFLS version conflict with UVLS's or EMLS's current protected assignments (Rule 1)? Does it expose a critical-infrastructure substation to a restricted stage without an accepted exception (Rule 2)? It owns no scheme data and no critical-asset data — it calls each source module's read-only service interface, cross-references the results, and produces its own durable, auditable check records.

This is the module [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) decided to build, now that both of its data dependencies — UFLS's `getProtectedAssignments()` ([ufls-module.md](ufls-module.md) §13) and Critical Infrastructure's `getCriticalityForSubstations()` ([critical-infrastructure-module.md](critical-infrastructure-module.md) §13) — are concretely defined.

---

## 2. Purpose

To provide a single, reusable cross-scheme validation capability such that:

- Every Defence Scheme module can check itself against every other scheme's current state without ever depending on their internal data.
- A version cannot become Approved or Active while violating a `block`-mode rule, while still allowing engineers room to iterate during Draft.
- A version's compliance state at the moment of a past decision remains permanently reconstructable — a compliance check is a historical fact, not a live, ever-changing view.
- Critical Infrastructure's per-asset restriction policy ([critical-infrastructure-module.md](critical-infrastructure-module.md) §7.4) is honored precisely, not flattened into a single global severity.
- Dashboard and future audit tooling can query compliance history and current state without any gating side effect.

---

## 3. Responsibilities

Cross-Scheme Compliance owns:

- ✓ Cross-scheme compliance rules (`ComplianceRuleConfig`)
- ✓ `ComplianceCheckRun`
- ✓ `ComplianceFinding`
- ✓ Validation orchestration across UFLS, UVLS, EMLS, and future Defence Scheme modules
- ✓ Rule execution timing (which checkpoints exist, and how each one affects blocking behaviour — §8, §9)
- ✓ The compliance result lifecycle (§8)
- ✓ Dashboard-readable compliance summaries (a read model over its own data, §13)
- ✓ Its own audit trail (`compliance_audit_log`, CLAUDE.md A4)

---

## 4. Non-Responsibilities

Cross-Scheme Compliance does **not** own:

- ✗ UFLS, UVLS, or EMLS assignments, stages, or scheme data of any kind.
- ✗ Critical-infrastructure classification data — owned by Critical Infrastructure; this module only consumes it.
- ✗ Substation identity or metadata — owned by Substation Registry; referenced here **only for display/reference resolution** (resolving a `substation_id` to a human-readable name/mnemonic in a finding description), never for validation logic itself.
- ✗ Deciding *whether* to attempt a lifecycle transition — that remains each scheme module's own decision; this module only tells the caller whether the transition is compliant and, per its response, whether it must be blocked.
- ✗ Identity, authentication, or authorization — owned by IAM.

**This module must never directly query a scheme module's repository, and must never write to a scheme module's tables.** All access to scheme data is exclusively through the source module's own service interface (CLAUDE.md A1, [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md)).

---

## 5. Owned Entities

| Entity | Description |
|---|---|
| `ComplianceRuleConfig` | One row per known cross-scheme rule (today: Rule 1 — cross-scheme overlap; Rule 2 — critical-infrastructure protection), carrying an `enforcement_mode`. |
| `ComplianceCheckRun` | One immutable record per executed check, pinned to the exact subject version and comparison scope (which versions of which other schemes were consulted) at the moment it ran. |
| `ComplianceCheckRunSchemeVersion` | Normalized child of `ComplianceCheckRun` — records every scheme version actually consulted during the run (subject and comparison scope alike), for full reproducibility. |
| `ComplianceFinding` | One row per issue actually found in a run — a clean run produces zero findings, not a "clean" finding row. |
| `compliance_audit_log` | This module's own audit trail (CLAUDE.md A4). |

**Design note — `ComplianceRuleConfig`'s primary key is a stable rule code, not a freely-user-created UUID.** The set of rules this module can evaluate is defined by what its own service layer implements (you cannot add "Rule 5" through an admin screen without code supporting it) — the same reasoning already applied to `Permission` in IAM ([ADR-002](../adr/ADR-002-identity-and-access-management.md)) and `CriticalityLevel` in [critical-infrastructure-module.md](critical-infrastructure-module.md) §5. Only its `enforcement_mode` column is administratively mutable and audited.

---

## 6. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| `UflsSchemeVersion` (and future `UvlsSchemeVersion`, `EmlsSchemeVersion`) | The respective scheme module | Traceability FK on `ComplianceCheckRunSchemeVersion` — descriptive record of what was checked, never a live dependency, `ON DELETE RESTRICT` |
| Substation | Master Data (Substation Registry) | `substation_id` (UUID) on `ComplianceFinding`, resolved at display time only (§4) |
| Critical asset classification | Critical Infrastructure | Not stored by FK — a `ComplianceFinding`'s severity and description are computed from a live call to `getCriticalityForSubstations` at check time (§9), then frozen into the finding's own fields; no ongoing reference is kept |
| User | Core Platform (IAM) | `user_id` (UUID) on `ComplianceCheckRun.triggered_by_user_id` and audit attribution; fallback `external_principal_id` + provider per [ADR-002](../adr/ADR-002-identity-and-access-management.md) |

---

## 7. Domain Model

```
ComplianceRuleConfig (owned; small, code-defined catalog)

ComplianceCheckRun (1) ──── (many) ComplianceCheckRunSchemeVersion ──── traceability ──▶ UflsSchemeVersion / UvlsSchemeVersion / EmlsSchemeVersion (external)
ComplianceCheckRun (1) ──── (many) ComplianceFinding ──── references ──▶ Substation.substation_id (external, display only)
ComplianceCheckRun / ComplianceRuleConfig ──── references ──▶ User.user_id (external)
```

**No arrow points from this module's owned tables toward any scheme module's stage/assignment tables** — only toward each scheme's **version** table, and only as a traceability pointer. This mirrors the decoupling principle already established in [network-model-module.md](network-model-module.md) §9 rule 8 and reaffirmed in [critical-infrastructure-module.md](critical-infrastructure-module.md) §9 rule 4.

---

## 8. Lifecycle / State Model

`ComplianceRuleConfig` is not governed by the Canonical Version Lifecycle (CLAUDE.md A3) — it is versioned engineering parameter configuration (CLAUDE.md A7) that takes effect immediately upon change, fully audited, the same justification already used for Critical Infrastructure's `restriction_type` ([critical-infrastructure-module.md](critical-infrastructure-module.md) §8).

`ComplianceCheckRun` follows a lightweight, non-A3 lifecycle:

```
Running → Completed | Failed
```

Once `Completed`, a run and its findings are **immutable and permanent** — this is a deliberate design choice, not an implementation detail (§9, §11).

**Whether compliance findings are snapshots or live views — answered explicitly:** every `ComplianceCheckRun`/`ComplianceFinding` created at a **gating checkpoint** (Submit for Review, Approval, Activation) or by an explicit ad hoc request is a **permanent, immutable snapshot** of what was found at that exact moment, against the exact scheme versions recorded in `ComplianceCheckRunSchemeVersion`. It is never recomputed in place, never updated as underlying scheme or criticality data changes later, and never deleted. This is what makes a past Approval decision permanently explainable.

**Draft-time advisory checks are the one exception, and are deliberately *not* persisted at all.** Running a full `ComplianceCheckRun` on every keystroke-adjacent edit during Draft would create unbounded low-value historical noise — the same reasoning already applied to why Network Model doesn't eagerly recompute every historical cut-set ([network-model-module.md](network-model-module.md) §8.4). Draft-time checks are computed live, on demand, and discarded — mirroring exactly how UFLS's own recommended MW is live and unpersisted during Draft ([ufls-module.md](ufls-module.md) §7.6).

---

## 9. Business Rules

1. Every gating check (Submit for Review, Approval, Activation) produces a permanent, immutable `ComplianceCheckRun`; Draft-time advisory checks do not persist anything (§8).
2. **Validation timing and blocking behaviour are checkpoint-driven, and this module — not the calling scheme module — is the single source of truth for whether a given outcome blocks a transition:**
   - **Draft** — always advisory; never blocks, regardless of `enforcement_mode`.
   - **Submit for Review** — mandatory, recorded; never hard-blocks, regardless of `enforcement_mode` (content is not yet frozen; this checkpoint exists to surface findings to reviewers).
   - **Approval** — mandatory, recorded; **hard-blocks** if any finding resolves to `block` severity.
   - **Activation** — mandatory, recorded, **always re-run even if the same version passed at Approval** (state elsewhere may have changed in the interval, per [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)); hard-blocks under the same condition.
   - **Dashboard / ad hoc audit** — never blocks, always available.
3. `ComplianceRuleConfig.enforcement_mode` is one of `Disabled` (rule not evaluated at all), `Warn`, or `Block` — the default/fallback severity for a finding that has no more specific per-finding severity source.
4. **Rule 2 findings derive their actual severity from the specific `CriticalAsset`'s `restriction_type`, not from `ComplianceRuleConfig` alone** (§ Rule 2 algorithm, below): `Prohibited` always yields a `Block`-severity finding regardless of Rule 2's configured `enforcement_mode` (unless Rule 2 is `Disabled` entirely); `ConditionallyAllowed` yields a `Warn`-severity finding carrying the asset's `condition_description`; `Unrestricted` yields no finding. `ComplianceRuleConfig`'s `enforcement_mode` for Rule 2 acts as a master switch and a fallback for substations Critical Infrastructure has not classified — it does not override a specific asset's own restriction policy.
5. Rule 1 findings, having no per-asset analog, use `ComplianceRuleConfig`'s `enforcement_mode` directly as their severity.
6. A `ComplianceFinding` is immutable once created; correcting the underlying issue and re-checking produces a new `ComplianceCheckRun` with fewer or no findings — the original run's findings remain in the historical record (CLAUDE.md §5.2).
7. This module's own tables contain no foreign key into any scheme module's stage/assignment-level tables, or into Critical Infrastructure's asset tables — only into scheme **version** tables, as traceability (§6, §7).
8. This module never queries a scheme module's repository directly and never writes to a scheme module's tables — every cross-module read is a service-interface call (CLAUDE.md A1).
9. A calling scheme module records a `compliance_check_run_id` traceability pointer in its own audit log at Approval and Activation, and — if it proceeds despite a `Warn`-severity finding — a mandatory acknowledgment reason, per [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)'s Audit Requirements.
10. Service-interface implementations this module calls (`getProtectedAssignments`, `getCriticalityForSubstations`) must be pure, side-effect-free reads that never themselves call back into this module or any other module that could create a re-entrant call chain (§ Avoiding Circular Dependencies, below) — this is a hard architectural constraint, not a style preference.

---

## 10. Validation Rules

- A `ComplianceCheckRun` must record at least the subject scheme version and, unless the comparison scope is legitimately empty (e.g. only one Defence Scheme module exists so far), at least one comparison scheme version.
- `ComplianceRuleConfig.enforcement_mode` must be one of `Disabled`, `Warn`, `Block`.
- A `ComplianceFinding`'s `substation_id` must reference an existing Substation Registry record (resolved for display only, §4).
- A `ComplianceFinding`'s severity must be `Warn` or `Block` (a finding, by definition, is never `Disabled` — a disabled rule produces no findings at all, per §9 rule 3).
- `ComplianceCheckRun.status` transitions only `Running → Completed` or `Running → Failed`; a `Failed` run (e.g. a downstream service call errored) produces no findings and, per §9 rule 2, is treated as **not passing** for blocking purposes at Approval/Activation — an inability to check compliance must never be silently treated as compliant.

---

## 11. Database Design (Concept)

Conceptual only — no migrations are defined here.

| Table (conceptual) | Key columns (conceptual) | Notes |
|---|---|---|
| `compliance_rule_config` | `rule_id` (stable code PK, e.g. `rule_1_cross_scheme_overlap`), `label`, `enforcement_mode`, `updated_by_user_id`, `updated_at` | Code-defined catalog (§5 design note). |
| `compliance_check_run` | `check_run_id` (UUID PK), `subject_scheme` (enum: UFLS \| UVLS \| EMLS \| ...), `subject_scheme_version_id`, `checkpoint` (Draft-not-persisted excluded; SubmitForReview \| Approval \| Activation \| AdHoc), `status`, `triggered_by_user_id`, `started_at`, `completed_at` | Immutable once `Completed`/`Failed`. |
| `compliance_check_run_scheme_version` | `id` (BIGINT PK), `check_run_id` (FK), `scheme_name`, `scheme_version_id` | One row per scheme version consulted, including the subject itself, for full reproducibility (§5). |
| `compliance_finding` | `finding_id` (UUID PK), `check_run_id` (FK), `rule_id` (FK), `substation_id` (FK, external, display-only), `severity`, `description`, `context` (JSON — descriptive labels: involved scheme names, stage labels, resolved at check time), `condition_description` (nullable, copied from the source `CriticalAsset` at check time for Rule 2 findings) | `context` is JSON deliberately, not normalized: it is descriptive display metadata, not a relationship requiring referential integrity — distinct from the substation-set normalization decisions made in [network-model-module.md](network-model-module.md) §5 and [ufls-module.md](ufls-module.md) §5, where FK enforcement over a *set of substations* mattered. Here there is no set to enforce integrity over, only free-form descriptive text. |
| `compliance_audit_log` | `log_id` (BIGINT PK), `entity_type`, `entity_id`, `field_name`, `old_value`, `new_value`, `changed_at`, `changed_by_user_id`, `change_reason` | Owned per CLAUDE.md A4. |

All foreign keys into scheme version tables, `substation`, and `user` are `ON DELETE RESTRICT`. Tables are written exclusively through this module's own service layer (CLAUDE.md A1, [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md)).

---

## 12. API Contract (Concept)

APIs are external/UI-facing contracts (CLAUDE.md §13, A9); conceptual resource shape only.

- `compliance-rule-configs` — read (broad), update (admin-tier only, §15).
- `compliance-check-runs` — list/retrieve historical runs, with filters (by scheme, by version, by date range); nested `findings`.
- `compliance-checks` (POST) — trigger an ad hoc, non-gating check (Dashboard/audit use); returns a `ComplianceCheckRun` immediately (or a job reference if run asynchronously, §17).
- `compliance-summary` — a read-only, aggregated Dashboard-facing view (current-state finding counts by rule/severity/scheme), the concrete implementation of "Dashboard-readable compliance summaries" (§3).

**Contract requirements (CLAUDE.md A9):** pagination/filtering for collection endpoints; structured error responses; authentication/authorization per endpoint (§15); audit-relevant actions flagged (all `ComplianceRuleConfig` writes).

**Data contracts:** standard three-layer separation (CLAUDE.md A6).

---

## 13. Service Interfaces

Per CLAUDE.md A1 (module communication via in-process service-layer interfaces):

**Cross-Scheme Compliance exposes:**
- **`checkCompliance(subject_scheme, subject_version_id, comparison_scope, checkpoint, triggered_by_user_id) → ComplianceCheckRun`** — the primary, checkpoint-aware gating interface. Its response includes an explicit `blocks_transition` boolean, computed internally per §9 rule 2 — the calling scheme module is expected to obey this value directly rather than re-implementing checkpoint-blocking logic itself, keeping that policy centralized in one place.
- `runAdHocComplianceCheck(scope)` — a live, non-persisted check for Dashboard/audit "current state" views (mirrors the Draft-time advisory pattern, exposed for read-only consumption outside a scheme module's own lifecycle).
- `queryComplianceHistory(filters)` — read-only query over persisted `ComplianceCheckRun`/`ComplianceFinding` records.
- `getComplianceSummary(scope)` — the Dashboard-facing aggregated read model (§3, §12).

**How scheme modules consume compliance results:** a scheme module (UFLS today; UVLS/EMLS once built) calls `checkCompliance` at its own Submit-for-Review, Approval, and Activation transitions, passing the appropriate `checkpoint` value. It stores only the returned `check_run_id` as a traceability pointer in its own audit log (§9 rule 9) — never a copy of the findings. If `blocks_transition` is true, the scheme module rejects the transition and surfaces the findings to the user for correction; if false but findings exist (a `Warn`-severity outcome), the scheme module requires the mandatory acknowledgment reason before proceeding (§9 rule 9).

**How Dashboard consumes compliance results:** through `runAdHocComplianceCheck` for real-time "what's the state right now" views, and `queryComplianceHistory`/`getComplianceSummary` for trend and audit reporting — both entirely read-only, with zero gating effect, consistent with Dashboard never owning or triggering an authoritative engineering decision (CLAUDE.md A12 applied to this module's read surface).

**Cross-Scheme Compliance consumes, from other modules' service layers — never their repositories directly:**
- `getProtectedAssignments(scope)` from UFLS; the equivalent interface from UVLS and EMLS once built.
- `getCriticalityForSubstations(substation_ids[])` from Critical Infrastructure (Rule 2).
- Substation Registry, for display-only name/mnemonic resolution when rendering a finding (§4).
- IAM, for authorization checks on `ComplianceRuleConfig` writes and user lookups for audit attribution.

### Rule 1 Algorithm Concept

For the subject version and each comparison scheme's current Active version, call that scheme's `getProtectedAssignments(scope)`, which returns, per assignment, a substation and a boolean-equivalent "is this stage protected" classification attached by the scheme module itself (each scheme knows its own stage semantics best — the classification is metadata in the scheme's own response, not centrally configured here, per [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)'s Open Question 3). Build a map of `substation_id → [(scheme, version, stage_label, is_protected), ...]` across every scheme consulted. Any substation with `is_protected = true` entries from **two or more distinct schemes simultaneously** is a Rule 1 finding, severity per §9 rule 5. Finer per-scheme-pair conflict configuration (e.g. treating a UFLS/EMLS overlap differently from a UFLS/UVLS overlap) remains an open question carried forward from [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) — not resolved by this document.

### Rule 2 Algorithm Concept

From the same `getProtectedAssignments` results (restricted to substations in stages the scheme classifies as protected/restricted), collect the distinct substation set and call Critical Infrastructure's `getCriticalityForSubstations(substation_ids[])`. For every substation with one or more linked critical assets: a `Prohibited` asset always produces a finding; a `ConditionallyAllowed` asset produces a finding carrying its `condition_description`; an `Unrestricted` asset produces none. Severity resolution follows §9 rule 4.

---

## 14. Audit Requirements

Per CLAUDE.md §5.4 and A4, this module owns and writes its own audit log.

- **`ComplianceRuleConfig` changes are audited** (not merely logged) — a human policy decision, with who, when, old/new `enforcement_mode`, and a required reason.
- **`ComplianceCheckRun` computation itself is logged**, not audited, in the strict CLAUDE.md §16 sense — it is a deterministic, automated calculation given its inputs, exactly the same distinction already drawn for `IslandAnalysisResult` in [network-model-module.md](network-model-module.md) §14. The audit-relevant event is the calling scheme module recording that a check occurred and what its outcome was, at the moment of a human Approval/Activation decision (§9 rule 9) — that audit entry lives in the *scheme module's* log, not duplicated here.
- Every `ComplianceCheckRun` is retained permanently, immutable once `Completed`/`Failed` — full historical reproducibility (§8).
- Audit log access is itself access-controlled (CLAUDE.md A10).

---

## 15. Security Considerations

- All GridDefence engineering data is sensitive by default (CLAUDE.md A10); TLS required outside local development.
- Triggering a check (`checkCompliance`, at any checkpoint) requires no new permission tier — it inherits whatever permission the calling scheme module's own transition already requires (an Approver triggering Approval already has the permission needed for the compliance check that gates it), the same reasoning already applied in [ufls-module.md](ufls-module.md) §15 and [network-model-module.md](network-model-module.md) §15.
- **Changing `ComplianceRuleConfig`** requires an elevated, admin-tier IAM permission — cross-cutting policy configuration, not routine engineering work, mirroring the same restriction recommended for Critical Infrastructure's write access ([critical-infrastructure-module.md](critical-infrastructure-module.md) §15).
- Read access to compliance history and summaries is broader than write access, consistent with CLAUDE.md A10's "sensitive by default, gated by authentication" baseline — though note that a compliance finding referencing a critical asset may itself carry some of the same heightened sensitivity Critical Infrastructure applies to its own data (§15 of that document); recommend the same restricted read tier apply specifically to Rule 2 findings' critical-asset details, even though Rule 1 findings and general compliance summaries may be more broadly readable.

---

## 16. Testing Requirements

Per CLAUDE.md §18 and A11, in priority order:

1. **Business rule tests** — checkpoint-driven blocking behaviour (Draft/Submit-for-Review never block; Approval/Activation block on `Block`-severity findings); Rule 1 and Rule 2 algorithm correctness against known fixtures; per-asset severity override correctness (§9 rule 4); immutability of completed runs/findings; a `Failed` run correctly treated as non-passing, never silently compliant (§10); a structural/architectural test confirming no re-entrant call chain exists between `checkCompliance` and any `getProtectedAssignments`/`getCriticalityForSubstations` implementation (§9 rule 10).
2. **Engineering calculation / validation tests** — comparison-scope resolution correctness; `ComplianceCheckRunSchemeVersion` completeness (every consulted version recorded).
3. **API contract tests** — request/response schema conformance; `blocks_transition` correctness per checkpoint; authorization enforcement.
4. **Database migration tests** — required once actual migrations are authored.
5. **UI behaviour tests** — required once a compliance-facing frontend exists; must confirm the frontend renders findings and never computes compliance itself (CLAUDE.md A12).

Business rules and calculations must not be merged without accompanying tests (CLAUDE.md A11).

---

## 17. Future Extensions

- **Additional cross-scheme rules** beyond Rule 1/2, as SPS/RAS and other future schemes surface new cross-scheme concerns ([ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) Open Question 5).
- **Per-scheme-pair enforcement granularity** ([ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) Open Question 1).
- **Async execution** — if the fan-out to many scheme modules grows large as more Defence Scheme modules are added, `checkCompliance` could move to a background-job model (Redis/RQ, already in CLAUDE.md's stack) for non-blocking checkpoints (Draft, Dashboard), while Approval/Activation likely remain synchronous given their gating nature.
- **Event-driven evolution** — if modules are ever extracted into separate services, the current synchronous service-call fan-out is the natural candidate to become an event-driven projection, exactly as [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md) and [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) both already anticipate — not before.
- **Richer Dashboard visualizations** of compliance trends over time, built on `queryComplianceHistory`.

### How to Support Future SPS/RAS

No change to this module's own architecture is required: SPS/RAS (and Black Start, Islanding Strategy, Restoration Planning — CLAUDE.md §3/§27) simply need to expose their own `getProtectedAssignments`-equivalent interface, and this module's comparison scope grows to include them. This is the same reuse property [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) already established, now concretely realized in a working module design.

### Avoiding Circular Dependencies

UFLS calls `checkCompliance` (a service call from UFLS to this module), and this module calls `getProtectedAssignments` on UFLS (a service call in the opposite direction) within the same overall request. **This is not a violation of CLAUDE.md A2's dependency-direction rule**, because A2 governs *data ownership* dependency (which module's entities may reference whose), not *service call* direction. The data-ownership graph here remains a strict, uncompromised DAG: UFLS's owned entities never reference this module's entities (§6, §7); this module's entities reference only scheme **version** tables as read-only traceability, never assignment/stage data. Calling another module's service as part of your own workflow — whether that's UFLS calling IAM for an authorization check, UFLS calling Network Model for an island analysis, or UFLS calling this module for a compliance gate — is exactly what CLAUDE.md A1 module communication looks like; a service being invoked by, and in turn reading from, the same originating module in a single request is a normal fan-out/gather orchestration pattern, not a cycle, **provided** the constraint in §9 rule 10 holds: the called interface (`getProtectedAssignments`) must be a pure, side-effect-free read that never itself calls back into this module or triggers any further nested cross-module chain. This constraint is what actually prevents a problematic cycle (infinite regress, transaction deadlock) — not the domain classification of either module.

One documentation-completeness note, not a defect: [domain-model.md](domain-model.md) §6 describes the Audit and Analytics domain as "referenced by: none," which this module's genuine gating role at Approval/Activation does not quite fit — it is called into by Defence Scheme modules, unlike a pure reporting capability. This is a minor placement nuance worth reconciling the next time domain-model.md is revisited (this document does not modify it).

---

## 18. Risks and Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| ADR-004's global per-rule `enforcement_mode` and Critical Infrastructure's per-asset `restriction_type` are two related severity signals, previously only cross-referenced from the Critical Infrastructure side | A reader of ADR-004 alone would miss that Rule 2's real severity is asset-specific | **Yes — this document, together with [critical-infrastructure-module.md](critical-infrastructure-module.md) §7.4, constitutes the addendum ADR-004 needs.** Recommend ADR-004 be formally updated at its next revision to reference both documents as the authoritative source for Rule 2's actual severity-resolution logic (§9 rules 3–4), rather than leaving the relationship documented only from the consuming side. |
| A `Failed` check run being treated as compliant by mistake (fail-open) | An outage in a downstream module's service (e.g. Critical Infrastructure unavailable) could silently permit an unsafe Approval/Activation | §10 mandates fail-closed treatment explicitly — a `Failed` run never passes; enforce this as a first-class business rule test (§16), not just documentation |
| Service-interface implementations drift into calling back into this module over time (a future maintainer adds a "helpful" cross-check inside `getProtectedAssignments`) | Reintroduces the exact re-entrant-call risk §9 rule 10 exists to prevent | Treat this as an explicit, tested architectural constraint (§16), and document the rule prominently in each scheme module's own service interface documentation, not only here |
| Fan-out to many scheme modules at Approval/Activation grows slow as more Defence Scheme modules (SPS/RAS, etc.) are added | Synchronous checkpoint calls could become a latency concern | Monitor in practice; async execution for non-gating checkpoints is already flagged as a Future Extension (§17), not adopted prematurely |
| `ComplianceRuleConfig`'s `Disabled` state used to silently suppress a rule long-term without governance review | A rule intended as temporary could remain off indefinitely, unnoticed | Recommend periodic review of any rule left in `Disabled` state, as an organisational process — not enforced architecturally here |

---

## Recommended Next Architecture Document

**UVLS module.**

Both the Canonical Version Lifecycle template ([ufls-module.md](ufls-module.md)) and the full compliance-interface contract formalized here (including the precise `checkCompliance(subject_scheme, subject_version_id, comparison_scope, checkpoint, ...)` signature and the `getProtectedAssignments` expectation) are now concretely defined and ready for a second scheme module to adopt directly. Building UVLS next validates that this whole pattern language — version lifecycle, MW capture, pocket assignments, compliance-checkpoint calling — genuinely generalizes beyond a single example, which is more architecturally load-bearing right now than building a pure consumer of interfaces that already exist.

**Dashboard module** is a strong, well-justified secondary: across PSS/E Integration, Network Model, UFLS, Critical Infrastructure, and this module, a substantial read-only surface has now accumulated (`getConnectivityGraph`, load analytics, `getComplianceSummary`, criticality lookups, historical compliance queries) that Dashboard is the natural consumer of, and building it would exercise all of these interfaces end-to-end. It is not blocked by, and does not block, UVLS.

**EMLS module** and **Equipment Registry module** remain important but lower urgency, for the same reasons already given in [critical-infrastructure-module.md](critical-infrastructure-module.md)'s equivalent recommendation.
