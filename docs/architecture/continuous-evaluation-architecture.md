# Continuous Evaluation Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (A1, A6, A7, A8, A12). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md).

Related: [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md), [boundary-pocket-architecture.md](boundary-pocket-architecture.md), [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md), [operational-snapshot-architecture.md](operational-snapshot-architecture.md), [network-model-module.md](network-model-module.md) §8.4 (the existing bounded-recomputation precedent this design generalizes), [engineering-review-panel-architecture.md](engineering-review-panel-architecture.md), [regional-engineering-analytics-architecture.md](regional-engineering-analytics-architecture.md), [engineering-parameter-configuration-architecture.md](engineering-parameter-configuration-architecture.md) (owns the MW tolerance parameter this engine reads, per [ADR-021](../adr/ADR-021-engineering-parameter-configuration-ownership.md)), [platform-event-architecture.md](platform-event-architecture.md) (the trigger mechanism behind §3 mechanism 1, per [ADR-023](../adr/ADR-023-platform-event-architecture.md)).

**Status update:** [regional-engineering-analytics-architecture.md](regional-engineering-analytics-architecture.md) is a named, precise elaboration of the "current analytics" bullet in §2, below — not a new capability outside this engine's ownership boundary. [engineering-review-panel-architecture.md](engineering-review-panel-architecture.md) is the UX consumer of this engine's findings and evaluation-status surface (§3.1, §6, below) — it visualizes this engine's output and owns none of it.

**Status update ([ADR-019](../adr/ADR-019-boundary-pocket-evaluation-by-connected-component-discovery.md)).** Boundary Pocket re-evaluation ([boundary-pocket-architecture.md](boundary-pocket-architecture.md) §9) is corrected: a structural finding is raised when a Published pocket's evaluation is no longer Boundary Effective (forms no isolated island at all), not merely "no longer complete" in the old inside/rest-of-grid sense; a composition finding is raised when the boundary remains effective but its derived isolated-island substation set(s) differ from the `PublicationRecord`'s captured baseline — including an island merging, splitting, or its membership changing. This document's own evaluation-cycle description (§5, below) is otherwise unaffected — only the specific Boundary Pocket finding conditions are corrected.

**Status update (Shared Platform Sprint 5, 2026-07-16).** Synchronous Continuous Evaluation core, the explicit detector framework (ADR-022), and the MW tolerance detector (§7) are implemented (`backend/app/modules/continuous_evaluation/`), reading the approved tolerance through Engineering Parameter Configuration's own service interface. This is mechanism 2 of §3 only: on-demand synchronous evaluation. Background event-driven refresh (mechanism 1, ADR-023) and the disposable cached-projection mechanism (§3.1, mechanism 4) remain unimplemented — no persistence was added this sprint, since no consumer or measured performance need for a cache exists yet, consistent with CLAUDE.md §21. No other detector is implemented; no real scheme module (UFLS/UVLS/EMLS) integration exists yet.

