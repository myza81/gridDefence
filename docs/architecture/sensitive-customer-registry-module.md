# Sensitive Customer Registry — Module Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. This document follows the Canonical Module Architecture Document Template (CLAUDE.md **A8**).

**Status: Approved and implemented (Phase 3.7).** This document, its companion [EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md), and [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md) defined the engineering philosophy, ownership boundaries, and integration contracts for this module, subsequently refined ([`sensitive-customer-registry-implementation-spec.md`](sensitive-customer-registry-implementation-spec.md)) and implemented in full — backend module, database migration, frontend pages, and test suites. Sections 11 and 12 below remain conceptual by design (engineering entities and required capabilities, not a restatement of the as-built schema/API) — see the implementation specification for the concrete, as-built shape.

> **Status update (post-ADR-013, Phase 3.7 UAT change request).** During manual UAT, the Project Owner approved a refinement: **`SensitiveFacility` now associates with zero, one, or many currently active Transformer Terminals**, replacing the single nullable `transformer_terminal_id` reference this document originally described. See [ADR-013](../adr/ADR-013-sensitive-facility-multiple-transformer-terminals.md), which amends decision 2 below. This is **not** alternate-supply modelling and **not** historical supply modelling — it is the authoritative record of every currently active supply point, exactly as this document's own §7 design note anticipated might one day be needed. Everywhere below that states or assumes "at most one Transformer Terminal, current-state only," ADR-013 now governs instead; the original text is preserved unmodified per this project's practice of never rewriting historical decision text (CLAUDE.md §5.2) — read it as the *original* decision, amended, not the current one.

