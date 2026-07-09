# Operational Correlation Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) (v1.1)

Governing engineering reference: [`docs/engineering/01-engineering-philosophy.md`](../engineering/01-engineering-philosophy.md) §6 (Engineering Information Layers); [EDR-007](../engineering/edr/EDR-007-phase-7-operational-identity-mapping.md) (Phase 7 — Operational Identity Mapping), particularly Engineering Principle 12 (Operational Identity Persistence).

Related: [`operational-snapshot-architecture.md`](operational-snapshot-architecture.md) (Operational Snapshot — the domain this document correlates against Engineering Registries); [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md) (Connectivity Registry vs. PSS/E Topology Architecture, including its Operational Snapshot pivot addendum). This document does not modify any of the above; it builds on them.

This document is the authoritative architecture for **Operational Correlation** — the layer responsible for relating Operational Snapshot objects to Engineering Registry objects. It is implementation-independent — it does not define parser behaviour, database schema, API contracts, or module internals.

---

## 1. Purpose

The recent Architecture Synchronization Sprint established a clear division: Operational Snapshot owns operational topology and operational state; Engineering Registries own engineering identity, metadata, capability, governance, and constraints. That division leaves one question open: **how do the two actually meet, for the engineering workflows that need both at once?**

This document defines that meeting point — Operational Correlation — as its own architectural concept, distinct from either domain it relates.

## 2. Relationship to Engineering Philosophy

[`01-engineering-philosophy.md`](../engineering/01-engineering-philosophy.md) §6 describes three Engineering Information Layers: Engineering Knowledge (Layer 1), Operational Context (Layer 2), and Engineering Decisions (Layer 3). Its own domain-model diagram already states that Layer 1 and Layer 2 "both inform, neither owns" Layer 3. Operational Correlation is the architectural layer that gives that statement a concrete shape: it is where Layer 1 (Engineering Knowledge) and Layer 2 (Operational Context) are related to one another, before either informs a Layer 3 Engineering Decision. Operational Correlation does not introduce a fourth layer, and does not sit "above" or "below" Layers 1–3 — it is the relationship between two of them, made explicit.

## 3. Relationship to Operational Snapshot

[`operational-snapshot-architecture.md`](operational-snapshot-architecture.md) defines Operational Snapshot and Operational Identity (Bus Number as the authoritative operational identity, preserved independently of import source). Operational Correlation consumes that identity — it never redefines it, never recomputes it, and never substitutes its own identity scheme in its place. Where Operational Snapshot answers "what does the network look like, operationally, right now," Operational Correlation answers a different question: "which Engineering Registry object, if any, does this operational object correspond to."

## 4. Correlation Domain

**Operational Correlation is the architectural layer responsible for associating Operational Snapshot objects with Engineering Registry objects, without duplicating ownership.**

Correlation creates relationships. Correlation does **not** create ownership. An Operational Snapshot object correlated to an Engineering Registry object remains exactly as owned as it was before — Operational Snapshot still owns the operational fact; the Engineering Registry still owns the identity/metadata fact. Correlation adds a third fact — "these two facts are about the same thing" — owned by neither original domain.

**Correlation targets, corrected against the already-established engineering scope of each registry** (EDR-005 — Bay as engineering identity; EDR-003 — Relay Registry scope; ADR-006 §6–§7 — Data Ownership):

```text
Operational Bus
        │
        ▼
Substation Registry
(bus name → substation identity)
        │
        ▼
Engineering Switchyard / SubstationVoltageYard
(bus name + base kV → switchyard identity — see §4.1, Operational Switchyard)

Operational Branch / Operational Transformer
        │
        ▼
Line Connectivity Registry / Equipment Registry
(bay/breaker identity — Circuit/CircuitTerminal, Transformer/TransformerTerminal)

Operational Branch Terminal / Operational Transformer Terminal (a Bay)
        │
        ▼
Relay Registry
(Grid Defence Capability — can this bay be operated)

Operational Load
        │
        ▼
Sensitive Customer Registry
(sensitive customer exclusion classification)
```

