# GridDefence Domain Model

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) (v1.1), particularly §5.1 (Single Source of Truth), §7 (Domain Hierarchy), §8 (Domain Ownership), A2 (Dependency Direction), and A4 (Audit Ownership).

This document describes GridDefence's domains conceptually. It does not define database schemas, API contracts, or module-internal detail — those live in each module's own architecture document (e.g. [substation-registry.md](substation-registry.md)).

---

## 1. Domain Hierarchy

CLAUDE.md §7 defines the engineering information flow as:

```
Master Data
    ↓
Reference Data
    ↓
Network Data
    ↓
Scheme Data
    ↓
Operational Data
    ↓
Audit Data
    ↓
Reporting & Analytics
```

For dependency purposes, CLAUDE.md A2 gives the concrete, authoritative rule: a **dependent** domain may reference a **foundational** domain; a foundational domain must never depend on a dependent domain (e.g. Scheme Data may depend on Master Data; Master Data must never depend on Scheme Data).

Applying that rule concretely across all layers: Reference Data (lookup tables) is foundational to Master Data, since master entities hold foreign keys into reference tables (CLAUDE.md §11.3). Master Data is in turn foundational to Network Data and Scheme Data. Operational Data builds on Scheme Data. Audit Data and Reporting & Analytics sit on top of all of them, consuming their history without ever being depended upon in return.

This document groups those layers into six working **domains** for documentation and module-organisation purposes:

| Domain (this document) | Corresponds to (CLAUDE.md §7 layer) |
|---|---|
| Core Platform | Reference Data + Identity and Access Management |
| Master Data | Master Data |
| Network Model | Network Data |
| Defence Scheme | Scheme Data + Operational Data |
| Audit and Analytics | Audit Data + Reporting & Analytics |
| Presentation | *(not part of the engineering data hierarchy — the consuming UI layer)* |

Dependency flows strictly left-to-right / top-to-bottom through this grouping: **Core Platform → Master Data → Network Model → Defence Scheme → Audit and Analytics**, with **Presentation** consuming all of them through backend APIs. No domain depends on a domain to its right.

---

## 2. Core Platform Domain

**Purpose:** Cross-cutting, foundational data and concerns that every other domain relies on but that belong to no single scheme or asset.

**Owns:**
- Reference/lookup data: voltage levels, regions, states, grid owners, operational statuses, and any future controlled vocabulary (CLAUDE.md §11.3). These use SMALLINT/INTEGER surrogate keys, not UUIDs (CLAUDE.md A5).
- **Identity and Access Management (IAM)** — accepted as a Core Platform bounded context under [ADR-002](../adr/ADR-002-identity-and-access-management.md). IAM owns the "who" behind every audit record and approval (CLAUDE.md §5.4, A4, A10):
  - Users
  - Roles
  - Permissions
  - External identity mappings (federated `external_principal_id` + provider metadata, for future LDAP/AD/SSO/OIDC integration)
  - The application authorization model (role-permission and user-role assignments)

  Every other module references IAM's stable internal `user_id` for audit "who" fields and authorization checks, rather than implementing its own notion of identity (CLAUDE.md §5.1, A1; see [ADR-002](../adr/ADR-002-identity-and-access-management.md)).

**References:** nothing — this is the most foundational domain in the platform.

**Referenced by:** every other domain.

**Does not own:** any entity specific to a single physical asset or a single scheme.

---

## 3. Master Data Domain

**Purpose:** Master Data Management (MDM) for physical/engineering assets. Single source of truth for asset identity.

**Owns (today):**
- **Substation Registry** — substation identity, mnemonic, official name, metadata, geography, operational status. See [substation-registry.md](substation-registry.md) for full detail.

**Owns (future, if introduced):** any additional master asset registries (e.g. an equipment/bay-level registry), each as its own module within this domain, following the same ownership pattern as the Substation Registry.

**References:** Core Platform reference data (voltage level, region, state, grid owner, operational status) via foreign key.

**Referenced by:** Network Model, Defence Scheme, Audit and Analytics, Presentation.

**Does not own:** scheme assignment logic or parameters (owned by Defence Scheme), network connectivity (owned by Network Model).

---

## 4. Network Model Domain *(future — scope reserved)*

**Purpose:** Models physical/electrical connectivity between substations (transmission line topology), independent of any scheme's use of that topology.

**Owns (future):** network topology / connectivity records — e.g. a transmission line entity referencing a substation at each end.

**References:** Master Data (the substations at each end of a connection) via foreign key. Never duplicates substation attributes.

**Referenced by:** Defence Scheme (e.g. islanding boundary definitions, restoration planning sequencing), Audit and Analytics.

**Does not own:** substation identity, scheme logic.

**Status:** Not yet implemented. Reserved so that when a Network Topology module is built, it has a clear place in the hierarchy and a clear dependency direction (depends on Master Data, is depended upon by Defence Scheme) without requiring rework of existing modules.

---

## 5. Defence Scheme Domain

**Purpose:** Owns the engineering rules, parameters, versions, and substation assignments for every grid defence scheme.

**Owns (today):**
- **UFLS** — frequency stages, load blocks, assignments, thresholds.
- **UVLS** — voltage stages, load blocks, assignments, thresholds.
- **EMLS** — manual shedding priorities, assignments.

**Owns (future):** SPS/RAS, Black Start, Islanding, Restoration Planning — each as its own module within this domain, following the same ownership discipline.

