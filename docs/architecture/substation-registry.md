# Substation Registry — Architecture Specification

Status: Draft v1
Owner: Solution Architecture
Scope: Master Data Management (MDM) module for GridDefence

> **Deprecation note (ADR-009):** this document's references to "voltage
> level" as a single static attribute of `Substation` (§2, §6, §7, §10) are
> superseded by [ADR-008](../adr/ADR-008-substation-voltage-yard.md)'s
> `SubstationVoltageYard`, owned by Equipment Registry, and
> [ADR-009](../adr/ADR-009-substation-voltage-level-deprecation.md)'s
> deprecation of `Substation.voltage_level_id`. A substation's voltage
> level(s) are now represented exclusively by its voltage yards (zero, one,
> or many); `Substation.voltage_level_id` remains in the database as
> nullable legacy data only and is no longer part of the API contract. The
> historical text below is left as-is per this project's immutable-history
> practice — read it as Phase 2's original design, not the current model.

---

## 1. Module Overview

The Substation Registry is a standalone Master Data Management (MDM) module that maintains the single, authoritative record of every substation relevant to grid defence engineering in Peninsular Malaysia.

It is deliberately **not** a load-shedding concept. UFLS, UVLS, and EMLS are *consumers* of substation identity, not owners of it. The Registry exists so that "what is this substation, where is it, who owns it, what is its current status" is answered exactly once in the system, and every other module — present or future — refers back to that single answer rather than re-describing it.

This mirrors standard MDM practice: identity and slowly-changing reference attributes live in one bounded context; every domain that needs that entity holds a stable reference (foreign key) to it, never a copy of its attributes.

```
Substation Registry  (MDM — identity & static attributes)
        │
        │ referenced by (FK, never copied)
        ▼
Scheme Assignments
        ├── UFLS
        ├── UVLS
        └── EMLS
        │
        └── (future) SPS/RAS, Black Start, Islanding, Restoration Planning, Analytics
```

---

## 2. Responsibilities

The Registry owns:

- Canonical identity of each substation (stable surrogate key, official name, mnemonic).
- Static and slowly-changing engineering attributes (voltage level, region, state, grid owner, coordinates, PSS/E bus number).
- Lifecycle/operational status of the substation as a physical asset (planned, active, decommissioned, etc.) — independent of any scheme's use of it.
- Uniqueness and validity rules for identifying attributes (mnemonic, name, bus number).
- A change/audit history of its own metadata, so that "what did we believe about substation X on date Y" is answerable.
- A read/query API that all other modules use to resolve, search, and display substation information.

The Registry explicitly does **not** own:

- Which scheme(s) a substation participates in, or with what parameters (stage, threshold, MW block, priority, etc.) — that belongs to the scheme module.
- Relay/protection settings, feeder-level load data, or SCADA real-time values.
- Network topology (which substations are electrically connected to which) — this is a natural future module (Network Topology) that itself references the Registry.

---

## 3. Scope and Non-Scope

**In scope**
- Substation identity, naming, and mnemonic management.
- Static engineering metadata: voltage level, region, state, grid ownership, PSS/E bus number, geolocation.
- Operational lifecycle status of the substation asset itself.
- Audit trail of metadata changes.
- Search/lookup API consumed by scheme modules and future modules.

**Non-scope (explicitly deferred to other modules)**
- Feeder / bay / equipment-level asset registry (transformers, breakers, CTs/VTs, relays). This is a natural future child module (`Substation Equipment Registry`) that references `substation_id`.
- Network connectivity / topology graph (transmission line linkage between substations).
- Scheme-specific configuration (UFLS stage assignment, UVLS thresholds, EMLS priority tiers, MW/MVAr blocks).
- Real-time telemetry, SCADA tags, historian data.
- Simulation/study case data (future Grid Analytics module).

---

## 4. Domain Model

**Aggregate root**
- `Substation` — the only entity external modules are allowed to reference. Everything else in this module is internal supporting detail.

**Supporting entities**
- `SubstationAuditLog` — append-only record of attribute changes to a `Substation` (who, when, what changed, old → new value). This is what protects Design Principle #4 (Historical Integrity).
- `SubstationAlias` (optional, recommended) — historical mnemonics/names a substation has held. Engineers routinely refer to old mnemonics in legacy reports; this prevents "lost" lookups after a rename without polluting the primary record.

