# ADR-003: PSS/E Topology and Load Snapshot Separation

- **Status:** Accepted
- **Date:** 2026-07-01
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1, §5.2, §5.5, §8, A1, A2, A3, A4, A7)
- **Depends on:** [ADR-000](ADR-000-architecture-principles.md), [ADR-001](ADR-001-modular-monolith-and-module-communication.md), [ADR-002](ADR-002-identity-and-access-management.md)
- **Affects:** [docs/architecture/domain-model.md](../architecture/domain-model.md) (Network Model domain — currently "future, scope reserved"), [docs/architecture/substation-registry.md](../architecture/substation-registry.md) (referenced, not owned), [docs/architecture/ufls-module.md](../architecture/ufls-module.md) §7.5 (Load MW Treatment)
- **Informed by:** the Codebase Discovery Report for the legacy Django + React MVP (gridshed), specifically its finding that the MVP's single `NetworkSnapshot` model conflates topology and load data, and that MW figures shown to UFLS designers are live-computed from that combined model rather than a static approved value.

---

## Context

The legacy MVP imports a PSS/E `.raw` case file into a single `NetworkSnapshot` entity that mixes two fundamentally different kinds of data: the network's **structural topology** (buses, branches, transformers, connectivity — which changes rarely, only when the physical grid changes) and its **load/generation state** (P/Q at each bus — which changes frequently, potentially every operational cycle). Because these are conflated, the MVP cannot cleanly express "import a new load reading without touching the topology," even though its own `TopologyVersion.signature` field shows the original design already anticipated topology reuse. The Codebase Discovery Report identified this as a capability GridDefence must explicitly support: **importing a new RAW file as a new grid load snapshot while preserving or reusing the existing topology when appropriate.**

The same discovery work surfaced a second, more consequential problem: the MVP computes and caches UFLS/UVLS/EMLS MW figures live from whichever network snapshot is currently active (`mw_cache`, recomputed on `activate`/`recompute`). This directly conflicts with [ufls-module.md](../architecture/ufls-module.md) §7.5, which specifies MW as a static, versioned, approved engineering figure, and with CLAUDE.md §5.2 (Immutable Engineering History) — a live dependency would mean an Approved or Active scheme version's effective MW could change without any version bump, approval step, or audit trail entry in the owning scheme module. This was flagged as an open, high-severity architectural question in the discovery report ("MW as derived/live value vs. static approved figure"). This ADR resolves it.

Two things must both be true, and they were previously in tension:
1. GridDefence needs an efficient way to keep grid load data current (import new load readings frequently, without re-establishing topology every time).
2. GridDefence's scheme modules (UFLS/UVLS/EMLS) must retain fully immutable, historically reproducible approved engineering data, per CLAUDE.md §5.2 and the Canonical Version Lifecycle (CLAUDE.md A3), regardless of how often the underlying network data changes.

---

## Decision

GridDefence separates PSS/E import into three distinct, independently-lifecycled entities, all owned by the PSS/E Integration domain (the concrete module implementing the "Network Data" layer of [domain-model.md](../architecture/domain-model.md) §1, currently marked future/reserved — this ADR is the first step in un-reserving it).

### Topology Version

Represents one immutable network structure: the set of buses, branches, and transformers and how they connect, as parsed from a RAW file's structural sections. Identified by a **topology signature** — a deterministic hash computed over structural data only (§ Topology Signature Comparison, below). Never edited once created; a structural change always produces a new `TopologyVersion`, never an in-place update (CLAUDE.md §5.2, applied here to source/derived data, not only to approved engineering policy).

At any time, exactly one `TopologyVersion` is **Current** (the reference used for new load-only imports, recommendations, and dashboards); all others are **Historical** — retained, immutable, and queryable, never deleted (CLAUDE.md §11.6).

### Load Snapshot

Represents one immutable capture of load/generation values (P/Q per bus) tied to exactly one `TopologyVersion` (bus identity is only meaningful within the topology that defines it). Never edited once created — a recalculation or a new import always produces a new `LoadSnapshot` row, never a mutation of an existing one.

At any time, exactly one `LoadSnapshot` is **Current**, and its `topology_version_id` must equal the Current `TopologyVersion`'s id (a `LoadSnapshot` can never be "current" against a topology that has itself been superseded). All other load snapshots are **Historical** — retained, immutable, queryable.

