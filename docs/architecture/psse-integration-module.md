# PSS/E Integration Module Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document follows the Canonical Module Architecture Document Template (CLAUDE.md **A8**).

Related documents: [system-overview.md](system-overview.md), [domain-model.md](domain-model.md), [substation-registry.md](substation-registry.md), [ufls-module.md](ufls-module.md), [ADR-000](../adr/ADR-000-architecture-principles.md), [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md), [ADR-002](../adr/ADR-002-identity-and-access-management.md), [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md) (the architectural decision this document formalizes).

---

## 1. Module Overview

PSS/E Integration is the module that imports PSS/E `.raw` case files (and lightweight load-profile files) and turns them into GridDefence's versioned, auditable representation of the transmission network's structure and load state. It is the concrete implementation of the "Network Data" layer described in [domain-model.md](domain-model.md) §1 — previously marked future/reserved, now activated by [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md).

The module's defining architectural move, decided in ADR-003, is separating two things the legacy MVP conflated: **topology** (network structure — buses, branches, transformers, connectivity — changes rarely) and **load** (P/Q at each bus — changes often). This lets GridDefence refresh grid load data frequently without unnecessary topology churn, while keeping approved UFLS/UVLS/EMLS scheme data fully immutable and historically reproducible regardless of how often the network model itself is refreshed.

---

## 2. Purpose

To provide GridDefence with an accurate, versioned, and fully auditable representation of the transmission network, imported from PSS/E study cases, such that:

- Structural topology changes are captured discretely, and reused automatically when a new import is structurally identical to the current one.
- Load data can be refreshed on its own cadence — independent of topology — without creating unnecessary topology history.
- Scheme modules (UFLS/UVLS/EMLS) can obtain recommended MW figures for engineering design, while their own approved data is never silently altered by a later import.
- Every import is fully traceable: who imported what, when, what was detected, and what was reused versus newly created.

---

## 3. Responsibilities

PSS/E Integration owns:

- ✓ RAW file import workflow (upload, parse, validate, preview, commit)
- ✓ `RawFileImportBatch` — the audit/traceability record of each import action
- ✓ `TopologyVersion` — immutable network structure
- ✓ `LoadSnapshot` — immutable load/generation capture, tied to one `TopologyVersion`
- ✓ Topology signature calculation (deterministic hash over structural data only)
- ✓ Topology/load separation during parsing
- ✓ Topology reuse when a new import's signature matches the Current `TopologyVersion`
- ✓ Load-only refresh from a different RAW (or load-profile) file
- ✓ Import validation (bus-matching, fatal-vs-warning classification)
- ✓ Import audit trail (its own audit log, per CLAUDE.md A4)
- ✓ Import status lifecycle (`RawFileImportBatch` status; `TopologyVersion`/`LoadSnapshot` Imported→Current→Superseded)
- ✓ Snapshot activation / Current selection
- ✓ Parse error and warning reporting

---

## 4. Non-Responsibilities

PSS/E Integration does **not** own:

- ✗ Substation identity or metadata — owned by the Substation Registry (Master Data). PSS/E Integration references substations only by `substation_id`.
- ✗ Physical equipment identity (transformers, branches as engineering assets) — reserved for a future Equipment Registry submodule of Master Data ([substation-registry.md](substation-registry.md) §14, [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md)). Until that module exists, `TopologyBranch`/`TopologyTransformer` remain self-contained PSS/E representations with no formal equipment linkage.
- ✗ **Network topology analysis** — connectivity-graph traversal, electrical island detection, and topology-based ("pocket") shedding logic belong to a future **Network Model** module, which consumes the `TopologyVersion` data owned here but implements its own analysis algorithms on top of it. PSS/E Integration owns the *data*; Network Model owns the *analysis*. This boundary is deliberate (CLAUDE.md §5.3, Explicit Architecture) and is the reason Network Model is this document's top recommended next step (§18).
- ✗ Approved scheme engineering data — UFLS/UVLS/EMLS own their own approved MW figures once captured. PSS/E Integration only ever supplies *recommendations*, never authoritative values (see §9).
- ✗ Cross-scheme compliance logic (Rule 1/2/3/4-style checks) — belongs to the scheme modules themselves, or a future Cross-Scheme Compliance capability.
- ✗ Identity, authentication, or authorization — owned by IAM (Core Platform). PSS/E Integration references actors only by `user_id`.
- ✗ Dashboard/reporting presentation — Dashboard reads this module's data read-only; it is never written to by Dashboard.

