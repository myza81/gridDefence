# ADR-028: Transformer Engineering Endpoint Architecture

- **Status:** Accepted
- **Date:** 2026-07-18
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1 Single Source of Truth, §11 Database Standards, §11.3 Reference Data, §11.8 Constraints, §21 Premature Generality, A6, A13)
- **Realizes:** [EDR-011](../engineering/edr/EDR-011-transformer-engineering-interface-model.md) (the ratified engineering meaning of transformer classification and Transformer Terminal endpoints — authoritative; this ADR decides only the software architecture that expresses it)
- **Depends on / builds upon:** [EDR-005](../engineering/edr/EDR-005-bay-as-engineering-identity.md) (a Transformer Bay's durable engineering identity is the `TransformerTerminal` — the stable anchor this ADR relies on), [ADR-008](ADR-008-substation-voltage-yard.md) (`SubstationVoltageYard` as the terminal connection point — the existing Registered endpoint), [EDR-007](../engineering/edr/EDR-007-phase-7-operational-identity-mapping.md)/[EDR-001](../engineering/edr/EDR-001-psse-as-operational-context.md) (Layer 2 operational topology, kept separate)
- **Affects:** [docs/architecture/equipment-registry-module.md](../architecture/equipment-registry-module.md) (Phase 3.5 Transformer Registry — Transformer Terminal model, uniqueness rule, voltage-order rule; a forward-pointer status note is added there, body left as historical per that document's own practice). **No code, schema, migration, API, or frontend is created or changed by this ADR** — it is the decision that a subsequent implementation phase will build against.

---

## Context

[EDR-011](../engineering/edr/EDR-011-transformer-engineering-interface-model.md) ratified that a transformer's engineering classification is the interface between electrical-system domains (never voltage ratio), and that a **Transformer Terminal interfaces an Engineering Endpoint** — either a **Registered Engineering Endpoint** (a GridDefence-owned object; today a Transmission Voltage Yard, `SubstationVoltageYard`) or a **Typed Engineering Endpoint** (a recognised engineering system not yet held in its own first-class registry: Distribution System, Generation Collector System, Station Auxiliary System, Customer Installation).

The as-built Transformer Registry (`equipment-registry-module.md` Phase 3.5 Addendum) requires **both** `TransformerTerminal` rows to resolve to a registered `SubstationVoltageYard` at the transformer's own substation (`EquipmentRegistryService.create_transformer`). This correctly expresses Inter-bus and Load transformers (both windings are transmission/grid switchyards) but **cannot express GSU, SST, or CST**, whose non-grid winding interfaces a system that is not a registered Voltage Yard. Per EDR-011 §3, this is a Layer-2 operational-connectivity assumption leaking into a Layer-1 engineering-identity model.

This ADR decides how a `TransformerTerminal` represents an Engineering Endpoint, while preserving existing transformer records, existing GridDefence workflows, existing ALSF capability/assignment relationships (which reference `transformer_terminal_id`), clear Layer 1 ownership, a credible future path for Generation/Customer/Distribution/Auxiliary registries and PSS/E correlation, auditability, and a backward-compatible migration.

## Decision

**A Transformer Terminal carries a discriminated Engineering Endpoint directly on the terminal (Option 1, hardened). The endpoint is described by a curated `endpoint_kind`, plus a mutually-exclusive representation: a Registered endpoint keeps its direct `SubstationVoltageYard` foreign key; a Typed endpoint carries its own nominal voltage level and an optional label. No dedicated Engineering Endpoint entity is introduced now.**

### 1. Endpoint representation on `TransformerTerminal` (Part A → Option 1)

Conceptually (final DDL is for the implementing phase, not this ADR):
- **`endpoint_kind`** — a curated, reference-data-backed enumeration (a small Core Platform lookup, in the shape of `line_type`/`voltage_level`, per CLAUDE.md §11.3), initial values: `TRANSMISSION_VOLTAGE_YARD`, `DISTRIBUTION_SYSTEM`, `GENERATION_COLLECTOR_SYSTEM`, `STATION_AUXILIARY_SYSTEM`, `CUSTOMER_INSTALLATION`. Reference-data, not a hardcoded CHECK, precisely because EDR-011 anticipates further kinds (and future registries) — a new kind is then a data change, not a schema migration.
- **Registered representation** (`endpoint_kind = TRANSMISSION_VOLTAGE_YARD`): the existing **`voltage_yard_id`** FK to `SubstationVoltageYard` (unchanged). The endpoint's identity, nominal voltage, and substation are all resolved from that yard — no wrapper is added over an object that already bears identity.
- **Typed representation** (any other `endpoint_kind`): `voltage_yard_id` is `NULL`; the terminal instead carries **`endpoint_nominal_voltage_level_id`** (FK to the `voltage_level` reference) and an optional free-text **`endpoint_label`**. The nominal voltage is required for typed endpoints because there is no yard to derive it from, and it is what the voltage-order rule (below) needs.
- **A mutual-exclusion `CHECK`** enforces exactly-one valid representation per kind — `(endpoint_kind = 'TRANSMISSION_VOLTAGE_YARD' AND voltage_yard_id IS NOT NULL AND endpoint_nominal_voltage_level_id IS NULL) OR (endpoint_kind <> 'TRANSMISSION_VOLTAGE_YARD' AND voltage_yard_id IS NULL AND endpoint_nominal_voltage_level_id IS NOT NULL)` — mirroring the established XOR-CHECK precedent already used for ALSF's own polymorphic target (`automatic_load_shedding_functionality/models.py`, `target_type` + `circuit_terminal_id` XOR `transformer_terminal_id`). This prevents invalid/ambiguous states (CLAUDE.md §11.8).

The `TransformerTerminal` primary key, `side` (`HV`/`LV`), `breaker_number`, and audit columns are **unchanged**, so `transformer_terminal_id` remains the stable identity every other module (ALSF, network model, PSS/E correlation) already references.

### 2. Typed endpoints have no independent durable identity yet (Part B)

A **Typed Engineering Endpoint is terminal-scoped descriptive-plus-structural data, not a reusable, independently-referenced object.** It gets no dedicated identity, no lifecycle of its own, and no separate audit log; changes to it are audited on the owning terminal's existing audit trail. It is **not shared** across transformers today.

- The **stable identity anchor is the `TransformerTerminal` itself** ([EDR-005](../engineering/edr/EDR-005-bay-as-engineering-identity.md)), not the endpoint. A transformer's Layer 1 identity does not depend on a separate endpoint object existing.
- **Reuse, shared identity, lifecycle, and independent auditability of a typed system are deferred to the future first-class registry** that will legitimately own that system (a Generation Registry for a collector system, a Customer/Sensitive Customer Registry for a customer installation, an auxiliary registry for a station auxiliary system). Modelling "the collector bus" or "the auxiliary board" as a shared object now would be premature generality (CLAUDE.md §21) and would invent an enterprise-asset model the Transformer Registry does not need — exactly the discipline `equipment-registry-module.md` §7.1 already applied when it declined to build a generic `Equipment` backbone "until a second equipment type actually needs it."
- **Scope:** a typed endpoint is meaningful only in the context of its owning terminal (and, transitively, that terminal's substation). It is neither substation-registered nor globally registered — it is a described interface, not a registered node.

### 3. Registered vs Typed, and the transition path (Part C)

- **Registered Engineering Endpoint:** `endpoint_kind = TRANSMISSION_VOLTAGE_YARD`, backed by a `SubstationVoltageYard`. This is the only Registered kind today; every existing transformer terminal is of this kind after migration.
- **Typed Engineering Endpoint:** `endpoint_kind ∈ {DISTRIBUTION_SYSTEM, GENERATION_COLLECTOR_SYSTEM, STATION_AUXILIARY_SYSTEM, CUSTOMER_INSTALLATION}`, backed by `endpoint_nominal_voltage_level_id` (+ optional `endpoint_label`).
- **Transition (Typed → Registered when a future registry appears):** additive and backward-compatible. When, say, a Generation Registry is introduced, a new **nullable** FK (e.g. `generation_collector_id`) is added, the relevant typed rows are backfilled by linking to newly-created registry objects, and that kind's representation becomes registry-backed — following the repo's established "add a nullable column, backfill, tighten later" migration discipline (e.g. the GM Zone rollout). **The terminal identity, the transformer's engineer-asserted classification, and every ALSF/scheme reference are untouched by this transition** — only the endpoint's *backing* is upgraded from a typed description to a registry reference. Endpoint identity is therefore stable across the transition because the identity was never the endpoint's to begin with; it is the terminal's.

### 4. Classification stays engineer-asserted and separate from endpoints (EDR-011 §8, §10)

- Transformer **classification** (Inter-bus / Load / GSU / SST / CST) is a **distinct, engineer-asserted attribute** of the transformer, promoted from today's free-text `transformer_type` to a **curated reference-data vocabulary** (same reference-data shape as `endpoint_kind`). It is **never silently derived from, nor overwritten by, `endpoint_kind`** (EDR-011 §8).
- The architecture **permits an optional, service-layer consistency check** between classification and endpoint kinds (e.g. advising when a GSU's non-grid endpoint is not a Generation Collector System) that **never rewrites** the classification. Whether such a check is advisory or blocking is an implementation/policy detail deferred to the implementing phase.
- **Classification remains independent of GridDefence application usage** (EDR-011 §10). Scheme participation continues to be expressed only through ALSF capability + assignment against a terminal; classification never implies eligibility. GSU/SST/CST are registry-only assets initially and are ignored by defence-scheme workflows naturally (no ALSF capability, no assignment).

### 5. Generalized invariants

- **Voltage order:** the existing rule (grid side = HV, HV nominal > LV nominal) is preserved, now evaluated using each terminal's endpoint nominal voltage — from the `SubstationVoltageYard` for a Registered endpoint, or from `endpoint_nominal_voltage_level_id` for a Typed endpoint. All five classifications satisfy "grid side is the higher voltage."
- **Same-substation constraint, generalized:** the **grid-side (Registered Voltage Yard) terminal** must still belong to the transformer's substation; the **non-grid (Typed) terminal** carries no substation-yard constraint (it is a typed system, not a registered yard).
- **Uniqueness, generalized:** the current key `(substation_id, hv_switchyard_id, lv_switchyard_id, transformer_number)` generalizes to an **endpoint pair** — each terminal contributes its `voltage_yard_id` when Registered, or `(endpoint_kind, endpoint_nominal_voltage_level_id)` when Typed — still enforced at the service layer (cross-row check), consistent with the Phase 3.5 UAT-correction-#2 design.

### 6. Layer separation and PSS/E (EDR-011 §9)

This is entirely a **Layer 1** decision. Layer 2 (Operational Snapshot / PSS/E `TopologyTransformer`) ownership is unchanged; correlation stays a comparison, never an ownership transfer. Typed endpoints will give GSU/SST/CST a Layer-1 anchor that future correlation *may* use (a GSU to a Layer-2 generator pattern; a CST/SST to a Layer-2 load), but **how PSS/E correlation consumes the endpoint model is explicitly deferred** to a later decision.

### 7. Three-winding extensibility (not designed here)

`side` is already a CHECK-extensible string, and the endpoint is per-terminal, so a future third winding is an additive terminal with its own Engineering Endpoint — no reshaping of `Transformer`. This ADR does not design three-winding support (EDR-011 §11); it only confirms the endpoint model does not preclude it.

## Rationale

**Option 1 keeps the Registered case exactly as it is, which is correct because a `SubstationVoltageYard` already bears identity.** Wrapping it in a generic endpoint entity (Options 2/4) adds an indirection layer over an object that is already a first-class, audited, lifecycle-managed registry node — redundant, and contrary to "introduce only what is genuinely different" (`scheme-future-extensibility.md` §6) and CLAUDE.md §21. Existing transformer terminals migrate to `endpoint_kind = TRANSMISSION_VOLTAGE_YARD` with their `voltage_yard_id` untouched — the lightest possible, fully backward-compatible migration, preserving every existing record, workflow, and ALSF reference.

**The Typed case needs description, not identity, today — and Option 1 provides exactly that, no more.** EDR-011 established that a typed endpoint is a candidate to become registered *later*. The durable, shared identity of a generation collector or customer installation rightly belongs to the future registry that owns that domain, not to a speculative endpoint table built now and half-deprecated when the real registry arrives. Because the terminal is the stable anchor (EDR-005), the future transition is a clean additive migration (new nullable FK + backfill) that never disturbs transformer or ALSF references. This is the same "defer the backbone until a second consumer needs it" reasoning `equipment-registry-module.md` §7.1 already applied to `Equipment`.

**A discriminated single-table endpoint with an XOR CHECK is the shape this codebase already trusts.** ALSF's polymorphic target (`target_type` discriminator + XOR-constrained FKs on one table) is the established, working precedent for "this row points at one of several kinds of thing." Reusing that shape keeps the model relationally sound (no orphan states), auditable (the terminal's own audit log), queryable/reportable (one row, no joins to reconstruct an endpoint), and PostgreSQL/SQLAlchemy-maintainable (no new entity, no new audit log, no join explosion).

**Reference-data-backed `endpoint_kind` and `transformer classification` fit CLAUDE.md §11.3.** Both are curated, expandable engineering vocabularies (new endpoint kinds, future classifications), so a reference table — not a hardcoded enum — is the correct mechanism, consistent with `line_type`/`voltage_level`/`gm_zone`. Keeping classification a separate engineer-asserted reference value (not derived from `endpoint_kind`) directly honours EDR-011 §8.

## Consequences

**Positive:**
- Removes the Layer-2 leakage (EDR-011 §3): GSU/SST/CST become expressible without pretending a non-grid system is a Voltage Yard and without losing that it is not one.
- Fully backward-compatible: existing terminals migrate to a Registered endpoint with their `voltage_yard_id` unchanged; existing GridDefence workflows, ALSF capability/assignment, and PSS/E correlation are unaffected (terminal identity unchanged).
- Scoped to what Transformer Registry needs (Part B) while preserving a credible, additive future path to Generation/Customer/Auxiliary registries and to PSS/E correlation — no generic "anything points anywhere" model.
- Keeps classification engineer-asserted and independent of usage, as EDR-011 requires; three-winding remains reachable additively.

**Negative / trade-offs:**
- A typed endpoint's data is duplicated per terminal (two parallel GSUs on one collector each describe it independently); the shared-object view is deferred to a future registry. Accepted deliberately — that shared identity is not a Transformer Registry concern today.
- Introduces, for the first time, transformer terminals that do not resolve to a GridDefence object; the same-substation and uniqueness rules are generalized accordingly (§5), a modest service-layer change the implementing phase must make carefully.
- Classification remaining engineer-asserted (not derived) permits a classification inconsistent with its endpoints until the optional consistency check exists (§4) — a deliberate trade-off favouring engineer intent (EDR-011 §8).
- `equipment-registry-module.md`'s Phase 3.5 text still describes both terminals as Voltage Yards; per that document's own immutable-history practice it is left as-is and superseded by a forward-pointer status note to this ADR.

## Alternatives Considered

1. **Embedded discriminated endpoint on `TransformerTerminal` (Option 1), as decided.** **Adopted.** Lightest backward-compatible migration; keeps the Registered case (a `SubstationVoltageYard` that already has identity) unwrapped; provides exactly the description a Typed endpoint needs today; reuses the trusted ALSF XOR-CHECK shape; preserves the terminal as the stable identity anchor for a clean future transition.

2. **Dedicated Engineering Endpoint entity (Option 2)** — every terminal references a separate `engineering_endpoint` row (registered-backed, typed, or future-registry-backed). **Rejected (now).** For the Registered case it adds a redundant indirection over `SubstationVoltageYard`, which already bears identity/lifecycle/audit. It forces a heavier migration (an endpoint row per existing terminal) and a new entity + audit log before any consumer needs shared endpoint identity — premature generality (CLAUDE.md §21). Its one genuine advantage (shared, durable typed-endpoint identity) is not required today and is better provided by the future domain registry, to which Option 1 transitions cleanly.

3. **Polymorphic references — `endpoint_kind` + multiple nullable FKs to different owning tables (Option 3).** **Rejected.** The typed domains have no tables to point at, so this collapses to a set of mostly-null FKs — the exact "three-way nullable-foreign-key XOR" anti-pattern `equipment-registry-module.md` §7.1 explicitly criticizes. It maximizes orphan/ambiguity risk and adds no capability over Option 1. (Polymorphism was not adopted merely because the discovery used the word.)

4. **Hybrid — dedicated identity for Typed endpoints only, Registered kept as a direct yard FK (Option 4).** **Rejected (now).** Better than Option 2 for the Registered case, but it still builds a typed-endpoint identity table before a consumer needs shared identity, and that table would be partially superseded the moment a real domain registry arrives — more churn than Option 1's additive "add a nullable FK when the registry exists" path. Reconsider only if a concrete near-term need to reference one typed system from multiple transformers emerges before any domain registry does.

---

## Deferred to a subsequent implementation phase (not decided here)

Final DDL/ORM shapes; the exact `endpoint_kind` and classification reference-table seed and the migration of existing free-text `transformer_type` values; the precise generalized uniqueness tuple and its service-layer check; whether the classification↔endpoint consistency check is advisory or blocking; frontend endpoint-selection UX; three-winding representation; and how PSS/E correlation consumes the endpoint model. These are implementation decisions this ADR deliberately leaves open.

**Implementation blueprint:** the sequenced, sprint-by-sprint plan realizing this ADR is [docs/architecture/transformer-engineering-endpoint-implementation-spec.md](../architecture/transformer-engineering-endpoint-implementation-spec.md). That plan re-opens one item for confirmation — it recommends `endpoint_kind` be a `CHECK`-constrained enumeration rather than the reference-data table stated in §1 above (an intrinsic structural discriminator whose new values require service logic, not a pure data change); adopt whichever this document is amended to, or confirm the plan's recommendation, before implementation begins.
