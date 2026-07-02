# CLAUDE.md

> GridDefence Engineering Standards & AI Collaboration Guide




# CLAUDE.md v1.1 Final Clarifications
Version: 1.1
Status: Active
Purpose: Final clarification before freezing `CLAUDE.md v1.1`.

---

---

# 1. Purpose

This document defines the engineering principles, architectural standards, software development practices, and AI collaboration guidelines for the GridDefence project.

It serves as the authoritative reference for all architecture, implementation, documentation, and code generation activities.

Every contributor—human or AI—must follow the principles defined in this document.

If a future design conflicts with this document, this document takes precedence until an Architecture Decision Record (ADR) formally updates the standard.

---

# 2. Project Overview

GridDefence is an enterprise engineering platform for managing transmission grid defence schemes.

The system is designed to become the single source of truth for engineering data related to grid defence planning, implementation, auditing, simulation, and operational readiness.

GridDefence is not merely a load shedding application.

It is an engineering information system whose primary objective is maintaining the integrity, traceability, and lifecycle of power system defence schemes.

---

# 3. Product Vision

GridDefence shall provide a centralized platform for managing:

• Under Frequency Load Shedding (UFLS)

• Under Voltage Load Shedding (UVLS)

• Emergency Manual Load Shedding (EMLS)

Future modules include:

• Special Protection Schemes (SPS)

• Remedial Action Schemes (RAS)

• Black Start Planning

• Islanding Strategy

• Restoration Planning

• Network Analytics

• PSS®E Integration

• Engineering Dashboard

Every module must integrate into a single coherent engineering platform.

---

# 4. Engineering Philosophy

GridDefence follows one fundamental principle.

> Engineering Truth Before Software Convenience.

The software models a real transmission network.

If software convenience conflicts with engineering correctness, engineering correctness shall always take precedence.

The purpose of the software is to support engineering decisions—not simplify them.

---

# 5. Core Engineering Principles

## 5.1 Single Source of Truth

Every engineering entity has exactly one owner.

Other modules reference it.

They never duplicate it.

Reference is always preferred over replication.

---

## 5.2 Immutable Engineering History

Approved engineering records are immutable.

Historical records shall never be overwritten.

Corrections create new versions.

History is preserved permanently.

---

## 5.3 Explicit Architecture

Every business rule shall have a clearly defined owner.

Implicit behaviour is discouraged.

Hidden side effects are prohibited.

---

## 5.4 Auditability

Every engineering change must be traceable.

Every important action must record:

- Who
- When
- Why
- What changed

---

## 5.5 Deterministic Behaviour

The same engineering input shall always produce the same engineering result.

Avoid hidden automation that changes engineering decisions.

---

# 6. System Architecture Philosophy

GridDefence follows a Modular Monolith architecture.

Modules are developed as independent bounded contexts.

Each module owns its own data.

Each module owns its own business rules.

Modules communicate through defined interfaces.

The architecture shall support future migration to microservices without major redesign.

---

# 7. Domain Hierarchy

Engineering information flows in the following order.

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

Higher layers may reference lower layers.

Lower layers shall never depend upon higher layers.

---

# 8. Domain Ownership

Every engineering entity has one owner.

Example:

Substation Registry owns:

✓ Identity

✓ Mnemonic

✓ Metadata

✓ Geography

✓ Operational Status

UFLS owns:

✓ Frequency Stages

✓ Load Blocks

✓ Assignments

✓ Thresholds

UFLS does NOT own:

✗ Substation Name

✗ Voltage Level

✗ Region

✗ Owner

Future modules shall follow the same ownership model.

---

# 9. Technology Stack

Backend

- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis
- RQ (initially)

Frontend

- React
- TypeScript
- Vite
- TanStack Query
- TanStack Table
- Apache ECharts

Infrastructure

- Docker Compose
- GitHub
- VS Code

Future deployment may migrate to Kubernetes.

---

# 10. Repository Structure

The repository follows a feature-oriented structure.

Architecture documentation lives under:

docs/architecture/

Architecture decisions live under:

docs/adr/

Claude project standards live in:

.claude/CLAUDE.md

Implementation follows documented architecture.

Architecture always precedes implementation.

---

# 11. Database Standards

The database is the authoritative store of engineering information.

Database design shall prioritize engineering integrity, historical traceability, and long-term maintainability over implementation convenience.

## 11.1 Primary Keys

- Every primary business entity shall use a UUID as its primary key.
- Business identifiers (e.g. mnemonic, bus number) shall never be used as primary keys.
- UUIDs are immutable and never reused.

## 11.2 Foreign Keys

