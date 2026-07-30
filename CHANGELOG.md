# GridDefence Changelog

This changelog records what has actually shipped, phase by phase, per
[`docs/architecture/implementation-plan.md`](docs/architecture/implementation-plan.md).
It is a factual record of implementation outcomes — not a design document.
Architecture rationale lives in `docs/architecture/` and `docs/adr/`;
day-to-day workflow lives in [`DEVELOPMENT.md`](DEVELOPMENT.md); review
criteria live in [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md).

Entries are added, never rewritten, as phases complete.

---

## Equipment Registry - Deterministic Transformer Pagination

**Scope:** Backend correctness fix for the Transformer Registry list endpoint.
Paginated Transformer queries now keep the existing user-facing
`transformer_number` ordering but add `transformer_id` as a stable unique
tie-breaker, producing a deterministic total order for `OFFSET`/`LIMIT`
pagination. The previous query ordered only by `transformer_number`, which is
non-unique and could duplicate rows across pages while omitting legitimate
records. Response schemas, filters, lifecycle semantics, authorization,
page-size behavior, and total-count semantics are unchanged.

**Tests:** Added service and API regression coverage that creates multiple
Transformers sharing the same `transformer_number`, traverses all pages with a
small page size, verifies every expected `transformer_id` is returned exactly
once, confirms the unique count equals the reported total, repeats traversal to
prove the ordered ID sequence is stable, and covers search/status filtering plus
`ENTERED_IN_ERROR` visibility behavior.

---

## Reference Data — Add Thailand and Singapore as State Options

**Scope:** Reference-data refinement only. Extends the existing flat `state`
reference list with two neighbouring interconnected systems so future
engineering records at the northern/southern grid boundaries may reference
them: `THA` (Thailand) and `SGP` (Singapore). No Country/Nation/Region-Group
hierarchy is introduced and the `State` model is unchanged — these are ordinary
`state` rows, exactly like every existing option. Not related to the completed
Substation Registry migration; no migrated Substation/Voltage-Yard record was
touched and no migration was rerun.

**Backend:** `app/reference_data/seed.py`'s `STATES` now lists the two rows
(idempotent `_seed_states` covers fresh databases); new migration
`0027_thailand_singapore_states` inserts them into already-deployed
databases — idempotent (inserts only a `code` not already present, so it is
safe alongside the seed), reversible (downgrade deletes only these two by
`code`; blocked by the `ON DELETE RESTRICT` FK if either is already
referenced), preserving every existing `state_id` and row. The read-only
`GET /reference-data/states` endpoint returns the two new values with no code
change.

**Frontend:** the State dropdown (Substation create/edit) now presents States
alphabetically by display name (A–Z) via `useReferenceData`, so the list scales
as options are added — presentation only; stored reference ids/codes are
unchanged.

**Tests:** backend seed test asserts the seeded States include `THA`/`SGP` while
the pre-existing Malaysian states remain; frontend tests assert the State
selector renders Thailand and Singapore in alphabetical order and that an
existing State selection still works after the list is extended.

## Stage Setting Registry — Multiple Operating Criteria per Stage (ADR-025)

**Scope:** Resolves a UFLS UAT-identified real-site configuration the as-built Stage Setting Registry could not represent — a single shedding stage carrying more than one independent relay operating criterion (e.g. Stage 8: 48.1 Hz at 0 ms delay, and 49.3 Hz at 60,000 ms delay). The prior one-threshold-per-stage model rejected a second setting sharing the same `stage_order`, since these are not separate shedding stages. See [ADR-025](docs/adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md).

**Decision:** A `StageSetting` (a stage) now owns one or more `StageSettingTrigger` rows, each an independent frequency/voltage-time operating criterion. Satisfaction of any one configured trigger constitutes operation of that same stage (an "any-of"/OR relationship, ratified via UFLS UAT engineering clarification, not silently assumed). `UflsStage.stage_setting_id` continues to reference the parent stage, unchanged — no UFLS assignment is duplicated because a stage carries more than one trigger. Between-stage monotonicity is evaluated using each stage's most severe (numerically lowest) trigger threshold. `docs/engineering/glossary.md` and `02-engineering-concepts.md`'s own Stage definitions are corrected to describe one-or-many operating criteria per stage.

**Backend (`backend/app/modules/stage_setting_registry/`):** new `StageSettingTrigger` model/table (`stage_setting_trigger`), owned by the parent `StageSetting`; `StageSetting` no longer carries `threshold_value`/`threshold_unit`/`time_delay_ms` directly. New migration `0025_stage_setting_trigger` creates the table, backfills exactly one trigger from every existing stage's own prior values, then drops the now-superseded columns (no deprecated compatibility columns retained — CLAUDE.md §5.1, no two authoritative copies). Verified upgrade/downgrade/re-upgrade on real PostgreSQL, preserving every existing `stage_setting_id` and `UflsStage` reference. Service layer split into stage-level (`add_stage`/`update_stage`/`remove_stage`/`reorder_stages`) and trigger-level (`add_trigger`/`update_trigger`/`remove_trigger`/`reorder_triggers`) operations; new structured errors for duplicate `trigger_order`, duplicate (threshold, delay) pairs, and zero-trigger publication attempts; audit log extended with a `STAGE_SETTING_TRIGGER` subject type and a non-foreign-key `stage_setting_trigger_id` column (mirroring `stage_setting_id`'s own established treatment). Draft deletion (ADR-024) now explicitly deletes every owned trigger before its owning stage, before the set itself — no `ON DELETE CASCADE` introduced.

**Backend (UFLS):** `UflsStageDetail` now exposes a `triggers` list instead of flat `threshold_value`/`threshold_unit`/`time_delay_ms` fields; `to_stage_detail` reads every trigger of the referenced stage.

**API:** `stage-setting-sets/{id}/settings` (stages) no longer accepts a threshold or time delay when creating a stage; new nested `stage-setting-sets/{id}/settings/{stage_setting_id}/triggers` endpoints (list/add/update/remove/reorder) for a stage's own operating criteria.

**Frontend:** Stage Setting Set detail page redesigned — each stage renders as its own card with its operating criteria nested and grouped beneath it (never as separate stage rows), with a per-stage "Add Operating Point" action; "Add Stage" now asks only for stage order (and, for UVLS, region scope). UFLS Draft Editor renders each stage's full trigger set and no longer assumes a single threshold/delay pair.

**Tests:** New backend coverage for single- and multi-trigger stages, duplicate trigger_order/pair rejection, most-severe-trigger monotonicity, zero-trigger publication blocking, trigger audit events, Draft deletion cascading through triggers, the `0025` migration's backfill correctness, and UFLS stage/trigger integration. New frontend coverage for grouped stage/trigger display, adding a second trigger under an existing stage without re-entering `stage_order`, Draft-only trigger editing, and Published read-only rendering.

---

## Stage Setting Registry — Draft Deletion and Selection-Time Validation Correction (ADR-024)

**Scope:** Resolves the UAT-identified Stage Setting Set Draft-abandonment governance gap (a Draft with no supported way to remove it) and a companion divergence between `stage-setting-set-architecture.md` §6's own stated rule ("[Draft is] not yet referenceable by any Scheme Version") and the as-built UFLS validation, which enforced only a scheme-type match at selection time, deferring the Published-only requirement to the Publish-time prerequisite alone. See [ADR-024](docs/adr/ADR-024-stage-setting-set-draft-deletion.md) for the full architecture decision (adopted from a Project Owner-ratified prior architecture review, not invented in this task).

**Decision:** A `DRAFT` Stage Setting Set may be physically deleted; `PUBLISHED` and `ENTERED_IN_ERROR` remain permanent and undeletable. No `Abandoned` state, soft-delete flag, or retirement flag was introduced — the identical reasoning [ADR-016](docs/adr/ADR-016-stage-setting-set-as-reusable-versioned-entity.md) already used to reject a `Superseded` state for this entity. A Scheme Version may now select only a `PUBLISHED` Stage Setting Set — enforced at selection time, not deferred.

**Backend (`backend/app/modules/stage_setting_registry/`):**

- `reference_check.py` (new) — `SchemeVersionReferenceChecker` Protocol plus `build_default_reference_checkers`, the read-only interface `StageSettingRegistryService.delete_draft` uses to ask each scheme module (today: UFLS only) "how many of your own Scheme Versions reference this set," without the Stage Setting Registry ever querying `ufls_scheme_version` directly (CLAUDE.md A1/A2) — a lazy-imported composition, mirroring `app.modules.ufls.evaluation.register_provider`'s own established pattern, avoiding a circular import (`UflsService` already imports `StageSettingRegistryService`).
- `service.py` — `delete_draft(stage_setting_set_id, *, change_reason=None, actor_user_id)`: requires `DRAFT`, blocks if referenced (via the checker above), audits the deletion (capturing scheme type/description/setting count in `old_value`, since the row no longer exists afterward), deletes owned `StageSetting` rows explicitly before the parent (no `ON DELETE CASCADE`, per CLAUDE.md §11.7), all in one flush-only transaction.
- `repository.py` — `delete_set`. `exceptions.py` — `StageSettingSetReferencedError`.
- `router.py` — `DELETE /api/v1/stage-setting-sets/{id}`, `stage_setting_registry.manage`, `204` on success, structured `404`/`400` errors (this codebase's own established convention — no `409` is used anywhere else and none is introduced here), never a raw `IntegrityError`.

**Backend (`backend/app/modules/ufls/`):** `_validate_stage_setting_set` now additionally requires the selected set's own `status == "PUBLISHED"` (new `StageSettingSetNotPublishedError`; the "missing record" case now raises a proper `StageSettingSetNotFoundError` instead of overloading the scheme-type-mismatch error). `UflsRepository.count_versions_by_stage_setting_set` / `UflsService.count_versions_referencing_stage_setting_set` — UFLS's own side of the reference-check interface above.

**Frontend (`frontend/src/modules/stage_setting_registry/`):** Delete Draft action on the Stage Setting Set detail page — visible only for `DRAFT`, permission-gated on `stage_setting_registry.manage`, requires explicit confirmation, explains the deletion is permanent because the set was never Published, surfaces the structured conflict error if referenced, navigates back to the list on success. No Abandon action anywhere in the UI. The UFLS Draft Editor's own Stage Setting Set selector already filtered to `scheme_type=UFLS`/`status_filter=PUBLISHED` (unchanged by this task — confirmed, not re-implemented).

**Tests:** New backend coverage for deletion (empty and with child settings, atomic parent+children deletion, audit entry content, permission enforcement, rejection for Published/Entered-in-Error, rejection when referenced by a UFLS Draft or Published version, `ON DELETE RESTRICT` as the final guarantee, rollback consistency) and for selection-time validation (Draft/Entered-in-Error/wrong-scheme-type/missing-record all rejected, Published accepted, historical Published UFLS data remains readable after its referenced set is later marked Entered in Error). New frontend coverage for Delete visibility/permission/confirmation/success/conflict-error rendering.

---

## Refinement — GM Zone Options (Authoritative Engineering Codes)

**Scope:** Project Owner-approved refinement replacing the twelve `gm_zone.code` values (introduced
by the "Substation Registry Enhancement — GM Zone Metadata" entry below) with the authoritative
engineering codes the Project Owner supplied. Display names (`label`) are unchanged; only the
persisted `code` changes.

- Old code → new code (identical `label`, hence unambiguous): `ALOR_SETAR` → `KEDP`,
  `BUTTERWORTH` → `PPNG`, `IPOH` → `PERK`, `SELANGOR` → `SELG`, `KUALA_LUMPUR` → `KLUM`,
  `SEREMBAN` → `NSEM`, `AYER_KEROH` → `MLKA`, `KLUANG` → `JOH2`, `JOHOR_BAHRU` → `JOH1`,
  `KUANTAN` → `PHNG`, `DUNGUN` → `TERG`, `KOTA_BHARU` → `KELN`.
- `app/reference_data/seed.py`'s `GM_ZONES` list updated to the new codes.
- New migration `0023_gm_zone_engineering_codes` remaps every pre-existing `gm_zone` row's `code`
  in place, by matching on the old `(code, label)` pair. `gm_zone_id` (the actual FK target of
  `substation.gm_zone_id`, per CLAUDE.md A5 — reference tables use surrogate SMALLINT keys, never
  a business identifier, as their primary key) is never touched, so every existing
  `substation.gm_zone_id` reference — and every UI/API consumer, which already resolves GM Zone
  by `gm_zone_id`, never by `code` — is unaffected. Fully reversible (`downgrade()` restores the
  original codes by the same matching approach).
- Test fixtures across the backend (every module's test `conftest.py`/`test_*_api.py` that looks
  up a GM Zone via `GmZone.filter_by(code=...)`) and frontend (Substation Registry page test
  mocks) updated from `ALOR_SETAR`/`BUTTERWORTH` to `KEDP`/`PPNG`.
- No frontend UI code change was needed: the GM Zone dropdown, list column, and filter are already
  driven entirely by `gm_zone_id` (the FK value) and `label` (the display value) fetched live from
  `GET /api/v1/reference-data/gm-zones` — `code` itself is never rendered.

---

## Phase 6 — UFLS Scheme Module (First Concrete Consumer of the Shared Defence-Scheme Platform)

**Scope:** Implements UFLS — the first concrete Defence Scheme module, validating the Shared
Defence-Scheme Platform's abstractions in a real engineering workflow. Full detail:
[ufls-architecture.md](docs/architecture/ufls-architecture.md).

**Reconciliation:** as with the Shared Platform task before it, this phase's own literal lifecycle
description does not match ADR-015's ratified four-state model. Implemented ADR-015's model exactly
(`Draft → Published → Superseded | Entered in Error`), per CLAUDE.md's own precedence rules.

**Backend (new module, `backend/app/modules/ufls/`):**

- `models.py` — `UflsScheme` (lineage identity), `UflsSchemeVersion` (composes
  `scheme_platform.SchemeVersionMixin`), `UflsStage` (references a Stage Setting Registry
  `StageSetting`; external-study `target_mw` only, no capture/approved-MW field anywhere), `UflsDirectAssignment`,
  `UflsPocketAssignment`/`UflsPocketAssignmentOpeningPoint` (both attach directly to a stage — no
  `UflsLoadBlock` grouping layer), `UflsAuditLog`.
- `service.py` — `UflsService`: scheme/version/stage/assignment CRUD; Stage Setting Set scheme-type
  validation; Transformer Terminal eligibility (excluded grid-owner/operational-status rules);
  Boundary Pocket construction via `NetworkModelService.evaluate_boundary` (ADR-019), rejecting an
  ineffective selection; direct/pocket substation-overlap prevention; ALSF-capability and
  Sensitive-Customer finding computation (reusing existing `FindingType`s, never duplicated);
  structural publication prerequisites (reusing `PublicationPrerequisiteResult`, no second validator);
  `publish()` orchestrating prerequisite/finding evaluation, `PublicationRecordService`, and
  `scheme_platform`'s own lifecycle transition as one transaction; engineering summaries (descriptive
  only); platform-event emission for scheme/version/stage/assignment changes not already covered by
  the shared platform's own lifecycle events.
- `evaluation.py` — `UflsEvaluationRequestProvider`, the first concrete
  `EvaluationRequestProvider` implementation. `target_mw` resolution is fully implemented; `current_mw`
  resolution is deliberately deferred (`CurrentMwNotResolvableError`) — no Transformer-Terminal/
  Substation-to-Bus load correlation mechanism exists anywhere in this codebase yet. Not wired into any
  production composition root, since none exists yet (a confirmed pre-existing Shared Platform Sprint 6
  gap); `register_provider()` is the documented, ready-to-call registration point for when one is built.
- `router.py`/`dependencies.py` — full REST surface (scheme/version/stage/assignment CRUD, publication
  review, publish, enter-in-error). `bootstrap.py` — `ufls.read`/`.manage`/`.publish`/`.enter_in_error`
  permission catalog, mirroring `stage_setting_registry`'s own Administrator-only publish precedent.
- `alembic/versions/0022_ufls.py` — seven tables, verified upgrade/downgrade against a real PostgreSQL
  database (full chain 0001→0022), not merely SQLite.

**Frontend (new module, `frontend/src/modules/ufls/`):** Scheme List, Scheme Detail (version history,
Draft creation with optional structure-copy), Draft Editor + Stage/Assignment Workspace (Draft-only
edit affordances; Published/Superseded/Entered-in-Error strictly read-only), Publication Review
(blocking prerequisites, findings, engineering summary, permission-gated Publish). Reuses
`components/scheme-platform`'s shared `LifecycleBadge`/`VersionBadge`/`SchemeVersionHeader`/
`SchemeVersionMetadataPanel`.

**Tests:** 13 backend service tests + 6 backend API tests (SQLite and real PostgreSQL, both green) + 9
frontend tests. Full pre-existing backend suite (1157 passed) and frontend suite (265 passed)
otherwise unaffected; one pre-existing, unrelated Windows-`subprocess` test failure in
`sensitive_customer_registry` and one pre-existing, unrelated TypeScript error in
`tests/components/ui/DataTable.test.tsx` — both predate this phase and are untouched by it.

**Deferred:** Continuous Evaluation composition-root wiring (`current_mw` resolution, provider
registration); a searchable Equipment Registry terminal picker in the frontend workspace (today: direct
UUID entry); Cross-Scheme Compliance integration (module does not exist yet).

---

## Shared Defence-Scheme Platform — Reusable Version Lifecycle Infrastructure

**Scope:** Implements the reusable platform every future Defence Scheme module (UFLS, UVLS, EMLS,
and beyond) composes with — version lifecycle, shared metadata, and platform-event integration. Not
the implementation of any defence scheme: no UFLS/UVLS/EMLS engineering logic, table, or route exists
in this module. See
[shared-scheme-platform-implementation.md](docs/architecture/shared-scheme-platform-implementation.md)
for the full architecture summary.

