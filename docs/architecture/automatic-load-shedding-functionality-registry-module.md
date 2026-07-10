# Automatic Load Shedding Functionality Registry — Module Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document follows the Canonical Module Architecture Document Template (CLAUDE.md **A8**).

Related documents: [system-overview.md](system-overview.md), [domain-model.md](domain-model.md), [equipment-registry-module.md](equipment-registry-module.md) (referenced entities), [critical-infrastructure-module.md](critical-infrastructure-module.md) (structural precedent this document follows), [ufls-module.md](ufls-module.md), [uvls-module.md](uvls-module.md), [ADR-011](../adr/ADR-011-automatic-load-shedding-functionality-registry.md) (the decision that establishes this module), [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md), [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md), [EDR-003](../engineering/edr/EDR-003-relay-registry-scope.md), [EDR-005](../engineering/edr/EDR-005-bay-as-engineering-identity.md).

---

## 1. Module Overview

The Automatic Load Shedding Functionality Registry is a static, manually-maintained Engineering Registry recording which Bay Terminals — a `CircuitTerminal` (line/circuit bay) or a `TransformerTerminal` (transformer bay) — have automatic load shedding functionality installed, wired, configured, commissioned, and available for UFLS and/or UVLS. It exists to answer two engineering questions precisely and auditably: *which bays already carry this functionality, and which are candidates for it.*

This module gives a final, precisely-scoped bounded-context home to the engineering concept previously discussed under the name "Relay Registry" (EDR-003), per [ADR-011](../adr/ADR-011-automatic-load-shedding-functionality-registry.md). It is **not** a relay or protection asset-management system, and it has no knowledge of UFLS/UVLS scheme versions, stages, or assignments.

---

## 2. Purpose

To provide a single, auditable source of truth for automatic UFLS/UVLS shedding readiness at Bay-Terminal granularity, so that:

