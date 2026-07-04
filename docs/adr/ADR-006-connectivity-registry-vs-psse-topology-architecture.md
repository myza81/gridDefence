# ADR-006: Connectivity Registry vs. PSS/E Topology Architecture

- **Status:** Accepted
- **Date:** 2026-07-04
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1, §5.3, §5.5, §8, §11.2, §21, A1, A2, A5)
- **Depends on:** [ADR-000](ADR-000-architecture-principles.md), [ADR-001](ADR-001-modular-monolith-and-module-communication.md), [ADR-002](ADR-002-identity-and-access-management.md), [ADR-003](ADR-003-psse-topology-and-load-snapshot-separation.md)
- **Affects:** [docs/architecture/equipment-registry-module.md](../architecture/equipment-registry-module.md) §7.7 (ratifies and extends the already-anticipated `EquipmentTopologyMap` relationship), [docs/architecture/psse-integration-module.md](../architecture/psse-integration-module.md) §17, [docs/architecture/network-model-module.md](../architecture/network-model-module.md), [docs/architecture/domain-model.md](../architecture/domain-model.md) §4 (identifies and resolves a staleness gap — see Context), [docs/architecture/substation-registry.md](../architecture/substation-registry.md) §14, [docs/architecture/implementation-plan.md](../architecture/implementation-plan.md) (Phase 3/4/5 sequencing)
- **Informed by:** the engineering scenario supplied with this decision request (a UFLS assignment to named circuits PKLG–IGBK Line 1/Line 2, and the requirement to later determine which pocket load those circuits isolate); [equipment-registry-module.md](../architecture/equipment-registry-module.md) §7.7, which already anticipated most of this relationship from the Equipment Registry side; [ADR-003](ADR-003-psse-topology-and-load-snapshot-separation.md)'s established match-by-identifier, never-duplicate pattern for correlating imported data against Master Data.

---

## 1. Problem Statement

GridDefence's implementation plan anticipates two upcoming sources of network-connectivity-adjacent information:

- **A proposed "Substation Connectivity Registry"** — human-maintained, holding engineering metadata such as connectivity definitions, circuit information, bay numbers, breaker numbers, line type, and operational identifiers.
- **PSS/E RAW topology import** — system-generated, holding buses, branches, transformers, and the actual electrical graph, already architected in [ADR-003](ADR-003-psse-topology-and-load-snapshot-separation.md) and [psse-integration-module.md](../architecture/psse-integration-module.md).

If both exist as independently maintained models of "what connects to what," GridDefence risks two authoritative-looking answers to the same question, silent drift as the real network evolves, and ambiguity about which one a scheme module (UFLS/UVLS/EMLS), Network Model, or a future application should trust. This ADR must resolve:

1. **Should a separate Connectivity Registry exist at all**, or can its stated purpose be served by architecture GridDefence has already designed?
2. If some human-maintained registry is genuinely needed, **what exactly does it own**, and how does that ownership avoid overlapping both PSS/E's topology data and the already-designed Equipment Registry's scope?
3. **What is the reconciliation and change-management process** when the two models disagree about the network's structure over time?
4. **How does this interact with GridDefence's immutable-history requirements** for approved UFLS/UVLS/EMLS scheme versions?

This ADR does not merely arbitrate "Registry wins" vs. "PSS/E wins" vs. "both coexist" as three abstract options — it first tests whether the premise (a new registry) is the right frame at all, per the explicit instruction accompanying this request.

---

## 2. Business Context

**Grid Defence correctness.** UFLS/UVLS/EMLS assignments exist to shed load in a controlled, predictable way during frequency/voltage excursions. If the application's understanding of "which substations become isolated when circuit X opens" is wrong — because it was computed against stale or hand-maintained connectivity rather than the actual energized network — a defence scheme could fail to isolate the intended pocket, or isolate the wrong one. This is the highest-stakes correctness question this ADR touches.

**Engineering governance.** CLAUDE.md §5.1 (Single Source of Truth) and §8 (Domain Ownership) are not stylistic preferences here — they exist precisely to prevent the scenario this ADR was asked to resolve: two systems each claiming to describe the same physical fact, with no defined arbiter. Every module design in this codebase so far (Substation Registry, PSS/E Integration, Network Model, Equipment Registry) has followed the same discipline: exactly one owner per fact, everything else references it. This ADR must not become the first exception without a very strong reason.

