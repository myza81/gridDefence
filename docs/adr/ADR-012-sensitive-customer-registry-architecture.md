# ADR-012: Sensitive Customer Registry — Independent Bounded Context, Designed for Multi-Application Reuse

- **Status:** Accepted — implemented (Phase 3.7)
- **Date:** 2026-07-10
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1, §6, §7, §8, §11.3, §11.5, §11.6, §20, §21, A1, A2, A5, A7, A8, F6)
- **Depends on:** [ADR-000](ADR-000-architecture-principles.md), [ADR-001](ADR-001-modular-monolith-and-module-communication.md), [ADR-007](ADR-007-canonical-engineering-reference-object.md) (Transformer Terminal as the canonical Bay-level reference target), [ADR-011](ADR-011-automatic-load-shedding-functionality-registry.md) (the immediately preceding Engineering Registry addition — the closest structural precedent, including its Future Integration Contract seam pattern)
- **Related:** [EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md) (the engineering scope this ADR's ownership decision implements), [EDR-003](../engineering/edr/EDR-003-relay-registry-scope.md), [EDR-005](../engineering/edr/EDR-005-bay-as-engineering-identity.md), [ADR-004](ADR-004-cross-scheme-compliance-mechanism.md) (Critical Infrastructure's own placement decision — the nearest comparison point for this ADR's central question), `docs/architecture/critical-infrastructure-module.md`, `docs/architecture/sensitive-customer-registry-module.md` (companion document this ADR authorizes)

---

## Context

The Automatic Load Shedding Functionality Registry (ADR-011) completed the Engineering Registry domain's answer to "can this bay execute a defence action." The next unanswered question from 01-engineering-philosophy.md §5 is Step 4 — Sensitive Customer Review: "would operating this bay affect a facility that deserves special engineering consideration." [EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md) scopes that question narrowly, mirroring EDR-003's discipline for the Relay Registry.

This module differs from every Engineering Registry module built so far in one material respect: it is explicitly required to be **reusable by future engineering applications that have never heard of GridDefence, UFLS, UVLS, or EMLS.** Every prior module in this series (Substation Registry, Equipment Registry, the Automatic Load Shedding Functionality Registry, and the still-unbuilt Critical Infrastructure) was designed to be *decoupled from scheme modules* (CLAUDE.md A2), but none was required to be decoupled from *GridDefence itself*. This ADR resolves the placement, ownership, and design-discipline questions that follow from that new requirement, alongside the questions every new Engineering Registry module must answer (mirroring [ADR-004](ADR-004-cross-scheme-compliance-mechanism.md)'s and [ADR-011](ADR-011-automatic-load-shedding-functionality-registry.md)'s own precedent of resolving several related decision points about one new module in a single ADR).

A second, unavoidable question arises because a structurally similar module — Critical Infrastructure — is already planned (Phase 9, [ADR-004](ADR-004-cross-scheme-compliance-mechanism.md)) but not yet built: both concepts classify a Master Data asset and both restrict or inform candidate selection during scheme design. Whether they should be the same registry, wearing two labels, is a question this ADR must answer definitively before either module's implementation begins.

---

## Decision

### 1. Sensitive Customer Registry is its own bounded context, in the Engineering Registry domain (Master Data), as a sibling to Critical Infrastructure — not merged with it, not folded into Equipment Registry

Sensitive Customer Registry and Critical Infrastructure remain **two separate registries**, each with its own owned entities, tables, service interface, and audit trail. See Alternatives Considered for the full reasoning; in summary, they answer different engineering questions, at different granularities, for different consumers, under different reusability constraints — the same kind of distinction this project already enforces between Sensitive Customer Review and Relay Capability Verification as workflow steps (03-system-workflow.md §3), now applied to their underlying registries.

It is **not Core Platform** — mirroring `critical-infrastructure-module.md` §7.1's own reasoning exactly: this data is asset-specific by definition (it always attaches to a specific Transformer Terminal), so it does not fit Core Platform's cross-cutting character (domain-model.md §2).

It is **not folded into Equipment Registry** — a facility's sensitivity classification is a policy/impact fact about what a bay *serves*, not a wiring or identity fact about the bay itself. Equipment Registry's own scope (equipment-registry-module.md §1, §4) has no engineering reason to know this, and a stricter, separate read-access policy (§15 of the companion module document) is far simpler to apply to a standalone module than to a subset of Equipment Registry's own, more open data.

### 2. Attachment granularity: current Transformer Terminal reference, no alternate-supply modelling

A `SensitiveFacility` references at most one Transformer Terminal (Equipment Registry, [ADR-007](ADR-007-canonical-engineering-reference-object.md)) at a time — the facility's *current* supply point, current-state only. No historical supply-point table, no many-to-many association object, no alternate/backup-supply modelling is introduced. This mirrors the "current-state master data plus full audit trail" pattern already established for `Circuit`, `Transformer`, and the Automatic Load Shedding Functionality Registry (CLAUDE.md §11.5) — a change of supply point is a field-level correction on the existing record, captured by the audit log, not a new historical row.

This is a deliberate, narrower choice than Critical Infrastructure's own `CriticalAssetSubstation` link, which *does* carry a validity window (`valid_from`/`valid_to`) because one critical asset may legitimately have multiple, historically-overlapping substation relationships (a hospital's primary and backup feed, both compliance-relevant simultaneously). Sensitive Customer Registry has no equivalent, currently-agreed engineering need for that richer shape (Agreed Engineering Principle 5); introducing it now, by analogy, would be exactly the premature generalization CLAUDE.md §21 warns against.

