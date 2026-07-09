# EDR-007: Phase 7 — Operational Identity Mapping

- **Status:** Living Document. The Tier 1 Operational Model is fully documented: Bus Data (§4), Branch Data (§5), Transformer Data (§6), Load Data (§7), and Generator Data (§8). Numerous Open Questions (§10) remain unresolved and this document continues to be expanded in place as future Phase 7 investigation warrants.
- **Governing document:** [01-engineering-philosophy.md](../01-engineering-philosophy.md) §6 (Layer 2 — Operational Context); [02-engineering-concepts.md](../02-engineering-concepts.md) — PSS/E Network Topology, PSS/E Load Snapshot
- **Related:** [EDR-001](EDR-001-psse-as-operational-context.md) (PSS®E as Operational Context, not engineering truth); [08-engineering-terminology.md](../08-engineering-terminology.md) (Switchyard translation); `docs/architecture/psse-integration-module.md` (existing PSS/E Integration module, referenced for context only — this record does not describe or constrain its implementation)

---

## 1. Purpose

This document is the authoritative engineering reference describing how the PSS®E operational model relates to the GridDefence engineering model — specifically, how the identifiers and naming conventions found in a PSS®E RAW file correspond (or deliberately do not correspond) to Substation Registry and Equipment Registry objects.

It exists to separate **engineering discovery** — what a PSS®E object actually represents, and what it does or does not correspond to in GridDefence's own engineering model — from **architecture and implementation decisions**, which belong in a future ADR once this discovery is complete. This document records engineering truth only. It does not design software.

This is a living document. It is created once and expanded in place as each Tier 1 Operational Model section is studied — Bus Data first, then Branch, Transformer, Load, and Generator Data in subsequent Phase 7 revisions. Later revisions append; they do not restate or replace earlier sections without a recorded reason (see §11, Revision History).

## 2. Scope

**Documented so far:** Bus Data (§4) — its role in the operational model, its identifiers, its naming conventions, and how (or whether) each kind of Bus corresponds to a GridDefence Engineering Registry object; Branch Data (§5) — its role, its identity, its connectivity, and the topology patterns observed in the analysed sample RAW file; Transformer Data (§6) — its role, its identity, the operational voltage-transformation scenarios observed, and the patterns and correlation philosophy established from the analysed sample RAW file; Load Data (§7) — its role, its identity, the operational demand categories established from the analysed sample RAW file and TNB engineering practice, and its correlation philosophy; and Generator Data (§8) — its role as supporting operational context, its identity, and its correlation philosophy.

**All five Tier 1 Operational Model sections (§3) are now documented.** This does not close the document — Open Questions (§10) remain, and later revisions may still append further discovery.

**Terminology.** This document uses TNB engineering terminology wherever an established engineering term exists (e.g. Inter-bus transformer, Switchyard, Fictitious Bus). Generic power-system terminology is used only where no established TNB equivalent exists.

**Out of scope for this document, and for Phase 7 generally:** PSS®E RAW sections outside the five named in §3. This document does not comment on their engineering meaning at all, favorably or otherwise — they are simply not part of this study.

**Out of scope for this document, by its own nature (EDR, not ADR):** database design, parser behaviour, correlation algorithms, and any other implementation detail. Where an engineering conclusion below will eventually require an implementation decision, this document says so and defers it — it does not make that decision itself.

## 3. Tier 1 Operational Model

For the purposes of Phase 7, GridDefence's engineering study of the PSS®E operational model is scoped to five core RAW sections, referred to collectively as the **Tier 1 Operational Model**:

- Bus Data
- Branch Data
- Transformer Data
- Load Data
- Generator Data

These five sections are the ones GridDefence's engineering model needs a considered position on, because they are the sections whose contents plausibly correspond — fully, partially, or not at all — to Substation Registry and Equipment Registry objects. Other RAW sections are currently outside the scope of this engineering study; this is a statement about present study scope, not a permanent judgment that they are unimportant.

"Tier 1" is a scoping term introduced for Phase 7's own purposes. It identifies which part of PSS®E's own data model is currently under engineering study; it is not a replacement for, or a peer of, the Engineering Information Layers (Layer 1 — Engineering Knowledge, Layer 2 — Operational Context, Layer 3 — Engineering Decisions) established in [01-engineering-philosophy.md](../01-engineering-philosophy.md) §6. The Tier 1 Operational Model sits entirely inside Layer 2 (Operational Context) — it is a finer-grained statement of *which parts* of PSS®E Network Topology and PSS®E Load Snapshot this phase is studying, not a new layer.

