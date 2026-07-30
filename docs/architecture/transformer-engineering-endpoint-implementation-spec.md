# Transformer Engineering Endpoint — Implementation Blueprint

**Planning status:** PLANNED — **implementation not started.** This is a sequencing/planning document only; no code, model, migration, API, or frontend has been changed to produce it.

**Authoritative dependencies (do not restate; do not contradict):**
- [EDR-011](../engineering/edr/EDR-011-transformer-engineering-interface-model.md) — Transformer Engineering Interface Model (engineering meaning).
- [ADR-028](../adr/ADR-028-transformer-engineering-endpoint-architecture.md) — Transformer Engineering Endpoint Architecture (software decision).
- Equipment Registry conventions: [equipment-registry-module.md](equipment-registry-module.md) (Phase 3.5 Transformer Registry), the Core Platform reference-data pattern (`app/reference_data/`), the `operational_status` lifecycle + `is_terminal` restoration pattern (ADR-014/ADR-027 as applied in `EquipmentRegistryService`).

**Readiness gate resolved (Sprint 0A, 2026-07-24): `endpoint_kind` is implemented as curated engineering reference data (`engineering_endpoint_kind` table), per ADR-028 §1. This supersedes this plan's earlier CHECK-enum recommendation. ADR-028 required no amendment. Application-level constants may mirror the reference-data codes for type safety, but the reference-data table remains the sole authoritative vocabulary; adding a new endpoint kind still requires engineering, architecture, validation, and software review. See [Sprint 0 readiness report](transformer-engineering-endpoint-sprint-0-readiness-report.md).**

---

## 1. Current implementation assessment (grounded in the repo)

