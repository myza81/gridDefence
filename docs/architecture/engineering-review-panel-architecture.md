# Engineering Review Panel Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (A1, A6, A8, A12). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md).

Related: [engineering-workspace-architecture.md](engineering-workspace-architecture.md), [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md), [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md), [regional-engineering-analytics-architecture.md](regional-engineering-analytics-architecture.md), [boundary-pocket-architecture.md](boundary-pocket-architecture.md).

Origin: an engineering-discovery review of the legacy Grid Defence MVP identified an in-app "Design Rules Reference" checklist as a mature, validated idea worth strengthening. This document does not carry that concept forward as a static rule list — it elevates it into a first-class architectural concept, the **Engineering Review Panel**, per the Project Owner's explicit direction. No prior document in this repository used the phrase "Engineering Design Rules"; this document introduces the Engineering Review Panel directly, with no rename required.

---

## 1. Purpose

The Engineering Review Panel is the primary UX representation of the Evaluation Engine. Its purpose is to continuously present an engineer with the current engineering health of a Scheme Version — structural integrity, assignment integrity, every current finding, and Publication readiness — in one place, so the engineer never has to search multiple pages to understand whether the scheme is healthy.

It is not a validation checklist and not merely a warning list. It is the engineering review workspace: every finding it presents links directly back to the engineering object that produced it, turning review into navigation, not just observation.

## 2. Scope

The Engineering Review Panel is not a new bounded context and owns no persisted data of its own — exactly as the [Engineering Workspace](engineering-workspace-architecture.md) and [Boundary Pocket](boundary-pocket-architecture.md) capabilities are architecture, not modules. It is the shared panel shape every Defence Scheme module's own Engineering Workspace presents, built entirely by composing data other modules already own and compute:

- structural Publication prerequisites ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §5);
- Findings, grouped and filtered ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §2–§3);
- evaluation status/staleness ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §3.1, §6);
- Publication treatment and acknowledgement state ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §4, §6).

## 3. Relationship to the Evaluation Engine and Findings

```text
Evaluation Engine
        │  evaluateFindings(scheme_version_id, evaluation_snapshot)
        ▼
Engineering Findings          (owned by Findings and Publication Governance,
                                per finding-source detector — Continuous Evaluation,
                                ALSF, Sensitive Customer Registry, cross-scheme,
                                critical-infrastructure)
        │
        ▼
Engineering Review Panel      (visualizes — owns nothing)
        │
        ▼
Publication Review            (the Administrator's Publish decision,
                                per findings-and-publication-governance-architecture.md §6)
```

