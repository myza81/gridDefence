# Engineering Parameter Configuration Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§22, A5, A7, A8). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md). Realizes [ADR-021](../adr/ADR-021-engineering-parameter-configuration-ownership.md) — read that ADR first for the decision rationale; this document is the architecture built from it.

Related: [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) (its §7.1 MW tolerance is the first consumer), [reference_data module] (`app/reference_data/`, deliberately distinct — see ADR-021 "Why not Reference Data").

**Status: Approved and implemented (Shared Platform Sprint 1).** Backend module (`app/modules/engineering_parameters/`: models, repository, service, router, schemas, exceptions, bootstrap), Alembic migration (`0017_engineering_parameters`), and unit/API test suites are complete and verified on both SQLite and PostgreSQL. Only the one architecture-approved parameter (`mw_tolerance_percentage`) is seeded — no other parameter is invented. Frontend pages are **not** part of this sprint's scope and remain unbuilt; every section below (§11, §12) remains the authoritative conceptual/as-built reference for the backend.

---

## 1. Module Overview

Engineering Parameter Configuration is a small, standalone Core Platform module owning the current, audited value of every platform-wide engineering parameter — numeric or textual settings that are engineering facts (CLAUDE.md A7), not infrastructure configuration, and not closed reference-data enumerations.

## 2. Purpose

Give every module that needs a named, versioned-by-audit-log, administrator-changeable engineering value (starting with the Continuous Evaluation Engine's MW tolerance) one shared, auditable home — realizing CLAUDE.md A7's principle, which existed before this module did.

## 3. Responsibilities

- Own the current value of every registered engineering parameter.
- Record a full audit trail of every value change (old value, new value, actor, mandatory reason, timestamp).
- Expose read access broadly (any authenticated user) and write access under one elevated permission.

## 4. Non-Responsibilities

- Does not decide *what a parameter's value should be* — that is an engineering/administrative decision made by an authorised user, not a computed or derived value.
- Does not interpret or apply a parameter's value — consuming modules (e.g. the MW tolerance detector, per [ADR-022](../adr/ADR-022-continuous-evaluation-detector-framework.md)) read the current value and apply it themselves.
- Does not own closed classification enumerations (Region, Voltage Level, Grid Owner, etc.) — those remain owned by `reference_data`, per ADR-021's "Why not Reference Data."
- Does not provide a Draft/Published workflow — a parameter has no in-progress editable state; see §8.

## 5. Owned Entities

| Entity | Description |
|---|---|
| `EngineeringParameter` | One row per named parameter: `parameter_key` (PK), `value`, `unit`, `description`, `updated_by_user_id`, `updated_at`. |
| `EngineeringParameterAuditLogEntry` | One row per change: `parameter_key`, `old_value`, `new_value`, `changed_by_user_id`, `change_reason`, `changed_at`. |

## 6. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| User | IAM | `updated_by_user_id` / `changed_by_user_id`, per CLAUDE.md F4 |

No other module's data is referenced — Engineering Parameter Configuration sits at the Core Platform tier and depends on nothing above it in the domain hierarchy (CLAUDE.md §7).

## 7. Domain Model

```
EngineeringParameter (1) ──── (many) EngineeringParameterAuditLogEntry
EngineeringParameter.updated_by_user_id ──── references (external, read-only) ──▶ User.user_id (IAM)
```

Every module that needs an engineering parameter's current value (e.g. the Continuous Evaluation Engine's MW tolerance detector, per ADR-022) consumes it through this module's own read service interface (§13) — never a direct table read, per CLAUDE.md A1.

## 8. Lifecycle / State Model

**Current-value-plus-audit-log — not a Draft/Published/Superseded state machine.** Each `EngineeringParameter` row always holds exactly one current value. A change is a single, atomic, audited write:

```text
current value ──[audited write, mandatory reason]──▶ new current value
```

This deliberately departs from the Canonical Version Lifecycle (CLAUDE.md A3) and from ADR-015's four-state Scheme Version lifecycle — both exist to manage *engineering records with a genuine review/approval workflow before taking effect*. A tolerance value has no such workflow: an Administrator changes it, with a reason, and the new value is immediately current. Introducing Draft/Published states here would be complexity with no corresponding requirement (CLAUDE.md §21). Historical values remain fully queryable via the audit log (CLAUDE.md §5.4), which is what a full lifecycle state machine would otherwise exist to provide.

## 9. Business Rules