## 4. Bus Data

### 4.1 Role of Bus Data

Bus Data forms the foundation of the operational network model. Every other Tier 1 operational object — Branch, Transformer, Load, and Generator — ultimately references one or more Bus Numbers. A Bus is the point of electrical connection that every other operational object attaches to; nothing else in the Tier 1 Operational Model can be understood, or correlated against the Engineering Registry, independently of the Bus Data it references.

### 4.2 Bus Number

Bus Number is the primary operational identifier within a PSS®E model.

- Every Branch, Transformer, Load, and Generator record references one or more Bus Numbers.
- Correlation between operational objects — determining which Branch, Transformer, Load, or Generator records relate to which Bus — must always be performed using Bus Numbers.
- Bus Numbers must never be inferred from Bus Names. A Bus Number is an explicit, already-present identifier on every record that carries it; it is never guessed, derived, or reconstructed from naming convention.

Bus Number is purely an internal PSS®E operational identifier. On its own, it carries no engineering identity — it says nothing about which Substation or Switchyard the Bus belongs to. That correlation is Bus Name's role (§4.3).

### 4.3 Bus Name

Bus Names provide the engineering correlation between the PSS®E operational model and the GridDefence Engineering Registry. Where Bus Number answers "which operational node is this, within this PSS®E model," Bus Name is what allows GridDefence to ask "which real, registered engineering asset does this operational node represent, if any."

Bus Names are classified into three categories, each with a distinct engineering meaning:

- Switchyard Bus (§4.4)
- Split Switchyard Bus (§4.5)
- Fictitious Bus (§4.6)

### 4.4 Switchyard Bus

**Naming convention:**

```text
<4-character mnemonic><nominal voltage>
```

**Examples:**

```text
ABBA132
KLGT275
BDKY500
```

A Switchyard Bus correlates directly with a **Substation** and a **Switchyard** within the Engineering Registry. The leading 4-character mnemonic identifies the Substation; the trailing nominal voltage identifies which of that Substation's Switchyards the Bus represents. This is the ordinary, expected shape for a Bus that represents a real, registered switchyard.

### 4.5 Split Switchyard Bus

**Naming convention:**

```text
<4-character mnemonic><nominal voltage><suffix>
```

**Examples:**

```text
BLPS132L
BLPS132R
```

**Engineering interpretation:**

- These are genuine operational buses, not an artifact of the naming convention or the parser.
- They occur when a physical switchyard is operating with separated bus sections — for example, with a bus coupler open.
- The suffix represents the operational bus section (e.g. left/right), not a separate engineering asset.
- A Split Switchyard Bus does **not** represent a separate Substation.
- A Split Switchyard Bus does **not** represent a separate Switchyard.
- Both buses of a split pair correlate to the **same** Engineering Registry Switchyard. The split is an operational condition of one Switchyard, observed at one point in time — never two Switchyards, and never two Substations.

### 4.6 Fictitious Bus

**Examples:**

```text
TJGSM1A
TJGSM1B
```

- Fictitious Buses are valid PSS®E Operational Topology nodes.
- They exist to support electrical network modelling — PSS®E's own representation sometimes requires a node that has no counterpart in the physically registered switchyard arrangement.
- Fictitious Buses are not engineering assets — they do not directly correspond to any object in the Engineering Registry.
- GridDefence should not attempt to correlate Fictitious Buses with any Engineering Registry object.
- Fictitious Buses are not ignored. They remain part of the imported operational network and may participate in Operational Topology traversal, exactly as any other Bus does — the absence of an Engineering Registry correspondence does not remove them from the Operational Topology.

No further engineering interpretation of Fictitious Buses is established beyond the conclusions above; how they arise, how they are best recognized in general, and how Operational Topology traversal should treat them are open questions (§10), not resolved here.

### 4.7 Correlation Philosophy