**Network evolution.** Peninsular Malaysia's transmission network changes over years — new lines commissioned, substations renamed, circuits re-terminated. GridDefence must keep functioning correctly and traceably through that evolution: old scheme versions must remain interpretable against the network state they were approved against, and new scheme design must reflect the current network, not a stale one.

**Future applications beyond GridDefence.** The request explicitly notes that human-curated engineering metadata (bay numbers, breaker numbers, operational naming) may not exist in PSS/E at all — PSS/E's RAW format has no fields for these; it is a pure electrical model, not an asset/nameplate model. This is the one genuinely strong argument for *some* human-maintained metadata layer to exist, independent of whatever a specific PSS/E case file happens to contain, and independent of GridDefence's own scheme logic.

---

## 3. Architecture Goals

- **Preserve engineering metadata** that PSS/E cannot represent (bay/breaker numbers, operational naming) across repeated PSS/E re-imports, without it being silently wiped out.
- **Maintain electrical accuracy** — the actual, current, energized network topology must have exactly one authoritative source, derived from validated power-system data, not re-typed by hand.
- **Prevent accidental data loss** — neither a PSS/E re-import nor an engineering-metadata edit should silently destroy the other's data.
- **Support future applications** beyond GridDefence's own scheme logic — human-curated equipment/circuit identity should be usable independent of a live PSS/E case, since it is asset metadata, not electrical topology.
- **Support historical studies** — an approved UFLS/UVLS/EMLS scheme version must remain interpretable against the network state (both electrical and nomenclature) it was approved against, indefinitely, even as both models continue to evolve.
- **Support operational auditing** — every change to network-adjacent data, human-maintained or imported, must be traceable: who, when, why, what changed (CLAUDE.md §5.4).
- **Avoid unnecessary architectural surface area** — CLAUDE.md §21 and the explicit instruction accompanying this request both require testing whether a new module is actually justified before designing one.

---

## 4. Architectural Options

### Option A — Registry as Source of Truth

A human-maintained Connectivity Registry is authoritative for network connectivity; PSS/E import is either advisory or not relied upon for connectivity determination at all.

**Advantages:** Full engineer control and stable identifiers; no dependency on disciplined, frequent PSS/E re-import.

