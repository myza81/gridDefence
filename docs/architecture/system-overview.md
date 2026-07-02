# GridDefence System Overview

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) (v1.1). This document describes how the platform is structured; it does not redefine or override any standard in CLAUDE.md.

---

## 1. What GridDefence Is

GridDefence is an engineering platform whose purpose is to be the single source of truth for transmission grid defence schemes — UFLS, UVLS, EMLS, and future schemes (SPS/RAS, Black Start, Islanding, Restoration Planning) — across their full lifecycle: planning, approval, versioning, auditing, and (in future) simulation.

Per CLAUDE.md §4, the platform is built on one governing rule: **Engineering Truth Before Software Convenience.** Every architectural choice in this document is made in service of engineering integrity, traceability, and long-term correctness — not implementation ease.

---

## 2. Major Bounded Contexts

GridDefence is composed of independent bounded contexts ("modules"), each owning its own data and business rules (CLAUDE.md §6, §12). The initial and planned contexts are:

| Bounded Context | Domain Grouping | Owns |
|---|---|---|
| **Substation Registry** | Master Data | Substation identity, mnemonic, metadata, geography, operational status |
| **UFLS** | Defence Scheme | Frequency stages, load blocks, assignments, thresholds |
| **UVLS** | Defence Scheme | Voltage stages, load blocks, assignments, thresholds |
| **EMLS** | Defence Scheme | Manual shedding priorities, assignments |
| *(future)* Network Topology | Network Model | Substation-to-substation connectivity |
| *(future)* SPS / RAS | Defence Scheme | Special protection / remedial action scheme logic |
| *(future)* Black Start, Islanding, Restoration Planning | Defence Scheme | Their respective engineering plans |
| *(future)* Analytics / Reporting | Audit and Analytics | Cross-module reporting, dashboards |

Full detail on domain groupings and entity ownership lives in [domain-model.md](domain-model.md). Detail on any individual module lives in that module's own architecture document (e.g. [substation-registry.md](substation-registry.md)).

Every bounded context owns exactly one slice of engineering truth (CLAUDE.md §5.1, §8). No bounded context duplicates another's data — it references it.

---

## 3. Backend Overview

- **Framework:** FastAPI
- **ORM:** SQLAlchemy
- **Migrations:** Alembic
- **Background processing:** Redis + RQ (initial choice; standards for job retry/idempotency are deferred per CLAUDE.md A15 until first real usage)

**Layering (CLAUDE.md §14, A6):**

```
Router → Service → Repository → Database
```

- Router: HTTP, request validation, authentication.
- Service: business rules, transactions, orchestration — the only place business rules may live.
- Repository: database persistence.
- Models are further split by concern (CLAUDE.md A6):

```
Persistence Model → Domain Model → API DTO / Schema
```

Persistence models never leak into API responses. Domain models carry engineering meaning and business rules; API DTOs carry only request/response contracts.

Each bounded context implements this layering internally and independently — there is no shared "god service" or shared repository layer across modules.

---

## 4. Frontend Overview

- **Framework:** React + TypeScript, built with Vite.
- **Server state:** TanStack Query.
- **Tabular data:** TanStack Table.
- **Visualization:** Apache ECharts.

The frontend presents engineering information; it does not make engineering decisions (CLAUDE.md §15). Per CLAUDE.md A12, the frontend may perform **display-only derivations** (formatting, visible subtotals, sorting/filtering of already-fetched data) but must never perform **authoritative engineering calculations** (e.g. determining compliance, computing approved shedding targets, deciding audit pass/fail). All authoritative calculations are backend-owned and exposed as data to the frontend.

---

## 5. Database Overview

- **Engine:** PostgreSQL, the authoritative store of engineering information (CLAUDE.md §11).
- **Primary keys:** business entities use UUIDs; reference/lookup tables may use SMALLINT/INTEGER surrogate keys (CLAUDE.md A5).
- **Reference data:** stored in dedicated lookup tables (voltage levels, regions, states, grid owners, operational statuses, etc.), never as database enums, to allow extension without schema migration (CLAUDE.md §11.3).
- **Deletion:** engineering entities are never physically deleted; lifecycle status represents retirement (CLAUDE.md §11.6). Cascading delete is prohibited; foreign keys default to `ON DELETE RESTRICT` (CLAUDE.md §11.7).
- **Deployment topology:** in the current modular-monolith phase, all modules share a single PostgreSQL database, but each module owns its own tables. Cross-module table access follows the rules in §6 below and in [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md).

---

## 6. Module Communication Rules

GridDefence is a **Modular Monolith** (CLAUDE.md §6, A1; see [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md)):

- Modules communicate through **in-process service-layer interfaces**. This is the default and expected communication mechanism.
- A module **must not** call another module's repository directly.
- A module **must not** write directly to another module's tables.
- **Read-only** cross-module SQL joins are permitted only for query optimisation, reporting, and dashboard read models — never for writes, and never as a substitute for going through the owning module's service layer when a business rule is involved.
- Business rules always execute through the owning module's service layer, regardless of which module initiates the request.
- HTTP APIs (CLAUDE.md §13, A9) define **external and UI-facing** contracts. They are not the default mechanism for internal, in-process module-to-module communication.

This design keeps module boundaries enforceable today and keeps the door open for extracting a module into a separate service later (CLAUDE.md §6) — with the explicit caveat that any reporting/dashboard feature built on cross-module joins represents deliberate coupling that will need review if that module is ever extracted (see [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md), Consequences).

---

## 7. Dependency Direction

Dependency direction follows the engineering data hierarchy (CLAUDE.md A2, refining §7):

```
Defence Scheme Data  ──depends on──▶  Master Data
```

- A scheme module (UFLS, UVLS, EMLS, and future SPS/RAS, Black Start, etc.) **may** depend on and reference Master Data (e.g. the Substation Registry).
- Master Data **must never** depend on any Defence Scheme module. The Substation Registry has no knowledge of UFLS, UVLS, or EMLS.
- More generally: foundational domains (Master Data, Reference Data) must never depend on the domains built on top of them (Network Data, Defence Scheme Data, Operational Data, Audit Data, Reporting & Analytics). Dependency only flows from a dependent domain toward the foundational domain it relies on, never the reverse.

See [domain-model.md](domain-model.md) for the full domain hierarchy and how each domain grouping fits this rule.

---

## 8. Future Extensibility

The system is designed so that future modules — SPS, RAS, Black Start, Islanding, Restoration Planning, GIS, CIM/SCADA/EMS integration, Analytics, Machine Learning (CLAUDE.md §27) — can be added without redesigning the platform:

- Each new module is a new bounded context, documented using the Canonical Module Architecture Document Template (CLAUDE.md A8), and added to the index in [README.md](README.md).
- Each new module references existing Master Data (e.g. Substation Registry) rather than duplicating it, following the same ownership pattern already established by UFLS/UVLS/EMLS against the Substation Registry (CLAUDE.md §8).
- Each new module owns its own audit trail (CLAUDE.md A4) and, if versioned, follows the Canonical Version Lifecycle (CLAUDE.md A3).
- Infrastructure is expected to evolve from Docker Compose toward Kubernetes (CLAUDE.md §9) without requiring a change to module boundaries, since those boundaries are already enforced at the service layer rather than at the deployment layer.
- Any change that alters a core principle — domain ownership, dependency direction, versioning, security, or database standards — requires an ADR (CLAUDE.md A13) before it is adopted.
