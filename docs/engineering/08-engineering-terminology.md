# GridDefence Engineering Terminology

This document defines the official engineering vocabulary for GridDefence and explains its relationship to the implementation vocabulary used in the codebase. It exists because a Phase 5 architecture verification found the two vocabularies describing the same engineering concepts under different names in several places — the implementation was correct throughout; only the shared vocabulary was missing.

---

## Purpose

Engineers, developers, and AI coding agents must all be able to discuss the same engineering concept using the same word, regardless of whether they are reading an architecture document, a database model, or an API response. Without a single authoritative vocabulary, the same idea acquires multiple names over time (as has already happened — see the translation table below), and every new contributor has to independently rediscover which names refer to the same thing.

This document is that authority. It does not introduce new engineering concepts — every concept named here is already defined in [02-engineering-concepts.md](02-engineering-concepts.md) or an existing Architecture Decision Record (ADR) / Engineering Decision Record (EDR). It only fixes the vocabulary those concepts should be called by, everywhere.

---

## Engineering Terminology Is Authoritative

When an engineering document, a design discussion, or a code comment explaining *why* something exists needs to name a concept, it uses the **engineering** term — the left-hand column of the translation table below. This is true even inside the codebase: a comment explaining the purpose of a `CircuitTerminal` row should say it represents a **Line Bay**, not invent a second, code-only description of the same idea.

Engineering terminology changes rarely, and only when the underlying engineering concept itself changes — never to match a passing implementation convenience or a refactor.

---

## Implementation Terminology May Differ

The implementation is free to use different, code-appropriate names for the same concept, for reasons that are usually good ones: an existing table name predates a concept being named formally, a generic name was chosen to avoid a premature one-off abstraction (CLAUDE.md §21), or a name was inherited from an earlier design phase before the engineering vocabulary was written down.

**This divergence is expected and is not a defect.** Renaming database tables, models, or API fields to literally match engineering vocabulary is not required, and should not be done reflexively — see [EDR-005](edr/EDR-005-bay-as-engineering-identity.md) for a concrete example (Bay) where the implementation already satisfies the engineering concept perfectly well under a different name, and inventing a new, literally-named entity would have been redundant, premature abstraction. What is required is that the correspondence between the two vocabularies is written down, once, here — so no one has to rediscover it.

---

## Translation Table

