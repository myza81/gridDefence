# EDR-008: The Sensitive Customer Registry Maintains Facility Engineering Knowledge, Not Scheme Decisions or Customer Relationships

- **Status:** Accepted — implemented (Phase 3.7)
- **Governing document:** [01-engineering-philosophy.md](../01-engineering-philosophy.md) §5 (Step 4 — Sensitive Customer Review); [02-engineering-concepts.md](../02-engineering-concepts.md) — Sensitive Customer, Sensitive Customer Review
- **Related:** [EDR-003](EDR-003-relay-registry-scope.md) (the parallel scope-discipline precedent for the registry now realized as the Automatic Load Shedding Functionality Registry); [03-system-workflow.md](../03-system-workflow.md); `docs/architecture/critical-infrastructure-module.md`; `docs/architecture/sensitive-customer-registry-module.md` (companion document); [ADR-012](../../adr/ADR-012-sensitive-customer-registry-architecture.md) (the architecture decision this EDR's scope feeds)

---

## Background

GridDefence cannot select a bay for load shedding without knowing what it would affect. Two different engineering questions have to be answered before a candidate bay reaches Selection of Shedding Actions: "can this bay technically execute a defence action" (Relay Capability Verification, now answered by the Automatic Load Shedding Functionality Registry — [EDR-003](EDR-003-relay-registry-scope.md)) and "would operating this bay affect a facility that deserves special engineering consideration" (Sensitive Customer Review). This EDR resolves the second question's scope.

A facility whose supply is interrupted can range from operationally inconvenient to genuinely dangerous — a hospital, an airport, a water treatment plant, a national security asset. Recording this is not optional engineering polish; 01-engineering-philosophy.md §5 Step 4 already treats it as a mandatory workflow step. The question this decision resolves is **how much** GridDefence should know about these facilities: a full facility/customer-management system (contact details, service-level agreements, billing relationships, correspondence history), or something narrower.

A second, newer consideration shapes this decision beyond what EDR-003 had to consider for the Relay Registry: this registry is explicitly intended to be **reusable outside GridDefence**, by future transmission-engineering applications that have never heard of UFLS, UVLS, or EMLS. Scope discipline here is not just about keeping one module trustworthy (EDR-003's reasoning) — it is a precondition for that reusability. A registry that accumulates GridDefence-specific vocabulary cannot be handed to a second consuming application without first being un-picked from GridDefence.

## Decision

**The Sensitive Customer Registry answers exactly one engineering question: which physical facilities require special engineering consideration if a given supply point is interrupted, and what is their classification? It is not a customer-relationship-management system, not a billing or service-level system, not a geographic information system, and it does not decide what a defence scheme does with that information.**

The registry's authoritative content is: the facility's identity (a physical place, not an organization), which broad sector it belongs to, and how sensitive it is judged to be, engineering-wise. It records this against the one supply-point reference GridDefence currently needs (a Transformer Terminal, per the Equipment Registry) without owning that identity itself. It never encodes what any consuming application — GridDefence's own UFLS/UVLS/EMLS included — should *do* with a sensitivity finding; that interpretation belongs entirely to the consumer.

## Rationale

**GridDefence, and any future consumer, needs an engineering fact, not a decision.** Every workflow step that touches this registry (Sensitive Customer Review, 03-system-workflow.md) asks the same question: would this candidate affect a sensitive facility, and how sensitive? Nothing in that workflow needs this registry to know what a "Stage" or a "Shedding Action" is to answer it — exactly the same reasoning EDR-003 already established for Relay Capability. A registry that also decided *whether* a UFLS stage should exclude that candidate would be answering a question that belongs to UFLS's own philosophy, not to this registry's.

**Physical facilities, not organizations, keep the registry's subject matter unambiguous.** "Hospital Kuala Lumpur" is one place with one (current) supply point. "Ministry of Health" is an administrative body that could refer to dozens of unrelated physical locations, none of which map cleanly to a single Transformer Terminal. Scoping the registry to physical facilities keeps every record answerable against a concrete engineering question ("what supplies this place") rather than requiring the registry to also model organizational hierarchy, which it has no engineering need for.

**Reusability requires the registry to stay ignorant of every consumer's own philosophy, not just GridDefence's.** A future non-GridDefence transmission-engineering application will have its own rules about what "High sensitivity" means for its own decisions — possibly rules that don't even resemble a shedding scheme's rules at all. The only way this registry can serve both GridDefence today and an unknown consumer later is if its own data never encodes any one consumer's interpretation. This sharpens EDR-003's original scope-discipline argument: it is no longer only about keeping one module maintainable, but about keeping the registry's engineering facts genuinely portable.

**Facility management (CRM, billing, GIS, service contracts) is a different discipline this platform does not need and should not build.** GridDefence needs to know "this place is sensitive, at what level, and what supplies it" — nothing about contact persons, tariffs, correspondence, or precise geographic coordinates is needed to answer any workflow question this registry exists to serve. Building that would repeat, in a new module, exactly the asset-management scope creep EDR-003 already rejected for relay data.

**This mirrors how GridDefence scopes every Engineering Knowledge registry.** Substation Registry, Equipment Registry, and the Automatic Load Shedding Functionality Registry are each scoped to the specific engineering question the platform actually needs answered, not to being an exhaustive record of everything that could theoretically be known about the underlying physical or organizational reality. The Sensitive Customer Registry follows the same discipline, and — per [ADR-012](../../adr/ADR-012-sensitive-customer-registry-architecture.md) — remains a distinct registry from the separately-scoped Critical Infrastructure concept rather than being folded into it.

## Consequences

**Positive:**
- The registry stays focused on a fact any consumer — GridDefence today, a different transmission-engineering application later — can trust and interpret for itself.
- GridDefence avoids building customer-relationship, billing, or geographic-information functionality that has no engineering workflow depending on it.
- Sensitivity classification (High/Medium/Low, per the agreed engineering principles) remains a plain engineering fact; each consuming defence scheme is free to interpret it according to its own philosophy without that interpretation leaking back into the registry's own data.
- Because the registry never encodes GridDefence-specific vocabulary, extracting it into a standalone service for a second consuming application later (CLAUDE.md §6, F6) requires no change to what the registry itself owns or answers — only to how it is transported.

**Negative / trade-offs:**
- GridDefence cannot answer detailed facility-management questions (contact persons, service agreements, correspondence, precise site plans) from this registry — those remain the responsibility of whatever system, if any, owns facility/customer relationship management, entirely outside this platform's scope.
- The registry currently models only a facility's *current* supply point (one Transformer Terminal), not historical or alternate supply arrangements. If a genuine engineering need for multi-point or historical supply modelling emerges, that is a new, separate engineering question requiring its own decision — it should not be quietly retrofitted into this registry's current, narrowly-scoped current-state design (see `sensitive-customer-registry-module.md` §17, §19).
- Because sensitivity classification carries no built-in enforcement meaning, a defence scheme module that never actually consults this registry, or that consults it but chooses to ignore its findings, is not prevented from doing so by this registry itself — enforcement, if any is ever wanted, is each consuming scheme module's own responsibility to design and is explicitly not decided by this EDR (see `sensitive-customer-registry-module.md` §17, Open Question).
