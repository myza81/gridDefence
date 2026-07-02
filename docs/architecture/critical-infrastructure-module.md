# Critical Infrastructure Module Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document follows the Canonical Module Architecture Document Template (CLAUDE.md **A8**).

Related documents: [system-overview.md](system-overview.md), [domain-model.md](domain-model.md), [substation-registry.md](substation-registry.md), [ufls-module.md](ufls-module.md), [network-model-module.md](network-model-module.md), [ADR-000](../adr/ADR-000-architecture-principles.md), [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md), [ADR-002](../adr/ADR-002-identity-and-access-management.md), [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) (the decision this module completes a dependency for).

---

## 1. Module Overview

Critical Infrastructure is the module that records which substations serve critical loads — hospitals, government facilities, national security assets, water treatment, data centres, and similar — and under what shedding restriction policy each one operates. It exists to answer one question, precisely and auditably: *"is this substation critical, at what level, and may it be shed at all?"*

This module was identified as a concrete, named dependency in [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md), which decided Rule 2 (critical-substation protection) requires a real Critical Infrastructure bounded context before it can be enforced as anything more than a documented gap. This document builds that context.

---

## 2. Purpose

To provide a single, auditable source of truth for critical-infrastructure classification, so that:

- Cross-Scheme Compliance (and, in the future, any consumer needing to know a substation's criticality) can query it through a stable, read-only service interface, without any scheme module needing to own or duplicate this data.
- A restriction is never ambiguous: every critical asset carries an explicit policy — always prohibited from shedding, conditionally allowed under stated conditions, or tracked but unrestricted — rather than a single blunt "critical/not critical" flag.
- Changes to criticality classification are fully auditable and historically reconstructable, since a compliance decision made months ago must remain explainable against the criticality data that was true at the time.

---

## 3. Responsibilities

Critical Infrastructure owns:

- ✓ Critical infrastructure categories (`CriticalCategory`)
- ✓ Critical infrastructure sources (`CriticalSource`) — the evidentiary/regulatory basis for a criticality designation
- ✓ Critical infrastructure assets (`CriticalAsset`)
- ✓ The mapping between critical assets and substations (`CriticalAssetSubstation`), including its history
- ✓ Criticality classification (`CriticalityLevel`)
- ✓ Protection/restriction metadata (restriction type and, where applicable, allowed-exception conditions)
- ✓ Its own audit trail (`critical_infrastructure_audit_log`, per CLAUDE.md A4)

---

## 4. Non-Responsibilities

Critical Infrastructure does **not** own:

- ✗ Substation identity or metadata — owned by the Substation Registry (CLAUDE.md §8). This module references a substation only by `substation_id`.
- ✗ UFLS, UVLS, or EMLS assignments, stages, or scheme data of any kind. This module has **no knowledge of "stages," "schemes," or "shedding" as concepts** — it only ever answers "is this substation critical, how, and under what restriction policy." Whether a given scheme assignment actually conflicts with that restriction is Cross-Scheme Compliance's responsibility, not this module's (§9, rule 10).
- ✗ Cross-scheme compliance checking logic — owned by the Cross-Scheme Compliance module ([ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)). This module supplies data; it never decides whether a shedding assignment is compliant.
- ✗ Equipment/relay master data — a future Equipment Registry concern; a critical asset in this module is linked at substation granularity only, not equipment granularity (§17).
- ✗ Identity, authentication, or authorization — owned by IAM (Core Platform). This module references actors only by `user_id`.

---

## 5. Owned Entities

| Entity | Description |
|---|---|
| `CriticalCategory` | A classification grouping for critical assets (e.g. Hospital, Government, National Security, Water Treatment, Data Centre). |
| `CriticalSource` | The evidentiary/regulatory basis for a criticality designation (e.g. a government directive, a signed engineering assessment) — a document reference plus issuance metadata. |
| `CriticalityLevel` | An ordered classification of how critical an asset is (e.g. Low, Medium, High, Critical) — a lookup table owned by this module (§7, design note). |
| `CriticalAsset` | The critical infrastructure entity itself (e.g. "Kuala Lumpur General Hospital") — belongs to one `CriticalCategory`, carries one `CriticalityLevel`, an optional `CriticalSource`, and a restriction policy (§7.4). |
| `CriticalAssetSubstation` | The many-to-many link between a `CriticalAsset` and a substation, with a validity period preserving history (§7.5). |
| `critical_infrastructure_audit_log` | This module's own audit trail (CLAUDE.md A4), covering all entities above. |

**Design note — `CriticalityLevel` is module-owned reference data, not Core Platform's.** [domain-model.md](domain-model.md) §2 scopes Core Platform's reference data to genuinely cross-cutting lookups (voltage level, region, grid owner) used across the whole platform. Criticality tiers are specific vocabulary belonging to this module's own domain and are not referenced anywhere else — they are modeled as a lookup table (CLAUDE.md §11.3) owned locally by Critical Infrastructure, not centralized in Core Platform. A module-owned reference table is a legitimate pattern distinct from platform-wide reference data, and this is the first place in the architecture series it has been needed.

---

## 6. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| Substation | Master Data (Substation Registry) | `substation_id` (UUID) only, on `CriticalAssetSubstation` — no attributes copied |
| User | Core Platform (IAM) | `user_id` (UUID) only, for `created_by_user_id`/`updated_by_user_id` and audit attribution; fallback `external_principal_id` + provider per [ADR-002](../adr/ADR-002-identity-and-access-management.md) |
| Role / Permission | Core Platform (IAM) | Not referenced by foreign key; authorization checks performed via IAM's service layer at request time (CLAUDE.md A1) |

This module never stores substation name, mnemonic, voltage, region, state, owner, or coordinates — only `substation_id`.

---

## 7. Domain Model

```
CriticalCategory (1) ──── (many) CriticalAsset
CriticalityLevel (1) ──── (many) CriticalAsset
CriticalSource   (0..1) ──── (many) CriticalAsset

CriticalAsset (1) ──── (many) CriticalAssetSubstation ──── references ───▶ Substation.substation_id  (Master Data, external)

CriticalCategory / CriticalSource / CriticalAsset / CriticalAssetSubstation
                  ──── references ───▶ User.user_id  (Core Platform/IAM, external)
```

**No arrow points from this module toward any scheme module** — mirroring the exact decoupling principle already established in [network-model-module.md](network-model-module.md) §9, rule 8. This is deliberate: Critical Infrastructure is consumed by Cross-Scheme Compliance, never the reverse, and this module's own data model has no concept of "stage" or "scheme" to couple to in the first place.

### 7.1 Whether This Should Be Master Data, Core Platform, or Its Own Domain

**Decision: Master Data domain, as a sibling module to the Substation Registry — not folded into it, and not Core Platform.**

- **Not Core Platform:** Core Platform's own definition ([domain-model.md](domain-model.md) §2) is "cross-cutting... concerns that belong to no single scheme or asset." Critical Infrastructure data is asset-specific by definition — it always attaches to particular substations — so it does not fit Core Platform's cross-cutting character.
- **Not folded into Substation Registry directly:** although criticality could superficially look like "just another substation attribute" (similar to `operational_status`), it differs in shape and sensitivity in ways that justify a separate module: (a) the relationship is genuinely many-to-many — one critical asset can span multiple substations (e.g. a hospital with a primary and backup supply point), and one substation can serve multiple critical assets — which is a richer relational shape than a scalar attribute; (b) it carries its own evidentiary/documentary trail (`CriticalSource`) that has no equivalent on `Substation` itself; (c) it plausibly warrants a stricter read-access policy than general substation browsing (§15) — knowing *which* substations serve national-security-sensitive loads is itself more sensitive than knowing a substation's voltage level, and keeping it in a separate module makes that different security posture straightforward to apply without complicating Substation Registry's own, more open read policy.
- **Master Data domain fits:** it is foundational, asset-classification data, referenced by (never depending on) the Defence Scheme domain — exactly the dependency direction CLAUDE.md A2 requires (Defence Scheme, via Cross-Scheme Compliance, depends on Master Data; Master Data never depends on Defence Scheme). This is consistent with how the module's own data model has zero knowledge of schemes (§4, §9).

### 7.2 CriticalCategory

A simple, administratively-managed classification (e.g. Hospital, Government, National Security, Water Treatment, Data Centre). Not itself scheme-aware; used purely for grouping/reporting.

### 7.3 CriticalSource

Records the evidentiary or regulatory basis for a criticality designation — a source document reference (mirroring the legacy MVP's PDF-based `CriticalSource`), an issuance date, and descriptive context. A `CriticalAsset` may reference a source for traceability ("why is this asset classified as critical"), but a source is optional — some designations may be based on direct engineering judgment rather than a specific document, at least initially.

### 7.4 Criticality Level and Restriction Policy

Every `CriticalAsset` carries:
- A `CriticalityLevel` (an ordered tier — Low/Medium/High/Critical or similar), for prioritization and reporting.
- A **restriction type**, one of:
  - **`Prohibited`** — this asset must never be shed, under any circumstance. Always a hard restriction.
  - **`ConditionallyAllowed`** — this asset may be shed only under stated conditions. Requires a non-empty `condition_description` (versioned engineering policy text, CLAUDE.md A7 — e.g. "may be shed only under declared system emergency with confirmed alternate supply available"), which Cross-Scheme Compliance surfaces to the approver/activator when a potential conflict is found.
  - **`Unrestricted`** — tracked as critical for visibility and reporting purposes, but carries no shedding restriction of its own.

**How this refines Rule 2's enforcement (relationship to ADR-004):** [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)'s `ComplianceRuleConfig` gives Rule 2 a single global `enforcement_mode` (warn/block). This module supplies a finer, **per-asset** signal that Cross-Scheme Compliance should use to determine actual severity for a specific violation: a `Prohibited` asset's conflict should always be treated as a hard block regardless of Rule 2's global default; a `ConditionallyAllowed` asset's conflict should be treated as a warning carrying the specific `condition_description`, requiring the acknowledgment already described in ADR-004's Audit Requirements; an `Unrestricted` asset produces no violation at all. ADR-004's global `enforcement_mode` remains useful as a master on/off switch for Rule 2 checking as a whole, and as a fallback for any substation Critical Infrastructure has not yet classified. This relationship should be reflected explicitly the next time ADR-004 is revisited or superseded — this document does not modify ADR-004 itself, only clarifies how its data feeds Rule 2's actual per-violation severity (§18).

### 7.5 CriticalAssetSubstation and History Preservation

**How to preserve history if a substation's critical status changes:** each `CriticalAssetSubstation` link carries `valid_from` and a nullable `valid_to` (null = currently in effect) — mirroring the same pattern already used for [substation-registry.md](substation-registry.md)'s `substation_alias` and the legacy MVP's `IncomingBranchAlias`. Ending a link (a substation no longer serves a given critical asset) sets `valid_to`; the row is never deleted (CLAUDE.md §5.2, §11.6). Combined with the full field-level `critical_infrastructure_audit_log`, this supports two different needs: the audit log answers "exactly what changed, by whom, and why," while the validity range on the link itself supports an efficient direct query — "which substations were serving which critical assets, under what restriction, as of a specific past timestamp" — without needing to replay audit history. This matters specifically because a Cross-Scheme Compliance check performed months ago must remain fully explainable against the criticality data that was actually true at that time (§14).

A link also carries a `relationship_type` (e.g. Primary Supply, Backup Supply, Alternate Feed) — descriptive context for how the substation relates to the asset, not itself restriction-bearing (restriction policy lives on the `CriticalAsset`, not per-link).

---

## 8. Lifecycle / State Model

`CriticalCategory`, `CriticalSource`, and `CriticalAsset` are **not** governed by the Canonical Version Lifecycle (CLAUDE.md A3) — consistent with the same choice already made for Substation Registry (CLAUDE.md §11.5's "current-state master data... single authoritative record"): this is Master Data, not approved engineering policy requiring a Draft/Review/Approve workflow. Instead:

- `CriticalAsset.status`: `Active → Retired`. Soft-delete only — a retired critical asset (e.g. a hospital that has closed or been reclassified) is never physically deleted (CLAUDE.md §11.6); its historical links and audit trail remain queryable.
- `CriticalAssetSubstation`: `valid_from`/`valid_to` as described in §7.5 — not a formal state machine, just a validity window.
- Every change to any owned entity is captured in the audit log (§14), regardless of the lack of a formal approval lifecycle — auditability does not require versioning machinery to be meaningful (CLAUDE.md §5.4 applies independently of §5.2/A3).

---

## 9. Business Rules

1. Every `CriticalAsset` belongs to exactly one `CriticalCategory` and carries exactly one `CriticalityLevel`.
2. A `CriticalAsset` may be linked to one or more substations via `CriticalAssetSubstation`; a substation may serve multiple critical assets concurrently.
3. Every `CriticalAsset` carries a `restriction_type` of `Prohibited`, `ConditionallyAllowed`, or `Unrestricted`. `ConditionallyAllowed` requires a non-empty `condition_description`; the other two types carry none.
4. **This module's own tables contain no foreign key to any scheme module's owned entities.** Mirrors [network-model-module.md](network-model-module.md) §9, rule 8's decoupling principle, applied here.
5. This module never writes to Substation Registry, and never duplicates substation attributes beyond `substation_id`.
6. `CriticalAsset`/`CriticalCategory`/`CriticalSource` follow Master Data's "current-state record plus full audit log" pattern, not the Canonical Version Lifecycle (§8).
7. A `CriticalAssetSubstation` link's end is recorded by setting `valid_to`, never by deleting the row (§7.5).
8. A substation may not have more than one **currently active** (`valid_to IS NULL`) link to the *same* `CriticalAsset` — duplicate concurrent links to the same asset are not permitted. Concurrent links to *different* assets are explicitly permitted (rule 2).
9. Changing a `CriticalAsset`'s `restriction_type`, `criticality_level`, or a `CriticalAssetSubstation`'s validity requires an authenticated, named IAM user (CLAUDE.md A10) and is fully audited — these are safety-relevant classification changes, not routine data entry.
10. **This module has no knowledge of "stages," "schemes," or "shedding."** It answers only "is this substation critical, how, and under what restriction policy" (§4). Interpreting whether a specific scheme assignment actually conflicts with that policy is Cross-Scheme Compliance's responsibility.
11. Cross-Scheme Compliance (and any future consumer) accesses this module's data exclusively through its read-only service interface (§13) — never through direct table access (CLAUDE.md A1, [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md)).

---

## 10. Validation Rules

- `CriticalCategory.category_name` must be unique.
- `CriticalAsset.critical_category_id` and `criticality_level_id` must reference existing rows.
- `restriction_type = ConditionallyAllowed` requires a non-empty `condition_description`; `restriction_type` of `Prohibited` or `Unrestricted` must not carry one (a CHECK constraint enforces this pairing, CLAUDE.md §11.8).
- `CriticalAssetSubstation.substation_id` must reference an existing Substation Registry record.
- `CriticalAssetSubstation.valid_to`, if set, must be greater than or equal to `valid_from`.
- No two `CriticalAssetSubstation` rows for the same `(critical_asset_id, substation_id)` pair may both have `valid_to IS NULL` at the same time (§9, rule 8).
- `CriticalSource.source_reference`, if a file, is validated by supported file type (mirroring the legacy MVP's PDF-only validation for source documents) where applicable.

---

## 11. Database Design (Concept)

Conceptual only — no migrations are defined here.

| Table (conceptual) | Key columns (conceptual) | Notes |
|---|---|---|
| `critical_category` | `critical_category_id` (UUID PK), `category_name` (unique), `slug`, `description` | |
| `critical_source` | `critical_source_id` (UUID PK), `source_reference` (file/document pointer), `issued_date`, `description` | |
| `criticality_level` | `criticality_level_id` (SMALLINT PK), `code`, `label`, `sort_order` | Module-owned reference table (§5 design note). |
| `critical_asset` | `critical_asset_id` (UUID PK), `name`, `critical_category_id` (FK), `criticality_level_id` (FK), `critical_source_id` (FK, nullable), `restriction_type`, `condition_description` (nullable), `status`, `notes`, `created_by_user_id`, `updated_by_user_id`, `created_at`, `updated_at` | UUID PK per CLAUDE.md A5 — a genuine business entity, not reference data. |
| `critical_asset_substation` | `id` (BIGINT PK), `critical_asset_id` (FK), `substation_id` (FK, external, `ON DELETE RESTRICT`), `relationship_type`, `valid_from`, `valid_to` (nullable), `created_by_user_id`, `created_at` | Normalized many-to-many link with history (§7.5). |
| `critical_infrastructure_audit_log` | `log_id` (BIGINT PK), `entity_type`, `entity_id`, `field_name`, `old_value`, `new_value`, `changed_at`, `changed_by_user_id`, `change_reason` | Owned per CLAUDE.md A4. |

All foreign keys into `substation` (Master Data) and `user` (IAM) are `ON DELETE RESTRICT`. Tables are written exclusively through this module's own service layer (CLAUDE.md A1, [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md)).

---

## 12. API Contract (Concept)

APIs are external/UI-facing contracts (CLAUDE.md §13, A9); conceptual resource shape only.

- `critical-categories`, `critical-sources`, `criticality-levels` — largely read-mostly reference/administrative resources.
- `critical-assets` — CRUD for critical assets, with nested read access to their linked substations; writes require elevated permission (§15).
- `critical-assets/{id}/substations` — manage `CriticalAssetSubstation` links (create, and end a link by setting `valid_to`, never delete).
- A read-only, **batch** substation-criticality lookup endpoint (`substation-criticality?substation_ids=...`) — the API-layer equivalent of the service interface in §13, intended for internal/dashboard consumption rather than as this module's primary integration point (which is the service interface, per CLAUDE.md A1).

**Contract requirements (CLAUDE.md A9):** pagination/filtering for collection endpoints; structured error responses; authentication/authorization per endpoint (§15); audit-relevant actions flagged (all writes).

**Data contracts:** standard three-layer separation (CLAUDE.md A6).

---

## 13. Service Interfaces

Per CLAUDE.md A1 (module communication via in-process service-layer interfaces):

**Critical Infrastructure exposes, for other modules to consume:**
- **`getCriticalityForSubstations(substation_ids[]) → per-substation list of {critical_asset_id, category, criticality_level, restriction_type, condition_description, relationship_type}`** — a **batch** interface, deliberately not a one-substation-at-a-time call, since Cross-Scheme Compliance will typically need to check every substation appearing in a scheme version being validated at once. This is the primary, and expected, integration point for [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)'s Rule 2 (§7.4). **How Rule 2 should consume this data:** Cross-Scheme Compliance calls `getProtectedAssignments` on the relevant scheme module(s) to obtain the substations assigned to restricted stages, then calls `getCriticalityForSubstations` with that same substation set, and cross-references: any substation both restricted-stage-assigned and carrying a `Prohibited` (or unacknowledged `ConditionallyAllowed`) critical asset is a Rule 2 violation, with severity determined per-asset as described in §7.4.
- A read-only, point-in-time variant (`getCriticalityForSubstations(substation_ids[], as_of_timestamp)`) supporting historical reconstruction of a past compliance check (§7.5, §14).

**Critical Infrastructure consumes, from other modules' service layers — never their repositories directly:**
- From Master Data (Substation Registry): substation existence validation for `CriticalAssetSubstation` links.
- From Core Platform (IAM): authorization checks for writes; user lookups for audit attribution.

This module never calls a scheme module's service interface, and no scheme module writes to this module's tables, per CLAUDE.md A1 and [ADR-001](../adr/ADR-001-modular-monolith-and-module-communication.md).

---

## 14. Audit Requirements

Per CLAUDE.md §5.4 and A4, Critical Infrastructure owns and writes its own audit log, covering every owned entity in §5.

- **Every change to a `CriticalAsset`'s `restriction_type`, `criticality_level`, `condition_description`, or `status`, and every change to a `CriticalAssetSubstation`'s validity, is audited** (not merely logged, per the CLAUDE.md §16 distinction already applied consistently across this document series) — these are human safety-relevant classification decisions, analogous in weight to `ManualOverride` in [network-model-module.md](network-model-module.md) §14, not automated computations.
- Every audit entry records who, when, what changed (old/new value), and why (a reason is required for any change to `restriction_type` or an active link's `valid_to`).
- Audit history is append-only and never modified.
- **Historical reconstruction:** because a Cross-Scheme Compliance check performed in the past must remain explainable, this module's point-in-time query capability (§13) combined with its audit log allows a full answer to "what criticality data existed, and why, at the time a specific compliance check ran" — without this module needing to store a copy of every check result itself (that remains Cross-Scheme Compliance's own `ComplianceCheckRun` record, per [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)).
- Audit log access is itself access-controlled (CLAUDE.md A10).

---

## 15. Security Considerations

- All GridDefence engineering data is sensitive by default (CLAUDE.md A10); TLS required outside local development.
- **This module's data warrants a stricter human read-access policy than typical engineering reference data.** Knowing which substations serve national-security- or safety-critical loads is itself more sensitive than general substation metadata. Recommend a dedicated "Critical Infrastructure Viewer" (or higher) role, distinct from and more restricted than general engineering read access, for *human* end-user queries against this module.
- **This distinction does not apply to module-to-module service calls.** Cross-Scheme Compliance's and Dashboard's calls to `getCriticalityForSubstations` (§13) are trusted internal code paths within the same modular monolith process (CLAUDE.md A1) — they are not gated by a per-request human permission check, since the calling module itself, not an end user, is the caller. Human-facing read restriction applies at this module's own API layer (§12), not at the service-interface layer other modules use internally.
- Writing to `CriticalAsset`/`CriticalAssetSubstation` (creating, reclassifying, or ending a link) requires an elevated, admin-tier IAM permission — a mistaken classification here (e.g. marking a critical hospital `Unrestricted`) is a serious, safety-relevant error, and should not be broadly editable.
- Reading `CriticalCategory`/`CriticalityLevel` (the reference vocabulary itself, not which specific substations are critical) may reasonably be less restricted than reading actual `CriticalAsset`/`CriticalAssetSubstation` data.

---

## 16. Testing Requirements

Per CLAUDE.md §18 and A11, in priority order:

1. **Business rule tests** — `restriction_type`/`condition_description` pairing enforcement; no-duplicate-concurrent-link enforcement (§9, rule 8); a structural/architectural test confirming no table in this module has a foreign key into any scheme module's schema (§9, rule 4, mirroring the equivalent test already specified in [network-model-module.md](network-model-module.md) §16).
2. **Engineering calculation / validation tests** — `getCriticalityForSubstations` batch correctness (including the point-in-time variant, §13); validity-range (`valid_from`/`valid_to`) correctness for historical queries.
3. **API contract tests** — request/response schema conformance; authorization enforcement distinguishing human read access (§15) from internal service-call access.
4. **Database migration tests** — required once actual migrations are authored.
5. **UI behaviour tests** — required once a Critical Infrastructure frontend exists.

Business rules and validation logic must not be merged without accompanying tests (CLAUDE.md A11).

---

## 17. Future Extensions

- **Structured condition modeling** — if free-text `condition_description` proves too vague to act on consistently in practice, a more structured, machine-checkable condition model could be introduced without changing this module's core ownership or entities.
- **Equipment-level linkage** — once a future Equipment Registry exists, a critical asset could be linked at equipment granularity (e.g. "this specific transformer," not just "this substation"), refining `CriticalAssetSubstation` or introducing an equipment-level sibling.
- **Regulatory reporting exports** — `CriticalSource` provides a natural basis for compliance reporting to external regulatory bodies.
- **Dashboard visualization** — GIS/mapping display of critical infrastructure locations and their restriction status, read-only, consuming this module's service interface exactly as Cross-Scheme Compliance does.
- **Expansion beyond substations** — if GridDefence models other Master Data asset types in the future, `CriticalAssetSubstation`'s pattern generalizes to a broader "critical asset ↔ any Master Data asset" relationship.

---

## 18. Risks and Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| ADR-004's global per-rule `enforcement_mode` and this module's per-asset `restriction_type` are two related but separately-documented severity signals | A reader consulting only ADR-004 could miss that actual Rule 2 severity is asset-specific, not just rule-global | This document explicitly cross-references the relationship (§7.4); recommend a short addendum to ADR-004 (or a note at its next revision) formally acknowledging this module supplies per-violation severity, rather than leaving the relationship documented only from this side |
| Over-broad "critical" designation dilutes the classification's usefulness over time | If too many assets are marked critical, Rule 2 becomes noisy and engineers may start ignoring warnings | Recommend a periodic governance review of the critical asset list (an organisational process, not an architectural constraint) |
| Stale criticality data — an asset closes or changes but the record isn't updated | Compliance checks could rely on outdated classification | Recommend a periodic attestation/review workflow as a future process improvement; not enforced by this architecture today |
| Free-text `condition_description` for `ConditionallyAllowed` assets is inconsistently written or hard to act on | Approvers may struggle to consistently interpret when a condition is actually satisfied | Monitor in practice; escalate to the structured-condition Future Extension (§17) if this proves to be a recurring problem |
| Human read-access restriction (§15) is a policy recommendation, not enforced automatically by this document | Inconsistent application across deployments if not backed by an actual IAM role definition | Ensure the "Critical Infrastructure Viewer" role recommendation is captured concretely when IAM's role catalog is next extended |

---

## Recommended Next Architecture Document

**Cross-Scheme Compliance module architecture.**

[ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md) decided the *mechanism*; this document now supplies Rule 2's missing data dependency. The natural next step — exactly the same "ADR decides, module doc formalizes" pattern already used for PSS/E Integration following [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md) — is to write the full Cross-Scheme Compliance module document using the Canonical Module Architecture Document Template (CLAUDE.md A8), now that both of its data dependencies (`UFLS.getProtectedAssignments` and this module's `getCriticalityForSubstations`) are concretely defined and ready to consume.

**UVLS module** remains a strong secondary candidate — the Canonical Version Lifecycle template and the compliance-interface pattern are both validated and ready for UVLS to adopt with minimal new architectural decision-making. It is not blocked by, and does not block, Cross-Scheme Compliance's module document.

**EMLS module** and **Equipment Registry module** remain important but lower urgency, for the same reasons already given in [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)'s equivalent recommendation.