---

## 5. Owned Entities

| Entity | Description |
|---|---|
| `RawFileImportBatch` | The audit/traceability record of one import action — created on every upload, regardless of outcome. |
| `TopologyVersion` | An immutable network structure, identified by a deterministic topology signature. |
| `TopologyBus` | A structural bus definition within a `TopologyVersion` (bus number, name, base kV, PSS/E area/zone/owner, optional `substation_id` reference). |
| `TopologyBranch` | A structural transmission branch within a `TopologyVersion` (from/to bus, circuit id, impedance, thermal ratings). Contains no in-service/operational state — see below. |
| `TopologyTransformer` | A structural transformer within a `TopologyVersion` (from/to/tertiary bus, circuit id, winding/impedance/rating data). Contains no in-service/operational state. |
| `LoadSnapshot` | An immutable capture of load/generation state, tied to exactly one `TopologyVersion`. |
| `LoadSnapshotBusState` | Per-`LoadSnapshot` bus state: voltage magnitude/angle, PSS/E bus type (load/gen/swing/isolated), **and in-service status**. |
| `LoadSnapshotElementState` | Per-`LoadSnapshot` in-service status for a branch or transformer — captures momentary operational state (e.g. switched out for maintenance) separately from the branch/transformer's permanent structural definition. |
| `NetworkLoad` | Per-`LoadSnapshot` load record at a bus (P MW, Q MVAr). |
| `NetworkGenerator` | Per-`LoadSnapshot` generator record at a bus (P/Q generation and limits). |
| `psse_import_audit_log` | PSS/E Integration's own audit trail (CLAUDE.md A4), covering all entities above. |

**Design note (refinement over the legacy MVP):** in-service/operational status for branches, transformers, and buses is modeled as **per-`LoadSnapshot` state** (`LoadSnapshotElementState`, `LoadSnapshotBusState`), not as a field on the structural `TopologyBus`/`TopologyBranch`/`TopologyTransformer` records themselves. This is a deliberate correction: it guarantees, by construction, that momentary operational state (a breaker happening to be open at import time) can never affect the topology signature (ADR-003), rather than relying on signature-calculation logic to remember to exclude it. The legacy MVP's `EquipmentSnapshotState`/`SnapshotBusState` split already pointed toward this pattern; this design makes it structurally load-bearing rather than incidental. (Shunts, switched shunts, and DC links follow the same per-`LoadSnapshot` ownership pattern and are not separately detailed here — see §11.)

---

## 6. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| Substation | Master Data (Substation Registry) | `substation_id` (UUID) on `TopologyBus`, where a bus is matched to a known substation. Never duplicated — no substation name/voltage/region copied here. |
| (future) Equipment | Master Data (future Equipment Registry) | Not yet referenced — deferred until that module exists (see §17). |
| User | Core Platform (IAM) | `user_id` (UUID) on `RawFileImportBatch.imported_by_user_id` and on the actor of any Activation event; fallback `external_principal_id` + provider per [ADR-002](../adr/ADR-002-identity-and-access-management.md) during transitional federation scenarios. |

---

## 7. Domain Model