- All relationships shall be enforced through foreign keys.
- Orphan records are not permitted.
- Nullable foreign keys shall only be used where the relationship is genuinely optional.

## 11.3 Reference Data

Reference data shall be stored in dedicated lookup tables.

Examples include:

- Voltage Levels
- Regions
- States
- Grid Owners
- Operational Statuses

Reference tables are preferred over database enums to support future expansion without schema changes.

## 11.4 Master Data

Master data is owned by exactly one module.

Other modules shall reference master data through foreign keys.

Master data shall never be duplicated.

## 11.5 Versioning

Current-state master data is stored in a single authoritative record.

Operational engineering data shall be version controlled.

Approved engineering records are immutable.

Historical records shall never be overwritten.

## 11.6 Soft Delete

Engineering entities shall not be physically deleted.

Lifecycle status shall represent retirement or decommissioning.

Hard delete is reserved for administrative correction only.

## 11.7 Cascading Delete

Cascade delete is prohibited on engineering entities.

Relationships shall default to ON DELETE RESTRICT.

## 11.8 Constraints

Every business rule that can be enforced by the database should be enforced by the database.

Examples include:

- Uniqueness
- Check constraints
- Foreign keys
- Not Null constraints

Application logic supplements database constraints—it does not replace them.

---

# 12. Module Design Standards

Every module represents a bounded context.

Each module owns its own business rules and data.

Modules shall not manipulate another module's internal data directly.

Every module architecture document shall define:

- Purpose
- Responsibilities
- Non-responsibilities
- Owned entities
- Referenced entities
- Public interfaces
- Dependencies
- Business rules
- Validation rules
- Audit requirements
- Future extensions

Modules communicate through service interfaces.

Module boundaries should remain stable over time.

---

# 13. API Standards

GridDefence follows an API-first architecture.

APIs define the contract between modules and external consumers.

## Principles

- RESTful design
- Resource-oriented URLs
- Plural resource names
- Nouns instead of verbs
- Consistent HTTP status codes

## Data Contracts

Persistence models shall never be exposed directly.

Separate:

- Database Models
- Domain Models
- API DTOs

## Versioning

API contracts should remain backward compatible whenever possible.

Breaking changes require version review.

## Documentation

Every endpoint shall include:

- Purpose
- Request schema
- Response schema
- Validation rules
- Error responses

---

# 14. Backend Standards

The backend follows layered architecture.

Business logic shall never exist inside routers.

Recommended structure:

Router

↓

Service

↓

Repository

↓

Database

Responsibilities:

Router

- HTTP
- Validation
- Authentication

Service

- Business rules
- Transactions
- Orchestration

Repository

- Database persistence

Model

- Persistence mapping

Schema

- API contracts

Business rules shall always live inside the Service layer.

---

# 15. Frontend Standards

The frontend exists to present engineering information.

Business decisions belong to the backend.

## Principles

- Feature-based organisation
- Reusable UI components
- Thin pages
- Stateless components whenever practical

## State Management

Server state

→ TanStack Query

UI state

→ React

Avoid duplicating backend business logic.

The frontend shall never determine engineering calculations.

---

# 16. Logging and Audit Standards

Logging and auditing are different concerns.

## Logging

Purpose:

Operational diagnostics.

Logs may include:

- Performance
- Errors
- Exceptions
- Infrastructure events

## Audit

Purpose:

Engineering traceability.

Audit records shall capture:

- Who
- When
- What
- Why

Audit history shall never be modified.

Engineering actions must remain fully traceable.

---

# 17. Security Standards

Security shall follow the Principle of Least Privilege.

## Authentication

Authentication verifies identity.

## Authorization

Authorization controls actions.

Permissions shall be role-based.

Administrative actions shall require elevated privileges.

Engineering approvals shall require authenticated users.

Future security enhancements should support:

- RBAC
- MFA
- SSO
- LDAP/Active Directory integration

---

# 18. Testing Standards

Testing validates engineering correctness.

The project shall include:

- Unit Tests
- Integration Tests
- API Tests
- Database Migration Tests
- UI Tests

Priority:

Business Rules

↓

Engineering Calculations

↓

API Contracts

↓

UI Behaviour

↓

Infrastructure

Testing shall verify engineering outcomes rather than implementation details.

---

# 19. Documentation Standards

Architecture documentation precedes implementation.

Every new module shall include:

- Purpose
- Scope
- Responsibilities
- Domain Model
- Database Design
- API Contract
- Validation Rules
- Security Considerations
- Future Extensions

Implementation shall reference architecture documentation.

---

# 20. Naming Standards

Naming shall reflect engineering terminology.

Avoid unnecessary abbreviations.

