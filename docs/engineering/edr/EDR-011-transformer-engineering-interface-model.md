# EDR-011: A Transformer's Engineering Classification Is the Interface Between Electrical-System Domains, and a Transformer Terminal Interfaces an Engineering Endpoint

- **Status:** Accepted
- **Governing document:** [01-engineering-philosophy.md](../01-engineering-philosophy.md) §6 (Engineering Information Layers — Layer 1 Engineering Knowledge vs Layer 2 Operational Context)
- **Related:** [EDR-007](EDR-007-phase-7-operational-identity-mapping.md) §6–§7 (the observed operational transformer/demand taxonomy this EDR gives Layer 1 engineering meaning to); [EDR-005](EDR-005-bay-as-engineering-identity.md) (a Transformer Bay's engineering identity is the `TransformerTerminal`, not a generic backbone — the terminal identity this EDR builds on); [EDR-001](EDR-001-psse-as-operational-context.md) (PSS/E is operational context, never engineering authority); [EDR-003](EDR-003-relay-registry-scope.md) (capability/usage recorded separately from asset identity — the precedent for §10 below); [EDR-008](EDR-008-sensitive-customer-registry-scope.md) (a customer installation is treated as a black box); `docs/architecture/equipment-registry-module.md` (the current Transformer Registry implementation); `docs/architecture/operational-snapshot-architecture.md` (Layer 2). **A subsequent ADR (not created by this EDR) will realise this engineering model in the schema, ORM, API, and frontend — see "Deferred Architectural Questions" below.**

---

## 1. Status

**Accepted.** This EDR ratifies the *engineering meaning* of transformer classification and transformer terminal endpoints. It deliberately establishes semantics only; it prescribes no database, ORM, API, or frontend implementation. Those decisions belong to the follow-on ADR.

## 2. Context

The Transformer Registry (part of Equipment Registry) was built from GridDefence's immediate defence-scheme needs, which involve transformers whose two terminals are both registered GridDefence Voltage Yards (switchyards). [01-engineering-philosophy.md](../01-engineering-philosophy.md) §6 is explicit that the transformer-asset portion of Equipment Registry is a **Layer 1 Engineering Knowledge** registry — it "curate[s] engineering identity and metadata … not … the authoritative source of *current* electrical topology" — while the *current operational transformer representation* is authoritative only in **Layer 2 Operational Snapshot** (PSS/E-derived), "never in a Layer 1 registry."

[EDR-007](EDR-007-phase-7-operational-identity-mapping.md) §6–§7, studying an actual TNB RAW file, already observed that the network contains genuinely distinct transformer roles: Inter-bus transformers (which "naturally correlate with the existing Transformer Registry"), generator step-up transformers (§6.6.2, "clearly distinguishable … outside the current Engineering Registry scope"), and transformers whose non-grid side manifests operationally as *demand* rather than as a transformer record — generating-station auxiliary supply (§7.3 Category C, N-series) and large-customer supply (§7.3 Category B, F-series, where "PSS®E models the demand directly" rather than the customer's internal transformer).

An engineering review then identified that additional transformer classes exist on the transmission network and should be representable if the registry is to become a durable, shared Engineering Registry rather than serving only GridDefence's present workflows.

## 3. Engineering Problem

The Transformer Registry is *intended* to be a Layer 1 Engineering Transformer registry, but its **Transformer Terminal model embeds a Layer 2 operational-topology assumption**: it requires both terminals to resolve to a registered GridDefence Voltage Yard at the same substation. "This winding connects to a registered grid switchyard" is a statement about *current grid connectivity* (a Layer 2 fact), not about the transformer's *engineering identity* (a Layer 1 fact). This assumption is correct for transformers embedded entirely within the transmission grid (Inter-bus, Load) but cannot express transformers whose non-grid winding interfaces a system GridDefence does not (yet) register — a generation collector system, a station auxiliary system, or a customer installation.

The problem is therefore twofold and purely at the level of engineering meaning:
1. **What does a transformer's *classification* mean** — such that it is not defined by voltage ratio, and such that a 132/33 kV unit can legitimately be several different classifications?
2. **What does a transformer *terminal* mean** — such that a winding can interface a grid switchyard *or* a non-grid engineering system, without the registry pretending the latter is a switchyard or losing the information that it is not.

## 4. Decision

**A transformer's engineering classification represents the electrical-system domains its windings interface with. A transformer terminal represents a physical winding-side connection to an Engineering Endpoint — an electrical-system domain — which may be a registered GridDefence object (a Transmission Voltage Yard) or a typed engineering system not (yet) held in a GridDefence registry.**

- **Classification is by interfaced electrical-system domains, never by voltage ratio.** For the presently-considered grid-connected transformers, the classification is determined by the **non-transmission domain coupled to the transmission grid**; the **Inter-bus Transformer** is the transmission-grid-to-transmission-grid special case.
- **A transformer terminal interfaces an Engineering Endpoint.** It does not inherently mean "a terminal connected to a registered Voltage Yard." An Engineering Endpoint is either a **Registered Engineering Endpoint** (resolving to a GridDefence-owned registry object — today, exactly one kind exists: a Transmission Voltage Yard) or a **Typed Engineering Endpoint** (a named engineering-system category that GridDefence recognises but does not currently register as a first-class object — a Distribution System, a Generation Collector System, a Station Auxiliary System, or a Customer Installation).
- **Classification is engineer-asserted; endpoint categories are structural engineering evidence for it.** They encode related meaning but are not the same statement, and neither silently derives from or overwrites the other (§8).
- **Classification is a Layer 1 engineering-identity attribute** of the transformer asset. It carries no implication about current operational topology (Layer 2) and no implication about GridDefence application usage (§10).
- **The engineering principle is stated over windings, not exactly two systems**, so that a future three-winding or tertiary arrangement is expressible without reinterpreting this decision (§11).

This EDR does not change any transformer classification, terminal, or validation behaviour today. It states the engineering model the follow-on ADR will realise.

## 5. Definitions

- **Transmission Grid.** The transmission network as GridDefence models it in Layer 1 — the switchyards (Voltage Yards) and the circuits between substations. The "grid side" of a transformer is the winding that interfaces the transmission grid; for every classification below except Inter-bus, exactly one winding is the grid side and it is the higher-voltage winding.
- **Electrical-System Domain.** A distinct kind of electrical network a transformer winding can interface: the transmission grid, a distribution system, a generation collector system, a station auxiliary system, or a customer installation. Domains are engineering categories, not GridDefence-owned records.
- **Transformer Engineering Classification.** The engineer-asserted statement of *which electrical-system domains a transformer's windings interface with*. One of the vocabulary values in §6. Not derived from voltage ratio.
- **Transformer Terminal.** The Layer 1 engineering identity of one physical winding-side connection of a transformer (already, per [EDR-005](EDR-005-bay-as-engineering-identity.md), the object `TransformerTerminal`). It interfaces exactly one Engineering Endpoint.
- **Engineering Endpoint.** The electrical-system domain a transformer terminal interfaces with, in the Layer 1 engineering model.
  - **Registered Engineering Endpoint** — an Engineering Endpoint that resolves to a GridDefence-owned registry object. Today the only kind is a **Transmission Voltage Yard** (`SubstationVoltageYard`).
  - **Typed Engineering Endpoint** — an Engineering Endpoint that GridDefence recognises as a named engineering system but does not currently hold as a first-class registry object. A Typed endpoint is a genuine engineering system that is *outside current GridDefence registry scope* — not a foreign or lesser object, and a candidate to become a Registered endpoint if a corresponding registry is created later (§11, §12).

*Terminology note:* "Registered" vs "Typed" is preferred over "internal/external" — a Typed endpoint (e.g. a generation collector system) is a real engineering system, merely not yet registered; calling it "external" would misstate its engineering standing.

## 6. Transformer Classification Vocabulary

Five classifications are ratified. Each is defined by the domains its windings interface, with example voltage combinations that are **illustrative, never definitional** (a given ratio does not fix a classification — §8, item 14 examples).

- **Inter-bus Transformer** — Transmission Grid ⇄ Transmission Grid. Both windings interface the transmission grid, normally at two different transmission voltage levels (e.g. 132/275 kV, 275/500 kV). It is **not** used for a transmission-to-33/22/11 kV transformer. (TNB engineering term, consistent with [EDR-007](EDR-007-phase-7-operational-identity-mapping.md) §6.3 Scenario A; both terminals are Registered Voltage-Yard endpoints.)
- **Load Transformer** — Transmission Grid ⇄ Distribution System. The non-grid winding interfaces a distribution system / distribution interface (e.g. 132/33 kV, 132/22 kV, 132/11 kV, and other valid transmission-to-distribution combinations). (Consistent with EDR-007 §7.3 Category A, T-series.)
- **Generation Step-Up Transformer (GSU)** — Generation Collector System ⇄ Transmission Grid. The non-grid winding interfaces a generation collector system (e.g. 11/132, 33/132, 11/275, 33/275, 11/500, 33/500 kV). The term is technology-agnostic: the generation collector system may aggregate solar, wind, hydro, thermal, battery energy storage (BESS), or future generation technologies — the classification describes the *interface to a generation collector system*, not a single synchronous machine. (Consistent with EDR-007 §6.3 Scenario B / §6.6.2.)
- **Station Service Transformer (SST)** — Transmission Grid ⇄ Station Auxiliary System. The non-grid winding supplies a station auxiliary system (e.g. 132/33, 132/11, 275/33, 275/11, 500/33, 500/11 kV). (Corresponds to the demand EDR-007 §7.3 Category C calls "Generating Station Auxiliary Supply," N-series — here given its Layer 1 asset meaning.)
- **Customer Supply Transformer (CST)** — Transmission Grid ⇄ Customer Installation. The non-grid winding interfaces a customer installation, with transmission-side voltages of 132, 275, or 500 kV and customer-side voltages such as 33 or 11 kV where they exist in engineering practice. The customer installation remains a GridDefence black box and outside the present internal network model unless a future Customer or Sensitive Customer Registry explicitly represents it. (Corresponds to EDR-007 §7.3 Category B "Spur Large Consumer," F-series; consistent with [EDR-008](EDR-008-sensitive-customer-registry-scope.md)'s black-box treatment.)

For every classification, the transmission grid side is the higher-voltage winding; this is an engineering observation about these classes, not a redefinition of classification by voltage.

## 7. Engineering Endpoint Concept

A transformer terminal interfaces exactly one Engineering Endpoint. The ratified endpoint categories are:

| Engineering Endpoint category | Kind | Resolves to a GridDefence registry object? |
|---|---|---|
| **Transmission Voltage Yard** | Registered | Yes — `SubstationVoltageYard` (today the only Registered kind) |
| **Distribution System** (distribution interface) | Typed | No (candidate future registry) |
| **Generation Collector System** | Typed | No (candidate future Generation Registry) |
| **Station Auxiliary System** | Typed | No (candidate future auxiliary registry) |
| **Customer Installation** | Typed | No (candidate future Customer / Sensitive Customer Registry) |

The engineering meaning is: a terminal names *what electrical-system domain the winding connects to*, and — only when that domain is a GridDefence-registered object — additionally resolves to that object. When it is a Typed endpoint, the terminal still carries a well-defined engineering meaning (the domain, and any engineer-recorded descriptive attributes such as a nominal voltage or label) without asserting a registered object that does not exist. This removes the Layer 2 assumption from the Layer 1 model (§3) while losing no information: an Inter-bus or Load transformer's grid terminals remain Registered Voltage-Yard endpoints exactly as today.

## 8. Classification-Versus-Endpoint Relationship

Classification and endpoint categories encode related engineering meaning — e.g. Transmission Grid + Customer Installation normally supports the classification Customer Supply Transformer. They are nonetheless **distinct statements**, and this EDR ratifies keeping them distinct:

- **Transformer classification is explicitly engineer-asserted.** It is a deliberate engineering statement of function, part of the transformer's Layer 1 identity.
- **Endpoint categories provide structural engineering evidence** for the classification — the concrete domains the windings interface.
- **The system must not silently derive the classification solely from endpoint categories, nor silently overwrite an engineer's classification from them.** Engineering intent is not always mechanically inferable, and a curated classification is clearer for every downstream consumer than one reconstructed from endpoints.
- **Future validation may check *consistency* between them** (e.g. flag a transformer classified GSU whose non-grid endpoint is a Distribution System) — a consistency check, never an automatic reclassification. Whether, when, and how such a check runs is an implementation/policy question for the ADR, not an engineering-meaning question here.

This mirrors GridDefence's established separation of an engineer's asserted record from derived evidence (e.g. a Boundary Pocket's engineer-selected opening points vs its derived substation set, [EDR-010](EDR-010-boundary-pocket-as-engineering-identity.md)).

## 9. Layer 1 Versus Layer 2 Boundary

This EDR sits entirely in Layer 1 and must not collapse the boundary [01-engineering-philosophy.md](../01-engineering-philosophy.md) §6 draws:

**Layer 1 — Engineering Knowledge (this EDR):** transformer engineering identity; winding/terminal identity; engineer-asserted classification; the intended engineering-endpoint meaning of each terminal. Slow-changing, engineer-curated.

**Layer 2 — Operational Context (unchanged, not owned here):** current operational bus connectivity; in-service topology; the PSS/E transformer representation; the current load/generator/network interpretation (EDR-007). Authoritative for *current* state.

Correlation across the layers (e.g. matching a Layer 1 Inter-bus transformer to a Layer 2 PSS/E transformer, or recognising that a Layer 1 GSU corresponds to a Layer 2 generator-terminal pattern, or a CST to a Layer 2 load) is a *comparison*, never an *ownership transfer*. A classification or endpoint asserted in Layer 1 does not become authoritative over Layer 2 topology, and Layer 2 topology never rewrites a Layer 1 classification. Neither layer overwrites the other.

## 10. GridDefence Application-Usage Separation

Transformer classification is independent of GridDefence application usage, and this EDR ratifies preserving that independence:

- GridDefence consumes relevant transformer terminals through **capabilities, assignments, and defence-scheme relationships** (e.g. a load-shedding capability recorded against a terminal, and a scheme assignment to it) — not by assuming that every transformer of a given classification participates in a scheme. This is the same asset-identity-vs-capability separation [EDR-003](EDR-003-relay-registry-scope.md) established for the Relay/ALSF concept.
- **Inter-bus and Load Transformers** may currently participate in GridDefence defence-scheme workflows; **GSU, SST, and CST** may initially be registry-only engineering assets.
- Future applications may consume GSU/SST/CST without any redesign of the Transformer Registry.
- **A transformer's classification must not itself imply defence-scheme eligibility.** Eligibility is expressed only through capability and assignment, never inferred from classification.

## 11. Multi-Winding Extensibility

The engineering principle is deliberately phrased over *windings*, not exactly two electrical systems: **"a transformer's engineering classification represents the electrical-system domains its windings interface with."** A present transformer is modelled with two terminals, but a future three-winding or tertiary arrangement (observed in the real network — [EDR-007](EDR-007-phase-7-operational-identity-mapping.md) §6.3 Scenario C, where an Inter-bus transformer's tertiary typically serves station auxiliaries or reactive compensation) must be expressible by adding a further winding/terminal interfacing its own Engineering Endpoint, without reinterpreting this decision. This EDR does not design three-winding representation; it only ensures the engineering meaning does not preclude it.

## 12. Consequences

**Positive:**
- Closes the Layer-1/Layer-2 leakage in the transformer terminal model (§3): the registry can express the full class of engineering transformers, not only those embedded entirely within the registered transmission grid.
- Gives EDR-007's observed operational taxonomy a precise, engineer-owned Layer 1 counterpart, so Inter-bus/Load/GSU/SST/CST have a single agreed engineering vocabulary.
- Makes the Transformer Registry durable as a shared enterprise Engineering Registry: new endpoint kinds, and future Generation/Customer/Auxiliary registries, attach additively to Typed endpoints without reshaping the transformer.
- Preserves every existing behaviour: Inter-bus and Load transformers keep Registered Voltage-Yard endpoints on both terminals; GridDefence workflows are unaffected because they never read classification (§10).

**Negative / trade-offs:**
- This EDR does not resolve *how* a Typed endpoint is represented, stored, or later migrated to a Registered one — those are architectural questions (§ Deferred).
- Introducing Typed endpoints creates, for the first time, transformer terminals that do not resolve to a GridDefence object; consistency and completeness rules that today assume a Voltage-Yard pair will need generalising (again, an ADR concern).
- Classification remaining engineer-asserted (rather than derived) accepts the possibility of a classification inconsistent with its endpoints until a future consistency check exists (§8) — a deliberate trade-off favouring engineer intent over mechanical inference.

## 13. Explicit Non-Goals

This EDR does **not**:
- prescribe any database schema, ORM mapping, API contract, or frontend behaviour;
- create or modify any migration, model, or reference-data seed;
- change any current transformer, terminal, validation, classification, or PSS/E-correlation behaviour;
- define voltage ratio as a classifier, or fix any classification to a voltage combination;
- decide whether Engineering Endpoint becomes a dedicated entity, is polymorphic, or is embedded vs normalised (all deferred);
- design three-winding representation;
- alter the Layer 2 Operational Snapshot / PSS/E model or its ownership;
- assert defence-scheme eligibility from classification.

## 14. Examples

Voltage combinations are illustrative; the classification follows the interfaced domains, not the ratio. (Two 132/33 kV examples below — Load and SST — deliberately share a ratio while differing in classification, per §2/§8.)

| # | Voltages (HV/LV) | Grid-side endpoint | Non-grid endpoint | Ratified classification |
|---|---|---|---|---|
| 1 | 132/275 kV (275 HV) | Transmission Voltage Yard | Transmission Voltage Yard | **Inter-bus Transformer** |
| 2 | 275/500 kV (500 HV) | Transmission Voltage Yard | Transmission Voltage Yard | **Inter-bus Transformer** |
| 3 | 132/33 kV | Transmission Voltage Yard (132) | Distribution System (33) | **Load Transformer** |
| 4 | 132/33 kV | Transmission Voltage Yard (132) | Station Auxiliary System (33) | **Station Service Transformer** |
| 5 | 275/11 kV | Transmission Voltage Yard (275) | Station Auxiliary System (11) | **Station Service Transformer** |
| 6 | 500/33 kV | Transmission Voltage Yard (500) | Station Auxiliary System (33) | **Station Service Transformer** |
| 7 | 33/132 kV (132 HV) | Transmission Voltage Yard (132) | Generation Collector System (33) | **Generation Step-Up Transformer** |
| 8 | 33/275 kV (275 HV) | Transmission Voltage Yard (275) | Generation Collector System (33) | **Generation Step-Up Transformer** |
| 9 | 33/500 kV (500 HV) | Transmission Voltage Yard (500) | Generation Collector System (33) | **Generation Step-Up Transformer** |
| 10 | 132/33 kV | Transmission Voltage Yard (132) | Customer Installation (33) | **Customer Supply Transformer** |

(In examples 7–9, the generation collector system is the lower-voltage winding; the transmission grid remains the higher-voltage, grid-side endpoint — the classification is determined by the generation collector interface, not by which number is written first.)

## 15. Relationship to EDR-007 and Other Engineering Decisions

- **[EDR-007](EDR-007-phase-7-operational-identity-mapping.md)** observed the operational taxonomy (Inter-bus, generator step-up, three-winding; and the demand-side N-series/F-series) in Layer 2. This EDR is its Layer 1 counterpart: it names the *engineering asset classifications* and endpoint domains those operational observations correspond to, without importing Layer 2 topology authority into Layer 1 (§9). EDR-007's conclusion that generator step-up transformers are "clearly distinguishable" and were "outside the current Engineering Registry scope" is precisely what this EDR now brings *into* Layer 1 scope as the GSU classification with a Generation Collector System endpoint.
- **[EDR-005](EDR-005-bay-as-engineering-identity.md)** established that a Transformer Bay's engineering identity is the `TransformerTerminal`. This EDR builds directly on that identity, adding *what each terminal interfaces* (its Engineering Endpoint) without introducing a new terminal identity.
- **[EDR-003](EDR-003-relay-registry-scope.md)** established recording capability/usage separately from asset identity — the basis for §10's classification-vs-usage separation.
- **[EDR-001](EDR-001-psse-as-operational-context.md)** established PSS/E as operational context, never engineering authority — the basis for §9's boundary.
- **[EDR-008](EDR-008-sensitive-customer-registry-scope.md)** established the customer installation as a black box — consistent with the CST endpoint (§6).

## 16. Deferred Architectural Questions (for the subsequent ADR — recorded, not decided here)

- whether Engineering Endpoint should be a dedicated entity;
- whether endpoint representation should be polymorphic;
- whether typed endpoints are embedded or normalised;
- how existing Voltage Yard foreign keys will be migrated;
- how transformer classification becomes curated reference data;
- how consistency between transformer classification and endpoint kinds will be validated;
- how uniqueness rules generalise beyond a Voltage Yard pair;
- how future Generation, Customer, or Auxiliary registries attach to endpoints;
- how three-winding transformers are represented;
- how PSS/E correlation will consume the endpoint model.

These are architecture and implementation decisions; they must not be resolved in this EDR.
