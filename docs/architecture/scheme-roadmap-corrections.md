# Roadmap and Implementation Plan Corrections

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.2 — historical text preserved, not rewritten). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md).

This document lists every correction this pack requires against [`implementation-plan.md`](implementation-plan.md), [`domain-model.md`](domain-model.md), [`system-overview.md`](system-overview.md), and the module documents it supersedes in part. Per CLAUDE.md §5.2 and this project's own established practice, none of the affected documents' original text is rewritten — each receives a short status note pointing here, added by this pack (§ "Status notes applied," below), leaving the original planning record fully legible as history.

---

## 1. Implementation Plan — Phase 6 (UFLS)

**Current text (unchanged, preserved):** "Selection of Shedding Actions must call `is_ufls_capable`/the candidate-search interfaces... for every candidate bay before it may be selected... a load that cannot be answered 'yes' is not selectable."

**Correction:** per [scheme-engineering-principles.md](scheme-engineering-principles.md) §6 and [ufls-engineering-philosophy.md](ufls-engineering-philosophy.md) §4, lack of ALSF capability must **not** remove a candidate from selection. It remains selectable; selecting it produces a Critical finding, governed by [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md). Phase 6's own acceptance criteria ("a full Draft → Under Review → Approved → Active workflow completes end to end") must also be corrected to the four-state lifecycle ([ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md)): "a full Draft → Published workflow completes end to end, including a Publication review surfacing the applicable findings."

**Also affected:** the `checkCompliance`-against-a-stub-Cross-Scheme-Compliance-client pattern described for Phase 6 is superseded by [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)'s unified findings mechanism (§9 of that document) — a future Phase 6 implementation should stub the cross-scheme detector's data sources (Critical Infrastructure, other schemes' `getProtectedAssignments`) directly, not a separate compliance-module client, since no separate module boundary exists for this concern under this pack's model.

## 2. Implementation Plan — Phase 7 (UVLS) and Phase 8 (EMLS)

Same lifecycle-wording correction as Phase 6 (Draft → Published, not the six-state workflow). Phase 8's own "no ALSF" instruction is unaffected and remains correct, unchanged — EMLS's exclusion was never in question.

## 3. Implementation Plan — Phase 5 (Network Model)

**Current text (unchanged, preserved):** describes `CutSetDefinition`/`IslandAnalysisResult`/`ManualOverride`/`analyzeIsland`/`getEffectiveIsland`/`createManualOverride` as Phase 5's own backend deliverables.

**Correction:** per [`network-model-module.md`](network-model-module.md) §19's own already-existing reconciliation note, Phase 5 as actually executed delivered the static `traverse`-based connectivity model instead, and the island/pocket analysis design remains entirely unbuilt. [ADR-017](../adr/ADR-017-boundary-pocket-assignment-architecture.md) further clarifies that Boundary Pocket construction (this pack's own realization of the "load pocket / boundary identification" future extension [`network-model-module.md`](network-model-module.md) §19.7 already named) does **not** require building the unbuilt `CutSetDefinition`/`IslandAnalysisResult`/`ManualOverride` design at all — it is layered directly on `traverse`. A future roadmap revision should either retire this section's backend-deliverable list as superseded, or explicitly relabel it "available future extension, not required for UFLS/UVLS/EMLS" per [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §15.

## 4. Domain Model — §5 Versioning

**Current text (unchanged, preserved):** "any versioned record in this domain... follows the Canonical Version Lifecycle (CLAUDE.md A3): `Draft → Under Review → Approved → Active → Superseded → Archived`."

**Correction:** superseded for Defence Scheme Version data specifically by [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md) — `Draft → Published → Superseded | Entered in Error`. CLAUDE.md A3 itself, and its applicability to every other versioned entity in the platform, is unaffected.

## 5. System Overview — §8 Future Extensibility