- Switchyard Buses are correlated with the Engineering Registry — both the Switchyard Bus (§4.4) and Split Switchyard Bus (§4.5) forms.
- Fictitious Buses (§4.6) are retained as part of the Operational Topology but have no direct Engineering Registry identity. GridDefence does not attempt to correlate them with any Engineering Registry object.
- Retaining a Fictitious Bus without correlating it is not the same as disregarding it: it remains a valid Operational Topology node and may participate in Operational Topology traversal, exactly as a correlated Bus does.
- Bus Number remains the authoritative basis for operational identity when correlating operational data originating from different Operational Snapshots — the same Bus Number authority already established for correlation within one snapshot (§4.2) extends across snapshots (Engineering Principle 12, §9).

This is a statement of engineering intent, not an implementation design. It does not specify how correlation is determined, computed, or persisted — those are architecture and implementation questions for a future ADR to resolve, informed by this record.

### 4.8 Engineering Conclusions

1. Bus Data is the foundation of the Tier 1 Operational Model — every other Tier 1 object depends on it.
2. Bus Number is the sole authoritative identifier for correlating operational objects to one another; it is never inferred from Bus Name.
3. Bus Name is the sole basis for correlating a Bus with the Engineering Registry; it plays no role in operational-object-to-operational-object correlation.
4. Three, and only three, Bus Name categories are currently recognized: Switchyard Bus, Split Switchyard Bus, and Fictitious Bus.
5. A Switchyard Bus and a Split Switchyard Bus both correlate to real Engineering Registry objects (Substation and Switchyard); a Fictitious Bus does not correlate to any.
6. A Split Switchyard Bus is one Switchyard's operational condition, never two Switchyards or two Substations.

## 5. Branch Data

### 5.1 Role of Branch Data

Branch Data represents electrical connectivity within the Operational Topology. Every Branch connects two Bus Numbers. Branch Data builds upon the Bus Data section (§4) — a Branch cannot be understood independently of the Bus Data it references. Branches derive their engineering meaning entirely from the buses they connect; a Branch record carries no engineering meaning of its own, apart from that.

### 5.2 Branch Identity

A Branch record consists primarily of:

- From Bus
- To Bus
- Circuit ID
- Operational status
- Electrical parameters

Bus Numbers remain the authoritative operational identifiers (§4.2) — a Branch's From Bus and To Bus fields reference Bus Number, never Bus Name. Branches do not directly identify Engineering Registry assets: a Branch's own identity (From Bus, To Bus, Circuit ID) is purely operational, and whatever Engineering Registry correspondence exists is inherited entirely from the Bus Names (§4.3) of the buses it connects — never asserted by the Branch record itself.

### 5.3 Branch Connectivity

A Branch represents an electrical connection between two operational buses. Branches may connect:

- Switchyard Bus ↔ Switchyard Bus
- Switchyard Bus ↔ Fictitious Bus
- Other bus categories that remain under investigation (§10)

Branch Data describes Operational Topology rather than engineering asset ownership — a Branch record states how two operational nodes are electrically connected, not which Engineering Registry assets, if any, they represent.

### 5.4 Observed Topology Patterns

The patterns below are recorded as **observations from the analysed sample RAW file**, not as a claim of universal PSS®E modelling behaviour. Where more than one pattern was observed, each is described separately, and no pattern is generalized beyond what the analysed evidence shows.

**Pattern A — Direct connection between Switchyard Buses.** The ordinary case: a Branch connecting two buses that each independently correlate to the Engineering Registry.

**Pattern B — Branch connectivity involving Fictitious Buses.** Some observed Fictitious Buses participate in connectivity consistent with multi-terminal junction or tee-off modelling — several Branches from one Fictitious Bus to multiple distinct Switchyard Buses. This is recorded as an observed pattern only. Not every Fictitious Bus observed followed it, and it is not established that every Fictitious Bus represents a tee-off.

**Pattern C — Near-zero impedance Branch connections associated with certain Fictitious Bus configurations.** A separately observed, distinct pattern: some Fictitious Buses connect to a Switchyard Bus via a Branch whose impedance is negligible, quantitatively distinct from the meaningful impedance observed elsewhere. This is recorded as a distinct observed modelling pattern whose engineering purpose has not yet been fully established. No further interpretation is offered here.

### 5.5 Correlation Philosophy