**This is an implementation-scope decision, not an architectural limitation.** Today's engineering practice associates a facility with a single, current Transformer Terminal, and the initial implementation should support exactly that — nothing more. But the domain model itself (companion document §7) already expresses this as an *association* between `SensitiveFacility` and `TransformerTerminal`, not as an attribute baked into `SensitiveFacility`'s own identity. Should a future engineering requirement introduce alternate or multiple concurrent supply arrangements, the architecture should be able to evolve by extending that association (for example, toward a richer association record carrying its own validity window, the same shape Critical Infrastructure already uses for `CriticalAssetSubstation`) rather than requiring a fundamental redesign of `SensitiveFacility` or of this module's service interface. No such association model is introduced now — this paragraph states an architectural capability the design does not foreclose, not a present-day feature.

### 3. Reference facility Sector and Sensitivity Classification as reference data, not hardcoded enumerations

Both `FacilitySector` (the eight categories named in the originating engineering conversation, referred to there as "Consumer Sector") and `SensitivityClassification` (High/Medium/Low) are modeled as small, module-owned reference tables (CLAUDE.md §11.3), mirroring Critical Infrastructure's own precedent for `CriticalityLevel` (`critical-infrastructure-module.md` §5, design note) — the first place this "module-owned reference table" pattern was needed, now the second. New sector or classification values can be added by data change alone, never a code deployment, satisfying the explicit instruction to evaluate extensibility without hardcoding.

### 4. The registry returns engineering facts, never enforcement verdicts — and is not, today, a Cross-Scheme Compliance rule

`SensitivityClassification` and facility association are returned by this module exactly as recorded — the module never computes, and never returns, a "block"/"allow" verdict of its own. Interpreting a sensitivity finding (exclude the candidate outright, warn the engineer, treat only "High" as consequential) is left entirely to each consuming defence scheme's own philosophy, not decided by this ADR, mirroring Agreed Engineering Principle 4 exactly. Consequently, **this registry is not, at this time, wired into Cross-Scheme Compliance as a new blocking rule** (contrast Critical Infrastructure's `restriction_type`, which *is* explicitly designed to drive Rule 2's severity, `critical-infrastructure-module.md` §7.4) — see Alternatives Considered.

Stated as a governing rule for this module:

> **The Sensitive Customer Registry records engineering facts about sensitive facilities. It never records engineering decisions made by consuming applications.**