**Current text (unchanged, preserved):** cites [ADR-010](../adr/ADR-010-engineering-decision-support-philosophy.md)'s two-way classification (Approved Engineering Policy → full A3; Engineering Source/Computed Data → lighter lifecycle) as the rule every new versioned entity must apply.

**Correction:** the classification rule itself is unaffected and remains correct guidance for any future module outside the Defence Scheme domain. Within the Defence Scheme domain specifically, [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md) records a third outcome: Defence Scheme Version data remains classified as Approved Engineering Policy, but now follows a simplified four-state realization of that classification rather than the full six-state A3 lifecycle — a scoped, named exception, not a change to the classification rule's own two categories.

## 6. Cross-Scheme Compliance Module

**Current text (unchanged, preserved):** [`cross-scheme-compliance-module.md`](cross-scheme-compliance-module.md) describes a dedicated module owning `ComplianceRuleConfig`/`ComplianceCheckRun`/`ComplianceFinding`, gating at Submit-for-Review/Approval/Activation.

**Correction:** per [ADR-018](../adr/ADR-018-findings-severity-and-publication-governance-separation.md) §9, this module's Rule 1/2 **detection** logic remains valid and reusable as two of [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)'s own detectors; its **governance** mechanism (the three-checkpoint model, the bespoke `enforcement_mode` severity scheme) is superseded by the unified findings/publication-treatment model, gated once, at the single Publish checkpoint [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md) defines.

## 7. Critical Infrastructure Module

**Current text (unchanged, preserved):** [`critical-infrastructure-module.md`](critical-infrastructure-module.md) §7.4's `restriction_type`-to-severity mapping.

**Correction:** none required to the severity mapping itself — fully preserved, per [ADR-018](../adr/ADR-018-findings-severity-and-publication-governance-separation.md) §3. Only the reference to [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)'s own `enforcement_mode` as the governing policy layer is superseded (now [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)'s publication-treatment policy).

## 8. Architecture Gaps Table (Implementation Plan, tail section)

The existing "Architecture Gaps That Must Be Resolved Before Implementation Begins" table should gain the following new rows at its next revision (not added here, since that table is itself part of the preserved historical planning record — recorded here for whoever next revises it):

