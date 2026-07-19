# UFLS Module Architecture

Status: Active
Supersedes: [ufls-module.md](ufls-module.md) §7 (lifecycle), §8 (approval-time capture), and its `UflsLoadBlock` model. §1-6, §9 (minus lifecycle), §10, §12-18 of that document remain authoritative background where not contradicted here.

Follows the canonical template ([CLAUDE.md](../../.claude/CLAUDE.md) A8).

---

## 1. Module Overview

UFLS (Under-Frequency Load Shedding) is the first concrete Defence Scheme module built on the **Shared Defence-Scheme Platform** ([shared-scheme-platform-implementation.md](shared-scheme-platform-implementation.md)) — the first real workload validating that shared kernel's abstractions. It is a dedicated module (`backend/app/modules/ufls/`), owning its own concrete persistence tables and engineering behaviour, composing the shared platform rather than duplicating it.

## 2. Purpose

Allow engineers to create, configure, validate, publish, inspect, and preserve versioned UFLS engineering schemes. GridDefence does not calculate the required UFLS shedding quantum or automatically design a scheme — external engineering studies determine the quantum, stages, thresholds, delays, allocation strategy, and acceptance criteria. GridDefence records, manages, validates, audits, and continuously evaluates that external decision.

> GridDefence detects engineering impacts. Engineers make engineering decisions.

## 3. Responsibilities

- Own UFLS Scheme lineage identity and sequential, per-lineage version numbering.
- Own the concrete UFLS Scheme Version lifecycle (Draft/Published/Superseded/Entered in Error), composing `scheme_platform.SchemeVersionLifecycleService` rather than reimplementing it.
- Own UFLS Stage structure (per-version, referencing a Stage Setting Registry `StageSetting`, which itself may own one or more `StageSettingTrigger` operating criteria — [ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md)) and its external-study `target_mw`.
- Own UFLS Direct Assignments (Transformer Terminals) and Boundary Pocket Assignments (Circuit Terminal opening-point sets), both attached directly to a stage.
- Validate structural publication prerequisites and compute ALSF-capability / Sensitive-Customer findings for its own assignments.
- Orchestrate publication (Findings and Publication Governance) and the underlying lifecycle transition (Shared Platform) as one transaction.
- Publish platform events for meaningful lifecycle/engineering changes.
- Own its own audit log (`ufls_audit_log`).

## 4. Non-Responsibilities

- Does not calculate required shedding quantum, design stage structure, or select loads automatically.
- Does not implement UVLS or EMLS behaviour.
- Does not own Substation, Transformer Terminal, Circuit Terminal, Stage Setting, ALSF, or Sensitive Customer data — all referenced live through their own service layers (CLAUDE.md A1).
- Does not store a captured/approved MW snapshot anywhere — current MW is always resolved live (§7).
- Does not silently redesign or mutate a Published version when new operational/topology data arrives — see §11.
- Does not implement Cross-Scheme Compliance (that module does not exist yet); no stub is called, since no faithful interface contract exists to stub against.

## 5. Owned Entities

`UflsScheme`, `UflsSchemeVersion` (composes `scheme_platform.SchemeVersionMixin`), `UflsStage`, `UflsDirectAssignment`, `UflsPocketAssignment`, `UflsPocketAssignmentOpeningPoint`, `UflsAuditLog`.

## 6. Referenced Entities

`Substation`/`SubstationVoltageYard` (Substation Registry), `TransformerTerminal`/`CircuitTerminal` (Equipment Registry), `StageSettingSet`/`StageSetting` (Stage Setting Registry), Automatic Load Shedding Functionality (via `is_ufls_capable`), Sensitive Customer Registry (via `get_sensitive_facilities_for_transformer_terminals`), `User` (IAM, audit/accountability), `TopologyVersion`/`LoadSnapshot` identifiers (PSS/E Integration — opaque traceability only, no FK).

## 7. Domain Model

Per [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md): a **Scheme** is a stable lineage identity; a **Scheme Version** is one versioned, immutable-once-Published engineering document within that lineage. A Stage belongs to exactly one version and references exactly one `StageSetting` from the version's own selected, Published `StageSettingSet` (unique per version). An assignment (Direct or Boundary Pocket) belongs to exactly one stage.

**A `StageSetting` may own more than one `StageSettingTrigger` — an independent frequency-time operating criterion each ([ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md)).** `UflsStage.stage_setting_id` continues to reference the stage itself, never an individual trigger; selecting a stage gives the `UflsStage` access to every trigger configured under it (`UflsStageDetail.triggers`, `to_stage_detail`). No assignment is duplicated because a stage carries more than one trigger — the assignment belongs to the stage, exactly as it always did.

**No `UflsLoadBlock` grouping layer** — superseded. Assignments attach directly to a stage.