Engineering decisions that must never be stored in, or derived by, this registry include (non-exhaustive): a candidate being excluded from UFLS; a facility being allowed only in a particular stage; an override having been approved; a temporary engineering exception; a scheme-specific restriction; or any defence-scheme assignment. Each of these belongs to the consuming application's own records — this registry supplies the fact that informed the decision, never the decision itself. This is the same "facts, not verdicts" discipline already applied to `SensitivityClassification` in the preceding paragraph, restated here as the module's own general fact-ownership boundary so it governs every present and future field this module might carry, not only the classification field that motivated it.

### 5. Designed for multi-application reuse from inception, not retrofitted later

The module's owned entities, business rules, and service-interface vocabulary use **no GridDefence-specific or scheme-specific terms** — no "scheme," "stage," "shedding action," "UFLS," "UVLS," or "EMLS" appears anywhere in this module's own data model or service contract (mirroring, and going further than, Critical Infrastructure's own equivalent discipline, `critical-infrastructure-module.md` §4). Every service-interface method is expressed purely in terms of facilities and Transformer Terminal identifiers — a shape any future consumer, GridDefence or not, can call without needing to understand GridDefence's own domain vocabulary. This is a **binding design constraint on the companion module document and on implementation**, not merely a stylistic preference — see Consequences.

**Clarification: referencing Transformer Terminal does not itself violate this constraint.** Transformer Terminal is not GridDefence vocabulary — it is an authoritative engineering identity owned by the Equipment Registry, describing a physical piece of transmission equipment, independent of any defence scheme, stage, or GridDefence-specific workflow. The governing principle this ADR adopts is:

> **Engineering registries may reference authoritative engineering identities owned by other registries without becoming application-specific.**

An engineering registry becomes application-specific only when it embeds *application* concepts — scheme, stage, shedding action, boundary pocket, or any other concept that exists solely because GridDefence's own workflow exists. Referencing another registry's engineering identity, by contrast, is exactly the ownership discipline CLAUDE.md §5.1 and A1 already require of every module in this project (reference, never duplicate). Sensitive Customer Registry's reusability rests on depending only on engineering identities (Transformer Terminal) and never on defence-scheme concepts (UFLS, UVLS, EMLS, stages, boundary pockets, or any GridDefence workflow step) — not on avoiding every reference to another registry's identity. A future non-GridDefence consumer with its own asset model would need to resolve its own equivalent of "Transformer Terminal" against this registry's association, exactly as it would need to resolve any other engineering identity it did not itself define — this is ordinary cross-registry integration, not an adaptation layer imposed by this module's own design.

---

## Rationale

This mirrors the same pattern already validated twice in this document series: a new Master Data module is placed in the Engineering Registry domain, decoupled from every scheme module by construction (CLAUDE.md A2), consumed through a read-only service interface, never the reverse ([ADR-004](ADR-004-cross-scheme-compliance-mechanism.md) for Critical Infrastructure; [ADR-011](ADR-011-automatic-load-shedding-functionality-registry.md) for the Automatic Load Shedding Functionality Registry). What is new here is the additional reusability constraint (decision 5), which this ADR treats as a first-class architectural decision precisely because it is easy to erode by accident during implementation if it is only ever stated as an aspiration rather than a binding rule enforced at design time.

---

## Consequences

**Positive:**
- A precisely-scoped registry matching the confirmed engineering specification, structurally consistent with every other Engineering Registry module in this series.
- Sensitive facility data can be consumed by UFLS/UVLS/EMLS identically (via the same interface), without this module ever distinguishing which scheme is asking or why.
- Because the module's vocabulary is GridDefence-free by construction, a future extraction into a standalone service consumed by a second, non-GridDefence application (CLAUDE.md §6, F6) requires no redesign of what the module owns or answers — only a transport-layer change, exactly as EDR-008 anticipates.
- Critical Infrastructure's own, already-planned architecture (substation granularity, compliance-rule-coupled `restriction_type`) remains untouched and un-conflated — this ADR does not reopen [ADR-004](ADR-004-cross-scheme-compliance-mechanism.md).

**Negative / trade-offs:**
- Two visibly similar registries (Sensitive Customer Registry, Critical Infrastructure) now exist side by side in the Engineering Registry domain. A future contributor unfamiliar with this ADR could reasonably wonder why they were not merged — mitigated by this ADR's own Alternatives Considered section and by a cross-reference in both modules' architecture documents (`sensitive-customer-registry-module.md` §4; a corresponding note recommended for `critical-infrastructure-module.md` when it is next revised, per the companion module document's Risks section).
- The "no GridDefence vocabulary" constraint (decision 5) requires ongoing implementation discipline — nothing in the platform mechanically prevents a future contributor from adding a scheme-specific field to this module out of convenience. Mitigated by treating this ADR, and the corresponding rule in the companion module document (§4, §9), as a PR-review checklist item for this module specifically, the same way CLAUDE.md A8/A13 already treat `getProtectedAssignments`-equivalent interfaces as a checklist item for new scheme modules.
- Sensitivity classification's current lack of any enforcement coupling means a defence scheme module could, in principle, ignore it entirely without this registry or this ADR preventing that — deferred, deliberately, to each scheme module's own future design (§17 of the companion module document).

---

## Alternatives Considered

1. **Merge Sensitive Customer Registry and Critical Infrastructure into one generic "Asset Classification / Restriction Registry."** **Rejected.** They answer different engineering questions at different granularities: Critical Infrastructure classifies *substations* for a compliance-enforcement purpose (`restriction_type` directly drives Cross-Scheme Compliance Rule 2 severity, `critical-infrastructure-module.md` §7.4); Sensitive Customer Registry classifies *facilities served through a specific Transformer Terminal* for an advisory, scheme-design-time purpose, and must never drive enforcement directly (decision 4). Merging would either force Critical Infrastructure's compliance-rule coupling — an explicitly GridDefence/Cross-Scheme-Compliance-specific concept — into a registry required to remain portable to non-GridDefence consumers, or force Sensitive Customer Registry's terminal-level granularity onto Critical Infrastructure's substation-level model, degrading one to fit the other. Every module in this series has so far been kept to one specific engineering question (EDR-003's own discipline, restated); this decision applies that same discipline a second time, deliberately, having genuinely considered the alternative.
2. **Fold Sensitive Customer data into Equipment Registry, as an attribute or related table of `TransformerTerminal`.** **Rejected**, for the same reasons `critical-infrastructure-module.md` §7.1 already rejected folding criticality into Substation Registry: the relationship shape differs (a terminal may serve zero, one, or many sensitive facilities; a facility's own record needs its own lifecycle, sector, and sensitivity classification, none of which belong on `TransformerTerminal` itself), and the data plausibly warrants a stricter, separate read-access policy (§15 of the companion document) that would be awkward to carve out of Equipment Registry's own, more open policy.
3. **Wire Sensitive Customer Registry into Cross-Scheme Compliance immediately, as a new Rule 3.** **Rejected for now**, not permanently foreclosed. This would encode a specific enforcement interpretation (what "High" sensitivity should *do*) into either this registry or a compliance rule before any scheme module's own philosophy has decided how sensitivity should influence candidate selection — a decision [EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md) explicitly declines to make on this registry's behalf. Left as an explicit Future Extension (companion document §17), revisited only once a concrete scheme-module design actually needs it — mirroring [ADR-004](ADR-004-cross-scheme-compliance-mechanism.md)'s own "Open Questions" item 5 (whether the Rule 1/2 catalog is closed).
4. **Design a fully generic "Supply Point" abstraction instead of referencing Transformer Terminal directly, to maximize reuse by applications with different asset models.** **Rejected for this phase.** No second consuming application exists yet to validate such an abstraction against, and designing one now would be speculative generalization ahead of real need (CLAUDE.md §21) — the exact mistake this project has already declined to make twice for a generic `Equipment`/`Bay` backbone (`equipment-registry-module.md`'s own header comment; [EDR-005](../engineering/edr/EDR-005-bay-as-engineering-identity.md) §Consequences). This is not, itself, a reusability compromise: per decision 5's clarification, referencing Transformer Terminal — an authoritative engineering identity, not GridDefence vocabulary — does not make the registry application-specific. A generic "Supply Point" abstraction would only become warranted if a future consuming application's own asset model could not resolve Transformer Terminal identity at all, which is a materially different problem from the vocabulary-coupling this ADR is designed to avoid. Recorded instead as an explicit open question (companion document §19), to be revisited if and when a second, structurally different consuming application actually materializes.
5. **Treat reusability as an aspiration only, without a binding design rule, and generalize later if a second consumer actually appears.** **Rejected.** Unlike alternative 4 (a genuinely premature *abstraction*), avoiding GridDefge-specific *vocabulary* in this module's own entities and interface costs nothing today and is far cheaper to maintain from the start than to retrofit later, once GridDefence-specific fields or method names have already accreted. This is a discipline decision, not a design-complexity one, and is adopted now (decision 5) rather than deferred.

---

## Service Interface Expectations

High-level only — concrete signatures, DTOs, and API routes are companion-document and implementation-phase work (`sensitive-customer-registry-module.md` §12, §13).

**Sensitive Customer Registry exposes, for other modules (and, eventually, other applications) to consume:**
- A single-terminal facility lookup, and a **batch** multi-terminal facility lookup — the batch shape exists specifically to serve the Boundary Pocket consumption pattern (Agreed Engineering Principle 6): Network Model resolves which Transformer Terminals lie inside a proposed electrical pocket, and the calling module hands that whole terminal-id set to this registry in one call, mirroring `getCriticalityForSubstations`'s own batch-first design (`critical-infrastructure-module.md` §13).
- A simple "does this terminal serve any sensitive facility" boolean convenience, mirroring the Automatic Load Shedding Functionality Registry's own `is_ufls_capable`/`is_uvls_capable` shape ([ADR-011](ADR-011-automatic-load-shedding-functionality-registry.md)).
- General read/list access for registry browsing (Dashboard, Reporting, a future administrative UI).

**Sensitive Customer Registry consumes, from other modules' service layers — never their repositories directly:**
- From Equipment Registry: Transformer Terminal existence/identity validation, exactly mirroring how the Automatic Load Shedding Functionality Registry validates its own terminal references.
- From Core Platform (IAM): authorization checks for writes; user lookups for audit attribution.

**Sensitive Customer Registry never calls, and is never called by:**
- Network Model — Network Model resolves pocket membership independently; this registry only ever receives an already-resolved terminal-id set from whichever module orchestrates a boundary-pocket check. Neither module calls the other directly, mirroring the same non-coupling already established between Network Model and the Automatic Load Shedding Functionality Registry.
- The Automatic Load Shedding Functionality Registry — both are independent, parallel fact-providers, each consulted separately by the same orchestrating caller (Agreed Engineering Principle "Intended Role Inside GridDefence"), never calling each other.
- Any scheme module's repository or tables directly (CLAUDE.md A1).

---

## Data Ownership Rules

- Sensitive Customer Registry owns: facility identity and classification data, its own reference tables (Sector, Sensitivity Classification), its own lifecycle, and its own audit log. Full detail: companion document §5.
- Sensitive Customer Registry references, never owns: Transformer Terminal identity (Equipment Registry), user identity (IAM).
- Sensitive Customer Registry is never referenced by a foreign key from any scheme module's own tables — consumption is exclusively through this module's service interface (CLAUDE.md A1), mirroring every other Engineering Registry module in this series.
- No scheme module, and no other Engineering Registry module (Critical Infrastructure included), writes to this module's tables.

---

## Recommended Next Architecture Document

**`docs/architecture/sensitive-customer-registry-module.md`** — the full Canonical Module Architecture Document Template (CLAUDE.md A8) treatment this ADR authorizes, produced alongside this ADR as its companion document, formalizing every decision above at the level of engineering entities, business rules, and service-interface contracts (not implementation schema).

Per this project's own established practice ([ADR-004](ADR-004-cross-scheme-compliance-mechanism.md) → `critical-infrastructure-module.md`; [ADR-011](ADR-011-automatic-load-shedding-functionality-registry.md) → `automatic-load-shedding-functionality-registry-module.md`), no implementation begins from this ADR or its companion document alone — per CLAUDE.md §24, both require Project Owner review and approval before any database schema, service code, or API design work starts.