```
RawFileImportBatch ──── produces/reuses ───▶ TopologyVersion (0 or 1 new, or reuse existing)
RawFileImportBatch ──── produces ──────────▶ LoadSnapshot (0 or 1 new)

TopologyVersion (1) ──── (many) TopologyBus
TopologyVersion (1) ──── (many) TopologyBranch
TopologyVersion (1) ──── (many) TopologyTransformer
TopologyVersion (1) ──── (many) LoadSnapshot            [a topology may have many load captures over time]

LoadSnapshot (1) ──── (many) LoadSnapshotBusState        [one per bus in the parent topology]
LoadSnapshot (1) ──── (many) LoadSnapshotElementState    [one per branch/transformer in the parent topology]
LoadSnapshot (1) ──── (many) NetworkLoad
LoadSnapshot (1) ──── (many) NetworkGenerator

TopologyBus ──── references ───▶ Substation.substation_id   (Master Data, external, optional)
RawFileImportBatch ──── references ───▶ User.user_id        (Core Platform/IAM, external)
```

A `TopologyVersion` is the unit of structural identity (defined by its signature). A `LoadSnapshot` is always a child of exactly one `TopologyVersion` — bus/branch/transformer identity is only meaningful within the topology that defines it. `RawFileImportBatch` is not a parent of either in a data-ownership sense; it is the audit event that caused one or both to be created or reused.

---

## 8. Lifecycle / State Model

### 8.1 RawFileImportBatch Status Lifecycle

```
(upload) → Parsing → Completed | CompletedWithWarnings | Failed
```

Terminal states (`Completed`, `CompletedWithWarnings`, `Failed`) are immutable once reached — a batch record is never edited after parsing concludes; a corrected import is always a new batch.

### 8.2 TopologyVersion Status Lifecycle

```
Imported → Current → Superseded
```

A deliberately narrower lifecycle than the Canonical Version Lifecycle (CLAUDE.md A3) — see §9, rule 1, for why. Exactly one `TopologyVersion` may be `Current` at a time; all others are `Imported` (awaiting activation) or `Superseded` (previously Current, retained and immutable).

### 8.3 LoadSnapshot Status Lifecycle

```
Imported → Current → Superseded
```

Exactly one `LoadSnapshot` may be `Current` at a time, and its `topology_version_id` must equal the Current `TopologyVersion`'s id (§9, rule 3).

### 8.4 Workflow 1 — First RAW Import

No `TopologyVersion` exists yet. User uploads a full `.raw` file. Parsing separates structural and load sections. No existing signature to compare against, so a new `TopologyVersion` is created (status `Imported`), along with a new `LoadSnapshot` (status `Imported`) referencing it. The `RawFileImportBatch` records both as newly created. Nothing is `Current` until explicitly activated (§8.10).

### 8.5 Workflow 2 — RAW Import with Changed Topology

A `.raw` file is uploaded; its computed structural signature does not match the Current `TopologyVersion`. A new `TopologyVersion` (status `Imported`) is created, along with a new `LoadSnapshot` (status `Imported`) referencing it. The previous `TopologyVersion` remains `Current` until this new one is explicitly activated.

### 8.6 Workflow 3 — RAW Import with Unchanged Topology, New Load Snapshot

A full `.raw` file is uploaded; its computed signature **matches** the Current `TopologyVersion`. No new `TopologyVersion` is created — the batch reuses the existing one. A new `LoadSnapshot` (status `Imported`) is created against the reused `TopologyVersion`. This is the automatic resolution to the capability the legacy MVP lacked: a full RAW re-import behaves exactly like a load-only refresh whenever nothing structural actually changed, with no manual mode selection required.

### 8.7 Workflow 4 — Load-Only Refresh Using a Different RAW File

User uploads a lightweight load-profile file (or a full `.raw` file explicitly submitted for load-only processing) referencing the Current `TopologyVersion`. No signature comparison against structural data is needed for this path since no structural data is being asserted — the system validates that referenced buses exist in the Current `TopologyVersion` (§10) and creates a new `LoadSnapshot` (status `Imported`) against it. No `TopologyVersion` is created or modified.