**Critical reconciliation:** this task's own prompt described a lifecycle of `Draft → Submitted for
Review → Approved → Activated → Archived` — CLAUDE.md A3's general-purpose six-state model. That
model is explicitly, narrowly superseded for Defence Scheme Version data specifically by
[ADR-015](docs/adr/ADR-015-defence-scheme-version-lifecycle-simplification.md) (ratified via six
Project Owner engineering-discovery workshops,
[EDR-009](docs/engineering/edr/EDR-009-grid-defence-scheme-lifecycle-realignment.md)). Per CLAUDE.md's
own precedence rules and this task's own explicit instruction to preserve engineering philosophy over
a literal prompt reading, this implementation follows ADR-015's ratified four-state model exactly:
`Draft → Published → Superseded | Entered in Error`. No `Under Review`, `Approved`, or `Archived`
state exists; `Superseded → Published` reactivation (an explicitly open question) is not implemented.

**Backend (new module, `backend/app/modules/scheme_platform/`):**

- `lifecycle.py` — `SchemeVersionLifecycleStatus` (exactly the four ADR-015 states) and
  `validate_transition()`, a pure function enforcing ADR-015's own closed four-transition allow-list.
- `models.py` — `SchemeVersionMixin`, an `__abstract__ = True` SQLAlchemy mixin (never a table of its
  own) carrying the shared columns every concrete scheme version needs: identity, sequential
  `version_number`, lifecycle status, publish/supersede/entered-in-error timestamps and actors,
  engineering remarks, audit timestamps. Deliberately excludes `scheme_id` (FK target differs per
  concrete module) and any self-referential column — each concrete module adds these itself.
- `schemas.py` — `SchemeVersionLifecycleInfo`, `SchemeVersionSummaryBase`/`SchemeVersionDetailBase`,
  `EnterInErrorRequest` — reusable Pydantic base DTOs a concrete module extends.
- `repository.py` — `get_next_version_number`, `get_current_published`, `list_versions`: plain
  functions parameterized by the concrete model class, not a generic base-repository class hierarchy.
- `service.py` — `SchemeVersionLifecycleService`: `create_draft`, `delete_draft`, `publish` (validates
  the transition and atomically supersedes the previous Published version), `supersede`,
  `enter_in_error` (mandatory reason). Calls
  `ContinuousEvaluationService.notify_source_data_changed` (ADR-023) after every transition via a
  reusable `build_lifecycle_change_descriptor` helper — no engineering-specific event payload.
  Explicitly does **not** run structural Publication prerequisites, resolve Publication Treatment, or
  create a `PublicationRecord` (already the established job of
  `PublicationRecordService.evaluate_and_record_publication`, Sprint 4) — a concrete module composes
  both, in one transaction, rather than this sprint duplicating that mechanism.
- `exceptions.py` — `IllegalLifecycleTransitionError`, `DraftDeletionNotPermittedError`,
  `EnteredInErrorReasonRequiredError`, `PublishedVersionAlreadyExistsError`.
- `tests/synthetic_scheme_version.py` — a test-only concrete model built from `SchemeVersionMixin`,
  proving the mixin is genuinely reusable without any real scheme module existing; never a production
  table, never migrated, never exposed through any router.

**Frontend (new components, `frontend/src/components/scheme-platform/`):** `LifecycleBadge`,
`VersionBadge`, `SchemeVersionHeader`, `SchemeVersionMetadataPanel`, `PublicationHistoryPanel` — named
"Publication History," not "Review History"/"Approval History," since ADR-015 defines no separate
review or approval state to have a history of. None reference UFLS, UVLS, or EMLS.

**Explicitly deferred, not built this sprint:** a generic FastAPI router (its exact shape cannot be
validated without a real concrete consumer — the reusable pattern is documented, the code is deferred
to the first concrete scheme module that needs it) and a separate "validator registry" for Publication
prerequisites (the existing `PublicationPrerequisiteResult`/`PublicationRequest` contract, Sprint 4,
already serves this need — not duplicated here).

**Testing:** 52 new backend tests (`test_lifecycle.py`: exactly four states, every legal/illegal
transition pair including `Superseded → Published` reactivation and reverse transitions;
`test_models.py`: the database-level lifecycle-status `CHECK` constraint; `test_repository.py`:
version-number sequencing and per-scheme scoping, current-published lookup; `test_service.py`: draft
creation, deletion rules, publish/supersede/enter-in-error transitions and their mandatory-reason/
illegal-transition guards, platform-event descriptor shape and ordering, and a structural test
confirming no scheme-specific engineering term appears in the shared service's own code) and 17 new
frontend tests across 5 component test files. Full backend suite and full frontend suite both pass
with no regressions (backend: pre-existing `sensitive_customer_registry` subprocess flake unrelated to
this work; frontend: one pre-existing, unrelated TypeScript typecheck issue in
`tests/components/ui/DataTable.test.tsx`, confirmed untouched by this sprint).

**Documentation:** new
[shared-scheme-platform-implementation.md](docs/architecture/shared-scheme-platform-implementation.md)
(why the platform exists, module boundaries, inheritance strategy, lifecycle/version philosophy, the
ADR-015 reconciliation, and what was explicitly deferred). Status-note pointers added to
`scheme-engineering-principles.md`'s own pack index and `shared-defence-scheme-domain-model.md` — no
rewrite of either. No new ADR: ADR-015 already governs the lifecycle question this sprint implements.

---

## Shared Platform Sprint 6 — Continuous Evaluation Engine: Background Refresh, Evaluation Projection, and Platform Event Consumption Foundation

**Scope:** Sixth implementation sprint of the finalized Shared Platform architecture. Implements
ADR-023's asynchronous evaluation-refresh foundation and the disposable Evaluation Projection
lifecycle continuous-evaluation-architecture.md §3.1 defines, on top of Sprint 5's synchronous core.
Background refresh foundation, disposable Evaluation Projection, and platform-event consumer
contracts implemented; source-module event emission and non-MW detectors remain pending.

**Backend (new files, `app/modules/continuous_evaluation/`):**

- `models.py` — `EvaluationProjection`: disposable, non-authoritative, one row per `(scheme_type,
  scheme_version_id)` target (unique index), the four documented statuses (`CURRENT`/`STALE`/
  `RECALCULATING`/`FAILED`), a `generation` invalidation counter, and a frozen JSON snapshot of the
  most recent *successful* `EvaluationResult` (preserved across a later `FAILED`/`STALE`
  transition). No FK into any scheme-version table (none exists); never referenced by
  `PublicationRecord`.
- `repository.py` — `EvaluationProjectionRepository`: pure persistence (`get_by_target` with an
  optional `SELECT ... FOR UPDATE`, `create`, `save`) — no business rules, no transition logic.
- `provider.py` — `EvaluationRequestProvider` (typed seam a future scheme module implements to
  supply an `EvaluationRequest` from its own repository, hidden from this module entirely) and
  `EvaluationRequestProviderRegistry` (explicit, static, per-scheme-type registration, empty by
  default — no real scheme module exists yet).
- `resolver.py` — `AffectedSchemeResolver` (typed seam mapping one platform event to the
  `EvaluationTarget`s it may affect) and `NullAffectedSchemeResolver` (the production default: zero
  targets, since no real source-to-scheme mapping exists yet).
- `worker.py` — `refresh_evaluation_projection`, the plain, RQ-serializable job function
  (`app.core.execution`-submitted) owning Continuous Evaluation's own exclusive `continuous_evaluation`
  RQ queue (ADR-023). Opens its own database session, delegates every state transition and the one
  `evaluate()` call to `ContinuousEvaluationService.run_refresh_worker_cycle` — no detector logic of
  its own.
- `schemas.py` (extended) — `ProjectionStatus`, `EvaluationTarget`, `ChangeDescriptor` (ADR-023's own
  `change_descriptor`, realized as a stable, dot-namespaced-validated envelope — not one Python class
  per event type, and no invented causation-id/payload-schema-version/arbitrary-payload fields beyond
  what ADR-023 itself documents), `RefreshRequestResult`, `ProjectionDetail`.
- `service.py` (extended) — three new public entry points, all reusing Sprint 5's `evaluate()`
  exactly once per refresh, never duplicating detector logic: `notify_source_data_changed(event)`
  (ADR-023's own named entry point), `request_refresh(target, trigger, correlation_id)` (marks/creates
  the projection `STALE`, bumps `generation`, and arranges an idempotent refresh to be enqueued — never
  evaluates inline), and `run_refresh_worker_cycle(...)` (the worker's own claim/evaluate/complete-or-
  reconcile algorithm). At most one job is ever outstanding per target — a request while one is already
  queued or running just bumps `generation`; the in-flight worker's own end-of-run generation
  comparison detects a newer invalidation and re-enqueues exactly once itself, guaranteeing no false
  `CURRENT` state. The actual job submission is deferred to `self.db`'s own SQLAlchemy `after_commit`
  event rather than called synchronously — see the dedicated finding below.
- `tests/synthetic_evaluation.py` (extended) — `FakeEvaluationRequestProvider`,
  `RaisingEvaluationRequestProvider`, `FakeAffectedSchemeResolver`, `RecordingExecutionEngine` (an
  `ExecutionEngine` test double that records submissions without running them, isolating
  enqueue/coalescing decisions from real execution), `synthetic_change_descriptor`.

**Backend (extended shared infrastructure, minimal and additive):** `app/core/queue.py`
(`get_queue`/`enqueue` gained an optional `queue_name`, default unchanged — every existing PSS/E
Integration call site is unaffected) and `app/core/execution.py` (`ExecutionEngine.submit` gained
optional `queue_name`/`job_id`/`retry`, `DirectExecutionEngine` accepts and discards them,
`QueueExecutionEngine` forwards them to RQ). This was a necessary, narrow adjustment: ADR-023
requires "one shared queue... owned exclusively by the Continuous Evaluation Engine module," but the
pre-existing infrastructure had exactly one hardcoded queue name belonging to PSS/E Integration —
resolved by parameterizing the queue name rather than reusing PSS/E's own queue or building new
infrastructure. `app/worker.py` now listens on both named queues from the same single worker process
— no new worker or infrastructure component.

**Persistence and migration:** `0021_evaluation_projection` (down-revision `0020_publication_record`)
creates `continuous_evaluation_projection` only. The revision id is `0021_evaluation_projection`, not
the fuller `0021_continuous_evaluation_projection` — that longer id was tried first and rejected by a
real PostgreSQL database's own `alembic_version.version_num varchar(32)` column, an error this
sprint's own verification pass caught and fixed by shortening it. Verified on a real PostgreSQL
database: full chain `0001`→`0021`, downgrade one revision (table correctly dropped), re-upgrade
(table correctly restored), all check constraints and both unique/non-unique indexes confirmed via
direct catalog inspection.

**No API, no new permissions:** service-only, matching Sprint 5's own precedent and this sprint's own
explicit preference — no generic projection routes are documented as required this sprint.

**Critical finding from real-PostgreSQL verification: a genuine self-deadlock, found and fixed.**
`execution_mode="direct"` — this platform's own documented default, and its default deployment
configuration regardless of database choice (`docker-compose.yml` always points `DATABASE_URL` at a
real PostgreSQL server, independent of `EXECUTION_MODE`) — runs a submitted job function immediately,
in-process, including this module's own worker cycle, which opens a *separate* database connection
(`worker.py`'s own `SessionLocal()`, deliberately mimicking a real separate worker process). The first
implementation of `request_refresh` enqueued (and, transitively, ran the worker inline) synchronously,
before its own row mutation was committed — on a real multi-connection database, the worker's own
separate connection blocked waiting to lock a row this connection's own uncommitted transaction still
held, a genuine deadlock. This was invisible on SQLite's shared single-connection `StaticPool` test
setup and was caught only by running the full `continuous_evaluation` suite against a real PostgreSQL
database, where it hung indefinitely partway through. **Fix:** `request_refresh`/
`notify_source_data_changed` now defer the actual job submission to `self.db`'s own SQLAlchemy
`after_commit` event, firing exactly once and only if that commit actually succeeds — the row lock is
released before any recursive worker execution can occur, and, as a beneficial side effect, a caller
transaction that rolls back now never enqueues a job at all (no dual-write/outbox gap to disclose,
where an earlier draft of this sprint's own work had flagged one as an accepted limitation). `job_id`
remains available synchronously from `request_refresh`'s own return value regardless, since it is a
deterministic identity, not one RQ assigns. Re-verified clean (all 78 tests, no hang) against real
PostgreSQL after the fix.

**Testing:** 46 new tests — 17 projection-lifecycle tests (`test_projection_lifecycle.py`: creation,
coalescing while a job is already outstanding, transitions back to `STALE` from `CURRENT`/`FAILED`,
successful/failed worker cycles, failure preserving the last successful result, the critical
generation-mismatch-during-recalculation concurrency case, read-DTO reconstruction, and an explicit
regression test for the deadlock fix using the real, uninjected `DirectExecutionEngine`), 11
platform-event-consumer tests (`test_platform_event_consumer.py`: `ChangeDescriptor` envelope
validation and immutability, resolver invocation, deterministic deduplication, zero/one/multiple
targets, correlation propagation, duplicate event delivery safety, and confirmation that no detector
calculation ever runs inside the event-consumer path), 7 worker/queue integration tests
(`test_worker_queue_integration.py`: real queue routing via fakeredis, deterministic job identity,
missing-provider and missing-projection safe handling, retry-safe duplicate execution, and the outer
worker wrapper's own rollback/re-raise behaviour on a genuinely unexpected exception), and 6 tests
extending the existing `tests/test_execution.py` for the new `queue_name` parameter (default-preserving
behaviour confirmed for every pre-existing call shape). All Sprint 5 tests continue to pass unchanged.
Full backend suite passes on SQLite with no regressions beyond the same pre-existing,
independently-reproduced `sensitive_customer_registry` standalone-bootstrap subprocess flake already
documented in Sprints 1-5. The full `continuous_evaluation` suite was additionally run against a real
PostgreSQL database via this repository's own sanctioned `GRIDDEFENCE_TEST_DATABASE_URL`/
`GRIDDEFENCE_ALLOW_DESTRUCTIVE_TEST_DATABASE` mechanism — twice: once which surfaced the deadlock above
(killed after hanging), and once clean after the fix.

**Known, disclosed limitation:** a projection stuck `RECALCULATING` because its own worker process
crashed without raising has no automatic timeout/recovery in this sprint — no such mechanism is
documented, and inventing one was judged premature without evidence of need (CLAUDE.md §21).

**Frontend:** Not part of this sprint's scope — deferred, per the task's own instructions.

**Documentation:** [ADR-023](docs/adr/ADR-023-platform-event-architecture.md),
`docs/architecture/platform-event-architecture.md`, and
`docs/architecture/continuous-evaluation-architecture.md` all updated with an implementation-status
note using the wording: "Background refresh foundation, disposable Evaluation Projection, and
platform-event consumer contracts implemented; source-module event emission and non-MW detectors
remain pending." ADR-023 is explicitly not marked fully complete — no source module yet calls
`notify_source_data_changed`.

---

## Shared Platform Sprint 5 — Continuous Evaluation Engine: Synchronous Core and MW Tolerance Detector

**Scope:** Fifth implementation sprint of the finalized Shared Platform architecture. Implements
[ADR-022](docs/adr/ADR-022-continuous-evaluation-detector-framework.md)'s detector framework and the
synchronous Continuous Evaluation Engine core in a new `app/modules/continuous_evaluation/` module.
Synchronous Continuous Evaluation core, explicit detector framework, and MW tolerance detector
implemented; background event-driven refresh (ADR-023) and remaining detectors pending. No persisted
evaluation projection, no API/router, and no real scheme (UFLS/UVLS/EMLS) integration were
implemented this sprint.

**Backend (new files):**

- `schemas.py` — the evaluation value contracts (CLAUDE.md A6): `EvaluationRequest` (scheme type,
  scheme-version id, opaque snapshot references, and a named, typed `mw_inputs` sub-contract — no
  ORM model, no generic `SchemeVersion` table, no unbounded dictionary service locator),
  `MwAssignmentGroupInput`/`MwEvaluationInputs` (the MW detector's own typed input), and
  `EvaluationResult`/`DetectorExecutionSummary` (the stable result contract; computed MW metrics are
  conveyed as structured evidence on each raised MW finding rather than a separate top-level field,
  since populating one for in-tolerance groups would require either MW-specific logic inside the
  engine or an invented "everything is fine" finding — both explicitly out of scope).
- `detectors/base.py` — `EngineeringFindingDetector`, ADR-022's own interface exactly: stable
  `detector_id`, declared `applicable_scheme_types`, synchronous `detect(context) -> list[Finding]`.
- `detectors/registry.py` — `DetectorRegistry`: explicit `register()`, duplicate-id rejection,
  registration-order-preserving `for_scheme_type()` filtering (ADR-022: execution order carries no
  meaning beyond registration order). No dynamic discovery of any kind.
- `detectors/mw_tolerance.py` — `MwToleranceDetector`, the first and, this sprint, only registered
  detector. Implements the exact documented formula
  (`deviation_percentage = (current_mw - reference_mw) / reference_mw * 100`), the exact documented
  tolerance boundary (±tolerance inclusive = within tolerance; strictly beyond = under-/over-
  allocation finding), reads the approved tolerance exclusively through
  `EngineeringParameterService.get_parameter`, and validates its unit (`percent`) and numeric range
  independently of that service's own write-time validation. Assigns exactly one severity
  (`Severity.WARNING`) to every out-of-tolerance finding — no invented percentage-based escalation
  bands, since ADR-018 left this exact decision to this sprint and neither document defines a second
  threshold.
- `detectors/registration.py` — `build_default_registry()`, the one application-composition point
  that registers `MwToleranceDetector`; detector registration remains composition-only, never a
  runtime API.
- `service.py` — `ContinuousEvaluationService.evaluate(request)`: resolves applicable detectors in
  registration order, runs each, validates every returned `Finding.source` matches its own
  detector's `detector_id`, and assembles the result. Contains no MW-specific calculation logic. A
  detector's own exception fails the whole evaluation (wrapped in `DetectorExecutionFailedError`)
  rather than silently omitting that detector or returning a result that looks complete — the
  architecture defines no partial-evaluation mode. FastAPI-independent (plain constructor args only).
- `exceptions.py` — structured domain errors for every expected failure mode (duplicate detector id,
  no applicable detectors, detector source mismatch, detector execution failure, missing/invalid-
  unit/invalid-value engineering parameter, invalid/zero reference MW, invalid current MW). No
  generic 500s; a software/configuration failure is never converted into a `Finding`.
- `tests/synthetic_evaluation.py` — reusable synthetic `EvaluationRequest`/`MwAssignmentGroupInput`
  factories, mirroring `findings_publication_governance/tests/synthetic_scheme.py`'s own established
  shape; no production synthetic records or routes.

**No persistence, no migration:** No migration was created because the synchronous evaluation result
remains transient in Sprint 5 under the authoritative architecture. continuous-evaluation-
architecture.md §3 frames the disposable cached projection as an independent, performance-motivated
mechanism with no documented mandate for this sprint's on-demand synchronous path, and no consumer or
measured performance need for one exists yet (CLAUDE.md §21).

**No API, no new permissions:** continuous-evaluation-architecture.md documents no HTTP contract of
its own for this engine — it is a shared, in-process capability future scheme modules call from their
own routers. `evaluate()` is therefore service-only this sprint; no router, no new IAM permissions.

**Testing:** 38 new tests — 6 detector-framework tests (`test_detector_registry.py`: ABC enforcement,
duplicate-id rejection, deterministic registration-order execution, scheme-type filtering, additive
registration), 20 MW tolerance detector tests (`test_mw_tolerance_detector.py`: within/at/beyond
tolerance in both directions, multi-group independence, Decimal-precision, zero/negative reference and
current MW, missing/wrong-unit/non-numeric/out-of-range engineering parameter, parameter changes
affecting only later evaluations), and 12 evaluation-engine tests
(`test_continuous_evaluation_service.py`: successful evaluation, deterministic multi-detector
ordering/aggregation, context propagation, no-applicable-detectors and detector-failure semantics,
source-mismatch validation, no session commit, FastAPI-independent callability, request/result
immutability). Full backend suite passes on SQLite with no regressions beyond the same pre-existing,
independently-reproduced `sensitive_customer_registry` standalone-bootstrap subprocess flake already
documented in Sprints 1-4.

**Frontend:** Not part of this sprint's scope — deferred, per the task's own instructions.

**Documentation:** [ADR-022](docs/adr/ADR-022-continuous-evaluation-detector-framework.md) and
`docs/architecture/continuous-evaluation-architecture.md` both updated with an implementation-status
note: "Synchronous Continuous Evaluation core, explicit detector framework, and MW tolerance detector
implemented; background event-driven refresh and remaining detectors pending." ADR-023's own
background/event-driven path is explicitly noted as still unimplemented.

---

## Shared Platform Sprint 4 — Findings and Publication Governance: Publication Record and Publication Orchestration Foundation

**Scope:** Fourth implementation sprint of the finalized Shared Platform architecture. Extends the
existing `app/modules/findings_publication_governance/` module (Sprint 3) with immutable
`PublicationRecord` evidence and the shared publication-orchestration foundation — never a second
publication-governance module. **Only the Publication Record foundation is complete** — real scheme
publication integration (a real UFLS/UVLS/EMLS Scheme Version, its own publish route, its own
structural-prerequisite checks) and the Continuous Evaluation Engine remain future work. No generic
`SchemeVersion` table was created; no real scheme entity or publish route was implemented; no
detector or evaluation cache was implemented.

**Backend (new files):**

- `publication.py` — the publication-orchestration value contracts: `PublicationPrerequisiteResult`
  (a generic, scheme-agnostic structural-prerequisite result — ADR-015's own Publication
  Prerequisites, without this module ever knowing a scheme module's own table structure),
  `AcknowledgementInput` (keyed by `finding_index`, the deterministic *publication-local* identity
  this sprint introduces since `Finding` itself has none), `PublicationRequest` (everything the
  shared service needs from a future scheme module's own Publish action — never an ORM model), and
  `PublicationResult` (a thin write-result DTO).
- `tests/synthetic_scheme.py` — a durable, reusable synthetic scheme-version test fixture
  demonstrating the publication service is entirely scheme-module-agnostic; no
  `synthetic_scheme_version` production table, no route reachable through the normal application
  router.

**Backend (extended files):**

- `models.py` — `PublicationRecord` (immutable; `publication_event_id` UNIQUE as the caller-supplied
  idempotency key) plus three frozen-evidence child tables: `PublicationRecordFinding` (every
  `Finding` field copied at Publish time, plus the resolved treatment *and* the matched policy's own
  severity/finding_type/scheme_type — so the record stays interpretable even after that policy is
  later changed or removed), `PublicationRecordPrerequisite`, `PublicationRecordAcknowledgement`
  (composite foreign key into `PublicationRecordFinding` — genuine same-aggregate referential
  integrity). `scheme_version_id`/`topology_version_id`/`load_snapshot_id` are deliberately not
  foreign keys (CLAUDE.md A2/F2 — Shared Platform never depends on a scheme module's own tables,
  which do not exist).
- `repository.py` — `PublicationRecordRepository`: insert-and-read only, no update or delete method
  anywhere (immutability enforced structurally, by absence, not a runtime guard).
- `service.py` — `PublicationRecordService.evaluate_and_record_publication(request)`, the shared
  entry point, following the exact sequential algorithm this sprint's own instructions specify:
  validate structurally → reject a duplicate `publication_event_id` → confirm every prerequisite
  passed → resolve Publication Treatment Policy per finding (Sprint 3's own policy service) → reject
  if any finding resolves to `BLOCK` → verify acknowledgement evidence matches exactly (no missing,
  no unnecessary, no duplicate, no unknown target) → freeze evidence into new ORM rows → insert
  (flush only, **never commit** — a future scheme service calls this within its own transaction,
  alongside its own Scheme Version transition, and commits once, itself). Also adds
  `resolve_publication_treatment_with_policy` to `PublicationTreatmentPolicyService` — a
  behaviour-preserving refactor; the existing `resolve_publication_treatment` now delegates to it
  and returns the identical bare treatment string every Sprint 3 caller already expects.
- `router.py` — new `publication_records_router` (`/publication-records`): `GET` list (summary
  shape, no publisher identity, no evidence) and `GET /{id}` (full frozen evidence). No write route
  of any kind — `evaluate_and_record_publication` is reachable only in-process, never through HTTP,
  per this sprint's own explicit instruction not to expose the internal publication command to
  ordinary API callers.

**Concurrency / idempotency:** the chosen, documented approach is a caller-supplied
`publication_event_id` (UUID) — a per-attempt idempotency key, enforced by a database-level `UNIQUE`
constraint. Not a scheme-lifecycle sequence number: this module has no visibility into any scheme
module's own version-history sequencing, so that alternative was not implementable without inventing
scheme lifecycle behaviour this sprint has no mandate to invent.

**Permissions:** list uses the existing broad `findings_publication_governance.read`; full-evidence
detail reuses the existing, more restrictive `findings_publication_governance.view_audit`
(Administrator-only) — the same permission Sprint 3 already gates policy audit history behind,
reused rather than duplicated, per this sprint's own "most restrictive documented precedent for
immutable audit evidence" instruction.

**Database:** `0020_publication_record` (down-revision `0019_publication_treatment`). Creates
`publication_record`, `publication_record_finding`, `publication_record_prerequisite`,
`publication_record_acknowledgement`. Verified linear on both SQLite (full backend suite) and a real
PostgreSQL database — full chain upgrade from `0001` through `0020`, downgrade, and re-upgrade all
confirmed clean, including the composite foreign key, the `publication_event_id` uniqueness
constraint, and every check constraint.

**Testing:** 27 orchestration-service tests (`test_publication_service.py` — every successful/
blocked/acknowledgement scenario, policy-resolution integration at every precedence level, frozen-
evidence immutability against later policy changes/removals and against caller-side input mutation,
duplicate-event prevention, no-hidden-commit/rollback behaviour, deterministic ordering, synthetic-
fixture reuse), 11 repository/database tests (`test_publication_record_repository.py` — 2 of which
are PostgreSQL-only, skipped under SQLite, since SQLite does not enforce `FOREIGN KEY` constraints by
default and this project's own shared `conftest.py` does not turn that pragma on), and 16 API
contract tests (`test_publication_records_api.py` — authentication, permission tiers, filters,
pagination, complete evidence in detail, not-found/malformed-identifier handling, and confirmation
that no write route of any kind is exposed) — 54 new tests total. All Sprint 3 tests continue to
pass unchanged, confirming the `resolve_publication_treatment` refactor preserved exact behaviour.
Full backend suite passes on SQLite with no regressions beyond the same pre-existing,
independently-reproduced `sensitive_customer_registry` standalone-bootstrap subprocess flake already
documented in Sprints 1-3.

**Frontend:** Not part of this sprint's scope — deferred, per the task's own instructions.

**Documentation:** `docs/architecture/findings-and-publication-governance-architecture.md` and
[ADR-018](docs/adr/ADR-018-findings-severity-and-publication-governance-separation.md) both updated
to "Policy Layer and Publication Record foundation implemented; real scheme publication integration
and Continuous Evaluation remain pending" — no architecture rewritten, no adopted decision reopened.

---

## Shared Platform Sprint 3 — Findings and Publication Governance: Policy Layer

**Scope:** Third implementation sprint of the finalized Shared Platform architecture. Implements
[ADR-018](docs/adr/ADR-018-findings-severity-and-publication-governance-separation.md)'s Finding
value contract and Publication Treatment Policy layer only. `PublicationRecord` persistence,
`recordPublication()`, scheme-version publish actions, structural publication-prerequisite
checking, the Continuous Evaluation Engine, detector execution, evaluation caching, regional
analytics, the Engineering Review Panel, platform-event producers/consumers, and every UFLS/UVLS/
EMLS scheme entity all remain explicitly out of scope, per later sprints. **Only the Policy Layer
is complete after this sprint** — Publication Record and publish orchestration remain future work.

**Backend:** New `app/modules/findings_publication_governance/` module.

- `findings.py` — the shared `Finding` value contract: a frozen, non-ORM Pydantic model (no
  `finding` table — findings are computed live, never persisted at Draft time, per module document
  §8), plus the canonical `Severity` (`INFORMATION`/`ADVISORY`/`WARNING`/`CRITICAL`), `FindingType`
  (the exact eight finding-source categories the architecture already names — MW tolerance
  deviation, ALSF capability absence, Sensitive Customer association, topology/registry change,
  Boundary Pocket structural, Boundary Pocket composition, cross-scheme overlap, critical-
  infrastructure protection — no detailed subtypes invented), and `SchemeType` (UFLS/UVLS/EMLS)
  enums.
- `models.py`/`0019_publication_treatment` — `PublicationTreatmentPolicy` (severity mandatory;
  `finding_type`/`scheme_type` independently optional narrowing dimensions; `treatment` one of
  `BLOCK`/`ALLOW_WITH_ACKNOWLEDGEMENT`/`ALLOW_WITHOUT_ACKNOWLEDGEMENT`) and its own append-only
  `publication_treatment_policy_audit_log`. Four partial unique indexes (not one composite `UNIQUE`
  constraint) correctly enforce "at most one policy per precedence level" across two independently-
  nullable columns — generalizing the same `NULL`-is-never-equal-to-`NULL` lesson Sprint 2 already
  documented for one nullable column to two.
- `service.py` — `resolve_publication_treatment(finding, scheme_type=None)`, the one shared
  resolution path (ADR-018's own central rule: never bespoke per-detector gating logic), following
  a four-level precedence order derived from the architecture's own stated axis primacy (finding-
  type specificity ranks above scheme-type specificity): scheme+finding-type override → global
  finding-type override → scheme-specific severity override → global severity baseline. Raises a
  domain exception rather than silently falling back if no policy resolves (only possible if
  bootstrap has never run). `resolve_publication_treatments` batches the same resolution for a
  collection of findings.
- Baseline protection: the four global severity baselines can have their `treatment` changed but
  never be removed (`CannotRemoveBaselinePolicyError`), guaranteeing every supported severity always
  resolves. `severity`/`finding_type`/`scheme_type` are immutable once a policy is created — only
  `treatment` may be updated.

Permissions: `findings_publication_governance.read` (all roles), `.manage_policy` and
`.view_audit` (Administrator-only — two separate permissions, per this sprint's own explicit model,
mirroring ADR-018 §4.1's elevated-tier precedent; ordinary scheme editors never change publication
governance). Removal is a dedicated `POST .../remove` action (mandatory reason), not a bare
`DELETE`, mirroring Sprint 2's own precedent for reasoned lifecycle actions.

**Database:** `0019_publication_treatment` (down-revision `0018_stage_setting_registry`). Creates
`publication_treatment_policy` and `publication_treatment_policy_audit_log`, referencing
`user.user_id` only (nullably, mirroring Sprint 1's own bootstrap-actor precedent). Verified linear
on both SQLite (full backend suite) and a real PostgreSQL database — full chain upgrade from `0001`
through `0019`, downgrade, and re-upgrade all confirmed clean, including all four partial unique
indexes and every check constraint.

**Testing:** 23 value-contract tests (`test_findings.py`, including parametrized coverage of every
canonical severity and finding type — construction, enum validation, immutability, serialization,
no ORM coupling), 28 service tests (`test_service.py` — precedence at every level, fallback after
override removal, baseline protection, duplicate prevention, mandatory reason, no-op mutation
handling, audit retention after removal, deterministic batch resolution), 7 bootstrap tests
(`test_bootstrap.py`), and 17 API contract tests (`test_findings_publication_governance_api.py` —
authentication, read/manage_policy/view_audit permission enforcement, validation, conflict,
baseline protection, deterministic ordering, complete create/update/remove lifecycle) — 75 new
tests total, all passing on both SQLite and PostgreSQL. Full backend suite passes on SQLite with no
regressions beyond the same pre-existing, independently-reproduced `sensitive_customer_registry`
standalone-bootstrap subprocess flake already documented in Sprints 1 and 2.

**Frontend:** Not part of this sprint's scope — deferred, per the task's own instructions.

**Documentation:** `docs/architecture/findings-and-publication-governance-architecture.md` and
[ADR-018](docs/adr/ADR-018-findings-severity-and-publication-governance-separation.md) both gain a
short, additive "Policy Layer implemented; Publication Record and publish orchestration pending"
status note — no architecture rewritten, no adopted decision reopened.

---

## Shared Platform Sprint 2 — Stage Setting Registry

**Scope:** Second implementation sprint of the finalized Shared Platform architecture. Implements
[ADR-020](docs/adr/ADR-020-stage-setting-registry-as-standalone-shared-module.md) in full: a new,
standalone shared module owning `StageSettingSet`/`StageSetting` — the reusable, independently
versioned stage structure UFLS and UVLS will reference by id, never duplicate. UFLS, UVLS, EMLS
entities, the Continuous Evaluation Engine, Detector Framework, Publication Governance, Regional
Analytics, and the Engineering Review Panel all remain out of scope, per later sprints. No Stage
Setting Sets are seeded — the architecture defines no approved initial engineering records, and no
default UFLS/UVLS thresholds are invented.

**Backend:** New `app/modules/stage_setting_registry/` module — `StageSettingSet` (`scheme_type`
`UFLS`/`UVLS`, `description`, `status`, audit metadata) and `StageSetting` (`stage_order`,
`threshold_value` as an exact `Numeric(9,4)` — never a binary float, `threshold_unit` derived from
the parent's own `scheme_type`, `time_delay_ms`, an optional UVLS-only `region_scope_id`), plus
their own append-only `stage_setting_registry_audit_log`. Closed lifecycle transition table —
`DRAFT -> PUBLISHED -> ENTERED_IN_ERROR` only; `ENTERED_IN_ERROR` is reachable only from
`PUBLISHED` (never directly from `DRAFT`, mirroring ADR-015's own Scheme Version transition table
and ADR-016's "should never have been published" framing) — no Draft-deletion operation is
implemented (neither ADR-016 nor this sprint's own instructions grant one, unlike Scheme Version's
own explicit exception). `StageSettingRegistryService.publish()` atomically validates the complete
setting set (non-empty; no duplicate `stage_order` within any region-scope group; threshold values
strictly decreasing as `stage_order` increases, independently within each region-scope group,
including the grid-wide null-scope group treated as its own scope) before transitioning — no
row-locking is needed, since the architecture explicitly permits many Stage Setting Sets of the
same scheme type to be simultaneously Published (no "only one current" invariant, unlike Scheme
Version). Two partial unique indexes (`region_scope_id IS NULL` / `IS NOT NULL`) implement
per-scope `stage_order` uniqueness correctly — a single composite `UNIQUE` constraint cannot, since
standard SQL treats every `NULL` as distinct from every other `NULL`. `reorder_settings()` reorders
exactly one region-scope group at a time via a two-phase update (temporary negative sentinel values,
then final positions) — found and fixed during PostgreSQL verification: an initial large positive
offset (100,000) overflowed `stage_order`'s `SMALLINT` column on PostgreSQL (invisible under
SQLite's flexible typing), corrected to small negative sentinels instead.

Permissions: `stage_setting_registry.read` (Administrator/Engineer/Viewer), `.manage`
(Administrator/Engineer — create/edit Drafts), `.publish` and `.enter_in_error` (Administrator
only, mirroring findings-and-publication-governance-architecture.md §6's own "Only Administrators
may publish" precedent — a user who may edit a Draft is not assumed to also be trusted to publish
or correct it). Audit log endpoint follows this codebase's *default* precedent (open to any
authenticated user), not Engineering Parameter Configuration's own documented exception — this
module's architecture does not call for a stricter gate.

**Database:** `0018_stage_setting_registry` (down-revision `0017_engineering_parameters`; revision
id shortened from the fuller module name for the same `VARCHAR(32)` reason as Sprint 1). Creates
`stage_setting_set`, `stage_setting`, `stage_setting_registry_audit_log`, referencing `user.user_id`
and `region.region_id` only. Verified linear on both SQLite (full backend suite) and a real
PostgreSQL database — full chain upgrade from `0001` through `0018`, downgrade, and re-upgrade all
confirmed clean, including both partial unique indexes and every check constraint.

**Testing:** 52 module-level unit tests (45 service-layer + 7 bootstrap — Draft creation/editing,
UFLS/UVLS scheme-type-specific validation, per-scope threshold monotonicity, publication atomicity,
the closed lifecycle transition table, audit history, decimal precision) plus 17 API contract tests
(authentication, read/manage/publish/enter-in-error permission enforcement, request validation,
list filters, deterministic ordering, complete UFLS and UVLS lifecycles) — 69 new tests total, all
passing on both SQLite and PostgreSQL. Full backend suite (876 tests) passes on SQLite with no
regressions.

**Frontend:** Not part of this sprint's scope — deferred, per the task's own instructions.

**Documentation:** `docs/architecture/stage-setting-set-architecture.md` and
[ADR-020](docs/adr/ADR-020-stage-setting-registry-as-standalone-shared-module.md) both gain a
short, additive "implemented" status note — no architecture rewritten. Two deliberate scope gaps
recorded explicitly in that status note (threshold-range validation against Engineering Parameter
Configuration; the "which Scheme Versions reference this set" reverse lookup) rather than silently
invented or silently omitted.

---

## Shared Platform Sprint 1 — Engineering Parameter Configuration

**Scope:** First implementation sprint of the finalized Shared Platform architecture
([ADR-020](docs/adr/ADR-020-stage-setting-registry-as-standalone-shared-module.md) through
[ADR-023](docs/adr/ADR-023-platform-event-architecture.md)). Implements
[ADR-021](docs/adr/ADR-021-engineering-parameter-configuration-ownership.md) in full: a new,
standalone Core Platform module owning the current, audited value of every named platform-wide
engineering parameter. Only the one architecture-approved parameter — `mw_tolerance_percentage`,
the ±10% global MW tolerance already named by
[continuous-evaluation-architecture.md](docs/architecture/continuous-evaluation-architecture.md)
§7 — is seeded; no additional parameter is invented. Stage Setting Registry, the Continuous
Evaluation Engine/Detector Framework, Publication Governance, Regional Analytics, the Engineering
Review Panel, and every Defence Scheme module (UFLS/UVLS/EMLS) remain out of scope, per later
sprints.

**Backend:** New `app/modules/engineering_parameters/` module — `EngineeringParameter`
(`parameter_key` string PK, `value`/`unit`/`description`, `updated_at`/`updated_by_user_id`) and
its own append-only `EngineeringParameterAuditLog`, current-value-plus-audit-log only (no
Draft/Published lifecycle — ADR-021 §8). `EngineeringParameterService.set_parameter_value()` is
the single, audited upsert write path (creates on first use, updates thereafter; mandatory
non-empty `change_reason`; per-`parameter_key` value validation via a small, explicit
`_NUMERIC_PARAMETER_BOUNDS` registry, extensible without a schema change). `GET
/api/v1/engineering-parameters`, `GET /api/v1/engineering-parameters/{key}`, `PUT
/api/v1/engineering-parameters/{key}`, `GET /api/v1/engineering-parameters/{key}/audit-log`. Read
requires only authentication; `PUT` and the audit-log endpoint require the new, Administrator-only
`engineering_parameters.manage` permission (Engineer/Viewer hold `engineering_parameters.read`
only) — the audit-log gating is a deliberate deviation from this codebase's usual "audit log open
to any authenticated user" precedent, per ADR-021 §4.1. `bootstrap.py` registers both permissions
and idempotently seeds `mw_tolerance_percentage` through the same audited service-layer write path
any future Administrator change uses (`actor_user_id=None`, mirroring every other module's own
bootstrap convention). Also exposes `get_parameter_value(parameter_key)`, a read-only in-process
interface for the future MW tolerance detector (ADR-022) to consume without an HTTP round trip.

**Database:** `0017_engineering_parameters` (Alembic revision id shortened from
`0017_engineering_parameter_configuration` — `alembic_version.version_num` is `VARCHAR(32)`).
Creates `engineering_parameter` and `engineering_parameter_audit_log`, both referencing
`user.user_id` only (`ON DELETE RESTRICT`); both actor columns are nullable, exclusively for the
bootstrap-seed exception. Verified linear on both SQLite (full backend suite) and a real
PostgreSQL database — full chain upgrade from `0001` through `0017`, downgrade, and re-upgrade all
confirmed clean.

**Testing:** 22 module-level unit tests (bootstrap idempotency/permission grants/initial seeding;
service-layer upsert/audit/validation/not-found behaviour) plus 13 API contract tests
(authentication, permission enforcement including the audit-log deviation, full set/get/audit-log
flow, validation error shapes) — all passing on both SQLite and PostgreSQL. Full backend suite (843
tests) passes on SQLite with no regressions.

**Frontend:** Not part of this sprint's scope — deferred, per the task's own instructions.

**Documentation:** `docs/architecture/engineering-parameter-configuration-architecture.md` and
[ADR-021](docs/adr/ADR-021-engineering-parameter-configuration-ownership.md) both gain a short,
additive "implemented" status note — no architecture rewritten.

---

## IAM Completion Sprint — User Status Lifecycle and Last-Active-Administrator Safeguard

**Scope:** Two bounded IAM gaps identified by the Bootstrap Administrator Lifecycle and Existing
IAM User Management Capability investigations (following the Development Database Recovery
incident): (1) `User.status` had no service/API path to transition a user between `Active`,
`Suspended`, and `Deactivated` after creation, even though the data model already supported it;
(2) nothing prevented removing the Administrator role, or suspending/deactivating a user, in a way
that would leave the system with zero active Administrators. Both closed the gap that made it
impossible to fully retire the `gd_recovery_admin` account created during the earlier recovery.

**Backend:** `IAMService.set_user_status()` — a closed allow-list (`Active ⇄ Suspended`,
`Active/Suspended → Deactivated`, `Deactivated` terminal), mirroring Substation Registry's own
`_STATUS_TRANSITIONS` convention. Rejects no-op transitions, undefined transitions, and an
empty/whitespace-only reason; never touches username, password, or role grants; records a full
audit entry (previous status, new status, reason, actor, timestamp) on every successful
transition. `POST /api/v1/users/{user_id}/status`, gated by the existing `iam.user.manage`
permission — no new permission or role introduced. The last-active-Administrator invariant
(`IAMService._assert_would_not_remove_last_active_administrator`) is enforced inside the same
transaction as the mutation, with `FOR UPDATE OF "user"` row-locking against concurrent callers,
applied to both `set_user_status` and `revoke_role_from_user`. Confirmed (no code change needed):
`get_current_user` already re-checks `User.status` from the database on every request, so an
existing token for a newly-suspended or -deactivated user is rejected on its very next use — no
token blacklist was required.

**Frontend:** `UsersPage.tsx` gains a status panel per user (Suspend/Reactivate/Deactivate buttons,
matching the user's current status), requiring a non-empty reason before the action can be
confirmed, and surfacing the backend's own rejection message verbatim (including the
last-Administrator safeguard's message) — no client-side admin-counting logic. No delete or
password control was added.

**Explicitly not implemented (deferred, per this sprint's own scope):** self-service or
administrator-driven password reset/change, audit-history viewing, Role retirement, bootstrap
scope changes, and a CLI administration tool — see `docs/architecture/iam-module.md` §17.

**Documentation:** `docs/architecture/iam-module.md` §8 (lifecycle) and §12 (API contract) updated
in place to describe the completed transitions and the new endpoint; a status note records the
sprint and cross-references the investigations that motivated it.

---

## Substation Registry Fix — Editable Region, State, and Grid Owner Metadata

**Scope:** UAT finding: Region, State, and Grid Owner could not be edited on an existing Substation
after creation, unlike GM Zone. Investigation found this was a **frontend-only gap, not an
architectural decision** — `SubstationService.update_substation()`, `SubstationUpdate` (schema),
and the `PATCH /api/v1/substations/{id}` router have supported all three fields (validated against
reference data, audited, no-op-safe) since Phase 2/the GM Zone enhancement; the Edit form in
`SubstationDetailPage.tsx` simply never rendered the corresponding controls.

**Backend:** No changes — already correct. Added the test coverage that previously existed only
incidentally: editing State, editing Grid Owner, editing Region/State/Grid Owner/GM Zone together
in one request (one audit row per changed field, no coupling), a no-op update writing zero audit
rows, unknown-reference-id rejection on update (mirroring the existing create-time checks), and
write-permission enforcement on the update endpoint.

**Frontend:** Added Region, State, and Grid Owner `<select>` fields to the Substation Detail page's
Edit form, mirroring GM Zone's existing pattern exactly (preloaded from the current record,
independently changeable, backend validation errors displayed the same way as every other field).
No layout change beyond the three new fields.

**Documentation:** `docs/architecture/substation-registry.md` §10 updated in place to state that
`region_id`/`state_id`/`grid_owner_id`/`gm_zone_id` are independently editable, and to record that
this was a frontend omission rather than a restriction.

**Confirmed:** no reference table involved (`Region`/`State`/`GridOwner`/`GmZone`) has an
`is_active` concept, so no "active/inactive" enforcement was needed. No field is derived from or
coupled to another. Substation identity (`substation_id`, `mnemonic`-as-identity) is unaffected —
only organizational/location metadata is now editable, exactly as it already was for GM Zone.

---

## Substation Registry Enhancement — Lifecycle Simplification

**Scope:** Project Owner-directed simplification of the Substation lifecycle
([ADR-014](docs/adr/ADR-014-substation-lifecycle-simplification.md), superseding
[ADR-005](docs/adr/ADR-005-substation-operational-status-lifecycle.md)) from six states/seven
transitions down to four states/four transitions: `Under Construction`, `Active`,
`Decommissioned`, `Entered in Error`. `Planned`, `Mothballed`, and `Retired` are removed from the
Substation lifecycle.

**Backend**

- `SubstationService`'s closed allow-list (`_STATUS_TRANSITIONS`, `_ALLOWED_INITIAL_STATUS_CODES`)
  rewritten to the four ADR-014 edges (`Under Construction → Active`,
  `Under Construction → Entered in Error`, `Active → Decommissioned`, `Active → Entered in Error`);
  creation-time initial status is now `Under Construction` or `Active` (`Under Construction`
  replaces the removed `Planned` as the "newly registered" entry point).
- **No schema or migration change.** `operational_status` is shared Core Platform reference data —
  Equipment Registry's own service layer (Circuit, Transformer, SubstationVoltageYard)
  independently uses `Planned`/`Mothballed`/`Retired` for its own, unrelated status model, so the
  seeded reference rows are left untouched (`app/reference_data/seed.py` unchanged); the closed
  allow-list above simply no longer includes them as legal for a *Substation*. No pre-existing
  Substation row's `operational_status_id` was reassigned — a row already at a removed status
  (verified: one development-database row, `TEST`, at `Retired`) is left as-is and becomes
  permanently terminal under the new allow-list, per this project's "do not invent or silently
  alter real data" discipline.

**Frontend**

- Create Substation's "Initial status" options and Substation Detail's "Change status" and List
  page's status filter options are now filtered to the four ADR-014 codes (mirroring the existing
  filtered-options pattern already used for Create's initial-status list); the Detail page's status
  *display* (and the List page's own status column) remain unfiltered, since either can still show
  a legacy row's actual, previously-assigned status.

**Documentation:** [ADR-014](docs/adr/ADR-014-substation-lifecycle-simplification.md) added;
[`docs/architecture/substation-registry.md`](docs/architecture/substation-registry.md) §8 rule 7,
§10 (CRUD Lifecycle diagram/table, now v3) updated in place, consistent with how §10 was already
updated in place from v1 to v2 for ADR-005. ADR-005 itself is left unmodified as the historical
record of the lifecycle's prior form.

**Tests:** `TestStatusTransitionLegality` in Substation Registry's service-layer tests rewritten
for the four-edge model (creation-time codes, the four legal edges, terminal-state and
rejected-transition coverage); the API contract test for transition legality rewritten to exercise
`Under Construction → Active` and the now-illegal `Active → Under Construction`/
`Under Construction → Decommissioned` edges.

**Confirmed:** no other module's business rules were changed — Equipment Registry's own,
independent use of `Planned`/`Mothballed`/`Retired` for Circuit/Transformer/SubstationVoltageYard
is untouched, confirmed by an explicit database check before implementation (only
`Active`/`Entered in Error` are actually in use by those tables in the development database).

---

## Substation Registry Enhancement — GM Zone Metadata

**Scope:** Project Owner-approved enhancement to the Substation Registry. Each `Substation` gains
a new attribute, **GM Zone (Grid Maintenance Zone)** — the organizational maintenance zone
responsible for maintaining the substation. Purely organizational, not electrical, and
**independent of `Region`** (a grid-planning grouping) — the two are never coupled by any FK,
constraint, or derivation. Implemented following the exact architectural and implementation
pattern already established for `Region`: a Core Platform reference/lookup table
(`app/reference_data/`), not a table owned by the Substation Registry module itself, mirroring the
already-established precedent that domain-adjacent simple lookup tables (e.g. `line_type`) live
alongside the other shared reference data rather than duplicating that pattern per module. See
[`docs/architecture/substation-registry.md`](docs/architecture/substation-registry.md)'s own
"Status update (GM Zone metadata enhancement)" callout for the full architectural rationale.

**Backend**

- New Core Platform reference table `gm_zone` (`gm_zone_id`, `code`, `label`) — twelve seeded
  values (Alor Setar, Butterworth, Ipoh, Selangor, Kuala Lumpur, Seremban, Ayer Keroh, Kluang,
  Johor Bahru, Kuantan, Dungun, Kota Bharu), seeded via `app/reference_data/seed.py` exactly like
  every other reference table — never hardcoded into application logic. Exposed read-only via
  `GET /api/v1/reference-data/gm-zones`, mirroring every other reference-data endpoint (no
  permission gate beyond authentication).
- New `substation.gm_zone_id` FK column (migration `0016_gm_zone`) — `NOT NULL`, exactly like
  `region_id`/`state_id`/`grid_owner_id`. The column was briefly nullable during initial rollout
  (avoiding an invented default to backfill pre-existing substation rows against); once the
  Project Owner manually assigned a valid GM Zone to every existing Substation in the development
  database, the migration was tightened to `NOT NULL` in place (never having been merged) and the
  now-obsolete service-layer "required only when Active" conditional logic
  (`GmZoneRequiredForActiveSubstationError`) was removed — GM Zone is now unconditionally required,
  exactly like the three fields it mirrors.
- `gm_zone_id` is independently editable via `PATCH /api/v1/substations/{id}` (unlike
  `region_id`/`state_id`/`grid_owner_id`, which the service layer has always supported changing
  but the frontend's edit form does not yet expose) — every change is audited via the existing
  `substation_audit_log`, one row per change, exactly like every other tracked field.
- `GET /api/v1/substations` gains a `gm_zone_id` filter, alongside the existing `region_id`
  filter — the two are independent, composable filters, never coupled.

**Frontend**

- GM Zone added everywhere Region already appears: the Substation List (new column and filter),
  Create Substation (new field, unconditionally `required`), Substation Detail (displayed) and its
  Edit form (a new editable field — Region itself is not yet editable in this form; GM Zone's own
  editability is a deliberate, explicit addition per this enhancement, not a byproduct of mirroring
  Region). Display label: **"GM Zone"**, not abbreviated further.
- `useReferenceData()` (the shared Core Platform reference-data hook) gains `gmZones`/
  `gmZonesById`, following the exact pattern already used for `regions`/`regionsById`.

**Dashboard:** No GM Zone summary was added — the existing Substation Registry list/filter surface
already answers "how many substations are in GM Zone X" via the new filter; no dedicated dashboard
concept exists for Region either, so none was introduced for GM Zone by analogy (consistent with
the instruction not to invent new dashboard concepts).

**Tests**

- Backend: new reference-data seed/backfill/API tests for `gm_zone`, mirroring `line_type`'s own
  established test pattern exactly (`test_seed_backfills_gm_zones`, etc.).
  `TestGmZoneIndependenceAndEditing` test class in Substation Registry's own service-layer tests
  (independent of Region, editable and audited) — the Active-conditional/Planned-optional test
  cases from the initial rollout were removed once GM Zone became unconditionally required,
  mirroring how region_id/state_id/grid_owner_id are tested. GM Zone API contract tests
  (create-without-GM-Zone returns 422, list filter, edit-and-audit, `null` in an update payload
  treated as not-supplied). **Every other module's test fixtures that create an Active substation
  directly through `SubstationService`** (Automatic Load Shedding Functionality Registry, Equipment
  Registry, Network Model, PSS/E Integration, Sensitive Customer Registry, and the corresponding
  `backend/tests/test_*_api.py` files) already supplied `gm_zone_id` from the initial rollout and
  needed no further change.
- Frontend: GM Zone reference-data stubs and assertions in all three Substation Registry page test
  suites; the Create/Detail page tests' conditional-requiredness cases were simplified to
  unconditional-requiredness once the backend invariant was tightened.

**Confirmed:** Region's own behavior is unchanged (no test, schema, or business-rule modification
to `region_id` itself). GM Zone is implemented as fully independent organizational metadata — no
FK, constraint, derivation, or shared vocabulary ties it to Region. No unrelated registry's own
business logic was modified — only test fixtures that construct an Active `Substation` (Substation
Registry's own upstream entity) were updated to supply the newly-required field.

---

## Phase 3.7 — Sensitive Customer Registry

**Scope:** A new, dedicated Engineering Registry module answering, per Transformer Terminal,
"would operating this bay affect a facility that deserves special engineering consideration, and
how sensitive is it?" —
[`docs/architecture/sensitive-customer-registry-module.md`](docs/architecture/sensitive-customer-registry-module.md),
[ADR-012](docs/adr/ADR-012-sensitive-customer-registry-architecture.md),
[EDR-008](docs/engineering/edr/EDR-008-sensitive-customer-registry-scope.md). Unlike every other
module in this series, this registry is explicitly designed from inception to remain reusable by
future engineering applications that have never heard of GridDefence, UFLS, UVLS, or EMLS —
no scheme-specific vocabulary appears anywhere in its owned entities or service interface.

**Backend**

- New module `app/modules/sensitive_customer_registry/`: `models.py` (`SensitiveFacility`,
  `FacilitySector`, `SensitivityClassification`, `SensitiveCustomerRegistryAuditLog`),
  `schemas.py`, `service.py`, `repository.py`, `router.py`, `bootstrap.py`, `seed.py`,
  `exceptions.py`, `dependencies.py`.
- **One record per physical facility** (`SensitiveFacility`), referencing at most one *current*
  Transformer Terminal by ID (nullable — a facility may be registered before its supply point is
  confirmed), never Equipment Registry's attributes directly (CLAUDE.md A1). **No uniqueness
  constraint on the terminal reference** — the deliberate inverse of ALSF's own per-terminal
  uniqueness rule: many facilities may legitimately share one bay.
- **`FacilitySector` and `SensitivityClassification` as module-owned, admin-editable reference
  data** — the first implemented precedent of this pattern in this codebase (Critical
  Infrastructure's parallel `CriticalityLevel` remains unimplemented). Seeded with the eight
  approved sectors and three approved classifications
  (`python -m app.modules.sensitive_customer_registry.seed`); `code` is immutable after creation,
  `label`/`sort_order`/`description`/`is_active` are editable; no `DELETE` endpoint exists for
  either table — deactivation is the only retirement path.
- **Lifecycle: `Active ⇄ Archived → Entered in Error`** — deliberately not ALSF's
  `DECOMMISSIONED` vocabulary. `Active → Archived` is reversible (unlike ALSF's terminal
  decommission); `Entered in Error` is terminal, reachable from either prior state, no exceptions.
  Every transition requires a non-empty, audited reason.
- **A `transformer_terminal_resolution` field (`NOT_ASSIGNED`/`RESOLVED`/`UNRESOLVED`) is reported
  independently of `lifecycle_status` on every read** — a facility is never omitted from
  `list_facilities`/`get_facility_detail`/any lookup merely because its Transformer Terminal
  cannot currently be resolved through Equipment Registry; the condition is surfaced as
  information instead of hidden.
- **Reassigning a facility's Transformer Terminal association requires a mandatory, non-empty
  reason** — stricter than ALSF's optional-reason-on-metadata-edit convention, producing one
  audit row containing the previous terminal ID, new terminal ID, reason, actor, and timestamp.
- **Batch and single-terminal lookup service interfaces**
  (`get_sensitive_facilities_for_transformer_terminal(s)`, `has_sensitive_facility`) for future
  UFLS/UVLS/EMLS Sensitive Customer Review consumption — the batch contract resolves entirely
  against this module's own table (no cross-module call on the read path), so every requested
  terminal ID always receives a result, with no partial-failure mode.
- **Permissions — Administrator-only mutation**, a deliberate departure from ALSF's own
  Administrator+Engineer `.write` precedent: this registry is global authoritative engineering
  knowledge that scheme engineers consume but do not own. `sensitive_customer_registry.read`
  (Administrator + Engineer — gated, not open to every authenticated user, unlike ALSF's own
  read permission), `.write` (Administrator only — create/edit/reassign/lifecycle actions),
  `.manage_reference_data` (Administrator only — sector/classification administration). No new
  role introduced.
- New endpoints under `/api/v1/sensitive-customer-registry`: facility list/create/detail/update,
  `/archive`, `/reactivate`, `/entered-in-error`, `/audit-log`, `/facilities/summary`,
  `/facilities/batch-lookup`, `/facilities/by-transformer-terminal/{id}`, plus
  `/reference-data/facility-sectors` and `/reference-data/sensitivity-classifications`
  (list/create/update).
- Migration `0015_sensitive_customer_registry` — hand-written, manually reviewed, verified
  `upgrade → downgrade → upgrade` against real PostgreSQL.

**Frontend**

- New module `frontend/src/modules/sensitive_customer_registry/` (`types.ts`, `api.ts`,
  `displayHelpers.ts`) plus 5 pages under `pages/`: `FacilityListPage` (filterable registry list
  with a lightweight in-module summary strip — active/archived/entered-in-error/unresolved-
  terminal counts), `FacilityCreatePage`, `FacilityDetailPage` (detail, metadata edit, and all
  three lifecycle actions), `FacilitySectorAdminPage`, `SensitivityClassificationAdminPage`
  (reference-data administration, gated by `.manage_reference_data`).
- **A stale/unresolved Transformer Terminal reference is always rendered as an explicit notice**
  ("Terminal could not be resolved"), never a blank cell or a silently-omitted row — the frontend
  counterpart of the backend's `transformer_terminal_resolution` field.
- Wired into `router.tsx` (`/sensitive-customer-registry`, `/new`, `/:facilityId`,
  `/reference-data/facility-sectors`, `/reference-data/sensitivity-classifications`) and
  `AppShell.tsx`'s nav ("Sensitive Customer Registry").

**Tests**

- Backend: 36 service-layer tests (`test_service.py` — creation/validation, reference-data
  administration, the multi-facility-per-terminal regression test, mandatory-reason reassignment
  auditing, all four lifecycle transitions plus the `Entered in Error` terminal-state prohibition,
  stale-terminal-never-omitted behaviour, deterministic audit ordering for same-timestamp rows,
  the seed-vs-service actor-nullability boundary, batch-lookup completeness, the no-cross-module-
  import architectural test), 7 bootstrap tests, and 20 API contract tests
  (`backend/tests/test_sensitive_customer_registry_api.py` — auth/RBAC including the
  Administrator-only mutation regression test explicitly covering every lifecycle action, full
  create→lifecycle HTTP flow, reference-data administration, no `DELETE` endpoint confirmed
  absent, batch-lookup deduplication/bounding/empty-input behaviour). Full backend suite
  (666 tests) passing; this module's own 63 tests additionally verified against real PostgreSQL.
- Frontend: 18 tests across the 3 core pages plus `displayHelpers`, reusing the existing
  `frontend/tests/testUtils.tsx` harness exactly as every other module's tests do — no new test
  infrastructure introduced. Full frontend suite (209 tests) passing; lint/typecheck/build clean
  for every file this phase added.

**Known limitations**

- Sensitive Customer Review (03-system-workflow.md) is not yet an end-to-end workflow step — this
  module provides every interface UFLS/UVLS/EMLS need, but none of those scheme modules exist yet
  to call them. See `docs/architecture/implementation-plan.md` Phase 6/7/8 for the recorded
  dependency; Phase 3.7 is required to precede Phase 6, mirroring ALSF (Phase 3.6)'s own
  precedent.
- This module was built and merged outside the original 14-phase numbered sequence, following the
  precedent already set by Phase 3.5 (Transformer Registry) and Phase 3.6 (ALSF); labeled
  **Phase 3.7** in `implementation-plan.md`.
- **The repository-standard `npm run build` gate does not pass** — it fails on a pre-existing
  TypeScript project-check error in `frontend/tests/components/ui/DataTable.test.tsx`
  (a `@tanstack/react-table` generic-inference incompatibility), confirmed via `git diff` against
  this phase's own commit to predate it entirely — no file this phase added or modified is
  implicated, and this module's own TypeScript surface typechecks cleanly in isolation. The actual
  Vite production bundle (`vite build`) succeeds. Recommend fixing `DataTable.test.tsx` in its own
  follow-up task, since it blocks the standard build command for every module, not just this one.

---

## Phase 3.7 — UAT Change Request: Multiple Transformer Terminal Association

**Scope:** During manual UAT of Phase 3.7 above, the Project Owner approved an engineering
refinement: **`SensitiveFacility` now associates with zero, one, or many currently active
Transformer Terminals**, replacing the single nullable `transformer_terminal_id` reference.
Recorded in [ADR-013](docs/adr/ADR-013-sensitive-facility-multiple-transformer-terminals.md),
which amends [ADR-012](docs/adr/ADR-012-sensitive-customer-registry-architecture.md) decision 2.
This is **not** alternate-supply modelling (no primary/backup priority) and **not**
supply-history modelling (no validity window) — it is the authoritative record of every
currently active supply point, exactly as the module document's own §7 design note anticipated
might one day be needed.

**Backend**

- New association table `sensitive_facility_transformer_terminal(facility_id,
  transformer_terminal_id, added_at, added_by_user_id)` — composite primary key, current-state
  only, mirroring IAM's own `RolePermission` grant pattern (not `UserRole`'s historical-retention
  `revoked_at` pattern). `transformer_terminal_id` is removed from `sensitive_facility`.
- Migration `0015_sensitive_customer_registry.py` edited in place (never merged prior to this
  change, so per this project's own established convention for pre-merge migrations, it is
  corrected directly rather than superseded by a new migration).
- `SensitiveFacilityCreate.transformer_terminal_ids: list[UUID]` replaces the singular field;
  duplicate IDs in a request are silently deduped, not rejected.
- New endpoint `PUT /facilities/{id}/terminals` (`SensitiveFacilityTerminalsUpdate`) replaces the
  full association set in one call; the service layer diffs the requested set against the current
  set and writes one audit row per actual addition or removal (never one opaque bulk event) — a
  mandatory, non-empty `change_reason` is required whenever the set actually changes, continuing
  Correction 5's reassignment-reason discipline. `SensitiveFacilityUpdate` (`PATCH`) no longer
  carries a terminal field at all.
- `transformer_terminal_resolution` becomes per-association (`RESOLVED`/`UNRESOLVED`); a
  facility-level aggregate is retained for list filtering (`NOT_ASSIGNED`/`RESOLVED`/`UNRESOLVED`
  per ADR-013 decision 4), but full per-association detail is always exposed in list/detail
  responses — `SensitiveFacilitySummary`/`SensitiveFacilityDetail` gain
  `transformer_terminals: list[SensitiveFacilityTerminalAssociation]`.
- Batch/single lookup (`get_sensitive_facilities_for_transformer_terminal(s)`,
  `has_sensitive_facility`) now match on "any associated terminal matches" — a facility with
  terminals A and B appears under both A's and B's key in a batch-lookup response. The
  `BatchLookupRequest`/`BatchLookupResponse` contract shape itself is unchanged.
- New Equipment Registry endpoint `GET /transformer-terminals`
  (`list_transformer_terminal_identities`) — every Transformer Terminal across every substation,
  with full composed identity, unpaginated. Exposed as its own top-level resource (final UAT
  naming refinement — initially added as `/transformers/terminals`, renamed to match
  `VoltageYard`'s own `/voltage-yards` precedent: a subordinate engineering entity that must be
  browsed/filtered across its parent, not only within one already-selected parent's context).
  Added to support the frontend's flat multi-select (no existing endpoint provided this without
  requiring a substation/transformer to already be selected); a general-purpose,
  module-boundary-respecting addition to the module that already owns Transformer Terminal
  identity, not specific to the Sensitive Customer Registry.

**Frontend**

- Removed the cascading Substation → Transformer → Transformer Terminal picker from
  `FacilityCreatePage` entirely.
- New `TerminalMultiSelect` component (`frontend/src/modules/sensitive_customer_registry/
  components/`) — a searchable, flat multi-select sourced from every Transformer Terminal across
  every substation, each option labelled with full engineering context (e.g. "SARA | 33kV |
  Transformer T1 (LV)"), used by both `FacilityCreatePage` and a new, separate "Transformer
  Terminal(s)" section on `FacilityDetailPage`. Selected terminals are shown in a compact
  Substation / Voltage / Transformer / Terminal table.
- `FacilityDetailPage`'s Transformer Terminal association editing is now a separate section and
  mutation (`PUT .../terminals`) from the metadata edit form (name/sector/classification/
  remarks) — the Save button is disabled until the set actually changes and a reason is entered.
- `FacilityListPage`'s "Supply Point(s)" column now lists every currently associated terminal
  (or the resolution explanation, per facility, if none are associated).
- New `apiClient.put` method (previously absent — only `get`/`post`/`patch`/`delete` existed).

**Tests**

- Backend: `test_service.py` and `test_sensitive_customer_registry_api.py` updated for the
  collection-based shape; new tests cover multiple terminals on one facility, deduplication of
  duplicate terminal IDs, add-and-remove-in-one-call association diffing and per-change audit
  rows, no-op calls requiring no reason, per-association resolution with a correctly-aggregated
  facility-level status, and batch lookup matching a facility under every associated terminal's
  key. Full backend suite (678 tests, 1 pre-existing Windows-only subprocess-flake deselected)
  passing.
- Frontend: `TerminalMultiSelect` exercised through `FacilityCreatePage`/`FacilityDetailPage`
  tests (search-and-select without a Transformer step, compact selected-terminal table, the
  `PUT .../terminals` reason-required-when-changed flow); `displayHelpers.test.ts` covers the new
  `side`-aware identity formatting and `formatTerminalPickerLabel`. Full frontend suite (212
  tests) passing; `tsc --noEmit` clean.

**No unrelated functionality was changed.** Module boundaries, permission model, lifecycle model,
reference-data conventions, and the polymorphic audit log's shape are all unaffected — only the
cardinality of the Transformer Terminal association changed, exactly as ADR-013 scopes it.

---

## Phase 3.6 — Automatic Load Shedding Functionality Registry

**Scope:** A new, dedicated Engineering Registry module answering, per Bay Terminal, "can this
bay be operated by a Grid Defence Scheme?" —
[`docs/architecture/automatic-load-shedding-functionality-registry-module.md`](docs/architecture/automatic-load-shedding-functionality-registry-module.md),
[ADR-011](docs/adr/ADR-011-automatic-load-shedding-functionality-registry.md). This is the
implementation of the engineering concept previously discussed as "Relay Registry"
([EDR-003](docs/engineering/edr/EDR-003-relay-registry-scope.md),
[02-engineering-concepts.md](docs/engineering/02-engineering-concepts.md)) — "Relay Registry" is
retired as a working/implementation name, not as an engineering concept; EDR-003's scope
discipline (a capability answer, never general relay asset management) is unchanged and fully
carried into the as-built module. Retires the general-purpose relay-wiring direction sketched
(never built) in `equipment-registry-module.md` §7.8, in favor of this simpler, purpose-built
entity.

**Backend**

- New module `app/modules/automatic_load_shedding_functionality/`: `models.py`
  (`AutomaticLoadSheddingFunctionality`, `AutomaticLoadSheddingFunctionalityAuditLog`),
  `schemas.py`, `service.py`, `repository.py`, `router.py`, `bootstrap.py`, `exceptions.py`,
  `dependencies.py`.
- **One record per Bay Terminal** — `circuit_terminal_id` XOR `transformer_terminal_id`
  (database-enforced two-way `CHECK`), referencing Equipment Registry's `CircuitTerminal`/
  `TransformerTerminal` by ID only, never duplicating their attributes (CLAUDE.md A1). A partial
  unique index enforces at most one non-decommissioned record per terminal.
- **UFLS and UVLS capability represented independently, on the same record**:
  `ufls_function`/`uvls_function` booleans — a single bay terminal may support both
  simultaneously (one multifunction relay serving both schemes). **EMLS is intentionally excluded
  in every respect** — no field, enum value, or query parameter anywhere in this module references
  EMLS, since EMLS is manually invoked and has no automatic-functionality prerequisite (module
  document §4, §9 rule 4).
- **Simplified two-state persisted lifecycle**: `lifecycle_status` (`ACTIVE`/`DECOMMISSIONED`) —
  a record is always created `ACTIVE`; `Active → Decommissioned` is the only transition, terminal,
  one-way, requires a non-empty reason, and is fully audited. A decommissioned record is
  permanently immutable — including against a second decommission attempt, which is rejected, not
  silently accepted.
- **Computed, never-stored display status** — `AVAILABLE` / `ASSIGNED` / `DECOMMISSIONED` — is
  derived at read time from `lifecycle_status` plus an optional, caller-supplied
  `assigned_terminal_ids` set (the Future Integration Contract for UFLS/UVLS, module document
  §8.2): no caller exists yet, so every non-decommissioned record displays `AVAILABLE` today, with
  zero placeholder assignment table anywhere in this module's schema.
- **Candidate-search and capability-check service interfaces** for future UFLS/UVLS consumption:
  `is_ufls_capable`/`is_uvls_capable`, `list_candidate_terminals`, `list_assigned_and_available`.
  New endpoints under `/api/v1/automatic-load-shedding-functionality`: `GET`/`POST` (list/create),
  `GET`/`PATCH /{id}` (detail/metadata edit), `POST /{id}/decommission`, `GET /{id}/audit-log`,
  `GET /candidates`, `GET /capability-check`. No `/activate`/`/deactivate` endpoints exist —
  Available/Assigned are always computed, never manually set.
- **Equipment Registry additions** (read-only, cross-module, via its own service layer per
  CLAUDE.md A1): `get_circuit_terminal_identity`/`get_transformer_terminal_identity`,
  `get_circuit_terminal_summary`/`get_transformer_terminal_summary`,
  `get_transformer_terminal_by_id` — compose each terminal's full engineering identity
  (substation, voltage level, and `Circuit.circuit_name`/`Transformer.generated_short_name`,
  reusing those already-computed values, never re-deriving them) so two terminals at the same
  substation and voltage level are always displayed distinctly.
- New permissions: `automatic_load_shedding_functionality.read` (open to any authenticated user,
  matching this project's existing read-permission precedent) and
  `automatic_load_shedding_functionality.write` (Administrator + Engineer; Viewer receives read
  only) — `bootstrap.py` registers and grants both to the baseline roles.
- Migration `0014_alsf_registry` — hand-written, manually reviewed, edited in place multiple times
  before its first merge (never after — CLAUDE.md §5.2), verified `upgrade → downgrade → upgrade`
  against real PostgreSQL each time.

**Frontend**

- New module `frontend/src/modules/automatic_load_shedding_functionality/` (`types.ts`, `api.ts`,
  `displayHelpers.ts`) plus 4 pages under `pages/`: `FunctionalityListPage` (filterable registry
  list, with an explanatory message rather than a silently-hidden action when the current user
  lacks write permission), `FunctionalityCreatePage`, `FunctionalityDetailPage` (detail, metadata
  edit, and the sole remaining Decommission lifecycle action), `FunctionalityCandidatePage`
  (scheme-design-time candidate search by UFLS/UVLS scheme type).
- **Full engineering identity displayed consistently across every view** — `"Substation | Voltage
  | Bay"` (e.g. `IGBK | 33kV | Transformer T1`), composed client-side (CLAUDE.md A12,
  display-only derivation) from three already-separate fields every read DTO reports, never
  stored as its own column.
