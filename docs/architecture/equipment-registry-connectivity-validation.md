# Equipment Registry — Connectivity Validation

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This is an **architecture validation document**, not a module document (CLAUDE.md A8) and not an ADR — it tests a prior decision against concrete engineering workflows and records findings. It does not itself change any architecture document.

Related documents: [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md), [equipment-registry-module.md](equipment-registry-module.md), [psse-integration-module.md](psse-integration-module.md), [network-model-module.md](network-model-module.md), [substation-registry.md](substation-registry.md), [domain-model.md](domain-model.md), [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md).

---

## Executive Summary

**ADR-006's top-level conclusion holds up under scrutiny, but its supporting design does not, as currently documented.** No new module is required — Equipment Registry remains the correct owner of circuit/bay/breaker identity, and PSS/E Integration + Network Model remain the correct owners of electrical topology and connectivity analysis. That part of ADR-006 is reaffirmed, not walked back.

However, `IncomingBranchDetail` as specified in [equipment-registry-module.md](equipment-registry-module.md) §7.4 has three concrete structural gaps that would prevent it from actually satisfying the workflows this validation tested:

1. **One `breaker_number` field per circuit**, when breaker numbers are terminal-specific — a circuit between two substations has two independently-numbered breakers, not one.
2. **One `to_substation_id` field**, modeling every circuit as strictly two-terminal and asymmetrically "owned" by whichever substation happens to hold the row — this cannot represent a tee-off/multi-terminal line, and bakes in exactly the directional framing §7's "directionality concern" flags as risky.
3. **No first-class circuit/line identity independent of a single terminal's row** — two engineers editing "the same" circuit from each substation's side today have no structural link between their two records, only a hoped-for match on `ckt_id` text.

None of these gaps require a new module, a new source of truth, or reversing ADR-006's ownership decision. They require refining Equipment Registry's *internal* domain model — specifically, introducing a lightweight `Circuit` entity and reframing `IncomingBranchDetail` into a per-terminal record (tentatively `CircuitTerminalDetail`) — before Phase 3 implementation begins. This document is not itself that refinement; it is the validation record establishing that the refinement is needed, and what it must contain (§ Recommended Refinements, § Final Architecture Recommendation).

Voltage level and line-type support, the interconnector case, and the discrepancy-handling model from ADR-006 all check out as sound, with one small addition (a `line_type` reference table) and one confirmation (interconnectors need no new modeling at all, given data GridDefence already seeded in Phase 1).

---

## Reviewed Documents

