# ADR-004: Cross-Scheme Compliance Mechanism

- **Status:** Accepted
- **Date:** 2026-07-01
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1, §5.2, §6, §8, §11.2, A1, A2, A3, A4, A7, A10)
- **Depends on:** [ADR-000](ADR-000-architecture-principles.md), [ADR-001](ADR-001-modular-monolith-and-module-communication.md), [ADR-002](ADR-002-identity-and-access-management.md), [ADR-003](ADR-003-psse-topology-and-load-snapshot-separation.md)
- **Affects:** [docs/architecture/ufls-module.md](../architecture/ufls-module.md) §13/§17 (`getProtectedAssignments`, Cross-Scheme Compliance listed as a future consumer), [docs/architecture/domain-model.md](../architecture/domain-model.md) (a new bounded context and, pending its own module doc, a new Master Data submodule)
- **Informed by:** the Codebase Discovery Report for the legacy MVP, which flagged the tension between per-module bounded contexts and Rule 1's need to check across UFLS/UVLS/EMLS as the single highest-severity *open* architectural risk identified across the entire discovery exercise.

---

## Context

The legacy MVP enforced four business rules across its load-shedding schemes. Two of them — Rule 3 (direct/pocket overlap) and Rule 4 (IPP/LSS exclusion) — turned out, on closer architectural analysis during UFLS's design, to be **version-internal**: they only require visibility into one scheme version's own data plus a read-only lookup against Substation Registry, and are now fully owned and enforced inside UFLS itself ([ufls-module.md](../architecture/ufls-module.md) §9, rules 7–8). That resolved two of the four rules without needing any new module.

The remaining two are genuinely cross-scheme and cannot be resolved this way:

- **Rule 1** — a substation/assignment protected in one scheme must not be simultaneously exposed to a conflicting protected stage in another scheme (e.g. a substation locked into UFLS's early protected stages must not also appear in UVLS's or EMLS's stages).
- **Rule 2** — critical-infrastructure substations must not be assigned to restricted shedding stages unless explicitly allowed.

Both require a check to see across module boundaries — exactly the kind of concern CLAUDE.md §8 and [ADR-001](ADR-001-modular-monolith-and-module-communication.md) exist to prevent modules from resolving by directly reaching into each other's data. UFLS's design already anticipated this by exposing a read-only `getProtectedAssignments(scope)` service interface specifically so a future capability could consume it without violating module boundaries ([ufls-module.md](../architecture/ufls-module.md) §13). This ADR decides what that future capability is, how it is triggered, what it owns, and how it scales to UVLS, EMLS, and future defence schemes.

---

## Decision

GridDefence adopts a **dedicated Cross-Scheme Compliance module** — a bounded context in its own right, belonging to the Audit and Analytics domain per [domain-model.md](../architecture/domain-model.md) §6 (it *observes* engineering data across schemes; it does not own any of it). It calls each scheme module's read-only service interface (`getProtectedAssignments`, and — once it exists — Critical Infrastructure's equivalent interface), cross-references the results itself, and persists its own audit-relevant check records. It never owns UFLS/UVLS/EMLS data, never holds a foreign key into their assignment/stage tables directly as a source of truth, and never bypasses their service layers.

This directly reuses the decoupling pattern already validated twice in this document series — Network Model consuming PSS/E Integration's data without owning it ([network-model-module.md](../architecture/network-model-module.md) §9), and UFLS consuming Network Model's/PSS/E Integration's data as recommendations captured into its own owned data ([ufls-module.md](../architecture/ufls-module.md) §7.6, §9) — applied a third time to a genuinely different shape of problem: a **read-only, multi-source cross-check**, not a single-source derived recommendation.

### Who owns compliance results (decision point 3)

Cross-Scheme Compliance owns its own `ComplianceCheckRun` (one row per check execution, pinned to the exact scheme version(s) it checked) and `ComplianceViolation` (one row per violation found in a run). These are **not** approved engineering data belonging to any scheme module — a scheme module never "captures" a compliance result into its own tables the way it captures MW. Instead, each scheme module's own audit log records a traceability pointer (`compliance_check_run_id`) at Approval and Activation, exactly mirroring the pattern already established for `source_load_snapshot_id`/`source_analysis_result_id` in [ufls-module.md](../architecture/ufls-module.md) §14.

### How the module accesses protected assignments without violating boundaries (decision point 4)

