# Scheme Data Consumption Matrix

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (A1, A2). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md).

This document is the detailed registry/data-consumption matrix requested by the six-workshop conclusions — a single reference for exactly what every Defence Scheme module (and the Engineering Workspace, Continuous Evaluation Engine, and Findings/Publication Governance capabilities this pack introduces) is permitted to read from, and never write to, each source module.

---

## 1. Substation Registry

**Provides:** identity; mnemonic; official name; Region; State; GM Zone; Grid Owner; lifecycle (operational status).

**Consumption rule:** Region, State, GM Zone, and Grid Owner are **analytics and filtering metadata, not validation rules.** A Defence Scheme module never conditions assignment eligibility on these fields (the sole exception, carried forward unchanged: Grid Owner's excluded-ownership check, per [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §7 rule 2 — an eligibility rule, not a metadata display concern, and the only field in this list any scheme module's business rules touch). Every other field is resolved read-only, at request time, for the Engineering Workspace's candidate view and Continuous Evaluation's analytics surface — never persisted into scheme data (CLAUDE.md §5.1). [Regional Engineering Analytics](regional-engineering-analytics-architecture.md) is the concrete, precise elaboration of "analytics" for this field set — informational only, never enforced, never a finding source.

**Consumed by:** every Defence Scheme module (assignment validity, candidate metadata); the Engineering Workspace (candidate view filtering, §4 of [engineering-workspace-architecture.md](engineering-workspace-architecture.md)); [boundary-pocket-architecture.md](boundary-pocket-architecture.md) (Substation identity for every reported isolated island's membership — never an engineer-nominated "inside"/"rest of grid" anchor, removed per [ADR-019](../adr/ADR-019-boundary-pocket-evaluation-by-connected-component-discovery.md)).

## 2. Equipment Registry

**Provides:** Transformer Terminal identity; Circuit Terminal identity; Transformer/Circuit context; voltage and engineering context; lifecycle.

**Consumption rule:** **Transformer Terminal is the direct load-assignment identity.** **Circuit Terminal is the boundary-construction identity.** These are never interchangeable — a direct assignment references `transformer_terminal_id`; a Boundary Pocket's opening points reference `circuit_terminal_id` ([EDR-010](../engineering/edr/EDR-010-boundary-pocket-as-engineering-identity.md)). Neither is ever copied into scheme data beyond its stable id.

**Consumed by:** every Defence Scheme module (direct assignment identity); [boundary-pocket-architecture.md](boundary-pocket-architecture.md) (opening-point identity, via [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md)).

## 3. Automatic Load Shedding Functionality Registry (ALSF)

**Provides:** current automatic-shedding capability, per Transformer/Circuit Terminal.

**Consumption rule:** used by UFLS and UVLS. **Not a prerequisite for EMLS** ([emls-engineering-philosophy.md](emls-engineering-philosophy.md) §3 — a hard exclusion, not a deferred integration). Loss of capability, or a candidate's own lack of capability, **never removes an assignment or a candidate** — it raises a Critical finding, governed by [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md).

**UFLS/UVLS opening-point rule:** every selected direct `TransformerTerminal` assignment, and every selected boundary `CircuitTerminal` opening point, must have applicable ALSF capability — checked by the consuming scheme module at assignment-validation time, never by [boundary-pocket-architecture.md](boundary-pocket-architecture.md)'s own evaluation, which is topology-only and never queries ALSF ([ADR-019](../adr/ADR-019-boundary-pocket-evaluation-by-connected-component-discovery.md)). **EMLS does not require ALSF on any opening point.** ALSF equipment *inside* a derived isolated island (as opposed to *on* a selected opening point) is irrelevant to boundary formation, for every scheme type — see each scheme's own [Engineering Philosophy](scheme-engineering-principles.md) document.

**Consumed by:** UFLS's and UVLS's own Engineering Workspace candidate views (capability display) and assignment-validation logic (opening-point capability check, above); [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) (capability findings). Never by [boundary-pocket-architecture.md](boundary-pocket-architecture.md)'s own evaluation.

## 4. Sensitive Customer Registry

**Provides:** sensitive-facility associations and classifications, per Transformer Terminal.

**Consumption rule:** used by UFLS, UVLS, and EMLS alike — scheme-agnostic. A new or changed association **never removes an assignment** — it raises a finding, governed by [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md).

**Consumed by:** every Defence Scheme module's Engineering Workspace candidate view; [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) (association findings).

## 5. Operational Snapshot / PSS/E Integration

**Provides:** current load and topology context (`TopologyVersion`, `LoadSnapshot`, and their child structural/state records), per [operational-snapshot-architecture.md](operational-snapshot-architecture.md).

**Consumption rule:** **read-only to the Engineering Workspace, at every point.** A Draft may select any historical or Current snapshot for its own evaluation context, without ever writing to PSS/E Integration's own tables ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §5). A Published version is always evaluated against the globally Active snapshot (§4 of the same document) — a Draft's own snapshot selection is never inherited into a Published version's operational basis.

**Consumed by:** [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) (MW/topology evaluation); [boundary-pocket-architecture.md](boundary-pocket-architecture.md) (`traverse`'s own topology source, and `EquipmentTopologyMap` for opening-point resolution).

## 6. Network Model

**Provides:** connectivity, path verification (`traverse`), pocket detection (via the orchestration layer [boundary-pocket-architecture.md](boundary-pocket-architecture.md) builds on top of it — Network Model's own §1–§18 unbuilt design is not itself a current provider, per [ADR-017](../adr/ADR-017-boundary-pocket-assignment-architecture.md)), topology evaluation, change-impact detection.

**Consumption rule:** **read-only to the Engineering Workspace.** Network Model owns no scheme data and never receives a write from any Defence Scheme module ([`network-model-module.md`](network-model-module.md) §9 rule 8, unaffected).

**Consumed by:** [boundary-pocket-architecture.md](boundary-pocket-architecture.md); [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) (topology findings).

## 7. Critical Infrastructure

**Provides:** critical-asset classification (category, criticality level, `restriction_type`), batch and point-in-time, per `substation_id`.

**Consumption rule:** consulted by [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)'s Rule-2-equivalent detector, cross-referenced against every scheme module's `getProtectedAssignments`. Never duplicated into scheme data; a finding's severity is resolved per-asset (`Prohibited` → `Critical`; `ConditionallyAllowed` → `Warning`; `Unrestricted` → no finding), per [`critical-infrastructure-module.md`](critical-infrastructure-module.md) §7.4, unaffected by this pack.

**Kept as a separate bounded context from the Sensitive Customer Registry** (§8, below) — different granularity, different enforcement coupling, different reusability requirements, unchanged from [`domain-model.md`](domain-model.md) §3's own existing reasoning. Not a Phase 6 (UFLS) dependency — Critical Infrastructure remains Phase 9 in the roadmap ([scheme-roadmap-corrections.md](scheme-roadmap-corrections.md)), and its findings simply do not fire until it exists, exactly as [`ufls-module.md`](ufls-module.md) originally anticipated via a stub.

## 8. Critical Infrastructure vs. Sensitive Customer Registry — the Boundary, Restated

Two distinct questions, never merged (per this task's explicit instruction, reaffirming [`domain-model.md`](domain-model.md) §3 and [`sensitive-customer-registry-module.md`](sensitive-customer-registry-module.md)'s own Appendix):

- **Sensitive Customer Registry asks:** "Which important facility or consumer is affected by interruption?" — facts only, Transformer-Terminal granularity, no restriction policy of its own, reusable by future engineering applications that have never heard of GridDefence.
- **Critical Infrastructure asks:** "Which network or operational asset is strategically important to operate, protect, or restore the grid?" — substation granularity, carries an explicit `restriction_type` that directly drives finding severity, purpose-built for GridDefence's own compliance-checking needs.

Both are consulted, independently, by Continuous Evaluation; neither is a Phase 6 (UFLS) dependency unless a future, explicitly-approved architecture change says otherwise.

## 9. Stage Setting Registry

**Provides:** the current set of Published Stage Setting Sets, filtered by scheme type; the reverse lookup of which Scheme Versions currently reference a given Stage Setting Set.

**Consumption rule:** resolved by [ADR-020](../adr/ADR-020-stage-setting-registry-as-standalone-shared-module.md) — a new, standalone module, never duplicated inside UFLS or UVLS. **Read-only to every consuming scheme module** — a Scheme Version references a Stage Setting Set by id; it never copies or reinterprets the referenced set's own `StageSetting` rows. EMLS never consumes this module — it has no Stage Setting Set ([shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §2.3).

**Consumed by:** UFLS and UVLS (Stage Setting Set selection during Draft editing, and Publication-prerequisite validation, per [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md)); the Entered-in-Error correction workflow's own "which versions reference this" query ([stage-setting-set-architecture.md](stage-setting-set-architecture.md) §7 rules 2/3).

## 10. Engineering Parameter Configuration

**Provides:** the current, audited value of every named platform-wide engineering parameter (e.g. `mw_tolerance_percentage`).

**Consumption rule:** resolved by [ADR-021](../adr/ADR-021-engineering-parameter-configuration-ownership.md) — a new, standalone Core Platform module, deliberately not folded into `reference_data` (see that ADR's "Why not Reference Data"). **Read-only to every consumer** — no module other than Engineering Parameter Configuration itself ever writes a parameter's value; a consumer reads the current value at evaluation time, never caches it as its own owned fact.

**Consumed by:** the Continuous Evaluation Engine's MW tolerance detector ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §7.1, [ADR-022](../adr/ADR-022-continuous-evaluation-detector-framework.md)); any future detector or scheme module needing a validated threshold range or similar audited engineering constant (CLAUDE.md A7).
