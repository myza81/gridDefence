# GridDefence Implementation Plan

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document converts the completed architecture (12 module documents, 5 ADRs) into a phased implementation plan suitable for execution by Codex, GridDefence's Senior Software Engineer (CLAUDE.md §23: "Codex implements approved architecture. Codex does not redefine architecture.").

**This document does not define new architecture.** Every backend, frontend, and database deliverable below references the specific architecture document section it implements. Where implementation requires a small, genuinely new judgment call (e.g. a stub-interface sequencing technique), that is flagged explicitly as an implementation-sequencing decision, not an architecture decision — and does not override or reinterpret any module document.

---

## Guiding Principles for Every Phase

These apply to all 14 phases without exception, restating the task's binding rules against CLAUDE.md's own authority:

1. **Architecture precedes implementation, and is not redefined by it** (CLAUDE.md §24, A13). If implementation surfaces a genuine architectural gap, it is raised back to the architecture layer (a new ADR or module-doc revision) — never silently resolved in code.
2. **Codex implements one phase at a time.** Each phase is scoped to be independently reviewable and mergeable; a phase is not started until the prior phase's Definition of Done is met.
3. **Database migrations are intentional and reviewed**, never auto-generated and blindly committed. Alembic's autogenerate is a starting draft, not a final artifact (§7).
4. **Every business rule identified in a module document has an accompanying test before its phase is done** (CLAUDE.md A11) — this is a merge-blocking requirement, not a follow-up task.
5. **Approved/Active engineering data is immutable** (CLAUDE.md §5.2, A3) — enforced at the service layer in every phase that owns versioned data, and tested explicitly.
6. **Scheme modules reference master data by ID only** — no phase may introduce a duplicated substation, equipment, or topology attribute into a scheme module's own tables.
7. **PSS/E imports never silently modify approved scheme data** (ADR-003) — Phase 4 and Phase 6–8 each carry an explicit regression test for this.
8. **All inter-module communication uses service interfaces** (CLAUDE.md A1, ADR-001) — no phase may import another module's repository or write to another module's tables. This is checked by code review and, from Phase 2 onward, by an architectural test per module (§10).
9. **No hardcoded engineering parameters** (CLAUDE.md A7) — thresholds, enforcement modes, and validation ranges are database-resident, versioned data in every phase, never application constants.
10. **No Django-specific implementation pattern is copied blindly.** FastAPI + SQLAlchemy + Alembic have different idioms than Django + DRF: an explicit Router→Service→Repository→Database layering (CLAUDE.md §14) replaces Django's fat-model/admin/signal patterns; Pydantic schemas replace DRF serializers; Alembic's reviewed, explicit migrations replace Django's `makemigrations`-and-commit convention. Where the legacy MVP's *domain knowledge* is worth preserving (per each module document's own "MVP Behaviours Preserved" section), its *implementation pattern* is not assumed to transfer.

---

## 1. Recommended Initial Repository Structure

```
griddefence/
├── .claude/CLAUDE.md
├── docs/
│   ├── architecture/
│   └── adr/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py                # CLAUDE.md §22 — environment-driven settings
│   │   │   ├── database.py              # SQLAlchemy session/engine
│   │   │   └── dependencies.py          # shared FastAPI dependencies (current user, DB session)
│   │   ├── reference_data/              # Core Platform shared reference tables (§6)
│   │   └── modules/
│   │       ├── iam/
│   │       ├── substation_registry/
│   │       ├── equipment_registry/
│   │       ├── psse_integration/
│   │       ├── network_model/
│   │       ├── ufls/
│   │       ├── uvls/
│   │       ├── emls/
│   │       ├── critical_infrastructure/
│   │       ├── cross_scheme_compliance/
│   │       └── dashboard/
│   │           # each module package: models.py (persistence) / domain.py / schemas.py (API DTOs)
│   │           # / repository.py / service.py / router.py / tests/  — CLAUDE.md §14, A6
│   ├── alembic/versions/
│   ├── tests/                            # cross-module integration tests only
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── api/                          # typed API clients, one per backend module
│   │   ├── features/                     # one folder per module, mirroring backend/app/modules
│   │   ├── components/                   # shared/reusable UI only
│   │   └── routes/
│   └── vite.config.ts
├── docker-compose.yml
└── README.md
```

Every `modules/<name>/` package on the backend, and every `features/<name>/` folder on the frontend, maps 1:1 to one architecture document — this is the structural expression of CLAUDE.md §12's bounded-context requirement, and makes "which architecture doc governs this code" always unambiguous.

## 2. Backend Module Order

`iam → substation_registry → equipment_registry → automatic_load_shedding_functionality → sensitive_customer_registry → psse_integration → network_model → ufls → uvls → emls → critical_infrastructure → cross_scheme_compliance → dashboard`

This is the same order as the phase list (§ below), because CLAUDE.md A2's dependency direction rule makes it the *only* order in which every module's dependencies already exist when that module is built — with one deliberate, explicitly-managed exception: UFLS/UVLS/EMLS (phases 6–8) call Cross-Scheme Compliance (phase 10) four phases before it exists. This is resolved by the **stub-then-real** sequencing technique described in §5 and Phase 6/10 below — an implementation-sequencing decision, not a reordering of the architecture's dependency direction. `automatic_load_shedding_functionality` (Phase 3.6) and `sensitive_customer_registry` (Phase 3.7) are both placed here to reflect their actual dependency (Equipment Registry only, plus IAM); ALSF was, in practice, built after PSS/E Integration and Network Model (Phase 4/5) — see Phase 3.6's own status note for why it carries no phase-4/5 dependency despite the build-order difference. Sensitive Customer Registry has no such build-order history yet — see Phase 3.7 below.

## 3. Frontend Module Order

Mirrors the backend order exactly, with one addition: the scheme-designer UI (Stage/PriorityGroup + assignment editor) is architecturally near-identical across UFLS, UVLS, and EMLS (per each module doc's own "shared structurally" comparison tables). Recommend building it once as a reusable component set during Phase 6 (UFLS), then adapting — not rebuilding — for Phase 7 (UVLS: add region-scope UI, voltage-magnitude display) and Phase 8 (EMLS: remove threshold UI, add priority/invocation-guidance display).

## 4. First Docker Compose Target (Phase 0)

Deliberately minimal — **PostgreSQL + backend (FastAPI) + frontend (Vite dev server) only.** Redis and an RQ worker are *not* part of the Phase 0 target; they are added starting Phase 4 (PSS/E Integration), the first module with genuinely heavy async computation (per [psse-integration-module.md](psse-integration-module.md) §18 and [network-model-module.md](network-model-module.md) §9 rule 10). Standing up background-job infrastructure before any module needs it would be premature optimisation (CLAUDE.md §21) applied to infrastructure bring-up.

## 5. First Database Migration Strategy

- One Alembic migration per logical schema change, reviewed in the same PR as the model change it corresponds to — never one giant migration per phase.
- Alembic `--autogenerate` output is a **draft only**: every generated migration is manually reviewed for correctness (check constraints, `ON DELETE RESTRICT` clauses, and partial unique indexes are common autogenerate gaps) before commit.
- Migrations are **never edited after merging to `main`** — a correction is always a new migration, consistent with CLAUDE.md §5.2 applied to schema history itself, not just engineering data.
- CI runs `alembic upgrade head` against a fresh database on every PR touching a migration (§9).
- **The stub-interface sequencing technique**, used at the Phase 6–10 seam: a scheme module calls `CrossSchemeComplianceClient.checkCompliance(...)` against an injected implementation. In Phases 6–9, that implementation is a stub returning `blocks_transition=false` with zero findings, satisfying the exact interface contract in [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md) §13. In Phase 10, the real implementation is substituted via dependency injection — **the calling scheme module's own code does not change.** This is the concrete mechanism that lets phases 6–8 be built and reviewed independently, four phases before their real compliance dependency exists, without violating CLAUDE.md A1 (the call is still a real service-interface call throughout, never a direct dependency on Cross-Scheme Compliance's internals).

## 6. Initial Seed / Reference Data Strategy

Phase 1 seeds:
- Core Platform's shared reference tables: `voltage_level`, `region`, `state`, `grid_owner`, `operational_status` (per [substation-registry.md](substation-registry.md) §6, populated with the exact values the legacy MVP hardcoded — 500/275/230/132 kV; the MVP's grid codes and region groupings; TNB/DC/LSS/IPP/LPC/Tie-Line ownership classes).
- IAM's own baseline: system roles (`Administrator`, `Engineer`, `Viewer`) and IAM's own permission codes (`iam.role.manage`, etc.).

**Every subsequent module's own permission codes are seeded incrementally, as part of that module's own phase** — not all upfront in Phase 1, since the full catalog cannot be known until every module exists (per [iam-module.md](iam-module.md) §7.3: "a corresponding `Permission` catalog entry is registered in IAM as part of that module's own deployment/seed process"). Phase 2 seeds `substation_registry.*`; Phase 6 seeds `ufls.*`; and so on.

Reference-data seed scripts are idempotent (safe to re-run) and version-controlled alongside schema migrations, consistent with CLAUDE.md A7's treatment of engineering parameters as versioned data, not deployment-time constants.

## 7. MVP Data Migration Strategy (detailed in Phase 12)

