# GridDefence Engineering Concepts

This document defines, in engineering terms, the core concepts every contributor to GridDefence — engineer, developer, or AI coding agent — must understand before designing, building, or reviewing any part of the system. It expands [01-engineering-philosophy.md](01-engineering-philosophy.md); it does not reinterpret it. Where a concept here touches a specific software decision, a pointer to the relevant Architecture Decision Record (ADR) or Engineering Decision Record (EDR) is given at the end of that concept's entry — those records are not restated here.

Each concept is defined the way a power system engineer would explain it to a colleague: what it is, why it exists, why it matters to the grid, and how it relates to the concepts around it.

---

## Grid Defence

**Definition.** Grid Defence is the set of coordinated, pre-planned operational strategies used to protect the stability of the interconnected transmission system during major disturbances — frequency excursions, voltage collapse, or loss of critical infrastructure — by deliberately removing load or reconfiguring the network before the disturbance can cascade into a wider blackout.

**Purpose.** A transmission grid cannot be protected the way one piece of equipment is protected. A transformer differential relay protects a transformer; a distance relay protects a line. Grid Defence exists because none of those local protections, acting alone, can prevent a system-wide collapse triggered by a large generation loss, a cascading line trip, or a sudden imbalance between generation and demand. Grid Defence acts on the *system*, not the *asset*.

**Engineering significance.** Grid Defence is the last organized line of defence before an uncontrolled, cascading blackout. Its schemes are designed, reviewed, and maintained with the same rigor as any other critical protection system, but they operate at a different scale — substations and regions, not individual bays.

**Relationship to other concepts.** Grid Defence is realized through one or more **Grid Defence Schemes** (UFLS, UVLS, EMLS today; future schemes without changing this concept). Everything else in this document — Stages, Shedding Actions, registries, PSS®E snapshots — exists in service of designing, validating, and governing those schemes.

---

## Grid Defence Scheme

**Definition.** A Grid Defence Scheme is an engineered, version-controlled operational strategy that defines what load is shed, where, and under what triggering condition, in order to preserve transmission system stability during a defined class of disturbance (frequency, voltage, or manually-invoked emergency).

**Purpose.** A scheme turns an engineering judgement ("if frequency falls below 49.0 Hz, shed 800 MW from this set of transformer bays") into a durable, approved, executable engineering record — not a one-time calculation, but a maintained document that the grid operator relies on every day it is Active.

**Engineering significance.** A scheme is only useful if it remains technically executable against the *real, current* network — a scheme designed against a network that has since changed structurally (a transformer removed, a line decommissioned) may no longer shed the load it claims to. This is why every scheme is continuously validated against the latest PSS®E information (see **Validation**), even though the scheme itself does not change automatically.

**Relationship to other concepts.** A Grid Defence Scheme is composed of one or more **Stages**. It progresses through a **Scheme Lifecycle** (Working Draft → Scheme Review → Published Scheme → eventually Archived Scheme). It is designed against a selected **PSS®E Load Snapshot** and **PSS®E Network Topology**, filtered by the **Sensitive Customer** registry, and constrained by **Grid Defence Capability**. UFLS, UVLS, and EMLS are the three Grid Defence Schemes GridDefence currently manages (01-engineering-philosophy.md §3).

---

## Scheme Lifecycle

**Definition.** The Scheme Lifecycle is the ordered sequence of engineering states a Grid Defence Scheme version passes through, from initial design to eventual retirement, each state carrying a different degree of engineering authority.

**Purpose.** Not every version of a scheme is equally trustworthy. A scheme an engineer is actively editing must be clearly distinguishable from a scheme that has been reviewed and is currently governing real operational behaviour. The lifecycle exists to make that distinction unambiguous to every reader — another engineer, an auditor, or the system itself.

**Engineering significance.** The lifecycle is what makes a scheme's engineering authority *legible at a glance*: a **Working Draft** is exploratory and may change freely; a **Published Scheme** is the current operational reference and is never silently edited; an **Archived Scheme** is historical record, kept forever, never deleted.

**Relationship to other concepts.** The lifecycle governs one **Grid Defence Scheme** version at a time. **Scheme Review** is the gate between Working Draft and Published Scheme. Only one Published Scheme may be the operational reference for a given scheme type at any moment; every prior Published version becomes an Archived Scheme when superseded. See [EDR-004](edr/EDR-004-decision-support-not-automation.md) for why this lifecycle exists as engineering governance rather than as a technical convenience, and `docs/adr/ADR-010-engineering-decision-support-philosophy.md` for the corresponding software classification (Approved Engineering Policy, governed by the full Canonical Version Lifecycle).