1. Every value change requires a non-empty `change_reason`.
2. `parameter_key` is immutable once created — a parameter is never renamed, only its value changes; introducing a genuinely new parameter is a new `parameter_key` row, never a repurposed one (preserves the audit trail's own meaning over time).
3. A `parameter_key` referenced by any consuming module's own service logic (e.g. `mw_tolerance_percentage`) is a code-level contract — removing a parameter a consumer still reads is a coordinated change across both modules, not a unilateral deletion.
4. Parameters are never hard-deleted once created, consistent with CLAUDE.md §11.6 — an obsolete parameter is left in place with its historical audit trail intact; consuming code simply stops reading it.

## 10. Validation Rules

- `value` must satisfy whatever type/range constraint is defined for that specific `parameter_key` (e.g. `mw_tolerance_percentage` must be a positive percentage) — enforced at the service layer per-parameter, since parameters are not structurally uniform in type.
- `change_reason` must be non-empty.

## 11. Database Design (Concept)

Conceptual only — no migrations are defined here.

| Table (conceptual) | Key columns (conceptual) | Notes |
|---|---|---|
| `engineering_parameter` | `parameter_key` (string PK), `value`, `unit`, `description`, `updated_by_user_id` (FK, RESTRICT), `updated_at` | String PK per CLAUDE.md A5's "stable, code-referenced identity" allowance — mirrors `Permission.permission_id`. |
| `engineering_parameter_audit_log` | `audit_log_id` (UUID PK), `parameter_key` (FK, RESTRICT), `old_value`, `new_value`, `changed_by_user_id` (FK, RESTRICT), `change_reason`, `changed_at` | Append-only, per CLAUDE.md A4. |

## 12. API Contract (Concept)

- `GET /engineering-parameters` — list all parameters and their current values. Requires authentication only.
- `GET /engineering-parameters/{key}` — read one parameter's current value. Requires authentication only.
- `PUT /engineering-parameters/{key}` — update a parameter's value; body includes `value` and mandatory `change_reason`. Requires `engineering_parameters.manage`.
- `GET /engineering-parameters/{key}/audit-log` — read a parameter's change history. Requires `engineering_parameters.manage` (audit history of a platform-wide policy value is itself sensitive, mirroring [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §13).

Structured error responses per CLAUDE.md A9; persistence models never exposed directly (CLAUDE.md A6).

## 13. Service Interfaces

- Exposes a read-only interface, `get_parameter_value(parameter_key)`, for any module needing a current engineering-parameter value (e.g. the MW tolerance detector, per ADR-022) — consumed via CLAUDE.md A1's service-layer discipline, never a direct table read by the consumer.
- Exposes the write path (`set_parameter_value`) exclusively behind `engineering_parameters.manage`.

## 14. Audit Requirements

Owned exclusively by this module's own `engineering_parameter_audit_log`, per CLAUDE.md A4. Every value change is recorded: who, when, old value, new value, why (mandatory `change_reason`). Audit history is append-only and never modified, per CLAUDE.md §16.

## 15. Security Considerations

- Read: any authenticated user (engineers and reviewers across the platform need to see the current tolerance and other parameters in context, e.g. in the Engineering Workspace and Engineering Review Panel).
- Write: `engineering_parameters.manage`, an elevated, admin-tier permission, distinct from ordinary Editor-tier scheme-design permissions — changing a platform-wide policy value is a platform administration action, not a scheme-design action, mirroring the elevated-tier reasoning already established for `PublicationTreatmentPolicy` changes ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §4.1).
- Audit log read access is gated behind the same `engineering_parameters.manage` permission as writes.

## 16. Testing Requirements

Per CLAUDE.md §18/A11: every value change is audited with a mandatory reason; unauthorized users cannot write; `parameter_key` immutability; per-parameter validation (e.g. `mw_tolerance_percentage` range checks); consuming modules receive the current value through the read service interface, never a stale or cached-incorrectly value.

## 17. Future Extensions

- Additional parameters as future detectors or scheme modules need them (e.g. a validated UFLS/UVLS threshold range, per `ufls-module.md`'s own long-standing recommendation) — each a new `parameter_key` row, no schema change required unless a parameter's shape genuinely differs from key/value/unit/description.
- A future notification-on-change hook (e.g. alerting affected scheme owners when a parameter they depend on changes) is not built now — no evidenced requirement yet (CLAUDE.md §21).

## 18. Risks and Recommendations

No open risks at this time. The module's scope is deliberately narrow (one table plus its audit log); expansion should be evaluated per-parameter against ADR-021's "Why not Reference Data" reasoning to avoid drift back toward conflating engineering parameters with reference/lookup data.
