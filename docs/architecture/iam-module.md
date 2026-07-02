# Identity and Access Management (IAM) Module Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document follows the Canonical Module Architecture Document Template (CLAUDE.md **A8**).

Related documents: [domain-model.md](domain-model.md) §2 (Core Platform domain), [ADR-002](../adr/ADR-002-identity-and-access-management.md) (the decision this document formalizes), and every other module document in this series — each one references `user_id` for accountability and calls into this module's authorization service, making this the one foundational module whose full design every other document has assumed but never itself specified.

> **On completing the foundational layer:** every module built since [ADR-002](../adr/ADR-002-identity-and-access-management.md) — Substation Registry, PSS/E Integration, Network Model, UFLS, UVLS, EMLS, Critical Infrastructure, Cross-Scheme Compliance, Equipment Registry — assumed IAM's existence and referenced `user_id` accordingly, but IAM itself never received the full Canonical Module Architecture Document Template treatment. This document closes that gap. It does not revisit or contradict ADR-002's decisions; it formalizes them, exactly as [psse-integration-module.md](psse-integration-module.md) formalized ADR-003 and [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md) formalized ADR-004.

---

## 1. Module Overview

IAM is the Core Platform module that owns application-level identity and authorization for GridDefence: Users, Roles, Permissions, the assignments between them, and the mapping between a GridDefence identity and any external authentication source. It is the most foundational module in the entire platform — every other module depends on it for accountability and authorization, and it depends on nothing else in GridDefence (CLAUDE.md A2, [domain-model.md](domain-model.md) §2).

IAM's central design commitment, established in [ADR-002](../adr/ADR-002-identity-and-access-management.md) and reaffirmed here: **authentication and authorization are different concerns.** An external identity provider may one day verify *who* a user is; GridDefence's IAM module always decides *what* that user may do, and always resolves every accountable action to one stable, internal `user_id` — regardless of how that user authenticated.

---

## 2. Purpose

To provide a single, authoritative source of truth for identity and authorization, so that:

- Every module's audit trail resolves to a stable, permanent `user_id`, never a free-text name or a locally-invented identity concept (CLAUDE.md §5.1, §5.4).
- Authorization decisions are made in exactly one place, via Role → Permission resolution, and every other module calls into that decision rather than re-implementing it.
- GridDefence can start with local username/password accounts and later adopt LDAP, Active Directory, SSO, or OIDC — for some, all, or a changing mix of users — without any other module changing how it references identity or checks authorization.
- Segregation-of-duties patterns already recommended throughout this series (Editor ≠ Approver, Approver ≠ Activator) have real, assignable roles to be built on, rather than remaining a documentation-only aspiration.
- Fine-grained, module-specific read restrictions — such as the stricter tier already recommended for Critical Infrastructure ([critical-infrastructure-module.md](critical-infrastructure-module.md) §15) — are expressible without inventing a special-case mechanism outside the normal Permission model.

---

## 3. Responsibilities

IAM owns:

- ✓ Users (`User`)
- ✓ Roles (`Role`)
- ✓ Permissions (`Permission`)
- ✓ Role-permission assignments (`RolePermission`)
- ✓ User-role assignments (`UserRole`)
- ✓ External identity mappings (`ExternalIdentityMapping`)
- ✓ The application authorization model — the single decision point every module calls to answer "may this user do this"
- ✓ Its own audit trail (`iam_audit_log`, CLAUDE.md A4)

---

## 4. Non-Responsibilities

IAM does **not** own:

