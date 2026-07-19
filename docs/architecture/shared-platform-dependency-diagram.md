# Shared Platform Dependency Diagram

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§7 Domain Hierarchy, A2/F2 Dependency Direction). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md). This is the **canonical dependency reference** for the Shared Defence-Scheme Platform, synthesizing [ADR-018](../adr/ADR-018-findings-severity-and-publication-governance-separation.md), [ADR-020](../adr/ADR-020-stage-setting-registry-as-standalone-shared-module.md), [ADR-021](../adr/ADR-021-engineering-parameter-configuration-ownership.md), [ADR-022](../adr/ADR-022-continuous-evaluation-detector-framework.md), and [ADR-023](../adr/ADR-023-platform-event-architecture.md).

---

## 1. Purpose

Give every future implementer one authoritative picture of how the Shared Platform's own capabilities depend on each other, on existing modules, and on future scheme modules — so that no module is ever built with a dependency running the wrong direction (CLAUDE.md A2/F2).

## 2. Layered Diagram

```text
┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 0 — Core Platform (foundational; depends on nothing above it)     │
│                                                                           │
│   IAM        Reference Data        Engineering Parameter Configuration  │
│  (users,     (Region, Voltage      (mw_tolerance_percentage and every   │
│   roles,      Level, Grid Owner,    future audited engineering          │
│   perms)      etc. — ADR-021        parameter — ADR-021)                │
│               "why not" analysis)                                       │
└─────────────────────────────────────────────────────────────────────────┘
        ▲                  ▲                          ▲
        │ read-only        │ read-only                │ read-only
        │                  │                          │
┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 1 — Existing Master / Network Data Modules                        │
│           (each depends only on Layer 0; owns its own audit log)        │
│                                                                           │
│   Substation Registry     Equipment Registry     ALSF Registry          │
│   Sensitive Customer Registry     PSS/E Integration     Network Model   │
│   Stage Setting Registry (ADR-020 — new; references Region only)        │
└─────────────────────────────────────────────────────────────────────────┘
        │                                                    │
        │ notify_source_data_changed                         │ read-only,
        │ (async, Redis/RQ — ADR-023,                         │ service-layer
        │  see platform-event-architecture.md)                │ (A1)
        ▼                                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 2 — Shared Evaluation & Governance Capabilities                   │
│                                                                           │
│   Continuous Evaluation Engine  ───internal fan-out───▶  Detector       │
│   (evaluateFindings, ADR-023                              Framework      │
│    trigger consumer)                                      (ADR-022,      │
│         │                                                  registered,   │
│         │ Finding[]                                        independent   │
│         ▼                                                  detectors)    │
│   Findings & Publication Governance (ADR-018)                           │
│   (severity/treatment separation, PublicationTreatmentPolicy,           │
│    PublicationRecord, §4.2 initial policy table)                        │
└─────────────────────────────────────────────────────────────────────────┘
        │                                          │
        │ read-only                                │ read-only
        ▼                                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 3 — Shared Presentation / Analytics Capabilities                  │
│                                                                           │
│   Regional Engineering Analytics       Engineering Review Panel         │
│   (informational only — never a                                         │
│    finding source, per its own §8)                                      │
└─────────────────────────────────────────────────────────────────────────┘

        ▲  read-only, service-layer (A1)                ▲  read-only
        │  (Stage Setting Registry, Continuous            │  (evaluateFindings,
        │   Evaluation Engine, Findings & Publication      │   recordPublication)
        │   Governance)                                    │
┌─────────────────────────────────────────────────────────────────────────┐
│ LAYER 4 — Defence Scheme Modules                                        │
│                                                                           │
│   UFLS   UVLS   EMLS   (future: SPS, RAS, generator rejection, ...)     │
└─────────────────────────────────────────────────────────────────────────┘
```

## 3. Reading the Diagram