| Item | Blocking? | Notes |
|---|---|---|
| `Superseded → Published` reactivation (restated from the six-state model's own unresolved `Superseded → Active` question) | Not blocking | Forward-only lifecycle works without it; remains an explicitly open question under the four-state model too |
| `EquipmentTopologyMap` per-terminal correlation granularity verification | **Should be resolved before Boundary Pocket implementation begins** | [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §6/§16 — required for per-`CircuitTerminal` opening-point resolution; unverified against the actual PSS/E Integration implementation |
| "Rest of grid" reference substation configuration | **Should be resolved before Boundary Pocket implementation begins** | [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §7/§16 — no default is specified anywhere in the architecture |
| Rule 2 no-weakening policy for EMLS — formal ratification | Not blocking | Restated, unresolved, from [`emls-module.md`](emls-module.md) §18; [ADR-018](../adr/ADR-018-findings-severity-and-publication-governance-separation.md) formalizes the *mechanism*, not this values question |
| ~~Default `PublicationTreatmentPolicy` table (beyond the one carried-forward default)~~ — **Resolved** | Not blocking (resolved) | [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §4.2, added by the Shared Platform Architecture Finalization (2026-07-15) — a severity-keyed baseline table (Critical → Block; Warning → Allow with acknowledgement; Advisory/Information → Allow without acknowledgement), carrying forward the one previously-shipped default and adding no invented per-source rule beyond it |
| ~~Stage Setting Set module ownership~~ — **Resolved** | Not blocking (resolved) | [ADR-020](../adr/ADR-020-stage-setting-registry-as-standalone-shared-module.md) — standalone Stage Setting Registry module, added by the Shared Platform Architecture Finalization (2026-07-15) |
| ~~Engineering Parameter Configuration home~~ — **Resolved** | Not blocking (resolved) | [ADR-021](../adr/ADR-021-engineering-parameter-configuration-ownership.md) — standalone module, realizing CLAUDE.md A7, added by the Shared Platform Architecture Finalization (2026-07-15) |
| ~~Continuous Evaluation detector code structure~~ — **Resolved** | Not blocking (resolved) | [ADR-022](../adr/ADR-022-continuous-evaluation-detector-framework.md) — registered, independent detector components, added by the Shared Platform Architecture Finalization (2026-07-15) |
| ~~Source-module-to-Evaluation-Engine trigger mechanism~~ — **Resolved** | Not blocking (resolved) | [ADR-023](../adr/ADR-023-platform-event-architecture.md) — existing Redis/RQ infrastructure confirmed sufficient, added by the Shared Platform Architecture Finalization (2026-07-15) |

## 9. Status Notes Applied by This Pack

The following documents receive a short, additive status note (not a rewrite) pointing to this pack, as part of this task's own deliverables:

- [`ufls-module.md`](ufls-module.md), [`uvls-module.md`](uvls-module.md), [`emls-module.md`](emls-module.md) — §7–§8 superseded, pointer to [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) and the scheme-specific philosophy documents.
- [`cross-scheme-compliance-module.md`](cross-scheme-compliance-module.md) — governance mechanism superseded, pointer to [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md).
- [`network-model-module.md`](network-model-module.md) — pointer clarifying Boundary Pocket construction's relationship to §19's `traverse` and §1–§18's unbuilt design.
- [`domain-model.md`](domain-model.md) §5 — pointer to [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md).
- [`system-overview.md`](system-overview.md) §8 — pointer clarifying the scoped exception to [ADR-010](../adr/ADR-010-engineering-decision-support-philosophy.md)'s classification rule.
- [`implementation-plan.md`](implementation-plan.md) Phases 5–8 — pointer to this document.
- [`docs/architecture/README.md`](README.md) — index entries added for every new document in this pack.

## 10. Status Notes Applied by the Shared Platform Architecture Finalization (2026-07-15)

The following documents received a short, additive status note or a scoped section addition (not a rewrite) as part of resolving the remaining Shared Platform platform-level decisions ([ADR-020](../adr/ADR-020-stage-setting-registry-as-standalone-shared-module.md) through [ADR-023](../adr/ADR-023-platform-event-architecture.md)):

- [`stage-setting-set-architecture.md`](stage-setting-set-architecture.md) — §12's own "left open, not resolved here" audit-ownership language resolved in place; module ownership note added; §11 clarified to name the owning module.
- [`continuous-evaluation-architecture.md`](continuous-evaluation-architecture.md) — new §3.3 Detector Framework; §7.1 updated to point at the resolved Engineering Parameter Configuration home; §3 mechanism 1 updated to point at the resolved trigger mechanism.
- [`findings-and-publication-governance-architecture.md`](findings-and-publication-governance-architecture.md) — new §4.2 Initial Publication Treatment Policy (Shipped Defaults).
- [`scheme-engineering-principles.md`](scheme-engineering-principles.md) — pack index and governing-decisions list extended; a new status note added alongside the existing Architecture Freeze note.
- [`scheme-data-consumption-matrix.md`](scheme-data-consumption-matrix.md) — new §9 (Stage Setting Registry) and §10 (Engineering Parameter Configuration).
- [`codex-foundation-readiness-audit-brief.md`](codex-foundation-readiness-audit-brief.md) — §1.2 and §1.13 status notes resolving their own previously-open questions; §3's ratified-ADR range extended.
- This document (§8, above) — five rows of the Architecture Gaps table marked resolved.
- Two new documents created: [`engineering-parameter-configuration-architecture.md`](engineering-parameter-configuration-architecture.md), [`platform-event-architecture.md`](platform-event-architecture.md), [`shared-platform-dependency-diagram.md`](shared-platform-dependency-diagram.md).
- [`docs/architecture/README.md`](README.md) — index entries added for every new document from this finalization pass.