- Branch Data belongs to the Operational Topology.
- Branch records are not interpreted as direct Engineering Registry assets.
- A single engineering transmission corridor or line may be represented by one or more Branch records, depending on the operational topology.
- Correlation with the Line Connectivity Registry remains an engineering question to be resolved after the remaining Phase 7 discoveries (§6–§8) are complete.

This is a statement of engineering intent, not an implementation design — consistent with §4.7's own disclaimer. It does not specify how correlation with the Line Connectivity Registry is determined, computed, or persisted.

### 5.6 Engineering Conclusions

1. Branch Data describes operational connectivity within the Operational Topology.
2. Branch identity depends on Bus identity — a Branch has no engineering meaning apart from the Bus Numbers, and by extension the Bus Names, it connects.
3. Fictitious Buses participate in valid Operational Topology via Branch Data, exactly as Switchyard Buses do.
4. Observed Branch topology may contain intermediate operational nodes without implying additional Engineering Registry assets — an operational path between two Engineering-Registry-correlated buses may pass through one or more Fictitious Buses.

## 6. Transformer Data

### 6.1 Role of Transformer Data

Transformer Data represents operational voltage transformation within the Operational Topology. Transformer Data builds upon Bus Data (§4) — Transformer terminals are identified using Bus Numbers, exactly as Branch Data's terminals are (§5.2). Transformer records describe voltage transformation between operational buses; a Transformer record has no engineering meaning apart from the buses it connects.

### 6.2 Transformer Identity

Transformer records are primarily identified by:

- Bus I
- Bus J
- Bus K (where applicable)
- Circuit ID

The RAW file's Transformer Name field exists but was blank for every Transformer record in the analysed sample — no exceptions were observed. Transformer identity therefore relies on Bus relationships (Bus I, Bus J, Bus K, Circuit ID) rather than a transformer name.

### 6.3 Operational Voltage Transformation

The analysed Transformer Data contains multiple engineering scenarios. The following were confirmed against the analysed sample RAW file.

**Scenario A — Inter-bus transformer (TNB terminology).** An Inter-bus transformer connects two transmission switchyards operating at different nominal voltage levels within the transmission network (e.g. 132/275 kV, 275/500 kV, 230/275 kV). This terminology follows TNB engineering practice and is used consistently throughout this document. Characteristics observed: it connects recognised Switchyard Buses; it connects different transmission voltage levels; it is often represented by multiple parallel Transformer records. An Inter-bus transformer represents genuine operational voltage transformation between transmission switchyards.

**Scenario B — Generator step-up transformer.** One terminal ultimately connects to a generating unit; the generator terminal is isolated from the Branch network except through its own transformer; this shape repeated consistently across multiple generating units in the analysed sample. This is recorded only as the observed engineering pattern.

**Scenario C — Three-winding transformer representation.** In the analysed TNB network, Inter-bus transformers are commonly represented as three-winding transformers. The operational relationship relevant to GridDefence is the HV/LV voltage transformation; the tertiary winding forms part of the engineering transformer representation, not an anomaly or an artefact of the modelling. Within the current GridDefence application scope, the tertiary winding typically serves station auxiliary supplies and/or reactive compensation (such as shunt reactors), and therefore does not participate in the application's operational analysis. This is a statement about current application scope, not a statement that the tertiary winding is disregarded, invalid, or unreal — it remains a genuine part of the engineering transformer representation.

### 6.4 Observed Operational Patterns

The patterns below are recorded as observations supported by the analysed sample RAW file:

- Parallel transformers, between the same Bus I/Bus J pair, distinguished by Circuit ID.
- Generator terminals consistently connected through their own transformer, never through a Branch.
- Three-winding representation used for Inter-bus transformers in the analysed TNB network (Scenario C).

### 6.5 Correlation Philosophy

- Transformer Data belongs to the Operational Topology.
- Operational Transformer records do not necessarily represent a single engineering category — Scenarios A, B, and C above are each a distinct engineering concept.
- Inter-bus transformers naturally correlate with the existing Transformer Registry.
- Other operational transformer representations (such as generator step-up transformers) are recognised as valid operational patterns but remain outside the current Engineering Registry scope.
- Correlation of specialised operational transformer representations remains outside the current Phase 7 engineering conclusions.

This is a statement of engineering intent, not an implementation design — consistent with §4.7's and §5.5's own disclaimer.

