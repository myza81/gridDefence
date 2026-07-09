# Phase 7 Implementation Specification — Operational Snapshot & Operational Correlation

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) (v1.1)

This is an **implementation specification**, not an architecture document and not code. It translates the Phase 7 engineering and architecture documents into an executable implementation plan. It does not reinterpret or contradict any of its source documents; where this plan appears to require a decision those documents don't already make, that gap is named explicitly (§17) rather than resolved silently.

---

## 1. Purpose

Phase 7's engineering discovery (EDR-007) and its two follow-on architecture documents (`operational-snapshot-architecture.md`, `operational-correlation-architecture.md`) established a responsibility model but did not specify how to build against it. This document is the bridge: for each conceptual entity and boundary those documents name, it states what backend/frontend surface realizes it, distinguishing **what is already implemented** (Phase 4's PSS/E Integration module, under ADR-003 and ADR-006) from **what Phase 7 must newly build**. Nothing here is code; it is the blueprint a future implementation task would work from.

## 2. Source Documents

- [EDR-007](../engineering/edr/EDR-007-phase-7-operational-identity-mapping.md) — Bus/Branch/Transformer/Load/Generator Data engineering interpretation; Engineering Principle 12 (Operational Identity Persistence).
- [`operational-snapshot-architecture.md`](operational-snapshot-architecture.md) — Operational Snapshot, Operational Identity, Snapshot Types.
- [`operational-correlation-architecture.md`](operational-correlation-architecture.md) — Operational Correlation, correlation targets, module boundaries.
- [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md) — the **already-accepted and already-implemented** `TopologyVersion`/`LoadSnapshot` separation this specification builds on, never rebuilds.
- [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md) — the **already-accepted and already-implemented** `EquipmentTopologyMap` correlation mechanism, including its Operational Snapshot pivot addendum.
- [`implementation-plan.md`](implementation-plan.md) — phase sequencing this specification fits into (Phase 4 complete; this is Phase 7 discovery/spec work, not a renumbering of the plan).

## 3. Scope and Non-Scope

**In scope:**

- Operational Snapshot representation (confirming, not rebuilding, what ADR-003 already delivered).
- Full RAW topology + load snapshot handling (confirming what Phase 4 already delivered).
- Load-only snapshot synchronisation against active topology (confirming what Phase 4 already delivered, and extending its correlation-status model per EDR-007).
- Bus classification (Switchyard Bus / Split Switchyard Bus / Fictitious Bus / Blank-named Bus / Other non-conforming Bus, per EDR-007 §4) as a first-class, explicit concept — this is genuinely new.
- Operational Correlation as a formalized boundary — extending, not replacing, `EquipmentTopologyMap` and `_match_substation_for_bus`.
- A correlated operational model as a read/query surface for downstream consumers.

**Explicitly not in scope for Phase 7:**

- UFLS/UVLS/EMLS implementation.
- Relay Registry implementation.
- Sensitive Customer Registry implementation.
- Scheme assignment frozen-reference implementation (named as a future extension in both architecture documents; not designed here).
- Full dashboard/heatmap implementation.
- Advanced analytics.
- SCADA/EMS/CIM integration.

## 4. Domain Model

Each entity below is marked with its status. **"Already implemented"** entities are not being redesigned — this section states the conceptual mapping only; the persistence shape is whatever `psse-integration-module.md` already specifies.

| Conceptual entity (EDR-007 / Operational Snapshot Architecture) | Status | Existing realization |
|---|---|---|
| Operational Snapshot | Already implemented | `TopologyVersion` + `LoadSnapshot` pair (ADR-003) — a Full Operational Snapshot is one `TopologyVersion` with its child `LoadSnapshot`; an Incremental Operational Snapshot is a new `LoadSnapshot` against the existing Current `TopologyVersion`. |
| Operational Topology | Already implemented | `TopologyVersion` and its structural children. |
| Operational Load Snapshot | Already implemented | `LoadSnapshot`, always a child of exactly one `TopologyVersion`. |
| Operational Bus | Already implemented, classification is new | `TopologyBus`. EDR-007's Switchyard/Split Switchyard/Fictitious/Blank/Other classification (§4) is not currently a stored or computed attribute — this is Phase 7's new work (§6). |
| Operational Branch | Already implemented | `TopologyBranch`. |
| Operational Transformer | Already implemented | `TopologyTransformer`. EDR-007's Scenario A/B/C distinction (Inter-bus transformer / generator step-up / three-winding) is not currently a stored or computed attribute. |
| Operational Load | Already implemented, categorization is new | `NetworkLoad` (part of `LoadSnapshot`). EDR-007's T/F/N/X-series and Owner-based categorization (§7.3) is not currently stored or computed. |
| Operational Generator | Already implemented | `NetworkGenerator`. |
| Operational Correlation Record | Partially implemented | `EquipmentTopologyMap` already realizes this for Circuit/Transformer-level correlation (ADR-006). Bus-level correlation (`TopologyBus.substation_id`, set by `_match_substation_for_bus`) already exists but is not currently exposed as its own named, queryable correlation-status concept — this is Phase 7's new work (§7).