Prefer explicit names over clever names.

Examples:

Good

SubstationRegistry

SchemeVersion

AssignmentBlock

Poor

Manager

Data

Utils

Helper

Table names shall use plural nouns.

API resources shall use plural nouns.

Module names shall represent engineering concepts.

---

# 21. Performance Guidelines

Correctness precedes optimisation.

Avoid premature optimisation.

Performance improvements shall be based on measured evidence.

Optimisations shall not compromise readability or maintainability.

---

# 22. Configuration Management

Application configuration shall be externalised.

Environment-specific values belong in environment variables.

Secrets shall never be committed to source control.

Engineering constants shall be documented.

Configuration shall remain reproducible across environments.

---

# 23. AI Collaboration Model

GridDefence adopts an AI-assisted engineering workflow.

Each AI agent has clearly defined responsibilities.

## Project Owner

Defines business requirements.

Approves engineering decisions.

Owns product direction.

## ChatGPT

Role:

Chief Solution Architect

Responsibilities:

- System architecture
- Domain decomposition
- Technical planning
- Prompt engineering
- Cross-module consistency
- Architecture review
- Engineering guidance

## Claude

Role:

Principal Software Architect

Responsibilities:

- Architecture refinement
- Domain modelling
- Technical documentation
- Design review
- Architecture validation

Claude should think before implementing.

Architecture precedes code.

## Codex

Role:

Senior Software Engineer

Responsibilities:

- Implementation
- Refactoring
- Test development
- Bug fixing
- Migration generation
- Build automation

Codex implements approved architecture.

Codex does not redefine architecture.

---

# 24. Development Workflow

Every feature shall follow the same engineering lifecycle.

Requirements

↓

Architecture

↓

Domain Model

↓

Database Design

↓

API Contract

↓

Review

↓

Implementation

↓

Testing

↓

Documentation

↓

Approval

↓

Merge

Implementation shall not begin before architecture has been reviewed.

---

# 25. Definition of Done

A feature is complete only when:

✓ Architecture approved

✓ Database impact reviewed

✓ API contract documented

✓ Business rules implemented

✓ Tests passing

✓ Documentation updated

✓ Audit requirements satisfied

✓ Code reviewed

✓ Ready for deployment

---

# 26. Claude Behaviour Guidelines

Claude acts as the project's Principal Software Architect.

Claude should:

- Think before coding.
- Challenge architectural weaknesses.
- Prefer maintainability over cleverness.
- Keep module boundaries clean.
- Explain design trade-offs.
- Ask for clarification when requirements are ambiguous.
- Produce architecture before implementation.

Claude must not:

- Invent business rules.
- Duplicate master data.
- Bypass module boundaries.
- Modify approved architecture without justification.
- Overwrite historical engineering records.
- Remove auditability.
- Introduce unnecessary abstraction.
- Optimise prematurely.
- Change engineering terminology.

---

# 27. Future Evolution

GridDefence is expected to evolve over many years.

Future modules may include:

- SPS
- RAS
- Black Start
- Islanding
- Restoration Planning
- GIS
- CIM Integration
- SCADA Integration
- EMS Integration
- Analytics
- Machine Learning

Every future module shall conform to the architectural principles defined in this document.

---

# Final Principle

GridDefence is an engineering platform.

Engineering correctness always takes precedence over software convenience.

Every architectural decision shall support maintainability, traceability, auditability, and long-term evolution.

When in doubt, choose the solution that best preserves engineering integrity.

---

# A1. Module Communication Standard

Within the GridDefence modular monolith, modules communicate through in-process service-layer interfaces.

Modules must not call another module's repositories directly.

Modules must not write directly to another module's tables.

Read-only joins across module-owned tables are permitted only for query optimisation, reporting, and dashboard read models.

Business rules must always be executed through the owning module's service layer.

APIs define external and UI-facing contracts. They are not the default communication mechanism between internal modules inside the monolith.

---

# A2. Dependency Direction

Dependency direction must follow the engineering data hierarchy.

Allowed direction:

```text
Scheme Data
    ↓
Master Data
```

Example:

UFLS may reference Substation Registry.

Forbidden direction:

```text
Master Data
    ↓
Scheme Data
```

Example:

Substation Registry must never depend on UFLS, UVLS, or EMLS.

Lower-level domains must not depend on higher-level domains.

---

# A3. Canonical Version Lifecycle

All versioned engineering modules shall use the following lifecycle unless an ADR approves an exception.

```text
Draft
  ↓
Under Review
  ↓
Approved
  ↓
Active
  ↓
Superseded
  ↓
Archived
```

Rules:

