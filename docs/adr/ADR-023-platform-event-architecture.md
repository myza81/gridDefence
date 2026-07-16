# ADR-023: Platform Event Architecture

- **Status:** Accepted
- **Date:** 2026-07-15
- **Implementation status (Shared Platform Sprint 6, 2026-07-16):** Consumer and refresh infrastructure implemented; source integration pending. `ContinuousEvaluationService.notify_source_data_changed`, the shared `ExecutionEngine`-based enqueue path (a new, exclusively-owned `continuous_evaluation` RQ queue alongside PSS/E Integration's own, both drained by the same worker process), idempotent full-recompute jobs, and the disposable `EvaluationProjection` (`backend/app/modules/continuous_evaluation/`) are implemented. No source module (Substation Registry, Equipment Registry, ALSF Registry, Sensitive Customer Registry, PSS/E Integration, Network Model, Stage Setting Registry, Engineering Parameter Configuration) yet calls `notify_source_data_changed` — that wiring remains a later integration sprint, per this ADR's own §5 ("no module other than Continuous Evaluation subscribes... single producer-to-single-consumer relationship"). The `AffectedSchemeResolver` and `EvaluationRequestProvider` seams this sprint introduces are typed interfaces with test fakes only — no real source-to-scheme mapping or real scheme adapter exists yet, since no real scheme module (UFLS/UVLS/EMLS) exists.
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.5 Deterministic Behaviour, §21, A1)
- **Depends on:** [ADR-022](ADR-022-continuous-evaluation-detector-framework.md) (this ADR decides how source modules *trigger* an evaluation; ADR-022 decides what happens *inside* one, once triggered — the two are independent halves of the same pipeline and do not constrain each other's decision)
- **Affects:** [docs/architecture/continuous-evaluation-architecture.md](../architecture/continuous-evaluation-architecture.md) (gains a cross-reference to the new [platform-event-architecture.md](../architecture/platform-event-architecture.md)), [docs/architecture/codex-foundation-readiness-audit-brief.md](../architecture/codex-foundation-readiness-audit-brief.md) §1.13 (resolved — see Consequences)
- **Informed by:** the Shared Defence-Scheme Platform Implementation Readiness Review, which identified "how does a change in Substation Registry / Equipment Registry / ALSF Registry / Sensitive Customer Registry / PSS/E Integration / Network Model actually reach the Continuous Evaluation Engine" as an undecided platform-level question

---

## Context

`continuous-evaluation-architecture.md` §3 already establishes a hybrid evaluation model — on-demand evaluation when an engineer opens the Engineering Workspace, plus background recalculation when upstream data changes underneath a scheme version nobody currently has open. What has not been decided anywhere in the pack is the *mechanism* connecting the two: when the Substation Registry changes a substation's operational status, or the Sensitive Customer Registry adds a facility, or PSS/E Integration imports a new network snapshot, how does that fact reach the Continuous Evaluation Engine so it knows to recompute findings for every scheme version that depends on the changed data?

The existing codebase already has one piece of asynchronous infrastructure suited to this: `app.core.execution` / `app.core.queue`, a Redis/RQ-backed job submission mechanism, already used elsewhere in the platform for background work. No event bus, message broker, or pub/sub layer exists today, and none is otherwise needed by anything else in the current architecture pack.

## Decision

**All Continuous Evaluation triggers are asynchronous, via the existing Redis/RQ infrastructure — no new event bus or message broker is introduced.**

### Trigger mechanism

Every source module (Substation Registry, Equipment Registry, ALSF Registry, Sensitive Customer Registry, PSS/E Integration, Network Model, and every future scheme module) calls one new, shared, in-process service method after committing a change that could affect evaluation results:

```text
ContinuousEvaluationService.notify_source_data_changed(change_descriptor)
```

This call happens synchronously, in-process, inside the same service-layer transaction boundary as the source module's own write (an ordinary same-module-tier method call, per CLAUDE.md A1 — not a network call, not a message publish). Its own implementation does exactly one thing: it enqueues one background job onto the existing Redis/RQ queue and returns immediately. The source module never waits for evaluation to complete, never learns the outcome synchronously, and never blocks its own transaction on Continuous Evaluation's own work.

### Queue ownership

**One shared queue/job type, owned exclusively by the Continuous Evaluation Engine module.** Source modules do not each own their own queue or job type — they all call the same `notify_source_data_changed` entry point, and the Continuous Evaluation Engine's own worker is the only consumer. This mirrors CLAUDE.md A1's own principle applied to asynchronous communication: the owning module (Continuous Evaluation) owns the mechanism by which it is invoked, exactly as it would own a synchronous service interface.

### Idempotency

**Every triggered job performs a full recompute for the affected scheme version(s) — never an incremental delta.** This is a deliberate simplification, not an oversight: `continuous-evaluation-architecture.md` §3 already establishes that on-demand evaluation is a full recompute against the current snapshot; making the background-triggered path use the identical full-recompute logic (the same `evaluateFindings` entry point ADR-022 already specifies) means:
- a job that runs twice for the same change produces the same result both times (naturally idempotent — CLAUDE.md §5.5, "the same engineering input shall always produce the same engineering result");
- a burst of several source-data changes in quick succession collapses safely into however many recompute jobs actually run — running one extra time wastes some compute, never produces a wrong or partial result;
- no delta-tracking, change-diffing, or partial-invalidation logic is needed anywhere in the platform, which would be exactly the premature complexity CLAUDE.md §21 warns against for a first implementation.

### Retry behaviour

Retry is delegated entirely to the existing RQ job-retry mechanism already available in `app.core.queue` — no new retry policy is introduced by this ADR. Because every job is a full, idempotent recompute (above), a retried job after a transient failure (a database contention error, a momentary service unavailability) is safe by construction: re-running it produces the same correct result a first successful run would have, never a duplicate or inconsistent one.

### Event naming philosophy

`change_descriptor` identifies *what kind of thing changed*, using the same dot-namespaced convention the codebase's own `Permission.permission_id` catalog already establishes (`module.resource.action`, e.g. `substation_registry.substation.status_changed`, `sensitive_customer_registry.facility.created`, `network_model.topology.recalculated`, `pss_e_integration.snapshot.imported`). Reusing an already-established, already-understood naming convention (rather than inventing a second one for events) keeps the platform's own vocabulary consistent, and gives every future module a naming pattern to follow without a new decision.

The Continuous Evaluation Engine's own job handler does not need to branch meaningfully on `change_descriptor`'s exact value today (every trigger currently results in the identical full-recompute path) — it is carried for two reasons only: (1) audit/observability (knowing why a recompute ran, for diagnosis and for the audit trail CLAUDE.md §5.4 requires), and (2) so a future, genuinely more selective evaluation strategy (should one ever become necessary) has the information it would need, without requiring every source module to be changed again to supply it retroactively.

### What this does not include

No event bus, no message broker (Kafka, RabbitMQ, etc.), no pub/sub layer, and no new infrastructure dependency beyond the Redis/RQ pair already present in the codebase. No module other than Continuous Evaluation subscribes to these notifications — this is a single producer-to-single-consumer relationship (many source modules, one consumer), not a general-purpose platform event bus serving multiple future subscribers. If a second, genuinely independent consumer of "something changed" notifications emerges in the future (unforeseen today), that would be a new architectural decision, made with an ADR at that time — not something this ADR pre-builds for speculatively.

## Rationale

**Reusing existing infrastructure is the CLAUDE.md §21-correct choice, and it is sufficient.** `app.core.execution` / `app.core.queue` already provides exactly what this trigger mechanism needs — asynchronous job submission, with retry, already proven elsewhere in the codebase. Introducing a message broker or event bus to solve a single-producer-pattern, single-consumer problem would be infrastructure the requirement does not justify.

**Full-recompute idempotency is what makes "async, retryable, best-effort" a safe design rather than a source of engineering error.** CLAUDE.md §5.5 requires deterministic behaviour — the same engineering input must always produce the same engineering result. A delta/incremental-update design would need to get every edge case of partial invalidation correct to preserve that guarantee; a full-recompute design gets it by construction, at the cost of some redundant computation the platform is not, today, evidence-shown to need to avoid (CLAUDE.md §21 — "performance improvements shall be based on measured evidence," not anticipated ahead of it).

**A single, shared, Continuous-Evaluation-owned queue — not one queue per source module — keeps the ownership model simple and consistent with CLAUDE.md A1.** Every source module needs exactly one thing from this relationship: "tell Continuous Evaluation something changed." Giving each source module its own queue or job type would multiply the surface area for no corresponding benefit, since every one of them ends up calling the identical downstream recompute logic regardless.

## Consequences

**Positive:**
- Directly resolves `codex-foundation-readiness-audit-brief.md` §1.13's open question ("is the existing Redis/RQ infrastructure sufficient for event-driven recalculation, or does the platform need something more") — the existing infrastructure is confirmed sufficient, no new infrastructure dependency is introduced.
- Gives every current and future source module (including every future scheme module) one obvious, already-proven integration point (`notify_source_data_changed`), with one naming convention to follow.
- Idempotency and retry safety are structural, not a policy every caller must separately get right.

**Negative / trade-offs:**
- Full recompute on every trigger is less computationally efficient than a selective/incremental design would be — an accepted, deliberate trade-off given no measured evidence yet exists that this matters at the platform's current scale (CLAUDE.md §21).
- `change_descriptor` carries more information than the current implementation strictly consumes (see "Event naming philosophy," above) — a small, intentional forward-compatibility allowance, not speculative infrastructure, since the cost is a naming convention, not a subsystem.
- Every source module gains one new, mandatory call at the end of its own relevant write paths — a small, ordinary integration cost, no different in kind from the audit-log calls every module already makes on every write (CLAUDE.md A4).

---

## Alternatives Considered

1. **Asynchronous, Redis/RQ-based, single shared queue, full-recompute, as decided above.** **Adopted.** Reuses proven infrastructure; idempotent and retry-safe by construction; matches CLAUDE.md §21's proportionality principle.

2. **Synchronous, in-process recompute at the moment of the source change (no queue at all).** **Rejected.** Would couple every source module's own write transaction to the performance and correctness of Continuous Evaluation's own recompute logic, directly on the critical path of unrelated writes (e.g. a Substation Registry status change would be slowed by, and could fail because of, an unrelated Continuous Evaluation bug) — violates the separation of concerns CLAUDE.md A1 and §12 already establish between modules.

3. **A new general-purpose event bus / message broker, supporting future multi-subscriber pub/sub.** **Rejected as premature.** No second subscriber exists or is currently anticipated by any document in this pack; building multi-subscriber infrastructure for a single-consumer problem is exactly the "infrastructure a requirement does not actually need" CLAUDE.md §21 warns against. Revisit with a new ADR if and when a genuine second subscriber emerges.

4. **Incremental/delta-based recompute, tracking exactly which findings are affected by a given change.** **Rejected for this first implementation.** Correctness-critical and materially more complex than full recompute, with no measured performance evidence yet that full recompute is inadequate — reconsider only if evidence emerges (CLAUDE.md §21).