A note on this correction: an earlier working draft of this correlation example paired Operational Load with Relay Registry. Relay Registry is scoped, by EDR-003, to answer exactly one question — "can this bay or switching point be operated" — a question about a Bay (an operational Branch or Transformer terminal), not about Load. The corrected mapping above reflects EDR-003's and EDR-005's already-accepted scope; it does not introduce a new engineering rule.

### 4.1 Operational Switchyard

**Operational Switchyard is the read-side correlation of one or more Operational Buses to an existing Engineering Switchyard (`SubstationVoltageYard`).**

EDR-007 §4.4 already establishes the underlying engineering fact: a Switchyard Bus's name (`<4-character mnemonic><nominal voltage>`) correlates directly to both a Substation *and* a Switchyard — the trailing nominal voltage identifies which of that Substation's Switchyards the Bus represents. §4.5 extends this to Split Switchyard Buses: both buses of a split pair correlate to the *same* Switchyard, never two. Operational Switchyard is the name this document gives to that correlation, at the architectural level, so it is no longer only an implementation detail of one module's read path.

Operational Switchyard is explicitly:

- **Not a new database entity.** It introduces no table, no persisted row, and no migration.
- **Not a new registry.** The engineering identity it correlates against remains exactly `SubstationVoltageYard`, owned by Equipment Registry (ADR-008) — the user-facing term for that entity is already "Switchyard" (ADR-008 addendum), unchanged by this document.
- **Not a new ownership domain.** Operational Snapshot continues to own the operational fact (a Bus exists, at a given `base_kv`, electrically connected a given way). Equipment Registry continues to own the engineering fact (a Switchyard exists, at a given substation and voltage level). Operational Switchyard states a relationship between the two — it owns neither fact, exactly as §4 and §9 ("Correlation Without Duplication") already require of every other correlation target in this document.
- **Not a replacement for `SubstationVoltageYard`.** Every workflow that needs to create, edit, or authoritatively read a Switchyard's own engineering metadata continues to do so through Equipment Registry, unchanged.

**What it is:** a named read-side concept in the Correlated Operational Model — one or more Operational Buses (matched by `substation_id` and `base_kv`) grouped under the `SubstationVoltageYard` they correlate to. A Fictitious Bus (EDR-007 §4.6) has no Substation correlation and therefore no Operational Switchyard correlation either — consistent with, not an exception to, EDR-007's existing conclusion that Fictitious Buses are retained in the Operational Topology but are never correlated against any Engineering Registry object.

### 4.2 Operational Projections

The Correlated Operational Model (§4) does not have one fixed shape. It may be **projected** into different engineering views, depending on the granularity a given workflow needs:

- **Bus View** — individual Operational Buses, their operational identity (Bus Number), and their correlation status.
- **Switchyard View** — Operational Buses grouped by Operational Switchyard (§4.1), i.e. by their correlated `SubstationVoltageYard`.
- **Substation View** — further grouped up to the correlated Substation, the coarsest projection.
- **Branch View** — Operational Branches, with the Substation/Switchyard correlation of the Buses they connect.
- **Transformer View** — Operational Transformers, similarly correlated, including the voltage-level (Switchyard) transition an Inter-bus Transformer represents (EDR-007 §6.3, Scenario A).
- **Load View** — Operational Load, correlated to the Bus (and, transitively, Switchyard/Substation) it is attached to.

An **Operational Projection** is a read model only. Projecting the Correlated Operational Model into a Switchyard View, for example, does not create a "Switchyard Graph" as a new source of truth — it re-presents the same underlying Operational Snapshot facts and the same underlying Engineering Registry facts, at a different level of aggregation. No projection may compute a fact that does not already exist in Operational Snapshot or Engineering Registry data (the same boundary EDR-006 already draws for visualisation generally: presentation, never a second analysis capability). Different projections may coexist without conflict, because they are views over one correlated model, not independent computations that could disagree with one another.

## 5. Responsibilities

Operational Correlation is responsible for:

- establishing engineering relationships between Operational Snapshot objects and Engineering Registry objects,
- preserving Operational Identity (never recomputing or overriding it — see §3),
- enriching operational objects with engineering metadata, for presentation and workflow purposes,
- detecting unmatched objects — an operational object with no corresponding registry object, or a registry object with no corresponding operational object,
- supporting engineering validation (§8),
- supporting Defence Scheme workflows that need both operational state and engineering identity at once,
- exposing the correlated model through Operational Projections (§4.2) — Bus, Switchyard, Substation, Branch, Transformer, and Load views — without introducing a second source of truth for any of them.