**Reference (lookup) data** — modeled as small, independently managed tables rather than hardcoded enums, so new values can be added without a schema migration:
- `voltage_level` (e.g. 500kV, 275kV, 132kV, 66kV, 33kV, 11kV)
- `region` (planning regions, e.g. Northern, Central, Southern, Eastern)
- `state` (the 11 Peninsular Malaysia states + Federal Territories)
- `grid_owner` (TNB, and future IPP/third-party interconnection owners)
- `operational_status` (Planned, Under Construction, Active, Mothballed, Decommissioned, Retired)

**Value concepts (not separate tables, but validated as a unit)**
- Geolocation (`latitude`, `longitude`) — validated together, optional as a pair.
- Mnemonic — short, unique, immutable-by-policy engineering code.

**Relationship to consumer modules**

```
Substation (1) ────────── (0..*) SchemeAssignment[UFLS|UVLS|EMLS|future]
```

Scheme modules store `substation_id` (FK) plus scheme-specific attributes only. They never store substation name, coordinates, voltage, etc. — those are always resolved by joining/calling back to the Registry.

---

## 5. Entity Relationship Diagram (text form)

```
┌────────────────────────────┐
│        substation           │
│----------------------------│
│ PK substation_id (uuid)     │
│ UK mnemonic                 │
│    official_name            │
│ FK voltage_level_id ────────┼──────┐
│ FK region_id ────────────────┼────┐ │
│ FK state_id ──────────────────┼──┐ │ │
│ FK grid_owner_id ───────────────┼┐│ │ │
│ FK operational_status_id ───────┼┼┼─┼─┼──┐
│    psse_bus_number (uk, null) │ │││ │ │  │
│    latitude (nullable)        │ │││ │ │  │
│    longitude (nullable)       │ │││ │ │  │
│    commissioned_date (nullable)│││ │ │  │
│    remarks (nullable)          │││ │ │  │
│    created_at                  │││ │ │  │
│    updated_at                  │││ │ │  │
│ FK created_by_user_id (→ IAM)  │││ │ │  │
│ FK updated_by_user_id (→ IAM)  │││ │ │  │
└───────────┬─────────────┬──────┘││ │ │  │
            │             │        ││ │ │  │
            │1            │1       ││ │ │  │
            │             │        ││ │ │  │
      ┌─────▼──────┐ ┌────▼──────────┐ │ │  │
      │ substation │ │ substation_   │ │ │  │
      │ _audit_log │ │ alias         │ │ │  │
      │------------│ │---------------│ │ │  │
      │ PK log_id  │ │ PK alias_id   │ │ │  │
      │ FK subst.. │ │ FK subst..    │ │ │  │
      │ field_name │ │ alias_mnemonic│ │ │  │
      │ old_value  │ │ alias_name    │ │ │  │
      │ new_value  │ │ valid_from    │ │ │  │
      │ changed_at │ │ valid_to      │ │ │  │
      │ FK changed_by_user_id │ └───────────────┘ │ │  │
      └────────────────────────┘                    │ │  │
                                          │ │  │
      grid_owner ◄──────────────────────┘ │  │
      region     ◄────────────────────────┘  │
      state      ◄───────────────────────────┘
      voltage_level ◄── (joined above)
      operational_status ◄── (joined above)

                          │
                          │ referenced by (FK only, 1..*)
                          ▼
      ┌───────────────────────────────────────┐
      │   scheme_assignment (UFLS/UVLS/EMLS)   │
      │   — owned by scheme modules, NOT here  │
      │   FK substation_id → substation         │
      └───────────────────────────────────────┘
```

---

## 6. Recommended PostgreSQL Schema