Each scheme module is an independent bounded context (CLAUDE.md §8, §12): UFLS, UVLS, and EMLS do not share tables, do not share business rules, and do not read or write each other's data directly. A future cross-scheme concern (e.g. a substation's combined defence posture across UFLS + UVLS + EMLS) is a **read** concern belonging to Audit and Analytics, not a reason to merge these modules.

**References:**
- Master Data (substations) — every scheme assignment references a substation by `substation_id`; it never copies substation name, voltage, region, or owner (CLAUDE.md §5.1, §8, §11.4).
- Network Model, where a scheme's logic depends on topology (e.g. islanding boundaries).
- Core Platform, for shared reference data and (once formalised) identity.

**Referenced by:** Audit and Analytics, Presentation.

**Does not own:** substation name, voltage level, region, or grid owner (CLAUDE.md §8 — stated explicitly as a non-owned example for UFLS, and applies identically to UVLS, EMLS, and future scheme modules).

**Versioning:** any versioned record in this domain (e.g. a Scheme Version) follows the Canonical Version Lifecycle (CLAUDE.md A3):

```
Draft → Under Review → Approved → Active → Superseded → Archived
```

Only one Active version may exist per scheme type at a time. Approved and Active records are immutable; corrections always create a new version.

---

## 6. Audit and Analytics Domain

**Purpose:** Engineering traceability and derived insight across the platform.

**Owns:** nothing centrally. Per CLAUDE.md A4, **audit data is owned by the module that owns the business data it describes** — e.g. the Substation Registry owns `substation_audit_log`; UFLS owns `ufls_audit_log`; UVLS owns `uvls_audit_log`; EMLS owns `emls_audit_log`. This domain grouping is a conceptual umbrella over those per-module audit logs plus any future reporting/analytics capability, not a single owning module.

A future central audit dashboard or analytics/reporting module may **aggregate and display** audit records and engineering data from every module, using read-only cross-module access as permitted by CLAUDE.md A1 (read-only joins for reporting, dashboards, and query optimisation). Such a dashboard never becomes the owner of the records it displays, and never writes back to another module's tables.

**References:** all other domains, read-only.

**Referenced by:** none. This is the top of the dependency chain — every domain's history flows into audit and analytics; nothing depends on audit and analytics in return.

---

## 7. Presentation Domain

**Purpose:** Presents engineering information to users. Makes no authoritative engineering decisions (CLAUDE.md §15).

**Owns:** UI-only state — view preferences, in-browser sort/filter/pagination state, and TanStack Query's client-side server-state cache. This is presentation state, not engineering data, and is never treated as a system of record.

**References:** all other domains, exclusively through backend APIs (CLAUDE.md §13, A9). The Presentation domain never queries the database directly and never embeds business rules belonging to another domain.

**Allowed:** display-only derivations — formatting values, computing visible table subtotals from already-fetched data, displaying percentages the backend already computed, sorting/filtering displayed data (CLAUDE.md A12).

**Forbidden:** authoritative engineering calculations — determining scheme compliance, calculating approved load-shedding targets, deciding whether a scheme passes audit, or changing engineering state based on UI-only logic (CLAUDE.md A12). These always belong to the Defence Scheme (or relevant) domain's backend service layer.

---

## 8. Entity Ownership Rules

1. **Exactly one owner.** Every engineering entity is owned by exactly one module, in exactly one domain (CLAUDE.md §5.1, §8).
2. **Ownership controls writes.** Only the owning module's service layer may create, update, or retire an entity it owns (CLAUDE.md A1).
3. **Reference, never replicate.** Any module needing another module's data holds a foreign key to that entity's stable identifier (UUID for business entities, per CLAUDE.md A5) — never a copy of its attributes (CLAUDE.md §5.1, §11.4).
4. **Reference/lookup data is the one shared-read exception.** Core Platform reference tables carry no business rules of their own; any module may hold a foreign key to them and read them directly. This is distinct from reading another module's *business* entities, which must go through that module's service layer for anything beyond simple read-only reporting joins (CLAUDE.md A1).
5. **Audit is per-owner, not centralized.** Each module audits its own records; there is no shared "Audit" module that owns audit rows on another module's behalf (CLAUDE.md A4).
6. **Dependency direction is one-way.** A module may depend on a more foundational domain (Core Platform → Master Data → Network Model → Defence Scheme → Audit and Analytics); it must never be depended upon by a more foundational domain (CLAUDE.md A2).

---

## 9. Referenced vs. Owned Entities — Summary

| Domain | Owns | References (does not own) |
|---|---|---|
| Core Platform | Reference/lookup data (voltage level, region, state, grid owner, operational status); Identity and Access Management (Users, Roles, Permissions, external identity mappings, authorization model) | — |
| Master Data | Substation identity, mnemonic, metadata, geography, operational status | Core Platform reference data |
| Network Model *(future)* | Network topology / connectivity records | Master Data (substations at each connection endpoint) |
| Defence Scheme (UFLS / UVLS / EMLS / future SPS, RAS, Black Start, Islanding, Restoration Planning) | Frequency/voltage stages, load blocks, assignments, thresholds, scheme versions | Master Data (substations); Network Model (where relevant); Core Platform |
| Audit and Analytics | Nothing centrally — audit logs are owned per-module | All domains (read-only) |
| Presentation | UI/view state only | All domains, via backend APIs only |

This table is the quick reference for "who owns this, and who is just borrowing it." When in doubt, the owning module's own architecture document (built from the Canonical Module Architecture Document Template, CLAUDE.md A8) is authoritative for that module's entities.
