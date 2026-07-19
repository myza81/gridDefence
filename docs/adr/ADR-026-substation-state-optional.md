# ADR-026: State Is an Optional Substation Attribute

- **Status:** Accepted
- **Date:** 2026-07-18
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§4 Engineering Truth Before Software Convenience, §5.1 Single Source of Truth, §11 Database Standards, A13)
- **Affects:** [docs/architecture/substation-registry.md](../architecture/substation-registry.md) (§6 schema, §8, §10 — superseded by a status note, body left historical), `backend/app/modules/substation_registry/` (model, schemas, service), `backend/alembic/versions/0026_substation_state_optional.py`, `frontend/src/modules/substation_registry/`
- **Relates to:** [ADR-009](ADR-009-substation-voltage-level-deprecation.md) (voltage level moved off `Substation` — a prior refinement of what belongs on the Substation identity), the GM Zone metadata enhancement (which made `gm_zone_id` `NOT NULL`); this ADR moves in the opposite direction for State specifically, for the reason below.

---

## Context

`substation.state_id` was created `NOT NULL` (migration `0003_substation_registry`), grouped with `region_id`, `gm_zone_id`, and `grid_owner_id` as a mandatory reference-data attribute of every Substation. Creating or migrating a Substation therefore required a State.

The Project Owner identified this as an over-constraint. A GridDefence Substation's **engineering identity** is electrical and operational — its mnemonic, its voltage yards (ADR-008/009), its connectivity, its operational status. **State (the Malaysian state a substation sits in) is an administrative/geographic classification**, consumed as analytics-and-filtering metadata, never as a validation rule or an eligibility condition ([`scheme-data-consumption-matrix.md`](../architecture/scheme-data-consumption-matrix.md) §1 states this explicitly for Region/State/GM Zone/Grid Owner). Requiring an administrative label in order to record an engineering asset inverts the platform's own philosophy ("Engineering Truth Before Software Convenience", CLAUDE.md §4): the asset exists and is engineering-meaningful whether or not its administrative State has been determined yet.

This also surfaced concretely at the migration boundary: legacy records with no resolvable State were being deferred from migration solely because GridDefence rejected a null State (the Legacy Migration Workbench's own `DEFERRED_MISSING_STATE` classification), even though those records are otherwise complete, valid engineering assets.

## Decision

**`substation.state_id` becomes optional (nullable). State remains fully supported — it is simply no longer required.**

- **Database:** `substation.state_id` is relaxed from `NOT NULL` to nullable (migration `0026_substation_state_optional`). The FK to `state(state_id)` (`ON DELETE RESTRICT`) and the `ix_substation_state` index are unchanged. No existing row is modified; no placeholder or "Unknown" State is introduced.
- **Create:** State may be omitted entirely, or supplied. When supplied it is validated against reference data exactly as before; when omitted it is stored as `NULL`.
- **Update:** State may be added to a substation that lacks one, changed, or **cleared** (set back to `NULL`) — each an ordinary, audited field change. Clearing is expressed as an explicit `null` in the PATCH payload, distinct from omitting the field (which leaves it unchanged), mirroring the existing sentinel treatment of other genuinely-nullable fields (`psse_bus_number`, geolocation).
- **API responses:** the `state_id` field is always present in `SubstationSummary`/`SubstationDetail`, and is `null` when no State is assigned. No response shape changes beyond nullability.
- **Filtering:** filtering by a specific `state_id` continues to work unchanged; a substation with `state_id IS NULL` simply does not match a specific-State filter. No "unknown/none" filter bucket is invented.
- **Scope boundary:** `region_id`, `gm_zone_id`, and `grid_owner_id` remain `NOT NULL`. This ADR makes **State alone** optional, because State alone is the purely administrative label in that group — Region (grid-planning grouping), GM Zone (maintenance responsibility), and Grid Owner (asset ownership, and the one field a scheme rule actually reads — the excluded-ownership check) each still carry current engineering or governance weight that this ADR does not reassess.

No other engineering behaviour changes.

## Rationale

**State is not part of engineering identity, so requiring it violates the platform's own layering.** CLAUDE.md §4 puts engineering correctness ahead of software convenience; `scheme-data-consumption-matrix.md` §1 already classifies State as metadata "never a validation rule." Making it mandatory was the software-convenience position (uniform NOT NULL columns), not the engineering-truth position. Optionality realigns the schema with the documented meaning of the field.

**Nullable is the honest representation of "not yet determined," and the only one that avoids fabricating engineering data.** The rejected alternatives all require inventing a value the engineer did not supply — a sentinel "Unknown" State row, or inferring State from Region. Both would write a fact into the permanent record that no one asserted (CLAUDE.md §5.1 / §5.2), and inference would additionally couple two fields the Project Owner has kept deliberately independent. `NULL` records exactly what is true: no State has been assigned.

**A loosening migration is safe and preserves history.** Relaxing `NOT NULL` touches no existing data — every current substation keeps its State — and needs no backfill. The reverse (re-tightening) is intentionally left as a migration that would fail against any legitimately-null row, because reimposing the constraint is a data decision, not a mechanical one.

## Consequences

**Positive:**
- The schema matches the documented engineering meaning of State (administrative metadata, not identity).
- Substations can be recorded before their administrative State is known, and corrected later — no blocked creation, no placeholder data.
- Legacy records previously deferred solely for a missing State become eligible for migration with no importer or payload change required on GridDefence's side (the API now accepts an omitted or null State).
- Existing queries, filters, and every substation that already has a State are entirely unaffected.

**Negative / trade-offs:**
- `state_id` is now nullable in API responses; any consumer that assumed non-null must tolerate `null` (within GridDefence, only the Substation Registry frontend read it, and it now renders "—"). No scheme module reads `substation.state_id`.
- The `downgrade` of migration `0026` cannot succeed if any substation has a null State by then — an accepted, explicit limitation (a re-tightening would require a Project Owner data decision), never worked around with a silent placeholder.
- `substation-registry.md`'s §6/§8/§10 still describe State as mandatory; per this project's immutable-history documentation practice these are left as-is and superseded by a status note pointing here, exactly as the GM Zone enhancement was handled.

---

## Alternatives Considered

1. **Make `state_id` nullable, State fully supported but optional — as decided above.** **Adopted.** Matches the field's documented meaning, preserves all existing data, requires no fabricated values, and unblocks stateless engineering records.

2. **Keep State mandatory; seed an "Unknown"/"Unassigned" State row and default to it.** **Rejected.** Writes a value no engineer asserted into the permanent record (CLAUDE.md §5.1/§5.2), pollutes State analytics and filters with a non-State bucket, and merely disguises "no State" as a fake State — the opposite of engineering truth.

3. **Keep State mandatory; infer it from Region.** **Rejected.** Region and State are deliberately independent attributes (no FK, constraint, or derivation couples them — the same independence the GM Zone enhancement was careful to preserve); inference would invent that coupling and could assign a wrong State no one chose.

4. **Make Region, GM Zone, and Grid Owner optional too, for uniformity.** **Rejected as out of scope and not engineering-justified.** Each of those still carries current engineering or governance weight (Grid Owner is even read by a scheme eligibility rule); this ADR reassesses only State, the one purely-administrative label, and does not loosen constraints the Project Owner has not identified as over-constraints.