```sql
-- Reference / lookup tables ---------------------------------------

CREATE TABLE voltage_level (
    voltage_level_id    SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    label                VARCHAR(20) NOT NULL UNIQUE,   -- e.g. '500kV'
    nominal_kv           NUMERIC(6,2) NOT NULL,
    sort_order           SMALLINT NOT NULL DEFAULT 0
);

CREATE TABLE region (
    region_id            SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code                 VARCHAR(20) NOT NULL UNIQUE,   -- e.g. 'NORTHERN'
    label                VARCHAR(50) NOT NULL
);

CREATE TABLE state (
    state_id             SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code                 VARCHAR(10) NOT NULL UNIQUE,   -- e.g. 'SEL', 'PRK'
    label                VARCHAR(50) NOT NULL
);

CREATE TABLE grid_owner (
    grid_owner_id        SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code                 VARCHAR(20) NOT NULL UNIQUE,   -- e.g. 'TNB'
    label                VARCHAR(100) NOT NULL
);

CREATE TABLE operational_status (
    operational_status_id SMALLINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    code                  VARCHAR(20) NOT NULL UNIQUE,  -- 'ACTIVE', 'PLANNED', ...
    label                 VARCHAR(50) NOT NULL,
    is_terminal           BOOLEAN NOT NULL DEFAULT FALSE -- e.g. RETIRED
);

-- Core aggregate ----------------------------------------------------

CREATE TABLE substation (
    substation_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mnemonic              VARCHAR(10) NOT NULL,
    official_name         VARCHAR(150) NOT NULL,

    voltage_level_id      SMALLINT NOT NULL REFERENCES voltage_level(voltage_level_id),
    region_id             SMALLINT NOT NULL REFERENCES region(region_id),
    state_id              SMALLINT NOT NULL REFERENCES state(state_id),
    grid_owner_id         SMALLINT NOT NULL REFERENCES grid_owner(grid_owner_id),
    operational_status_id SMALLINT NOT NULL REFERENCES operational_status(operational_status_id),

    psse_bus_number       INTEGER,
    latitude              NUMERIC(9,6),
    longitude             NUMERIC(9,6),
    commissioned_date     DATE,
    remarks               TEXT,

    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- created_by_user_id / updated_by_user_id reference IAM's user_id (ADR-002).
    -- Not free-text: identity is owned by the IAM bounded context, not by this module.
    created_by_user_id    UUID NOT NULL, -- REFERENCES iam.user(user_id), once IAM is implemented
    updated_by_user_id    UUID NOT NULL, -- REFERENCES iam.user(user_id), once IAM is implemented

    CONSTRAINT uq_substation_mnemonic UNIQUE (mnemonic),
    CONSTRAINT uq_substation_psse_bus UNIQUE (psse_bus_number),
    CONSTRAINT ck_substation_lat_range CHECK (latitude  IS NULL OR (latitude  BETWEEN -90  AND 90)),
    CONSTRAINT ck_substation_lon_range CHECK (longitude IS NULL OR (longitude BETWEEN -180 AND 180)),
    CONSTRAINT ck_substation_geo_pair  CHECK (
        (latitude IS NULL AND longitude IS NULL) OR
        (latitude IS NOT NULL AND longitude IS NOT NULL)
    )
);

CREATE UNIQUE INDEX uq_substation_mnemonic_ci ON substation (lower(mnemonic));
CREATE UNIQUE INDEX uq_substation_name_ci ON substation (lower(official_name));

CREATE INDEX ix_substation_region   ON substation (region_id);
CREATE INDEX ix_substation_state    ON substation (state_id);
CREATE INDEX ix_substation_voltage  ON substation (voltage_level_id);
CREATE INDEX ix_substation_owner    ON substation (grid_owner_id);
CREATE INDEX ix_substation_status   ON substation (operational_status_id);

-- Historical name/mnemonic tracking ---------------------------------

CREATE TABLE substation_alias (
    alias_id       BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    substation_id  UUID NOT NULL REFERENCES substation(substation_id) ON DELETE CASCADE,
    alias_mnemonic VARCHAR(10),
    alias_name     VARCHAR(150),
    valid_from     TIMESTAMPTZ NOT NULL,
    valid_to       TIMESTAMPTZ,
    CONSTRAINT ck_alias_has_value CHECK (alias_mnemonic IS NOT NULL OR alias_name IS NOT NULL)
);

CREATE INDEX ix_substation_alias_lookup ON substation_alias (alias_mnemonic);

-- Audit trail ---------------------------------------------------------

CREATE TABLE substation_audit_log (
    log_id         BIGINT PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    substation_id  UUID NOT NULL REFERENCES substation(substation_id),
    field_name     VARCHAR(100) NOT NULL,
    old_value      TEXT,
    new_value      TEXT,
    changed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- changed_by_user_id follows the same IAM reference principle as
    -- substation.created_by_user_id / updated_by_user_id (ADR-002).
    changed_by_user_id UUID NOT NULL, -- REFERENCES iam.user(user_id), once IAM is implemented
    change_reason  TEXT
);

CREATE INDEX ix_audit_substation_time ON substation_audit_log (substation_id, changed_at DESC);
```