- ✗ Authentication mechanics beyond resolving identity to a `user_id` — the specific mechanism (password hashing algorithm, session/token implementation, MFA challenge flow, SSO handshake) is an implementation concern outside architectural scope; this document specifies the identity/authorization *data model* and *service contract*, not the authentication protocol itself.
- ✗ External identity provider infrastructure (an organisation's actual LDAP/AD/SSO/OIDC deployment) — those are external systems IAM integrates *with*, never owns or operates.
- ✗ Any scheme module's business data, business rules, or domain-specific authorization logic (e.g. "the Draft editor may not also be the Approver" for a specific UFLS version) — IAM provides the structural building blocks (distinct, assignable roles; a reusable actor-comparison utility, §9) but does not enforce scheme-specific segregation-of-duties rules itself (§9 rule 8).
- ✗ Any other module's data whatsoever — Substation Registry, PSS/E Integration, Network Model, UFLS/UVLS/EMLS, Critical Infrastructure, Cross-Scheme Compliance, and Equipment Registry each own their own tables entirely; IAM's only footprint elsewhere is the `user_id` foreign key every one of them holds for accountability.

---

## 5. Owned Entities

| Entity | Description |
|---|---|
| `User` | The stable, permanent identity record every accountable action in GridDefence resolves to. |
| `UserCredential` | Local password credential material, deliberately separated from `User` for tighter access control (§7.1). Present only for accounts that authenticate locally. |
| `Role` | A configurable, named collection of permissions (§7.2). |
| `Permission` | One entry in the centrally-registered, code-defined catalog of authorizable actions across every GridDefence module (§7.3). |
| `RolePermission` | The grant of one `Permission` to one `Role`. |
| `UserRole` | The grant of one `Role` to one `User`, with a validity window (§7.4). |
| `ExternalIdentityMapping` | The mapping between a `User` and an external authentication principal, with a validity window (§7.5). |
| `iam_audit_log` | This module's own audit trail (CLAUDE.md A4), covering all owned entities above. |

---

## 6. Referenced Entities

IAM is the most foundational module in GridDefence (Core Platform domain, [domain-model.md](domain-model.md) §2) — it depends on nothing else in the platform (CLAUDE.md A2). Its only "reference" relationship is to itself:

| Entity | Owned by | Referenced as |
|---|---|---|
| `User` | IAM (self) | `created_by_user_id`/`updated_by_user_id` on every owned entity in §5, including `User` itself — a self-referential foreign key. The bootstrap/first-record exception is addressed explicitly in §9, rule 7. |

External identity providers (LDAP, Active Directory, SSO, OIDC) are **external systems**, not GridDefence modules — IAM integrates with them at the authentication boundary (§7.5, §13), but they are not "referenced entities" in the CLAUDE.md A1 module-communication sense, since no service-interface contract governs them the way it does between GridDefence's own bounded contexts.

---

## 7. Domain Model

```
User (1) ──── (0..1) UserCredential
User (1) ──── (many) UserRole ──── (many) Role
Role (1) ──── (many) RolePermission ──── (many) Permission
User (1) ──── (many) ExternalIdentityMapping

User / Role / UserRole / ExternalIdentityMapping / RolePermission
     ──── references ───▶ User.user_id   (self, created_by/updated_by/granted_by)
```

Every other module in GridDefence holds a `user_id` foreign key into `User` (and, per [ADR-002](../adr/ADR-002-identity-and-access-management.md), an `external_principal_id` + provider fallback for cases where a local `User` record does not yet exist) — those foreign keys are not repeated in this diagram, since they belong to each referencing module's own domain model, not to IAM's.

### 7.1 User Model — Answering Question 1

`User` carries: `user_id` (UUID, CLAUDE.md A5 — a genuine business entity, not reference data), `username` (unique, used for local login and display fallback), `display_name`, `email` (nullable — useful for future notification features, not required for identity itself), `status` (§8), plus standard accountability fields.

**Credential material is deliberately separated into `UserCredential`, not stored on `User` itself.** A `User` row is identity-only and is safe to reference broadly (every module's audit log points at it); `UserCredential` (password hash, hashing algorithm metadata, last-changed timestamp) exists only for accounts that authenticate locally, and warrants tighter access restriction than general identity data (§15). A federated user (§7.5) may have no `UserCredential` row at all. This separation is a deliberate security-architecture choice: identity and secret material have different sensitivity profiles and different consumers, and conflating them on one table would force every reader of basic identity data to also have access to (or at least proximity to) credential material.

### 7.2 Role Model — Answering Question 2

`Role` carries: `role_id` (UUID, CLAUDE.md A5 — Roles are created and renamed within a live authorization model, the same "independent lifecycle" reasoning already used in [ADR-002](../adr/ADR-002-identity-and-access-management.md)), `name` (unique), `description`, `is_system_role` (boolean), `status`.

**Roles are configurable**, per the task's explicit requirement: an administrator may create a new Role and assign it any combination of `Permission` grants, not merely select from a fixed built-in list. GridDefence ships with a small set of system-defined baseline roles (§9, rule 5) marked `is_system_role = true`, which cannot be deleted (though their permission grants may still be adjusted) — this gives every deployment a working starting point (Administrator, a general engineering baseline, a Viewer tier) without forcing every organisation into exactly GridDefence's own default shape for anything beyond that baseline.

### 7.3 Permission Model — Answering Question 3

`Permission` carries: `permission_id` (a stable, code-defined identifier, e.g. `ufls.version.approve`), `label`, `description`, `module_scope` (which module this permission pertains to, for organizing what will become a large catalog as more modules are built).

**Permissions are centrally registered reference data (CLAUDE.md §11.3, and the same code-defined-catalog treatment already applied to `Permission` in [ADR-002](../adr/ADR-002-identity-and-access-management.md), `ComplianceRuleConfig` in [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md) §5, and `CriticalityLevel` in [critical-infrastructure-module.md](critical-infrastructure-module.md) §5) — the catalog's *existence* is centrally owned by IAM, but its *content* is driven by what every other module's service layer actually checks.** In practice this means: when a new module is built (or a new module doc's Security Considerations section names a new permission, as every module in this series has done — e.g. `ufls.version.approve`, `critical_infrastructure.asset.write`, `compliance.rule_config.write`), a corresponding `Permission` catalog entry is registered in IAM as part of that module's own deployment/seed process — never written at runtime by the other module's own service layer, which would violate module boundaries (CLAUDE.md A1). A `Permission` row, once created, is immutable in meaning: if a module's authorization needs change, a new permission code is introduced and the old one deprecated, never silently repurposed (§9, rule 4).

### 7.4 User-Role Assignment

`UserRole` links a `User` to a `Role`, carrying `granted_at` and a nullable `revoked_at` — the same validity-window pattern already established repeatedly across this series (`substation_alias`, `CriticalAssetSubstation`, `EquipmentAlias`). A revoked assignment is never deleted; it remains a permanent record of who had what access, and for how long — directly supporting audit reconstruction of "what could this user do at the time of this action" (§14).

### 7.5 External Identity Mapping — Answering Question 4

`ExternalIdentityMapping` links a `User` to an external authentication principal: `external_principal_id` (the subject identifier issued by the provider — an LDAP DN, an AD object identifier, an OIDC `sub` claim), `provider` (which system issued it), and the same `linked_at`/`unlinked_at` validity window used for `UserRole`. A `User` may have **zero, one, or several** concurrent mappings — zero for a purely local account, one for a straightforwardly federated user, or several during a provider migration (e.g. a user retaining a historical AD mapping while a new OIDC mapping is established, exactly the scenario [ADR-002](../adr/ADR-002-identity-and-access-management.md) anticipated). GridDefence never uses an external identifier as a primary key anywhere (CLAUDE.md §11.1, A5) — the internal `user_id` remains the only durable reference every other module holds.

### 7.6 Authentication vs. Authorization Boundary — Answering Question 5

Restated precisely, as the load-bearing architectural boundary of this entire module: **authentication verifies who a user is; authorization decides what they may do.** Authentication may occur locally (`UserCredential`) or be delegated to an external provider (`ExternalIdentityMapping`) — GridDefence does not mandate one over the other, and different users may authenticate differently at the same time. **Authorization never varies by authentication method.** `hasPermission(user_id, permission_code)` (§13) resolves purely through `User → UserRole → Role → RolePermission → Permission`, with no branch on whether the underlying `user_id` came from a local login or a federated one. This is the concrete mechanism behind [ADR-002](../adr/ADR-002-identity-and-access-management.md)'s core commitment, and the reason every other module in this series has been able to reference `user_id` without ever needing to know or care how that user authenticated.

### 7.7 Maker-Checker / Segregation of Duties — Answering Question 6

IAM's contribution to segregation of duties is **structural, not prescriptive**: distinct, independently-assignable roles per responsibility tier (Editor, Reviewer, Approver, Activator — already recommended identically across [ufls-module.md](ufls-module.md) §15, [uvls-module.md](uvls-module.md) §15, [emls-module.md](emls-module.md) §15) exist as real, grantable `Role` rows, so an organisation *can* assign them to different people. **IAM does not itself enforce "the Draft editor may not also be the Approver" for any specific scheme version** — that is scheme-specific business logic (comparing two `user_id` values recorded on a specific `UflsSchemeVersion`, for instance), and belongs in each scheme module's own business rules, not in IAM, which has no knowledge of "UFLS versions" or any other module's domain concepts (§4). What IAM *does* provide, as a reusable convenience, is a generic **actor-comparison service interface** (§13) — `assertDifferentActors(user_id_a, user_id_b)` or equivalent — that any scheme module may call to implement its own segregation-of-duties check without re-deriving the comparison logic independently three (or more) times. This mirrors the "shared Rule 7/8 validation utility" pattern already flagged as worth factoring out once a second scheme module existed ([ufls-module.md](ufls-module.md) §17, §18) — the same reasoning applies here.

### 7.8 Approval and Activation Permissions — Answering Question 7

Each scheme module registers its own approval/activation permission codes in IAM's catalog (§7.3): `ufls.version.approve`, `ufls.version.activate`, `uvls.version.approve`, `uvls.version.activate`, `emls.version.approve`, `emls.version.activate`, and their equivalents for any future Defence Scheme module. IAM has no special-cased knowledge of what "approve" or "activate" means for any particular scheme — these are opaque permission codes to IAM, checked identically to any other permission, with all scheme-specific meaning residing entirely in the calling module.

### 7.9 Admin Permissions — Answering Question 8

Administrative/elevated permissions follow the same registration pattern, scoped per module: `iam.role.manage` (creating/editing Roles and their grants — itself gated, §15), `critical_infrastructure.asset.write` (elevated per [critical-infrastructure-module.md](critical-infrastructure-module.md) §15), `compliance.rule_config.write` (elevated per [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md) §15), and equivalents for any module with a similarly sensitive configuration surface. GridDefence's built-in `Administrator` system role (§7.2) bundles the full set of these, but individual elevated permissions may also be granted standalone via a custom `Role`, supporting finer-grained administrative delegation than an all-or-nothing superuser flag would allow.

### 7.10 Read-Only Viewer Roles — Answering Question 9

**IAM supports more than one read tier, not a single flat "Viewer."** A baseline `Viewer` system role grants broad read permissions across ordinary engineering data (mirroring the "read access broader than write access" pattern established in every module's own Security Considerations section throughout this series). But [critical-infrastructure-module.md](critical-infrastructure-module.md) §15 explicitly recommended a **stricter**, separate read tier for critical-asset data — this is directly realizable because `critical_infrastructure.asset.read` is its own distinct permission code, deliberately **not** bundled into the baseline `Viewer` role by default; an administrator must grant it separately (or via a dedicated `Critical Infrastructure Viewer` role, §7.9) to the specific users who need it. This closes the loop that module's own document opened (§15 of this document, Question 15).

---

## 8. Lifecycle / State Model

`User`, `Role`, and `Permission` are **not** governed by the Canonical Version Lifecycle (CLAUDE.md A3) — the same reasoning already applied consistently to every Master Data entity in this series: this is current-state identity/authorization data with a full audit trail (CLAUDE.md §11.5), not approved engineering policy requiring a Draft/Review/Approve workflow.

- `User.status`: `Active → Suspended → Deactivated`. Soft-delete only (CLAUDE.md §11.6) — a `User` row is never physically deleted, since every other module's audit log may hold a permanent, immutable reference to it.
- `Role.status`: `Active → Retired`, soft-delete only, for the same reason (a retired `Role`'s historical `UserRole` grants remain meaningful audit history).
- `Permission` rows are effectively append-only reference data (§7.3) — retired, never deleted, once any historical `RolePermission` grant has referenced them.
- `UserRole` and `ExternalIdentityMapping` use the `granted_at`/`revoked_at` and `linked_at`/`unlinked_at` validity-window pattern (§7.4, §7.5) rather than a formal state machine.
- Every change is captured in the audit log (§14) regardless of the lack of an approval lifecycle.

---

## 9. Business Rules

1. Every accountable action in GridDefence resolves to exactly one `User.user_id`, or — during a transitional federation scenario before a local `User` record exists — an `external_principal_id` + provider pair, per [ADR-002](../adr/ADR-002-identity-and-access-management.md)'s "either/or, never neither" rule. **No module may invent its own local user table** (task requirement, restated from [ADR-002](../adr/ADR-002-identity-and-access-management.md)).
2. A `User` may have zero or one `UserCredential` and zero or more `ExternalIdentityMapping` rows, in any combination — these are independent, not mutually exclusive (§7.1, §7.5).
3. Authorization is always evaluated via `User → UserRole → Role → RolePermission → Permission` resolution; it never varies based on how the user authenticated (§7.6).
4. A `Permission`'s meaning is immutable once registered; a changed authorization need is expressed as a new permission code, with the old one deprecated, never repurposed (§7.3).
5. GridDefence ships with system-defined baseline `Role`s (`Administrator`, a general engineering baseline, `Viewer`) marked `is_system_role = true`; these cannot be deleted, though their specific permission grants remain administratively adjustable. Custom roles beyond this baseline are fully configurable (§7.2).
6. `UserRole` and `ExternalIdentityMapping` grants are ended by setting `revoked_at`/`unlinked_at`, never by deleting the row — full historical access accountability is preserved permanently (CLAUDE.md §5.2).
7. Every write to `User`, `Role`, `RolePermission`, `UserRole`, or `ExternalIdentityMapping` requires an authenticated, named actor and is audited (§14) — **except the bootstrap/seed record(s)** created during initial system setup, which are explicitly exempted from the self-referential `created_by_user_id` requirement and are instead recorded in the audit log under a distinct, clearly-labeled system-bootstrap marker (never a silent `NULL` actor).
8. **IAM does not enforce scheme-specific segregation-of-duties rules.** It provides the structural building blocks (§7.2) and an optional reusable actor-comparison utility (§7.7, §13); the specific rule (e.g. "Draft editor ≠ Approver for this UFLS version") remains each scheme module's own business rule.
9. **No engineering data read or write in GridDefence is available to an unauthenticated actor** — every access, including the lowest-privilege `Viewer` tier, requires a resolved `user_id` (§7.10, Question 14; §15).
10. IAM has no knowledge of any other module's domain concepts beyond opaque `permission_code` strings it stores and checks (§4) — it never special-cases "UFLS," "Critical Infrastructure," or any other module by name in its own business logic.
11. An authorization check against an unregistered or unrecognized `permission_code` **must fail closed (deny)**, never fail open (allow) — a missing or misconfigured permission catalog entry is a configuration defect, never a reason to silently grant access (§12, §15).

---

## 10. Validation Rules

- `User.username` must be unique, case-insensitively.
- `Permission.permission_id`/`permission_code` must be unique and, once created, immutable in meaning (§9, rule 4).
- `Role.name` must be unique.
- `UserRole.revoked_at`, if set, must be greater than or equal to `granted_at`.
- `ExternalIdentityMapping.unlinked_at`, if set, must be greater than or equal to `linked_at`.
- The pair `(external_principal_id, provider)` must be unique among **currently linked** (`unlinked_at IS NULL`) `ExternalIdentityMapping` rows — no two `User` records may simultaneously claim the same external identity.
- `UserCredential.password_hash` must never be stored as, or derived from, plaintext — a hashed representation using an approved algorithm is architecturally mandated (the specific algorithm is an implementation detail, not fixed by this document).
- A `RolePermission` grant must reference an existing `Permission`; a `UserRole` grant must reference an existing, non-`Retired` `Role`.

---

## 11. Database Design (Concept)

Conceptual only — no migrations are defined here.

| Table (conceptual) | Key columns (conceptual) | Notes |
|---|---|---|
| `user` | `user_id` (UUID PK), `username` (unique), `display_name`, `email` (nullable), `status`, `created_by_user_id` (self FK, nullable for bootstrap), `updated_by_user_id` (self FK, nullable), `created_at`, `updated_at` | UUID PK per CLAUDE.md A5. |
| `user_credential` | `user_id` (PK/FK to `user`), `password_hash`, `hash_algorithm`, `last_changed_at` | Present only for locally-authenticating accounts (§7.1); deliberately separated from `user` for access-control segregation. |
| `role` | `role_id` (UUID PK), `name` (unique), `description`, `is_system_role` (boolean), `status`, `created_by_user_id`, `updated_by_user_id`, `created_at`, `updated_at` | |
| `permission` | `permission_id` (stable code, e.g. text PK such as `ufls.version.approve`), `label`, `description`, `module_scope`, `created_at` | Code-defined reference catalog (§7.3); registered per-module during that module's own deployment, not written at runtime by other modules. |
| `role_permission` | `role_id` (FK), `permission_id` (FK), `granted_at`, `granted_by_user_id` (FK) | Composite key on (`role_id`, `permission_id`). |
| `user_role` | `id` (BIGINT PK), `user_id` (FK), `role_id` (FK), `granted_at`, `revoked_at` (nullable), `granted_by_user_id` (FK) | Validity-window pattern (§7.4). |
| `external_identity_mapping` | `id` (BIGINT PK), `user_id` (FK), `external_principal_id`, `provider`, `linked_at`, `unlinked_at` (nullable), `linked_by_user_id` (FK, nullable — may be self-service on first federated login) | Unique on (`external_principal_id`, `provider`) where `unlinked_at IS NULL` (§10). |
| `iam_audit_log` | `log_id` (BIGINT PK), `entity_type`, `entity_id`, `field_name`, `old_value`, `new_value`, `changed_at`, `changed_by_user_id` (nullable only for the bootstrap exception, §9 rule 7), `change_reason` | Owned per CLAUDE.md A4. |

**Cross-module constraints:** every other module's `user_id` foreign key (already specified in each module's own Database Design section throughout this series) is `ON DELETE RESTRICT` into this module's `user` table — consistent with `User` rows never being physically deleted (§8). IAM's own tables are written to exclusively by IAM's own service layer.

---

## 12. API Contract (Concept)

APIs are external/UI-facing contracts (CLAUDE.md §13, A9); conceptual resource shape only.

- `users`, `users/me` — list/retrieve identity records; `users/me` mirrors the legacy MVP's precedent of a current-user endpoint, now returning role/permission summary rather than just `is_staff`/`is_superuser` flags.
- `users/{id}/roles` — manage a user's role assignments (grant/revoke, §7.4).
- `users/{id}/external-identities` — manage a user's federated identity mappings (§7.5).
- `roles`, `roles/{id}/permissions` — manage roles and their permission grants; write access gated to `iam.role.manage` (§7.9, §15).
- `permissions` — read-only catalog listing, for populating role-configuration UI.
- Authentication-adjacent endpoints (login/logout/session or token issuance) exist conceptually but their exact shape is an implementation detail outside this document's scope (§4) — this contract only specifies that such endpoints resolve to a `user_id` and do not themselves carry authorization logic.

**Contract requirements (CLAUDE.md A9):** pagination/filtering for collection endpoints; structured error responses; authentication/authorization per endpoint; audit-relevant actions flagged (all writes to §5's owned entities).

**Data contracts:** standard three-layer separation (CLAUDE.md A6) — in particular, `UserCredential` is never returned in any API response shape, under any circumstance.

---

## 13. Service Interfaces

Per CLAUDE.md A1 (module communication via in-process service-layer interfaces) — **answering Question 11**:

**IAM exposes, for every other module to consume:**
- **`hasPermission(user_id, permission_code) → boolean`** — the single authorization decision point every other module's service layer calls before any write or lifecycle-transition operation, already referenced by name throughout this entire document series. Fails closed on an unrecognized `permission_code` (§9, rule 11).
- **`getUser(user_id) → user summary`** — a read-only lookup (display name, username) for rendering audit trails and approval records human-readably, without every module needing to duplicate user display data.
- **`resolveExternalPrincipal(external_principal_id, provider) → user_id`** — used during a federated authentication flow to resolve an external identity to GridDefence's internal `user_id`.
- **`assertDifferentActors(user_id_a, user_id_b) → boolean`** — the reusable segregation-of-duties helper (§7.7), available to any scheme module wanting to enforce "the drafter may not also be the approver" without re-deriving the comparison independently.
- **`listUserRoles(user_id) → roles/permissions summary`** — for a module wanting to display or reason about a user's current access without duplicating role logic.

**IAM consumes:** nothing from other GridDefence modules — it is the most foundational module and depends on none of them (CLAUDE.md A2, §6). Its only external dependency is the authentication boundary to external identity providers (LDAP/AD/SSO/OIDC), which is an integration concern (§4), not an internal module-communication relationship.

No other module calls IAM's repository directly, and IAM writes exclusively through its own service layer, per CLAUDE.md A1 and [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md). **This is the mechanism that lets future LDAP/AD/SSO/OIDC integration happen without requiring every domain module to change** (task requirement): every other module already calls `hasPermission`/`getUser` against an opaque `user_id`; how that `user_id` came to be authenticated is entirely IAM's internal concern.

---

## 14. Audit Requirements — Answering Question 10

Per CLAUDE.md §5.4 and A4, IAM owns and writes its own audit log, covering every owned entity in §5, and additionally governs how every *other* module records identity in its own audit trail:

- **The "either/or, never neither" rule** (established in [ADR-002](../adr/ADR-002-identity-and-access-management.md), restated here as IAM's own requirement): every audit record across every GridDefence module must resolve to either a `user_id` or an `external_principal_id` + provider pair — never neither.
- Every change to `Role`, `Permission`, `RolePermission`, `UserRole`, or `ExternalIdentityMapping` is audited with particular emphasis — these are access-control changes, at least as safety-relevant as the `ManualOverride` and `restriction_type` changes already treated with elevated audit scrutiny in [network-model-module.md](network-model-module.md) §14 and [critical-infrastructure-module.md](critical-infrastructure-module.md) §14.
- The bootstrap exception (§9, rule 7) is itself recorded in the audit log under a distinct, clearly-labeled system-bootstrap marker — never a silently missing or null actor.
- Audit history is append-only and never modified; audit log access is itself access-controlled, gated by a dedicated permission distinct from general engineering-data read access (§15).

---

## 15. Security Considerations — Answering Question 12

- **All GridDefence engineering data is sensitive by default** (CLAUDE.md A10), and IAM's own data — credentials and access-control configuration — is more sensitive still.
- **`UserCredential` requires stricter access control than any other table in this module**, let alone the platform generally — no API response shape ever includes it (§12), and only IAM's own authentication-handling code path may read it.
- **Fail-closed authorization is the single most important security property of this module** (§9, rule 11): an unrecognized `permission_code`, a misconfigured `RolePermission` grant, or any ambiguity in resolution must deny, never silently allow.
- **Managing `Role`/`Permission` grants requires the `iam.role.manage` permission**, held by the `Administrator` system role and any custom role an administrator explicitly extends it to — this is the most powerful permission in the system (it can grant any other permission) and must be treated accordingly.
- **Role sprawl is a real risk** in a fully-configurable role model: an unmanaged proliferation of ad hoc custom roles over time can make the effective authorization surface hard to reason about. This document recommends periodic administrative review of the role catalog (§18), not a hard architectural limit on role creation.
- Local credential handling (password hashing algorithm, brute-force/rate-limiting protection on login attempts) follows industry-standard practice; the legacy MVP's DRF throttling precedent (anonymous/user rate limits) is a reasonable baseline to carry forward at the infrastructure level, though the specific implementation is outside this document's scope (§4).
- Module-to-module service calls (every other module's `hasPermission`/`getUser` calls) are trusted internal code paths within the modular monolith (CLAUDE.md A1) — not themselves gated by a further permission check; the permission check *is* the service call's own purpose.

---

## 16. Testing Requirements

Per CLAUDE.md §18 and A11, in priority order:

1. **Business rule tests** — fail-closed behaviour on an unrecognized `permission_code` (§9 rule 11) is the single highest-priority test in this module; authorization resolution correctness across `User → UserRole → Role → RolePermission → Permission`, independent of authentication method (§7.6); validity-window correctness for `UserRole`/`ExternalIdentityMapping`; uniqueness of `(external_principal_id, provider)` among currently-linked mappings; the bootstrap exception's audit behaviour (§9 rule 7).
2. **Engineering calculation / validation tests** — `assertDifferentActors` correctness; username/role-name uniqueness enforcement.
3. **API contract tests** — confirming `UserCredential` is never present in any response payload, under any circumstance; authorization enforcement per endpoint.
4. **Database migration tests** — required once actual migrations are authored.
5. **UI behaviour tests** — required once an IAM-facing frontend (role/permission management) exists.

Business rules and calculations must not be merged without accompanying tests (CLAUDE.md A11) — the fail-closed authorization test in particular should be treated as a release-blocking regression test given its platform-wide blast radius.

---

## 17. Future Extensions

- **Concrete LDAP/AD/SSO/OIDC provider integration** — the data model (`ExternalIdentityMapping`) and service contract (`resolveExternalPrincipal`) already support this structurally (§7.5, §13); a Future Extension is wiring an actual provider adapter, not redesigning this module.
- **Multi-factor authentication (MFA)** — an authentication-mechanism enhancement (§4), layered on top of whichever authentication path (local or federated) a user takes, without changing the authorization model this document specifies.
- **Self-service password reset and account recovery flows** — authentication-mechanism concerns, deferred per §4.
- **Resource-scoped permissions** (e.g. a permission limited to a specific region or substation set, rather than module-wide) — not needed by any module built so far, and deliberately not designed here to avoid premature abstraction (CLAUDE.md §26); would extend `RolePermission`/`UserRole` with a scope qualifier if a real need emerges.
- **A formalized `assertDifferentActors`-based segregation-of-duties utility library**, consumed identically by UFLS, UVLS, and EMLS, rather than each independently choosing whether to call it — echoing the same "shared validation utility" Future Extension already flagged in [ufls-module.md](ufls-module.md) §17.

---

## 18. Risks and Recommendations — Answering Question 12 (continued)

| Risk | Impact | Recommendation |
|---|---|---|
| A misconfigured or missing `Permission` catalog entry for a `permission_code` a module's service layer checks | Fail-closed design (§9 rule 11) means this manifests as *denied* access, not a security breach — but it is still an operational/availability risk | Recommend a startup/deployment-time consistency check confirming every `permission_code` referenced in code has a corresponding registered `Permission` row, catching drift before it reaches production |
| Role sprawl (§15) — an unmanaged proliferation of custom roles over time | Authorization surface becomes hard to reason about; increases the chance of an over-privileged role going unnoticed | Recommend periodic administrative review of the role catalog and actual `UserRole` grants, as an organisational process (not enforced architecturally) |
| `UserCredential` compromise (weak hashing, credential-stuffing, brute force) | Direct compromise of local accounts | Mandate industry-standard password hashing and login rate-limiting at implementation time; recommend federated authentication (§7.5) as the preferred path for any organisation with an existing enterprise identity provider, reducing local credential exposure |
| Segregation-of-duties remaining optional per scheme module (§7.7, §9 rule 8) rather than architecturally mandatory | A scheme module could, in principle, be built or configured without ever calling `assertDifferentActors`, silently permitting a single user to draft and approve unchecked | Flagged as a genuine open policy question requiring Project Owner ratification (closing summary) — this document intentionally does not make segregation of duties an IAM-enforced hard constraint, since IAM cannot know a scheme module's specific workflow, but whether it *should* become mandatory platform-wide policy is worth deciding explicitly rather than leaving as a per-module recommendation indefinitely |
| The bootstrap/first-user exception (§9 rule 7) becoming a template for future "just this once, no audited actor" shortcuts elsewhere in the system | Erosion of the "every action has a who" principle (CLAUDE.md §5.4) if the exception is copied casually | Keep the bootstrap exception narrowly scoped to genuine initial-system-setup, with its own distinct audit marker (§14) — never a general-purpose escape hatch |

---

## MVP Behaviours Preserved

- The concept of a `users/me` endpoint returning the current authenticated actor's identity and access summary — preserved in shape, now returning role/permission data instead of just `is_staff`/`is_superuser` flags.
- Local username/password authentication as one supported path — the legacy MVP's session-based local login remains a valid authentication mechanism under this design, just no longer the *only* one, and no longer conflated with authorization.
- Rate-limiting/throttling as a sound baseline security practice, worth carrying forward at the infrastructure level (§15), even though DRF-specific implementation details do not transfer directly.

## MVP Behaviours Redesigned

- **The flat `is_staff`/`is_superuser` two-tier model is redesigned into a full Role/Permission system** — answering Question 13. The legacy MVP had no Django Groups/Permissions usage at all (per the Codebase Discovery Report), only two boolean flags. GridDefence's migration path: `is_superuser` maps conceptually to the built-in `Administrator` system role (broad permissions); non-superuser `is_staff` maps to a broad baseline "Engineer" role bundling Editor-tier permissions across modules. This is deliberately a **coarse, transitional bootstrap mapping, not an automatic transformation** — the MVP's flat model has no way to express who *should* hold Approver vs. Activator vs. Editor permissions specifically, since it never distinguished them. The recommended migration process is: (1) bootstrap every existing MVP user into the coarse Administrator/Engineer mapping so the system remains usable immediately after cutover, then (2) as a deliberate, human-reviewed follow-up — not an automated step — refine individual users into the proper segregation-of-duties role assignments (Editor, Reviewer, Approver, Activator per module) that the flat MVP model could never represent.
- **Permission granularity**: from two hardcoded flags to a centrally-registered, per-module permission catalog (§7.3), enabling exactly the kind of fine-grained distinction (e.g. a separate Critical Infrastructure read tier, §7.10) the MVP's model had no way to express.

## MVP Behaviours Discarded

- **Anonymous/guest read access — answering Question 14, discarded outright, not carried forward in any form.** The legacy MVP's `ANONYMOUS_USER` sentinel allowed unauthenticated browsing of engineering data. GridDefence's CLAUDE.md A10 baseline ("all engineering data is sensitive by default... authentication required for all non-public endpoints") is applied here without a public-read carve-out: even basic substation or scheme data has operational security value (grid topology and asset locations) that a typical enterprise CRUD application's "public read" convention does not adequately weigh for critical infrastructure software. The lowest-privilege tier in GridDefence is an authenticated `Viewer`, not an anonymous visitor (§7.10, §9 rule 9).
- The self-registration endpoint (disabled by default in the MVP, and already flagged as unnecessary in the original Codebase Discovery Report) — not carried forward; user provisioning is an administrative or federated-identity-driven action, not self-service signup, consistent with GridDefence's accountability requirements for engineering approvals.

## Architectural Decisions Still Requiring an ADR

1. **Whether segregation of duties should become an IAM-enforced, platform-wide mandatory constraint rather than a per-scheme-module recommendation** (§7.7, §9 rule 8, §18) — a genuine values decision, similar in kind to the `Superseded → Active` reactivation and Rule 2 manual-invocation severity questions already flagged as needing Project Owner ratification in [ufls-module.md](ufls-module.md) and [emls-module.md](emls-module.md) respectively.
2. **Which specific external identity provider(s) GridDefence will actually integrate with first** (LDAP, Active Directory, a specific OIDC provider) — not an architectural question this document needs to answer (the data model and service contract are provider-agnostic by design, §7.5, §13), but the concrete integration, once undertaken, may warrant its own ADR if it introduces provider-specific constraints this document did not anticipate.
3. **Formal credential and session security policy** (password hashing algorithm choice, rotation policy, MFA requirement thresholds, session/token lifetime) — deferred here as an implementation-level security decision (§4), but whether these should themselves be treated as versioned, configurable engineering parameters (CLAUDE.md A7) rather than fixed application constants is worth a small ADR when first implemented.
