# UFLS Engineering Philosophy

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md). Read [scheme-engineering-principles.md](scheme-engineering-principles.md) and [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) first — this document states only what is genuinely specific to UFLS, per the six-workshop conclusions, and does not restate shared principles.

Supersedes, in part, [ufls-module.md](ufls-module.md) §7–§8 (status note added there, not a rewrite — see [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §9). [`ufls-module.md`](ufls-module.md) §1–§6, §9 (minus lifecycle rules), §10–§18 remain the authoritative source for UFLS's ownership, non-responsibilities, referenced entities, Rule 3/4-equivalents, and testing priorities.

---

## 1. Frequency-Triggered Staged Philosophy

UFLS defines, in successive stages, how much load is shed and where, as system frequency falls below defined thresholds — unchanged from [`ufls-module.md`](ufls-module.md) §1. Frequency is a single, system-wide quantity — a threshold crossing is a whole-grid event, not a localized one, unlike UVLS's voltage thresholds ([uvls-engineering-philosophy.md](uvls-engineering-philosophy.md) §1).

## 2. Stage Setting Set Usage

UFLS uses its own Stage Setting Set ([stage-setting-set-architecture.md](stage-setting-set-architecture.md)), scoped to `scheme_type = UFLS`, never shared with UVLS. A UFLS Stage Setting Set's stage settings are always grid-wide — UFLS has no regional-scoping concept (unlike UVLS's optional `region_scope_id`). Threshold ordering (strictly decreasing as `stage_order` increases) applies version-wide, with no scope grouping.

**Do not hardcode the present number of stages.** Stage count and settings are driven entirely by the selected Published UFLS Stage Setting Set — never assumed fixed at any particular number, in code, in the UI, or in test fixtures.

## 3. External-Study Target MW Input

Per [scheme-engineering-principles.md](scheme-engineering-principles.md) §1: the total shedding quantum and per-stage target MW are determined by external engineering studies, recorded by the engineer as `target_mw` on each Version Stage — never calculated by GridDefence itself.

## 4. ALSF Relevance

ALSF (Automatic Load Shedding Functionality) capability is directly relevant to UFLS — a UFLS stage's automatic response depends on the assigned Transformer Terminal actually having automatic shedding functionality installed, wired, configured, commissioned, and available. Per [scheme-engineering-principles.md](scheme-engineering-principles.md) §6, lack of ALSF capability never removes a candidate from selection — it remains selectable, and produces a Critical finding, governed by [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)'s policy layer. This is a deliberate correction to [`implementation-plan.md`](implementation-plan.md) Phase 6's own prior wording ("a load that cannot be answered 'yes' is not selectable") — see [scheme-roadmap-corrections.md](scheme-roadmap-corrections.md).

This applies to every selected direct `TransformerTerminal` assignment **and** every selected boundary `CircuitTerminal` opening point alike — both must have applicable ALSF capability, checked by UFLS's own assignment-validation logic. [boundary-pocket-architecture.md](boundary-pocket-architecture.md)'s own evaluation is topology-only and never queries ALSF at all ([ADR-019](../adr/ADR-019-boundary-pocket-evaluation-by-connected-component-discovery.md)) — this check belongs entirely to UFLS, at the point a candidate opening point or a candidate isolated island is considered for assignment. ALSF equipment *inside* a derived isolated island (as opposed to *on* a selected opening point) is irrelevant to boundary formation — see [scheme-data-consumption-matrix.md](scheme-data-consumption-matrix.md) §3.

## 5. Transformer Terminal and Boundary Assignments

Both mechanisms are commonly used for UFLS, per [`ufls-module.md`](ufls-module.md) §7.5's own original reasoning (unaffected by [ADR-017](../adr/ADR-017-boundary-pocket-assignment-architecture.md), which changes the mechanism, not the engineering judgement about how often each is used): a system-wide frequency imbalance is helped by isolating any electrically self-sufficient chunk of the grid, regardless of where that island sits — unlike UVLS, where isolation can worsen a local voltage problem.

## 6. Stage Completeness

Per [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §2.2: every stage in the selected Stage Setting Set must exist in the version, with a target MW and at least one shedding action, before Publication — a structural prerequisite, unconditional.

## 7. Current MW Evaluation and Tolerance Findings

Per [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §7 — the shared ±10% global tolerance, unless a future UFLS-specific override is administratively configured (§4.1 of [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)). No UFLS-specific tolerance logic exists today.

## 8. Publication and Continuous Evaluation

Standard, per [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md) and [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) — no UFLS-specific deviation. A Published UFLS version is continuously re-evaluated against the globally Active operational snapshot; findings accumulate; the version itself never changes automatically.
