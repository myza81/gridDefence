# Sensitive Customer Registry — Implementation Specification

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) (v1.1)

This is an **implementation specification**, not an architecture document and not code. It translates the approved [EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md), [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md), and [`sensitive-customer-registry-module.md`](sensitive-customer-registry-module.md) (all approved and committed at `920bfbe`) into an executable, phased development plan. It does not reinterpret or contradict any of its source documents; where this plan requires a decision those documents don't already make, that gap is named explicitly (§19) rather than resolved silently. Nothing in this document is code, and this task did not modify any application code, migration, test, or frontend file.

Mirrors the precedent already established by [`phase-7-operational-snapshot-correlation-implementation-spec.md`](phase-7-operational-snapshot-correlation-implementation-spec.md) — a dedicated implementation-spec document, separate from the module architecture document, bridging approved architecture to buildable increments.

> **Status update (post-ADR-013, Phase 3.7 UAT change request).** [ADR-013](../adr/ADR-013-sensitive-facility-multiple-transformer-terminals.md) replaces the single nullable `transformer_terminal_id` column on `sensitive_facility` (§5.1 below) with a many-to-many association table, `sensitive_facility_transformer_terminal(facility_id, transformer_terminal_id, added_at, added_by_user_id)`, as-built in migration `0015_sensitive_customer_registry.py`. Everywhere below that describes `transformer_terminal_id` as a single column on `SensitiveFacility`, an `UPDATE .../facilities/{id}` reassignment, or a per-facility `transformer_terminal_resolution`, treat it as superseded by ADR-013's decisions 1–5: the association is now a set (zero or more), reassignment is now `PUT /facilities/{id}/terminals` (full-set replacement, diffed and audited per actual change), and `transformer_terminal_resolution` is now a per-association fact with a facility-level aggregate for filtering. The original text is preserved unmodified below (CLAUDE.md §5.2) as the historical as-built record this spec described *before* the UAT refinement — it is not rewritten, only superseded where noted.

---

## 1. Source Documents

- [EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md) — engineering scope: the registry answers "which facilities require special consideration if a supply point is interrupted, and what is their classification," nothing about CRM, billing, GIS, or scheme decisions.
- [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md) — the five binding architecture decisions: independent bounded context; current-terminal-only attachment (implementation-scope, not a ceiling); reference-data sector/classification; facts-not-verdicts, no Cross-Scheme Compliance coupling today; zero GridDefence vocabulary.
- [`sensitive-customer-registry-module.md`](sensitive-customer-registry-module.md) — the full A8 module document this specification implements section-by-section (§5 Owned Entities, §7 Domain Model, §8 Lifecycle, §9 Business Rules, §10 Validation Rules, §11 Domain Data Elements, §12 Required Capabilities, §13 Service Interfaces, §15 Security Considerations).
- [`implementation-plan.md`](implementation-plan.md) — phase sequencing this specification fits into (this document is Phase 3.7, added additively per §2 below — no existing phase is renumbered).
- [`automatic-load-shedding-functionality-registry-module.md`](automatic-load-shedding-functionality-registry-module.md) and its as-built code (`backend/app/modules/automatic_load_shedding_functionality/`) — the nearest structural precedent this specification reuses wherever consistent with the Sensitive Customer Registry's own architecture, and deliberately departs from wherever the approved architecture requires a different shape (differences are called out explicitly, never silently copied).

## 2. Roadmap Placement

**Phase label: 3.7 — Sensitive Customer Registry.**

**Rationale.** ALSF's own phase placement (Phase 3.6) was decided by *actual dependency*, not build order: "placed here to reflect its actual dependency (Equipment Registry only)... following the precedent already set by Phase 3.5 (Transformer Registry)" ([implementation-plan.md](implementation-plan.md) §2). The Sensitive Customer Registry has the identical dependency shape — Phase 3 (Equipment Registry, for the `TransformerTerminal` reference target) and Phase 1 (IAM, for audit attribution and permissions) only. It has no dependency on PSS/E Integration (Phase 4), Network Model (Phase 5), or any scheme module. Phase 3.7 is therefore the smallest safe additive label: it continues the exact numbering convention already established twice (3.5, 3.6) for unplanned, additive Engineering Registry domain modules, renumbers nothing, and correctly reflects that this module could be built any time after Phase 3 completes — including before Phase 4, exactly as ALSF's own eventual build order (after Phase 4/5, despite its Phase 3.6 label) already demonstrates that the label reflects dependency, not literal build sequence.

**Sequencing relative to other phases:**
- **Critical Infrastructure (Phase 9):** No dependency in either direction. Sibling registries, never calling each other (ADR-012 decision 1; module doc Appendix). Sequencing between Phase 3.7 and Phase 9 is not architecturally constrained — Phase 3.7 is sequenced before Phase 6 (below) for a UFLS-driven reason, not a Phase-9-driven one.
- **UFLS (Phase 6), UVLS (Phase 7), EMLS (Phase 8):** Each phase's Selection of Shedding Actions must call this registry's read interfaces during Sensitive Customer Review (01-engineering-philosophy.md §5 Step 4; 03-system-workflow.md). **Phase 3.7 is architecturally dependent only on Phase 1 (IAM) and Phase 3 (Equipment Registry) — nothing prevents it from being completed well before Phase 6 begins, and it must be.** [implementation-plan.md](implementation-plan.md)'s stub-then-real client pattern remains documented as a general contingency mechanism (the same one Cross-Scheme Compliance uses at the Phase 6–10 seam, §5), but it exists here **only as a fallback against schedule slippage, never as the planned path** — Phase 3.7 is expected to be complete before Phase 6 begins, exactly as Phase 3.6 (ALSF) already was, so that UFLS, UVLS, and EMLS consume the real Sensitive Customer Registry service contract from their own first commit, with no scheme module ever actually needing the stub for this dependency. Wording anywhere in this plan that could be read as treating "build it later, stub it for now" as an equally-valid default for this specific dependency is corrected by this paragraph — it is not. This sequencing requirement introduces no scheme-specific behaviour into Phase 3.7 itself (§3, §18): the registry's own service contract remains identical regardless of which scheme module calls it, or when.
- **Cross-Scheme Compliance (Phase 10):** No dependency. This registry is explicitly not wired into compliance rules today (ADR-012 decision 4). If a future Rule 3 is ever approved, that is a new ADR and a new increment on top of this specification, not assumed here.

This specification updates [implementation-plan.md](implementation-plan.md) directly (§18 below records exactly what changed there); no other roadmap document is modified by this task.

## 3. Scope and Non-Scope

**In scope:** everything named in [`sensitive-customer-registry-module.md`](sensitive-customer-registry-module.md) §5 (Owned Entities) through §16 (Testing Requirements) — a working, testable `sensitive_customer_registry` backend module and its corresponding frontend module, following the increments in §15.

**Explicitly out of scope for this module, permanently (not merely deferred — CLAUDE.md §21, EDR-008, module doc §4):**

- UFLS, UVLS, or EMLS rule design of any kind.
- Cross-Scheme Compliance rules — this registry is not wired into any compliance rule in this phase (§19 records this as an open question for a *future* phase, not this one).
- Blocking, approval, or override logic of any kind — the registry returns facts only (module doc §9 rule 6).
- Stage restrictions or scheme-specific override records.
- Alternate or backup supply modelling, supply priority, or supply-history tables (ADR-012 decision 2; §6 below explains why the schema still tolerates this being revisited later without redesign).
- Active-supply detection from real-time/SCADA/EMS systems.
- GIS, mapping, or geographic coordinate data.
- CRM, billing, or customer-account management.
- Distribution-network topology.
- Verification workflows, approval workflows, or facility "certification" of any kind (Agreed Engineering Principle 8; module doc §8).
- Automatic facility discovery from PSS/E, or automatic classification changes of any kind — every field on `SensitiveFacility` is set only by an authenticated, authorized human action.
- Any change to Critical Infrastructure's own (not-yet-built) implementation.

## 4. Backend Module Boundaries

**New module: `backend/app/modules/sensitive_customer_registry/`**, structured exactly like `automatic_load_shedding_functionality/` (the nearest precedent, §1): `models.py`, `schemas.py`, `service.py`, `repository.py`, `router.py`, `bootstrap.py`, `dependencies.py`, `exceptions.py`, `seed.py` (new — reference-data seeding, §11), `tests/`.

**Not added to Core Platform's `app/reference_data/` package.** `FacilitySector` and `SensitivityClassification` are module-owned reference data (ADR-012 decision 3; module doc §7.2), the first implemented precedent of this pattern in this codebase (Critical Infrastructure's parallel `CriticalityLevel` precedent is documented but not yet implemented). They live inside `sensitive_customer_registry/models.py`, not `app/reference_data/models.py` — this is a deliberate departure from Core Platform's reference-data package, not an oversight, because these two tables are this module's own domain vocabulary (facility sector, sensitivity tier), never referenced by any other module, exactly the boundary CLAUDE.md §11.3/§11.4 draws between shared cross-cutting reference data and module-owned classification data.

