# GridDefence Engineering Glossary

This is the standard terminology reference for the GridDefence project. Every term below is defined consistently with [01-engineering-philosophy.md](01-engineering-philosophy.md) and expanded upon in [02-engineering-concepts.md](02-engineering-concepts.md). Where a term has a fuller treatment elsewhere in this library, that document is linked. Use these terms exactly as defined here — do not introduce a synonym for a concept that already has a name in this glossary.

For the corresponding **implementation** name of any engineering term below (which entity, table, or module realizes it in code), see [08-engineering-terminology.md](08-engineering-terminology.md) — the authoritative engineering-to-implementation translation table. This glossary defines engineering meaning; it does not restate implementation detail.

---

**Archived Scheme** — A Grid Defence Scheme version that was previously the operational reference (a Published Scheme) but has since been superseded by a newer Published version. Preserved permanently, never deleted. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Automatic Load Shedding Functionality Registry (ALSF)** — The Engineering Knowledge registry recording, per Bay Terminal, whether automatic UFLS and/or UVLS shedding functionality is installed, wired, configured, commissioned, and available, with a computed Available/Assigned/Decommissioned status. This is the implementation of the engineering concept previously discussed as **Relay Registry** — see that entry below. Complete; see [ADR-011](../adr/ADR-011-automatic-load-shedding-functionality-registry.md) and `docs/architecture/automatic-load-shedding-functionality-registry-module.md`.

**Bay** — The permanent engineering identity of one substation's local connection point to a single piece of Primary Equipment (a transformer or a transmission line), together with its breaker. A Transformer Bay and a Line Bay are the two kinds. Primary equipment hosted by a Bay may change over time; the Bay's own identity normally does not. Currently represented in the implementation by `TransformerTerminal` (Transformer Bay) and `CircuitTerminal` (Line Bay) — see [02-engineering-concepts.md](02-engineering-concepts.md), [EDR-005](edr/EDR-005-bay-as-engineering-identity.md), and [08-engineering-terminology.md](08-engineering-terminology.md).

**Boundary Line** — A transmission line whose disconnection, together with one or more other Boundary Lines, electrically isolates a Load Pocket as a single block. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Continuous Validation** — GridDefence's ongoing comparison of Published Schemes against the latest Operational Context, for as long as a scheme remains published. See **Validation**; [06-validation-philosophy.md](06-validation-philosophy.md).

**Core Platform** — The set of GridDefence capabilities that create, curate, and govern engineering truth: Registries, PSS/E Integration, Scheme Management, Validation, and Version Control. See [07-future-roadmap.md](07-future-roadmap.md).

**Emergency Manual Load Shedding (EMLS)** — One of the three Grid Defence Schemes GridDefence manages; a manually-invoked, priority-ordered shedding scheme with no automatic frequency or voltage trigger.

**Engineering Decision** — A deliberate, human, authenticated choice that becomes part of GridDefence's permanent engineering record — publishing a scheme, resolving a validation finding, correcting a registry. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Engineering Knowledge** — The slow-changing, engineer-curated information layer describing the physical engineering environment: the Substation Registry, Equipment Registry, Line Connectivity Registry, Relay Registry, and Sensitive Customer Registry. Layer 1 of the three Engineering Information Layers. See [01-engineering-philosophy.md](01-engineering-philosophy.md) §6.

**Engineering Metadata** — Descriptive, accountability-carrying information attached to an engineering record: scheme version, review information, approval details, engineering remarks, and revision history. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Engineering Study** — An external power system study (performed outside GridDefence, typically using PSS®E and professional engineering judgement) that determines a defence scheme's operational requirement — for example, the required load shedding quantum.

**Equipment Registry** — The Engineering Knowledge registry recording physical/electrical equipment identity — transformer bays, line bays, and their connection points.

**Grid Defence** — The set of coordinated, pre-planned operational strategies used to protect the stability of the interconnected transmission system during major disturbances by deliberately removing load or reconfiguring the network. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Grid Defence Capability** — The engineering property of a specific bay or switching point indicating whether it can be operated as part of a Grid Defence Scheme action. Recorded in the Relay Registry (see that entry — implemented as the Automatic Load Shedding Functionality Registry). See [02-engineering-concepts.md](02-engineering-concepts.md).

**Grid Defence Scheme** — An engineered, version-controlled operational strategy defining what load is shed, where, and under what triggering condition, to preserve transmission system stability during a defined class of disturbance. UFLS, UVLS, and EMLS are the three Grid Defence Schemes GridDefence currently manages. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Line Bay Shedding** — A Shedding Action that disconnects a specific transmission line bay at a substation. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Line Connectivity Registry** — A curated metadata registry for line/circuit identity and engineering attributes (bay numbers, breaker numbers, line type, interconnector flags, commissioning dates), part of Engineering Knowledge (Layer 1). It is not the authoritative source of *current* electrical topology or connectivity — that is Operational Snapshot's role (Layer 2). See **Operational Context**, [EDR-007](edr/EDR-007-phase-7-operational-identity-mapping.md), and `docs/architecture/operational-snapshot-architecture.md`. The same distinction applies to Equipment Registry's transformer-asset records: curated identity/metadata, not authoritative current operational transformer representation.

**Load Assessment** — The workflow step in which an engineer identifies which loads are available in the network, using the selected PSS/E Load Snapshot. See [03-system-workflow.md](03-system-workflow.md).