**Indicative persistence needs (not schema — see §15):** the genuinely new surface is (a) a bus-classification value, computed or stored per `TopologyBus`, and (b) a unified correlation-status concept spanning both the existing `substation_id` match and the existing `EquipmentTopologyMap` match, so a caller can ask "what is this operational object's correlation status" once, regardless of which kind of object it is.

## 5. Backend Module Boundaries

**Recommendation: do not create new `operational_snapshot` or `psse_import` modules.** `psse_integration` already owns exactly this responsibility (ADR-003, ADR-006) — creating parallel modules would duplicate an already-accepted, already-implemented design and violate CLAUDE.md §5.1. The architectural roles named in `operational-snapshot-architecture.md` and `operational-correlation-architecture.md` are **roles**, realized as follows:

```text
psse_integration (existing module, unchanged ownership)
    owns Operational Snapshot persistence (TopologyVersion, LoadSnapshot, children)
    owns Operational Correlation persistence (EquipmentTopologyMap, and the
        bus-level substation match already on TopologyBus)
    gains: bus classification computation (§6), a unified correlation-status
        read model (§7) — both additive to the existing module, not a new one

engineering_registry modules (Substation Registry, Equipment Registry, ...;
    existing, unchanged)
    own curated metadata only — never write to, and are never written to by,
        psse_integration (ADR-006 §8, unchanged)

scheme modules (future — UFLS/UVLS/EMLS)
    consume the correlated model via psse_integration's own service interface
    never perform their own correlation (§11)
```

**Open naming question, not resolved here:** whether the bus-classification and unified correlation-status work (§6, §7) should land as new files inside `psse_integration` (e.g. `classification.py`, extending `matching.py`) or as a clearly-separated internal boundary within the same module. Either satisfies "no new module"; the choice is an implementation-time judgment call, not an architectural one — flagged in §17.

**Hard constraint, restated from the architecture documents:** no plan under this specification may have Engineering Registries overwrite Operational Snapshot data, Operational Snapshot overwrite Engineering Registry metadata, or a scheme module implement its own correlation logic. This is not new — it restates ADR-006 §8 ("never automatically rewritten... never writes into, Equipment Registry") and `operational-correlation-architecture.md` §9 (Separation of Ownership), extended to the Bus-classification and correlation-status work this document adds.

## 6. Operational Snapshot Entities

Fields below are grouped by **already present** (existing `ParsedX`/`TopologyX`/`NetworkX` fields, per `raw_parser.py` and `psse-integration-module.md`) vs. **new for Phase 7**.

### Operational Bus

- Already present: `bus_number`, `bus_name`, `base_kv` (nominal voltage), `substation_id` (bus-level correlation), voltage solution fields (`LoadSnapshotBusState`, per-snapshot).
- New for Phase 7: **`bus_classification`** — one of Switchyard Bus / Split Switchyard Bus / Fictitious Bus / Blank-named Bus / Other non-conforming Bus (EDR-007 §4). Computed from `bus_name` at the same point `_match_substation_for_bus` already runs; not a new parse, not a new query.

### Operational Branch

- Already present: `from_bus_number`, `to_bus_number`, `circuit_id`, `status`, electrical parameters (r/x/b/ratings).
- New for Phase 7: none required. EDR-007's Pattern A/B/C (§5.4) are observational findings about *existing* fields, not new fields.

### Operational Transformer

- Already present: `bus_i_number`, `bus_j_number`, `bus_k_number` (nullable), `circuit_id`, `status`.
- New for Phase 7: optionally, a **`transformer_scenario`** classification (Inter-bus / generator step-up / three-winding, EDR-007 §6.3) — flagged as optional because, unlike Bus classification, no engineering conclusion in EDR-007 depends on this being persisted rather than computed ad hoc when needed. Recommend deferring unless a concrete consumer requires it (§17).

