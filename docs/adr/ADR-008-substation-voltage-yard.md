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

- **Status:** Accepted
- **Date:** 2026-07-06
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1, §8, §11.2, A5)
- **Depends on:** [ADR-006](ADR-006-connectivity-registry-vs-psse-topology-architecture.md), [ADR-007](ADR-007-canonical-engineering-reference-object.md)
- **Affects:** [docs/architecture/equipment-registry-module.md](../architecture/equipment-registry-module.md) §7.5–§7.7, §9 rule 6a (addendum below), §11 (`CircuitTerminal`'s connection point); `docs/architecture/substation-registry.md` (unaffected in ownership — see Decision); `backend/app/modules/equipment_registry/models.py` (`SubstationVoltageYard` gains optional `commissioning_date`/`latitude`/`longitude` metadata, Phase 3 UAT follow-up — no change to this ADR's ownership decision)

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
