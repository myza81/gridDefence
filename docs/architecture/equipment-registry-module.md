# Equipment Registry Module Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document follows the Canonical Module Architecture Document Template (CLAUDE.md **A8**).

**This is the single implementation specification for Phase 3.** It incorporates every accepted decision from [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md) (module ownership) and [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md) (canonical reference object) directly into the sections below. A developer or coding agent implementing Phase 3 should not need to read either ADR or the connectivity validation document to know what to build — they exist as historical rationale for *why* this document says what it says, not as additional requirements layered on top of it. Where this document's current text differs from an earlier draft of it, or from the connectivity validation's tentative proposals, see the **Superseded Design Decisions** appendix at the end of this document.

Related documents: [domain-model.md](domain-model.md), [substation-registry.md](substation-registry.md) (§14, which first reserved this module), [psse-integration-module.md](psse-integration-module.md) (§17, which anticipated the same linkage from its own side), [ufls-module.md](ufls-module.md) §7.4 (Open Questions 1–2, which this document resolves the second half of), [uvls-module.md](uvls-module.md), [emls-module.md](emls-module.md), [ADR-000](../adr/ADR-000-architecture-principles.md) through [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md), [ADR-006: Connectivity Registry vs. PSS/E Topology Architecture](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md), [ADR-007: Canonical Engineering Reference Object](../adr/ADR-007-canonical-engineering-reference-object.md), [ADR-008: Substation Voltage Yard as the CircuitTerminal Connection Point](../adr/ADR-008-substation-voltage-yard.md), [equipment-registry-connectivity-validation.md](equipment-registry-connectivity-validation.md) (the gap analysis that motivated this revision).

**Phase 3 UAT addendum (ADR-008):** `CircuitTerminal` connects to a `SubstationVoltageYard`, not directly to a `Substation` — a multi-voltage substation (e.g. PKLG with both a 275kV yard and a 132kV yard) cannot be expressed by a single `substation_id` reference alone. See §7.5a and ADR-008 for the full decision. Every other section of this document that says "terminal's substation" now means "terminal's voltage yard's substation," reached by one additional join.

**Phase 3 close-out — final UAT-validated model.** §7.4 and §7.6 state the current, authoritative `bay_number`/circuit-name semantics. Some illustrative examples elsewhere in this document (§7.9, §7.11, §7.13, §19, the Appendix) still show the earlier "Line 1"/"Line 2" convention and a circuit name with the bay number appended (e.g. "PKLG–IGBK Line 1") — these are historical illustrations, left as originally written per this document's practice of correcting the authoritative text directly while noting supersession rather than rewriting every narrative example. Read any such example as: bay number is now a short designator (`1`, `Main`), and the circuit name never includes it. See the "Phase 3 Final Model Summary" section immediately below for the current, consolidated picture, and the Appendix for the itemized list of what changed and why.

**Phase 3.5 addendum — Transformer Registry.** Equipment Registry now also owns `Transformer`/`TransformerTerminal`/`transformer_audit_log`, added between Equipment Registry (Phase 3) and PSS/E Topology Import (Phase 4) specifically because a transformer is a fundamental topology element defining connectivity between two voltage levels — PSS/E import needs a Master Data anchor for it, exactly as it already has one for `Circuit`/`CircuitTerminal`. See the **"Phase 3.5 Addendum: Transformer Registry"** section immediately after the Phase 3 Final Model Summary below for the complete specification (domain model, business rules, generated short-name convention, uniqueness rule, API, testing). Tertiary windings, transformer impedance, tap-changer modelling, transformer loading, and protection-relay modelling remain explicitly out of scope, deferred to future phases. **The uniqueness rule and breaker-number convention stated in that section were both corrected post-acceptance — see the numbering-model pointer below; read that pointer before trusting either one.**

**Phase 3 follow-up — Engineering Connectivity.** UAT clarified that Transformer Registry (above) answers *asset ownership* ("which transformers are installed at this substation") while Circuit Registry answers *engineering connectivity* ("which circuits are connected to this substation") — genuinely different questions. `Circuit` does **not** gain a `substation_id` column; it remains modeled through `CircuitTerminal` since a circuit connects two or more substations. See the **"Phase 3 Follow-up: Engineering Connectivity (Substation Detail Page)"** section (immediately after the Transformer Registry addendum below) for the full record, including the explicit architectural note distinguishing this manually-maintained engineering baseline from PSS/E's future operational topology snapshot.

**Phase 3 follow-up — Deletion/Correction Policy.** UAT found that switchyards, circuit terminals, circuits, and transformers created by mistake could never be corrected — this module still never hard-deletes (CLAUDE.md §11.6), so a new `ENTERED_IN_ERROR` operational status was added, hidden from default list views but always reachable via an explicit toggle or a record's own detail page. `CircuitTerminal` correction is never blocked, even below the two-terminal minimum — that completeness rule is instead enforced only when a circuit tries to (re)enter `Active`. `TransformerTerminal` gains no independent correction path; a mistaken transformer is corrected as a whole. See the **"Phase 3 Follow-up: Deletion/Correction Policy"** section (immediately after the Engineering Connectivity follow-up below) for the full record.

**Transformer Registry UAT correction #2 — Numbering Model.** UAT found that `UNIQUE(substation_id, transformer_number)` (the substation-ownership correction above) was too coarse: real Malaysian grid practice numbers transformer bays *per transformation pair*, not per substation as a whole — a substation legitimately has a "Transformer Bay 1" on its 275/132kV pair *and a separate* "Transformer Bay 1" on its 132/33kV pair, which that constraint wrongly rejected. Uniqueness reverts to `(substation_id, hv_switchyard_id, lv_switchyard_id, transformer_number)`, enforced at the service layer, not as a raw database constraint. The breaker-number suggestion convention was also corrected to a mapping keyed by (HV nominal kV, LV nominal kV, side) — voltage alone was not enough to determine the right formula. See the **"Phase 3.5 Addendum: Transformer Registry"** section's Business Rules 5 and 7 (both revised in place, with supersession noted) and [ADR-008](../adr/ADR-008-substation-voltage-yard.md)'s "UAT Correction #2 (Numbering Model)" addendum for the full record.

**Transformer breaker-numbering convention moved to reference data.** The (HV nominal kV, LV nominal kV, side)-keyed mapping introduced by UAT correction #2 (above) was itself hardcoded in a frontend TypeScript file (`transformerBreakerSuggestion.ts`). It has since been moved into a new Core Platform reference table, `transformer_breaker_numbering_convention` (`app/reference_data/`, seeded and served alongside `voltage_level`/`line_type`/etc.), keyed by real `voltage_level` FKs rather than raw nominal-kV numbers. This is an implementation/maintainability change only — the convention's actual values, and its suggestion-only, never-backend-enforced nature (Business Rule 7), are unchanged. See Business Rule 7 and the Database Design table in the **"Phase 3.5 Addendum: Transformer Registry"** section below for the corrected shape.

---

## Phase 3 Final Model Summary (UAT-Validated)

This section consolidates the model as validated through Phase 3 UAT, for a reader who wants the current picture without tracing every ADR and addendum individually. It does not introduce anything not already decided in §7 and the ADRs referenced below — it is a summary, not a new decision.

### Conceptual hierarchy

```
Substation                                  (Substation Registry — Master Data)
    ├── Voltage Yard / Switchyard            (Equipment Registry; ADR-008)
    │       ├── voltage level
    │       ├── commissioning date            (optional; Phase 3 UAT follow-up)
    │       ├── latitude / longitude          (optional, both-or-neither; Phase 3 UAT follow-up)
    │       └── circuit terminals             (0..N CircuitTerminal rows)
    └── (identity, geography, ownership, operational status — unchanged, ADR-009)

Circuit                                      (Equipment Registry — canonical reference object; ADR-007)
    ├── canonical route/name                  (computed: sorted terminal mnemonics, never bay_number)
    ├── bay / circuit number                  (short designator: "1", "Main" — never a route description)
    ├── voltage level                         (single value; every terminal's yard must match it — rule 6a)
    ├── line type
    └── terminals (2..N)                      (each terminal → exactly one voltage yard/switchyard)
```

Busbars, bus couplers, breakers-as-first-class-entities, disconnectors, transformers, reactors, capacitors, and a generalized `Equipment` backbone are **future scope**, not part of Phase 3 (§4, §17). `CircuitTerminal` sits directly on its own identity rather than a shared `Equipment` backbone for exactly this reason (§7.1's scope note) — introducing that backbone is deferred until a second equipment type actually needs it.

### Terminal voltage-level guardrail (rule 6a)

Every `CircuitTerminal`'s voltage yard/switchyard must share its parent `Circuit`'s own `voltage_level_id` — a circuit is one physical line at one voltage class; a terminal at a different voltage level would represent a transformer connection, which this phase does not model (§9 rule 6a, added Phase 3 close-out). Enforced at the service layer on both circuit creation and terminal addition, not only in the UI — a mismatched voltage yard submitted directly to the API is rejected with a human-readable error. See ADR-008's addendum for how this interacts with rule 6's own scoping.

### Master-data ownership principle (ADR-009)

Master data entities are created and managed only within their owning module; dependent modules may reference them but must not create or modify them inline without a compelling, separately-documented exception. Concretely: voltage yard/switchyard creation and editing happen exclusively on the Substation Detail page; Circuit pages only ever consume existing voltage yards for terminal selection. This generalizes to every future topology entity (busbars, transformers, etc.) — see ADR-009's addendum for the full principle and reasoning.

### `Substation.voltage_level_id` deprecation (ADR-009)

`Substation.voltage_level_id` is deprecated, not removed: the column remains in the database (nullable, no data destroyed) but is out of the API contract entirely. A substation's voltage level(s) are represented exclusively by its `SubstationVoltageYard` (switchyard) rows — zero, one, or several. Substation creation no longer asks for a voltage level.

### Canonical circuit naming rule (Phase 3 close-out)

The circuit name is computed, never stored, and is the terminal substation mnemonics only — sorted alphabetically (case-insensitive), never the terminal-entry order, and never with `bay_number` appended. This makes the name deterministic regardless of which terminal an engineer happened to enter first, and keeps it visually distinct from the separately-displayed bay/circuit number (§7.4, §7.6). No PSS/E or other engineering naming convention is introduced by this rule — it is UI/domain display naming only, and may be revisited once a real convention is documented.

### `bay_number` semantics (Phase 3 close-out)

`bay_number` is a bay/circuit *designator*, not a display label: `1`, `2`, `Main`, `Transfer` — not `Line 1`, `Line 2`. It remains free text (not restricted to numeric-only), since real bay designators are frequently non-numeric. It is never embedded in the computed circuit name (see above), so a list or detail view showing both the circuit name and the bay number never displays the same number twice.

---

## Phase 3.5 Addendum: Transformer Registry

This section is a self-contained specification for the Transformer Registry, added as Phase 3.5 — after Equipment Registry (Phase 3) completed UAT, before PSS/E Topology Import (Phase 4). It follows the same architecture-first process as Phase 3: an Architecture Decision Gate was run before implementation, presenting the three genuine modelling ambiguities below as options with a recommendation, and implementation began only after explicit approval. It does not restate or duplicate the Circuit/CircuitTerminal sections above; it adds a sibling entity family alongside them, owned by this same module.

**UAT correction #1 (post-implementation, before acceptance):** UAT found that the initial design exposed only two switchyards on creation, with no first-class substation context — a transformer could not be discovered "from a substation's own perspective," and nothing prevented a transformer's HV and LV switchyards from belonging to two different substations. In the Malaysian transmission/distribution domain, **a transformer is substation-owned equipment and is never modeled as spanning two substations.** `Transformer.substation_id` was added as a mandatory, first-class column; both terminals' switchyards must resolve to this same substation (service-layer check); creation is now substation-first in the UI; and the uniqueness rule (Decision 3 below) was revised from a switchyard-pair key to `UNIQUE(substation_id, transformer_number)` — see the corrected Business Rules, Database Design, and API Contract below, and the ADR-008 addendum recording this correction.

**UAT correction #2 (post-acceptance):** UAT found `UNIQUE(substation_id, transformer_number)` above too coarse — it collapses every transformation level at a substation into one shared bay-number namespace, but real Malaysian grid practice numbers transformer bays *per transformation pair*. Uniqueness (Decision 3, revised a second time) reverts to `(substation_id, hv_switchyard_id, lv_switchyard_id, transformer_number)`, enforced at the service layer, not a raw database constraint. The breaker-number suggestion convention (Business Rule 7) was also corrected to a mapping keyed by (HV nominal kV, LV nominal kV, side), replacing the previous per-voltage table. `Transformer.substation_id` itself (UAT correction #1 above) is unaffected. See the ADR-008 addendum ("UAT Correction #2 (Numbering Model)") for the full record.

### Conceptual hierarchy

```
Substation                                  (Substation Registry — Master Data)
    ├── Switchyard (SubstationVoltageYard)   (Equipment Registry; ADR-008)
    └── Transformer                         (Equipment Registry; Phase 3.5 — substation-owned, UAT correction)
            └── TransformerTerminal (HV, LV) (each references one of this substation's own switchyards)
```

A `Transformer` belongs to exactly one substation (`Transformer.substation_id`) and connects exactly two of that substation's own `SubstationVoltageYard` rows — one HV, one LV (e.g. a substation's own 275kV yard stepping down to its own 132kV yard). **A transformer spanning two different substations is not a legal configuration** (UAT correction above). **Tertiary windings, transformer impedance, tap-changer modelling, transformer loading, and protection-relay modelling are explicitly out of scope** for this phase, deferred to future phases exactly as busbars, bus couplers, and a generalized `Equipment` backbone already are for Circuit (see the Phase 3 Final Model Summary above).

### Architecture Decision Gate — decisions made and their rationale

Three genuine modelling ambiguities were identified before implementation began. Per this phase's process (mirroring Phase 3's own gate), each was presented with options and a recommendation, and implementation did not proceed until the Project Owner explicitly approved all three:

**Decision 1 — `TransformerTerminal` rows vs. direct `hv_*`/`lv_*` columns on `Transformer`.** Two options were considered: (A) `Transformer` holds `hv_switchyard_id`/`hv_breaker_number`/`lv_switchyard_id`/`lv_breaker_number` directly as columns; (B) `Transformer` owns two `TransformerTerminal` child rows, each with `side` (`HV`/`LV`), `voltage_yard_id`, and `breaker_number` — structurally mirroring `CircuitTerminal`'s own precedent exactly. **Option B was approved.** Rationale: `side` is a CHECK-constrained string, not a hardcoded pair of columns, so a future tertiary-winding phase can add a third `side` value via a constraint change alone, with zero migration to `Transformer` itself — the same forward-compatibility reasoning that already justifies `CircuitTerminal`'s own shape for tee-off circuits (§7.5, §7.13). Rejecting Option A avoids baking a two-winding assumption directly into the `Transformer` table's own column set.

