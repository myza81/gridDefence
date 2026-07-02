# Equipment Registry Module Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document follows the Canonical Module Architecture Document Template (CLAUDE.md **A8**).

Related documents: [domain-model.md](domain-model.md), [substation-registry.md](substation-registry.md) (§14, which first reserved this module), [psse-integration-module.md](psse-integration-module.md) (§17, which anticipated the same linkage from its own side), [ufls-module.md](ufls-module.md) §7.4 (Open Questions 1–2, which this document resolves the second half of), [uvls-module.md](uvls-module.md), [emls-module.md](emls-module.md), [ADR-000](../adr/ADR-000-architecture-principles.md) through [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md).

---

## 1. Module Overview

Equipment Registry extends Master Data one level below the Substation Registry: it owns the physical grid equipment — transformers, incoming branches, and protection relays — that exists at or between substations. Substation Registry answers "what substations exist, and what are their identity and status"; Equipment Registry answers "what physical assets exist at those substations, how are they identified, and how do they connect to each other."

This module was reserved from the very first architecture document in this series ([substation-registry.md](substation-registry.md) §14: "any additional master asset registries... following the same ownership pattern as the Substation Registry") and referenced as a deferred dependency by every Defence Scheme module built since (`equipment_reference` free text, pending this module — [ufls-module.md](ufls-module.md) §7.4, [uvls-module.md](uvls-module.md), [emls-module.md](emls-module.md)) and by PSS/E Integration (§17 of [psse-integration-module.md](psse-integration-module.md), which anticipated "a mapping entity correlating physical equipment to topology elements... once a future Equipment Registry exists").

**Scope framing.** GridDefence is built for grid **system operators** — engineers who plan and operate transmission grid defence schemes — not for asset owners running an enterprise asset lifecycle. Equipment Registry is **not** intended to replace, duplicate, or partially reimplement an enterprise asset management (EAM) system. Its scope is deliberately narrow: the *operational/functional* equipment identity and wiring that grid defence schemes actually need to reference — what exists, where, how it is identified, and what it trips — not the fuller asset-management record (manufacturer, procurement, maintenance history, ownership lifecycle) an EAM system would own. This framing governs every design decision in this document, most visibly the relay model (§7.5) and the mandatory/optional field split (§7.1, §11).

---

## 2. Purpose

To provide a single, authoritative source of truth for physical grid equipment, so that:

- Every transformer, incoming branch, and relay has exactly one owner, referenced everywhere else by a stable `equipment_id` — never duplicated.
- Bay/circuit identifier changes over time are preserved as history, not silently overwritten, exactly as substation mnemonic history is already preserved.
- Scheme modules (UFLS/UVLS/EMLS) that currently reference only `substation_id`, with a temporary free-text equipment placeholder, have a concrete, well-defined target to migrate toward.
- PSS/E Integration has a real Master Data anchor to correlate imported topology elements against, closing the gap it explicitly deferred.
- A protection relay's physical identity (a real device, wired to specific equipment) is modeled separately from any scheme's use of it — resolving the relay-ownership ambiguity flagged since the Codebase Discovery Report.
- The module stays scoped to what grid defence schemes operationally need — never expanding, by default, into enterprise asset management concerns (§4).

---

## 3. Responsibilities

Equipment Registry owns:

- ✓ Equipment identity (`Equipment` — the common backbone every equipment type shares, §7.1)
- ✓ Load transformers, auto-transformers, and incoming branches as equipment types (§7.2–§7.4)
- ✓ Protection relays as physical equipment (§7.5)
- ✓ Equipment lifecycle status (§8)
- ✓ Bay ID / alias history for any equipment type (§7.6)
- ✓ Its own audit trail (`equipment_registry_audit_log`, CLAUDE.md A4)

---

## 4. Non-Responsibilities

Equipment Registry does **not** own:

