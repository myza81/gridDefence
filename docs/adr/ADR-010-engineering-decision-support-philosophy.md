# ADR-010: Engineering Decision-Support Philosophy

- **Status:** Accepted
- **Date:** 2026-07-05
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§4 Engineering Philosophy, §5.4 Auditability, §5.5 Deterministic Behaviour, A3 Canonical Version Lifecycle)
- **Depends on:** [ADR-000](ADR-000-architecture-principles.md) (this ADR names an additional, previously-implicit principle within ADR-000's existing scope; it does not replace or narrow any of ADR-000's nine principles)
- **Affects:** [docs/architecture/psse-integration-module.md](../architecture/psse-integration-module.md) (adds an explicit "Engineering Philosophy" section restating this ADR for that module's own workflow), [docs/architecture/network-model-module.md](../architecture/network-model-module.md) (`ManualOverride` already follows this pattern; unchanged), [docs/architecture/ufls-module.md](../architecture/ufls-module.md)/[uvls-module.md](../architecture/uvls-module.md)/[emls-module.md](../architecture/emls-module.md) (the Canonical Version Lifecycle these modules use remains the correct, unaffected model for *approved engineering policy* — this ADR does not apply to them in the way it applies to source/computed data)
- **Informed by:** the completed Phase 4 (PSS/E Integration) implementation and its independent architecture validation, which surfaced a pattern already present but never previously named as a general rule: [ADR-003](ADR-003-psse-topology-and-load-snapshot-separation.md)'s `Imported → Current → Superseded` lifecycle and [network-model-module.md](../architecture/network-model-module.md)'s `Computing → Computed` lifecycle both deliberately reject the Canonical Version Lifecycle (CLAUDE.md A3) for the same underlying reason, stated independently in each place rather than as one shared principle.

---

## Context

Phases 2 through 4 have now each, independently, faced the same design question: when a new versioned engineering entity is introduced, does it need the full Canonical Version Lifecycle (CLAUDE.md A3 — Draft → Under Review → Approved → Active → Superseded → Archived, requiring human review and sign-off at each gate), or does it need something lighter?

ADR-003 answered this for `TopologyVersion`/`LoadSnapshot` (a three-state `Imported → Current → Superseded` model, explicitly rejecting A3 in its own Alternatives Considered #6). `network-model-module.md` answered it again, independently, for `IslandAnalysisResult` (a `Computing → Computed` model, also explicitly not A3, in its own §9 rule 1). Both arrived at the same underlying reasoning — imported or computed data is not approved engineering policy, and forcing A3's approval machinery onto it would misrepresent it as something it is not — but that reasoning was stated twice, in two module-specific documents, as if it were a coincidence rather than a rule. A future module facing the identical question (a difference-detection result, a validation-rule outcome, a future SPS/RAS analysis) would have no single place to look this up; it would either re-derive the same reasoning a third time or, worse, default to A3 by habit because that is the only versioning pattern with a name.

This ADR exists to name the rule explicitly, once, as a durable architectural principle — not to change any decision ADR-003 or `network-model-module.md` already made, and not to touch the Canonical Version Lifecycle itself, which remains exactly correct for what it governs.

---

## Decision

**GridDefence is an engineering decision-support platform. It is not a business workflow system, and it is not an approval management application.**

The system's purpose is to maximise engineering confidence in the decisions an engineer makes — by automating validation, automating comparison, preserving complete traceability, and presenting engineering evidence — not to interpose organisational sign-off machinery between an engineer and the data they need. Every workflow this platform introduces must be justified by an engineering need for confidence, never by an assumed need for bureaucratic process.

This ADR ratifies a rule that generalizes what ADR-003 and `network-model-module.md` each already decided independently:

### The classification rule

When a new module introduces a versioned or lifecycled entity, it must first be classified as exactly one of the following two kinds, and the classification determines which lifecycle applies:

1. **Approved Engineering Policy** — a record that will itself govern real equipment or real operational behaviour once active (a UFLS/UVLS/EMLS scheme version is the canonical example; a Cross-Scheme Compliance rule configuration is another). This kind of record **requires** the full Canonical Version Lifecycle (CLAUDE.md A3) and the human review/approval gates that go with it — because the record's own correctness, once active, is the thing standing between the grid and an engineering mistake. This is not the pattern this ADR is relaxing; A3 remains fully correct and mandatory here, unchanged by anything in this ADR.

2. **Engineering Source or Computed Data** — a record that is imported from an external source (a PSS/E RAW file) or deterministically computed from other data already in the system (an island analysis, a future topology comparison), and which a scheme module may *consult* but does not itself *become* approved policy until a human explicitly captures a value from it into their own owned data. `TopologyVersion`, `LoadSnapshot`, and `IslandAnalysisResult` are the established examples. This kind of record **must not** be forced through A3. It uses a lighter, module-specific lifecycle instead — see below.

### What the lighter lifecycle must still guarantee

Relaxing away from A3 does not mean relaxing away from rigor. A lighter lifecycle for Engineering Source/Computed Data must still provide, in full:

- **Automated validation** at the point of import or computation (parse/structural validation, coverage/quality checks) — surfaced to the engineer, never silently passed over.
- **Complete audit traceability** — who, when, what was produced or reused, and what the validation found (CLAUDE.md §5.4, A4) — exactly as rigorous as any A3-governed audit trail, never lighter simply because the lifecycle is lighter.
- **Exactly one explicit, human, authenticated, authorized decision point** before the data becomes the operational reference other consumers rely on — an **Activation** (PSS/E Integration's own term, §8.10 of that module's document) or equivalent single gate. This is the one mandatory checkpoint; it is not optional, and it is not the same thing as "no review at all."
- **Immutability once created**, and **retained, queryable history** for every prior state (CLAUDE.md §5.2, §11.6) — a superseded `TopologyVersion` or `IslandAnalysisResult` is never deleted, exactly as an Archived scheme version never is.

### Activation is the engineering decision; review is informational

The single checkpoint named above — Activation — **is** the engineering decision. It is not a preliminary step toward a separate approval elsewhere; there is no additional "Approve this import" or "Approve this analysis" stage layered on top of it. Everything before Activation (automated validation, comparison against the previous state, correlation against other Master Data, an engineer's own review of warnings or discrepancies) exists to give the activating engineer **confidence** in that one decision — it is evidence, not a queue of separate sign-offs. A reviewing engineer reading a batch's warnings before deciding whether to activate it is exercising engineering judgement directly, in one step, not routing a request through a second person's separate approval action.

This is precisely what Phase 4's PSS/E import workflow already implements (Preview → Commit → Activate, with `EquipmentTopologyMap` discrepancy review folded into the informational evidence an engineer consults before Activation, never a second gate blocking it) and what Network Model's `analyzeIsland`/`ManualOverride` design already implements (a computed result is a recommendation; a scheme module's own later Approval, under A3, is the actual engineering-policy decision). Neither needed to change to comply with this ADR — this ADR names the rule they were both already following.

### What this rule forbids, going forward

A future module introducing Engineering Source/Computed Data **must not**:
- Add a second human "approval" role or step between validation and Activation, on the theory that more sign-offs imply more safety — they do not; they dilute accountability for the one decision that matters and add process cost with no corresponding confidence gain.
- Apply the Canonical Version Lifecycle to data that is not itself approved engineering policy, even if doing so would "reuse an existing pattern" — reuse of the wrong pattern is not consistency, it is the exact misclassification this ADR exists to prevent.
- Treat "the import succeeded" and "the import was activated" as the same event, or collapse them into one step — the separation is what gives the activating engineer a genuine decision point rather than an automatic, unreviewed default.

---

## Consequences

**Positive:**
- Every future module facing this classification question now has one ratified rule to apply, rather than re-deriving ADR-003's reasoning independently a third or fourth time.
- Prevents "approval creep" — the natural tendency, over a multi-year, multi-contributor project, to add a review/sign-off step to a workflow "to be safe," which this ADR names explicitly as a cost without a corresponding confidence benefit when applied to data that isn't approved policy.
- Clarifies, for anyone reading `psse-integration-module.md` or `network-model-module.md` fresh, *why* those modules' lifecycles look different from UFLS/UVLS/EMLS's — a deliberate, ratified distinction, not an inconsistency to "fix" by making them all use A3.

**Negative / trade-offs:**
- Requires every future module's designer to correctly perform the classification (§ Decision) at design time — a wrong classification (treating approved policy as if it were source data, or vice versa) is a real error this ADR does not automatically prevent, only names the criteria for avoiding.
- Does not, by itself, resolve any specific future module's design — it is a classification rule and a minimum-guarantee list, not a template; each future module (SPS/RAS, Black Start, Restoration Planning) must still work through its own module-architecture-document process (CLAUDE.md A8) to apply it correctly.

---

## Alternatives Considered

1. **Leave the reasoning distributed across ADR-003 and `network-model-module.md`, without naming a shared rule.** Rejected. This is the status quo this ADR is correcting — a future module would have no single place to look up the classification question, and risks re-deriving it inconsistently or defaulting to A3 out of habit.

2. **Fold this principle into ADR-000 directly, as a tenth core principle.** Considered and rejected. ADR-000 explicitly states it "does not introduce new principles; it formalizes the ones already active in CLAUDE.md v1.1" — this ADR's classification rule is not yet in CLAUDE.md, and is a genuinely new, more specific decision than ADR-000's role is scoped to carry. Recording it separately, with its own Context/Decision/Consequences reasoning, keeps ADR-000 an accurate historical record of what it actually ratified at the time, per this project's established practice of treating ADRs as an append-only record (the same practice already applied when ADR-009 added a pointer note to ADR-008 rather than rewriting it).

3. **Reopen ADR-003 and add this reasoning there instead.** Rejected, per this task's explicit instruction and on independent merit: ADR-003 is scoped to PSS/E's own topology/load separation specifically; the classification rule this ADR states is broader than PSS/E and already independently apparent in Network Model's own, unrelated design. Housing a cross-cutting principle inside a module-specific ADR would make it easy for a future reader of, say, a Black Start module design to miss it entirely.

4. **Wait until a third module needs this classification before ratifying anything.** Rejected. Network Model's `IslandAnalysisResult` is already the second independent instance of this exact pattern (after PSS/E Integration's own), which is sufficient evidence this is a recurring architectural question, not a one-off. Naming it now, while Phase 5 has not yet begun, lets Network Model's own documentation and every future module benefit from a ratified answer from the start, rather than retrofitting one later.

---

## Relationship to Existing Decisions (for the avoidance of doubt)

This ADR does not reopen, weaken, or reinterpret:
- **CLAUDE.md A3** (Canonical Version Lifecycle) — remains exactly as specified, and remains mandatory for Approved Engineering Policy.
- **ADR-003** — `TopologyVersion`/`LoadSnapshot`'s lifecycle, workflows, and business rules are unchanged; this ADR only names, as a general rule, the classification reasoning ADR-003's own Alternatives Considered #6 already applied.
- **ADR-004** (Cross-Scheme Compliance) — the Approval/Activation compliance-gating behaviour it specifies applies to Approved Engineering Policy (scheme versions) exactly as before; nothing in this ADR relaxes those gates.
- **ADR-006, ADR-007** — unaffected; neither concerns lifecycle classification.

Any future module document that classifies an entity under this ADR's rule should cite this ADR directly, the same way `psse-integration-module.md` and `network-model-module.md` already cite ADR-003 for their own lifecycle decisions.
