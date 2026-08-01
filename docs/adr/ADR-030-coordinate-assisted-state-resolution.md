# ADR-030: Coordinate-Assisted Malaysian State Resolution

- **Status:** Proposed (awaiting Project Owner approval — implementation deferred)
- **Date:** 2026-08-01
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§4 Engineering Truth Before Software Convenience, §5.1 Single Source of Truth, §5.4 Auditability, A1 Module Communication, A6 Domain Model Layering, F4 IAM, and [EDR-004](../engineering/edr/EDR-004-decision-support-not-automation.md) decision-support-not-automation)
- **Relates to:** [ADR-008](ADR-008-substation-voltage-yard.md) (Substation Registry exclusively owns substation geography; the switchyard asserts no fact about it), [ADR-014](ADR-014-substation-lifecycle-simplification.md), [ADR-026](ADR-026-substation-state-optional.md) (State is optional), [ADR-006](ADR-006-connectivity-registry-vs-psse-topology-architecture.md) (registry vs operational topology). Phase E.1 delivered the read-only geographic map on already-authoritative coordinates; this ADR governs the *coordinate → State* addendum, which is **not** implemented pending approval.

---

## Context

The Phase E.1 addendum asks that, when an engineer enters valid switchyard latitude/longitude, GridDefence determine the corresponding Malaysian **State** (a Substation Registry classification, ADR-026, optional) and assist with updating the owning Substation's `state`. Discovery surfaced decisions that are **not yet governed**, so per CLAUDE.md ("architecture precedes code") and the addendum's own §14, they must be decided in an ADR before implementation.

Discovery findings:

1. **State ownership.** `State` is a nullable FK on **`Substation`** only (Substation Registry). `SubstationVoltageYard` has **no** State column — it carries per-yard GIS `latitude/longitude` metadata (ADR-008 addendum), and ADR-008 states the switchyard "asserts no new fact about the substation's own identity, **geography**, or operational status — all still exclusively owned by Substation Registry." The canonical substation coordinate is likewise `Substation.latitude/longitude`.
2. **No cross-module write today.** Updating a switchyard (`equipment_registry.write`) does **not** and must not silently write the Substation's `state` (`substation_registry.write`) — that would cross the module boundary (A1) and two permission scopes.
3. **No provenance field.** There is no persisted "how was this State chosen" column anywhere.
4. **No geographic-boundary dependency** exists (no polygon dataset, no point-in-polygon service).
5. **Reference data.** State codes/labels are seeded reference data (e.g. `MLK` → "Melaka"), keyed by `state_id`.

## Decision

**Geographic computation provides engineering evidence; the engineer retains authority over the persisted registry classification.** Concretely:

1. **Evidence, not automatic mutation.** A coordinate-derived State is a **suggestion** surfaced in the create/edit workflow. It is never persisted without an explicit engineer action. This preserves EDR-004 (the application detects; the engineer decides).
2. **Authoritative resolver is a backend domain service.** Point-in-polygon lives in a dedicated `StateResolutionService` (Router → Service → Repository → Models), consumed by both switchyard workflows and future map data-quality checks. **No point-in-polygon in routers, repositories, or React** (the frontend never re-implements the geometry).
3. **Resolution result contract** (read-only): `{ resolution_status: MATCHED | OUTSIDE_SUPPORTED_BOUNDARY | AMBIGUOUS_BOUNDARY | INVALID_COORDINATE, state_id?, state_code?, state_label?, source: "COORDINATE_BOUNDARY", boundary_dataset_version }`. Deterministic polygon matching — **no fabricated probabilistic confidence**.
4. **Boundary dataset.** An authoritative, **versioned**, locally-packaged Malaysian administrative-boundary polygon set (admin level 1 = State), deployed with the backend; deterministic point-in-polygon; **no third-party geocoding / reverse-geocoding at runtime**, no name geocoding, no GM Zone/Region as a State proxy. *(Dataset + licence to be confirmed by the Project Owner — see Open Questions.)*
5. **State remains a Substation Registry decision.** Any accepted State change is written by **Substation Registry's own service** under `substation_registry.write`. A user with only `equipment_registry.write` may save switchyard coordinates and *see* the suggestion, but **cannot** change State; the UI states that a Substation Registry writer must resolve it. Permissions are never conflated.
6. **Provenance is explicit, or absent.** If provenance is persisted, it is a new, documented `state_source` contract on Substation (`MANUAL | COORDINATE_DERIVED | MANUAL_OVERRIDE | LEGACY_IMPORT`) owned by Substation Registry — **never inferred later from value differences**. If not persisted, the workflow treats every stored State as engineer-confirmed and provenance lives only in the audit event. *(Persist vs audit-only — see Open Questions.)*
7. **Multiple-switchyard conflict is surfaced, never resolved automatically.** If coordinate-bearing switchyards resolve to different States, raise an engineering **consistency warning** and require manual resolution — never majority/first/averaged/centroid. Missing-coordinate yards reduce coverage and are reported as such, not treated as verified.
8. **Auditability.** A State change audits previous/new State, the coordinate used, `source`, `boundary_dataset_version`, engineer confirmation, and (if required) an override reason. **No audit event when the resolved State equals the existing value** (no redundant update / audit noise). The audit record distinguishes system-derived evidence from the engineer's final decision.
9. **Transaction ownership.** When a switchyard create/update and an accepted Substation State update are one approved action, they must not partially succeed. Because two modules own the two writes (A1), the orchestration is an explicit application-service command with safe failure handling: if the accepted State update fails, the engineer is informed (never silent partial success). *(Single transactional command vs orchestrated two-step — see Open Questions.)*
10. **Map reuse.** The map's coordinate-quality/State-verification indicators (consistent / missing State / mismatch / conflicting switchyards / missing coordinates) reuse this same resolver output — data-quality signals, not decorative analytics — only if the projection can compute them accurately.

## Open questions for the Project Owner

- **Boundary dataset + licence:** confirm the source (GADM 4.1, DOSM official boundaries, or OSM-derived), its licence, admin level, CRS (WGS84), included territories (Peninsular vs full Malaysia), version, and deployment packaging.
- **Provenance persistence:** add a `state_source` column (new migration + contract) or keep provenance in the audit trail only?
- **Transaction ownership:** a single Substation-Registry-owned application command that also invokes Equipment Registry, vs two explicit mutations with compensating UX on failure?
- **Scope of "assist":** create-only, edit-only, or both; and whether the map's State-verification filter is in-scope for the first cut.

## Consequences

**Positive:** engineers get authoritative geographic assistance without losing control of the registry classification; module boundaries, permissions, and auditability are preserved; the resolver is reusable by map data-quality and future continuous-evaluation workflows.

**Negative / cost:** a new backend service, a packaged polygon dataset (size + licence + update process), possibly a schema migration for provenance, and cross-module orchestration — none of which should be built until the Open Questions are decided.

## Alternatives considered

- **Auto-persist the coordinate-derived State** — rejected: violates EDR-004 (automation making an engineering decision) and A1 (Equipment write mutating Substation truth).
- **Frontend point-in-polygon** — rejected: duplicates authoritative logic in the client, ships a large polygon bundle to every browser, and cannot be audited server-side.
- **Runtime third-party reverse-geocoding** — rejected: non-deterministic, uncontrolled external dependency, licence/privacy exposure; the addendum explicitly forbids it.

---

*Implementation of this ADR is deferred until it is Accepted. Phase E.1's geographic map (read-only, on already-authoritative Substation coordinates) does not depend on it and is delivered independently.*