- Wired into `router.tsx` (`/automatic-load-shedding-functionality`, `/new`,
  `/:functionalityId`, `/candidates`) and `AppShell.tsx`'s nav ("ALSF Registry").

**Tests**

- Backend: 41 service-layer tests (`test_service.py` — creation/validation, uniqueness, the
  decommission lifecycle, bay-identity distinctness, Available/Assigned/Decommissioned status
  computation from a caller-supplied `assigned_terminal_ids` set, candidate/capability queries),
  6 bootstrap tests, and 10 API contract tests
  (`backend/tests/test_automatic_load_shedding_functionality_api.py` — auth/RBAC, full create→
  decommission HTTP flow, `/activate`/`/deactivate` confirmed absent, re-decommission rejected).
  Full backend suite (600+ tests across every module) passing against real PostgreSQL.
- Frontend: 28 tests across the 4 pages plus `displayHelpers`, including explicit coverage for
  two ambiguous terminals at the same substation and voltage level always rendering distinct
  identities. Full frontend suite passing; lint/typecheck/build all clean.

**Known limitations**

- Relay Capability Verification (03-system-workflow.md) is not yet an end-to-end workflow step —
  this module provides every interface UFLS/UVLS need, but neither scheme module exists yet to
  call them. See `docs/architecture/implementation-plan.md` Phase 6/7 for the recorded dependency.
