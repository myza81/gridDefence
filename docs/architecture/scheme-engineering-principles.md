# Grid Defence Scheme Engineering Principles

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. Governing engineering reference: [01-engineering-philosophy.md](../engineering/01-engineering-philosophy.md) (authoritative; this document elaborates it for the Defence Scheme domain specifically, and does not override it).

This document is the entry point to the Engineering Scheme Architecture Pack — the authoritative basis for UFLS, UVLS, EMLS, shared scheme services, the Engineering Workspace, continuous evaluation, and findings/publication governance, per six Project Owner engineering-discovery workshops. It states the philosophy every other document in the pack builds from; it does not itself define schemas, APIs, or UI detail.

> **Architecture Freeze.** The Engineering Scheme Architecture Pack is now considered architecturally complete and serves as the authoritative implementation baseline for Phase 6 onward. This states that the architecture is frozen pending future engineering requirements — it does not claim any implementation is complete; Phases 6–8 (UFLS, UVLS, EMLS) remain unbuilt, per [implementation-plan.md](implementation-plan.md).

**Pack index:**
- [Shared Defence Scheme Domain Model](shared-defence-scheme-domain-model.md)
- [Stage Setting Set Architecture](stage-setting-set-architecture.md)
- [Boundary Pocket Architecture](boundary-pocket-architecture.md)
- [Engineering Workspace Architecture](engineering-workspace-architecture.md)
- [Continuous Evaluation Architecture](continuous-evaluation-architecture.md)
- [Findings and Publication Governance Architecture](findings-and-publication-governance-architecture.md)
- [Engineering Review Panel Architecture](engineering-review-panel-architecture.md)
- [Regional Engineering Analytics Architecture](regional-engineering-analytics-architecture.md)
- [UFLS Engineering Philosophy](ufls-engineering-philosophy.md), [UVLS Engineering Philosophy](uvls-engineering-philosophy.md), [EMLS Engineering Philosophy](emls-engineering-philosophy.md)
- [Scheme Data Consumption Matrix](scheme-data-consumption-matrix.md)
- [Future Extensibility and Architecture Constraints](scheme-future-extensibility.md)
- [Roadmap and Implementation Plan Corrections](scheme-roadmap-corrections.md)
- [Codex Foundation-Readiness Audit Brief](codex-foundation-readiness-audit-brief.md)
- Governing decisions: [EDR-009](../engineering/edr/EDR-009-grid-defence-scheme-lifecycle-realignment.md), [EDR-010](../engineering/edr/EDR-010-boundary-pocket-as-engineering-identity.md), [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md), [ADR-016](../adr/ADR-016-stage-setting-set-as-reusable-versioned-entity.md), [ADR-017](../adr/ADR-017-boundary-pocket-assignment-architecture.md), [ADR-018](../adr/ADR-018-findings-severity-and-publication-governance-separation.md), [ADR-019](../adr/ADR-019-boundary-pocket-evaluation-by-connected-component-discovery.md) (corrects ADR-017's own evaluation mechanism only)

---

## 1. What GridDefence Is (and Is Not)

GridDefence is an engineering design, scheme-management, analytics, governance, reporting, and continuous-validation platform for transmission grid defence schemes. It does not perform dynamic simulation, steady-state stability analysis, relay-setting calculation, or automatic scheme optimisation (01-engineering-philosophy.md §1, §3).

**External engineering studies determine:**
- the required total shedding quantum;
- target MW per stage;
- the approved operating philosophy;
- threshold and delay requirements.

**GridDefence manages:** scheme assignments, engineering workspaces, versioning, current MW evaluation, topology evaluation, ALSF evaluation, Sensitive Customer evaluation, analytics, findings, publication governance, reporting, auditability, and continuous reassessment when operational context changes.

The core principle, unchanged and non-negotiable ([01-engineering-philosophy.md](../engineering/01-engineering-philosophy.md) §2, [EDR-004](../engineering/edr/EDR-004-decision-support-not-automation.md)):

> **GridDefence detects engineering impacts. Engineers make engineering decisions.**

## 2. Ownership of Engineering Truth

This is a fundamental, load-bearing principle governing every document in this pack:

- **External studies own the engineering objective** — the quantum, the strategy, the thresholds. GridDefence never derives these; it records and manages their implementation.
- **Engineers own scheme design and publication decisions** — every Draft, every Boundary Pocket construction, every Publication, is a human act GridDefence supports, never performs on an engineer's behalf.
- **Engineering registries own authoritative engineering facts** — Substation Registry, Equipment Registry, the Automatic Load Shedding Functionality Registry, and the Sensitive Customer Registry each own exactly one slice of engineering truth (CLAUDE.md §5.1, §8), referenced by id, never duplicated into a scheme module's own tables.
- **Operational Context owns current network topology and load conditions** — PSS/E Integration's Operational Snapshot, per [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md) and [operational-snapshot-architecture.md](operational-snapshot-architecture.md), is authoritative for what is *currently* electrically connected and loaded. No engineering registry, including the Defence Scheme domain's own data, may silently override it.
- **GridDefence owns evaluation, analytics, findings, governance, and audit** — never a second, competing source of engineering fact about what a substation is, what a network looks like, or what a study determined.
- **Operational data must never silently alter engineering assignments.** A topology change, a load change, a new PSS/E import — none of these ever remove, add, or modify an assignment automatically. They produce findings ([Findings and Publication Governance Architecture](findings-and-publication-governance-architecture.md)). An engineer decides the response.
- **AI or optimisation may recommend, but may not become the authoritative decision-maker** (§10, below) — a durable constraint on every future extension this pack anticipates, not merely a note about the current implementation.

## 3. Relationship to the Existing Architecture Series

This pack does not replace [`ufls-module.md`](ufls-module.md), [`uvls-module.md`](uvls-module.md), [`emls-module.md`](emls-module.md), [`cross-scheme-compliance-module.md`](cross-scheme-compliance-module.md), [`network-model-module.md`](network-model-module.md), or [`critical-infrastructure-module.md`](critical-infrastructure-module.md). None of those modules has been implemented in code. Where the six workshops' conclusions diverge from what those documents describe, the divergence is recorded as a new, explicit decision ([ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md) through [ADR-018](../adr/ADR-018-findings-severity-and-publication-governance-separation.md)) and a short status note is added to the affected document — never a silent rewrite (CLAUDE.md §5.2; see each ADR's own Consequences section for exactly what is superseded and what remains valid). Substantial parts of those documents remain the correct foundation this pack builds on: module ownership and non-responsibilities, the Substation Registry/Equipment Registry/Core Platform reference-data consumption pattern, the recommended-vs-approved MW capture concept (generalized here to every kind of live-data recommendation, not only MW), the version-internal Rule 3/4-equivalent business rules, per-module audit ownership (CLAUDE.md A4), and the service-interface-only cross-module communication discipline (CLAUDE.md A1).