- **`Transformer`** (`equipment_registry/models.py`): `transformer_id` (UUID PK), `substation_id` (FK, mandatory), `transformer_number`, `capacity_mva` (nullable, `CHECK > 0`), `commissioning_date`, `operational_status_id` (FK), **`transformer_type` (nullable free-text `String(50)`, no enum/table/CHECK)**, `manufacturer`, `remarks`, audit columns. Created by `0008_transformer_registry`; `0010_transformer_yard_pair` dropped the single-table uniqueness constraint.
- **`TransformerTerminal`**: `transformer_terminal_id` (UUID PK), `transformer_id` (FK), `side` (`CHECK IN ('HV','LV')`), **`voltage_yard_id` (FK → `substation_voltage_yard`, NOT NULL)**, `breaker_number`, audit. Exactly two rows per transformer.
- **Service** (`create_transformer` L1189, `update_transformer` L1305): validates both yards exist and belong to the transformer's substation (`_require_yard_belongs_to_substation`), HV≠LV yard, **HV nominal_kv > LV nominal_kv**, and uniqueness `(substation_id, hv_switchyard_id, lv_switchyard_id, transformer_number)` via `repository.find_transformer_by_yard_pair_and_number` (L555). Short name (`T`/`SGT`/`XGT`) computed from HV nominal voltage — never from `transformer_type`.
- **Lifecycle:** initial status ∈ `{PLANNED, ACTIVE}`; `ENTERED_IN_ERROR` correction; `ENTERED_IN_ERROR → ACTIVE` restoration exists; terminality read from `operational_status.is_terminal`. Transformers have **no Draft/Publish workflow** — "not yet in service" is `PLANNED`.
- **Reference-data pattern** (`app/reference_data/models.py` + `seed.py`): each lookup = SMALLINT surrogate PK + unique `code` + `label` (+ optional `sort_order`/`is_terminal`/`is_standard`), idempotently seeded, served at `/api/v1/reference-data/*`. Precedents: `voltage_level`, `line_type`, `gm_zone`, `transformer_breaker_numbering_convention`.
- **Migration chain head:** `0027_thailand_singapore_states`. Next transformer revisions are **0028+**. (ADR-027 "voltage-yard restoration" is a separate doc/service concern, not migration 0027.)
- **Consumers of `TransformerTerminal` (by id):** ALSF (`automatic_load_shedding_functionality` — polymorphic `transformer_terminal_id` capability target), UFLS (`ufls` — direct assignment target), Sensitive Customer Registry (facility ↔ transformer terminal), Network Model (`repository` reads terminals by `transformer_id`), PSS/E Integration (`schemas` DTO reference). **All reference the terminal by `transformer_terminal_id` only.** UVLS/EMLS are not yet built.
- **Frontend** (`frontend/src/modules/equipment_registry/`): `TransformerCreate/Update/Detail/Summary` carry `transformer_type?: string | null` (free-text `<input>`); `TransformerTerminal*` carry `voltage_yard_id` + `side`. Pages: `TransformerCreatePage`, `TransformerDetailPage`, `TransformerListPage`; tests for each; `transformerBreakerSuggestion` uses the reference-data convention.
- **Migration workbench (report-only; do not modify):** now contains `app/transformer_migration/` (builds Transformer + HV/LV TransformerTerminal candidates and resolves against GridDefence's API). It is a downstream client of GridDefence's transformer create API.
- **Working tree:** pre-existing uncommitted equipment-registry work is present on this branch (see §Risks) — the plan must be executed on top of it without reverting it.

**Assessment:** the endpoint evolution is *additive* over a stable terminal identity. No consumer reads `transformer_type` or assumes anything about the endpoint beyond "the terminal exists," so the blast radius is contained to Equipment Registry + reference data + frontend, with the workbench as an external client to coordinate separately.

---

## Part A — Reference-data strategy

**Transformer Classification → a Core Platform reference table.** Genuinely reference data: engineer-curated, user-facing (dropdown label), expandable, and additive without new logic. Shape (mirroring `line_type`): `transformer_classification(transformer_classification_id SMALLINT PK, code UNIQUE, label, description NULLABLE, sort_order, is_active)`.
- **Codes/labels (seed, ordered):** `INTER_BUS`→"Inter-bus Transformer", `LOAD`→"Load Transformer", `GENERATION_STEP_UP`→"Generation Step-Up Transformer", `STATION_SERVICE`→"Station Service Transformer", `CUSTOMER_SUPPLY`→"Customer Supply Transformer". Malaysian engineering terminology; classification is never derived from voltage ratio.
- Served at `/api/v1/reference-data/transformer-classifications`; retrieved by the existing `useReferenceData` hook; idempotent seed + first-run/backfill/idempotency tests mirroring `line_type`.

**Engineering Endpoint Kind → a Core Platform reference table (`engineering_endpoint_kind`), per ADR-028 §1 (Sprint 0A resolution).** Shape mirroring `line_type`: `engineering_endpoint_kind(engineering_endpoint_kind_id SMALLINT PK, code UNIQUE, label, description NULLABLE [if convention supports], [active/lifecycle field only if consistent with existing reference-data practice])`.
- **Codes/labels (seed, ordered):** `TRANSMISSION_VOLTAGE_YARD`→"Transmission Voltage Yard", `DISTRIBUTION_SYSTEM`→"Distribution System", `GENERATION_COLLECTOR_SYSTEM`→"Generation Collector System", `STATION_AUXILIARY_SYSTEM`→"Station Auxiliary System", `CUSTOMER_INSTALLATION`→"Customer Installation".
- Served at `/api/v1/reference-data/engineering-endpoint-kinds`; retrieved by the existing `useReferenceData` hook; idempotent seed + first-run/backfill/idempotency tests mirroring `line_type`.
- **The reference-data table is the authoritative vocabulary.** An application-level enum/constant **may** mirror the codes for type safety, but must not become an independent competing authority. Adding a new endpoint kind still requires engineering, architecture, validation, and software review — the presence of a reference-data row does **not** imply arbitrary runtime extension is supported (each kind carries distinct validation: nominal-voltage requirement, grid-side eligibility, uniqueness descriptor, future-registry binding). Database constraints enforce valid representation through the **endpoint-kind FK** plus the XOR logic (Part B); the FK is **not** replaced by a free-standing text CHECK enumeration.

---

## Part B — Database evolution (additive; multiple revisions, safety over count)

Two migrations, not one — reviewability and the populated-table constraint-tightening risk both argue for separating the *permissive additive* step from the *tightening* step.

**Revision 0028 — additive, permissive (Sprint 2):**
- `Transformer`: add `transformer_classification_id SMALLINT NULL FK → transformer_classification ON DELETE RESTRICT`. **Keep `transformer_type` free-text column** (coexistence window). Both nullable during transition.
- `TransformerTerminal`: add `engineering_endpoint_kind_id SMALLINT NULL FK → engineering_endpoint_kind ON DELETE RESTRICT` (**temporarily nullable** to allow backfill), `endpoint_nominal_voltage_level_id SMALLINT NULL FK → voltage_level ON DELETE RESTRICT`, `endpoint_label TEXT NULL`. Keep `voltage_yard_id` (now to become nullable **only after** backfill — see 0029).
- Backfill in-migration: set every existing terminal `engineering_endpoint_kind_id` = the `TRANSMISSION_VOLTAGE_YARD` row (all existing terminals resolve to a yard). Existing `voltage_yard_id` unchanged; typed fields remain NULL.
- Indexes: `ix_transformer_terminal_engineering_endpoint_kind_id`; retain `ix_transformer_terminal_*` on `voltage_yard_id`.
- Constraint **not yet enforced** as NOT NULL / XOR — permissive so backfill can complete.

**Revision 0029 — tightening (Sprint 5, after backfill verified):**
- `TransformerTerminal`: make `engineering_endpoint_kind_id` NOT NULL; make `voltage_yard_id` **nullable** (typed terminals have none); add the XOR `CHECK` (named `ck_transformer_terminal_endpoint_repr`) evaluated against the endpoint-kind FK — conceptually: *for the `TRANSMISSION_VOLTAGE_YARD` kind* `voltage_yard_id IS NOT NULL AND endpoint_nominal_voltage_level_id IS NULL`; *for any typed kind* `voltage_yard_id IS NULL AND endpoint_nominal_voltage_level_id IS NOT NULL`. (Because the discriminator is an FK surrogate id rather than a text code, the CHECK references the `TRANSMISSION_VOLTAGE_YARD` id resolved in-migration; the endpoint-kind vocabulary itself is constrained by the FK, **not** by a free-standing text CHECK enumeration.)
- `Transformer`: resolve/deprecate `transformer_type` (see Part C) — drop it **only** once every value is reconciled and consumers stop reading it; `transformer_classification_id` may remain nullable (a classification is optional-but-encouraged) or become NOT NULL only if Part C confirms every legacy row can be classified. **Default plan: keep `transformer_classification_id` nullable** (a legitimately-unclassified legacy transformer must remain valid, echoing the substation-`state` optionality precedent) unless the Project Owner requires it mandatory.
- All constraint names explicit and prefixed `ck_`/`ix_` per existing convention.

Existing rows remain valid at every step; final target = discriminated endpoint with XOR guarantee.

---

## Part C — Data migration and backfill

**Endpoint backfill (deterministic):** every existing `TransformerTerminal` → `endpoint_kind = 'TRANSMISSION_VOLTAGE_YARD'`, `voltage_yard_id` unchanged, typed fields NULL. IDs untouched (Sprint 2 verification asserts count-in = count-out and identical `transformer_terminal_id` set).

**Legacy `transformer_type` free-text (NEVER silently mapped):** Sprint 0 profiled the live/dev distribution of `transformer_type` (distinct values, counts, casing/whitespace). Each value is categorised:
- **null / blank** → no classification set; `transformer_classification_id` stays NULL (valid). Never silently classified.
- **engineer-approved exact text** → mapped **only via the explicit, engineer-reviewed mapping table below** (Sprint 0A), never by fuzzy inference. **Approved exact mappings (Sprint 0A):**

  | Exact legacy text | Approved classification |
  |---|---|
  | `Interbus Transformer` | `INTER_BUS` |
  | `Load Transformer` | `LOAD` |

  Approval applies **only to those exact values**; case/whitespace variants require separate explicit engineer approval before any normalization.
- **unresolved legacy text** → **`Auto` is explicitly NOT mapped** — retained for explicit engineer review. Do not assume `Auto` means Inter-bus, an autotransformer, a construction type, or any accepted functional classification. **Transformer construction technology and transformer engineering classification are separate concepts.**
- **unknown / ambiguous legacy text (incl. `Auto`)** → **left in the retained `transformer_type` column**, surfaced in a **migration exception report** (Sprint 0 profile + Sprint 5 pre-flight), and **must not** be auto-mapped and **must not** block Revision 0028 (the permissive step). It blocks only the *optional* decision to make classification NOT NULL — which this plan does not require.
- Casing/whitespace differences are normalised **only for an explicitly approved mapping lookup**, never written back silently.

**Verification (conceptual, not written as migration code here):** pre-migration — `SELECT transformer_type, count(*) ... GROUP BY`; count of terminals, distinct `transformer_id`. Post-migration — every terminal has `endpoint_kind` set; `voltage_yard_id` unchanged for all pre-existing rows; FK integrity intact; no orphaned/mixed endpoint state; the same `transformer_terminal_id` set exists.

---

## Part D — Domain model and validation

- **Registered endpoint:** `endpoint_kind='TRANSMISSION_VOLTAGE_YARD'` → require `voltage_yard_id`, forbid typed fields; the yard must belong to the transformer's substation (existing `_require_yard_belongs_to_substation`); nominal voltage read from the yard.
- **Typed endpoint:** `endpoint_kind∈{DISTRIBUTION_SYSTEM,GENERATION_COLLECTOR_SYSTEM,STATION_AUXILIARY_SYSTEM,CUSTOMER_INSTALLATION}` → require `endpoint_nominal_voltage_level_id`, forbid `voltage_yard_id`, `endpoint_label` optional; no substation-yard constraint.
- **HV > LV:** preserved, evaluated on each terminal's endpoint nominal voltage (from the yard when Registered, from `endpoint_nominal_voltage_level_id` when Typed).
- **Same-substation:** applies only to the Registered (grid) terminal.
- **Classification–endpoint consistency: ADVISORY, non-blocking (recommended policy).** Rationale grounded in the accepted philosophy: EDR-011 §8 keeps classification engineer-asserted and endpoints as *evidence only*, forbidding silent derivation/override; EDR-004 ("GridDefence detects; engineers decide"); and the existing HV≥LV rule is itself documented as "a light physical-sanity check, not a hard architectural constraint given real-world exceptions." Transformers also have **no Draft/review stage** at which to gate a blocking check, and can be created directly as ACTIVE. Therefore the service records an advisory finding/warning when classification and endpoint kinds are inconsistent (e.g. GSU whose non-grid endpoint is not a Generation Collector System) but never rejects or reclassifies. *(If the Project Owner wants blocking-at-activation, that is an ADR-028 amendment — see Stop Conditions.)*
- **Never derive classification** from endpoints; classification is only ever the engineer's supplied value.
- **Lifecycle/entered-in-error/restore:** unchanged mechanism — classification and endpoints are ordinary audited fields; a mistaken transformer is corrected as a whole (`ENTERED_IN_ERROR`) and may be restored (`ENTERED_IN_ERROR → ACTIVE`), exactly as today.
- **Audit:** classification changes, `endpoint_kind`/`endpoint_nominal_voltage_level_id`/`endpoint_label` changes, and (existing) `voltage_yard_id`/`breaker_number` changes are captured on the existing `transformer_audit_log`, one row per changed field (existing pattern).

---

## Part E — Ownership and endpoint scope (service rules)

Per classification, the required endpoint shape:
- **INTER_BUS:** both terminals `TRANSMISSION_VOLTAGE_YARD`; both yards belong to the owning Substation; different voltage levels; a 33/22/11 kV winding must **not** be accepted as Inter-bus.
- **LOAD:** one `TRANSMISSION_VOLTAGE_YARD` + one `DISTRIBUTION_SYSTEM`.
- **GENERATION_STEP_UP:** one `TRANSMISSION_VOLTAGE_YARD` + one `GENERATION_COLLECTOR_SYSTEM`.
- **STATION_SERVICE:** one `TRANSMISSION_VOLTAGE_YARD` + one `STATION_AUXILIARY_SYSTEM`.
- **CUSTOMER_SUPPLY:** one `TRANSMISSION_VOLTAGE_YARD` + one `CUSTOMER_INSTALLATION`.

These shapes drive the **advisory** consistency check (Part D), not a hard gate.

**Grid-side identification independent of input order:** the grid side is the terminal whose `endpoint_kind = TRANSMISSION_VOLTAGE_YARD` (for Inter-bus, both are grid; the higher nominal voltage is HV). The service determines HV/LV from **nominal voltage** (higher = HV), never from submission order — as it already does. **`side` (`HV`/`LV`) remains the stored terminal vocabulary; no separate "endpoint role" column is needed** — role (grid vs non-grid) is derivable from `endpoint_kind`, and adding a role column would duplicate that fact (CLAUDE.md §5.1). GSU stored per UAT scenario: grid winding `HV` at 132/275/500, generation winding `LV` at 11/33.

---

## Part F — Uniqueness redesign (recommended rule; **not** a stop condition)

**Recommended:** `transformer_number` unique within `(substation_id, HV-endpoint-descriptor, LV-endpoint-descriptor)`, excluding `ENTERED_IN_ERROR` rows, enforced at the service layer, where an **endpoint descriptor** is `voltage_yard_id` for a Registered endpoint and `(endpoint_kind, endpoint_nominal_voltage_level_id)` for a Typed endpoint. **Never uses `endpoint_label`.**
- Generalises today's `(substation_id, hv_switchyard_id, lv_switchyard_id, transformer_number)` by substituting the typed descriptor where a yard id is absent; preserves the UAT-#2 "numbered per transformation pair" intent (two parallel GSUs on the same grid yard + same collector must have distinct numbers).
- **Excludes `ENTERED_IN_ERROR`** so a corrected transformer never blocks its replacement — learning from the ADR-027 voltage-yard trap (Sprint 0 must confirm whether the *current* transformer uniqueness is status-aware; if not, this is a bundled correctness fix).
- Rejected alternatives: *number-unique-within-substation* (too coarse — the exact UAT-#2 failure); *number-unique-within-substation+classification* (couples identity to a mutable, engineer-asserted classification — an identity must not depend on a reclassifiable attribute).
- **Why not a stop condition:** the endpoint-pair generalisation is unambiguous and preserves engineering identity; it needs no ADR amendment. (It *would* become a stop condition only if a typed descriptor could not distinguish two genuinely-distinct transformers — which the transformer_number already resolves.)

---

## Part G — API compatibility

- **Read DTOs** (`TransformerSummary`/`TransformerDetail`, `TransformerTerminal*`): add `transformer_classification` (code + label) and, per terminal, `endpoint_kind`, `endpoint_nominal_voltage_level_id`/label, keeping `voltage_yard_id` (now nullable in the response for typed terminals). `transformer_type` remains in the read DTO during the compat window, then is removed in Sprint 5.
- **Create/Update payloads:** accept `transformer_classification_id` (optional initially) and per-terminal endpoint fields. **Short, explicit compatibility window:** during Sprints 3–4 the backend continues to accept the legacy create/update shape (both terminals as `voltage_yard_id`, free-text `transformer_type`) and internally maps it to Registered endpoints; the window **closes in Sprint 5** (legacy `transformer_type` write path and column removed). Prefer this short window over permanent dual semantics.
- **Reference-data endpoints:** new `/reference-data/transformer-classifications` and `/reference-data/engineering-endpoint-kinds` (both curated reference tables per ADR-028 §1 / Sprint 0A).
- **Error contracts:** structured `ValidationAppError` (existing `_error_response` mapping) for invalid endpoint representation, missing nominal voltage on a typed endpoint, Inter-bus with a non-grid endpoint (advisory → warning, not error, per Part D), unknown classification code, uniqueness violation. **OpenAPI** regenerates additively; the only breaking element (removal of `transformer_type`) is deferred to Sprint 5 and announced.

---

## Part H — Frontend evolution

**Evolve the existing create/edit pages into a structured endpoint editor (do not rebuild from scratch)** — the pages already own the substation-first workflow and switchyard selectors; the change is additive.
Workflow: (1) select **Transformer Classification** (dropdown from reference data); (2) define each terminal's endpoint; (3) Registered → **Voltage Yard** selector (existing); (4) Typed → **nominal voltage** selector + optional **descriptive label**; (5) the UI **may suggest** expected endpoint kinds from the chosen classification but (6) **must never silently set or overwrite** the classification from endpoints; (7) accurate terminology throughout.
- **Terminology (enforced in labels/tests):** *Voltage Yard / switchyard* for 132/275/500 kV transmission; *Distribution System*; *Generation Collector System*; *Station Auxiliary System*; *Customer Installation*; optional *Busbar / Switchgear / System* in descriptive labels for 11/22/33 kV. **No "switchboard."**
- **List/detail/filter:** add a Classification column and a Classification filter; detail shows each terminal's endpoint (yard label, or typed kind + nominal voltage + label); typed terminals render their label as descriptive text only.
- Types (`types.ts`): add `transformer_classification`, per-terminal `endpoint_kind`/`endpoint_nominal_voltage_level_id`/`endpoint_label`; make `voltage_yard_id` nullable on terminal types; deprecate `transformer_type` (Sprint 5).

---

## Part I — Existing relationship impact

**Expected result: unchanged, because `transformer_terminal_id` is stable.**

| Consumer | Change required? | Why |
|---|---|---|
| ALSF capability | **No** | References `transformer_terminal_id` (polymorphic target); terminal id/identity unchanged. Typed terminals simply won't receive ALSF capability (EDR-011 §10). |
| UFLS direct assignment | **No** | Targets `transformer_terminal_id`; unchanged. |
| UVLS / EMLS | **No (N/A)** | Not yet built; will consume the same stable terminal id. |
| Shared assignment infra | **No** | Terminal id stable. |
| Sensitive Customer Registry | **No** | Facility ↔ `transformer_terminal_id`; unchanged. |
| PSS/E correlation | **No (this scope)** | Correlates on buses/voltage; never on `transformer_type`. How correlation consumes typed endpoints is **explicitly deferred** (ADR-028). |
| Network Model | **No** | Reads terminals by `transformer_id`; endpoint fields are additive. |
| Audit | **Additive only** | New fields audited on existing `transformer_audit_log`. |
| **Migration workbench** (`app/transformer_migration/`) | **Yes, but external and out of scope here (report-only)** | It constructs transformer create payloads; when GridDefence's create contract gains classification/endpoint fields (and later drops `transformer_type`), the workbench importer must adopt them. Coordinated in the workbench's own repo during the Sprint 3–5 compat window; **not modified by this effort.** |

---

## Part J — Test strategy

- **Migration (real PostgreSQL, per repo convention):** existing rows backfill to `TRANSMISSION_VOLTAGE_YARD`; `transformer_terminal_id` set identical pre/post; `voltage_yard_id` unchanged; FKs valid; unknown `transformer_type` NOT silently mapped (asserts they remain in the legacy column + appear in the exception report); XOR CHECK (0029) rejects mixed/incomplete states; downgrade expectations documented (0029 down re-permits; 0028 down drops added columns — lossy for typed data, documented like the `state`/`stage_setting_trigger` precedents).
- **Model/repository:** Registered persistence; Typed persistence; XOR CHECK enforcement; FK integrity (nominal voltage level, classification); generalised uniqueness; `ENTERED_IN_ERROR` exclusion from uniqueness; lifecycle exclusions.
- **Service:** each valid classification/endpoint shape (Part E); invalid shapes (missing nominal voltage on typed; `voltage_yard_id` on typed; Inter-bus with a 33 kV typed endpoint → **advisory**, not rejection); **no silent classification change/derivation**; HV>LV via endpoint nominal voltage; same-substation only on the grid terminal; `endpoint_label` optional and **never used as identity/uniqueness**; audit rows per changed field.
- **API:** create/read/update with classification + endpoints; legacy-payload compatibility during the window; reference-data lookup; structured validation errors; list/detail shape incl. nullable `voltage_yard_id`.
- **Frontend:** classification selection; endpoint-kind selection; Registered vs Typed controls; Malaysian terminology (no "switchboard"); optional label; validation; edit round-trip; **no silent classification overwrite**.
- **Regression:** ALSF, UFLS assignment, sensitive-customer, PSS/E workflows, existing Equipment Registry behaviour, breaker-number suggestion — all green with terminal ids unchanged.

**UAT scenarios (all 14 from the task):** (1) 132/275 Inter-bus; (2) 275/500 Inter-bus; (3) 132/33 Load; (4) 132/33 SST; (5) 275/11 SST; (6) 500/33 SST; (7) 33/132 GSU stored HV 132 / LV 33; (8) 33/275 GSU; (9) 33/500 GSU; (10) 132/33 CST label `ABC Steel 33 kV System`; (11) CST label `ABC Steel 33 kV Busbar`; (12) **invalid** Inter-bus with a 33 kV typed endpoint (advisory warning surfaced, not silently reclassified); (13) **invalid** mixed endpoint representation (XOR CHECK / service rejects); (14) existing transformer migrated with **unchanged terminal IDs**.

---

## Sprint decomposition

Each sprint is small and independently reviewable; migrations are separated for safety. "Independently committable" = can merge without leaving the app broken.

**Sprint 0 — Preflight & data profiling.** *Objective:* go/no-go. *Files:* none (analysis + this doc's checklist). *Migration:* none. *Deps:* none. *Tests:* n/a (produces a profile report). *Acceptance:* live/dev `transformer_type` distribution enumerated with an approved explicit mapping table; migration head confirmed (0027); every `TransformerTerminal` consumer inventoried (§Part I); current transformer-uniqueness status-awareness confirmed; no cross-substation transformers exist (else Stop Condition). **Status: complete — CONDITIONAL GO; readiness gates resolved in Sprint 0A (endpoint-kind = reference table per ADR-028; advisory consistency confirmed; legacy `Interbus Transformer`→`INTER_BUS`, `Load Transformer`→`LOAD` approved, `Auto` unresolved).** *Out of scope:* any code. *Committable:* yes (report only).

**Sprint 1 — Reference data & contracts.** *Objective:* classification vocabulary + endpoint-kind vocabulary + contracts. *Files:* `reference_data/models.py`,`seed.py`,`repository.py`,`router.py`,`schemas.py`; new reference migrations for `transformer_classification` **and `engineering_endpoint_kind`** (both curated reference tables); frontend `reference_data` types/hook. *Migration:* reference tables only; no `transformer`/`transformer_terminal` change yet. *Deps:* Sprint 0/0A sign-off + owner-confirmed working-tree isolation strategy (see Risks). *Tests:* seed first-run/idempotency/backfill; reference-data API contract. *Acceptance:* `transformer_classification` and `engineering_endpoint_kind` seeded & served at `/reference-data/*`; no transformer behaviour change; **Transformer/TransformerTerminal persistence is NOT modified in Sprint 1** unless this spec explicitly places additive contract scaffolding there (it does not — that is Sprint 2). *Out of scope:* transformer schema/service. *Committable:* yes.

**Sprint 2 — Additive database model (permissive).** *Objective:* add columns + backfill, nothing enforced yet. *Files:* Revision **0028**; `equipment_registry/models.py` (nullable additions). *Migration:* 0028. *Deps:* Sprint 1. *Tests:* migration tests (backfill correctness, id stability, FK validity, unknown-`transformer_type` untouched). *Acceptance:* every terminal `endpoint_kind='TRANSMISSION_VOLTAGE_YARD'`; existing data valid; app runs. *Out of scope:* service/API/frontend behaviour. *Committable:* yes (columns present but unused by behaviour).

**Sprint 3 — Backend endpoint behaviour.** *Objective:* service/repository/API read+write for Registered & Typed endpoints + advisory consistency + audit; legacy-payload compatibility. *Files:* `equipment_registry/service.py`,`repository.py`,`schemas.py`,`router.py`,`exceptions.py`; `test_transformer_service.py`,`test_transformer_registry_api.py`. *Migration:* none. *Deps:* Sprint 2. *Tests:* model/repo/service/API per §Part J. *Acceptance:* create/edit typed & registered transformers; classification stored, never derived; advisory inconsistency surfaced; legacy payloads still accepted; uniqueness generalised (excl. ENTERED_IN_ERROR). *Out of scope:* frontend; constraint tightening; `transformer_type` removal. *Committable:* yes (backward-compatible).

**Sprint 4 — Frontend endpoint workflow.** *Objective:* structured endpoint editor + list/detail/filter + terminology. *Files:* `TransformerCreatePage`,`TransformerDetailPage`,`TransformerListPage`,`api.ts`,`types.ts`, their tests. *Migration:* none. *Deps:* Sprint 3. *Tests:* frontend per §Part J. *Acceptance:* classification-first workflow; Registered/Typed controls; Malaysian terminology; no silent classification overwrite; edit round-trip. *Out of scope:* `transformer_type` removal. *Committable:* yes.

**Sprint 5 — Classification migration & constraint tightening.** *Objective:* reconcile legacy `transformer_type`, close the compat window, enforce constraints. *Files:* Revision **0029**; service/schemas/frontend cleanup (drop `transformer_type` read/write/UI); exception-report tooling. *Migration:* 0029 (NOT NULL `engineering_endpoint_kind_id`, nullable `voltage_yard_id`, XOR CHECK; resolve `transformer_type` via the Sprint 0A approved mapping only). *Deps:* Sprints 3–4 + **confirmed migration-workbench release readiness**. *Tests:* constraint enforcement; approved exact values mapped (`Interbus Transformer`→`INTER_BUS`, `Load Transformer`→`LOAD`); unknown/`Auto` values reported not mapped; legacy-path removal. *Acceptance:* XOR enforced; `transformer_type` retired (or explicitly retained-with-reason for unresolved rows per Project Owner); no silent mapping. **Legacy write compatibility must NOT be removed until: (1) the migration workbench has been updated to the new contract; (2) its relevant fixtures and mappings pass; (3) release coordination is confirmed.** *Out of scope:* three-winding; PSS/E endpoint correlation. *Committable:* yes (gated on workbench readiness for the write-path change).

**Sprint 6 — Regression, UAT, doc sync.** *Objective:* full regression + 14 UAT scenarios + docs. *Files:* `equipment-registry-module.md` (update Phase 3.5 body in place to the endpoint model), `CHANGELOG.md` (newest-first completion entry), completion report. *Migration:* none. *Deps:* Sprint 5. *Tests:* full backend + frontend suites; real-PostgreSQL migration verification; UAT. *Acceptance:* all suites green; 14 UAT scenarios pass; docs synchronized; ADR-028/EDR-011 unchanged. *Out of scope:* new capability. *Committable:* yes.

---

## Risk analysis & mitigations

- **Unknown legacy `transformer_type` values** → never auto-map; Sprint 0 profile + explicit approved mapping; unknowns retained + reported; classification stays nullable so unknowns don't block.
- **Migration ordering / constraint on populated tables** → split 0028 (permissive+backfill) from 0029 (tighten); verify backfill before tightening; real-PostgreSQL migration tests.
- **Frontend/backend contract mismatch** → additive read DTOs + short explicit compat window; ship backend (Sprint 3) before frontend (Sprint 4).
- **Breaking `TransformerTerminal` references** → terminal PK/identity never changes; regression suite over ALSF/UFLS/sensitive-customer/network-model/PSS-E each sprint.
- **Uniqueness ambiguity** → endpoint-pair descriptor with typed `(kind, nominal_voltage)`; never label; exclude `ENTERED_IN_ERROR`; Sprint 0 confirms current status-awareness.
- **Classification–endpoint inconsistency** → advisory, never silent reclassification (EDR-011 §8); consistency surfaced as a finding.
- **`endpoint_label` misused as identity** → CHECK/tests forbid its use in any key, FK, or uniqueness; label is display-only text.
- **PSS/E correlation assumptions** → correlation keys on buses/voltage, not `transformer_type`; endpoint-correlation deferred (ADR-028) — no change this scope.
- **Migration workbench assumptions** → `app/transformer_migration/` is a downstream API client; coordinate its adoption of the new create contract in its own repo during the compat window; **do not modify it here**.
- **Pre-existing uncommitted branch work (Sprint 1 operational prerequisite)** → equipment-registry and frontend files already carry uncommitted changes overlapping future Sprint 3/4 files. **Before Sprint 1 implementation begins, the repository owner must choose one controlled isolation strategy:** **(A) Preserve & commit** the accepted pre-existing work as its own coherent, tested change first; **(B) Isolated worktree/branch** cut from the correct accepted commit, then deliberately bring in required accepted docs + prerequisite code; **(C) Explicitly include** the existing work only if it is known to be part of the same approved implementation sequence and can be reviewed coherently. This is an **operational prerequisite, not an architectural stop condition.** Sprint 0A does not stash, reset, revert, commit, branch, or create a worktree.
- **`endpoint_kind` representation (resolved, Sprint 0A)** → implemented as the `engineering_endpoint_kind` reference table per ADR-028 §1; no ADR amendment required; application constants may mirror the codes only.

---

## Stop conditions (halt and escalate — do not resolve by convenience)

1. **`endpoint_kind` representation — RESOLVED (Sprint 0A):** implemented as the `engineering_endpoint_kind` reference table per ADR-028 §1; the earlier CHECK-enum recommendation is withdrawn; **no ADR amendment required.**
2. **Classification-consistency policy — CONFIRMED advisory (Sprint 0A):** consistency is `ADVISORY`, non-blocking, non-rewriting (representation integrity remains blocking). This matches ADR-028's "engineer-asserted, endpoints are evidence" stance → no amendment. (A future move to *blocking* consistency would still require an ADR-028 amendment.)
3. **Uniqueness cannot be generalised** without changing engineering identity → ADR amendment (this plan judges it *can* be, but Sprint 0 must confirm no data pattern defeats the endpoint-pair key).
4. **Cross-substation transformers** exist in data (conflicting with ADR-028's substation-owned model) → stop; ADR clarification.
5. **Classification vocabulary conflicts** with an existing authoritative engineering record → stop; reconcile via EDR/ADR.
6. **A consumer relies on `voltage_yard_id` being non-null for every terminal** → stop (Sprint 0 must clear this; today only Equipment Registry writes it, and consumers use `transformer_terminal_id`).
7. **A migration cannot preserve `TransformerTerminal` IDs** → stop (the plan is strictly additive; any design forcing id change is rejected).
8. **No safe lifecycle stage for an incomplete classification/endpoint combination** → the plan uses `PLANNED` + advisory consistency; if a stricter gate is mandated with no Draft stage available, escalate.
9. **EDR-011 or ADR-028 conflicts with another accepted decision** → stop and report; do not proceed.

---

## Acceptance gates (per the whole effort)

Backfill preserves every `transformer_terminal_id`; XOR CHECK enforced; classification never derived/overwritten; `endpoint_label` never an identity/key; all consumers green with unchanged terminal ids; Malaysian terminology accurate (no "switchboard"); unknown legacy values reported not mapped; ADR-028/EDR-011 unchanged (save a permitted cross-reference); full backend+frontend suites and real-PostgreSQL migration verification pass; 14 UAT scenarios pass.
