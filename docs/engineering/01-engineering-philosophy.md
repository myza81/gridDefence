# GridDefence Project Reference

## Engineering Philosophy and System Vision

*This document is the authoritative engineering reference for the GridDefence project. It governs every other document in `docs/engineering/`, every architecture decision, and every contributor — human or AI. Where any other document appears to conflict with this one, this document takes precedence.*

> **Duplicate-document note (Architecture Synchronization Sprint).** [`docs/architecture/engineering-philosophy.md`](../architecture/engineering-philosophy.md) independently presents overlapping content under the same title. This document — the Engineering Reference Library copy — is the authoritative one; the `docs/architecture/` copy has been updated only enough to stay non-contradictory on the Operational Snapshot pivot (§6, below), not promoted to equal authority. See that file's own note for the full record. Consolidating or formally deprecating one copy is flagged as unresolved future documentation work, not decided here.

---

## 1. Introduction

GridDefence is a centralized engineering decision support platform developed for managing, designing, validating, and maintaining the Grid Defence Schemes of the Peninsular Malaysia transmission network.

Unlike conventional protection engineering software, GridDefence does not perform power system simulations, relay setting calculations, or dynamic stability studies. Those engineering studies remain the responsibility of external analysis tools such as PSS®E and the professional judgement of system planning and operation engineers.

Instead, GridDefence serves as the authoritative engineering repository where approved defence schemes are developed, maintained, audited, validated, and continuously reviewed throughout their operational lifecycle.

The philosophy of the system is simple:

> Engineering studies determine **what should be done**. GridDefence manages **how those engineering decisions are implemented, maintained, validated, and governed.**

---

## 2. Engineering Philosophy

The primary objective of GridDefence is not to calculate defence schemes.

Its objective is to ensure that every approved defence scheme remains:

* Technically executable
* Properly documented
* Fully traceable
* Version controlled
* Engineering auditable
* Continuously validated against the latest network information

The application never replaces engineering judgement.

Instead, it provides engineers with accurate and up-to-date information to support engineering decisions.

The guiding principle of the project is:

> **GridDefence detects engineering impacts. Engineers make engineering decisions.**

---

## 3. Scope of the Application

GridDefence focuses specifically on transmission grid defence schemes.

These include:

* Under Frequency Load Shedding (UFLS)
* Under Voltage Load Shedding (UVLS)
* Emergency Manual Load Shedding (EMLS)

Future defence schemes may be incorporated without changing the overall system architecture.

The application does not manage local equipment protection such as:

* Distance protection
* Transformer differential protection
* Busbar protection
* Overcurrent protection
* Relay coordination studies

Those belong to local protection engineering and are outside the scope of GridDefence.

---

## 4. What is a Grid Defence Scheme?

A Grid Defence Scheme is an engineered operational strategy designed to preserve the stability of the transmission system during major disturbances.

Instead of protecting individual equipment, the objective is to protect the integrity of the entire interconnected grid.

Typical defence actions include:

* Disconnecting selected transformer bays
* Disconnecting selected transmission line bays
* Isolating electrical load pockets
* Coordinating staged load shedding
* Executing emergency manual shedding

The engineering objective is always to remove sufficient load from the system to restore system stability.

---

## 5. Core Engineering Workflow

The overall engineering workflow supported by GridDefence is as follows.

### Step 1 – Determine Required Load Shedding Quantum

Engineering studies performed externally determine the required amount of load that must be shed.

For example:

* Total grid demand = 10,000 MW
* Required UFLS quantum = 60%
* Total shedding target = 6,000 MW

The application does not calculate this value.

It records and manages the engineering implementation of the decision.

---

### Step 2 – Select PSS®E Reference Snapshot

The engineer selects an appropriate PSS®E load snapshot.

Examples include:

* Peak demand
* Off-peak demand
* Seasonal loading
* Specific operational scenarios

Different engineering studies may require different snapshots.

The selected snapshot becomes the operational reference for scheme design.

---

### Step 3 – Evaluate Available Loads

Using the selected PSS®E snapshot, engineers identify the available loads throughout the transmission network.

Most transmission loads are represented through transformer bays.

Typical examples include:

* Transformer 1
* Transformer 2
* Transformer 3

Approximately 80% of practical defence schemes involve transformer bay shedding.

The remaining 20% involve transmission line shedding.

---

### Step 4 – Exclude Sensitive Customers

Not every available load can be selected.

Critical or sensitive customers must be excluded according to operational policy.

Examples may include:

* Hospitals
* Airports
* Strategic industries
* Essential public infrastructure

The Sensitive Customer Registry provides this engineering information.

---

### Step 5 – Verify Grid Defence Capability

The engineer must verify whether the selected bay or switching point is capable of executing a defence action.

This is the purpose of the Relay Registry.

Within GridDefence, the Relay Registry is not intended to function as a traditional relay asset management database.

Instead, it answers a much simpler engineering question:

> Can this bay or switching point be operated by the Grid Defence Scheme?

Information such as manufacturer, model, or firmware is secondary.

The primary concern is engineering capability.

---

### Step 6 – Select Load Shedding Strategy

The engineer may choose between different engineering strategies.

#### Strategy A – Local Bay Shedding

Selected transformer bays are assigned into the defence scheme.