### 8.8 Workflow 5 — Failed Import

The uploaded file fails to parse (malformed content, unsupported PSS/E version, unreadable format) or fails validation with zero matched buses. A `RawFileImportBatch` is created with status `Failed`, recording the specific error(s). No `TopologyVersion` or `LoadSnapshot` is created. A failed batch cannot be activated (§10) and has nothing to activate.

### 8.9 Workflow 6 — Import Preview Before Commit

Before committing to persistent records, a user may request a **preview**: the file is parsed and validated exactly as in a real import (signature computed, bus-matching checked, warnings collected), and a preview report is returned — reuse-or-new topology determination, matched/unmatched bus counts, coverage percentage — **without creating any persistent entity** (no `RawFileImportBatch`, `TopologyVersion`, or `LoadSnapshot` row). This keeps the audit trail free of abandoned or rejected import attempts. A subsequent explicit **commit** action re-runs validation against the same file (in case of a stale preview or a race with another import) and only then creates the real `RawFileImportBatch` and any resulting `TopologyVersion`/`LoadSnapshot`.

### 8.10 Workflow 7 — Current LoadSnapshot Activation

An authenticated, authorized user (CLAUDE.md A10) reviews a batch's outcome (warnings, coverage) and explicitly activates it. Activation is a single atomic operation:
- If the batch introduced a new `TopologyVersion`: both the new `TopologyVersion` and its `LoadSnapshot` transition `Imported → Current`, and the previously `Current` `TopologyVersion` and `LoadSnapshot` both transition `→ Superseded`.
- If the batch reused the existing `TopologyVersion` (Workflows 3 or 4): only the new `LoadSnapshot` transitions `Imported → Current`; the `TopologyVersion` remains `Current` (unchanged); the previously `Current` `LoadSnapshot` transitions `→ Superseded`.
- Both halves of any supersession are recorded as a single correlated audit event (§14).
- `promoted_at` is stamped on the record(s) becoming Current; `superseded_at` is stamped on the record(s) being superseded (§11) — enabling efficient point-in-time queries without replaying the audit log.

### 8.11 Workflow 8 — Historical LoadSnapshot Query