- This module was built and merged outside the original 14-phase numbered sequence (it was
  originally deferred out of Phase 3 as `RelayDetail`/`RelayControlledEquipment`, never built,
  then re-scoped by ADR-011); labeled **Phase 3.6** in `implementation-plan.md`, following the
  precedent already set by Phase 3.5 (Transformer Registry) — see that document's phase numbering
  note for the full reasoning.

---

## Phase 4 — PSS/E Integration

**Scope:** RAW file import infrastructure —
[`docs/architecture/psse-integration-module.md`](docs/architecture/psse-integration-module.md),
[ADR-003](docs/adr/ADR-003-psse-topology-and-load-snapshot-separation.md) (topology/load
separation), [ADR-006](docs/adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md)
and [ADR-007](docs/adr/ADR-007-canonical-engineering-reference-object.md)
(`EquipmentTopologyMap`). Implements only PSS/E import/preview/commit/activate and
`EquipmentTopologyMap` correlation — Network Model, UFLS, UVLS, and scheme assignment logic remain
explicitly out of scope, per the task's own instruction.

**Mandatory pre-implementation step.** Before any parser or model code was written, the two real
sample RAW files at `docs/samples/psse/` (`110226n.raw` — full topology + load, rev 34; and
`PSSE_LOAD_20260608_1730.raw` — load-only, abbreviated field shape) were inspected directly
(section ordering, exact field layouts, terminator conventions, comment syntax) and findings
presented before implementation began, per the task's explicit mandate to design against real
files rather than generic PSS/E documentation. Two concrete, non-obvious findings drove the
parser's design: (1) LOAD DATA appears in **two different shapes** in real files — a 17-field
standard shape and a 7-field abbreviated shape sharing fields 0-6 — and a third, genuinely valid
"no reading" 2-field shape (`I,'ID' / No Reading / ...`) that is not malformed data, just a meter
with nothing to report that cycle; (2) the load-only sample has **zero header lines, zero bus
records, and inconsistent/out-of-sequence section terminator labels**, so section tracking is done
purely by counting terminator lines in the order they appear, never by matching a fixed, closed
list of expected section names — an unrecognized section is tolerated (warned, not fatal).