Note: no `DELETE` privilege is granted at the application-role level on `substation` in normal operation — see §12.

---

## 7. Field-by-Field Explanation

| Field | Purpose | Notes |
|---|---|---|
| `substation_id` | Stable surrogate key | UUID, never reused, the only thing other modules reference |
| `mnemonic` | Engineering short code | Unique, case-insensitively; treated as immutable-by-policy (see §8) |
| `official_name` | Full descriptive name | Human-facing; unique to avoid ambiguity in reports |
| `voltage_level_id` | Nominal voltage class | FK to reference table, supports future voltage classes (e.g. HVDC) |
| `region_id` | Grid planning region | FK; used for regional reporting/filtering |
| `state_id` | Malaysian state | FK; administrative/geographic grouping |
| `grid_owner_id` | Asset owner | FK; TNB today, extensible to IPPs/third parties |
| `operational_status_id` | Lifecycle state of the physical asset | FK; independent from whether any scheme currently uses it |
| `psse_bus_number` | Power system model cross-reference | Optional; unique when present, links to PSS/E studies |
| `latitude` / `longitude` | Geolocation | Optional but validated as a pair and range-checked; enables map rendering (ECharts geo / future GIS) |
| `commissioned_date` | Engineering asset history | Recommended addition (see §"Additional Attributes" below) |
| `remarks` | Free-text notes | Engineering context that doesn't warrant a column |
| `created_at` / `updated_at` | Standard bookkeeping | Auto-managed |
| `created_by_user_id` / `updated_by_user_id` | Accountability | UUID FK referencing IAM's `user_id` (ADR-002) — not a free-text identity field. In transitional federation scenarios where the acting principal has not yet been provisioned as a local IAM user, the fallback `external_principal_id` + provider pattern defined in ADR-002 applies until the identity is resolved to a `user_id` |

**Recommended additional attributes beyond the minimum set**

- `commissioned_date` — when the substation entered service; useful for asset-age analytics and future reliability studies.
- `remarks` — free-text engineering notes (e.g. "shared busbar with X", "temporary configuration").
- `created_by_user_id` / `updated_by_user_id` — every MDM record needs an accountable actor, not just a timestamp, for audit and change-control purposes. These reference IAM's `user_id` rather than storing identity locally, per [ADR-002](../adr/ADR-002-identity-and-access-management.md) and the Core Platform ownership of identity described in [domain-model.md](domain-model.md).
- Consider (not included above to avoid premature scope): `iso_code` if GridDefence ever needs to interoperate with an external national asset registry; `time_zone` is unnecessary (single time zone country) so intentionally omitted.

---

## 8. Data Integrity Rules

1. **Mnemonic uniqueness & immutability-by-policy.** Mnemonic is unique (case-insensitive). It should not be silently reused after a substation is retired — retired mnemonics are never reassigned to a new physical substation, to avoid corrupting historical reports that reference the mnemonic as text. If a mnemonic must change, the old value is preserved in `substation_alias`.
2. **Name uniqueness.** `official_name` is unique (case-insensitive) to prevent ambiguous references in scheme documentation.
3. **PSS/E bus number uniqueness when present.** Enforced via a partial/standard unique constraint; `NULL` is allowed (not every substation is modeled in PSS/E, e.g. planned or non-transmission-level stations).
4. **Geolocation pair integrity.** Latitude and longitude must both be present or both be null — a partial coordinate is worse than none.
5. **Referential immutability of identity.** `substation_id` is never reused, never changed, and is the only value scheme modules are permitted to store as a foreign key.
6. **No back-writes from scheme modules.** UFLS/UVLS/EMLS modules have read-only access to `substation`; only the Registry's own service can write to it. This is enforced architecturally (service boundary) and can be reinforced at the DB role/grant level.
7. **Status transitions follow a defined, closed-list lifecycle** (see §10; [ADR-005](../adr/ADR-005-substation-operational-status-lifecycle.md)) — e.g. a substation cannot go directly from `Planned` to `Active`; it must pass through `Under Construction`. Only the seven transitions §10 enumerates are legal; every other transition, including `Planned → Decommissioned` in any number of hops other than the defined path, is rejected at the service layer.
8. **Every attribute change is audited.** Any update to a tracked field on `substation` produces a corresponding `substation_audit_log` row (via application-level service logic or a DB trigger — see §11).