Any authorized reader may query a specific `Superseded` `LoadSnapshot` by id, or ask "what was Current as of timestamp T" (resolved via each record's `promoted_at`/`superseded_at` window, not by replaying audit history). This supports reproducing exactly what network state informed a scheme version's recommended MW at the time it was designed or approved (§9, §14), and supports Dashboard's historical reporting needs.

---

## 9. Business Rules

1. `TopologyVersion` and `LoadSnapshot` are **not** governed by the Canonical Version Lifecycle (CLAUDE.md A3). A3 governs approved engineering policy requiring human review and approval; topology/load data is imported or computed source data with no approval workflow of its own. Applying A3's states here would misrepresent raw data as approved engineering policy — directly contradicting rule 6 below.
2. A RAW or load-profile import always produces a `RawFileImportBatch` (except previews, §8.9); it never directly or silently mutates an existing `TopologyVersion` or `LoadSnapshot`.
3. Exactly one `TopologyVersion` may be `Current` at a time; exactly one `LoadSnapshot` may be `Current` at a time; the Current `LoadSnapshot`'s `topology_version_id` must equal the Current `TopologyVersion`'s id.
4. Topology reuse is determined solely by deterministic signature comparison over structural data (CLAUDE.md §5.5) — never by user assertion.
5. `TopologyVersion` and `LoadSnapshot` rows, and their child structural/state records, are immutable once created. A recalculation or re-import always produces new rows, never an in-place update.
6. **RAW file import is source data, not approved scheme data.** Nothing imported by this module is ever automatically treated as an approved UFLS/UVLS/EMLS engineering figure.
7. Import (parsing/validation) and Activation are separate steps; only an authenticated, authorized user can activate (§15).
8. Activating a new Current record automatically supersedes the previous Current record(s) of the same type, as a single atomic operation.
9. **Approved scheme MW values are not changed by new imports.** A scheme module may treat this module's Current `LoadSnapshot` data as a *recommendation* only while its own version is in Draft or Under Review (CLAUDE.md A3); at Approval, the value must be explicitly captured into the scheme module's own owned data.
10. An Approved scheme version **may** store a traceability pointer (`source_load_snapshot_id`) to the `LoadSnapshot` that informed a captured MW value, purely as descriptive metadata — never as a live dependency that continues to track the snapshot's status.
11. **Importing a new RAW file must never silently modify approved UFLS/UVLS/EMLS data.** This is a structural guarantee (no live FK from approved scheme data back to this module), not merely a policy statement — see [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md).
12. This module never auto-creates or auto-modifies Substation Registry records; unmatched buses are recorded as warnings on the `RawFileImportBatch` only.
13. This module never implements topology analysis (island detection, connectivity traversal) — that is Network Model's responsibility, consuming this module's data via its service interface or read-only reporting joins (CLAUDE.md A1).

---

## 10. Validation Rules

- Uploaded files must be a supported format: PSS/E `.raw` for topology(+load), or an approved lightweight load-profile format for load-only updates.
- Signature computation includes only structural connectivity and rating data (bus/branch/transformer definitions) — never load/generation values, and never in-service/operational state, which is modeled separately (§5). Parsed records are canonicalized (deterministically sorted, numeric values normalized) before hashing so incidental formatting differences don't produce spurious signature mismatches.
- A load-only import (Workflow 4) must validate that every referenced bus exists in the target `TopologyVersion`. Unmatched buses are recorded as warnings; a batch is blocked only if it has zero matched buses or another fatal parse error.
- A batch can only be activated if its status is `Completed` or `CompletedWithWarnings`. A `Failed` batch cannot be activated (§8.8).
- `TopologyVersion`, `LoadSnapshot`, and their child records cannot be deleted or edited once created (CLAUDE.md §11.6, §11.7).
- A preview (§8.9) re-validates at commit time rather than trusting a possibly-stale prior preview result.

---

## 11. Database Design (Concept)

Conceptual only — no migrations are defined here.

| Table (conceptual) | Key columns (conceptual) | Notes |
|---|---|---|
| `raw_file_import_batch` | `batch_id` (UUID PK), `source_file_reference`, `imported_by_user_id` (FK, IAM), `content_type` (topology_only \| load_only \| topology_and_load), `computed_signature`, `topology_version_id` (FK, nullable — set if produced or reused), `load_snapshot_id` (FK, nullable), `status`, `warnings` (structured list), `fatal_error` (nullable), `created_at` | Audit/traceability record; never mutated after reaching a terminal status. |
| `topology_version` | `topology_version_id` (UUID PK), `signature` (unique), `status`, `created_from_batch_id` (FK), `promoted_at` (nullable), `superseded_at` (nullable), `created_at` | Immutable once created. |
| `topology_bus` | `topology_bus_id` (BIGINT PK), `topology_version_id` (FK), `bus_number`, `bus_name`, `base_kv`, `substation_id` (FK, nullable, external to Master Data), `psse_area`, `psse_zone`, `psse_owner` | No in-service field — see §5 design note. |
| `topology_branch` | `topology_branch_id` (BIGINT PK), `topology_version_id` (FK), `from_bus_id` (FK), `to_bus_id` (FK), `ckt_id`, `r`, `x`, `b`, `rate_a/b/c` | Purely structural; no in-service field. |
| `topology_transformer` | `topology_transformer_id` (BIGINT PK), `topology_version_id` (FK), `from_bus_id`/`to_bus_id`/`tertiary_bus_id` (FK, tertiary nullable), `ckt_id`, winding/impedance/rating fields | Purely structural; no in-service field. |
| `load_snapshot` | `load_snapshot_id` (UUID PK), `topology_version_id` (FK), `created_from_batch_id` (FK), `status`, `promoted_at` (nullable), `superseded_at` (nullable), `created_at` | Immutable once created. |
| `load_snapshot_bus_state` | `id` (BIGINT PK), `load_snapshot_id` (FK), `topology_bus_id` (FK), `bus_type`, `voltage_mag`, `voltage_angle`, `in_service` | One row per bus per snapshot. |
| `load_snapshot_element_state` | `id` (BIGINT PK), `load_snapshot_id` (FK), `topology_branch_id` (FK, nullable), `topology_transformer_id` (FK, nullable), `in_service` | Exactly one of branch/transformer set per row. |
| `network_load` | `id` (BIGINT PK), `load_snapshot_id` (FK), `topology_bus_id` (FK), `load_id`, `p_mw`, `q_mvar` | |
| `network_generator` | `id` (BIGINT PK), `load_snapshot_id` (FK), `topology_bus_id` (FK), `gen_id`, `p_gen`, `q_gen`, `p_max/min`, `q_max/min` | |
| `psse_import_audit_log` | `log_id` (BIGINT PK), `entity_type`, `entity_id`, `event_type` (e.g. `created`, `activated`, `superseded`), `changed_at`, `changed_by_user_id`, `change_reason` | Owned per CLAUDE.md A4. |

**Cross-module constraints:** `topology_bus.substation_id` is `ON DELETE RESTRICT` into Substation Registry's `substation` table (read/reference only — this module never writes to it). All tables are written exclusively by PSS/E Integration's own service layer (CLAUDE.md A1, [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md)).

---

## 12. API Contract (Concept)

APIs are external/UI-facing contracts (CLAUDE.md §13, A9); this section describes conceptual resource shape only.

- `raw-file-import-batches` — list/retrieve past import batches (with status filter); a `preview` action (stateless, no persistence, §8.9) and a `commit` action (creates the real batch and any resulting `TopologyVersion`/`LoadSnapshot`, §8.9).
- `topology-versions` — list/retrieve; a `current` convenience lookup; retrieval of a specific historical version by id.
- `load-snapshots` — list/retrieve; a `current` convenience lookup; retrieval of a specific historical snapshot by id or "as of timestamp" (Workflow 8, §8.11).
- An `activate` action on a batch (or directly on its resulting topology/load records) implementing Workflow 7 (§8.10) — requires a reason and results in a correlated audit event.
- A read-only `recommended-mw` (or similar) query, exposed for scheme modules and Dashboard, resolving a substation/bus's load figure from the Current `LoadSnapshot` — this is the mechanism scheme modules use for Draft/Under-Review recommendations (§9, rule 9), never for Approved data.

**Contract requirements (CLAUDE.md A9):** pagination/filtering/sorting for list endpoints; structured error response shape (including preview/validation warnings as structured data, not free text); authentication and authorization requirements per endpoint; audit-relevant actions flagged (all commit and activate actions are audit-relevant).

**Data contracts:** standard three-layer separation (CLAUDE.md A6) — persistence models, domain models, and API DTOs are distinct; persistence models are never returned directly.

---

## 13. Service Interfaces

Per CLAUDE.md A1 (module communication via in-process service-layer interfaces):

**PSS/E Integration exposes, for other modules to consume:**
- A read-only "recommended MW" / load lookup interface, keyed by `substation_id`, resolved against the Current `LoadSnapshot` — consumed by UFLS/UVLS/EMLS during Draft/Under Review (never for Approved data, per §9 rule 9).
- A read-only "current topology/load snapshot" interface — consumed by Dashboard for visualization and by a future Network Model module for analysis.
- A read-only "historical load snapshot" interface (Workflow 8) — consumed by Audit and Analytics for reproducing the network state behind a past approved figure.
- A read-only substation-match coverage/health-check interface — consumed by Dashboard (mirroring the discovery report's `missing-substations` finding).

**PSS/E Integration consumes, from other modules' service layers — never their repositories directly:**
- From Master Data (Substation Registry): substation lookup/matching by mnemonic, used during import parsing (§ Business Rules, rule 12).
- From Core Platform (IAM): authorization checks for commit/activate actions; user lookups for audit attribution.

PSS/E Integration never calls another module's repository directly, and no other module writes to its tables, per CLAUDE.md A1 and [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md). Read-only cross-module joins are permitted only for reporting/dashboard purposes, never as a substitute for the service calls above.

---

## 14. Audit Requirements

Per CLAUDE.md §5.4 and A4, PSS/E Integration owns and writes its own audit log (`psse_import_audit_log`), covering every entity in §5.

- Every `RawFileImportBatch` commit is recorded: who, when, source file reference, outcome (topology reused/created, load snapshot created, warnings/errors).
- Every Activation (Workflow 7) is recorded as a single correlated audit event covering both halves of any supersession — the newly Current record(s) and the just-Superseded record(s) — mirroring the pattern in [ufls-module.md](ufls-module.md) §14.
- Audit history is append-only and never modified (CLAUDE.md A4, §16).
- When a scheme module captures an MW value informed by this module's data at Approval time, that module's own audit log should record the source `load_snapshot_id` (§9, rule 10) — a cross-module audit consideration this module enables but does not itself write (the capturing module owns that audit entry).
- Audit log access is itself access-controlled (CLAUDE.md A10).

---

## 15. Security Considerations

- All GridDefence engineering data, including topology and load data, is sensitive by default (CLAUDE.md A10); TLS required outside local development.
- **Preview** (§8.9) may reasonably be available to any authenticated engineering user, since it has no persistent effect.
- **Commit** (creating a real `RawFileImportBatch`/`TopologyVersion`/`LoadSnapshot`) requires an authenticated, named user with an "Importer" (or equivalent) role.
- **Activation** (promoting to Current) is recommended as a separate, elevated permission from Commit — mirroring the review-gate rationale already established for UFLS in [ufls-module.md](ufls-module.md) §15 — so that a batch's warnings/coverage can be reviewed by someone other than (or in addition to) the person who uploaded it before it becomes the operational reference. This resolves [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md)'s Open Question 3 with a concrete recommendation: separate Importer and Activator roles, not a single "Integration Engineer" role, given the operational reach of activation (it affects every scheme module's recommendations and Dashboard immediately).
- Read access (viewing current/historical topology and load data) is broader than write access, consistent with CLAUDE.md A10's "sensitive by default, gated by authentication" baseline.

---

## 16. Testing Requirements

Per CLAUDE.md §18 and A11, in priority order:

1. **Business rule tests** — signature-based reuse vs. new-topology-version logic; immutability of `TopologyVersion`/`LoadSnapshot` and their children; atomic activation (both halves of a supersession succeed or neither does); the structural guarantee that no live dependency exists from approved scheme data back to this module.
2. **Engineering calculation / validation tests** — canonicalization stability of signature computation (structurally identical files with incidental formatting differences must produce the same signature); bus-matching and coverage calculation; fatal-vs-warning classification.
3. **API contract tests** — preview-vs-commit behavior (preview must have zero persistent side effects); request/response schema conformance; authorization enforcement per endpoint (§12, §15).
4. **Database migration tests** — required once actual migrations are authored (out of scope for this document).
5. **UI behaviour tests** — required once a PSS/E Integration frontend exists; must confirm the UI only ever displays recommended MW as advisory during Draft/Under Review and never presents it as an approved figure (CLAUDE.md A12).

Business rules and validation logic must not be merged without accompanying tests (CLAUDE.md A11).

---

## 17. Future Extensions

- **Equipment Registry linkage** — once a future Equipment Registry exists, introduce a mapping entity correlating physical equipment (transformers/branches) to `TopologyBranch`/`TopologyTransformer` records, mirroring the legacy MVP's `EquipmentTopologyMap` pattern (deferred per [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md)).
- **Network Model integration** — a future Network Model module will consume `TopologyVersion` data (via this module's service interface) to implement connectivity-graph analysis and island/"pocket" detection, without this module ever owning that analysis itself.
- **Historical-topology load-only imports** — currently load-only refresh targets the Current `TopologyVersion` only; supporting imports against a historical topology for what-if/backtesting analysis is deferred (ADR-003 Open Question 1).
- **Additional structural element types** — shunts, switched shunts, DC links follow the same per-`LoadSnapshot` state pattern (§5) and can be added without changing this module's core architecture.
- **Alternative network model sources** — CIM/SCADA/EMS integration (CLAUDE.md §27) would extend this module's import capability beyond PSS/E `.raw` files, using the same `TopologyVersion`/`LoadSnapshot` separation.
- **Retention/archival policy** — deferred until real historical data volume is observed (CLAUDE.md A15's pattern; ADR-003 Open Question 5).

---

## 18. Risks and Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| Signature instability from incidental file-format differences | False "new topology" detection, unnecessary `TopologyVersion` churn | Canonicalize parsed structural records before hashing, not raw file bytes (already adopted in §10) |
| Large `.raw` file parsing performed synchronously in-request | Directly echoes the Codebase Discovery Report's finding that the legacy MVP ran heavy computation synchronously in-request; at national-grid scale this risks slow/blocked requests | Run import parsing and validation as an async job (Redis+RQ, already in CLAUDE.md's stack) rather than a blocking HTTP request; preview and commit should both be designed as async-friendly from the start |
| Activation gate skipped or rushed under operational time pressure | Poor-quality data (low substation match coverage) becomes the operational reference for every scheme module's recommendations | Treat as a policy/process control (§15's Importer/Activator role separation), not a technical bypass |
| A recommendation shown to a scheme designer becomes stale if the Current `LoadSnapshot` is superseded before Approval | Designer confusion about which network state a displayed MW reflects | Always surface which `load_snapshot_id` a recommendation came from, and flag if it has since been superseded; approval still captures a value regardless, so correctness is unaffected, only clarity |
| Ad hoc cross-module reads of this module's data by Dashboard/scheme modules beyond the reporting-only exception | Erodes module boundary enforcement (ADR-001), complicates future service extraction | Route any read that informs a business decision through this module's service interface (§13); reserve raw joins strictly for reporting/dashboards |
| Unbounded historical growth of `TopologyVersion`/`LoadSnapshot` and their child rows | Long-term storage/performance concern | Defer a retention/archival policy until real volume is observed (§17), consistent with CLAUDE.md §21 (avoid premature optimisation) |

---

## Recommended Next Architecture Document

**Network Model module.**

This document deliberately excludes topology *analysis* from PSS/E Integration's scope (§4) — connectivity-graph traversal and island/"pocket" detection are real, proven, already-used capabilities (per the Codebase Discovery Report) that now have no owning module. Network Model is the direct consumer of the `TopologyVersion` data this module owns, and it is the dependency UFLS/UVLS/EMLS need before their own pocket/island-based assignment design can be completed.

**UFLS module refinement** is the logical step immediately after Network Model, not before it — it needs both this document's recommended-MW service interface (already defined, §13) and Network Model's island-detection primitives (not yet defined) to fully resolve [ufls-module.md](ufls-module.md) §7.4/§7.5 against real-world assignment patterns.

**Equipment Registry** and **Cross-Scheme Compliance** remain important but are not blocked by, or blocking, this document, for the same reasons given in [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md)'s equivalent recommendation — sequencing them after Network Model does not add risk, and Cross-Scheme Compliance in particular should still be treated as the single highest-severity *open* architectural question from the discovery report, to be picked up once Network Model is in place.
