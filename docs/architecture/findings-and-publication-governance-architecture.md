# Findings and Publication Governance Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (A1, A4, A6, A7, A8, A10). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md). Realizes [ADR-018](../adr/ADR-018-findings-severity-and-publication-governance-separation.md) — read that ADR first for the decision rationale.

Related: [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md), [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md), [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) (formally superseded in governance mechanism, not in underlying detection logic — see §9), [critical-infrastructure-module.md](critical-infrastructure-module.md) §7.4 (unaffected — consumed, not replaced), [engineering-review-panel-architecture.md](engineering-review-panel-architecture.md).

**Status update:** the [Engineering Review Panel](engineering-review-panel-architecture.md) is the UX surface built on §10's `scheme-versions/{id}/findings` API and the §6 acknowledgement workflow — it presents this document's findings and treatment data to the engineer, and does not own, compute, or alter any of it.

**Status: Policy Layer and Publication Record foundation implemented (Shared Platform Sprints 3-4); real scheme publication integration and Continuous Evaluation remain pending.** Sprint 3 completed the `Finding` value contract (§2) and the full `PublicationTreatmentPolicy` domain model (§4, §4.2). Sprint 4 adds the immutable `PublicationRecord` aggregate (§2, §2.1, §8) — `publication_record` plus its three frozen-evidence child tables (`publication_record_finding`, `publication_record_prerequisite`, `publication_record_acknowledgement`) — a generic, scheme-agnostic `PublicationPrerequisiteResult` contract (`publication.py`) realizing §5's structural prerequisites without this module knowing any scheme module's own table structure, and `PublicationRecordService.evaluate_and_record_publication` — this sprint's own realization of §11's `recordPublication(scheme_version_id, findings, acknowledgements, publisher) → PublicationRecord`, following the exact algorithm this sprint's own instructions specify (validate → reject duplicate event → check prerequisites → resolve policy per finding → reject on Block → verify acknowledgements → freeze evidence → insert, flush only, never commit). A synthetic scheme-version test fixture (`tests/synthetic_scheme.py`) exercises the full flow without any real scheme module existing. Backend module, Alembic migration (`0020_publication_record`), and unit/repository/API test suites are complete and verified on both SQLite and PostgreSQL. **Not yet implemented, and explicitly out of scope:** any real UFLS/UVLS/EMLS Scheme Version entity or publish route, the `scheme-versions/{id}/publish`/`scheme-versions/{id}/findings` routes (§10 — a future scheme module's own concern, calling `evaluate_and_record_publication` in-process, never through this module's own router), the Continuous Evaluation Engine, detector execution, evaluation caching, and platform-event integration (ADR-023) — all remain future sprints. `evaluateFindings` (§11) is likewise not implemented. `resolve_publication_treatment`/`resolve_publication_treatments`/`evaluate_and_record_publication` are in-process service interfaces only — no public HTTP endpoint invokes publication orchestration directly (deliberate; a future scheme module's own Publish action is the only intended caller). Frontend pages are not part of this sprint's scope and remain unbuilt.

---

## 1. Purpose

To provide one governed-findings mechanism, applied uniformly to every kind of finding a Defence Scheme Version can accumulate, separating **what was found and how severe it is** (detection, never configurable) from **what happens at Publication because of it** (policy, administratively configurable and fully audited).

## 2. Owned Concepts