- ✗ Substation identity or metadata — owned by the Substation Registry (CLAUDE.md §8). Every piece of equipment references a `substation_id`, never a copy of substation attributes.
- ✗ PSS/E topology data (`TopologyVersion`, `TopologyBus`, `TopologyBranch`, `TopologyTransformer`) — owned by PSS/E Integration. Equipment Registry does not parse or store topology; it is a correlation *target*, not a topology source (§7.7).
- ✗ Load snapshots or any live/derived network state — owned by PSS/E Integration.
- ✗ UFLS, UVLS, or EMLS assignments, stages, or scheme data of any kind. **This module has no knowledge of "schemes," "stages," or "shedding assignments"** — mirroring the identical decoupling principle already established for Network Model ([network-model-module.md](network-model-module.md) §9 rule 8) and Critical Infrastructure ([critical-infrastructure-module.md](critical-infrastructure-module.md) §9 rule 10).
- ✗ Scheme-specific shedding configuration — which relay a scheme uses for which stage, or what threshold triggers it, is scheme-owned data (§7.5's relay-ownership resolution).
- ✗ Network analysis results (connectivity, islands) — owned by Network Model.
- ✗ Identity, authentication, or authorization — owned by IAM.
- ✗ **Enterprise asset management.** GridDefence serves grid system operators, not asset owners — this module is not an EAM system and does not become one. Specifically out of scope: work orders, maintenance history and scheduling, procurement, warranty tracking, and asset ownership lifecycle (acquisition, depreciation, disposal). Where a future EAM system exists elsewhere in the organisation, this module is, at most, a read-only reference point it could correlate against — Equipment Registry never grows toward owning that data itself (§7.1, §17).

---

## 5. Owned Entities

| Entity | Description |
|---|---|
| `Equipment` | The common identity backbone every piece of equipment shares: a stable `equipment_id`, its owning substation, its type discriminator, its current bay ID, and its lifecycle status (§7.1). |
| `LoadTransformerDetail` | Type-specific attributes for a load transformer, one row per `Equipment` of that type (§7.2). |
| `AutoTransformerDetail` | Type-specific attributes for an auto-transformer (§7.3). |
| `IncomingBranchDetail` | Type-specific attributes for an incoming branch, including the far-end substation (§7.4). |
| `RelayDetail` | Type-specific attributes for a protection relay as a physical device (§7.5). |
| `RelayControlledEquipment` | The set of other `Equipment` rows a given relay is physically wired to control. |
| `EquipmentAlias` | Historical bay ID / identifier changes for any `Equipment` row, with a validity window (§7.6). |
| `equipment_registry_audit_log` | This module's own audit trail (CLAUDE.md A4). |

---

## 6. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| Substation | Master Data (Substation Registry) | `substation_id` (UUID) only, on `Equipment` and (for the far end) `IncomingBranchDetail` — no attributes copied |
| Operational Status | Core Platform (reference data) | `operational_status_id`, reused directly from the same reference table Substation Registry already uses (§8) — not duplicated as an equipment-specific lookup |
| User | Core Platform (IAM) | `user_id` (UUID) only, for `created_by_user_id`/`updated_by_user_id` and audit attribution; fallback `external_principal_id` + provider per [ADR-002](../adr/ADR-002-identity-and-access-management.md) |
| `TopologyVersion`, `TopologyBranch`, `TopologyTransformer` | PSS/E Integration | Not referenced by this module's own tables (§7.7) — PSS/E Integration is expected to hold the reverse reference once it builds its own equipment-topology mapping; Equipment Registry may optionally *consume* PSS/E Integration's read-only interfaces for display purposes only (e.g. current in-service status), never storing a copy |

---

## 7. Domain Model

```
Equipment (1) ──── (0..1) LoadTransformerDetail   [exactly one detail row matching equipment_type]
Equipment (1) ──── (0..1) AutoTransformerDetail
Equipment (1) ──── (0..1) IncomingBranchDetail
Equipment (1) ──── (0..1) RelayDetail

Equipment (relay) ──── (many) RelayControlledEquipment ──── references ──▶ Equipment (controlled)  [both internal to this module]

Equipment (1) ──── (many) EquipmentAlias

Equipment           ──── references ───▶ Substation.substation_id            (Master Data, external)
IncomingBranchDetail ──── references ───▶ Substation.substation_id (to_substation) (Master Data, external)
Equipment            ──── references ───▶ OperationalStatus (Core Platform, external)
Equipment / EquipmentAlias ──── references ───▶ User.user_id                 (Core Platform/IAM, external)
```

No arrow points from this module toward PSS/E Integration or any scheme module — the correlation to topology data is held by PSS/E Integration itself, referencing `equipment_id` read-only (§7.7), and no scheme module's tables are referenced at all (§4).

### 7.1 Equipment Identity and Type Model — Answering "Equipment Identity" and "Equipment Type Model"

**`Equipment` is a common backbone entity, not four unrelated top-level tables.** Every piece of equipment — regardless of type — gets one `equipment_id` (UUID, per CLAUDE.md A5), one `substation_id`, one `bay_id`, one lifecycle status, and one audit trail, through the shared `Equipment` row. Type-specific attributes live in a separate detail table (`LoadTransformerDetail`, `AutoTransformerDetail`, `IncomingBranchDetail`, `RelayDetail`), exactly one of which exists per `Equipment` row, matching its `equipment_type` discriminator.

This is a deliberate improvement over the legacy MVP's design, which modeled `LoadTransformer`, `AutoTransformer`, and `IncomingBranch` as three entirely separate, unrelated tables with no common identity. That design forced the MVP's own `EquipmentTopologyMap` and `EquipmentSnapshotState` (per the Codebase Discovery Report) to use three parallel nullable foreign keys with an XOR constraint ("exactly one of load_transformer/incoming_branch/auto_transformer is set") every time they needed to reference "a piece of equipment, whatever type it is." A single `equipment_id` backbone removes that awkwardness at the source: any future consumer — a scheme module's assignment, PSS/E Integration's topology mapping — needs only one foreign key, not a polymorphic triple. This directly serves the stated goal: **"scheme modules may eventually reference `equipment_id` instead of only `substation_id`"** (§7.8) is a clean, single-column reference under this design, not a three-way XOR.

`equipment_type` is one of `LoadTransformer`, `AutoTransformer`, `IncomingBranch`, `Relay` — immutable once an `Equipment` row is created (§9); there is no "convert this transformer into a branch" operation, only retiring one record and creating another, consistent with Master Data's immutable-identity principle applied at the equipment level.

**Mandatory vs. optional fields — the scope boundary made concrete.** Consistent with §1's scope framing (grid system operators, not asset owners), the `Equipment` backbone's *mandatory* fields are limited to exactly what a grid defence scheme needs to function:

- Equipment identity (`equipment_id`)
- Substation association (`substation_id`)
- Bay/function identifier (`bay_id`)
- Equipment type (`equipment_type`)
- Trip/affected-equipment relationship, where applicable (`RelayControlledEquipment` for relays, §7.5)
- Operational usability/status (`operational_status_id`)
- Scheme relevance (`is_scheme_relevant` — a scheme-agnostic flag marking whether this equipment is the kind of thing a grid defence scheme assignment would ever reference, distinguishing operationally-relevant switching/protection equipment from equipment of no shedding relevance; it says nothing about *which* scheme or *how*, preserving the decoupling in §9 rule 9)
- Remarks (`remarks`, free text)

**Manufacturer, model, firmware version, serial number, maintenance owner, and any other asset-management-adjacent metadata are optional fields only** (§11) — never required to create, edit, or operationally use an `Equipment` record. They exist purely as convenience metadata for a site engineer who happens to know them; nothing in this module's business rules, validation rules, or service interfaces depends on their presence.

### 7.2 Load Transformer Model

`LoadTransformerDetail` carries: `transformer_no`, `hv_voltage`, `hv_breaker_number`, `lv_voltage`, `lv_breaker_number`, `capacity_mva`, `commissioning_date` — directly matching the legacy MVP's `LoadTransformer` fields (Codebase Discovery Report), now attached to the common `Equipment` backbone rather than standing alone. The computed `bay_id` convention (`{substation_mnemonic}_T{transformer_no}`) is preserved as documented policy (§10).

### 7.3 Auto-Transformer Model

`AutoTransformerDetail` carries the same shape as `LoadTransformerDetail` (`transformer_no`, `hv_voltage`, `hv_breaker_number`, `lv_voltage` [required, unlike load transformers], `lv_breaker_number`, `capacity_mva`, `commissioning_date`), reflecting the MVP's own near-identical field set for the two transformer types, kept as genuinely separate `equipment_type` values (not merged into one "transformer" type) because they represent distinct physical roles in the substation (auto-transformers interconnect voltage levels; load transformers step down to load-serving voltage) — a distinction worth preserving in the type model even though their attribute shapes are similar. The computed `bay_id` convention (`{substation_mnemonic}_AT{transformer_no}`) is preserved.

### 7.4 Incoming Branch Model

`IncomingBranchDetail` carries: `to_substation_id` (the far-end substation — a second, distinct reference to Substation Registry, alongside the base `Equipment.substation_id` representing the near/"from" end), `ckt_id`, `breaker_number`, `commissioning_date`. The computed `bay_id` convention (`{substation_mnemonic}_{to_substation_mnemonic}_{ckt_id}`) is preserved, and, per the legacy MVP's own precedent, is exactly the kind of identifier most likely to change over time (renumbering, re-terminuation) — making incoming branches the primary, though not exclusive, beneficiary of the generalized alias-history mechanism (§7.6).

### 7.5 Relay Model — The Relay Ownership Decision

**Relays are physical equipment master data, but a relay's use by a specific scheme is not.** This is the resolution to the ambiguity flagged since the Codebase Discovery Report ("if a relay is genuinely scheme-agnostic physical equipment, it should be Master Data referenced by all scheme modules, not duplicated per scheme").

The reasoning: a protection relay is a real physical device — it has a location, physical wiring to specific transformers and branches it can trip, and (in modern digital/numerical relays) frequently implements *multiple* protection functions simultaneously in one physical box. This physical reality — identity, location, and **which equipment it can trip** — is genuinely Master Data, no different in kind from a transformer's physical existence. What is **not** Master Data is a relay's *scheme-specific trip configuration*: which frequency or voltage threshold makes it act, and which scheme's stage it is currently configured to serve. That is scheme-owned business data, because it is a design decision UFLS, UVLS, or EMLS makes independently, and — critically — **the same physical relay may legitimately be referenced by more than one scheme module** (a multifunction relay implementing both a UFLS element and a UVLS element), which is only expressible cleanly if the physical device and its per-scheme configuration are separate things owned by separate modules.

**Relay modeling in this module is deliberately scoped to the relay/tripping function and its wired trip targets — nothing more.** `RelayDetail` carries `relay_name`, `target_voltage_kv` (the voltage level of the breakers this relay operates, a physical/wiring characteristic, not a trip threshold), and `is_active`, plus, via `RelayControlledEquipment`, the mandatory set of other `Equipment` rows (transformers, branches) it is physically wired to control — this trip-target relationship is the operational core of the relay model, and is why `RelayControlledEquipment` is listed as mandatory-supporting data in §7.1, not optional. `RelayDetail` carries **no** frequency threshold, voltage threshold, time delay, or any concept of "which scheme uses this" (those remain scheme-owned, as above), and it carries **no manufacturer, model, or firmware version as required data** — a site engineer working the relay/tripping function has everything this module requires without ever entering that information. Manufacturer, model, firmware version, and serial number *may* be recorded, using the same optional metadata fields available to any `Equipment` row (§7.1, §11) — they are convenience data, never load-bearing for this module's own business rules. Once scheme modules migrate to equipment-level references (§7.8), each scheme's own assignment records which `relay_id` it uses for a given stage — that reference, and the threshold/delay it implies, remains entirely the scheme module's own business data, exactly as `equipment_reference` free text is scheme-owned today.

### 7.6 Bay ID / Alias History

**Bay ID history is a generic capability of the `Equipment` backbone, not limited to incoming branches.** The legacy MVP only tracked alias history for `IncomingBranch` via a dedicated `IncomingBranchAlias` model; `LoadTransformer` and `AutoTransformer` bay IDs, while equally derived and equally capable of changing (e.g. a transformer renumbering), had no equivalent history mechanism. GridDefence generalizes this: `EquipmentAlias` applies to any `Equipment` row regardless of type, carrying `alias_bay_id`, `valid_from`, and a nullable `valid_to` (null = the alias that was in effect immediately before the current one) — the same validity-window pattern already established for Substation Registry's `substation_alias` ([substation-registry.md](substation-registry.md) §7.6) and Critical Infrastructure's `CriticalAssetSubstation` ([critical-infrastructure-module.md](critical-infrastructure-module.md) §7.5). This is now the third or fourth Master Data entity to use this exact pattern — a validated, recurring design choice, not a one-off.

When `Equipment.bay_id` changes, the previous value is closed out into a new `EquipmentAlias` row (`valid_to` set to the change timestamp) before the new value is written — never silently overwritten (CLAUDE.md §5.2 applied to Master Data relationship/identifier history, as already established elsewhere in this series).

### 7.7 Relationship to PSS/E TopologyVersion and the EquipmentTopologyMap Concept

**Equipment Registry does not own the equipment-to-topology mapping.** [psse-integration-module.md](psse-integration-module.md) §17 already anticipated this exact linkage from its own side ("a mapping entity correlating physical equipment... to `TopologyBranch`/`TopologyTransformer` records, mirroring the legacy MVP's `EquipmentTopologyMap` pattern") and reserved it as a Future Extension once Equipment Registry exists. This document does not reverse that ownership assignment — PSS/E Integration is expected to own `EquipmentTopologyMap`, scoped per `TopologyVersion` (since a piece of equipment's correlation to a specific topology element could differ across topology versions, e.g. after renumbering), holding a single, clean foreign key to `equipment_id` (§7.1) instead of the MVP's three-way XOR, resolved during RAW file import by matching bay IDs (and their alias history, §7.6) against Equipment Registry's records.

Equipment Registry's role in this relationship is purely as the **referenced side**: it exposes a read-only equipment-lookup service interface (§13) that PSS/E Integration's import process calls to resolve a parsed bay identifier — checking both the current `bay_id` and historical `EquipmentAlias` entries — to a stable `equipment_id`. Equipment Registry never writes to, or holds a foreign key into, PSS/E Integration's tables.

### 7.8 How Scheme Modules Should Eventually Reference Equipment, and the Migration Path

**Answering "how UFLS/UVLS/EMLS should eventually reference equipment" and "migration path from substation-level to equipment-level assignment":** this confirms and elaborates the migration path already sketched, identically, in [ufls-module.md](ufls-module.md) §7.4 Open Question 2, [uvls-module.md](uvls-module.md), and [emls-module.md](emls-module.md):

1. A migration adds a nullable `equipment_id` foreign key (referencing this module's `Equipment.equipment_id`) to each scheme module's own direct-assignment table (`ufls_direct_assignment`, `uvls_direct_assignment`, `emls_direct_assignment`), alongside — not replacing — the existing `equipment_reference` free-text column.
2. A data migration attempts to resolve every existing `equipment_reference` value against Equipment Registry, checking both current `bay_id` values and historical `EquipmentAlias` entries (§7.6) — a free-text value recorded by an engineer months or years ago may match a *historical* alias rather than the equipment's current identifier, which is precisely why alias history matters for this reconciliation to succeed accurately.
3. Assignments that resolve are populated with the real `equipment_id`; assignments that do not resolve are flagged for manual reconciliation, mirroring the "unmatched" reporting pattern already established in PSS/E Integration's own import process ([psse-integration-module.md](psse-integration-module.md) §5).
4. `equipment_reference` is retained afterward as a legacy/fallback display value, not removed — historical assignments' originally-recorded intent is never lost, consistent with CLAUDE.md §5.2 applied to this migration itself.
5. Once populated, a scheme module's assignment may resolve equipment-level attributes (which specific transformer, which relay) via `equipment_id`, in addition to the substation-level `substation_id` reference it already holds — both remain valid references simultaneously; equipment-level granularity refines, rather than replaces, the substation-level relationship.

**Whether this requires a new ADR — yes, but not for Equipment Registry's existence.** This module's existence and domain placement (Master Data, sibling to Substation Registry, following the exact ownership pattern already reserved since [substation-registry.md](substation-registry.md) §14) is not itself a new or controversial decision — it was anticipated from the beginning of this document series and requires no separate ratification. **The migration described in steps 1–5 above does require its own ADR before it is undertaken**, because it simultaneously modifies the core assignment model of three already-built, already-ratified Defence Scheme modules (UFLS, UVLS, EMLS) — exactly the kind of cross-cutting change CLAUDE.md A13 requires an ADR for ("any change that modifies core architecture, domain ownership... or database standards"). This document defines the target shape and the migration mechanism; it does not authorize executing it. See §17.

---

## 8. Lifecycle / State Model

`Equipment` and its type-specific detail rows are **not** governed by the Canonical Version Lifecycle (CLAUDE.md A3) — the same justification already established for Substation Registry ([substation-registry.md](substation-registry.md) §11.5) and every other Master Data entity in this series (CLAUDE.md §11.5: "current-state master data... single authoritative record"). This is physical asset data with a current-truth-plus-audit-log pattern, not approved engineering policy requiring a Draft/Review/Approve workflow.

- `Equipment.operational_status_id` follows the same lifecycle values already defined by Core Platform's reference data and used by Substation Registry (Planned → Active → Decommissioned/Retired) — reused directly, not redefined (§6). Soft-delete only; an `Equipment` row is never physically deleted (CLAUDE.md §11.6).
- `EquipmentAlias` entries use the `valid_from`/`valid_to` window described in §7.6 — not a formal state machine.
- `RelayDetail.is_active` is a simple physical-device flag (is this relay currently commissioned/in service), independent of `operational_status_id` on the parent `Equipment` row in the same way [substation-registry.md](substation-registry.md) keeps physical commissioning status conceptually distinct from scheme participation — a relay can be `Active` as physical equipment while a scheme independently decides whether it currently assigns anything to it.
- Every change is captured in the audit log (§14) regardless of the lack of an approval lifecycle.

---

## 9. Business Rules

1. Every `Equipment` row belongs to exactly one substation (`substation_id`) — its "home" location; for an incoming branch, this is the near/"from" end.
2. `equipment_type` is immutable once an `Equipment` row is created; a genuine type change is modeled as retiring one record and creating another, never an in-place conversion.
3. Exactly one detail row (`LoadTransformerDetail`/`AutoTransformerDetail`/`IncomingBranchDetail`/`RelayDetail`) exists per `Equipment` row, and its type must match `equipment_type`.
4. `bay_id` is unique among all *currently valid* `Equipment` records (no two pieces of equipment share an active bay ID simultaneously); a superseded `bay_id` remains unique within its own validity window via `EquipmentAlias` (§7.6).
5. An `IncomingBranchDetail`'s `substation_id` (via its parent `Equipment`) and `to_substation_id` must reference two distinct substations.
6. A `RelayControlledEquipment` link's controlled equipment must not itself have `equipment_type = Relay` — a relay controls transformers/branches, not other relays.
7. A `RelayControlledEquipment` link's controlled equipment must belong to the same substation as the relay itself — a relay does not typically control equipment at a different physical location.
8. **Bay ID changes are always tracked via `EquipmentAlias`, never overwritten in place** (§7.6, CLAUDE.md §5.2).
9. **This module has no knowledge of "schemes," "stages," or "shedding assignments."** It answers only "what equipment exists, where, and how is it identified and wired" (§4). A scheme's use of a relay or transformer, and any threshold or delay that implies, is that scheme module's own business data (§7.5).
10. Equipment Registry never writes to Substation Registry, PSS/E Integration, or any scheme module's tables — every cross-module write boundary in this series applies equally here (CLAUDE.md A1, [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md)).
11. Changing `operational_status_id`, `bay_id` (which produces a new `EquipmentAlias`), or any `RelayControlledEquipment` link requires an authenticated, named IAM user and is audited (§14).
12. Cross-module consumers (PSS/E Integration, and eventually scheme modules) access this module's data exclusively through its read-only service interface (§13) — never through direct table access.
13. **Manufacturer, model, firmware version, serial number, maintenance owner, and any other asset-management-adjacent metadata are optional fields and must never be made mandatory** by validation rules, API contracts, or downstream tooling (§7.1) — doing so would silently expand this module's scope toward enterprise asset management, which §4 explicitly excludes.
14. This module does not model work orders, maintenance history, procurement, or asset ownership lifecycle, and must not be extended to do so without a new ADR revisiting the scope decision in §1/§4.

---

## 10. Validation Rules

- `bay_id` is computed per the documented convention for each type (`{substation_mnemonic}_T{transformer_no}` for load transformers, `{substation_mnemonic}_AT{transformer_no}` for auto-transformers, `{substation_mnemonic}_{to_substation_mnemonic}_{ckt_id}` for incoming branches, an administratively-assigned identifier for relays) and validated for uniqueness among currently-valid equipment (§9, rule 4).
- `substation_id` (and, for incoming branches, `to_substation_id`) must reference existing Substation Registry records.
- `operational_status_id` must reference a valid Core Platform reference row.
- For transformers and auto-transformers, `hv_voltage` should be greater than or equal to `lv_voltage` where both are populated (a light physical-sanity check, not a hard architectural constraint given real-world exceptions may exist).
- `EquipmentAlias.valid_to`, if set, must be greater than or equal to `valid_from`.
- A `RelayControlledEquipment` link's controlled-equipment constraint (§9, rules 6–7) is validated at creation time.
- A `Relay`-type `Equipment` row must have at least one `RelayControlledEquipment` link before it can be marked `is_active` — a relay with no wired trip target is not yet operationally meaningful (§7.5).
- No validation rule may require a value for manufacturer, model, firmware version, serial number, maintenance owner, or other optional metadata fields (§9, rule 13) — these fields accept `NULL`/empty without constraint.

---

## 11. Database Design (Concept)

Conceptual only — no migrations are defined here.

| Table (conceptual) | Key columns (conceptual) | Notes |
|---|---|---|
| `equipment` | **Mandatory:** `equipment_id` (UUID PK), `substation_id` (FK, external, `ON DELETE RESTRICT`), `equipment_type`, `bay_id` (unique among current), `operational_status_id` (FK, external), `is_scheme_relevant` (boolean), `remarks` (text, nullable value but always-present field), `created_by_user_id`, `updated_by_user_id`, `created_at`, `updated_at`. **Optional (asset-management-adjacent, never required — §7.1, §9 rule 13):** `manufacturer`, `model`, `firmware_version`, `serial_number`, `maintenance_owner` (free text) | The common backbone (§7.1). UUID PK per CLAUDE.md A5. Optional columns accept `NULL` with no validation constraint. |
| `load_transformer_detail` | `equipment_id` (PK/FK to `equipment`), `transformer_no`, `hv_voltage`, `hv_breaker_number`, `lv_voltage`, `lv_breaker_number`, `capacity_mva`, `commissioning_date` | One row iff `equipment.equipment_type = 'LoadTransformer'`. Functional/operational attributes only — no asset-management fields duplicated here (those live once, optionally, on `equipment`, §7.1). |
| `auto_transformer_detail` | `equipment_id` (PK/FK), `transformer_no`, `hv_voltage`, `hv_breaker_number`, `lv_voltage` (required), `lv_breaker_number`, `capacity_mva`, `commissioning_date` | One row iff `equipment_type = 'AutoTransformer'`. |
| `incoming_branch_detail` | `equipment_id` (PK/FK), `to_substation_id` (FK, external, `ON DELETE RESTRICT`), `ckt_id`, `breaker_number`, `commissioning_date` | One row iff `equipment_type = 'IncomingBranch'`. |
| `relay_detail` | `equipment_id` (PK/FK), `relay_name`, `target_voltage_kv`, `is_active` | One row iff `equipment_type = 'Relay'`. Function/tripping attributes only — no threshold/delay/scheme fields (§7.5), and no manufacturer/model/firmware fields (those are the shared, optional `equipment` columns, not duplicated per type). |
| `relay_controlled_equipment` | `id` (BIGINT PK), `relay_equipment_id` (FK to `equipment`), `controlled_equipment_id` (FK to `equipment`) | Both internal FKs into this module's own `equipment` table. Mandatory-supporting data for any active relay (§10). |
| `equipment_alias` | `id` (BIGINT PK), `equipment_id` (FK), `alias_bay_id`, `valid_from`, `valid_to` (nullable) | Generalized alias history (§7.6). |
| `equipment_registry_audit_log` | `log_id` (BIGINT PK), `entity_type`, `entity_id`, `field_name`, `old_value`, `new_value`, `changed_at`, `changed_by_user_id`, `change_reason` | Owned per CLAUDE.md A4. |

**Cross-module constraints:** all foreign keys into `substation` and `user` are `ON DELETE RESTRICT`. Tables are written exclusively through this module's own service layer.

---

## 12. API Contract (Concept)

APIs are external/UI-facing contracts (CLAUDE.md §13, A9); conceptual resource shape only.

- `equipment` — list/retrieve across all types (filterable by `substation_id`, `equipment_type`, `operational_status`); type-specific detail returned nested per row.
- `load-transformers`, `auto-transformers`, `incoming-branches`, `relays` — type-specific sub-resources for creation/editing, each ultimately backed by an `equipment` row plus its detail table.
- `equipment/{id}/aliases` — read-only history of bay ID changes (§7.6).
- `relays/{id}/controlled-equipment` — manage a relay's physical wiring to other equipment.

**Contract requirements (CLAUDE.md A9):** pagination/filtering for collection endpoints; structured error responses; authentication/authorization per endpoint (§15); audit-relevant actions flagged (all writes).

**Data contracts:** standard three-layer separation (CLAUDE.md A6).

---

## 13. Service Interfaces

Per CLAUDE.md A1 (module communication via in-process service-layer interfaces):

**Equipment Registry exposes, for other modules to consume:**
- A read-only equipment-lookup interface, resolving a bay identifier (current or historical, via `EquipmentAlias`) to a stable `equipment_id` — the primary interface PSS/E Integration's future `EquipmentTopologyMap` will call during import (§7.7).
- A read-only equipment-by-substation listing interface — for Substation Registry's own detail views (mirroring the legacy MVP's `SubstationDetailSerializer` prefetching pattern) and for future scheme-module equipment-level assignment lookups (§7.8).
- A read-only relay lookup, resolving a `relay_id` to its physical details and controlled-equipment set — for future scheme-module consumption once equipment-level relay assignment is adopted (§7.8).

**Equipment Registry consumes, from other modules' service layers — never their repositories directly:**
- From Substation Registry: substation existence/validity checks for `substation_id`/`to_substation_id`.
- From Core Platform (IAM): authorization checks for writes, user lookups for audit attribution.
- Optionally, from PSS/E Integration: read-only current in-service status for display purposes only (e.g. showing whether a piece of equipment appears energized in the latest topology) — never stored, never authoritative for this module's own lifecycle status (§8).

Equipment Registry never calls a scheme module's service interface (§4), and no scheme module writes to this module's tables, per CLAUDE.md A1 and [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md).

---

## 14. Audit Requirements

Per CLAUDE.md §5.4 and A4, Equipment Registry owns and writes its own audit log, covering every owned entity in §5.

- Every create, update, and status change on `Equipment` or its detail tables is recorded with who, when, what changed, and why.
- **Bay ID changes are audited with particular emphasis**, given they directly affect the reconciliation described in §7.8 — a poorly-documented bay ID change could make future scheme-module migration or PSS/E Integration matching materially harder.
- `RelayControlledEquipment` changes (a relay's physical wiring being added or removed) are audited — this is safety-relevant physical configuration, not routine metadata.
- Audit history is append-only and never modified; audit log access is itself access-controlled (CLAUDE.md A10).

---

## 15. Security Considerations

- All GridDefence engineering data is sensitive by default (CLAUDE.md A10); TLS required outside local development.
- Equipment Registry's data is engineering reference data broadly similar in sensitivity to Substation Registry's own — **not** subject to the stricter human read-access tier recommended for Critical Infrastructure ([critical-infrastructure-module.md](critical-infrastructure-module.md) §15), since knowing a substation's transformer inventory is materially less sensitive than knowing which substations serve national-security-critical loads.
- Write access (creating/editing equipment, changing status, modifying relay wiring) requires an authenticated, named IAM user with an appropriate engineering-editor role — comparable in tier to Substation Registry's own write permissions, not the elevated admin-tier reserved for Critical Infrastructure or Cross-Scheme Compliance's rule configuration.
- Module-to-module service calls (PSS/E Integration's future lookup calls, future scheme-module equipment resolution) are trusted internal code paths, not gated by per-request human permission checks — the same distinction already drawn explicitly in [critical-infrastructure-module.md](critical-infrastructure-module.md) §15.

---

## 16. Testing Requirements

Per CLAUDE.md §18 and A11, in priority order:

1. **Business rule tests** — `bay_id` uniqueness among current equipment; exactly-one-detail-row-matching-type enforcement; `RelayControlledEquipment` constraints (no relay-controls-relay, same-substation requirement); a structural/architectural test confirming no table in this module has a foreign key into any scheme module's schema (§9 rule 9, mirroring the equivalent tests already specified in [network-model-module.md](network-model-module.md) §16 and [critical-infrastructure-module.md](critical-infrastructure-module.md) §16).
2. **Engineering calculation / validation tests** — bay ID computation correctness per type; alias-history resolution correctness (both current and historical lookups succeeding, §7.7, §7.8).
3. **API contract tests** — request/response schema conformance; authorization enforcement.
4. **Database migration tests** — required once actual migrations are authored.
5. **UI behaviour tests** — required once an Equipment Registry frontend exists.

Business rules and validation logic must not be merged without accompanying tests (CLAUDE.md A11).

---

## 17. Future Extensions

- **PSS/E `EquipmentTopologyMap`** — owned by PSS/E Integration, referencing this module's `equipment_id` (§7.7); the concrete realization of the Future Extension already reserved in [psse-integration-module.md](psse-integration-module.md) §17.
- **Scheme-module equipment-level migration** (§7.8) — the concrete data/schema migration for UFLS/UVLS/EMLS; **requires its own ADR** before being undertaken (§7.8), not designed further here.
- **Richer equipment types** — circuit breakers, current/voltage transformers (CTs/VTs), or other bay-level assets could be added as additional `equipment_type` values sharing the same `Equipment` backbone, without redesigning this module's core structure.
- **Integration with an external enterprise asset management (EAM) system**, should the organisation operate one — a read-only correlation (e.g. resolving `equipment_id` against an external asset record by serial number) is the appropriate future shape, not building work-order, maintenance-history, or procurement functionality inside this module (§1, §4, §9 rule 14). Any such integration remains strictly optional and read-only from this module's side.
- **Relay scheme-usage visibility** — once scheme modules migrate to equipment-level relay references (§7.8), a read-only Audit and Analytics capability could show "which schemes currently use this relay" by querying each scheme module's own data — Equipment Registry itself still never needs to know.

---

## 18. Risks and Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| The scheme-module equipment-level migration (§7.8) is a cross-cutting change touching three already-built modules simultaneously | Risk of inconsistent or partial migration across UFLS/UVLS/EMLS if undertaken informally | Require the dedicated ADR already flagged (§7.8) before starting; the ADR should define a single, coordinated migration plan covering all three modules together, not three independent efforts |
| `bay_id` reconciliation against historical `EquipmentAlias` entries (§7.8) may still fail to resolve some legacy `equipment_reference` free-text values (typos, ambiguous historical records) | Some historical assignments could remain unresolved indefinitely | Mirror PSS/E Integration's own "unmatched" reporting pattern (§7.7) — surface unresolved assignments for manual reconciliation rather than blocking the migration on 100% automatic resolution |
| A relay physically serving multiple schemes (§7.5) could create confusion if two scheme modules independently configure conflicting thresholds against the same physical device without realizing they share it | Operational miscoordination at a shared relay | Recommend this scenario be explicitly surfaced by a future Cross-Scheme Compliance extension or Dashboard view once equipment-level relay references exist (§17) — out of scope for this module itself, which has no visibility into scheme configuration by design |
| Generalizing alias history to all equipment types (§7.6) is new relative to the legacy MVP's incoming-branch-only precedent | Slightly more schema than the MVP had for transformers, for a benefit (transformer renumbering history) that may prove rarely used in practice | Acceptable, low-cost consistency given the pattern is already established and reused three times elsewhere in this series; monitor actual usage before considering removal |
| Scope creep toward enterprise asset management over time (e.g. a future contributor adds a "next maintenance date" field because it seems convenient) | Would silently expand this module beyond what grid system operators need, duplicating or competing with a real EAM system | Treat §4's EAM exclusion and §9 rules 13–14 as a hard boundary requiring a new ADR to cross, not a soft guideline; any proposal to add maintenance/procurement/ownership-lifecycle fields should be rejected at review unless that ADR exists |

---

## Recommended Next Architecture Document

**IAM module.**

Every module in this entire series — Substation Registry, PSS/E Integration, Network Model, UFLS, UVLS, EMLS, Critical Infrastructure, Cross-Scheme Compliance, and now Equipment Registry — references `user_id` for accountability and calls into IAM's service layer for authorization, yet IAM itself is the one foundational module that has never received the full Canonical Module Architecture Document Template treatment every other module has. [ADR-002](../adr/ADR-002-identity-and-access-management.md) ratified IAM's *ownership* of Users, Roles, Permissions, and external identity mappings, but not the full detail — Role/Permission database design, lifecycle, service interface contract, security model for managing authorization itself — that a proper module document specifies. Completing this closes the one remaining gap in an otherwise fully-architected foundational layer, and is a prerequisite of substance (not just form) for the equipment-level migration ADR flagged in §7.8, which will itself need to reference specific IAM roles/permissions precisely.

**Implementation planning document** is a very strong, arguably comparably urgent alternative: across eleven architecture documents and five ADRs, GridDefence now has a substantially complete design for its foundational layer, its network/topology layer, all three Defence Scheme modules, and its cross-cutting compliance mechanism. At this scale, continuing to add architecture documents without pausing to sequence actual build work risks analysis running further ahead of implementation than is useful. Once IAM's module document closes the last foundational gap, an implementation planning document — sequencing phases, dependencies, and the several ADRs this series has flagged as still outstanding (`Superseded → Active` reactivation, the equipment-level migration, Rule 2's manual-invocation severity policy) — becomes the natural next step.

**UVLS/EMLS refinement** and **Dashboard module** remain valuable but lower urgency: neither is blocked by, nor blocks, IAM's completion, and both were already reasoned about as secondary recommendations in [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md) and [emls-module.md](emls-module.md) respectively.