- **Substation master data**: migrate the legacy MVP's `initial_data.json` fixture (~5,000 records) into the real Substation Registry schema. `mnemonic + voltage` becomes a derived display convention, never the primary key (a fresh UUID is generated per row). Flat string fields (`ownership`, `grid`, `region`, `state`) are resolved against the Phase 1-seeded reference tables — this resolution must succeed for every row before commit, or the row is flagged for manual reconciliation.
- **Equipment data**: best-effort migration of the legacy MVP's `LoadTransformer`/`AutoTransformer`/`IncomingBranch` records into Equipment Registry's as-built schema (Phase 3, complete) — `Transformer`/`TransformerTerminal` for the two transformer types, `Circuit`/`CircuitTerminal` for `IncomingBranch`, not a generic `Equipment` common backbone (superseded per [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md)/[ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md); see Phase 3's own status note above).
- **Scheme data (`LoadSheddingVersion`/`Stage`/bays) is deliberately NOT auto-migrated.** The legacy MVP's "active" status carries none of GridDefence's Approved/Active rigor (CLAUDE.md §5.2) — silently importing old scheme data as "Approved" would misrepresent it as having passed a review process it never went through. **Recommendation: engineers re-author current schemes fresh in GridDefence**, using the legacy data only as a read reference during that process (e.g. a temporary, clearly-labeled read-only export, not a live GridDefence record).
- **Critical asset data**: migrated into Critical Infrastructure (Phase 9), but `restriction_type` (Prohibited/ConditionallyAllowed/Unrestricted) has no MVP equivalent and **requires a manual classification pass by engineers post-migration** — it cannot be automatically derived from the MVP's `critical_restricted_stages` list.
- **PSS/E topology/snapshot data**: not migrated. A fresh RAW file import into the new PSS/E Integration module (Phase 4) is simpler and safer than attempting to migrate historical `NetworkSnapshot` rows into the new `TopologyVersion`/`LoadSnapshot` split — the legacy data's value was primarily current-state, not long-term historical record (consistent with [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md)'s own reasoning about load snapshot churn).
- **Users**: not migrated with any rich role data (the MVP had none). Bootstrap fresh per [iam-module.md](iam-module.md)'s closing summary: `is_superuser → Administrator`, `is_staff → Engineer`, followed by a deliberate, human-reviewed refinement into real Editor/Reviewer/Approver/Activator assignments.

## 8. Testing Strategy by Phase

Every phase follows CLAUDE.md §18's priority order — Business Rules → Engineering Calculations → API Contracts → UI Behaviour → Infrastructure — detailed per-phase in each phase's "Tests required" below. Three tests recur across every module-owning phase and are called out once here rather than repeated:

- **The "no foreign key into a scheme module's schema" architectural test**, for every non-scheme module (Substation Registry, Equipment Registry, PSS/E Integration, Network Model, Critical Infrastructure) — already specified explicitly in each of those modules' own §16.
- **The immutability test** ("approved data does not change when its source is recomputed/superseded") for every module in the PSS/E Integration → Network Model → UFLS/UVLS/EMLS chain.
- **The fail-closed test** for IAM's `hasPermission` (Phase 1) and, from Phase 10, Cross-Scheme Compliance's handling of a `Failed` check run.

## 9. CI/CD Minimum Viable Pipeline

CLAUDE.md A15 explicitly defers a formal CI/CD standard "until first implementation need" — that need is now. This is a deliberately minimal starting pipeline, not a claim that A15's deferred standard has been formally superseded by this document:

1. Lint (`ruff`/backend, `eslint`/frontend).
2. Type-check (`mypy`/backend, `tsc`/frontend).
3. Unit + business-rule tests (`pytest`, `vitest`) — merge-blocking per CLAUDE.md A11.
4. Migration check: `alembic upgrade head` against a fresh database.
5. Build check: backend and frontend Docker images build successfully.

Runs on every PR; blocks merge on any failure. Expanded in Phase 13 (load/security testing) once the platform is feature-complete enough for that to be meaningful.

## 10. Implementation Risks and Mitigations (Global)

| Risk | Mitigation |
|---|---|
| Architecture drift — Codex reinterpreting a module doc during implementation | Definition of Ready (§12) requires explicit citation of the relevant doc section per deliverable; PR review checklist requires "matches architecture doc §X" sign-off |
| Phase scope creep | Strict one-phase-at-a-time; Definition of Done (§13) is the phase's contract, not a moving target |
| The Phase 6→10 compliance stub cutover requiring unexpected scheme-module changes | Phase 6's stub must implement the *exact* interface contract from [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md) §13; Phase 10 includes a dedicated regression test proving zero scheme-module code changes were needed (Phase 10 Tests) |
| Migration irreversibility | Human-reviewed migrations only, tested in CI against a fresh DB, never edited post-merge (§5) |
| Business-rule test debt | CLAUDE.md A11 enforced as a CI gate (§9), not a review suggestion |
| Django-pattern leakage (fat models, signals-as-business-logic, implicit `makemigrations`) | Explicit review checklist item per phase; Router→Service→Repository→Database layering enforced structurally by the repository layout (§1) |
| Dashboard (Phase 11) has no dedicated architecture document | Flagged explicitly in "Architecture Gaps" (closing section) — recommend a lightweight design note before Phase 11 begins, scoped from every other module's already-documented read interfaces |

## 11. Definition of Ready for Codex (per phase)

- The relevant module architecture document(s) have been read in full for this phase.
- The prior phase is merged, and its CI is green.
- No open item in the relevant module doc's "architectural decisions still requiring ADR" section blocks this phase's *core* functionality (cross-checked in the closing "Architecture Gaps" section — most flagged items are deferrable, not blocking).
- The phase's Codex prompt (outlined per phase below) is finalized and scoped to that phase only.
- The database schema for this phase's owned entities is already specified in the relevant module doc's Database Design Concept section — Codex translates concept to SQLAlchemy models and an Alembic migration; it does not invent new schema design.

## 12. Definition of Done (per phase, general template)

- All backend deliverables implemented, each traceable to a specific architecture doc section.
- Migrations created, reviewed, and passing the CI migration check.
- Every business rule named in the relevant module doc(s) has a passing test (CLAUDE.md A11).
- API contract matches the module doc's Database/API Contract concept in intent (resource shape and behaviour), not necessarily identical route naming.
- No cross-module repository imports (verified in review; architectural test where specified).
- No hardcoded engineering parameters (verified in review).
- Approved/Active immutability enforced and tested, where the phase owns versioned data.
- Frontend deliverables (where applicable) implemented and manually verified against the golden path.
- PR reviewed and merged; CI green.
- Phase-specific acceptance criteria (below) all satisfied.

---

# Phased Implementation Plan

## Phase 0 — Repository Foundation

**Objective:** Stand up a real, empty skeleton — structure, tooling, CI, Docker Compose, health checks — with zero business logic, so every later phase has a working foundation.

**Architecture documents involved:** [system-overview.md](system-overview.md), [ADR-000](../adr/ADR-000-architecture-principles.md), [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md), CLAUDE.md §9/§10/§14.