Exclusively through each scheme module's service interface — `UFLS.getProtectedAssignments(scope)`, and the equivalent interface UVLS and EMLS must expose once built. This is a standard synchronous service-to-service call under CLAUDE.md A1's primary communication mechanism, not the narrow read-only-join reporting exception in [ADR-001](ADR-001-modular-monolith-and-module-communication.md). Cross-Scheme Compliance's own tables hold no foreign key into any scheme module's stage/assignment tables — only into their **version** tables (`ufls_scheme_version_id`, etc.), as a traceability pointer recording which version was checked, consistent with how every other cross-module reference in this document series is modeled.

### Should Critical Infrastructure become its own bounded context (decision points 5 & 6)

**Yes.** Critical-infrastructure classification (which substations are critical, at what sensitivity, and why) is fundamentally asset classification data — the same category as `grid_owner` or `operational_status` — and belongs in the Master Data domain per [domain-model.md](../architecture/domain-model.md) §3, referenced by `substation_id`, never duplicated into any scheme module or into Cross-Scheme Compliance itself. Rule 2 enforcement then becomes: Cross-Scheme Compliance calls Critical Infrastructure's read-only service interface ("is substation X critical, at what sensitivity level") alongside each scheme module's `getProtectedAssignments`, and cross-references the results — the exact same fan-out pattern as Rule 1, just with one more source module. This ADR does not design Critical Infrastructure's full data model; it decides its bounded-context placement so Cross-Scheme Compliance's Rule 2 has a concrete, correctly-owned dependency to call once that module exists (see Recommended Next Architecture Document).

### Rule policy ownership

Rather than each scheme module independently configuring its own enforcement mode for a cross-scheme rule (as the legacy MVP did, via a near-duplicated `LoadSheddingAlertConfig` per scheme type), Cross-Scheme Compliance owns a single `ComplianceRuleConfig` per rule (e.g. `rule_1_cross_scheme_overlap`, `rule_2_critical_protection`), each carrying an `enforcement_mode` (`warn` | `block`) as versioned engineering parameter data (CLAUDE.md A7). This is a deliberate simplification over the MVP's design: a cross-cutting rule has one policy, not three near-identical copies of it.

---

## Consequences

**Positive:**
- Resolves the single highest-severity open risk carried forward from the Codebase Discovery Report through ADR-003, [psse-integration-module.md](../architecture/psse-integration-module.md), [network-model-module.md](../architecture/network-model-module.md), and [ufls-module.md](../architecture/ufls-module.md), all of which explicitly deferred it to this point.
- Extends a now three-times-validated architectural pattern (module A consumes module B's read-only interface, captures/records what it needs, never owns B's data) to a new shape of problem (multi-source cross-checking) without inventing new infrastructure.
- A single, centrally-owned `ComplianceRuleConfig` per rule removes the MVP's near-duplicated per-scheme configuration.
- Generalizes cleanly to SPS/RAS, Black Start, Islanding Strategy, and Restoration Planning (see Future Support for SPS/RAS) without redesigning Cross-Scheme Compliance itself.

**Negative / trade-offs:**
- Introduces a new module that must exist and be built before Rule 1/2 can be enforced as anything more than a documented gap — UFLS's own Rule 1/2 enforcement remains unimplemented until this module and (for Rule 2) Critical Infrastructure both exist.
- Every future scheme module must remember to expose a `getProtectedAssignments`-equivalent interface; this is a convention this module depends on, not something enforced automatically by the platform. (Mitigation: the Canonical Module Architecture Document Template review, CLAUDE.md A8/A13, should treat this as a checklist item for any new Defence Scheme module.)
- Adds a synchronous fan-out call (to every relevant scheme module, and to Critical Infrastructure) at Approval and Activation — see Risks/Validation Timing for why this is acceptable at current scale but worth watching as more schemes are added.

---

## Alternatives Considered

1. **Dedicated Cross-Scheme Compliance module calling scheme service interfaces.** **Adopted.** Respects bounded-context ownership (CLAUDE.md §8), uses the established, already-provisioned communication mechanism ([ufls-module.md](../architecture/ufls-module.md) already exposes `getProtectedAssignments` for exactly this purpose), and requires no new infrastructure.