- UFLS and UVLS scheme designers can determine, for any candidate substation or bay, whether automatic execution is actually possible before it is offered as a Shedding Action candidate (mirroring `03-system-workflow.md`'s "Relay Capability Verification" step, now understood as this module's own subject matter).
- Engineers can immediately tell, at a glance, which bays are **Available** (functionally ready, not yet scheme-assigned), which are **Assigned** (functionally ready and currently referenced by an active UFLS and/or UVLS scheme), and which are **Decommissioned** (permanently removed) — the registry page's own three statuses (Status Model Refinement, §8).
- Once UFLS/UVLS exist, the same functionality data is composed, read-only, against active scheme assignments to compute the Available/Assigned distinction above — never a second, independently-maintained "assignment" fact of this module's own.
- Every change to a bay's functionality record (created, decommissioned, metadata edited) is permanently, individually auditable — a compliance or incident review months later can reconstruct exactly what was known, and when.
- The distinction between "this bay is physically/functionally capable" (this module) and "this bay is currently assigned by an active scheme" (UFLS/UVLS's own data) is never blurred — mirroring `03-system-workflow.md` §3's explicit rule that Sensitive Customer Review and Relay Capability Verification "answer different engineering questions... and a finding from one must never be mistaken for a finding from the other," extended here to the assignment-status distinction as well.

---

## 3. Responsibilities

This module owns:

- ✓ The record of automatic load shedding functionality **existence**, per Bay Terminal (`AutomaticLoadSheddingFunctionality`)
- ✓ Whether that functionality supports UFLS, UVLS, or both, independently (`ufls_function`, `uvls_function`)
- ✓ The functionality record's own persisted lifecycle: `Active` → `Decommissioned` (terminal) — Status Model Refinement (engineering refinement, §8): a binary existence flag, not the three-value status an engineer sees
- ✓ **Decommissioned state** — a terminal, manually-initiated engineering decision (§8)
- ✓ Optional, secondary relay metadata (make, model) — never required, never the registry's primary subject matter (EDR-003)
- ✓ Free-text engineering remarks per record
- ✓ Its own full audit trail, covering every lifecycle transition and metadata edit (CLAUDE.md A4)
- ✓ Read-only candidate-search and functionality-lookup query interfaces for future scheme-module consumption

This module does **not** own the Available/Assigned distinction itself — that is computed, at read time, from UFLS/UVLS's own scheme assignment data (owned by those future modules). See §8's Status Model Refinement.

---

## 4. Non-Responsibilities

This module does **not** own:

- ✗ Bay Terminal identity, wiring, or existence — owned by Equipment Registry (`CircuitTerminal`/`TransformerTerminal`). This module references a terminal only by ID, exactly as Critical Infrastructure references `substation_id`, and copies no attribute from it.
- ✗ **EMLS** in any capacity. EMLS is manually invoked and may be assigned to any bay at the scheme designer's discretion (per the confirmed engineering rule) — it has no automatic-functionality prerequisite, and this module has no field, flag, or query surface referencing EMLS at all.
- ✗ **UFLS/UVLS scheme data of any kind** — no scheme identity, version, stage, or assignment. This module has no knowledge of "schemes," "stages," or "shedding assignments," mirroring the identical decoupling principle already established for Equipment Registry (§4), Network Model, and Critical Infrastructure. This module *computes* whether a Bay Terminal displays as Assigned (§8), but only from a plain `assigned_terminal_ids` set supplied, in-process, by the calling UFLS/UVLS module (CLAUDE.md A1) — it never queries UFLS/UVLS's own tables, never stores which scheme a terminal is assigned to, and never learns *which* scheme did the assigning.
- ✗ **General relay or protection asset management.** Manufacturer, model, firmware version, settings history, and maintenance scheduling are out of scope beyond the two optional, secondary metadata fields named in §5 (EDR-003's scope discipline, restated for this module by name).
- ✗ **Electrical topology or connectivity analysis of any kind** — owned by PSS/E Integration and Network Model. This module never determines what a bay's opening would isolate; it only records whether the bay itself is functionally ready to be opened automatically.
- ✗ Sensitive Customer classification — a related but distinct policy concern, owned by its own future registry (see §17).
- ✗ Identity, authentication, or authorization — owned by IAM. This module references actors only by `user_id`.

---

## 5. Owned Entities

| Entity | Description |
|---|---|
| `AutomaticLoadSheddingFunctionality` | One record per Bay Terminal, recording whether automatic UFLS and/or UVLS shedding functionality is installed and ready, its own lifecycle status, optional relay metadata, and remarks (§7, §9). |
| `automatic_load_shedding_functionality_audit_log` | This module's own append-only audit trail (CLAUDE.md A4), covering every lifecycle transition and field edit. |

**Design note — no `RelayDetail`/`RelayControlledEquipment` generic wiring model.** [ADR-011](../adr/ADR-011-automatic-load-shedding-functionality-registry.md) retires that direction (originally sketched, never built, in `equipment-registry-module.md` §7.8) in favor of this single, purpose-built entity. There is no generic "relay as physical equipment" row and no separate "controlled equipment" wiring table — a functionality record targets its Bay Terminal directly.

---

## 6. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| `CircuitTerminal` | Equipment Registry | `circuit_terminal_id` (UUID), nullable, populated only when `target_type = 'CIRCUIT_TERMINAL'` |
| `TransformerTerminal` | Equipment Registry | `transformer_terminal_id` (UUID), nullable, populated only when `target_type = 'TRANSFORMER_TERMINAL'` |
| `Substation` | Substation Registry | Never referenced directly — always reached via the Bay Terminal's own substation association, exactly as Critical Infrastructure never duplicates Substation Registry's attributes and Equipment Registry never duplicates Substation Registry's own fields |
| User | IAM | `user_id` (UUID) only, for `created_by_user_id`/`updated_by_user_id`/audit attribution |

This module never stores a substation's name, mnemonic, voltage, region, or any other Substation Registry or Equipment Registry attribute — only the terminal's own ID.

---

## 7. Domain Model

```
CircuitTerminal (Equipment Registry, external, read-only)
TransformerTerminal (Equipment Registry, external, read-only)
        │
        ▼
AutomaticLoadSheddingFunctionality  ── one row per Bay Terminal ──
        │                              (never more than one active
        │                               record per terminal, §9)
        │
        ├── ufls_function: boolean
        ├── uvls_function: boolean         (at least one true, §10)
        ├── lifecycle_status: ACTIVE | DECOMMISSIONED   (persisted; §8)
        ├── relay_make / relay_model: optional metadata
        └── remarks
        │
        ▼
automatic_load_shedding_functionality_audit_log  ── append-only,
                                                      every transition
```

`lifecycle_status` is **not** the three-value status (Available / Assigned / Decommissioned) an engineer sees on the registry page — see §8's Status Model Refinement for how that display status is computed, never stored.

A Bay Terminal may support both UFLS and UVLS simultaneously on the **same** record (`ufls_function = true AND uvls_function = true`) — this is not two records, since both facts describe the same physical functionality installation, per the confirmed engineering rule that "a single bay terminal can support both UFLS and UVLS."

**Bay Terminal display identity (engineering refinement — Complete Engineering Identity Display).** This module stores no bay-identifying string of its own. Every read path composes a `bay_label` from Equipment Registry's own already-computed identity — `Circuit.circuit_name`/`bay_number` (for a `CircuitTerminal`) or `Transformer.generated_short_name` (for a `TransformerTerminal`) — via two read-only Equipment Registry service methods added for this purpose, `get_circuit_terminal_identity`/`get_transformer_terminal_identity` (`equipment_registry/service.py`), never re-derived or duplicated as stored data here (§4, §6). The full engineering identity an engineer sees — e.g. `IGBK | 33kV | Transformer T1`, `IGBK | 132kV | Line IGBK–ROMEO No.1` — is a `"{substation_mnemonic} | {voltage_level_label} | {bay_label}"` composition performed **client-side** (CLAUDE.md A12 — display-only derivation), from the three already-separate fields every read DTO in this module reports; the pipe-separated string itself is never stored, computed, or returned by the backend as a single field. This guarantees two Bay Terminals at the same substation and voltage level — e.g. two parallel circuits, or two transformers T1/T2 — are always displayed distinctly, since each retains its own distinct `bay_label`.

---

## 8. Lifecycle / State Model

This is **current-state master data with a full audit trail**, not the Canonical Version Lifecycle (CLAUDE.md A3) — the same classification already established for `Circuit`, `CircuitTerminal`, `Transformer`, and `SubstationVoltageYard` (CLAUDE.md §11.5: "current-state master data... single authoritative record"). Per [ADR-010](../adr/ADR-010-engineering-decision-support-philosophy.md)'s classification rule, this module's data is Engineering Knowledge (Layer 1) — a standing engineering fact consulted by future scheme modules, never itself an Approved Engineering Policy.

### 8.1 Status Model Refinement (engineering refinement)

This supersedes an earlier `Added → Active ⇄ Inactive → Decommissioned` design. Two *separate* concepts now exist, and must never be confused:

1. **Persisted lifecycle (`lifecycle_status`)** — binary, this module's own stored existence flag:

   ```text
   Active
     │
     ▼
   Decommissioned  (terminal)
   ```

   A record is created directly into `Active` — there is no other legal creation-time value. `Active` → `Decommissioned` is the *only* transition this module still exposes: one-way, manually initiated by the engineer (or a future decommissioning utility), reasoned, audited. A decommissioned record is never reactivated (a bay whose functionality is later reinstalled after genuine dismantlement receives a **new** record, §18) and is fully immutable thereafter — including a second decommission attempt, which is rejected, not silently accepted (re-applying the transition would misrepresent an already-immutable historical fact).

2. **Display status (Available / Assigned / Decommissioned)** — the three-value status an engineer actually sees on the registry page, **computed at read time, never stored**:

   | Display status | Condition |
   |---|---|
   | **Available** | `lifecycle_status = Active` and the terminal is **not** currently referenced by any active UFLS or UVLS scheme |
   | **Assigned** | `lifecycle_status = Active` and the terminal **is** currently referenced by at least one active UFLS and/or UVLS scheme (scheme-type-agnostic — referenced by either counts) |
   | **Decommissioned** | `lifecycle_status = Decommissioned` — always, regardless of assignment |

   Available is the default state for every newly created record. Assigned is **system-derived and never manually editable** — there is no endpoint, field, or UI control that sets it directly.

### 8.2 Future Integration Contract

This module never queries UFLS/UVLS's own tables to determine assignment (CLAUDE.md A1). Instead, every read path that returns a display status accepts an optional `assigned_terminal_ids: set[UUID]` — the union of every Bay Terminal ID currently referenced by an Active UFLS or UVLS scheme version, supplied **in-process, by the caller**. No caller exists yet (UFLS/UVLS are not yet implemented), so every read defaults to an empty set, and every non-decommissioned record therefore displays as Available — exactly the *Current Phase Behaviour* this module implements today, with no placeholder assignment table anywhere in its schema. Once a UFLS/UVLS module (or a future Dashboard composition layer) exists, it supplies its own current-Active-version assignment set to this same parameter — no redesign, no migration, no new endpoint required. `list_assigned_and_available` (§13) is the same contract, already built, for the candidate-search flow.

Every transition is captured in the audit log with actor, timestamp, and an optional/required reason depending on the transition (§14). Creation itself is also always an audit event (§14), recording the record's initial `lifecycle_status` (always `Active`).

---

## 9. Business Rules

1. **Exactly one target per record**: a record references either a `CircuitTerminal` or a `TransformerTerminal`, never both, never neither (§11's database-enforced XOR).
2. **At most one non-decommissioned record per Bay Terminal.** A terminal may accumulate multiple `Decommissioned` historical records over its lifetime (§8), but only one record may have `lifecycle_status = Active` at any time (§11, partial unique index).
3. **At least one of `ufls_function`/`uvls_function` must be true.** A record with both false represents no functionality at all and must not exist (§10).
4. **EMLS is never referenced.** No field, enum value, or query parameter in this module names EMLS.
5. **A `TransformerTerminal`-targeted record and a `CircuitTerminal`-targeted record are independent** — a substation with both a transformer bay and a line bay commissioned for automatic shedding has two separate records, one per terminal, exactly as Equipment Registry itself models each terminal as its own row.
6. **Candidate search excludes any Bay Terminal with no record or a `Decommissioned` record** for the requested scheme type — every `lifecycle_status = Active` record with the matching `ufls_function`/`uvls_function` flag is a candidate, Available or Assigned alike (§13); `list_assigned_and_available` further partitions that set once a caller supplies its own assignment data.
7. **This module never determines or stores *which scheme* a bay is assigned to, or scheme-level assignment data of any kind.** It computes only the boolean Available/Assigned display distinction (§8), and only from an `assigned_terminal_ids` set supplied, in-process, by the calling UFLS/UVLS module (CLAUDE.md A1) — never persisted here, never queried from another module's tables.

---

## 10. Validation Rules

- `target_type` must be exactly `CIRCUIT_TERMINAL` or `TRANSFORMER_TERMINAL`; the corresponding FK must be non-null and the other FK must be null (database `CHECK`, §11).
- `ufls_function OR uvls_function` must be true (database `CHECK`, §11).
- The referenced `circuit_terminal_id`/`transformer_terminal_id` must exist in Equipment Registry at creation time (service-layer existence check — this module holds no FK constraint into another module's schema per CLAUDE.md A1/A2, so referential integrity here is enforced at the service layer, exactly as Critical Infrastructure's `substation_id` reference is; see §15's testing requirement).
- A referenced terminal that is later deleted or re-typed in Equipment Registry is an "unknown, not invalid" condition for this module (mirroring Network Model's own established incomplete-data tolerance) — this module's read interfaces omit such orphaned records from output rather than raising, and a data-integrity report flags them for manual reconciliation (§17).
- `lifecycle_status` transitions must follow §8.1 exactly: `Active → Decommissioned` is the only legal transition. An attempted second decommission of an already-`Decommissioned` record is rejected at the service layer with a clear error directing the engineer to create a new record instead — the same error used for any other post-decommission edit attempt (immutability, not a distinct "invalid transition" error family).
- A `Decommissioned` transition requires a non-empty reason (audited).
- A record is always *created* with `lifecycle_status = Active` — there is no other legal creation-time value, and no field or parameter through which a caller may set it otherwise.
- The Available/Assigned display status (§8.1) is never accepted as request input on any endpoint — it is computed, and computed only.

---

## 11. Database Design

```text
automatic_load_shedding_functionality
    id                          UUID PK
    target_type                 VARCHAR   NOT NULL   CHECK (target_type IN ('CIRCUIT_TERMINAL','TRANSFORMER_TERMINAL'))
    circuit_terminal_id         UUID      NULL        FK -> circuit_terminal.circuit_terminal_id (RESTRICT)
    transformer_terminal_id     UUID      NULL        FK -> transformer_terminal.transformer_terminal_id (RESTRICT)
    ufls_function                BOOLEAN  NOT NULL   DEFAULT false
    uvls_function                BOOLEAN  NOT NULL   DEFAULT false
    lifecycle_status             VARCHAR  NOT NULL   CHECK (lifecycle_status IN ('ACTIVE','DECOMMISSIONED'))   DEFAULT 'ACTIVE'
    relay_make                   VARCHAR  NULL        -- optional, secondary (EDR-003)
    relay_model                  VARCHAR  NULL        -- optional, secondary (EDR-003)
    remarks                      TEXT     NULL
    created_by_user_id           UUID     NOT NULL    FK -> user.user_id (RESTRICT)
    created_at                   TIMESTAMPTZ NOT NULL
    updated_by_user_id           UUID     NOT NULL    FK -> user.user_id (RESTRICT)
    updated_at                   TIMESTAMPTZ NOT NULL

    CHECK (
      (target_type = 'CIRCUIT_TERMINAL'
        AND circuit_terminal_id IS NOT NULL
        AND transformer_terminal_id IS NULL)
      OR
      (target_type = 'TRANSFORMER_TERMINAL'
        AND transformer_terminal_id IS NOT NULL
        AND circuit_terminal_id IS NULL)
    )                                                  -- mirrors ck_equipment_topology_map_target_xor
                                                        -- and ck_load_snapshot_element_state_xor
                                                        -- (psse_integration/models.py) — same established
                                                        -- pattern, applied here for consistency.

    CHECK (ufls_function OR uvls_function)

    -- Partial unique indexes: at most one non-decommissioned record per terminal.
    UNIQUE INDEX (circuit_terminal_id) WHERE lifecycle_status != 'DECOMMISSIONED' AND circuit_terminal_id IS NOT NULL
    UNIQUE INDEX (transformer_terminal_id) WHERE lifecycle_status != 'DECOMMISSIONED' AND transformer_terminal_id IS NOT NULL

automatic_load_shedding_functionality_audit_log
    log_id                       BIGINT PK autoincrement
    functionality_id             UUID     NOT NULL    FK -> automatic_load_shedding_functionality.id (RESTRICT)
    event_type                   VARCHAR  NOT NULL     -- created | activated | deactivated | decommissioned | metadata_updated
    changed_by_user_id           UUID     NOT NULL    FK -> user.user_id (RESTRICT)
    changed_at                   TIMESTAMPTZ NOT NULL
    change_reason                TEXT     NULL         -- required for 'decommissioned' (service-layer enforced)
    previous_status               VARCHAR NULL
    new_status                    VARCHAR NULL
```

Primary key uses UUID (business entity, CLAUDE.md A5) — this is Master-Data-adjacent, durable, cross-referenced identity, not reference/lookup data. `ON DELETE RESTRICT` throughout (CLAUDE.md §11.7); no cascading delete. `lifecycle_status` and `target_type` are modeled as `CHECK`-constrained strings rather than reference tables, mirroring `TopologyVersion.status`'s own precedent in this codebase, since both enumerations are small, stable, and internal to this module alone (not cross-module reference data per CLAUDE.md §11.3's scoping). The Available/Assigned/Decommissioned display status is deliberately *not* a column at all — see §8.1.

---

## 12. API Contract

All endpoints require authentication; write endpoints require a dedicated `automatic_load_shedding_functionality.write` permission (registered in IAM's catalog per this module's own deployment, mirroring every other module's incremental permission-seeding pattern); read endpoints require only authentication, matching Equipment Registry's and Network Model's own precedent for engineering reference data.

- `GET /automatic-load-shedding-functionality` — paginated list, filterable by `substation_id`, `target_type`, `ufls_function`, `uvls_function`, `status` (`status` filters on the *computed* display value — `AVAILABLE`/`ASSIGNED`/`DECOMMISSIONED`, §8.1 — not a raw column; today, with no `assigned_terminal_ids` caller, `ASSIGNED` always yields zero results).
- `GET /automatic-load-shedding-functionality/{id}` — single record detail.
- `POST /automatic-load-shedding-functionality` — create (`lifecycle_status` always starts `Active`, always displays as `Available` today — §8.1; no `status` field accepted on this request at all).
- `PATCH /automatic-load-shedding-functionality/{id}` — edit metadata (`relay_make`/`relay_model`/`remarks`) and/or `ufls_function`/`uvls_function`; the lifecycle transition below is separate and dedicated (never silently implied by a general PATCH, mirroring `equipment_registry`'s own status-vs-metadata separation).
- `POST /automatic-load-shedding-functionality/{id}/decommission` (requires `change_reason`) — the only remaining lifecycle transition; Status Model Refinement removed `/activate` and `/deactivate` entirely, since Available/Assigned are always computed, never manually set.
- `GET /automatic-load-shedding-functionality/audit-log/{id}` — this record's own history.
- `GET /automatic-load-shedding-functionality/candidates` — §13's candidate-search interface, exposed at the API layer for the future UFLS/UVLS frontend designer to consume directly.

Structured error responses throughout (CLAUDE.md A9); no persistence model is ever returned directly — a dedicated response schema mirrors Equipment Registry's own DTO discipline.

---

## 13. Service Interfaces

These are the in-process interfaces future UFLS/UVLS modules call (CLAUDE.md A1) — never a direct repository or table read:

- **`is_ufls_capable(bay_terminal_reference) -> bool`** — true iff a `lifecycle_status = Active` record exists for the given terminal with `ufls_function = true`. Answers "does the functionality exist," not "is it Available or Assigned" — capability is unaffected by scheme assignment.
- **`is_uvls_capable(bay_terminal_reference) -> bool`** — symmetric, for `uvls_function`.
- **`list_candidate_terminals(scheme_type: UFLS | UVLS, filters...) -> list[CandidateTerminal]`** — every `lifecycle_status = Active` record matching the requested scheme type's function flag, enriched (read-only, via Equipment Registry's own service) with the terminal's substation/bay display context. Does **not** know about scheme assignments — this returns *all* functionally-ready bays, Available or Assigned alike.
- **`list_assigned_and_available(scheme_type, assigned_terminal_ids: set[bay_terminal_reference]) -> AssignmentAwareCandidateList`** — a convenience composition, callable only once UFLS/UVLS exist: takes the calling scheme module's own current-Active-version assignment set as an explicit parameter (this module never queries another module's tables itself, per CLAUDE.md A1) and partitions `list_candidate_terminals`'s own output into "already assigned" vs. "available." This is the same Future Integration Contract (§8.2) `get_detail`/`list_functionality` use for the registry's own Available/Assigned status display — already built, requiring no further work once a caller exists.
- **`get_detail(functionality_id, assigned_terminal_ids: set[UUID] | None = None) -> FunctionalityDetail | None`** — full record detail (computed status, both function flags, metadata) for a single terminal. `assigned_terminal_ids` defaults to empty (§8.2's Current Phase Behaviour); a future caller supplies the real set to get an accurate Assigned computation.
- **`list_functionality(..., assigned_terminal_ids: set[UUID] | None = None) -> ...`** — the registry list view's own read method; same `assigned_terminal_ids` contract, plus a `status` filter that matches against the *computed* display value.

All read interfaces degrade gracefully for an unregistered or orphaned terminal reference (return `False`/empty/`None`, never raise) — the same "unknown, not invalid" tolerance already established across this codebase's Network Model and PSS/E Integration modules.

---

## 14. Audit Requirements

Per CLAUDE.md A4, every entity above is audited. Specifically:

- Every lifecycle transition (`created`, `decommissioned`) is a mandatory audit event — who, when, why (required for `decommissioned`, `null` for `created`), previous/new `lifecycle_status`. The Available/Assigned display status is never itself audited as a field change — it is computed, not transitioned (§8.1).
- Every metadata edit (`ufls_function`/`uvls_function`/`relay_make`/`relay_model`/`remarks`) is a mandatory audit event, with particular emphasis on `ufls_function`/`uvls_function` changes given their direct downstream effect on scheme-design candidate search (mirroring Equipment Registry's own "audited with particular emphasis" treatment of bay-identifier changes, §7.9).
- Audit history is append-only and permanent (CLAUDE.md §5.2) — never modified or deleted, including for a `Decommissioned` record.

---

## 15. Security Considerations

- Read access: any authenticated user (matches Equipment Registry/Network Model precedent — this is engineering reference data, not sensitive-customer-tier data).
- Write access (create, edit, all status transitions): a dedicated `automatic_load_shedding_functionality.write` permission, distinct from Equipment Registry's own write permission, since this module's write path is a genuinely separate engineering workflow (scheme-readiness attestation) performed potentially by a different set of engineers than those maintaining raw equipment identity.
- No elevated tier beyond this is currently warranted (contrast Critical Infrastructure's stricter read tier, justified there by the sensitivity of *which* substations serve critical loads — this module's content, "is this bay functionally ready," carries no comparable sensitivity).

---

## 16. Testing Requirements

- The database-level XOR constraint (§11) rejects both-null and both-populated target references.
- The `ufls_function OR uvls_function` constraint rejects an all-false record.
- The partial-unique-index rule correctly permits multiple `Decommissioned` historical records for the same terminal while forbidding two simultaneous non-decommissioned records.
- Lifecycle enforcement (§8.1): `Active → Decommissioned` succeeds; a second decommission attempt on an already-`Decommissioned` record is rejected with a clear, actionable error, as is any metadata edit attempt.
- Candidate search correctly excludes `Decommissioned`/absent records, and correctly filters by scheme type.
- **Status computation** (§8.1, §8.2): with no `assigned_terminal_ids` supplied, every non-decommissioned record displays `AVAILABLE`; with a supplied set, a terminal present in that set displays `ASSIGNED` and a terminal absent from it displays `AVAILABLE`, regardless of other terminals' membership; a `DECOMMISSIONED` record displays `DECOMMISSIONED` even if its terminal ID is present in the supplied set.
- Orphaned-reference tolerance: a functionality record whose target terminal no longer resolves in Equipment Registry is omitted from read output, never raised as an error, and is surfaced via a dedicated data-integrity report.
- The no-foreign-key-into-any-scheme-module architectural test (this module owns no scheme-module reference, mirroring every other non-scheme module in this series).
- **Bay-identity distinctness** (§7): two Bay Terminals at the same substation and voltage level — e.g. two parallel circuits, or two transformers T1/T2 — must always resolve to two distinct `bay_label` values, never a display collision.

---

## 17. Future Extensions

- **Sensitive Customer Registry** (its own future ADR/module) will be consulted alongside this module during scheme design, but the two remain structurally independent — a bay can be functionally capable and simultaneously excluded by sensitive-customer policy; scheme modules consult both, this module knows nothing of the other.
- **PSS/E operational MW correlation.** Once PSS/E Integration's recommended-MW read interface exists (per the prior architecture review's "Scheme Assignment Foundations" recommendation), a future Dashboard or scheme-design view may display a functionally-ready bay's current recommended MW alongside its capability status — a read-only composition this module does not itself need to implement.
- **Data-integrity reporting** for orphaned terminal references (§10, §16), mirroring PSS/E Integration's own unmatched/discrepancy reporting pattern.
- **Bulk import/reconciliation tooling**, if the initial population of this registry proves large enough to warrant it (deferred — not required for this module's initial design, consistent with CLAUDE.md §21's premature-optimisation caution).

---

## 18. Risks and Recommendations

| Risk | Impact | Mitigation |
|---|---|---|
| A future engineer reads `equipment-registry-module.md` §7.8 and assumes it is still the live design | Duplicated or conflicting relay-related modeling effort | §7.8 is annotated as superseded, pointing to this document and ADR-011, per this session's documentation-change plan |
| Decommissioned records are never reactivated (§8) — an engineer may find this counter-intuitive for a bay that is genuinely re-commissioned later | Minor workflow friction; a "new record instead of reactivation" decision needs to be explained in the UI | Recommend the create-record UI detect an existing `Decommissioned` record for the same terminal and surface it as context ("a prior functionality record for this bay was decommissioned on [date] — create a new one") rather than silently allowing a duplicate-looking entry |
| `list_assigned_and_available`'s caller-supplied-assignment-set design (§13) could be implemented sloppily by a future UFLS/UVLS module, reintroducing a cross-module repository read | Would violate CLAUDE.md A1 | Flag explicitly in UFLS/UVLS's own future module documents when this interface is adopted; review this module's own service interface contract before either scheme module's implementation begins |
| This module's write workflow (engineer manually attests functionality) has no independent verification against Equipment Registry's or PSS/E's own data | A functionality record could be entered for a bay that doesn't physically support it, with nothing in software catching the error | Accepted as an inherent limitation of a manually-maintained registry (identical in kind to every other Engineering Knowledge registry in this series) — out of scope for this module to solve; a future data-quality/reconciliation capability could compare against PSS/E's structural data as a Supporting Module, never as this module's own responsibility |

---

## 19. Open Questions

1. Should `list_assigned_and_available` (§13) instead be owned jointly, or replaced by a Dashboard-level composition once Dashboard's own architecture is designed (per the prior architecture review's Phase 11 gap)? Left open — either placement is consistent with this module's own boundary, since the composition itself never becomes this module's owned data either way.
2. Should a decommissioned-then-reinstalled bay's new record retain any link (informational only, not a foreign key) to its prior decommissioned record, for audit narrative continuity? Deferred — not required for correctness, a UX refinement only (§18).
3. Exact `automatic_load_shedding_functionality.write` permission grant policy (which baseline roles receive it at seed time) — deferred to this module's own implementation phase, following IAM's incremental permission-seeding pattern (`implementation-plan.md` §6).