**Backend**

- New module `app/modules/psse_integration/`: `models.py` (`RawFileImportBatch`,
  `TopologyVersion`, `TopologyBus`, `TopologyBranch`, `TopologyTransformer`, `LoadSnapshot`,
  `LoadSnapshotBusState`, `LoadSnapshotElementState`, `NetworkLoad`, `NetworkGenerator`,
  `EquipmentTopologyMap`, `PsseImportAuditLog`), `raw_parser.py`, `signature.py`, `matching.py`,
  `repository.py`, `service.py`, `schemas.py`, `exceptions.py`, `dependencies.py`, `router.py`,
  `bootstrap.py`, `jobs.py`.
- **Topology/load separation is structural (ADR-003), not a naming convention:**
  `TopologyBus`/`TopologyBranch`/`TopologyTransformer` carry no P/Q, voltage, or in-service field
  anywhere — that data lives exclusively on `LoadSnapshotBusState`/`LoadSnapshotElementState`/
  `NetworkLoad`/`NetworkGenerator`. This guarantees, by construction, that momentary operational
  state can never leak into the deterministic topology signature.
- **Deterministic topology signature** (`signature.py`): a SHA-256 hash over canonicalized
  (sorted, fixed-6-decimal-formatted) bus/branch/transformer records, with branch/transformer
  endpoints sorted so PSS/E's arbitrary from/to ordering never affects the hash. Re-importing a
  structurally identical file reuses the existing `TopologyVersion` rather than creating a
  duplicate.
- **Preview → Commit → Activate workflow**, all through the service layer: Preview
  (`PsseIntegrationService.preview`) is genuinely zero-persistence — no database row is ever
  created. Commit persists a `RawFileImportBatch`, `TopologyVersion`/`LoadSnapshot` (or reuses an
  existing `TopologyVersion` by signature), but never marks anything Current. Activate is a
  separate, explicit, privileged action (`psse_integration.activate`) that atomically promotes a
  batch's `TopologyVersion`/`LoadSnapshot` to `Current`, automatically superseding whatever was
  previously Current — the lighter `Imported → Current → Superseded` lifecycle (ADR-003),
  deliberately distinct from CLAUDE.md A3's canonical engineering version lifecycle.
- **Flexible import types**, detected purely from parsed content (bus-record count present or
  absent), never from filename or user assertion: `FULL_TOPOLOGY_WITH_LOAD` creates/reuses a
  `TopologyVersion` and always extracts a `LoadSnapshot` from the same file; `LOAD_ONLY` requires
  an existing Current `TopologyVersion` to target (raises `NoCurrentTopologyVersionError`
  otherwise) and creates only a `LoadSnapshot`, matching loads by PSS/E bus number.
- **`EquipmentTopologyMap`** targets `CircuitTerminal` directly (never `Circuit`, never a generic
  `Equipment` id — this codebase's real Phase 3 build has no generic Equipment backbone, so
  ADR-007's terminology was adapted to the actual schema). Matching (`matching.py`, a pure,
  ORM-free function) is computed automatically whenever a *new* `TopologyVersion` is created:
  for each `CircuitTerminal`, candidates are PSS/E elements connecting that terminal's substation
  to any *other* terminal's substation within the same `Circuit` (generalizes to tee-offs with no
  special-casing); disambiguated by exact `ckt_id`-vs-`bay_number` match. Zero candidates →
  `unmatched`; exactly one exact match → `clean_match`; anything ambiguous or mismatched →
  `discrepancy`, never guessed. `ENTERED_IN_ERROR` circuits/terminals are excluded from matching
  candidates entirely. Resolving a discrepancy (`resolve_discrepancy`) only records the engineer's
  classification on this module's own table — it never writes to Equipment Registry, since the
  real `CircuitTerminal.voltage_yard_id` has no edit path after creation to write to.
- **Redis + RQ** introduced for the first time in this project (`app/core/queue.py`,
  `app/worker.py`) for async RAW parsing/validation. `settings.rq_async` (new config field,
  default `True`) set to `False` in the test environment (`backend/conftest.py`) runs jobs
  synchronously, in-process, against a `fakeredis` connection — no real Redis server needed for
  correctness tests. `jobs.py` contains the only code in this module that opens its own database
  session (`SessionLocal`), since RQ jobs run in a worker process outside any FastAPI request
  context.
- New endpoints under `/api/v1/psse-integration`: `POST /imports/preview`, `POST /imports/commit`
  (both return a job id; parsing runs async), `GET /imports/jobs/{id}` (poll), `GET/GET
  /imports/batches[/{id}]`, `POST /imports/batches/{id}/activate`, `GET/GET
  /topology-versions[/{id}]`, `POST /topology-versions/{id}/recompute-matching`, `GET/GET
  /load-snapshots[/{id}]`, `GET /current-status`, `GET
  /topology-versions/{id}/equipment-map`, `POST /equipment-map/{id}/resolve`, `GET
  /circuits/{id}/correlation`. New permissions: `psse_integration.read` (open to any authenticated
  user, matching this project's existing read-permission precedent), `psse_integration.import`
  (Administrator + Engineer), `psse_integration.activate` (Administrator only — activation is
  "explicit, privileged, atomic, and audited").
- Migration `0012_psse_integration` — hand-written, manually reviewed, fully reversible (verified
  `upgrade → downgrade → upgrade` against real PostgreSQL). One genuine design issue found and
  fixed before the migration was written: `raw_file_import_batch` ↔ `topology_version` ↔
  `load_snapshot` forms a real 3-table foreign-key cycle (a batch points forward at the
  TopologyVersion/LoadSnapshot it produced; those point back at the batch that created them) —
  resolved with `use_alter=True` on the batch's two forward-pointing columns, closing the cycle via
  a separate `ALTER TABLE` once all three tables exist, both in the SQLAlchemy models and the
  migration.
- `python-multipart` added as a new dependency (required by FastAPI for the RAW file upload
  endpoints — the first file-upload endpoints in this project).

**Frontend**

- New module `frontend/src/modules/psse_integration/` (`types.ts`, `api.ts`,
  `useJobPolling.ts`) plus 5 pages under `pages/`: `PsseImportUploadPage` (file select, preview,
  commit — polls the async job until terminal), `PsseImportHistoryPage` (paginated batch list),
  `PsseBatchDetailPage` (batch detail + Activate control, permission-gated), `PsseCurrentStatusPage`
  (current TopologyVersion/LoadSnapshot summary), `PsseEquipmentTopologyMapPage` (clean-match/
  unmatched/discrepancy review, with an Accept/Reject resolution form for discrepancies).
- `apiClient` gained a `postForm` method (multipart upload, no `Content-Type` override so the
  browser sets its own boundary) — the first file-upload support in the shared API client.
- Wired into `router.tsx` (`/psse-integration/import`, `/history`, `/batches/:batchId`,
  `/current-status`, `/topology-versions/:id/equipment-map`) and `AppShell.tsx`'s nav.

**Tests**

- Backend: 55 new tests across `test_raw_parser.py` (16, including direct integration tests
  against the real sample files — bus/branch/transformer counts, both 2- and 3-winding
  transformers, voltage solution extraction, "no reading" load handling, unknown-section
  tolerance), `test_signature.py` (7 — determinism, record-order and endpoint-order independence),
  `test_matching.py` (8 — clean-match/unmatched/discrepancy, case-insensitive ckt_id matching,
  tee-off generalization, cross-circuit isolation), `test_service.py` (16 — preview zero-
  persistence, topology reuse vs. new, load-only against Current, activation atomicity and
  supersession, ENTERED_IN_ERROR exclusion, discrepancy resolution and re-resolution rejection,
  circuit correlation), `test_jobs.py` (4), `test_bootstrap.py` (6), plus
  `tests/test_psse_integration_api.py` (8 — auth/RBAC, full preview→commit→activate HTTP flow via
  RQ running synchronously against `fakeredis`). 351 backend tests total, passing against both
  SQLite and real PostgreSQL.
- Frontend: 15 new tests across the 5 new pages plus 1 new `apiClient.postForm` test. 118 frontend
  tests total, passing; lint/typecheck/build all clean.
- **One genuine PostgreSQL-only defect found and fixed**, exactly the kind SQLite-only testing
  cannot catch: `psse_import_audit_log.entity_id` was `String(64)`, but
  `EquipmentTopologyMap`'s own audit entries key on a composite
  `"{topology_version_id}:{circuit_terminal_id}"` string (two UUIDs + separator = 73 characters) —
  SQLite silently accepts an over-length `VARCHAR`; PostgreSQL correctly raised
  `StringDataRightTruncation`. Fixed by widening the column to `String(80)` in both the model and
  the (still-unmerged) migration, then re-verified against real PostgreSQL.

**Known limitations**

- No manual browser UAT was performed for this phase — no browser automation tool was available in
  the implementation environment. Verification relied on the automated backend (SQLite + real
  PostgreSQL) and frontend (React Testing Library + lint/typecheck/build) suites, plus direct
  `alembic upgrade/downgrade/upgrade` verification against the real dev PostgreSQL database.
  Redis/RQ's real, non-`fakeredis` production path (`app.worker`, a genuine background worker
  process against a real Redis server) was not separately smoke-tested — only its `docker-compose.yml`
  wiring and the `rq_async=True` code path (exercised by every non-test run) were reviewed for
  correctness.
- The substation-to-bus matching heuristic (`_match_substation_for_bus`, matching a bus name's
  leading 4 characters against `Substation.mnemonic`, case-insensitively) is deliberately simple
  and documented as such — not a claim of perfect fidelity against every possible real PSS/E
  naming convention.
- The parser supports PSS/E RAW revision 34 only, as scoped — section boundaries are tracked by
  terminator-line counting rather than a fixed section list specifically so a future revision's
  differently-ordered or additional sections degrade to warnings rather than breaking existing
  parsing, but no second revision was implemented or tested against.
- A future Network Model module is the intended consumer of `get_circuit_correlation`
  (union-of-terminals resolution) — that module itself is out of this phase's scope, so this
  endpoint currently has no real caller beyond its own test coverage and the review UI.

---

## Phase 3.5 — Transformer Registry

**Scope:** `Transformer`/`TransformerTerminal` identity, inserted between Equipment Registry
(Phase 3) and PSS/E Topology Import (Phase 4) because a transformer is a fundamental topology
element defining connectivity between two voltage levels —
[`docs/architecture/equipment-registry-module.md`](docs/architecture/equipment-registry-module.md)'s
new "Phase 3.5 Addendum: Transformer Registry" section. Tertiary windings, transformer impedance,
tap-changer modelling, transformer loading, and protection-relay modelling remain explicitly out of
scope.

**Architecture Decision Gate.** Following the same architecture-first process used for Phase 3,
three genuine modelling ambiguities were presented with options and a recommendation before any
code was written, and implementation began only after explicit approval of all three: (1)
`TransformerTerminal` child rows (`side` = HV/LV) over direct `hv_*`/`lv_*` columns on
`Transformer`, mirroring `CircuitTerminal`'s own precedent, for future tertiary-winding
compatibility; (2) the generated engineering short name (e.g. `SGT1`) computed at read time, never
stored, for the identical reason `Circuit`'s own canonical name is computed rather than stored; (3)
uniqueness keyed on `(hv_switchyard_id, lv_switchyard_id, transformer_number)` — representing the
*physical transformer's* identity — deliberately distinct from the generated short name, which is a
separate, computed, user-facing label two physically distinct transformers at different substations
may legitimately share.

