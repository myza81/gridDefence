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

This document groups those layers into six working **domains** for documentation and module-organisation purposes. Each domain's name here is a documentation-level label for its CLAUDE.md §7 layer, not a rename of that layer or of any module within it — this document has always used this pattern (e.g. "Core Platform" for "Reference Data + IAM"); the two labels below marked with a note simply extend the same convention to the two domains whose original 1:1 labels had become ambiguous once more than one module came to occupy them:

| Domain (this document) | Corresponds to (CLAUDE.md §7 layer) |
|---|---|
| Core Platform | Reference Data + Identity and Access Management |
| **Engineering Registry** *(labeled "Master Data" prior to Phase 3/4; renamed here for clarity now that it holds two modules, not one — see §3)* | Master Data |
| **Network Representation** *(labeled "Network Model" prior to Phase 4; renamed here to avoid confusion with the Network Model *module*, which is only one of the two modules in this domain — see §4)* | Network Data |
| Defence Scheme | Scheme Data + Operational Data |
| Audit and Analytics | Audit Data + Reporting & Analytics |
| Presentation | *(not part of the engineering data hierarchy — the consuming UI layer)* |

Dependency flows strictly left-to-right / top-to-bottom through this grouping: **Core Platform → Engineering Registry → Network Representation → Defence Scheme → Audit and Analytics**, with **Presentation** consuming all of them through backend APIs. No domain depends on a domain to its right.

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

## 3. Engineering Registry Domain

**Purpose:** Owns engineering identity and engineering master data — the single source of truth for "what physically exists and what do we call it," independent of any one scheme's or import's use of it. Four modules complete this domain (Phases 2 and 3, plus the Automatic Load Shedding Functionality Registry per ADR-011 and the Sensitive Customer Registry per ADR-012); further modules are planned.

**Owns (today):**
- **Substation Registry** (Phase 2, complete) — substation identity, mnemonic, official name, metadata, geography, operational status. See [substation-registry.md](substation-registry.md) for full detail.
- **Equipment Registry** (Phase 3, complete) — physical/electrical equipment identity: `Circuit`/`CircuitTerminal` (a physical transmission line and its per-substation terminals — the canonical engineering reference object per [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md)), `SubstationVoltageYard`/Switchyard (per [ADR-008](../adr/ADR-008-substation-voltage-yard.md)), and `Transformer`/`TransformerTerminal`. No generic `Equipment` common backbone exists — this was an explicit, considered outcome of [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md)/[ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md), not an omission. See [equipment-registry-module.md](equipment-registry-module.md) for full detail, including its own "Superseded Design Decisions" appendix recording why the generic-backbone approach was not carried into the as-built module.
- **Automatic Load Shedding Functionality Registry** (complete) — per Bay Terminal (`CircuitTerminal`/`TransformerTerminal`) record of whether automatic UFLS/UVLS shedding functionality is installed, wired, configured, commissioned, and available, referenced by terminal ID, with a computed Available/Assigned/Decommissioned status and read-only candidate-search/capability-check interfaces for future UFLS/UVLS consumption. This module **is** the realization of the engineering concept previously discussed under the name "Relay Registry" (see [02-engineering-concepts.md](../engineering/02-engineering-concepts.md), [EDR-003](../engineering/edr/EDR-003-relay-registry-scope.md)) — "Relay Registry" is retired as a working/implementation name, not as an engineering concept; the underlying capability question (§7.8, superseded) it answers is unchanged. It remains explicitly scoped as a defence-functionality capability registry, never a general relay asset-management system (EDR-003). See [automatic-load-shedding-functionality-registry-module.md](automatic-load-shedding-functionality-registry-module.md) and [ADR-011](../adr/ADR-011-automatic-load-shedding-functionality-registry.md).
- **Sensitive Customer Registry** (Phase 3.7, complete) — `SensitiveFacility`, one record per physical facility, associated with zero, one, or many currently active Transformer Terminals via `SensitiveFacilityTransformerTerminal` (no uniqueness constraint in either direction — many facilities may share one terminal, and one facility may itself have several terminals, per [ADR-013](../adr/ADR-013-sensitive-facility-multiple-transformer-terminals.md), which amends ADR-012 decision 2), `FacilitySector`/`SensitivityClassification` module-owned reference data, and its own shared audit log. Records engineering facts only — never a defence-scheme decision, never alternate-supply priority, never supply history — and is designed from inception to remain reusable by future engineering applications that have never heard of GridDefence, UFLS, UVLS, or EMLS (ADR-012 decision 5). See [sensitive-customer-registry-module.md](sensitive-customer-registry-module.md), [ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md), [ADR-013](../adr/ADR-013-sensitive-facility-multiple-transformer-terminals.md), and [EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md).

