# ADR-008: Substation Voltage Yard as the CircuitTerminal Connection Point

> **Note (ADR-009):** this ADR's Decision states `substation-registry.md` is
> "unaffected in ownership." [ADR-009](ADR-009-substation-voltage-level-deprecation.md)
> revisits that specific point: `Substation.voltage_level_id` is deprecated
> (nullable, removed from the API contract) now that this ADR's
> `SubstationVoltageYard` is the sole authoritative representation of a
> substation's voltage level(s). The rest of this ADR's decision is
> unchanged.

> **Note (Phase 3 UAT follow-up):** this ADR's Decision illustrates rule 6's
> yard-vs-substation scoping with an example of a circuit terminating twice
> at the same multi-voltage substation, across two different voltage
> levels. A new business rule (equipment-registry-module.md §9 rule 6a)
> now requires every `CircuitTerminal`'s voltage yard to match its
> `Circuit`'s own `voltage_level_id`, since a real transmission line
> operates at one voltage class. See the addendum below for the full
> reconciliation — rule 6 itself (yard-, not substation-, scoped
> uniqueness) is unchanged.

> **Note (Transformer Registry UAT corrections):** the "Transformer Registry —
> Architecture Decision Gate Outcomes" addendum below records the original
> Decision 3 (`UNIQUE (hv_switchyard_id, lv_switchyard_id,
> transformer_number)`, service-layer only). "Transformer Registry — UAT
> Correction (Substation Ownership)" supersedes that specific decision with
> `Transformer.substation_id` (mandatory column, both terminals must belong
> to it) and `UNIQUE(substation_id, transformer_number)` as a real database
> constraint. **"Transformer Registry — UAT Correction #2 (Numbering
> Model)" supersedes the uniqueness key a second time**: it reverts to
> `(substation_id, hv_switchyard_id, lv_switchyard_id, transformer_number)`,
> enforced at the service layer, not as a database constraint — the
> substation-only key incorrectly collapsed every transformation level at a
> substation into one shared bay-number namespace. `substation_id` itself
> remains a mandatory column (unaffected). Read all three addenda together;
> the third is authoritative for uniqueness.

