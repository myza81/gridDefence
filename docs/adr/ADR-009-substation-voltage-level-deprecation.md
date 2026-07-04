# ADR-009: Deprecate `Substation.voltage_level_id`

- **Status:** Accepted
- **Date:** 2026-07-06
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1, §8, F1, F2, A2, A13)
- **Depends on:** [ADR-008](ADR-008-substation-voltage-yard.md)
- **Affects:** `docs/architecture/substation-registry.md` (deprecation note added, not rewritten); `backend/app/modules/substation_registry/*` (model/schemas/service/repository/router); `frontend/src/modules/substation_registry/*`; `frontend/src/modules/equipment_registry/pages/CircuitDetailPage.tsx` (addendum below — inline voltage yard creation removed)

---

## Context

ADR-008 introduced `SubstationVoltageYard` (owned by Equipment Registry) as the entity that actually represents "this substation has equipment terminating at this voltage level," and explicitly noted that Substation Registry's own `voltage_level_id` column was left untouched — "unaffected in ownership."

Phase 3 UAT follow-up found that leaving it untouched was itself now a consistency defect, not a neutral no-op:

1. `Substation.voltage_level_id` is still `NOT NULL` and still required on Substation Create, encoding an assumption — one substation, one voltage level — that ADR-008 already established is false for real substations (e.g. PKLG: 275kV and 132kV).
2. Substation List/Detail still render `voltage_level_id` as if it were the substation's one authoritative voltage, even though a substation may now hold zero, one, or several `SubstationVoltageYard` rows.
3. `voltage_level_id` is independently editable via `PATCH /substations/{id}`, with no relationship to `SubstationVoltageYard` at all — a substation's "primary" voltage level and its actual voltage yards can silently diverge.
4. The engineering fact this column was created to hold — "what voltage level is this substation at" — no longer has a single correct answer once a substation has more than one yard. A NOT NULL, single-valued column cannot express that fact for a multi-voltage substation; forcing an answer at creation time (before any yard may even be known) does not reflect engineering reality.

## Decision

`Substation.voltage_level_id` is **deprecated**, not removed:

- The database column stays, becomes **nullable**, keeps its FK to `voltage_level` (no data is destroyed — this preserves every row's original value for historical/administrative reference).
- It is **removed from the API contract entirely**: dropped from `SubstationCreate`, `SubstationUpdate`, `SubstationSummary`, `SubstationDetail`, and from the list-filter query parameter. The backend no longer reads, writes, or validates it through any live code path.
- Substation creation no longer asks for a voltage level. A newly created substation legitimately has zero voltage yards until one is added via the existing `POST /voltage-yards` workflow (ADR-008) — consistent with "a substation is never required to have more than one [yard]," now extended to "never required to have any at creation time."
- `SubstationVoltageYard` (ADR-008) becomes the sole authoritative representation of a substation's voltage level(s), for both List and Detail views.

**Why deprecate rather than drop the column outright:** the column is `NOT NULL`, indexed, FK'd, and referenced by existing historical `substation_audit_log` rows (`field_name = 'voltage_level_id'`) and by several existing tests exercising unrelated business rules. Dropping it is a larger, less reversible migration than this consistency fix requires, for no present benefit — nothing currently needs the column gone, only unused and non-authoritative. A future migration may drop it once no consumer (including ad-hoc reporting) depends on the legacy value; that is out of this ADR's scope.

**Why the frontend composes the List page's voltage-yard display client-side, not the backend:** Substation Registry is Master Data; `SubstationVoltageYard` is owned by Equipment Registry, one layer below Master Data in the domain hierarchy (CLAUDE.md §7). A backend join or service call from Substation Registry into Equipment Registry would invert the dependency direction CLAUDE.md A2/F2 explicitly forbid ("Substation Registry must never depend on UFLS, UVLS, or EMLS" generalizes to any dependent-domain module, including Equipment Registry's Network Data). The frontend already fetches `GET /api/v1/voltage-yards` from Equipment Registry elsewhere (`CircuitDetailPage`); the List and Detail pages do the same and group client-side — no backend module boundary is crossed.

## Consequences

**Positive:** Substation Create/List/Detail now reflect the same engineering model ADR-008 already established for circuit terminals — voltage level is a per-yard fact, not a per-substation fact. Removes a live data-integrity gap (item 3 above) rather than merely documenting it.