Example:

* Alpha Transformer 1
* Alpha Transformer 2
* Bravo Transformer 3

Each bay contributes a known amount of load.

---

#### Strategy B – Boundary Line Shedding

Instead of selecting individual substations, engineers may isolate an entire electrical pocket.

Example:

Open:

* Line Alpha–Beta
* Line Romeo–Charlie

The enclosed network is disconnected as one block.

This approach relies heavily on the PSS®E topology model.

---

### Step 7 – Coordinate Stages

Selected shedding actions are organised into stages.

Each stage contains:

* Frequency or voltage threshold
* Time delay
* Collection of shedding actions

A stage may contain:

* Transformer bays
* Transmission line bays
* Boundary line isolation
* Any combination of the above

The composition of each stage depends entirely on engineering judgement.

---

### Step 8 – Review, Publish and Maintain

Once complete, the scheme enters the engineering review process.

Before publication, metadata is recorded, including:

* Scheme version
* Review information
* Approval details
* Engineering remarks
* Revision history

Every published version becomes part of the permanent engineering record.

---

## 6. Engineering Information Layers

GridDefence is built upon three independent information layers.

### Layer 1 – Engineering Knowledge

Slow-changing information curated by engineers.

Includes:

* Substation Registry
* Equipment Registry
* Line Connectivity Registry
* Relay Registry
* Sensitive Customer Registry

These registries describe the physical engineering environment.

**Clarification (Operational Snapshot pivot).** Line Connectivity Registry, and the transformer-asset portion of Equipment Registry, curate engineering **identity and metadata** for lines, circuits, and transformers — bay numbers, breaker numbers, commissioning dates, line type, interconnector flags, alias/rename history, and other engineering attributes PSS®E cannot represent. They are not, and have never been intended to be, the authoritative source of *current* electrical topology or *current* operational connectivity — that authority belongs to Operational Snapshot (Layer 2, below). See [EDR-007](edr/EDR-007-phase-7-operational-identity-mapping.md) and [operational-snapshot-architecture.md](../architecture/operational-snapshot-architecture.md).

---

### Layer 2 – Operational Context

Dynamic information imported from PSS®E.

Includes:

* Network topology
* Load snapshots

These represent the operational condition of the network at a particular point in time. **Network topology — current electrical connectivity, and current bus/branch/transformer/load/generator representation — is authoritative here, in Operational Snapshot, never in a Layer 1 registry.** GridDefence correlates Layer 1 identity/metadata against Layer 2 operational state for engineering workflows; neither layer overwrites the other.

---

### Layer 3 – Engineering Decisions

Version-controlled engineering schemes.

Includes:

* UFLS
* UVLS
* EMLS

These represent approved engineering decisions.

---

## 7. Continuous Validation

One of GridDefence's primary responsibilities is continuous engineering validation.

Whenever new PSS®E data is imported, the application compares:

* Current topology
* Current loading
* Existing defence schemes

Examples include:

* A transformer no longer exists.
* A transmission line has been removed.
* A bay assignment is no longer valid.
* The expected shed load has changed significantly.

The application reports these engineering impacts.

It does not redesign the scheme.

The engineer decides whether a review is necessary.

---

## 8. Version Control Philosophy

Engineering schemes evolve through formal reviews.

Operational load snapshots change frequently.

Therefore:

PSS®E snapshots are temporary operational references.

Engineering schemes are permanent engineering documents.

A new PSS®E import does not automatically create a new defence scheme.

The engineer decides whether the imported changes justify a scheme review.

---

## 9. Role of Supporting Modules

Several future modules enhance the engineering workflow without changing the application's philosophy.

Examples include:

* Engineering reporting
* Network load heatmaps
* Dashboard analytics
* Compliance monitoring
* Audit reporting
* Validation summaries
* Historical comparisons

These modules consume information from the core system.

They do not become sources of engineering truth.

---

## 10. Engineering Design Principles

The following principles govern the entire architecture of GridDefence.

1. The application never replaces engineering judgement.
2. External engineering studies determine the defence strategy.
3. GridDefence manages engineering implementation.
4. Every engineering decision must be traceable.
5. Every published scheme must be reproducible.
6. Every engineering action must be auditable.
7. Dynamic operational data must never overwrite engineering decisions.
8. Engineering registries are authoritative references.
9. PSS®E provides operational context, not engineering authority.
10. The application detects engineering impacts; engineers decide the engineering response.

---

## 11. Long-Term Vision

GridDefence is intended to become the single authoritative engineering platform for managing the operational lifecycle of transmission grid defence schemes.

It provides a unified environment where engineers can:

* Maintain engineering registries
* Import operational PSS®E information
* Design defence schemes
* Validate engineering decisions
* Track revisions
* Preserve engineering knowledge
* Produce reports
* Support audits
* Monitor long-term network evolution

The project is deliberately designed to remain modular and extensible.

Future registries, engineering rules, validation engines, dashboards, and analytical tools should integrate naturally into the existing architecture without requiring fundamental redesign.

The ultimate objective is to preserve engineering knowledge, improve consistency, reduce manual effort, strengthen governance, and ensure that every published Grid Defence Scheme remains technically executable, operationally relevant, and fully traceable throughout its entire lifecycle.