### 6.6 Engineering Conclusions

1. Transformer Data represents operational voltage transformation within the Operational Topology.
2. Inter-bus transformers are clearly distinguishable from generator step-up transformers.
3. Three-winding representation is part of the engineering model for Inter-bus transformers in the analysed TNB network, rather than a modelling anomaly.
4. Transformer identity is determined primarily by operational Bus relationships (Bus I, Bus J, Bus K, Circuit ID), not by a transformer name.

## 7. Load Data

### 7.1 Role of Load Data

Load Data represents operational demand attached to operational buses. Load Data derives its operational identity from Bus Data (§4) — a Load record cannot be understood independently of the Bus it is attached to. Load Data forms part of the Operational Topology. Load Data represents operational demand modelling rather than a single engineering category — as established below (§7.3), different recurring Load ID patterns correspond to genuinely different engineering purposes, not variations of one demand model.

### 7.2 Load Identity

Load records are primarily identified by:

- Bus Number
- Load ID

Multiple recurring Load ID patterns were observed in the analysed sample RAW file. §7.3 records what each pattern was found to represent; this subsection records only that they exist and recur.

### 7.3 Operational Demand Representation

The engineering categories below combine three distinct kinds of statement, each labelled: **observed** (directly supported by the analysed sample RAW file), **TNB interpretation** (established TNB engineering practice, supplied as domain knowledge rather than derived from topology alone), and **application scope** (a statement about current GridDefence application scope, not about engineering reality).

**Category A — T-series.** TNB terminology: represents **Load Transformer** demand. *TNB interpretation:* commonly associated with transmission-to-distribution transformers (132/33 kV, 132/22 kV, 132/11 kV and similar arrangements); represents the operational demand supplied through Load Transformers. *Observed:* the dominant operational demand category in the analysed sample.

**Category B — F-series.** TNB terminology: represents **Spur Large Consumer** substations. *TNB interpretation:* rather than modelling the customer's internal transformer arrangement, PSS®E models the demand directly at transmission voltage; represents customer demand. *Observed:* typically associated with Branch-connected Switchyard Buses.

**Category C — N-series.** TNB terminology: represents **Generating Station Auxiliary Supply** — auxiliary supply imported from the transmission network. This is distinct from Generator-terminal modelling (Category D): Generating Station Auxiliary Supply is demand drawn *from* the transmission network to support a generating station's own operation, not the generating unit's own terminal representation.

**Category D — X-series.** Represents Generator-terminal operational modelling. Does not represent ordinary customer demand. *Observed:* consistently appears as zero-MW operational loads associated with Generator terminals in the analysed sample.

**Category E — External and Special Operational Load Representations.** *Observed:* Numeric Load IDs are overwhelmingly associated with Owner 99 within the analysed sample; Owner 99 correlates consistently with Blank-named Buses. *TNB interpretation:* Owner 99 — SPPG (Singapore network); Owner 5 — EGAT (Thailand interconnection); Owner 1 — TNB customer substations with embedded cogeneration; Owner 106 — LSS substations.

These operational load representations remain valid components of the Operational Topology. Within the current GridDefence application scope, they lie outside the defence scheme management scope.

**No separate engineering category is established for the small `1A`/`1B`/`2A`/`2B` Load ID group.** The analysed evidence (6 records at two substations) is insufficient to establish a general engineering category; this remains an unresolved observation (§10).

### 7.4 Observed Operational Patterns

The patterns below are recorded as observations supported by the analysed sample RAW file:

- T-series dominates the analysed sample.
- F-series consistently represents Branch-connected Spur Large Consumer modelling.
- N-series consistently represents Generator Station Auxiliary Supply.
- X-series consistently appears at Generator terminals.
- Numeric-ID loads predominantly correlate with Owner 99 and Blank-named Buses.
- No Load record was observed on any confirmed Fictitious Bus.

### 7.5 Correlation Philosophy

- Load Data belongs to the Operational Topology.
- Operational Load records represent multiple engineering categories, not one homogeneous demand model.
- Engineering interpretation depends upon operational context and established TNB engineering practice.
- Only some operational demand categories fall within the current GridDefence engineering scope.
- Operational objects outside the current application scope remain preserved within the Operational Topology.

