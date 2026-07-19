# Shared Defence-Scheme Platform — Implementation

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (A6, A8, A9, §21). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md). Realizes [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md)/[EDR-009](../engineering/edr/EDR-009-grid-defence-scheme-lifecycle-realignment.md) and [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §2, §4, §5 as reusable backend/frontend infrastructure — this document describes what was actually built, not a new architectural decision (no new ADR is introduced by this document).

Related: [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md), [scheme-future-extensibility.md](scheme-future-extensibility.md), [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md), [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md), [platform-event-architecture.md](platform-event-architecture.md), [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md).

**Status.** Implemented (`backend/app/modules/scheme_platform/`, `frontend/src/components/scheme-platform/`) as of this sprint. This is shared platform infrastructure only — **no scheme calculation of any kind, and no UFLS, UVLS, or EMLS implementation, exists in this module.** No concrete scheme module has been built against it yet.

---

## 1. Why the Shared Platform Exists

Every future Defence Scheme module (UFLS, UVLS, EMLS today; SPS, RAS, Black Start, Islanding Strategy, Restoration Planning tomorrow) needs the identical *shape* of version lifecycle, metadata, and platform-event integration — not because they share engineering meaning (they do not: a UFLS stage and an EMLS priority group are genuinely different concepts), but because the **lifecycle a Scheme Version passes through, and the bookkeeping that lifecycle requires, is exactly the same shape regardless of scheme type** (ADR-015; shared-defence-scheme-domain-model.md §4).

Building this once, here, means a future concrete scheme module implements only its own genuinely-different policy layer (stage structure, priority ordering, thresholds, assignment rules) and composes with this platform for everything else — never re-deriving lifecycle transition rules, never re-wiring platform event integration, never inventing its own metadata shape.

## 2. What This Is Not

Per [scheme-future-extensibility.md](scheme-future-extensibility.md): *"This pack deliberately does not build a single, generic 'Assignment' or 'Scheme' abstraction that UFLS/UVLS/EMLS/future schemes all inherit from identically."* This module is **not**:

- a standalone, queryable `scheme_version` table with a `scheme_type` discriminator column — no such table exists, and none is created here;
- a runtime-polymorphic dispatch framework — there is no `SchemeType`-keyed branching anywhere in this module;
- an implementation of any scheme's own engineering logic — no stage, no priority group, no assignment, no threshold, no MW calculation exists here.

It is a **shared kernel**: plain Python value types, a pure lifecycle-transition validator, an abstract (non-instantiable) SQLAlchemy mixin, reusable Pydantic DTO base classes, reusable repository query functions parameterized by a concrete model class, and a lifecycle service that operates only on the mixin's own shared attributes.

## 3. Module Boundaries

`backend/app/modules/scheme_platform/` owns:
- the lifecycle enum and transition validator (`lifecycle.py`);
- the shared persistence mixin (`models.py`) — never a table of its own;
- shared DTO base classes (`schemas.py`);
- reusable repository query helpers (`repository.py`);
- the reusable lifecycle service, including platform-event integration (`service.py`).

It owns **no data of its own** — nothing here is migrated, nothing here is queryable independently of a concrete scheme module's own table.

A future concrete scheme module (e.g. `app/modules/ufls/`) owns:
- its own Defence Scheme identity table (`UflsScheme`) and its own concrete `UflsSchemeVersion(SchemeVersionMixin, Base)`, adding `scheme_id` (its own FK) and its own scheme-specific columns;
- its own repository, calling this platform's own `repository.py` helpers where the query is generic (`get_current_published`, `get_next_version_number`, `list_versions`) and its own queries where scheme-specific;
- its own service, composing `SchemeVersionLifecycleService` for lifecycle transitions and orchestrating its own structural validation, its own `PublicationRecordService.evaluate_and_record_publication` call (already built, Sprint 4), and its own scheme-specific writes, all within one transaction;
- its own router, schemas (extending this platform's own base DTOs), and frontend pages (composing this platform's own shared components).

Dependency direction (CLAUDE.md A2/F2): this module depends on nothing scheme-specific; every future scheme module depends on this one. This module itself depends on Continuous Evaluation (`app.modules.continuous_evaluation`, for platform-event integration) and IAM (`user.user_id`, for actor attribution) — both Core Platform/Shared Platform tier, never a scheme module.

## 4. Inheritance Strategy

**Composition and mixin inheritance, not a class hierarchy with runtime dispatch.**

- `SchemeVersionMixin` is an `__abstract__ = True` SQLAlchemy declarative mixin. A concrete module's own model multiply-inherits from it (`class UflsSchemeVersion(SchemeVersionMixin, Base)`), contributing the shared columns to that module's **own** concrete table — there is exactly one physical table per concrete scheme module, never a shared one.
- `SchemeVersionLifecycleService` is a plain class a concrete module's own service **composes with** (constructs and calls), not a base class a concrete service extends — the concrete module's own service remains free to define its own additional operations without inheriting this service's own method resolution order.
- `SchemeVersionSummaryBase`/`SchemeVersionDetailBase` (Pydantic) are meant to be **extended** by a concrete module's own richer DTOs (ordinary Pydantic model inheritance), adding scheme-specific fields.
- Deliberately excluded from the mixin: `scheme_id` (its FK target differs per concrete module) and any self-referential "superseded by" column. Each concrete module adds these itself — a small, explicit, one-line addition, not worth generic `declared_attr` machinery for a single column (CLAUDE.md §21).

## 5. Lifecycle Philosophy

**Exactly ADR-015/EDR-009's four states — not the generic six-state Canonical Version Lifecycle (CLAUDE.md A3) a naive reading of "Draft → Submitted for Review → Approved → Activated → Archived" might suggest.**

Six Project Owner engineering-discovery workshops ratified:

```text
Draft -> Published -> Superseded
                    -> Entered in Error
         Superseded -> Entered in Error
```

There is no `Under Review` state and no `Approved` state distinct from `Published` — review and approval are evidence-gathering activity that happens *within* Draft, made rigorous by continuously-visible findings (Continuous Evaluation), not separate gated states. There is no `Archived` state — `Superseded` and `Entered in Error` are both already permanent, queryable, terminal states (CLAUDE.md §5.2). `Superseded -> Published` reactivation is an explicitly open question (ADR-015 §"Reactivation") and is **not implemented** — this platform's own lifecycle is forward-only.

This is a deliberate, necessary deviation from a literal reading of this sprint's own task prompt, which described the older, superseded six-state shape. CLAUDE.md's own precedence rules (F1: Project Vision & Engineering Principles rank above Accepted ADRs, which rank above implementation) require preserving the ratified engineering decision. See §7, below, for the exact reconciliation.

## 6. Version Philosophy

A Scheme Version is the versioned aggregate root belonging to exactly one Defence Scheme (shared-defence-scheme-domain-model.md §2). This platform's own mixin carries: identity (`version_id`), a sequential `version_number` (scoped per scheme, computed by `repository.get_next_version_number`), the lifecycle status, publish/supersede/entered-in-error timestamps and actors, engineering remarks, and audit timestamps. It carries **no MW, no derived topology, no evaluation result** — those are never stored as Scheme Data, at any time, in any module (scheme-engineering-principles.md §11), and this shared platform is no exception.

Publication remains the one authorized, audited, Administrator-only decision point (§8, below) — extending [ADR-010](../adr/ADR-010-engineering-decision-support-philosophy.md)'s "Activation is the engineering decision; review is informational" philosophy, exactly as ADR-015 itself frames it.

## 7. Reconciliation With This Sprint's Own Task Prompt

This sprint's own task described a lifecycle of `Draft → Submitted for Review → Approved → Activated → Archived`. That description matches CLAUDE.md A3's general-purpose Canonical Version Lifecycle — the same lifecycle [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md) explicitly, narrowly supersedes *for Defence Scheme Version data specifically*, following six ratified Project Owner engineering-discovery workshops ([EDR-009](../engineering/edr/EDR-009-grid-defence-scheme-lifecycle-realignment.md)).

Per this sprint's own explicit instruction — *"If implementation details appear to conflict with the engineering philosophy, preserve the engineering philosophy and propose architectural adjustments instead of changing the intended engineering behavior"* — this implementation follows ADR-015's ratified four-state model, not the task prompt's own literal (and, for this specific domain, superseded) five-state description. No new ADR was required: ADR-015 already governs this exact question, and this implementation applies it, rather than reopening it.

## 8. Publication Prerequisites and Validation Entry Points

This sprint's own task asked for "Validation Entry Points... extension points only... to allow Continuous Evaluation, Compliance checks, Future engineering validators to integrate consistently." That mechanism already exists: `findings_publication_governance.publication.PublicationPrerequisiteResult`/`PublicationRequest` (Sprint 4) is the established, generic, scheme-agnostic structural-prerequisite contract every future scheme module's own service supplies when calling `PublicationRecordService.evaluate_and_record_publication`. This sprint does not duplicate that mechanism with a second "validator registry" (CLAUDE.md §21) — a concrete module composes both: this platform's own `SchemeVersionLifecycleService.publish()` for the entity-level state transition, and the existing `PublicationRecordService` call for prerequisite resolution and publication evidence, in the same transaction.

## 9. Platform Event Integration

`SchemeVersionLifecycleService` calls `ContinuousEvaluationService.notify_source_data_changed` (ADR-023) after every lifecycle transition (`draft_created`, `published`, `superseded`, `entered_in_error`), via `build_lifecycle_change_descriptor` — a reusable helper producing a correctly-namespaced `module.resource.action` descriptor (platform-event-architecture.md §9) from a caller-supplied `source_module` name. No engineering-specific event payload is invented; the descriptor carries only identity, timing, and (for Entered in Error) the mandatory reason. Since no `AffectedSchemeResolver` implementation exists yet (no concrete scheme module to resolve against), every such call currently resolves to zero affected targets and is a safe no-op in production — the integration point exists and is exercised by this module's own tests, ready for a future concrete module to make meaningful.

## 10. Router Patterns and Frontend Components — Scope Decision

**No generic FastAPI router was built this sprint.** A router's exact shape (which lifecycle actions are exposed as which HTTP verbs/paths, which permissions gate them) cannot be validated without a real concrete consumer, and inventing one speculatively risks exactly the premature, likely-wrong abstraction [scheme-future-extensibility.md](scheme-future-extensibility.md) and CLAUDE.md §21 warn against. The reusable router *pattern* is documented here (§3, above — a concrete module's own router, composing this platform's own service/schemas); the router code itself is deferred to the first concrete scheme module that needs it.

**Frontend shared components were built** (`frontend/src/components/scheme-platform/`): `LifecycleBadge`, `VersionBadge`, `SchemeVersionHeader`, `SchemeVersionMetadataPanel`, `PublicationHistoryPanel`. Named `PublicationHistoryPanel`, not "Review History"/"Approval History" as this sprint's own task prompt suggested — ADR-015 defines no separate review or approval state, so no separate review/approval history exists to render; the panel shows the lifecycle event history the ratified model actually has.

## 11. What Was Not Built (Explicitly Out of Scope This Sprint)

- Any UFLS, UVLS, or EMLS engineering logic, table, or route.
- `Superseded -> Published` reactivation (an explicitly open question, ADR-015).
- A generic FastAPI router or a generic "validator registry" (§8, §10, above — existing mechanisms already cover these needs).
- Version copying's own *structural* data (stages, priority groups, assignments) — genuinely scheme-specific, per shared-defence-scheme-domain-model.md §5; only the lifecycle/metadata portion of "a copied version starts as Draft" is covered by `create_draft()`.