**Decision 2 — should the generated engineering short name (e.g. `SGT1`) be stored on `Transformer` or computed at read time?** **Computed at read time was approved**, for the identical reason `Circuit`'s own canonical name is computed, not stored (§7.4): "storing it separately would create a second place it could drift out of sync" — here, out of sync with the HV terminal's voltage level or the transformer number, either of which can change after creation. It is derived from the HV terminal's voltage level (via the TNB prefix convention below) and `Transformer.transformer_number`, and is exposed on every read response (list and detail) but never accepted on a create/update request.

**Decision 3 — the transformer uniqueness rule.** `UNIQUE (hv_switchyard_id, lv_switchyard_id, transformer_number)` was originally approved, enforced at the service layer. **Superseded by UAT correction #1, then re-superseded by UAT correction #2 (both above).** UAT correction #1 collapsed the key to `UNIQUE(substation_id, transformer_number)` once `substation_id` became a mandatory column, trading the original cross-row check for a real database constraint. UAT correction #2 found that key too coarse — it wrongly conflated every transformation pair at a substation into one shared bay-number namespace, rejecting the legitimate case of the same bay number appearing once per transformation pair. **The uniqueness key is now `(substation_id, hv_switchyard_id, lv_switchyard_id, transformer_number)`, back to a service-layer, cross-row check** (an aliased double join on `TransformerTerminal`, mirroring the original design), because `hv_switchyard_id`/`lv_switchyard_id` live on the two child `TransformerTerminal` rows, not on `Transformer` itself — denormalizing them onto `Transformer` to regain a single-table constraint was considered and rejected (it would reintroduce the exact two-winding-only assumption Decision 1 avoided baking into `Transformer`'s own column set). **This uniqueness key still represents the physical transformer's own identity, distinct from the generated engineering short name (e.g. `SGT1`), which remains a separate, computed, user-facing label derived from the HV voltage level and transformer number.** Two physically distinct transformers may legitimately share the same computed short name (e.g. two transformers both computing to `SGT1`, one at PKLG and one at IGBK, or even two at the same substation on different transformation pairs) without violating uniqueness, because uniqueness is keyed on physical identity, not on the display label derived from voltage level.

### Transformer identity and the generated short name

Users never type the engineering short name directly — they enter only the **Bay / Transformer Number** (e.g. `1`, `2`, `3`, `Main`), mirroring `Circuit.bay_number`'s own free-text, non-numeric-only convention (§7.4, §7.6). The short name is computed from the HV terminal's voltage level using the following TNB convention:

| HV side voltage | Prefix | Example (Transformer No. 1) |
|---|---|---|
| 500kV | `XGT` | `XGT1` |
| 275kV | `SGT` | `SGT1` |
| 230kV | `SGT` | `SGT1` |
| 132kV | `T` | `T1` |
| 33kV | `T` | `T1` |
| 22kV | `T` | `T1` |
| 11kV | `T` | `T1` |

E.g. a 500/275kV Transformer No. 1 computes to `XGT1`; a 275/132kV No. 1 to `SGT1`; a 132/33kV No. 1 to `T1`. Any HV voltage level not in this table falls back to the `T` prefix — a display convenience, never a validation gate; the transformer may still be created. The generated short name is presented read-only everywhere it appears; only the transformer number is ever editable.

### Domain Model

```
Transformer (1) ──── (2) TransformerTerminal   [exactly one HV, one LV — enforced at creation, not editable after]

Transformer          ──── references ───▶ Substation.substation_id               (Master Data, external; UAT correction)
TransformerTerminal ──── references ───▶ SubstationVoltageYard.voltage_yard_id   (this module, existing entity; must resolve to the parent Transformer's own substation_id)
Transformer          ──── references ───▶ OperationalStatus                      (Core Platform, external)
Transformer / TransformerTerminal ──── references ───▶ User.user_id              (Core Platform/IAM, external)
```

`Transformer` carries: `transformer_id` (UUID PK), `substation_id` (FK to Substation Registry, external, mandatory — UAT correction: a transformer is substation-owned equipment), `transformer_number`, `capacity_mva` (optional), `commissioning_date` (optional), `operational_status_id` (FK, external), `transformer_type` (optional, free text — no reference table introduced, since no fixed vocabulary was specified and CLAUDE.md discourages inventing one), `manufacturer` (optional, free text), `remarks` (optional), plus standard audit columns (`created_at`/`updated_at`/`created_by_user_id`/`updated_by_user_id`).

`TransformerTerminal` carries: `transformer_terminal_id` (UUID PK), `transformer_id` (FK to `Transformer`), `side` (`HV` or `LV`, CHECK-constrained), `voltage_yard_id` (FK to `SubstationVoltageYard`), `breaker_number`, plus audit columns — breaker number is editable after creation, mirroring `CircuitTerminal`'s own post-creation editability (§7.5, ADR-008).

`transformer_audit_log` owns this entity family's own audit trail (CLAUDE.md A4), structurally identical to `equipment_registry_audit_log`.

### Business Rules

1. **A transformer must have exactly two terminals: one HV, one LV.** Enforced at creation; `side` uniqueness is additionally enforced per `transformer_id` at the database level (`UNIQUE (transformer_id, side)`).
2. **The HV terminal's voltage level must be strictly higher than the LV terminal's voltage level.** A reversed or equal pairing (e.g. 132kV declared HV against a 275kV LV, or two terminals at the same voltage level) is rejected with a human-readable error naming both voltage levels.
3. **HV and LV terminals must connect to two different switchyards.** A transformer cannot have both terminals at the same `SubstationVoltageYard` — it must step between two genuinely different voltage-level connection points.
4. **HV and LV terminals must both belong to the transformer's own substation.** A transformer is substation-owned equipment (UAT correction) — a substation's own 275kV yard stepping down to its own 132kV yard is the legitimate, common case; **a transformer physically spanning two different substations is not modeled and is rejected.** Enforced at the service layer on creation: each terminal's `SubstationVoltageYard.substation_id` must equal `Transformer.substation_id`, or the specific mismatching side and both substation mnemonics are named in the rejection.
5. **Uniqueness: `(substation_id, hv_switchyard_id, lv_switchyard_id, transformer_number)`**, representing physical transformer identity (Architecture Decision Gate, Decision 3, as superseded twice — see UAT corrections #1 and #2 above) — enforced at the service layer (an aliased double join on `TransformerTerminal`), not a raw database constraint, since the two switchyard ids are not columns on `transformer` itself. A transformer number (e.g. "1", "TX1") is locally meaningful within one substation-and-transformation-pair only; the same number may legitimately exist at a different substation, or at the same substation on a different HV/LV pair (e.g. a "1" on the 275/132kV pair and a separate "1" on the 132/33kV pair). Parallel transformers on the same pair are supported by using different transformer numbers.
6. **A transformer's switchyards are immutable after creation.** Only the transformer number, both breaker numbers, and the non-structural metadata fields (capacity, commissioning date, status, type, manufacturer, remarks) may be edited afterward — changing which switchyards a transformer connects would change its physical identity, which this phase treats as a new transformer, not an edit (consistent with Master Data's immutable-identity principle applied elsewhere in this module, §7.1).
7. **Breaker-number suggestions are a display-only convenience, never enforced by the backend — and the convention itself is now Core Platform reference data, not hardcoded frontend logic.** UAT correction #2 (above) first corrected the convention to a mapping keyed by (HV nominal kV, LV nominal kV, side) — voltage alone does not determine the right formula, since the same nominal voltage requires a different formula depending on which side of which transformation pair it is (e.g. 132kV is `{N}10` as the HV side of a 132/33, 132/22, or 132/11kV transformer, but `{N}80` as the LV side of a 275/132kV transformer). A follow-up correction then moved that mapping out of a hardcoded TypeScript table (`transformerBreakerSuggestion.ts`) into a new reference table, `transformer_breaker_numbering_convention`, keyed by `(hv_voltage_level_id, lv_voltage_level_id, side)` — real `voltage_level` FKs, not raw text — so a new transformation pair, or a corrected pattern, is a seed-data change, not a frontend code change (CLAUDE.md §11.3: reference tables preferred over hardcoded application constants). See this section's Database Design table below for the full column shape:

   | Transformation pair | HV side | LV side |
   |---|---|---|
   | 500/275kV | non-standard, no suggestion | `T{N}0` |
   | 275/132kV | `H{N}0` | `{N}80` |
   | 132/33kV | `{N}10` | `{N}T0` |
   | 132/22kV | `{N}10` | `{N}T0` |
   | 132/11kV | `{N}10` | `3{N}` |

   Any transformation pair outside this table (e.g. one involving 230kV) has no matching row — an intentional scope limit matching what was specified, not an inferred extrapolation; the frontend shows no suggestion and the field remains freely editable. `{N}` in a `pattern` value is replaced by the frontend with the transformer/bay number. The user may freely overwrite any suggestion, and the backend never validates a breaker number's format or content against this convention (or at all) — mirroring `CircuitTerminal.breaker_number`'s own no-cross-substation-uniqueness, no-format-validation precedent (§9 rule 6, Validation Rules §10). This remains true regardless of where the convention data lives: moving it to the database changed *where the suggestion comes from*, not *whether it is enforced* — it is still suggestion-only.
8. This module has no knowledge of "schemes," "stages," or "shedding assignments" for transformers, identically to Circuit (§9 rule 10) — unaffected by this addendum.
9. Every create, update on `Transformer`/`TransformerTerminal` requires an authenticated, named IAM user and is audited (§14) — unaffected in kind by this addendum, only in owned entity set.

### Validation Rules

