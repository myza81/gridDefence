# Platform Event Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.5, §21, A1). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md). Realizes [ADR-023](../adr/ADR-023-platform-event-architecture.md) — read that ADR first for the decision rationale; this document is the architecture built from it.

Related: [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §3 mechanism 1 (the consumer side of this design), [codex-foundation-readiness-audit-brief.md](codex-foundation-readiness-audit-brief.md) §1.13 (the open question this document resolves), [shared-platform-dependency-diagram.md](shared-platform-dependency-diagram.md).

**Status update (Shared Platform Sprint 6, 2026-07-16).** Consumer and refresh infrastructure implemented; source integration pending. `ContinuousEvaluationService.notify_source_data_changed` (§4), the exclusively-owned `continuous_evaluation` RQ queue (§6), and idempotent full-recompute background jobs (§7) are implemented in `backend/app/modules/continuous_evaluation/`, reusing the existing `app.core.execution`/`app.core.queue` infrastructure (extended, minimally and additively, with an optional named-queue parameter so this module's own queue can coexist with PSS/E Integration's pre-existing one on the same Redis connection and worker process). No producer named in §3's table calls `notify_source_data_changed` yet — that remains a later integration sprint.

---

## 1. Purpose

Define one consistent mechanism by which any module holding data the Continuous Evaluation Engine depends on — today's existing modules and every future scheme module alike — notifies the Engine that a recompute may be needed, without coupling any source module's own write path to the Engine's own performance or correctness.

## 2. Scope

Covers the trigger relationship between source modules and the Continuous Evaluation Engine only. It is **not** a general-purpose platform event bus — see [ADR-023](../adr/ADR-023-platform-event-architecture.md) Alternatives Considered, option 3, for why that broader scope is explicitly out of scope today.

## 3. Participating Modules

**Producers** (call `notify_source_data_changed` after a relevant write):

| Module | Example triggering change |
|---|---|
| Substation Registry | Operational status change; metadata correction |
| Equipment Registry | Circuit/Transformer Terminal correction; capability change |
| Automatic Load Shedding Functionality Registry | ALSF status change |
| Sensitive Customer Registry | Facility created, updated, or association changed |
| PSS/E Integration | New topology/load snapshot imported and activated |
| Network Model | Connectivity recalculation affecting derived topology |
| Stage Setting Registry | A Stage Setting Set is marked Entered in Error (per [stage-setting-set-architecture.md](stage-setting-set-architecture.md) §7 rule 3) |
| Engineering Parameter Configuration | A parameter value changes (e.g. `mw_tolerance_percentage`) |
| Every future scheme module (SPS, RAS, etc.) | Any write to its own owned data that other findings might depend on (e.g. cross-scheme overlap detectors) |

**Consumer:** the Continuous Evaluation Engine, exclusively (§5 of [ADR-023](../adr/ADR-023-platform-event-architecture.md)).

## 4. Trigger Mechanism

```text
[Source module service layer, after commit]
        │
        ▼
ContinuousEvaluationService.notify_source_data_changed(change_descriptor)
        │  (synchronous, in-process call — CLAUDE.md A1)
        ▼
[enqueue one job on the existing Redis/RQ queue, owned by Continuous Evaluation]
        │  (asynchronous from this point on)
        ▼
[Continuous Evaluation worker: full recompute for every affected, currently-relevant
 Scheme Version — Draft and Published — per continuous-evaluation-architecture.md §3]
```

The call to `notify_source_data_changed` is the only thing synchronous about this flow — it does no recompute itself, only enqueues. The source module's own transaction is never blocked on evaluation completing (per [ADR-023](../adr/ADR-023-platform-event-architecture.md) Rationale, and [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §3.2's own decoupling principle, which this document now gives its concrete mechanism).

## 5. Sync vs. Async

**Everything past the initial enqueue call is asynchronous.** No part of this platform's evaluation triggering is designed to be awaited synchronously by a source module's own request/response cycle. A user-facing "recalculation pending" state (per [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §6) is the correct and expected UX consequence, not a defect to engineer around.

## 6. Queue Ownership

One shared queue/job type, owned exclusively by the Continuous Evaluation Engine module. Every producer calls the identical `notify_source_data_changed` entry point; none maintains its own queue, job type, or retry policy for this purpose. See [ADR-023](../adr/ADR-023-platform-event-architecture.md) Decision, "Queue ownership."

## 7. Idempotency

Every triggered job performs a **full recompute** for the affected scheme version(s) — never a partial or delta update. A job run twice (e.g. after a retry) for the same underlying change produces the same result both times. See [ADR-023](../adr/ADR-023-platform-event-architecture.md) Decision, "Idempotency," for the full reasoning; this is the structural property that makes the retry behaviour in §8 safe.

## 8. Retry Behaviour

Delegated entirely to the existing RQ job-retry mechanism already available via `app.core.queue` — no new retry policy is defined by this document. Because every job is a full, idempotent recompute (§7), a retried job after a transient failure is safe by construction.

## 9. Event Naming Philosophy

`change_descriptor` uses the same dot-namespaced convention already established by the codebase's own `Permission.permission_id` catalog: `module.resource.action`.

Examples, illustrative:

```text
substation_registry.substation.status_changed
equipment_registry.circuit.corrected
alsf_registry.function.status_changed
sensitive_customer_registry.facility.created
sensitive_customer_registry.association.changed
pss_e_integration.snapshot.activated
network_model.topology.recalculated
stage_setting_registry.stage_setting_set.entered_in_error
engineering_parameters.parameter.changed
```

A new producer follows this pattern without needing a new naming decision. See [ADR-023](../adr/ADR-023-platform-event-architecture.md) Decision, "Event naming philosophy," for why `change_descriptor` is carried even though today's handler does not currently branch meaningfully on its value (audit/observability, and forward-compatibility for a future more selective strategy, should one ever be justified by evidence).

## 10. Integration Contract for Future Modules

A future scheme module (SPS, RAS, or any other) that wants its own data changes to trigger Continuous Evaluation recomputation need only:

1. Call `ContinuousEvaluationService.notify_source_data_changed(change_descriptor)` after any commit to data another module's findings might depend on.
2. Use a `change_descriptor` in the `module.resource.action` shape (§9).
3. Do nothing else — no queue setup, no retry configuration, no new infrastructure. The Continuous Evaluation Engine's own worker and full-recompute logic (per [ADR-022](../adr/ADR-022-continuous-evaluation-detector-framework.md)) already handle the rest.

This is the concrete mechanism that satisfies this task's own goal of letting "future modules integrate consistently" — one call, one naming convention, no per-module bespoke wiring.

## 11. What This Document Does Not Cover

- Any communication pattern other than "notify Continuous Evaluation that something changed." Ordinary synchronous service-layer reads between modules (e.g. a scheme module reading Substation Registry data) are unaffected and continue exactly as [`shared-defence-scheme-domain-model.md`](shared-defence-scheme-domain-model.md) §8 already describes.
- Any new infrastructure component. This document describes a usage pattern for infrastructure that already exists (`app.core.execution` / `app.core.queue`).
