# Regional Engineering Analytics Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (A1, A7, A12). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md).

Related: [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md), [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md), [scheme-data-consumption-matrix.md](scheme-data-consumption-matrix.md) §1, [engineering-workspace-architecture.md](engineering-workspace-architecture.md), [engineering-review-panel-architecture.md](engineering-review-panel-architecture.md).

Origin: an engineering-discovery review of the legacy Grid Defence MVP found mature regional engineering analytics (target/potential/assigned comparison per region) worth adopting as an engineering concept. This document adopts the concept, not the MVP's implementation — most importantly, it explicitly rejects the MVP's percentage-derived regional target model, per the Project Owner's direction (§3, below).

---

## 1. Purpose

To give an engineer, while designing or reviewing a Scheme Version, a clear picture of how shedding capacity and shedding assignments are distributed across Region (and, in future, GM Zone, State, and Grid Owner) — without ever treating that distribution as a validation rule, a Publication gate, or a source of automatic balancing.

## 2. Scope and Ownership

Regional Engineering Analytics owns no persisted data of its own. It is a named, precise elaboration of the "current analytics" capability [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §2 already lists as owned by the Continuous Evaluation Engine — not a new capability sitting outside that engine's ownership boundary. It composes, at evaluation time:

- the candidate universe ([engineering-workspace-architecture.md](engineering-workspace-architecture.md) §4), resolved from Equipment Registry;
- Region (and future GM Zone/State/Grid Owner) metadata, resolved read-only from Substation Registry ([scheme-data-consumption-matrix.md](scheme-data-consumption-matrix.md) §1);
- current MW, per [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §7;
- the current Draft or Published version's own assignment universe.

No new table, no new module, no new owned entity — the same non-ownership pattern [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §3 already establishes for orchestration-only capabilities in this pack.

## 3. Version Total Target MW — Explicit Clarification

**Target MW comes from the external engineering study. It is not derived from a percentage, and it remains fixed for the life of the Scheme Version** — restated here, precisely, per the Project Owner's explicit confirmation, extending [scheme-engineering-principles.md](scheme-engineering-principles.md) §1's existing "external engineering studies determine... target MW per stage" principle to the version-total level specifically:

```text
Version Total Target MW = sum(Stage Target MW)
```

Nothing else. This document, and this pack generally, does **not** introduce a `Version Target Percentage` field, and does **not** introduce any automatic scaling of a region's or a stage's target from a system-wide percentage. A snapshot change never changes any target MW value, at any level — snapshots change only current MW, evaluation, and findings ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §2, §4), never a target. See [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §2, which carries a pointer to this section.

This is a deliberate rejection of the MVP's own `LoadSheddingVersion.target_percentage` concept (a version-wide percentage the MVP applied against each region's total load to derive a per-region target). That mechanism is not adopted — it would make a target MW a *derived, moving* figure rather than the fixed external-study input this pack's target-MW model has always required, contradicting [scheme-engineering-principles.md](scheme-engineering-principles.md) §2's "external studies own the engineering objective... GridDefence never derives these" principle directly.

## 4. Regional Engineering Summary — Metric Definitions

For a given Scheme Version (Draft or Published) and a given dimension value (a Region, and in future a GM Zone/State/Grid Owner — §6, below), optionally scoped to one stage or priority group or aggregated across the whole version:

| Metric | Definition |
|---|---|
| **Potential MW** | Sum of current MW, per [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §7, across every candidate in the candidate universe located in this dimension value, whether or not currently assigned — subject only to the eligibility rule in §5, below. |
| **Current Assigned MW** | The current MW contribution of every engineering object currently assigned in this dimension value, under whichever evaluation snapshot currently applies (the Draft's selected snapshot, or the Published version's globally Active snapshot). |
| **Contribution %** | This dimension value's Current Assigned MW ÷ the total Current Assigned MW across the same scope (stage, priority group, or whole version) × 100. A pure derivation over two already-computed figures — computed once, backend-side, as part of the same analytics response, so every consumer (Engineering Workspace, future Dashboard) sees an identical figure rather than each re-deriving it. |
| **Candidate Count** | Count of eligible candidates (§5) in this dimension value. |
| **Assigned Count** | Count of currently-assigned candidates in this dimension value, within the current version. |
| **Remaining Potential MW** | Potential MW − Current Assigned MW — the still-available eligible capacity not yet committed in this dimension value. |

**Current Assigned MW is not a stored value.** It is recalculated every time it is requested, exactly like Potential MW and every other figure in this table. No occurrence of "assigned" anywhere in this document, or in Regional Engineering Analytics generally, refers to a second, frozen MW figure sitting alongside Current MW — there is only ever one live MW figure per assignment, per [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §7 ("current MW is always derived from the applicable evaluation snapshot"), and Current Assigned MW is simply that same figure, summed over the assignments in a given dimension value.

This is deliberately distinct from, and never reads from, the separate `approved_mw`/baseline value a Publication's own `PublicationRecord` captures once, immutably, at the moment of Publication ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §2.1, [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §8) — that narrower capture is Publication Evidence, not Scheme Data, exists solely so a `PublicationRecord` remains permanently reproducible ([scheme-engineering-principles.md](scheme-engineering-principles.md) §9, §11), and is never itself an analytics figure. Regional Engineering Analytics always recomputes live from the current evaluation snapshot, for both a Draft and a Published version, and never substitutes that historical capture for a live figure.

### 4.1 Recommended Analytical Breakdowns of Potential MW

Potential MW as a single aggregate can hide engineering-relevant structure. The following breakdowns are recommended additions to the Regional Engineering Summary — each is a decomposition of the existing Potential MW total, computed the same way, from the same read-only sources already consumed (§10). None of them introduces an eligibility rule, a finding, or a candidate exclusion; every candidate counted in any breakdown below remains fully counted in Total Potential MW and remains fully selectable.

| Recommended metric | Definition |
|---|---|
| **Total Potential MW** | Renamed from "Potential MW" (§4, above) for clarity now that sub-breakdowns exist — identical figure, identical computation. |
| **ALSF-Capable Potential MW** | The subset of Total Potential MW attributable to candidates that currently have Automatic Load Shedding Functionality capability. UFLS/UVLS only, per [scheme-data-consumption-matrix.md](scheme-data-consumption-matrix.md) §3 — always equal to Total Potential MW for EMLS, which never consults ALSF. |
| **Potential MW Associated with ALSF Findings** | Total Potential MW − ALSF-Capable Potential MW — the MW that would produce a Critical ALSF finding if selected today. Informational only; these candidates remain fully selectable ([scheme-engineering-principles.md](scheme-engineering-principles.md) §6). |
| **Potential MW Associated with Sensitive Customer Findings** | The subset of Total Potential MW attributable to candidates carrying a current Sensitive Customer association — the MW that would produce a Sensitive Customer finding if selected today. Also fully selectable; also never excluded. |
| **Excluded-Ownership MW** | MW attributable to substations excluded from the candidate universe entirely, due to an excluded-ownership classification ([shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §7 rule 2) — shown adjacent to, but never included in, Total Potential MW or Candidate Count (§5). Purely contextual: "this MW exists in the dimension value but can never be assigned," distinct from every other breakdown, which describes MW that *can* be assigned. |

These breakdowns materially improve engineering visibility (an engineer designing a UFLS stage in a region with low ALSF-Capable Potential MW relative to Total Potential MW has immediately useful context, without any candidate ever being hidden or removed) and are recommended for inclusion. They are additive to §4's core metric set, not a replacement for it, and carry the same non-enforcement guarantee as every other metric in this document (§8).

## 5. Eligibility for "Potential"

**Potential MW and Candidate Count (and every breakdown in §4.1) are computed over the candidate universe, minus only structurally-ineligible candidates — never minus candidates lacking ALSF capability.** Precisely:

- A substation whose Grid Owner classification is an excluded-ownership classification (IPP, LSS) is excluded from Potential MW and Candidate Count, since it can never be assigned under any circumstance ([shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §7 rule 2).
- A candidate lacking ALSF capability, or carrying a Sensitive Customer association, **remains counted** in Potential MW and Candidate Count — per [scheme-engineering-principles.md](scheme-engineering-principles.md) §6, absence of ALSF capability never removes a candidate; it only produces a finding once actually selected. Excluding it from "potential" would misrepresent it as unavailable when it is, in fact, engineer-selectable today.

This is a deliberate, precise divergence from the MVP's own equivalent metric, which scoped its "potential" figure to substations with an *active, wired* relay (`LoadSheddingRelay.is_active`) — the MVP's closest analogue to an ALSF-style capability gate. Adopting that scoping here would silently reintroduce exactly the kind of capability-based exclusion [engineering-workspace-architecture.md](engineering-workspace-architecture.md) §4.3 and [scheme-data-consumption-matrix.md](scheme-data-consumption-matrix.md) §3 already prohibit. "Potential" in this architecture means "structurally assignable," not "already equipped for automatic response."

## 6. Dimensions

Region is the first dimension implemented. GM Zone, State, and Grid Owner are the same computation shape, applied to a different Substation Registry field ([scheme-data-consumption-matrix.md](scheme-data-consumption-matrix.md) §1) — no redesign required to add them, consistent with [scheme-future-extensibility.md](scheme-future-extensibility.md) §6's "reuse shared platform capabilities, introduce only what is genuinely different" discipline. Each metric in §4 is computed identically regardless of dimension; only the grouping key changes.

Scope (whole version vs. a single stage/priority group) is a query parameter of the same computation, not a separate metric set — an engineer may view a version-wide regional summary or drill into "Region X, Stage 4" using the identical underlying figures.

## 7. Recommended Placement in the Product

Four candidate placements were considered — module dashboard, Engineering Workspace, published-version analytics, and a future executive Dashboard. These collapse to two real answers, not four independent ones:

- **Primary home: the Engineering Workspace**, for both Draft and Published versions. Regional Engineering Analytics is scheme-version-scoped data (§2) — an engineer needs it while actively designing a Draft, and while reviewing a Published version's ongoing standing. Since [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §4 already keeps Published versions under continuous evaluation, "published-version analytics" is not a fourth, separate location — it is simply the Engineering Workspace's own view of a Published version, which is already the pack's existing model. No new UX surface is required to serve both cases.
- **Secondary, future home: the Phase 11 Dashboard**, composing the same Continuous Evaluation analytics service read-only, aggregated across scheme types and versions, for a cross-scheme executive view — consistent with Dashboard's own already-established "owns no schema, composes read-only interfaces from every other module" principle ([`domain-model.md`](domain-model.md) §6, [`implementation-plan.md`](implementation-plan.md) Phase 11). Dashboard never recomputes Potential MW, Contribution %, or any other metric independently — it reads the same figures the Engineering Workspace reads, at a coarser grain.
- **"Module dashboard"** (a UFLS/UVLS/EMLS module's own cross-version list view, distinct from a single Scheme Version's Workspace) is a plausible future refinement — e.g. a rollup card showing the module's currently-Published version's regional summary — but is not designed here, is not blocking, and carries no redesign risk either way, since it would read the identical analytics surface.

**No duplication:** exactly one computation of every metric in §4, owned by the Continuous Evaluation Engine's analytics surface; the Engineering Workspace and any future Dashboard are pure presentation layers over it.

## 8. Regional Balancing Philosophy

Restated, unconditionally, per this pack's own governing principle ([scheme-engineering-principles.md](scheme-engineering-principles.md) §6, [scheme-data-consumption-matrix.md](scheme-data-consumption-matrix.md) §1):

- Regional balancing remains an engineering objective that may inform an engineer's decisions.
- It is **never** automatically enforced — no finding, no structural prerequisite, no Publication treatment is ever triggered by a region being over- or under-represented relative to its Potential MW or its share of Current Assigned MW.
- The platform informs. Engineers decide. This applies identically to every dimension in §6, present and future.

Regional Engineering Analytics is therefore never a Finding source and never appears in the [Engineering Review Panel](engineering-review-panel-architecture.md)'s findings list (§4 of that document) — it is informational analytics, presented alongside the panel in the Engineering Workspace, never injected into it as a detected issue.

## 9. API Contract (Concept)

- `scheme-versions/{id}/regional-analytics?dimension=region|gm_zone|state|grid_owner&scope=version|stage:{stage_id}` — read-only, returns the metric set in §4 grouped by the requested dimension's values, for the requested scope.
- No persistence endpoint of its own — every figure is computed on read, from Continuous Evaluation's own live data, mirroring [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §10's "always synchronous, no persistence endpoint" precedent for orchestration-only capabilities in this pack.

## 10. Service Interfaces

- `getRegionalEngineeringSummary(scheme_version_id, dimension, scope) → RegionalEngineeringSummary[]` — the primary interface, consumed by the Engineering Workspace and, in future, by Dashboard.
- Consumes, from other modules' service layers, never repositories directly (CLAUDE.md A1): Substation Registry (dimension metadata); Equipment Registry (candidate universe); the Continuous Evaluation Engine's current-MW and evaluation-snapshot surface; the Automatic Load Shedding Functionality Registry and Sensitive Customer Registry are deliberately **not** consulted for eligibility filtering (§5) — only for the same optional, non-filtering display metadata the Engineering Workspace's candidate view already exposes.

## 11. Audit Requirements

This capability computes and logs, not audits — it is a deterministic, automated calculation over already-audited engineering data, producing no new engineering decision of its own (mirroring [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §12's identical reasoning). No new audit trail is introduced.

## 12. Security Considerations

- Requesting regional analytics requires no elevated permission beyond whatever permission the calling scheme module's own Draft/Published-version read access already requires.
- All GridDefence engineering data, including regional analytics, is sensitive by default (CLAUDE.md A10); TLS required outside local development.

## 13. Testing Requirements

Per CLAUDE.md §18/A11: Potential MW and Candidate Count correctly include ALSF-incapable and Sensitive-Customer-associated candidates, and correctly exclude excluded-ownership substations (§5); §4.1's breakdowns sum back to Total Potential MW (ALSF-Capable + Potential MW Associated with ALSF Findings = Total Potential MW) and never affect Candidate Count; Current Assigned MW recalculates correctly, and differently, before and after an evaluation snapshot change, confirming no cached or stored value is ever read in its place; Contribution % sums to 100% across a complete dimension partition; Remaining Potential MW is never negative under normal data (and, if it is, that itself is worth surfacing as a data-quality signal, not silently clamped); Version Total Target MW always equals the sum of Stage Target MW, with no code path capable of deriving it any other way.

## 14. Future Extensions

- GM Zone, State, and Grid Owner dimensions (§6) — additive, no redesign.
- A "module dashboard" cross-version rollup (§7) — deferred, not designed here.
- Historical regional-trend reporting (how a region's Current Assigned MW has changed across successive Published versions) — not designed here; would consume the same per-version metric set across a version history query, not a new computation.

## 15. Risks and Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| A future implementer, familiar with the MVP, reintroduces a percentage-derived target "for convenience" | Silently violates the fixed-target-MW principle (§3) and the external-study-ownership principle | Treat §3 as a hard architectural constraint in code review, not a preference |
| A future implementer filters "Potential" by ALSF capability by analogy with the MVP | Silently reintroduces capability-based candidate exclusion, contradicting [engineering-workspace-architecture.md](engineering-workspace-architecture.md) §4.3 | Treat §5's eligibility rule as a hard constraint; test explicitly for ALSF-incapable candidates remaining counted (§13) |
| Dashboard (Phase 11) is eventually built without reusing this capability's service interface, recomputing its own regional aggregation | Duplication risk, drift between Engineering Workspace and Dashboard figures | Phase 11's own scoping (recommended in [`implementation-plan.md`](implementation-plan.md) Architecture Gaps) should explicitly reference this document before implementation begins |