Operational Correlation is **not** responsible for:

- importing RAW files (Operational Snapshot's own concern),
- maintaining Engineering Registry data (each Engineering Registry's own concern),
- maintaining Operational Snapshot data (Operational Snapshot's own concern),
- performing protection calculations,
- making engineering decisions.

## 6. Module Boundaries

### Engineering Registry

Owns:

- engineering identity,
- metadata,
- governance,
- engineering constraints.

### Operational Snapshot

Owns:

- topology,
- connectivity,
- operational state,
- operational load,
- operational generation.

### Operational Correlation

Owns:

- relationships,
- mapping,
- enrichment,
- validation (of the correlation itself — see §8),
- projections (§4.2) — the read-only views the correlated model may be presented through.

Operational Correlation owns none of the facts it relates — only the relationship between them, and the views composed from that relationship.

### Defence Schemes

Consume correlated information. Do not implement their own correlation logic. A scheme module that needs to know "what engineering asset does this operational object correspond to" asks Operational Correlation; it does not re-derive the answer itself.

### Dashboard / Analytics

Consume correlated operational models. Do not maintain engineering relationships of their own.

## 7. Correlation Lifecycle

```text
Engineering Registry
        +
Operational Snapshot

        ↓

Operational Correlation

        ↓

Engineering Validation

        ↓

Correlated Operational Model

        ↓

Scheme Design / Dashboard / Analytics
```

This is a conceptual lifecycle, not a state machine or a processing pipeline specification. It describes the architectural shape of how a correlated model comes to exist and is consumed — not the specific algorithm, storage mechanism, or trigger condition any one module implements to realize it.

## 8. Engineering Validation

Architecturally, Operational Correlation is responsible for surfacing:

- unmatched operational objects — an Operational Snapshot object with no corresponding Engineering Registry object,
- unmatched engineering objects — an Engineering Registry object with no corresponding Operational Snapshot object,
- inconsistent identity — a correlation that was previously established but is no longer consistent with current data on either side,
- missing metadata — a correlation that exists, but the Engineering Registry side lacks metadata a workflow expects,
- the requirement that any of the above be routed to engineering review rather than resolved automatically (consistent with Engineering Principle 12 — Operational Identity Persistence — and with `operational-snapshot-architecture.md` §8, Engineering Validation).

This document does not define validation rules, thresholds, or procedures — only that these categories of finding are Operational Correlation's responsibility to surface.

## 9. Architectural Principles

### Separation of Ownership

Ownership remains within the originating domain. Correlation never transfers, copies, or reassigns ownership of a fact from the domain that owns it.

### Correlation Without Duplication

Relationships are created without copying ownership. A correlation record states that two facts are related; it does not restate either fact.

### Operational Identity Preservation

Operational identity remains derived from Operational Snapshot (Bus Number, per Engineering Principle 12). Operational Correlation never substitutes its own identity scheme for it.

### Engineering Metadata Preservation

Engineering metadata remains owned by Engineering Registries. Operational Correlation never becomes a second, informal home for metadata that belongs in a registry.

### Single Correlation Layer

All engineering workflows consume the same correlated model rather than each implementing an independent mapping. A scheme module, a dashboard, and a future analytics capability all ask the same Operational Correlation layer the same kind of question, rather than each re-deriving its own answer.

## 10. Future Extensions

Captured as future possibilities, not designed here:

- EMS integration.
- SCADA integration.
- CIM (Common Information Model) integration.
- Historical replay of a correlated model at a past point in time.
- Scenario comparison across multiple correlated models.
- Multiple simultaneous Operational Snapshots, each independently correlated.
- Frozen operational references for approved Defence Schemes — an approved scheme assignment may need to retain an immutable reference to the specific correlation (Operational Snapshot object + Engineering Registry object) that informed it, for reproducibility and auditability. This mirrors the same forward-looking note already recorded in [`operational-snapshot-architecture.md`](operational-snapshot-architecture.md) §10.

None of these are resolved by this document.