**Disadvantages:** Directly contradicts the engineering scenario in this request, which explicitly states that spur/pocket/island/radial/downstream-load identification **must** come from the imported PSS/E topology graph, not a manually maintained registry. It would require re-implementing graph/connectivity algorithms against hand-maintained data that already has a validated, higher-fidelity source — duplicating work [network-model-module.md](../architecture/network-model-module.md) already does correctly against PSS/E data. At real network scale (thousands of buses/branches — see [substation-registry.md](../architecture/substation-registry.md)'s own note on the ~5,000-record Phase 12 fixture), manually maintaining a parallel connectivity graph accurate enough to drive island detection is not credible to sustain. **Rejected.**

### Option B — PSS/E as Sole Source of Truth (attach metadata directly to topology objects, no separate registry)

No registry at all. Any needed human metadata (bay/breaker numbers, operational naming) is attached as optional fields directly on PSS/E Integration's own `TopologyBus`/`TopologyBranch`/`TopologyTransformer` rows.

**Advantages:** Single source of truth for everything; no reconciliation logic; minimal new infrastructure.

**Disadvantages — and this is the crux of the "should a registry exist at all" question:** [ADR-003](ADR-003-psse-topology-and-load-snapshot-separation.md) makes `TopologyVersion` and its structural children **immutable**, and a **new** `TopologyVersion` is created whenever *anything* structural changes anywhere in the network — including changes with no relationship whatsoever to the specific bay or breaker an engineer annotated. Metadata attached directly to a `TopologyBranch` row would need to be manually re-entered or re-associated on every new `TopologyVersion`, indefinitely, defeating the entire purpose of metadata meant to be stable and human-curated over years. This is not a stylistic objection — it follows mechanically from a decision already ratified in ADR-003. Additionally, PSS/E's per-unit electrical model does not always have 1:1 correspondence with physical bays/breakers (a substation may have several physical breakers represented by a single PSS/E bus, or switching elements PSS/E does not model at all) — there is no guarantee every piece of metadata GridDefence needs even has a PSS/E object to attach to. **Rejected as the sole mechanism**, but its core instinct — don't invent a second connectivity *graph* — is correct and is preserved in the recommendation below.

### Option C — Dual Source with Reconciliation (a new, general-purpose Connectivity Registry)

A new, independent Connectivity Registry module maintains its own connectivity graph (which substations connect to which, via which circuits), alongside PSS/E's topology, with an explicit reconciliation process for mismatches.

**Advantages:** Preserves stable human metadata without topology-churn problems (Option B's flaw); on the surface, matches how some utility EMS/SCADA architectures separate a "network model" from an "asset/nameplate database."

**Disadvantages:** This option, if it independently asserts *connectivity* (not just identity/metadata), directly re-creates the exact two-sources-of-truth problem this ADR exists to prevent — now with a formal reconciliation workflow bolted on to manage the drift, rather than a design that prevents the drift from being possible. It is also, on inspection, **largely redundant with architecture GridDefence has already ratified**: [equipment-registry-module.md](../architecture/equipment-registry-module.md) — a fully designed, approved module awaiting implementation as Phase 3 — already owns `IncomingBranchDetail` (`to_substation_id`, `ckt_id`, `breaker_number`), computed bay identifiers in the `{substation}_{to_substation}_{ckt_id}` shape (e.g. `PKLG_IGBK_1`, matching this request's own "PKLG–IGBK Line 1" example almost exactly), and alias/history tracking for identifier changes (§7.6). [psse-integration-module.md](../architecture/psse-integration-module.md) §17 and equipment-registry-module.md §7.7 have *already* anticipated and named the exact reconciliation mechanism this option would reinvent — a PSS/E-owned `EquipmentTopologyMap` that resolves imported topology elements to Equipment Registry's `equipment_id` by matching bay identifiers. Building a new, separate Connectivity Registry now would duplicate this already-approved design, violating CLAUDE.md §5.1 in the specific, concrete way it exists to prevent. **Rejected as a new module — its legitimate underlying need is already met by Option D.**

### Option D — No New Module: Reaffirm Equipment Registry as the Metadata Home, PSS/E as the Sole Topology Authority

Do not create a Connectivity Registry. The engineering-metadata need this request describes is served by the **already-approved** Equipment Registry module (specifically its `IncomingBranchDetail` entity for inter-substation circuits, and its `Equipment`/`bay_id`/`EquipmentAlias` backbone generally), correlated to PSS/E's electrical topology through the **already-anticipated** `EquipmentTopologyMap`, owned by PSS/E Integration. PSS/E topology remains the sole authority for actual electrical connectivity and the sole input to Network Model's island/pocket analysis; Equipment Registry remains the sole authority for stable, human-curated identity and physical metadata that PSS/E cannot represent.

**Advantages:** No new module, no duplicated responsibility, no new source of truth to keep synchronized against two others; reuses two already-ratified designs (Equipment Registry, ADR-003's match-by-identifier pattern) rather than inventing a third; the topology-churn problem that sank Option B does not apply, because Equipment Registry's own identity (`equipment_id`) is independent of any specific `TopologyVersion` — it is *matched against* each new topology on import, not embedded inside it.

**Disadvantages:** Requires a genuinely new decision this ADR must supply — equipment-registry-module.md and psse-integration-module.md named the `EquipmentTopologyMap` concept but did not fully specify its reconciliation/mismatch-handling behaviour (matched-but-conflicting endpoints, not just unmatched) or a network-change-management policy; this ADR must complete that specification (§8, §9 below) rather than simply cite the existing documents.

---

## 5. Recommended Architecture

**Option D.** No new Connectivity Registry is created. GridDefence already has the two modules this need requires — Equipment Registry (identity and physical metadata) and PSS/E Integration + Network Model (electrical topology and connectivity analysis) — and already has, in outline, the correlation mechanism between them. What was missing was not a third module; it was a small number of specific decisions about how that correlation behaves under real-world network change. This ADR supplies those decisions.

**Engineering justification.** The two "sources" this request worried about are not actually competing descriptions of the same fact. PSS/E answers "what is electrically connected, right now, as validated by power-system engineers" — a fact with exactly one correct answer at any point in time. Equipment Registry answers "what do we call this piece of equipment, and what do we know about it that the electrical model doesn't capture" — a fact about human nomenclature and physical wiring that is meaningful even when no PSS/E case currently represents it, and that must survive PSS/E re-import unchanged. These are genuinely different kinds of fact, owned by genuinely different modules, exactly as CLAUDE.md §8's domain-ownership model expects — not two overlapping opinions about the same graph.

**Trade-offs accepted.** This recommendation requires PSS/E Integration to actually build `EquipmentTopologyMap` (currently only a named Future Extension, not yet implemented) before a scheme module can cleanly go from "assign to circuit PKLG–IGBK Line 1" to "determine what that isolates" without an engineer manually cross-referencing bay identifiers by hand. This is accepted as necessary, sequenced work (§11), not a reason to build a redundant registry instead.

---

## 6. Source of Truth Responsibilities

**Connectivity Registry does not exist as a module.** Its stated purpose is split between two already-owned domains:

| Responsibility | Owner |
|---|---|
| Circuit/branch/transformer **identity**, naming, bay numbers, breaker numbers, alias/rename history | **Equipment Registry** (Master Data) |
| Which substation a piece of equipment belongs to, and (for inter-substation circuits) its declared far end | **Equipment Registry** (`IncomingBranchDetail.to_substation_id`) — declared, human-asserted metadata, not an electrical assertion (§7 below) |
| The actual, current, validated **electrical topology** — buses, branches, transformers, and how they are actually connected in the energized network | **PSS/E Integration** (`TopologyVersion` and its structural children, [ADR-003](ADR-003-psse-topology-and-load-snapshot-separation.md)) |
| **Connectivity analysis** — island/pocket/spur/radial/downstream-load determination | **Network Model**, computed exclusively from PSS/E Integration's data ([network-model-module.md](../architecture/network-model-module.md) §4, §9 rule 2) |
| The **correlation** between an Equipment Registry identity and the PSS/E topology element(s) it corresponds to in a given `TopologyVersion` | **PSS/E Integration**, via `EquipmentTopologyMap` (§8, §9 below) — referencing Equipment Registry's `equipment_id` read-only; Equipment Registry never holds a reverse reference |

No entity is owned twice. Equipment Registry never asserts electrical connectivity as fact (it asserts identity and a *declared* far end, which is metadata, not a topology claim — see §7). PSS/E Integration and Network Model never own bay numbers, breaker numbers, or any human-assigned circuit name.

---

## 7. Data Ownership

| Information | Owner | Notes |
|---|---|---|
| Connectivity identity (a circuit's stable identifier, e.g. `PKLG_IGBK_1`) | Equipment Registry | `Equipment.bay_id`, computed per the documented convention (equipment-registry-module.md §7.4) |
| Circuit identity (`ckt_id`) | Equipment Registry | `IncomingBranchDetail.ckt_id` |
| Bay numbers | Equipment Registry | `Equipment.bay_id` backbone |
| Breaker numbers | Equipment Registry | `IncomingBranchDetail.breaker_number`, `*TransformerDetail.hv_breaker_number`/`lv_breaker_number` |
| Voltage level | **Substation Registry**, for the substation itself (`voltage_level_id`); PSS/E Integration, for a topology bus's modeled base kV | Two different facts sharing a name — a substation's nominal voltage class is Master Data; a specific bus's per-unit base kV is topology data. Neither module duplicates the other's value. |
| Line type (equipment type: incoming branch vs. transformer) | Equipment Registry | `Equipment.equipment_type` discriminator |
| **Electrical topology** (which buses/branches/transformers actually exist and how they connect, right now) | PSS/E Integration | `TopologyVersion` and structural children — the sole authority |
| Bus relationships, branch relationships (electrical) | PSS/E Integration | Structural topology data |
| Spur identification, pocket identification, island detection | **Network Model** | Computed exclusively from PSS/E Integration's data; never from Equipment Registry (network-model-module.md §4, §9 rule 2) — Equipment Registry has no connectivity-analysis capability and must never grow one |
| The **declared** far-end substation of a named circuit (`to_substation_id`) | Equipment Registry | Human-asserted engineering metadata — **not** treated as an electrical fact on its own; it must be correlated against PSS/E's actual topology (§8) before Network Model relies on it for any analysis |
| The **correlation** of a named circuit to its actual PSS/E branch/transformer element(s) | PSS/E Integration (`EquipmentTopologyMap`) | Read-only reference to Equipment Registry's `equipment_id`; recomputed/re-matched on every import, never stored by Equipment Registry |

---

## 8. Network Change Management

Using the request's own example: Equipment Registry holds a circuit `ABBA_NUNI_1` (declared far end: NUNI). A later PSS/E RAW import's structural data, once correlated, implies the physically corresponding element now runs `ABBA–KULN` instead.

The response is governed by one rule: **Equipment Registry is never automatically rewritten by a PSS/E import, under any circumstance.** PSS/E Integration's import process only ever creates `RawFileImportBatch`, `TopologyVersion`, and `LoadSnapshot` rows (ADR-003) and attempts to *match*, never to *write into*, Equipment Registry — mirroring the existing, ratified rule that PSS/E import never auto-creates or auto-modifies Substation Registry records (ADR-003, Business Rule 10; equipment-registry-module.md §9 rule 10 makes the equivalent guarantee from Equipment Registry's side).

Three concrete outcomes follow from applying `EquipmentTopologyMap`'s bay-identifier matching (equipment-registry-module.md §7.7, §7.8) to a new import:

1. **Clean match, consistent endpoints.** The imported branch's electrical endpoints agree with Equipment Registry's declared `to_substation_id`. No action needed; the correlation is recorded silently as part of the batch's normal processing.
2. **No match found.** No PSS/E element resolves against `ABBA_NUNI_1`'s current bay identifier *or* its alias history (equipment-registry-module.md §7.6, §7.8). This is reported as an **unmatched-equipment warning** on the `RawFileImportBatch`, exactly mirroring the existing unmatched-bus/unmatched-mnemonic pattern already established in PSS/E Integration's import process ([psse-integration-module.md](../architecture/psse-integration-module.md) §5) — surfaced for engineer review, never silently dropped, never blocking the rest of the import.
3. **Matched, but endpoints conflict** (a bay identifier still resolves — directly or via alias history — but the electrically-implied far end no longer agrees with Equipment Registry's declared `to_substation_id`, e.g. `ABBA_NUNI_1` now electrically terminates at KULN). This is the case the request's example actually describes, and is the one genuinely new decision this ADR adds beyond what equipment-registry-module.md already specified: it is reported as a **discrepancy**, a second, distinct category from "unmatched," on the same `RawFileImportBatch`. A discrepancy **never triggers an automatic write** to Equipment Registry. It requires an authenticated, authorized engineer to explicitly resolve it as one of:
   - **Accept as a genuine network change** — the engineer updates Equipment Registry's `to_substation_id` through Equipment Registry's own service layer (a normal, audited edit, per equipment-registry-module.md §9 rule 11), which produces its own `EquipmentAlias`-adjacent record of the change; the PSS/E import itself never performs this write.
   - **Reject as a data/import error** — the discrepancy is acknowledged and closed without changing Equipment Registry; the batch's record of the discrepancy remains as a permanent, queryable part of that import's audit trail regardless of which way it was resolved.

Updates are therefore **never automatic**, **always manual** (a named, authenticated engineering decision), and **always audited** — on both sides: PSS/E Integration's own audit log records the discrepancy and its detection (ADR-003 §Audit Requirements), and, if accepted, Equipment Registry's own audit log records the resulting metadata change (equipment-registry-module.md §14) as an ordinary, independently-attributable edit.

---

## 9. Reconciliation Strategy

Reconciliation is a **matching problem with a mandatory human decision on conflict**, not a merge algorithm, and not new infrastructure beyond what §8 just described:

- **Matching** is performed by `EquipmentTopologyMap` (PSS/E Integration, owned per equipment-registry-module.md §7.7), keyed on Equipment Registry's bay identifiers — current value first, then historical `EquipmentAlias` entries (equipment-registry-module.md §7.8) — against the newly imported `TopologyVersion`'s structural elements. This is the same identifier-matching discipline ADR-003 already established for correlating PSS/E buses to Substation Registry records; this ADR applies it a second time, to a second Master Data entity, rather than inventing a new mechanism.
- **Mismatch detection** produces exactly two outcomes, both attached to the triggering `RawFileImportBatch`: *unmatched* (no candidate found at all) and *discrepancy* (a candidate found, but its implied electrical relationship conflicts with Equipment Registry's declared metadata) — §8.
- **Engineer review** is mandatory for both outcomes before any downstream consequence (Network Model recommendation, scheme-module equipment-level assignment) can be considered fully reliable for that equipment. An unresolved discrepancy does not block the PSS/E import itself from being activated (ADR-003's own activation gate governs that, independently) — it blocks confidence in *that specific piece of equipment's* correlation only, surfaced wherever that correlation is subsequently used.
- **Acceptance** updates Equipment Registry through its own service layer, by its own audited process (§8) — never as a side effect of the PSS/E import transaction.
- **Rejection** leaves Equipment Registry unchanged and closes the discrepancy as reviewed-and-declined, permanently visible in that import batch's history.

No implementation detail (schema, API, algorithm) is specified here, per this ADR's scope — only the required behaviour.

---

## 10. Historical Studies

A completed, Approved or Active UFLS/UVLS/EMLS scheme version continues to reference the specific `equipment_id`(s) it was assigned against (once the equipment-level migration described in equipment-registry-module.md §7.8 is executed under its own dedicated ADR) — a stable, immutable UUID, per CLAUDE.md A5. **Historical scheme versions continue referencing historical connectivity; they never automatically migrate.**

This falls out of decisions already ratified elsewhere, applied consistently:

- `equipment_id` never changes once assigned (equipment-registry-module.md §9 rule 2 — `equipment_type` is immutable; the identity itself is never reassigned).
- A metadata edit to Equipment Registry (accepting a §8 discrepancy, e.g. correcting `to_substation_id`) changes what is *currently true* about that equipment; it does not retroactively alter what a past scheme version's own captured, approved data said at the time it was approved (CLAUDE.md §5.2, Immutable Engineering History) — exactly the same guarantee ADR-003 already established for PSS/E `LoadSnapshot` changes never retroactively altering approved MW figures, and network-model-module.md already established for `IslandAnalysisResult` recomputation never altering an already-captured scheme assignment.
- If an engineer wants to know "what did we believe about this equipment's connectivity when scheme version 3 was approved," that question is answered by Equipment Registry's own audit log (equipment-registry-module.md §14) and `EquipmentAlias` history (§7.6), correlated against the timestamp of that scheme version's approval — the same point-in-time reconstruction pattern substation-registry.md §11 already describes for Substation Registry's own audit log.

No automatic migration of historical scheme data is introduced by this ADR, and none should be — a scheme version's engineering validity is a statement about the network as understood at approval time; silently rewriting it to reflect a later-discovered discrepancy would be a correctness violation, not an improvement.

---

## 11. Impact on Future Modules

- **Phase 3 — Substation Connectivity Registry, as separately proposed:** superseded by this decision. No such module should be built. Equipment Registry, already fully designed, is the correct target for Phase 3, unchanged by this ADR in its own right (§6, §7).
- **Phase 4 — PSS/E Topology Import:** unchanged in its already-ratified design (ADR-003); this ADR adds the discrepancy-handling behaviour of §8 to `EquipmentTopologyMap`'s eventual implementation, which was already scoped as a Future Extension of this module (psse-integration-module.md §17).
- **Phase 5 — Load Import:** unaffected — load import is already fully specified as part of PSS/E Integration's `LoadSnapshot` workflow (ADR-003); this ADR does not introduce a separate load-import concern.
- **UFLS/UVLS/EMLS:** once equipment-level assignment is migrated to (equipment-registry-module.md §7.8, itself gated behind its own required ADR), a scheme module can assign to a named circuit (`equipment_id`) and, via `EquipmentTopologyMap` and Network Model's `analyzeIsland`, obtain a recommended isolated-substation set and MW for it — directly closing the gap in the request's own engineering example (PKLG–IGBK Line 1/2 → downstream IGBK/NKST pocket). This ADR does not itself authorize that migration; it only confirms the data-ownership shape it will rely on.
- **Cross-Scheme Compliance:** unaffected directly; benefits indirectly from this ADR's insistence that connectivity has exactly one authoritative source, since compliance checks that reason about network state must not inherit ambiguity from having two.
- **Dashboard:** should visualize connectivity from PSS/E Integration/Network Model's data (already the design in network-model-module.md §17), and may separately display Equipment Registry's identity/nomenclature metadata as labels — it must never compute or infer connectivity itself (CLAUDE.md A12), and this ADR gives it no new reason to.
- **Future engineering applications beyond GridDefence:** served by Equipment Registry's already-stated design intent (equipment-registry-module.md §1: scoped for grid system operators generally, not GridDefence-specific) — this ADR does not change that, and explicitly avoids narrowing Equipment Registry's applicability by keeping it free of any GridDefence-scheme-specific concept (equipment-registry-module.md §4, §9 rule 9, unchanged here).

---

## 12. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| `EquipmentTopologyMap` (§8, §9) is still only a named Future Extension, not yet implemented — this ADR's recommendation is not fully realized until it is built | Scheme modules cannot yet cleanly go from a named circuit to a computed pocket; manual cross-referencing remains necessary in the interim | Sequence `EquipmentTopologyMap` explicitly in the implementation plan (§13) rather than leaving it an open-ended "future extension" |
| A discrepancy (§8, outcome 3) is left unresolved for a long period, with engineers working around it manually | Recommendations/assignments referencing that equipment silently rely on stale or ambiguous correlation | Surface unresolved discrepancies prominently wherever that equipment's correlation is subsequently consulted (Dashboard, scheme-module assignment UI), not only at import time |
| Bay-identifier matching (§9) fails to resolve a genuinely-renamed circuit because its rename was not recorded via `EquipmentAlias` at the time | False "unmatched" result, requiring manual reconciliation that a well-maintained alias history would have avoided | Reinforce, as already stated in equipment-registry-module.md §14, that bay ID changes are audited "with particular emphasis" given exactly this downstream reconciliation dependency |
| Someone proposes reviving a standalone "Connectivity Registry" later, having forgotten this ADR's analysis | Reintroduces the duplicated-source-of-truth problem this ADR exists to prevent | This ADR is the durable record of why that path was rejected (§4, Option C) — any future proposal to reintroduce it must explicitly address why Option D (§5) is no longer sufficient, not silently re-propose Option C |
| Equipment Registry's `IncomingBranchDetail` model does not represent intra-substation (bus-section/busbar-level) switching topology — only inter-substation branches | A future requirement for full single-line-diagram-level detail inside a substation would not be served by today's Equipment Registry design | Out of scope for this ADR (not needed by the engineering scenario that motivated it); flagged as an Open Question (§14) rather than silently assumed away |
| Cross-module correlation logic (bay-identifier matching, discrepancy detection) becomes a second, informally-duplicated implementation if built inside PSS/E Integration without care, given it must query Equipment Registry's service interface repeatedly during import | Performance/complexity risk during large RAW file imports | Not a new risk introduced here — the same class of concern ADR-003 already accepted for Substation Registry matching; no additional mitigation beyond what that ADR already assumes (batch-level warning aggregation, not per-record blocking) |

---

## 13. Decision

**No Substation Connectivity Registry module is created.** GridDefence's existing, ratified architecture — Equipment Registry for identity and physical/nomenclature metadata (Master Data), PSS/E Integration for electrical topology (Network Data), and Network Model for connectivity analysis derived exclusively from PSS/E data — already provides everything this need requires, and provides it without duplicating any fact across two owners. This ADR:

1. Confirms Equipment Registry (Phase 3, already fully designed in [equipment-registry-module.md](../architecture/equipment-registry-module.md)) as the sole owner of circuit/bay/breaker identity and naming, including inter-substation circuits via `IncomingBranchDetail`.
2. Confirms PSS/E Integration ([psse-integration-module.md](../architecture/psse-integration-module.md), [ADR-003](ADR-003-psse-topology-and-load-snapshot-separation.md)) as the sole owner of actual electrical topology, and directs it to implement `EquipmentTopologyMap` (already named as a Future Extension) as real, sequenced work, not an indefinitely-deferred idea.
3. Confirms Network Model ([network-model-module.md](../architecture/network-model-module.md)) as the sole owner of connectivity analysis (spur/pocket/island/radial/downstream-load determination), computed exclusively from PSS/E Integration's data — never from Equipment Registry, which has no connectivity-analysis capability and must never acquire one.
4. Specifies the previously-unspecified behaviour required to make that relationship correct under real network change: `EquipmentTopologyMap` matching must distinguish *unmatched* from *discrepancy* (§8), and any discrepancy requires an explicit, authenticated, audited engineering decision — never an automatic write in either direction.
5. Confirms that this design satisfies GridDefence's historical-study requirement structurally (§10), by the same immutable-identity, capture-not-live-dependency pattern already proven for MW (ADR-003) and island analysis (network-model-module.md).

**Why this over Option C:** because Option C's legitimate underlying need — stable, human-curated metadata that survives topology churn — is already met by architecture GridDefence had already approved before this ADR was requested. Proposing a new module to solve an already-solved problem would itself violate the single-source-of-truth discipline this whole decision exists to protect.

---

## 14. Open Questions

1. What is the exact severity/blocking policy for an unresolved `EquipmentTopologyMap` discrepancy — does it merely warn wherever that equipment is subsequently used (§12), or should it actively block a scheme module from assigning to that equipment until resolved? (Mirrors ADR-003 Open Question 3's still-unresolved reviewer/approver-role question, now recurring here.)
2. Does `EquipmentTopologyMap` warrant its own dedicated reviewer/approver role, distinct from general PSS/E import activation and from Equipment Registry's own write permissions, given it sits at the intersection of two modules' authorization models?
3. Equipment Registry's current design (§12) does not model intra-substation, bus-section-level switching topology. Is single-line-diagram-level detail inside a substation a real, near-term GridDefence requirement, or safely deferred indefinitely? If real, it needs its own architecture discussion — not a retrofit of this ADR's conclusions.
4. Should a discrepancy's resolution (§8, §9) itself be a permission-gated, "Editor"-tier action (mirroring equipment-registry-module.md §15), or does it warrant the same elevated tier already recommended for Cross-Scheme Compliance's rule configuration, given it can silently affect every scheme module's downstream connectivity assumptions if handled carelessly?
5. Once real PSS/E case files and real Equipment Registry data exist, what is the expected steady-state rate of discrepancies? This should inform whether §8's manual-review-per-discrepancy model remains proportionate at scale, or whether a batched/summary review UX becomes necessary — deferred until real volume is observed, consistent with CLAUDE.md A15's pattern for retention/scale questions elsewhere in this series.
6. [domain-model.md](../architecture/domain-model.md) §4 ("Network Model Domain") still describes its future scope in terms of an owned "connectivity record — e.g. a transmission line entity referencing a substation at each end," predating [ADR-003](ADR-003-psse-topology-and-load-snapshot-separation.md)'s later decision that Network Model owns no topology data of its own. This ADR's conclusion (§13) is consistent with ADR-003's later, more specific decision, not with domain-model.md §4's earlier phrasing — domain-model.md should be updated to reflect this in a future documentation pass, but that edit is not made by this ADR itself (ADRs record decisions; domain-model.md's own maintainers should reconcile the wording).

---

## Recommended Next Architecture Document

**`EquipmentTopologyMap` design**, as a focused addition to [psse-integration-module.md](../architecture/psse-integration-module.md) (or a short standalone ADR, if its discrepancy-handling model proves to need more ratification than a module-document update warrants) — this ADR has made the load-bearing ownership and behavioural decisions; the next step is specifying the mapping entity's own conceptual shape (mirroring the level of detail equipment-registry-module.md and network-model-module.md already established for their own owned entities), sequenced to land before Equipment Registry (Phase 3) and PSS/E Integration (Phase 4) implementation reaches the point of needing it.

**Equipment-level scheme assignment migration ADR** (equipment-registry-module.md §7.8) remains the other clearly-flagged prerequisite for UFLS/UVLS/EMLS to actually consume this ADR's design end-to-end (§11) — independent of this ADR's own scope, already queued by equipment-registry-module.md's own recommendation.