**Owns (planned):**
- **Critical Infrastructure** (Phase 9, not yet built) — critical-asset classification (category, criticality level, restriction type), referenced by `substation_id`, per [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)'s explicit placement of this module in the Master Data domain (this document's Engineering Registry). See [critical-infrastructure-module.md](critical-infrastructure-module.md). Remains a separate bounded context from the Sensitive Customer Registry — different granularity (substation vs. Transformer Terminal), different enforcement coupling (compliance-rule-driving `restriction_type` vs. facts-only), different reusability requirements (see [sensitive-customer-registry-module.md](sensitive-customer-registry-module.md)'s Appendix and ADR-012 Alternatives Considered).

**References:** Core Platform reference data (voltage level, region, state, grid owner, operational status, line type) via foreign key.

**Referenced by:** Network Representation (Substation Registry, for PSS/E bus-to-substation matching; Equipment Registry, correlated against by PSS/E Integration's `EquipmentTopologyMap`, never referenced directly by Network Model — see §4), Defence Scheme, Audit and Analytics, Presentation.

**Does not own:** scheme assignment logic or parameters (owned by Defence Scheme), electrical topology or connectivity analysis (owned by Network Representation).

---

## 4. Network Representation Domain

**Purpose:** Models the transmission network's electrical topology and load/generation state, and computes connectivity/reachability analysis over it — independent of any scheme's use of either. This domain is deliberately split into two modules with two distinct kinds of ownership, per [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md) and [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md): one owns the *data*, the other owns the *analysis*. Neither owns the other's concern, and a future third topology-aware module (SPS/RAS, Black Start, etc.) would consume both without either module changing.

**Owns (today) — PSS/E Integration (Phase 4, complete):**
- Imported electrical topology, immutable and versioned: `TopologyVersion`, `TopologyBus`, `TopologyBranch`, `TopologyTransformer`.
- Load/generation state, immutable and versioned, always a child of exactly one `TopologyVersion`: `LoadSnapshot` and its child state/load/generator records.
- Equipment correlation: `EquipmentTopologyMap`, correlating Equipment Registry's `CircuitTerminal` identities against imported topology elements (never the reverse — this module never writes to Equipment Registry).
- Import history and audit: `RawFileImportBatch`, `psse_import_audit_log`.

See [psse-integration-module.md](psse-integration-module.md) for full detail.

**Owns (planned) — Network Model (Phase 5, not yet built):**
- Connectivity graph construction and reachability analysis, derived exclusively from PSS/E Integration's data.
- Island/pocket detection: `CutSetDefinition`, `IslandAnalysisResult`, `IslandAnalysisResultSubstation`.
- The manual engineering override model for a computed result: `ManualOverride`, `ManualOverrideSubstation`.

**Network Model does not own topology data of any kind.** It consumes `TopologyVersion`/`LoadSnapshot` from PSS/E Integration, read-only, and holds no foreign key that would let it be mistaken for a second source of structural truth. See [network-model-module.md](network-model-module.md) for full detail, including its own architectural test (no table in this module has a foreign key into any scheme module's schema) that keeps it reusable by every future topology-aware module without modification.

**Reconciliation note (Phase 5 build vs. this section, and the Operational Snapshot pivot):** what this section describes above (Connectivity graph construction, island/pocket detection) remains unbuilt, exactly as originally specified — see [network-model-module.md](network-model-module.md) §19 for what Phase 5 actually built instead: a static, PSS/E-independent connectivity view derived from Substation Registry and Equipment Registry. Per [EDR-007](../engineering/edr/EDR-007-phase-7-operational-identity-mapping.md) and [operational-snapshot-architecture.md](operational-snapshot-architecture.md), **Operational Snapshot (PSS/E Integration's `TopologyVersion`/`LoadSnapshot`) is authoritative for current electrical topology and connectivity; Engineering Registries remain authoritative for curated identity and metadata only.** The Phase 5 static model is therefore a metadata/correlation support view, not an independent or authoritative source of current operational topology — this does not change Network Model's own "does not own topology data" rule above; it clarifies which layer the *static* Phase 5 build sits in. This closes [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md)'s Open Question 6, which flagged this section as predating and needing reconciliation with ADR-003's later decision.

**Lifecycle note:** neither module's versioned entities follow the Canonical Version Lifecycle (CLAUDE.md A3). Both are **Engineering Source/Computed Data** under [ADR-010](../adr/ADR-010-engineering-decision-support-philosophy.md)'s classification rule — imported or computed data that a scheme module may consult but does not itself become approved policy until explicitly captured elsewhere. PSS/E Integration uses `Imported → Current → Superseded`; Network Model uses `Computing → Computed`. Neither is an oversight or a simplified stand-in for A3 — ADR-010 names this as the correct, deliberate lifecycle for this kind of data.

**References:** Engineering Registry (Substation Registry, for bus-to-substation matching; Equipment Registry's `Circuit`/`CircuitTerminal`, correlated by PSS/E Integration's `EquipmentTopologyMap` — Network Model itself never references `Circuit`/`CircuitTerminal` directly, per [ADR-007](../adr/ADR-007-canonical-engineering-reference-object.md) §6/§9).

**Referenced by:** Defence Scheme (a scheme module resolves a `Circuit`-level assignment to a cut-set via PSS/E Integration's own `Circuit`-resolution interface, *before* calling Network Model's `analyzeIsland` — Network Model is never queried with a `Circuit` id directly), Audit and Analytics.

**Does not own:** substation identity, equipment identity, scheme logic.

**Status:** PSS/E Integration — implemented (Phase 4, complete, independently architecture-validated and stabilized). Network Model — the connectivity-analysis capability described above (Connectivity graph, island/pocket detection) remains planned/unbuilt; a static, registry-derived connectivity view was implemented under the same module name in Phase 5 (see the reconciliation note above and [network-model-module.md](network-model-module.md) §19) — the two are not the same deliverable.

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
- Engineering Registry (substations, and — once the equipment-level scheme-assignment migration in [equipment-registry-module.md](equipment-registry-module.md) §7.11 is executed under its own ADR — `Circuit`) — every scheme assignment references by id; it never copies substation name, voltage, region, owner, or circuit bay/breaker detail (CLAUDE.md §5.1, §8, §11.4).
- Network Representation — PSS/E Integration's recommended-MW interface and Network Model's `analyzeIsland`, where a scheme's logic depends on live network data (§4). Both are consulted only as recommendations while a version is Draft/Under Review; nothing here is a live dependency of Approved/Active data (§9 rule 9 of each of those modules' own documents).
- Core Platform, for shared reference data and identity.

**Referenced by:** Audit and Analytics, Presentation.

**Does not own:** substation name, voltage level, region, or grid owner (CLAUDE.md §8 — stated explicitly as a non-owned example for UFLS, and applies identically to UVLS, EMLS, and future scheme modules).

**Versioning:** any versioned record in this domain (e.g. a Scheme Version) follows the Canonical Version Lifecycle (CLAUDE.md A3):

```
Draft → Under Review → Approved → Active → Superseded → Archived
```

Only one Active version may exist per scheme type at a time. Approved and Active records are immutable; corrections always create a new version. This is not a stylistic choice shared by every versioned entity in GridDefence — per [ADR-010](../adr/ADR-010-engineering-decision-support-philosophy.md)'s classification rule, this full lifecycle applies specifically because Defence Scheme data is **Approved Engineering Policy**: an Active version itself governs real load-shedding behaviour, unlike Network Representation's Engineering Source/Computed Data (§4), which uses a deliberately lighter lifecycle. ADR-010 confirms this domain's existing lifecycle choice; it does not change it.

> **Status update (Engineering Scheme Architecture Pack, six-workshop conclusions).** The six-state lifecycle above is **superseded, specifically for Defence Scheme Version data**, by [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md): `Draft → Published → Superseded | Entered in Error`. Defence Scheme Version data remains classified as Approved Engineering Policy under [ADR-010](../adr/ADR-010-engineering-decision-support-philosophy.md)'s rule — only the *shape* of the lifecycle realizing that classification changes, a scoped, named exception to CLAUDE.md A3's general-purpose default, not a change to A3 itself or to any other versioned entity in the platform. See [scheme-engineering-principles.md](scheme-engineering-principles.md).

---

## 6. Audit and Analytics Domain

**Purpose:** Engineering traceability and derived insight across the platform.

**Owns:** nothing belonging to another domain — but two modules within this domain own real, first-class entities of their own:
- Per CLAUDE.md A4, **every module's own audit data is owned by that module**, not centralized here — e.g. the Substation Registry owns `substation_audit_log`; Equipment Registry owns `equipment_registry_audit_log`; PSS/E Integration owns `psse_import_audit_log`; UFLS/UVLS/EMLS will each own their own audit log once built. This domain grouping is a conceptual umbrella over those per-module audit logs, not a single owning module.
- **Cross-Scheme Compliance** (Phase 10, not yet built) — per [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md), this module belongs here specifically because it *observes* engineering data across UFLS/UVLS/EMLS and Critical Infrastructure without owning any of it: it holds foreign keys only into each scheme module's **version** table (traceability, never a source of scheme truth), and owns its own `ComplianceRuleConfig`/`ComplianceCheckRun`/`ComplianceViolation` outright. See [cross-scheme-compliance-module.md](cross-scheme-compliance-module.md).
- **Dashboard** (Phase 11, not yet built, no dedicated architecture document yet — see [implementation-plan.md](implementation-plan.md)'s Architecture Gaps) — owns no schema of its own at all; composes read-only service interfaces from every other module (`getConnectivityGraph`, `getComplianceSummary`, each scheme module's current-Active-version query, and so on) purely for presentation. Never becomes the owner of, and never writes back to, any record it displays. [regional-engineering-analytics-architecture.md](regional-engineering-analytics-architecture.md) §7 already applies this same read-only-composition principle to regional engineering analytics specifically, as prior art for Phase 11's eventual scoping.

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
6. **Dependency direction is one-way.** A module may depend on a more foundational domain (Core Platform → Engineering Registry → Network Representation → Defence Scheme → Audit and Analytics); it must never be depended upon by a more foundational domain (CLAUDE.md A2).

---

## 9. Referenced vs. Owned Entities — Summary

| Domain | Owns | References (does not own) |
|---|---|---|
| Core Platform | Reference/lookup data (voltage level, region, state, grid owner, operational status, line type); Identity and Access Management (Users, Roles, Permissions, external identity mappings, authorization model) | — |
| Engineering Registry — Substation Registry *(complete)* | Substation identity, mnemonic, metadata, geography, operational status | Core Platform reference data |
| Engineering Registry — Equipment Registry *(complete)* | `Circuit`, `CircuitTerminal`, `SubstationVoltageYard` (Switchyard), `Transformer`, `TransformerTerminal` | Core Platform reference data; Substation Registry (`substation_id`) |
| Engineering Registry — Critical Infrastructure *(planned, Phase 9)* | Critical-asset classification (category, criticality level, restriction type) | Substation Registry (`substation_id`) |
| Network Representation — PSS/E Integration *(complete)* | `TopologyVersion`/`TopologyBus`/`TopologyBranch`/`TopologyTransformer`, `LoadSnapshot` and children, `EquipmentTopologyMap`, `RawFileImportBatch` | Substation Registry (bus matching); Equipment Registry's `CircuitTerminal` (correlation, read-only, never written to) |
| Network Representation — Network Model *(planned, Phase 5)* | `CutSetDefinition`, `IslandAnalysisResult`, `ManualOverride` — **never topology data itself** | PSS/E Integration's `TopologyVersion`/`LoadSnapshot`, read-only; Substation Registry (override validation) |
| Defence Scheme (UFLS / UVLS / EMLS / future SPS, RAS, Black Start, Islanding, Restoration Planning) | Frequency/voltage stages, load blocks, assignments, thresholds, scheme versions | Engineering Registry (substations, future `Circuit`); Network Representation (recommendations only, never a live dependency); Core Platform |
| Audit and Analytics — Cross-Scheme Compliance *(planned, Phase 10)* | `ComplianceRuleConfig`, `ComplianceCheckRun`, `ComplianceViolation` | Defence Scheme (version-level traceability only); Engineering Registry (Critical Infrastructure) |
| Audit and Analytics — Dashboard *(planned, Phase 11)* | Nothing — composes read-only interfaces only | All domains, read-only |
| Audit and Analytics — per-module audit logs | Each module owns its own (`substation_audit_log`, `equipment_registry_audit_log`, `psse_import_audit_log`, etc.) | — |
| Presentation | UI/view state only | All domains, via backend APIs only |

This table is the quick reference for "who owns this, and who is just borrowing it." When in doubt, the owning module's own architecture document (built from the Canonical Module Architecture Document Template, CLAUDE.md A8) is authoritative for that module's entities.
