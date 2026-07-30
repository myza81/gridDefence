# Transformer Engineering Endpoint — Sprint 0 Readiness Report

**Date:** 2026-07-18 · **Branch:** `phase-02-substation-registry` · **HEAD:** `093a216` ("Add Thailand and Singapore as State reference options")

**Status:** Preflight/profiling (Sprint 0) + readiness-gate resolution (Sprint 0A, 2026-07-24) — **documentation-alignment only. No code, model, schema, migration, API, frontend, seed, test, or data was changed.** All database inspection was read-only. No temporary tooling remains (inline read-only queries only; nothing added to Git status).

**Authoritative basis (not reopened):** [EDR-011](../engineering/edr/EDR-011-transformer-engineering-interface-model.md), [ADR-028](../adr/ADR-028-transformer-engineering-endpoint-architecture.md), [transformer-engineering-endpoint-implementation-spec.md](transformer-engineering-endpoint-implementation-spec.md), [equipment-registry-module.md](equipment-registry-module.md).

---

## FINAL RESULT: **GO — ARCHITECTURAL GATES RESOLVED**

> **Operational prerequisite (not an architectural stop condition):** Implementation may begin after the repository owner confirms the working-tree isolation strategy (see Part A / Sprint 0A §6).

Sprint 0 concluded CONDITIONAL GO. Sprint 0A resolved every named readiness gate through documentation alignment. **There is no unresolved architectural stop condition** and no data conflict (the dev database is empty of transformer data, so backfill, cross-substation, uniqueness, and ID-preservation risks are all nil).

### Sprint 0A gate resolutions (2026-07-24)

1. **Endpoint-kind representation — RESOLVED.** `endpoint_kind` is **curated engineering reference data** (`engineering_endpoint_kind` table), exactly as ADR-028 §1 already selected. The blueprint's earlier CHECK-enum recommendation is **withdrawn and corrected**. **ADR-028 required no amendment** — it already chose reference data; the blueprint (not the ADR) was the divergent document, so the blueprint was aligned to the ADR. Application-level enums/constants may mirror the codes for type safety but never become a competing authority; adding a kind still requires engineering + architecture + validation + software review; a DB row does not imply arbitrary runtime extension. The endpoint-kind **FK** (not a free-standing text CHECK) plus XOR logic enforce valid representation.
2. **Classification-consistency policy — CONFIRMED.** `ADVISORY`, non-blocking, non-rewriting. The system may detect an engineer-asserted classification that appears inconsistent with the endpoint kinds, but must never derive, silently set, overwrite, block persistence for, or reinterpret classification from voltage ratio. **Representation integrity remains blocking** (mixed Registered/Typed fields, missing required endpoint fields, invalid endpoint-kind representation, invalid FKs, impossible HV/LV ordering, invalid same-substation Registered ownership). Reuses the existing advisory `Finding`/`Severity` mechanism; the exact integration point is an implementation concern (no parallel framework invented).
3. **Legacy `transformer_type` mappings — APPROVED (exact values only).** `Interbus Transformer → INTER_BUS`; `Load Transformer → LOAD`. `Auto` remains **unresolved — explicit engineer review only** (not Inter-bus, not "autotransformer", not a construction type; transformer construction technology and transformer engineering classification are separate concepts). Unknown/ambiguous/blank/null are never silently classified.
4. **Migration-workbench coordination — ACKNOWLEDGED as a release-order gate.** GridDefence Sprint 3 introduces the new contract + temporary compat behavior → workbench updated & tested in its own repo → GridDefence Sprint 4 moves the frontend → Sprint 5 removes legacy write compat **only after** the workbench is updated, its fixtures/mappings pass, and release coordination is confirmed.

### Transformer Classification representation (confirmed)

Curated engineering reference data; codes `INTER_BUS`/`LOAD`/`GENERATION_STEP_UP`/`STATION_SERVICE`/`CUSTOMER_SUPPLY` → labels "Inter-bus Transformer"/"Load Transformer"/"Generation Step-Up Transformer"/"Station Service Transformer"/"Customer Supply Transformer" (Malaysian terminology; never derived from voltage ratio).

### Remaining operational prerequisite (non-architectural)

