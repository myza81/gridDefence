# ADR-001: Modular Monolith and Module Communication

- **Status:** Accepted
- **Date:** 2026-07-01
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§6, §12, A1)
- **Depends on:** [ADR-000: Architecture Principles](ADR-000-architecture-principles.md)

---

## Context

GridDefence must support an initially small deployment footprint (Docker Compose, a single FastAPI application, a single PostgreSQL database) while remaining architecturally sound enough to eventually split into separately deployable services as the platform grows to include SPS/RAS, Black Start, Islanding, Restoration Planning, Network Analytics, and other future modules (CLAUDE.md §27).

Two risks needed to be resolved before further module work (e.g. UFLS, UVLS, EMLS) could proceed safely:

1. Choosing an overall system architecture style that balances current simplicity against future extensibility, without requiring a rewrite later.
2. Defining, precisely, how independent modules are allowed to talk to each other. Without an explicit rule, it is easy for a module to reach directly into another module's tables or repository layer "just this once" for convenience — which quietly destroys the bounded-context guarantees that Domain Ownership (CLAUDE.md §8) depends on.

CLAUDE.md §6 already states that GridDefence follows a Modular Monolith and that "the architecture shall support future migration to microservices without major redesign." CLAUDE.md A1 already specifies the concrete module communication rules. This ADR formally ratifies both as an accepted architectural decision, and records the reasoning and trade-offs behind them.

---

## Decision

### System Architecture Style

GridDefence is built as a **Modular Monolith**:

- A single deployable FastAPI application, backed by a single PostgreSQL database, deployed via Docker Compose.
- Internally, the application is organized into independent modules, each representing one bounded context (e.g. Substation Registry, UFLS, UVLS, EMLS).
- Each module owns its own tables, its own business rules, and its own audit trail (CLAUDE.md §8, A4).
- Module boundaries are enforced at the **service layer**, not at the network or deployment layer, for as long as the system remains a monolith.

### Module Communication Rules

The following rules are binding for all modules, present and future:

1. **Modules communicate through in-process service-layer interfaces.** This is the default and required mechanism for one module to invoke behaviour owned by another module inside the monolith.

2. **Modules must not call another module's repository directly.** A module may only reach another module's persistence layer through that module's public service interface — never by importing or invoking its repository classes/functions directly.

3. **Modules must not write directly to another module's tables.** All writes to an entity happen exclusively through the service layer of the module that owns that entity. There is no exception to this rule.

4. **Read-only cross-module joins are permitted only for reporting, dashboard read models, and query optimisation.** A module (or a future dedicated reporting/analytics capability) may issue a read-only SQL query joining across module-owned tables strictly to serve a reporting, dashboard, or performance-sensitive read path. This is the one narrow exception to rule 2, and it applies to reads only — it never substitutes for executing a business rule, and it never justifies a write.

5. **Business rules always execute through the owning module's service layer**, regardless of which module or user-facing feature initiated the request.

6. **HTTP/REST APIs (CLAUDE.md §13, A9) define external- and UI-facing contracts.** They are not the default mechanism for internal module-to-module communication inside the monolith. APIs and in-process service interfaces serve different audiences and are not interchangeable.

---

## Consequences

**Positive:**
- The system can be built and operated today with the simplicity of a single deployable and a single database — appropriate for the current team size and infrastructure (Docker Compose).
- Because module boundaries are already enforced logically (service-layer interfaces, no cross-module repository or table writes), a module can later be extracted into its own service by replacing in-process service calls with network calls, without redesigning its internal structure or its data ownership model.
- Domain Ownership (CLAUDE.md §8) and Single Source of Truth (CLAUDE.md §5.1) remain enforceable in practice, not just in principle, because the rules above give a concrete, checkable definition of "a module manipulating another module's internal data" (CLAUDE.md §12).

**Negative / trade-offs:**
- This requires ongoing engineering discipline: nothing at the database level automatically prevents a developer (or an AI agent generating code) from importing another module's repository. Enforcement depends on code review and, if drift becomes a problem in practice, may eventually warrant lint rules or database role/grant restrictions per module.
- A single shared PostgreSQL database means schema migrations must be coordinated across modules even though each module owns a disjoint set of tables; a migration affecting one module's tables still runs against the same database as every other module's.
- Rule 4 (read-only cross-module joins for reporting) is a deliberate exception that trades some future migration ease for present-day query simplicity and performance. Any reporting or dashboard feature built on a cross-module join represents physical coupling between those modules' schemas. Before any module involved in such a join is ever extracted into a separate service, that join must be reviewed and replaced (e.g. with an API call, a read replica, or an aggregated read model) — this review should itself be recorded as an ADR at that time, per CLAUDE.md A13.

---

## Alternatives Considered

1. **Microservices from day one.** Rejected. Given the current single small deployable (Docker Compose) and the early stage of the platform, splitting into independently deployed services now would introduce service discovery, distributed transaction, and inter-service authentication overhead with no corresponding benefit yet. CLAUDE.md §9 already anticipates a future move to Kubernetes; this decision does not foreclose that path, it defers it until it is actually needed.

2. **Unstructured single monolith with no enforced module boundaries.** Rejected. Without the rules in this ADR, nothing would stop a module from directly querying or writing another module's tables "for convenience," which would silently violate Domain Ownership (CLAUDE.md §8) and Single Source of Truth (CLAUDE.md §5.1), and would make any future service extraction far more costly by the time it was attempted.

3. **Require all internal module-to-module calls to go through internal HTTP APIs, even within the monolith.** Rejected for now. This would add network-call complexity (serialization, retries, error mapping) to calls that are, today, ordinary in-process function calls within the same operating system process. This approach can be revisited via a new ADR if and when a module is physically extracted into a separate deployable service.

4. **Allow modules to read each other's tables directly for any purpose, not just reporting.** Rejected. This would erode the bounded-context guarantees this ADR exists to protect — it would become impossible to reason about which module's business rules are in effect for a given piece of data. The read-only exception in this ADR is deliberately narrowed to reporting, dashboards, and query optimisation.
