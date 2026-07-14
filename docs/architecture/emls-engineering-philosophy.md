# EMLS Engineering Philosophy

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md). Read [scheme-engineering-principles.md](scheme-engineering-principles.md) and [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) first — this document states only what is genuinely specific to EMLS.

Supersedes, in part, [emls-module.md](emls-module.md) §7–§8 (status note, not a rewrite). [`emls-module.md`](emls-module.md) §1–§6, §9 (minus lifecycle rules), §10–§18 remain authoritative — most importantly §7.7's Rule 1/2 participation reasoning, still valid in engineering judgement even though its governance *mechanism* is now [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) rather than a bespoke Cross-Scheme-Compliance-only special case.

---

## 1. Manual Operational Shedding Philosophy

EMLS has no automatic trigger — no frequency or voltage threshold, no relay armed to a physical quantity, no time delay to coordinate. A human operator decides, in the moment, whether and how much to invoke, during a declared grid emergency automatic UFLS/UVLS response cannot or should not resolve on its own. EMLS's engineering design provides a **priority order**: a pre-approved, ranked sequence of what to shed first, so that when an operator must act quickly under real emergency conditions, the decision of *what* has already been made carefully in advance ([`emls-module.md`](emls-module.md) §1, unaffected).

## 2. No Stage Setting Set

EMLS uses no Stage Setting Set ([stage-setting-set-architecture.md](stage-setting-set-architecture.md) §2) — there is no threshold or delay to make reusable across versions. An EMLS Priority Group ([shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §2.3) is owned directly by its Scheme Version, ranked by `priority_order` (unique, no monotonicity comparison — there is no physical quantity to compare against), optionally carrying human-facing `invocation_guidance` (descriptive context for when a human should consider invoking it, never a machine-evaluated condition).

## 3. No ALSF Prerequisite

**EMLS must not call the Automatic Load Shedding Functionality Registry, and must acquire no automatic-load-shedding capability prerequisite of any kind.** EMLS is manually invoked and may be assigned to any bay at the scheme designer's discretion — a bay's automatic-shedding capability is simply irrelevant to a manually-invoked scheme. This is a hard exclusion carried forward unchanged from [`emls-module.md`](emls-module.md) §4/§9 rule 4 and [`implementation-plan.md`](implementation-plan.md) Phase 8's own explicit instruction ("do NOT call the Automatic Load Shedding Functionality Registry or add any automatic-capability check") — not a deferred integration, and not something a future reviewer should "complete the pattern" by adding, by analogy with UFLS/UVLS. This applies identically to a selected boundary `CircuitTerminal` opening point — unlike UFLS/UVLS ([ufls-engineering-philosophy.md](ufls-engineering-philosophy.md) §4, [uvls-engineering-philosophy.md](uvls-engineering-philosophy.md) §4), EMLS never checks ALSF capability on any opening point at all ([scheme-data-consumption-matrix.md](scheme-data-consumption-matrix.md) §3).

## 4. Manual-Action Assignment Structure

Both direct Transformer Terminal assignment and Boundary Pocket assignment are available, and Boundary Pocket assignment is **commonly used, primary-tier**, not demoted to rare usage the way it is for UVLS ([`emls-module.md`](emls-module.md) §7.5, unaffected by [ADR-017](../adr/ADR-017-boundary-pocket-assignment-architecture.md)): EMLS's scope is not limited to a single physical-condition category the way UFLS (frequency) and UVLS (voltage) are — it is invoked for any declared grid emergency an operator judges warrants manual shedding, which routinely includes scenarios where deliberately islanding a stressed section of the grid is itself the appropriate emergency response, not an incidental side effect to guard against.

## 5. Target or Total Quantum Philosophy

Each `EmlsPriorityGroup` carries a `target_shed_mw`, identical in purpose to UFLS/UVLS's per-stage target — "if invoked, approximately this much MW would be shed," useful for planning and Publication-governance findings even though no automatic trigger will ever act on it. Current MW is derived the same way as any other assignment kind, per [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md).

## 6. Sensitive Customer Review

Applies to EMLS exactly as it does to UFLS/UVLS — Sensitive Customer association is scheme-agnostic ([`implementation-plan.md`](implementation-plan.md) Phase 8's own note), and produces a finding rather than an automatic removal, per [scheme-engineering-principles.md](scheme-engineering-principles.md) §6.

## 7. Publication and Continuous Evaluation

Standard, per [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md), with one deliberately unweakened point carried forward from [`emls-module.md`](emls-module.md) §7.7: a `Prohibited`-severity critical-infrastructure finding's default publication treatment is `Block`, exactly as for UFLS/UVLS, on the reasoning that EMLS's manual invocation adds a second, complementary layer of protection (human judgement at the moment of the actual emergency) rather than substituting for rigorous design-time review — if anything, the case for design-time rigor is stronger, not weaker, given the compressed decision time an operator has during a genuine crisis. Segregation of duties (Draft editor distinct from the Administrator who Publishes) is recommended with particular emphasis for EMLS, given it is the plan operators execute during genuine emergencies with limited opportunity for real-time correction ([`emls-module.md`](emls-module.md) §15, unaffected).

## 8. How EMLS Differs from Staged Automatic Schemes

| Aspect | UFLS / UVLS (staged, automatic) | EMLS |
|---|---|---|
| Trigger | Threshold crossing (frequency/voltage), automatic | None — human-invoked |
| Grouping unit | Stage, via a Stage Setting Set | Priority Group, owned directly by the version |
| Ordering | Threshold monotonicity | Priority uniqueness only, no physical-quantity comparison |
| ALSF | Required capability check, non-removing finding on absence | Never called — hard exclusion |
| Boundary Pocket usage | Common (UFLS), rare (UVLS) | Common, primary-tier |
| Guidance field | None | `invocation_guidance` — human decision support, never machine-evaluated |

## 9. Unresolved Engineering Questions (not invented here)

Per this task's own instruction not to invent EMLS detail the workshops did not provide:

- **Real-time emergency invocation tracking** — whether and how an actual operator invocation event (who invoked which Priority Group, when, under what declared emergency) should ever be recorded, and by what module, remains open. EMLS's own scope, unchanged from [`emls-module.md`](emls-module.md) §4/§17, is the engineering design record only — it does not track real-time invocation. Whether a future, separate operational/SCADA-adjacent capability should exist for this is not decided by this pack.
- **Formal ratification of the Rule 2 no-weakening policy (§7)** — [`emls-module.md`](emls-module.md) §18/closing summary already flagged this as needing explicit Project Owner sign-off via its own ADR, distinct from this pack's own [ADR-018](../adr/ADR-018-findings-severity-and-publication-governance-separation.md), which formalizes the *mechanism* (policy is now configurable) without independently re-ratifying *whether* the shipped default should ever be weakened for EMLS specifically. That values question remains open.
- **Whether `invocation_guidance` should become a hard validation requirement** (non-empty, mandatory) rather than merely recommended — [`emls-module.md`](emls-module.md) §18 already flags this as worth strengthening in practice; this pack does not resolve it.
