# Operational Snapshot Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) (v1.1)

Governing engineering reference: [EDR-007](../engineering/edr/EDR-007-phase-7-operational-identity-mapping.md) (Phase 7 — Operational Identity Mapping), particularly Engineering Principle 12 (Operational Identity Persistence) and §4.7 (Correlation Philosophy).

Related: [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md) (PSS/E Topology and Load Snapshot Separation) and [psse-integration-module.md](psse-integration-module.md) — an existing, accepted concrete realization of the concepts this document generalizes, for the PSS/E Integration module specifically. This document does not reopen, redefine, or constrain that existing architecture; it states the engineering-derived concepts at a level independent of any one module's implementation.

This document is the authoritative architectural specification for Operational Snapshot management. It translates the engineering principles established in EDR-007 into architectural concepts. It is implementation-independent — it does not define parser behaviour, database schema, API contracts, or module internals.

---

## 1. Purpose

This document defines how GridDefence, architecturally, manages **Operational Snapshots** — versioned representations of the operational power-system model over time — and how **Operational Identity** is preserved as those snapshots accumulate, are updated, and are correlated with one another.

It exists to give GridDefence's future architecture and implementation work a stable, engineering-grounded vocabulary for this concept, so that any module handling operational data (PSS/E Integration today; potentially others in future) can be designed against the same shared architectural concepts rather than each independently reinventing them.

## 2. Relationship to EDR-007

EDR-007 completed the engineering interpretation of the Tier 1 Operational Model (Bus, Branch, Transformer, Load, and Generator Data) and, in its final amendment, established Engineering Principle 12 — Operational Identity Persistence:

- Bus Number is the authoritative Operational Identity.
- Operational Identity persists across Operational Snapshots.
- Network Topology and Operational Load may originate from different PSS®E RAW files.
- Bus Number is the authoritative basis for correlation across snapshots.

This document translates those engineering principles into architectural concepts. It does not restate or reopen EDR-007's own Tier 1 Operational Model findings — those remain entirely EDR-007's domain. This document begins where EDR-007 ends: it takes "Bus Number is the authoritative Operational Identity, persisting across snapshots" as an established engineering fact, and asks what architectural concepts are needed to represent that fact faithfully.

`ADR-003` already provides one concrete, accepted realization of a closely related idea (`TopologyVersion` / `LoadSnapshot` separation) for the PSS/E Integration module. This document is deliberately more general than that ADR: it describes the architectural concepts EDR-007's engineering principles imply, independent of any one module's own entities, tables, or workflows.

## 3. Operational Snapshot Concept

An **Operational Snapshot** is:

> A versioned representation of the operational power-system model at a specific point in time.

An Operational Snapshot may contain:

- Operational Topology
- Operational Load
- Operational Generation
- Operational Connectivity
- Operational Context

An Operational Snapshot's components need not all originate from the same source file. A snapshot's Operational Topology may have been established at one point in time from one source, while its Operational Load is updated later from a different source — the snapshot concept itself does not require single-origin data, only that Operational Identity (§5) is preserved across whatever data it is composed from.

## 4. Snapshot Types

Two snapshot categories are recognized.

### Full Operational Snapshot

Produced from a complete RAW containing Bus, Branch, Transformer, Load, and Generator data. A Full Operational Snapshot establishes an **Operational Topology** — the structural definition of the network's buses and their electrical connectivity.

### Incremental Operational Snapshot

Produced from data containing only operational updates — for example, a Load-only RAW, or a future operational update dataset of a different kind. An Incremental Operational Snapshot extends or updates an existing Operational Snapshot; it does not redefine Operational Topology. Its data is understood only in relation to the Operational Topology it extends, correlated through Operational Identity (§5, §6).

## 5. Operational Identity

- Operational Identity is preserved through Bus Number.
- Operational Identity is independent of import source — a Bus Number's identity does not change because the data referencing it arrived in a different file, at a different time, or from a different snapshot type.
- Bus Name remains responsible for Engineering Registry correlation (EDR-007 §4.3) — a separate concern from Operational Identity. Bus Number identifies *which operational node this is*; Bus Name identifies *what engineering asset it may correspond to*, if any. Operational Snapshot correlation is governed by the former, never the latter.
- Operational Snapshot correlation is based upon Operational Identity.

## 6. Snapshot Correlation

Operational datasets originating from different Operational Snapshots are correlated through Bus Number:

```text
Operational Snapshot A
(Network Topology)

        │

   Bus Number

        │

Operational Snapshot B
(Load Update)
```

An Incremental Operational Snapshot's data is understood by locating the same Bus Number within the Operational Topology it extends. This document does not define the algorithm, procedure, or validation logic by which that correlation is carried out — those are architecture and implementation questions for the owning module to resolve, informed by this document and by EDR-007.

## 7. Snapshot Lifecycle

Conceptually, an Operational Snapshot's lifecycle proceeds as follows:

```text
Create Snapshot

        ↓

Activate Snapshot

        ↓

Receive Operational Update

        ↓

Correlate

        ↓

Engineering Review (if required)

        ↓

Updated Operational Snapshot
```

This is a conceptual lifecycle, not a state machine specification. It describes the architectural shape of how an Operational Snapshot comes to exist, becomes the reference snapshot, and evolves as further operational data arrives — not the specific states, transitions, or persistence mechanism any one module implements to realize it.

## 8. Engineering Validation

Architecturally, any module managing Operational Snapshots is responsible for:

- preserving Operational Identity,
- preserving Operational Topology,
- detecting inconsistencies,
- requiring Engineering Review where identity cannot be established.

These are architectural responsibilities, not implementation prescriptions — they do not define a user interface, a database rule, or a specific validation procedure. They state what any correct implementation must achieve, leaving how to achieve it to the owning module's own architecture.

## 9. Architectural Principles

### Operational Identity First

Operational Identity shall be preserved independently of data source.

### Topology Independence

Operational Topology shall not be implicitly redefined by incremental operational datasets.

### Engineering Validation Before Correlation

Operational inconsistencies require engineering review rather than automatic interpretation.

### Separation of Engineering Registry and Operational Snapshot

Engineering Registry represents engineering assets. Operational Snapshot represents operational system state. Correlation exists between them, but they remain independent architectural concepts — neither is derived from, nor subordinate to, the other.

## 10. Open Architectural Questions

These are intentionally deferred, not resolved here:

- Whether multiple Operational Snapshots may be active concurrently, and under what architectural circumstances.
- Historical Operational Snapshot retention.
- Operational Snapshot comparison.
- Multi-scenario studies built on divergent Operational Snapshots.
- Future operational data sources beyond PSS®E RAW, and whether they fit this same architectural concept unchanged.
- Defence scheme assignments that select operational objects may require immutable references to the selected Operational Snapshot object, plus correlated engineering metadata, to preserve reproducibility and auditability. Not designed here — flagged for future documentation.