This is a statement of engineering intent, not an implementation design — consistent with §4.7's, §5.5's, and §6.5's own disclaimer.

### 7.6 Engineering Conclusions

1. Load Data represents multiple engineering categories rather than one homogeneous demand model.
2. Load ID carries engineering meaning.
3. Different Load categories represent different operational purposes.
4. Operational relevance depends upon engineering interpretation rather than Load records alone.

## 8. Generator Data

Generator Data is documented more concisely than §4–§7. Unlike Bus, Branch, Transformer, and Load Data, Generator Data is recorded as **supporting operational context** for GridDefence, not as a primary Engineering Registry or defence-scheme assignment object.

### 8.1 Role of Generator Data

Generator Data represents operational generation connected to buses. Generator Data derives its operational identity from Bus Data (§4). Generator Data provides supporting operational context. Generator Data does not carry the same GridDefence functional weight as Bus, Branch, Transformer, or Load Data.

### 8.2 Generator Identity

Generator records are primarily identified by:

- Bus Number
- Generator ID

Generator ID was overwhelmingly `1` in the analysed sample. Generator ID did not show a rich engineering naming convention comparable to Load ID or Transformer Circuit ID.

### 8.3 Operational Generation Context

Generator Data indicates where generation is injected into the operational model. Most Generator records occur on non-switchyard operational buses. Generator records are commonly associated with Generator-terminal modelling and Generator Step-Up Transformer arrangements. Generator Data should be understood as operational context rather than Engineering Registry identity.

### 8.4 Observed Operational Patterns

- The dominant pattern is Generator-terminal modelling: a Generator connected at a non-conforming generator terminal bus, commonly associated with one Generator Step-Up Transformer and X-series modelling load.
- Some Generator records occur on Blank-named Buses with Numeric loads.
- A small number of special cases were observed, including Branch-connected generators, HVDC-style representation, SVG-like naming, and one ordinary Switchyard Bus generator.
- No Generator record was observed on any confirmed Fictitious Bus.

### 8.5 Correlation Philosophy

- Generator Data belongs to the Operational Topology.
- Generator Data is preserved as part of the PSS®E operational context.
- Detailed generator modelling, generator asset management, dispatch, AVR, and plant operation are outside the current GridDefence application scope.
- Generator Data may support dashboard context or future analytics but does not currently drive defence-scheme assignment.

### 8.6 Engineering Conclusions

1. Generator Data represents operational generation context.
2. Generator Data validates that generation is modelled primarily through Generator-terminal arrangements.
3. Generator records should not be treated as Engineering Registry assets in the current application scope.
4. Observed special cases should remain preserved but unresolved unless future GridDefence requirements require deeper treatment.

## 9. Engineering Principles Established

These are recorded as enduring engineering guidance — statements about what PSS®E operational objects *are*, engineering-wise — not as implementation rules. They are expected to inform, but not themselves constitute, future architecture decisions.

1. Bus Data is the foundation of the Tier 1 Operational Model.
2. Bus Number is the authoritative operational identifier, used exclusively for correlating operational objects to one another.
3. Bus Names provide the engineering identity correlation between the PSS®E operational model and the GridDefence Engineering Registry.
4. Switchyard Bus naming follows `<4-character mnemonic><nominal voltage>`, and correlates directly to a Substation and a Switchyard.
5. Split Switchyard Buses remain part of the same physical Switchyard — a split is an operational condition, never a second engineering asset.
6. Fictitious Buses are Operational Topology nodes rather than engineering assets, and are not correlated against the Engineering Registry.
7. GridDefence shall preserve the Operational Topology represented by PSS®E, including modelling constructs such as Fictitious Buses. Although these buses do not directly correspond to Engineering Registry assets, they remain valid Operational Topology nodes and contribute to the electrical representation of the network.
8. Branch Data preserves the electrical connectivity of the Operational Topology. Engineering interpretation of Branches depends upon the connected Bus identities rather than Branch records alone.
9. Transformer Data represents operational voltage transformation within the Operational Topology. Engineering interpretation depends on the operational role of the transformer and the identities of its connected buses rather than the Transformer record alone.
10. Operational Load records may represent multiple engineering categories. Engineering interpretation shall be determined from operational context and established TNB engineering conventions rather than the Load record alone.
11. Generator Data provides supporting operational context for GridDefence. It shall be preserved as part of the Operational Topology, but detailed generator modelling remains outside the current GridDefence application scope unless future engineering requirements expand that scope.
12. **Operational Identity Persistence.** The Bus Number is the authoritative operational identity across PSS®E Operational Snapshots. When operational data originating from multiple PSS®E RAW files is correlated, Bus Number shall remain the authoritative basis for operational identity and correlation. Operational objects that cannot be correlated through Bus Number represent engineering inconsistencies requiring engineering review rather than automatic interpretation.

