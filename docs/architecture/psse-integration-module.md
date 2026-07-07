# PSS/E Integration Module Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document follows the Canonical Module Architecture Document Template (CLAUDE.md **A8**).

Related documents: [system-overview.md](system-overview.md), [domain-model.md](domain-model.md), [substation-registry.md](substation-registry.md), [equipment-registry-module.md](equipment-registry-module.md) (Phase 3, complete — owns the `Circuit`/`CircuitTerminal`/`Transformer`/`TransformerTerminal` identities this document's `EquipmentTopologyMap` correlates against), [ufls-module.md](ufls-module.md), [ADR-000](../adr/ADR-000-architecture-principles.md), [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md), [ADR-002](../adr/ADR-002-identity-and-access-management.md), [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md) (the architectural decision this document formalizes), [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md) (confirms this module owns electrical topology, Equipment Registry owns identity/metadata, and names `EquipmentTopologyMap` as the correlation between them), [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md) (specifies `EquipmentTopologyMap`'s target as `CircuitTerminal`, not generic `Equipment`), [ADR-010](../adr/ADR-010-engineering-decision-support-philosophy.md) (names, as a general rule, the decision-support/no-approval-workflow philosophy this module's Preview → Commit → Activate design already followed).

**Reconciliation note (post-Phase-3):** this document was originally written before Equipment Registry's Phase 3 implementation, and some of it still described Equipment Registry as future/unbuilt and its own equipment-correlation mechanism as an unspecified, indefinitely-deferred idea. Equipment Registry is now complete, with a materially different shape than originally anticipated (`Circuit`/`CircuitTerminal`/`Transformer`/`TransformerTerminal`/`SubstationVoltageYard` — no generic `Equipment` backbone, no `IncomingBranchDetail`; see [equipment-registry-module.md](equipment-registry-module.md)'s Appendix for the full supersession history). This revision brings this document into alignment: it formalizes **EquipmentTopologyMap** (§8a) as specified by ADR-006/ADR-007, and corrects every reference below that still described Equipment Registry as not yet existing. No part of ADR-003's topology/load separation, the Imported→Current→Superseded lifecycle, or the preview/commit/activate workflow changes as a result — those remain exactly as originally designed.

