# PSS®E RAW Sample Files

## Purpose

This directory contains the official reference PSS®E RAW files used during development and testing of the GridDefence PSS®E Integration module.

These files should be used by developers and AI coding agents to understand the actual structure of PSS®E RAW files used by the utility, rather than relying solely on generic PSS®E documentation.

The parser implementation should always be validated against these reference files.

---

## Sample Files

### 110226n.raw

Representative **full network snapshot** exported from PSS®E.

Characteristics:

* PSS®E RAW Revision 34
* Complete network topology
* Bus data
* Load data
* Generator data
* Branch data
* Transformer data
* Other standard PSS®E sections

This file is used to develop and validate:

* RAW parser
* Topology import
* Topology signature generation
* TopologyVersion creation
* LoadSnapshot extraction from a full topology snapshot

---

### PSSE_LOAD_20260608_1730.raw

Representative **load-only snapshot**.

Characteristics:

* PSS®E RAW Revision 34
* Load records only
* No network topology

This file is used to develop and validate:

* Load-only import
* LoadSnapshot creation
* Association with an existing TopologyVersion

---

## Snapshot Philosophy

Every PSS®E RAW file represents the state of the electrical network at a particular timestamp.

GridDefence separates these into two concepts:

### Topology

Represents the electrical structure of the network.

Topology changes relatively infrequently and is stored as a versioned `TopologyVersion`.

### Load Snapshot

Represents the operating condition of the network at a specific point in time.

Load snapshots may be imported much more frequently than topology updates and are always associated with a specific `TopologyVersion`.

This design allows:

* occasional topology imports when the network changes;
* frequent operational load imports;
* extraction of load information from a full topology RAW file;
* separate load-only imports between topology changes.

---

## Parser Requirements

The Phase 4 parser should:

* support PSS®E RAW Revision 34;
* inspect these sample files before implementation;
* distinguish between full topology imports and load-only imports;
* be resilient to unsupported or optional sections;
* preserve auditability of every import;
* be designed for future support of newer PSS®E RAW revisions with minimal changes.

These sample files are considered the canonical development references for Phase 4.