## 10. Open Questions

These are discussion items for future Phase 7 investigation. They are not resolved in this revision, and this document does not speculate toward an answer.

- How should Branch connections involving Fictitious Buses be understood, engineering-wise?
- How should Transformer connections involving Fictitious Buses be understood, engineering-wise?
- Are there split-bus suffix conventions beyond the currently observed examples (`L`/`R`) that need to be accounted for?
- How should Operational Topology traversal treat a path that passes through a Fictitious Bus?
- What is the engineering interpretation of the multi-terminal Branch patterns observed at certain Fictitious Buses (§5.4, Pattern B)?
- What is the engineering meaning of the near-zero impedance Branch connections observed at certain Fictitious Bus configurations (§5.4, Pattern C)?
- How should multiple Branch records correlate with a single Line Connectivity Registry asset?
- What is the engineering meaning of the remaining non-conforming Bus naming groups not yet individually examined?
- What is the engineering meaning of blank-named buses?
- A very small number of Transformer records involving Fictitious Buses were observed in the analysed sample. Their engineering purpose could not be generalised from the analysed evidence — although one example was understood through engineering interpretation, the observed population is too small to establish a general engineering rule, and future RAW files may contain additional modelling patterns not yet seen. This remains intentionally unresolved.
- Whether additional operational transformer modelling patterns exist in other PSS®E datasets beyond the single sample file analysed so far.
- Whether specialised operational transformer representations (such as generator step-up transformers) should remain outside the current GridDefence Engineering Registry scope, or eventually be brought into it.
- Whether additional Load ID categories exist in future PSS®E datasets.
- Whether the observed Load ID conventions remain consistent across future RAW files.
- A small number of site-specific Load ID conventions (for example `1A`/`1B`/`2A`/`2B`) were observed at large consumer substations alongside F-series loads. Their engineering purpose could not be established from the available evidence and remains intentionally unresolved pending future investigation.
- Whether Blank-named Bus generator patterns require future interpretation.
- Whether HVDC, SVG-like, or Branch-connected generator representations require future treatment.
- Whether future GridDefence analytics will require deeper Generator Data semantics.
- Future engineering work shall determine the engineering acceptance criteria for correlating Operational Topology and Load-only Operational Snapshots originating from different study processes, including the treatment of unmatched or inconsistent Bus Numbers.

## 11. Revision History

