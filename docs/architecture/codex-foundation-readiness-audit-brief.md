# Codex Foundation-Readiness Audit Brief

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§23 — Codex is Senior Software Engineer, implements approved architecture). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md).

This is an instruction document for a future Codex audit pass. **Codex should not implement fixes during this audit.** The audit's output is a findings report, classified by severity, that the Project Owner and Claude (as Principal Software Architect) use to decide what must be resolved before UFLS implementation begins.

---

## 1. Audit Scope

Evaluate the codebase and this architecture pack together against the following dimensions. For each, produce a finding (or confirm no finding) classified as **Critical, High, Medium, Low,** or **Enhancement**.

### 1.1 Architecture conformance

Does every document in this pack (§ Engineering Scheme Architecture Pack index, [scheme-engineering-principles.md](scheme-engineering-principles.md)) conform to CLAUDE.md's standards — module layering (A6), module communication (A1), primary key standards (A5), audit ownership (A4), versioning (A3, as scoped by [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md))? Flag any internal inconsistency between this pack's own documents.

### 1.2 Domain ownership

Confirm every new entity this pack introduces (Scheme Version, Stage Setting Set, Finding, PublicationTreatmentPolicy, PublicationRecord) has exactly one owning module, per [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) and [ADR-016](../adr/ADR-016-stage-setting-set-as-reusable-versioned-entity.md). Confirm no entity is duplicated across modules.

**Status update ([ADR-020](../adr/ADR-020-stage-setting-registry-as-standalone-shared-module.md)):** Stage Setting Set's own owning module is now decided — a new, standalone Stage Setting Registry, never UFLS or UVLS. This was the one entity this section could not previously confirm from documentation alone; the audit should verify the *implementation* matches ADR-020 (a genuinely separate module, not a shared table accessed by two modules' own service layers), not re-litigate the ownership decision itself. Engineering Parameter Configuration ([ADR-021](../adr/ADR-021-engineering-parameter-configuration-ownership.md)) is a further new entity/module introduced since this brief was first written — apply the same "exactly one owning module" confirmation to it.

### 1.3 Module boundaries

Confirm no table this pack describes holds a foreign key into another module's business-entity tables beyond the explicitly-permitted traceability pointers (e.g. a Scheme Version's Stage Setting Set reference, a Finding's substation/assignment reference). Confirm the decoupling test pattern already established in [`network-model-module.md`](network-model-module.md) §9 rule 8 and [`critical-infrastructure-module.md`](critical-infrastructure-module.md) §9 rule 4 is extended to every new module this pack's implementation introduces.

### 1.4 Existing read contracts

**Verify, do not assume, the following before implementation begins** (flagged as open questions this pack could not resolve from documentation alone):

- Does PSS/E Integration's `EquipmentTopologyMap` currently support per-`CircuitTerminal` correlation resolution, or only per-`Circuit`? [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §6 requires the former; if the actual implementation only supports the latter, this is a **Critical** finding — Boundary Pocket construction as designed cannot proceed without it.
- Does the Automatic Load Shedding Functionality Registry's existing candidate-search/capability-check interface ([`automatic-load-shedding-functionality-registry-module.md`](automatic-load-shedding-functionality-registry-module.md) §13) already return a shape [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)'s ALSF detector can consume directly, or does it need a small extension?
- Does the Sensitive Customer Registry's existing candidate-facing read interface ([`sensitive-customer-registry-implementation-spec.md`](sensitive-customer-registry-implementation-spec.md) §9) already support the batch lookup shape a scheme module's candidate view needs (§1.7, below)?

### 1.5 Snapshot activation semantics

**Confirmed already, from direct code inspection, not merely documentation** — record this as a baseline finding, not an open question: PSS/E Integration's `activate()` (`backend/app/modules/psse_integration/service.py`) atomically supersedes the prior `Current` `TopologyVersion`/`LoadSnapshot` and marks the new one `Current`; `get_current_topology_version()`/`get_current_load_snapshot()` (`backend/app/modules/psse_integration/repository.py`) query `WHERE status == 'Current'` with no scoping parameter, confirming a single, globally-consistent Active snapshot resolution. This satisfies [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §4's requirement without further work. Audit should re-verify this remains true (no regression) and check whether a database-level partial unique constraint (not only service-layer enforcement) protects "at most one Current row," per CLAUDE.md §11.8's general preference for database-enforced constraints — if none exists, this is a **Medium** finding.

### 1.6 Network Model sufficiency