**Load Pocket** — The electrically isolated region of the network that results when its defining Boundary Line(s) are opened. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Operational Context** — The layer of dynamic, PSS®E-derived information (network topology and load snapshots) describing the network's condition at a given point in time. Layer 2 of the three Engineering Information Layers; informs, but never becomes, an Engineering Decision. See [01-engineering-philosophy.md](01-engineering-philosophy.md) §6, §9.

**Publication** — The workflow step at which a reviewed Working Draft becomes the new Published Scheme, its engineering metadata is permanently recorded, and any previous Published version of the same scheme type becomes an Archived Scheme. See [03-system-workflow.md](03-system-workflow.md).

**Published Scheme** — A Grid Defence Scheme version that has completed Scheme Review and is the current operational reference. Immutable once published. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Relay Capability Verification** — The workflow step in which an engineer confirms, via the Relay Registry, that a candidate bay or switching point has Grid Defence Capability. The registry side of this step is implemented (Automatic Load Shedding Functionality Registry); the step becomes fully realized once UFLS/UVLS (not yet built) call its capability interfaces during Selection of Shedding Actions. See [03-system-workflow.md](03-system-workflow.md).

**Relay Registry** — The engineering concept naming the registry that records, for each bay or switching point, whether it has Grid Defence Capability. Deliberately scoped to this capability question, not general relay asset management. **Implemented as the Automatic Load Shedding Functionality Registry** (see that entry above) — "Relay Registry" is retired as a working/implementation name, per [ADR-011](../adr/ADR-011-automatic-load-shedding-functionality-registry.md), but remains the name of the underlying engineering concept this glossary and [02-engineering-concepts.md](02-engineering-concepts.md) describe. See [EDR-003](edr/EDR-003-relay-registry-scope.md).

**Review** (Scheme Review) — The formal engineering evaluation a Working Draft undergoes before it may become a Published Scheme. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Selection of Shedding Actions** — The workflow step in which an engineer chooses which validated, capable, non-sensitive loads to include as concrete Shedding Actions. See [03-system-workflow.md](03-system-workflow.md).

**Scheme Lifecycle** — The ordered sequence of engineering states a Grid Defence Scheme version passes through: Working Draft → Scheme Review → Published Scheme → Archived Scheme. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Sensitive Customer** — A load connection excluded, by operational policy, from being selected for load shedding — e.g. a hospital, airport, strategic industry, or essential public infrastructure. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Sensitive Customer Review** — The workflow step in which candidate loads are checked against the Sensitive Customer registry and excluded loads are removed from consideration. See [03-system-workflow.md](03-system-workflow.md).

**Shedding Action** — A single, specific instruction within a Stage to disconnect a defined piece of equipment or electrical boundary, contributing a known quantity of load. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Stage** — A named subdivision of a Grid Defence Scheme, triggered at a specific frequency or voltage threshold with an associated time delay, grouping the Shedding Actions executed together. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Stage Coordination** — The workflow step in which selected Shedding Actions are grouped into Stages with their triggering thresholds. See [03-system-workflow.md](03-system-workflow.md).

**Substation Registry** — The Engineering Knowledge registry recording substation identity, metadata, geography, and operational status.

**Supporting Module** — A GridDefence capability (Reporting, Dashboard, Heatmaps, Analytics, Historical Comparison, Statistics, Audit Summaries) that consumes Core Platform information without ever originating engineering truth of its own. See [07-future-roadmap.md](07-future-roadmap.md).

**Transformer Bay Shedding** — A Shedding Action that disconnects a specific transformer bay at a substation. The most common form of Shedding Action in practice. See [02-engineering-concepts.md](02-engineering-concepts.md).

**Under Frequency Load Shedding (UFLS)** — One of the three Grid Defence Schemes GridDefence manages; sheds load in stages as system frequency falls below defined thresholds.

**Under Voltage Load Shedding (UVLS)** — One of the three Grid Defence Schemes GridDefence manages; sheds load in stages as system voltage falls below defined thresholds.

**Validation** — GridDefence's continuous, automated comparison of existing Grid Defence Schemes against the latest Operational Context, reporting engineering impact without deciding a response. See [02-engineering-concepts.md](02-engineering-concepts.md); [06-validation-philosophy.md](06-validation-philosophy.md).

**Working Draft** — A Grid Defence Scheme version an engineer is actively designing or revising, carrying no operational authority. See [02-engineering-concepts.md](02-engineering-concepts.md).

**PSS®E** — The external power system simulation software (from Siemens PTI) used to perform load flow, stability, and other studies of the transmission network. GridDefence imports its network models and load data as Operational Context but never performs PSS®E's own studies itself.

**PSS/E Load Snapshot** — A captured record of the network's load and generation state at a specific point in time, evaluated against a specific PSS/E Network Topology. A temporary operational reference, never a permanent engineering record. See [02-engineering-concepts.md](02-engineering-concepts.md).

**PSS/E Network Topology** — The structural, electrical model of the transmission network — buses, branches, and transformers, and how they connect — imported from a PSS®E case file. See [02-engineering-concepts.md](02-engineering-concepts.md).

**PSS/E Snapshot Selection** — The workflow step in which an engineer chooses the PSS/E Load Snapshot to use as the operational reference for scheme design or review. See [03-system-workflow.md](03-system-workflow.md).