**Negative:** Existing `substation_audit_log` rows with `field_name = 'voltage_level_id'` remain (correctly, per CLAUDE.md §5.2 — history is never rewritten) but describe a field that can no longer be changed going forward; a reader must know this field is legacy. The Substation List page's former "filter by voltage level" capability is removed rather than reimplemented against voltage yards in this pass — no consumer of this project currently depends on it, and rebuilding it against a different owning module is a separate, later piece of work if requested.

## Alternatives Considered

- **Drop the column immediately.** Rejected: no functional requirement forces this now, and it is the least reversible option for a UAT-cycle fix; deferred to a future cleanup migration once nothing (including ad-hoc SQL reporting) still reads it.
- **Keep `voltage_level_id` required and auto-create a matching default `SubstationVoltageYard` on Substation Create.** Rejected: re-introduces exactly the single-voltage assumption this ADR removes, just automated instead of manual, and re-couples Substation Registry's create path to Equipment Registry's write path (forbidden dependency direction, CLAUDE.md A2).
- **Backend-side read model joining `Substation` and `SubstationVoltageYard` for List/Detail display.** Rejected for this pass: crosses the forbidden Master-Data-depends-on-Network-Data direction (CLAUDE.md A2/F2). CLAUDE.md F6 permits read-only cross-module joins for "reporting and dashboard read models," but that carve-out is for a genuinely separate reporting/dashboard surface, not for Substation Registry's own primary List/Detail views reaching into a lower-layer module's table.

---

## Addendum (2026-07-06): General Principle — Master Data Ownership Applies to Inline Creation

This addendum is additive; nothing above is revised.

### Context

`CircuitDetailPage` (Equipment Registry) contained a "Need a different voltage yard?" section that could create a new `SubstationVoltageYard` directly from within the Circuit module, in addition to the Substation Detail page's own add-voltage-yard workflow (which this ADR's main decision establishes as the authoritative one). Phase 3 UAT follow-up flagged this as the wrong place for that capability: `SubstationVoltageYard` is master topology data, and Circuit is a *consumer* of it, not an owner. The ownership hierarchy is:

```
Substation
    ↓
Voltage Yard
    ↓
Circuit
    ↓
Protection Scheme
```

Allowing a downstream module (Circuit) to create upstream master data (Voltage Yard) blurs module responsibility in exactly the direction CLAUDE.md A2/F2 already prohibits for *reading* dependencies, and sets a precedent that would compound badly as more topology entity types are added (busbars, bus couplers, transformers, disconnectors, reactors, capacitors) and as PSS/E topology import arrives — each would otherwise have its own excuse for an inline "just create it here too" shortcut in whichever downstream page needed it that day.

### Decision

**Master data entities are created and managed only within their owning module. Dependent modules may reference those entities but must not create or modify them inline, unless there is a compelling, explicitly documented workflow requirement.**

Concretely for this fix: the "Need a different voltage yard?" section (substation select, voltage level select, "Add voltage yard" button, and the mutation/query logic backing it) is removed from `CircuitDetailPage` entirely. Circuit pages read `SubstationVoltageYard` (via `GET /api/v1/voltage-yards`) but never call `POST /api/v1/voltage-yards`. Voltage yard creation remains exclusively on the Substation Detail page, per this ADR's main decision. When no suitable voltage yard exists for a circuit's terminal-selection dropdown, the Circuit UI shows static guidance text directing the user to the Substation Registry — never a creation shortcut, and not a navigation link either, keeping the boundary unambiguous rather than softened into "just one click away."

This principle generalizes to every future topology entity, not only `SubstationVoltageYard`: a Busbar page must not let a Bus Coupler page create busbars inline; a Transformer page must not let a Protection Scheme page create transformers inline; and so on, following the same ownership hierarchy. A future module that has a *genuinely* compelling reason to deviate (e.g. a true workflow wizard that provably cannot function otherwise) must document that specific exception in its own ADR — this is not a blanket prohibition on ever composing a creation step into another module's page, only a default that inline creation is not a UI convenience to reach for casually.

### Consequences

**Positive:** One workflow entry point per master data type, matching the "single source of truth" principle (CLAUDE.md §5.1) at the UI layer, not just the data layer. Removes a precedent that would otherwise be cited to justify inline creation for every future topology entity.

**Negative:** A user on the Circuit page who needs a voltage yard that doesn't exist yet must navigate to the Substation Registry manually — one extra step compared to the removed inline form. Judged acceptable: master data creation is comparatively rare (topology is mostly stable once established) relative to circuit creation/editing, and the removed form's own UAT history (Phase 3 UAT validation fix) shows inline creation forms are also where subtle validation/consistency defects accumulate fastest, since they duplicate logic that already exists in the owning module's page.
