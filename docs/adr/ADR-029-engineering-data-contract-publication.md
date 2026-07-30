# ADR-029: Engineering Data Contract Publication

- **Status:** Accepted
- **Date:** 2026-07-26
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) (§5 Single Source of Truth, §13 DTOs never expose persistence models, A6 API DTO layer)
- **Relates to:** the Engineering Data Workbench promotion (workbench ADR-WB-002) and the shared-contract direction set out in that repository's EDW-0 architecture. This ADR decides only the **GridDefence-side publication**; the workbench-side consumption is EDW-2B.
- **Affects:** adds `contracts/engineering-data/` (generated artefacts), `backend/app/contracts/engineering_data/` (generator + tests), and `docs/architecture/engineering-data-contract-publication.md`. **No API behaviour, DTO, model, migration, router, or existing test is changed.**

## Context

GridDefence owns the canonical engineering data architecture; the Engineering
Data Workbench consumes it. Until now the workbench inferred compatibility from
implicit signals — hardcoded API paths and field names, and the GridDefence
Alembic migration head (`EXPECTED_GRIDDEFENCE_ALEMBIC_HEAD`). Migration head is a
poor external contract: it changes for internal reasons irrelevant to the
integration boundary and can fail to change when a boundary-relevant DTO change
occurs. A durable, explicit, versioned contract is needed.

## Decision

**GridDefence publishes a narrow, versioned, machine-readable Engineering Data
Contract, generated deterministically from its own API DTOs, under
`contracts/engineering-data/`.**

1. **Ownership.** GridDefence is the sole authority for the contract (terminology,
   field names, identifier types, reference-data identifiers, lifecycle/validation
   at the boundary, and versioning). Consumers pin a snapshot; they never redefine
   it.
2. **Derivation.** Schemas are derived from `SubstationCreate` and
   `TransformerCreate` (plus the shared structured-error shape), not hand-written
   and not from ORM models. Generation guards required-ness of canonical
   dimensions and fails on incompatible model drift.
3. **Scope (narrow).** Only Substation (import target, portable), Transformer
   (target, preview-only), and the validation-error shape — the surfaces the
   workbench currently produces or previews. Nothing else.
4. **Determinism.** Artefacts contain no volatile metadata (no timestamps, no git
   revision); regeneration is byte-stable, enabling exact drift detection.
5. **Reference data as open codes/labels.** Surrogate integer ids are never in the
   contract; consumers resolve them live and must tolerate unknown reference-data
   values.
6. **Versioning.** Semantic `contract_version` (initial `0.1.0`), independent of
   app version, git commit, Alembic head, and OpenAPI version. Alembic head is
   demoted to diagnostic metadata only.

## Consequences

**Positive:** an explicit, auditable, deterministic boundary; consumers pin and
detect drift precisely; internal schema churn no longer masquerades as a contract
change; the contract cannot silently diverge from the DTOs (generation guards +
reproducibility test).

**Negative / trade-offs:** a new artefact to keep in sync (mitigated by the
`--check` reproducibility gate and tests); the portable Substation shape is a
*representation* of `SubstationCreate` (reference codes/labels, not surrogate ids),
so alignment is by documented correspondence + tests, not literal field equality —
a deliberate choice because surrogate ids are environment-specific and out of
contract scope.

## Alternatives considered

1. **Publish the full OpenAPI schema.** Rejected — far broader than needed, leaks
   unrelated endpoints and internal/response fields, and is noisier to drift-check.
2. **Keep using Alembic head as the compatibility key.** Rejected — couples
   consumers to internal DB state; wrong in both directions (§Context).
3. **Hand-author schemas in the workbench.** Rejected — violates GridDefence
   ownership and guarantees drift.
4. **Emit raw `model_json_schema()` per DTO.** Rejected as the published form —
   would carry surrogate-id fields and is less narrow; the generator instead
   derives constraints from the DTO schema while publishing the portable canonical
   shape the workbench actually uses.

## Deferred

Transactional change-set apply and its authoritative re-validation (future EDW-8),
registry read model (EDW-5), and any expansion of contract scope to Circuit/
connectivity/scheme objects (only when a workflow requires them).
