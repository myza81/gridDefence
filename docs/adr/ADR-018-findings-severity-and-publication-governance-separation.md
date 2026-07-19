# ADR-018: Findings Severity and Publication Governance Separation

- **Status:** Accepted — Policy Layer and Publication Record foundation implemented (Shared Platform Sprints 3-4); real scheme publication integration and Continuous Evaluation remain pending
- **Date:** 2026-07-12
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.4, §5.5, A7, A10, A13)
- **Depends on:** [ADR-015](ADR-015-defence-scheme-version-lifecycle-simplification.md) (this ADR's single Publish gate is what publication treatment attaches to), [ADR-010](ADR-010-engineering-decision-support-philosophy.md), [EDR-004](../engineering/edr/EDR-004-decision-support-not-automation.md)
- **Affects:** [docs/adr/ADR-004-cross-scheme-compliance-mechanism.md](ADR-004-cross-scheme-compliance-mechanism.md) (receives a formal addendum note — see Consequences; not superseded, its Rule 1/2 *detection* logic is subsumed, not discarded), [docs/architecture/cross-scheme-compliance-module.md](../architecture/cross-scheme-compliance-module.md) §8, §9 (status note), [docs/architecture/critical-infrastructure-module.md](../architecture/critical-infrastructure-module.md) §7.4 (unaffected — this ADR consumes, not changes, its per-asset `restriction_type` signal)
- **Informed by:** six Project Owner engineering-discovery workshops on Defence Scheme governance

---

## Context

[ADR-004](ADR-004-cross-scheme-compliance-mechanism.md) designed Cross-Scheme Compliance's Rule 1/Rule 2 enforcement around a single `ComplianceRuleConfig.enforcement_mode` (`Disabled | Warn | Block`) per rule, refined by [`critical-infrastructure-module.md`](../architecture/critical-infrastructure-module.md) §7.4's per-asset `restriction_type` (`Prohibited` always yields `Block`; `ConditionallyAllowed` yields `Warn` with a condition; `Unrestricted` yields nothing). This conflates two questions into one field: *how severe is this finding* and *what should happen at Publication because of it*. It also exists only for cross-scheme checks — there is no equivalent model for a single scheme's own internal findings (e.g. MW tolerance deviation, ALSF capability absence, Sensitive Customer association, Boundary Pocket composition change), each of which the six workshops require to be treated the same way.

The six workshops concluded that finding severity and publication treatment must be two independent, separately-configured axes, applied uniformly to every kind of finding a scheme version can accumulate — not a cross-scheme-only mechanism with its own bespoke severity model.

## Decision

**Every finding a Defence Scheme Version accumulates — regardless of source (MW tolerance, ALSF capability, Sensitive Customer association, topology change, Boundary Pocket composition change, cross-scheme overlap, critical-infrastructure protection) — carries exactly one severity, assigned by the Evaluation Engine that detected it, and is subject to exactly one publication treatment, assigned by administrative policy. The two are never the same field.**

### Finding severity (detection-time, not configurable)

One of: **Information, Advisory, Warning, Critical.** Severity is computed by whichever evaluation logic detected the finding (MW tolerance math, ALSF's own capability answer, Sensitive Customer's own association fact, Critical Infrastructure's own `restriction_type`, a Boundary Pocket composition diff, a cross-scheme protected-assignment overlap) — it reflects the underlying engineering fact, never an administrative choice. The Evaluation Engine never decides whether publication is allowed (see Continuous Evaluation Architecture, a companion document in this pack) — it only classifies.

### Publication treatment (administrative policy, configurable)

One of: **Block publication, Allow with mandatory acknowledgement, Allow without acknowledgement.** Assigned by policy, keyed by finding type (and, where finer granularity is genuinely needed — e.g. a specific critical asset's own `restriction_type` — by the finding's own source data, exactly as `critical-infrastructure-module.md` §7.4's `Prohibited`/`ConditionallyAllowed`/`Unrestricted` already provides per-asset nuance). Policy characteristics, carried forward unchanged from [ADR-004](ADR-004-cross-scheme-compliance-mechanism.md)'s own design intent:

- A **global default** exists per finding type.
- An **optional scheme-specific override** may narrow or widen the default for one scheme type only (e.g. EMLS may retain a stricter default for critical-asset findings than UFLS/UVLS, mirroring [`emls-module.md`](../architecture/emls-module.md) §7.7's own recommendation against weakening Rule 2 for manually-invoked schemes — now expressed as a scheme-specific policy override rather than a hardcoded, unweakened business rule).
- Every policy change is **fully audited**: previous treatment, new treatment, administrator, timestamp, and a **non-empty reason** are all mandatory, mirroring the audit rigor [ADR-004](ADR-004-cross-scheme-compliance-mechanism.md) already required for `ComplianceRuleConfig` changes.
- A policy change applies only to **future** publication attempts — a historical Publication decision retains the policy that applied at the time it was made (see below).
- A finding that is no longer valid (its underlying condition was corrected) simply stops appearing; a finding that remains valid stays visible for as long as it remains true, independent of any policy change.

### Structural publication prerequisites remain outside this policy entirely

Per [ADR-015](ADR-015-defence-scheme-version-lifecycle-simplification.md)'s own Publication Prerequisites: missing scheme identity, a missing or non-Published required Stage Setting Set, incomplete stage/priority-group structure, missing target MW, a stage/priority-group with no shedding action, an invalid or incomplete Boundary Pocket, a broken authoritative reference, or an inability to perform the mandatory fresh publication evaluation. **These are never findings, never assigned a severity, and never subject to configurable treatment.** They are structural — a version in this condition is not yet a coherent engineering record, independent of any policy question. No administrator, at any privilege tier, may configure them away.

### Acknowledgement

When a finding's applicable treatment is `Allow with mandatory acknowledgement`:
- The publishing Administrator reviews the finding, grouped sensibly for review (by scheme stage/priority group, by rule, or by severity), with the individual supporting evidence for any group remaining expandable on demand — never hidden, never summarized away.
- Explicit confirmation is required, per finding group.
- A free-text justification is mandatory, non-empty.
- The Publication record permanently stores: which findings were present, their severities, the treatment that applied to each, the publishing Administrator, the timestamp, and the justification.
- **Acknowledgement never resolves or downgrades the finding itself.** A finding remains exactly as severe, and exactly as visible in every future evaluation, whether or not it was ever acknowledged at a past Publication — acknowledgement is a durable record that a human reviewed and accepted the finding at that moment, not a correction to the finding.
- **Only Administrators may publish** — unchanged from every scheme module's own existing "engineering approval actions require an authenticated, named IAM user" rule, now stated at the elevated Administrator tier specifically for the Publish action, matching the six workshops' own explicit requirement.

### Relationship to MW tolerance

The global engineering tolerance (±10% of target MW, per this pack's Continuous Evaluation Architecture) is versioned engineering parameter data (CLAUDE.md A7), not hardcoded per scheme module. A deviation outside tolerance produces a finding (severity determined by the evaluation logic, e.g. `Warning` for a moderate deviation, `Critical` for a severe one — the exact severity banding is an implementation detail for the Continuous Evaluation Architecture, not decided here) subject to the same publication-treatment policy as every other finding type. **The tolerance itself never blocks publication directly** — only the finding it produces, filtered through publication-treatment policy, can.

## Rationale

**Separating severity from treatment is what lets one detection mechanism serve every scheme, every finding type, and every deployment's own risk tolerance, without rewriting detection logic to change policy.** Under the old model, changing how strictly a `Prohibited` critical asset's conflict was enforced required either changing `ComplianceRuleConfig.enforcement_mode` (a blunt, rule-wide lever) or changing the hardcoded "always Block regardless of enforcement_mode" special case [`critical-infrastructure-module.md`](../architecture/critical-infrastructure-module.md) §7.4 built directly into Rule 2's algorithm. Under this ADR, the same outcome — a `Prohibited` critical-asset conflict always blocks Publication — is achievable as a **default policy setting**, changeable by an audited administrative action, with no code change and no ADR required to adjust it later. This is a strictly more flexible realization of the same engineering intent [`emls-module.md`](../architecture/emls-module.md) §7.7 already argued for, not a weakening of it — the recommended default (Prohibited → Block, unweakened for EMLS) is preserved; only the *mechanism* by which that default is expressed changes.

**Uniform application across every finding type, not just cross-scheme rules, is the genuine expansion the six workshops require.** [ADR-004](ADR-004-cross-scheme-compliance-mechanism.md)'s severity/treatment machinery existed only for Rule 1/Rule 2 — a scheme's own internal MW-tolerance deviation, ALSF-capability absence, or Boundary Pocket composition change had no equivalent governed-findings model at all in the prior architecture; each would have needed its own bespoke gating logic, duplicated per scheme module, exactly the kind of drift [`ufls-module.md`](../architecture/ufls-module.md) §17/§18 already flagged as a risk for Rule 7/8 validation logic. This ADR generalizes the one mechanism ADR-004 already validated to every finding a scheme accumulates, closing that gap once rather than per finding type.

**Structural prerequisites must remain outside configurable policy because they are not engineering judgement calls — they are completeness checks.** A version with a stage that has no shedding action is not "risky, pending administrator sign-off" — it is not yet a coherent scheme at all, the same category of defect [`ufls-module.md`](../architecture/ufls-module.md) §9's original rule 12-equivalent already treated as an unconditional block, never subject to any `enforcement_mode`. This ADR preserves that unconditional treatment explicitly, rather than letting it drift into the configurable-findings model where an administrator could, in principle, configure around it — a category error EDR-004's own decision-support philosophy would not tolerate (the platform reports and gates on structural fact; it does not let policy override fact).

**Acknowledgement without resolution mirrors the auditable-trust principle EDR-004 already establishes.** "A system that reports honestly is more trustworthy than one that acts confidently" (EDR-004) — an acknowledged finding that silently stopped appearing would erode exactly this trust, since a later reviewer could no longer distinguish "this was never a problem" from "this was a problem someone once accepted." Keeping the finding visible, permanently, alongside its acknowledgement record, is what makes the acknowledgement itself a genuine, checkable engineering decision rather than a one-time dismissal.

## Consequences

**Positive:**
- One governed-findings mechanism now covers every finding type a Defence Scheme Version can accumulate, not only cross-scheme rules — closing the gap the six workshops identified between Rule 1/2's existing rigor and every other finding's previous lack of any equivalent model.
- Publication-treatment policy changes (e.g. tightening or loosening how a specific finding type is handled) no longer require code changes or a new ADR — only an audited administrative action, exactly the flexibility [ADR-004](ADR-004-cross-scheme-compliance-mechanism.md)'s own `ComplianceRuleConfig` already demonstrated at smaller scope, now generalized.
- Structural prerequisites remain a hard, unconfigurable floor beneath the entire policy layer, preventing the category error of letting administrative policy substitute for basic scheme completeness.

**Negative / trade-offs:**
- [ADR-004](ADR-004-cross-scheme-compliance-mechanism.md)'s own `ComplianceRuleConfig`/`enforcement_mode` model and [`critical-infrastructure-module.md`](../architecture/critical-infrastructure-module.md) §7.4's "Rule 2 derives severity from `restriction_type`" algorithm are both subsumed by this ADR's more general model — not discarded (the underlying detection logic, and the specific `Prohibited`-always-severe engineering judgement, both carry forward), but the *governance* layer around them (the Block/Warn enforcement_mode, and Rule 2's own bespoke severity-derivation special case) is superseded. [ADR-004](ADR-004-cross-scheme-compliance-mechanism.md) receives a formal addendum note (per its own §18 Risk table, which already recommended exactly this kind of future addendum) rather than a rewrite.
- Every existing finding-producing capability this pack introduces or references (MW tolerance, ALSF, Sensitive Customer, Boundary Pocket, cross-scheme overlap, critical-infrastructure protection) must be re-expressed as "detects and classifies severity" only, with treatment resolution happening in one shared place — a genuine implementation-consistency requirement flagged for the Codex foundation-readiness audit, since a future implementer could easily reintroduce a bespoke gating shortcut inside one specific detector by habit.
- The exact default policy table (which finding types default to which treatment) is not fully enumerated by this ADR — only the mechanism and the one concretely-carried-forward default (`Prohibited` critical asset → `Block`) are specified here; the remaining defaults are an implementation/administrative-configuration decision for the module that first implements this mechanism, informed by but not dictated by this ADR.

---

## Alternatives Considered

1. **Separate severity and publication treatment, applied uniformly to every finding type, as decided above.** **Adopted.** Matches the six workshops' explicit conclusion, generalizes [ADR-004](ADR-004-cross-scheme-compliance-mechanism.md)'s own validated pattern rather than replacing it with something unproven, and closes the "every other finding type had no governed model" gap.

2. **Extend `ComplianceRuleConfig`'s existing per-rule `enforcement_mode` to cover every finding type, without separating severity from treatment.** **Rejected.** This would still conflate the two questions ADR-004 already conflated for Rule 1/2, now for every finding type — exactly the problem this ADR exists to correct, not a genuine alternative resolution of it.

3. **Give each finding-producing capability (MW tolerance, ALSF, Sensitive Customer, etc.) its own independent gating/severity model, as the prior architecture effectively did by never specifying one at all.** **Rejected.** This is the status quo the six workshops identified as insufficient — it would mean re-deriving (or worse, inconsistently re-deriving) the same severity/treatment/acknowledgement reasoning per finding type, the same drift risk [`ufls-module.md`](../architecture/ufls-module.md) already flagged for duplicated Rule 7/8 logic, now at a larger scale.