- **Status:** Accepted
- **Date:** 2026-07-06
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1, §8, §11.2, A5)
- **Depends on:** [ADR-006](ADR-006-connectivity-registry-vs-psse-topology-architecture.md), [ADR-007](ADR-007-canonical-engineering-reference-object.md)
- **Affects:** [docs/architecture/equipment-registry-module.md](../architecture/equipment-registry-module.md) §7.5–§7.7, §9 rule 6a (addendum below), §11 (`CircuitTerminal`'s connection point), and its "Phase 3.5 Addendum: Transformer Registry" section (addendum below — `Transformer`/`TransformerTerminal` reuse this ADR's `SubstationVoltageYard` connection point as a second consuming entity); `docs/architecture/substation-registry.md` (unaffected in ownership — see Decision); `backend/app/modules/equipment_registry/models.py` (`SubstationVoltageYard` gains optional `commissioning_date`/`latitude`/`longitude` metadata, Phase 3 UAT follow-up — no change to this ADR's ownership decision)

---

## Context

Phase 3 UAT found that `CircuitTerminal` referencing `Substation` directly is insufficient for real substations that have more than one voltage level physically present on site (e.g. PKLG has both a 275kV yard and a 132kV yard). A `CircuitTerminal` naming only `substation_id = PKLG` cannot express *which* of PKLG's voltage yards a given circuit actually terminates at — a real ambiguity that will directly block PSS/E topology correlation (a PSS/E bus is a specific voltage-level bus, not "the substation" as a whole) and, later, scheme assignment (a UFLS stage sheds load at a specific voltage yard, not an entire multi-voltage station).

## Decision

Introduce `SubstationVoltageYard` as a new entity, and change `CircuitTerminal` to reference `voltage_yard_id` instead of `substation_id` directly:

```
Substation (Master Data, Substation Registry)
    -> SubstationVoltageYard (0..N per substation)
         -> CircuitTerminal (references exactly one voltage yard)
```

- `SubstationVoltageYard` is owned by **Equipment Registry**, not Substation Registry. It references `substation_id` (Substation Registry, external FK, no attributes copied) and `voltage_level_id` (Core Platform reference data, external FK) — it asserts no new fact about the substation's own identity, geography, or operational status (all still exclusively owned by Substation Registry, unchanged). It asserts a wiring-level fact — "this substation has equipment terminating at this voltage level" — which is the same kind of fact Equipment Registry already owns for `Circuit`/`CircuitTerminal` (ADR-007).
- A substation may have one or more voltage yards; each voltage yard belongs to exactly one substation and references exactly one voltage level. A substation is never required to have more than one — a single-voltage substation simply has one yard.
- `CircuitTerminal.substation_id` is removed; `CircuitTerminal.voltage_yard_id` (mandatory) replaces it. A terminal's substation is now reached by one join (`CircuitTerminal → SubstationVoltageYard → Substation`), never duplicated.
- The uniqueness rule scoped to a circuit (equipment-registry-module.md §9 rule 6) is restated at voltage-yard granularity: no voltage yard may hold more than one terminal of the same circuit. This is deliberately *not* restated at substation granularity — a circuit legitimately may terminate twice at the same multi-voltage substation, once per voltage yard, without that being a duplicate.

## Consequences

**Positive:** Removes a real, near-term correctness gap before it reaches PSS/E import or scheme assignment, which both need voltage-level-specific terminal identity. Costs one additional join for every terminal→substation resolution, in exchange for resolving an ambiguity that would otherwise have to be special-cased later, at higher cost (migrating live PSS/E correlation and scheme-assignment data instead of pre-Phase-4 Equipment Registry data).

**Negative:** Every existing `circuit_terminal` row must be migrated to point at a real `voltage_yard_id` (see the accompanying migration's data-backfill strategy, documented in its own docstring). A substation with genuinely no reachable voltage-yard row (should not occur post-migration, since every substation is backfilled exactly one default yard) cannot receive a new circuit terminal until one is added.

## Alternatives Considered

- **Add a `voltage_level_id` column directly on `CircuitTerminal`, keep `substation_id` as-is.** Rejected: this duplicates a fact (`voltage_level_id`) without giving it its own identity, so nothing prevents two terminals independently entering the "same" voltage yard with slightly inconsistent metadata, and there is nowhere to hang future voltage-yard-level facts (e.g. a yard's own PSS/E substation/zone mapping) without another migration later.
- **Do nothing until Phase 4 (PSS/E import) forces the issue.** Rejected: Phase 3 is explicitly the foundation PSS/E import and scheme assignment are sequenced on top of (per the Phase 4 pause that prompted this fix); deferring would mean migrating live topology-correlation and scheme-assignment data later instead of pre-Phase-4 registry data now.

## Decision (implementation-facing, restated for equipment-registry-module.md)

`equipment-registry-module.md` §7.5–§7.7 and §11 are updated to reflect this: `CircuitTerminal` now carries `voltage_yard_id`, not `substation_id`; `SubstationVoltageYard` is documented as a new owned entity of Equipment Registry, referencing Substation Registry and Core Platform reference data only, never duplicating either.

---

## Addendum (2026-07-04): Reconciling Rule 6 with the New Terminal-Voltage-Level Rule

This addendum is additive; nothing above is revised.

### Context

Phase 3 UAT found that the Add Terminal dropdown (Circuit Create and Circuit Detail) could offer voltage yards at a different voltage level than the circuit itself — e.g. a 132kV circuit accepting a 500kV terminal. A `Circuit` represents one physical transmission line at one voltage class; a terminal at a different voltage level does not represent a real line terminal (that would be a transformer connection — a different equipment type, not modeled by this phase per §1/§4).

### Decision

**Every `CircuitTerminal`'s `SubstationVoltageYard.voltage_level_id` must equal its parent `Circuit.voltage_level_id`**, enforced at the service layer on both circuit creation and terminal addition (equipment-registry-module.md §9 rule 6a).

**Interaction with this ADR's own rule-6 example:** this ADR's Decision section illustrates rule 6 (voltage-yard-, not substation-, scoped uniqueness) using a circuit terminating twice at PKLG — once at a 500kV-equivalent yard, once at a 132kV-equivalent yard. That example remains a correct illustration of rule 6's *scope* (it is not a duplicate, because the two terminals reference different yards), but it is no longer a *constructible* example once rule 6a is enforced, because rule 6a requires both of that circuit's terminals to share one voltage level, and §10 already limits a substation to one yard per voltage level — so two yards at the same substation can never both match one circuit's voltage level. In practice, this means a single `Circuit` can no longer terminate twice at the same substation at all, under the current model (no `Transformer` equipment type exists yet to represent a same-site, cross-voltage connection). Rule 6 itself is unchanged and still correctly scoped to voltage yards, not substations — it simply no longer has a reachable same-substation example until a real cross-voltage equipment type (e.g. `Transformer`) is introduced in a future phase.

### Consequences

**Positive:** Removes a real validation gap found in Phase 3 UAT (a mismatched voltage yard was selectable and acceptable via a direct API call) and makes the domain model consistent with a `Circuit`'s real-world meaning (one line, one voltage class).

**Negative:** The specific illustrative scenario in this ADR's Decision section is no longer constructible as written; readers should treat it as historical context for rule 6's scoping decision, not as a currently-reachable example. The automated test that previously exercised this scenario has been replaced by tests for the new rule 6a (see equipment_registry's test suite).

---

## Addendum (2026-07-04): "Switchyard" as the User-Facing Term

This addendum is additive; nothing above is revised.

### Context

As Phase 3 closes out, the project asked whether `SubstationVoltageYard` should be renamed to `Switchyard` — engineering reasoning being that a voltage-specific yard within a substation is closer to a switchyard, especially as future entities (busbars, bus couplers, breakers, disconnectors, transformers, reactors, capacitors) are added and "voltage yard" becomes an increasingly imprecise term for what is, physically, a switchyard.

### Decision

**Option B: keep the internal model/table/column/API names unchanged; use "Switchyard" as the user-facing term.**

- `SubstationVoltageYard` (class), `substation_voltage_yard` (table), `voltage_yard_id` (column/FK), `/api/v1/voltage-yards` (endpoint prefix), and every internal method name (`create_voltage_yard`, `list_voltage_yards`, `update_voltage_yard`, `VoltageYardCreate`/`VoltageYardSummary`/`VoltageYardUpdate` schemas) are **not renamed**.
- UI labels, buttons, headings, and user-facing error/validation messages now say "Switchyard" (e.g. "Add switchyard," "Switchyard 'X' does not exist," the Substation Detail page's "Switchyards" section).
- Architecture documentation uses "Voltage Yard / Switchyard" going forward, to bridge existing "Voltage Yard" terminology already pervasive in this ADR and ADR-009 with the new user-facing term.

**Why not full rename (Option C):** a full rename touches a table, its FKs and indexes, every backend module file referencing it, every frontend file referencing it, and the historical decision text of this ADR and ADR-009, for a naming-only change with no functional benefit. Judged disproportionate churn immediately before freezing Phase 3.

**Why not keep "Voltage Yard" everywhere (Option A):** the engineering reasoning above is sound and will only get more relevant as busbars/breakers/transformers are modeled in future phases; deferring the terminology fix indefinitely would mean relabeling a larger UI surface later, for the same reason, at higher cost.

### Consequences

**Positive:** User-facing terminology now anticipates the module's own documented future scope (§17 of equipment-registry-module.md) without any migration risk. Internal identifiers remain stable, so this decision carries zero risk to existing data, tests, or API consumers.

**Negative:** A temporary terminology split exists between code (still "voltage yard" internally) and UI/most-of-docs (now "switchyard") — mitigated by this addendum and equipment-registry-module.md's own Appendix entry recording the decision, so a future reader is not left to guess why the two differ.

---

## Addendum (2026-07-04): Transformer Registry — Architecture Decision Gate Outcomes (Phase 3.5)

This addendum is additive; nothing above is revised. It records the three genuine modelling ambiguities identified before Phase 3.5 (Transformer Registry) implementation began, and the Project Owner's explicit approval of all three, per the same architecture-first, stop-before-implementing process used throughout Phase 3. Full specification: [equipment-registry-module.md](../architecture/equipment-registry-module.md)'s "Phase 3.5 Addendum: Transformer Registry" section.

### Context

A `Transformer` connects exactly two `SubstationVoltageYard` (Switchyard) rows — one HV, one LV — the same connection point this ADR already established for `CircuitTerminal`. Extending that connection point to a second consuming entity surfaced three questions this ADR's original decision did not need to answer for `CircuitTerminal` alone.

### Decision 1 — `TransformerTerminal` child rows vs. direct `hv_*`/`lv_*` columns on `Transformer`

**Option B — `TransformerTerminal` child rows (`side` = `HV`/`LV`, each with its own `voltage_yard_id` and `breaker_number`) — approved**, structurally mirroring `CircuitTerminal`'s own shape exactly, over Option A (`hv_switchyard_id`/`hv_breaker_number`/`lv_switchyard_id`/`lv_breaker_number` as direct columns on `Transformer`).

**Why:** `side` is a CHECK-constrained string (`'HV'`/`'LV'`), not a fixed pair of columns — a future tertiary-winding phase can add a third `side` value via a constraint change alone, with zero migration to `Transformer` itself. Option A would have baked a permanent two-winding assumption directly into the `Transformer` table's own column set, which a tertiary-winding phase could only undo with a breaking schema change.

### Decision 2 — generated engineering short name: stored or computed at read time

**Computed at read time — approved**, never stored on `Transformer`, for the identical reason this document's sibling entity `Circuit`'s own canonical name is computed rather than stored (equipment-registry-module.md §7.4): storing it separately would create a second place it could drift out of sync with the HV terminal's voltage level or the transformer number, either of which can change after creation.

### Decision 3 — the transformer uniqueness rule

**`UNIQUE (hv_switchyard_id, lv_switchyard_id, transformer_number)` — approved**, enforced at the service layer (not a raw database `UNIQUE` constraint, since the identity spans two child `TransformerTerminal` rows joined by `transformer_id`, which a single-table constraint cannot express — CLAUDE.md §11.8).

**This uniqueness constraint represents the physical transformer's own identity — the specific pair of switchyards it connects, plus its bay/transformer number — whereas the generated engineering short name (e.g. `SGT1`) is a separate, computed, user-facing label derived from the HV voltage level and transformer number.** Two physically distinct transformers at two different substations may legitimately share the same computed short name (e.g. two transformers both computing to `SGT1`, one at PKLG and one at IGBK) without violating uniqueness, because uniqueness is keyed on physical switchyard identity, not on the display label derived from it. This separation is also the most suitable key for future PSS/E topology reconciliation (Phase 4), which will need to correlate a physical transformer to its two real switchyard connection points, not to a display label two unrelated transformers can share.

### Consequences

**Positive:** All three decisions extend this ADR's own `SubstationVoltageYard` connection-point pattern and `Circuit`'s own computed-name precedent consistently, rather than introducing a third, divergent convention for a second consuming entity. The uniqueness/short-name separation gives Phase 4's PSS/E reconciliation a stable physical key untangled from a display label that is expected to collide by design.

**Negative:** None identified — no data migration risk (new tables, no pre-existing rows), and no existing `Circuit`/`CircuitTerminal` behaviour is touched by this addendum.

---

## Addendum (2026-07-04): Transformer Registry — UAT Correction (Substation Ownership)

This addendum is additive; it supersedes Decision 3 of the addendum immediately above, and does not reopen Decisions 1–2 or this ADR's own original decision.

### Context

UAT on the Transformer Registry (the addendum above) found a workflow/data-model gap before acceptance: transformer creation exposed only two switchyard pickers, with no first-class substation context anywhere in the create workflow, list, or detail views. An engineer at a given substation had no way to answer "how many transformers are installed here" or "which transformer belongs to this substation" without indirectly inferring it from switchyard labels. Worse, nothing in the original design prevented a transformer's HV and LV switchyards from being selected at two different substations — the original Decision 3 uniqueness key (`hv_switchyard_id`, `lv_switchyard_id`, `transformer_number`) does not itself require the two switchyards to share a substation.

**Malaysian transmission/distribution domain rule, stated explicitly during UAT:** a transformer is installed within a single substation. It is never modeled as equipment connected between two different substations — unlike a `Circuit`, which by definition connects two (or more) substations.

### Decision

**`Transformer.substation_id` is added as a mandatory, first-class column** (not merely derivable by joining through a terminal's own `SubstationVoltageYard`). Both of a transformer's `TransformerTerminal` rows must resolve, via their `voltage_yard_id` → `SubstationVoltageYard.substation_id`, to this same `substation_id` — enforced at the service layer on creation (`EquipmentRegistryService._require_yard_belongs_to_substation`), checked before the same-switchyard and voltage-order checks so a cross-substation mismatch is reported precisely (naming the offending side and both substation mnemonics), not conflated with either of those other errors.

**Decision 3 of the addendum above is superseded:** uniqueness moves from `UNIQUE (hv_switchyard_id, lv_switchyard_id, transformer_number)`, enforced at the service layer only, to **`UNIQUE(substation_id, transformer_number)`, enforced as a real, single-table database constraint** — once `substation_id` is a column on `Transformer` itself, the physical transformer's identity no longer needs to span two child `TransformerTerminal` rows to be expressed, so CLAUDE.md §11.8's "enforce by the database where possible" applies cleanly, without the aliased-double-join workaround the original design required. The generated engineering short name (Decision 2, unchanged) remains a separate, computed, user-facing label — still not part of the uniqueness key, and still may legitimately collide across substations (e.g. two `SGT1`s).

Creation is also now **substation-first** in the frontend workflow: the user selects the substation before either switchyard, and both HV/LV switchyard pickers are filtered client-side to that substation's own switchyards, mirroring `CircuitCreatePage`'s existing per-voltage-level filtering pattern (§9 rule 6a's own precedent). `GET /api/v1/transformers` gained a `substation_id` filter, and `SubstationDetailPage` gained a "Transformers" section (reusing that filter) so "which transformers are installed here" is answered directly from a substation's own detail page — the specific UAT-reported requirement.

### Consequences

**Positive:** The corrected model matches the real Malaysian grid domain rule exactly (a transformer cannot span substations, structurally, not just by convention). Uniqueness enforcement is simpler and stronger (a real database constraint, not a service-layer-only cross-row check). Every read response (list and detail) now carries substation context directly, removing the need to infer it from terminal data. The fix required no new tables and no change to `TransformerTerminal`'s own shape (Decision 1 stands unchanged).

**Negative:** None identified — this correction was made before the Transformer Registry migration was ever committed to version control, so the migration was edited in place (no additional migration was needed) and no production data was affected. The three genuine architecture decisions from the addendum above (Decisions 1–2, and Decision 3's *shape*, just not its exact key) all stand.

---

## Addendum (2026-07-05): Transformer Registry — UAT Correction #2 (Numbering Model)

This addendum is additive; it supersedes the uniqueness decision made by the addendum immediately above, and does not reopen Decisions 1–2, this ADR's own original decision, or the substation-ownership correction (`Transformer.substation_id`, unaffected and unchanged).

### Context

UAT found that the substation-ownership correction above went one step too far: `UNIQUE(substation_id, transformer_number)` collapses every transformation level at a substation into one shared bay-number namespace. Real Malaysian grid practice numbers transformer bays *per transformation pair*, not per substation as a whole — a substation legitimately has a "Transformer Bay 1" on its 275/132kV pair *and a separate* "Transformer Bay 1" on its 132/33kV pair. The corrected constraint rejected the second one outright.

UAT also found the breaker-number suggestion formulas insufficient for the same underlying reason: they were keyed on voltage alone, but the correct formula depends on the transformation pair and terminal side, not the voltage in isolation. 132kV, for example, needs `{N}10` as the HV side of a 132/33, 132/22, or 132/11kV transformer, but `{N}80` as the LV side of a 275/132kV transformer — a per-voltage table cannot express this.

### Decision

**Uniqueness reverts to `(substation_id, hv_switchyard_id, lv_switchyard_id, transformer_number)`, enforced at the service layer** — the same shape as the original Decision 3 above, now additionally scoped by `substation_id` (redundant with the HV/LV pair for uniqueness purposes, since a switchyard belongs to exactly one substation, but kept for symmetry with the substation-ownership correction and because it is the natural first filter the query already needs). This is **not** re-expressed as a raw single-table database `UNIQUE` constraint: doing so would require denormalizing `hv_switchyard_id`/`lv_switchyard_id` onto `Transformer` itself, which was considered and rejected — it would reintroduce the exact two-winding-only assumption Decision 1 deliberately avoided baking into `Transformer`'s own column set (a future tertiary-winding phase would need a third denormalized column, defeating Decision 1's "zero migration to `Transformer` itself" benefit). The `uq_transformer_substation_number` database constraint is dropped (migration `0010_transformer_yard_pair`); no replacement single-table constraint is added.

The one-time single-table-constraint simplification the previous addendum made ("once `substation_id` is a column on `Transformer` itself, the physical transformer's identity no longer needs to span two child rows") is itself superseded: it is correct that the identity *can* be expressed without the two child rows once `substation_id` is present, but *should not be*, because the whole HV/LV pair — not just the substation — is part of what makes a transformer number locally meaningful. `substation_id` alone was too coarse a scope.

**Breaker-number suggestion formulas are re-specified as a mapping keyed by (HV nominal kV, LV nominal kV, side)**, replacing the previous per-voltage table:

| Transformation pair | HV side | LV side |
|---|---|---|
| 500/275kV | non-standard, no suggestion | `T{N}0` |
| 275/132kV | `H{N}0` | `{N}80` |
| 132/33kV | `{N}10` | `{N}T0` |
| 132/22kV | `{N}10` | `{N}T0` |
| 132/11kV | `{N}10` | `3{N}` |

Any transformation pair outside this table (e.g. one involving 230kV) has no suggestion — an intentional scope limit matching what was actually specified, not an inferred extrapolation. This remains a frontend-only display convenience (Business Rule 7, unchanged): the backend never validates or enforces breaker-number format, and the user may always override.

### Consequences

**Positive:** The corrected uniqueness key matches real Malaysian grid engineering practice exactly — a bay number is a designator local to one transformation pair, not one whole substation. The breaker-number convention now produces the numbers engineers actually expect for every side of every specified pair, rather than a value keyed on voltage alone. `TransformerTerminal`'s shape (Decision 1) is untouched, so this correction imposes no cost on a future tertiary-winding phase.

**Negative:** Uniqueness enforcement is once again a service-layer, cross-row check (an aliased double join on `TransformerTerminal`) rather than a raw database constraint, reversing the previous addendum's specific CLAUDE.md §11.8 simplification — accepted as the correct trade-off, since the alternative (denormalizing both switchyard ids onto `Transformer`) would have cost more architecturally (violating Decision 1's own rationale) than it would have gained. A breaker-number suggestion is now unavailable until *both* HV and LV switchyards are selected (previously, a suggestion could appear from either side alone) — a direct, accepted consequence of the formula now genuinely depending on the pair, not a regression to be worked around.