**The Engineering Review Panel does not own findings, does not compute them, and does not decide Publication treatment.** It is a read-only composition surface over `evaluateFindings`, structural-prerequisite checks, and evaluation status — exactly as the [Regional Engineering Analytics](regional-engineering-analytics-architecture.md) surface and the [future Dashboard](regional-engineering-analytics-architecture.md#7-recommended-placement-in-the-product) are read-only compositions over their own respective owning modules, per Dashboard's own established "owns no schema, composes read-only interfaces" principle ([`domain-model.md`](domain-model.md) §6, [`implementation-plan.md`](implementation-plan.md) Phase 11).

## 4. Responsibilities

The panel consolidates, for the Scheme Version currently open in the Engineering Workspace:

- **Structural integrity** — every structural Publication prerequisite ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §5): scheme identity, Stage Setting Set completeness, stage/priority-group structure, target MW presence, at least one shedding action per stage/priority group, Boundary Pocket completeness, broken authoritative references.
- **Assignment integrity** — the version-internal cross-cutting rules ([shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §7): no Transformer Terminal simultaneously direct-assigned and pocket-derived; no excluded-ownership substation assigned.
- **Current engineering findings** — every finding currently active against this version, from every detector ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §3): MW tolerance deviation, ALSF capability absence, Sensitive Customer association, topology/registry change, Boundary Pocket structural or composition change, cross-scheme protected-assignment overlap, critical-infrastructure protection.
- **Publication readiness** — whether Publication is currently permitted at all (structural prerequisites met, mandatory fresh evaluation available) and, if so, what acknowledgements a Publish action will require.
- **Operational, topology, snapshot, and MW evaluation status** — current MW per stage/priority group against target MW, deviation percentage, evaluation snapshot identity and timestamp, current/stale/recalculating status ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §3.1, §6).
- **ALSF findings and Sensitive Customer findings** — surfaced with the same shape as every other finding, never a separate, differently-structured sub-panel.
- **Boundary Pocket findings** — structural (incomplete/invalid) and composition (substation set changed) findings ([boundary-pocket-architecture.md](boundary-pocket-architecture.md) §9), each linking back to the specific pocket.
- **Stale evaluation state** — the panel is the canonical place the [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §6 UX requirement ("the UX must never present stale results as current") is satisfied; every section above states clearly whether it reflects a current or stale evaluation.

## 5. Panel Contents and Grouping

Findings are grouped sensibly, per [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §6.1 — by stage/priority group, by source/rule, or by severity — never as a single undifferentiated flat list for a version carrying many findings. The grouping mode is a presentation choice, not an architectural one; the underlying data (finding, severity, source, affected object) is identical regardless of how it is grouped for display.

Individual supporting evidence for any finding or group remains expandable on demand, consistent with the same acknowledgement-review pattern the Publish action itself uses.

## 6. Finding Presentation Contract

Every finding the panel presents carries, at minimum:

- **severity** (Information, Advisory, Warning, Critical — [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §3), unmodified from what the detector assigned;
- **engineering explanation** — human-readable, specific enough to act on (e.g. "still connected to the rest of the grid via substation X," per [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §7);
- **affected object** — the specific assignment, stage/priority group, Boundary Pocket, or substation/Transformer Terminal the finding concerns;
- **navigation back to the relevant engineering object** (§7, below);
- **current evaluation status** — whether the finding reflects the current evaluation snapshot or a stale one, and its applicable Publication treatment where one has been resolved ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §4).

## 7. Navigation Model

The panel is a navigation hub, not merely a warning list. Selecting a finding takes the engineer directly into the part of the Engineering Workspace that can address it:

```text
Finding: Boundary Pocket no longer complete
    → Select Boundary Pocket → Open Pocket Builder (boundary-pocket-architecture.md §7, §9)

Finding: Sensitive Customer detected
    → Select affected assignment → Open Transformer Terminal detail

Finding: Stage 4 below target
    → Select Stage 4 → Open Stage 4 Assignment View
```

The first example always concerns a Boundary Pocket that was Complete when it was committed to the assignment universe and has since drifted out of validity due to a network change ([boundary-pocket-architecture.md](boundary-pocket-architecture.md) §9) — never a pocket that was assignable while Incomplete. A candidate pocket that has not yet reached Complete during construction is Pocket Builder feedback, not yet part of the assignment universe, and therefore not yet a governed finding at all ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §8).

This list is illustrative, not exhaustive — every finding source in §4 above must resolve to a navigable affected object; a finding type that cannot be traced back to a specific engineering object is not yet ready to be surfaced in the panel and should be treated as an implementation gap, not an acceptable panel entry.

## 8. Draft vs. Published Presentation

The same panel shape is presented for both a Draft and a Published version, since Continuous Evaluation already applies to both ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §4, §5):

- For a **Draft**, the panel reflects live, on-demand evaluation against the Draft's own selected evaluation snapshot ([engineering-workspace-architecture.md](engineering-workspace-architecture.md) §3, §6), updating continuously as the engineer edits.
- For a **Published** version, the panel reflects the version's current standing under the globally Active snapshot, re-evaluated continuously ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §4) — distinct from, and never retroactively rewriting, the immutable `PublicationRecord` captured at the moment of Publish ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §2.1, §8).
- Where the two differ in meaning: a Draft's panel additionally surfaces whether Publication is *currently* permitted (§4, above); a Published version's panel has no such action to gate — it exists purely to keep the engineer informed of the version's ongoing engineering standing.

**The panel is exclusively a current-evaluation surface — it never renders a `PublicationRecord`'s own contents directly.** A Published version's panel and its Publication history are two different views over two different kinds of data ([scheme-engineering-principles.md](scheme-engineering-principles.md) §11): the panel always shows what Continuous Evaluation currently finds true; a separate, historical Publication-history view (`scheme-versions/{id}/publication-records`, [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §10) shows what evidence justified each past Publish action. An engineer comparing "is this still valid" against "what did we approve" is necessarily looking at two different screens, not one panel doing both jobs.

## 9. Relationship to Publication Review

Formal Publication review ([engineering-workspace-architecture.md](engineering-workspace-architecture.md) §3, final bullet) is realized concretely as the Engineering Review Panel's own Publication-readiness section (§4, above), presented together with the acknowledgement workflow ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §6) immediately before the Publish action. This does not introduce a new gate beyond the single Publish checkpoint [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md) already defines — it is the same checkpoint, given one first-class, always-available UX home rather than being scattered across separate review screens.

## 10. What the Engineering Review Panel Does Not Do

- It does not compute findings, evaluate MW, evaluate topology, or determine Publication treatment — every one of those remains owned exactly where [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) and [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) already place it.
- It does not perform an authoritative engineering calculation itself (CLAUDE.md A12) — every figure it displays is backend-computed and presented, never computed client-side.
- It does not resolve, acknowledge, or dismiss a finding on the engineer's behalf — acknowledgement remains the explicit, justified, per-finding-group action [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §6 already defines.
- It does not persist findings differently than [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §8 already specifies — Draft-time findings remain unpersisted and recomputed on demand; only a `PublicationRecord` is ever permanent.
- It is not a fifth checkpoint, a second approval gate, or a replacement for the single Publish decision — it is the view an Administrator uses to make that decision, never a decision-maker itself.

## 11. API Contract (Concept)

- `scheme-versions/{id}/review-panel` — read-only, composing `scheme-versions/{id}/findings` ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §10), structural-prerequisite status, and evaluation status ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §3.1) into one response shaped for the panel's grouping and navigation needs. This is a presentation-convenience composition, not a new source of truth — every field it returns is already available individually from its owning capability's own API.
- No write endpoint of its own — the panel triggers existing actions (navigate to Pocket Builder, navigate to Stage Assignment View, the existing acknowledgement/Publish flow) rather than exposing any new mutation.

## 12. Service Interfaces

- Consumes, from other modules' service layers, never repositories directly (CLAUDE.md A1): `evaluateFindings` and `resolvePublicationTreatment` ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §11); the Continuous Evaluation Engine's evaluation-status/staleness surface ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §3.1); each Defence Scheme module's own structural-prerequisite check.
- Exposes no new authoritative service of its own — every consumer of "the panel's data" should, in principle, be able to reconstruct the same information by calling the underlying capabilities directly; the panel exists for UX convenience and consistency, not to become a second interface a future module might mistakenly treat as authoritative.