`LoadSnapshot` and `TopologyVersion` are **not** governed by the Canonical Version Lifecycle (CLAUDE.md A3). A3 governs *approved engineering policy* (Draft → ... → Active, requiring human review and approval). A topology/load snapshot is *imported or computed source data* — it carries no approval workflow of its own. Instead, each uses a lighter three-state model: **Imported → Current → Superseded** (see Snapshot Activation, below). This is a deliberate, narrower lifecycle than A3, chosen because applying full scheme-version-style approval machinery to raw imported data would misrepresent it as approved engineering policy, which it explicitly is not (see Business Rules, below).

### Raw File Import Batch

The audit/traceability record of one import action — created every time a user uploads a RAW (or load-profile) file, regardless of what it results in. A `RawFileImportBatch` records:

- The source file reference, the importing user (`user_id`, per [ADR-002](ADR-002-identity-and-access-management.md)), and the timestamp.
- Whether the parsed file contained structural (topology) data, load data, or both.
- The computed topology signature and whether it matched an existing `TopologyVersion` (reused) or produced a new one.
- The resulting `topology_version_id` and `load_snapshot_id` (a batch may result in a `TopologyVersion` only, a `LoadSnapshot` only, or both — see workflows below).
- Parse warnings (e.g. unmatched bus-to-substation mnemonics, in the same spirit as the MVP's `unmatched_mnemonics` tracking) and any fatal errors.
- Batch status: `Completed`, `CompletedWithWarnings`, or `Failed`.

A `RawFileImportBatch` never itself becomes "Current" or "Active" — it is a permanent audit record of what happened during an import, distinct from the data products (`TopologyVersion`, `LoadSnapshot`) that import may have produced or reused.

### Topology Signature Comparison

The signature is a deterministic hash (CLAUDE.md §5.5, Deterministic Behaviour) computed **only** over structural elements: bus records, branch records, and transformer records' connectivity and rating data. It explicitly **excludes** volatile, non-structural fields — load P/Q values, in-service/energization flags, and any other data that represents operational state rather than physical structure. Before hashing, parsed records are canonicalized (deterministically sorted, numeric values normalized) so that incidental differences in file formatting or record ordering between two structurally identical exports do not produce different signatures.

Comparison is a straightforward lookup: if the computed signature matches an existing `TopologyVersion.signature`, that version is reused; otherwise a new `TopologyVersion` is created. This comparison is never based on user assertion ("I know this hasn't changed") — it is always computed from the file's actual structural content.

### Load-Only Update Workflow

A user imports a file containing only load/generation data (e.g. a lightweight CSV/XLSX load profile, following the MVP's precedent for this file class). The system:
1. Creates a `RawFileImportBatch` (content type: load-only).
2. Validates every referenced bus exists in the Current `TopologyVersion` (§ Validation Rules).
3. Creates a new `LoadSnapshot` linked to the Current `TopologyVersion`. No `TopologyVersion` is created or modified.
4. Leaves the new `LoadSnapshot` in `Imported` state pending explicit activation.

### Topology+Load Update Workflow

A user imports a full PSS/E `.raw` file (structural and load data together). The system:
1. Creates a `RawFileImportBatch` (content type: topology+load).
2. Computes the topology signature from the structural sections.
3. **If the signature matches the Current `TopologyVersion`:** no new `TopologyVersion` is created; the batch reuses the existing one. This is the resolution to the discovery report's flagged gap — a full RAW file re-import is automatically treated as a load-only update whenever nothing structural actually changed, with no need for the user to manually select a "load-only" mode.
4. **If the signature does not match:** a new `TopologyVersion` is created (structural change detected — e.g. a new line commissioned, a bus renumbered).
5. Either way, a new `LoadSnapshot` is created, linked to whichever `TopologyVersion` applies (reused or newly created). Both remain in `Imported` state pending activation.

### Snapshot Activation

Import and activation are separate, deliberate steps — mirroring the review gate already established for scheme versions in [ufls-module.md](../architecture/ufls-module.md) §8. A successfully parsed import does not automatically become the operational reference; an authenticated, authorized user (CLAUDE.md A10) must explicitly **Activate** it after reviewing the batch's warnings (e.g. unmatched substations, coverage percentage).

Activating a `LoadSnapshot` (and, if applicable, the `TopologyVersion` it belongs to) is a single atomic operation that:
- Transitions the target `LoadSnapshot` (and new `TopologyVersion`, if any) to `Current`.
- Transitions the previously `Current` `LoadSnapshot` (and previously `Current` `TopologyVersion`, if superseded) to `Superseded`.
- Is recorded as a single correlated audit event covering both halves of the transition (§ Audit Requirements), mirroring the pattern already used for scheme version activation in ufls-module.md §14.

A batch with fatal parse errors cannot be activated. A batch with only warnings may be activated at the importer's discretion.

### Relationship to Substation Registry

Buses in a `TopologyVersion` are matched to Substation Registry records by mnemonic (or another stable identifying attribute), referenced only by `substation_id` — never duplicated (CLAUDE.md §5.1, §8). PSS/E Integration never creates, updates, or infers Substation Registry records from an import; an unmatched bus is recorded as a warning on the `RawFileImportBatch`, not silently dropped and not auto-registered. Registering the missing substation, if warranted, is a separate, deliberate action in the Substation Registry's own service, never a side effect of a PSS/E import.

### Relationship to Equipment Registry (Future)

Branches and transformers in a `TopologyVersion` conceptually correspond to physical equipment (`LoadTransformer`, `AutoTransformer`, `IncomingBranch` in the discovery report's terms) that will eventually be owned by a future Equipment Registry submodule of Master Data, per [substation-registry.md](../architecture/substation-registry.md) §14. Until that module exists, `TopologyVersion`'s structural elements remain self-contained PSS/E representations with no formal equipment linkage. Once an Equipment Registry is designed, a mapping entity correlating physical equipment to topology elements (mirroring the MVP's `EquipmentTopologyMap`) should be introduced as a Future Extension of this ADR's design — not built now, to avoid designing against a module that doesn't yet exist (CLAUDE.md §21, avoid premature optimisation/abstraction).

### Relationship to UFLS/UVLS/EMLS Approved MW Values

This is the central resolution of this ADR:

- While a scheme version is in **Draft** or **Under Review** (CLAUDE.md A3), a scheme module (UFLS/UVLS/EMLS) **may** display a **recommended MW** figure for a substation/assignment, resolved live by calling PSS/E Integration's read-only service interface against the Current `LoadSnapshot` (CLAUDE.md A1). This is advisory — a calculated input to help the engineer, not authoritative engineering data.
- At the moment an assignment's MW is fixed for **Approval**, the scheme module **must explicitly capture** the value into its own owned data (per [ufls-module.md](../architecture/ufls-module.md) §7.5 — MW remains a static, approved, UFLS-owned figure). The scheme module may optionally record which `load_snapshot_id` informed that captured value, purely for traceability — this reference is descriptive metadata, never a live dependency the approved value continues to track.
- Once captured, an Approved or Active scheme version's MW values are structurally independent of PSS/E Integration's data. Superseding, recalculating, or re-activating a `LoadSnapshot` can never modify them — there is no live foreign key from approved scheme data back to a load snapshot that could cause this, only an optional descriptive pointer recorded once, at approval time. This satisfies "importing a new load snapshot must not silently modify approved UFLS/UVLS/EMLS versions" as a structural guarantee, not merely a policy statement.

### Relationship to Dashboard and Audit Engine

- **Dashboard** reads the Current `TopologyVersion` and Current `LoadSnapshot` read-only (via PSS/E Integration's service interface, or read-only cross-module joins strictly for reporting per CLAUDE.md A1/[ADR-001](ADR-001-modular-monolith-and-module-communication.md)) for network visualization, regional/ownership load breakdowns, and data-quality health checks (e.g. unmatched-substation coverage, mirroring the discovery report's `missing-substations`/`network-links`/`aggregate` findings). Dashboard never owns or writes PSS/E Integration data.
- **Audit Engine**: PSS/E Integration owns its own audit log (`psse_import_audit_log`, per CLAUDE.md A4), covering every `RawFileImportBatch`, every `TopologyVersion`/`LoadSnapshot` creation, and every Activation as first-class audit events (§ Audit Requirements).

---

## Business Rules

1. A RAW or load-profile file import always produces a `RawFileImportBatch`; it never directly or silently mutates an existing `TopologyVersion` or `LoadSnapshot`.
2. Topology reuse is determined solely by deterministic signature comparison over structural data — never by user assertion.
3. Exactly one `TopologyVersion` may be Current at a time; exactly one `LoadSnapshot` may be Current at a time; the Current `LoadSnapshot`'s topology must equal the Current `TopologyVersion`.
4. A `LoadSnapshot` can only exist against a `TopologyVersion` (new or reused) — it is never orphaned.
5. `TopologyVersion` and `LoadSnapshot` rows are immutable once created; recalculation always creates a new row, never an in-place update.
6. Import (parsing) and Activation are separate steps; only an authenticated, authorized user can activate.
7. Activating a new Current record automatically supersedes the previous Current record of the same type, as a single atomic operation (mirrors the pattern already established for scheme versions).
8. Importing or activating a new `LoadSnapshot` must never modify, recompute, or invalidate any Approved or Active UFLS/UVLS/EMLS scheme version's stored MW data.
9. A scheme module may treat PSS/E Integration's load snapshot data as a recommendation only while its own version is in Draft or Under Review; at Approval, the value must be explicitly captured into the scheme module's own data.
10. PSS/E import never auto-creates or auto-modifies Substation Registry records; unmatched buses are recorded as warnings only.

---

## Validation Rules

- Uploaded files must be a supported format: PSS/E `.raw` for topology(+load), or an approved lightweight load-profile format for load-only updates.
- Signature computation must exclude load/generation values and any operational-state flags — only structural connectivity and rating data participate in the hash, and parsed records are canonicalized before hashing to avoid spurious signature differences from incidental formatting.
- A load-only import must validate that referenced buses exist in the target `TopologyVersion`; unmatched buses are reported as warnings on the batch. A batch is only blocked from activation if it has zero matched buses or another fatal parse error, not merely a partial mismatch.
- Activation requires a batch with no fatal errors (`Completed` or `CompletedWithWarnings`); a `Failed` batch cannot be activated.
- `TopologyVersion` and `LoadSnapshot` cannot be deleted or edited once created (CLAUDE.md §11.6, §11.7 — no cascading delete, no hard delete outside administrative correction).

---

## Audit Requirements

- PSS/E Integration owns its own audit log (CLAUDE.md A4), covering every `RawFileImportBatch`, every `TopologyVersion`/`LoadSnapshot` creation (reused vs. newly created), and every Activation.
- Activation is recorded as a single correlated audit event covering both halves of any supersession (the newly Current record and the just-Superseded record), mirroring [ufls-module.md](../architecture/ufls-module.md) §14.
- When a scheme module captures an MW value informed by a load snapshot at Approval time, that module's own audit log (already required by CLAUDE.md A4) should record the source `load_snapshot_id` alongside the captured value, so the provenance of an approved figure remains traceable across module boundaries without creating a live dependency.

---

## Consequences

**Positive:**
- Directly closes the discovery report's flagged gap: a new RAW file can be imported purely to refresh load data while automatically reusing the existing topology when nothing structural changed — no manual mode selection required.
- Resolves the MW source-of-truth tension identified in the discovery report: UFLS/UVLS/EMLS keep the static, approved, immutable MW model already specified in ufls-module.md §7.5, while gaining a well-defined, optional path for that value to be *informed* by live network data without ever being *dependent* on it.
- `TopologyVersion`/`LoadSnapshot` immutability plus the explicit capture-at-approval pattern make CLAUDE.md §5.2 (Immutable Engineering History) hold structurally for scheme modules, not just by policy.
- The signature-reuse mechanism prevents unbounded `TopologyVersion` growth under a load-update cadence that is naturally much more frequent than actual grid structural changes.

**Negative / trade-offs:**
- Requires PSS/E Integration to exist as a real module (with its own service layer, audit log, and API) before UFLS/UVLS/EMLS can consume live recommendations — a dependency that must be sequenced (see Recommended Next Architecture Document).
- The three-state (Imported/Current/Superseded) lifecycle is a deliberate deviation from the Canonical Version Lifecycle (A3) used elsewhere; this needs to be clearly understood by anyone extending this module so it isn't mistaken for an oversight or "missing states."
- Historical `TopologyVersion`/`LoadSnapshot` data accumulates indefinitely under this design (no deletion); long-term storage/retention policy is deferred (see Open Questions), consistent with CLAUDE.md A15's pattern of deferring standards until a real need arises.

---

## Alternatives Considered

1. **Single combined entity for topology and load (the MVP's actual design).** Rejected. Conflates two different rates of change and two different consumer needs, and makes "reuse topology, update load only" awkward to express or query cleanly.
2. **Let scheme modules hold a live foreign key to "the current load snapshot" for MW, recomputing on demand.** Rejected. This is exactly the MVP's approach; it directly violates "importing a new load snapshot must not silently modify approved... versions" and CLAUDE.md §5.2, since an approved version's effective MW could change with no version bump, approval step, or audit entry in the owning module.
3. **Always create a new `TopologyVersion` on every import, regardless of signature.** Rejected. Contradicts the explicit requirement to reuse topology when unchanged, and would cause unbounded version growth given load updates are expected far more frequently than real structural changes.
4. **Require the user to manually declare "load-only" vs. relying on automatic signature detection.** Rejected as the primary mechanism (retained as a *complementary* lightweight import path). Manual declaration depends on the user correctly knowing the topology hasn't changed structurally, which they frequently won't be able to determine from the file alone; automatic detection is strictly more robust and is mandated as the primary mechanism.
5. **Auto-activate every successful import immediately, with no separate review gate.** Rejected. Removes the human checkpoint for reviewing parse-quality issues (unmatched substations, coverage) before data becomes the operational reference for recommendations and dashboards — an unacceptable risk given this data ultimately informs grid defence scheme design.
6. **Apply the full Canonical Version Lifecycle (A3) to `TopologyVersion`/`LoadSnapshot`.** Rejected. A3 is designed for approved engineering policy requiring human review/approval workflow. Topology and load snapshots are imported/computed source data with no approval workflow of their own; forcing A3's six states onto them would misrepresent raw data as approved engineering policy, which directly contradicts this ADR's core rule that imported data is not automatically approved scheme data.

---

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Signature instability from incidental file-format differences (record ordering, whitespace, trivial re-export variance) | False "new topology" detection, unnecessary `TopologyVersion` churn | Canonicalize (sort, normalize) parsed structural records before hashing, rather than hashing raw file content |
| Review/activation gate skipped or rushed under operational time pressure | Poor-quality data (low substation match coverage) becomes the operational reference | Treat as a policy/process control, not a technical bypass — do not add a "skip review" technical shortcut |
| A recommendation shown to a scheme designer becomes stale between viewing and approval if the load snapshot is superseded in between | Designer confusion about which network state a displayed MW reflects | Always show which `load_snapshot_id` a recommendation came from, and flag if it has since been superseded — approval still captures a value regardless, so correctness is unaffected, only clarity |
| Ad hoc cross-module reads of PSS/E Integration data by Dashboard/scheme modules accumulate beyond the reporting-only exception in ADR-001 | Erodes module boundary enforcement, complicates future service extraction | Route any read that informs a business decision (e.g. "get recommended MW") through PSS/E Integration's service interface; reserve raw joins strictly for reporting/dashboards |
| Unbounded historical growth of `TopologyVersion`/`LoadSnapshot` rows over years | Long-term storage/performance concern | Defer a retention/archival policy decision until real volume is observed (CLAUDE.md §21, avoid premature optimisation); revisit via a future ADR |

---

## Open Questions

1. Should a load-only import be permitted against a non-Current (historical) `TopologyVersion` for what-if/backtesting purposes, or restricted to the Current topology only?
2. What exact unmatched-bus threshold should block activation outright versus merely warn?
3. Does PSS/E import activation need its own dedicated reviewer/approver role (mirroring the Editor/Reviewer/Approver/Activator separation recommended for UFLS in ufls-module.md §15), or is a single "Integration Engineer" role sufficient given this is source data, not approved engineering policy?
4. Should the canonicalization rules used for signature computation themselves be treated as versioned engineering parameter data (CLAUDE.md A7), given that changing them changes what counts as "the same topology"?
5. What is the long-term retention/archival policy for historical `TopologyVersion`/`LoadSnapshot` rows? (Deferred per CLAUDE.md A15's pattern — to be addressed once real data volume is observed.)

---

## Recommended Next Architecture Document

**PSS/E Integration module** (`docs/architecture/psse-integration-module.md`), using the Canonical Module Architecture Document Template (CLAUDE.md A8).

This ADR has already made the load-bearing architectural decisions — entity design, workflows, signature comparison, activation, and the resolution of the MW source-of-truth question. The natural next step is to formalize those decisions into a complete module document (responsibilities, non-responsibilities, full domain model, API contract concept, service interfaces, testing requirements, and future extensions), the same way [ufls-module.md](../architecture/ufls-module.md) formalized UFLS after its own foundational decisions were settled. Per [docs/architecture/README.md](../architecture/README.md), a module document — not just an ADR — is required before implementation begins.

**Network Model module** should follow immediately after, not later. The discovery report found that topology-based island shedding ("pocket bays" in the legacy MVP) is proven, core, already-used functionality — not a future nice-to-have — and it consumes exactly the `TopologyVersion` structure this ADR just defined. Sequencing it right after PSS/E Integration avoids UFLS/UVLS/EMLS being designed without parity for a capability that matters operationally today.

**Equipment Registry** and **Cross-Scheme Compliance** remain important but are not blocked by, or blocking, this ADR. Equipment Registry has no urgent dependency here (this ADR explicitly defers equipment linkage as a future extension). Cross-Scheme Compliance remains the single highest-severity *open* architectural risk identified in the discovery report (the tension between per-module bounded contexts and Rule 1's need to check across UFLS/UVLS/EMLS) and should not be deferred indefinitely — but it is independent of PSS/E import architecture and can be sequenced after PSS/E Integration and Network Model without additional risk accumulating from this ADR's decisions.