2. **Shared scheme kernel used by UFLS/UVLS/EMLS** (a single underlying "scheme version/stage" table set differentiated by a scheme-type discriminator — the legacy MVP's actual design). **Rejected.** This is precisely the design the Codebase Discovery Report flagged as being in tension with GridDefence's per-module ownership model, and precisely what [ufls-module.md](../architecture/ufls-module.md) was built to move away from. Retrofitting a shared kernel now would mean unwinding UFLS's already-ratified independent ownership of its own scheme identity, versions, and assignments (CLAUDE.md §8, ADR-000) — a far more invasive change than the problem warrants, especially now that Rule 3/4 turned out not to need it at all.

3. **Reporting-only dashboard validation** (a read-only compliance report, computed on demand or periodically, with no write-time gating — mirroring the legacy MVP's `compliance_report` endpoint as the *only* mechanism). **Rejected as the sole mechanism, retained as a complementary capability.** A report that only informs after the fact cannot prevent an unsafe Approval or Activation, which is exactly the scenario a "block" enforcement mode exists to stop. However, the same underlying check logic should also be exposed as an on-demand, non-gating report for continuous monitoring and audit purposes (§ Validation Timing) — this is not wasted effort, it is one capability serving two access patterns.

4. **Direct cross-module database joins** (querying UFLS's, UVLS's, and EMLS's assignment tables directly via SQL joins for validation). **Rejected.** [ADR-001](ADR-001-modular-monolith-and-module-communication.md) scopes read-only cross-module joins strictly to reporting, dashboards, and query optimisation — explicitly *not* as a substitute for business-rule execution. Using joins here would be exactly the anti-pattern that rule exists to prevent, and would hard-couple Cross-Scheme Compliance to every scheme module's internal schema.

5. **Event-driven compliance projection** (each scheme module publishes assignment-changed events; Cross-Scheme Compliance maintains an asynchronously-updated materialized projection it queries). **Rejected for now, noted as a future evolution path.** This introduces a formal event/message-bus mechanism that does not yet exist in GridDefence's stack (CLAUDE.md §9 lists Redis/RQ for background jobs, not pub/sub messaging — the same gap already flagged in [network-model-module.md](../architecture/network-model-module.md) §17 as "new infrastructure, not assumed today"). It also introduces eventual consistency at exactly the moment strong consistency matters most: a compliance check performed at Activation on a stale projection could pass a version that is, at that instant, actually non-compliant against another scheme's just-activated version. Synchronous service calls (option 1) are simpler, strongly consistent, and cheap at current physical-deployment scale (in-process calls within a single modular monolith, per [ADR-001](ADR-001-modular-monolith-and-module-communication.md)). [ADR-001](ADR-001-modular-monolith-and-module-communication.md) itself already anticipates that read-only cross-module access patterns may need to become event-driven projections if modules are later extracted into separate services — this remains the natural next step for Cross-Scheme Compliance specifically, if and when that extraction happens, not before.

---

## Service Interface Expectations

**Cross-Scheme Compliance exposes:**
- `checkCompliance(subject_scheme, subject_version_id, comparison_scope)` — runs Rule 1/2 (and any future cross-scheme rule) against the specified subject version and the current Active version(s) of the other schemes in scope; returns a `ComplianceCheckRun` with any `ComplianceViolation` rows. This is the interface UFLS (and future UVLS/EMLS) call at Submit-for-Review, Approval, and Activation (§ Validation Timing).
- A read-only, on-demand compliance report interface (no gating effect) for Dashboard and ad hoc audit use — the complementary capability retained from Alternative 3.

**Cross-Scheme Compliance consumes, from other modules' service layers — never their repositories directly:**
- `getProtectedAssignments(scope)` from UFLS today; the equivalent interface from UVLS and EMLS once built. Every Defence Scheme module is expected to expose this interface as a condition of being included in cross-scheme checking — this expectation should be added to the Canonical Module Architecture Document Template review checklist (CLAUDE.md A8) for any new scheme module.
- A read-only criticality-lookup interface from the future Critical Infrastructure module (for Rule 2).
- From Core Platform (IAM): authorization checks for `ComplianceRuleConfig` changes; user lookups for audit attribution.

Every interface exposed by this module is read-only with respect to the modules it consumes — it never writes to another module's data, and no other module writes to Cross-Scheme Compliance's tables except through its own service layer, per CLAUDE.md A1 and [ADR-001](ADR-001-modular-monolith-and-module-communication.md).

---

## Data Ownership Rules

- Cross-Scheme Compliance owns: `ComplianceRuleConfig` (one row per rule, including `enforcement_mode`), `ComplianceCheckRun` (immutable once completed — a `Running → Completed | Failed` status only, not the Canonical Version Lifecycle, since a check run is an automated computation, not approved engineering policy, mirroring the same justification already given for `IslandAnalysisResult` in [network-model-module.md](../architecture/network-model-module.md) §8), `ComplianceViolation` (child rows), and its own audit log.
- Cross-Scheme Compliance **does not** own: UFLS/UVLS/EMLS assignment or stage data, Substation Registry data, or (once it exists) Critical Infrastructure data. It holds foreign keys only into each scheme module's **version** table (for traceability of what was checked), never into stage/assignment-level tables.
- A `ComplianceViolation` row references the offending `substation_id` (Substation Registry, external) and descriptive context (rule id, involved scheme version ids, stage labels resolved from the calling interfaces' responses at check time) — it does not duplicate scheme module data beyond what is needed to describe the violation, and it does not persist a copy of any scheme's stage/assignment structure.
- A scheme module's own audit log records a `compliance_check_run_id` pointer at Approval and Activation — descriptive metadata only, never a live dependency (consistent with every other cross-module traceability pointer in this document series).

---

## Validation Timing

Answering decision point 1 with a deliberately multi-checkpoint design, not a single trigger point:

| Checkpoint | Nature | Blocking? |
|---|---|---|
| Draft (assignment add/edit) | Advisory, real-time, non-gating | Never blocks — Draft is inherently exploratory |
| Submit for Review (Draft → Under Review) | Mandatory check, recorded as a `ComplianceCheckRun` | Never hard-blocks, regardless of `enforcement_mode` — this checkpoint exists to surface findings to reviewers, not to gate them |
| Approval (Under Review → Approved) | Mandatory check, recorded | **Hard-blocks if any `block`-mode rule is violated** (§ Enforcement Policy, below) |
| Activation (Approved → Active) | Mandatory check, **re-run**, recorded | **Hard-blocks if any `block`-mode rule is violated** |
| Dashboard / on-demand audit | Always available, non-gating | Never blocks — informational only |

**Why Activation re-checks even an already-Approved version:** cross-scheme compliance is a relationship between modules' *current* state, and that state can change out from under an Approved-but-not-yet-Active version. Another scheme could approve and activate its own new version in the interval between this version's Approval and its Activation, creating a conflict that did not exist at the time this version was approved. Re-checking at Activation is a genuine safety measure, not redundant work — it is the only checkpoint that reflects the state of the grid at the actual moment this version would start governing it.

**Answering decision point 2 (block vs. warn) precisely:** the `enforcement_mode` on a `ComplianceRuleConfig` determines whether a violation is *classified* as blocking-worthy at all. A rule set to `warn` never blocks any checkpoint, ever — it is deliberately, permanently advisory by policy. A rule set to `block` is still only advisory at Draft and Submit-for-Review (engineers need room to iterate before content is frozen), but becomes a hard stop at Approval and Activation — the two checkpoints where a version's data becomes immutable and grid-governing, respectively.

---

## Audit Requirements

- Cross-Scheme Compliance owns its own audit log (CLAUDE.md A4), covering every `ComplianceCheckRun` and any change to `ComplianceRuleConfig` (who changed an enforcement mode, when, and why — this is engineering policy configuration and is audited with the same rigor as any other engineering parameter change, CLAUDE.md §5.4).
- Every `ComplianceCheckRun` is retained permanently and is immutable once `Completed` — full historical reproducibility of what was checked and what was found, matching the reproducibility guarantee already established for `IslandAnalysisResult` in [network-model-module.md](../architecture/network-model-module.md) §9.
- **An Approval or Activation that proceeds despite a `warn`-mode violation requires an explicit, recorded acknowledgment** — a mandatory reason from the approving/activating user, captured in that scheme module's own audit log alongside the `compliance_check_run_id` pointer. This mirrors the change-reason pattern already established in [ufls-module.md](../architecture/ufls-module.md) §7.7/§14, and ensures a known, accepted violation is never silently ignored — it is a deliberate, accountable engineering decision every time.
- Audit log access is itself access-controlled (CLAUDE.md A10).

---

## Security Considerations

- All GridDefence engineering data, including compliance check results, is sensitive by default (CLAUDE.md A10); TLS required outside local development.
- Requesting a compliance check (`checkCompliance`) requires no elevated permission beyond whatever permission the calling scheme module already requires for the checkpoint it is running at (e.g. an Editor may trigger a Draft-time advisory check; an Approver's existing elevated permission already covers the Approval-time mandatory check) — no new permission tier is introduced solely for triggering a check.
- **Changing `ComplianceRuleConfig`** (enforcement mode, rule parameters) is recommended to require an elevated, admin-tier IAM permission, consistent with how the legacy MVP restricted its equivalent `LoadSheddingAlertConfig` to staff/superuser-only — this is cross-cutting policy configuration, not routine engineering work.
- Read access to `ComplianceCheckRun`/`ComplianceViolation` history is broader than write access, consistent with CLAUDE.md A10's "sensitive by default, gated by authentication" baseline — any authenticated engineering user should be able to review past compliance findings for audit purposes.

---

## Future Support for SPS/RAS

This design generalizes to Special Protection Schemes / Remedial Action Schemes, Black Start, Islanding Strategy, and Restoration Planning (CLAUDE.md §3/§27) without any change to Cross-Scheme Compliance's own architecture: each new topology-aware or protection-aware scheme module simply needs to expose its own `getProtectedAssignments`-equivalent read-only service interface, and Cross-Scheme Compliance's fan-out list of consulted schemes grows to include it. No new cross-module coupling pattern is required — this is the same reuse property already designed into [network-model-module.md](../architecture/network-model-module.md) §9, rule 8 (Network Model's decoupling from scheme modules), now demonstrated a second time at the compliance layer. Whether SPS/RAS introduces genuinely new cross-scheme rules beyond Rule 1/2's shape is left open (§ Open Questions) — the mechanism does not presuppose the rule catalog is closed.

---

## Open Questions

1. Should `enforcement_mode` be settable per rule globally, or per scheme-pair (e.g. UFLS-vs-UVLS overlap configured differently from UFLS-vs-EMLS overlap)? This ADR defaults to per-rule-global for simplicity; finer granularity may be needed once real cross-scheme conflicts are observed in practice.
2. Should the Draft-time advisory check be synchronous (blocking the UI briefly while fanning out to every relevant scheme module) or asynchronous (Redis/RQ)? Likely fine synchronously at today's scale (a handful of schemes); worth revisiting as SPS/RAS, Black Start, and other future schemes are added and the fan-out grows.
3. Where exactly should "which of my stages count as protected/restricted" be defined — as configuration centrally owned by `ComplianceRuleConfig`, or as metadata each scheme module attaches to its own `getProtectedAssignments` response (since each scheme module best understands its own stage semantics)? This ADR leans toward the latter but leaves the precise interface contract to be finalized when the Critical Infrastructure module and UVLS's own module doc are written.
4. How does the pending `Superseded → Active` reactivation decision (flagged as needing its own ADR in [ufls-module.md](../architecture/ufls-module.md) §8/closing summary) interact with compliance checking? A reactivation should logically trigger a fresh compliance check, following the same reasoning already given for why Activation re-checks — this needs to be reconciled once that ADR is written.
5. Is the Rule 1/Rule 2 catalog closed, or should this ADR anticipate a formal process for adding new cross-scheme rules over time (e.g. as SPS/RAS is designed)? Not resolved here — deferred until a concrete new rule is actually proposed.

---

## Recommended Next Architecture Document

**Critical Infrastructure module.**

This ADR establishes that Critical Infrastructure must be its own Master Data-adjacent bounded context (decision points 5–6) and makes it a concrete, named dependency of Cross-Scheme Compliance's Rule 2 enforcement — without it, Rule 2 has no data source to call, and Cross-Scheme Compliance's fan-out design is only half-implementable. Building this module next closes the last missing piece needed for both rules identified in the Codebase Discovery Report to be fully, correctly enforceable, completing the chain that began with that report.

**UVLS module** is a strong secondary candidate — both the Canonical Version Lifecycle template ([ufls-module.md](../architecture/ufls-module.md)) and the `getProtectedAssignments` compliance-interface pattern established here are now validated and ready for UVLS to adopt directly, with minimal net-new architectural decision-making required. It is not blocked by Critical Infrastructure and could reasonably be sequenced in parallel or immediately after.

**EMLS module** and **Equipment Registry module** remain important but lower urgency: EMLS follows the same template as UVLS once that pattern is exercised a second time, and Equipment Registry has no urgent dependency from this ADR (UFLS's `equipment_reference` placeholder, per [ufls-module.md](../architecture/ufls-module.md) §7.4, remains a documented, deliberate deferral, not a blocker).