- **Arrows point from a dependent module toward the module it depends on** — the same convention [`shared-defence-scheme-domain-model.md`](shared-defence-scheme-domain-model.md) already uses. A module only ever points downward or sideways within its own layer's own peers it explicitly reads (e.g. Findings & Publication Governance reading a scheme module's `getProtectedAssignments`, per §9 of [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) — the one intentional exception, discussed in §5 below).
- **Layer 0 depends on nothing above it.** IAM, Reference Data, and Engineering Parameter Configuration are the platform's foundation, per CLAUDE.md §7 and [ADR-021](../adr/ADR-021-engineering-parameter-configuration-ownership.md).
- **Layer 1 depends only on Layer 0.** Every existing registry module (Substation, Equipment, ALSF, Sensitive Customer, PSS/E Integration, Network Model) and the new Stage Setting Registry ([ADR-020](../adr/ADR-020-stage-setting-registry-as-standalone-shared-module.md)) read Core Platform data only — never a scheme module, never Layer 2 or 3's own data.
- **Layer 2 depends on Layer 0 and Layer 1.** The Continuous Evaluation Engine is triggered asynchronously by Layer 1 modules via `notify_source_data_changed` ([ADR-023](../adr/ADR-023-platform-event-architecture.md)), and reads Layer 1's data synchronously, on demand, when actually evaluating (§3 of [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md)). Its own internal Detector Framework ([ADR-022](../adr/ADR-022-continuous-evaluation-detector-framework.md)) is not a separate dependency layer — it is Continuous Evaluation's own internal structure, shown nested to make clear it adds no new external dependency. Findings & Publication Governance depends on Continuous Evaluation's own `Finding[]` output plus, exceptionally, each Layer 4 scheme module's own `getProtectedAssignments` interface (§5, below).
- **Layer 3 depends on Layer 2 only**, reading findings/evaluation/publication data to present or aggregate it — never computing or altering any of it (per [regional-engineering-analytics-architecture.md](regional-engineering-analytics-architecture.md) §8 and [engineering-review-panel-architecture.md](engineering-review-panel-architecture.md)'s own explicit "presents, does not own" status notes).
- **Layer 4 (Defence Scheme Modules) depends on Layer 1 and Layer 2**, never the reverse — a scheme module calls Stage Setting Registry, Continuous Evaluation's `evaluateFindings`, and Findings & Publication Governance's `recordPublication`; none of those modules ever calls into, or knows about, any specific scheme module's own internal data structures.

## 4. Existing Modules → Shared Platform → Future Scheme Modules

```text
[Existing Modules: Substation Registry, Equipment Registry, ALSF Registry,
 Sensitive Customer Registry, PSS/E Integration, Network Model]
                              │
                              │  (Layer 1, unchanged by this
                              │   finalization — already implemented)
                              ▼
                    [ Shared Platform ]
     (Stage Setting Registry · Engineering Parameter Configuration ·
      Continuous Evaluation Engine + Detector Framework ·
      Findings & Publication Governance · Regional Analytics ·
      Engineering Review Panel · Platform Event Architecture)
                              │
                              │  (read-only service interfaces,
                              │   consumed the same way by every
                              │   scheme module — no bespoke
                              │   per-scheme wiring)
                              ▼
        [Future Scheme Modules: UFLS, UVLS, EMLS, and any future
         staged or manually-invoked scheme type — SPS, RAS, etc.]
```

This is the concrete shape of [`scheme-future-extensibility.md`](scheme-future-extensibility.md) §10's own requirement — a new scheme type integrates with the Shared Platform through the same interfaces every other scheme type already uses, never a redesign of the platform itself.

## 5. One Intentional Cross-Layer Read (Not a Violation)

Findings & Publication Governance (Layer 2) reads each Defence Scheme module's (Layer 4) `getProtectedAssignments` interface, per [ADR-004](../adr/ADR-004-cross-scheme-compliance-mechanism.md)'s own preserved Rule 1 detection logic (§9 of [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)). This is a deliberate, already-justified exception, not a hidden violation of the layering above: Rule 1 (cross-scheme protected-assignment overlap) is structurally a cross-scheme *observation*, not scheme-owned business logic — Findings & Publication Governance observes across scheme modules without owning or altering any of their data, exactly as ADR-004 itself originally reasoned. It is analogous to CLAUDE.md F6's own "read-only joins... permitted for query optimisation, reporting, and dashboard read models" allowance, applied here to a service-layer read rather than a SQL join. No other Layer 2 or Layer 3 capability reads Layer 4 data directly.

## 6. No Circular Dependencies

Tracing every arrow above: Layer 0 ← Layer 1 ← Layer 2 ← Layer 3, and Layer 4 ← {Layer 1, Layer 2}, with the single documented exception in §5 running from Layer 2 to Layer 4 for one specific, read-only, already-justified purpose. No module in a lower-numbered layer ever depends on a higher-numbered layer. No two modules within the same layer depend on each other (Layer 1's modules are mutually independent; Layer 2's two capabilities depend on each other in one direction only — Findings & Publication Governance consumes Continuous Evaluation's output, never the reverse).

## 7. Status

This diagram reflects the Shared Platform architecture as finalized by this task (the four new ADRs, and the documentation synchronized alongside them). It supersedes any informal or partial dependency sketch appearing elsewhere in this pack; where another document's own diagram appears to conflict, this document is authoritative for cross-module dependency direction specifically (individual module documents remain authoritative for their own internal entity/domain models).
