# Future Extensibility and Architecture Constraints

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§21, §27, A2). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md).

This document stress-tests the pack against the future scenarios the six workshops named, and states the durable constraints every future extension must respect. It does not design any of these future capabilities — it confirms the pack's own boundaries hold against them, and flags where they do not yet.

---

## 1. Stress Tests

| Future scenario | Does this pack's architecture accommodate it without redesign? | Notes |
|---|---|---|
| SPS (Special Protection Schemes) | Yes | A new Defence Scheme module, its own Scheme Version lifecycle ([ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md)), its own `getProtectedAssignments`-shaped interface for [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)'s cross-scheme detector. Whether SPS needs a Stage-Setting-Set-equivalent or an EMLS-style priority structure is a decision for SPS's own future module document, not decided here. |
| RAS (Remedial Action Schemes) | Yes, same reasoning as SPS | — |
| Generator rejection | Yes, as a new assignment kind within a future scheme module | Direct-assignment-equivalent, referencing a generator identity a future Master Data module would need to own first — not yet a registry that exists |
| Controlled islanding | Yes | [boundary-pocket-architecture.md](boundary-pocket-architecture.md)'s completeness-evaluation mechanism generalizes directly — a deliberate controlled-islanding scheme is structurally the same shape as EMLS's own already-routine Boundary Pocket usage ([emls-engineering-philosophy.md](emls-engineering-philosophy.md) §4) |
| BESS (Battery Energy Storage Systems) | Partially | A BESS is neither a load to shed nor a generator to reject — it is a genuinely new engineering identity a future Master Data registry would need to own before any scheme module could reference it (§2, below). This pack's assignment model does not need to change; a new registry and a new assignment kind would |
| Demand response | Partially, same reasoning as BESS | Likely a new assignment kind (a controllable-demand identity, not a Transformer Terminal), owned by a future registry |
| New engineering identities generally | Yes, by construction | §2, below — the pattern is already established (Transformer Terminal, Circuit Terminal) and generalizes |
| Real-time SCADA/EMS/PMU data | Yes | Consumed exactly as Operational Snapshot is consumed today — read-only, recommendation-only, never a live dependency of Published data ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md)). A richer, faster-updating snapshot source changes *what feeds* Operational Snapshot, not how the Defence Scheme domain consumes it |
| Multi-utility terminology | Yes | §3, below |
| Multi-country deployment | Partially | Reference data (Region, State, Grid Owner) is already externalized as versioned lookup tables (CLAUDE.md §11.3), not hardcoded — a new country's own reference data is additive. Engineering-parameter defaults (the ±10% MW tolerance, threshold validity ranges) are already versioned configuration, not hardcoded, so a per-deployment or per-country override is structurally possible without redesign, though this pack does not design a multi-tenancy or per-country-scoping mechanism |
| Much larger network scale | Yes, with a known risk already flagged | [`network-model-module.md`](network-model-module.md) §18's own existing risk table already names national-grid-scale synchronous computation as a risk, mitigated by async background jobs — [boundary-pocket-architecture.md](boundary-pocket-architecture.md) reuses `traverse`'s existing performance characteristics and flags its own scale risk in §16 of that document |
| AI-assisted recommendation | Yes, with a hard constraint | §4, below |
| Richer snapshot scenarios | Yes | [operational-snapshot-architecture.md](operational-snapshot-architecture.md) §10 already leaves multi-scenario studies and snapshot comparison as open architectural questions; [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §5's Draft-scoped snapshot selection already supports comparing more than one snapshot without redesign |

## 2. New Engineering Identities Remain Owned by Authoritative Registries

Every assignment kind this pack introduces (direct Transformer Terminal assignment, Boundary Pocket Circuit Terminal opening points) references an identity owned by an existing Engineering Registry module, never invented inside a scheme module. A future assignment kind (BESS, demand response, generator rejection) must follow the same discipline: a new Master Data/Engineering Registry module owns the new identity first; a scheme module references it by id, exactly as UFLS/UVLS/EMLS already reference Transformer Terminal and Circuit Terminal ([shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) §3). This pack does not, and should not, pre-design what that future identity looks like.

## 3. Organisational Terminology Does Not Leak Into the Scheme Engine

Every shared concept this pack defines — Scheme Version, Stage Setting Set, Boundary Pocket, Finding, Publication Treatment — is stated in engineering terms, never in any one utility's internal jargon, department naming, or process vocabulary. A future multi-utility or multi-country deployment must be able to adopt this pack's shared model directly, translating only display labels, not the underlying concepts. Where this pack does use Peninsular-Malaysia-specific terminology (e.g. Region/State/GM Zone as Substation Registry's own reference data), it consumes that data read-only, as metadata, never as a structural assumption baked into the Scheme Engine's own logic ([scheme-data-consumption-matrix.md](scheme-data-consumption-matrix.md) §1).

## 4. AI May Recommend, Never Decide

A durable, unconditional constraint, restated from [scheme-engineering-principles.md](scheme-engineering-principles.md) §2 and [EDR-004](../engineering/edr/EDR-004-decision-support-not-automation.md): any future AI-assisted recommendation capability (candidate suggestion, threshold suggestion, Boundary Pocket suggestion) may only ever populate the Engineering Workspace's candidate/recommendation surface — it may never automatically publish a version, automatically resolve a finding, automatically construct or commit a Boundary Pocket, or automatically rewrite an existing assignment. This is not a current-implementation limitation to be relaxed later; it is a permanent philosophical boundary every future AI capability must respect, exactly as every non-AI recommendation source (PSS/E's recommended MW, `traverse`'s reachability computation) already does.

## 5. Automatic Reassignment in Response to Snapshot Changes Is Prohibited by Philosophy

Not merely undesigned — explicitly forbidden, for every current and future finding type this pack or any future extension introduces. A snapshot change, a registry correction, or any other source-data change always produces a finding for a human to act on ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §2); it never triggers an automatic reassignment, automatic Boundary Pocket redesign, or automatic Publication of a corrected version. A future capability that appears to require automatic reassignment to be useful should be reconsidered, not exempted from this constraint.

## 6. Do Not Over-Generalize Prematurely

This pack deliberately does not build a single, generic "Assignment" or "Scheme" abstraction that UFLS/UVLS/EMLS/future schemes all inherit from identically. [Shared Defence Scheme Domain Model](shared-defence-scheme-domain-model.md) states which capabilities are genuinely shared (version lifecycle, MW/pocket capture semantics, audit, findings, publication governance) and leaves scheme-specific policy (thresholds, regional scoping, priority ordering, trigger presence/absence) as separate, per-module concerns — exactly as [`uvls-module.md`](uvls-module.md) §7.1 and [`emls-module.md`](emls-module.md) §7.1 already modeled this distinction for UFLS-vs-UVLS-vs-EMLS specifically. A future scheme module should extend this same discipline: reuse the shared platform capabilities directly, and introduce a new, clearly-scoped policy layer only for what is genuinely different about its own engineering problem (CLAUDE.md §21).