| Revision | Date | Summary |
|---|---|---|
| 1 | 2026-07-07 | Initial creation. Documents Bus Data (§4) in full: Bus Number, Bus Name, Switchyard Bus, Split Switchyard Bus, Fictitious Bus, Correlation Philosophy, and Engineering Conclusions. Branch, Transformer, Load, and Generator Data (§5–§8) recorded as placeholders. |
| 2 | 2026-07-07 | Wording amendment, no engineering conclusions changed. Refined §4.7 Correlation Philosophy and §4.6 Fictitious Bus to state more clearly that Fictitious Buses are retained (not ignored), are not engineering assets, and remain part of the imported operational network. Added Engineering Principle 7 (§9) on preserving the Operational Topology represented by PSS®E, including Fictitious Buses. Standardized terminology throughout ("Switchyard Bus" in place of "Standard Switchyard Bus"; "Operational Topology" used consistently in place of ad hoc lowercase phrasing; "Engineering Registry" used in place of an inconsistent "Substation Registry or Switchyard Registry" reference). |
| 3 | 2026-07-07 | Documents Branch Data (§5) in full, from the Branch Data engineering discovery performed against the analysed sample RAW file: Role of Branch Data, Branch Identity, Branch Connectivity, Observed Topology Patterns (Pattern A — direct Switchyard Bus connections; Pattern B — multi-terminal/tee-off-consistent connectivity at some Fictitious Buses; Pattern C — near-zero impedance connections at some Fictitious Bus configurations), Correlation Philosophy, and Engineering Conclusions. Added Engineering Principle 8 (§9) on Branch Data preserving Operational Topology connectivity. Added five Open Questions (§10) arising from the Branch Data analysis. Updated the Status line and §2 Scope to reflect that Bus Data and Branch Data are now both documented. Transformer, Load, and Generator Data (§6–§8) remain placeholders. |
| 4 | 2026-07-07 | Documents Transformer Data (§6) in full, from the Transformer Data engineering discovery performed against the analysed sample RAW file: Role of Transformer Data, Transformer Identity, Operational Voltage Transformation (Scenario A — Inter-bus transformer, TNB terminology, defined here for the first time; Scenario B — generator step-up transformer; Scenario C — three-winding representation, with the tertiary winding's typical station-auxiliary/reactive-compensation role recorded as current-scope context, not disregard), Observed Operational Patterns, Correlation Philosophy, and Engineering Conclusions. Added Engineering Principle 9 (§9). Added three Open Questions (§10), including the intentionally unresolved status of the small number of Transformer records involving Fictitious Buses (3 of 560 in the analysed sample). Added a Terminology note (§2) recording that this document uses TNB engineering terminology wherever an established term exists. Updated the Status line and §2 Scope to reflect that Bus Data, Branch Data, and Transformer Data are now all documented. Load and Generator Data (§7–§8) remain placeholders. |
| 5 | 2026-07-07 | Documents Load Data (§7) in full, from the Load Data engineering discovery performed against the analysed sample RAW file: Role of Load Data, Load Identity, Operational Demand Representation (Category A — T-series / Load Transformer demand; Category B — F-series / Spur Large Consumer; Category C — N-series / Generating Station Auxiliary Supply; Category D — X-series / Generator-terminal modelling; Category E — External and Special Operational Load Representations, combining observed Owner correlation with TNB interpretation of Owners 99/5/1/106), Observed Operational Patterns, Correlation Philosophy, and Engineering Conclusions. Throughout §7.3, engineering observations from the analysed sample, TNB engineering interpretation, and current GridDefence application scope are kept explicitly distinct. No separate category was created for the small `1A`/`1B`/`2A`/`2B` Load ID group (6 records, two substations) — recorded instead as an unresolved Open Question. Added Engineering Principle 10 (§9). Added three Open Questions (§10). Updated the Status line and §2 Scope to reflect that Bus Data, Branch Data, Transformer Data, and Load Data are now all documented. Generator Data (§8) remains a placeholder. |
| 6 | 2026-07-07 | Documents Generator Data (§8), deliberately concise, from the Generator Data engineering discovery/validation performed against the analysed sample RAW file: Role of Generator Data, Generator Identity, Operational Generation Context, Observed Operational Patterns, Correlation Philosophy, and Engineering Conclusions. Generator Data is recorded as supporting operational context, not as a primary Engineering Registry or defence-scheme assignment object — a deliberate scope distinction from §4–§7. Observed special cases (Blank-named Bus generators with Numeric loads, Branch-connected generators, HVDC-style representation, SVG-like naming, one Switchyard Bus generator) are noted but intentionally left unresolved rather than individually explained. Added Engineering Principle 11 (§9). Added three Open Questions (§10). Updated the Status line and §2 Scope: all five Tier 1 Operational Model sections (Bus, Branch, Transformer, Load, and Generator Data) are now documented — this does not close the document, as Open Questions (§10) remain and future revisions may still append. |
| 7 | 2026-07-07 | Additive amendment — Operational Identity Persistence. No existing engineering conclusions changed for Bus, Branch, Transformer, Load, or Generator Data. Added one short statement to §4.7 Correlation Philosophy reinforcing that Bus Number remains authoritative when correlating operational data across different Operational Snapshots (e.g. a Network Topology snapshot and a later Load-only snapshot). Added Engineering Principle 12 — Operational Identity Persistence (§9). Added one Open Question (§10) on the future engineering acceptance criteria for correlating Operational Topology and Load-only Operational Snapshots, including treatment of unmatched or inconsistent Bus Numbers. This amendment remains entirely at the engineering-philosophy level — it does not describe importer, database, parser, or UI behaviour. |