* Draft records are editable.
* Under Review records are locked except by reviewers or administrators.
* Approved records are immutable.
* Active records are immutable.
* Only one active version may exist per scheme type unless explicitly allowed by architecture.
* Superseded records remain queryable.
* Archived records remain queryable.
* Corrections to approved or active records require a new version.

---

# A4. Audit Ownership

Audit data is owned by the module that owns the business data.

Each module is responsible for auditing its own engineering records.

Examples:

```text
Substation Registry
    owns substation_audit_log

UFLS Module
    owns ufls_audit_log

UVLS Module
    owns uvls_audit_log

EMLS Module
    owns emls_audit_log
```

A future central audit dashboard may aggregate audit records from modules, but it does not become the owner of those audit records.

Audit history is append-only and must not be modified.

---

# A5. Primary Key Standard Clarification

Business entities use UUID primary keys.

Reference and lookup tables may use SMALLINT or INTEGER surrogate keys.

Examples of business entities:

* Substation
* Scheme
* Scheme Version
* Assignment
* Import Batch
* Audit Run

Examples of reference tables:

* Voltage Level
* Region
* State
* Grid Owner
* Operational Status

Business entities require durable global identity.

Reference tables are controlled lookup data and do not require UUIDs unless there is a specific architectural reason.

---

# A6. Domain Model Layering

Backend models shall distinguish between:

```text
Persistence Model
    ↓
Domain Model
    ↓
API DTO / Schema
```

Persistence models represent database structure.

Domain models represent engineering concepts and business rules.

API DTOs represent request and response contracts.

Business logic belongs in the domain/service layer, not in persistence models, routers, or frontend components.

---

# A7. Engineering Parameters vs Infrastructure Configuration

Infrastructure configuration belongs in environment variables.

Examples:

* Database URL
* Redis URL
* JWT secret
* Logging level
* Storage path
* External service endpoint

Engineering parameters belong in the database.

Examples:

* UFLS frequency thresholds
* UVLS voltage thresholds
* EMLS priority levels
* Load block definitions
* Scheme activation dates
* Approval status

Engineering parameters must be versioned, auditable, and visible to authorised users.

Engineering parameters must not be hidden in `.env` files, source code, or deployment configuration.

---

# A8. Canonical Module Architecture Document Template

Every module architecture document shall use the following structure.

```text
1. Module Overview
2. Purpose
3. Responsibilities
4. Non-Responsibilities
5. Owned Entities
6. Referenced Entities
7. Domain Model
8. Lifecycle / State Model
9. Business Rules
10. Validation Rules
11. Database Design
12. API Contract
13. Service Interfaces
14. Audit Requirements
15. Security Considerations
16. Testing Requirements
17. Future Extensions
18. Risks and Recommendations
```

This template replaces all previous module documentation checklists.

---

# A9. API Contract Details

All API designs shall define:

* Pagination convention
* Filtering convention
* Sorting convention
* Error response shape
* Authentication requirement
* Authorization requirement
* Request schema
* Response schema
* Validation errors
* Audit-relevant actions

API responses must not expose ORM objects directly.

Structured error responses are required for all non-success responses.

---

# A10. Security Baseline

All GridDefence engineering data is sensitive by default.

Security standards:

* Authentication is required for all non-public endpoints.
* Authorization is role-based.
* Administrative actions require elevated privileges.
* Engineering approval actions require authenticated named users.
* Audit logs are access-controlled.
* Secrets must never be committed to source control.
* TLS is required outside local development.
* Sensitive exports must be traceable.

Security shall be designed from the beginning, not deferred until production.

---

# A11. Testing Gate

Business rules and engineering calculations must not be merged without tests.

Minimum required test coverage by feature:

* Business rule tests
* Validation tests
* API contract tests
* Database migration tests where schema changes exist
* UI behaviour tests where frontend behaviour changes

Tests should verify engineering outcomes, not internal implementation details.

---

# A12. Frontend Calculation Boundary

The frontend may perform display-only derivations.

Allowed examples:

* Formatting MW values
* Calculating visible table subtotals
* Displaying percentages from backend-provided values
* Sorting and filtering displayed data

The frontend must not perform authoritative engineering calculations.

Prohibited examples:

* Determining UFLS compliance
* Calculating approved load shedding targets
* Deciding whether a scheme passes audit
* Changing engineering state based on UI-only logic

Authoritative calculations belong in the backend.

---

# A13. ADR Standard

Architecture Decision Records shall live in:

```text
docs/adr/
```

ADR filename format:

```text
ADR-000-short-title.md
```

Each ADR shall include:

```text
Title
Status
Date
Context
Decision
Consequences
Alternatives Considered
```

