# ADR-002: Identity and Access Management

- **Status:** Accepted
- **Date:** 2026-07-01
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1, §5.4, §8, §11.1, §17, A2, A4, A5, A10)
- **Depends on:** [ADR-000: Architecture Principles](ADR-000-architecture-principles.md), [ADR-001: Modular Monolith and Module Communication](ADR-001-modular-monolith-and-module-communication.md)
- **Affects:** [docs/architecture/domain-model.md](../architecture/domain-model.md), [docs/architecture/substation-registry.md](../architecture/substation-registry.md)

---

## Context

Every module's audit trail must record who performed an engineering action (CLAUDE.md §5.4, "Who, When, Why, What changed"), and CLAUDE.md A4 assigns audit ownership per module — but no document to date assigns ownership of the identity concept that "who" actually refers to.

[docs/architecture/domain-model.md](../architecture/domain-model.md) already anticipated this gap: it places "Identity/Principal data" under the Core Platform domain but explicitly marks it **"reserved, not yet implemented,"** and warns that no module's audit trail should depend on it as a real foreign key until it is formally scoped. [docs/architecture/substation-registry.md](../architecture/substation-registry.md) worked around the gap by specifying `created_by`/`updated_by` as free-text `VARCHAR(100)` fields — a placeholder, not a durable design.

CLAUDE.md §17 (Security Standards) requires role-based authorization and anticipates future RBAC, MFA, SSO, and LDAP/Active Directory integration, but does not say who owns the underlying Users/Roles/Permissions data model, nor how it relates to an eventually-federated authentication source.

This decision cannot wait: UFLS, UVLS, EMLS, and every future scheme module will need the same "who" concept for their own per-module audit logs (CLAUDE.md A4) and for role-based approval gating (CLAUDE.md A10 — "engineering approval actions require authenticated named users"). Left unresolved, each module would independently invent its own notion of identity, which directly violates Single Source of Truth (CLAUDE.md §5.1) — the same failure mode the Domain Ownership model (§8) exists to prevent.

---

## Decision

GridDefence owns a dedicated **Identity and Access Management (IAM)** bounded context, placed in the **Core Platform domain** (per [domain-model.md](../architecture/domain-model.md) §2), the most foundational domain in the dependency hierarchy. IAM depends on nothing else in the platform; every other module may depend on it (CLAUDE.md A2).

### What IAM Owns

- **User** — the durable, application-level identity record. Primary key `user_id` is a UUID (CLAUDE.md A5 — User is a business entity, not reference data), immutable and never reused, consistent with every other business entity in the platform (CLAUDE.md §11.1).
- **Role** — an administratively defined authorization grouping (e.g. "Scheme Approver," "Substation Registry Editor"). Modeled as a business entity with a UUID primary key, not as static reference data: roles are created, renamed, and evolve within a live authorization model, which is the kind of "specific architectural reason" CLAUDE.md A5 allows for deviating from simple lookup-table treatment.
- **Permission** — the fixed catalog of capabilities the codebase implements (e.g. "approve-scheme-version," "edit-substation"). Modeled as reference/lookup data (CLAUDE.md §11.3), since the permission catalog is defined by what the system implements, not by end users.
- **Role-Permission** and **User-Role** associations — owned by IAM, defining who has which permissions.
- **Federated identity mapping** — for users authenticated by an external identity provider, IAM stores `external_principal_id` (the subject identifier issued by that provider — e.g. an LDAP DN, AD object identifier, or OIDC `sub` claim) together with provider metadata (provider name/type and any claims needed to derive roles), mapped to exactly one internal `user_id`. GridDefence never uses an external identifier as a primary key (CLAUDE.md §11.1, A5) — the internal UUID remains the only durable identity FK used anywhere else in the platform.

### Authentication vs. Authorization

- **Authentication** (verifying who someone is) may be performed locally today and delegated to an external provider (LDAP/AD, SSO/OIDC) in the future, per CLAUDE.md §17. This ADR does not select or mandate a specific authentication mechanism or library — that is an implementation decision to be made when the integration is built.
- **Authorization** (what an authenticated user may do) and the durable internal identity record used for ownership and audit purposes are always owned by GridDefence's IAM context, regardless of where or how authentication happens. Other modules never implement their own role/permission logic — they call into IAM's service layer to ask whether a given `user_id` holds a given permission, per the module communication rules in CLAUDE.md A1 / ADR-001.

---

## Impact on Audit Records