| Engineering Term | Implementation | Notes |
|---|---|---|
| **Transformer Bay** | `TransformerTerminal` (Equipment Registry) | One side (HV or LV) of a `Transformer`. Has its own identity, breaker, and voltage yard — see [EDR-005](edr/EDR-005-bay-as-engineering-identity.md). |
| **Line Bay** | `CircuitTerminal` (Equipment Registry) | One substation's own terminal of a `Circuit`. The object PSS®E's `EquipmentTopologyMap` already correlates against, and the object a future Relay Registry entry would attach to. |
| **Transmission Line** / **Primary Equipment** (line) | `Circuit` (Equipment Registry) | The line as a coherent whole, spanning two or more substations. Hosted, at each end, by a Line Bay. |
| **Primary Equipment** (transformer) | `Transformer` (Equipment Registry) | Hosted, at each side, by a Transformer Bay. |
| **Breaker** | `breaker_number` attribute | An attribute of `CircuitTerminal`/`TransformerTerminal` (the Bay), not yet its own entity — sufficient today because GridDefence identifies breakers, it does not asset-manage them. |
| **Grid Defence Capability** / **Relay Capability** | *Future Relay Registry* (not yet built) | Will attach to a `CircuitTerminal` or `TransformerTerminal` — i.e., to a Bay — exactly as `EquipmentTopologyMap` already does for PSS®E correlation. |
| **Switchyard** | `SubstationVoltageYard` (Equipment Registry) | User-facing term as of Phase 3 close-out (ADR-008 addendum); the model/table/API name is unchanged. Engineering Knowledge (Layer 1) — created, edited, and owned only through Equipment Registry. |
| **Operational Switchyard** | Correlated Operational Model concept (`docs/architecture/operational-correlation-architecture.md` §4.1) — no dedicated implementation entity | A read-side correlation of one or more Operational Buses to an existing Switchyard (`SubstationVoltageYard`), matched by Substation identity and `base_kv`, exactly as EDR-007 §4.4 already describes for Switchyard Bus naming. **Not** a registry object, **not** a new entity, and **not** editable — it is a derived relationship, recomputed from Operational Snapshot and Engineering Registry data, never stored as its own authoritative fact. Do not confuse with **Switchyard** above: "Switchyard" is the engineering asset (Layer 1, Equipment Registry); "Operational Switchyard" is that asset's correlation to the *current* Operational Snapshot (Layer 2, Correlated Operational Model). |
| **Operational Projection** | `NetworkModelService`'s existing Registry-sourced read methods (`SubstationConnectivity`, etc.) and PSS/E Integration's `OperationalBusView` family (Phase 7C) are today's concrete examples; no single "projection" entity exists in code | A named output view of the Correlated Operational Model at a chosen granularity — Bus View, Switchyard View, Substation View, Branch View, Transformer View, or Load View (`operational-correlation-architecture.md` §4.2). A read model only: it never introduces a new source of truth, and different projections of the same underlying result must never disagree, because they are views over one correlated model, not independent computations. |
| **Line Connectivity Registry** | Equipment Registry's `Circuit`/`CircuitTerminal` records (identity and engineering metadata — bay numbers, breaker numbers, line type) | **Reframed under the Operational Snapshot pivot** (EDR-007, `docs/architecture/operational-snapshot-architecture.md`): the curated metadata registry is realized directly in Equipment Registry's own tables. `network_model` (Phase 5, `backend/app/modules/network_model/`) is a read-only query/composition layer built from these records — the first software-side connectivity *view*, not the authoritative source of *current* electrical connectivity. That authority belongs to Operational Snapshot (PSS/E Integration's `TopologyVersion`/`LoadSnapshot`). `network_model`'s intended future direction (see `network-model-module.md` §19's reconciliation note) is to become a metadata-correlation layer over Operational Snapshot, not an independent connectivity source. Not to be confused with the still-unbuilt PSS/E-topology-analysis capability also described under the name "Network Model" in `docs/architecture/network-model-module.md` §1–§18. |
| **Bay Number** | `Circuit.bay_number` / `Transformer.transformer_number` | The circuit-level or transformer-level human designator ("1", "Main") — a property of the whole `Circuit`/`Transformer`, shared across its Bays, distinct from each Bay's own `breaker_number`. |
| **Working Draft** → **Scheme Review** → **Published Scheme** → **Archived Scheme** (Scheme Lifecycle) | `Draft` → `Under Review` → `Approved`/`Active` → `Superseded`/`Archived` (Canonical Version Lifecycle, CLAUDE.md A3) | Future scheme modules (UFLS/UVLS/EMLS). The engineering lifecycle names the states an engineer reasons about; the implementation's Canonical Version Lifecycle additionally distinguishes `Approved` (reviewed, not yet governing) from `Active` (currently governing) — a software-level refinement of "Published," not a contradiction of it. |

This table is not exhaustive by design — it grows as new correspondences are found. See "Guidelines for Documentation" below for how to add to it.

---

## Guidelines for Documentation

- Engineering documents (`docs/engineering/`, and the conceptual/domain-model sections of `docs/architecture/*-module.md`) use **engineering terminology** when describing what a concept *is* and *why it matters*.
- Architecture documents may, and should, name the corresponding **implementation** term alongside the engineering term the first time a concept is discussed in an implementation-facing section (database design, API contract) — exactly as `equipment-registry-module.md` already does throughout (e.g. "Switchyard" / `SubstationVoltageYard").
- When a new correspondence between an engineering term and an implementation name is discovered — during a new module's design, an architecture review, or an implementation pass — add it to the translation table above. Do not leave it undocumented, and do not invent a third name for the same concept in the document where it was found.
- `docs/engineering/04-domain-model.md` describes engineering relationships only; it should stay implementation-independent in its diagrams, using at most a brief, clearly-marked pointer to this document for the corresponding implementation names (see its own §1 for the current example).

## Guidelines for Implementation

- Code identifiers (table names, model classes, DTO fields) are **not required** to be renamed to match engineering vocabulary. A working, already-proven implementation name (`CircuitTerminal`, `TransformerTerminal`) should not be changed just to look more like the engineering term — that would be exactly the kind of unnecessary, disruptive refactor CLAUDE.md §21 and this project's own precedent (see `equipment_registry/models.py`'s own header comment on deliberately not building a generic `Equipment`/`Bay` backbone) both caution against.
- Code comments and docstrings that explain *why* an entity or field exists **should** reference the engineering term, so a future reader can connect the implementation to the engineering concept without needing to consult this document from scratch — exactly as `equipment-registry-module.md` and `CircuitTerminal`'s own docstring already do ("the object Relay Registry wires to").
- When a **new** module or entity is introduced for a concept already named in [02-engineering-concepts.md](02-engineering-concepts.md), check this document first. If the engineering term already maps to an existing implementation entity, reuse that entity — do not create a second, differently-named representation of the same concept (this is precisely the mistake [EDR-005](edr/EDR-005-bay-as-engineering-identity.md) confirms must not happen for Bay).
- If no mapping exists yet because the concept is genuinely new, implement it, then add the new mapping to the translation table above as part of that same change.

---

## Examples

**Engineering phrasing:** "The Transformer Bay's Grid Defence Capability is verified against the Relay Registry before it may be assigned to a Shedding Action."

**Implementation phrasing (equivalent):** "A future Relay Registry entry, keyed to a `transformer_terminal_id`, is checked before a scheme module accepts that `TransformerTerminal` as a candidate for a shedding assignment."

---

**Engineering phrasing:** "A Line Bay's Primary Equipment — the transmission line it hosts — may be replaced or re-terminated without the Bay itself changing identity."

**Implementation phrasing (equivalent):** "A `CircuitTerminal` row's own identity (`circuit_terminal_id`) is independent of which `Circuit` it currently belongs to; a re-termination is modeled as a data correction to the terminal's `circuit_id`, not as deleting and recreating the terminal."

---

**Engineering phrasing:** "The Line Connectivity Registry identifies which circuit connects a substation to its neighbour; Operational Snapshot confirms that connection is currently electrically present."

**Implementation phrasing (equivalent):** "`NetworkModelService.list_substation_neighbours` (`backend/app/modules/network_model/service.py`) currently answers this from Equipment Registry's `CircuitTerminal` rows alone, as a static, PSS/E-independent view. Per the Operational Snapshot pivot, this remains a valid statement of *declared* identity, but is not the authoritative statement of *current* connectivity — that answer should ultimately be derived from PSS/E Integration's `TopologyVersion`, correlated back to the `CircuitTerminal` via `EquipmentTopologyMap`, per `network-model-module.md` §19's own reconciliation note. No code change is made by this documentation pass."