**Post-Phase-4 note (implementation-validated, Phase 4.1):** Phase 4 has been implemented, independently architecture-validated, and stabilized (one topology-signature exclusion defect and one commit-performance issue found and fixed; see `docs/releases/PHASE_04_COMPLETION_REPORT.md` for the full historical record). Every workflow, business rule, and lifecycle description in this document reflects the as-built, as-validated system, not merely the original design intent. The three sections immediately below consolidate the engineering philosophy that emerged from that implementation experience, so a reader arriving fresh (or a future module's designer facing the same questions) does not have to reconstruct it from the CHANGELOG or the architecture validation report.

---

## Engineering Philosophy: Decision Support, Not Approval Management

**GridDefence, and this module specifically, exists to support engineering decisions — not to manage a business approval workflow.** This is now a ratified, general architectural principle ([ADR-010](../adr/ADR-010-engineering-decision-support-philosophy.md)); this section restates what it means concretely for PSS/E Integration, since this module's Preview → Commit → Activate design is ADR-010's own reference example.

- **Automated validation, comparison, and correlation exist to build engineering confidence, not to gate a queue of sign-offs.** Parse validation, topology-signature comparison (reuse-vs-new), and `EquipmentTopologyMap` correlation (§8a) all run automatically, before a human ever needs to look at the result — their job is to hand the activating engineer evidence, not to block progress pending a separate reviewer's approval.
- **Activation is the engineering decision.** There is no additional "approve this import" step layered on top of Activation (§8.10) — Activation *is* the decision point, made by one authenticated, authorized engineer, informed by everything validation and correlation surfaced beforehand. Reviewing a batch's warnings, or a `TopologyVersion`'s unresolved `EquipmentTopologyMap` discrepancies, before deciding whether to activate is the engineer exercising judgement directly — it is not a separate workflow stage with its own actor.
- **This is deliberately lighter than the Canonical Version Lifecycle (CLAUDE.md A3), and that is correct, not incomplete.** `TopologyVersion`/`LoadSnapshot` are Engineering Source Data (ADR-010's classification), not Approved Engineering Policy — imported network data does not itself govern equipment the way an Active UFLS scheme version does. A3's Draft → Under Review → Approved → Active → Superseded → Archived machinery is the right lifecycle for a scheme version; it would be the wrong lifecycle here, misrepresenting imported data as something requiring organisational sign-off it was never meant to carry.
- **Nothing about this changes what UFLS/UVLS/EMLS themselves require.** When a scheme module captures a recommended MW value or pocket assignment informed by this module's Current data, *that capture* becomes the scheme module's own Approved Engineering Policy, and *that* still goes through the full A3 lifecycle, unaffected by anything above. This module's job ends at supplying validated, traceable, activatable source data — the scheme module's own approval process picks up from there, on its own terms.

## Network Evolution Model

The physical transmission network changes over years — lines are commissioned, substations are renumbered, load grows and shifts by the hour. This section makes explicit how GridDefence's data model tracks both kinds of change without conflating them, consolidating what ADR-003 and §7/§8 above already establish, for a reader who wants the consolidated picture without tracing every workflow individually.

```
RawFileImportBatch          (the audit event — "an import happened")
        │
        ├── produces or reuses ──▶ TopologyVersion
        │                              (immutable structural snapshot,
        │                               identified by its signature)
        │
        └── produces ──────────────▶ LoadSnapshot
                                       (immutable load/generation snapshot,
                                        always a child of exactly one
                                        TopologyVersion)
```

- **`RawFileImportBatch`** is not a parent of either entity in a data-ownership sense — it is the permanent audit record of the import *action* that caused a `TopologyVersion` and/or `LoadSnapshot` to be created or reused. It never itself becomes Current.
- **`TopologyVersion`** is the unit of structural identity. Its signature is computed from structural data only (§10; see the Phase 4.1 stabilization note there) — two imports of an unchanged network produce the same signature and therefore the same `TopologyVersion`, regardless of how much time passed between them or how many times load was refreshed in between.
- **`LoadSnapshot`** is always a child of exactly one `TopologyVersion` — a load figure is only meaningful within the topology whose bus numbering and connectivity it was captured against. A single `TopologyVersion` accumulates many `LoadSnapshot`s over its lifetime, one per load refresh, for as long as the physical network it represents remains unchanged:

```
TopologyVersion A (signature S, e.g. commissioned network as of March)
   ├── LoadSnapshot 08:00
   ├── LoadSnapshot 08:30
   ├── LoadSnapshot 09:00
   └── LoadSnapshot 09:30   ← Current (most recently activated)
```

- **Current vs. Historical is a per-type, single-pointer distinction, not a separate table.** Exactly one `TopologyVersion` is `Current` at a time (the reference for new load-only imports and for any consumer asking "what does the network look like right now"); exactly one `LoadSnapshot` is `Current` at a time, and it must belong to the Current `TopologyVersion` (§9 rule 3). Every other row of either type is `Superseded` — not deleted, not archived out of reach, permanently queryable by id or by "what was Current as of timestamp T" (§8.11).
- **When the topology itself changes** (a new line commissioned, a bus renumbered), the next import's computed signature no longer matches the Current `TopologyVersion`, so a *new* `TopologyVersion` (with its own first `LoadSnapshot`) is created — the old `TopologyVersion` and every `LoadSnapshot` that was ever captured against it remain permanently in place, immutable, retrievable exactly as they were. Activating the new pair supersedes both the old `TopologyVersion` and its own last-Current `LoadSnapshot` in one atomic step (§8.10) — GridDefence does not lose, overwrite, or silently reinterpret the network's prior state; it accumulates a permanent, queryable history of how the network actually evolved.
- **Why topology and load are separated at all, restated plainly:** they change at fundamentally different rates for fundamentally different reasons. Refreshing load data every 30 minutes must never force the system to re-establish (or worse, silently duplicate) structural network data that hasn't changed in months. Conversely, a genuine structural change must never be hidden inside what looks like an ordinary load refresh. Keeping them as two independently-lifecycled entities, joined only by `LoadSnapshot.topology_version_id`, is what makes both guarantees hold simultaneously (ADR-003).

## PSS/E Import Engineering Workflow

The full engineering workflow, end to end, restated as a single sequence for a reader who wants the whole picture in one place (§8.4-§8.11 specify each step's exact persistence/lifecycle behaviour; this section is the narrative, not a new decision):

```
RAW Upload
    ↓
Automatic Validation        (parsing, structural checks, bus-matching coverage)
    ↓
Topology Comparison         (signature computed; reuse existing TopologyVersion,
    ↓                        or detect a structural change and prepare a new one)
Equipment Correlation       (EquipmentTopologyMap matching against Equipment
    ↓                        Registry's CircuitTerminal identities, §8a — automatic,
    ↓                        runs whenever a new TopologyVersion is produced)
Engineering Review          (the importing/activating engineer examines warnings,
    ↓                        coverage, and any unmatched/discrepancy correlation
    ↓                        entries — informational evidence, not a gate)
Activation                  (the engineering decision — promotes to Current,
                             atomically supersedes the prior Current, audited)
```

**"RAW Upload"** and **"Automatic Validation"** together correspond to this document's own Preview (§8.9, zero persistence) followed by Commit (§8.4-§8.8, persists but never activates) — an engineer may preview repeatedly before ever committing, and every commit re-validates rather than trusting a stale preview. **"Topology Comparison"** is the signature lookup described above. **"Equipment Correlation"** is `EquipmentTopologyMap` matching (§8a) — it runs automatically as part of a new-topology commit, not as a separate user-triggered step. **"Engineering Review"** has no dedicated persistence state of its own — it is what an engineer does, using the Batch Detail and `EquipmentTopologyMap` review screens, in the time between Commit and Activation; it is **informational only**, exactly as ADR-010 requires — nothing about reviewing warnings or discrepancies blocks or gates Activation at a technical level (a batch with only warnings, per §10, may be activated at the importer's discretion). **"Activation"** is the one mandatory, explicit, privileged, audited decision point (§8.10, §15) — restated here for emphasis: **no separate management-approval stage exists, or should ever be added, between Engineering Review and Activation** (ADR-010).

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
- ✓ `EquipmentTopologyMap` — correlating Equipment Registry's registered `CircuitTerminal` identities to the imported PSS/E topology elements they physically correspond to, per `TopologyVersion` (§8a; ADR-006, ADR-007)

---

## 4. Non-Responsibilities

PSS/E Integration does **not** own:

- ✗ Substation identity or metadata — owned by the Substation Registry (Master Data). PSS/E Integration references substations only by `substation_id`.
- ✗ Physical equipment identity, naming, bay numbers, and breaker numbers — owned by **Equipment Registry** (Master Data, Phase 3, complete: `Circuit`/`CircuitTerminal`/`Transformer`/`TransformerTerminal`/`SubstationVoltageYard`; see [equipment-registry-module.md](equipment-registry-module.md)). PSS/E Integration never duplicates this identity and never writes to Equipment Registry's tables — it only *correlates* against them, via `EquipmentTopologyMap` (§8a), which holds a read-only reference to a `CircuitTerminal`-backed `equipment_id`. `TopologyBranch`/`TopologyTransformer` themselves remain self-contained PSS/E representations, exactly as before — the correlation lives in `EquipmentTopologyMap`, not as a column on either side.
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
| `EquipmentTopologyMap` | Correlates one `CircuitTerminal`-backed `equipment_id` (Equipment Registry) to the `TopologyBranch`/`TopologyTransformer` element(s) it resolves to within one `TopologyVersion`, plus its match outcome (clean-match / unmatched / discrepancy). Full specification: §8a. |
| `psse_import_audit_log` | PSS/E Integration's own audit trail (CLAUDE.md A4), covering all entities above. |

**Design note (refinement over the legacy MVP):** in-service/operational status for branches, transformers, and buses is modeled as **per-`LoadSnapshot` state** (`LoadSnapshotElementState`, `LoadSnapshotBusState`), not as a field on the structural `TopologyBus`/`TopologyBranch`/`TopologyTransformer` records themselves. This is a deliberate correction: it guarantees, by construction, that momentary operational state (a breaker happening to be open at import time) can never affect the topology signature (ADR-003), rather than relying on signature-calculation logic to remember to exclude it. The legacy MVP's `EquipmentSnapshotState`/`SnapshotBusState` split already pointed toward this pattern; this design makes it structurally load-bearing rather than incidental. (Shunts, switched shunts, and DC links follow the same per-`LoadSnapshot` ownership pattern and are not separately detailed here — see §11.)

---

## 6. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| Substation | Master Data (Substation Registry) | `substation_id` (UUID) on `TopologyBus`, where a bus is matched to a known substation. Never duplicated — no substation name/voltage/region copied here. |
| `CircuitTerminal` (and, via it, `Circuit`) | Master Data (Equipment Registry, Phase 3) | `equipment_id` (UUID) on `EquipmentTopologyMap`, read-only (§8a). Never duplicated — no bay number, breaker number, or circuit name copied here; PSS/E Integration never writes to Equipment Registry's tables. |
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

TopologyVersion (1) ──── (many) EquipmentTopologyMap    [one entry per matched/unmatched/discrepant CircuitTerminal]

TopologyBus ──── references ───▶ Substation.substation_id           (Master Data, external, optional)
EquipmentTopologyMap ──── references ───▶ CircuitTerminal.equipment_id   (Master Data/Equipment Registry, external, read-only)
EquipmentTopologyMap ──── references ───▶ TopologyBranch.id | TopologyTransformer.id   (this module, internal, nullable — unset when unmatched)
RawFileImportBatch ──── references ───▶ User.user_id        (Core Platform/IAM, external)
```

A `TopologyVersion` is the unit of structural identity (defined by its signature). A `LoadSnapshot` is always a child of exactly one `TopologyVersion` — bus/branch/transformer identity is only meaningful within the topology that defines it. `RawFileImportBatch` is not a parent of either in a data-ownership sense; it is the audit event that caused one or both to be created or reused. `EquipmentTopologyMap` is scoped per `TopologyVersion`, not per `RawFileImportBatch` — matching is (re)computed against the topology, not the import event, since a given `TopologyVersion` may be the target of several `EquipmentTopologyMap` recomputations over time as Equipment Registry itself changes (§8a).

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

### 8.9a Preview Execution Model (Phase 5B Refinement)

**Preview executes synchronously, in-request. Commit remains asynchronous, unchanged.** This corrects the original design, which enqueued both as RQ jobs by blanket policy (§18's original risk table entry, still shown below for history) before either had been built or measured.

**Measured evidence** (Phase 4.1 stabilization report, against the real 1,520-bus/2,197-branch/560-transformer/1,971-load sample file): parsing takes ~131–158ms and signature computation ~3.3ms — Preview's entire workload, since it is zero-persistence (§8.9) and issues only read-only bus-matching lookups beyond that. Commit's own persistence path, by contrast, measured 1,047ms after the Phase 4.1 batching fix (2,120ms before it) — 7–10× more expensive than Preview even after optimization, and its cost scales with row count in a way Preview's does not.

**Why the original policy no longer fits Preview specifically:** the original §18 entry reasoned by analogy to the legacy MVP's known defect (synchronous heavy computation blocking requests) before this module's own parser existed to benchmark. That precaution was reasonable at the time; it is no longer supported by Preview's own measured cost, which sits well within normal interactive request latency. Commit's profile matches the original concern exactly — large, growing, write-heavy — and keeps its async treatment unchanged.

**Consequences:**
- Preview no longer depends on Redis or a running RQ worker at all — `POST /imports/preview` calls `PsseIntegrationService.preview()` directly through the request-scoped database session and returns `200 OK` with the `PreviewResult` body immediately, never a `202 Accepted` + job id to poll.
- Commit's own execution mechanism (Redis+RQ, or in-process) became independently configurable in Phase 6 — see §8.9c.
- No engineering behaviour changed: parsing, signature computation, bus-matching, and validation logic are identical to before this refinement — only how the HTTP layer invokes and returns them changed.

### 8.9b Preview Engineering Presentation (Phase 6 Refinement)

**The Preview page is organized around four engineering questions, not around `PreviewResult`'s own field order:** what operational snapshot was uploaded, does GridDefence understand it, is anything wrong, and is it ready to import. This corrects a UAT finding that the page, while technically correct, read as parser output rather than an engineering summary.

**No engineering behaviour changed.** Parsing, signature computation, bus-matching, and validation logic (§8.9, §8.9a) are unchanged. This refinement is presentation plus a small set of additive `PreviewResult` fields exposing data the parser already produces.

**New `PreviewResult` fields** — `raw_version`, `bus_count`, `branch_count`, `transformer_count`, `load_count`, `generator_count` — read directly off the already-parsed RAW case (`ParsedCase.rev`/`.buses`/`.branches`/`.transformers`/`.loads`/`.generators`). No new parsing, no new database query, no new engineering calculation; these were always computed in memory during Preview and simply were not previously returned. `raw_version` is nullable — a load-only file's header is frequently absent (§8.7), matching the existing best-effort nullability already established for `rev`/`sbase` in `raw_parser.py`.

**The five presentation sections, and what each answers:**

1. **Snapshot Summary** ("what did I upload") — Snapshot Type (plain-language, never the raw `FULL_TOPOLOGY_WITH_LOAD`/`LOAD_ONLY` enum value), PSS/E RAW Version, Network Size (the five new counts above), and Network Topology Status.
2. **Registry Matching** ("does GridDefence understand it") — the existing matched/unmatched/coverage figures, relabeled by import type: a full-topology snapshot's figures describe **substation** matching; a load-only snapshot's figures describe **load-bus-against-Current-topology** matching — these are genuinely different engineering checks (§8.6 vs §8.7) and were previously shown under identical labels. **Bay-level matching is deliberately never shown here** — Equipment Correlation (`EquipmentTopologyMap`, §8a) runs at Commit, not Preview; this section only ever reflects what Preview itself checked.
3. **Engineering Findings** — replaces the flat "Warnings" list, split into "Requires Attention" and "Informational." The split is inferred by the frontend from existing message text (no backend severity field exists yet — see Risks below), and an explicit "No engineering findings detected" is shown rather than an empty section.
4. **Import Readiness** — a one-line, plain-language recommendation derived from the same data already shown above (findings present, or unmatched buses present, or neither). This is presentation only: it never blocks, disables, or auto-triggers Commit, and introduces no new engineering decision (CLAUDE.md A12, ADR-010).
5. **Advanced Information** (collapsed) — the structural signature, and the natural home for any future parser/processing metadata. Nothing engineering-decision-relevant lives here.

**Consequence for a Load-Only preview with no Current `TopologyVersion` yet:** rather than showing a `0%` coverage figure (which reads as a data-quality problem), the page states plainly that no current network topology exists yet to validate against — the same underlying condition (`unmatched_bus_count == load_count`, warning text unchanged), presented as what it actually is.

**Risk carried forward, not resolved here:** "Requires Attention" vs. "Informational" classification is a frontend pattern match against existing warning message text, not a backend-tagged severity. This is transparent and reversible, but a future addition of a genuine severity field to `service.preview()`'s warning collection (and `PreviewResult`) would be more robust than string matching — noted here for a future, small, non-urgent enhancement; not implemented as part of this presentation-only refinement.

### 8.9c Commit Execution Engine (Phase 6 Refinement)

**Commit's execution mechanism is configurable, via `app.core.execution`'s Execution Engine abstraction — an engineer-facing behaviour is never coupled to a specific infrastructure choice.** This corrects a UAT finding: Commit could not run at all when Redis was unavailable, even though nothing about Commit's own engineering meaning (import operational context, validate, correlate equipment, update Current Topology) requires Redis specifically — only *some form* of execution does, and this project's own primary deployment target (a small engineering team, typically fewer than 10 concurrent users, often developing on company-managed Windows machines where installing Redis may not always be possible) does not need a separate queue and worker process to get that.

**No engineering behaviour changed.** `PsseIntegrationService.commit()` and `jobs.run_commit_job` (the thin adapter that opens a session and calls it) are byte-for-byte unchanged. This refinement only changes how `run_commit_job` is invoked and how its completion is reported back — never *what* it does.

**Two execution modes, selected by `Settings.execution_mode`:**

1. **"direct"** (default) — `run_commit_job` executes immediately, synchronously, in the request's own worker thread. No Redis, no RQ, no separate worker process. `POST /imports/commit` returns `200 OK` with the completed batch result directly, exactly mirroring Preview's own response shape (§8.9a).
2. **"queue"** — `run_commit_job` is enqueued via Redis+RQ (`app.core.queue`), unchanged from the original Phase 4 design. `POST /imports/commit` returns `202 Accepted` + a job id, polled via `GET /imports/jobs/{job_id}`, exactly as before this refactor.

**The PSS/E Integration module itself never imports `redis`, `rq`, or `app.core.queue`.** Its router depends only on `app.core.execution.ExecutionEngine` (`submit`/`fetch`, returning a uniform `ExecutionResult`) — those infrastructure dependencies are confined entirely to `app.core.execution` and `app.core.queue`. This is a direct instance of CLAUDE.md A1's module-communication discipline applied to *infrastructure* dependency, not just cross-module business-data dependency: a business module depends on an abstraction, never on the concrete mechanism behind it.

**Error handling, per mode:**
- Direct mode never raises a queue-unavailable error — it has no external dependency to fail. A business validation failure (e.g. a load-only file with no Current `TopologyVersion`) is translated to a structured `400`, identical in shape to how Preview's own validation failures are reported (§8.9a).
- Queue mode: if Redis is unreachable when Commit is submitted, `QueueExecutionEngine.submit` raises `ExecutionUnavailableError`, and the router responds `503 Service Unavailable` (`code: "queue_unavailable"`) — unchanged from the Phase 5B behaviour this replaces internally.

**Frontend consequence:** the frontend does not choose, or need to know, which mode is active. `POST /imports/commit`'s response is a discriminated union (`CommitSubmission` — a completed batch result, or a job id) and the Preview/Commit page reacts to whichever shape it receives: Direct mode's already-complete result renders immediately, with no polling; Queue mode's job id is polled exactly as before. This mirrors the same "engineering behaviour identical, execution mechanism invisible to the consumer" principle the backend abstraction itself embodies.

**Deployment recommendations:**
- **Local development, UAT, and small deployments** (this project's primary target): use `EXECUTION_MODE=direct` (the default) — no Redis, no RQ worker process, no `docker compose --profile queue` needed. A developer with only Python, PostgreSQL, and Node.js installed can run the complete Preview → Commit → Activate workflow.
- **Larger deployments** that want genuine background execution (e.g. many engineers importing concurrently, or wanting to submit a large Commit and navigate away before it finishes) may set `EXECUTION_MODE=queue` and run the `redis`/`worker` Compose services (`docker compose --profile queue up`, or equivalent outside Compose). Queue mode remains fully supported and unchanged in behaviour.
- Both modes are expected to coexist across this project's lifetime — Direct mode is not a stepping stone to be removed once Queue mode "works"; it is the intended default for this project's actual scale.

### 8.9d Import Result Engineering Presentation (Phase 6.1 Refinement)

**The Import Result page (a batch's own detail view) is organized around the same kind of engineering questions as Preview's own presentation refinement (§8.9b), applied to Commit's outcome:** did the import succeed, is the imported operational context usable, what needs engineering attention, and can the engineer confidently continue with scheme review. This corrects a UAT finding that the page, while technically correct, read as a raw batch record rather than an engineering result.

**No engineering behaviour changed.** `PsseIntegrationService.commit()`'s parsing, validation, topology/load persistence, and Equipment Correlation triggering are unchanged. This refinement is presentation plus a small set of additive fields.

**Warning aggregation, not a new engineering fact.** `RawFileImportBatch.warnings` already records one entry per individual occurrence — for a large, poorly-matched file this can mean hundreds or thousands of entries (one per unmatched bus, branch, or transformer). Rendering that flat is a real UX defect, not a hypothetical one. Each warning entry is now tagged with a `category` at the point it is *constructed* (where its meaning is already unambiguous — e.g. `"unmatched_bus"`, `"unmatched_branch_reference"`, `"unmatched_load_bus"`), except for the two shapes `raw_parser.py` itself produces as undifferentiated strings (an unrecognized-section notice, or a skipped/unparseable data line), which are recognized by their own fixed, already-documented message text. `BatchSummary.finding_groups` (new) groups these by category into a count and a plain-language summary sentence (e.g. *"1087 buses could not be matched to the current Substation Registry."*), computed at read time from data already persisted — no new parsing, query shape, or engineering calculation. The full, ungrouped `warnings` list remains stored and returned unchanged, preserving complete audit traceability (CLAUDE.md §5.4); the aggregation is presentation-only.

**Three presentation groups**, matching Preview's own precedent: `engineering_review_required` (an unmatched bus/branch/transformer/load, or a skipped data line — something an engineer should know about), `parser_notices` (an unrecognized RAW section — tolerated, summarized, never shown as an individual per-section warning), and `informational` (reserved for future non-actionable notices; nothing currently populates it).

**Registry Matching counts** (`matched_count`/`unmatched_count`/`coverage_percent`, new, additive) are computed only for a single batch's own detail view (`get_batch_summary`), never for the list view (`list_batch_summaries`) — reusing the same repository methods (`list_topology_buses`, `list_network_loads`) `counts_for_topology_version`/`counts_for_load_snapshot` already call elsewhere, so no new query shape is introduced, and the list view avoids an extra query per row (CLAUDE.md §21). A full-topology batch's counts describe substation matching; a load-only batch's describe load-to-current-topology matching — the same distinction §8.9b already draws for Preview. When no matching data exists at all, the page states that plainly rather than showing a `0%` that would read as a data-quality problem.

**Import Health** — a five-step trail (Parsing, Operational Context, Current Topology, Engineering Review, Activation) — reflects the batch's *actual* current state, not merely what Commit itself established. Commit never activates (§8.10); a fresh batch's Current Topology is always "Pending Activation" until an actual, later Activation occurs. To report this correctly for both a freshly-committed batch and a historical one viewed later, the frontend additionally reads the batch's own `LoadSnapshot`'s `status` (via the already-existing `GET /load-snapshots/{id}` endpoint) — every successful commit, of either import type, creates its own new `LoadSnapshot`, so its status is the authoritative per-batch signal for whether *this* batch's result was ever promoted to Current. This is a frontend composition of two already-existing endpoints, not a new backend query.

### 8.9e Operational Context Inspector (Phase 6.2)

**The Inspector is a structured, Excel-like view of exactly what the PSS/E parser produced during Preview — an inspection tool, not an engineering analysis tool.** Where the Preview Summary (§8.9b) answers four engineering questions in prose ("what did I upload," "does GridDefence understand it," "is anything wrong," "is it ready to import"), the Inspector answers a narrower, different question: "let me look at the actual imported records myself, row by row, before I decide." It never infers engineering meaning, never validates, never recommends, and never transforms the imported data — it presents the parser's own output, unchanged, in a form an engineer can page through, sort, and search.

**The Inspector does not replace the Preview Summary; the two are complementary, not competing.** The Preview Summary remains the primary engineering decision-support page an engineer reads first. The Inspector is an optional, deeper look an engineer reaches for when the summary alone is not enough to confirm "this is the right file" — e.g. verifying a specific bus's name and voltage class, or checking whether a particular load bus is actually present in the file at all.

**No new parsing, no new backend query, no new persistence.** `PreviewResultData` (and its schema, `PreviewResult`) is extended with the same `ParsedCase` lists (`buses`, `branches`, `transformers`, `loads`, `generators`) Preview already builds in memory, plus `source_file_reference` and `base_mva` (`ParsedCase.sbase`) — additive fields only, read off data that already exists at the point Preview computes its result. `router.py`'s existing `PreviewResult.model_validate(result)` call required zero changes; Pydantic's `from_attributes=True` picks up the new fields automatically once both the service and schema layers declare them, confirmed by a passing API-level test (`test_preview_response_includes_parsed_records_for_inspector`).

**Payload-size trade-off, documented per this phase's own "document and justify" requirement.** Returning full parsed records on every Preview call increases the response payload meaningfully — for this project's own benchmark full-topology file (~1,500 buses, ~2,200 branches, ~560 transformers, ~2,000 loads), a rough estimate is 1-2MB of additional JSON, whether or not an engineer ever opens the Inspector. This was deliberately accepted over two alternatives:
- **A server-side cache keyed by a Preview id, with a separate fetch-for-inspection endpoint** — rejected because it reintroduces server-side state into a workflow whose entire design (§8.9) is zero-persistence; cache expiry and key management would add real complexity disproportionate to the problem, and no evidence yet exists that payload size is an actual problem at this project's scale (CLAUDE.md §21 — avoid premature optimisation, prefer measured evidence).
- **Re-parsing the RAW file a second time when the Inspector is opened** — rejected outright: it duplicates parsing logic and risks the Inspector's view drifting from what Preview itself showed, which this phase's constraints explicitly forbid.

If a future measurement shows this payload size is a genuine problem (e.g. a much larger file, or a slow-network deployment), the correct fix is narrower than reintroducing server state: e.g. an explicit `include_records` query flag on `/imports/preview` defaulting to `true` today, or paginating the parsed-record lists server-side. Neither is implemented now, since no evidence yet justifies the added complexity.

**Data flow: no second network request.** The already-fetched `PreviewResult` (held in `PsseImportUploadPage`'s own component state after a successful Preview) is passed directly to the Inspector page via React Router's navigation state (`navigate(path, { state: { previewResult } })` / `useLocation().state`) — the simplest mechanism available, requiring no new global-state library, no query-cache manipulation, and no new persistence. Because Preview data is never persisted or addressable by id (§8.9), a direct visit to the Inspector's route (e.g. a bookmarked link, or a page refresh) has nothing to show; the page states this plainly, with a link back to Preview, rather than guessing or attempting to re-fetch.

**Reusable components, not a one-off page.** Two new components — `frontend/src/components/ui/DataTable.tsx` and `frontend/src/components/ui/DataInspector.tsx` — carry no PSS/E-specific knowledge:
- `DataTable<T>` is a generic, fully client-side sortable/searchable/paginated table, built from `@tanstack/react-table`'s already-installed `getSortedRowModel`/`getFilteredRowModel`/`getPaginationRowModel` helpers (previously unused in this project — every other list page paginates/sorts server-side via `getCoreRowModel()` alone, because its data is never fully loaded at once). Client-side operation is justified here specifically because the Inspector's entire dataset is already in memory by design — a further backend query is neither possible nor wanted, unlike every other existing list page.
- `DataInspector` is a generic tab-switching shell (`role="tablist"`/`role="tab"`/`role="tabpanel"`) whose tab content is fully caller-supplied `ReactNode` — it has no knowledge of tabular data at all, so it remains usable for a future non-tabular inspection view (e.g. a spatial view under EDR-006) without modification.

Both live under `frontend/src/components/ui/`, alongside the project's existing (if so far minimal) shared-component convention (`StatusBadge.tsx`) — this is the first genuinely-justified extraction of a reusable component in this codebase; every PSS/E-specific piece (column definitions, tab composition, the Overview tab's field choices, routing) remains inside `frontend/src/modules/psse_integration/`, not shared, since only the table/tab mechanics themselves are actually reusable today.

**Inspector layout:** Overview (source file, RAW version, base MVA, snapshot type, and the same five network-size counts the Preview Summary already shows), Bus Data, Branch Data, Transformer Data, Load Data, Generator Data — one tab per parsed record type, each backed by `DataTable`. A tab with no records for a given file (e.g. Generator Data for a load-only snapshot) still exists and renders `DataTable`'s own default empty message ("No records available.") rather than being hidden — an engineer confirming "this file has no generator data" is itself a useful, honest answer, not a state to conceal.

**Relationship to EDR-006.** EDR-006 establishes that Operational Context should ultimately be presented visually and spatially, in addition to textually, because engineers reason about a network the way they were trained to — as a diagram, not a table of counts. The Inspector is **not** that spatial view; it is a tabular, Excel-like one, and is explicitly named as one of EDR-006's own "Future Opportunities" only in the sense that PSS/E Import Preview generally is (EDR-006, Future Opportunities). What the Inspector shares with EDR-006's own principle is the boundary, not the form: both are presentation-only extensions of Operational Context an engineer already has read access to, and both are forbidden from computing, inferring, or implying an engineering conclusion the underlying data does not already contain. A future spatial view of the same imported records remains open territory EDR-006 already claims; the Inspector's `DataInspector` shell was deliberately built tab-content-agnostic so that a future spatial tab could be added alongside the tabular ones without restructuring the Inspector itself.

**A future EDR is worth considering, not created here.** This phase treats the Inspector as the first implementation of a reusable inspection capability, not a one-off PSS/E feature — `DataTable`/`DataInspector` were built generic specifically so that future modules (Current Operational Context, historical `LoadSnapshot` comparison, Network Explorer's own record-level views, a future Continuous Validation result inspector) can reuse them without re-justifying the pattern. If a second module actually reuses these components, that is the point at which "Operational Context Inspection" (or a broader "Engineering Record Inspection") crosses from an implementation pattern into a named architectural capability worth its own EDR — recorded here as an observation for that future point, not decided now, since one implementation does not yet establish a recurring pattern.

**No engineering behaviour changed.** The parser, `service.preview()`'s validation/matching logic, `service.commit()`, Activation, and Equipment Correlation are all untouched by this phase — confirmed by the full existing Preview/Commit/Activate test suite passing unchanged alongside the new Inspector-specific tests.

### 8.10 Workflow 7 — Current LoadSnapshot Activation

An authenticated, authorized user (CLAUDE.md A10) reviews a batch's outcome (warnings, coverage) and explicitly activates it. Activation is a single atomic operation:
- If the batch introduced a new `TopologyVersion`: both the new `TopologyVersion` and its `LoadSnapshot` transition `Imported → Current`, and the previously `Current` `TopologyVersion` and `LoadSnapshot` both transition `→ Superseded`.
- If the batch reused the existing `TopologyVersion` (Workflows 3 or 4): only the new `LoadSnapshot` transitions `Imported → Current`; the `TopologyVersion` remains `Current` (unchanged); the previously `Current` `LoadSnapshot` transitions `→ Superseded`.
- Both halves of any supersession are recorded as a single correlated audit event (§14).
- `promoted_at` is stamped on the record(s) becoming Current; `superseded_at` is stamped on the record(s) being superseded (§11) — enabling efficient point-in-time queries without replaying the audit log.

### 8.11 Workflow 8 — Historical LoadSnapshot Query

Any authorized reader may query a specific `Superseded` `LoadSnapshot` by id, or ask "what was Current as of timestamp T" (resolved via each record's `promoted_at`/`superseded_at` window, not by replaying audit history). This supports reproducing exactly what network state informed a scheme version's recommended MW at the time it was designed or approved (§9, §14), and supports Dashboard's historical reporting needs.

---

## 8a. EquipmentTopologyMap

Formalizes what [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md) §6–§9 and [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md) §6/§9/§12 already decided, at the same section-by-section level of detail this document gives every other owned entity. Nothing here reopens either ADR — this section only completes the specification `psse-integration-module.md` §17 had previously left as a vague, unbuilt Future Extension.

### 8a.1 Purpose

`EquipmentTopologyMap` is the read-only bridge between two independently-owned, independently-correct facts: **what an engineer declared** (Equipment Registry's `Circuit`/`CircuitTerminal` identity — bay number, substation, breaker number) and **what is actually electrically connected** (this module's own `TopologyVersion` and its structural children). Neither side is more authoritative than the other for its own kind of fact (ADR-006 §5) — `EquipmentTopologyMap` exists solely to correlate them, not to decide between them.

### 8a.2 What It Correlates

- **Target granularity: `CircuitTerminal`, never `Circuit` directly, and never a generic `Equipment`/`IncomingBranch` row.** Bay-identifier matching against real PSS/E structural data is inherently per-terminal (ADR-007 §5 Workflow F, §6, §9) — a `Circuit`'s own effective PSS/E correlation is the **union** of its `CircuitTerminal`s' individual `EquipmentTopologyMap` entries, resolved by traversal at query time (by Network Model or this module's own service layer), never stored redundantly on `Circuit` itself.
- Scoped **per `TopologyVersion`**, not per `RawFileImportBatch` (§7) — a `CircuitTerminal`'s correlation can differ across topology versions (e.g. after a bus renumbering), and matching may be recomputed against an existing `TopologyVersion` independently of any new import, as Equipment Registry's own data changes.
- Each entry references at most one `TopologyBranch` or `TopologyTransformer` (nullable — unset when unmatched).

### 8a.3 Matching Outcomes

Every `CircuitTerminal` that a `TopologyVersion` is checked against produces exactly one of three outcomes, per ADR-006 §8:

1. **Clean match, consistent endpoints.** A PSS/E element resolves, and its electrically-implied far end agrees with the `Circuit`'s other declared terminal(s). Recorded silently as part of normal processing — no warning, no review needed.
2. **Unmatched.** No PSS/E element resolves against this `CircuitTerminal` at all. Reported as an **unmatched-equipment warning** on the triggering event, mirroring the existing unmatched-bus/unmatched-mnemonic pattern already established for Substation Registry matching (§9, rule 12) — surfaced for engineer review, never silently dropped, never blocking the rest of import processing.
3. **Discrepancy.** A candidate PSS/E element resolves, but the electrically-implied relationship conflicts with Equipment Registry's declared circuit membership (e.g. the imported topology now shows this terminal's circuit reaching a different far substation than Equipment Registry declares). This is a distinct category from "unmatched," never conflated with it.

### 8a.4 Matching Key (Open Implementation Detail)

Matching is keyed on Equipment Registry's own declared identity for the `CircuitTerminal` — its substation (via `SubstationVoltageYard`) and its owning `Circuit`'s `bay_number` — checked against `TopologyBus`/`TopologyBranch`/`TopologyTransformer` records at that substation. **Unlike Substation Registry's own mnemonic history (`SubstationAlias`), `Circuit`/`CircuitTerminal` currently has no persisted rename/alias history** (`equipment-registry-module.md`'s own §7.9–§7.11 describe a `bay_id`/`EquipmentAlias` mechanism from an earlier draft that was not, in fact, carried into the as-built Phase 3 model — see that document's own "Superseded Design Decisions" appendix). Matching against only the *current* declared identity is therefore all this module can rely on today; if a `Circuit`'s `bay_number` or terminal assignment is corrected after a prior clean match, that prior match may need to be recomputed rather than resolved historically. **This is flagged as an open implementation question for whoever builds `EquipmentTopologyMap`, not resolved by this revision** — it does not block Phase 4 from starting, since the fallback (match against current identity only, treat a stale match as a fresh unmatched/discrepancy outcome on recomputation) is a safe, conservative default.

### 8a.5 Human Review Is Mandatory for Non-Clean Outcomes

Both **unmatched** and **discrepancy** outcomes require an authenticated, authorized engineer to review before that specific `CircuitTerminal`'s correlation is treated as reliable for any downstream purpose (Network Model cut-set resolution, scheme-module assignment). For a discrepancy, review resolves to exactly one of (ADR-006 §8):

- **Accept as a genuine network change** — an engineer updates Equipment Registry's own declared data (e.g. `CircuitTerminal`'s switchyard/substation) through Equipment Registry's own service layer, as a normal, audited edit. This module never performs that write itself.
- **Reject as a data/import error** — the discrepancy is acknowledged and closed without changing Equipment Registry; it remains a permanent, queryable part of the triggering `TopologyVersion`'s matching history regardless of resolution.

An unresolved discrepancy or unmatched result does **not** block the `TopologyVersion`/`LoadSnapshot` activation gate (§8.10) — that gate is governed independently by ADR-003's own parse-quality criteria. It blocks confidence in *that specific `CircuitTerminal`'s* correlation only, surfaced wherever that correlation is subsequently consulted.

### 8a.6 Never an Automatic Write, in Either Direction

**PSS/E import never automatically mutates `Circuit`, `CircuitTerminal`, `Transformer`, or `TransformerTerminal` records, under any circumstance.** This module's import process only ever creates `RawFileImportBatch`, `TopologyVersion`, `LoadSnapshot`, and `EquipmentTopologyMap` rows, and only ever *matches against* Equipment Registry — never writes into it — mirroring the already-ratified rule that PSS/E import never auto-creates or auto-modifies Substation Registry records (§9, rule 12; ADR-003 Business Rule 10). Symmetrically, Equipment Registry's own service layer never writes to this module's tables. The only write Equipment Registry ever receives as a consequence of a PSS/E import is the explicit, human-authorized correction described in §8a.5 — performed through Equipment Registry's own API, never as a side effect of this module's import transaction.

### 8a.7 ENTERED_IN_ERROR Exclusion

Equipment Registry's deletion/correction policy (a Phase 3 follow-up, postdating ADR-006/ADR-007) allows a mistakenly-created `Circuit`, `CircuitTerminal`, `Transformer`, or `TransformerTerminal` to be marked `ENTERED_IN_ERROR` rather than hard-deleted (CLAUDE.md §11.6) — meaning "this record does not represent a real engineering asset," per that policy's own stated intent. **`EquipmentTopologyMap` matching must exclude `ENTERED_IN_ERROR` records as candidates** — a corrected, mistaken `CircuitTerminal` (or one whose parent `Circuit`/`Transformer` is itself corrected) must never be offered as a match target for imported PSS/E topology, for the same reason it is already excluded from this module's own default list views' equivalents elsewhere in the codebase (Equipment Registry's own default-view filtering). This exclusion did not exist as a consideration when ADR-006/ADR-007 were written, since the deletion/correction policy postdates both; it is a new, additive requirement introduced by this revision, not a reopening of either ADR's own decisions.

### 8a.8 Audit

Every `EquipmentTopologyMap` computation (matched, unmatched, or discrepancy) and every discrepancy resolution is recorded per §14.

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
14. **PSS/E import never automatically mutates `Circuit`, `CircuitTerminal`, `Transformer`, or `TransformerTerminal` records.** `EquipmentTopologyMap` (§8a) only ever matches against Equipment Registry, never writes into it; a discrepancy is resolved only by an authenticated engineer, through Equipment Registry's own service layer, never as a side effect of an import (§8a.5, §8a.6; ADR-006 §8).
15. **`EquipmentTopologyMap` excludes `ENTERED_IN_ERROR` `Circuit`/`CircuitTerminal`/`Transformer`/`TransformerTerminal` records as matching candidates** (§8a.7) — a record corrected as a mistake under Equipment Registry's deletion/correction policy is never offered as a match target for imported topology.

---

## 10. Validation Rules

- Uploaded files must be a supported format: PSS/E `.raw` for topology(+load), or an approved lightweight load-profile format for load-only updates.
- Signature computation includes only structural connectivity and rating data (bus/branch/transformer definitions) — never load/generation values, and never in-service/operational state, which is modeled separately (§5). Parsed records are canonicalized (deterministically sorted, numeric values normalized) before hashing so incidental formatting differences don't produce spurious signature mismatches. **Phase 4.1 stabilization correction:** the initial implementation included the PSS/E `IDE` bus-type code (whose value `4` means isolated/out-of-service) in the bus signature line — a genuine, if narrow, violation of this rule, since `IDE=4` is an in-service flag, not a structural fact, and is already carried separately as `LoadSnapshotBusState.in_service`. Found by independent architecture validation before Phase 5 began and corrected; `IDE` no longer contributes to the signature under any value. A regression test (`test_bus_ide_does_not_affect_signature`) asserts a bus's signature contribution is identical regardless of its `IDE` value.
- A load-only import (Workflow 4) must validate that every referenced bus exists in the target `TopologyVersion`. Unmatched buses are recorded as warnings; a batch is blocked only if it has zero matched buses or another fatal parse error.
- A batch can only be activated if its status is `Completed` or `CompletedWithWarnings`. A `Failed` batch cannot be activated (§8.8).
- `TopologyVersion`, `LoadSnapshot`, and their child records cannot be deleted or edited once created (CLAUDE.md §11.6, §11.7).
- `EquipmentTopologyMap` matching queries Equipment Registry's read-only equipment-lookup interface (§13) excluding any `ENTERED_IN_ERROR` `Circuit`/`CircuitTerminal`/`Transformer`/`TransformerTerminal` (§8a.7, §9 rule 15) — the query itself must apply this exclusion, not rely on a caller to filter results afterward.
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
| `equipment_topology_map` | `map_id` (UUID PK), `topology_version_id` (FK), `equipment_id` (FK, external to Equipment Registry — a `CircuitTerminal`-backed id, never a `Circuit` id directly), `topology_branch_id` (FK, nullable), `topology_transformer_id` (FK, nullable), `match_outcome` (`clean_match` \| `unmatched` \| `discrepancy`), `discrepancy_resolution` (nullable — `accepted` \| `rejected`), `resolved_by_user_id` (FK, IAM, nullable), `resolved_at` (nullable), `created_at` | See §8a. At most one of `topology_branch_id`/`topology_transformer_id` set; both null when `unmatched`. `discrepancy_resolution`/`resolved_by_user_id`/`resolved_at` remain null until an engineer reviews a `discrepancy` outcome. |
| `psse_import_audit_log` | `log_id` (BIGINT PK), `entity_type`, `entity_id`, `event_type` (e.g. `created`, `activated`, `superseded`, `equipment_match_computed`, `equipment_discrepancy_resolved`), `changed_at`, `changed_by_user_id`, `change_reason` | Owned per CLAUDE.md A4. |

**Cross-module constraints:** `topology_bus.substation_id` and `equipment_topology_map.equipment_id` are both `ON DELETE RESTRICT` into their respective external Master Data tables (read/reference only — this module never writes to either). All tables are written exclusively by PSS/E Integration's own service layer (CLAUDE.md A1, [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md)); `equipment_topology_map`'s `discrepancy_resolution` field records only *this module's own* record of the reviewer's decision — the corresponding write to Equipment Registry's own data (if accepted) happens through Equipment Registry's own service layer, not this table (§8a.6).

---

## 12. API Contract (Concept)

APIs are external/UI-facing contracts (CLAUDE.md §13, A9); this section describes conceptual resource shape only.

- `raw-file-import-batches` — list/retrieve past import batches (with status filter); a `preview` action (stateless, no persistence, synchronous — §8.9, §8.9a) returning its result directly, and a `commit` action (execution mode configurable — §8.9c — Direct mode returns the completed result directly, Queue mode is job-polled; either way it creates the real batch and any resulting `TopologyVersion`/`LoadSnapshot`, §8.9).
- `topology-versions` — list/retrieve; a `current` convenience lookup; retrieval of a specific historical version by id.
- `load-snapshots` — list/retrieve; a `current` convenience lookup; retrieval of a specific historical snapshot by id or "as of timestamp" (Workflow 8, §8.11).
- An `activate` action on a batch (or directly on its resulting topology/load records) implementing Workflow 7 (§8.10) — requires a reason and results in a correlated audit event.
- A read-only `recommended-mw` (or similar) query, exposed for scheme modules and Dashboard, resolving a substation/bus's load figure from the Current `LoadSnapshot` — this is the mechanism scheme modules use for Draft/Under-Review recommendations (§9, rule 9), never for Approved data.
- `equipment-topology-map` (§8a) — list/retrieve match entries for a `TopologyVersion`, filterable by outcome (`clean_match`/`unmatched`/`discrepancy`); a `resolve` action on a `discrepancy` entry (requires a reason and one of `accept`/`reject`, §8a.5) — `accept` triggers a call into Equipment Registry's own service layer, never a direct write from this module's own transaction.

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
- A read-only **"resolve `Circuit` to PSS/E elements"** interface (§8a) — given one or more `circuit_id`s, returns the union of their `CircuitTerminal`s' matched `EquipmentTopologyMap` entries for a given `TopologyVersion`, plus any unmatched/discrepancy entries among them. **This is the interface Network Model calls to translate a scheme assignment's `Circuit` reference(s) into a cut-set** (see [network-model-module.md](network-model-module.md)'s own updated Business Rules/Service Interfaces sections) — Network Model never queries `EquipmentTopologyMap` directly.

**PSS/E Integration consumes, from other modules' service layers — never their repositories directly:**
- From Master Data (Substation Registry): substation lookup/matching by mnemonic, used during import parsing (§ Business Rules, rule 12).
- From Master Data (Equipment Registry, Phase 3): a read-only equipment-lookup interface resolving a `CircuitTerminal`'s declared identity (substation, bay number) for `EquipmentTopologyMap` matching (§8a) — excluding `ENTERED_IN_ERROR` records (§8a.7, §9 rule 15); and, when a discrepancy is accepted (§8a.5), a call into Equipment Registry's own write path to record the correction — this module never writes to Equipment Registry's tables directly.
- From Core Platform (IAM): authorization checks for commit/activate/discrepancy-resolution actions; user lookups for audit attribution.

PSS/E Integration never calls another module's repository directly, and no other module writes to its tables, per CLAUDE.md A1 and [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md). Read-only cross-module joins are permitted only for reporting/dashboard purposes, never as a substitute for the service calls above.

---

## 14. Audit Requirements

Per CLAUDE.md §5.4 and A4, PSS/E Integration owns and writes its own audit log (`psse_import_audit_log`), covering every entity in §5.

- Every `RawFileImportBatch` commit is recorded: who, when, source file reference, outcome (topology reused/created, load snapshot created, warnings/errors).
- Every Activation (Workflow 7) is recorded as a single correlated audit event covering both halves of any supersession — the newly Current record(s) and the just-Superseded record(s) — mirroring the pattern in [ufls-module.md](ufls-module.md) §14.
- Every `EquipmentTopologyMap` computation is recorded (event type `equipment_match_computed`, §11) — including the outcome (clean-match/unmatched/discrepancy) for every `CircuitTerminal` checked, not only the ones with a problem, so a full historical picture of match quality per `TopologyVersion` is reconstructable.
- Every discrepancy resolution (`accept`/`reject`, §8a.5) is recorded (event type `equipment_discrepancy_resolved`) on **this module's own** audit log, who/when/why/which way — independently of, and in addition to, the corresponding edit Equipment Registry's own audit log records if the resolution was `accept` (that is Equipment Registry's own audit entry, for its own write; this module's entry is for its own detection-and-review event).
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

1. **Business rule tests** — signature-based reuse vs. new-topology-version logic; immutability of `TopologyVersion`/`LoadSnapshot` and their children; atomic activation (both halves of a supersession succeed or neither does); the structural guarantee that no live dependency exists from approved scheme data back to this module; `EquipmentTopologyMap` never writes to `Circuit`/`CircuitTerminal`/`Transformer`/`TransformerTerminal` under any outcome (§8a.6, §9 rule 14); `ENTERED_IN_ERROR` records are never offered as matching candidates (§8a.7, §9 rule 15).
2. **Engineering calculation / validation tests** — canonicalization stability of signature computation (structurally identical files with incidental formatting differences must produce the same signature); bus-matching and coverage calculation; fatal-vs-warning classification; `EquipmentTopologyMap` outcome classification (clean-match/unmatched/discrepancy) against fixture `CircuitTerminal`/topology data.
3. **API contract tests** — preview-vs-commit behavior (preview must have zero persistent side effects); request/response schema conformance; authorization enforcement per endpoint (§12, §15).
4. **Database migration tests** — required once actual migrations are authored (out of scope for this document).
5. **UI behaviour tests** — required once a PSS/E Integration frontend exists; must confirm the UI only ever displays recommended MW as advisory during Draft/Under Review and never presents it as an approved figure (CLAUDE.md A12).

Business rules and validation logic must not be merged without accompanying tests (CLAUDE.md A11).

---

## 17. Future Extensions

- **`EquipmentTopologyMap` extended to `Transformer`/`TransformerTerminal`** — §8a's initial specification targets `CircuitTerminal` only, since UFLS/UVLS/EMLS assignment targets `Circuit` first (ADR-007 §10); extending the same matching mechanism to transformer-type equipment is a natural, low-risk follow-on once a real consumer needs it, not required for the initial Phase 4 build.
- **Network Model integration** — a future Network Model module will consume `TopologyVersion` data (via this module's service interface) to implement connectivity-graph analysis and island/"pocket" detection, without this module ever owning that analysis itself. Now additionally consumes the `Circuit`-resolution interface defined in §13 for translating scheme assignments into cut-sets — see [network-model-module.md](network-model-module.md).
- **Historical-topology load-only imports** — currently load-only refresh targets the Current `TopologyVersion` only; supporting imports against a historical topology for what-if/backtesting analysis is deferred (ADR-003 Open Question 1).
- **Additional structural element types** — shunts, switched shunts, DC links follow the same per-`LoadSnapshot` state pattern (§5) and can be added without changing this module's core architecture.
- **Alternative network model sources** — CIM/SCADA/EMS integration (CLAUDE.md §27) would extend this module's import capability beyond PSS/E `.raw` files, using the same `TopologyVersion`/`LoadSnapshot` separation.
- **Retention/archival policy** — deferred until real historical data volume is observed (CLAUDE.md A15's pattern; ADR-003 Open Question 5).
- **`Circuit`/`CircuitTerminal` rename/alias history for matching** — if Equipment Registry later adds a persisted rename-history mechanism for circuits (mirroring `SubstationAlias`), `EquipmentTopologyMap` matching should be extended to consult it, per §8a.4's open point — not required for the initial build.
- **Topology Difference Engine** — a future engineering *analysis* capability (not an import function) comparing two `TopologyVersion`s and reporting the structural changes between them in engineering terms: added buses, removed buses, added branches, removed branches, transformer changes, and electrical parameter changes (impedance, ratings) on elements common to both versions. This is deliberately distinct from signature comparison (§10), which only answers "same or different" — a difference engine would answer "different *how*," as a read-only report over two already-persisted, immutable `TopologyVersion`s. No schema, algorithm, or API is specified here; this is a named future capability, not a design.
- **Validation Engine** — a future rule-based validation framework, applied during import validation (§8.4-§8.8) or on demand against an existing `TopologyVersion`, capable of detecting engineering-meaningful problems beyond today's bus-matching coverage check — for example: a bus number inconsistent with its matched substation, duplicate identifiers within one import, voltage-level inconsistencies across a connected branch, electrically impossible connections, missing `EquipmentTopologyMap` correlations, or orphaned topology elements (a bus with no branch/transformer connecting it to anything). Rules would be configurable engineering parameters (CLAUDE.md A7), not hardcoded, so the rule set itself can evolve without a code change. This section names the architectural purpose only — the specific rule catalogue is intentionally not enumerated here, and is real, sequenced future work, not a requirement of the initial Phase 4 build.
- **Engineering Confidence Report** — a future consolidated presentation of one import's (or one `TopologyVersion`'s) quality, expressed entirely as engineering evidence — a topology comparison summary (once the Difference Engine above exists), a validation summary (once the Validation Engine above exists), `EquipmentTopologyMap` correlation statistics (matched/unmatched/discrepancy counts), warnings, and other informational findings. This is explicitly **not** an approval mechanism or a gating score (ADR-010) — it exists to give the activating engineer a single place to see the evidence Engineering Review already consults today in a more scattered form (batch warnings, correlation review screen), never to introduce a pass/fail threshold that silently becomes a de facto approval gate.

---

## 18. Risks and Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| Signature instability from incidental file-format differences | False "new topology" detection, unnecessary `TopologyVersion` churn | Canonicalize parsed structural records before hashing, not raw file bytes (already adopted in §10) |
| Large `.raw` file parsing performed synchronously in-request | Directly echoes the Codebase Discovery Report's finding that the legacy MVP ran heavy computation synchronously in-request; at national-grid scale this risks slow/blocked requests | **Amended by §8.9a (Phase 5B) with measured evidence, then again by §8.9c (Phase 6):** Preview's own cost, once measured, did not match this concern (~150-300ms, zero persistence) — it now runs synchronously, in-request, with no Redis dependency. Commit's cost does match the original concern (~1 second, scaling with file size) — but Redis+RQ is no longer the *only* answer to it: Commit's execution mechanism is now configurable (Execution Engine, §8.9c), defaulting to in-process ("direct") for this project's actual small-team scale, with Redis+RQ ("queue") remaining available for deployments that want it. The original blanket "preview and commit should both be async-friendly, via Redis+RQ specifically" policy is superseded; this row is kept for history. |
| Activation gate skipped or rushed under operational time pressure | Poor-quality data (low substation match coverage) becomes the operational reference for every scheme module's recommendations | Treat as a policy/process control (§15's Importer/Activator role separation), not a technical bypass |
| A recommendation shown to a scheme designer becomes stale if the Current `LoadSnapshot` is superseded before Approval | Designer confusion about which network state a displayed MW reflects | Always surface which `load_snapshot_id` a recommendation came from, and flag if it has since been superseded; approval still captures a value regardless, so correctness is unaffected, only clarity |
| Ad hoc cross-module reads of this module's data by Dashboard/scheme modules beyond the reporting-only exception | Erodes module boundary enforcement (ADR-001), complicates future service extraction | Route any read that informs a business decision through this module's service interface (§13); reserve raw joins strictly for reporting/dashboards |
| Unbounded historical growth of `TopologyVersion`/`LoadSnapshot` and their child rows | Long-term storage/performance concern | Defer a retention/archival policy until real volume is observed (§17), consistent with CLAUDE.md §21 (avoid premature optimisation) |
| `EquipmentTopologyMap` matching has no persisted rename/alias history to consult for `Circuit`/`CircuitTerminal` (§8a.4) — unlike Substation Registry's own mnemonic history | A `Circuit` renamed or re-terminated after a prior clean match could spuriously appear `unmatched` on recomputation rather than resolving against its known history | Accept as a known limitation for the initial build (a fresh `unmatched`/`discrepancy` outcome still routes to mandatory human review, §8a.5 — it fails safe, not silently); revisit if Equipment Registry adds circuit-level alias history (§17) |
| An unresolved `discrepancy` or `unmatched` `EquipmentTopologyMap` entry is left unreviewed for a long period | A scheme module or Network Model consulting that `CircuitTerminal`'s correlation silently relies on stale or absent matching | Surface unresolved entries prominently wherever that equipment's correlation is subsequently consulted (Dashboard, scheme-module assignment UI), not only at import time — mirroring ADR-006 §12's identical risk and mitigation |

---

## Recommended Next Architecture Document

**Network Model module.**

This document deliberately excludes topology *analysis* from PSS/E Integration's scope (§4) — connectivity-graph traversal and island/"pocket" detection are real, proven, already-used capabilities (per the Codebase Discovery Report) that now have no owning module. Network Model is the direct consumer of the `TopologyVersion` data this module owns, and it is the dependency UFLS/UVLS/EMLS need before their own pocket/island-based assignment design can be completed.

**UFLS module refinement** is the logical step immediately after Network Model, not before it — it needs both this document's recommended-MW service interface (already defined, §13) and Network Model's island-detection primitives (not yet defined) to fully resolve [ufls-module.md](ufls-module.md) §7.4/§7.5 against real-world assignment patterns.

**Equipment Registry** and **Cross-Scheme Compliance** remain important but are not blocked by, or blocking, this document, for the same reasons given in [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md)'s equivalent recommendation — sequencing them after Network Model does not add risk, and Cross-Scheme Compliance in particular should still be treated as the single highest-severity *open* architectural question from the discovery report, to be picked up once Network Model is in place.