---

## 9. Constraints and Indexes

- **Primary key:** `substation_id UUID` (generated, not user-supplied) — avoids merge collisions across environments and is safe for future distributed/replicated deployments.
- **Unique constraints:** `mnemonic` (case-insensitive), `official_name` (case-insensitive), `psse_bus_number` (when not null).
- **Check constraints:** latitude/longitude range and pairing, as shown in §6.
- **Foreign keys:** all reference-table FKs use `ON DELETE RESTRICT` (default) — a lookup value in use cannot be deleted out from under a substation record; reference tables are managed data, not user-deletable rows.
- **Indexes for query patterns:** region, state, voltage level, owner, and status are all indexed since these are the primary filter/search dimensions expected from scheme modules and the UI (TanStack Table filtering).
- **Future spatial index:** if map-based querying (radius search, bounding box) becomes a requirement, add PostGIS and a `GIST` index on a `geography(Point)` column rather than doing this prematurely with plain numeric lat/long.

---

## 10. CRUD Lifecycle

Status: v2 (revised by [ADR-005](../adr/ADR-005-substation-operational-status-lifecycle.md)) — v1's diagram omitted `Under Construction` entirely (despite it being seeded reference data since Phase 1) and showed no direct `Active → Decommissioned` edge. Both gaps are resolved below; see ADR-005 for the full rationale.

```
        ┌─────────┐
        │ Planned │  (registered ahead of commissioning; usable for
        └────┬────┘   forward-looking scheme planning)
             │ begin construction
             ▼
  ┌─────────────────────┐
  │ Under Construction   │  (physically being built; not yet in service)
  └──────────┬───────────┘
             │ commission
             ▼
        ┌─────────┐
   ┌───▶│ Active  │───────────────────┐
   │    └────┬────┘                   │
   │         │ mothball                │ decommission
   │         ▼                         │
   │    ┌───────────┐                  │
   └────┤ Mothballed├───decommission───┤
reactivate└─────┬─────┘                │
                │                      │
                └──────────┬───────────┘
                            ▼
                    ┌──────────────┐
                    │ Decommissioned│  (terminal for operational purposes,
                    └──────┬────────┘   but record is retained)
                           │ (optional, admin-only, rare)
                           ▼
                    ┌──────────┐
                    │ Retired  │  (fully closed record; still never
                    └──────────┘   hard-deleted if ever referenced
                                    historically)
```

**Allowed transitions (closed list — no other transition is legal):**

| From | To | Trigger |
|---|---|---|
| `Planned` | `Under Construction` | begin construction |
| `Under Construction` | `Active` | commission |
| `Active` | `Mothballed` | mothball |
| `Mothballed` | `Active` | reactivate |
| `Active` | `Decommissioned` | decommission |
| `Mothballed` | `Decommissioned` | decommission |
| `Decommissioned` | `Retired` | administrative closure (optional, admin-only, rare) |

Any transition not listed above — including `Planned → Active` directly, anything into or out of `Retired` other than the one edge shown, or any transition touching `Under Construction` other than the two edges shown — is illegal and must be rejected at the service layer (§8 rule 7).