## 4. Shared Platform vs. Scheme-Specific Policy

Do not assume UFLS, UVLS, and EMLS should duplicate common infrastructure, and do not over-generalize their genuine differences into one undifferentiated framework. The [Shared Defence Scheme Domain Model](shared-defence-scheme-domain-model.md) states precisely which capabilities are shared platform (version lifecycle, MW/pocket capture semantics, audit, change reasons, findings, publication governance, the Engineering Workspace) and which are scheme-specific policy (UFLS's frequency thresholds, UVLS's regional voltage scoping, EMLS's priority ordering and absence of any trigger). A new future scheme type (SPS, RAS, generator rejection, controlled islanding — [Future Extensibility](scheme-future-extensibility.md)) should be able to adopt the shared platform capabilities directly and define only its own genuinely-different policy layer, exactly as UVLS and EMLS were already designed to reuse UFLS's own validated pattern before this pack existed ([`uvls-module.md`](uvls-module.md) §7.1, [`emls-module.md`](emls-module.md) §7.1).

## 5. Version Control and Continuous Validation

Two independent principles, neither weakening the other:

- **A scheme's version history is independent of PSS/E's own import history** ([EDR-002](../engineering/edr/EDR-002-scheme-versioning-independent-of-psse.md), unaffected by this pack). A new PSS/E import never creates, requires, or forces a new scheme version.
- **A Published scheme remains under continuous validation regardless.** Every subsequent PSS/E import, every registry change, is compared against every currently-Published scheme, and any relevant impact is reported as a finding ([Continuous Evaluation Architecture](continuous-evaluation-architecture.md)) — never redesigning the scheme, never creating a new version automatically.

## 6. Findings, Not Automatic Correction

Per [EDR-004](../engineering/edr/EDR-004-decision-support-not-automation.md), every capability this pack introduces ends at the point where information becomes available for an engineer to act on. This governs, specifically:
- Lack of ALSF capability never removes a candidate — it remains selectable, and raises a Critical finding.
- A Sensitive Customer association never silently removes an existing assignment — it remains assigned, and raises a finding.
- A topology change that invalidates or materially changes a Boundary Pocket never redesigns the boundary — it raises a finding.
- An MW deviation outside tolerance never blocks assignment or auto-adjusts a target — it raises a finding, subject to publication governance ([Findings and Publication Governance Architecture](findings-and-publication-governance-architecture.md)).

## 7. Engineering Workspace, Not a Linear Wizard

Scheme design is iterative — an engineer moves freely between browsing candidates, building assignments, adjusting a Boundary Pocket, reviewing findings, and comparing operational snapshots, in any order, repeatedly, before Publishing. The [Engineering Workspace Architecture](engineering-workspace-architecture.md) formalizes this as the shared UX/workflow shape every scheme module presents, replacing any notion of a fixed, step-by-step form sequence.

## 8. Publication Is the Engineering Decision

Per [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md) and [EDR-009](../engineering/edr/EDR-009-grid-defence-scheme-lifecycle-realignment.md): a Defence Scheme Version's lifecycle is `Draft → Published → Superseded | Entered in Error`. Review and approval are evidence-gathering activity within Draft, made rigorous by continuously-visible findings, not separate gated states. Publication is the one authorized, audited, Administrator-only decision point — extending [ADR-010](../adr/ADR-010-engineering-decision-support-philosophy.md)'s "Activation is the engineering decision; review is informational" philosophy from Engineering Source/Computed Data to Approved Engineering Policy, a deliberate, ratified extension, not an erosion of rigor.

## 9. Auditability and Reproducibility

Every engineering action this pack governs is traceable: who, when, what changed, why (CLAUDE.md §5.4). Every Published version is permanently reproducible from two complementary, distinct stores (§11, below): its Scheme Data — assignments and Stage Setting Set (where applicable) — and its `PublicationRecord` — captured MW, Boundary Pocket baselines, and Publication findings/acknowledgements. Both remain queryable, unmodified, forever (CLAUDE.md §5.2). Historical audit entries are never rewritten because a later architectural decision, including this pack's own, changed the model going forward.

## 10. Future Extensibility Is a First-Class Constraint

This pack is stress-tested, not merely hoped to work, against SPS, RAS, generator rejection, controlled islanding, BESS, demand response, new engineering identities, real-time SCADA/EMS/PMU data, multi-utility terminology, multi-country deployment, larger network scale, AI-assisted recommendation, and richer snapshot scenarios (§10 of [Future Extensibility and Architecture Constraints](scheme-future-extensibility.md)). The following hold across every future extension:

- A new scheme type uses shared platform capabilities (version lifecycle, findings, publication governance, Engineering Workspace) wherever the underlying engineering problem is genuinely the same shape; scheme-specific rules remain policy layers, never forked copies of shared infrastructure.
- New assignment identities remain owned by authoritative registries — a scheme module never invents its own equipment or facility identity.
- Organisational terminology never leaks into the Scheme Engine — the shared model speaks in engineering terms (stage, assignment, finding, Boundary Pocket), not in any one utility's internal jargon.
- Operational data sources may evolve (new SCADA/EMS/PMU feeds, a richer Operational Snapshot model) without changing scheme ownership — the Defence Scheme domain consumes Operational Context through the same read-only, recommendation-only boundary regardless of what feeds it.
- AI may recommend but may not automatically publish or rewrite assignments — §2 and [EDR-004](../engineering/edr/EDR-004-decision-support-not-automation.md), unconditionally, for every future capability.
- Automatic reassignment in response to a snapshot change is prohibited by philosophy, not merely undesigned — §6, unconditionally.

Do not over-generalize the first implementation into a polymorphic abstraction that obscures UFLS/UVLS/EMLS's own engineering meaning. Prefer the clear extensibility seams this pack names explicitly over speculative generic frameworks (CLAUDE.md §21).

## 11. Three Engineering Views: Current, Published, and Evidence

Every document in this pack distinguishes three views of engineering information. Blurring them is the single most common source of ambiguity this pack has had to correct (see the Regional Engineering Analytics and Boundary Pocket clarifications this section formalizes) — every future document and every future implementation decision should be checked against this separation.

**Current Engineering View.** Used for editing, evaluation, engineering review, dashboards, and analytics (the [Engineering Workspace](engineering-workspace-architecture.md), the [Engineering Review Panel](engineering-review-panel-architecture.md), [Regional Engineering Analytics](regional-engineering-analytics-architecture.md)). Always derived, live, from the applicable evaluation snapshot ([Continuous Evaluation Architecture](continuous-evaluation-architecture.md)). Never frozen — every figure in this view is recalculated on read and holds no authority of its own.

**Published Engineering Decision.** The engineering design an Administrator approved for operational use — a Scheme Version's own **Scheme Data**: engineering identities only (Transformer Terminal references, Boundary Pocket Circuit Terminal opening-point sets, stage/priority-group structure, Stage Target MW, lifecycle, ownership, engineering metadata). Contains no operational MW state, no derived topology, no evaluation result — those are never stored here, at any time, per [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §7 and [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §8. Scheme Data owns only what the engineer decided to assign, never what that assignment currently measures.

**Publication Evidence.** The engineering evidence reviewed when the Published Engineering Decision was approved — a `PublicationRecord` ([Findings and Publication Governance Architecture](findings-and-publication-governance-architecture.md) §2, §2.1): evaluation snapshot identity, MW evaluation summaries, Boundary Pocket baselines, findings present, treatments applied, acknowledgements, the publishing Administrator, the timestamp. Immutable once created. Historical — it documents a moment, not an ongoing state. **Never participates in current evaluation**: Continuous Evaluation never reads a `PublicationRecord` to determine what is true now, only to diff against it for composition-change detection ([boundary-pocket-architecture.md](boundary-pocket-architecture.md) §9); the Engineering Review Panel never renders it directly ([engineering-review-panel-architecture.md](engineering-review-panel-architecture.md) §8).

| | Current Engineering View | Published Engineering Decision (Scheme Data) | Publication Evidence (`PublicationRecord`) |
|---|---|---|---|
| Contains MW? | Yes — always live, derived | Never — only Stage Target MW, an external-study input, not a measurement | Yes — frozen at the moment of Publish |
| Mutability | N/A — recomputed on every read | Immutable once Published (assignment identity only) | Immutable once created |
| Owner | Continuous Evaluation Engine (computes), presented by Engineering Workspace/Review Panel | The consuming scheme module (UFLS/UVLS/EMLS) | Findings and Publication Governance |
| Answers | "What is true right now?" | "What did the engineer decide to assign?" | "What evidence justified approving that decision?" |

The statement "MW values are never stored as engineering facts within Scheme Data" (§9, above) governs the middle column only. It does not apply to the right-hand column: a `PublicationRecord` is not Scheme Data — it is immutable audit evidence, and storing a frozen MW figure there is exactly what it exists to do.
