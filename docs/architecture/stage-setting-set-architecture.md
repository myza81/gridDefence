# Stage Setting Set Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (A6, A8). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md). Realizes [ADR-016](../adr/ADR-016-stage-setting-set-as-reusable-versioned-entity.md) (entity shape and lifecycle), [ADR-020](../adr/ADR-020-stage-setting-registry-as-standalone-shared-module.md) (module ownership), and [ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md) (a stage's one-or-many operating criteria) — read all three ADRs first for the decision rationale; this document is the architecture built from them.

Related: [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md), [ufls-engineering-philosophy.md](ufls-engineering-philosophy.md), [uvls-engineering-philosophy.md](uvls-engineering-philosophy.md).

**Module ownership (resolved 2026-07-15 by [ADR-020](../adr/ADR-020-stage-setting-registry-as-standalone-shared-module.md)):** the entities and interfaces described in this document are owned by a new, standalone **Stage Setting Registry** module (`app/modules/stage_setting_registry/`) — never duplicated inside UFLS or UVLS. Every mention of "the owning module" below refers to the Stage Setting Registry.

**Status: Implemented (Shared Platform Sprint 2; frontend, Draft deletion, and multiple operating criteria per stage added later — see below).** Backend module (`app/modules/stage_setting_registry/`: models, repository, service, router, schemas, exceptions, bootstrap), Alembic migrations (`0018_stage_setting_registry`, `0025_stage_setting_trigger`), and unit/API test suites are complete and verified on both SQLite and PostgreSQL. No Stage Setting Sets are seeded — this document defines no approved initial engineering records, so the registry starts empty (§14 of the implementing sprint's own instructions: no default UFLS/UVLS thresholds are invented). §8's own "policy-defined valid range... engineering parameter data" threshold-range validation is **not yet implemented** — no such parameter exists in Engineering Parameter Configuration yet (only `mw_tolerance_percentage` was seeded in Sprint 1); today this module validates threshold *structure* only (a positive decimal number), deferring range enforcement to a future addition once that parameter exists.

**Frontend implemented.** `frontend/src/modules/stage_setting_registry/` — list page, detail/edit page (stages grouped with their nested operating criteria), Draft deletion action. Routed at `/stage-setting-sets`.

**Draft deletion implemented ([ADR-024](../adr/ADR-024-stage-setting-set-draft-deletion.md)).** A `DRAFT` Stage Setting Set may be physically deleted; `Published`/`Entered in Error` remain permanently undeletable. See §6, §10 below.

**Multiple operating criteria per stage implemented ([ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md)).** A `StageSetting` (a stage) owns one or more `StageSettingTrigger` rows — see §3, §5–§13 below. `UflsStage.stage_setting_id` continues to reference the parent `StageSetting`, unchanged.

**§11's "which Scheme Versions reference this Stage Setting Set" interface is implemented, in the direction ADR-024 required it: as a read-only check `StageSettingRegistryService.delete_draft` performs before deleting, not as a general-purpose reverse lookup exposed for arbitrary callers.** Each scheme module (today: UFLS only) implements a small `SchemeVersionReferenceChecker` protocol (`app/modules/stage_setting_registry/reference_check.py`) answering "how many of my own Scheme Versions reference this set" against its own repository — the Stage Setting Registry never queries `ufls_scheme_version` (or a future `uvls_scheme_version`) directly (CLAUDE.md A1/A2). UVLS's own checker is simply absent until a `uvls` persistence module exists.

---

## 1. Purpose

A Stage Setting Set is the reusable, independently-versioned definition of a staged scheme's stage structure — thresholds, delays, and (for UVLS) regional scoping — separated from any one Scheme Version so that multiple versions of the same scheme type can share an identical, unmodified stage design without duplicating it.

## 2. Scope

Applies to UFLS and UVLS only. EMLS has no Stage Setting Set — its Priority Groups are owned directly by the Scheme Version ([shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §2.3).

## 3. Owned Entities

| Entity | Description |
|---|---|
| `StageSettingSet` | The stable identity, description, and lifecycle-governed container for one ordered stage structure, belonging to exactly one scheme type. |
| `StageSetting` | One shedding stage within a Stage Setting Set — `stage_order` and (UVLS only) an optional region scope. Owns one or more `StageSettingTrigger` rows ([ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md)); carries no threshold or time delay directly. |
| `StageSettingTrigger` | One independent frequency/voltage-time operating criterion for a stage — `trigger_order`, a threshold, a time delay ([ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md)). Satisfaction of any one trigger under a stage constitutes operation of that same stage; a stage may own several. |

## 4. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| Region | Core Platform (reference data) | `region_id`, read-only, UVLS `StageSetting.region_scope_id` only — unchanged from [`uvls-module.md`](uvls-module.md) §7.2's own region-scoping reasoning |
| `UflsSchemeVersion` / `UvlsSchemeVersion`-equivalent | Defence Scheme (UFLS / UVLS) | Not referenced by `StageSettingSet` itself — the reference runs the other way (a Scheme Version references a Stage Setting Set), per §5 |

## 5. Domain Model

```
StageSettingSet (1) ──── (many) StageSetting ──── (many) StageSettingTrigger
                              │
                              └── references (read-only, UVLS only) ──▶ Region.region_id (Core Platform, external)

UflsSchemeVersion / UvlsSchemeVersion (many) ──── references ───▶ StageSettingSet.stage_setting_set_id (owned by the scheme type, external to the version)

UflsStage / UvlsStage (many) ──── references ───▶ StageSetting.stage_setting_id (the stage — never an individual StageSettingTrigger)
```

A Stage Setting Set is never owned by, or nested inside, a Scheme Version. The reference always runs from the version toward the set, never the reverse — a Stage Setting Set has no knowledge of which, or how many, Scheme Versions currently reference it, except via the narrow, deletion-time-only read-only check described in §11 and [ADR-024](../adr/ADR-024-stage-setting-set-draft-deletion.md).

**A `UflsStage`/`UvlsStage` references the parent `StageSetting` (the stage), never an individual `StageSettingTrigger` ([ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md)).** Selecting a stage gives the Scheme Version access to every trigger configured under it. No assignment (target MW, Shedding Actions) is duplicated merely because a stage owns more than one trigger.

**Only a `PUBLISHED` Stage Setting Set may ever be selected by a Scheme Version.** This is enforced by the scheme module's own service-layer validation at the moment a `stage_setting_set_id` is selected (e.g. `UflsService.update_version_metadata`) — never deferred to the Publish-time structural prerequisite alone (ADR-024, correcting an earlier divergence between this document and the as-built UFLS validation). A `DRAFT` or `ENTERED_IN_ERROR` Stage Setting Set is rejected immediately, with a structured domain error, the moment a Draft Scheme Version attempts to select it.

**A UFLS version must never reference a UVLS Stage Setting Set, and vice versa.** Enforced at the service layer (each scheme module validates the referenced set's own scheme-type discriminator matches its own before accepting the reference) and reinforced by a database CHECK/foreign-key scoping where practical.

## 6. Lifecycle / State Model

```text
Draft → Published → Entered in Error
```

| State | Editable? | Meaning |
|---|---|---|
| Draft | Yes | Free to add, remove, or reorder `StageSetting` rows and, within each stage, its own `StageSettingTrigger` rows ([ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md)). **Not referenceable by any Scheme Version** — enforced by the scheme module's own selection-time validation (§5, [ADR-024](../adr/ADR-024-stage-setting-set-draft-deletion.md)), not merely a documented convention. **May be physically deleted** ([ADR-024](../adr/ADR-024-stage-setting-set-draft-deletion.md)) — a never-Published Draft carries no historical weight (the same reasoning [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md) already applied to Defence Scheme Version Drafts, applied here on this entity's own terms). Deletion is blocked if any UFLS/UVLS Scheme Version references the set regardless of that version's own lifecycle state (defense-in-depth: with selection-time validation enforced, this should never trigger for a row created after ADR-024 shipped) and is recorded in `stage_setting_registry_audit_log`; deletion explicitly removes every owned `StageSettingTrigger`, then every owned `StageSetting`, then the set itself, in that order, in one transaction. |
| Published | No (immutable) | Structure — every stage **and every one of its triggers** — is frozen; referenceable by any number of Scheme Versions of the matching scheme type, concurrently or across time. **Never physically deleted** — permanent engineering record. |
| Entered in Error | No (immutable, terminal) | Correction mechanism for a Stage Setting Set that should never have been published — mandatory reason required. Existing references from already-Published Scheme Versions remain valid (CLAUDE.md §5.2); no new Draft Scheme Version may newly reference it (enforced at selection time, not only at Publish). **Never physically deleted** — permanent engineering record. |

No `Superseded` state — see [ADR-016](../adr/ADR-016-stage-setting-set-as-reusable-versioned-entity.md) Rationale for why a shared, multi-owner-referenced entity has no well-defined superseding trigger. No `Abandoned` state and no soft-delete flag either — [ADR-024](../adr/ADR-024-stage-setting-set-draft-deletion.md) rejects both for the identical reason ADR-016 rejects `Superseded`: a state with no engineering meaning distinct from non-existence.

## 7. Business Rules

1. A Published staged Scheme Version must reference a Published Stage Setting Set of the matching scheme type — a structural Publication prerequisite ([ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md)).
2. A Draft Scheme Version referencing a Stage Setting Set that is later marked Entered in Error acquires a structural Publication-blocking condition (it may no longer be Published while that reference stands) — the Draft's engineer must either select a different Published Stage Setting Set or wait for a replacement to be published.
3. A currently-Published Scheme Version referencing a Stage Setting Set later marked Entered in Error is unaffected structurally (CLAUDE.md §5.2 — its own Publication already happened against a then-valid reference) but acquires a Continuous Evaluation finding, flagging the situation for engineering review without altering the Published version itself.
4. Within a Stage Setting Set, `stage_order` values are unique. For UFLS: each stage's most severe trigger's threshold value must strictly decrease as `stage_order` increases, version-wide. For UVLS: the same, **within the same region scope** (including the grid-wide "null scope" group treated as its own scope) — unchanged from [`uvls-module.md`](uvls-module.md) §9 rule 4's own reasoning, now scoped to the Stage Setting Set rather than the Scheme Version, and amended by [ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md) to compare each stage's most severe (numerically lowest) trigger threshold rather than a single scalar. No ordering or monotonicity relationship is enforced *between* triggers within the same stage — they are independent criteria, not a sequence.
5. A Stage Setting Set with zero `StageSetting` rows may not be Published. **A `StageSetting` with zero `StageSettingTrigger` rows may not be published either** ([ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md) business rule 1) — every stage in a Stage Setting Set being published must own at least one trigger.
6. A Scheme Version may select a Stage Setting Set only if it is `PUBLISHED` and its `scheme_type` matches — validated at the moment of selection, not deferred to the Publish-time prerequisite alone ([ADR-024](../adr/ADR-024-stage-setting-set-draft-deletion.md)).
7. A `DRAFT` Stage Setting Set may be physically deleted, only by a caller holding `stage_setting_registry.manage`, only if no UFLS/UVLS Scheme Version references it ([ADR-024](../adr/ADR-024-stage-setting-set-draft-deletion.md)). `PUBLISHED` and `ENTERED_IN_ERROR` Stage Setting Sets may never be physically deleted, by any caller, under any condition.
8. `trigger_order` is unique within its parent stage; the pair (threshold value, time delay) is unique within its parent stage — an identical pair configured twice is a data-entry error, not a second real operating criterion ([ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md) business rules 2–3).

## 8. Validation Rules

- `StageSettingTrigger.threshold_value` must fall within a policy-defined valid range for its physical quantity (Hz for UFLS, per-unit voltage for UVLS) — engineering parameter data (CLAUDE.md A7), never a hardcoded application constant.
- `StageSettingTrigger.time_delay_ms` must be `>= 0`.
- `StageSettingTrigger.trigger_order` is unique within its parent stage; the (`threshold_value`, `time_delay_ms`) pair is unique within its parent stage ([ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md)).
- UVLS's `region_scope_id`, if set, must reference an existing, valid Core Platform `region` row.
- A Stage Setting Set's `scheme_type` (`UFLS` | `UVLS`) is immutable once any `StageSetting` row exists against it.

## 9. Database Design (Concept)

Conceptual only — no migrations are defined here.

| Table (conceptual) | Key columns (conceptual) | Notes |
|---|---|---|
| `stage_setting_set` | `stage_setting_set_id` (UUID PK), `scheme_type` (`UFLS` \| `UVLS`), `description`, `status`, `created_by_user_id`, `updated_by_user_id`, `created_at`, `updated_at` | UUID PK per CLAUDE.md A5 — a genuine business entity. |
| `stage_setting` | `stage_setting_id` (UUID PK), `stage_setting_set_id` (FK), `stage_order`, `region_scope_id` (FK, external, nullable, UVLS only) | Unique on (`stage_setting_set_id`, `stage_order`) and, for UVLS, (`stage_setting_set_id`, `region_scope_id`, `stage_order`). Carries no threshold or time delay ([ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md)) — those live on its own `stage_setting_trigger` rows. |
| `stage_setting_trigger` | `stage_setting_trigger_id` (UUID PK), `stage_setting_id` (FK, `ON DELETE RESTRICT`), `trigger_order`, `threshold_value`, `threshold_unit` (denormalized display convenience, derived from the grandparent's `scheme_type`), `time_delay_ms` | Unique on (`stage_setting_id`, `trigger_order`) and (`stage_setting_id`, `threshold_value`, `time_delay_ms`). Introduced by [ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md), migration `0025_stage_setting_trigger`. |

`{Ufls,Uvls}SchemeVersion.stage_setting_set_id` (owned by the Defence Scheme domain, per [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md)) is a foreign key into `stage_setting_set`, `ON DELETE RESTRICT`. `{Ufls,Uvls}Stage.stage_setting_id` is a foreign key into `stage_setting` (the stage, never `stage_setting_trigger`), `ON DELETE RESTRICT`, unchanged by ADR-025.

## 10. API Contract (Concept)

- `stage-setting-sets` — list/create/retrieve, filtered by `scheme_type`; writes permitted only while `Draft`.
- `stage-setting-sets/{id}/settings` — nested read/write for stages, writes permitted only while the owning set is `Draft`. Creating a stage accepts only `stage_order` and (UVLS only) `region_scope_id` — no threshold or time delay ([ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md)); each returned stage nests its own `triggers` array.
- `stage-setting-sets/{id}/settings/{stage_setting_id}/triggers` — nested read/write for one stage's own operating criteria, writes permitted only while the owning set is `Draft` ([ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md)). Supports add, update, remove, and reorder, mirroring the stage-level `/settings` endpoints' own established shape one level deeper.
- `DELETE stage-setting-sets/{id}` — physical deletion, `Draft` only, `stage_setting_registry.manage` ([ADR-024](../adr/ADR-024-stage-setting-set-draft-deletion.md)). Returns the module's own established successful-delete response (`204`) and a structured domain error — never a raw database exception — for: the set not existing (`404`), the set not being `Draft` (`400`, this module's own established `ValidationAppError` convention — no `409` is used anywhere else in this codebase and none is introduced here for consistency), or the set being referenced by any UFLS/UVLS Scheme Version (`400`, same convention, reporting the reference count). Deletion explicitly removes every owned trigger, then every owned stage, then the set.
- `stage-setting-sets/{id}/publish` — lifecycle transition, now also rejecting a set where any stage owns zero triggers ([ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md)); `stage-setting-sets/{id}/enter-in-error` — correction, mandatory reason.
- A Scheme Version's own create/edit contract accepts `stage_setting_set_id`, validated against the version's own scheme type **and** its `PUBLISHED` status ([ADR-024](../adr/ADR-024-stage-setting-set-draft-deletion.md)) at the moment of selection.

## 11. Service Interfaces

The Stage Setting Registry module (§ownership note above) exposes:

- A read-only interface for the current set of Published Stage Setting Sets, filtered by scheme type — consumed by UFLS and UVLS for the Engineering Workspace's Stage Setting Set selection step, per CLAUDE.md A1 (service-layer interface, never direct table access). Each returned stage nests its own trigger list ([ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md)).
- **`delete_draft`'s own reference-check, implemented as the reverse of the naive design** — rather than the Stage Setting Registry querying `ufls_scheme_version`/`uvls_scheme_version` directly (forbidden: CLAUDE.md A2, a "lower-tier" registry module must never depend on "upper-tier" Scheme Data), each scheme module implements a small `SchemeVersionReferenceChecker` protocol (`app/modules/stage_setting_registry/reference_check.py`) against its own repository, and the Stage Setting Registry calls that protocol, lazily composed at `StageSettingRegistryService.__init__` time (mirroring `continuous_evaluation`'s own `build_default_*`/injectable-override composition pattern) — never a hard, module-load-time import of `app.modules.ufls` from this module's own core files. This same interface also answers "which Scheme Versions currently reference this Stage Setting Set" for the Entered-in-Error correction workflow's own informational purposes (§7 rule 2/3) and general audit/reporting, superseding this section's earlier "deferred, no consumer exists yet" status.

It consumes Core Platform's Region reference data, read-only, for UVLS scoping validation.

## 12. Audit Requirements

**Resolved by [ADR-020](../adr/ADR-020-stage-setting-registry-as-standalone-shared-module.md):** owned exclusively by the Stage Setting Registry module's own `stage_setting_registry_audit_log`, per CLAUDE.md A4 — not shared with, or duplicated inside, UFLS's or UVLS's own audit logs. Every create, edit (while Draft), Publish, Entered-in-Error transition, and Draft deletion is recorded: who, when, what changed, why (mandatory reason for Entered in Error; optional for a Draft deletion, per the module's own established `change_reason` convention). A Draft deletion's own audit entry captures the deleted set's identifying metadata (scheme type, description, setting count, and trigger count at time of deletion) in `old_value`, since the row itself no longer exists afterward to look this up ([ADR-024](../adr/ADR-024-stage-setting-set-draft-deletion.md)). **Since ADR-025:** a `STAGE_SETTING_TRIGGER` subject type is added, audited identically for add/update/remove/reorder — `stage_setting_trigger_id` on the audit log, like `stage_setting_id` before it, is deliberately not a foreign key, so a removed trigger's own audit history survives its row being deleted.