| Concept | Description |
|---|---|
| `Finding` | One detected issue against a specific Scheme Version (or a specific assignment within it) — a source (which detector produced it), a severity, a description, and enough structured context to resolve it (e.g. the affected substation/assignment id). Transient by default (§8), persisted only as part of a Publication record. |
| `PublicationTreatmentPolicy` | The administratively-configured mapping from finding type (and, where applicable, finer per-source-data granularity — e.g. a critical asset's own `restriction_type`) to publication treatment. |
| `PublicationRecord` | The permanent, immutable record of one Publish action — the engineering evidence that supported the decision to publish. **Not Scheme Data** ([scheme-engineering-principles.md](scheme-engineering-principles.md) §11): it is Publication Evidence, owned by this capability, never by the scheme module whose version it documents. |

### 2.1 Publication Record Contents (Illustrative)

A `PublicationRecord` answers one question: *what engineering evidence supported the decision to publish this version?* Its contents are conceptual here, not a schema — field names and storage shape are an implementation decision. Typical evidence includes:

- Publication timestamp and the publishing Administrator;
- the evaluation snapshot identity and timestamp the Publish action evaluated against ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §3 mechanism 3's mandatory fresh evaluation);
- a stage-level (or priority-group-level) evaluation summary — target MW, current MW, deviation, at the moment of Publish;
- a version-level evaluation summary — the same, aggregated;
- a Boundary Pocket baseline, per assigned pocket — the derived substation set and `topology_version_id`, per [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §8;
- an engineering findings summary — every finding present, its severity, and its resolved treatment (§4, below);
- the Publication decision itself, and any override acknowledgements given, with their justifications (§6, below);
- optional free-text Publication notes.

None of this is Scheme Data, and none of it participates in any later evaluation ([scheme-engineering-principles.md](scheme-engineering-principles.md) §11) — it is read only by historical Publication-history views and by Continuous Evaluation's own baseline-diffing (e.g. [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §9), never written back to, never treated as a live source of truth.

## 3. Finding Severity

One of: **Information, Advisory, Warning, Critical.** Assigned by the detector that produced the finding — never by administrative configuration. Detectors, per [scheme-data-consumption-matrix.md](scheme-data-consumption-matrix.md) and [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md):

- MW tolerance deviation (§7 of [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md));
- ALSF capability absence;
- Sensitive Customer association;
- topology/registry change (a referenced substation or Transformer Terminal changed lifecycle state, was corrected, or no longer exists);
- Boundary Pocket structural invalidity or composition change ([boundary-pocket-architecture.md](boundary-pocket-architecture.md) §9);
- cross-scheme protected-assignment overlap (Rule-1-equivalent, via `getProtectedAssignments`, per [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §8);
- critical-infrastructure protection (Rule-2-equivalent, via Critical Infrastructure's `getCriticalityForSubstations`, per [`critical-infrastructure-module.md`](critical-infrastructure-module.md) §13).

Each detector's own severity-assignment logic is its own concern — this document does not prescribe, for example, exactly which MW-deviation percentage yields `Warning` vs. `Critical`; it only requires that every detector classify into this shared four-level scale, so that publication-treatment policy (§4) can be expressed uniformly regardless of source.

**One carried-forward, concrete severity rule, preserved unchanged from [`critical-infrastructure-module.md`](critical-infrastructure-module.md) §7.4:** a substation's `Prohibited` critical asset always yields a `Critical` finding; a `ConditionallyAllowed` asset yields a `Warning` finding carrying the asset's `condition_description`; an `Unrestricted` asset yields no finding. This is detection-time classification, not policy — see §4 for how its *treatment* is now configured.

## 4. Publication Treatment

One of: **Block publication, Allow with mandatory acknowledgement, Allow without acknowledgement.**

- **Global default** per finding type (and, for critical-infrastructure findings, per `restriction_type` — a finer default than a flat per-type default, mirroring the existing per-asset nuance [`critical-infrastructure-module.md`](critical-infrastructure-module.md) §7.4 already established).
- **Optional scheme-specific override** — narrows or widens the default for one scheme type only. The recommended default carried forward from [`emls-module.md`](emls-module.md) §7.7 (`Prohibited` critical-asset findings always `Block`, unweakened for EMLS specifically, given its manual-invocation stakes) is expressed here as the shipped default policy, not as hardcoded, unchangeable business logic — an Administrator could, in principle, weaken it later, but doing so is now an audited, deliberate, reviewable policy action (§4.1), not a silent code change.
- **Fully audited** — every policy change records the previous treatment, the new treatment, the administrator, the timestamp, and a **non-empty reason**.
- **Applies to future Publication attempts only** — a historical Publication decision retains the policy that applied at the time it was made (§6).
- **Findings remain visible for as long as they remain true**, independent of any policy change — a policy change never hides or resolves an existing finding.

### 4.1 Who may change publication treatment policy

An elevated, admin-tier IAM permission, distinct from the Editor/Approver-tier permissions that govern ordinary scheme design and Publication itself — mirroring the same elevated-tier reasoning already established for `ComplianceRuleConfig` changes in [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) and for Critical Infrastructure's own write access in [`critical-infrastructure-module.md`](critical-infrastructure-module.md) §15.

### 4.2 Initial Publication Treatment Policy (Shipped Defaults)

This platform ships with exactly one policy dimension pre-configured: **default treatment keyed by finding severity.** This is the authoritative initial `PublicationTreatmentPolicy` table — every default below is either a fact already established elsewhere in this architecture pack (carried forward unchanged) or a baseline convention this decision adopts now, and each row states which. No per-finding-type or per-source default is shipped beyond what these four severity-keyed rows already produce, since §3 deliberately reserves severity assignment (including which specific condition within a detector yields which severity) to each detector's own logic, not to this document — a per-type table would either duplicate that detector logic here or contradict it, both undesirable.

| Severity | Default publication treatment | Provenance |
|---|---|---|
| **Critical** | **Block** | **Carried forward.** The one concrete default this pack already states explicitly (§3, §4): a `Prohibited` critical asset (§3's own worked example) always yields a `Critical` finding, and that finding always blocks Publication, unweakened even for EMLS ([`emls-module.md`](emls-module.md) §7.7). This row generalizes that already-shipped rule to every `Critical`-severity finding regardless of source — consistent, not new, since every detector already treats `Critical` as reserved for findings serious enough that Publication should not proceed without correction or a deliberate, audited policy change (§3's own "so that publication-treatment policy can be expressed uniformly regardless of source"). |
| **Warning** | **Allow with mandatory acknowledgement** | **Baseline convention, adopted by this decision.** A `Warning`-severity finding (e.g. a `ConditionallyAllowed` critical asset, §3) is real and must be consciously seen and accepted by the publishing Administrator, but is not, by itself, a reason a version cannot be published — this is exactly the purpose §4 already defines the "Allow with mandatory acknowledgement" tier for. |
| **Advisory** | **Allow without acknowledgement** | **Baseline convention, adopted by this decision.** Informative context for the publishing Administrator and for anyone reviewing the version's findings, not serious enough to require an explicit acknowledgement gesture on every Publish. |
| **Information** | **Allow without acknowledgement** | **Baseline convention, adopted by this decision.** Same reasoning as Advisory, at a lower severity still. |

**This table is the shipped default only, not a ceiling on future refinement.** The existing override mechanism (§4: scheme-specific override; a future finer per-restriction-type or per-source override, should one become genuinely justified) remains fully available without further redesign — this decision deliberately does not pre-populate any such override, since none is justified by anything in today's architecture (per this task's own constraint against inventing engineering rules). If a future finding source's own engineering characteristics genuinely warrant a treatment different from its assigned severity's baseline (e.g. a specific `Warning`-severity condition that should `Block` for one scheme type only), that is expressed as a scheme-specific override at implementation time, per §4, itself audited per §4/§12 — not by amending this baseline table.

**Structural Publication Prerequisites (§5) are unaffected and remain outside this policy entirely** — they have no severity and are never findings, so no row of this table applies to them.

## 5. Structural Publication Prerequisites (outside this policy entirely)

Per [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md): missing scheme identity; a missing or non-Published required Stage Setting Set; incomplete stage/priority-group structure; missing target MW; a stage/priority-group with no shedding action; an invalid or incomplete Boundary Pocket; a broken authoritative reference; inability to perform the mandatory fresh publication evaluation.

**These are never findings.** They have no severity, no publication-treatment policy, and cannot be acknowledged. A version in this condition is not yet a coherent engineering record — Publication is structurally unavailable until it is corrected, for every Administrator, unconditionally.

## 6. Acknowledgement

When a finding's applicable treatment is `Allow with mandatory acknowledgement`:

1. The publishing Administrator reviews the grouped findings — grouped sensibly (by stage/priority group, by rule/source, or by severity), never as an undifferentiated flat list for a version with many findings.
2. Individual supporting evidence for any group remains expandable on demand.
3. Explicit confirmation is required, per finding group.
4. A free-text justification is mandatory, non-empty.
5. The `PublicationRecord` permanently stores: findings present, their severities, the treatment applied to each, the publisher, the timestamp, and the justification.

**Acknowledgement never resolves or downgrades the finding itself** — it remains exactly as severe, and exactly as visible, in every future evaluation, whether or not it was ever acknowledged at a past Publication (§4).

**Only Administrators may publish** — the elevated tier applies to the Publish action itself, not only to policy changes (§4.1).

## 7. What Blocks vs. What Does Not

| Condition | Treatment |
|---|---|
| Structural publication prerequisite unmet (§5) | Always blocks — unconditional, not configurable |
| Finding with `Block` treatment | Blocks, until the underlying condition is corrected or the applicable policy is changed (an audited administrative action) |
| Finding with `Allow with mandatory acknowledgement` treatment | Does not block, but requires acknowledgement (§6) before Publish proceeds |
| Finding with `Allow without acknowledgement` treatment | Does not block, no acknowledgement required, remains visible in the version's own findings list |

## 8. Persistence Model

**Draft-time findings are computed live and are not persisted** — mirroring [`cross-scheme-compliance-module.md`](cross-scheme-compliance-module.md) §8's own existing "Draft-time advisory checks are the one exception, and are deliberately not persisted at all" reasoning, generalized here to every finding type, not only Rule 1/2. Recomputing on demand avoids unbounded low-value historical noise from every keystroke-adjacent Draft edit.

**A `PublicationRecord`, once created, is permanent and immutable** — every finding present at that Publish action, its severity, the treatment applied, and any acknowledgement given are frozen exactly as they were at that moment, forever (CLAUDE.md §5.2), regardless of any later policy change or any later correction to the underlying condition.

**Findings against a Published version, computed by Continuous Evaluation after Publication (§4 of [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md)), are live, not persisted the same way** — they represent the version's *current* standing, re-evaluated continuously, and are not retroactively added to the original `PublicationRecord` (which remains a snapshot of the moment of Publish specifically).

## 9. Relationship to ADR-004 and Cross-Scheme Compliance

[ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)'s own Rule 1/Rule 2 **detection logic** — comparing `getProtectedAssignments` results across schemes for overlap (Rule 1), and cross-referencing against Critical Infrastructure's `getCriticalityForSubstations` (Rule 2) — is fully preserved and reused, unchanged, as two of this document's own detectors (§3). What is superseded is [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)'s own **governance mechanism**: a dedicated `ComplianceRuleConfig`/`ComplianceCheckRun`/`ComplianceFinding` module, gating specifically at Submit-for-Review/Approval/Activation (a three-checkpoint model that no longer exists under [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md)'s single-Publish-gate lifecycle), with its own bespoke `enforcement_mode` severity model. Under this document's model, Rule 1/2 findings are two detector sources among several, governed by the same single publication-treatment policy layer as every other finding type, gated once, at Publish. A dedicated Cross-Scheme Compliance *module* — as its own bounded context, still worth keeping (it observes across schemes without owning any of their data, exactly as [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) itself reasoned) — remains the natural home for the Rule 1/2 *detection* logic specifically (the fan-out to every scheme module's `getProtectedAssignments`, the cross-referencing against Critical Infrastructure); it simply no longer owns its own separate gating/severity machinery, which this document's shared mechanism now provides instead.

## 10. API Contract (Concept)

- `scheme-versions/{id}/findings` — read-only, live, grouped and filterable by severity/source; the Engineering Workspace's own continuous-findings surface.
- `scheme-versions/{id}/publish` — the Publish action; request includes acknowledgement confirmations and justifications for any `Allow with mandatory acknowledgement` findings present; returns either success (with the created `PublicationRecord`) or a structured rejection naming the unmet structural prerequisite or unacknowledged `Block`-treatment finding.
- `publication-treatment-policies` — read (broad), update (admin-tier only, §4.1), with full audit trail exposed.
- `scheme-versions/{id}/publication-records` — read-only, historical, immutable.

## 11. Service Interfaces

Exposes:
- `evaluateFindings(scheme_version_id, evaluation_snapshot) → Finding[]` — the shared entry point every Defence Scheme module's Engineering Workspace and Continuous Evaluation Engine call, fanning out internally to every applicable detector.
- `resolvePublicationTreatment(finding) → treatment` — resolves a finding's current applicable policy (global default, scheme-specific override, or per-asset override where applicable).
- `recordPublication(scheme_version_id, findings, acknowledgements, publisher) → PublicationRecord`.

Consumes, from other modules' service layers, never repositories directly: every Defence Scheme module's `getProtectedAssignments`; Critical Infrastructure's `getCriticalityForSubstations`; the Automatic Load Shedding Functionality Registry's capability interfaces; the Sensitive Customer Registry's association interfaces; [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md)'s MW/topology/Boundary-Pocket evaluation surface; Core Platform/IAM for authorization and audit attribution.

## 12. Audit Requirements

- Every `PublicationTreatmentPolicy` change is audited (not merely logged) — a human policy decision, per §4.
- Every `PublicationRecord` is retained permanently, immutable once created — full historical reproducibility of what was found, what treatment applied, and what was acknowledged, at the exact moment of every Publish action.
- A scheme module's own audit log records the Publication event itself (who published, when) alongside a pointer to the `PublicationRecord`, mirroring the existing traceability-pointer pattern used throughout this architecture series (e.g. `source_load_snapshot_id`).
- Audit log access is itself access-controlled (CLAUDE.md A10).

## 13. Security Considerations

- All GridDefence engineering data, including findings and publication records, is sensitive by default (CLAUDE.md A10); TLS required outside local development.
- Requesting findings (`evaluateFindings`) requires no elevated permission beyond whatever permission the calling scheme module's own Draft-editing action already requires.
- Changing `PublicationTreatmentPolicy` and performing the Publish action itself both require an elevated, admin-tier permission (§4.1, §6) — distinct from ordinary Editor-tier scheme design permission.
- A finding referencing critical-infrastructure detail may carry the same heightened sensitivity Critical Infrastructure applies to its own data ([`critical-infrastructure-module.md`](critical-infrastructure-module.md) §15) — recommend the same restricted read tier apply to that specific finding category.

## 14. Testing Requirements

Per CLAUDE.md §18/A11: severity assignment correctness per detector, independent of any policy configuration; publication-treatment resolution correctness (global default, scheme-specific override, per-asset override precedence); structural-prerequisite blocking is unconditional and never affected by any policy setting; acknowledgement requires non-empty justification and does not alter the underlying finding; `PublicationRecord` immutability; a policy change never retroactively alters a historical `PublicationRecord`'s own stored treatment.

## 15. Future Extensions

- Per-scheme-pair cross-scheme overlap policy granularity (carried forward, unresolved, from [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) Open Question 1) — this document's policy model already supports this without further redesign, since policy is keyed by finding type/source, which can be refined to include the comparison scheme.
- Additional cross-scheme rules beyond Rule 1/2, as future scheme types (SPS/RAS) surface new cross-scheme concerns — new detectors, same governance mechanism, no redesign required ([ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)'s own "Future Support for SPS/RAS" reasoning, unaffected).