---

## Working Draft

**Definition.** A Working Draft is a Grid Defence Scheme version an engineer is actively designing or revising. It has no operational authority — it does not govern any real load-shedding behaviour.

**Purpose.** Scheme design is iterative: an engineer selects a PSS®E snapshot, evaluates loads, checks sensitive customers, verifies capability, and assembles stages, often revising earlier choices as later ones reveal a problem. A Working Draft gives the engineer room to do this freely, without any risk of a half-finished idea being mistaken for an approved engineering decision.

**Engineering significance.** Because a Working Draft carries no authority, recommendations shown to the engineer while drafting (available load, capability status, sensitive-customer conflicts) are always clearly informational — advisory, not final, until the draft is submitted for **Scheme Review**.

**Relationship to other concepts.** A Working Draft becomes a candidate for **Scheme Review** once the engineer believes it is complete. It may reference any **PSS®E Load Snapshot**/**PSS®E Network Topology** for evaluation, but nothing it contains is fixed until review and publication.

---

## Published Scheme

**Definition.** A Published Scheme is a Grid Defence Scheme version that has completed Scheme Review and is now the operational reference the grid relies on for its defence strategy.

**Purpose.** A Published Scheme is what an operator, an auditor, or another engineering study consults when they ask "what does the defence scheme currently do." It must be stable, unambiguous, and never quietly change underneath anyone relying on it.

**Engineering significance.** A Published Scheme is immutable once published — a correction is never an edit to a Published Scheme, it is a new Working Draft that goes through review again and, once approved, becomes the new Published Scheme, superseding the old one. This is what makes "what did the scheme say on a given date" always answerable with certainty.

**Relationship to other concepts.** Only one scheme version of a given type is Published (the operational reference) at a time. When a new version is published, the previous Published Scheme becomes an **Archived Scheme** — this transition happens as a single, deliberate engineering act, not automatically as a side effect of anything PSS®E-related.

---

## Archived Scheme

**Definition.** An Archived Scheme is a Grid Defence Scheme version that was previously the operational reference (a Published Scheme) but has since been superseded by a newer Published version.

**Purpose.** Grid Defence Schemes have real operational history: a disturbance that occurred last year was governed by whatever scheme was Published at that time, not by today's scheme. Archived Schemes preserve that history permanently, so it can always be reconstructed.

**Engineering significance.** Archiving is never deletion. An Archived Scheme remains fully readable, fully auditable, and fully reproducible indefinitely — exactly as it was the day it was superseded.

**Relationship to other concepts.** Every Published Scheme eventually becomes an Archived Scheme, exactly once, at the moment its successor is published. An Archived Scheme's own history of **Scheme Review** and revision remains attached to it permanently.

---

## Scheme Review

**Definition.** Scheme Review is the formal engineering evaluation a Working Draft undergoes before it may become a Published Scheme — checking completeness, technical soundness, and alignment with current network and operational policy.

**Purpose.** A scheme governs real load-shedding behaviour once published; review is the checkpoint that catches a mistake, an oversight, or an outdated assumption before it becomes the operational reference, not after.

**Engineering significance.** Review records who reviewed the scheme, what they found, and what engineering remarks accompanied their decision — this record becomes part of the scheme's permanent history the moment it is published (01-engineering-philosophy.md §5, Step 8).

**Relationship to other concepts.** Scheme Review sits between **Working Draft** and **Published Scheme** in the **Scheme Lifecycle**. It may surface findings from **Validation** (e.g. a stage referencing a bay whose capability has since changed) that the reviewing engineer must explicitly address before approving.

---

## Stage

**Definition.** A Stage is a named subdivision of a Grid Defence Scheme, triggered at a specific frequency or voltage threshold (with an associated time delay), that groups together the Shedding Actions to be executed when that threshold is crossed.

**Purpose.** A single disturbance rarely calls for shedding all planned load at once. Staging lets a scheme shed progressively larger amounts of load as a disturbance worsens, giving the system a chance to stabilize after each stage rather than over-shedding on the first trigger.

**Engineering significance.** The composition of a stage — which bays, which lines, which pockets are grouped together, and at what threshold — is entirely an engineering judgement call; GridDefence records and enforces the structure of that judgement, it does not compute it (01-engineering-philosophy.md §5, Step 7).

**Relationship to other concepts.** A **Grid Defence Scheme** contains one or more Stages. A Stage contains one or more **Shedding Actions**, of any combination of type (Transformer Bay Shedding, Line Bay Shedding, Boundary Line Shedding).

---

## Shedding Action

**Definition.** A Shedding Action is a single, specific instruction within a Stage to disconnect a defined piece of equipment or a defined electrical boundary, contributing a known quantity of load to that stage's total.

**Purpose.** A Shedding Action is the atomic unit of a defence scheme's actual grid impact — everything above it (Stage, Scheme) is organizational; the Shedding Action is where an engineering decision meets a physical switching device.

**Engineering significance.** Every Shedding Action must reference real, currently-capable equipment (see **Grid Defence Capability**) and must not target a **Sensitive Customer**-excluded load. Its expected MW/MVAr contribution is evaluated against a specific **PSS®E Load Snapshot**, and that evaluation is a recommendation to the engineer, not an automatically-enforced constraint.

**Relationship to other concepts.** A **Stage** contains one or more Shedding Actions. A Shedding Action is one of: **Transformer Bay Shedding**, **Line Bay Shedding**, or a **Boundary Line** action defining a **Load Pocket**.

---

## Bay

**Definition.** A Bay is the permanent engineering identity of one substation's local connection point to a single piece of **Primary Equipment** — a transformer or a transmission line — together with the breaker that connects or disconnects it. A Bay belongs to exactly one Substation. A Transformer Bay and a Line Bay are the two kinds of Bay.

**Purpose.** A substation is physically organized around its bays, not around whichever equipment currently occupies them: a bay is a fixed structural position — breaker, isolators, and protection wiring — that can, over the operational life of a substation, host different primary equipment as the network is upgraded, replaced, or reconfigured. Grid Defence needs a stable identity to assign a Shedding Action to that survives this kind of change, and the Bay is that identity — not the equipment inside it.

**Engineering significance.** Primary equipment may change — a transformer may be replaced with a higher-capacity unit, a line may be re-terminated — but the Bay itself, and its relationship to its Substation and its Breaker, normally persists throughout the substation's operational life. This is why a **Transformer Bay Shedding** or **Line Bay Shedding** action is ultimately an assignment to a Bay, not a permanent binding to one physical asset. A Bay is also what **Grid Defence Capability** (via the **Relay Registry**) is recorded against, and what PSS®E topology correlation ultimately resolves to.

**Implementation.** GridDefence's current implementation already represents Bays, under different names, at exactly the granularity this concept requires — no generic `Bay` database entity exists or is required:
- **Transformer Bay → `TransformerTerminal`** (Equipment Registry) — one side (HV or LV) of a `Transformer`, with its own identity, its own breaker, and its own voltage yard.
- **Line Bay → `CircuitTerminal`** (Equipment Registry) — one substation's own terminal of a `Circuit`, already the object PSS®E's `EquipmentTopologyMap` correlates against, and the object a future Relay Registry entry would attach to.

See [EDR-005](edr/EDR-005-bay-as-engineering-identity.md) for the full engineering decision, and [08-engineering-terminology.md](08-engineering-terminology.md) for the complete engineering-to-implementation translation table.

**Relationship to other concepts.** A Bay **hosts** one piece of **Primary Equipment** (a transformer or a transmission line) and **belongs to** exactly one **Substation**. A **Shedding Action** of type **Transformer Bay Shedding** or **Line Bay Shedding** references a Bay. A Bay's **Grid Defence Capability** is recorded in the **Relay Registry**.

---

## Transformer Bay Shedding

**Definition.** Transformer Bay Shedding is a Shedding Action that disconnects a specific transformer bay at a substation, removing the load served through that transformer from the system.

**Purpose.** Most transmission-connected load is served through transformer bays stepping down to distribution voltage; disconnecting a bay is the most direct, most common way to remove a known quantity of load (01-engineering-philosophy.md §5, Step 3 — approximately 80% of practical defence schemes use this strategy).

**Engineering significance.** The load removed by a transformer bay shedding action is read from the selected **PSS®E Load Snapshot** at the time the engineer evaluates it, and its capability to be shed at all is verified against the **Relay Registry** before it may be selected.

**Relationship to other concepts.** This is one of the two "local bay shedding" strategies (01-engineering-philosophy.md §5, Strategy A), alongside **Line Bay Shedding**. Both target one piece of equipment directly, as opposed to **Boundary Line** shedding, which isolates a whole **Load Pocket**.

---

## Line Bay Shedding

**Definition.** Line Bay Shedding is a Shedding Action that disconnects a specific transmission line bay at a substation, removing whatever load is served beyond that line (directly, or as part of a larger disconnection).

**Purpose.** Some load is more naturally shed at the transmission line level than at an individual transformer — for example, when a scheme's engineering intent is to disconnect an entire downstream area rather than one transformer at one substation.

**Engineering significance.** Line Bay Shedding accounts for a smaller share of practical schemes than transformer bay shedding (01-engineering-philosophy.md §5, Step 3 — roughly 20%), but is the natural building block for **Boundary Line** shedding, where multiple line bays are opened together to isolate a pocket.

**Relationship to other concepts.** A Line Bay Shedding action targets one specific line bay. When several such actions are combined specifically to enclose and isolate a region of the network, the result is a **Boundary Line** action defining a **Load Pocket**, not a set of independent Line Bay Shedding actions.

---

## Boundary Line

**Definition.** A Boundary Line is a transmission line whose disconnection, together with one or more other Boundary Lines, electrically isolates a defined region of the network — a Load Pocket — as a single block.

**Purpose.** Rather than identifying every individual load within a region and shedding each one, an engineer may choose to open the small number of lines that connect that region to the rest of the grid, disconnecting the entire enclosed pocket at once (01-engineering-philosophy.md §5, Strategy B).

**Engineering significance.** Correctly identifying which lines form a valid boundary — and confirming that opening them genuinely isolates the intended pocket, no more and no less — depends on the actual, current electrical topology of the network, not on assumption or memory. This is precisely why Boundary Line shedding "relies heavily on the PSS®E topology model" (01-engineering-philosophy.md §5).

**Relationship to other concepts.** A set of Boundary Lines, opened together, defines a **Load Pocket**. Their validity as a boundary is evaluated against the currently selected **PSS®E Network Topology** (and, in the future, computed connectivity/island analysis built on top of it).

---

## Load Pocket

**Definition.** A Load Pocket is the electrically isolated region of the network that results when its defining **Boundary Line**(s) are opened — a set of substations and their load, disconnected from the rest of the grid as a single unit.

**Purpose.** A Load Pocket lets a scheme shed a whole region's load with a small number of switching actions (the boundary lines), rather than enumerating every transformer bay within that region individually.

**Engineering significance.** The size and composition of a Load Pocket — which substations actually fall inside it, and how much load that represents — is a direct consequence of the network's real topology at the time the boundary is evaluated. A structural change to the network (a new interconnection, a decommissioned substation) can change what a given boundary actually isolates, which is exactly the kind of change **Validation** exists to surface.

**Relationship to other concepts.** A Load Pocket is defined by one or more **Boundary Line** shedding actions and evaluated against **PSS®E Network Topology**. Its aggregate expected load is read from the currently selected **PSS®E Load Snapshot**.

---

## Grid Defence Capability

**Definition.** Grid Defence Capability is the engineering property of a specific bay or switching point indicating whether it can be operated (opened) as part of a Grid Defence Scheme action.

**Purpose.** Not every bay in the network is wired to a protection scheme capable of executing a fast, coordinated defence trip — some may lack the necessary relay/tripping arrangement entirely. A scheme can only assign a bay to a Shedding Action if that bay is actually, physically capable of being operated that way.

**Engineering significance.** Grid Defence Capability is a yes/no engineering question about *whether this bay can be used for Grid Defence at all* — it is deliberately not a detailed relay asset record. Manufacturer, model, and firmware information may exist, but they are secondary; the question that matters is capability (01-engineering-philosophy.md §5, Step 5).

**Relationship to other concepts.** Grid Defence Capability is recorded in, and answered by, the **Relay Registry**. Every **Shedding Action** must reference equipment whose capability has been verified before it may be selected for a scheme. See [EDR-003](edr/EDR-003-relay-registry-scope.md) for why the Relay Registry is scoped to this question specifically, and not to general relay asset management.

---

## Relay Registry

**Definition.** The Relay Registry is the engineering registry that records, for each bay or switching point in the network, whether it possesses **Grid Defence Capability** — the ability to be operated by a Grid Defence Scheme.

**Purpose.** Before an engineer can assign a bay to a Shedding Action, they need a fast, authoritative answer to one question: can this bay actually be operated by Grid Defence? The Relay Registry exists to answer exactly that question, and no more.

**Engineering significance.** The Relay Registry is deliberately *not* a general-purpose relay asset management system. It does not track maintenance history, settings files, or firmware versions as primary data — those may be recorded as secondary metadata, but the registry's authoritative purpose is the capability answer alone (01-engineering-philosophy.md §5, Step 5). This scoping decision is deliberate and durable — see [EDR-003](edr/EDR-003-relay-registry-scope.md).

**Relationship to other concepts.** The Relay Registry is part of **Engineering Knowledge** (Layer 1). It is consulted every time an engineer attempts to add a **Shedding Action** referencing a specific bay, and its answer does not depend on, or change with, the currently selected **PSS®E Load Snapshot**.

---

## Sensitive Customer

**Definition.** A Sensitive Customer is a load connection that is excluded, by operational policy, from being selected for load shedding — for example a hospital, an airport, a strategic industry, or essential public infrastructure.

**Purpose.** Some loads must never be interrupted by an automatic or emergency defence action, regardless of how attractive they might otherwise look from a pure MW-shedding standpoint. The Sensitive Customer designation exists to make this exclusion explicit and enforceable during scheme design.

**Engineering significance.** Excluding sensitive customers is not optional engineering polish — it is a hard operational policy constraint, checked during scheme design before a load is ever offered as a candidate for a Shedding Action (01-engineering-philosophy.md §5, Step 4).

**Relationship to other concepts.** The Sensitive Customer Registry is part of **Engineering Knowledge** (Layer 1). It is consulted during the evaluation of available loads for **Transformer Bay Shedding** and **Line Bay Shedding**, and its exclusions apply regardless of which **PSS®E Load Snapshot** is currently selected.

---

## PSS/E Network Topology

**Definition.** PSS/E Network Topology is the structural, electrical model of the transmission network — buses, branches, and transformers, and how they connect — as imported from a PSS®E case file.

**Purpose.** Scheme design, especially Boundary Line/Load Pocket shedding, depends on knowing the network's actual electrical connectivity — not an engineer's memory of it, and not a static diagram that may be out of date.

**Engineering significance.** Topology changes rarely — only when the physical network genuinely changes (a line commissioned, a bus renumbered, a substation retired) — but when it does change, every scheme that depends on the affected part of the network needs to be re-evaluated. This is why topology is held as a distinct, versioned artifact rather than being re-derived every time it's needed.

**Relationship to other concepts.** PSS/E Network Topology is one of the two components of **Operational Context** (Layer 2), alongside **PSS/E Load Snapshot**. It is what **Boundary Line** validity and **Load Pocket** composition are evaluated against. See `docs/adr/ADR-003-psse-topology-and-load-snapshot-separation.md` for the corresponding software decision separating topology from load data, and [EDR-001](edr/EDR-001-psse-as-operational-context.md) for why PSS/E data of any kind is operational context, never engineering authority.

---

## PSS/E Load Snapshot

**Definition.** A PSS/E Load Snapshot is a captured record of the network's load and generation state (P/Q at each bus) at a specific point in time, evaluated against a specific PSS/E Network Topology.

**Purpose.** Load conditions change constantly — by time of day, by season, by operating scenario. A scheme designer needs to be able to ask "how much load would this action actually shed under peak conditions" or "under this specific operational scenario," and get a real, current answer.

**Engineering significance.** A snapshot is a temporary operational reference, not a permanent engineering record (01-engineering-philosophy.md §8). Many snapshots can exist against the same topology over time (peak, off-peak, seasonal, scenario-specific); none of them, by themselves, ever become part of a scheme's approved engineering record. If a value informed by a snapshot is to become authoritative, an engineer must capture it explicitly into the scheme at the moment of approval.

**Relationship to other concepts.** A PSS/E Load Snapshot is always evaluated against exactly one **PSS/E Network Topology**. It is the source of the expected MW/MVAr contribution shown for a candidate **Shedding Action**, and the basis for **Continuous Validation**'s "changed loading" check.

---

## Operational Context

**Definition.** Operational Context is the layer of dynamic, PSS®E-derived information — network topology and load snapshots — that describes the network's condition at a given point in time.

**Purpose.** Operational Context gives engineers an accurate, current picture of the real network to design and validate schemes against, without that picture ever being mistaken for the schemes themselves.

**Engineering significance.** Operational Context is explicitly *not* engineering authority (01-engineering-philosophy.md §9 principle). It informs and supports engineering decisions; it never overwrites or automatically alters them. A new PSS®E import updating Operational Context never, by itself, changes a Published Scheme.

**Relationship to other concepts.** Operational Context is Layer 2 of the three **Engineering Information Layers** (01-engineering-philosophy.md §6), composed of **PSS/E Network Topology** and **PSS/E Load Snapshot**. It sits between **Engineering Knowledge** (Layer 1, slow-changing) and **Engineering Decisions** (Layer 3, version-controlled) — informing the latter without ever becoming it. See [EDR-001](edr/EDR-001-psse-as-operational-context.md) for why it never becomes engineering authority, and [EDR-006](edr/EDR-006-operational-context-visualization.md) for why it should ultimately be presented visually, not only in text.

---

## Engineering Knowledge

**Definition.** Engineering Knowledge is the slow-changing, engineer-curated information describing the physical engineering environment — substations, equipment, line connectivity, relay capability, and sensitive customer designations.

**Purpose.** Scheme design needs a stable, authoritative description of "what exists and what do we call it" that does not change every time a new PSS®E file is imported, and that persists independently of any one study or scenario.

**Engineering significance.** Engineering Knowledge is the authoritative reference layer — when it disagrees with an inference drawn from Operational Context (for example, PSS®E topology implying a circuit's far end has changed), the disagreement is a **Validation** finding requiring engineering review, never something Operational Context is allowed to silently overwrite.

**Relationship to other concepts.** Engineering Knowledge is Layer 1 of the three **Engineering Information Layers** (01-engineering-philosophy.md §6): the Substation Registry, Equipment Registry, Line Connectivity Registry, **Relay Registry**, and Sensitive Customer Registry. It is referenced by, but never derived from, **Operational Context** or **Engineering Decisions**.

---

## Engineering Decision

**Definition.** An Engineering Decision is a deliberate, human, authenticated choice made by an engineer that becomes part of GridDefence's permanent engineering record — most centrally, the act of publishing a Grid Defence Scheme version, but also the act of resolving a validation finding or reviewing a discrepancy.

**Purpose.** GridDefence exists to support Engineering Decisions, not to make them (01-engineering-philosophy.md §2's guiding principle). Every point where the system could plausibly "just decide automatically" is instead a point where the system presents information and waits for an engineer to decide.

**Engineering significance.** An Engineering Decision is what converts a recommendation, a validation finding, or a draft into something with real engineering authority. Before that moment, information is advisory; after it, it is part of the permanent record, traceable to who decided, when, and why.

**Relationship to other concepts.** Publishing a **Working Draft** into a **Published Scheme** is the central example of an Engineering Decision. Resolving a **Validation** finding is another. See [EDR-004](edr/EDR-004-decision-support-not-automation.md) and `docs/adr/ADR-010-engineering-decision-support-philosophy.md` for the full reasoning behind why GridDefence is built this way.

---

## Validation

**Definition.** Validation is GridDefence's continuous, automated comparison of existing Grid Defence Schemes against the latest Operational Context, reporting any engineering impact it finds — without redesigning, approving, or rejecting anything itself.

**Purpose.** A Published Scheme's technical executability depends on the real network continuing to match what the scheme assumed when it was designed. Validation exists to catch the moment that assumption stops holding — a transformer removed, a line decommissioned, a bay assignment no longer valid, a materially changed expected shed load — as early and clearly as possible.

**Engineering significance.** Validation reports impact; it never decides response. This distinction is the core of GridDefence's entire philosophy (01-engineering-philosophy.md §7) and is treated at full length in [06-validation-philosophy.md](06-validation-philosophy.md).

**Relationship to other concepts.** Validation compares **Engineering Decisions** (Published Schemes) against current **Operational Context** (topology and load snapshots), and its findings are surfaced to an engineer, who then makes the actual **Engineering Decision** about whether a **Scheme Review** is warranted.

---

## Engineering Metadata

**Definition.** Engineering Metadata is the descriptive, accountability-carrying information attached to an engineering record — scheme version, review information, approval details, engineering remarks, and revision history — that is not itself the engineering content but explains its provenance.

**Purpose.** A Published Scheme is only as trustworthy as the record of who approved it, when, and why. Engineering Metadata is what makes a scheme's history reconstructable years later, not just its current content.

**Engineering significance.** Engineering Metadata is recorded at every meaningful engineering event — most visibly at publication (01-engineering-philosophy.md §5, Step 8) — and, once recorded, is never altered or removed; a correction adds new metadata, it does not erase old metadata.

**Relationship to other concepts.** Engineering Metadata accompanies every **Grid Defence Scheme** version through its **Scheme Lifecycle**, and every **Scheme Review** decision. It is the durable record of engineering accountability underlying the whole platform's traceability requirement (01-engineering-philosophy.md §10, principle 4).