- Every module's per-module audit log (CLAUDE.md A4 — e.g. `substation_audit_log`, and future `ufls_audit_log`, `uvls_audit_log`, `emls_audit_log`) records the acting principal as a `user_id` foreign key to IAM's `User`, replacing any free-text "changed by" field.
- Where the acting principal is a federated identity not yet resolved to a local `user_id` (for example, mid-provisioning on a user's first SSO login, or an external system principal GridDefence does not provision as a full local user), the audit record instead captures `external_principal_id` and provider metadata directly, so "who" is never lost for want of a local record.
- This is an **either/or, never neither** rule: every audit record must resolve to at least one of (`user_id`) or (`external_principal_id` + provider). This satisfies CLAUDE.md §5.4's non-negotiable requirement that every important action record who performed it, without forcing premature provisioning of a full local user record.
- IAM audits itself the same way every other module audits its own data (CLAUDE.md A4, no special-casing): changes to Users, Roles, Permissions, and their associations are recorded in an IAM-owned audit log.
- **Follow-up required:** [substation-registry.md](../architecture/substation-registry.md)'s `created_by`/`updated_by` fields were specified as placeholder `VARCHAR(100)` values before IAM ownership was decided. They should be revised to `user_id` foreign keys (with the federated fallback above) in a follow-up update to that document. This ADR does not modify that document directly.

---

## Impact on Future LDAP/AD/SSO/OIDC Integration

- LDAP/AD/SSO/OIDC integration plugs in as an **authentication provider behind IAM's existing internal `User` model.** No other module (Substation Registry, UFLS, UVLS, EMLS, or any future scheme module) needs to change when this happens, because they only ever reference IAM's stable internal `user_id` — never an external principal identifier directly.
- IAM's federated-identity mapping is designed to support multiple providers, sequentially or concurrently (e.g. starting with local accounts, later adding SSO/OIDC, potentially migrating identity providers again later) without changing the internal `user_id` that every other module's foreign keys and audit records already depend on.
- Deriving roles from federated group claims (e.g. an Active Directory group mapping to a GridDefence Role) is an IAM-internal mapping concern. Other modules remain unaware of how a user's roles were derived — they only ever ask IAM's service layer whether a `user_id` holds a given permission (CLAUDE.md A1).
- MFA, SSO session handling, and token/credential management are authentication-mechanism implementation details, explicitly out of scope for this ADR (CLAUDE.md §17 lists them as future security enhancements). This ADR fixes the identity/authorization *ownership and data model* decision; it does not select an authentication mechanism.

---

## Consequences

**Positive:**
- Closes the gap [domain-model.md](../architecture/domain-model.md) flagged as "reserved, not yet implemented" — every module now has a concrete, stable identity concept to reference instead of inventing its own.
- Preserves Single Source of Truth (CLAUDE.md §5.1): identity and authorization exist in exactly one place, referenced by every other module, never duplicated.
- Decouples authentication mechanism from authorization and audit: GridDefence can start with local accounts and later adopt LDAP/AD/SSO/OIDC without touching any other module's audit trail or permission checks, since they all key off the stable internal `user_id`.
- Fits cleanly into the existing dependency model: IAM sits in Core Platform, the most foundational domain, and depends on nothing else (CLAUDE.md A2, ADR-001).

**Negative / trade-offs:**
- IAM becomes a hard prerequisite for other modules' audit trails and approval-gating logic to be "real" rather than placeholder — this makes IAM one of the first modules that must be built, alongside or immediately after the Substation Registry, which is a sequencing consideration for the roadmap.
- Every per-module audit log must accommodate a `user_id` FK plus an external-identity fallback path, adding modest complexity to the otherwise simple per-module audit log pattern established by CLAUDE.md A4.
- Requires follow-up documentation changes: [domain-model.md](../architecture/domain-model.md)'s Core Platform section should be updated to mark Identity/Principal as an active module rather than "reserved," and [substation-registry.md](../architecture/substation-registry.md)'s audit fields should be revised to reference `user_id`. Neither is performed by this ADR; both are tracked as necessary follow-ups.
- A full IAM module architecture document (using the Canonical Module Architecture Document Template, CLAUDE.md A8, per the process in [docs/architecture/README.md](../architecture/README.md)) is required before implementation begins, per CLAUDE.md §24.

---

## Alternatives Considered

1. **Treat the external identity provider as the sole system of record — store only `external_principal_id` everywhere, with no local `User` table.** Rejected. External identifiers are not guaranteed stable across a provider migration (e.g. moving from AD to an OIDC-based IdP), and CLAUDE.md A5 / §11.1 already establish that external/business identifiers must never serve as primary keys. Every other module's FKs and audit records need an identifier guaranteed never to change or be reused.

2. **Let each module manage its own local notion of "who" independently** (as the initial Substation Registry design implicitly did with a free-text field). Rejected. This directly violates Single Source of Truth (CLAUDE.md §5.1) and Domain Ownership (§8): it would duplicate identity and authorization logic across every module and make consistent role-based authorization impossible to enforce.

3. **Defer identity/access ownership entirely, treating it as a "Deferred Standard" (CLAUDE.md A15), to be resolved only when LDAP/AD/SSO integration is actually built.** Rejected. Unlike CI/CD or observability, identity is not a deferrable concern — it is a hard prerequisite for Auditability (§5.4) and Authorization (§17), both already active requirements for the Substation Registry and imminent for UFLS/UVLS/EMLS. Deferring further would force every module to either block or invent ad hoc identity handling that would need retrofitting later, at far greater cost than deciding now.

4. **Model Role and Permission uniformly as simple reference/lookup tables**, identical in treatment to Voltage Level or Region. Rejected for Role, accepted for Permission. Permission behaves like a fixed, codebase-defined capability catalog and fits reference-data treatment (CLAUDE.md §11.3). Role does not: roles are administratively created, renamed, and assigned within a live authorization model — the kind of independent lifecycle CLAUDE.md A5 treats as sufficient architectural reason to model an entity as a business entity with a UUID key rather than a simple lookup value.