**No captured/approved MW field anywhere.** `UflsStage.target_mw` is always an external-study, engineer-entered value (never computed, never scaled). Current/actual MW contributed by a stage's assignments is always resolved live (via a future Continuous Evaluation provider, §11) — never stored as Scheme Data. This supersedes [ufls-module.md](ufls-module.md) §7.6's capture-at-Approval design entirely.

**Boundary Pocket Assignments** store only the selected `CircuitTerminal` opening-point id set (§9 below) — no derived substation set, no topology reference, no MW is stored on the assignment itself. Derived evidence (the isolated island, at the moment of Publish) is captured only in Findings and Publication Governance's own `PublicationRecord`, never on the assignment.

## 8. Lifecycle / State Model

Exactly ADR-015's ratified four-state model, via `scheme_platform.SchemeVersionLifecycleService`:

```text
Draft → Published
Draft → Entered in Error
Published → Superseded (automatic, atomic, on a new Publish for the same lineage)
Published → Entered in Error
```

No Under Review, no Approved distinct from Published, no Archived — this deliberately does not match [ufls-module.md](ufls-module.md) §7's original six-state description, per CLAUDE.md's own precedence rules (Accepted ADRs > Module Architecture Documents) and this module's own instructions to preserve ratified engineering philosophy over literal task wording.

- Draft: fully editable (metadata, stages, assignments) and deletable.
- Published: immutable. Publishing atomically supersedes the scheme's own previously Published version (same lineage only — never cross-lineage).
- Superseded / Entered in Error: terminal for that transition path; queryable, never mutated. Reactivation of a Superseded version is explicitly unresolved/unimplemented (per Shared Platform's own open question).

## 9. Business Rules

1. Version numbers are sequential per scheme lineage (`get_next_version_number`), never global.
2. A version's stages must reference `StageSetting`s belonging to that version's own selected `StageSettingSet`; the set's `scheme_type` must be `"UFLS"` (`StageSettingSetSchemeTypeMismatchError`) and its status must be `PUBLISHED` at the moment of selection (`StageSettingSetNotPublishedError`) — validated in `_validate_stage_setting_set`, never deferred to the Publish-time `UFLS_STAGE_SETTING_SET_PUBLISHED` prerequisite alone ([ADR-024](../adr/ADR-024-stage-setting-set-draft-deletion.md), correcting an earlier divergence from [stage-setting-set-architecture.md](stage-setting-set-architecture.md) §6's own stated rule).
3. A Transformer Terminal may be Direct-Assigned at most once per Scheme Version (`uq_ufls_direct_assignment_terminal_per_version`).
4. A substation may not simultaneously be Direct-Assigned and appear within any Boundary Pocket's own derived isolated-island substation set, within the same version (`DirectAndPocketOverlapError`).
5. A Boundary Pocket Assignment's opening-point selection must form a genuinely effective boundary (`NetworkModelService.evaluate_boundary().is_boundary_effective`); an ineffective selection can never be committed (`IneffectiveBoundaryError`) — per [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §7.
6. A Transformer Terminal is ineligible for Direct Assignment if its substation carries an excluded grid-owner classification (`IPP`, `LSS`) or an ineligible operational status (`DECOMMISSIONED`, `RETIRED`, `ENTERED_IN_ERROR`) — `SubstationNotEligibleForAssignmentError`.
7. Only a Draft version may have its stages, assignments, or metadata edited or deleted (`VersionNotEditableError`).
8. Publishing a new version always, atomically, supersedes the scheme's own currently Published version (if any) — never any other lineage's.
9. Copying a version (`copied_from_version_id`) copies stage/assignment structure only — never target MW, publication status, acknowledgements, or historical findings (domain model §5).

## 10. Validation Rules

Structural publication prerequisites (`compute_prerequisites`, reusing `PublicationPrerequisiteResult` — no second validator mechanism):

| Code | Meaning |
|---|---|
| `UFLS_STAGE_SETTING_SET_SELECTED` | A Stage Setting Set has been selected. |
| `UFLS_STAGE_SETTING_SET_PUBLISHED` | The selected set is itself Published. |
| `UFLS_AT_LEAST_ONE_STAGE` | At least one stage exists. |
| `UFLS_STAGE_STRUCTURE_COMPLETE` | Every setting in the selected set has a corresponding stage in this version. |
| `UFLS_STAGE_TARGET_MW_SET` (per stage) | The stage has a target MW. |
| `UFLS_STAGE_HAS_ASSIGNMENT` (per stage) | The stage has at least one assignment (direct or pocket). |

Any `passed=False` unconditionally blocks publication (ADR-015; findings-and-publication-governance-architecture.md §5).

## 11. Database Design