**Backend**

- `Transformer` (transformer number, capacity, commissioning date, operational status, type,
  manufacturer, remarks) and `TransformerTerminal` (one HV row, one LV row per transformer — each
  with its own breaker number) as new persistence models, plus `transformer_audit_log` as this
  entity family's own audit trail (CLAUDE.md A4).
- The engineering short name (`XGT1`, `SGT1`, `T1`, ...) is computed at read time from the HV
  terminal's voltage level, using a TNB prefix convention (500kV→`XGT`, 275/230kV→`SGT`,
  132/33/22/11kV→`T`) — never stored, never accepted on create/update.
- Business rules enforced at the service layer: exactly one HV and one LV terminal; HV voltage
  level strictly higher than LV; HV and LV terminals cannot connect to the same switchyard; HV and
  LV may belong to the same or different substations; a switchyard pair plus transformer number
  must be unique (checked via a repository query joining `TransformerTerminal` twice via
  `sqlalchemy.orm.aliased`, not a raw database constraint, per CLAUDE.md §11.8 — the identity spans
  two child rows a single-table `UNIQUE` constraint cannot express); a transformer's switchyards
  are immutable after creation.
- `voltage_level` reference data extended with 33kV, 22kV, and 11kV (previously only
  500/275/230/132kV existed) — the LV-side distribution voltage classes the short-name prefix table
  and breaker-suggestion formulas name explicitly.
- `equipment_registry.read`/`equipment_registry.write` permissions reused as-is — no new permission
  introduced.
- New endpoints: `GET/POST /api/v1/transformers`, `GET/PATCH /api/v1/transformers/{id}`,
  `GET /api/v1/transformers/{id}/audit-log` (the last one beyond the originally-specified four
  endpoints, added for consistency with Circuit's own audit-visibility pattern — a hard CLAUDE.md
  auditability requirement, not optional polish). No `DELETE` endpoint.
- Migration `0008_transformer_registry` — hand-written, manually reviewed, fully reversible, no
  data backfill (new tables, no pre-existing rows). Verified directly against real PostgreSQL
  (`alembic upgrade head`, schema inspection of all three new tables) and via live `curl` smoke
  testing against a running server on the real dev database (create, duplicate rejection, and
  reversed-voltage-order rejection all returned the expected human-readable errors).

**Frontend**

- `/transformers`, `/transformers/new`, `/transformers/:transformerId` — list (search/filter/
  paginate), create, and detail (inline edit, audit log) pages, following Circuit Registry's exact
  page/API-client conventions and UX pattern (list + create + detail-with-inline-edit, no separate
  edit route).
- Breaker-number suggestion (`suggestBreakerNumber`) — a pure, frontend-only function implementing
  the five given formulas (275kV: `H{N}0`; 230kV: `{N}H0`; 132kV: `{N}10`; 33kV/22kV: `{N}T0`;
  11kV: `3{N}`; no formula for 500kV, an intentional spec gap). Triggered once the HV/LV switchyard
  and transformer number are chosen; always freely overridable; the backend never validates or
  enforces breaker-number format.

**Tests**

- Backend: 42 new tests (29 service + 13 API) covering two-terminal creation, the generated
  short-name computation (parametrized across all 7 voltage levels), HV/LV voltage-order and
  same-switchyard rejection, same-substation-different-switchyard allowance, uniqueness rejection
  and parallel-transformer allowance, breaker-number override never rejected, search/filter, edit,
  and permission enforcement. 233 backend tests total, passing against both SQLite and real
  PostgreSQL.
- Frontend: 22 new tests (list, create, detail pages, plus the breaker-suggestion pure function)
  covering the generated short name display, auto-suggested and freely-overridable breaker numbers,
  list/detail rendering, edit submission, and permission-gated create/edit controls. 79 frontend
  tests total, passing; lint/typecheck/build all clean.

**Known limitations**

- No manual browser UAT was performed for this phase — no browser automation tool was available in
  the implementation environment. Verification relied on the automated backend (SQLite + real
  PostgreSQL) and frontend (React Testing Library simulating real DOM rendering, user interaction,
  and form submission against mocked network calls, plus lint/typecheck/build) suites, together
  with live `curl` smoke testing of the real backend API against the real dev database.
- `transformer_type` is free text, not a reference table — no fixed vocabulary was specified, and
  inventing one was judged out of scope (CLAUDE.md: "Claude must not invent business rules").
- No transition-legality graph is asserted for `Transformer.operational_status_id`, unlike
  `Circuit`'s own dedicated status-change endpoint — `operational_status_id` is a plain field on the
  general `PATCH` endpoint, since no transition rule was specified for transformers.

### Phase 3.5 UAT blocker fix — substation-centric workflow and data model correction

UAT found a critical workflow/data-model gap before acceptance: transformer creation exposed only
HV/LV switchyard pickers with no first-class substation context, so an engineer could not answer
"how many transformers are installed at substation X" or "which transformer belongs to X" without
indirectly inferring it from switchyard labels — and nothing prevented a transformer's HV and LV
switchyards from being selected at two different substations. **Malaysian transmission/distribution
domain rule, stated explicitly during UAT: a transformer is installed within a single substation and
is never modeled as equipment connected between two different substations.** See
[ADR-008](docs/adr/ADR-008-substation-voltage-yard.md)'s "Transformer Registry — UAT Correction"
addendum for the full architecture record.