- [ADR-006: Connectivity Registry vs. PSS/E Topology Architecture](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md)
- [equipment-registry-module.md](equipment-registry-module.md)
- [psse-integration-module.md](psse-integration-module.md)
- [network-model-module.md](network-model-module.md)
- [substation-registry.md](substation-registry.md) — the task referenced `substation-registry-module.md`; the actual file is `substation-registry.md` (the one module document in this series without a `-module` suffix in its filename — noted here, not corrected, per this task's instruction not to modify existing docs)
- [domain-model.md](domain-model.md)
- [ADR-003: PSS/E Topology and Load Snapshot Separation](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md)
- `backend/app/reference_data/seed.py` (implementation, consulted to confirm what reference data — voltage levels, grid owner categories — already exists, rather than assuming)

---

## Key Findings

1. **ADR-006's ownership decision is correct and is reaffirmed.** Equipment Registry (identity/metadata), PSS/E Integration (electrical topology), and Network Model (connectivity analysis) remain the right three owners. No evidence gathered in this validation supports reviving a separate Connectivity Registry module.
2. **`IncomingBranchDetail`'s shape does not survive contact with real terminal-level detail.** It was designed (correctly, for its time) around the legacy MVP's own `IncomingBranch` field set (equipment-registry-module.md §7.4 says so explicitly), which itself only ever recorded one breaker number and one far-end reference per row. This validation's scenarios show that shape does not hold once bay numbers and breaker numbers are examined as genuinely terminal-specific, and once multi-terminal (tee-off) circuits are considered.
3. **The directionality concern (workflow 7) is real, not merely a naming complaint.** The problem is not that "Incoming Branch" sounds directional — it is that the underlying schema *is* directional (one substation "owns" the row; the other is a passive `to_substation_id` value with no row, no breaker number, and no independent identity of its own).
4. **Voltage level support requires no new architecture.** `voltage_level` reference data already contains exactly the four values needed (500/275/230/132kV, confirmed in `backend/app/reference_data/seed.py`) and is already designed for reuse by any module via foreign key (substation-registry.md §4; equipment-registry-module.md §6 already reuses `operational_status_id` from the same reference-table pattern). A circuit-level `voltage_level_id` is a new *usage* of existing infrastructure, not new infrastructure.
5. **Line type is a genuine, small gap** — no existing entity records overhead/cable/submarine/hybrid construction type anywhere. This is a one-table reference-data addition (mirroring `voltage_level`'s own pattern), not a new module or a new domain concern.
6. **Interconnectors need no new modeling at all.** `grid_owner` reference data already includes a `Tie-Line` category (seeded since Phase 1, confirmed in `backend/app/reference_data/seed.py`) — the architecture already anticipated cross-border/tie connections at the Substation Registry level. An interconnector is an ordinary circuit whose far-end substation happens to be a minimal, `Tie-Line`-owned Substation Registry record.
7. **ADR-006's discrepancy-handling model (never auto-write, mandatory engineer review, both sides audited) remains sound** under the refined per-terminal model — it applies more cleanly once matching happens per-terminal rather than per-circuit-as-a-whole, and needs no reconsideration of its core rule.

---

## Workflow Walkthroughs

### 1. PKLG–IGBK Double Circuit Spur

**As currently documented**, PKLG–IGBK Line 1 and Line 2 would each become one `Equipment` row of type `IncomingBranch`, "living" at one arbitrarily-chosen endpoint (say PKLG), with `IncomingBranchDetail.to_substation_id = IGBK`, `ckt_id = "1"` / `"2"`, and computed `bay_id`s `PKLG_IGBK_1` / `PKLG_IGBK_2` (equipment-registry-module.md §7.4). This much **works** for the two-line-count itself — two distinct `ckt_id` values cleanly produce two distinct `Equipment` rows.

**Where it breaks down:**
- `breaker_number` is a single field on that one row. It can only hold *one* substation's breaker identifier for that circuit. IGBK's own breaker for the same physical line has nowhere to live unless IGBK is given an entirely separate, independently-created `Equipment` row (`IGBK_PKLG_1`) — and nothing in the current design links that row back to `PKLG_IGBK_1` as "the same physical circuit." Two engineers, working independently at each substation, could easily end up with `ckt_id` values that don't textually match (`"1"` vs `"01"` vs `"L1"`), silently breaking even the implicit, name-based correlation.
- UFLS would reference whichever `equipment_id` was created (per equipment-registry-module.md §7.8's planned migration path) — that part is fine, since `equipment_id` is stable regardless of naming. The gap is entirely on the *modeling* side, not the *referencing* side.
- `EquipmentTopologyMap` (per ADR-006 §8–§9) would match `PKLG_IGBK_1`'s bay identifier against the current `TopologyVersion` and resolve it to a PSS/E branch. This part of the design holds regardless of the terminal-modeling gap — it just needs to be applied per-terminal once the refinement below lands, matching each terminal's bay identifier to its own end of the corresponding PSS/E branch.
- Master data duplication is correctly avoided today: `Equipment.substation_id` and `IncomingBranchDetail.to_substation_id` both reference `Substation.substation_id` by foreign key only, never copying substation attributes (equipment-registry-module.md §7, consistent with CLAUDE.md §5.1). This holds under the refinement too.

**Verdict:** the *identity* half of this workflow (two named circuits, two `equipment_id`s) works today. The *terminal detail* half (each substation's own breaker number, and a structural link between the two ends) does not, and needs the refinement in § Recommended Refinements.

### 2. Multi Tee-Off Visibility (ABBA–NUNI / SMRK / NLAI)

**Equipment Registry cannot, and should not, answer "show me the whole corridor" itself.** This is the same boundary ADR-006 already drew for Network Model (§4, §9 rule 2 of network-model-module.md: connectivity analysis is never Equipment Registry's job) — a corridor spanning multiple substations and multiple circuit segments is a *graph traversal* question, which belongs to Network Model, reasoning over PSS/E's actual electrical topology (via `getConnectivityGraph`, already designed in network-model-module.md §13), with Equipment Registry's names used only for display labels.

What Equipment Registry **should** support, and today only partially does:

- "If I am viewing SMRK, can I see SMRK's own bays/circuits?" — **yes, already supported**, via the already-designed "read-only equipment-by-substation listing interface" (equipment-registry-module.md §13), once each substation genuinely has its own terminal-level rows (§ gap above).
- A true three-way (or more) tee-off, structurally, **cannot** be expressed by `IncomingBranchDetail` today — its `to_substation_id` field is singular. Even setting aside the breaker-number gap, a tee point with three legitimate terminal substations has no way to be recorded as one coherent circuit; it would have to be force-fit into two or three separate, uncorrelated two-terminal rows.
- Line 1/Line 2/Line 3-style bay numbering (workflow 3's naming) works fine as a per-terminal string field, once terminals are modeled correctly (§ gap above) — this is not itself a new problem, it inherits directly from the breaker-number/terminal gap.

**Verdict:** genuine, structural gap. Equipment Registry needs a way to express "this circuit has N terminals," not just "this circuit has exactly one other end." Corridor-level *visibility* across multiple circuits remains, correctly, Network Model's responsibility, not Equipment Registry's.

### 3. Bay Number vs. Breaker Number

The task's clarification is precise and matches real substation engineering practice: bay number ("Line 1," "Line 2") is a circuit/position designation; breaker number ("L25," "805," "Z1230") is a physical device identifier, and it is unambiguously **terminal-specific** — each substation names its own breakers independently, often under a different local convention than the substation at the other end.

**Current model:** `IncomingBranchDetail` already keeps `ckt_id`/`bay_id` and `breaker_number` as genuinely separate fields (equipment-registry-module.md §7.4, §11) — this part of the design is already correct in principle. The flaw is cardinality, not conflation: there is one of each per row, and one row per circuit (not per terminal), so only one substation's breaker number can ever be recorded.

Whether bay number is "circuit-specific or terminal-specific" is, on inspection, the same question as breaker number: in practice both are properly **terminal-specific** — a bay number is assigned by, and meaningful within, one substation's own numbering scheme, and there is no guarantee (or requirement) that both ends of a circuit share the same bay label.

**Recommended modelling approach** (detailed in § Recommended Refinements): one row per terminal, each with its own bay identifier and its own breaker number, both terminal-scoped by construction rather than by convention.

### 4. Voltage Level and Line Type

- **Voltage level (132/230/275/500kV):** fully supported by existing Core Platform reference data — `voltage_level` already contains exactly these four values (confirmed in `backend/app/reference_data/seed.py`), and the reuse pattern (a new module referencing an existing reference table by foreign key, never duplicating it) is already established and already used by Equipment Registry itself for `operational_status_id` (equipment-registry-module.md §6). A circuit needs its own `voltage_level_id` — distinct from, but structurally identical in kind to, `Substation.voltage_level_id` — because a substation with multiple voltage classes present (e.g. a 275/132kV station) cannot have every one of its bays correctly described by a single substation-level value.
- **Line type (overhead/cable/submarine/hybrid):** not modeled anywhere today. This belongs in Equipment Registry (it describes a specific piece of equipment's physical construction, not a substation-level or PSS/E-level fact) and should follow the exact same lightweight reference-table pattern as `voltage_level` (CLAUDE.md §11.3 — reference tables over hardcoded enums, so new construction types can be added without a schema migration).

**Verdict:** voltage level needs no new architecture, only a new foreign key on the circuit-level entity introduced by the refinement. Line type needs one small, conventional reference table plus the same foreign key treatment — a natural, low-risk addition to Equipment Registry's existing design pattern.

### 5. Interconnector Case

Peninsular Malaysia's cross-border interconnectors do not require a new module, a new equipment type, or deferral. `grid_owner` reference data already has a `Tie-Line` category (`TIE_LINE`, seeded since Phase 1). An interconnector is structurally an ordinary circuit (once the refinement in § Recommended Refinements lands) whose far-end terminal happens to reference a minimal Substation Registry record representing the border/tie point, owned under `grid_owner = Tie-Line`. No special-cased handling is needed at the circuit level beyond, optionally, a lightweight `is_interconnector` flag for reporting/dashboard convenience.

**Recommendation: a metadata flag**, not a connection category requiring its own taxonomy, not a new equipment type, and not deferred — the structural support already exists in data GridDefence seeded during Phase 1, before this question was ever asked.

### 6. Registry vs. PSS/E Topology Discrepancy

ADR-006 §8–§9 already specified this in detail and this validation finds no reason to revise its core rule: **neither side ever automatically overwrites the other.** Restated against the refined per-terminal model:

- **Detection:** `EquipmentTopologyMap` (PSS/E Integration, per ADR-006 §8) attempts to match each `CircuitTerminalDetail`'s bay identifier — current value, then historical alias entries — against the newly imported `TopologyVersion`. Three outcomes: clean match, unmatched (no candidate), or **discrepancy** (a candidate is found, but the electrically-implied far end conflicts with the terminal's declared circuit membership).
- **PSS/E does not overwrite the registry; the registry does not overwrite PSS/E.** Both remain independently correct in their own domain (electrical fact vs. declared metadata) until a human reconciles a discrepancy.
- **Engineer review** is mandatory before a discrepancy is closed, resulting in one of exactly two audited outcomes: accept as a genuine network change (update Equipment Registry through its own service layer) or reject as a data/import error (Equipment Registry unchanged, the discrepancy record itself retained permanently).
- **Discrepancy status model** (naming refined here, behaviour unchanged from ADR-006): `Detected → (Accepted | Rejected)`, append-only, mirroring the same lightweight status-tracking pattern already used elsewhere in this series (`RawFileImportBatch`'s `Completed`/`CompletedWithWarnings`/`Failed` in PSS/E Integration; `ManualOverride`'s `Active`/`Superseded` in Network Model) rather than inventing a new lifecycle shape.
- **Historical UFLS/UVLS/EMLS studies remain interpretable** because scheme versions reference an immutable `equipment_id`, never a mutable name — accepting a discrepancy changes what is *currently* true about a terminal's declared far end; it does not, and structurally cannot, retroactively alter what an already-approved scheme version's captured data said (CLAUDE.md §5.2), exactly the same guarantee already proven for MW (ADR-003) and island analysis (network-model-module.md).

**Verdict:** sound as designed in ADR-006; carries over cleanly to the refined per-terminal model with no change to its core rule.

### 7. Directionality Concern

Confirmed as a real conceptual **and structural** risk, not only a naming one. "Incoming Branch" implies a receiving/downstream perspective that does not exist in physical reality — a transmission line has no inherent direction, and the current schema's asymmetry (one substation gets a row; the other gets only a foreign key value) is a symptom of, not the cause of, the terminal-modeling gaps found in workflows 1–3.

Of the options offered:
- *Retained as-is* — rejected; does not satisfy the tested workflows.
- *Wrapped with a view/query layer* — rejected as sufficient on its own; a friendlier read API cannot fix a write model that structurally cannot hold two substations' independent breaker numbers or more than one far-end terminal. The underlying data would still be wrong or incomplete no matter how it is queried.
- **Generalized, and renamed to match** — recommended. Generalizing to a per-terminal, N-terminal-capable model (§ Recommended Refinements) resolves the structural gaps in workflows 1–3 simultaneously; renaming away from "Incoming Branch" to a direction-neutral term (e.g. `CircuitTerminalDetail`) is then not cosmetic but an accurate description of what the generalized entity actually holds.
- *Replaced* — rejected; nothing here warrants abandoning Equipment Registry's ownership or its `Equipment` backbone pattern (§7.1's common-identity design remains correct and unaffected) — only its `IncomingBranchDetail` specialization needs to change shape.

---

## Gaps

| # | Gap | Severity | Affects workflow(s) |
|---|---|---|---|
| 1 | `breaker_number` is a single field per circuit row; breaker numbers are terminal-specific | High — blocks accurate double-circuit and tee-off modelling | 1, 2, 3 |
| 2 | `to_substation_id` is singular — only two-terminal circuits are representable | High — blocks tee-off/multi-terminal modelling entirely | 1, 2 |
| 3 | No first-class circuit/line identity independent of one terminal's row — the "same circuit" link between two substations' records is implicit (string-matched `ckt_id`), not FK-enforced | Medium-High — silent drift risk, violates CLAUDE.md §11.2's foreign-key-enforced-relationships expectation | 1, 2, 6 |
| 4 | No `line_type` (overhead/cable/submarine/hybrid) anywhere in the current design | Low — additive, well-understood fix | 4 |
| 5 | `EquipmentTopologyMap` (ADR-006) is still only a named Future Extension, not yet fully specified against the refined per-terminal shape | Medium — sequencing risk, not a design flaw | 1, 6 |
| 6 | "Incoming Branch" naming actively signals the wrong (directional) mental model, compounding gaps 1–2 rather than merely mislabeling them | Medium — conceptual/communication risk that follows from, and should be fixed alongside, gaps 1–2 | 7 |

No gap found requires reversing ADR-006's module-ownership decision (§6/§7 of that ADR). Every gap here is a refinement *within* Equipment Registry's already-correct ownership boundary.

---

## Recommended Refinements

These are architectural refinements to Equipment Registry's domain model, described conceptually — no schema, migration, or code is specified here, consistent with this task's scope.

1. **Introduce a `Circuit` entity** (naming placeholder — final name to be settled when equipment-registry-module.md is actually revised) as a new entity owned by Equipment Registry, representing a physical circuit/line as a whole, independent of any one terminal:
   - Stable identity (`circuit_id`), independent of `equipment_id` — a circuit is a distinct concept from any one terminal's equipment record.
   - `voltage_level_id` (FK to Core Platform reference data — already exists, §4 above).
   - `line_type_id` (FK to a new, small `line_type` reference table — overhead/cable/submarine/hybrid, §4 above).
   - `is_interconnector` (boolean, §5 above) for reporting convenience only — not load-bearing for any structural rule.
   - Lifecycle/status, commissioning date, remarks — following the same conventions already established for `Equipment` itself (equipment-registry-module.md §8, §11).
   - A `Circuit` has **two or more** terminals (see next point) — an ordinary point-to-point line has exactly two; a tee-off has three or more, modeled uniformly by the same entity, with no special-cased "third terminal" mechanism.

2. **Generalize and rename `IncomingBranchDetail` to a per-terminal entity** (placeholder name: `CircuitTerminalDetail`):
   - One row per **substation per terminal** of a `Circuit` — not one row per circuit.
   - References the owning `Circuit` (`circuit_id`) and, via the existing `Equipment` backbone, the substation this specific terminal lives at (`Equipment.substation_id`, unchanged in meaning — no longer implicitly "the near end," just "this terminal's home").
   - Carries this terminal's own bay identifier (renamed from `ckt_id`/computed `bay_id` convention, now scoped per-terminal) and this terminal's own `breaker_number` — resolving gaps 1 and 6 directly.
   - A `Circuit` with exactly two `CircuitTerminalDetail` rows behaves exactly as `IncomingBranchDetail` does today for ordinary two-terminal lines (workflow 1) — this is a strict generalization, not a breaking redesign of the common case.
   - A `Circuit` with three or more `CircuitTerminalDetail` rows now correctly represents a tee-off (workflow 2) using the same entity shape, with no additional mechanism.

3. **Add a `line_type` reference table** (Core Platform-style lookup, per CLAUDE.md §11.3): `Overhead`, `Cable`, `Submarine`, `Hybrid` — extensible without a schema migration, exactly like `voltage_level`/`region`/`grid_owner` today.

4. **Extend `EquipmentTopologyMap`'s (still-unbuilt) design to match per-terminal**, not per-circuit: each `CircuitTerminalDetail`'s bay identifier is matched independently against the `TopologyVersion` at its own substation, producing independent match/unmatched/discrepancy outcomes per terminal (ADR-006 §8's model applies unchanged, just at the correct granularity).

5. **No change is needed to `Equipment`'s common backbone** (§7.1 of equipment-registry-module.md), to the relay model (§7.5), to transformer details (§7.2–§7.3), to Network Model, to PSS/E Integration's `TopologyVersion`/`LoadSnapshot` design, or to ADR-006's ownership conclusions (§6, §7, §13) or its discrepancy-handling rule (§8, §9) — this refinement is scoped narrowly to the circuit/branch representation.

---

## Final Architecture Recommendation

**A. Is a separate Substation Connectivity Registry required?** No. This validation found no workflow, including the tee-off and directionality cases specifically raised as concerns, that requires a new module or a new source of truth. ADR-006's core conclusion stands.

**B. Is the existing Equipment Registry sufficient as-is?** No — not as currently documented. `IncomingBranchDetail`'s single-breaker-number, single-far-end, no-independent-circuit-identity shape cannot represent terminal-specific breaker numbers or multi-terminal circuits, both of which are real, near-term requirements demonstrated by the workflows tested here.

**C. What exact changes are required?** The five refinements in § Recommended Refinements: a new `Circuit` entity; generalizing `IncomingBranchDetail` into a per-terminal `CircuitTerminalDetail`-style entity; a new `line_type` reference table; extending the (still-unbuilt) `EquipmentTopologyMap` to match per-terminal; no other changes.

**D. Should `IncomingBranchDetail` be renamed or generalized?** Both, and the two are linked — generalize first (to a per-terminal, N-terminal-capable shape), and rename to match what it then actually represents (a direction-neutral term such as `CircuitTerminalDetail`, not a cosmetic rename of the current, still-directional shape).

**E. What entities/fields are required to satisfy the workflows?** `Circuit` (circuit-level identity, voltage level, line type, interconnector flag, lifecycle) and `CircuitTerminalDetail` (per-terminal bay identifier and breaker number, one row per substation per terminal) — see § Recommended Refinements for the full field-level reasoning. No other new entities are required by any tested workflow.

**F. What should remain owned by the PSS/E topology graph?** Everything ADR-006 already assigned it: the actual, current, validated electrical topology (`TopologyVersion` and its structural children) and, via Network Model, all connectivity analysis (spur/pocket/island/radial/downstream-load determination, and corridor/multi-hop visibility per workflow 2). Nothing found in this validation shifts any of this toward Equipment Registry.

**G. What should remain owned by Equipment Registry?** Everything ADR-006 already assigned it, now refined: circuit/terminal identity, bay numbers, breaker numbers (correctly terminal-scoped), line type, and — reused from existing Core Platform reference data, not owned but correctly referenced — voltage level. Equipment Registry still performs no connectivity analysis of its own, per ADR-006's boundary, unchanged by this validation.

**H. What implementation phase should these refinements belong to?** Phase 3 (Equipment Registry), before implementation begins — not a later patch. `IncomingBranchDetail` does not yet exist as code (only as architecture); refining its shape now costs a documentation update and a design conversation. Refining it after Phase 3 ships would cost a schema migration touching live data and any scheme-module references already made to the old shape. `EquipmentTopologyMap`'s per-terminal matching design (refinement 4) belongs to Phase 4 (PSS/E Integration), sequenced to consume Phase 3's corrected shape — consistent with ADR-006's own recommended next step.

---

## Open Questions

1. What should the `Circuit`/`CircuitTerminalDetail` entities actually be named once equipment-registry-module.md is formally revised? This document uses placeholder names deliberately, since naming is a module-document-authoring decision, not a validation finding.
2. Should a two-terminal `Circuit` retain any convenience/denormalized "primary far-end" accessor for simple display purposes, or should all consumers always resolve terminals via the `Circuit` → `CircuitTerminalDetail` relationship uniformly, even for the common two-terminal case? A denormalized shortcut risks reintroducing a subtle asymmetry the refinement is meant to remove.
3. For a tee-off, is the physical tap point itself always a real, addressable substation (as assumed throughout this validation), or does GridDefence need to represent a tap point that is not itself a Substation Registry entity (a pole-mounted tee with no associated substation)? If the latter is real, it needs its own follow-up — not assumed away by this validation.
4. Should `line_type` support being unknown/unspecified for legacy circuits with no recorded construction type, and if so, is `NULL` sufficient or does the reference table need an explicit "Unknown" row (mirroring how other reference tables in this series have handled similar gaps)?
5. Does the `is_interconnector` flag need any special handling in future Cross-Scheme Compliance or Critical Infrastructure work (e.g. a tie-line's load characteristics being treated differently from a domestic circuit), or is it purely a reporting/display convenience as assessed here? Out of scope for this validation, flagged for whoever designs those modules' next refinement.
6. This validation, like ADR-006 before it, did not touch [domain-model.md](domain-model.md) §4's still-stale "Network Model Domain" description (predating ADR-003's later, more specific decision) — that documentation gap remains open and unaddressed by either document.
7. Should the refinements recommended here be folded directly into a revision of [equipment-registry-module.md](equipment-registry-module.md), or does the terminal-modeling change (specifically, introducing a genuinely new `Circuit` entity that did not exist in any prior version of that document) warrant its own short ADR before that revision, given CLAUDE.md A13's threshold for "modifies core architecture, domain ownership... or database standards"? This validation does not resolve that procedural question — it is the first decision required before any document is actually changed.