ADR statuses:

```text
Proposed
Accepted
Superseded
Rejected
```

Any change that modifies core architecture, domain ownership, versioning, security, or database standards requires an ADR.

---

# A14. AI Agent Conflict Resolution

ChatGPT provides overall architecture governance and cross-module consistency.

Claude provides module-level architecture refinement, documentation, and design review.

Codex implements approved architecture.

If AI agents produce conflicting architectural guidance, the Project Owner decides.

The final decision shall be recorded in an ADR when the issue affects long-term architecture.

---

# A15. Deferred Standards

The following standards are intentionally deferred until first implementation need:

* CI/CD pipeline standard
* Background job retry and idempotency standard
* Observability and metrics standard
* Migration rollback standard
* Export governance standard

When one of these areas becomes active, an ADR shall define the standard before implementation proceeds.

---

# A16. Approval of v1.1

This addendum clarifies `CLAUDE.md v1.0`.

It does not replace the original engineering philosophy.

Where this addendum is more specific than v1.0, the v1.1 clarification takes precedence.

GridDefence remains governed by the same final principle:

Engineering correctness always takes precedence over software convenience.

---


# F1. Standards Precedence

When guidance appears to conflict, apply the following precedence:

```text
Project Vision & Engineering Principles
    ↓
CLAUDE.md Standards
    ↓
Accepted ADRs
    ↓
Module Architecture Documents
    ↓
Implementation
    ↓
Optimisation / Refactoring
```

Accepted ADRs may clarify or extend the standards, but must not violate the core engineering philosophy unless `CLAUDE.md` is formally revised.

---

# F2. Dependency Direction Clarification

Dependencies always point toward foundational domains.

Foundational domains shall never depend on dependent domains.

Example:

```text
UFLS → Substation Registry
```

Allowed.

```text
Substation Registry → UFLS
```

Forbidden.

Master Data is foundational.

Scheme Data is dependent.

Audit, Dashboard, and Reporting depend on the engineering data they observe.

They do not own that engineering data.

---

# F3. Superseded Section References

The following original sections are clarified by v1.1 addenda:

```text
Section 7  → clarified by A2 and F2
Section 11 → clarified by A5
Section 12 → replaced by A8
Section 13 → clarified by A1 and A9
Section 14 → clarified by A6
Section 19 → replaced by A8
Section 22 → clarified by A7
```

When using these sections, apply the v1.1 clarification where it is more specific.

---

# F4. Identity and Access Management Ownership

GridDefence shall include an Identity and Access Management module.

This module owns:

* Users
* Roles
* Permissions
* Authentication identity references
* Authorization rules

Audit records shall reference a stable user identity.

Preferred audit reference:

```text
user_id
```

Fallback for externally federated identity:

```text
external_principal_id
```

Modules must not invent their own local user tables.

The Identity and Access Management module is the source of truth for user identity inside GridDefence.

Future integrations may include:

* LDAP
* Active Directory
* SSO
* OAuth / OIDC

External identity providers may authenticate users, but GridDefence still owns the application-level authorization model.

---

# F5. Active Version Supersession

When a new scheme version is activated, the previously active version of the same scheme type is automatically changed to `Superseded`.

This transition is automatic.

Manual superseding is not permitted for normal scheme activation.

Only one active version may exist per scheme type unless an ADR explicitly allows otherwise.

---

# F6. Read-Only Join Trade-Off

Read-only joins across module-owned tables are permitted inside the modular monolith for query optimisation, reporting, and dashboard read models.

This is a deliberate implementation trade-off.

If a module is later extracted into an independent service, cross-module SQL joins must be replaced with service interfaces, APIs, materialised read models, or event-driven projections.

Any service extraction that changes module communication must be documented in an ADR.

---

# F7. Encryption and Data Protection

Engineering data is sensitive by default.

Where supported by the deployment platform:

* Databases shall use encryption at rest.
* Backups shall use encryption at rest.
* Sensitive exports shall be protected and traceable.
* Access to audit records shall be restricted.
* Secrets shall never be stored in source control.

Security protections apply to both production data and exported engineering datasets.

---

# F8. Freeze Rule

After this clarification, `CLAUDE.md v1.1` is considered the active engineering standard for GridDefence.

Future changes require one of the following:

* Accepted ADR
* Explicit version update to `CLAUDE.md`
* Project Owner approval

Do not casually edit this document during feature work.

Feature-specific decisions belong in:

```text
docs/architecture/
```

Architecture decisions belong in:

```text
docs/adr/
```

Implementation belongs in:

```text
backend/
frontend/
```

`CLAUDE.md` remains the stable engineering standard.