**Status update (Shared Platform Sprint 6, 2026-07-16).** Background refresh foundation, disposable Evaluation Projection, and platform-event consumer contracts implemented; source-module event emission and non-MW detectors remain pending. Mechanism 1 (§3: event-driven background recalculation) and mechanism 4 (§3.1: disposable cached projections) are now implemented — `continuous_evaluation_projection` (Alembic `0021_evaluation_projection`), with exactly the four documented statuses (`Current`/`Stale`/`Recalculating`/`Failed`) and the generation-based concurrency safeguard needed so a newer invalidation arriving mid-recalculation can never produce a false `Current` state. Every refresh, synchronous or background, still calls the identical Sprint 5 `evaluate()` core — no detector logic is duplicated. `EvaluationRequestProvider` and `AffectedSchemeResolver` are typed seams with test fakes only (no real scheme module exists yet to supply a real implementation of either). No source module yet calls `notify_source_data_changed` (ADR-023's own producer list, platform-event-architecture.md §3) — that integration is later work.

---

## 1. Purpose

The Continuous Evaluation Engine is the shared capability that keeps every Draft and Published Defence Scheme Version's derived data — current MW, allocation deviation, ALSF findings, Sensitive Customer findings, topology findings, Boundary Pocket validity and composition, current analytics — current, without ever becoming a second source of engineering truth for any of it.

## 2. Ownership Boundary

**The Evaluation Engine owns no authoritative engineering data.** It derives, on demand and continuously:

- current MW (per assignment, per stage/priority group, per version);
- allocation deviation against target MW (§7, below);
- ALSF findings;
- Sensitive Customer findings;
- topology findings;
- Boundary Pocket validity (structural finding) and composition change (composition finding), per [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §9;
- current analytics, including Regional Engineering Analytics ([regional-engineering-analytics-architecture.md](regional-engineering-analytics-architecture.md)) — informational only, never a finding source (see that document §8);
- current publication-review findings (fed into [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)).

**Assignments never disappear automatically because a source fact changes.** They remain assigned and become findings — the same non-negotiable principle stated in [scheme-engineering-principles.md](scheme-engineering-principles.md) §6, restated here as the Evaluation Engine's own operating constraint, not merely a UX guideline.

## 3. Hybrid Evaluation Model

Four complementary mechanisms, none of which substitutes for another:

1. **Event-driven background recalculation when source data changes** — a source-module write (a PSS/E import activation, a registry correction, an ALSF status change) triggers a background refresh scoped to affected, currently-relevant Scheme Versions (Draft and Published — unlike [`network-model-module.md`](network-model-module.md) §8.4's own precedent, which scopes recomputation to non-terminal assignments only, this pack's evaluation must also cover Published versions, since Continuous Validation applies to them too, per [scheme-engineering-principles.md](scheme-engineering-principles.md) §5). The trigger mechanism itself — a direct in-process call to `notify_source_data_changed`, enqueuing one idempotent, full-recompute background job on the existing Redis/RQ queue — is now fully decided by [ADR-023](../adr/ADR-023-platform-event-architecture.md); see [platform-event-architecture.md](platform-event-architecture.md) for the complete design. No new event-bus/pub-sub mechanism is introduced.
2. **On-demand evaluation when a Draft is opened or edited** — synchronous, live recomputation for the Engineering Workspace's own continuously-updated findings/totals ([engineering-workspace-architecture.md](engineering-workspace-architecture.md) §3, §6).
3. **Mandatory fresh evaluation during publication review** — re-run unconditionally at the moment of Publish, per [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md)'s Publication Prerequisites, regardless of how recently an on-demand or background evaluation last ran — the single point where staleness must be structurally impossible.
4. **Disposable cached projections for performance** — an evaluation result may be cached to avoid redundant recomputation, but every cache is explicitly non-authoritative and regenerable.

### 3.1 What a cache identifies

An evaluation cache/projection should identify, as appropriate:
- scheme version;
- evaluation snapshot (`topology_version_id`/`load_snapshot_id`, per [operational-snapshot-architecture.md](operational-snapshot-architecture.md));
- evaluation timestamp;
- source revision or watermark (whatever upstream data version it was computed against);
- status: `Current`, `Stale`, `Recalculating`, `Failed`;
- pending recalculation, if one has been enqueued but not yet completed.

**Evaluation caches are never authoritative and never part of the engineering decision itself** — mirroring exactly [`network-model-module.md`](network-model-module.md) §5's own existing "connectivity graph is not a persisted engineering entity" design note, generalized here to every kind of evaluation cache this pack introduces.

### 3.2 Decoupling from synchronous source writes

**Do not tightly couple a source module's own write path to a synchronous, full-scheme recalculation.** A Substation Registry correction, an ALSF status change, or a PSS/E import activation must complete on its own terms, at its own module's own speed, without blocking on every Defence Scheme Version that might be affected being fully re-evaluated first. Event-driven background recalculation (§3, mechanism 1) exists precisely so source-data updates and scheme evaluation remain decoupled in time, consistent with [`network-model-module.md`](network-model-module.md) §8.4's own already-validated reasoning.

### 3.3 Detector Framework

**Resolved by [ADR-022](../adr/ADR-022-continuous-evaluation-detector-framework.md):** `evaluateFindings(scheme_version_id, evaluation_snapshot)` ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §11) fans out internally to a set of independent, explicitly-registered detector components — never a single method with one hardcoded branch per finding type. Each detector implements a uniform interface (`detector_id`, `applicable_scheme_types`, `detect(context) -> list[Finding]`), is registered once at bootstrap (mirroring the existing Permission-registration pattern in every module's own `bootstrap.py`), and is independent of every other detector's result. Every finding source this document names in §2 — MW tolerance, ALSF, Sensitive Customer, topology, Boundary Pocket structural, Boundary Pocket composition — is one registered detector; a future finding source (a new scheme type's own detector, a future Critical Infrastructure detector once that module exists) is added the same way, with no change to `evaluateFindings`'s own orchestration logic. See [ADR-022](../adr/ADR-022-continuous-evaluation-detector-framework.md) for the full interface, registration, and execution-order design.

## 4. Published Versions

Published versions are always evaluated against the globally Active operational snapshot — see [operational-snapshot-architecture.md](operational-snapshot-architecture.md) and the Active-Snapshot Verification finding in this pack's [Codex Foundation-Readiness Audit Brief](codex-foundation-readiness-audit-brief.md) (confirmed, from PSS/E Integration's actual implementation, to already provide exactly this: a single globally "Current" `TopologyVersion`/`LoadSnapshot`, atomically superseding the prior one on activation).

When the global Active snapshot changes:
- assignments remain unchanged;
- current MW is recalculated;
- Boundary Pocket composition is recalculated;
- findings are recalculated;
- the scheme remains Published;
- the application raises findings where the current evaluation no longer meets engineering expectations (an out-of-tolerance MW deviation, a Boundary Pocket that is no longer Boundary Effective, a lost ALSF capability, a new Sensitive Customer association).

None of this alters the Published version's own stored assignment data — the exact same "operational data must never silently alter engineering assignments" principle stated throughout this pack.

## 5. Draft Versions

A Draft is a **user-scoped Engineering Workspace** (per [engineering-workspace-architecture.md](engineering-workspace-architecture.md) §2):

- A Draft may select its own evaluation snapshot without changing the global Active snapshot — a per-user, per-Draft selection, never a platform-wide side effect.
- The Draft retains that selected evaluation snapshot until the engineer explicitly changes it — it is not silently reset to Current on every page load.
- The engineer may compare multiple snapshots side by side (e.g. peak-demand vs. off-peak, mirroring 01-engineering-philosophy.md §5 Step 2's own description of engineers selecting different reference snapshots for different studies).
- **Draft snapshot selection is evaluation context only; it is never part of the authoritative Published scheme assignment.** A Published version never retains a private Draft snapshot as its own operational basis — Publication always evaluates against, and captures baseline data from, the globally Active snapshot at the moment of Publish (§4, and [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md)'s mandatory fresh evaluation), regardless of what snapshot the Draft happened to be viewed against beforehand.

## 6. UX Requirement for Stale Evaluation

**The UX must never present stale results as current.** Every relevant evaluation view must show:
- snapshot used;
- evaluation timestamp;
- current/stale/recalculating status;
- reason for staleness, where known (e.g. "a new operational snapshot has been activated since this evaluation ran");
- a refresh/recalculate action;
- whether Publication review is currently permitted (i.e. whether a mandatory fresh evaluation has run and structural prerequisites are satisfied, per [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md)).

Example intent, illustrative only:

> Operational snapshot changed. This version was evaluated using Snapshot A. Snapshot B is now active. Displayed MW values and findings may be outdated.

**Publication always forces a fresh evaluation**, per §3 mechanism 3 — a stale cache can never be Published against, regardless of what the UI last displayed.

**A brief "Recalculation pending" state is acceptable, and preferable to blocking source-data updates.** A Substation Registry correction or a PSS/E import activation should never be delayed waiting for every affected Scheme Version's evaluation to finish recomputing first (§3.2) — a short window where an evaluation view shows `Recalculating` is the correct, honest trade-off, never hidden from the engineer.

## 7. MW Evaluation and Tolerance

Actual (current) MW is always derived from the applicable evaluation snapshot — never stored as the ongoing source of truth for a Draft, and never stored anywhere within Scheme Data, at any time. At Publication, the MW evaluation that supported the decision is captured once, immutably, as Publication Evidence within that Publication's own `PublicationRecord` ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §2) — never as a field on the Scheme Version, stage, or assignment itself (per each assignment kind's own capture rule in [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §3; the full Scheme Data / Publication Record distinction is stated in [scheme-engineering-principles.md](scheme-engineering-principles.md) §11).

The **global engineering tolerance** is initially:

```text
±10% of target MW
```

For each stage or priority group:

```text
deviation_percentage = (actual_mw - target_mw) / target_mw × 100
```

**Finding behaviour:**
- below −10%: under-allocation finding;
- between −10% and +10% inclusive: within tolerance, no finding;
- above +10%: over-allocation finding.

**The tolerance produces findings only. It does not automatically block Publication** — Publication treatment for an out-of-tolerance finding is governed entirely by [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)'s policy layer, never hardcoded into the tolerance check itself.

### 7.1 Where the tolerance configuration lives

**Resolved by [ADR-021](../adr/ADR-021-engineering-parameter-configuration-ownership.md):** the tolerance is **global engineering configuration**, versioned engineering parameter data (CLAUDE.md A7) — owned by the standalone Engineering Parameter Configuration module ([engineering-parameter-configuration-architecture.md](engineering-parameter-configuration-architecture.md)) as the `mw_tolerance_percentage` parameter, read by the MW tolerance detector ([ADR-022](../adr/ADR-022-continuous-evaluation-detector-framework.md)) through that module's own read service interface — never hardcoded independently across scheme modules, and never a local table owned by this engine itself. It is the same category of data as, e.g., a future validated-range bound for a frequency or voltage threshold, per [`ufls-module.md`](ufls-module.md) §10/§18's own existing recommendation that such bounds be stored, not hardcoded — each such future bound is a further parameter in the same shared module, not a new configuration surface per scheme type.

### 7.2 Auditability of tolerance changes

Every change to the tolerance value is audited — who, when, old/new value, why (CLAUDE.md §5.4, A7). Consistent with [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)'s own policy-change audit requirements, a tolerance change applies only to **future** evaluations; it never retroactively recomputes or reinterprets a historical Publication's own findings, which remain exactly as they were computed and recorded at the time (CLAUDE.md §5.2). A Scheme Version's own historical assignment data is entirely unaffected by any future tolerance change — only what counts as "within tolerance" for a *new* evaluation changes.