## 13. Audit Requirements

The panel itself computes and logs nothing new — it triggers no engineering decision on its own. Every audit-relevant event it surfaces a path to (acknowledgement, Publish, Boundary Pocket edit, assignment edit) is already owned and audited by the module that performs it ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §12, [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §12). Viewing the panel is not itself an audit-relevant engineering action, consistent with read-only Draft-time findings review generally.

## 14. Security Considerations

- Viewing the Engineering Review Panel requires no elevated permission beyond whatever permission the calling scheme module's own Draft/Published-version read access already requires — it exposes no data a permitted user could not already see by querying the underlying capabilities directly.
- A finding referencing critical-infrastructure detail carries the same heightened sensitivity Critical Infrastructure applies to its own data ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §13) when surfaced in the panel — the panel does not weaken that restriction by aggregating the finding alongside others.
- All GridDefence engineering data, including panel contents, is sensitive by default (CLAUDE.md A10); TLS required outside local development.

## 15. Testing Requirements

Per CLAUDE.md §18/A11: every finding source in §4 resolves to a correctly-shaped, navigable affected object; grouping (by stage, by source, by severity) produces identical underlying finding data regardless of grouping mode; the panel never presents a stale evaluation as current (§4, §8); the panel correctly reflects Publication-readiness state for both a structurally-blocked version and a fully-clear one; a structural test confirming the panel persists nothing of its own and holds no foreign key into any scheme module's or Findings-and-Publication-Governance's schema.

## 16. Future Extensions

- A cross-version or cross-scheme review surface (e.g. "every currently-Published version with an open Critical finding") is a natural [future Dashboard](regional-engineering-analytics-architecture.md#7-recommended-placement-in-the-product) composition over the same per-version panel data — not designed here, and not required before Phase 6 (UFLS).
- Saved/default grouping preference per engineer is a UX refinement, not an architectural concern, left to whichever module first implements the panel.

## 17. Risks and Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| A future finding source is added to Continuous Evaluation or Findings and Publication Governance without a corresponding navigable affected object | The panel would present an unactionable finding, undermining its "navigation hub" purpose | Treat "resolves to a navigable object" as a review criterion for any new detector, not an afterthought (§7) |
| Grouping/composition logic for `scheme-versions/{id}/review-panel` could be duplicated per scheme module (UFLS, UVLS, EMLS each re-implementing it slightly differently) | Drift risk, mirroring the same risk already flagged for the Publish/findings contract ([shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §8, [codex-foundation-readiness-audit-brief.md](codex-foundation-readiness-audit-brief.md) §1.10) | Implement the composition once, in shared scheme-engine infrastructure, consumed identically by every scheme module — not re-derived per module |