### Operational Load

- Already present: `load_snapshot_id`, `bus_number`, `load_id`, `p_mw`, `q_mvar`, `status`. `owner` is parsed by the RAW format but **not currently persisted** — this is a genuine gap EDR-007's investigation surfaced (the Owner-correlation analysis required a one-off raw-text re-scan, since the existing parser doesn't extract it).
- New for Phase 7: **`owner`** (currently unparsed field — see §17, this may warrant its own small, separately-reviewed parser change, out of this specification's own no-code-change scope), and optionally a **`load_category`** (T/F/N/X-series, per EDR-007 §7.3) — same deferral reasoning as Operational Transformer above.

### Operational Generator

- Already present: `bus_number`, `gen_id`, `p_gen`, `q_gen`, `status`.
- New for Phase 7: none required.

## 7. Operational Correlation Entities

Correlation targets, corrected to match the already-accepted engineering scope of each registry (per `operational-correlation-architecture.md` §4, which itself corrected an earlier draft's mismatched example):

```text
Operational Bus → Substation Registry
    (already implemented: TopologyBus.substation_id, via _match_substation_for_bus)

Operational Branch / Operational Transformer → Line Connectivity Registry /
    Equipment Registry (bay/breaker identity)
    (already implemented: EquipmentTopologyMap, via matching.compute_matches)

Operational Branch Terminal / Operational Transformer Terminal (a Bay)
    → Relay Registry, where applicable
    (not yet applicable — Relay Registry is not yet built)

Operational Load → Sensitive Customer Registry, where applicable
    (not yet applicable — Sensitive Customer Registry is not yet built)
```

**Correlation status concepts** (new, unifying work — §5, §6): every correlation, regardless of which pair of entities it relates, should be expressible as one of:

- **correlated** — a single, unambiguous match (mirrors `EquipmentTopologyMap`'s existing `clean_match`, and a non-null `TopologyBus.substation_id`).
- **unmatched operational object** — an Operational Snapshot object with no corresponding registry object (mirrors the existing `unmatched` outcome and a null `substation_id`).
- **unmatched registry object** — a registry object with no corresponding Operational Snapshot object (not currently surfaced anywhere; a genuine gap this specification names but does not design a fix for).
- **ambiguous** — more than one plausible match exists (mirrors `EquipmentTopologyMap`'s existing `discrepancy` outcome; the bus-level match has no equivalent today, since `_match_substation_for_bus` is an exact, non-ambiguous lookup by construction).
- **requires engineering review** — any of the above non-`correlated` outcomes, surfaced for human review, never resolved automatically (ADR-006 §8, §9; unchanged).

## 8. Import and Snapshot Creation Flow

```text
Upload RAW
        ↓
Parse Tier 1 Operational Model         [already implemented — raw_parser.py]
        ↓
Create Operational Snapshot            [already implemented — commit(),
                                         _commit_full_topology / _commit_load_only]
        ↓
Classify operational objects           [NEW — bus classification, §6]
        ↓
Run correlation                        [already implemented for Circuit/Transformer
                                         (_run_matching) and Bus (_match_substation_for_bus);
                                         NEW: unify into one correlation-status read model, §7]
        ↓
Produce validation report              [partially implemented — batch warnings/finding-groups
                                         exist; NEW: express in terms of §7's correlation
                                         status vocabulary consistently]
        ↓
Activate or keep as draft/pending review [already implemented — Activation, §8.10 of
                                         psse-integration-module.md]
```

No parser internals are defined here, consistent with the constraint.

## 9. Load-only Snapshot Synchronisation

This is **already implemented** (`_commit_load_only`, `psse-integration-module.md` §8.7) and already satisfies EDR-007's requirements precisely:

- A load-only RAW does not redefine Operational Topology — confirmed: `_commit_load_only` never creates or modifies a `TopologyVersion`.
- It correlates against the currently active Operational Topology — confirmed: matches against `get_current_topology_version()`.
- Bus Number is the authoritative correlation key — confirmed: matching is by `bus_number` exclusively, never by any other field (Engineering Principle 12).
- Missing or unmatched Bus Numbers must be flagged — confirmed: produces a warning per unmatched load bus.
- Load-only snapshot acceptance requires engineering validation — confirmed: Activation remains a separate, explicit, privileged step (ADR-003).

**Phase 7's contribution here is presentational/classificatory, not behavioural:** expressing the existing matched/unmatched outcome in the §7 correlation-status vocabulary, and — once Bus classification (§6) exists — being able to state *which kind* of bus (Switchyard, Fictitious, etc.) went unmatched, which the current implementation cannot yet distinguish. No change to the underlying engineering behaviour is implied or required.

## 10. Correlated Operational Model

A **read/query model**, not a new source of truth — composing already-owned data from `psse_integration` and (once built) Engineering Registries, without copying either into a new table. Conceptually:

- Operational Bus enriched with: Substation/Switchyard identity (where correlated) and its classification (§6).
- Operational Branch/Transformer enriched with: Equipment Registry bay/breaker metadata (where correlated via `EquipmentTopologyMap`).
- Operational Load enriched with: Sensitive Customer classification, where that registry exists (future).
- Every enriched object also carries its correlation status (§7) — a caller must always be able to tell "is this real, registry-backed metadata, or is this object simply unmatched."

This mirrors `get_circuit_correlation`'s existing shape (already implemented, `psse-integration-module.md` §13) generalized across every operational object type, not only `Circuit`.

## 11. Defence Scheme Consumption

- UFLS/UVLS/EMLS (future) consume the correlated operational model described in §10 via `psse_integration`'s own service interface — never PSS/E's raw parsed data directly.
- Scheme modules never perform their own RAW parsing.
- Scheme modules never independently correlate operational objects against registries — they ask the correlation layer (§7) and receive a status, exactly as `operational-correlation-architecture.md` §6 requires ("Defence Schemes... do not implement their own correlation logic").
- Future scheme assignments will likely need **frozen Operational Snapshot references** for auditability and reproducibility (Snapshot ID + Bus Number + Load ID, or equivalent per-object-type keys) — named identically in both `operational-snapshot-architecture.md` §10 and `operational-correlation-architecture.md` §10 as a future extension. **Not designed here.**

## 12. Frontend Surface Areas

All of the following already exist in some form (Phase 4/6 PSS/E Integration frontend, and the Phase 6.2 Operational Context Inspector) — this section states where Phase 7's new concepts would surface, not new pages to build from nothing:

- **Operational Snapshot import/preview** — already exists (`PsseImportUploadPage`). Would gain: Bus classification counts alongside existing network-size counts.
- **Snapshot activation** — already exists (`PsseBatchDetailPage`'s Activate section).
- **Load-only synchronisation report** — already exists as part of Import Result's Registry Matching section; would gain classification-aware wording once §6 exists.
- **Correlation validation report** — already exists in narrower form (Registry Matching, `EquipmentTopologyMap` review page); would generalize toward the unified §7 status vocabulary.
- **Operational object browser** — already exists (the Operational Context Inspector, `PsseOperationalContextInspectorPage`, per §8.9e of `psse-integration-module.md`) — its Bus Data tab is the natural home for the new classification column.
- **Correlated operational model preview** — new; no existing page composes registry metadata onto operational objects yet, since the registries this would correlate against (Relay Registry, Sensitive Customer Registry) are not yet built.

No UI design detail is specified, consistent with the constraint.

## 13. Validation and Error Handling

| Category | Status |
|---|---|
| Parser errors | Already implemented — `RawParseError` → structured `400`. |
| Snapshot structural errors | Already implemented — fatal vs. warning classification in `commit()`. |
| Missing Bus Numbers | Already implemented — unmatched-load-bus warnings (load-only path). |
| Unmatched operational objects | Already implemented per-entity-type (unmatched bus, unmatched branch/transformer reference); **new**: express uniformly via §7's vocabulary. |
| Unmatched registry metadata | Not currently surfaced anywhere — genuine gap (§7, §17). |
| Ambiguous correlation | Already implemented for `EquipmentTopologyMap` (`discrepancy`); not applicable to bus-level matching today (exact-match only). |
| Engineering review required | Already implemented — discrepancy resolution workflow (ADR-006 §8, §9). |

Validation reports must continue to distinguish **technical parse failures** (fatal, block commit) from **engineering correlation issues** (non-fatal, routed to review) — this is the existing, already-correct behaviour (`psse-integration-module.md` §8.9d's Engineering Findings grouping); Phase 7 must not blur this distinction while adding the new classification/status vocabulary on top of it.

## 14. Testing Strategy

- Parser fixtures for full RAW and load-only RAW — already exist (`test_raw_parser.py`, against the real sample files).
- Snapshot creation tests — already exist (`test_service.py`, `test_psse_integration_api.py`).
- Bus Number correlation tests — already exist (`_match_substation_for_bus` coverage).
- Load-only mismatch tests — already exist.
- **New: Bus classification tests** — every EDR-007 category (Switchyard, Split Switchyard, Fictitious, Blank-named, Other non-conforming) against both real sample files, mirroring the discovery session's own analysis scripts turned into permanent fixtures.
- **New: correlation-status unification tests** — that the same status vocabulary (§7) is produced consistently whether the underlying match came from `_match_substation_for_bus` or `EquipmentTopologyMap`.
- No-overwrite ownership tests — already exist in spirit (`EquipmentTopologyMap` "never writes to Equipment Registry" tests); extend the same pattern to any new correlation surface.
- API contract tests — extend existing `test_psse_integration_api.py` patterns for any new/changed response fields.
- Frontend preview and validation display tests — extend existing `PsseImportUploadPage.test.tsx` / `PsseOperationalContextInspectorPage.test.tsx` patterns.

## 15. Migration Strategy

- New persistence is likely required only for: the Bus classification value (§6) — whether computed at read time or persisted is an implementation choice, not an architectural one (leaning toward computed-at-read-time first, per CLAUDE.md §21's "avoid premature optimisation," unless a measured need for persistence emerges) — and the `owner` field currently parsed but not stored (§6, flagged separately since it's a parser change, out of this document's own no-code-change scope).
- Existing Engineering Registry tables must not be repurposed as operational topology storage — restates ADR-006 §6, unchanged.
- Existing registry metadata remains intact — no migration touches Substation Registry or Equipment Registry data.
- Any future migration must preserve current `psse_integration` data (`TopologyVersion`/`LoadSnapshot`/`EquipmentTopologyMap` and their history) exactly as CLAUDE.md §11.6/§5.2 already require.

No migration code is written here.

## 16. Implementation Sequence

1. Resolve the open naming/placement question (§5, §17) — where Bus classification and the unified correlation-status model live inside `psse_integration`.
2. Implement Bus classification (§6) as a computed value, with tests against both real sample files (§14).
3. Decide whether `owner` needs to be parsed and persisted (§6, §17) — a small, separately-reviewable parser change if so.
4. Implement the unified correlation-status vocabulary (§7) as a read-model composition over existing `substation_id` and `EquipmentTopologyMap` data — no new write path.
5. Extend existing validation/finding-group presentation (§13) to use the new vocabulary consistently.
6. Extend the Operational Context Inspector's Bus Data tab (§12) to display classification.
7. Extend Import Result / Registry Matching presentation (§12) to reference the unified status vocabulary.
8. Add the new tests named in §14.
9. Update `psse-integration-module.md` and EDR-007 (a future revision, not this specification) to record what was actually built, mirroring the practice already established for every prior Phase 6/7 documentation pass.

This sequence deliberately does not include UFLS/UVLS/EMLS consumption (§11), Relay Registry, or Sensitive Customer Registry — those remain future phases per §3.

## 17. Open Questions

- Where exactly Bus classification and the unified correlation-status model should live within `psse_integration` (new files vs. extending `matching.py`/`service.py`) — an implementation-time judgment call, not resolved here (§5).
- Whether `owner` should be parsed and persisted now, given EDR-007's Load Data investigation already needed it and had to work around its absence via a one-off re-scan — or deferred until a concrete consumer needs it (§6).
- Whether Operational Transformer's Scenario A/B/C classification and Operational Load's T/F/N/X-series categorization (§6) are worth persisting now, or should remain purely observational (EDR-007) until a scheme module or dashboard concretely needs them.
- Frozen operational references for approved scheme assignments — named as a future extension in every Phase 7 document so far; still not designed (§11).
- Exact load-only mismatch acceptance criteria — EDR-007 and this specification both note that unmatched buses are flagged, but neither defines a threshold for when a load-only import should be rejected outright versus flagged-but-accepted; this remains an open engineering policy question, not a technical one.
- Correlation confidence and ambiguity handling beyond the existing clean-match/unmatched/discrepancy three-way split — whether a richer confidence model is ever needed.
- Multiple active Operational Snapshots — already an open question in `operational-snapshot-architecture.md` §10; unaffected by this specification.
- Historical retention policy for Operational Snapshots and Correlation Records — deferred per CLAUDE.md §21/A15's established pattern for retention questions elsewhere in this project.
- Performance/scalability of correlation computation for large assignment sets, once scheme modules exist and begin consuming the correlated model at scale.