## 13. Testing Requirements

Per CLAUDE.md §18/A11: threshold/order uniqueness and monotonicity (including UVLS's region-scoped variant); immutability once Published; the "Entered in Error blocks new Draft references, does not affect existing Published references" rule; reference-integrity between a Scheme Version and its Stage Setting Set across scheme-type boundaries (a UFLS version must be rejected if it attempts to reference a UVLS set). **Since ADR-024:** Draft physical deletion (empty and with child settings, atomic parent+children deletion, audit entry written, `stage_setting_registry.manage` required, rejected for Published/Entered-in-Error, rejected when referenced by a UFLS Draft or Published version, database `ON DELETE RESTRICT` remains effective as the final guarantee, transaction rollback leaves parent/children/audit log mutually consistent); selection-time validation (a Draft version must reject selecting a Draft or Entered-in-Error Stage Setting Set, must accept a Published matching-scheme-type set, wrong scheme type remains rejected); historical Published UFLS data remains fully readable after its referenced Stage Setting Set is later marked Entered in Error. **Since ADR-025:** one stage with one trigger; one stage with several triggers; duplicate trigger_order rejected; duplicate (threshold, delay) pair rejected; stage_order remains unique at the parent-stage level regardless of trigger count; trigger add/update/remove/reorder while Draft; no trigger modification after Publish; publication blocked for a stage with zero triggers; monotonicity evaluated against each stage's most severe trigger; audit events for trigger changes; Draft deletion removes owned triggers explicitly before their owning stages; the `0025_stage_setting_trigger` migration converts each pre-existing `StageSetting` row into one child trigger without disturbing any existing identity, Published Stage Setting Set, or UFLS stage reference; a UFLS stage exposes every trigger associated with its referenced stage.

## 14. Future Extensions

- A "clone Stage Setting Set" convenience action (start a new Draft set pre-populated from an existing Published one) — a UX convenience, not a new architectural concept.
- Versioned diffing between two Stage Setting Sets, for engineers comparing candidate stage designs before committing to one.