- **Create:** always starts as `Planned` or `Active` (data migration/backfill case) — this is a *creation-time* exception, not a transition, and remains unchanged by ADR-005. A newly created row does not pass through `Under Construction`; only a status *change* on an existing row is validated against the transition table above. Requires mnemonic, name, voltage level, region, state, owner — geolocation and PSS/E bus number may be added later.
- **Read:** open to all authenticated modules/users; this is reference data, not sensitive.
- **Update:** metadata can be updated at any time; every update writes an audit log entry. Mnemonic changes are a special, gated operation (see §8, #1) requiring an alias record.
- **Status change:** validated against the transition table above; illegal transitions rejected at the service layer.
- **Delete:** never a hard delete in normal operation — see §12.

---

## 11. Versioning Considerations

The critical constraint (Design Principle #4) is: **changing substation metadata must never invalidate a historical scheme version.** This is achieved structurally, not by versioning the substation table itself:

- Scheme assignment records store `substation_id` (an immutable surrogate key) — never a copy of name/voltage/coordinates. The FK relationship itself is timeless: it doesn't matter that the substation's name changed in 2027, the FK to `substation_id` from a 2024 scheme version is still valid and still points at the same physical asset.
- The `substation` table itself is **not** append-only/versioned — it always holds the *current* truth. History of *what the truth used to be* lives separately in `substation_audit_log`. This keeps normal reads simple (no "as-of" filtering needed for 99% of consumers) while still making point-in-time reconstruction possible when needed (e.g. "what was this substation's grid owner when scheme version 3 was approved?" — answerable by querying the audit log for the timestamp of that scheme version).
- This is effectively a lightweight audit-log pattern rather than full SCD Type 2 on the main table. Full SCD Type 2 (validity date ranges directly on `substation`) is not recommended here — it would force every consumer query to filter by validity window, adding complexity that isn't justified unless a concrete requirement for "time-travel joins" emerges. The audit log gives the same historical answer on demand without that cost.
- If a future requirement needs an authoritative point-in-time snapshot bundled *with* a scheme version (e.g. for regulatory submission, where the exact substation attributes at approval time must be frozen and reproducible without depending on the audit log), that snapshot should be materialized and stored **by the scheme module** at the moment of scheme version approval — not by changing how the Registry itself models data. The Registry stays the single current source of truth; snapshotting-for-a-point-in-time is a concern of whoever needs the frozen copy.

---

## 12. Soft Delete vs Hard Delete Recommendation

**Recommendation: soft delete only, via lifecycle status — hard delete is disallowed by default.**

- A substation is retired by transitioning `operational_status` to `Decommissioned`/`Retired`, not by removing the row. This satisfies Design Principle #4 automatically: any scheme that historically referenced this substation continues to resolve its FK successfully.
- Enforce this at the database level: scheme assignment tables' FKs to `substation_id` use `ON DELETE RESTRICT`, so even an attempted hard delete of a referenced substation fails loudly rather than silently orphaning scheme data.
- Hard delete should be reserved for a narrow, admin-only, audited exception: correcting a genuine data-entry error (e.g. a duplicate substation created by mistake, never referenced by any scheme, never exposed externally). This should require explicit confirmation that zero references exist across all consuming modules (present and future) before being permitted, and itself should be logged (who, why, when) outside the normal audit table structure (e.g. a separate administrative action log), since the row being deleted won't exist to hold its own audit trail.
- Do **not** implement a generic `deleted_at`/`is_deleted` soft-delete flag in addition to `operational_status` — that would create two overlapping "is this substation gone" signals. Status *is* the soft-delete mechanism here; adding a redundant flag invites inconsistency.

---

## 13. API Boundary

The Registry is a bounded context with its own service layer and API surface, independent of scheme modules, even though it may be deployed as part of the same FastAPI application/monolith initially.

**Registry-owned API surface (conceptual, not implementation):**
- Create/update/retrieve a substation.
- Search/filter substations (by region, state, voltage level, owner, status, free-text on name/mnemonic).
- Retrieve a substation's audit history.
- Resolve one or many `substation_id`s to display attributes (used heavily by scheme modules for UI rendering — e.g. TanStack Table joins, map rendering via ECharts).
- Manage reference/lookup data (voltage levels, regions, states, owners, statuses) — likely an admin-only sub-surface.

**Boundary rules:**
- Scheme modules (UFLS/UVLS/EMLS) are **read-only consumers** of this API/data. They never write to `substation`, `substation_alias`, or the reference tables.
- Even within a single physical database, this boundary should be enforced logically at the service/repository layer (a `SubstationService` that only the Registry module code path may write through), and can optionally be reinforced with database roles/grants (scheme-module DB role has `SELECT` only on registry tables).
- Scheme modules resolve display data either by direct FK join (efficient, single-database case) or by calling the Registry's resolve/lookup API (if the modules are ever split into separate services). Designing the boundary this way now means a future move to separate microservices doesn't require redesigning the scheme modules' data access pattern — it only changes *how* the join happens, not *whether* scheme modules own substation data (they never do).

---

## 14. Future Extensibility

The schema and boundary are designed so the following can be added without touching the Registry's core identity model:

- **Substation Equipment Registry** (transformers, breakers, CTs/VTs, protection relays) — a new module with its own tables, each row FK'd to `substation_id`. Does not require changes to `substation` itself.
- **Network Topology module** — models transmission line connectivity between substations (a substation-to-substation graph). References `substation_id` on both ends of each line/link; does not duplicate substation attributes.
- **SPS/RAS, Black Start, Islanding, Restoration Planning** — each is structurally identical to how UFLS/UVLS/EMLS consume the Registry: a scheme-specific assignment table with a FK to `substation_id` plus scheme-specific parameters. No Registry changes needed to onboard these.
- **Grid Analytics / Simulation** — study cases can reference sets of `substation_id`s and, if needed, request point-in-time attribute snapshots via the audit log (§11) for reproducible study inputs.
- **GIS/mapping enhancement** — the existing nullable `latitude`/`longitude` pair can be upgraded to a PostGIS `geography` column later for spatial queries (radius search, containment) without breaking existing consumers, since the plain numeric columns can be kept in sync or migrated in a single pass.
- **Geographic expansion beyond Peninsular Malaysia** — because `region`, `state`, and `grid_owner` are reference tables rather than hardcoded enums/CHECK lists, extending coverage (e.g. Sabah/Sarawak, or a different owner/utility) is a data change, not a schema migration.
- **Backlog (recorded, not scheduled): a `decommissioned_at`-equivalent column.** `commissioned_date` (a nullable `DATE`) already exists (Phase 2) and records when a substation entered service, but there is no symmetrical column recording when it was decommissioned — that fact is currently only reconstructable indirectly, by querying `substation_audit_log` for the row where `field_name = 'operational_status_id'` and `new_value = 'DECOMMISSIONED'`. If a dedicated column becomes a real requirement (e.g. for reporting that shouldn't depend on parsing audit-log text), implementing it should also resolve a naming/precision inconsistency it would otherwise inherit: `commissioned_date` is `DATE`-precision, while every other timestamp column in this schema (`created_at`, `updated_at`, `changed_at`) is `TIMESTAMPTZ`-precision and `_at`-suffixed. That decision — whether to add `commissioned_at`/`decommissioned_at` as new `TIMESTAMPTZ` columns alongside (or replacing) `commissioned_date` — should be made explicitly at implementation time, not defaulted silently, since it affects an existing, already-shipped column.

---

## 15. Risks and Architectural Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| Mnemonic reuse after decommissioning | Historical reports/mnemonic-text references become ambiguous or wrong | Enforce policy: never reassign a retired mnemonic; preserve it via `substation_alias`; consider a DB-level check against a "retired mnemonics" set if this proves error-prone in practice |
| Scheme modules bypassing the boundary and writing directly to `substation` | Silent duplication/drift between Registry and scheme data, defeating the MDM purpose | Enforce at both service layer (code review discipline / module structure) and DB grants (scheme DB role has no `INSERT`/`UPDATE`/`DELETE` on registry tables) |
| Over-normalizing too early (e.g. building full PostGIS/topology support before it's needed) | Delays MVP delivery for speculative future needs | Ship with plain lat/long + reference tables now; defer PostGIS, equipment registry, and topology modules until a concrete module requires them — the schema already accommodates adding them later without rework |
| Geolocation data quality (missing or incorrect coordinates) | Weakens future map-based features (ECharts geo visualizations) | Keep optional at the schema level (not all legacy records will have coordinates on day one), but treat coordinates as a required field in the data-entry workflow/UI for newly created `Active` substations going forward |
| PSS/E bus number drift as power system models are re-numbered over study cycles | Stale or incorrect cross-references into simulation tooling | Keep as a single current-value optional field (not a full history) for now; if PSS/E model versioning becomes a real requirement, track bus number history the same way as other attributes — via the audit log, not a new versioned column |
| Treating `operational_status` as a stand-in for "does any scheme currently use this substation" | Confuses two different concepts: physical asset lifecycle vs. scheme participation | Keep these separate by design: a substation can be `Active` (physically in service) while having zero current scheme assignments, and scheme modules independently track their own "assignment active/inactive" state per scheme — the Registry's status is never used as a proxy for scheme participation |
| Hard-coding "Peninsular Malaysia" assumptions into the schema | Blocks future geographic expansion (Sabah/Sarawak, cross-border) | Already mitigated by modeling `region`/`state`/`grid_owner` as reference tables rather than fixed enums; avoid adding any CHECK constraint or application logic that assumes exactly 11 states |