**Backend deliverables:** FastAPI app skeleton (`main.py`, `core/config.py`, `core/database.py`); empty `modules/` packages (one per §2's module order, `__init__.py` only); Alembic initialized and wired to SQLAlchemy metadata; a `/health` endpoint; environment-driven settings (CLAUDE.md §22).

**Frontend deliverables:** Vite + React + TypeScript skeleton; TanStack Query provider; empty routing skeleton; a placeholder app shell; ESLint/Prettier configuration.

**Database deliverables:** Empty PostgreSQL database via Docker Compose; Alembic migration chain established with a no-op initial revision.

**Tests required:** Trivial backend test hitting `/health`; trivial frontend smoke test (app shell renders); the CI pipeline itself is this phase's primary validation.

**Acceptance criteria:** `docker compose up` brings up postgres+backend+frontend cleanly; `/health` returns 200; frontend renders the app shell; `alembic upgrade head` runs cleanly; CI runs lint+test+build on a trivial PR and passes.

**Dependencies:** None — first phase.

**Risks:** Over-scaffolding (building out module boilerplate before it's needed) — mitigated by keeping module packages genuinely empty until their own phase. Under-scaffolding (missing a convention a later phase needs) — mitigated by referencing [system-overview.md](system-overview.md)'s layering explicitly in the Codex prompt.

**Codex implementation prompt outline:** "Set up the GridDefence repository skeleton per `docs/architecture/system-overview.md` §3–§6 and `docs/adr/ADR-001-modular-monolith-and-module-communication.md`. Create the backend FastAPI structure exactly as `docs/architecture/implementation-plan.md` §1 specifies, with empty module packages for iam, substation_registry, equipment_registry, psse_integration, network_model, ufls, uvls, emls, critical_infrastructure, cross_scheme_compliance, dashboard. Initialize Alembic against the SQLAlchemy metadata. Create the frontend Vite+React+TypeScript skeleton per CLAUDE.md §9's technology stack. Create `docker-compose.yml` per `implementation-plan.md` §4 (Postgres + backend + frontend only — no Redis yet). Add a minimal CI pipeline per `implementation-plan.md` §9. Implement nothing beyond a health check — no business models, no endpoints, no migrations beyond the no-op initial revision. Do not modify `.claude/CLAUDE.md` or anything under `docs/`."

---

## Phase 1 — IAM + Core Reference Data

**Objective:** Implement identity/authorization and seed Core Platform's shared reference data, since every later phase depends on both.

**Architecture documents involved:** [iam-module.md](iam-module.md), [ADR-002](../adr/ADR-002-identity-and-access-management.md), [substation-registry.md](substation-registry.md) §6 (for the specific reference tables to seed).

**Backend deliverables:** `User`/`UserCredential`/`Role`/`Permission`/`RolePermission`/`UserRole`/`ExternalIdentityMapping` models, repository, service, router per [iam-module.md](iam-module.md) §5/§11/§12/§13; local username/password authentication (session-based, matching the legacy MVP's simplicity while behind a swappable dependency-injection boundary — §7.6's "authentication mechanism is an implementation detail" holds); `hasPermission`/`getUser`/`resolveExternalPrincipal`/`assertDifferentActors`/`listUserRoles` service methods; a bootstrap script creating the first `Administrator` user, handling the self-referential FK exception per §9 rule 7; a separate `reference_data` package implementing Core Platform's `voltage_level`/`region`/`state`/`grid_owner`/`operational_status` tables (kept structurally distinct from IAM's own bounded context, even though built in the same phase).

**Frontend deliverables:** Login page; `users/me` display; basic role/permission administration screens (list/create roles, assign permissions to roles, assign roles to users) — functional, not polished.

**Database deliverables:** `user`, `user_credential`, `role`, `permission`, `role_permission`, `user_role`, `external_identity_mapping`, `iam_audit_log`; `voltage_level`, `region`, `state`, `grid_owner`, `operational_status` + seed data migration (§6).

**Tests required:** Fail-closed `hasPermission` test against an unregistered `permission_code` (highest priority in this phase, per [iam-module.md](iam-module.md) §16); username/role-name uniqueness; `(external_principal_id, provider)` uniqueness among current mappings; bootstrap-exception audit behaviour; reference-data seed idempotency.

**Acceptance criteria:** An Administrator can log in; `hasPermission` correctly denies an unregistered code; role/permission CRUD works; reference tables are seeded and queryable by later phases.

**Dependencies:** Phase 0.

**Risks:** The chosen session mechanism affecting later phases' auth wiring — mitigated by isolating it behind `core/dependencies.py`.

**Codex implementation prompt outline:** "Implement the IAM module per `docs/architecture/iam-module.md` in full — §5 (Owned Entities), §7 (Domain Model, all subsections), §8 (Lifecycle), §9 (Business Rules), §10 (Validation Rules), §11 (Database Design), §13 (Service Interfaces). Implement Core Platform reference data per `docs/architecture/substation-registry.md` §6, seeded with the values documented in `implementation-plan.md` §6. Follow CLAUDE.md §14's Router→Service→Repository→Database layering. The fail-closed `hasPermission` behaviour (§9 rule 11 of iam-module.md) is the single highest-priority business rule in this phase and must have a dedicated test. Do not implement authentication mechanics beyond a working local login — MFA, SSO, and LDAP/AD/OIDC integration are explicitly out of scope (iam-module.md §4, §17)."

---

## Phase 2 — Substation Registry

**Objective:** Implement the platform's master data anchor.

**Architecture documents involved:** [substation-registry.md](substation-registry.md).

**Backend deliverables:** `Substation`, `SubstationAlias`, `substation_audit_log` — model, repository, service, router; `created_by_user_id`/`updated_by_user_id` wired to Phase 1's `getUser`/`hasPermission`.

**Frontend deliverables:** Substation list (TanStack Table), substation detail/create/edit form. Map visualization is optional at this phase — may be deferred to Phase 11 (Dashboard) without blocking this phase's acceptance.

**Database deliverables:** `substation`, `substation_alias`, `substation_audit_log`; `substation_registry.read`/`substation_registry.write` permission codes seeded.

**Tests required:** Mnemonic uniqueness (case-insensitive); `substation_id` immutability; alias creation on mnemonic change; geo coordinate pair validation; soft-delete-only enforcement (no hard delete outside the documented administrative exception).

**Acceptance criteria:** CRUD works end to end; mnemonic uniqueness enforced; changing a mnemonic produces a `SubstationAlias` row, never an overwrite.

**Dependencies:** Phase 1 (accountability fields, reference data FKs).

**Risks:** None significant — this phase works correctly with a handful of test records; the real ~5,000-record fixture is Phase 12's concern, not this phase's.

**Codex implementation prompt outline:** "Implement the Substation Registry per `docs/architecture/substation-registry.md` in full. Reference Phase 1's IAM service for `hasPermission`/`getUser` — do not implement local user handling here. Reference Core Platform's reference tables (seeded in Phase 1) via foreign key, never duplicate their values. Implement the alias-history pattern (§7.6 equivalent in substation-registry.md) exactly — mnemonic changes never overwrite in place."

---

## Phase 3 — Equipment Registry

**Objective:** Implement physical equipment master data one level below Substation Registry.

**Architecture documents involved:** [equipment-registry-module.md](equipment-registry-module.md).

**STATUS: Complete, frozen after UAT (commit `c94e061`).** The plan below is this phase's *original* description, retained as historical record — it predates [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md) and [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md), both decided during Phase 3's own implementation, and the as-built module differs materially from it. **The entities actually delivered are `Circuit`/`CircuitTerminal` (not `IncomingBranchDetail`), `SubstationVoltageYard`/Switchyard ([ADR-008](../adr/ADR-008-substation-voltage-yard.md)), and `Transformer`/`TransformerTerminal` (not generic `LoadTransformerDetail`/`AutoTransformerDetail`) — plus the `ENTERED_IN_ERROR` deletion/correction policy and the transformer breaker-numbering-convention reference table, both added as UAT follow-ups.** No generic `Equipment` backbone and no `RelayDetail`/`RelayControlledEquipment` were built — both were deliberately deferred future scope at the time. **That deferred scope is now complete, not as `RelayDetail`/`RelayControlledEquipment`, but as the Automatic Load Shedding Functionality Registry — see Phase 3.6 below.** For the authoritative final shape, see [equipment-registry-module.md](equipment-registry-module.md) (including its "Superseded Design Decisions" appendix) and `CHANGELOG.md`'s Phase 3/3.5 entries, not the bullets immediately below.

**Backend deliverables (original plan, superseded — see status note above):** `Equipment` (common backbone) + `LoadTransformerDetail`/`AutoTransformerDetail`/`IncomingBranchDetail`/`RelayDetail` + `RelayControlledEquipment` + `EquipmentAlias` + audit log; read-only equipment-lookup and equipment-by-substation service interfaces.

**Frontend deliverables:** Equipment list/detail, embedded within the Substation detail view (per substation) rather than a fully separate top-level screen. *(This held true in the as-built module as well — Circuit/Transformer management is reachable from the Substation Detail page.)*

**Database deliverables:** Per §11 of the module doc, including the mandatory `is_scheme_relevant`/`remarks` fields and the explicitly-optional asset-metadata columns. *(Superseded — see status note above; the as-built schema has no `is_scheme_relevant` field and no generic `Equipment` table at all.)*

**Tests required:** `bay_id` uniqueness among current equipment; exactly-one-detail-row-matching-`equipment_type`; `RelayControlledEquipment` constraints (no relay-controls-relay, same-substation requirement); the no-foreign-key-into-any-scheme-module architectural test; a test confirming optional metadata fields (manufacturer/model/firmware/serial/maintenance owner) are never required by any validation rule. *(Superseded — the as-built test suite covers `Circuit`/`CircuitTerminal`/`Transformer`/`TransformerTerminal` uniqueness and lifecycle rules instead; see `equipment-registry-module.md` §16 and `CHANGELOG.md`.)*

**Acceptance criteria:** Equipment CRUD works per type; bay ID / alias history works; relay wiring (trip-target relationships) works; a `Relay` cannot be marked active with zero controlled equipment. *(Superseded — relay wiring was not built; the as-built acceptance criteria are recorded in `CHANGELOG.md`'s Phase 3/3.5 UAT-acceptance entries.)*

**Dependencies:** Phase 2 (`substation_id` references).

**Risks:** Scope discipline — the module doc's explicit EAM exclusion (§1/§4/§9 rules 13–14) must be respected; no work-order, maintenance-history, or procurement functionality is in scope for this phase, ever, without a new ADR.

**Codex implementation prompt outline (historical — not the actual build; retained for record only):** "Implement Equipment Registry per `docs/architecture/equipment-registry-module.md` in full, paying particular attention to §1's scope framing and §4's explicit EAM exclusion — do not add any maintenance, work-order, or procurement functionality. Implement the `Equipment` common-backbone pattern exactly as §7.1 specifies (one `equipment_id`, type-specific detail tables), not four unrelated top-level tables. Manufacturer/model/firmware/serial number/maintenance owner are optional columns only — no validation rule may require them."

---

## Phase 3.6 — Automatic Load Shedding Functionality Registry

**Phase numbering note.** The original 14-phase sequence (Phase 0–13) never assigned this module a phase number — it was originally sketched inside Phase 3 (`RelayDetail`/`RelayControlledEquipment`, deferred; see Phase 3's status note above), then re-scoped as its own module by [ADR-011](../adr/ADR-011-automatic-load-shedding-functionality-registry.md) after Phase 3 shipped without it. It is labeled **Phase 3.6** here, following the precedent already set by Phase 3.5 (Transformer Registry, `CHANGELOG.md`) — an unplanned, additive post-Phase-3 addition to the Engineering Registry domain. This is a label for this document's own internal consistency only; it does not renumber Phase 4 onward, and no other phase number changes.

**Objective:** Answer, per Bay Terminal, "can this bay be operated by a Grid Defence Scheme?" — the engineering question [EDR-003](../engineering/edr/EDR-003-relay-registry-scope.md) scopes and [01-engineering-philosophy.md](../engineering/01-engineering-philosophy.md) §5 Step 5 names Relay Capability Verification. Retires "Relay Registry" as a working/implementation name (not as an engineering concept) and the general-purpose relay-wiring direction `equipment-registry-module.md` §7.8 had sketched (superseded).

**Architecture documents involved:** [automatic-load-shedding-functionality-registry-module.md](automatic-load-shedding-functionality-registry-module.md), [ADR-011](../adr/ADR-011-automatic-load-shedding-functionality-registry.md).

**STATUS: Complete.** Backend module (`AutomaticLoadSheddingFunctionality` + audit log), frontend registry pages, and full test suites are implemented and merged.

**Backend deliverables (as built):** `AutomaticLoadSheddingFunctionality` — one record per Bay Terminal (`circuit_terminal_id`/`transformer_terminal_id`, XOR), `ufls_function`/`uvls_function` independent booleans (a bay may support both simultaneously), persisted `lifecycle_status` (`ACTIVE`/`DECOMMISSIONED` — a bay-level existence flag, never itself the status an engineer sees), optional `relay_make`/`relay_model` metadata, and its own append-only audit log. A computed, never-stored **Available / Assigned / Decommissioned** status per record (module document §8.1), plus `is_ufls_capable`/`is_uvls_capable`, candidate-search, and capability-check read interfaces for future UFLS/UVLS consumption (module document §13) — see Phase 6/7 dependency updates below.

**Frontend deliverables (as built):** Registry list/create/detail/candidate pages, reachable from the app shell nav, showing the full engineering identity (`Substation | Voltage | Bay`) consistently across every view.

**Database deliverables:** Per the module document §11 — `automatic_load_shedding_functionality` and `automatic_load_shedding_functionality_audit_log`, referencing Equipment Registry's `circuit_terminal`/`transformer_terminal` and IAM's `user` by ID only (CLAUDE.md A1); no cross-module table is altered.

**Tests required (delivered):** Target-type XOR; at-least-one-function-flag; at-most-one-non-decommissioned-record-per-terminal (partial unique index); decommission is terminal and re-decommissioning an already-decommissioned record is rejected, not silently accepted; Available/Assigned/Decommissioned status computation from a caller-supplied `assigned_terminal_ids` set, including the "decommissioned wins even if assigned" case; bay-identity distinctness for two ambiguous terminals at the same substation and voltage level; the no-foreign-key-into-any-scheme-module architectural test.

**Acceptance criteria:** A full create → (optional metadata edit) → decommission flow completes end to end; capability and candidate-search interfaces return correct results against real Equipment Registry data; every non-decommissioned record displays `AVAILABLE` when no `assigned_terminal_ids` is supplied (today's Current Phase Behaviour, since UFLS/UVLS do not exist yet).

**Dependencies:** Phase 3 (Equipment Registry — `CircuitTerminal`/`TransformerTerminal` reference targets), Phase 1 (IAM — `user_id` audit attribution).

**Downstream integration seam (for Phase 6/7, not yet connected):** `get_detail`/`list_functionality`/`list_assigned_and_available` accept an optional `assigned_terminal_ids: set[UUID]` — the union of Bay Terminal IDs currently referenced by an Active UFLS and/or UVLS scheme version. No caller exists yet, so this defaults to empty and every non-decommissioned record displays Available. UFLS/UVLS connect this seam themselves, in-process, when built (module document §8.2) — ALSF never queries their tables, and assignment ownership is never transferred into ALSF (CLAUDE.md A1).

---

## Phase 3.7 — Sensitive Customer Registry

**Phase numbering note.** Following the exact precedent set by Phase 3.5 (Transformer Registry) and Phase 3.6 (Automatic Load Shedding Functionality Registry): this module's only real dependencies are Phase 3 (Equipment Registry, for the `TransformerTerminal` reference target) and Phase 1 (IAM), so it is labeled **Phase 3.7** — an unplanned, additive post-Phase-3 addition to the Engineering Registry domain, continuing the established numbering convention. This is a label for this document's own internal consistency only; it does not renumber Phase 4 onward, and no other phase number changes. See [`sensitive-customer-registry-implementation-spec.md`](sensitive-customer-registry-implementation-spec.md) §2 for the full placement rationale.

**Objective:** Answer, per Transformer Terminal, "would operating this bay affect a facility that deserves special engineering consideration, and how sensitive is it?" — the engineering question [EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md) scopes and [01-engineering-philosophy.md](../engineering/01-engineering-philosophy.md) §5 Step 4 names Sensitive Customer Review. Unlike every other module in this series, this registry is explicitly designed to remain reusable by future engineering applications that have never heard of GridDefence ([ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md) decision 5).

**Architecture documents involved:** [`sensitive-customer-registry-module.md`](sensitive-customer-registry-module.md), [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md), [EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md), [`sensitive-customer-registry-implementation-spec.md`](sensitive-customer-registry-implementation-spec.md) (the full implementation-level plan for this phase — entities, migration, service contracts, API surface, increments, and test matrix).

**STATUS: Complete.** Backend module (`SensitiveFacility` + `FacilitySector`/`SensitivityClassification` reference data + shared audit log), frontend registry pages, and full test suites are implemented and merged. **Post-UAT update:** the single-terminal association described immediately below was subsequently replaced by a many-to-many association per [ADR-013](../adr/ADR-013-sensitive-facility-multiple-transformer-terminals.md) — a `SensitiveFacility` now associates with zero, one, or many currently active Transformer Terminals; see CHANGELOG.md's "Phase 3.7 — UAT Change Request" entry for the as-built shape. The description below records the original Phase 3.7 delivery and is preserved unmodified (CLAUDE.md §5.2).

**Backend deliverables (as built):** `SensitiveFacility` — one record per physical facility, `facility_sector_id`/`sensitivity_classification_id` (both required, FK to module-owned reference tables), optional `transformer_terminal_id` (current supply point only, no uniqueness constraint — many facilities may share one terminal, the deliberate inverse of ALSF's own per-terminal uniqueness rule), `lifecycle_status` (`ACTIVE`/`ARCHIVED`/`ENTERED_IN_ERROR` — not ALSF's `DECOMMISSIONED` vocabulary), and its own audit trail. `FacilitySector`/`SensitivityClassification` — module-owned, admin-editable reference data (the first implemented precedent of this pattern in this codebase; Critical Infrastructure's parallel `CriticalityLevel` remains unimplemented). Read/batch-lookup service interfaces (`has_sensitive_facility`, `get_sensitive_facilities_for_transformer_terminal(s)`) for future UFLS/UVLS/EMLS consumption — see implementation spec §9. **Registry mutation (create/edit/reassign/lifecycle actions/reference-data administration) is Administrator-only** — Engineer holds read access only, no new role was introduced (implementation spec §12), since this registry is global authoritative engineering knowledge that scheme engineers consume but do not own. A `transformer_terminal_resolution` field (`NOT_ASSIGNED`/`RESOLVED`/`UNRESOLVED`) is reported independently of `lifecycle_status` on every read — a facility is never omitted from a list/detail response merely because its Transformer Terminal cannot currently be resolved (Correction 4).

**Frontend deliverables (as built):** Registry list/create/edit/detail pages plus a lightweight in-module summary strip and two reference-data administration pages, following ALSF's established UX pattern, reachable from the app shell nav.

**Database deliverables:** Per the module document §11 / implementation spec §5/§13 — `facility_sector`, `sensitivity_classification`, `sensitive_facility`, `sensitive_customer_registry_audit_log` (migration `0015_sensitive_customer_registry`), referencing Equipment Registry's `transformer_terminal` and IAM's `user` by ID only (CLAUDE.md A1); no cross-module table is altered. Verified `upgrade → downgrade → upgrade` against real PostgreSQL.

**Tests required (delivered):** No per-terminal uniqueness (positive multi-facility-per-terminal test); reference-data rename-after-use audit correctness and seed idempotency; all four lifecycle transitions plus the `Entered in Error` terminal-state prohibition; a stale/unresolvable terminal reference never omitting the facility from a read (Correction 4); mandatory-reason enforcement for Transformer Terminal reassignment (Correction 5); Administrator-only mutation, Engineer read-only (Correction 1); batch-lookup completeness-by-construction; the no-foreign-key/no-cross-module-import architectural test. Full backend suite (666 tests) passing; this module's own 63 tests additionally verified against real PostgreSQL; full frontend suite (209 tests) passing; lint/typecheck clean for all newly-added files; the repository-standard `npm run build` gate fails only due to a pre-existing, unrelated TypeScript error in `frontend/tests/components/ui/DataTable.test.tsx` (confirmed via `git diff` to predate this phase — no file this phase touches is implicated); the underlying Vite production bundle builds cleanly.

**Acceptance criteria:** A full create → (optional terminal reassignment) → archive → reactivate → entered-in-error flow completes end to end; batch lookup against a realistic (500+) Transformer Terminal ID set returns a complete, correctly-shaped mapping in one call; reference-data administration works without any code deployment.

**Dependencies:** Phase 3 (Equipment Registry — `TransformerTerminal` reference target), Phase 1 (IAM — `user_id` audit attribution, permission bootstrap).

**Required sequencing relative to Phase 6:** This phase's implementation is architecturally dependent only on Phase 1 (IAM) and Phase 3 (Equipment Registry) — nothing about its own scope depends on Phase 4, 5, or 6. Given that, **Phase 3.7 must be completed before Phase 6 (UFLS) begins**, exactly as ALSF (Phase 3.6) was completed before Phase 6 for Relay Capability Verification, so that UFLS, UVLS, and EMLS consume the real Sensitive Customer Registry service contract from their own first commit, with no scheme module ever actually needing the stub-then-real fallback described in Phase 6's own Backend deliverables below. That fallback remains documented as a general contingency mechanism for genuine schedule slippage, not as an equally-valid default sequencing choice for this specific dependency — Phases 0–3.6 do not consult this registry and are unaffected either way, but Phase 6 planning should treat Phase 3.7's completion as a precondition, not an optional nicety.

**Downstream integration seam (for Phase 6/7/8, not yet connected):** `get_sensitive_facilities_for_transformer_terminal(s)`/`has_sensitive_facility` are ready to be called by any scheme module's Selection of Shedding Actions once built. No caller exists yet. This registry never queries a scheme module's tables, and is never queried by Network Model or the Automatic Load Shedding Functionality Registry (CLAUDE.md A1; ADR-012 Service Interface Expectations).

---

## Phase 4 — PSS/E Integration

**Objective:** Implement RAW file import with topology/load separation, and correlate the imported topology against Equipment Registry's registered `Circuit`/`CircuitTerminal` identities.

**Architecture documents involved:** [psse-integration-module.md](psse-integration-module.md), [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md), [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md), [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md) (both decided after this plan was originally written — see [equipment-registry-module.md](equipment-registry-module.md), which owns the `Circuit`/`CircuitTerminal` identities this phase correlates against).

**Backend deliverables:** `RawFileImportBatch`; `TopologyVersion`/`TopologyBus`/`TopologyBranch`/`TopologyTransformer`; `LoadSnapshot`/`LoadSnapshotBusState`/`LoadSnapshotElementState`/`NetworkLoad`/`NetworkGenerator`; deterministic signature calculation with canonicalization; preview/commit workflow (preview has zero persistent side effects); activation workflow (atomic Current-promotion with correlated audit event); **`EquipmentTopologyMap`** — correlates Equipment Registry's `CircuitTerminal`-backed `equipment_id` values to imported `TopologyBranch`/`TopologyTransformer` elements per `TopologyVersion`, producing a clean-match/unmatched/discrepancy outcome per terminal, with discrepancies requiring mandatory human review and never an automatic write to Equipment Registry (see [psse-integration-module.md](psse-integration-module.md) §8a for the full specification); Redis + RQ introduced here for async parsing/validation.

**Frontend deliverables:** RAW file upload screen; preview report display (topology reuse-or-new determination, coverage, warnings); activation UI; current/historical snapshot browsing; an `EquipmentTopologyMap` review screen surfacing unmatched/discrepancy entries for engineer resolution.

**Database deliverables:** Per §11 of the module doc; `psse_import_audit_log`; `equipment_topology_map` (psse-integration-module.md §8a/§11).

**Tests required:** Signature stability under canonicalization (structurally identical files with incidental formatting differences produce the same signature); topology-reuse-vs-new-version decision correctness; preview-has-zero-persistence test; activation atomicity (both halves of a supersession succeed together or neither does); the ADR-003 regression test — importing a new load snapshot never modifies any Approved/Active scheme version's data (a placeholder/no-op check at this phase, since no scheme module exists yet — the meaningful version of this test lands in Phase 6); `EquipmentTopologyMap` matching correctness (clean-match/unmatched/discrepancy classification), the never-auto-mutate-Equipment-Registry guarantee, and the `ENTERED_IN_ERROR`-exclusion-from-matching rule (psse-integration-module.md §8a, §9 rules 14–15).

**Acceptance criteria:** Uploading a RAW file correctly separates topology from load; re-uploading a structurally-unchanged file reuses the existing `TopologyVersion` automatically; activation works; preview leaves no trace if abandoned; `EquipmentTopologyMap` correctly classifies matched/unmatched/discrepant `CircuitTerminal`s for a given `TopologyVersion`, and a discrepancy can be reviewed and resolved (accept/reject) without any automatic write to Equipment Registry.

**Dependencies:** Phase 2 (substation matching), Phase 1 (IAM), **Phase 3 (Equipment Registry — `Circuit`/`CircuitTerminal` must exist before `EquipmentTopologyMap` can correlate against them; not listed as a dependency in this plan's original version, corrected per ADR-006/ADR-007)**. Redis/RQ added to Docker Compose in this phase (§4 of this document) — used both for RAW file parsing/validation and for `EquipmentTopologyMap` matching against large topologies.

**Risks:** RAW file parsing edge cases; large-file performance — the async job design must be correct from the start, not retrofitted, given the explicit risk noted in [psse-integration-module.md](psse-integration-module.md) §18; `EquipmentTopologyMap` has no persisted rename/alias history to match against for `Circuit`/`CircuitTerminal` (psse-integration-module.md §8a.4) — accepted as a known limitation, not a blocker, since a stale match still fails safe into mandatory human review rather than silently succeeding.

**Codex implementation prompt outline:** "Implement PSS/E Integration per `docs/architecture/psse-integration-module.md` in full, `docs/adr/ADR-003-psse-topology-and-load-snapshot-separation.md`, and `docs/adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md`/`docs/adr/ADR-007-canonical-engineering-reference-object.md`. Implement all 8 workflows from module doc §8.4–§8.11 explicitly, including the preview/commit split (§8.9) with zero persistence on preview. Implement `EquipmentTopologyMap` per module doc §8a — target `CircuitTerminal`, never generic `Equipment` or `Circuit` directly; classify every match as clean-match/unmatched/discrepancy; never write to `Circuit`/`CircuitTerminal`/`Transformer`/`TransformerTerminal` automatically, in either direction; exclude `ENTERED_IN_ERROR` records as matching candidates. Add Redis and an RQ worker to docker-compose.yml for import parsing and validation — this is the first phase requiring them. Signature calculation must canonicalize parsed structural records before hashing, never hash raw file bytes (§10)."

---

## Phase 5 — Network Model

**Objective:** Implement connectivity/island analysis over PSS/E Integration's topology data.

**Reconciliation note (what was actually delivered, and the Operational Snapshot pivot):** Phase 5, as executed, delivered a static, PSS/E-independent connectivity view derived from Substation Registry and Equipment Registry (see [network-model-module.md](network-model-module.md) §19) rather than the island/pocket analysis this section originally planned, which remains unbuilt. Per [EDR-007](../engineering/edr/EDR-007-phase-7-operational-identity-mapping.md) and [operational-snapshot-architecture.md](operational-snapshot-architecture.md), Operational Snapshot is authoritative for current electrical topology and connectivity; Engineering Registries (including this section's own connectivity data) remain authoritative for curated identity and metadata. Future phases building on Network Model should describe **correlating** Operational Snapshot against Engineering Registries for engineering workflows, not populating topology truth into a registry, and not treating a registry-derived view as authoritative current connectivity.

**Architecture documents involved:** [network-model-module.md](network-model-module.md).

**Backend deliverables:** `CutSetDefinition`; `IslandAnalysisResult` + `IslandAnalysisResultSubstation`; `ManualOverride` + `ManualOverrideSubstation`; `analyzeIsland`/`getEffectiveIsland`/`getConnectivityGraph`/`createManualOverride` service interfaces; async job wiring (reusing Phase 4's Redis/RQ setup, not reinventing it).

**Frontend deliverables:** Connectivity graph visualization (ECharts); pocket/island analysis preview; manual override creation UI.

**Database deliverables:** Per §11 of the module doc — normalized substation sets (no JSON blobs), matching the module doc's explicit correction of the legacy MVP's pattern.

**Tests required:** Determinism/reproducibility (same `(TopologyVersion, LoadSnapshot, CutSetDefinition)` triple always yields the same result); immutability of computed results; single-active-override-per-result enforcement; the no-foreign-key-into-any-scheme-module architectural test (this module's defining decoupling property, per §9 rule 8 of the module doc).

**Acceptance criteria:** Island detection is correct against known topology fixtures; overrides work and are audited; results are reproducible on re-request.

**Dependencies:** Phase 4 (PSS/E Integration data), Phase 2 (substations).

**Risks:** Graph algorithm correctness at realistic national-grid scale; reuse Phase 4's async job pattern rather than inventing a second one.

**Codex implementation prompt outline:** "Implement Network Model per `docs/architecture/network-model-module.md` in full. The architectural decoupling test in §16 (no table in this module has a foreign key into any scheme module's schema) is the single most important test in this phase — this module must remain reusable by future topology-aware modules without modification. Reuse Phase 4's Redis/RQ setup for heavy graph computation; do not stand up a second job queue."

---

## Phase 6 — UFLS

**Objective:** Implement the first Defence Scheme module — the validated template every later scheme module follows.

**Architecture documents involved:** [ufls-module.md](ufls-module.md).

**Backend deliverables:** `UflsScheme`/`UflsSchemeVersion`/`UflsStage`/`UflsLoadBlock`/`UflsDirectAssignment`/`UflsPocketAssignment`(+`Substation`)/`UflsChangeReason`/audit log; full Canonical Version Lifecycle service logic (Draft→Under Review→Approved→Active→Superseded→Archived, single-active-per-scheme, atomic auto-supersede); recommended-MW resolution calling Phase 4's PSS/E Integration; pocket-assignment construction calling Phase 5's Network Model; **Relay Capability Verification calling Phase 3.6's Automatic Load Shedding Functionality Registry** — Selection of Shedding Actions must call `is_ufls_capable`/the candidate-search interfaces (module document §13) for every candidate bay before it may be selected (01-engineering-philosophy.md §5 Step 5); a load that cannot be answered "yes" is not selectable. This is a **real** call from Phase 6 onward — ALSF is already complete, so no stub is needed here, unlike Cross-Scheme Compliance below. **Sensitive Customer Review calling the Sensitive Customer Registry (Phase 3.7)** — every candidate load must also be checked for policy exclusion (01-engineering-philosophy.md §5 Step 4) before Selection of Shedding Actions, calling `has_sensitive_facility`/the candidate-facing read interfaces per [`sensitive-customer-registry-implementation-spec.md`](sensitive-customer-registry-implementation-spec.md) §9. This is expected to be a **real** call, not a stub, since Phase 3.7 is required to be completed before Phase 6 begins (see Phase 3.7's own sequencing note above). The stub-then-real fallback used for Cross-Scheme Compliance below (a swappable client, always "not excluded" until the real registry exists) remains available only as a contingency if Phase 3.7's completion has genuinely slipped past Phase 6's start — it is not the planned path, and its use should be flagged in review as a deviation from the required sequencing, not treated as routine. **`checkCompliance` called against a stub Cross-Scheme Compliance client** implementing the exact interface contract from [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md) §13 (§5 of this document) — always returns `blocks_transition=false`, zero findings, until Phase 10.

**Frontend deliverables:** Scheme version list/manager; the stage/assignment designer (the largest UI build in this plan, architecturally mirroring the legacy MVP's `LoadSheddingDesigner` complexity — built here, then adapted for Phases 7–8 per §3); reviewer/comparison view; change-reason submission UI.

**Database deliverables:** Per §11 of the module doc. No assignment or capability data is duplicated from Automatic Load Shedding Functionality Registry or Sensitive Customer Registry into UFLS's own tables — both are consulted live via service interfaces (CLAUDE.md A1), never copied.

**Tests required:** Single-Active-version-per-scheme; atomic activate-and-supersede; Approved/Active immutability; Rule 7 (direct/pocket overlap) and Rule 8 (excluded ownership) enforcement; MW capture-at-approval correctness, including verification that no residual live dependency on PSS/E Integration or Network Model remains after capture; a candidate lacking UFLS capability is correctly rejected at Selection of Shedding Actions; the stub compliance client's contract shape (not its business logic, which doesn't exist yet).

**Acceptance criteria:** A full Draft → Under Review → Approved → Active workflow completes end to end against real Phase 4/5 data and real Phase 3.6 capability data, gated by the stub compliance client.

**Dependencies:** Phase 5, Phase 4, Phase 3.6 (Automatic Load Shedding Functionality Registry — real, not stubbed), Phase 3.7 (Sensitive Customer Registry — **required**, real, not stubbed; see Phase 3.7's own sequencing note), Phase 2, Phase 1.

**Risks:** The stub pattern itself is the highest-leverage risk in this phase — if implemented loosely (e.g. inline rather than behind a real, swappable interface), Phase 10's cutover will require unplanned rework. The same risk applies to any Phase 3.7 stub used here, for the identical reason. Frontend designer complexity is this plan's single largest UI undertaking.

**Codex implementation prompt outline:** "Implement UFLS per `docs/architecture/ufls-module.md` in full — this is the template every later scheme module (UVLS, EMLS) will structurally follow, so implement it precisely, not provisionally. Call Phase 3.6's Automatic Load Shedding Functionality Registry (`is_ufls_capable`, candidate-search) for real at Selection of Shedding Actions — it is already built, not stubbed. Implement `checkCompliance` calls at Submit for Review, Approval, and Activation exactly per `docs/architecture/cross-scheme-compliance-module.md` §13's interface contract, but backed by a stub implementation (always `blocks_transition=false`, zero findings) injected via dependency injection — this stub will be swapped for the real Cross-Scheme Compliance module in Phase 10 without any change to UFLS's own code; implement the seam accordingly. Call Phase 3.7's Sensitive Customer Registry (`has_sensitive_facility`) for real — it is required to already be built by this point, not stubbed. MW is never persisted during Draft/Under Review — it is resolved live and captured exactly once at Approval (§7.6)."

---

## Phase 7 — UVLS

**Objective:** Implement the second Defence Scheme module, validating that UFLS's pattern generalizes.

**Architecture documents involved:** [uvls-module.md](uvls-module.md).

**Backend deliverables:** Structurally identical to Phase 6, adapted per [uvls-module.md](uvls-module.md) §7.1's comparison table — region-scoped stages (`region_scope_id`), `voltage_threshold_pu` instead of `frequency_threshold_hz`, live bus-voltage-magnitude consumption alongside recommended MW, pocket assignment treated as a rare/secondary mechanism rather than primary; same stub compliance client pattern as Phase 6. **Relay Capability Verification calling Phase 3.6's Automatic Load Shedding Functionality Registry, symmetric to Phase 6** — Selection of Shedding Actions must call `is_uvls_capable`/the candidate-search interfaces (module document §13) for every candidate bay, using the `UVLS` scheme type, not `UFLS`. Real call, no stub — identical reasoning to Phase 6. **Sensitive Customer Review calling the Sensitive Customer Registry (Phase 3.7)**, same as Phase 6 — a **real** call, expected by this point since Phase 3.7 is required to precede Phase 6.

**Frontend deliverables:** Adapt (not rebuild) Phase 6's designer components: add region-scope selection, add voltage-magnitude display, remove nothing from the underlying component architecture.

**Database deliverables:** Per §11 of the module doc — note the region-scoped uniqueness/ordering constraints, materially different from UFLS's simpler version-wide ordering. No assignment or capability data is duplicated from Automatic Load Shedding Functionality Registry or Sensitive Customer Registry, same as Phase 6.

**Tests required:** All Phase 6-equivalent tests (including the UVLS-capability-rejection equivalent), plus the region-scoped threshold monotonicity test explicitly flagged as higher-risk in [uvls-module.md](uvls-module.md) §18 (verifying stages in different regions are correctly *not* compared against each other).

**Acceptance criteria:** Full lifecycle workflow works with region-scoped stages; voltage-magnitude recommendation displays correctly; region-scoped ordering validation is correct; UVLS capability (not UFLS) is the flag checked at Selection of Shedding Actions.

**Dependencies:** Phase 6 (template + reusable frontend components), Phase 5, Phase 4, Phase 3.6 (Automatic Load Shedding Functionality Registry — real, not stubbed), Phase 3.7 (Sensitive Customer Registry — **required**, real, not stubbed, same as Phase 6), Phase 2, Phase 1.

**Risks:** Region-scoped validation logic is materially more complex than UFLS's version-wide equivalent — prioritize that specific test.

**Codex implementation prompt outline:** "Implement UVLS per `docs/architecture/uvls-module.md` in full, reusing Phase 6's UFLS implementation and frontend designer components wherever §7.1 of uvls-module.md marks something 'shared structurally' — do not rebuild from scratch. Call the Automatic Load Shedding Functionality Registry's `is_uvls_capable` (not `is_ufls_capable`) at Selection of Shedding Actions, reusing Phase 6's real integration pattern. Pay particular attention to §7.2's region-scoping and §9 rule 4's region-scoped monotonicity rule, which is a materially different (and higher-risk) validation than UFLS's simpler version-wide threshold ordering."

---

## Phase 8 — EMLS

**Objective:** Implement the third Defence Scheme module — no automatic trigger, priority-ordered.

**Architecture documents involved:** [emls-module.md](emls-module.md).

**Backend deliverables:** `EmlsScheme`/`EmlsSchemeVersion`/`EmlsPriorityGroup`/`EmlsShedBlock`/`EmlsDirectAssignment`/`EmlsPocketAssignment`(+`Substation`)/`EmlsChangeReason`/audit log — **no threshold or time-delay fields at all**, `priority_order` uniqueness only (no monotonicity check, since no physical quantity exists to compare); pocket assignment treated as a routine, primary-tier mechanism (unlike UVLS); same stub compliance client pattern, implemented exactly as Phase 6/7, with the explicit design intent (not yet exercisable until Phase 10) that `Prohibited`-severity Rule 2 findings will hard-block EMLS with no weakening. **EMLS must NOT call the Automatic Load Shedding Functionality Registry, and must acquire no automatic-load-shedding capability prerequisite of any kind** — EMLS is manually invoked and may be assigned to any bay at the scheme designer's discretion (module document §4, §9 rule 4; EDR-003); a bay's automatic-shedding capability is simply irrelevant to a manual scheme. This is a hard exclusion, not a deferred integration — do not add a stub for it, now or in a later phase. **Sensitive Customer Review calling the Sensitive Customer Registry (Phase 3.7) still applies** — that workflow step is scheme-agnostic (03-system-workflow.md), so EMLS's own Selection of Shedding Actions must still check policy exclusion, a **real** call, expected by this point since Phase 3.7 is required to precede Phase 6.

**Frontend deliverables:** Priority-group-based designer, adapted from Phase 6/7's components — remove threshold/delay UI, add `invocation_guidance` display, keep pocket-assignment UI prominent (unlike its de-emphasis in Phase 7).

**Database deliverables:** Per §11 of the module doc.

**Tests required:** Priority-order uniqueness (not monotonicity — a test confirming no threshold-comparison logic is accidentally applied); MW capture-at-approval; the stub client's contract shape. **Note:** the real "`Prohibited` always hard-blocks EMLS" behaviour cannot be meaningfully tested until Phase 10's real Cross-Scheme Compliance implementation exists — this phase can only verify the stub's shape, not that specific business rule's actual enforcement.

**Acceptance criteria:** Full lifecycle workflow works with priority groups; no threshold/delay concept appears anywhere in the schema or API contract.

**Dependencies:** Phase 6, Phase 5, Phase 4, Phase 3.7 (Sensitive Customer Registry — **required**, real, not stubbed, same as Phase 6/7), Phase 2, Phase 1. **Deliberately not** Phase 3.6 (Automatic Load Shedding Functionality Registry) — see the hard exclusion above.

**Risks:** The Rule 2 no-weakening policy question remains an open ADR item ([emls-module.md](emls-module.md) §18/closing summary) — implement the module *as designed* (no weakening), but flag in PR review that this behaviour is contingent on that ADR's eventual resolution. A reviewer unfamiliar with EDR-003's scope discipline could mistakenly "complete the pattern" by wiring EMLS to the Automatic Load Shedding Functionality Registry, by analogy with Phase 6/7 — flag this explicitly in PR review as a rejection criterion, not just an omission to fix.

**Codex implementation prompt outline:** "Implement EMLS per `docs/architecture/emls-module.md` in full. This module has no frequency or voltage threshold and no time delay — do not add these fields even as unused/nullable columns; their absence is structural, not incidental (§7.2 of emls-module.md). Pocket/island assignment is a routine, primary-tier mechanism here, unlike UVLS — do not apply UVLS's rare-usage treatment. Do NOT call the Automatic Load Shedding Functionality Registry or add any automatic-capability check — EMLS has no such prerequisite, unlike UFLS/UVLS in Phase 6/7. Implement the stub compliance client exactly as in Phase 6/7. Call Phase 3.7's Sensitive Customer Registry for real — it is required to already be built by this point, not stubbed."

---

## Phase 9 — Critical Infrastructure

**Objective:** Implement critical-asset classification, closing Rule 2's data dependency.

**Architecture documents involved:** [critical-infrastructure-module.md](critical-infrastructure-module.md).

**Backend deliverables:** `CriticalCategory`/`CriticalSource`/`CriticalityLevel`/`CriticalAsset`/`CriticalAssetSubstation`/audit log; batch `getCriticalityForSubstations(substation_ids[])` service interface, including the point-in-time (`as_of_timestamp`) variant.

**Frontend deliverables:** Critical asset management screens; UI enforcement of the stricter read-access tier recommended in the module doc §15.

**Database deliverables:** Per §11 of the module doc.

**Tests required:** `restriction_type`/`condition_description` pairing enforcement; no-duplicate-concurrent-link constraint; the no-foreign-key-into-any-scheme-module architectural test; point-in-time query correctness.

**Acceptance criteria:** Critical asset CRUD works; batch and point-in-time lookups work; a `ConditionallyAllowed` asset without a condition description is rejected.

**Dependencies:** Phase 2 (substations), Phase 1 (IAM, for the distinct stricter-tier permission).

**Risks:** The stricter human read-access tier (§15) must actually be wired to a distinct IAM permission code, not merely documented — verify this explicitly in review.

**Codex implementation prompt outline:** "Implement Critical Infrastructure per `docs/architecture/critical-infrastructure-module.md` in full. Implement the `restriction_type` model (Prohibited/ConditionallyAllowed/Unrestricted) precisely per §7.4 — this is the data Cross-Scheme Compliance's Rule 2 will consume in Phase 10. Register a distinct, stricter read-access permission for this module's data, separate from the general Viewer role's baseline read permissions, per §15."

---

## Phase 10 — Cross-Scheme Compliance

**Objective:** Implement real Rule 1/2 enforcement, and cut over Phases 6–8's stub compliance client to the real implementation.

**Architecture documents involved:** [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md), [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md).

**Backend deliverables:** `ComplianceRuleConfig`/`ComplianceCheckRun`(+`SchemeVersion` child)/`ComplianceFinding`/audit log; `checkCompliance`/`runAdHocComplianceCheck`/`queryComplianceHistory`/`getComplianceSummary`; the real Rule 1 and Rule 2 algorithms (§13 of the module doc); **the stub cutover** — replace the dependency-injected stub client in UFLS, UVLS, and EMLS with the real implementation, with zero changes to any scheme module's own code beyond the injection wiring itself.

**Frontend deliverables:** Compliance rule configuration admin screen; findings display integrated into each scheme module's own approval flow; a compliance summary view (feeding Phase 11's dashboard).

**Database deliverables:** Per §11 of the module doc.

**Tests required:** Rule 1 and Rule 2 algorithm correctness against fixtures spanning UFLS, UVLS, and EMLS together; checkpoint-driven blocking behaviour (Draft/Submit-for-Review never block; Approval/Activation hard-block on `Block`-severity findings); **a dedicated regression test proving the stub-to-real cutover required zero changes to UFLS/UVLS/EMLS's own code** — this is this phase's single most important acceptance test, validating the entire Phase 6–10 sequencing strategy; a `Failed` check run correctly treated as non-passing (fail-closed, never silently compliant); the circular-call-safety architectural test (§9 rule 10 of the module doc — `getProtectedAssignments` must never call back into this module).

**Acceptance criteria:** Real Rule 1/2 enforcement now blocks or warns correctly across all three scheme modules; the cutover regression test passes; `Prohibited`-severity Rule 2 findings hard-block EMLS with no weakening, exactly as designed.

**Dependencies:** Phase 6, Phase 7, Phase 8 (their stub interface contracts must already exist and be precise), Phase 9 (real Critical Infrastructure data for Rule 2).

**Risks:** The highest-integration-risk phase in this entire plan. If Phase 6's stub interface contract was implemented loosely, this cutover could require unplanned scheme-module changes, directly violating this phase's central acceptance goal — review Phase 6's stub implementation with this cutover explicitly in mind before starting this phase.

**Codex implementation prompt outline:** "Implement Cross-Scheme Compliance per `docs/architecture/cross-scheme-compliance-module.md` and `docs/adr/ADR-004-cross-scheme-compliance-mechanism.md` in full. Implement the Rule 1 and Rule 2 algorithms exactly per module doc §13. Then perform the stub cutover: replace the dependency-injected stub `CrossSchemeComplianceClient` in UFLS, UVLS, and EMLS (Phases 6–8) with this module's real implementation, wiring only the dependency injection — do not modify UFLS/UVLS/EMLS's own business logic, service methods, or database schema in any way. Write a dedicated test asserting this: run each scheme module's existing test suite unmodified against the real implementation and confirm it still passes."

---

## Phase 11 — Dashboard and Reporting

**Objective:** Compose read-only interfaces from every prior module into operator-facing visualizations.

**Architecture documents involved:** No dedicated Dashboard module document exists in this series (flagged explicitly in "Architecture Gaps," closing section). This phase's scope is inferred pragmatically from every other module's own already-documented read-only service interfaces: `getConnectivityGraph`/health-check data (Network Model), load analytics-style aggregation (PSS/E Integration), `getComplianceSummary`/`queryComplianceHistory` (Cross-Scheme Compliance), criticality lookups (Critical Infrastructure), each scheme module's current-Active-version query interface.

**Backend deliverables:** No new persisted data — Dashboard does not own a schema of its own, consistent with every module's own "Dashboard reads X read-only, never owns X's data" statement. A thin, optional aggregation endpoint (or a small number of them) may compose several modules' service interfaces into one response for frontend convenience, but stores nothing.

**Frontend deliverables:** Network connectivity/topology map (ECharts geo); load analytics charts; compliance summary view; data-quality health-check views (e.g. unmatched-substation coverage, mirroring the legacy MVP's `missing-substations` capability, already flagged as worth preserving in [psse-integration-module.md](psse-integration-module.md)'s own discovery-report grounding).

**Database deliverables:** None.

**Tests required:** Aggregation-endpoint correctness (composing multiple modules' data accurately); frontend rendering tests against representative data.

**Acceptance criteria:** Dashboard renders real, correct data sourced from every module built in Phases 1–10.

**Dependencies:** Phases 1–10 (all of them).

**Risks:** Scope ambiguity from the missing dedicated architecture document — mitigated by scoping this phase strictly to interfaces *already* documented elsewhere, inventing no new business logic or data ownership here under any circumstance.

**Codex implementation prompt outline:** "Implement Dashboard and Reporting by composing only the read-only service interfaces already documented in `docs/architecture/psse-integration-module.md` §13, `network-model-module.md` §13, `ufls-module.md`/`uvls-module.md`/`emls-module.md` §13, `critical-infrastructure-module.md` §13, and `cross-scheme-compliance-module.md` §13. Do not introduce new backend data ownership, new business rules, or new authoritative calculations of any kind — CLAUDE.md A12 applies to this phase as strictly as to any frontend work. If a desired dashboard view requires data no existing service interface provides, stop and flag it for an architecture-layer decision rather than inventing one."

---

## Phase 12 — Data Migration from Django MVP

**Objective:** Migrate real historical master data into the completed schema.

**Architecture documents involved:** The Codebase Discovery Report, [substation-registry.md](substation-registry.md), [equipment-registry-module.md](equipment-registry-module.md), [critical-infrastructure-module.md](critical-infrastructure-module.md).

**Backend deliverables:** One-off, standalone data migration scripts (not Alembic schema migrations) for substation master data, best-effort equipment data, and critical asset data — per the detailed strategy in §7 of this document. Scheme/version data is explicitly excluded from automated migration.

**Frontend deliverables:** None required; an optional minimal migration-status view is acceptable but not mandatory.

**Database deliverables:** No new schema — populates existing Phase 2/3/9 tables with real data.

**Tests required:** Row-count and referential-integrity validation post-import; mnemonic-uniqueness verification against the full imported dataset; a dry-run/preview mode exercised and reviewed before any production commit.

**Acceptance criteria:** Substation data matches the source fixture's row count within a documented, explained tolerance (unresolved rows are listed, not silently dropped); no referential-integrity violations; scheme data is confirmed *not* migrated, with engineers notified to re-author current schemes fresh.

**Dependencies:** Phases 1–9 (every master-data-adjacent module must exist).

**Risks:** Data-quality issues accumulated over years in the source fixture surfacing unexpectedly during migration — mitigated by a mandatory dry-run/preview stage with human review before any commit to production data, mirroring the review-gate pattern already established for PSS/E imports in Phase 4.

**Codex implementation prompt outline:** "Write standalone data migration scripts (not schema migrations) to import the legacy MVP's substation fixture data into Substation Registry, equipment data into Equipment Registry, and critical asset data into Critical Infrastructure, per the strategy in `docs/architecture/implementation-plan.md` §7. Implement a mandatory dry-run mode that reports match/mismatch/unresolved counts without writing anything, reviewed by a human before any commit run. Do not attempt to migrate `LoadSheddingVersion`/`Stage`/bay data — that is explicitly excluded per §7; scheme data is re-authored fresh by engineers."

---

## Phase 13 — Testing, Hardening, and Release Preparation

**Objective:** Close remaining cross-cutting gaps and prepare for release.

**Architecture documents involved:** All.

**Backend deliverables:** The shared Rule 7/8 (direct/pocket overlap, excluded ownership) validation utility flagged as worth factoring out once three scheme modules exist ([ufls-module.md](ufls-module.md) §17/§18) — implemented now that UFLS, UVLS, and EMLS all exist; security hardening (rate limiting on authentication, TLS enforcement verification, audit-log access-control verification); performance testing for Phase 4/5's async jobs at realistic data volume.

**Frontend deliverables:** Accessibility pass; error-state and empty-state polish across all module UIs; cross-browser verification.

**Database deliverables:** Index review and tuning based on realistic data volume from Phase 12's migrated dataset.

**Tests required:** Full end-to-end integration suite spanning every module; load/performance testing against realistic volumes; a formal security review (the `security-review` skill available in this environment is explicitly recommended here).

**Acceptance criteria:** Full regression suite green; security review complete with findings triaged; CI/CD pipeline hardened beyond Phase 0's minimal viable pipeline (§9); the shared Rule 7/8 utility is adopted by all three scheme modules with no behavioural regression.

**Dependencies:** Everything (Phases 0–12).

**Risks:** This phase can expand indefinitely without a fixed scope — mitigated by treating the acceptance criteria above as a closed, pre-agreed checklist, not an open-ended hardening exercise.

**Codex implementation prompt outline:** "Factor UFLS/UVLS/EMLS's duplicated Rule 7/8 (direct-pocket-overlap, excluded-ownership) validation logic into one shared utility, consumed by all three modules with no behavioural change — verify via each module's existing test suite passing unmodified. Run the `security-review` skill against the full codebase and triage findings. Finalize the CI/CD pipeline per the release checklist in `docs/architecture/implementation-plan.md` §9/§13. Do not introduce new business features in this phase."

---

## Recommended First Codex Prompt for Phase 0

> Implement Phase 0 (Repository Foundation) of `docs/architecture/implementation-plan.md`. Read `docs/architecture/system-overview.md` §3–§6 and `docs/adr/ADR-001-modular-monolith-and-module-communication.md` first. Create the backend FastAPI application skeleton and the frontend Vite+React+TypeScript skeleton exactly per `implementation-plan.md` §1 (repository structure) and §4 (Docker Compose target — Postgres + backend + frontend only, no Redis). Create empty module packages for every module named in `implementation-plan.md` §2, containing only `__init__.py`. Initialize Alembic with a single no-op revision. Add a `/health` endpoint on the backend and a placeholder app shell on the frontend. Set up the CI pipeline per `implementation-plan.md` §9 (lint, type-check, test, migration check, build). Implement no business logic, no data models beyond what Alembic needs to establish its migration chain, and no API endpoints beyond `/health`. Do not modify `.claude/CLAUDE.md` or any file under `docs/`. When finished, list every file created and confirm `docker compose up`, `alembic upgrade head`, and the CI pipeline all succeed.

## Recommended Review Checklist After Phase 0

- [ ] `docker compose up` brings up all three services without error.
- [ ] Backend `/health` returns `200` with no database dependency failures.
- [ ] Frontend loads the app shell with no console errors.
- [ ] `alembic upgrade head` runs cleanly against a fresh database.
- [ ] Every module package listed in §2 exists and is empty (no premature business logic).
- [ ] CI pipeline (lint, type-check, test, migration check, build) is green on the PR.
- [ ] No `.claude/CLAUDE.md` or `docs/` file was modified.
- [ ] Repository structure matches §1 exactly — deviations are flagged for architecture-layer discussion, not silently accepted.
- [ ] No Django-specific idiom is present anywhere (no fat models, no implicit signal-based logic, no auto-migration-and-commit pattern).

## Architecture Gaps That Must Be Resolved Before Implementation Begins

**None of the items below block Phases 0–10.** Every module needed for those phases is fully specified in its own architecture document. The items below are genuine open questions this series has flagged, categorized by whether they are true blockers or safely deferrable:

| Item | Blocking? | Notes |
|---|---|---|
| `Superseded → Active` reactivation (A3 amendment) — [ufls-module.md](ufls-module.md) §8 | Not blocking | Forward-only lifecycle works without it; reactivation is an additive future transition |
| Cross-Scheme Compliance per-scheme-pair enforcement granularity — [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) | Not blocking | Global-per-rule default is sufficient for Phase 10 |
| Region reference data sufficiency for UVLS long-term | Not blocking | Works as designed for Phase 7; escalation path already documented |
| Equipment-level migration for scheme modules — [equipment-registry-module.md](equipment-registry-module.md) §7.8 | Not blocking, but **not included in this plan** | Requires its own ADR before being undertaken; Phases 6–8 correctly use the `equipment_reference` free-text placeholder by design |
| Rule 2 no-weakening policy for EMLS — [emls-module.md](emls-module.md) §18 | Not blocking | Phase 8 implements it as designed; the ADR only matters if the Project Owner later decides to change the default |
| IAM segregation-of-duties mandatory-vs-recommended — [iam-module.md](iam-module.md) §18 | Not blocking | Structural support (distinct roles) ships in Phase 1 regardless of the policy answer |
| External identity provider selection — [iam-module.md](iam-module.md) §17 | Not blocking | Phase 1 ships with local authentication; federation is additive |
| Credential/session security policy specifics | **Minor practical decision needed**, not a full ADR | Codex needs *some* concrete choice (e.g. Argon2/bcrypt password hashing, server-side session cookies) to build Phase 1 — reasonable industry-standard defaults are sufficient; this does not require Project Owner sign-off before starting |
| **Dashboard module has no dedicated architecture document** | **Recommend resolving before Phase 11**, not before Phase 0 | A lightweight design note (not necessarily a full A8 document) scoping Phase 11 more precisely than "compose whatever already exists" would reduce risk at that specific phase; does not block Phases 0–10 |
| ~~Sensitive Customer Registry has no architecture document~~ — **fully resolved.** Architecture (EDR-008, ADR-012, module document), a full implementation specification, and the implementation itself (Phase 3.7) are all complete. | Not blocking — complete | No longer a gap of any kind; retained here only as a historical record of this item's resolution path (architecture discovery → implementation specification → implementation, per CLAUDE.md §24). |

**Conclusion:** implementation may begin at Phase 0 immediately. One item remains worth addressing before its own dependent phase specifically (rather than before the plan as a whole): Dashboard's missing architecture document (recommended sometime during Phases 6–10, well ahead of Phase 11). Sensitive Customer Registry is now fully complete (Phase 3.7) and is no longer a precondition risk for Phase 6 — UFLS, UVLS, and EMLS can consume its real service contract from their own first commit, exactly as ALSF (Phase 3.6) already allows for Relay Capability Verification.