**Backend.** `Transformer.substation_id` added as a mandatory column (previously substation context
was only reachable indirectly via each terminal's own `SubstationVoltageYard`). Both HV and LV
terminals must now resolve to this same `substation_id` — enforced at the service layer on creation,
checked before the same-switchyard/voltage-order checks so a cross-substation mismatch names the
specific offending side and both substation mnemonics
(`TransformerYardSubstationMismatchError`). Uniqueness moved from
`UNIQUE (hv_switchyard_id, lv_switchyard_id, transformer_number)` (service-layer-only, cross-row) to
**`UNIQUE(substation_id, transformer_number)`, a real single-table database constraint** — simpler
and stronger now that identity no longer spans two child rows. `TransformerSummary`/`TransformerDetail`
now carry `substation_id`/`substation_mnemonic`/`substation_official_name` directly (replacing the
former `hv_substation_mnemonic`/`lv_substation_mnemonic` pair, which is redundant once both terminals
are guaranteed to share one substation). `GET /api/v1/transformers` gained a `substation_id` filter.
Migration `0008_transformer_registry` was edited in place (never committed to version control before
this fix, so no new migration was needed) and re-verified end-to-end against the real dev PostgreSQL
database (drop-and-reapply, schema inspection confirming the new column, FK, and unique constraint).

**Frontend.** `TransformerCreatePage` is now substation-first: the user selects the substation before
either switchyard, and both HV/LV switchyard dropdowns are filtered client-side to that substation's
own switchyards only (mirroring `CircuitCreatePage`'s existing per-voltage-level filtering pattern) —
selecting a different substation clears any already-chosen switchyard. `TransformerListPage` shows a
"Substation" column (replacing the former HV/LV-substation "Switchyards" column) and the existing
free-text search already matches substation mnemonic/name. `TransformerDetailPage`'s heading and a new
"Substation" field show the parent substation explicitly. `SubstationDetailPage` gained a
"Transformers" section (reusing the new `substation_id` filter) so "which transformers are installed
here" is answered directly from a substation's own detail page — the specific UAT-reported
requirement.

**Tests.** Backend: 47 transformer tests total (31 service + 16 API; net +5 over the original 42) —
new coverage for cross-substation rejection on both HV and LV sides, substation-scoped uniqueness
allowing the same transformer number at a different substation, substation-id list/API filtering, and
substation fields present on every create/read response; one now-unreachable "equal voltage level via
two distinct same-substation switchyards" service test removed, since a substation can hold at most
one switchyard per voltage level once both switchyards must share a substation. 238 backend tests
total, passing against both SQLite and real PostgreSQL. Frontend: `TransformerCreatePage` tests
extended to cover substation-first selection, switchyard filtering by substation, and switchyard
reset on substation change; `TransformerListPage`/`TransformerDetailPage` tests updated for the new
substation fields; `SubstationDetailPage` gained 2 new tests for the "Transformers" section. 84
frontend tests total, passing; lint/typecheck/build all clean.

### Phase 3 follow-up — Engineering Connectivity section (Substation Detail page)

UAT clarified an architectural distinction the Transformer Registry work above surfaced but did not
itself resolve: **Transformer Registry answers asset ownership** ("which transformers are installed
at this substation"), while **Circuit Registry answers engineering connectivity** ("which circuits
are connected to this substation"). Unlike `Transformer`, `Circuit` does **not** gain a
`substation_id` column — a circuit legitimately connects two or more substations via its
`CircuitTerminal` rows, so it remains modeled exactly as it already was (§7.4–§7.5). See
`docs/architecture/equipment-registry-module.md`'s new "Engineering Connectivity" note for the full
architecture record, including the explicit distinction from PSS/E's future operational topology
snapshot.

**Backend.** `GET /api/v1/circuits` gained a `substation_id` filter (mirroring the equivalent filter
already added to `GET /api/v1/transformers`) — a circuit matches if any of its `CircuitTerminal` rows'
`SubstationVoltageYard.substation_id` equals the given substation, expressed as a read-only SQL join
across `Circuit`/`CircuitTerminal`/`SubstationVoltageYard` (CLAUDE.md F6 — permitted for query
optimisation/reporting; no data duplicated, no new table). No circular service dependency was
introduced — this stays inside Equipment Registry's own repository, reading `Substation` read-only
exactly as the existing `search` filter already does.

**Frontend.** `SubstationDetailPage` gained an "Engineering Connectivity" section (that exact
heading — not "Live Topology" or "Operational Connectivity", to keep this manually-maintained
engineering baseline visually and terminologically distinct from any future PSS/E-derived
operational snapshot) showing: a connected-circuits count, and a table with circuit name, bay number,
voltage level, line type, operational status, other connected terminal substations (derived from the
existing computed `circuit_name`, which already lists every terminal's substation mnemonic — no new
backend field needed), and a link to each circuit's detail page. Empty state:
"No connected circuits recorded in the engineering registry." Existing substation details, the
Switchyards section, and the Transformers section are unaffected; permission gating for the
edit/status-change forms is unchanged (this new section is read-only for every user, gated on nothing
beyond authentication, mirroring the Switchyards/Transformers sections' own read visibility).

**Tests.** Backend: 3 new service tests (`TestSubstationConnectivityFilter` — a circuit appears for
each of its own terminal substations, an unrelated substation sees nothing, the filter combines with
existing filters) plus 1 new API test (substation-id filter end-to-end, including a third, genuinely
unrelated substation created specifically to prove it sees nothing). 242 backend tests total, passing
against both SQLite and real PostgreSQL — live-verified via `curl` against the real dev database
(PKLG correctly returned its 2 real connected circuits; an unrelated substation returned zero).
Frontend: 2 new `SubstationDetailPage` tests (section renders with connected circuits and the correct
other-substation derivation; empty-state message shown when none exist). 86 frontend tests total,
passing; lint/typecheck/build all clean.

### Phase 3 follow-up — Deletion/Correction Policy

UAT found a practical gap this module's existing no-hard-delete rule (CLAUDE.md §11.6) had not yet
addressed: users could add switchyards, circuit terminals, and transformers by mistake, but had no
way to correct any of them. A new `ENTERED_IN_ERROR` operational status was added once to the shared
Core Platform `operational_status` reference table, distinct from `DECOMMISSIONED`/`RETIRED` (real
end-of-life) in that it represents a data-entry mistake. See
`docs/architecture/equipment-registry-module.md`'s new "Phase 3 Follow-up: Deletion/Correction
Policy" section for the full record, including the Architecture Decision Gate outcomes.

**Architecture Decision Gate.** Four questions were presented with a recommendation each before any
code was written: (1) `TransformerTerminal` correction is disallowed at the individual-terminal
level — a mistaken transformer is corrected only as a whole, since its HV/LV terminals are intrinsic
to what it is (exactly one of each, always); (2) `CircuitTerminal` correction is never blocked, even
when it would leave a circuit with fewer than two active terminals — a circuit may be temporarily
incomplete while under correction, but must satisfy the minimum two-active-terminal rule before it
can (re)enter an `Active` operational state, so the completeness check moved from correction-time to
activation-time; (3) default list views exclude entered-in-error records, revealed only via an
explicit opt-in query parameter; (4) `Circuit` and `Transformer` whole-entity correction reuse their
existing status-change paths — no new endpoint needed.

**Backend.** `SubstationVoltageYard.operational_status_id` and `CircuitTerminal.operational_status_id`
added as new, mandatory columns (previously neither entity had a status at all); `Circuit` and
`Transformer` simply gain a new legal value on their existing `operational_status_id` column;
`TransformerTerminal` deliberately gains no column. New `substation_voltage_yard_audit_log` table
closes a previously-documented gap (switchyard edits were only tracked via `updated_at`/
`updated_by_user_id`). A switchyard cannot be corrected to `ENTERED_IN_ERROR` while a non-entered-in-
error `CircuitTerminal` or `TransformerTerminal` still references it (on a non-entered-in-error
parent), and no new terminal can be created against a switchyard already `ENTERED_IN_ERROR`. New
`include_entered_in_error` query parameter (default `false`) on `GET /circuits`, `GET /transformers`,
`GET /voltage-yards`; detail endpoints remain unfiltered by status. New
`GET /api/v1/voltage-yards/{id}/audit-log` endpoint. Migration `0009_correction_status` — nullable
columns backfilled to `ACTIVE`, then `NOT NULL` + FK + index; new audit table; fully reversible.
Applied to the real dev database; schema and backfill verified via direct SQL (18/18 switchyards,
4/4 circuit terminals correctly backfilled to `ACTIVE`).

**Frontend.** "Mark as Entered in Error" action added to `SubstationDetailPage` (per switchyard) and
`CircuitDetailPage` (per terminal) — never "Delete", since this module has no concept of an
uncommitted draft. `SubstationDetailPage` always fetches switchyards with
`include_entered_in_error: true` (the database's `(substation_id, voltage_level_id)` uniqueness
constraint is not status-aware, so the "Add Switchyard" dropdown must always see corrected yards to
avoid re-offering an already-taken voltage level); a "Show entered-in-error switchyards" checkbox
filters the rendered list client-side only. `CircuitListPage` and `TransformerListPage` gained
equivalent "Show entered-in-error circuits/transformers" toggles wired to the new backend parameter.

**Tests.** Backend: 22 new tests (17 service + 5 API) covering switchyard/terminal correction,
reference-protection rejection, the activation guard, and default-list filtering. 264 backend tests
total, passing against both SQLite and real PostgreSQL. Frontend: 8 new tests across
`SubstationDetailPage`, `CircuitDetailPage`, `CircuitListPage`, and `TransformerListPage`. 94 frontend
tests total, passing; lint/typecheck/build all clean.

**Known limitations**

- `GET /api/v1/voltage-yards/{id}/audit-log` does not 404 on an unknown id — it returns an empty page,
  consistent with the existing behaviour of this module's other audit-log endpoints.
- No transition-legality graph is asserted for correcting a switchyard or circuit terminal to
  `ENTERED_IN_ERROR` beyond the reference-protection check itself — any active-status record may be
  corrected directly, mirroring `Transformer.operational_status_id`'s own unguarded status field.

### Phase 3.5 UAT fix #2 — transformer numbering model (uniqueness + breaker convention)

UAT found that `UNIQUE(substation_id, transformer_number)` (the Phase 3.5 UAT blocker fix above) was
itself too coarse: real Malaysian grid practice numbers transformer bays *per transformation pair*,
not per substation as a whole. A substation legitimately has a "Transformer Bay 1" on its 275/132kV
pair *and a separate* "Transformer Bay 1" on its 132/33kV pair — the substation-only constraint
wrongly rejected the second one. UAT separately found the breaker-number suggestion formulas
insufficient: they were keyed on voltage alone, but the correct formula depends on the transformation
pair and terminal side (e.g. 132kV needs `{N}10` as an HV side but `{N}80` as an LV side). See
[ADR-008](docs/adr/ADR-008-substation-voltage-yard.md)'s "UAT Correction #2 (Numbering Model)"
addendum for the full architecture record.

**Backend.** Uniqueness reverts to `(substation_id, hv_switchyard_id, lv_switchyard_id,
transformer_number)`, enforced at the service layer via an aliased double join on
`TransformerTerminal` (mirroring the module's original, pre-Phase-3.5-UAT-fix design) — not as a raw
database constraint, since denormalizing both switchyard ids onto `Transformer` to regain a
single-table constraint was considered and rejected (it would reintroduce the exact two-winding-only
assumption Decision 1 deliberately avoided baking into `Transformer`'s own column set, undermining
future tertiary-winding compatibility). Migration `0010_transformer_yard_pair` drops the now-incorrect
`uq_transformer_substation_number` constraint; no replacement single-table constraint is added.
`update_transformer` previously performed **no uniqueness check at all** when `transformer_number`
changed — a pre-existing gap, closed as part of this fix, since the exact same repository lookup now
backs both `create_transformer` and `update_transformer`. `DuplicateTransformerError`'s message was
reworded to name the HV/LV pair, not just the substation.

**Frontend.** `transformerBreakerSuggestion.ts` rewritten from a per-voltage table to a mapping keyed
by (HV nominal kV, LV nominal kV, side), covering the five transformation pairs the convention
specifies (500/275, 275/132, 132/33, 132/22, 132/11kV) — any other pair (e.g. one involving 230kV) has
no suggestion, an intentional scope limit. `TransformerCreatePage` now waits for both HV and LV
switchyards to be selected before suggesting either breaker number, since the formula genuinely
depends on the pair, not either voltage alone — a direct, accepted UX consequence of the corrected
model, not a regression.

**Tests.** Backend: 6 new tests (4 service + 2 API) covering same-number-different-pair allowance
(create and update), same-pair-same-number rejection (unchanged behaviour, re-verified against the new
implementation), and the previously-untested `update_transformer` uniqueness path. 271 backend tests
total (36 in `test_transformer_service.py`, 18 in `test_transformer_registry_api.py`), passing against
both SQLite and real PostgreSQL. Frontend: `transformerBreakerSuggestion.test.ts` rewritten (15 tests
covering all five transformation pairs, both sides, and the out-of-scope-pair/non-numeric-input null
cases); 2 `TransformerCreatePage` tests updated for the corrected LV-side formula and the
both-switchyards-required suggestion timing. 100 frontend tests total, passing; lint/typecheck/build
all clean.

### Transformer breaker-numbering convention moved to reference data

The (HV nominal kV, LV nominal kV, side)-keyed breaker-suggestion mapping introduced by the numbering-
model fix above was itself hardcoded in a frontend TypeScript file. Moved into a new Core Platform
reference table so the convention is auditable, seedable, and maintainable (a new transformation pair,
or a corrected pattern, is now a data change, not a frontend code change) without changing what the
convention actually says or its suggestion-only, never-backend-enforced nature.

**Backend.** New reference table `transformer_breaker_numbering_convention`
(`app/reference_data/models.py`) — `convention_id` (surrogate PK), `hv_voltage_level_id`/
`lv_voltage_level_id` (real FKs to `voltage_level`, not raw nominal-kV numbers), `side` (`CHECK IN
('HV','LV')`), `pattern` (nullable — `NULL` means no automatic suggestion), `is_standard`, `notes`.
`UNIQUE (hv_voltage_level_id, lv_voltage_level_id, side)`. No `created_at`/`updated_at` — consistent
with every other reference table in this module (`VoltageLevel`, `Region`, `State`, `GridOwner`,
`OperationalStatus`, `LineType`), none of which have them. Migration `0011_breaker_convention` creates
the table (no data — seeding is a separate step, per this project's established convention). Seeded
idempotently by `app/reference_data/seed.py`'s `run_seed`, with the exact ten rows (five transformation
pairs × two sides) matching the corrected convention exactly — safe to re-run, and backfills correctly
into a database seeded before this table existed (mirroring `line_type`'s own established backfill
guarantee). One real bug found and fixed along the way: this project's `SessionLocal` is configured
`autoflush=False` (`app/db/session.py`), so `run_seed` needed an explicit `db.flush()` after seeding
`voltage_level` and before seeding this new table, since it is the first seed function to depend on
another table's rows being visible within the same call — every prior seed function only ever queried
its own table. Exposed read-only via the existing reference-data router:
`GET /api/v1/reference-data/transformer-breaker-numbering-conventions` (authentication required, no
additional permission gate, matching every other reference-data endpoint). No write endpoint —
reference data is managed exclusively via the seed script, never through the API.

**Frontend.** `transformerBreakerSuggestion.ts` rewritten: the hardcoded pair/side lookup table is
gone, replaced by a pure function that takes the fetched convention list as a parameter and looks up
the matching row by `(hv_voltage_level_id, lv_voltage_level_id, side)`, applying `pattern`'s `{N}`
placeholder substitution. `TransformerCreatePage` now fetches the convention list via its own query and
gates suggestion display on four conditions: the transformer number, both switchyards' voltage levels,
and the convention list itself being loaded — a suggestion cannot appear until all four are ready. A
missing convention row, or a row with `pattern = null`, both correctly produce no suggestion, leaving
the breaker-number field free for manual entry — never a rejected or blocked input.

**Tests.** Backend: 3 new reference-data seed tests (exact seeded pattern/`is_standard` values matched
against the documented convention table; a dedicated backfill-into-a-partially-seeded-database test for
this table, mirroring `line_type`'s own) plus 2 new API tests (authentication required; every seeded
row returned, with the non-standard/null-pattern row distinguishable from a real pattern). 282 backend
tests total, passing against both SQLite and real PostgreSQL. Frontend: `transformerBreakerSuggestion.test.ts`
rewritten again for the new convention-array-based signature (16 tests, same coverage as before plus an
explicit "empty convention list" case); 1 new `TransformerCreatePage` test for the no-matching-convention/
manual-entry path. 102 frontend tests total, passing; lint/typecheck/build all clean.

### Phase 3.5 UAT fix #3 — ENTERED_IN_ERROR transformers permanently reserved their identity

UAT found that a transformer corrected to `ENTERED_IN_ERROR` still permanently occupied its
`(substation, HV switchyard, LV switchyard, transformer_number)` identity: creating "PKLG, 275kV HV,
132kV LV, Transformer 1" was rejected as a duplicate even though the only visible PKLG transformers
were both on the 132/11kV pair. The corrected record — hidden from every default view per the
deletion/correction policy — was still counted as "existing" by the uniqueness check, since
`find_transformer_by_yard_pair_and_number` never filtered on `operational_status_id`.

**Investigation (performed before any code change, at the user's explicit request).** Reconstructed
the exact submitted payload and queried `transformer`/`transformer_terminal` directly, confirming a
third PKLG transformer existed beyond the two visible ones: a stray `ENTERED_IN_ERROR` row from an
earlier live smoke test, sitting on exactly the 275kV/132kV pair with `transformer_number = "1"`. The
join/comparison logic in `find_transformer_by_yard_pair_and_number` was verified correct — real
switchyard ids, both terminals, no incorrect join — the sole gap was the missing status exclusion.
Frontend payload construction was also verified correct (switchyard ids submitted verbatim from the
selected options, no transformation).

**Backend.** `find_transformer_by_yard_pair_and_number` now excludes `ENTERED_IN_ERROR` transformers
(`Transformer.operational_status_id != _entered_in_error_status_id_subquery()`), mirroring the same
exclusion already used for switchyard reference-protection and default list filtering elsewhere in this
module. Applies automatically to both `create_transformer` and `update_transformer`, since both call
this same repository method. The corrected transformer row itself is never deleted or altered by this
fix — only excluded from this one uniqueness check — so it remains reachable by id and fully
audit-visible, consistent with CLAUDE.md §11.6 (no hard delete) and the deletion/correction policy's own
"hidden from default views, not from audit/history" principle.

**Tests.** Backend: 4 new service tests (`TestTransformerUniquenessExcludesEnteredInError` —
an `ENTERED_IN_ERROR` transformer no longer blocks recreating the same identity; an `ACTIVE`
transformer still correctly blocks a genuine duplicate; the same exclusion applies to
`update_transformer`) plus 1 new API test reproducing the full correction-then-recreation flow over
HTTP end-to-end, including confirming the corrected record remains reachable by `GET` afterward. 286
backend tests total, passing against both SQLite and real PostgreSQL. No frontend changes were
required — the bug was entirely in the backend uniqueness query. Live-verified via `curl` against the
real dev database: the exact reported scenario (PKLG, 275kV HV, 132kV LV, Transformer 1) now succeeds;
a subsequent genuine duplicate against the new record is still correctly rejected; the original stray
`ENTERED_IN_ERROR` artifact and this fix's own smoke-test transformer both remain reachable by id,
neither hard-deleted.

**Dev database cleanup.** The stray smoke-test artifact from an earlier session (`300aac73-...`,
PKLG, 275/132kV, "1") was left exactly as found — already correctly marked `ENTERED_IN_ERROR`, which is
itself the "neutralized" state this policy defines; hard-deleting it via raw SQL was deliberately not
done, since it would bypass this module's own audit/correction mechanism and CLAUDE.md §11.6 prohibits
hard delete on engineering entities regardless of whether a UI path exists for it. This fix's own new
smoke-test transformer was corrected to `ENTERED_IN_ERROR` the same way, for consistency.

---

## Phase 3 — Equipment Registry (Circuit / CircuitTerminal Management)

**Scope:** Circuit and CircuitTerminal identity —
[`docs/architecture/equipment-registry-module.md`](docs/architecture/equipment-registry-module.md),
incorporating [ADR-006](docs/adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md)
and [ADR-007](docs/adr/ADR-007-canonical-engineering-reference-object.md). This phase implements
Circuit & CircuitTerminal management specifically — not the full Equipment Registry module (load
transformers, auto-transformers, and relays remain unimplemented; see "Known limitations" below).

**Backend**

- `Circuit` (bay number, voltage level, line type, interconnector flag, operational status,
  remarks) and `CircuitTerminal` (one row per substation terminal — breaker number,
  commissioning date, remarks) as new persistence models, with `Circuit.bay_number` and
  `CircuitTerminal.breaker_number` deliberately separated per ADR-007's corrected field
  placement.
- A circuit is created with two or more terminals atomically; `CircuitTerminal` may be added
  later to extend a two-terminal circuit into a tee-off, using the same entity shape.
- `line_type` added as a new Core Platform reference table (Overhead Line / Cable / Submarine /
  Hybrid), following the exact `voltage_level` pattern.
- Full Router → Service → Repository → Models layering; `equipment_registry_audit_log` records
  every circuit-level field change and every terminal addition.
- `equipment_registry.read`/`equipment_registry.write` permissions registered and granted to the
  baseline Administrator/Engineer/Viewer roles, mirroring Substation Registry's own bootstrap.
- Migration `0004_equipment_registry_circuits` — hand-written, manually reviewed, and verified
  directly against real PostgreSQL (schema inspection, FK/unique-constraint verification,
  downgrade/upgrade reversibility).

**Frontend**

- `/circuits`, `/circuits/new`, `/circuits/:circuitId` — list (search/filter/paginate), create
  (dynamic terminal rows, minimum two, addable for tee-offs), and detail (edit, status change,
  add-terminal, audit log) pages, following Substation Registry's existing page/API-client
  conventions exactly.

**Tests**

- Backend: 27 new tests (service + bootstrap + API) covering two-terminal creation, tee-off/
  N-terminal creation, bay_number-vs-breaker_number field placement, validation failures
  (insufficient terminals, duplicate terminal substation, unknown substation, invalid reference
  data, invalid initial status), and search/filter/pagination — run against both SQLite and real
  PostgreSQL.
- Frontend: 10 new tests (list, create, detail pages) covering reference-data label resolution,
  the two-terminal minimum, tee-off extension, permission-gated write UI, and full-form
  submission.

**Known limitations**

- This phase does not implement the full Equipment Registry module — `LoadTransformerDetail`,
  `AutoTransformerDetail`, `RelayDetail`, `RelayControlledEquipment`, and the shared `Equipment`
  identity backbone those types would sit on (equipment-registry-module.md §7.1, §7.5, §7.8) are
  out of scope and unimplemented. `CircuitTerminal` carries its own identity directly rather than
  attaching to that backbone; see this phase's implementation report for the full reasoning.
- `EquipmentTopologyMap` (PSS/E correlation) and the scheme-module `circuit_id` migration
  (equipment-registry-module.md §7.10, §7.11) remain unimplemented, as documented — both were
  already sequenced to later phases before this implementation began.
- No manual browser UAT was performed for this phase; verification relied on the automated
  backend (SQLite + PostgreSQL) and frontend (lint/typecheck/test/build) suites.

### Phase 3 UAT follow-up — New Circuit button/empty-state fix, and a deployment gap found

**UAT defect 1 — missing create affordance.** `/circuits` had no visible way to create a circuit
and no helpful empty state when the database was empty. Fixed in `CircuitListPage.tsx`: a
prominent, permission-gated "New Circuit" button next to the page heading, and a genuine empty
state ("No circuits have been registered yet." + "Register your first circuit") shown only when
the circuit list is truly empty and no search/filter is active — distinct from the
filtered-empty-results case. 3 new frontend tests (navigation on click, empty state with/without
write permission); 2 existing tests updated for the renamed control.

**UAT defect 2 — the fix above didn't fix it; root cause was a missing deployment step, not
frontend code.** After the button/empty-state fix, the Administrator account still could not see
the write-gated controls. Root cause, confirmed by querying the live dev database directly:
`equipment_registry.read`/`equipment_registry.write` were never registered in `permission`, and
never granted to any role, because **no part of the application (no `main.py` startup hook, no
lazy bootstrap on login) ever invokes any module's `bootstrap.py` automatically** — every
module's permission catalog is registered only by manually running
`python -m app.modules.<name>.bootstrap` against the target database, a step that was previously
undocumented outside the automated test suite's own disposable-database fixtures. The frontend
was behaving correctly throughout, faithfully reflecting an incomplete backend deployment state.
Fixed by running `python -m app.modules.equipment_registry.bootstrap` against the dev database
(verified end-to-end via a live login + `GET /users/{id}/roles` call showing
`equipment_registry.write` now present for Administrator) and documenting the full required
seed/bootstrap sequence in README.md's new "Seeding and Bootstrapping" section, so this does not
recur for the next module or the next fresh environment.

**UAT defect 3 — same shape of bug again, in reference data this time.** The Line Type dropdown
on Create Circuit was empty. Investigation, in order: (1) `line_type` table exists on the dev
database — the Phase 3 migration ran correctly; (2) it had zero rows; (3) the other five
reference tables (`voltage_level`, `region`, `state`, `grid_owner`, `operational_status`) all held
their full, correct row counts, proving `python -m app.reference_data.seed` *had* been run at some
point — just before Phase 3 added `line_type` to it, and never re-run since; (4)/(5)/(6) the
backend endpoint, frontend API client, `useReferenceData` hook, and `CircuitCreatePage` were all
verified correct by inspection and by a live authenticated call to
`GET /api/v1/reference-data/line-types` — no code defect anywhere in that chain. Fixed by
re-running `python -m app.reference_data.seed` against the dev database (idempotent — it left the
other five tables untouched and inserted exactly the four missing `line_type` rows), confirmed via
direct SQL query and the same live API call afterward. No test or code change was needed — the
seed logic itself already had full, passing coverage (`app/reference_data/tests/test_seed.py`);
the gap was operational (a persistent database not re-synchronized after a code change), and is
now covered by the re-run guidance added to README.md's "Seeding and Bootstrapping" section.

### Phase 3 UAT fix package — commissioning date entry, full circuit edit, multi-voltage substations

Three must-fix items found during Phase 3 UAT before Phase 4 (PSS/E topology import) could begin,
implemented as one scoped fix package. See
[ADR-008](docs/adr/ADR-008-substation-voltage-yard.md) for the architecture decision.

**1. Commissioning date entry.** `CircuitTerminal.commissioning_date` was shown on the detail page
but had no input anywhere. Added to both `CircuitCreatePage`'s terminal rows and as an editable
field on the detail page (see item 2).

**2. Full circuit edit.** Circuit edit previously covered only `bay_number` and status; `line_type`
and `voltage_level` were already editable in the backend service (`update_circuit`) but not exposed
in the frontend form — added. Per-terminal `breaker_number`/`commissioning_date`/`remarks` editing
required a genuinely new backend capability (`EquipmentRegistryService.update_terminal`,
`PATCH /circuits/{id}/terminals/{terminal_id}`) — added, with its own audit trail
(`terminal_breaker_number`/`terminal_commissioning_date`/`terminal_remarks` fields). No DELETE
functionality was added, per the task's explicit constraint.

**3. Multi-voltage substation modeling.** The root cause the other two items were blocked behind:
`CircuitTerminal` referenced `Substation` directly, which cannot express which of a multi-voltage
substation's voltage levels (e.g. PKLG's own 275kV yard vs. its own 132kV yard) a circuit actually
terminates at. Added `SubstationVoltageYard` (owned by Equipment Registry, referencing Substation
Registry and Core Platform reference data only — no substation attributes duplicated) and changed
`CircuitTerminal.substation_id` to `CircuitTerminal.voltage_yard_id`. Business rule 6 (no duplicate
terminal on the same circuit) is now scoped to voltage yards, not substations — a circuit may
legitimately terminate twice at the same multi-voltage substation, once per voltage yard.

**Migration** (`0005_substation_voltage_yard`): creates `substation_voltage_yard`; backfills one
default yard per existing substation from that substation's own `voltage_level_id` (real, `NOT
NULL` on every existing row — the "no reliable voltage_level" fallback was not needed); repoints
every existing `circuit_terminal` row at its substation's new default yard; drops the old
`substation_id` column only after the new column is fully populated. Adds
`circuit_terminal.updated_at`/`updated_by_user_id` (backfilled from `created_at`/
`created_by_user_id`) to support terminal editability. Verified directly against the real,
persistent dev database (5 pre-existing substations → 5 yards; 4 pre-existing terminals correctly
repointed, confirmed by joining back to substation mnemonic and voltage level) — full
`upgrade → downgrade → upgrade` cycle run and re-verified against that same real data, not only in
the abstract. Downgrade restores `substation_id` by joining back through
`substation_voltage_yard`.

**New endpoints:** `GET/POST /api/v1/voltage-yards` (list, filterable by `substation_id`; create,
`equipment_registry.write`-gated); `PATCH /api/v1/circuits/{id}/terminals/{terminal_id}` (update).
`SubstationDetailPage` gained a "Voltage yards" section (list + add-yard form) — gated on
`equipment_registry.write`, not `substation_registry.write`, since voltage yards are owned by
Equipment Registry (ADR-008).

**Tests:** 46 new/updated backend tests (service + API), including a dedicated multi-voltage-
substation test class (`TestMultiVoltageSubstations`) proving a circuit may terminate twice at the
same substation across two different voltage yards; 168 backend tests total, passing against both
SQLite and real PostgreSQL. 12 new/updated frontend tests across `CircuitCreatePage`,
`CircuitDetailPage`, and `SubstationDetailPage`.

**Known limitation:** the voltage yard a terminal connects to is not editable after creation in
this fix package — only `breaker_number`/`commissioning_date`/`remarks`. Re-pointing a terminal to
a different yard was judged a materially different, out-of-scope operation.

### Phase 3 UAT validation fix — add-voltage-yard workflow was unusable, not just undiscoverable

UAT reported being unable to add a voltage yard from the Substation Detail page, despite the
button/form (added above) being present and permission-gated correctly. Root cause: the "New
voltage yard voltage level" dropdown offered *every* voltage level, including ones the substation
already had a yard at (most substations have exactly one, from the `0005` migration's backfill).
Picking one — the natural first attempt, since nothing distinguished available from taken — always
failed with `DuplicateVoltageYardError`, whose message embedded a raw internal `voltage_level_id`
("voltage level '4'") instead of a human-readable label, making a correctly-rejected duplicate look
like an unexplained, generic failure. The automated test written for this workflow in the previous
fix package coincidentally selected the one already-used voltage level in its own mock data and
still "passed," because the mock POST handler didn't enforce the real duplicate constraint the way
the actual backend does — masking the exact defect a real user hit.

**Fix:** (1) `DuplicateVoltageYardError` now takes the substation's mnemonic and the voltage
level's label, not raw ids — e.g. `"Substation 'PKLG' already has a voltage yard at '132kV'"`. (2)
Both add-voltage-yard forms (`SubstationDetailPage`, and `CircuitDetailPage`'s "Need a different
voltage yard?" mini-form) now filter the voltage-level dropdown to exclude levels already used by
the selected substation, and show a clear message ("already has a voltage yard at every known
voltage level") instead of an empty-looking form when none remain. Verified live against the real
dev database: reproduced the exact failing scenario, confirmed the new message, then confirmed a
valid creation succeeds and immediately appears in the global voltage-yard list Circuit Create/Edit
terminal selection reads from.

**Tests:** 1 new backend test assertion (human-readable duplicate message, both service- and
API-level); 5 new frontend tests — dropdown correctly excludes an already-used voltage level on
both forms, all-levels-exhausted empty state, and a newly-created yard becoming selectable in the
add-terminal dropdown without a page reload.

### Phase 3 UAT follow-up — `Substation.voltage_level_id` deprecated (ADR-009)

UAT found that `SubstationVoltageYard` (ADR-008) and `Substation.voltage_level_id` had become two
competing representations of the same fact. Substation Create still required a single voltage
level; List/Detail still displayed it as if authoritative even after a substation could hold
several voltage yards; and it was independently editable via `PATCH /substations/{id}` with no
relationship to the yards table at all, so the two could silently diverge.

**Fix (ADR-009):** `Substation.voltage_level_id` is deprecated, not dropped — the database column
stays (nullable, FK intact, no existing row's value touched) but is removed entirely from the API
contract (`SubstationCreate`/`Update`/`Summary`/`Detail`) and from both frontend forms. Substation
Create no longer asks for a voltage level; a new substation legitimately has zero voltage yards
until one is added via the existing `POST /voltage-yards` workflow. `SubstationVoltageYard` is now
the sole authoritative representation of a substation's voltage level(s), for both List and Detail.
The Substation List page composes this client-side (fetching Equipment Registry's
`GET /api/v1/voltage-yards` and grouping by `substation_id`), the same pattern `CircuitDetailPage`
already used — Substation Registry (Master Data) must never depend on Equipment Registry (Network
Data), so this is never a backend join (CLAUDE.md A2/F2). A substation with multiple voltage yards
now renders as e.g. "PKLG: 275kV, 230kV, 132kV, 500kV" instead of a single, potentially-stale value.

**Migration:** `0006_deprecate_substation_vlevel` — a single `ALTER COLUMN ... DROP NOT NULL`, no
data backfill (every existing row keeps its original value; only new rows are expected to be NULL
going forward). Verified against the real dev database: column confirmed nullable, all 7 existing
substations' legacy values confirmed untouched, and a substation created through the live API with
no `voltage_level_id` in the payload succeeded with the column landing `NULL` in PostgreSQL.

**Removed:** the Substation List "filter by voltage level" query parameter — nothing in this
project depended on it, and it would have silently given increasingly incomplete answers once new
substations stop populating the legacy column. Rebuilding it against voltage yards is deferred
to a later, separately-scoped piece of work if needed.

**Tests:** backend — `create_substation`'s signature no longer accepts `voltage_level_id`
(regression test), reference-data validation coverage moved to `region_id`; frontend — 4 new tests
(`SubstationCreatePage` no longer offers a voltage level field; `SubstationListPage` renders a
substation's voltage yards, including the multi-yard join case; `SubstationDetailPage` no longer
shows a standalone "Voltage level" field). 169 backend tests / 51 frontend tests passing.

### Phase 3 UAT follow-up — inline voltage yard creation removed from Circuit Detail (ADR-009 addendum)

UAT flagged that `CircuitDetailPage`'s "Need a different voltage yard?" section let a Circuit page
create `SubstationVoltageYard` rows directly — master topology data owned by the Substation
Registry workflow (per this ADR's main decision), created from a downstream, consuming module. The
ownership hierarchy is Substation → Voltage Yard → Circuit → Protection Scheme; a circuit should
consume voltage yards, not create them, and allowing it set a bad precedent for every future
topology entity (busbars, bus couplers, transformers, disconnectors, reactors, capacitors, PSS/E
import).

**Fix:** the entire "Need a different voltage yard?" section — substation select, voltage level
select, "Add voltage yard" button, and the supporting query/mutation logic
(`substationsQuery`, `addVoltageYardMutation`, `invalidateVoltageYards`) — is removed from
`CircuitDetailPage`. Voltage yard creation remains exclusively on the Substation Detail page. When
the "Add terminal" dropdown has no available voltage yard to offer, the page now shows static
guidance ("No suitable voltage yard exists for this circuit. Please add the required voltage yard
from the Substation Registry.") instead of a creation shortcut — helper text, not a navigation
link, per the explicit requirement that this stay a hard boundary.

**Architecture:** recorded as an addendum to ADR-009 (additive, not a rewrite of its existing
decision) generalizing the principle: *master data entities are created and managed only within
their owning module; dependent modules may reference them but must not create or modify them
inline without a compelling, separately-documented exception.* This applies to every future
topology entity, not only voltage yards.

**Tests:** 2 obsolete tests removed (mini-form dropdown filtering, newly-created-yard-becomes-
selectable — both exercised the now-removed inline creation path); 2 new tests added (confirms no
inline creation controls render at all; confirms the guidance text renders, and no "Add voltage
yard" button, when no voltage yard is available). Net test count unchanged (8 in this file, 51
frontend total). Backend untouched — `POST /api/v1/voltage-yards` still exists, still exclusively
reachable from the Substation Detail page's own workflow.

### Phase 3 close-out — terminal voltage-level guardrail and voltage yard metadata

Two final UAT-driven refinements before closing Phase 3.

**1. Terminal voltage-level guardrail (equipment-registry-module.md §9 rule 6a).** UAT found the
Add Terminal dropdown (Circuit Create and Circuit Detail) could offer a voltage yard at a
different voltage level than the circuit itself. A `Circuit` represents one physical transmission
line at one voltage class; enforced at the service layer on both `create_circuit` and
`add_terminal`, not only the frontend — a mismatched voltage yard submitted directly to the API
now returns a clear `TerminalVoltageLevelMismatchError`
(e.g. `"Voltage yard 'SIDST — 132kV' does not match this circuit's voltage level '500kV'"`).
`CircuitCreatePage` and `CircuitDetailPage` both filter their voltage-yard dropdowns to the
selected/current circuit voltage level.

**Architecture note:** this rule interacts with ADR-008's own rule-6 illustration (a circuit
terminating twice at the same multi-voltage substation, across two different voltage levels) —
combined with the existing one-yard-per-substation-per-level constraint, a single circuit can no
longer terminate twice at the same substation at all under the current model (no `Transformer`
equipment type exists yet to represent a same-site, cross-voltage connection). Recorded as an
addendum to ADR-008, not a rewrite; the conflicting test was replaced with an equivalent one using
two different substations at the same non-default voltage level.

**2. `SubstationVoltageYard` metadata — `commissioning_date`, `latitude`, `longitude`.** All
optional, and deliberately on the voltage yard, not the parent `Substation`: a multi-voltage site
may have yards commissioned at different dates with slightly different GIS coordinates. Migration
`0007_voltage_yard_metadata` adds the three nullable columns plus the same range/pair CHECK
constraints already established for `Substation`'s own geolocation fields, and
`updated_at`/`updated_by_user_id` for edit accountability (mirroring `CircuitTerminal`'s own
precedent). No data backfill — every existing row remains valid with `NULL` metadata. New
`PATCH /api/v1/voltage-yards/{id}` endpoint supports partial updates (Ellipsis-sentinel pattern,
consistent with every other partial-update endpoint in this codebase). `SubstationDetailPage`'s
voltage yard list now displays and lets an authorized user edit each yard's metadata inline; the
add-voltage-yard form accepts all three fields optionally.

**Known limitation:** voltage yard metadata edits are tracked via `updated_at`/`updated_by_user_id`
only, not a field-level audit log (unlike `Substation`/`Circuit`'s own attribute changes) — judged
proportionate for this incremental addition; a full `substation_voltage_yard_audit_log` can be
added later analogous to the existing audit log pattern if required.

**Tests:** backend — 4 new service tests + 2 new API tests for the terminal-voltage-level
guardrail (create-circuit rejection, add-terminal rejection, human-readable message, valid
non-default-level circuit still succeeds); 8 new service tests + 5 new API tests for voltage yard
metadata (create/update/partial-update/clear/geo-pair validation/range validation/not-found).
1 pre-existing backend test rewritten (its cross-voltage-level scenario is no longer constructible
under rule 6a). Frontend — 2 new tests on `CircuitCreatePage` (no yard offered before a voltage
level is chosen; dropdown filtered per selected level) replacing 1 obsolete test, 1 new test on
`CircuitDetailPage` (excludes a mismatched-level yard), 4 new tests on `SubstationDetailPage`
(metadata submitted on create, metadata displayed and editable, read-only without
`equipment_registry.write`). 190 backend tests / 56 frontend tests passing (SQLite, real
PostgreSQL, and lint/typecheck/build all clean).

### Phase 3 freeze package — bay number semantics, canonical circuit naming, Switchyard terminology

Five final UAT/architecture cleanup items before freezing Phase 3.

**1. Bay number semantics.** Users were unsure whether to enter "1" or "Line 1" for `bay_number`.
Decision: it is a bay/circuit *designator* only ("1", "2", "Main", "Transfer"), never a route
description. UI placeholders/labels updated (`CircuitCreatePage`/`CircuitDetailPage`/
`CircuitListPage`); deliberately **no** numeric-only validation added, since real bay designators
are frequently non-numeric.

**2 & 3. Duplicate circuit-number display and canonical circuit naming.** Investigation confirmed
`circuit_name` is fully computed, never stored (`EquipmentRegistryService._compute_circuit_name`)
— so both defects were fixable with zero migration. Root causes: (a) the computed name embedded
`bay_number` (e.g. `"PKLG–IGBK Line 1"`), which duplicated visually against a separately-displayed
`bay_number` field; (b) terminal mnemonics were joined in terminal-insertion order, so the same
physical circuit could display as `"PKLG–IGBK"` or `"IGBK–PKLG"` depending on which terminal was
entered first. Fix: `_compute_circuit_name` now takes only the terminal mnemonics, sorted
alphabetically (case-insensitive), and never appends `bay_number`. `CircuitDetailPage` now shows
"Circuit: {name}" and a separately-labeled "Bay / Circuit No." field, never combined.

**Architecture conflict found and resolved:** the new canonical-naming rule interacts with rule 6a
(the terminal voltage-level guardrail added in the prior fix package) in a way that makes ADR-008's
own rule-6 illustration (a circuit terminating twice at the same multi-voltage substation, across
two voltage levels) no longer constructible — combined with the one-yard-per-substation-per-level
constraint, a single circuit can no longer terminate twice at the *same* substation at all under
the current model (no `Transformer` equipment type exists yet). Recorded as a new business rule 6a
in `equipment-registry-module.md` §9 and an ADR-008 addendum; the one pre-existing test relying on
the old scenario was replaced with an equivalent one using two different substations.

**4. "Voltage Yard" vs "Switchyard" terminology.** Recommendation: keep internal model/table/
column/API names unchanged (`SubstationVoltageYard`, `substation_voltage_yard`, `voltage_yard_id`,
`/api/v1/voltage-yards`); adopt **"Switchyard"** as the user-facing term in UI labels, buttons, and
user-facing error messages (`VoltageYardNotFoundError`, `DuplicateVoltageYardError`,
`TerminalVoltageLevelMismatchError` message text updated); architecture docs use "Voltage Yard /
Switchyard" to bridge existing terminology. A full rename (table + FKs + every reference across two
modules and three ADRs) was judged disproportionate churn for a naming-only change. Recorded as an
ADR-008 addendum.

**5. Architecture document finalized.** `equipment-registry-module.md` gained a new "Phase 3 Final
Model Summary" section (conceptual hierarchy diagram, terminal voltage-level guardrail, ADR-009's
master-data ownership principle, `Substation.voltage_level_id` deprecation summary, canonical
naming rule, `bay_number` semantics, explicit note that transformers/busbars/bays remain future
scope) plus corrected §7.4/§7.6 definitions, an updated Glossary, and three new Appendix entries.

**Migration impact:** none — every change in this package is code/UI/documentation only.

**Tests:** backend — 2 rewritten (naming format), 1 new (deterministic ordering regardless of
terminal entry order); frontend — 1 rewritten test replaced with 2 (`CircuitCreatePage`), 1 new
regression test (`CircuitListPage`, proving the route name and bay number never duplicate), test
label/text updates across `CircuitCreatePage`/`CircuitDetailPage`/`SubstationDetailPage`/
`CircuitListPage` for the Switchyard terminology and new naming format. 191 backend tests / 57
frontend tests passing (SQLite, real PostgreSQL, and lint/typecheck/build all clean).

---

## Phase 2 — Substation Registry

**Scope:** The platform's master data anchor —
[`docs/architecture/substation-registry.md`](docs/architecture/substation-registry.md).

**Backend**

- `Substation`, `SubstationAlias`, `SubstationAuditLog` — model, repository,
  service, router, wired to Phase 1's IAM (`getUser`/`hasPermission`,
  `require_permission("substation_registry.write")`) for accountability and
  authorization.
- A shared, read-only Core Platform reference-data API
  (`app/reference_data/router.py`) — not owned by Substation Registry, added
  as a necessary prerequisite for populating create/edit form dropdowns,
  reusable by every future module.
- `substation_registry.read`/`substation_registry.write` permission codes
  registered in IAM's catalog and granted to the baseline
  Administrator/Engineer/Viewer roles.
- Alembic migration `0003_substation_registry`.

**Frontend**

- Substation list (TanStack Table, with region/status filtering and search),
  detail/edit view, create form, and status-change control, under
  `frontend/src/modules/substation_registry/`.

**Tests:** 45 backend service/bootstrap tests + 9 API contract tests + 8
frontend tests, covering mnemonic uniqueness (case-insensitive, incl.
historical-alias reuse), `substation_id` immutability, alias creation on
mnemonic change, geolocation pair validation, and soft-delete-only
enforcement.

**Architectural issue flagged, not resolved at the time:** substation-registry.md
§10's lifecycle diagram omitted the `UNDER_CONSTRUCTION` status entirely and
showed no direct `Active → Decommissioned` edge. Resolved conservatively for
this phase (closed allow-list of only the drawn edges) and explicitly
flagged for follow-up — see below.

### Phase 2 follow-up — lifecycle resolution and PostgreSQL verification

**Operational status lifecycle resolved via [ADR-005](docs/adr/ADR-005-substation-operational-status-lifecycle.md).**
substation-registry.md §10 revised to a seven-edge closed transition graph
restoring `Under Construction` to active use
(`Planned → Under Construction → Active`) and adding a direct
`Active → Decommissioned` edge (mothballing is not a mandatory
precondition of decommissioning). `Planned → Active` directly is no longer
legal — a behavioural change from this phase's original interim
implementation. Backend allow-list and 20 status-transition tests updated;
no frontend changes were needed (the UI never replicated the transition
graph client-side, by design — CLAUDE.md A12).

**PostgreSQL environment established as a permanent part of local
development** — dedicated `engineering_platform` database and
least-privileged `engineering_app` role (never the default `postgres`
database/superuser), documented in full in
[`docs/development/postgresql-setup.md`](docs/development/postgresql-setup.md).
A real, pre-existing configuration bug was found and fixed in the process:
`backend/app/core/config.py`'s `env_file=".env"` was a relative path,
resolved against the process's current working directory — meaning the
documented root `.env` was never actually read during local (non-Docker)
backend runs (`cd backend && uvicorn ...`/`pytest`), only during Docker
Compose (which injects real environment variables directly, bypassing the
file entirely). Fixed by resolving `.env` via an absolute path computed from
`config.py`'s own location.

**Full verification against real PostgreSQL 18** (migrations 0001–0003,
schema inspection, full pytest suite, `downgrade -1`/`upgrade head`
reversibility) — see `docs/development/postgresql-setup.md` §9 for the
opt-in `GRIDDEFENCE_TEST_DATABASE_URL` mechanism added to
`backend/conftest.py` to make this repeatable. Found and fixed one genuine
PostgreSQL-only defect: `voltage_level_id=99999` (and equivalent
out-of-range reference-data ids) is silently accepted by SQLite's flexible
integer typing but raises an unhandled `psycopg.errors.NumericValueOutOfRange`
on PostgreSQL's real `SMALLINT` columns — would have surfaced as a raw 500
error in production, never caught by SQLite-only testing. Fixed in
`app/reference_data/repository.py` by treating any id outside `SMALLINT`'s
representable range as "not found" before it reaches the database.

### Phase 2 UAT — ACCEPTED

Manually verified end-to-end through `localhost` against the real
PostgreSQL `engineering_platform` database (not SQLite) — see
`docs/development/postgresql-setup.md` for how that environment is set up.
Tested:

- Backend starts successfully.
- Frontend starts successfully.
- Login with the bootstrap Administrator account works.
- Substations page is accessible.
- Create substation works.
- Editing a substation's official name and mnemonic works.
- The created row is visible directly in the PostgreSQL table.
- Duplicate-mnemonic and duplicate-name validation both correctly reject.

**Phase 2 (Substation Registry) is ACCEPTED.** All required backend/frontend
tests pass, the operational status lifecycle gap is resolved (ADR-005), the
schema is verified against real PostgreSQL, and manual UAT confirms the
end-to-end flow works as built.

### Phase 2 UAT fix — mnemonic uniqueness incorrectly rejected same-substation reuse

UAT found that renaming a substation's mnemonic away and then back (e.g.
`SIDS` → `SIDST` → `SIDS`) was incorrectly rejected with "Mnemonic ... is
already in use by a current or historical substation," even though the
historical alias being collided with belonged to the *same* substation
making the request. `_check_mnemonic_available`'s historical-alias check
(`repo.alias_mnemonic_exists_ci`) tested only whether any alias row existed
for the mnemonic, never *whose* alias it was — so a substation always
collided with its own retired mnemonics, and `exclude_substation_id` (already
threaded through correctly by both call sites) had no effect on this half of
the check.

**Backend.** `SubstationRepository.alias_mnemonic_exists_ci` (returned
`bool`) replaced with `find_alias_mnemonic_owner_ci` (returns the owning
`substation_id | None`), so the service can distinguish "this substation's
own historical mnemonic" (allow) from "a different substation's historical
mnemonic" (reject) — the same `exclude_substation_id` parameter used for the
live-record check now scopes the alias check too. Split the previously
single `DuplicateMnemonicError` into two distinct, more specific errors so a
user is never told the wrong reason: `DuplicateMnemonicError` ("already in
use by another *current* substation") and the new
`MnemonicReservedByHistoricalSubstationError` ("previously used by a
*different* substation ... permanently reserved to that substation's
identity"). `DuplicateNameError`'s message was updated to the same "another
current substation" phrasing for consistency; `official_name` was confirmed
to have no equivalent historical-reservation behavior to fix — unlike
mnemonic, substation-registry.md §8 rule 1 singles out mnemonic alone as
"a special, gated operation," and no code path ever writes
`SubstationAlias.alias_name`, so a name rename-and-back already worked
correctly before this fix and required no change.

**Tests.** 7 new tests: 4 in a new `TestMnemonicOwnershipAcrossRename` class
(same-substation reactivation of a historical mnemonic allowed; a different
substation's *current* mnemonic rejected; a different substation's
*historical* mnemonic rejected on both create and update), 1 documenting the
already-correct name rename-and-back behavior, and 2 new API tests
reproducing the exact UAT repro steps end-to-end over HTTP. The pre-existing
`test_retired_mnemonic_cannot_be_reassigned_to_a_new_substation` test was
updated to expect the new, more specific `MnemonicReservedByHistoricalSubstationError`.
271 backend tests total, passing against both SQLite and real PostgreSQL —
live-verified via `curl` against the real dev database reproducing the exact
`SIDS`-style rename-away-and-back sequence (succeeds) and a second
substation attempting to claim the first's retired mnemonic (rejected with
the new historical-reservation message).

---

## Phase 1 — IAM + Core Reference Data

**Scope:** Identity and Access Management (local authentication only) and
the Core Platform reference/lookup tables, per
[`docs/architecture/iam-module.md`](docs/architecture/iam-module.md),
[`docs/adr/ADR-002-identity-and-access-management.md`](docs/adr/ADR-002-identity-and-access-management.md),
and `substation-registry.md` §6.

**Backend**

- IAM data model: `User`, `UserCredential`, `Role`, `Permission`,
  `RolePermission`, `UserRole`, `ExternalIdentityMapping`, `IAMAuditLog`.
- IAM service layer implementing the five interfaces named in
  `iam-module.md` §13: `hasPermission()` (fail-closed), `getUser()`,
  `resolveExternalPrincipal()`, `assertDifferentActors()`,
  `listUserRoles()` — plus user/role/permission CRUD and grant/revoke
  orchestration, each with audit writes.
- Local username/password authentication only. LDAP, Active Directory,
  OAuth, OIDC, MFA, and SSO are explicitly out of scope for this phase
  (structurally supported by `ExternalIdentityMapping`, not implemented).
- A stateless, HMAC-SHA256-signed bearer access token
  (`app/modules/iam/security.py`) — chosen because `iam-module.md` §4
  scopes the token mechanism itself as an implementation detail outside
  architectural scope, and no `Session` entity exists among IAM's owned
  entities.
- Idempotent bootstrap of the initial Administrator account, the baseline
  `Administrator`/`Engineer`/`Viewer` roles, and IAM's own permission
  catalog (`app/modules/iam/bootstrap.py`) — the bootstrap Administrator
  self-references its own `user_id` as creator and audit actor, a stronger
  realization of "never a null actor" than the architecture's stated
  minimum.
- Core Platform reference data: `voltage_level`, `region`, `state`,
  `grid_owner`, `operational_status`, seeded by an idempotent script
  (`app/reference_data/seed.py`).
- Alembic migration `0002_iam_and_core_reference_data` — hand-written (no
  live PostgreSQL reachable in the implementation environment to
  autogenerate against), manually reviewed, verified via `alembic upgrade
  head` → schema inspection → `alembic downgrade base` against a
  throwaway SQLite database as a stand-in.

**Frontend**

- Local login page, current-user display and sign-out (`AppShell`), role
  management, permission catalog management, and user↔role assignment
  UI, under `frontend/src/modules/iam/`.
- Client-side route gating (`ProtectedRoute`) and UI-only permission
  gating derived from the current user's granted permissions — the
  backend remains the sole authorization authority (CLAUDE.md A12); the
  frontend gate only decides what to *show*, never what to *allow*.

**Tests**

- Backend: 47 pytest tests covering fail-closed `hasPermission()`,
  username/role-name/external-identity uniqueness, role lifecycle
  (retired-role guard, revoke-not-delete, idempotent grants),
  authentication, bootstrap idempotency, reference data seed idempotency,
  and API-contract-level authorization enforcement.
- Frontend: 16 Vitest tests covering login success/failure, session
  handling (including a fix for a defect this test suite caught — see
  below), route protection, and permission-gated management UI.

**Defects found and fixed during this phase**

- A SQLite-only autoincrement incompatibility on reference-table primary
  keys (SQLite requires a literal `INTEGER PRIMARY KEY` for its
  rowid-autoincrement behaviour; `SMALLINT PRIMARY KEY` does not qualify)
  was found via the seed-idempotency test and fixed with a
  dialect-variant column type (`SMALLINT` on PostgreSQL, `INTEGER`
  elsewhere) applied identically to both the SQLAlchemy model and the
  Alembic migration.
- The frontend session handler originally cleared a valid access token on
  *any* failure of the `/users/me` request, including transient network
  errors — meaning a brief outage could silently sign a user out. Fixed
  to clear the token only on an explicit `401 Unauthorized` response;
  covered by a regression test.

**Known limitations**

- No Docker and no local PostgreSQL instance was reachable in the
  implementation environment; both the migration and the full test suite
  were verified against SQLite as a documented stand-in. The migration
  should still be run once against real PostgreSQL before being treated
  as final.
- Frontend styling is intentionally minimal — this phase prioritized
  correctness over visual design.

**Architectural issue surfaced**

- `implementation-plan.md` §6 mentions seeding "the MVP's grid codes,"
  but `substation-registry.md`'s canonical schema (the authoritative
  source for this phase) defines no `grid` table. Flagged during
  implementation and resolved by following `substation-registry.md`
  exactly — only the five documented reference tables were seeded, using
  region groupings rather than grid codes.

---

## Phase 0 — Repository Foundation

**Scope:** Project skeleton, tooling, and infrastructure — no business
modules — per `docs/architecture/implementation-plan.md`'s Phase 0
section.

**Backend**

- FastAPI application skeleton with an unversioned `/health` check and an
  empty versioned `/api/v1` router that later phases attach module
  routers to.
- SQLAlchemy `Base` declarative model shared by every future module.
- Alembic initialized with a single no-op baseline revision
  (`0001_initial_baseline`) establishing the migration chain without
  creating any domain tables.
- `backend/pyproject.toml` established as the single source of truth for
  backend dependencies (no `requirements.txt`); Ruff configured for
  linting and formatting; Pytest configured with per-module test
  discovery.
- Empty module packages created for every module named in
  `implementation-plan.md` §2 (`__init__.py` only) — no business logic.

**Frontend**

- Vite + React + TypeScript skeleton: `AppShell`, a `StatusPage` proving
  connectivity to the backend `/health` endpoint through TanStack Query,
  and a minimal `StatusBadge` UI primitive.
- `frontend/package.json` established as the single source of truth for
  frontend dependencies; ESLint, TypeScript strict checking, and Vitest
  configured.
- `src/modules/` established as the convention every future business
  module's frontend feature folder lands in.

**Infrastructure**

- `docker-compose.yml` defining `postgres`, `backend`, and `frontend`
  services — Postgres 16 with a persisted named volume, backend waiting
  for Postgres health before starting. The host's `.venv` is never
  mounted into any container.
- Project-local Python virtual environment convention established:
  `.venv` at the repository root, no global installs, `pip install -e
  "./backend[dev]"` as the standard setup command.
- `.env.example` documenting every environment variable with defaults; no
  secrets committed to source control.

**Tests**

- Backend smoke tests confirming the app starts and `/health` responds
  correctly, and that settings load from the environment without error.
- Frontend smoke test confirming the app shell renders the status page
  without crashing.

**Known limitations**

- No business logic, no domain models beyond Alembic's baseline revision,
  and no API endpoints beyond `/health` — by design, this phase is
  infrastructure only.