Migration `0022_ufls` (`backend/alembic/versions/0022_ufls.py`). Seven tables: `ufls_scheme`, `ufls_scheme_version`, `ufls_stage`, `ufls_direct_assignment`, `ufls_pocket_assignment`, `ufls_pocket_assignment_opening_point`, `ufls_audit_log`. No table for `scheme_platform.SchemeVersionMixin` (`__abstract__ = True`).

- UUID primary keys throughout (CLAUDE.md A5).
- `lifecycle_status` enforced via CHECK constraint (`ck_ufls_scheme_version_lifecycle_status`), not a DB enum, per established convention.
- All cross-module foreign keys (`transformer_terminal`, `circuit_terminal`, `stage_setting_set`, `stage_setting`, `user`) are `ON DELETE RESTRICT`.
- `topology_version_id`/`load_snapshot_id` on `ufls_scheme_version` are deliberately bare UUID — opaque traceability only, no FK (CLAUDE.md A2/F2 — Scheme Data must not create a structural dependency on an Operational Snapshot module beyond what's needed to trace back to it).
- Uniqueness: `(scheme_id, version_number)`, `(scheme_version_id, stage_setting_id)`, `(scheme_version_id, transformer_terminal_id)`, `(ufls_pocket_assignment_id, circuit_terminal_id)`.
- Verified: upgrade/downgrade both apply cleanly against a real PostgreSQL database (full migration chain 0001→0022, `downgrade -1`, re-`upgrade head`), not merely SQLite.

## 12. API Contract

Router `backend/app/modules/ufls/router.py`, prefix `/api/v1/ufls`. DTOs only (`schemas.py`) — no ORM object is ever returned. All mutation endpoints require `ufls.manage`, except `publish` (`ufls.publish`) and `enter-in-error` (`ufls.enter_in_error`) — each its own permission, since a user trusted to edit a Draft is not assumed to also be trusted to publish or correct it (mirrors `stage_setting_registry`'s own precedent). Read endpoints require only authentication.

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/schemes` | List / create scheme lineages |
| GET | `/schemes/{id}` | Scheme detail |
| GET/POST | `/schemes/{id}/versions` | List versions / create a Draft (optionally copied) |
| GET/PATCH/DELETE | `/versions/{id}` | Version detail / metadata update / Draft deletion |
| POST | `/versions/{id}/enter-in-error` | Mark Entered in Error |
| GET/POST | `/versions/{id}/stages` | List / add stages |
| PATCH/DELETE | `/stages/{id}` | Update / remove a stage |
| GET/POST | `/stages/{id}/direct-assignments` | List / add Direct Assignments |
| PATCH | `/direct-assignments/{id}/move` | Move to another stage |
| DELETE | `/direct-assignments/{id}` | Remove |
| GET/POST | `/stages/{id}/pocket-assignments` | List / add Boundary Pocket Assignments |
| DELETE | `/pocket-assignments/{id}` | Remove |
| GET | `/versions/{id}/summary` | Engineering summary (descriptive only) |
| GET | `/versions/{id}/publication-review` | Read-only prerequisite + finding preview |
| POST | `/versions/{id}/publish` | Publish |

No generic shared-scheme router was created merely to reduce duplication, per this module's own explicit scope boundary.

## 13. Service Interfaces

`UflsService` (Router → Service → Repository → Model). Composes: `scheme_platform.SchemeVersionLifecycleService`, `findings_publication_governance.PublicationRecordService`, `substation_registry.SubstationService`, `equipment_registry.EquipmentRegistryService`, `automatic_load_shedding_functionality.AutomaticLoadSheddingFunctionalityService`, `sensitive_customer_registry.SensitiveCustomerRegistryService`, `stage_setting_registry.StageSettingRegistryService`, `network_model.NetworkModelService`, `continuous_evaluation.ContinuousEvaluationService`, `iam.IAMService`, `reference_data.ReferenceDataRepository`. Never imports another module's repository directly (CLAUDE.md A1).

`UflsEvaluationRequestProvider` (`evaluation.py`) — the first concrete `EvaluationRequestProvider` implementation; see §14.

## 14. Continuous Evaluation Integration

Published version remains a permanent record always; new operational/topology data never alters it. Findings from a future evaluation refresh are informational only — an engineer decides whether to create a new Draft; there is no automatic redesign engine and no automatic new version.

`UflsEvaluationRequestProvider.build_request` fully implements `target_mw` resolution (a direct read of stored, external-study `UflsStage.target_mw` — no calculation). **`current_mw` resolution is deliberately not implemented and documented as deferred**, raising `CurrentMwNotResolvableError`: resolving "current MW for a Transformer Terminal (or a Boundary Pocket's derived island) as of a given Load Snapshot" requires correlating that terminal/substation to a specific bus and summing its load, and no such correlation mechanism exists anywhere in this codebase today — `EquipmentTopologyMap` (PSS/E Integration) is keyed only by `CircuitTerminal`, built for connectivity correlation, not load attribution. Inventing one would be new, unratified cross-module infrastructure this phase's own instructions explicitly forbid.

The provider is **not wired into any production composition root**, because none exists yet: `ContinuousEvaluationService.__init__` still only ever builds its own empty `build_default_provider_registry()` and a no-op `NullAffectedSchemeResolver` — confirmed pre-existing gaps from Shared Platform Sprint 6, not introduced here (the MW tolerance detector's own `build_default_registry` is, symmetrically, never called from `main.py` either). `evaluation.py::register_provider(registry, db)` is the documented, ready-to-call registration point for whenever that composition root is built — calling it today would be safe (an unresolved current_mw raises a clean, recorded `FAILED` projection, the same outcome as today's "no provider registered" path) but was deliberately left uncalled since wiring a shared, request-scoped registry is Continuous Evaluation's own composition-root work, not something one scheme module should invent unilaterally.

## 15. Audit Requirements

`UflsAuditLog` — append-only, owned by this module (CLAUDE.md A4). Records scheme/version/stage/assignment creation, update, removal, lifecycle transitions, with actor and optional change reason. Never modified after write.

## 16. Security Considerations

Permissions (`bootstrap.py`): `ufls.read` (any authenticated user), `ufls.manage` (Engineer+ — Draft creation/editing), `ufls.publish` and `ufls.enter_in_error` (Administrator-only, mirroring `stage_setting_registry`'s own precedent). No UFLS scheme data is seeded — an authorized user creates the first scheme through the ordinary API.

## 17. Testing Requirements

Backend: `app/modules/ufls/tests/test_service.py` (13 tests — sequential per-lineage versioning, Published immutability, Draft-only deletion, Stage Setting Set scheme-type validation, duplicate/overlap/ineffective-boundary assignment rejection, publication prerequisite blocking, atomic same-lineage-only supersession, ALSF/Sensitive-Customer finding computation, engineering summary totals, per-stage assignment listing) plus `backend/tests/test_ufls_api.py` (6 tests — authentication, permission enforcement including the manage-vs-publish distinction, end-to-end scheme/Draft/review/deletion flow). All verified against both SQLite (default) and a real PostgreSQL database (`GRIDDEFENCE_TEST_DATABASE_URL`).

Frontend: `tests/ufls/` (9 tests) — scheme list rendering (empty state, populated rows, permission-gated create form), Draft-editable vs. Published-read-only rendering, publication review (blocking vs. passing prerequisites, findings display, publish-button permission gating).

**Since [ADR-025](../adr/ADR-025-stage-setting-trigger-multiple-operating-criteria.md):** a UFLS stage exposes every trigger associated with its referenced Stage Setting Registry `StageSetting`; selecting Stage 8 gives the stage access to all of Stage 8's own operating criteria without duplicating the assignment; historical Published UFLS data (including each stage's own trigger set at the time) remains fully readable and unaffected by later Stage Setting Registry changes.

## 18. Future Extensions

- Wiring a real `AffectedSchemeResolver` and provider-registry composition root in Continuous Evaluation, then registering `UflsEvaluationRequestProvider` via `register_provider`.
- A genuine Transformer-Terminal/Substation-to-Bus load correlation mechanism, unblocking `current_mw` resolution.
- Cross-Scheme Compliance integration, once that module exists.
- UVLS and EMLS, reusing this module's own structural pattern and the Shared Defence-Scheme Platform.
- A dedicated Equipment Registry terminal picker in the frontend workspace, replacing today's direct-ID-entry inputs.

## 19. Risks and Recommendations

- **Direct-ID-entry assignment inputs** (frontend): the Draft Editor's Direct/Boundary Pocket assignment forms take raw Transformer Terminal / Circuit Terminal UUIDs rather than a searchable picker, since no Equipment Registry frontend search/browse component exists yet to reuse. Functional and consistent with dense, engineer-facing data entry, but a follow-up picker component would materially improve usability.
- **No "list direct/pocket assignments for stage" endpoint existed in the original API design** — added during implementation (`GET /stages/{id}/direct-assignments`, `GET /stages/{id}/pocket-assignments`) once the frontend workspace's own need to display and remove existing assignments made the gap concrete. Documented here rather than silently.
- **Continuous Evaluation's own composition root remains unbuilt** (§14) — this is a pre-existing platform gap, not a UFLS defect, but it means no scheme module's findings are live-refreshed yet; all finding computation today happens synchronously, on demand, via `compute_findings`/`get_publication_review`.