Related documents: [system-overview.md](system-overview.md), [domain-model.md](domain-model.md), [equipment-registry-module.md](equipment-registry-module.md) (referenced entity — Transformer Terminal), [critical-infrastructure-module.md](critical-infrastructure-module.md) (the sibling registry this document's §4 and Appendix distinguish itself from), [automatic-load-shedding-functionality-registry-module.md](automatic-load-shedding-functionality-registry-module.md) (nearest structural precedent and parallel, non-coupled fact-provider), [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md) (the decision that establishes this module), [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md), [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md), [EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md), [EDR-003](../engineering/edr/EDR-003-relay-registry-scope.md), [EDR-005](../engineering/edr/EDR-005-bay-as-engineering-identity.md).

---

## 1. Module Overview

The Sensitive Customer Registry is a reusable Engineering Knowledge registry recording which physical facilities — hospitals, airports, water treatment plants, security and defence installations, and similar — require special engineering consideration if their electrical supply is interrupted, and what supplies them today. It exists to answer one engineering question, precisely and auditably, for any consumer that asks it: *"which sensitive facilities, if any, would be affected by interrupting this Transformer Terminal, and how sensitive are they?"*

Unlike every scheme module in this series (UFLS, UVLS, EMLS) and unlike Critical Infrastructure's own tighter coupling to Cross-Scheme Compliance ([ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)), this module is designed from the outset to be consumable by engineering applications that know nothing about GridDefence — GridDefence is one consumer of this registry, not its reason for existing ([ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md), decision 5). It is **not** a customer-relationship-management system, **not** a billing or service-level system, **not** a geographic information system, and it never decides what any defence scheme does with a sensitivity finding ([EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md)).

The module's governing philosophy, stated as a single rule that binds every section below:

> **The Sensitive Customer Registry records engineering facts about sensitive facilities. It never records engineering decisions made by consuming applications.**

A candidate being excluded from UFLS, a facility being allowed only in a particular stage, an override having been approved, a temporary engineering exception, a scheme-specific restriction, and any defence-scheme assignment are all engineering decisions — each belongs to the consuming application's own records, never to this registry ([ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md), decision 4).

---

## 2. Purpose

To provide a single, auditable, reusable source of truth for facility sensitivity, so that:

- Any consumer — a UFLS/UVLS/EMLS candidate-load evaluation today, a Dashboard summary, or a future non-GridDefence transmission-engineering application — can query "does this Transformer Terminal serve a sensitive facility, and how sensitive" through a stable, read-only service interface, without needing to understand schemes, stages, or GridDefence's own domain vocabulary at all.
- A facility's engineering classification (sector, sensitivity) is recorded once, authoritatively, rather than being informally known by individual engineers or re-derived inconsistently by each consuming application.
- Every change to a facility's classification or supply-point reference is fully auditable and historically reconstructable — a scheme design decision made months ago must remain explainable against the sensitivity data that was true at the time.
- The distinction between "this facility is sensitive, at this level" (this module's own fact) and "this candidate should therefore be excluded from this scheme" (a consuming scheme's own decision) is never blurred — mirroring 03-system-workflow.md §3's existing rule that Sensitive Customer Review and Relay Capability Verification "answer different engineering questions... and a finding from one must never be mistaken for a finding from the other," now extended to this module's relationship with every consumer's own interpretation of its findings.

---

## 3. Responsibilities

Sensitive Customer Registry owns:

- ✓ The record of a sensitive physical facility's identity and classification (`SensitiveFacility`)
- ✓ The reference vocabulary for facility sector (`FacilitySector`) and sensitivity classification (`SensitivityClassification`)
- ✓ A facility's current supply-point reference (the Transformer Terminal it is currently understood to be served through, where known)
- ✓ The facility's own lifecycle (§8)
- ✓ Its own full audit trail, covering every classification change, supply-point correction, and lifecycle transition (CLAUDE.md A4)
- ✓ Read-only facility-lookup and batch-lookup query interfaces for any consumer, GridDefence or not

---

## 4. Non-Responsibilities

Sensitive Customer Registry does **not** own:

- ✗ Transformer Terminal identity, wiring, or existence — owned by Equipment Registry (`TransformerTerminal`). This module references a terminal only by ID, exactly as the Automatic Load Shedding Functionality Registry does, and copies no attribute from it.
- ✗ **Any GridDefence-specific concept.** No field, enum value, method name, or query parameter in this module's owned data or service interface names a scheme, a stage, a Shedding Action, UFLS, UVLS, or EMLS ([ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md), decision 5). This is a binding design constraint, not a stylistic preference — see §9, rule 1.
- ✗ **Whether a candidate should be excluded, warned about, or approved for a scheme.** This module answers only "is this facility sensitive, and how" — the consuming scheme decides what that means for its own candidate selection ([EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md)). This module never returns a block/allow verdict of its own.
- ✗ **Network topology or electrical connectivity analysis of any kind** — owned by Network Model. This module never determines which Transformer Terminals lie inside a proposed boundary pocket; it only answers, for a terminal-id set already resolved by the caller, which of those terminals serve sensitive facilities.
- ✗ **Critical Infrastructure's own subject matter** — substation-level criticality classification and its Cross-Scheme Compliance Rule 2 coupling remain entirely Critical Infrastructure's responsibility ([ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md); Appendix below). This module is never consulted for, and never answers, "is this substation critical infrastructure."
- ✗ **Facility/customer-relationship management of any kind.** Contact persons, service-level agreements, billing relationships, correspondence history, tariffs, and site plans are out of scope entirely — not deferred, not partially modeled ([EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md)).
- ✗ **Geographic information or mapping data.** This module does not record facility coordinates, addresses, or spatial geometry. A future Dashboard visualization consuming this module alongside a genuinely geographic data source is conceivable (§17) but is not this module's own responsibility to provide.
- ✗ **Historical or alternate supply-point modelling — as a present-day feature.** Only the current Transformer Terminal reference is recorded (§8, [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md) decision 2). This reflects today's engineering practice and is an implementation-scope decision, not an architectural ceiling — see §7's design note.
- ✗ Identity, authentication, or authorization — owned by IAM. This module references actors only by `user_id`.

---

## 5. Owned Entities

| Entity | Description |
|---|---|
| `SensitiveFacility` | One record per physical facility (e.g. "Hospital Kuala Lumpur"), carrying a name, a `FacilitySector`, a `SensitivityClassification`, an optional current Transformer Terminal reference, a lifecycle status, and free-text remarks (§7, §9). |
| `FacilitySector` | Reference data (CLAUDE.md §11.3) — the broad category of facility (Healthcare; Security, Defence & Emergency Services; Government & Public Administration; Transport; Utilities; Strategic & Economic Infrastructure; Special or Protected Customers; Other Sensitive Consumer). Module-owned, not Core Platform's — this vocabulary belongs to this module's own domain and is not referenced elsewhere, mirroring `CriticalityLevel`'s identical precedent (`critical-infrastructure-module.md` §5, design note). |
| `SensitivityClassification` | Reference data — an ordered engineering-importance tier (High/Medium/Low today). Module-owned, for the same reason as `FacilitySector`. |
| `sensitive_customer_registry_audit_log` | This module's own append-only audit trail (CLAUDE.md A4), covering every owned entity above. |

**Design note — `SensitiveFacility`, not `SensitiveCustomer`, as the entity name.** The registry's own established name, "Sensitive Customer Registry," is retained throughout this document series (glossary.md, domain-model.md, 02-engineering-concepts.md) as the engineering concept's name. The entity representing one physical facility record is named `SensitiveFacility` — more precise, and deliberately avoiding "Customer," which carries a billing/CRM connotation this module explicitly does not have (§4). This mirrors the Automatic Load Shedding Functionality Registry's own precedent of a registry name and its primary entity name being closely related but not identical where precision benefits from the distinction.

---

## 6. Referenced Entities

| Entity | Owned by | Referenced as |
|---|---|---|
| `TransformerTerminal` | Equipment Registry | `transformer_terminal_id` (UUID), nullable — a facility's current supply point, where known (§8, §9) |
| User | IAM | `user_id` (UUID) only, for `created_by_user_id`/`updated_by_user_id`/audit attribution |

This module never stores a Transformer Terminal's substation, voltage level, breaker number, or any other Equipment Registry attribute — only the terminal's own ID. If a consumer needs a facility's full engineering identity (e.g. "IGBK | 33kV | Transformer T1"), it resolves that itself against Equipment Registry, exactly as the Automatic Load Shedding Functionality Registry's own consumers do — this module never duplicates that composition.

**Referencing Transformer Terminal does not make this module application-specific.** Transformer Terminal is not GridDefence vocabulary — it is an authoritative engineering identity owned by the Equipment Registry, describing a physical piece of transmission equipment independent of any defence scheme or GridDefence workflow. The governing rule ([ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md), decision 5 clarification):

> **Engineering registries may reference authoritative engineering identities owned by other registries without becoming application-specific.**

This module's reusability rests on depending only on engineering identities and never on defence-scheme concepts (UFLS, UVLS, EMLS, stages, boundary pockets, or any GridDefence workflow step) — not on avoiding every reference to another registry's identity. A future non-GridDefence consumer resolves this registry's Transformer Terminal reference exactly as it would resolve any other engineering identity it did not itself define; this is ordinary cross-registry integration (CLAUDE.md §5.1, A1 — reference, never duplicate), not an adaptation layer this module's own design imposes.

---

## 7. Domain Model

```
TransformerTerminal (Equipment Registry, external, read-only)
        │
        ▼ (0..1 — a facility's current supply point, where known)
FacilitySector (reference data)  ──┐
                                    ▼
                            SensitiveFacility  ── one row per physical facility ──
                                    ▲                (many facilities may share
SensitivityClassification ─────────┘                 one Transformer Terminal;
  (reference data)                                    a facility has at most one
                                                        current terminal, §9)
        │
        ▼
sensitive_customer_registry_audit_log  ── append-only, every change
```

**A Transformer Terminal may serve zero, one, or many `SensitiveFacility` records simultaneously** — a single bay might supply both a hospital and an adjacent government building. This is the opposite cardinality from the Automatic Load Shedding Functionality Registry's own "at most one non-decommissioned record per terminal" rule, and is a deliberate, real-world difference this module's own uniqueness rules must not accidentally copy from that precedent (§9, rule 3).

**A `SensitiveFacility` references at most one Transformer Terminal, current-state only.** No historical or alternate-supply table exists today ([ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md), decision 2). The reference is nullable: a facility may be registered as sensitive before its supply point is confirmed, or its supply point may be temporarily unknown pending investigation — an unassigned facility contributes no candidate-filtering signal to any consumer until it is assigned (§9, rule 5), mirroring the Automatic Load Shedding Functionality Registry's own "unknown, not invalid" tolerance for orphaned or unresolved references.

**Design note — implementation scope, not an architectural ceiling.** The domain model expresses the Transformer Terminal reference as an *association* on `SensitiveFacility`, not as part of the facility's own identity. This is deliberate: today's engineering practice needs only a single, current supply point, so the initial implementation supports exactly that (CLAUDE.md §21 — no premature generalization). But because the reference is modeled as an association rather than baked-in identity, the architecture can evolve — by extending that association (for example, toward a richer association record carrying its own validity window, mirroring Critical Infrastructure's own `CriticalAssetSubstation` shape) — without a fundamental redesign of `SensitiveFacility` or of this module's service interface, should a genuine future need for alternate or historical supply arrangements emerge ([ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md), decision 2).

### 7.1 Whether This Should Be Master Data, Core Platform, or Its Own Domain

**Decision (per [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md)): Master Data domain, as a sibling module to Critical Infrastructure and the Automatic Load Shedding Functionality Registry — not Core Platform, not folded into Equipment Registry.**

- **Not Core Platform:** this data is asset-specific by definition — it always attaches (where assigned) to a particular Transformer Terminal — so it does not fit Core Platform's cross-cutting character (domain-model.md §2), mirroring `critical-infrastructure-module.md` §7.1's identical reasoning.
- **Not folded into Equipment Registry:** a facility's sensitivity is a policy/impact fact about what a bay *serves*, not a wiring or identity fact about the bay itself; Equipment Registry's own scope has no engineering reason to know it, and this data plausibly warrants a stricter, separate read-access policy (§15) that is simpler to apply to a standalone module.
- **Master Data domain fits:** foundational, asset-adjacent classification data, referenced by (never depending on) the Defence Scheme domain — exactly CLAUDE.md A2's required direction.

### 7.2 FacilitySector and SensitivityClassification as Reference Data

Both are modeled as small, module-owned reference tables (CLAUDE.md §11.3), not hardcoded enumerations — a new sector or classification value is a data change, never a code deployment. `SensitivityClassification` additionally carries an ordering (mirroring `CriticalityLevel`'s own `sort_order`, `critical-infrastructure-module.md` §5) so future consumers can reason about "at least Medium sensitivity" without hardcoding tier semantics into their own code. The eight sectors and three classification tiers agreed for this phase (Agreed Engineering Principles 3–4, this task's own background) seed these tables; neither list is treated as closed (§17, §19).

### 7.3 SensitiveFacility

Carries: a free-text name (§ Agreed Engineering Principle 2 — facility names remain free text, deliberately not a controlled vocabulary, since facility naming has no reference-data-style stability), one `FacilitySector`, one `SensitivityClassification`, an optional current `transformer_terminal_id`, a lifecycle status (§8), and free-text remarks. No geographic, contact, or billing fields exist on this entity (§4).

### 7.4 Why Facility, Not Organization

Per [EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md): one record represents one physical facility ("Hospital Kuala Lumpur"), never an administrative body ("Ministry of Health") that could correspond to many unrelated physical locations. This keeps every record answerable against this module's one engineering question — "what supplies this place, and how sensitive is it" — without requiring this module to also model organizational hierarchy, which no consumer of this registry has an engineering need for.

---

## 8. Lifecycle / State Model

This is **current-state master data with a full audit trail**, not the Canonical Version Lifecycle (CLAUDE.md A3) — the same classification already established for `Circuit`, `Transformer`, `CriticalAsset`, and the Automatic Load Shedding Functionality Registry (CLAUDE.md §11.5). Per [ADR-010](../adr/ADR-010-engineering-decision-support-philosophy.md)'s classification rule, this module's data is Engineering Knowledge (Layer 1) — a standing engineering fact consulted by future consumers, never itself an Approved Engineering Policy. No verification or approval workflow exists (Agreed Engineering Principle 8) — Administrator/Editor-tier governance, backed by a complete audit trail, is treated as sufficient.

`SensitiveFacility.lifecycle_status` is this module's own, small, `CHECK`-constrained set of values (mirroring the Automatic Load Shedding Functionality Registry's own `lifecycle_status` pattern) — deliberately **not** a value drawn from Core Platform's shared `operational_status` reference table, since "Archived" is vocabulary specific to this module's own engineering meaning, not a cross-cutting platform concept (Agreed Engineering Principle 7: "do not assume every registry must share identical lifecycle states").

```text
Active
  │  ┌──────────────┐
  ├─▶│  Archived    │  (no longer a currently sensitive facility — closed,
  │  └──────┬───────┘   relocated, or reclassified; reversible if
  │         │            circumstances change)
  │         ▼ (reversal, back to Active — same row)
  │
  ▼
Entered in Error  (terminal — reachable from Active or Archived)
```

- **`Active`** — the facility is currently recognized as sensitive; it is included in every consumer-facing lookup (§13).
- **`Archived`** — the facility is no longer currently considered a sensitive facility (it closed, relocated, or was reclassified) but the record is preserved for audit/historical traceability (CLAUDE.md §11.6) and is excluded from consumer-facing lookups. Unlike the Automatic Load Shedding Functionality Registry's `Decommissioned`, this is **reversible** — a facility may return to `Active` if circumstances change (e.g. an incorrectly-archived record, or a facility resuming sensitive status), since "no longer currently sensitive" is a reviewable engineering judgment, not a physical, irreversible fact.
- **`Entered in Error`** — the record itself should never have been created as described (CLAUDE.md §11.6's deletion/correction policy, mirroring Equipment Registry's own `ENTERED_IN_ERROR` precedent). Reachable from either `Active` or `Archived`; terminal — never reversible, and the record remains permanently excluded from consumer-facing lookups thereafter.
- Every transition is captured in the audit log with actor, timestamp, and a required reason (§14).

---

## 9. Business Rules

1. **No GridDefence-specific or scheme-specific concept may appear in this module's owned entities or service interface** — no "scheme," "stage," "Shedding Action," UFLS, UVLS, or EMLS reference anywhere ([ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md), decision 5). This is the primary architectural constraint distinguishing this module from every scheme-adjacent module in this series, and is a mandatory PR-review checklist item for this module specifically.
2. **A `SensitiveFacility` is scoped to exactly one physical facility.** Organizational bodies spanning multiple physical locations are never modeled as a single record (§7.4).
3. **A Transformer Terminal may be referenced by any number of `SensitiveFacility` records concurrently** — no uniqueness constraint on `transformer_terminal_id` exists, deliberately the opposite of the Automatic Load Shedding Functionality Registry's own per-terminal uniqueness rule (§7).
4. **A `SensitiveFacility` references at most one Transformer Terminal, current-state only.** Changing it is a field-level correction on the existing record (audited), never a new historical row (§7, [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md) decision 2).
5. **A `SensitiveFacility` with no assigned Transformer Terminal, or with `lifecycle_status` other than `Active`, contributes no result to any consumer-facing lookup** — it exists in the registry but is not yet, or no longer, operationally consultable (§13).
6. **This module never computes or returns an enforcement verdict.** Every read interface returns facts (facility existence, sector, sensitivity) exactly as recorded — never a "block"/"allow"/"exclude" decision of its own ([EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md)).
7. **This module never determines network topology or pocket membership.** A batch lookup accepts a Transformer Terminal id set already resolved by the caller (typically via Network Model, called independently by that same caller) — this module never calls Network Model itself (§4, §13).
8. **This module never queries or writes to Critical Infrastructure's tables, and vice versa** — the two remain fully independent registries, consulted separately by any shared caller (Appendix).
9. **This module's own tables contain no foreign key into any scheme module's owned entities**, mirroring the identical decoupling rule already established for Critical Infrastructure and Network Model.
10. Changing a `SensitiveFacility`'s sector, sensitivity classification, supply-point reference, or lifecycle status requires an authenticated, named IAM user (CLAUDE.md A10) and is fully audited.

---

## 10. Validation Rules

- `SensitiveFacility.name` must be non-empty free text; no uniqueness constraint is imposed on name alone (two distinct facilities may share a name in different regions — disambiguation is a matter of engineering judgment during data entry, not a system-enforced rule).
- `SensitiveFacility.facility_sector_id` and `sensitivity_classification_id` must reference existing, non-retired reference rows.
- `SensitiveFacility.transformer_terminal_id`, if set, must reference an existing Transformer Terminal in Equipment Registry at the time it is set (service-layer existence check, mirroring the Automatic Load Shedding Functionality Registry's own precedent — this module holds no FK constraint into another module's schema per CLAUDE.md A1/A2, so referential integrity is enforced at the service layer).
- A Transformer Terminal reference that is later deleted or re-typed in Equipment Registry is an "unknown, not invalid" condition for this module (mirroring the Automatic Load Shedding Functionality Registry's own established tolerance) — affected facilities are omitted from terminal-keyed lookups rather than raising an error, and are flagged for manual reconciliation (§17, data-integrity reporting).
- `lifecycle_status` transitions must follow §8's diagram exactly; `Entered in Error` is terminal.
- Every lifecycle transition requires a non-empty reason (audited) — stricter than the Automatic Load Shedding Functionality Registry's own optional-reason-except-for-decommission rule, since even a reversible `Active ⇄ Archived` transition here represents a real engineering judgment about a facility's current sensitivity that later readers must be able to understand.

---

## 11. Domain Data Elements (Conceptual — Not Implementation Schema)

Conceptual engineering entities and their key attributes only. No column types, constraints, indexes, or migrations are defined here — that is implementation-phase work, gated on this document's approval (CLAUDE.md §24).

| Entity (conceptual) | Key engineering attributes (conceptual) | Notes |
|---|---|---|
| `FacilitySector` | identifier, code, label, sort order, description | Module-owned reference data (§7.2). |
| `SensitivityClassification` | identifier, code, label, sort order (ordered tier), description | Module-owned reference data (§7.2). |
| `SensitiveFacility` | identifier, name (free text), sector reference, sensitivity classification reference, current Transformer Terminal reference (optional), lifecycle status, remarks, creator/modifier attribution, timestamps | The primary business entity — a genuine, durable identity (CLAUDE.md A5's UUID-for-business-entities guidance applies at implementation time), not reference data. |
| `sensitive_customer_registry_audit_log` | log identifier, subject facility reference, field name, old value, new value, changed-at, changed-by, change reason | Owned per CLAUDE.md A4; append-only. |

All references into Equipment Registry (`TransformerTerminal`) and IAM (`User`) are non-cascading at implementation time (CLAUDE.md §11.7) — this module never causes another module's data to be deleted or altered.

---

## 12. Required Capabilities (Conceptual — Not an API Contract)

This module will need an external/UI-facing API surface once implementation begins (CLAUDE.md §13); concrete routes, request/response shapes, and DTOs are implementation-phase work, not designed here. At the capability level, the eventual API must support:

- Authenticated read access to facility records, individually and as a filtered/paginated list (by sector, sensitivity, lifecycle status, or associated Transformer Terminal).
- A batch lookup capability keyed by a set of Transformer Terminal ids — the API-layer equivalent of §13's `get_sensitive_facilities_for_transformer_terminals`, intended primarily for internal/Dashboard consumption rather than as this module's primary integration point (which is the service interface, per CLAUDE.md A1).
- Elevated-permission write access for creating and editing facility records and for lifecycle transitions (§15), each requiring a change reason.
- Structured error responses and audit-relevant action flagging, consistent with every other module in this series (CLAUDE.md A9).

---

## 13. Service Interfaces

Per CLAUDE.md A1 (module communication via in-process service-layer interfaces) — the primary integration point for every consumer, GridDefence or not:

- **`has_sensitive_facility(transformer_terminal_id) -> bool`** — true iff at least one `Active`, terminal-assigned `SensitiveFacility` currently references the given terminal. Mirrors the Automatic Load Shedding Functionality Registry's own `is_ufls_capable`/`is_uvls_capable` shape.
- **`get_sensitive_facilities_for_transformer_terminal(transformer_terminal_id) -> list[SensitiveFacilitySummary]`** — every `Active` facility currently associated with the given terminal, with sector and sensitivity classification resolved.
- **`get_sensitive_facilities_for_transformer_terminals(transformer_terminal_ids: set[UUID]) -> mapping[UUID, list[SensitiveFacilitySummary]]`** — the **batch** shape, existing specifically to serve the Boundary Pocket consumption pattern (Agreed Engineering Principle 6, `network-model-module.md`): the caller resolves pocket membership via Network Model first, then hands the resulting terminal-id set to this one call. Mirrors `getCriticalityForSubstations`'s own batch-first design (`critical-infrastructure-module.md` §13).
- **`list_facilities(filters...) -> paginated list[SensitiveFacilitySummary]`** — general registry browsing, for Dashboard, Reporting, and administrative use.
- **`get_facility_detail(facility_id) -> SensitiveFacilityDetail | None`** — full record detail for a single facility.

All read interfaces degrade gracefully for an unregistered or orphaned terminal reference (return empty/`False`/`None`, never raise) — the same "unknown, not invalid" tolerance already established across this codebase's Network Model, PSS/E Integration, and Automatic Load Shedding Functionality Registry modules.

**This module consumes, from other modules' service layers — never their repositories directly:**
- From Equipment Registry: Transformer Terminal existence validation.
- From Core Platform (IAM): authorization checks for writes; user lookups for audit attribution.

**This module never calls, and is never called by:** Network Model, the Automatic Load Shedding Functionality Registry, Critical Infrastructure, or any scheme module — see [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md)'s Service Interface Expectations for the full reasoning.

**Anticipated consumers** (none of which this module has any knowledge of): UFLS/UVLS/EMLS, during Selection of Shedding Actions candidate evaluation (Sensitive Customer Review, 03-system-workflow.md) — advisory today, interpretation left entirely to each scheme's own philosophy (§17, Open Question); Dashboard and Reporting, for read-only summaries; Cross-Scheme Compliance, only as a possible future read-only informational source, never (at this time) as a new blocking rule ([ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md), decision 4 and Alternatives Considered); and, in principle, any future non-GridDefence engineering application, via the same interface.

---

## 14. Audit Requirements

Per CLAUDE.md A4, every entity in §5 is audited. Specifically:

- Every lifecycle transition (`Active → Archived`, `Archived → Active`, `* → Entered in Error`) is a mandatory audit event — who, when, why (always required, §10), previous/new status.
- Every classification change (`facility_sector_id`, `sensitivity_classification_id`) and every supply-point correction (`transformer_terminal_id`) is a mandatory audit event, with particular emphasis given their direct downstream effect on every consumer's candidate evaluation (mirroring Equipment Registry's own "audited with particular emphasis" treatment of bay-identifier changes).
- Audit history is append-only and permanent (CLAUDE.md §5.2) — never modified or deleted, including for an `Entered in Error` record.
- Audit log access is itself access-controlled (§15).

---

## 15. Security Considerations

- All GridDefence engineering data is sensitive by default (CLAUDE.md A10); TLS required outside local development.
- **This module's data warrants a stricter human read-access policy than typical engineering reference data**, mirroring Critical Infrastructure's own explicit recommendation (`critical-infrastructure-module.md` §15). Knowing precisely which facilities are registered as sensitive — and, for the "Security, Defence & Emergency Services" sector specifically, which bay supplies them — is itself security-relevant information. Recommend a dedicated "Sensitive Customer Registry Viewer" (or higher) role, distinct from general engineering read access, for *human* end-user queries.
- **This distinction does not apply to module-to-module service calls.** Consumers' calls to §13's interfaces are trusted internal code paths within the same modular monolith process (CLAUDE.md A1) — not gated by a per-request human permission check, since the calling module, not an end user, is the caller. If and when this module is extracted into a standalone service consumed by an external application (CLAUDE.md §6, F6), that extraction is exactly the point at which a service-to-service authentication mechanism must be introduced — not designed here.
- Writing to `SensitiveFacility` (creating, reclassifying, correcting its supply-point reference, or transitioning its lifecycle) requires an elevated IAM permission — a mistaken classification here is a safety-relevant error.
- Reading the reference vocabulary itself (`FacilitySector`/`SensitivityClassification`) may reasonably be less restricted than reading actual `SensitiveFacility` records.

---

## 16. Testing Requirements

Per CLAUDE.md §18 and A11, in priority order — requirements only; no tests are written as part of this architecture-discovery task.

1. **Business rule tests** — no scheme-specific vocabulary appears anywhere in this module's own schema or interface (an architectural/structural test, mirroring the no-foreign-key-into-any-scheme-module test already specified for Critical Infrastructure and Network Model); a Transformer Terminal may be referenced by multiple concurrent `SensitiveFacility` records; a facility references at most one terminal, current-state only; lifecycle transitions follow §8 exactly, with `Entered in Error` correctly terminal and reachable from either `Active` or `Archived`.
2. **Engineering calculation / validation tests** — batch lookup correctness across a multi-terminal set, including terminals with zero, one, and multiple associated facilities; orphaned-terminal-reference tolerance (omitted from lookups, never raised as an error); unassigned/non-Active facilities correctly excluded from every consumer-facing lookup.
3. **API contract tests** — required once an actual API exists; request/response conformance; authorization enforcement distinguishing human read access (§15) from internal service-call access.
4. **Database migration tests** — required once actual migrations are authored.
5. **UI behaviour tests** — required once a frontend exists.

Business rules and validation logic must not be merged without accompanying tests (CLAUDE.md A11) once implementation begins.

---

## 17. Future Extensions

- **Cross-Scheme Compliance integration**, if a future scheme module's own philosophy decides sensitivity classification should carry enforcement weight (a new Rule 3, structurally analogous to Rule 2's consumption of Critical Infrastructure) — explicitly not decided by this document or [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md) (§ Open Questions, below).
- **A finer-grained facility-type taxonomy** beneath `FacilitySector` (e.g. distinguishing "Hospital" from "Clinic" within Healthcare), if broad sector classification proves insufficiently precise in practice (§19, Open Question).
- **Historical or alternate supply-point modelling**, if a genuine engineering need for it emerges (network reconfiguration making current-state-only tracking a real limitation) — deferred per [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md) decision 2, not designed here.
- **Geographic/GIS enrichment**, consumed read-only by a future Dashboard visualization alongside a genuinely geographic data source — this module would remain the facility/classification source of truth, never the geographic one (§4).
- **Data-integrity reporting** for orphaned Transformer Terminal references (§10), mirroring the Automatic Load Shedding Functionality Registry's own equivalent Future Extension — recommended at somewhat higher priority here than that precedent, given the greater real-world consequence of silently losing a sensitive-facility association (§18).
- **Extraction into a standalone service**, consumed by a second, non-GridDefence engineering application (CLAUDE.md §6, F6) — the explicit long-term goal this module's design (§4, §9 rule 1) is intended to make low-cost when it actually happens.

---

## 18. Risks and Recommendations

| Risk | Impact | Recommendation |
|---|---|---|
| A future contributor, by analogy with Critical Infrastructure, adds a GridDefence- or scheme-specific field to this module "for convenience" | Erodes the reusability this module's entire design exists to preserve ([ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md) decision 5) | Treat §9 rule 1 as a mandatory PR-review checklist item specifically for this module, not just a documented aspiration |
| A future contributor, unfamiliar with [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md), assumes Sensitive Customer Registry and Critical Infrastructure should be merged, given their visible structural similarity | Duplicated effort re-litigating an already-considered and rejected alternative, or an actual, harmful merge | This document's §4 and Appendix, and [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md)'s Alternatives Considered, state the reasoning explicitly; recommend a short cross-reference note in `critical-infrastructure-module.md` when it is next revised, pointing here |
| Stale facility or supply-point data — a facility closes, relocates, or is reassigned to a different terminal but the record is not updated | Consumers rely on outdated sensitivity/supply data during candidate evaluation | Recommend a periodic governance/attestation review (an organisational process, not an architectural constraint), mirroring Critical Infrastructure's own identical recommendation |
| Sensitivity classification currently has no enforcement coupling to any scheme module | A defence scheme could ignore a "High" finding entirely, with nothing in this architecture preventing that | Deliberately deferred to each scheme module's own future design (§17); not a defect in this module, but should be revisited explicitly when UFLS/UVLS/EMLS's own Selection-of-Shedding-Actions logic is designed |
| Human read-access restriction (§15) is a policy recommendation, not automatically enforced by this document | Inconsistent application across deployments if not backed by an actual IAM role definition | Ensure the "Sensitive Customer Registry Viewer" role recommendation is captured concretely when IAM's role catalog is next extended |
| A future contributor mistakes referencing Transformer Terminal (an authoritative engineering identity) for a reusability compromise, and proposes a generic "Supply Point" abstraction prematurely | Speculative generalization ahead of real need (CLAUDE.md §21), with no second consumer to validate the abstraction against | This document's §6 and [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md) decision 5 state explicitly that referencing another registry's authoritative engineering identity does not make a registry application-specific; a generic abstraction is warranted only if a future consuming application's own asset model genuinely cannot resolve Transformer Terminal identity — not before (§19, Open Question) |

---

## 19. Open Questions

See the companion architecture-review report's "Unresolved Engineering Questions" for the complete, numbered list surfaced during this discovery task. Summarized here for this document's own record:

1. Should sensitivity classification ever become a formal Cross-Scheme Compliance rule, or remain permanently scheme-design-time advisory only?
2. Is the eight-sector, three-tier reference-data set final for initial seeding, or provisional pending further Project Owner review?
3. Should a finer-grained facility-type taxonomy exist beneath `FacilitySector`, or is free-text `remarks` sufficient for that level of detail?
4. Should orphaned Transformer Terminal references trigger a more proactive data-integrity mechanism here than the "omit and flag" tolerance used elsewhere in this codebase, given the higher real-world stakes?
5. When, if ever, should the "current Transformer Terminal only" constraint (§7, [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md) decision 2) be revisited?
6. What is this module's actual implementation sequencing relative to Critical Infrastructure (Phase 9) and UFLS (Phase 6) — not decided by this document (§ Roadmap Recommendations, architecture-review report).

---

## Appendix: Relationship to Critical Infrastructure

This appendix records, in one place, why Sensitive Customer Registry and Critical Infrastructure remain two separate registries rather than one — the single most important question this discovery task was asked to resolve ([ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md), decision 1 and Alternatives Considered, item 1).

Stated at their sharpest, the two registries answer two different engineering questions:

> Sensitive Customer Registry: **"Which facilities require special engineering consideration if their electrical supply is interrupted?"**
>
> Critical Infrastructure Registry: **"Which transmission assets are strategically important to the operation of the transmission network itself?"**

The first question is about *what is served* by the network — an external, downstream consequence of interruption. The second is about *what the network itself* depends on to keep operating — an internal, structural property of the transmission system. Neither question can be answered by the other registry's data without changing its subject matter.

| | Sensitive Customer Registry | Critical Infrastructure |
|---|---|---|
| **Engineering question answered** | Which facilities require special engineering consideration if their electrical supply is interrupted? | Which transmission assets are strategically important to the operation of the transmission network itself? |
| **Attachment granularity** | Transformer Terminal (bay-level) | Substation (substation-level) |
| **Relationship to enforcement** | Never — returns facts only, interpreted entirely by the consumer | Direct — `restriction_type` drives Cross-Scheme Compliance Rule 2's actual severity |
| **Primary consumer today** | Any future scheme-design candidate evaluation (broad, informational) | Cross-Scheme Compliance specifically (narrow, enforcement-coupled) |
| **Reusability requirement** | Explicit — must remain consumable by non-GridDefence applications | None stated — coupled to GridDefence's own Cross-Scheme Compliance mechanism by design ([ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)) |
| **Historical modelling** | None (current-state only) | Yes — `valid_from`/`valid_to` validity windows on asset-substation links |

These are genuinely different engineering questions, at different granularities, for different consumers, under different reusability constraints — not two views of the same concept. Merging them would either import Critical Infrastructure's compliance-enforcement coupling into a registry required to stay portable, or dilute Critical Infrastructure's own substation-level, compliance-specific design to accommodate bay-level, purely-advisory data. Both registries remain siblings within the Engineering Registry domain, structurally similar in *pattern* (Master Data, current-state-plus-audit-trail or current-state-plus-history, read-only service interface, no scheme coupling in their own data model) without sharing ownership, tables, or a service interface.