- `substation_id` must reference an existing Substation Registry record (UAT correction).
- `hv_switchyard_id`/`lv_switchyard_id` must reference existing `SubstationVoltageYard` rows, and each must belong to the selected `substation_id` (Business Rule 4) — checked before the same-switchyard and voltage-order checks below, so a cross-substation mismatch is reported precisely (naming the offending side and both substation mnemonics), not conflated with a same-switchyard or voltage-order error.
- `operational_status_id` must reference a valid Core Platform reference row; a transformer's initial status on creation is restricted to `Planned` or `Active`, mirroring Circuit's own creation-time rule (§8).
- `capacity_mva`, if provided, must be strictly positive (database `CHECK` constraint).
- The HV/LV voltage-order and same-switchyard rules (Business Rules 2–3 above) are enforced at the service layer on creation, using `SubstationVoltageYard.voltage_level_id` → `VoltageLevel.nominal_kv` for the comparison. (An "equal HV/LV voltage level via two distinct switchyards" scenario is not separately constructible once Business Rule 4 is in force — a substation holds at most one switchyard per voltage level, so two same-substation, same-level switchyards would necessarily be the same row, already covered by the same-switchyard rule.)
- The uniqueness rule (Business Rule 5) is enforced entirely at the service layer (no raw database constraint — see UAT correction #2 above), on both create and update, as a pre-insert/pre-update check (mirroring `DuplicateVoltageYardError`'s own precedent) that produces a human-readable rejection naming the substation, rather than a raw constraint-violation error.
- No validation rule requires or restricts the format of `breaker_number` — the backend never rejects a custom breaker number regardless of voltage level (Business Rule 7).

### Database Design (Concept)

| Table (conceptual) | Key columns (conceptual) | Notes |
|---|---|---|
| `transformer` | `transformer_id` (UUID PK), `substation_id` (FK to `substation`, external, `ON DELETE RESTRICT`, mandatory — UAT correction #1), `transformer_number`, `capacity_mva` (nullable, `CHECK > 0`), `commissioning_date` (nullable), `operational_status_id` (FK, external, `ON DELETE RESTRICT`), `transformer_type` (nullable, free text), `manufacturer` (nullable, free text), `remarks` (nullable), audit columns. No `UNIQUE` constraint (UAT correction #2 dropped `uq_transformer_substation_number` — migration `0010_transformer_yard_pair`). | New (Phase 3.5). Generated short name is never a column — computed at read time (Decision 2 above). Uniqueness is enforced at the service layer, scoped to `(substation_id, hv_switchyard_id, lv_switchyard_id, transformer_number)` — see UAT correction #2. |
| `transformer_terminal` | `transformer_terminal_id` (UUID PK), `transformer_id` (FK to `transformer`, `ON DELETE RESTRICT`), `side` (`CHECK IN ('HV','LV')`), `voltage_yard_id` (FK to `substation_voltage_yard`, `ON DELETE RESTRICT`), `breaker_number`, audit columns. `UNIQUE (transformer_id, side)`. | New (Phase 3.5). Exactly two rows per `transformer_id` once creation completes. |
| `transformer_audit_log` | `log_id` (BIGINT PK), `transformer_id` (FK), `field_name`, `old_value`, `new_value`, `changed_at`, `changed_by_user_id`, `change_reason` | New (Phase 3.5). Owned per CLAUDE.md A4, structurally identical to `equipment_registry_audit_log`. |
| `transformer_breaker_numbering_convention` | `convention_id` (surrogate PK, `SMALLINT` on PostgreSQL — CLAUDE.md A5), `hv_voltage_level_id` (FK to `voltage_level`, `ON DELETE RESTRICT`), `lv_voltage_level_id` (FK to `voltage_level`, `ON DELETE RESTRICT`), `side` (`CHECK IN ('HV','LV')`), `pattern` (nullable — `NULL` means no automatic suggestion), `is_standard` (boolean), `notes` (nullable). `UNIQUE (hv_voltage_level_id, lv_voltage_level_id, side)`. | New — Core Platform reference data (`app/reference_data/`, not owned by this module), added by the breaker-numbering-convention-as-reference-data correction. Seeded by `app/reference_data/seed.py`, idempotent and backfill-safe like every other reference table (see `test_seed_backfills_transformer_breaker_numbering_conventions`). No `created_at`/`updated_at` — consistent with `VoltageLevel`/`Region`/`State`/`GridOwner`/`OperationalStatus`/`LineType`, none of which have them either. |

**Reference data addition:** 33kV, 22kV, and 11kV were added to the `voltage_level` Core Platform reference table (previously only 500/275/230/132kV existed) — the LV-side distribution voltage classes the short-name prefix table and breaker-suggestion formulas above name explicitly. `transformer_breaker_numbering_convention` (above) is a second, later reference-data addition specific to the breaker-suggestion convention itself.

### API Contract (Concept)

- `GET /api/v1/transformers` — list, filterable by `substation_id` (UAT correction — answers "which transformers are installed at this substation"), `operational_status_id`, and free-text `search` (transformer number or substation mnemonic/name); paginated.
- `POST /api/v1/transformers` — create; requires `substation_id` (UAT correction, mandatory) plus both switchyards, which must belong to that substation; requires `equipment_registry.write` (reused, no new permission — no strong architectural reason to diverge from Circuit's own permission scope).
- `GET /api/v1/transformers/{id}` — retrieve, including the parent substation (id, mnemonic, official name — UAT correction), both terminals, and the computed generated short name.
- `PATCH /api/v1/transformers/{id}` — update transformer number, both breaker numbers, and non-structural metadata; requires `equipment_registry.write`.
- `GET /api/v1/transformers/{id}/audit-log` — read-only audit history, mirroring Circuit's own audit-log endpoint (§13's auditability requirement applied consistently, rather than treating audit visibility as Circuit-specific).
- `GET /api/v1/transformer-terminals` — every Transformer Terminal across every substation, with full composed identity (substation, voltage level, transformer short name, side), unpaginated (Phase 3.7 UAT refinement, added to support the Sensitive Customer Registry's cross-module multi-select picker). Exposed as its own top-level resource — `/transformer-terminals`, not `/transformers/{id}/terminals` — mirroring `VoltageYard`'s own established `/voltage-yards` resource (this document's ADR-008 addendum; also referenced at §"Corrected records..." and the UAT-correction list above): a caller here needs to browse or filter Transformer Terminals *across* their parent, not only within one already-selected Transformer's context, exactly the same shape of need `VoltageYard` already has relative to `Substation`. This is different in kind from `CircuitTerminal` (`GET /circuits/{id}/terminals`), which stays path-nested because a Circuit Terminal is only ever meaningful, added, or edited in the context of one specific Circuit already being viewed. Authentication required, no additional permission gate — same read-access pattern as every other list endpoint in this module (mirroring `equipment_registry.read`'s own absence, per this module's read-endpoints-require-only-authentication convention above).
- `GET /api/v1/reference-data/transformer-breaker-numbering-conventions` — list every convention row; lives on the shared reference-data router (`app/reference_data/router.py`), not this module's own router, exactly like `voltage-levels`/`line-types`/etc. — read-only, authentication required, no additional permission gate (same pattern as every other reference-data endpoint).

No `DELETE` endpoint on `/transformers` — transformers are soft-deleted via `operational_status_id`, identically to every other entity in this module (§8, CLAUDE.md §11.6). The reference-data endpoint above has no write endpoint at all — reference data is managed exclusively via `app/reference_data/seed.py`, never through the API (CLAUDE.md §11.3, matching every other reference table).

### Testing Requirements

Per CLAUDE.md §18/A11, in the same priority order as §16 above: business-rule tests (two-terminal creation, HV/LV voltage-order rejection, same-switchyard rejection, **cross-substation HV/LV rejection (UAT correction #1) and same-substation allowance**, uniqueness rejection scoped to `(substation_id, hv_switchyard_id, lv_switchyard_id, transformer_number)` on both create and update, and what it deliberately allows — parallel transformers, same number at a different substation, **same number reused across a different HV/LV pair at the same substation (UAT correction #2)** — breaker-number override never rejected); the generated short-name computation across every seeded voltage level (parametrized); **reference-data seed tests for `transformer_breaker_numbering_convention` — first-run row count, second-run idempotency, exact pattern/is_standard values per transformation pair against the documented convention, and backfill-into-a-partially-seeded-database, mirroring `line_type`'s own established test shape**; an API contract test for the new `GET /api/v1/reference-data/transformer-breaker-numbering-conventions` endpoint (authentication required, every seeded row returned, non-standard/null-pattern row distinguishable from a real pattern); API contract tests (auth, permission enforcement, full create/read/update/audit-log flow including substation fields in every response, **substation-filtered list**, uniqueness rejection on both `POST` and `PATCH`, 404, 405 on `DELETE`); frontend tests (substation-first create workflow, HV/LV dropdowns filtered to the selected substation, generated short name display, **suggested breaker numbers looked up from the reference-data convention list (not a hardcoded table), requiring the transformer number, both switchyards, and the convention list itself to be ready before a suggestion appears**, override behaviour, **no suggestion and free manual entry when no convention row matches the pair**, list rendering with substation column, detail rendering with substation, edit, permission gating, **substation detail page's own transformers-installed-here section**) — implemented as part of this addendum and its UAT-correction and reference-data follow-ups; see this phase's implementation report for the full test inventory and pass counts.

### Glossary additions

| Term | Definition |
|---|---|
| **Transformer** | Substation-owned equipment (`substation_id`, mandatory — UAT correction) connecting exactly two of that substation's own `SubstationVoltageYard` rows (HV and LV) — the fundamental topology element defining connectivity between two voltage levels. Never modeled as spanning two substations. Tertiary windings are out of scope (Phase 3.5). |
| **TransformerTerminal** | One side (HV or LV) of a `Transformer`'s connection to a `SubstationVoltageYard`, carrying that side's own breaker number. Structurally mirrors `CircuitTerminal` (Architecture Decision Gate, Decision 1). |
| **Generated (engineering) short name** | A computed, read-only, user-facing label (e.g. `SGT1`, `XGT1`, `T1`) derived from the HV terminal's voltage level (via the TNB prefix convention) and `Transformer.transformer_number`. Never stored; never unique on its own (Decision 2 and 3 above). |

---

## Phase 3 Follow-up: Engineering Connectivity (Substation Detail Page)

UAT on the Transformer Registry addendum above surfaced an architectural distinction worth stating explicitly, since the two entities now answer superficially similar-sounding but genuinely different questions:

- **Transformer Registry answers asset ownership:** "which transformers are installed at this substation" — a `Transformer` belongs to exactly one substation (`Transformer.substation_id`, the UAT correction above).
- **Circuit Registry answers engineering connectivity:** "which circuits are connected to this substation" — a `Circuit` connects **two or more** substations via its `CircuitTerminal` rows (§7.4–§7.5), and this document's Transformer Registry correction does **not** generalize to `Circuit`.

**`Circuit` does not gain a `substation_id` column.** Doing so would be a category error: a circuit's whole reason for having two-or-more `CircuitTerminal` rows, rather than one, is that it is *not* substation-owned equipment — it is the connection between substations. `Circuit`/`CircuitTerminal` remain modeled exactly as §7.4–§7.5 already describe; only a new read path was added (below), not a new column.

### The Engineering Connectivity read path

`GET /api/v1/circuits` accepts a `substation_id` filter — a circuit matches if any of its `CircuitTerminal` rows' `SubstationVoltageYard.substation_id` equals the given substation, expressed as a read-only join across `Circuit`/`CircuitTerminal`/`SubstationVoltageYard` (permitted under CLAUDE.md F6 for query optimisation/reporting; this module already owns all three tables involved, so no cross-module join is even required). This mirrors the equivalent `substation_id` filter already added to `GET /api/v1/transformers`, giving both entity families a symmetric "which X are connected to/installed at this substation" read path, despite their different ownership models.

The Substation Detail page (Substation Registry, a different module) consumes this filter to render an **"Engineering Connectivity"** section — deliberately named to distinguish it from any future PSS/E-derived view. It displays: the connected-circuit count; and, per circuit, the circuit name, bay number, voltage level, line type, operational status, other connected terminal substations (derived client-side from the already-computed `circuit_name`, which lists every terminal's substation mnemonic — see §7.4; no new backend field was needed), and a link to the circuit's own detail page.

### Relationship to future PSS/E operational topology (architecture note)

**Registry connectivity — what this section, and this module generally, shows — is the manually maintained engineering baseline.** It reflects what an engineer has recorded as true: which circuits terminate where, according to Equipment Registry's own data. It is derived exclusively from `Circuit`/`CircuitTerminal`/`Substation` — never from PSS/E data, and Phase 3 introduces no PSS/E dependency of any kind (§4).

**Future PSS/E topology import (Phase 4) will provide a separate, operational connectivity snapshot** — what is actually, electrically connected according to imported network model data at a point in time (§7.10's `EquipmentTopologyMap` reconciliation already anticipates this). The two are **both valid, and answer different questions**: the engineering registry is the authoritative record of what was engineered and commissioned; the PSS/E snapshot is a point-in-time operational picture that may reveal drift (a physical change not yet recorded in the registry, or a registry entry not yet reflected in the network model actually in service).

**GridDefence must compare these two views, never let one silently overwrite the other.** This is the same reconciliation discipline §7.10 already specifies for individual terminal bay-identifier matching (clean match / unmatched / discrepancy, with discrepancies always requiring an authenticated engineer's explicit resolution, never an automatic write) — restated here at the level of this whole "Engineering Connectivity" concept, so that whichever future module or view eventually surfaces PSS/E-derived connectivity does not casually name itself in a way that implies it replaces, rather than complements, this section. Naming discipline matters here: this section is called "Engineering Connectivity," never "Live Topology" or "Operational Connectivity" — those terms are reserved for the future PSS/E-derived view precisely so the two are never visually or terminologically conflated.

---

## Phase 3 Follow-up: Deletion/Correction Policy

UAT identified a practical gap in an otherwise-already-correct principle: this module never hard-deletes engineering records (CLAUDE.md §11.6 — a substation-registry-wide rule this module has followed since Phase 3), but before this follow-up, users had no way to correct a mistakenly-created **switchyard**, **circuit terminal**, **circuit**, or **transformer** at all — `SubstationVoltageYard` and `CircuitTerminal` had no status field of any kind, and while `Circuit`/`Transformer` already had `operational_status_id`, no status value represented "this was a data-entry mistake" as distinct from "this was real equipment that has since been decommissioned."

### Policy

1. **No hard delete for persisted engineering records** — unchanged; this module still has no `DELETE` endpoint anywhere, for any entity.
2. **A new status, `ENTERED_IN_ERROR`** ("Entered in Error"), added once to the shared Core Platform `operational_status` reference table (CLAUDE.md §11.3) that `Substation`, `Circuit`, and `Transformer` already reuse. It is semantically distinct from `DECOMMISSIONED`/`RETIRED`, which represent real equipment reaching genuine end-of-life — `ENTERED_IN_ERROR` means the record itself should never have been created as described.
3. **Corrected records are hidden from default operational views, never from audit/history views.** Every list endpoint (`GET /circuits`, `GET /transformers`, `GET /voltage-yards`) excludes `ENTERED_IN_ERROR` rows by default; an explicit `include_entered_in_error=true` query parameter reveals them (used by an audit-facing "Show entered-in-error ⟨X⟩" toggle on each corresponding page). Detail endpoints (`GET /circuits/{id}`, `GET /transformers/{id}`) are never filtered by status — a circuit or transformer's own detail page is this module's audit/history view for that one record, reachable by id regardless of status.
4. **Every correction is audit logged**, through each entity's existing per-field audit-log convention — no new audit mechanism was introduced, except one gap this policy closed: `SubstationVoltageYard` previously had no audit log at all (a documented, pre-existing known limitation); it now has `substation_voltage_yard_audit_log`, following the exact shape of `equipment_registry_audit_log`/`transformer_audit_log`.
5. **Existing references are protected.** A switchyard cannot be corrected to `ENTERED_IN_ERROR` while it is still referenced by a non-entered-in-error `CircuitTerminal` or `TransformerTerminal` (on a non-entered-in-error parent `Circuit`/`Transformer`) — rejected with a message naming how many of each still reference it. A new `CircuitTerminal`/`TransformerTerminal` may never be created against a switchyard that is already `ENTERED_IN_ERROR`.
6. **Terminal correction never corrupts historical circuit topology.** Marking a `CircuitTerminal` `ENTERED_IN_ERROR` is *never blocked* — including when it would leave the circuit with fewer than two active terminals — because `CircuitTerminal` is a first-class connectivity object that may legitimately require individual correction, and a circuit may be temporarily incomplete while under correction. The completeness rule (§9 rule 5: at least two terminals) is instead enforced **at the point a circuit tries to (re)enter `Active`** (`change_status`), not at correction time. A circuit already `Active` when a terminal is corrected below the threshold is left as-is (no automatic demotion) — the guard only fires on an actual transition into `Active`.
7. **The UI action is "Mark as Entered in Error," never "Delete,"** for every corrected entity — there is no concept of an uncommitted draft anywhere in this module (every create call is one atomic, already-committed transaction), so the "unless the record is an uncommitted draft" exception this policy allows for never applies here.
8. **Future references cannot point at entered-in-error records — enforced today wherever a real consumer already exists.** No scheme module exists yet in this phase, so nothing yet *creates* a reference to a `Circuit`/`Transformer`; the concrete, actionable instance of this rule today is switchyards (point 5's second half). Any future scheme module must add its own equivalent check (`circuit.operational_status_id != ENTERED_IN_ERROR`) before allowing an assignment — a forward-looking obligation, not code that exists yet.

### Why `TransformerTerminal` is different

Unlike `CircuitTerminal`, `TransformerTerminal` gains **no** status column and **no** independent correction path. A `Transformer`'s HV and LV terminals are intrinsic to what it is — exactly one of each, always — so a single mistaken terminal cannot be corrected in isolation without leaving an invalid, one-terminal transformer on record. The correction unit for a mistaken transformer is the **whole `Transformer`**: mark it `ENTERED_IN_ERROR` via its own, already-existing `operational_status_id` field (no new endpoint needed — `PATCH /transformers/{id}` already accepted this field; the new reference-data row simply makes it a meaningful value to set).

### Affected tables

| Table | Change |
|---|---|
| `operational_status` (Core Platform reference data) | New row: `code=ENTERED_IN_ERROR`, `label="Entered in Error"`, `is_terminal=true`. |
| `substation_voltage_yard` | New column `operational_status_id` (FK, `NOT NULL`, backfilled to `ACTIVE`). |
| `circuit_terminal` | New column `operational_status_id` (FK, `NOT NULL`, backfilled to `ACTIVE`). |
| `substation_voltage_yard_audit_log` | **New table** — closes the pre-existing audit-log gap for this entity (point 4 above). |
| `circuit` | No schema change — `ENTERED_IN_ERROR` is simply a new legal value for the existing `operational_status_id` column. |
| `transformer` | No schema change — same. |
| `transformer_terminal` | **Not changed** — see "Why `TransformerTerminal` is different" above. |
| `substation` | **Not touched.** ADR-005's closed 7-edge transition graph does not list `ENTERED_IN_ERROR` as a reachable transition target, so it is structurally unreachable there even though it lives in the same shared reference table — no code change was needed to keep Substation Registry's own lifecycle unaffected. |

### API surface added

- `PATCH /api/v1/voltage-yards/{id}` — now also accepts `operational_status_id` and `change_reason`.
- `PATCH /api/v1/circuits/{id}/terminals/{id}` — now also accepts `operational_status_id`.
- `GET /api/v1/voltage-yards`, `GET /api/v1/circuits`, `GET /api/v1/transformers` — now accept `include_entered_in_error` (default `false`).
- `GET /api/v1/voltage-yards/{id}/audit-log` — new endpoint, mirroring Circuit's and Transformer's own audit-log endpoints.

No new endpoints were needed for Circuit or Transformer whole-entity correction — `POST /circuits/{id}/status` and `PATCH /transformers/{id}` already accepted `operational_status_id`; the new reference-data row is the only change that makes `ENTERED_IN_ERROR` a meaningful, selectable value there.

---

## 1. Module Overview

Equipment Registry extends Master Data one level below the Substation Registry: it owns the physical grid equipment — transformers, circuits, and protection relays — that exists at or between substations. Substation Registry answers "what substations exist, and what are their identity and status"; Equipment Registry answers "what physical assets exist at those substations, how are they identified, and how do they connect to each other, as a matter of engineering identity and metadata."

**Equipment Registry owns engineering identity and operational metadata. It does not perform, and must never perform, electrical topology analysis.** Electrical topology — what is actually, electrically connected, right now, in the energized network — is owned exclusively by PSS/E Integration; connectivity analysis derived from that topology (island/pocket/spur/downstream-load determination) is owned exclusively by Network Model. This boundary was tested directly against a proposed alternative (a separate "Substation Connectivity Registry") and reaffirmed twice: first by [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md), which rejected creating any such module and confirmed Equipment Registry as the correct owner of identity/metadata instead; then by [equipment-registry-connectivity-validation.md](equipment-registry-connectivity-validation.md), which stress-tested that conclusion against eight concrete engineering workflows and found it sound, while identifying structural gaps in this module's *internal* domain model (§7) that ADR-006 alone did not surface. [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md) then settled the remaining question those two documents left open — which single object every future module should reference — and its answer is built into §7 below.

This module was reserved from the very first architecture document in this series ([substation-registry.md](substation-registry.md) §14: "any additional master asset registries... following the same ownership pattern as the Substation Registry") and referenced as a deferred dependency by every Defence Scheme module built since (`equipment_reference` free text, pending this module — [ufls-module.md](ufls-module.md) §7.4, [uvls-module.md](uvls-module.md), [emls-module.md](emls-module.md)) and by PSS/E Integration (§17 of [psse-integration-module.md](psse-integration-module.md), which anticipated "a mapping entity correlating physical equipment to topology elements... once a future Equipment Registry exists").

**Scope framing.** GridDefence is built for grid **system operators** — engineers who plan and operate transmission grid defence schemes — not for asset owners running an enterprise asset lifecycle. Equipment Registry is **not** intended to replace, duplicate, or partially reimplement an enterprise asset management (EAM) system. Its scope is deliberately narrow: the *operational/functional* equipment identity and wiring that grid defence schemes actually need to reference — what exists, where, how it is identified, and what it trips — not the fuller asset-management record (manufacturer, procurement, maintenance history, ownership lifecycle) an EAM system would own. This framing governs every design decision in this document, most visibly the relay model (§7.8) and the mandatory/optional field split (§7.1, §11).

---

## 2. Purpose

To provide a single, authoritative source of truth for physical grid equipment, so that:

- Every transformer, circuit, and relay has exactly one owner, referenced everywhere else by a stable `equipment_id` (or, for a circuit as a whole, `circuit_id`) — never duplicated.
- **A circuit (a physical line, e.g. "IGBK–PKLG," bay/circuit no. `1`) is modeled as a first-class entity with its own identity, independent of any single terminal's record** — resolving the structural gap the legacy `IncomingBranchDetail` design could not close (§7.4–§7.6, Appendix).
- Bay identifier and breaker number changes over time are preserved as history, not silently overwritten, exactly as substation mnemonic history is already preserved.
- Scheme modules (UFLS/UVLS/EMLS) that currently reference only `substation_id`, with a temporary free-text equipment placeholder, have a concrete, well-defined target to migrate toward — specifically `circuit_id` for circuit-type assignments (§7.11).
- PSS/E Integration has a real Master Data anchor, at the correct granularity (per circuit terminal, §7.10), to correlate imported topology elements against, closing the gap it explicitly deferred.
- A protection relay's physical identity (a real device, wired to a specific circuit terminal or transformer) is modeled separately from any scheme's use of it — resolving the relay-ownership ambiguity flagged since the Codebase Discovery Report.
- The module stays scoped to what grid defence schemes operationally need — never expanding, by default, into enterprise asset management concerns (§4).

---

## 3. Responsibilities

Equipment Registry owns:

- ✓ Equipment identity (`Equipment` — the common backbone every equipment type shares, §7.1)
- ✓ Load transformers and auto-transformers as equipment types (§7.2–§7.3)
- ✓ **Circuit identity and circuit-level metadata** — bay number, voltage level reference, line type reference, interconnector status, lifecycle (`Circuit`, §7.4)
- ✓ **Circuit terminal identity and terminal-specific metadata** — breaker number, commissioning date, the terminal's own substation association (`CircuitTerminal`, §7.5)
- ✓ Protection relays as physical equipment, and their wiring to circuit terminals or transformers (§7.8)
- ✓ Equipment and circuit lifecycle status (§8)
- ✓ Bay ID / alias history for any equipment type, including circuit terminals (§7.9)
- ✓ Its own audit trail (`equipment_registry_audit_log`, CLAUDE.md A4)

---

## 4. Non-Responsibilities

Equipment Registry does **not** own:

- ✗ Substation identity or metadata — owned by the Substation Registry (CLAUDE.md §8). Every piece of equipment references a `substation_id`, never a copy of substation attributes.
- ✗ **Electrical topology data or analysis of any kind.** PSS/E Integration owns the actual, current, validated electrical topology — buses, branches, transformers, and the topology graph itself (`TopologyVersion`, `TopologyBus`, `TopologyBranch`, `TopologyTransformer`). Network Model owns everything derived from that graph — island detection, pocket detection, spur determination, and downstream-load analysis. Equipment Registry does not parse, store, or compute any of this; it is a correlation *target* for PSS/E's topology, never a topology source, and it must never acquire connectivity-analysis capability of its own (ADR-006 §6–§7, §13; reaffirmed by [equipment-registry-connectivity-validation.md](equipment-registry-connectivity-validation.md), Recommendation F).
- ✗ Load snapshots or any live/derived network state — owned by PSS/E Integration.
- ✗ UFLS, UVLS, or EMLS assignments, stages, or scheme data of any kind. **This module has no knowledge of "schemes," "stages," or "shedding assignments"** — mirroring the identical decoupling principle already established for Network Model ([network-model-module.md](network-model-module.md) §9 rule 8) and Critical Infrastructure ([critical-infrastructure-module.md](critical-infrastructure-module.md) §9 rule 10).
- ✗ Scheme-specific shedding configuration — which relay a scheme uses for which stage, or what threshold triggers it, is scheme-owned data (§7.8's relay-ownership resolution).
- ✗ Network analysis results (connectivity, islands, pockets, spurs) — owned by Network Model.
- ✗ Identity, authentication, or authorization — owned by IAM.
- ✗ **Enterprise asset management.** GridDefence serves grid system operators, not asset owners — this module is not an EAM system and does not become one. Specifically out of scope: work orders, maintenance history and scheduling, procurement, warranty tracking, and asset ownership lifecycle (acquisition, depreciation, disposal). Where a future EAM system exists elsewhere in the organisation, this module is, at most, a read-only reference point it could correlate against — Equipment Registry never grows toward owning that data itself (§7.1, §17).

---

## 5. Owned Entities

| Entity | Description |
|---|---|
| `Equipment` | The common identity backbone every piece of equipment shares: a stable `equipment_id`, its owning substation, its type discriminator, its current bay ID, and its lifecycle status (§7.1). |
| `LoadTransformerDetail` | Type-specific attributes for a load transformer, one row per `Equipment` of that type (§7.2). |
| `AutoTransformerDetail` | Type-specific attributes for an auto-transformer (§7.3). |
| `Circuit` | A physical circuit (a line) as a coherent whole, independent of any single terminal — the object engineers select during defence scheme design and the object every other future module references for "this line" (§7.4; ADR-007 §6, §10). |
| `SubstationVoltageYard` | One voltage level physically present at a substation — a substation with more than one voltage class present (e.g. PKLG 275kV and PKLG 132kV) has more than one row. References Substation Registry and Core Platform reference data only; owns no substation identity of its own (§7.5a; ADR-008). |
| `CircuitTerminal` | One voltage yard's end of a `Circuit`, one row per `Equipment` row of type `CircuitTerminal` — replaces and generalizes the earlier `IncomingBranchDetail` design (§7.5; Appendix). Connects to a `SubstationVoltageYard`, not directly to a `Substation` (§7.5a; ADR-008). |
| `RelayDetail` | Type-specific attributes for a protection relay as a physical device (§7.8). |
| `RelayControlledEquipment` | The set of other `Equipment` rows a given relay is physically wired to control — for circuit-type equipment, this always means a specific `CircuitTerminal`-backed `Equipment` row, never a `Circuit` as a whole (§7.8; ADR-007 §6). |
| `EquipmentAlias` | Historical bay ID / identifier changes for any `Equipment` row, with a validity window (§7.9). |
| `Transformer` | A physical transformer connecting exactly two `SubstationVoltageYard` rows (HV/LV). Phase 3.5 — see the "Phase 3.5 Addendum: Transformer Registry" section above for the full specification. |
| `TransformerTerminal` | One side (HV or LV) of a `Transformer`'s connection, structurally mirroring `CircuitTerminal`. Phase 3.5. |
| `equipment_registry_audit_log` | This module's own audit trail (CLAUDE.md A4). |
| `transformer_audit_log` | This entity family's own audit trail (CLAUDE.md A4), owned separately from `equipment_registry_audit_log`. Phase 3.5. |

---

## 6. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| Substation | Master Data (Substation Registry) | `substation_id` (UUID) only, on `Equipment` (every terminal's own substation) — no attributes copied |
| Operational Status | Core Platform (reference data) | `operational_status_id`, reused directly from the same reference table Substation Registry already uses (§8) — not duplicated as an equipment- or circuit-specific lookup |
| Voltage Level | Core Platform (reference data) | `voltage_level_id`, reused directly from the same reference table Substation Registry already uses — referenced by `Circuit.voltage_level_id` (§7.4). A circuit's voltage class is distinct from, and not assumed equal to, either terminal substation's own overall voltage class, since a substation may host multiple voltage levels. |
| **Line Type** | **Core Platform (reference data)** — a new, small reference table added by this revision, following the exact `voltage_level`/`region`/`grid_owner` pattern already established (CLAUDE.md §11.3) | `line_type_id`, referenced by `Circuit.line_type_id` (§7.4). It is a Core Platform-owned lookup, not an Equipment-Registry-owned table, but the *concept* it describes — a circuit's physical construction (overhead/cable/submarine/hybrid) — belongs entirely to Equipment Registry's domain, exactly as `voltage_level` already does for substations. |
| User | Core Platform (IAM) | `user_id` (UUID) only, for `created_by_user_id`/`updated_by_user_id` and audit attribution; fallback `external_principal_id` + provider per [ADR-002](../adr/ADR-002-identity-and-access-management.md) |
| `TopologyVersion`, `TopologyBranch`, `TopologyTransformer` | PSS/E Integration | Not referenced by this module's own tables (§7.10) — PSS/E Integration owns the reverse reference (`EquipmentTopologyMap`), keyed to `CircuitTerminal`-backed `equipment_id` values; Equipment Registry may optionally *consume* PSS/E Integration's read-only interfaces for display purposes only (e.g. current in-service status), never storing a copy |

---

## 7. Domain Model

```
Equipment (1) ──── (0..1) LoadTransformerDetail   [exactly one detail row matching equipment_type]
Equipment (1) ──── (0..1) AutoTransformerDetail
Equipment (1) ──── (0..1) CircuitTerminal
Equipment (1) ──── (0..1) RelayDetail

Circuit (1) ──── (2..N) CircuitTerminal            [every Circuit has at least two terminals; a tee-off has three or more, same entity shape]

Equipment (relay) ──── (many) RelayControlledEquipment ──── references ──▶ Equipment (controlled — a CircuitTerminal- or transformer-typed row, never a Circuit)  [both internal to this module]

Equipment (1) ──── (many) EquipmentAlias

Equipment  ──── references ───▶ Substation.substation_id                       (Master Data, external)
Circuit    ──── references ───▶ VoltageLevel, LineType                          (Core Platform, external)
Equipment  ──── references ───▶ OperationalStatus                               (Core Platform, external)
Equipment / EquipmentAlias ──── references ───▶ User.user_id                    (Core Platform/IAM, external)
```

No arrow points from this module toward PSS/E Integration or any scheme module — the correlation to topology data is held by PSS/E Integration itself, referencing `CircuitTerminal`-backed `equipment_id` values read-only (§7.10), and no scheme module's tables are referenced at all (§4).

### 7.1 Equipment Identity and Type Model

**`Equipment` is a common backbone entity, not several unrelated top-level tables.** Every piece of equipment — regardless of type — gets one `equipment_id` (UUID, per CLAUDE.md A5), one `substation_id`, one `bay_id`, one lifecycle status, and one audit trail, through the shared `Equipment` row. Type-specific attributes live in a separate detail table (`LoadTransformerDetail`, `AutoTransformerDetail`, `CircuitTerminal`, `RelayDetail`), exactly one of which exists per `Equipment` row, matching its `equipment_type` discriminator.

`equipment_type` is one of `LoadTransformer`, `AutoTransformer`, `CircuitTerminal`, `Relay` — immutable once an `Equipment` row is created (§9); there is no "convert this transformer into a circuit terminal" operation, only retiring one record and creating another, consistent with Master Data's immutable-identity principle applied at the equipment level. **`CircuitTerminal` replaces the earlier `IncomingBranch` discriminator value** (Appendix) — this is a renaming as well as a structural generalization, since the earlier name signaled a directional ("incoming") relationship that does not correspond to physical reality (a transmission line has no inherent direction).

This backbone-plus-detail-table shape is a deliberate improvement over the legacy MVP's design, which modeled equipment types as entirely separate, unrelated tables with no common identity, forcing any consumer needing "a piece of equipment, whatever type it is" to use a three-way nullable-foreign-key XOR constraint instead of one clean `equipment_id`. This directly serves §7.11: any scheme module referencing equipment-level assignment data uses a single, unambiguous foreign key.

**Mandatory vs. optional fields — the scope boundary made concrete.** Consistent with §1's scope framing (grid system operators, not asset owners), the `Equipment` backbone's *mandatory* fields are limited to exactly what a grid defence scheme needs to function:

- Equipment identity (`equipment_id`)
- Substation association (`substation_id`)
- Bay/function identifier (`bay_id`)
- Equipment type (`equipment_type`)
- Trip/affected-equipment relationship, where applicable (`RelayControlledEquipment` for relays, §7.8)
- Operational usability/status (`operational_status_id`)
- Scheme relevance (`is_scheme_relevant` — a scheme-agnostic flag marking whether this equipment is the kind of thing a grid defence scheme assignment would ever reference; it says nothing about *which* scheme or *how*, preserving the decoupling in §9 rule 9)
- Remarks (`remarks`, free text)

**Manufacturer, model, firmware version, serial number, maintenance owner, and any other asset-management-adjacent metadata are optional fields only** (§11) — never required to create, edit, or operationally use an `Equipment` record.

### 7.2 Load Transformer Model

`LoadTransformerDetail` carries: `transformer_no`, `hv_voltage`, `hv_breaker_number`, `lv_voltage`, `lv_breaker_number`, `capacity_mva`, `commissioning_date` — directly matching the legacy MVP's `LoadTransformer` fields, now attached to the common `Equipment` backbone rather than standing alone. The computed `bay_id` convention (`{substation_mnemonic}_T{transformer_no}`) is preserved as documented policy (§10). Unaffected by this revision.

### 7.3 Auto-Transformer Model

`AutoTransformerDetail` carries the same shape as `LoadTransformerDetail` (`transformer_no`, `hv_voltage`, `hv_breaker_number`, `lv_voltage` [required, unlike load transformers], `lv_breaker_number`, `capacity_mva`, `commissioning_date`), kept as a genuinely separate `equipment_type` value (not merged into one "transformer" type) because auto-transformers and load transformers represent distinct physical roles in a substation. The computed `bay_id` convention (`{substation_mnemonic}_AT{transformer_no}`) is preserved. Unaffected by this revision.

### 7.4 Circuit Model

**`Circuit` is the canonical engineering reference object for a physical line, as a whole.** It is the object an engineer selects during defence scheme design ("assign IGBK–PKLG, bay/circuit no. `1`, to UFLS Stage 3"), the object Compliance reasons about, and the object Dashboard reports against (ADR-007 §6, §10). It is not itself one piece of equipment and does not sit directly on an `Equipment` row (§7.1's "exactly one detail row per `Equipment` row" pattern does not apply to `Circuit`) — it is the grouping object above two or more `CircuitTerminal` rows, each of which *is* its own `Equipment` row.

`Circuit` carries:

- **Circuit ID** (`circuit_id`, UUID PK per CLAUDE.md A5) — stable identity, independent of any one terminal's `equipment_id`.
- **Bay / circuit number** (`bay_number`) — the circuit-level human designator distinguishing this line from another between the same pair of substations: `1`, `2`, `3`, `Main`, `Transfer`. This is a property of the circuit as a whole, not of one terminal (§7.6 explains why). **Semantics (Phase 3 close-out):** this is a bay/circuit *designator*, not a full display label — never a route description like "Line 1." It is free text, deliberately not restricted to numeric-only input, since real bay designators are often non-numeric (`Main`, `Transfer`, a lettered bay).
- **Circuit name** — not a separately stored field. It is a *computed* display value: the **canonical route name**, derived from the substation mnemonics of the circuit's terminals, sorted alphabetically (case-insensitive) — deterministic regardless of the order terminals were entered in, and **never includes `bay_number`** (e.g. `IGBK–PKLG`, not `PKLG–IGBK Line 1`; Phase 3 close-out — see the Appendix's "Superseded Design Decisions" entry for why this changed). Available through the read interface (§13). Storing it separately would create a second place it could drift out of sync with the terminals it actually names. No documented PSS/E or other engineering naming convention exists yet for terminal ordering; alphabetical-by-mnemonic is used as the default until one is established.
- **Voltage level** (`voltage_level_id`, FK to Core Platform reference data, §6).
- **Line type** (`line_type_id`, FK to Core Platform reference data, §6, §7.6's sibling concept — see below).
- **Interconnector flag** (`is_interconnector`, boolean) — reporting/dashboard convenience only, not load-bearing for any structural rule (§7.12).
- **Operational status** (`operational_status_id`, FK, reused from the same reference table as `Equipment` and Substation Registry, §8).
- **Remarks** (free text).

A `Circuit` has **two or more** `CircuitTerminal` rows: an ordinary point-to-point line has exactly two; a tee-off has three or more, modeled uniformly by the same entity, with no special-cased "third terminal" mechanism (§7.5, §7.13).

**Line type.** `Overhead`, `Cable`, `Submarine`, `Hybrid` — a new, small Core Platform-style reference table (§6), following the exact pattern already established for `voltage_level`/`region`/`grid_owner`/`operational_status` (CLAUDE.md §11.3: reference tables over hardcoded enums, so new construction types can be added without a schema migration). It belongs conceptually to Equipment Registry — it describes a specific circuit's physical construction, a fact no other module has any reason to own — even though it is implemented as a Core Platform-owned lookup table, exactly as `voltage_level` already is for substations.

### 7.5 CircuitTerminal Model

**`CircuitTerminal` is the per-substation terminal of a `Circuit`.** It replaces and generalizes the earlier `IncomingBranchDetail` design (Appendix), and is the object the Automatic Load Shedding Functionality Registry (the "Relay Registry" concept, retired as a working name per [ADR-011](../adr/ADR-011-automatic-load-shedding-functionality-registry.md)) wires to and PSS/E's `EquipmentTopologyMap` matches against (ADR-007 §6, §10; §7.8, §7.10 below).

Structurally, `CircuitTerminal` follows the same pattern as `LoadTransformerDetail`/`AutoTransformerDetail`: it is a per-`Equipment`-row detail table, one row per `Equipment` row of type `CircuitTerminal`, satisfying §7.1's "exactly one detail row per `Equipment` row" rule unchanged. What is new is that **multiple `CircuitTerminal` rows, at different substations, now share a common `circuit_id`** — the structural link the earlier design lacked (Appendix, Gap 3).

`CircuitTerminal` carries:

- `equipment_id` (PK/FK to `Equipment`) — this terminal's own identity, lifecycle status, and computed `bay_id` (§7.9) come from the shared backbone, unchanged in kind from every other equipment type.
- `circuit_id` (FK to `Circuit`, mandatory) — the owning circuit.
- **Voltage yard** (`voltage_yard_id`, FK to `SubstationVoltageYard`, mandatory) — this terminal's substation *and* voltage level, reached together in one reference. Replaces a direct `substation_id` reference (ADR-008; §7.5a). A terminal's substation is `SubstationVoltageYard.substation_id`, one join away, never duplicated onto `CircuitTerminal` itself.
- **Breaker number** (`breaker_number`) — this terminal's own, independently-numbered physical breaker identifier ("L25," "805," "Z1230"). Terminal-specific by construction, not by convention (§7.6). Editable after creation, audited per change.
- `commissioning_date` — kept at the terminal level, not the circuit level, because a tee-off's terminals may genuinely be commissioned at different times (e.g. an original two-terminal line, with a third tap added years later) — a circuit-level-only date could not represent that. Optional; editable after creation, audited per change.
- `remarks` (free text, terminal-specific). Editable after creation.
- `updated_at`/`updated_by_user_id` — added alongside terminal editability (ADR-008); mirrors `Circuit`'s own accountability columns.

**Support for 2-terminal, tee-off, and future N-terminal circuits.** An ordinary circuit has exactly two `CircuitTerminal` rows; a tee-off has three or more. Both are the same entity, the same table, the same relationship to `Circuit` — there is no separate "tee-off" type or mechanism to design or implement (§7.13 walks through a concrete example). This is what resolves the structural gap the connectivity validation identified: the earlier `IncomingBranchDetail.to_substation_id` field was singular, which made a genuine three-terminal tee physically impossible to represent without force-fitting it into multiple, uncorrelated two-terminal rows.

**Relay attachment point.** A relay's `RelayControlledEquipment` link, when it targets circuit-type equipment, always references a `CircuitTerminal`-backed `Equipment` row directly — never a `Circuit` — because a relay is physically wired to one substation's own breaker, not to the line as an abstract whole (§7.8, §9 rule 7; ADR-007 §6).

**EquipmentTopologyMap attachment point.** PSS/E Integration's `EquipmentTopologyMap` matches each `CircuitTerminal`'s bay identifier independently against imported topology data — one map entry per terminal (§7.10).

### 7.5a Substation Voltage Yard

**A substation may have more than one voltage level physically present on site — a `SubstationVoltageYard` row exists for each one.** PKLG with a 275kV yard and a separate 132kV yard is two `SubstationVoltageYard` rows, both referencing `substation_id = PKLG`, one at `voltage_level_id = 275kV` and one at `voltage_level_id = 132kV`. A single-voltage substation simply has one row. This was found to be a real, near-term gap during Phase 3 UAT: `CircuitTerminal` referencing `substation_id` directly cannot express which of a multi-voltage substation's yards a circuit actually terminates at — a fact PSS/E topology correlation and, later, scheme assignment both need at exactly this granularity (ADR-008).

`SubstationVoltageYard` carries:

- `voltage_yard_id` (UUID PK per CLAUDE.md A5) — stable identity, independent of the substation's own `substation_id`.
- `substation_id` (FK to Substation Registry, external, mandatory) — no substation attributes copied (CLAUDE.md §5.1).
- `voltage_level_id` (FK to Core Platform reference data, external, mandatory).
- `commissioning_date`, `latitude`, `longitude` (all optional; Phase 3 UAT follow-up) — yard-level metadata, deliberately **not** on `Substation`: a multi-voltage site may have yards commissioned at different dates with slightly different GIS coordinates (e.g. two physically distinct switchyards on one site). `latitude`/`longitude` follow the same validation as `Substation`'s own geolocation fields (§8 rule 4 equivalent: range-checked, and both-or-neither).
- **Display label** — not a stored field, computed from the referenced substation's mnemonic plus the referenced voltage level's label (e.g. "PKLG — 275kV"), exactly the same computed-not-stored pattern already used for `Circuit`'s own display name (§7.4).

**Ownership.** `SubstationVoltageYard` is owned by Equipment Registry, not Substation Registry (ADR-008) — it asserts a wiring-level fact ("equipment terminates at this substation at this voltage"), the same kind of fact Equipment Registry already owns for `Circuit`/`CircuitTerminal`, not a new fact about substation identity, geography, or operational status (all still exclusively Substation Registry's, unchanged).

**Uniqueness.** At most one `SubstationVoltageYard` row per `(substation_id, voltage_level_id)` pair — a substation does not have two independent yards at the same voltage level in this model.

**Every `CircuitTerminal` references a `SubstationVoltageYard`, never a `Substation` directly** (§7.5). Business rule 6 (§9) is restated at voltage-yard granularity: no voltage yard may hold more than one terminal of the same circuit — deliberately *not* restated at substation granularity. Rule 6a (§9; Phase 3 UAT follow-up) additionally requires every terminal's voltage yard to match its circuit's own `voltage_level_id`; see [ADR-008](../adr/ADR-008-substation-voltage-yard.md)'s addendum for why this means a circuit can no longer terminate twice at the same substation under the current model (no cross-voltage equipment type such as a transformer exists yet).

### 7.6 Bay Number vs. Breaker Number

These are intentionally separate fields, owned at intentionally different levels of the model, because they answer different engineering questions:

| | Bay Number | Breaker Number |
|---|---|---|
| **Owned by** | `Circuit.bay_number` | `CircuitTerminal.breaker_number` |
| **Scope** | The whole circuit — shared, by engineering convention, across every terminal | One terminal only — locally, independently assigned |
| **Examples** | `1`, `2`, `3`, `Main`, `Transfer` | `L25`, `805`, `Z1230` |
| **Why** | Both ends of a physical line are, by convention, called by the same bay/circuit designator — PKLG's engineers and IGBK's engineers both call the same physical circuit bay/circuit no. `1`. It distinguishes this circuit from a parallel circuit between the same two substations, not one terminal from another. It is a designator, not a route description — the route itself is the separately-computed canonical circuit name (§7.4), never `bay_number` appended to it. | Each substation numbers its own switchgear under its own local convention, with no coordination requirement with the substation at the other end. The same physical circuit's breaker at PKLG and its breaker at IGBK are legitimately, and typically, numbered completely differently. |

Conflating the two — as the earlier `IncomingBranchDetail` design implicitly did, by holding a single `breaker_number` per circuit row (Appendix) — cannot represent a circuit's two independently-numbered terminal breakers at once. Keeping them as genuinely separate fields, owned at genuinely different levels of the model, is what makes Workflow E in §7.13 (terminal-specific breakers on the same circuit) representable at all.

**Computed technical bay identifier.** Distinct from both of the above, `Equipment.bay_id` (§7.1, §7.9) remains the per-terminal, machine-facing identifier used for uniqueness enforcement and PSS/E bay-identifier matching (§7.10) — computed for a `CircuitTerminal`-typed `Equipment` row as `{substation_mnemonic}_{circuit.bay_number}` (e.g. `PKLG_1` at PKLG's terminal, `IGBK_1` at IGBK's terminal, for the same bay/circuit no. `1` circuit). This is a technical convenience derived from `Circuit.bay_number`, not a third independent number an engineer enters — see §7.9 for what happens to it when `Circuit.bay_number` itself changes.

### 7.7 Canonical Reference Object Summary

Per ADR-007's decision (§10 of that ADR), every future GridDefence module referencing "equipment" from this registry uses one of exactly two objects, chosen by what that module actually needs to express:

| Consuming module | References | Why |
|---|---|---|
| Relay Registry (this module's own `RelayControlledEquipment`) | `CircuitTerminal` | A relay is physically wired to one substation's own breaker — never to a circuit as an abstract whole (§7.8). |
| Defence Scheme Assignment (UFLS / UVLS / EMLS) | `Circuit` | An engineer designs a scheme against "this line," not against one terminal's detail (§7.11). |
| PSS/E Mapping (`EquipmentTopologyMap`) | `CircuitTerminal` | Bay-identifier matching against real PSS/E structural data is inherently per-terminal (§7.10). |
| Compliance | `Circuit` | Compliance rules reason about assigned lines, not substation-specific wiring detail. |
| Dashboard | `Circuit` (primary), drilling into `CircuitTerminal` for detail views only | A circuit is the natural reporting unit; terminal detail (breaker numbers at each end) is a drill-down, never the primary aggregation key. |
| Future modules (SPS/RAS, Black Start, Islanding, Restoration Planning) | `Circuit`, unless the future module's own concern is physically terminal-specific (in which case, `CircuitTerminal`, by the same reasoning as Relay Registry) | No future module should invent a third reference object without revisiting this table first. |

A `Circuit`'s effective correlation to PSS/E topology — the set of branch/transformer elements it maps to, needed by Network Model to build a cut-set for a scheme's assignment — is the **union of its `CircuitTerminal`s' individual `EquipmentTopologyMap` entries**, resolved by traversal at query time, never separately stored on `Circuit` itself (§7.10, §7.11).

### 7.8 Relay Model — The Relay Ownership Decision

> **Superseded ([ADR-011](../adr/ADR-011-automatic-load-shedding-functionality-registry.md)).** This section's general-purpose relay-wiring direction was never built (`implementation-plan.md`'s Phase 3 status note) and assumed a generic `Equipment` backbone the as-built module does not have. The engineering concept it was meant to serve — "Relay Registry" (EDR-003) — has since been refined into a precisely-scoped, dedicated module: the **Automatic Load Shedding Functionality Registry** (`docs/architecture/automatic-load-shedding-functionality-registry-module.md`), which records automatic UFLS/UVLS shedding readiness per Bay Terminal, independently of Equipment Registry. This section is retained as historical record of the reasoning that led there (relay identity/wiring as physical Master Data), per this document's own practice of noting supersession rather than rewriting narrative history — it is **not** the live design for relay-adjacent functionality going forward.

**Relays are physical equipment master data, but a relay's use by a specific scheme is not.** This is the resolution to the ambiguity flagged since the Codebase Discovery Report ("if a relay is genuinely scheme-agnostic physical equipment, it should be Master Data referenced by all scheme modules, not duplicated per scheme"). *(Note: "Relay Registry" in this document, and in ADR-007, refers to this section's own relay model within Equipment Registry — there is no separate Relay Registry module.)*

The reasoning: a protection relay is a real physical device — it has a location, physical wiring to specific transformers and circuit terminals it can trip, and (in modern digital/numerical relays) frequently implements *multiple* protection functions simultaneously in one physical box. This physical reality — identity, location, and **which equipment it can trip** — is genuinely Master Data, no different in kind from a transformer's physical existence. What is **not** Master Data is a relay's *scheme-specific trip configuration*: which frequency or voltage threshold makes it act, and which scheme's stage it is currently configured to serve. That is scheme-owned business data, because the same physical relay may legitimately be referenced by more than one scheme module (a multifunction relay implementing both a UFLS element and a UVLS element), which is only expressible cleanly if the physical device and its per-scheme configuration are separate things owned by separate modules.

**Relay modeling in this module is deliberately scoped to the relay/tripping function and its wired trip targets — nothing more.** `RelayDetail` carries `relay_name`, `target_voltage_kv` (the voltage level of the breakers this relay operates, a physical/wiring characteristic, not a trip threshold), and `is_active`, plus, via `RelayControlledEquipment`, the mandatory set of other `Equipment` rows it is physically wired to control. **For circuit-type equipment, a `RelayControlledEquipment` link always targets a specific `CircuitTerminal`-backed `Equipment` row, never a `Circuit`** (§7.5, §7.7; ADR-007 §5 Workflow A, §6). This is not merely a modeling convenience — it is the only choice consistent with §9 rule 7 (a relay may only control equipment at its own substation): since a relay lives at exactly one substation, and a `Circuit` may have a terminal at that substation, referencing that specific `CircuitTerminal` is the sole way to express, unambiguously, which physical breaker the relay operates, without any risk of a relay appearing to control a terminal at a substation it does not physically reach.

`RelayDetail` carries **no** frequency threshold, voltage threshold, time delay, or any concept of "which scheme uses this" (those remain scheme-owned, as above), and it carries **no manufacturer, model, or firmware version as required data** — a site engineer working the relay/tripping function has everything this module requires without ever entering that information. Manufacturer, model, firmware version, and serial number *may* be recorded, using the same optional metadata fields available to any `Equipment` row (§7.1, §11). Once scheme modules migrate to circuit-level references (§7.11), each scheme's own assignment records which `relay_id` it uses for a given stage — that reference, and the threshold/delay it implies, remains entirely the scheme module's own business data.

### 7.9 Bay ID / Alias History

**Bay ID history is a generic capability of the `Equipment` backbone, not limited to any one equipment type.** `EquipmentAlias` applies to any `Equipment` row regardless of type, carrying `alias_bay_id`, `valid_from`, and a nullable `valid_to` (null = the alias that was in effect immediately before the current one) — the same validity-window pattern already established for Substation Registry's `substation_alias` and Critical Infrastructure's `CriticalAssetSubstation`.

When `Equipment.bay_id` changes, the previous value is closed out into a new `EquipmentAlias` row (`valid_to` set to the change timestamp) before the new value is written — never silently overwritten (CLAUDE.md §5.2).

**Cascading effect of a `Circuit.bay_number` change.** Because a `CircuitTerminal`-typed `Equipment` row's computed `bay_id` is derived from `Circuit.bay_number` (§7.6: `{substation_mnemonic}_{circuit.bay_number}`), a change to `Circuit.bay_number` itself (e.g. renumbering "Line 1" to "Line 3") changes **every** terminal's computed `bay_id` simultaneously. This must be executed as a single, atomic service-layer operation that produces one new `EquipmentAlias` row per affected terminal, in the same transaction, at the same timestamp — never as independent, terminal-by-terminal edits that could leave terminals of the same circuit briefly (or permanently, on error) reporting inconsistent bay identifiers. Bay-related changes — at either the `Circuit` or `CircuitTerminal` level — are audited with particular emphasis (§14), given their direct effect on the PSS/E reconciliation described in §7.10.

### 7.10 Relationship to PSS/E TopologyVersion and EquipmentTopologyMap

**Equipment Registry does not own the equipment-to-topology mapping.** PSS/E Integration owns `EquipmentTopologyMap`, scoped per `TopologyVersion` (since a piece of equipment's correlation to a specific topology element could differ across topology versions, e.g. after renumbering), holding a clean foreign key to `equipment_id` — specifically, **a `CircuitTerminal`-backed `equipment_id`**, matched per terminal, not per circuit (ADR-006 §6–§9; ADR-007 §6, §12 item 5).

**Matching occurs at the terminal level because that is the level at which real PSS/E structural data is itself terminal-specific.** A PSS/E branch has a "from" bus and a "to" bus; each corresponds to one substation's own electrical connection point. Matching Equipment Registry's data at the same granularity — each `CircuitTerminal`'s own bay identifier (current value, then historical `EquipmentAlias` entries, §7.9) matched against the newly imported `TopologyVersion` — produces a clean, unambiguous correspondence. Matching at the `Circuit` level instead would require an artificial, and potentially lossy, aggregation step before any comparison to PSS/E's inherently per-endpoint data could even be attempted.

**Three outcomes per terminal**, per the reconciliation model ADR-006 already specified and this document now restates as binding for Phase 3/4 implementation:

1. **Clean match, consistent endpoint.** The imported branch element's electrical endpoint agrees with the terminal's declared circuit membership. No action needed.
2. **Unmatched.** No PSS/E element resolves against this terminal's current bay identifier or its alias history. Reported as an unmatched-equipment warning on the triggering `RawFileImportBatch`, surfaced for engineer review, never silently dropped, never blocking the rest of the import.
3. **Discrepancy.** A candidate is found, but the electrically-implied relationship conflicts with what this terminal's circuit membership declares. **Never triggers an automatic write to Equipment Registry, in either direction.** Requires an authenticated, authorized engineer to explicitly resolve it as either *accept as a genuine network change* (an ordinary, audited edit through Equipment Registry's own service layer) or *reject as a data/import error* (Equipment Registry unchanged; the discrepancy record itself retained permanently as part of that import batch's audit trail).

A `Circuit`'s effective correlation to PSS/E — needed whenever a scheme assignment referencing that `Circuit` must be resolved to a cut-set of PSS/E elements (§7.7, §7.11) — is the **union of its terminals' individual, independently-matched `EquipmentTopologyMap` entries**. This union is computed at query time by Network Model or PSS/E Integration's own service layer; it is never stored redundantly on `Circuit`, to avoid a second place that correlation could drift out of sync with its terminals' own, individually-maintained mappings.

Equipment Registry's role in this relationship is purely as the **referenced side**: it exposes a read-only equipment-lookup service interface (§13) that PSS/E Integration's import process calls to resolve a parsed bay identifier — checking both the current `bay_id` and historical `EquipmentAlias` entries — to a stable, `CircuitTerminal`-typed `equipment_id`. Equipment Registry never writes to, or holds a foreign key into, PSS/E Integration's tables.

### 7.11 Defence Scheme Reference Target and Migration Path

**UFLS, UVLS, and EMLS reference `Circuit` — never `CircuitTerminal` — when assigning a line to a scheme.** An engineer designing a scheme selects "PKLG–IGBK Line 1" as one object; the scheme module's own assignment data stores one `circuit_id` (ADR-007 §6, §10, §12 item 7). This confirms and refines the migration path already sketched, identically, in [ufls-module.md](ufls-module.md) §7.4 Open Question 2, [uvls-module.md](uvls-module.md), and [emls-module.md](emls-module.md):

1. A migration adds a nullable `circuit_id` foreign key (referencing this module's `Circuit.circuit_id`) to each scheme module's own direct-assignment table (`ufls_direct_assignment`, `uvls_direct_assignment`, `emls_direct_assignment`) for circuit-type assignments, alongside — not replacing — the existing `equipment_reference` free-text column. Non-circuit equipment (e.g. a transformer referenced directly by a scheme) continues to use a plain `equipment_id` foreign key, unaffected by this refinement — the `circuit_id` target applies specifically, and only, to circuit-type assignments.
2. A data migration attempts to resolve every existing `equipment_reference` value against Equipment Registry's `Circuit`/`CircuitTerminal` data, checking both current bay identifiers and historical `EquipmentAlias` entries (§7.9) — a free-text value recorded by an engineer months or years ago may match a *historical* alias rather than the equipment's current identifier.
3. Assignments that resolve are populated with the real `circuit_id`; assignments that do not resolve are flagged for manual reconciliation, mirroring the "unmatched" reporting pattern already established in PSS/E Integration's own import process and in §7.10.
4. `equipment_reference` is retained afterward as a legacy/fallback display value, not removed — historical assignments' originally-recorded intent is never lost (CLAUDE.md §5.2).
5. Once populated, a scheme module's assignment may resolve circuit-level attributes (voltage level, line type, terminal substations) via `circuit_id`, in addition to the substation-level `substation_id` reference it already holds — both remain valid references simultaneously; circuit-level granularity refines, rather than replaces, the substation-level relationship.

**This migration requires its own ADR before it is undertaken**, exactly as the earlier draft of this document already specified (Appendix) — because it simultaneously modifies the core assignment model of three already-built, already-ratified Defence Scheme modules (UFLS, UVLS, EMLS), which is the kind of cross-cutting change CLAUDE.md A13 requires an ADR for. This document defines the target shape (`circuit_id`) and the migration mechanism; it does not authorize executing it.

**Open question, carried forward unresolved from ADR-007 §13 item 1:** whether a scheme assignment to a tee-off `Circuit` (three or more terminals) always implies "open every terminal," or whether a scheme must be able to reference a subset of a tee-off's terminals independently. This document does not answer that question — it is a prerequisite for the migration ADR above, not for this revision.

### 7.12 Interconnectors

Cross-border and cross-utility tie circuits require no new module, no new equipment type, and no deferral. `grid_owner` reference data already includes a `Tie-Line` category (`TIE_LINE`, seeded since Phase 1). An interconnector is structurally an ordinary `Circuit` whose far-end `CircuitTerminal` happens to reference a Substation Registry record owned under `grid_owner = Tie-Line` — the existing Substation Registry and Circuit/CircuitTerminal design already supports this without modification. `Circuit.is_interconnector` (§7.4) is an optional flag for reporting/dashboard convenience only, distinguishing tie-line circuits at a glance — it carries no structural or validation significance beyond that.

### 7.13 Engineering Workflow Walkthroughs

**Scenario A — PKLG–IGBK Line 1 and Line 2, relay wiring through to pocket detection.**

1. Equipment Registry registers `Circuit` "PKLG–IGBK Line 1" (`bay_number = "1"`) with two `CircuitTerminal` rows — one at PKLG (`breaker_number = L25`), one at IGBK (`breaker_number = 805`) — and, separately, `Circuit` "PKLG–IGBK Line 2" (`bay_number = "2"`) with its own two terminals.
2. An engineer registers Relay A at PKLG, wired via `RelayControlledEquipment` to PKLG's own `CircuitTerminal` for Line 1 — not to the `Circuit` itself, and not to IGBK's terminal, which the same-substation rule (§9 rule 7) forbids regardless.
3. During UFLS scheme design, the engineer is shown circuits wired to relay assignments — resolved by Equipment Registry's own service layer traversing each wired `CircuitTerminal` up to its `circuit_id` (a single foreign-key lookup, §7.7) — and selects **PKLG–IGBK Line 1** and **PKLG–IGBK Line 2** as two `circuit_id` references in the scheme's own assignment data (§7.11).
4. When the scheme's isolated-pocket effect is computed, each selected `Circuit` resolves, via the union of its terminals' `EquipmentTopologyMap` entries (§7.7, §7.10), to its own PSS/E branch. Network Model's cut-set for this assignment is the union of both circuits' resolved branches; opening both, PSS/E's topology graph determines that the IGBK/NKST pocket becomes isolated. Equipment Registry supplies only the circuit identity and its PSS/E correlation; Network Model performs the actual pocket determination, exactly as §4 requires.

**Scenario B — ABBA–NUNI / SMRK / NLAI tee-off.**

1. Equipment Registry registers a single `Circuit` (`bay_number` per local convention) with **three** `CircuitTerminal` rows: one at ABBA, one at SMRK, one at NLAI — the same entity shape as a two-terminal line, with a third row.
2. A user viewing SMRK's own equipment listing sees SMRK's `CircuitTerminal` row directly; because that row carries the same `circuit_id` as ABBA's and NLAI's rows, "is SMRK part of the same registered circuit as ABBA and NLAI" is answered by Equipment Registry alone — a single foreign-key traversal (`Circuit` → its `CircuitTerminal` rows) — with no dependency on Network Model or PSS/E for this specific question.
3. The broader question — "what is the full electrical corridor beyond what has been jointly registered as one circuit, and what does opening it isolate" — remains Network Model's responsibility, computed from PSS/E's topology graph, unchanged by this module's ability to answer the narrower membership question in step 2.
4. Each terminal's own `breaker_number` (independently numbered at ABBA, SMRK, and NLAI) and each terminal's own `EquipmentTopologyMap` correlation are handled exactly as in a two-terminal circuit — no special-cased tee-off logic exists anywhere in this module.

---

## 8. Lifecycle / State Model

`Equipment`, `Circuit`, and their type-specific detail rows are **not** governed by the Canonical Version Lifecycle (CLAUDE.md A3) — the same justification already established for Substation Registry and every other Master Data entity in this series (CLAUDE.md §11.5: "current-state master data... single authoritative record"). **This revision introduces no versioning of any kind.** `Circuit` and `CircuitTerminal` follow the same current-state-plus-audit-log pattern as every other entity in this module — a Draft/Under Review/Approved/Active/Superseded/Archived workflow (CLAUDE.md A3) would be a category error here, exactly as it would for `Equipment` itself; history is preserved through `EquipmentAlias` and the audit log (§7.9, §14), not through versioned records.

- `Equipment.operational_status_id` and `Circuit.operational_status_id` follow the same lifecycle values already defined by Core Platform's reference data and used by Substation Registry (Planned → Active → Decommissioned/Retired) — reused directly, not redefined (§6). Soft-delete only; neither an `Equipment` row nor a `Circuit` row is ever physically deleted (CLAUDE.md §11.6).
- `EquipmentAlias` entries use the `valid_from`/`valid_to` window described in §7.9 — not a formal state machine.
- `RelayDetail.is_active` is a simple physical-device flag (is this relay currently commissioned/in service), independent of `operational_status_id` on the parent `Equipment` row — a relay can be `Active` as physical equipment while a scheme independently decides whether it currently assigns anything to it.
- Every change is captured in the audit log (§14) regardless of the lack of an approval lifecycle.

---

## 9. Business Rules

1. Every `Equipment` row belongs to exactly one substation (`substation_id`) — its "home" location; for a `CircuitTerminal`, this is that specific terminal's own substation.
2. `equipment_type` is immutable once an `Equipment` row is created; a genuine type change is modeled as retiring one record and creating another, never an in-place conversion.
3. Exactly one detail row (`LoadTransformerDetail`/`AutoTransformerDetail`/`CircuitTerminal`/`RelayDetail`) exists per `Equipment` row, and its type must match `equipment_type`.
4. `bay_id` is unique among all *currently valid* `Equipment` records (no two pieces of equipment share an active bay ID simultaneously); a superseded `bay_id` remains unique within its own validity window via `EquipmentAlias` (§7.9).
5. **A `Circuit` must have at least two `CircuitTerminal` rows to be considered complete and available for defence scheme assignment (§7.4, §7.11).** A `Circuit` with fewer than two terminals may exist transiently during data entry but must not be selectable by a scheme module or reported as an active circuit until this is satisfied.
6. **All `CircuitTerminal` rows belonging to the same `Circuit` must reference distinct `SubstationVoltageYard`s** — no voltage yard may hold more than one terminal of the same circuit (generalizes the earlier two-terminal-only distinctness rule to N terminals; restated at voltage-yard, not substation, granularity per ADR-008 — §7.5a).
6a. **Every `CircuitTerminal`'s `SubstationVoltageYard` must have the same `voltage_level_id` as its parent `Circuit`** (Phase 3 UAT follow-up). A `Circuit` represents one physical transmission line at one voltage class; a terminal at a different voltage level would represent a transformer connection, not a line terminal, and transformers are not modeled by this phase (§1/§4). Enforced on both circuit creation and terminal addition, at the service layer (not only the UI). **Interaction with rule 6:** combined with §10's "at most one `SubstationVoltageYard` row per `(substation_id, voltage_level_id)` pair," this rule means a single `Circuit` can no longer legitimately terminate twice at the *same* substation — doing so would require two yards at that substation sharing the circuit's one voltage level, which §10 already forbids. The multi-voltage-substation example in [ADR-008](../adr/ADR-008-substation-voltage-yard.md)'s Decision ("a circuit legitimately may terminate twice at the same multi-voltage substation") described rule 6's own scope correctly at the time, but relied on a circuit spanning two different voltage classes at the same site — a scenario this rule now correctly forecloses, since that is not a real single-voltage transmission line. See ADR-008's addendum note for the full reconciliation.
7. A `RelayControlledEquipment` link's controlled equipment must not itself have `equipment_type = Relay` — a relay controls transformers/circuit terminals, not other relays.
8. **A `RelayControlledEquipment` link's controlled equipment must belong to the same substation as the relay itself.** For circuit-type equipment, this means the link always targets a specific `CircuitTerminal`-backed `Equipment` row at the relay's own substation — **never a `Circuit` directly** (§7.5, §7.8; ADR-007 §6, §10).
9. **Bay ID changes are always tracked via `EquipmentAlias`, never overwritten in place** (§7.9, CLAUDE.md §5.2), including the cascading, atomic update to every affected `CircuitTerminal` when `Circuit.bay_number` itself changes (§7.9).
10. **This module has no knowledge of "schemes," "stages," or "shedding assignments."** It answers only "what equipment and circuits exist, where, and how are they identified and wired" (§4). A scheme's use of a relay, circuit, or transformer, and any threshold or delay that implies, is that scheme module's own business data (§7.8, §7.11).
11. Equipment Registry never writes to Substation Registry, PSS/E Integration, or any scheme module's tables — every cross-module write boundary in this series applies equally here (CLAUDE.md A1, [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md)).
12. **Defence scheme assignment (UFLS/UVLS/EMLS) references `circuit_id`, never a specific `CircuitTerminal` or `breaker_number`, directly** (§7.7, §7.11; ADR-007 §6, §10) — for circuit-type assignments. Non-circuit equipment (transformers) continues to be referenced by plain `equipment_id`.
13. Changing `operational_status_id`, `bay_id`/`bay_number` (which produces one or more new `EquipmentAlias` rows), or any `RelayControlledEquipment` link requires an authenticated, named IAM user and is audited (§14).
14. Cross-module consumers (PSS/E Integration, and eventually scheme modules) access this module's data exclusively through its read-only service interface (§13) — never through direct table access.
15. **Manufacturer, model, firmware version, serial number, maintenance owner, and any other asset-management-adjacent metadata are optional fields and must never be made mandatory** by validation rules, API contracts, or downstream tooling (§7.1) — doing so would silently expand this module's scope toward enterprise asset management, which §4 explicitly excludes.
16. This module does not model work orders, maintenance history, procurement, or asset ownership lifecycle, and must not be extended to do so without a new ADR revisiting the scope decision in §1/§4.

---

## 10. Validation Rules

- `bay_id` is computed per the documented convention for each type (`{substation_mnemonic}_T{transformer_no}` for load transformers, `{substation_mnemonic}_AT{transformer_no}` for auto-transformers, `{substation_mnemonic}_{circuit.bay_number}` for circuit terminals, an administratively-assigned identifier for relays) and validated for uniqueness among currently-valid equipment (§9, rule 4).
- `substation_id` (on every `Equipment` row not of type `CircuitTerminal`, and on every `SubstationVoltageYard`) must reference an existing Substation Registry record. A `CircuitTerminal` references a `SubstationVoltageYard`, not `substation_id` directly (§7.5a; ADR-008).
- `SubstationVoltageYard.voltage_level_id` must reference a valid Core Platform reference row; at most one `SubstationVoltageYard` row per `(substation_id, voltage_level_id)` pair (§7.5a).
- `operational_status_id` (on `Equipment` and `Circuit`) must reference a valid Core Platform reference row.
- `Circuit.voltage_level_id` and `Circuit.line_type_id` must reference valid Core Platform reference rows.
- For transformers and auto-transformers, `hv_voltage` should be greater than or equal to `lv_voltage` where both are populated (a light physical-sanity check, not a hard architectural constraint given real-world exceptions may exist).
- `EquipmentAlias.valid_to`, if set, must be greater than or equal to `valid_from`.
- **A `Circuit` must have at least two `CircuitTerminal` rows before it may be marked usable for scheme assignment** (§9 rule 5). Because this is a minimum-cardinality-across-child-rows constraint, it cannot be expressed as a simple column-level database constraint; it must be enforced at the service layer on any operation that marks a `Circuit` active/assignable, and should additionally be checked by a periodic data-integrity job — the exact mechanism (service-layer check only, vs. a database trigger) is left as a Phase 3 implementation decision, not specified further here.
- **`Circuit.bay_number` uniqueness scope is an open question, not resolved by this document** — carried forward unresolved from ADR-007 §13 item 2. Implementation must not assume global uniqueness (a different substation pair may legitimately have its own "Line 1"); the exact scoping rule (per substation-pair, per substation, or unconstrained with disambiguation coming entirely from the terminal set) must be settled before this validation can be implemented as a database constraint.
- `CircuitTerminal.breaker_number` has **no cross-substation uniqueness requirement** — different substations independently number their own breakers and may legitimately reuse the same code.
- A `RelayControlledEquipment` link's controlled-equipment constraint (§9, rules 7–8) is validated at creation time.
- A `Relay`-type `Equipment` row must have at least one `RelayControlledEquipment` link before it can be marked `is_active` — a relay with no wired trip target is not yet operationally meaningful (§7.8).
- No validation rule may require a value for manufacturer, model, firmware version, serial number, maintenance owner, or other optional metadata fields (§9, rule 15) — these fields accept `NULL`/empty without constraint.

---

## 11. Database Design (Concept)

Conceptual only — no migrations are defined here.

| Table (conceptual) | Key columns (conceptual) | Notes |
|---|---|---|
| `equipment` | **Mandatory:** `equipment_id` (UUID PK), `substation_id` (FK, external, `ON DELETE RESTRICT`), `equipment_type`, `bay_id` (unique among current), `operational_status_id` (FK, external), `is_scheme_relevant` (boolean), `remarks` (text, nullable value but always-present field), `created_by_user_id`, `updated_by_user_id`, `created_at`, `updated_at`. **Optional (asset-management-adjacent, never required — §7.1, §9 rule 15):** `manufacturer`, `model`, `firmware_version`, `serial_number`, `maintenance_owner` (free text) | The common backbone (§7.1). `equipment_type` now includes `CircuitTerminal` in place of the retired `IncomingBranch` value (Appendix). UUID PK per CLAUDE.md A5. |
| `load_transformer_detail` | `equipment_id` (PK/FK to `equipment`), `transformer_no`, `hv_voltage`, `hv_breaker_number`, `lv_voltage`, `lv_breaker_number`, `capacity_mva`, `commissioning_date` | One row iff `equipment.equipment_type = 'LoadTransformer'`. Unaffected by this revision. |
| `auto_transformer_detail` | `equipment_id` (PK/FK), `transformer_no`, `hv_voltage`, `hv_breaker_number`, `lv_voltage` (required), `lv_breaker_number`, `capacity_mva`, `commissioning_date` | One row iff `equipment_type = 'AutoTransformer'`. Unaffected by this revision. |
| `circuit` | `circuit_id` (UUID PK), `bay_number`, `voltage_level_id` (FK, external, `ON DELETE RESTRICT`), `line_type_id` (FK, external, `ON DELETE RESTRICT`), `is_interconnector` (boolean), `operational_status_id` (FK, external), `remarks`, `created_by_user_id`, `updated_by_user_id`, `created_at`, `updated_at` | **New** (§7.4). Circuit-level identity and metadata, independent of any one `equipment` row. |
| `substation_voltage_yard` | `voltage_yard_id` (UUID PK), `substation_id` (FK, external, `ON DELETE RESTRICT`), `voltage_level_id` (FK, external, `ON DELETE RESTRICT`), `created_at`, `created_by_user_id`, `updated_at`, `updated_by_user_id`. **Optional:** `commissioning_date`, `latitude`, `longitude` (range- and pair-checked, mirroring `substation`'s own — Phase 3 UAT follow-up). Unique on `(substation_id, voltage_level_id)`. | **New** (§7.5a; ADR-008). One row per voltage level physically present at a substation. |
| `circuit_terminal` | `equipment_id` (PK/FK to `equipment`), `circuit_id` (FK to `circuit`, `ON DELETE RESTRICT`), `voltage_yard_id` (FK to `substation_voltage_yard`, `ON DELETE RESTRICT`), `breaker_number`, `commissioning_date`, `remarks`, `updated_at`, `updated_by_user_id` | **New, replaces `incoming_branch_detail`** (Appendix); `voltage_yard_id` replaces a direct `substation_id` reference (ADR-008). One row iff `equipment_type = 'CircuitTerminal'`. Two or more rows share the same `circuit_id` for a single physical line (§7.5). |
| `relay_detail` | `equipment_id` (PK/FK), `relay_name`, `target_voltage_kv`, `is_active` | One row iff `equipment_type = 'Relay'`. Unaffected by this revision. |
| `relay_controlled_equipment` | `id` (BIGINT PK), `relay_equipment_id` (FK to `equipment`), `controlled_equipment_id` (FK to `equipment`) | Both internal FKs into this module's own `equipment` table. `controlled_equipment_id` may now resolve to a `circuit_terminal`-backed row (§7.8). Unaffected structurally by this revision. |
| `equipment_alias` | `id` (BIGINT PK), `equipment_id` (FK), `alias_bay_id`, `valid_from`, `valid_to` (nullable) | Generalized alias history (§7.9). Unaffected structurally by this revision. |
| `equipment_registry_audit_log` | `log_id` (BIGINT PK), `entity_type`, `entity_id`, `field_name`, `old_value`, `new_value`, `changed_at`, `changed_by_user_id`, `change_reason` | Owned per CLAUDE.md A4. `entity_type` now also covers `Circuit`. |

**Core Platform reference table addition:** `line_type` (`id` SMALLINT PK per CLAUDE.md A5, `code`, `label`) — `Overhead`, `Cable`, `Submarine`, `Hybrid` — owned by Core Platform's reference data, alongside `voltage_level`/`region`/`state`/`grid_owner`/`operational_status`, not by this module (§6).

**Cross-module constraints:** all foreign keys into `substation`, `voltage_level`, `line_type`, and `user` are `ON DELETE RESTRICT`. Tables are written exclusively through this module's own service layer.

---

## 12. API Contract (Concept)

APIs are external/UI-facing contracts (CLAUDE.md §13, A9); conceptual resource shape only.

- `equipment` — list/retrieve across all types (filterable by `substation_id`, `equipment_type`, `operational_status`); type-specific detail returned nested per row.
- `load-transformers`, `auto-transformers`, `relays` — type-specific sub-resources for creation/editing, each ultimately backed by an `equipment` row plus its detail table.
- `circuits` — create/list/retrieve `Circuit` records (filterable by `voltage_level`, `line_type`, `is_interconnector`, `operational_status`); returns the computed circuit name (§7.4) and its terminal count.
- `circuits/{id}/terminals` — manage a circuit's `CircuitTerminal` rows (add/edit a terminal; each terminal creation is itself backed by a new `equipment` row of type `CircuitTerminal`).
- `equipment/{id}/aliases` — read-only history of bay ID changes (§7.9).
- `relays/{id}/controlled-equipment` — manage a relay's physical wiring to other equipment (transformers or specific `CircuitTerminal`-backed equipment, §7.8).

**Contract requirements (CLAUDE.md A9):** pagination/filtering for collection endpoints; structured error responses; authentication/authorization per endpoint (§15); audit-relevant actions flagged (all writes).

**Data contracts:** standard three-layer separation (CLAUDE.md A6).

---

## 13. Service Interfaces

Per CLAUDE.md A1 (module communication via in-process service-layer interfaces):

**Equipment Registry exposes, for other modules to consume:**
- A read-only equipment-lookup interface, resolving a bay identifier (current or historical, via `EquipmentAlias`) to a stable `equipment_id` — the primary interface PSS/E Integration's `EquipmentTopologyMap` calls during import, at the `CircuitTerminal` granularity (§7.10).
- A read-only circuit-lookup interface, resolving a `circuit_id` to its full terminal set, computed circuit name, voltage level, and line type — the primary interface Defence Scheme modules will call once circuit-level assignment is adopted (§7.11), and the interface Compliance and Dashboard consume for reporting (§7.7).
- A read-only equipment-by-substation listing interface — for Substation Registry's own detail views and for the "which circuits terminate at this substation" question (§7.13, Scenario B step 2).
- A read-only relay lookup, resolving a `relay_id` to its physical details and controlled-equipment set — for future scheme-module consumption once equipment-level relay assignment is adopted (§7.11).

**Equipment Registry consumes, from other modules' service layers — never their repositories directly:**
- From Substation Registry: substation existence/validity checks for every `Equipment.substation_id`.
- From Core Platform: reference-data validity checks for `voltage_level_id`, `line_type_id`, `operational_status_id`.
- From Core Platform (IAM): authorization checks for writes, user lookups for audit attribution.
- Optionally, from PSS/E Integration: read-only current in-service status for display purposes only — never stored, never authoritative for this module's own lifecycle status (§8).

Equipment Registry never calls a scheme module's service interface (§4), and no scheme module writes to this module's tables, per CLAUDE.md A1 and [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md).

---

## 14. Audit Requirements

Per CLAUDE.md §5.4 and A4, Equipment Registry owns and writes its own audit log, covering every owned entity in §5.

- Every create, update, and status change on `Equipment`, `Circuit`, or their detail tables is recorded with who, when, what changed, and why.
- **Bay-related changes are audited with particular emphasis**, given they directly affect the PSS/E reconciliation described in §7.10 — this now explicitly includes both a `CircuitTerminal`'s own bay identifier changing and a `Circuit.bay_number` change, the latter of which cascades to every affected terminal's computed `bay_id` in a single audited transaction (§7.9).
- `RelayControlledEquipment` changes (a relay's physical wiring being added or removed) are audited — this is safety-relevant physical configuration, not routine metadata.
- Audit history is append-only and never modified; audit log access is itself access-controlled (CLAUDE.md A10).

---

## 15. Security Considerations

- All GridDefence engineering data is sensitive by default (CLAUDE.md A10); TLS required outside local development.
- Equipment Registry's data is engineering reference data broadly similar in sensitivity to Substation Registry's own — **not** subject to the stricter human read-access tier recommended for Critical Infrastructure, since knowing a substation's circuit/transformer inventory is materially less sensitive than knowing which substations serve national-security-critical loads.
- Write access (creating/editing equipment or circuits, changing status, modifying relay wiring) requires an authenticated, named IAM user with an appropriate engineering-editor role — comparable in tier to Substation Registry's own write permissions.
- Module-to-module service calls (PSS/E Integration's lookup calls, future scheme-module circuit resolution) are trusted internal code paths, not gated by per-request human permission checks.

---

## 16. Testing Requirements

Per CLAUDE.md §18 and A11, in priority order:

1. **Business rule tests** — `bay_id` uniqueness among current equipment; exactly-one-detail-row-matching-type enforcement; a `Circuit` cannot be marked scheme-assignable with fewer than two `CircuitTerminal` rows (§9 rule 5); all `CircuitTerminal` rows of the same `Circuit` reference distinct substations (§9 rule 6); `RelayControlledEquipment` constraints, including that a controlled `CircuitTerminal`-backed row must be at the relay's own substation (§9 rules 7–8); a structural/architectural test confirming no table in this module has a foreign key into any scheme module's schema (§9 rule 10).
2. **Engineering calculation / validation tests** — bay ID computation correctness per type, including the `{substation_mnemonic}_{circuit.bay_number}` convention for circuit terminals (§7.6); the cascading `EquipmentAlias` update across all of a circuit's terminals when `Circuit.bay_number` changes (§7.9); alias-history resolution correctness (both current and historical lookups succeeding, §7.10, §7.11).
3. **API contract tests** — request/response schema conformance; authorization enforcement.
4. **Database migration tests** — required once actual migrations are authored.
5. **UI behaviour tests** — required once an Equipment Registry frontend exists, including a tee-off (three-or-more-terminal) `Circuit` rendering correctly (§7.13, Scenario B).

Business rules and validation logic must not be merged without accompanying tests (CLAUDE.md A11).

---

## 17. Future Extensions

- **PSS/E `EquipmentTopologyMap`** — owned by PSS/E Integration, referencing this module's `CircuitTerminal`-backed `equipment_id` values at per-terminal granularity (§7.10); the concrete realization of the Future Extension already reserved in [psse-integration-module.md](psse-integration-module.md) §17, now fully specified as binding for Phase 4.
- **Scheme-module circuit-level migration** (§7.11) — the concrete data/schema migration for UFLS/UVLS/EMLS; **requires its own ADR** before being undertaken, not designed further here.
- **Richer equipment types** — circuit breakers, current/voltage transformers (CTs/VTs), or other bay-level assets could be added as additional `equipment_type` values sharing the same `Equipment` backbone, without redesigning this module's core structure.
- **Integration with an external enterprise asset management (EAM) system**, should the organisation operate one — a read-only correlation is the appropriate future shape, not building work-order, maintenance-history, or procurement functionality inside this module (§1, §4, §9 rule 16).
- **Relay scheme-usage visibility** — once scheme modules migrate to circuit-level relay references (§7.11), a read-only Audit and Analytics capability could show "which schemes currently use this relay" by querying each scheme module's own data.
- **Partial tee-off scheme assignment** — whether a scheme may assign to a subset of a tee-off `Circuit`'s terminals rather than the whole circuit, carried forward as unresolved from §7.11 and ADR-007 §13 item 1.

---

## 18. Risks and Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| The scheme-module circuit-level migration (§7.11) is a cross-cutting change touching three already-built modules simultaneously | Risk of inconsistent or partial migration across UFLS/UVLS/EMLS if undertaken informally | Require the dedicated ADR already flagged (§7.11) before starting; the ADR should define a single, coordinated migration plan covering all three modules together |
| `Circuit.bay_number` uniqueness scope is not yet resolved (§10) | Implementation could pick an arbitrary scoping rule that later proves too strict (blocking legitimate re-use of "Line 1" between different substation pairs) or too loose (allowing genuine duplicate confusion) | Resolve explicitly, with real Malaysian/TNB naming examples, before authoring the Phase 3 migration — do not default silently to global uniqueness |
| The minimum-two-terminal `Circuit` completeness rule (§9 rule 5) is not database-enforceable as a simple constraint | A service-layer-only check could be bypassed by a bug or a future direct-write path, leaving an incomplete circuit marked assignable | Enforce at the service layer on every status transition to "assignable," and add a periodic data-integrity check; consider a database trigger if the ORM/migration tooling makes one low-cost once Phase 3 implementation begins |
| Bay-identifier reconciliation against historical `EquipmentAlias` entries (§7.11) may still fail to resolve some legacy `equipment_reference` free-text values | Some historical assignments could remain unresolved indefinitely | Mirror PSS/E Integration's own "unmatched" reporting pattern (§7.10) — surface unresolved assignments for manual reconciliation rather than blocking the migration on 100% automatic resolution |
| A relay physically serving multiple schemes (§7.8) could create confusion if two scheme modules independently configure conflicting thresholds against the same physical device without realizing they share it | Operational miscoordination at a shared relay | Recommend this scenario be explicitly surfaced by a future Cross-Scheme Compliance extension or Dashboard view once circuit-level relay references exist (§17) |
| A tee-off `Circuit`'s scheme-assignment semantics (whole-circuit vs. partial-terminal) remain unresolved (§7.11, §17) | A Phase 3 implementer could silently pick an assumption that later proves wrong for a real three-way tee | Flag explicitly in the migration ADR (§7.11) as a question that must be answered before circuit-level scheme assignment ships, not discovered after |
| Scope creep toward enterprise asset management over time | Would silently expand this module beyond what grid system operators need, duplicating or competing with a real EAM system | Treat §4's EAM exclusion and §9 rules 15–16 as a hard boundary requiring a new ADR to cross |

---

## 19. Glossary

| Term | Definition |
|---|---|
| **Circuit** | A physical transmission line as a coherent whole, connecting two or more substations. The canonical engineering reference object for defence scheme assignment, compliance, and dashboard reporting (§7.4, §7.7; ADR-007 §6, §10). Not itself a PSS/E concept. |
| **CircuitTerminal** | One voltage yard's end of a `Circuit`. One row per `Equipment` row of type `CircuitTerminal`. The canonical reference object for relay wiring and PSS/E topology correlation (§7.5, §7.7; ADR-007 §6, §10). References a `SubstationVoltageYard`, not a `Substation` directly (§7.5a; ADR-008). |
| **SubstationVoltageYard** (a.k.a. **Switchyard**) | One voltage level physically present at a substation — a multi-voltage substation has more than one row. Owned by Equipment Registry, referencing Substation Registry and Core Platform reference data only (§7.5a; ADR-008). "Switchyard" is the user-facing term as of Phase 3 close-out; the model/table/API names are unchanged (ADR-008 addendum). |
| **Bay Number** | The circuit-level human *designator* distinguishing one line from another between the same pair of substations — e.g. `1`, `2`, `Main`, `Transfer` (not a route description like "Line 1" — Phase 3 close-out). Owned by `Circuit.bay_number`, shared across all of a circuit's terminals (§7.6). |
| **Breaker Number** | A terminal-specific, locally-assigned physical breaker identifier — e.g. "L25," "805," "Z1230." Owned by `CircuitTerminal.breaker_number`, independently numbered at each terminal (§7.6). |
| **Bay ID** | The computed, machine-facing technical identifier on the `Equipment` backbone (`{substation_mnemonic}_{circuit.bay_number}` for a circuit terminal), used for uniqueness enforcement and PSS/E bay-identifier matching — distinct from, and derived from, `Circuit.bay_number` (§7.1, §7.6, §7.9). |
| **EquipmentTopologyMap** | Owned by PSS/E Integration, not this module. Correlates each `CircuitTerminal`'s bay identifier to the PSS/E topology element(s) it corresponds to in a given `TopologyVersion`, producing a clean-match, unmatched, or discrepancy outcome per terminal (§7.10). |
| **Tee-off** | A `Circuit` with three or more `CircuitTerminal` rows, representing a multi-terminal line — modeled by the same entity shape as an ordinary two-terminal circuit, with no special mechanism (§7.5, §7.13). |
| **Interconnector** | A `Circuit` whose far-end terminal is at a `Tie-Line`-owned Substation Registry record, representing a cross-border or cross-utility tie. Flagged via `Circuit.is_interconnector` for reporting convenience only (§7.12). |
| **Discrepancy** | An `EquipmentTopologyMap` matching outcome where a candidate PSS/E element is found but its implied electrical relationship conflicts with a `CircuitTerminal`'s declared circuit membership. Requires mandatory, audited engineer review; never resolved automatically (§7.10). |

---

## Appendix: Superseded Design Decisions

This appendix records where this revision's content differs from an earlier draft of this document or from [equipment-registry-connectivity-validation.md](equipment-registry-connectivity-validation.md), per this task's instruction to note such inconsistencies here rather than silently editing historical documents.

1. **`IncomingBranchDetail` is superseded by `Circuit` + `CircuitTerminal`.** The earlier design modeled a circuit as a single row (one `breaker_number`, one `to_substation_id`), owned asymmetrically by whichever substation happened to hold the row. This could not represent terminal-specific breaker numbers or multi-terminal (tee-off) circuits. Superseded per [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md) §12 items 1–3 and [equipment-registry-connectivity-validation.md](equipment-registry-connectivity-validation.md)'s Recommended Refinements 1–2.
2. **The `equipment_type` value `IncomingBranch` is renamed to `CircuitTerminal`.** A generalization, not a cosmetic rename — it reflects a direction-neutral entity that did not exist in the earlier shape. Per the connectivity validation's Final Architecture Recommendation D.
3. **Bay number field placement is corrected relative to the connectivity validation document's initial proposal.** That document's Workflow 3 treated the bay/circuit identifier as terminal-scoped, identically to breaker number. [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md) §3 corrected this: `bay_number` ("Line 1"/"Line 2") is a **circuit-level** fact, shared across terminals by engineering convention; only `breaker_number` (and the derived, computed `bay_id`) are genuinely terminal-level. This document implements the corrected placement (§7.6). The connectivity validation document itself is left unedited, per this task's constraints — this entry is the authoritative correction.
4. **The equipment-level scheme-assignment migration target is refined from generic `equipment_id` to `circuit_id`.** The earlier draft of this document's §7.8 (now §7.11) described UFLS/UVLS/EMLS migrating to a generic `equipment_id` reference. [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md) §12 item 7 refines this: circuit-type assignments target `circuit_id` specifically; non-circuit equipment (transformers) continues to use plain `equipment_id`, unaffected.
5. **`CircuitTerminalDetail` (the connectivity validation's placeholder name) is finalized as `CircuitTerminal`**, dropping the "Detail" suffix, reflecting its elevation to a genuine, independently-referenced domain object rather than a satellite detail table — per [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md) §7, §8.
6. **`CircuitTerminal` connects to a `SubstationVoltageYard`, not directly to a `Substation`.** Found during Phase 3 UAT: a direct `substation_id` reference cannot express which voltage yard of a multi-voltage substation a circuit terminates at. `SubstationVoltageYard` (§7.5a) is a new Equipment-Registry-owned entity; business rule 6 (§9) is restated at voltage-yard granularity, not substation granularity. Per [ADR-008](../adr/ADR-008-substation-voltage-yard.md).
7. **`bay_number` is a short designator (`1`, `Main`), not a full display label (`Line 1`).** UAT found users unsure whether to enter "1" or "Line 1" for `bay_number`, since earlier examples throughout this document (§7.4, §7.6, and the illustrative walkthroughs in §7.9/§7.11/§7.13) used the "Line 1" convention. `bay_number` remains free text — no numeric-only validation is introduced, since real bay designators are frequently non-numeric (`Main`, `Transfer`). Phase 3 close-out; §7.4, §7.6 carry the corrected semantics and examples.
8. **The computed circuit name no longer includes `bay_number`, and terminal mnemonics are sorted, not joined in entry order.** Two defects found in the same UAT pass: (1) a circuit name like "PKLG–IGBK Line 1" displayed next to a separate `bay_number` field ("Line 1") looked duplicated; (2) mnemonics joined in terminal-insertion order meant the same physical circuit could display as "PKLG–IGBK" or "IGBK–PKLG" depending on which terminal was entered first. Both are corrected in §7.4: the canonical name is the sorted (case-insensitive), terminal-mnemonics-only route, computed identically regardless of entry order, with `bay_number` shown only as its own, separately-labeled field. No PSS/E or other documented engineering naming convention existed for terminal ordering, so alphabetical-by-mnemonic was adopted as the default.
9. **"Switchyard" is the user-facing term for what this document and the codebase still call `SubstationVoltageYard` internally.** Reviewed at Phase 3 close-out: as future entities (busbars, bus couplers, breakers, disconnectors, transformers, reactors, capacitors) are added, "voltage yard" becomes an increasingly awkward term for what is, physically, a switchyard. The model/table/column/API names (`SubstationVoltageYard`, `substation_voltage_yard`, `voltage_yard_id`, `/api/v1/voltage-yards`) are deliberately **not** renamed — the churn (a table rename, its FKs, every reference across two modules and three ADRs) was judged not worth it for a naming-only change. UI labels, buttons, and user-facing error messages now say "Switchyard"; this document uses "Voltage Yard / Switchyard" going forward to bridge old and new terminology. See ADR-008's addendum for the full reasoning.

No change recorded here reopens ADR-006's module-ownership decision, or any part of this document not listed above.

---

## Recommended Next Architecture Document

**The equipment-level scheme assignment migration ADR** (§7.11) is now the most concrete, most clearly-scoped next step: this document defines exactly what that ADR must decide (a coordinated, single migration plan adding `circuit_id` to `ufls_direct_assignment`/`uvls_direct_assignment`/`emls_direct_assignment`, alongside the existing `equipment_reference` reconciliation mechanism), and it is a hard prerequisite for UFLS/UVLS/EMLS to consume Phase 3's design end-to-end.

**IAM module** remains a very strong, arguably comparably urgent alternative, unchanged from the prior recommendation: every module in this series references `user_id` for accountability and calls into IAM's service layer for authorization, yet IAM itself has never received the full Canonical Module Architecture Document Template treatment every other module has.

**`EquipmentTopologyMap`'s own detailed design**, as a focused addition to [psse-integration-module.md](psse-integration-module.md), is the third clear candidate — this document has specified its required behaviour in full (§7.10), but psse-integration-module.md itself still only names it as a Future Extension; formalizing it there, at the same level of section-by-section detail this document now has, is the natural companion piece before Phase 4 implementation begins.