Confirm `traverse` ([`network-model-module.md`](network-model-module.md) §19.4, §19.6) is sufficient, unmodified, for [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §7's two-directional reachability comparison — specifically, whether calling `traverse` twice per evaluation (once from "inside," once from the "rest of grid" anchor) is performant enough for live, Draft-time, per-edit re-evaluation at realistic network scale, or whether this requires the async/caching treatment [`network-model-module.md`](network-model-module.md) §18 already flags as a risk for heavy computation generally.

### 1.7 Boundary Pocket correctness

Once implemented, verify: per-terminal opening-point resolution correctness against tee-off `Circuit` fixtures; completeness-detection correctness (a genuinely still-connected candidate is correctly reported Incomplete, not silently misclassified as Complete); determinism (identical inputs against an identical snapshot always yield an identical result); the "rest of grid" reference substation configuration is resolved and documented, not left as an undocumented hardcoded value.

### 1.8 Batch lookup sufficiency

Confirm every batch/candidate-facing read interface this pack's Engineering Workspace depends on ([engineering-workspace-architecture.md](engineering-workspace-architecture.md) §4) — Substation Registry, Equipment Registry, ALSF, Sensitive Customer Registry — actually supports batch (not one-at-a-time) queries at the scale a real candidate-browsing view requires, mirroring [`critical-infrastructure-module.md`](critical-infrastructure-module.md) §13's own explicit "deliberately not a one-substation-at-a-time call" design note. Flag any interface that would force N+1 query patterns in the Engineering Workspace's candidate view.

### 1.9 Lifecycle and audit integrity

Confirm [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md)'s deletable-Draft exception is implemented cleanly — a deleted Draft's own findings cache (if any), audit log entries (if any were written before deletion), and any Boundary Pocket evaluation state are all correctly discarded, with no orphaned references left in another module's tables. Confirm every Publish action produces a single, correlated audit event (mirroring [`ufls-module.md`](ufls-module.md) §8's own existing "both halves of an activation are recorded as a single correlated audit event" requirement, now for the single Publish action rather than a two-part Approve/Activate pair).

### 1.10 API consistency

Confirm every Defence Scheme module's eventual API surface follows [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §8's shared service-interface shape, and that [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §10's `scheme-versions/{id}/publish`/`scheme-versions/{id}/findings` contract shape is implemented identically across UFLS/UVLS/EMLS, not independently re-derived per module (the same drift risk [`ufls-module.md`](ufls-module.md) §17/§18 already flagged for Rule 7/8 validation logic, generalized here to the Publish/findings contract).

### 1.11 Frontend workflow readiness

Confirm the frontend's existing component library (per [`system-overview.md`](system-overview.md) §4's stack — TanStack Table/Query, ECharts) has, or can readily gain, the building blocks [engineering-workspace-architecture.md](engineering-workspace-architecture.md) §5 requires: a staged-selection/basket interaction pattern for direct assignment, and an incremental map-or-list-based Pocket Builder interaction for Boundary Pocket construction. No frontend code should be written during this audit — only readiness assessed.

### 1.12 Performance risks in continuous evaluation

Assess whether [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §3's event-driven background recalculation, scoped to every currently-relevant Draft **and Published** Scheme Version (a broader scope than [`network-model-module.md`](network-model-module.md) §8.4's own original non-terminal-only scoping), risks unbounded background-job volume as the number of Published schemes across UFLS/UVLS/EMLS grows. Flag whether this scope needs its own bounding rule before implementation, beyond what this pack currently specifies.

### 1.13 Event-driven recalculation readiness

Confirm Redis/RQ (already in use since PSS/E Integration, per [`system-overview.md`](system-overview.md) §3) is sufficient for [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §3's background-recalculation mechanism, or whether the formal domain-event/pub-sub mechanism [`network-model-module.md`](network-model-module.md) §17 and [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) Alternative 5 both already flag as "new infrastructure, not assumed today" has become genuinely necessary given this pack's broader recalculation scope (§1.12, above). Do not build this infrastructure during the audit — assess only whether it is now required.

**Status update ([ADR-023](../adr/ADR-023-platform-event-architecture.md)):** resolved — Redis/RQ is confirmed sufficient; no new event bus or pub-sub mechanism is introduced. See [platform-event-architecture.md](platform-event-architecture.md) for the full trigger design (single shared queue owned by Continuous Evaluation, idempotent full-recompute jobs, `notify_source_data_changed` as the one integration point every source module calls). The audit should verify the *implementation* matches this design (every source module actually calls the shared entry point; no module rolls its own queue), not re-open whether Redis/RQ suffices.

### 1.14 Publication governance readiness

Confirm [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)'s reused Rule 1/2 detection logic (§9 of that document) can genuinely be extracted from [`cross-scheme-compliance-module.md`](cross-scheme-compliance-module.md)'s own original design without carrying forward its now-superseded governance machinery (`ComplianceRuleConfig`/`ComplianceCheckRun` as separately-gating entities) — flag any part of the original design that resists this separation cleanly.

### 1.15 Foundation gaps before UFLS

Summarize every Critical and High finding from §1.1–§1.14 as the concrete "must resolve before Phase 6 (UFLS)" list, distinct from Medium/Low/Enhancement findings that may be addressed during or after Phase 6 implementation.

## 2. Format

Report findings as: **[Severity] Area — Finding — Recommended resolution owner (Claude/architecture decision, or Codex/implementation).** Group by the numbered sections above. Do not propose or write fixes; the resolution owner decides how each finding is addressed.

## 3. Explicitly Out of Scope for This Audit

- Implementing UFLS, UVLS, EMLS, or any of this pack's new capabilities.
- Writing migrations, models, schemas, services, routers, or frontend code.
- Modifying any existing architecture document beyond what this pack's own status notes already specify.
- Re-litigating any decision already ratified in [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md) through [ADR-023](../adr/ADR-023-platform-event-architecture.md) or [EDR-009](../engineering/edr/EDR-009-grid-defence-scheme-lifecycle-realignment.md)/[EDR-010](../engineering/edr/EDR-010-boundary-pocket-as-engineering-identity.md) — the audit assesses foundation readiness for implementing these decisions, not whether the decisions themselves were correct.