**Working-tree isolation.** The branch carries pre-existing uncommitted Equipment Registry + frontend changes overlapping future Sprint 3/4 files. Before Sprint 1, the repository owner must choose one controlled strategy — **(A)** preserve & commit the accepted pre-existing work as its own coherent tested change; **(B)** clean isolated worktree/branch from the correct accepted commit, then bring in required accepted docs + prerequisite code; or **(C)** explicitly include the existing work only if it is part of the same approved sequence and reviewable coherently. **This is an operational prerequisite, not an unresolved architectural gate.** Sprint 0A does not stash, reset, revert, commit, branch, or create a worktree.

---

## Executive justification

- **Data risk is essentially zero:** the dev/reference database contains **0 transformers and 0 transformer terminals**. There is nothing to migrate, no anomalous data, no cross-substation records, no uniqueness collisions, and no terminal IDs at risk. The additive migration (Rev 0028 backfill) is trivially safe on current data; correctness must still be proven by tests for future/production data.
- **The current uniqueness rule already excludes `ENTERED_IN_ERROR`** (UAT correction #3, confirmed in code), so the blueprint's generalized endpoint-pair rule preserves — rather than changes — accepted behaviour.
- **No consumer fundamentally requires a non-null `voltage_yard_id`.** All scheme/ALSF/sensitive-customer consumers reference `transformer_terminal_id` only; the one consumer that dereferences a transformer terminal's `voltage_yard_id` (Network Model) is already defensively None-tolerant.
- **The advisory-finding mechanism already exists** (`findings_publication_governance` `Severity.ADVISORY` + `Finding`; `continuous_evaluation` detector framework), so no second validation framework is invented.
- **Reference-data conventions cleanly support the classification table.**
- The one architectural item (the `endpoint_kind` representation) was **resolved in Sprint 0A**: reference data per ADR-028 §1, blueprint corrected, no ADR amendment. No architectural gate remains open.

---

## Part A — Repository & working-tree preflight

- **Branch:** `phase-02-substation-registry`. **HEAD:** `093a216`. **Staged:** 0. **Modified (tracked):** 14. **Untracked:** 4.
- **Pre-existing Transformer Registry changes are present** in the working tree (uncommitted from earlier phases): `equipment_registry/{exceptions,router,schemas,service,tests/test_service}.py`, `tests/test_equipment_registry_api.py`, `frontend/src/modules/equipment_registry/{api.ts,types.ts}`. These **overlap files expected in Sprints 1–5** (schemas/service/router/tests/frontend) — a real review/merge-risk that must be isolated.
- **EDR-011, ADR-028, the implementation spec, and this report** are **untracked** (`??`) — created by the accepted-decision tasks, not yet committed. ADR-027 (voltage-yard restoration) is also untracked. Docs `equipment-registry-module.md`, `glossary.md`, `02-engineering-concepts.md`, `ADR-008` are `M` (pre-existing doc edits).
- **Change classification:** *this sprint's changes* = one file (this report). *Pre-existing* = the 14 `M` + 3 other `??`. *Unrelated* = the substation-state frontend edit. *Merge/review risk* = the equipment_registry `M` files (Sprints 3–4 touch the same modules).
- **Recommended (not executed) strategy:** implement on a **dedicated feature branch cut from a commit that first captures or sets aside the pre-existing equipment_registry uncommitted work**, so this effort's diffs are reviewable in isolation. Do not stash/revert/clean the existing work as part of Sprint 0.

## Part B — Migration-chain readiness

- **Head:** `0027_thailand_singapore_states` (single head; **linear** chain `0001→…→0027`; dev DB **at head**). No uncommitted migration files.
- **Next revisions viable:** blueprint's `0028` (additive/permissive) and `0029` (tightening/reconciliation) map to the next free numbers.
- **Conventions:** migrations are hand-written and reviewed; real-PostgreSQL migration verification is an established practice (`test_ufls_migration_regression.py`, `test_stage_setting_trigger_migration.py`), each skipped without `GRIDDEFENCE_TEST_DATABASE_URL`; **downgrade paths are written and (where a disposable DB is available) exercised**. **SQLite risk noted:** SQLite's relaxed typing and partial CHECK/FK enforcement can mask XOR-CHECK/FK/partial-index behaviour — the endpoint XOR CHECK (Rev 0029) **must** be verified on real PostgreSQL, not only SQLite.

## Part C — Legacy `transformer_type` profiling

- **Live/dev DB:** **0 transformer rows → no live `transformer_type` values.**
- **GridDefence code:** a single test literal `transformer_type="Auto"` (`test_transformer_service.py:922`, a round-trip test) — **no** seed/factory/fixture free-text values.
- **Migration workbench (`app/transformer_migration/`, report-only):** Project-Owner decision **D1** maps legacy source models to exactly two free-text values written into `transformer_type`: `core.loadtransformer → "Load Transformer"`, `core.autotransformer → "Interbus Transformer"` (models.py:25–27, manifest.py:33–34). The workbench comment states these are "the only two allowed functional classifications … no enum/table/schema change."

**Proposed engineer-review categories (NOT a migration map — no value auto-mapped):**

| Stored value | Normalised | Source | Category | Proposed (engineer to confirm) |
|---|---|---|---|---|
| `"Load Transformer"` | `load transformer` | workbench D1 | (4) probable match requiring confirmation | → `LOAD` |
| `"Interbus Transformer"` | `interbus transformer` | workbench D1 | (4) probable match requiring confirmation | → `INTER_BUS` |
| `"Auto"` | `auto` | GridDefence test | (6) ambiguous (auto-transformer? → often Inter-bus, but "auto" is construction, not function) | engineer review |
| `NULL` | — | (future/live) | (1) null | leave unclassified (classification stays nullable) |
| `""` | — | (future/live) | (2) blank | leave unclassified |

No value is treated as automatically equivalent. Note the terminology gap flagged by EDR-011: the workbench's "Interbus Transformer" (no hyphen) and "Auto" both require confirmation against the ratified `INTER_BUS` = "Inter-bus Transformer".

## Part D — Transformer & terminal data profiling (read-only)

All counts **0** (empty reference DB): 0 transformers, 0 terminals; 0 by any lifecycle status; 0 terminals with NULL `voltage_yard_id`; 0 transformers with ≠2 terminals; 0 duplicate sides; 0 orphaned yard references; 0 cross-substation terminals; 0 HV≤LV or equal-voltage records; 0 records unable to fit ADR-028. **Limitation:** with no data present, data-quality assurance for future/production data rests entirely on migration + service tests (Sprints 2–5), not on current profiling.

## Part E — Uniqueness semantics

- **Current rule (confirmed in code):** `transformer_number` unique within `(substation_id, hv_switchyard_id, lv_switchyard_id, transformer_number)`, service-layer cross-row check via aliased `TransformerTerminal` joins (`repository.find_transformer_by_yard_pair_and_number`), **excluding `ENTERED_IN_ERROR`** (UAT correction #3). Order is normalised by HV/LV (HV = higher nominal voltage). No raw single-table DB UNIQUE constraint (dropped by `0010_transformer_yard_pair`).
- **Data:** no duplicates possible (empty).
- **Future rule viability:** the blueprint's generalized rule — `(substation_id, HV-endpoint-descriptor, LV-endpoint-descriptor)` excluding `ENTERED_IN_ERROR`, typed descriptor = `(endpoint_kind, endpoint_nominal_voltage_level_id)`, **never `endpoint_label`** — **appears implementable without changing accepted behaviour** (it preserves the existing yard-pair semantics and the existing ENTERED_IN_ERROR exclusion). **Uniqueness stop condition: NOT triggered.**

## Part F — TransformerTerminal consumer inventory

| Consumer | File(s) | Relationship | Uses `transformer_terminal_id`? | Assumes non-null `voltage_yard_id`? | Change needed (Sprints 2–5)? |
|---|---|---|---|---|---|
| ALSF capability | `automatic_load_shedding_functionality/{models,repository,service,router,schemas}.py` | polymorphic capability target FK | **Yes** | No | **No** |
| UFLS direct assignment | `ufls/{models,repository,service,schemas,router,evaluation}.py` | assignment target FK | **Yes** | No | **No** |
| Sensitive Customer Registry | `sensitive_customer_registry/{models,repository,service,schemas,router}.py` | facility ↔ terminal | **Yes** (uses `substation_id` from a summary) | No | **No** |
| Network Model | `network_model/{repository,service}.py` | reads terminals by `transformer_id`; `get_substation_equipment` reads each terminal's `voltage_yard_id` | id + yard | **Dereferences it, but is already defensively None-tolerant** (`get_voltage_yard(None)` → None → blank labels; no crash) | **No required change**; optional display refinement to show a typed endpoint's kind/label instead of blank (Sprint 3/4 nice-to-have) |
| PSS/E Integration | `psse_integration/schemas.py` | DTO doc reference | reference only | No | **No** |
| UVLS / EMLS | — | not built | — | — | N/A (future; stable id) |
| Audit / lifecycle | `equipment_registry` `transformer_audit_log` | additive fields | n/a | No | Additive only |
| Migration workbench | `app/transformer_migration/` | external API client | maps candidate terminals | writes both as yards today | **External** — see Part J |

**No consumer fundamentally requires `voltage_yard_id` to be non-null** → stop condition #6 **NOT TRIGGERED** (Network Model already handles None; the "no change" claim in the blueprint's Part I is correct as *no required change*, refined here to note the optional typed-endpoint display improvement).

## Part G — Reference-data convention & the `endpoint_kind` gate

- **Convention (confirmed):** every lookup (`voltage_level`, `region`, `state`, `gm_zone`, `grid_owner`, `operational_status`, `line_type`, `transformer_breaker_numbering_convention`) = SMALLINT surrogate PK + unique `code` + `label` (+ optional `sort_order`/`is_terminal`/`is_standard`), idempotently seeded in `reference_data/seed.py`, served at `/api/v1/reference-data/*`, retrieved by `useReferenceData`, with first-run/idempotency/backfill tests.
- **Transformer Classification → reference table: fully supported** (SMALLINT PK, stable `code`, `label`, optional `description`/`is_active`). Recommended.
- **Engineering Endpoint Kind — RESOLVED (Sprint 0A): curated reference table `engineering_endpoint_kind`, per ADR-028 §1.** Codes `TRANSMISSION_VOLTAGE_YARD`/`DISTRIBUTION_SYSTEM`/`GENERATION_COLLECTOR_SYSTEM`/`STATION_AUXILIARY_SYSTEM`/`CUSTOMER_INSTALLATION` → labels "Transmission Voltage Yard"/"Distribution System"/"Generation Collector System"/"Station Auxiliary System"/"Customer Installation". Served at `/reference-data/engineering-endpoint-kinds`. The reference table is the authoritative vocabulary; an application enum/constant may **mirror** the codes for type safety but is not a competing authority, and adding a kind still requires engineering + architecture + validation + software review (a DB row does not imply arbitrary runtime extension — each kind carries distinct validation: nominal-voltage requirement, grid-side eligibility, uniqueness descriptor, future-registry binding). Representation is enforced by the endpoint-kind **FK** + XOR logic, **not** a free-standing text CHECK enumeration.
- **ADR status:** ADR-028 §1 already selected reference-data-backed `endpoint_kind`. The earlier blueprint CHECK-enum recommendation was the divergent artifact; it was **corrected to match ADR-028** in Sprint 0A. **No ADR amendment was required or made.**

## Part H — Classification-consistency (advisory) readiness

- **A reusable mechanism exists:** `findings_publication_governance/findings.py` defines a canonical `Severity` (`INFORMATION`, `ADVISORY`, …) and a `Finding` model; `continuous_evaluation` provides a detector/provider/service framework (ADR-022). **An advisory consistency check can be introduced without inventing a second validation framework.**
- **Recommended home:** an **Equipment-Registry service-level advisory** surfaced in the create/update response (non-blocking), reusing the established *Advisory* severity terminology. Rationale: classification↔endpoint consistency is an Equipment-Registry-internal concern, not a Scheme-Version evaluation; routing it through `continuous_evaluation` (scheme-scoped) or the scheme `Finding` pipeline would over-couple Equipment Registry to the scheme-publication machinery. If the Project Owner prefers a first-class Finding, `continuous_evaluation` is the fallback. **A blocking business rule must not be silently downgraded** — advisory is a deliberate new advisory, consistent with EDR-011 §8 (endpoints are evidence, classification is engineer-asserted) and EDR-004.

## Part I — API & frontend contract inventory

- **Backend create** (`TransformerCreate`): `substation_id`, `transformer_number`, `hv_switchyard_id`/`lv_switchyard_id` (+breakers), `capacity_mva`, `commissioning_date`, `operational_status_id`, **`transformer_type` free-text**, `manufacturer`, `remarks`. **Update** is a partial subset (incl. `transformer_type`). Read DTOs carry `transformer_type`; **`TransformerTerminalSummary.voltage_yard_id` is non-null (`string`)** and must become nullable.
- **Frontend:** free-text `<input>` for transformer type; substation-first create; HV/LV switchyard selectors; list/detail/tests present (`TransformerCreatePage`, `TransformerDetailPage`, `TransformerListPage`, `transformerBreakerSuggestion`).
- **Compatibility window feasible:** Sprint 3 backend accepts both the legacy shape (both terminals as `*_switchyard_id`, free-text `transformer_type`) mapped internally to Registered endpoints, and the new structured shape; Sprint 4 frontend adopts the structured shape; Sprint 5 removes the legacy write path + `transformer_type`. No contract makes this unsafe — the only breaking element (removal of `transformer_type`) is deferred and announced.

## Part J — Migration workbench assessment (report-only)

- `app/transformer_migration/` (versioned in the **separate** workbench repo, not GridDefence) builds Transformer + HV/LV `TransformerTerminal` candidates and resolves them against GridDefence's API. Its D1 decision writes free-text `transformer_type ∈ {"Load Transformer","Interbus Transformer"}`; it assumes both terminals have a switchyard (legacy MVP data is all Load/Inter-bus, both grid-embedded); it maps/normalises candidates and reads GridDefence reference data via the API.
- **It creates a release-order dependency:** after GridDefence tightens `transformer_type` → classification (Sprint 5) and (eventually) removes the free-text write path, the workbench importer must send the classification code (and, if ever migrating non-grid-side assets, the typed-endpoint fields). During the compat window GridDefence must keep accepting the two free-text values. **Do not modify the workbench here** — coordinate its adoption in its own repo.

## Part K — Stop-condition matrix

| # | Condition | Result | Evidence |
|---|---|---|---|
| 1 | Endpoint-kind representation conflicts with ADR-028 | **RESOLVED (Sprint 0A) → PASS** | Reference table `engineering_endpoint_kind` per ADR-028 §1; blueprint corrected; no ADR amendment required. |
| 2 | A blocking consistency policy is required | **RESOLVED (Sprint 0A) → PASS** | Confirmed ADVISORY, non-blocking, non-rewriting (representation integrity stays blocking); reuses `Severity.ADVISORY`/`Finding`. No amendment. |
| 3 | Uniqueness cannot be generalised safely | **PASS** | Endpoint-pair rule preserves existing semantics + existing ENTERED_IN_ERROR exclusion; no data conflict. |
| 4 | Cross-substation transformers exist in data | **PASS** | 0 cross-substation terminals (and 0 transformers). |
| 5 | Authoritative vocabulary conflicts with EDR-011 | **NOT TRIGGERED — REQUIRES MONITORING** | Workbench D1 "Interbus Transformer"/"Auto" differ in spelling from ratified `INTER_BUS`; reconcile via the engineer-review table (not a conflict, a mapping). |
| 6 | A consumer fundamentally requires non-null `voltage_yard_id` | **PASS** | All consumers use `transformer_terminal_id`; Network Model is already None-tolerant. |
| 7 | TransformerTerminal IDs cannot be preserved | **PASS** | Migration is strictly additive; PK untouched; 0 rows to migrate. |
| 8 | Lifecycle cannot support temporarily unclassified/incomplete states | **PASS** | `PLANNED` status + nullable classification during the window; permissive Rev 0028 before tightening Rev 0029. |
| 9 | EDR-011/ADR-028 conflicts with another accepted decision | **PASS** | No conflict found; workbench D1 (two legacy values) is compatible with the forward-looking five-classification vocabulary. |

## Part L — Sprint-readiness matrix

| Sprint | Readiness | Notes |
|---|---|---|
| 1 — Reference data & contracts | **READY** (pending owner-confirmed working-tree isolation) | Both `transformer_classification` and `engineering_endpoint_kind` confirmed as reference tables (Sprint 0A); codes/labels/seed/API conventions confirmed; Transformer/TransformerTerminal persistence untouched in Sprint 1. |
| 2 — Additive DB migration | **READY** | Revision numbers free (0028); 0 rows → backfill trivial & ID-preserving; nullable `voltage_yard_id` (post-tighten) blocked by no consumer; PostgreSQL CHECK behaviour understood; migration-test harness exists. |
| 3 — Backend behaviour | **READY** | Service rules identified; uniqueness viable; **advisory consistency confirmed (Sprint 0A)**; compat window feasible; audit pattern understood. |
| 4 — Frontend | **READY** | Existing form evolvable; `useReferenceData` pattern exists; structured editor is additive; terminology confirmed. |
| 5 — Constraint tightening | **READY** | **Legacy mapping approved (Sprint 0A):** `Interbus Transformer`→`INTER_BUS`, `Load Transformer`→`LOAD`; `Auto`/unknowns stay visible (never silently mapped); legacy write contract retirable **only after workbench readiness**; empty data trivially satisfies XOR. |
| 6 — Regression & UAT | **READY** | Consumers identified; **workbench release-order coordination confirmed (Sprint 0A)**; UAT fixtures constructible; full backend+frontend+real-PostgreSQL commands known. |

## Part M — Prerequisite status before Sprint 1

| Prerequisite | Status (Sprint 0A) |
|---|---|
| Endpoint-kind representation (architectural) | **RESOLVED** — reference table per ADR-028 §1; no amendment. |
| Classification-consistency policy (architectural/policy) | **RESOLVED** — advisory, non-blocking, non-rewriting. |
| Legacy `transformer_type` mapping | **RESOLVED** — `Interbus Transformer`→`INTER_BUS`, `Load Transformer`→`LOAD` approved; `Auto`/unknowns engineer-review only, never auto-mapped. |
| Migration-workbench release-order dependency | **RESOLVED (acknowledged)** — Sprint 5 legacy-removal gated on confirmed workbench readiness. |
| **Working-tree isolation (operational)** | **OPEN** — repository owner must confirm strategy A/B/C before Sprint 1 implementation begins (Part A). This is the sole remaining item, and it is operational, not architectural. |

**All architectural gates are resolved. Sprint 1 may begin once the owner confirms the working-tree isolation strategy.**

---

## Files inspected

`equipment_registry/{models,schemas,service,repository,router,exceptions,tests/test_transformer_service.py}.py`; `tests/test_transformer_registry_api.py`; `reference_data/{models,seed,repository,router,schemas}.py`; `alembic/versions/` (head 0027); `automatic_load_shedding_functionality/*`, `ufls/*`, `sensitive_customer_registry/*`, `network_model/{repository,service,schemas,exceptions}.py`, `psse_integration/schemas.py`; `findings_publication_governance/findings.py`; `continuous_evaluation/` (listing); `frontend/src/modules/equipment_registry/{types.ts,api.ts,pages/*}`; EDR-011; ADR-028; the implementation spec; `equipment-registry-module.md`; (report-only) workbench `app/transformer_migration/{models,manifest,normalization}.py`, `app/config.py`. Read-only dev-DB queries against `transformer`, `transformer_terminal`, `operational_status`, `substation_voltage_yard`.

## Files created
`docs/architecture/transformer-engineering-endpoint-sprint-0-readiness-report.md` (this report — Sprint 0).

## Files modified (Sprint 0A — documentation only)
- `docs/architecture/transformer-engineering-endpoint-sprint-0-readiness-report.md` — recorded gate resolutions and the GO verdict.
- `docs/architecture/transformer-engineering-endpoint-implementation-spec.md` — corrected `endpoint_kind` to a reference table (per ADR-028 §1), confirmed advisory consistency, recorded the two approved legacy mappings + `Auto` unresolved, recorded the workbench release gate and the working-tree isolation prerequisite, updated Sprint 1 & Sprint 5 acceptance, and resolved Stop Conditions #1/#2.

**Not modified:** ADR-028 (no amendment required — it already selected reference data), EDR-011, and all production source (models/schemas/services/repositories/routers/APIs/frontend/seeds/tests). No Alembic migration created. No database record changed. Nothing staged, committed, or pushed.

## Git diff summary
Two documentation files changed (this report + the implementation spec, both untracked planning docs). No code/model/schema/migration/API/frontend/seed/test/data change.