**Cross-module reads — exact methods to call, no new Equipment Registry methods required.** `EquipmentRegistryService.get_transformer_terminal_summary(id)` (existence check at write time) and `EquipmentRegistryService.get_transformer_terminal_identity(id)` (display-identity composition for list/detail enrichment) already exist (added for ALSF's benefit) and are reused as-is — no new Equipment Registry service method is required for this module. `IAMService.has_permission`/`get_user` are consumed identically to every other module (CLAUDE.md A1) — no repository import ever crosses a module boundary.

## 5. Backend Domain Model

### 5.1 `SensitiveFacility`

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `Uuid` (PK, `uuid4` default) | No | CLAUDE.md A5 — genuine business-entity identity. |
| `name` | `String(255)` | No | Free text (Agreed Engineering Principle 2; module doc §7.3). No uniqueness constraint — two distinct facilities may share a name (module doc §10). |
| `facility_sector_id` | `SmallInteger`, FK → `facility_sector.id` (`ondelete="RESTRICT"`) | No | Every facility has exactly one sector (module doc §9 rule "facility must have exactly one sector"). |
| `sensitivity_classification_id` | `SmallInteger`, FK → `sensitivity_classification.id` (`ondelete="RESTRICT"`) | No | Every facility has exactly one classification. |
| `transformer_terminal_id` | `Uuid`, FK → `transformer_terminal.transformer_terminal_id` (`ondelete="RESTRICT"`) | **Yes** | Current supply point only (ADR-012 decision 2). Nullable — a facility may be registered before its supply point is confirmed (module doc §7, §9 rule 5). **No `circuit_terminal_id` column exists** — the approved architecture scopes this registry to Transformer Terminal only, unlike ALSF's Circuit/Transformer XOR (module doc §6). |
| `lifecycle_status` | `String(20)`, CHECK `IN ('ACTIVE','ARCHIVED','ENTERED_IN_ERROR')` | No, default `'ACTIVE'` | §7 below. Deliberately **not** `'DECOMMISSIONED'` — ALSF's terminology does not apply here (task instruction; module doc §8). |
| `remarks` | `Text` | Yes | Free text. |
| `created_at` / `updated_at` | `DateTime(timezone=True)`, `server_default=func.now()` | No | Standard pattern. |
| `created_by_user_id` / `updated_by_user_id` | `Uuid`, FK → `user.user_id` (`ondelete="RESTRICT"`) | No | CLAUDE.md A4/A10 — traceable creator/modifier. |

**Uniqueness — the deliberate inverse of ALSF.** There is **no unique or partial-unique index on `transformer_terminal_id`**. Any number of `SensitiveFacility` rows may reference the same terminal concurrently (module doc §7, §9 rule 3 — "a single bay might supply both a hospital and an adjacent government building"). A future implementer must not copy ALSF's partial-unique-index pattern here by analogy; this is the single most important structural difference from the ALSF precedent and is called out again in §15 Increment 1's non-goals.

**Indexes (plain, non-unique):** `transformer_terminal_id`, `facility_sector_id`, `sensitivity_classification_id`, `lifecycle_status`.

**Deletion restriction:** No hard delete, ever (CLAUDE.md §11.6). `Entered in Error` is the only correction mechanism for a record that should never have existed as valid engineering data.

**Treatment of a Transformer Terminal that is later archived, decommissioned, or entered in error in Equipment Registry:** this module does **not** subscribe to Equipment Registry events (none exist) and does **not** react automatically. The stored `transformer_terminal_id` is tolerated as "unknown, not invalid" — exactly ALSF's own established tolerance (module doc §10). A stale reference is not blocked, not auto-nulled, and does not force a lifecycle transition.

**Correction — a stale/unresolvable terminal reference must never cause the facility record itself to disappear from a read.** The registry is authoritative for the facility fact; Equipment Registry's inability to currently resolve a terminal's identity is a separate, *engineering-impact* condition, not grounds to erase or hide the facility. Concretely: `get_transformer_terminal_identity(id)` returning `None` for a facility's stored `transformer_terminal_id` must **only** affect that facility's *displayed identity string* (§7's `"Substation | Voltage | Bay"` composition), never whether the facility row itself is included in `list_facilities`, `get_facility_detail`, or any other read. This is a correction to the previous draft's phrasing, which described ALSF's "returns `None` for orphaned refs" tolerance without stating explicitly that the *containing row* is never dropped as a result — for `SensitiveFacility`, where the facility (not the terminal) is the entity of record, that distinction matters and is now made explicit. See §9 for the three-way status this specification introduces to make "terminal resolved" vs. "terminal unresolved" vs. "facility lifecycle status" independently visible, rather than conflating an Equipment Registry resolution failure with anything about the facility's own state.

Continuous, *automated* reconciliation (a scheduled job that scans for and flags stale references, or any automatic lifecycle mutation triggered by one) is named as a Future Extension (module doc §17) and remains explicitly **not** built in this specification's increments — this correction makes the *existing* facts visible on every normal read, which is a materially smaller and different thing than building a reconciliation subsystem, and is required now precisely so that a proactive reconciliation report is not the only way to discover a stale reference (§19).

### 5.2 `FacilitySector` (module-owned reference data)

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `id` | `SmallInteger` (PK) | No | Stable surrogate key, mirroring `app/reference_data/models.py`'s `_ReferenceKey` pattern (`Integer().with_variant(SmallInteger(), "postgresql")` for SQLite test compatibility) — replicated locally in this module, not imported from Core Platform's private helper, since this table is not a Core Platform table (§4). |
| `code` | `String(50)`, `UNIQUE` | No | Stable machine key (e.g. `HEALTHCARE`, `SECURITY_DEFENCE_EMERGENCY`). Never changes after creation — this is what a future non-GridDefence consumer or any programmatic filter keys against, never the human-editable `label`. |
| `label` | `String(150)` | No | Human-facing display text. **Renamable** — see §10. |
| `sort_order` | `SmallInteger` | No | Display ordering. Not semantically load-bearing (unlike `SensitivityClassification`'s). |
| `description` | `Text` | Yes | |
| `is_active` | `Boolean` | No, default `True` | Soft-retirement flag — see §10. Not the same concept as `SensitiveFacility.lifecycle_status`; this is reference-data activation, not an engineering-fact lifecycle. |
| `created_at` / `updated_at`, `created_by_user_id` / `updated_by_user_id` | as §5.1 | No | Unlike Core Platform's read-only-seeded reference tables (§11), this table is genuinely admin-editable (ADR-012 decision 3), so it carries the same accountability columns as any other administered entity. |

### 5.3 `SensitivityClassification` (module-owned reference data)

Identical shape to §5.2, with `sort_order` **semantically meaningful** here — it is the ordering a future consumer can use to reason about "at least Medium sensitivity" without hardcoding tier semantics (module doc §7.2). `code` values: `HIGH` (`sort_order=1`), `MEDIUM` (`sort_order=2`), `LOW` (`sort_order=3`) — lower `sort_order` = higher sensitivity, matching the natural reading order of the approved three-tier list.

### 5.4 `sensitive_customer_registry_audit_log` (single shared audit table)

Per module doc §5 — **one** audit table "covering every owned entity above," not one per entity. Polymorphic via three mutually-exclusive nullable foreign keys plus a discriminator, using the exact same XOR-by-`CheckConstraint` technique already established in this codebase by ALSF's `circuit_terminal_id`/`transformer_terminal_id` pair — extended here from two arms to three:

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `log_id` | `Integer` (PK, autoincrement) | No | |
| `subject_type` | `String(30)`, CHECK `IN ('SENSITIVE_FACILITY','FACILITY_SECTOR','SENSITIVITY_CLASSIFICATION')` | No | Query-ergonomics discriminator (technically derivable from which FK is set, but stored directly for cheap filtering — the same reasoning ALSF's own `target_type` column already applies alongside its XOR). |
| `sensitive_facility_id` | `Uuid`, FK → `sensitive_facility.id` (`ondelete="RESTRICT"`) | Yes | |
| `facility_sector_id` | `SmallInteger`, FK → `facility_sector.id` (`ondelete="RESTRICT"`) | Yes | |
| `sensitivity_classification_id` | `SmallInteger`, FK → `sensitivity_classification.id` (`ondelete="RESTRICT"`) | Yes | |
| `field_name` | `String(100)` | No | One row per changed field, exactly ALSF's convention. |
| `old_value` / `new_value` | `Text` | Yes | Stringified, exactly ALSF's convention. |
| `changed_at` | `DateTime(timezone=True)`, `server_default=func.now()` | No | |
| `changed_by_user_id` | `Uuid`, FK → `user.user_id` (`ondelete="RESTRICT"`) | No | |
| `change_reason` | `Text` | Yes | **Not** `NOT NULL` at the schema level — mandatory-reason enforcement for lifecycle transitions is a **service-layer** rule (§8), not a column constraint, because the same table also carries optional-reason field edits (§6). |

**`CheckConstraint`:** exactly one of `sensitive_facility_id`, `facility_sector_id`, `sensitivity_classification_id` is non-null, and it must match `subject_type`.

**Indexes:** `(sensitive_facility_id, changed_at DESC)`, `(facility_sector_id, changed_at DESC)`, `(sensitivity_classification_id, changed_at DESC)`, `subject_type`.

## 6. Data Integrity Rules

| Question | Answer | Basis |
|---|---|---|
| Must facility names be unique (globally, by terminal, or not at all)? | **Not at all.** No uniqueness constraint on `name` alone. | Module doc §10 — explicit. |
| May multiple facilities reference the same Transformer Terminal? | **Yes, without limit.** No uniqueness constraint on `transformer_terminal_id`. | Module doc §9 rule 3; ADR-012 decision 1 comparison table. |
| May a facility be reassigned from one terminal to another? | **Yes.** A field-level correction on the existing row (no new historical row). | ADR-012 decision 2; module doc §9 rule 4. |
| How is reassignment audited? | **One append-only audit row, `field_name='transformer_terminal_id'`, containing at minimum: the previous Transformer Terminal identifier (`old_value`), the new Transformer Terminal identifier (`new_value`), a mandatory non-empty `change_reason`, the acting `changed_by_user_id`, and the `changed_at` timestamp.** Unlike ordinary metadata-field edits (§5.4, where `change_reason` is optional), **`change_reason` is service-layer-enforced as required specifically for `transformer_terminal_id` changes** — corrected from "recommended" in the prior draft to a firm rule, mirroring the same mandatory-reason treatment already given to lifecycle transitions (§7), since a supply-point correction carries the same "particular emphasis" module doc §14 already assigns it. **No supply-history domain entity is introduced** — the audit log remains the only historical record of a facility's prior terminal associations, consistent with `SensitiveFacility` storing only the current association (ADR-012 decision 2). | Module doc §14; task Correction 5. |
| Do archived or entered-in-error records affect uniqueness? | **Not applicable** — no uniqueness constraint exists on any facility field, so lifecycle status cannot "free up" a name or terminal slot that was never constrained. | Derived from the two answers above. |
| Do inactive reference-data values remain valid for historical/existing records? | **Yes.** `ON DELETE RESTRICT` plus never-hard-delete means an existing `SensitiveFacility.facility_sector_id`/`sensitivity_classification_id` FK is untouched by deactivating the referenced row. | §10. |
| May an inactive sector or classification be assigned to a **new** facility, or to an existing facility being reassigned? | **No.** Enforced at the service layer (not a DB constraint, since the DB cannot distinguish "existing row keeps a stale FK" from "new row being inserted/updated" without a trigger, which this project does not use). | §10; CLAUDE.md §11.8 ("application logic supplements database constraints"). |
| What happens when a referenced Transformer Terminal is later archived/decommissioned/entered-in-error in Equipment Registry? | **Nothing automatic — and the facility is never hidden as a result.** "Unknown, not invalid" tolerance (§5.1). No cascade, no forced lifecycle transition, no silent null-out, and no omission of the facility row from any read — the read-time `transformer_terminal_resolution` field (§9) surfaces the condition (`UNRESOLVED`) directly alongside the facility's own `lifecycle_status`, so the two are always independently visible rather than one masking the other. | Module doc §10; §5.1, §9 (corrected). |
| How is cross-module validation performed without importing another module's repository? | `EquipmentRegistryService.get_transformer_terminal_summary(id)` at write time only (create, and any update that changes `transformer_terminal_id`) — a live existence check, not a stored denormalization — plus `get_transformer_terminal_identity(id)` at read time for display/resolution-status enrichment (§9), never a stored denormalization either. | CLAUDE.md A1; §4 above. |

## 7. Lifecycle Transition Model

Per module doc §8 exactly — **not** ALSF's binary model, **not** the Canonical Version Lifecycle (CLAUDE.md A3):

```text
Active ──────────► Archived  (reversible: Archived ──────────► Active)
  │                    │
  └────────► Entered in Error ◄────────┘   (terminal — no transition out)
```

| Transition | Allowed? | Reason required? | Permission | Audit event | Effect on lookups | Effect on dashboard metrics |
|---|---|---|---|---|---|---|
| `Active → Archived` | Yes | **Yes, non-empty, enforced at service layer** | `.write` | `field_name='lifecycle_status'`, old=`ACTIVE`, new=`ARCHIVED` | Excluded from every consumer-facing read (§9) from this point | Moves from "active" bucket to "archived" bucket |
| `Active → Entered in Error` | Yes | **Yes, non-empty** | `.write` | as above, new=`ENTERED_IN_ERROR` | Excluded | Moves to "entered in error" bucket |
| `Archived → Active` | **Yes** (module doc explicitly makes this reversible, unlike ALSF's `Decommissioned`) | **Yes, non-empty** | `.write` | as above, old=`ARCHIVED`, new=`ACTIVE` | Re-included in reads | Moves back to "active" bucket |
| `Archived → Entered in Error` | Yes | **Yes, non-empty** | `.write` | as above | Excluded (already was) | Moves to "entered in error" bucket |
| `Entered in Error → *` | **Prohibited, no exceptions.** | N/A | N/A | N/A | N/A | N/A |

**API behaviour:** four dedicated action endpoints (§12), never a generic "set lifecycle_status" PATCH field — this makes the reason requirement and the terminal-state prohibition structurally impossible to bypass through the general metadata-update endpoint. **Frontend behaviour:** four distinct action buttons/dialogs, each requiring the reason field before submission; `Entered in Error → *` actions are never rendered as available once a record is in that state. **Tests:** one test per row of the table above, plus a rejection test for every prohibited transition (`Entered in Error → Active`, `Entered in Error → Archived`).

## 8. Reference-Data Administration Strategy

Both `FacilitySector` and `SensitivityClassification` are **genuinely admin-editable**, a deliberate departure from Core Platform's read-only-seeded reference tables (§4, §11) — this follows directly from CLAUDE.md §11.3/A7 ("engineering parameters must not be hidden... must be versioned, auditable, and visible to authorised users") and the task's own explicit instruction that administrators must be able to maintain this data "without changing application code."

| Capability | Design |
|---|---|
| **Creation** | `POST` endpoint, `.manage_reference_data` permission (§13) — Administrator only. New `code` values must be unique; `sort_order` defaults to `max(existing) + 1` unless specified. |
| **Editing** | `PATCH` — `label`, `description`, `sort_order` are editable. **`code` is immutable after creation** — it is the stable identifier every historical audit row and any future non-GridDefence consumer keys against; changing it would silently reinterpret history. |
| **Ordering** | `sort_order` is a plain integer, re-editable at any time; no automatic renumbering on insert/delete (an admin may leave gaps). |
| **Activation/inactivation** | `is_active` boolean, toggled via the same `PATCH`. This is the "equivalent lifecycle" the reference table needs — **not** the `Active`/`Archived`/`Entered in Error` vocabulary, which belongs only to `SensitiveFacility` (module doc §8's lifecycle is an engineering-fact lifecycle; reference-data activation is a distinct, simpler on/off concept). |
| **Prevention of unsafe deletion** | **No `DELETE` endpoint exists for either reference table**, ever. `ON DELETE RESTRICT` on both FK columns makes a hard delete fail loudly at the database level even if attempted directly, but the API surface does not expose the operation at all — deactivation (`is_active=false`) is the only supported retirement path. |
| **Default initial seed values** | The eight approved sectors and three approved classifications (§11). |
| **Stable identifiers** | `code` (string) is the stable identifier for programmatic use; `id` (SmallInteger) is the stable identifier for FK relationships. Neither is ever reused or renumbered. |
| **Audit history** | Every create/edit/activate/deactivate writes a row to §5.4's shared audit log, `subject_type='FACILITY_SECTOR'` or `'SENSITIVITY_CLASSIFICATION'`. |
| **Frontend administration** | Two admin pages (Increment 8), gated by `.manage_reference_data`, not by `.write`. |
| **Historical record preservation** | Renaming a `label` after values are in use is **allowed** — existing `SensitiveFacility` rows keep the same FK, so they automatically display the new label. Historical auditability of the *label change itself* is preserved by the audit log (old label vs. new label), never by preventing the rename. This resolves the task's explicit question ("can labels be renamed after use, and how is historical auditability preserved") directly: rename freely, audit the rename. |

## 9. Stable Service Contracts

Per module doc §13 exactly, implemented in `service.py`, consumable by any future module (or future non-GridDefence application, once this module is eventually extracted per CLAUDE.md §6/F6) without ever importing `repository.py` or any ORM model:

```python
def has_sensitive_facility(transformer_terminal_id: UUID) -> bool: ...

def get_sensitive_facilities_for_transformer_terminal(
    transformer_terminal_id: UUID,
) -> list[SensitiveFacilitySummary]: ...

def get_sensitive_facilities_for_transformer_terminals(
    transformer_terminal_ids: set[UUID],
) -> dict[UUID, list[SensitiveFacilitySummary]]: ...

def list_facilities(filters: FacilityListFilters) -> Page[SensitiveFacilitySummary]: ...

def get_facility_detail(facility_id: UUID) -> SensitiveFacilityDetail | None: ...

def get_summary_counts() -> SensitiveFacilitySummaryCounts: ...  # §14
```

**Completeness semantics for the batch contract:** `get_sensitive_facilities_for_transformer_terminals` resolves **entirely against this module's own table** — `transformer_terminal_id` is a value already stored on `SensitiveFacility`, never re-resolved live against Equipment Registry on the read path. Consequently there is **no partial-failure mode**: every requested Transformer Terminal ID in the input set receives a key in the returned mapping, with a (possibly empty) list as its value. Equipment Registry's own availability does not affect this lookup's completeness or correctness — this directly satisfies the task's "distinguish complete/unavailable/partially-unresolved" requirement by making partial failure structurally impossible for this specific contract, rather than needing a status flag to communicate it.

**All read interfaces degrade gracefully** for an unregistered or orphaned terminal ID — empty list / `False` / `None`, never an exception (module doc §13, mirroring ALSF/Network Model/PSS/E Integration's established "unknown, not invalid" tolerance).

**Three independently-surfaced facts, not one conflated status (correction).** `SensitiveFacilitySummary` and `SensitiveFacilityDetail` carry **three separate fields**, each answering a different question, per the task's explicit requirement to distinguish "terminal resolved," "terminal unresolved or unavailable," and "facility lifecycle status":

```python
class TransformerTerminalResolution(str, Enum):
    NOT_ASSIGNED = "NOT_ASSIGNED"   # transformer_terminal_id is null — no supply point recorded yet
    RESOLVED = "RESOLVED"           # transformer_terminal_id is set and Equipment Registry currently resolves it
    UNRESOLVED = "UNRESOLVED"       # transformer_terminal_id is set but Equipment Registry could not resolve it now

class SensitiveFacilitySummary:
    ...
    transformer_terminal_id: UUID | None
    transformer_terminal_resolution: TransformerTerminalResolution
    transformer_terminal_identity: str | None   # e.g. "IGBK | 33kV | Transformer T1" — present only when RESOLVED
    lifecycle_status: Literal["ACTIVE", "ARCHIVED", "ENTERED_IN_ERROR"]
    ...
```

`transformer_terminal_resolution` is computed at read time in the service layer from the existing `get_transformer_terminal_identity(id)` call (§4) — `None` returned by Equipment Registry maps to `UNRESOLVED`, not to omission of the row. `lifecycle_status` is reported independently and is never inferred from or conflated with resolution status — a facility can be `ACTIVE` with an `UNRESOLVED` terminal (the common "stale reference" case this correction targets), `ARCHIVED` with a `RESOLVED` terminal, and so on; all nine combinations are valid and must render distinctly in both the API response and the frontend (§10, §16).

**Never calls, and is never called by** (module doc §13, ADR-012 Service Interface Expectations): Network Model, the Automatic Load Shedding Functionality Registry, Critical Infrastructure, or any scheme module's repository. This is enforced structurally by never importing those modules' `service.py` or `repository.py` from this module, and is verified by the architectural test in §16.

**This is the contract UFLS/UVLS/EMLS's Selection of Shedding Actions will call** for the batch case (a boundary pocket's resolved terminal-id set) and the single-lookup case (a direct candidate). No `UFLS`-, `UVLS`-, `EMLS`-, `Stage`-, or `Pocket`-specific method name or parameter exists anywhere in this service — the caller supplies plain Transformer Terminal IDs and interprets the plain facts returned, exactly as ADR-012 decision 5 requires.

## 10. API Surface Plan

REST resources under `/api/v1/sensitive-customer-registry`, following this project's existing conventions (pagination, filtering, sorting, structured errors — CLAUDE.md A9) exactly as ALSF's own router already demonstrates. **Not implemented in this task** — this is the plan for Increment 6.

| Method | Path | Purpose | Permission |
|---|---|---|---|
| `GET` | `/facilities` | Paginated, filtered, sorted list (filters: `facility_sector_id`, `sensitivity_classification_id`, `lifecycle_status`, `transformer_terminal_id`, `transformer_terminal_resolution` — so an engineer or administrator can specifically triage `UNRESOLVED` facilities without a separate report, §9 — plus substation/voltage-level filters applied in Python after per-row identity enrichment — exactly ALSF's established pattern. Every response row always includes `transformer_terminal_resolution` and `lifecycle_status` as independent fields, §9 — a row is never omitted due to resolution failure.) | `.read` |
| `GET` | `/facilities/{id}` | Detail | `.read` |
| `POST` | `/facilities` | Create | `.write` |
| `PATCH` | `/facilities/{id}` | Metadata edit (name, sector, classification, terminal reassignment, remarks) — **never** `lifecycle_status` | `.write` |
| `POST` | `/facilities/{id}/archive` | `Active → Archived` | `.write` |
| `POST` | `/facilities/{id}/reactivate` | `Archived → Active` | `.write` |
| `POST` | `/facilities/{id}/entered-in-error` | `* → Entered in Error` | `.write` |
| `GET` | `/facilities/{id}/audit-log` | Paginated audit history for one facility | `.read` |
| `GET` | `/facilities/by-transformer-terminal/{terminal_id}` | Single-terminal lookup (API-layer equivalent of §9's single-lookup contract) | `.read` |
| `POST` | `/facilities/batch-lookup` | Body `{"transformer_terminal_ids": [...]}` → mapping response. **`POST`, not `GET`**, because a boundary-pocket terminal set can exceed a safe URL query-string length — the one deliberate REST convention departure in this plan, justified explicitly here rather than silently chosen. | `.read` |
| `GET` | `/facilities/summary` | Dashboard aggregate counts (§14) | `.read` |
| `GET` | `/reference-data/facility-sectors` | List (including inactive, for admin views) | `.read` |
| `POST` | `/reference-data/facility-sectors` | Create | `.manage_reference_data` |
| `PATCH` | `/reference-data/facility-sectors/{id}` | Edit / activate / deactivate | `.manage_reference_data` |
| `GET` / `POST` / `PATCH` | `/reference-data/sensitivity-classifications[/{id}]` | Same shape as sectors | `.read` / `.manage_reference_data` |

**Errors:** `400` validation (unknown/inactive reference value, malformed request), `404` not found, `403` permission failure (fail-closed, per IAM's existing `require_permission` dependency), `409` conflict (e.g. an attempted `Entered in Error → *` transition — modeled as a lifecycle-rule violation, not a generic 400).

## 11. Dashboard Metrics Plan

Per the task's explicit instruction and module doc §17 — **descriptive only, never implying scheme eligibility, compliance, blocking, or operational safety** (this is a hard constraint, not a style preference, given EDR-008's "facts, not decisions" boundary).

**No standalone Dashboard module exists yet** (Phase 11, not yet built — confirmed absent in the codebase). This specification does **not** build a cross-module Dashboard page. It does two things Phase 11 can later consume:

1. **`get_summary_counts()` service method** (§9) — returns: active facility count; count by sector; count by sensitivity classification; archived count; entered-in-error count; recent-changes count (last N audit events). Substation/terminal-level counts are **not** computed server-side as a raw count (would require joining every row against Equipment Registry) — instead, the existing paginated `list_facilities` filtered by `transformer_terminal_id`, combined with client-side aggregation on the (already terminal-scoped) result set, covers this without a new server-side aggregation path. This keeps the service contract small and avoids speculative aggregation methods no confirmed consumer needs yet (CLAUDE.md §21).
2. **A lightweight in-module summary strip** on the frontend's `FacilityListPage` itself (Increment 11) — the same counts, rendered as a small stats row above the table, exactly as a registry's own list page reasonably shows its own totals. This is **not** the Phase 11 cross-module Dashboard; it is this module's own read of its own data, no different in kind from a table showing a row count.

## 12. Permission Model

Reuses IAM's existing `require_permission`/`has_permission` infrastructure exactly as ALSF does (§1) — **no new security framework, and no new registry-maintainer role**. Three permission codes, reflecting the Project Owner's decision that this registry is global authoritative engineering knowledge — administered by application administrators, consumed (read-only) by scheme engineers who do not own or casually modify it:

| Permission code | Grants | Administrator | Engineer | Viewer |
|---|---|---|---|---|
| `sensitive_customer_registry.read` | List/detail/audit-log/lookup/batch-lookup/summary of **active** registry data required for engineering work | ✓ | ✓ | **✗ by default** |
| `sensitive_customer_registry.write` | Create and edit `SensitiveFacility` records (including Transformer Terminal reassignment) and all four lifecycle actions (archive/reactivate/entered-in-error) | ✓ | **✗** | ✗ |
| `sensitive_customer_registry.manage_reference_data` | Facility Sector / Sensitivity Classification create/edit/activate/deactivate | ✓ | ✗ | ✗ |

**Corrected permission model — Administrator-only mutation.** Every mutating action on this registry — facility creation, metadata edits, Transformer Terminal reassignment, archive, reactivate, entered-in-error, and all reference-data administration — requires `.write` or `.manage_reference_data`, and **neither permission is granted to the Engineer role**. This is a deliberate departure from ALSF's precedent (where Engineer holds `.write`): ALSF's write actions are routine scheme-preparation data entry by the engineers who use it day to day, while this registry is global authoritative engineering knowledge that scheme engineers consume but do not own. Engineers hold `.read` only — sufficient for every engineering-work read need (candidate evaluation, audit-history review) without conferring any ability to alter the underlying facts. `.read` also covers audit-history viewing (`GET /facilities/{id}/audit-log`, §10), consistent with "Administrators and Engineers may view audit history, subject to the existing application access model" — no separate audit-visibility permission is introduced.

**No new role is introduced in this phase.** A distinct, broader "Sensitive Customer Registry Viewer" role (module doc §15's own suggestion, for non-Engineer/non-Administrator read access) remains a possible future addition but is explicitly not built now — this specification's permission model uses only the three existing baseline roles (Administrator, Engineer, Viewer), exactly as the task requires.

**Module-to-module service calls (§9) are never gated by a per-request human permission check** — the calling module, not an end user, is the caller, exactly mirroring ALSF's and Critical Infrastructure's own identical distinction (module doc §15). This is unaffected by the Administrator-only mutation correction above: a future UFLS/UVLS/EMLS read-only call to `has_sensitive_facility`/the batch lookup is a service-to-service call, not a human `.write` action, and remains ungated exactly as originally specified.

`bootstrap.py` follows ALSF's exact idempotent pattern: register the three permission codes via `IAMService.register_permission`, grant per the corrected table above via `IAMRepository.get_role_permission`-checked-then-`grant_permission_to_role` (Engineer receives `.read` only — no `.write`/`.manage_reference_data` grant row for Engineer at all), log (don't fail) if a baseline role doesn't exist yet. **Must be added to the bootstrap run-list manually** (§13/§18) — ALSF's own README documents a real incident where this step was forgotten; this specification calls it out explicitly in Increment 4's acceptance criteria to avoid repeating it.

## 13. Migration and Seed Strategy

**Migration file:** `backend/alembic/versions/0015_sensitive_customer_registry.py`, `down_revision = "0014_alsf_registry"` (current head, confirmed). Four tables, created in dependency order within one migration file (mirroring `0014_alsf_registry.py`'s exact structure — hand-written, manually reviewed, not autogenerated and blindly committed):

1. `facility_sector`
2. `sensitivity_classification`
3. `sensitive_facility` (FKs to both of the above, and to `transformer_terminal`/`user`)
4. `sensitive_customer_registry_audit_log` (FKs to all three entity tables, and to `user`)

**`downgrade()`** drops in exact reverse order: audit log → `sensitive_facility` → `sensitivity_classification` → `facility_sector`. Every `CheckConstraint`, `ForeignKeyConstraint` (`ondelete="RESTRICT"` throughout, per CLAUDE.md §11.7 — cascade delete is prohibited on engineering entities), and index from §5 is created explicitly in `upgrade()`, never left to autogenerate's default inference.

**PostgreSQL/SQLite compatibility:** the `SmallInteger`-on-Postgres / `Integer`-on-SQLite variant pattern from `app/reference_data/models.py` is replicated locally (§5.2) so the migration and the test suite's SQLite in-memory engine (§17) both work without modification.

**Reference-data seeding — deliberately follows the established manual `seed.py` convention, not migration-embedded `bulk_insert`.** `backend/app/modules/sensitive_customer_registry/seed.py` (module-owned, mirroring `app/reference_data/seed.py`'s idempotent, insert-if-missing shape). This is a **conscious continuation** of this repository's existing convention (schema via migration, data via a separate seed step) — confirmed, not merely assumed, by inspecting `backend/Dockerfile` (its `CMD` runs `uvicorn` directly, no migration or seed step) and `docker-compose.yml` (the `backend` service has no entrypoint script or `depends_on` condition tied to seeding) — **migration and seed execution are, and remain, two separate commands in every environment**, exactly as they already are for Core Platform's own reference data. The existing convention has a **documented failure mode** (`app/reference_data/README.md` records a real incident where a forgotten seed re-run silently broke a feature); this specification does not rely on that step remaining undocumented or tribal — it is specified explicitly, per environment, below, and backed by a fail-loud application-level guard.

**Installation, by environment:**

| Environment | How reference data is installed | Command(s) |
|---|---|---|
| **Local development** | Two explicit, documented commands, run in order after bringing up the database — identical shape to every other module's reference/seed data in this repository. | `cd backend && alembic upgrade head`, then `python -m app.modules.sensitive_customer_registry.seed` |
| **Automated tests** | **Not** a separate CLI invocation. The module's `tests/conftest.py` fixture calls the module's own `run_seed(db)` function directly against the test session (whether SQLite in-memory, the default per root `conftest.py`, or real PostgreSQL when `GRIDDEFENCE_TEST_DATABASE_URL` is set) as part of fixture setup — mirroring how ALSF's own `conftest.py` builds real Substation/Equipment Registry records through their own service/seed layers rather than inserting rows directly. This guarantees test data always matches the production seed content exactly (§15), with zero drift risk from hand-maintained test fixtures duplicating the seed list. | `run_seed(db)` called from `conftest.py`, not a shell command |
| **Docker Compose / deployment** | A **documented, required post-migration step**, listed explicitly in this module's own `README.md` (mirroring `app/reference_data/README.md`'s existing "Seeding and Bootstrapping" precedent, which this specification's Increment 2 acceptance criteria require reproducing here — §14) — not an undocumented step a developer must already know about. Executed once per environment after `alembic upgrade head` (itself already a required, documented Compose step per [implementation-plan.md](implementation-plan.md) §9's CI migration check) brings the schema up to date. | `docker compose exec backend python -m app.modules.sensitive_customer_registry.seed` |
| **Repeated execution (any environment)** | **Idempotent, insert-if-missing, keyed on the stable `code` column** (§5.2/§5.3) — running the command any number of times inserts only rows whose `code` is not yet present. **Critically, a re-run never reverts an administrator's subsequent edits** (a renamed `label`, an adjusted `sort_order`, a deactivated `is_active`) — the seed script only ever inserts missing `code`s, it never updates or overwrites an existing row's mutable columns. This is stated explicitly because a naive "upsert" implementation would silently undo legitimate admin edits on every re-run; this specification requires insert-only-if-missing, never upsert. | Same command as above, safe to repeat |

**Fails visibly if skipped.** Two independent layers, neither relying on the operator remembering an undocumented step:
1. **Documentation-level:** the required seed command is a first-class, numbered step in this module's own `README.md` and in Increment 2's acceptance criteria (§14) — the same visibility every other required-but-manual step (migrations, bootstrap permission registration) already has in this repository, not a lesser tier.
2. **Application-level (new for this module, mitigating the documented failure mode directly):** the `create()` service method performs an explicit, fast existence check ("does at least one row exist in `facility_sector` and in `sensitivity_classification`?") before attempting an insert, and raises a clear, actionable `ReferenceDataNotSeededError` — not a generic FK violation or an opaque 500 — naming the exact command to run, if either table is empty. This turns "reference data was never seeded" from a confusing failure discovered by an end user into an immediately diagnosable, self-explanatory error surfaced to whoever deploys or operates the environment.

**Seed values — deterministic, idempotent, matching the approved lists exactly:**

`facility_sector` (8 rows, `code` / `label` / `sort_order`):
`HEALTHCARE` / "Healthcare" / 1; `SECURITY_DEFENCE_EMERGENCY` / "Security, Defence & Emergency Services" / 2; `GOVERNMENT_PUBLIC_ADMIN` / "Government & Public Administration" / 3; `TRANSPORT` / "Transport" / 4; `UTILITIES` / "Utilities" / 5; `STRATEGIC_ECONOMIC_INFRASTRUCTURE` / "Strategic & Economic Infrastructure" / 6; `SPECIAL_PROTECTED_CUSTOMERS` / "Special or Protected Customers" / 7; `OTHER_SENSITIVE_CONSUMER` / "Other Sensitive Consumer" / 8.

`sensitivity_classification` (3 rows): `HIGH` / "High" / 1; `MEDIUM` / "Medium" / 2; `LOW` / "Low" / 3.

**Rollback for this increment:** `alembic downgrade -1` drops all four tables cleanly (no data-loss concern beyond this module's own, since nothing else references these tables yet at merge time — this module is additive only). If seeding has already run and a downgrade is later needed, re-running `upgrade()` + `seed.py` after a fix reproduces the exact same state, since seeding is idempotent and keyed on stable `code` values.

## 14. Implementation Increments

Each increment is independently reviewable and mergeable (implementation-plan.md's Guiding Principle 2), building strictly on the previous one. No increment after Increment 6 (REST API) requires any change to an earlier increment's schema or service contract — contracts are stabilized before consumer integration (planning-quality requirement, explicit).

### Increment 1 — Domain model and migration

- **Objective:** Establish the persisted schema exactly per §5, with zero business logic yet.
- **Files:** `backend/app/modules/sensitive_customer_registry/{__init__.py,models.py}`, `backend/alembic/versions/0015_sensitive_customer_registry.py`.
- **Behaviour introduced:** Four tables exist and are migratable (`upgrade`/`downgrade` both verified).
- **Validations:** All `CheckConstraint`/`ForeignKeyConstraint` from §5 present and named (`ck_...`, `fk_...`), matching `0014_alsf_registry.py`'s naming convention.
- **Tests:** `alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head` again, against real PostgreSQL, succeeds with no manual intervention (mirrors the documented process already used for `0014_alsf_registry`).
- **Acceptance criteria:** Migration reviewed line-by-line (not accepted from autogenerate output uncritically, per CLAUDE.md §11.8/[implementation-plan.md](implementation-plan.md) §5); four tables and all constraints/indexes exist in a fresh database.
- **Non-goals:** No partial-unique index on `transformer_terminal_id` (§5.1 — the deliberate inverse of ALSF; a reviewer must actively confirm this index does *not* exist, not merely that some index exists). No `circuit_terminal_id` column anywhere in this module. No seed data yet (Increment 2).

### Increment 2 — Reference-data seeding and administration (backend)

- **Objective:** `FacilitySector`/`SensitivityClassification` are seedable, creatable, editable, and (de)activatable via the service layer.
- **Files:** `seed.py`, `README.md` (new — this module's own seeding/bootstrapping runbook, mirroring `app/reference_data/README.md`'s precedent, §13), additions to `schemas.py`/`service.py`/`repository.py` for the two reference entities.
- **Behaviour introduced:** §8's full administration capability (create/edit/order/activate/deactivate), §13's seed strategy across all three environments, the `ReferenceDataNotSeededError` guard (§13).
- **Validations:** `code` uniqueness and immutability after creation; `is_active=false` never blocks an existing FK reference; create/reassign of a `SensitiveFacility` against an inactive reference value is rejected (this rule is *specified* here even though `SensitiveFacility` itself is Increment 3, since the reference-data service must expose an "is this code currently assignable" check for Increment 3 to call).
- **Tests:** seed idempotency (running twice produces no duplicates and does not revert a prior admin edit to `label`/`sort_order`/`is_active` — §13's insert-only-if-missing requirement, verified explicitly, not just assumed); `code` immutability enforced; rename-after-use preserves FK integrity and produces one audit row; deactivating a value in use does not error and does not affect existing facilities; `ReferenceDataNotSeededError` raised correctly when tables are empty, with a message naming the exact seed command.
- **Acceptance criteria:** `python -m app.modules.sensitive_customer_registry.seed` run twice produces exactly 8 + 3 rows, not 16 + 6; `README.md` documents the seed command as a required, numbered post-migration step for local development and Docker Compose (§13) — not left to be discovered only via this specification or source comments.
- **Non-goals:** No `DELETE` endpoint or repository method for either reference table (§8) — not merely "not exposed via API," genuinely not implemented at all.

### Increment 3 — Backend repository and service logic (facility CRUD)

- **Objective:** `SensitiveFacility` create/read/update (metadata) works end to end at the service layer, with all §6 validation rules enforced.
- **Files:** `repository.py`, `service.py` (facility methods), `exceptions.py`, `dependencies.py`.
- **Behaviour introduced:** `create`, `update_metadata` (field-by-field audit diffing, mirroring ALSF's `update_metadata` pattern exactly), `get_facility_detail`, existence/uniqueness validation, Transformer Terminal existence check via `EquipmentRegistryService.get_transformer_terminal_summary` (§4, §6).
- **Validations:** every row of §6's table.
- **Tests:** create with/without `transformer_terminal_id`; create against unknown terminal rejected; create against inactive sector/classification rejected; `update_metadata` reassigns terminal correctly, produces exactly one audit row with previous/new terminal IDs, reason, actor, and timestamp all populated, and **rejects the reassignment outright if `change_reason` is empty** (§6, Correction 5); concurrent facilities on one terminal succeed (the explicit inverse-of-ALSF regression test); name is never required to be unique (a positive test proving two same-named facilities can coexist).
- **Acceptance criteria:** A facility can be created with only `name`+`sector`+`classification` (no terminal), then later updated to add a terminal reference, with two audit rows total.
- **Non-goals:** No lifecycle actions yet (Increment 4). No API layer yet (Increment 6).

### Increment 4 — Audit and lifecycle actions

- **Objective:** §7's full lifecycle state machine, and §5.4's shared audit log, both fully wired.
- **Files:** `service.py` (lifecycle methods: `archive`, `reactivate`, `mark_entered_in_error`), `bootstrap.py`.
- **Behaviour introduced:** All four allowed transitions from §7's table; the `Entered in Error → *` prohibition; mandatory non-empty `change_reason` for every lifecycle transition (service-layer check, not a schema `NOT NULL`, per §5.4); permission bootstrap per §12.
- **Validations:** reason presence; terminal-state prohibition; permission enforcement (`.write` required for all four actions).
- **Tests:** one success test and one reason-omitted-rejected test per transition; two rejection tests for `Entered in Error → Active`/`Archived`; a test confirming `bootstrap.py` is actually included in the project's bootstrap run-list (regression test for the exact incident ALSF's own README documents).
- **Acceptance criteria:** A full `Active → Archived → Active → Entered in Error` sequence completes with four correctly-shaped audit rows and is then provably permanent (any further transition attempt is rejected).
- **Non-goals:** No frontend lifecycle UI yet (Increment 10).

### Increment 5 — Read and batch-lookup integration contracts

- **Objective:** §9's full stable service contract, ready for a future scheme module to call.
- **Files:** `service.py` (`has_sensitive_facility`, `get_sensitive_facilities_for_transformer_terminal`, `get_sensitive_facilities_for_transformer_terminals`, `list_facilities`, `get_summary_counts`), `schemas.py` (`SensitiveFacilitySummary`, `SensitiveFacilityDetail`, `SensitiveFacilitySummaryCounts`).
- **Behaviour introduced:** the completeness-by-construction batch contract (§9); pagination/filtering/sorting for `list_facilities`, following ALSF's exact "own-column filters at repo, cross-module filters in Python after enrichment" split; the `transformer_terminal_resolution` computation (§9, Correction 4) applied consistently across `list_facilities`, `get_facility_detail`, and the single/batch terminal lookups.
- **Validations:** batch lookup with an empty input set returns an empty mapping (not an error); batch lookup with unknown terminal IDs returns those keys mapped to empty lists, never omits them; a facility whose stored `transformer_terminal_id` cannot currently be resolved by Equipment Registry is still returned by every read method, with `transformer_terminal_resolution=UNRESOLVED` — never silently dropped.
- **Tests:** batch lookup across a set containing zero-, one-, and multi-facility terminals in the same call; `list_facilities` filter/sort/paginate combinations, including filtering specifically by `transformer_terminal_resolution=UNRESOLVED`; a dedicated test simulating `EquipmentRegistryService.get_transformer_terminal_identity` returning `None` for an otherwise-valid, `ACTIVE` facility, asserting the facility still appears in `list_facilities`/`get_facility_detail` output with `UNRESOLVED` correctly set and `lifecycle_status` unaffected; the architectural test (§16) confirming this module never imports Network Model's, ALSF's, or any scheme module's `repository.py`/`service.py`.
- **Acceptance criteria:** A simulated caller passing 500 terminal IDs (a realistic boundary-pocket size) receives a correctly-shaped, complete mapping in one call.
- **Non-goals:** No pocket resolution, no topology awareness — the input set is always caller-supplied (§4 Non-Responsibilities of the module doc).

### Increment 6 — REST API

- **Objective:** §10's full API surface, backed by Increments 3–5.
- **Files:** `router.py`, `schemas.py` (request/response DTOs), wiring into `main.py`'s router registration.
- **Behaviour introduced:** every endpoint in §10's table; structured error responses (400/403/404/409) per CLAUDE.md A9.
- **Validations:** Pydantic schema validation at the request boundary; permission dependencies exactly as §12 specifies.
- **Tests:** one API contract test per endpoint (auth-required, permission-required, happy path, each documented error code) — mirrors `test_automatic_load_shedding_functionality_api.py`'s 10-test shape, scaled to this module's larger endpoint count.
- **Acceptance criteria:** Every endpoint in §10 is reachable, correctly permissioned, and returns the documented shape; `POST /facilities/batch-lookup`'s deliberate `POST`-not-`GET` choice is exercised with a realistically large ID set in at least one test.
- **Non-goals:** No frontend yet (Increments 7–11).

### Increment 7 — Frontend list and filtering

- **Objective:** `FacilityListPage` — paginated, filterable, sortable registry list.
- **Files:** `frontend/src/modules/sensitive_customer_registry/{types.ts,api.ts,displayHelpers.ts,pages/FacilityListPage.tsx}`.
- **Behaviour introduced:** TanStack Table list view; filters for sector, sensitivity, lifecycle status, and Transformer Terminal/substation context; `displayHelpers.ts`'s pure, client-side-only identity composition (CLAUDE.md A12), reusing the exact `"Substation | Voltage | Bay"` composition pattern ALSF already established, sourced from the same already-existing Equipment Registry identity fields — never a new backend field.
- **Validations:** none (read-only page) — permission-gated visibility only (`canWrite`-style pattern from ALSF, applied here to `.write`/`.manage_reference_data`, not `.read`, since the page itself already requires `.read` to be reachable at all).
- **Tests:** `frontend/tests/sensitive_customer_registry/FacilityListPage.test.tsx`, built directly against `FunctionalityListPage.test.tsx`'s pattern (§16) using the existing shared `stubFetch`/`renderWithProviders` harness — list renders; each filter narrows results; empty-state renders when no facility matches.
- **Acceptance criteria:** Matches ALSF's `FunctionalityListPage` UX pattern closely enough that a user familiar with one registry immediately understands the other.
- **Non-goals:** No defence-scheme controls, no scheme-assignment buttons, no compliance/blocking indicator of any kind (task's explicit non-goal) — the list shows engineering facts only: name, sector, sensitivity, substation/transformer/terminal, lifecycle, last-modified.

### Increment 8 — Frontend creation and editing

- **Objective:** `FacilityCreatePage`, `FacilityEditPage` (or a shared form component used by both), plus the two reference-data admin pages.
- **Files:** `pages/{FacilityCreatePage,FacilityEditPage,FacilitySectorAdminPage,SensitivityClassificationAdminPage}.tsx`.
- **Behaviour introduced:** create/edit forms (name, sector dropdown, sensitivity dropdown, cascading substation→terminal picker reusing Equipment Registry's existing lookup endpoints exactly as ALSF's `FunctionalityCreatePage` already does, remarks); reference-data admin CRUD (create/edit/activate/deactivate rows, `.manage_reference_data`-gated).
- **Validations:** client-side required-field checks mirroring the backend's own validation (display-only convenience, never authoritative — CLAUDE.md A12); server-side errors surfaced verbatim on submit failure.
- **Tests:** form validation (required fields, terminal selection flow); reference-data admin page CRUD; permission-gated visibility (`.manage_reference_data` hides the two admin pages' write controls for non-Administrators, with an explanatory message rather than silent hiding, per ALSF's established UX precedent).
- **Acceptance criteria:** A facility can be created and later edited (including terminal reassignment) end to end through the UI.
- **Non-goals:** No bulk import, no automatic facility discovery from PSS/E (task's explicit non-goal).

### Increment 9 — Frontend detail and audit history

- **Objective:** `FacilityDetailPage` with an embedded audit-history view.
- **Files:** `pages/FacilityDetailPage.tsx`.
- **Behaviour introduced:** full record detail (all §5.1 fields); paginated audit-log table (field/old/new/who/when/reason); **`transformer_terminal_resolution` and `lifecycle_status` rendered as two visually distinct, independent indicators** (§9, Correction 4) — a facility with an `UNRESOLVED` terminal is displayed with a clear "terminal could not be resolved" notice alongside its normal fields, never as a missing/blank/hidden row.
- **Validations:** none (read-only, plus lifecycle action triggers — see Increment 10).
- **Tests:** detail renders all fields correctly for a facility with no terminal reference (`NOT_ASSIGNED`), a resolvable terminal (`RESOLVED`), and an unresolvable terminal (`UNRESOLVED`) — three distinct rendering cases, none of which omit the facility; audit history paginates correctly for a facility with many changes, including a reassignment entry showing previous/new terminal, reason, actor, and timestamp (Correction 5).
- **Acceptance criteria:** Every field changed in Increment 3/4's backend tests is visibly traceable in this page's audit view for an equivalent frontend-driven scenario.
- **Non-goals:** none beyond the module-wide non-goals (§3).

### Increment 10 — Lifecycle actions (frontend)

- **Objective:** Archive / Reactivate / Entered-in-Error action buttons and reason-entry dialogs on `FacilityDetailPage`.
- **Files:** additions to `pages/FacilityDetailPage.tsx`.
- **Behaviour introduced:** §7's transition table, enforced in the UI (only currently-valid transitions are ever rendered as available); mandatory reason field per transition, matching the backend's own enforcement (defense in depth, not a substitute for it).
- **Validations:** reason field required before submit is enabled.
- **Tests:** each transition button correctly hidden/shown per current lifecycle state; reason-required validation; successful transition updates the page's displayed status without a full reload (optimistic or refetch-on-success, consistent with existing TanStack Query mutation patterns).
- **Acceptance criteria:** A user cannot submit any lifecycle transition without a reason, and cannot see an action for a transition §7 prohibits.
- **Non-goals:** none beyond §3.

### Increment 11 — Dashboard metrics (in-module summary)

- **Objective:** §11's lightweight summary strip on `FacilityListPage`.
- **Files:** additions to `pages/FacilityListPage.tsx`, consuming `GET /facilities/summary`.
- **Behaviour introduced:** active/archived/entered-in-error counts, counts by sector and by sensitivity, rendered as plain descriptive numbers — no chart library dependency required for this small, in-module view (ECharts is reserved for the future cross-module Dashboard, Phase 11, per module doc §11).
- **Validations:** none.
- **Tests:** summary strip renders correct counts against a known fixture dataset.
- **Acceptance criteria:** Counts visibly update after a create/archive/reactivate action in the same session (query invalidation on mutation success).
- **Non-goals:** No claim of scheme eligibility, compliance, or safety implied anywhere in this view's copy or styling (explicit task non-goal — verify in review, not just in code).

### Increment 12 — Documentation synchronization

- **Objective:** Bring every document identified in §18 up to date with the as-built module.
- **Files:** per §18's table.
- **Behaviour introduced:** none (documentation only).
- **Validations:** relative-link checker (the same approach already used for the EDR-008/ADR-012/module-doc commit) re-run across every touched file.
- **Tests:** N/A.
- **Acceptance criteria:** §18's table fully checked off; EDR-008 and ADR-012 remain unmodified in their original decision text, gaining only a status-update note (mirroring EDR-005's own "Status update (post-ADR-011)" precedent) — never rewritten as though the outcome were always known.
- **Non-goals:** No re-litigation of any already-accepted architecture decision during this increment.

### Increment 13 — Full verification and release

- **Objective:** The same release discipline already applied to ALSF and to this module's own architecture-document commit.
- **Files:** none new — verification only.
- **Behaviour introduced:** none.
- **Validations:** full backend suite (`pytest`) green against **real PostgreSQL** (`GRIDDEFENCE_TEST_DATABASE_URL` set), not just SQLite; frontend suite (`vitest`) green, including the full `frontend/tests/sensitive_customer_registry/` directory built in Increments 7–11; `ruff check`/`ruff format --check`; `tsc -b --noEmit`; `eslint`; production frontend build succeeds; `alembic upgrade head` clean from empty. No Playwright step — confirmed not configured anywhere in this repository (§16); the golden path is covered by the Vitest/RTL and backend API contract tests instead.
- **Tests:** the full matrix in §16/§17.
- **Acceptance criteria:** CLAUDE.md §25's Definition of Done, all nine checkmarks, satisfied for this phase specifically.
- **Non-goals:** No scope addition of any kind during this increment — this is a verification gate, not a feature increment.

## 15. Backend Test Matrix

Module-local (`backend/app/modules/sensitive_customer_registry/tests/test_service.py`), flat `test_*` functions, `conftest.py` building real Substation/Equipment Registry/IAM records through their own service layers (never direct construction — CLAUDE.md A1), mirroring ALSF's `conftest.py` shape:

- Domain validation: required fields, `code` uniqueness/immutability, inactive-reference-data rejection.
- Lifecycle transitions: all rows of §7's table, both success and rejection cases.
- Terminal-reference validation: unknown terminal rejected at create/reassign; orphaned-reference tolerance at read time — a terminal ID that no longer resolves in Equipment Registry does not break `get_facility_detail`, does not raise, and **does not remove the facility from `list_facilities`/`get_facility_detail`/any read**, correctly reporting `transformer_terminal_resolution=UNRESOLVED` instead (Correction 4).
- Multiple facilities on one terminal: explicit positive test (the ALSF-inverse regression test called out in Increment 3).
- Reassignment: terminal change produces exactly one audit row, old/new correctly captured.
- Audit events: one row per changed field, never a bulk single-row diff.
- Reference-data lifecycle: create/edit/activate/deactivate/rename-after-use, all per §8's table.
- Permissions: `.read`/`.write`/`.manage_reference_data` each independently fail-closed against a user lacking that specific code (three separate tests, not one combined test — mirroring IAM's own fail-closed test discipline).
- List filtering: every filter in §10's table, individually and combined.
- Sorting and pagination: stable ordering, correct page boundaries.
- Batch lookup: zero/one/multi-facility terminals in one call; empty input set; large (500+) input set.
- Dashboard/summary counts: correctness against a known fixture, and correctness after a lifecycle transition changes a count.
- Migration/seed behaviour: idempotent seed re-run; `ReferenceDataNotSeededError` raised correctly.
- **PostgreSQL-specific:** case-sensitivity of `code` uniqueness, `ON DELETE RESTRICT` actually enforced (SQLite's FK enforcement can be looser depending on pragma state — verify explicitly against real PostgreSQL per [implementation-plan.md](implementation-plan.md) §8's testing strategy).

Root-level API tests (`backend/tests/test_sensitive_customer_registry_api.py`), mirroring `test_automatic_load_shedding_functionality_api.py`'s shape: auth required, each permission independently required, full create→edit→archive→reactivate→entered-in-error HTTP flow, batch-lookup endpoint with a realistic payload, every documented error code (400/403/404/409) exercised at least once, no `DELETE` endpoint exists for reference data (a confirmed-absence test, mirroring ALSF's confirmed-absent `/activate`/`/deactivate` test).

**Architectural test** (§16 of the module doc, §9 of this document): a static/import-graph check confirming `sensitive_customer_registry` never imports `network_model`, `automatic_load_shedding_functionality`, `critical_infrastructure`, `ufls`, `uvls`, or `emls`'s `repository.py`/`models.py` — and, symmetrically, that none of those modules import this module's `repository.py`/`models.py` either (this module has no consumers yet, but the test guards the *shape* of future integration, not just current absence).

## 16. Frontend Test Matrix

**Correction to the prior version of this specification.** The earlier draft stated "no frontend test files exist anywhere in the repository." That was wrong — a direct re-inspection (`Glob` over `frontend/**/*.test.*`, then reading the matched files) confirms a substantial, established frontend test suite already exists, entirely under a **top-level `frontend/tests/` directory** (not colocated under `frontend/src/`, which is why the prior pass, having searched only `frontend/src`, found nothing). This specification now reuses that infrastructure directly rather than proposing anything new.

**Existing infrastructure (confirmed, to be reused as-is — no new test tooling of any kind):**

- **Runner/config:** `frontend/vite.config.ts`'s `test` block — Vitest, `environment: "jsdom"`, `globals: true`, `setupFiles: ["./tests/setup.ts"]`, `include: ["tests/**/*.test.{ts,tsx}", "src/**/*.test.{ts,tsx}"]`. `frontend/tests/setup.ts` registers `@testing-library/jest-dom/vitest` only.
- **Shared harness — `frontend/tests/testUtils.tsx`** (already used by every existing module's tests, promoted here from an IAM-specific helper once Substation Registry needed it too): exports `stubFetch(handlers: FetchHandler[])` (routes `fetch` calls to canned JSON responses by HTTP method + URL `RegExp`, so component tests exercise the real component → TanStack Query → `apiClient` path without a live backend) and `renderWithProviders(ui, { route })` (wraps a component in `QueryClientProvider` + `AuthProvider` + `MemoryRouter`). **This module's tests use these two exports unchanged — no new provider wrapper, no new fetch-mocking approach.**
- **Directory convention:** tests live at `frontend/tests/<module_name>/*.test.tsx`, mirroring `frontend/src/modules/<module_name>/`, one-to-one with the module — e.g. `frontend/tests/automatic_load_shedding_functionality/`. This module's tests belong at **`frontend/tests/sensitive_customer_registry/`**.
- **Existing per-module test suites, confirmed present:** `iam/` (6 files), `substation_registry/` (3), `equipment_registry/` (6), `psse_integration/` (6), `network_model/` (6), `components/ui/` (2), plus root-level `App.render.test.tsx` and `apiClient.test.ts`. **`automatic_load_shedding_functionality/`** — the nearest structural precedent for this module — has 5 files: `FunctionalityListPage.test.tsx`, `FunctionalityCreatePage.test.tsx`, `FunctionalityDetailPage.test.tsx`, `FunctionalityCandidatePage.test.tsx`, `displayHelpers.test.ts`.

**Concrete patterns to reuse, read directly from the ALSF suite (implementation references, not to be redesigned):**

| Pattern | Reference file | What to reuse for this module |
|---|---|---|
| List-page rendering, filtering, and permission-gated action visibility (including the "explain, don't silently hide" UX rule for a missing-permission user, and the distinct empty-state-for-Viewer-vs-Engineer-vs-no-permission variants) | `frontend/tests/automatic_load_shedding_functionality/FunctionalityListPage.test.tsx` | `FacilityListPage.test.tsx` — same `stubFetch`/`renderWithProviders` setup, same session-handler shape (`/api/v1/users/me`, `/api/v1/users/{id}/roles` returning a role with a `permissions` array), same assertion style (`screen.getByRole("cell", ...)`, `within(row).getByText(...)`) |
| Route-param-driven detail page rendering, wrapped in `<Routes><Route path=".../:id" element={...} /></Routes>` rather than a bare `renderWithProviders` call | `frontend/tests/automatic_load_shedding_functionality/FunctionalityDetailPage.test.tsx` | `FacilityDetailPage.test.tsx`, and its lifecycle-action tests (Increment 10) |
| Create-page form interaction, cascading substation → terminal picker, mutation success/error handling | `frontend/tests/automatic_load_shedding_functionality/FunctionalityCreatePage.test.tsx` | `FacilityCreatePage.test.tsx` / `FacilityEditPage.test.tsx` |
| Pure display-helper unit testing (no rendering, no fetch stubbing — plain function-in, value-out) | `frontend/tests/automatic_load_shedding_functionality/displayHelpers.test.ts` | `displayHelpers.test.ts` for this module's own identity-composition and filter-mapping helpers |

**Test coverage plan (unchanged in substance from the prior draft, now correctly framed as following an established pattern, not inventing one):**

- List rendering: table populates from a mocked API response; empty state.
- Filters: each filter (sector, sensitivity, lifecycle, terminal/substation) narrows the displayed rows.
- Create/edit validation: required-field client-side checks; terminal cascading picker (substation → terminal) behaves correctly; server-side error surfaced on submit failure.
- Terminal selection: selecting a substation narrows the terminal dropdown correctly (reusing the exact interaction pattern already built for ALSF's create page).
- Lifecycle actions: button visibility per current state; reason-required submit gating; success updates displayed state.
- Permission-sensitive controls: `.write`/`.manage_reference_data`-gated controls hidden with an explanatory message (not silently absent) for a user lacking the permission — **and, per the corrected permission model (§12), a test proving an Engineer-only session sees the same read-only, no-write-controls experience as a Viewer with `.read`**, since Engineer no longer holds `.write` in this module.
- Audit display: audit table renders and paginates correctly.
- Reference-data administration: create/edit/activate/deactivate flows for both sector and classification admin pages, gated by `.manage_reference_data` (Administrator only).
- Dashboard/summary metrics: summary strip renders correct counts and updates after a mutation.
- Terminal-resolution display (§7 below): a facility whose `transformer_terminal_id` cannot currently be resolved still renders in the list/detail view, with an explicit "terminal unresolved" indicator rather than being silently omitted or showing a blank cell.
- API-error handling: a failed request surfaces a user-visible error message, never a silent failure or an unhandled promise rejection.

**Playwright:** confirmed **not configured anywhere in this repository** (no `playwright.config.*` file, no `playwright` dependency in `frontend/package.json`) — this is a directly-verified fact, not an assumption. This specification does not introduce Playwright tooling for the first time on this module alone; that remains a project-wide tooling decision out of scope here. The golden-path flow (create → edit → archive → reactivate → entered-in-error) is instead covered end-to-end at the Vitest/RTL level (Increment 10's acceptance criteria) plus the backend API contract test (Increment 6), which together already exercise the same sequence without requiring new infrastructure.

**Full command matrix (Increment 13):** `pytest` (backend, both SQLite-default and `GRIDDEFENCE_TEST_DATABASE_URL`-set real-Postgres runs), `vitest run` (frontend — runs both `tests/**` and `src/**` per `vite.config.ts`'s existing `include` pattern, no config change needed), `ruff check .` / `ruff format --check .`, `mypy` if configured for other modules, `npm run lint`, `npm run typecheck`, `npm run build` (production build must succeed), `alembic upgrade head` from empty.

## 17. Documentation Synchronization Plan

**Updated by this task (§20 confirms exactly what changed):**
- [`implementation-plan.md`](implementation-plan.md) — new Phase 3.7 section; §2 Backend Module Order; Phase 6/7/8 SCR-dependency notes updated to reference Phase 3.7 by name; the Architecture Gaps table row for Sensitive Customer Registry corrected to reflect approved-architecture/not-yet-implemented status.

**Identified as needing updates once this module is actually implemented (not modified by this planning task — listed here per the task's own §15 instruction to *identify*, not necessarily perform, these updates now):**

| Document | Update needed |
|---|---|
| [`domain-model.md`](domain-model.md) §3 | Move Sensitive Customer Registry from "Owns (planned)" to "Owns (today)," matching exactly how ALSF's own entry moved during the prior documentation-synchronization task. |
| [`system-overview.md`](system-overview.md) §2 | Update the bounded-context table row's Status column from "Recommended next architecture-discovery phase" to "Complete (Phase 3.7)," add a Phase-numbering note mirroring ALSF's own. |
| [`sensitive-customer-registry-module.md`](sensitive-customer-registry-module.md) | Add an "Implementation" note per section (§11/§12/§13) confirming the as-built shape matches the concept, mirroring ALSF's own architecture doc's eventual as-built annotations — only if the as-built module diverges from this specification in any way; if it matches exactly, no change is needed beyond a status-line update at the top of the document. |
| [`07-future-roadmap.md`](../engineering/07-future-roadmap.md) | Update the "of these, ... Sensitive Customer Registry is the recommended next architecture-discovery phase" sentence to reflect completion. |
| [`08-engineering-terminology.md`](../engineering/08-engineering-terminology.md), [`glossary.md`](../engineering/glossary.md) | Add `SensitiveFacility`/`FacilitySector`/`SensitivityClassification` implementation-correspondence entries, mirroring the ALSF entries added in the prior synchronization task exactly. |
| `CHANGELOG.md` | New "Phase 3.7 — Sensitive Customer Registry" entry, mirroring the ALSF entry's structure (Scope/Backend/Frontend/Tests/Known limitations). |
| API documentation (if the repository maintains generated/hand-written API docs beyond FastAPI's own OpenAPI schema) | Not currently identified as a separate artifact in this repository — FastAPI's auto-generated schema is the only "API documentation" observed; no additional file is known to require updating. |
| User-facing registry guidance | None found in this repository for any existing registry (ALSF, Equipment Registry, Substation Registry) — no precedent exists, so none is planned for this module either, consistent with existing practice. |

EDR-008 and ADR-012 are **preserved as historical decision records** — Increment 12 adds a status-update note only (mirroring [EDR-005](../engineering/edr/EDR-005-bay-as-engineering-identity.md)'s own "Status update (post-ADR-011)" callout block), never rewriting their original Context/Decision/Rationale text.

## 18. Explicit Non-Goals (consolidated)

Restated from §3 for a single-location reference, since the task requires this list to appear as its own deliverable: UFLS rule design; UVLS rule design; EMLS rule design; Cross-Scheme Compliance rules; blocking or approval logic; stage restrictions; scheme-specific override records; alternate or backup supply modelling; active-supply detection from real-time systems; supply-history modelling; GIS; CRM; customer billing or account management; distribution-network topology; verification workflows; approval workflows; facility certification; automatic facility discovery from PSS/E; automatic classification changes; Critical Infrastructure implementation changes.

## 19. Assumptions and Unresolved Implementation Questions

**Assumptions made where the approved architecture did not fully specify an implementation detail** (each resolved by the smallest, most consistent choice available, per this project's own precedent — none contradicts EDR-008/ADR-012/the module doc):

1. The shared audit log (§5.4) is implemented as one physically polymorphic table (three nullable FKs + discriminator + XOR check), not three separate per-entity audit tables — chosen because the module doc §5 explicitly names a single `sensitive_customer_registry_audit_log`, and this design reuses ALSF's already-proven XOR-constraint technique rather than inventing a new pattern.
2. `FacilitySector`/`SensitivityClassification` seeding follows the existing manual-`seed.py` convention rather than migration-embedded `bulk_insert`, for consistency with `app/reference_data/`'s established pattern — confirmed by inspecting `backend/Dockerfile`/`docker-compose.yml` directly (§13), with the required step now fully specified per environment and backed by a fail-loud safeguard, rather than left as an undocumented step.
3. `transformer_terminal_resolution` (§9) is a computed, read-time-only field, never persisted — chosen because Equipment Registry's own resolvability can change independently of any write to `SensitiveFacility`, so a stored value would risk going stale exactly like the condition it exists to surface.

**Previously listed as open questions — now resolved by this correction task, retained here only as a record of what changed:**

- ~~Sensitive Customer Review integration timing~~ — **settled (§2, Correction 3).** Phase 3.7 is required to complete before Phase 6 begins; the stub-then-real fallback is a schedule-slippage contingency only, never the planned path.
- ~~Frontend testing precedent~~ — **settled (§16, Correction 2).** An established Vitest + React Testing Library suite already exists under `frontend/tests/`, with a directly reusable ALSF precedent; this module's frontend tests follow that existing pattern exactly, using no new infrastructure.
- ~~Playwright tooling~~ — **settled (§16).** Confirmed, by direct inspection, not configured anywhere in this repository; this specification does not introduce it for this module alone.
- ~~Permission tier for `.write`~~ — **settled (§12, Correction 1).** Administrator only; Engineer holds `.read` only; no new role introduced.

**Genuinely unresolved questions requiring Project Owner input** (none blocks Increment 1; each is independently deferrable to the increment named):

1. **Stale-terminal reconciliation *report*.** Correction 4 (§5.1, §9) already ensures a stale/unresolved terminal reference is always visible on every normal read (`transformer_terminal_resolution=UNRESOLVED`), so this is no longer a visibility gap — the remaining, smaller question is only whether a *proactive*, scheduled reconciliation report (module doc §17 Future Extension) should be pulled into this phase or genuinely deferred. Does not block any increment in this specification.
2. **Future Cross-Scheme Compliance Rule 3.** Entirely out of scope for this specification (§3, §18) — flagging only that if a future scheme module's design ever needs sensitivity-driven enforcement, that requires a new ADR before any code in *this* module changes to support it (ADR-012 Alternatives Considered, item 3). Not reopened by this correction task.
3. **Broader read-access tier.** Module doc §15 recommends (but does not mandate) a dedicated "Sensitive Customer Registry Viewer" role for non-Engineer/non-Administrator read access. This specification assigns `.read` to Administrator+Engineer only for this phase (§12) — confirm whether that narrower default is acceptable for initial release. (Distinct from the now-settled `.write` question above — this concerns only whether *read* access should ever extend beyond the two existing roles, not whether Engineer gains any mutation permission.)
4. **`sort_order` gap-filling.** §8 allows admin-created gaps in `sort_order` with no automatic renumbering — confirm this is acceptable, or whether a stricter contiguous-ordering rule is preferred for a user-facing dropdown's display order.

## 20. Recommendation (reassessed after corrections)

**No implementation-blocking questions remain.** All four corrections requiring an actual specification change (permission model, stale-terminal handling, reassignment auditing, seed execution) are now fully specified in §5–§13, and the two corrections that were factual research errors (frontend testing, Phase 3.7 sequencing) are now grounded in direct repository evidence rather than assumption. §19's four remaining open questions are all genuinely deferrable — none prevents Increment 1 (domain model and migration) from starting, and none reopens a settled architecture question (EDR-008/ADR-012/the module doc are unchanged by this correction task) or introduces speculative functionality beyond what was already specified.

This specification is **ready to guide implementation** for all 13 increments without further architectural clarification. Every field, constraint, contract, and permission decision traces directly to an already-approved source document section or to one of this task's six explicit corrections; every remaining implementation-level judgment call is named in §19 rather than silently resolved.

---

## 21. Task Completion Confirmations

- **No application code, database model, migration, API, frontend page, or test file was created or modified during this task.** This document and the corresponding update to [`implementation-plan.md`](implementation-plan.md) are the only changes.
- **Nothing was staged, committed, or pushed.**
