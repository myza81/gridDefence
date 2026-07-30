# Engineering Data Contract — Publication (GridDefence-owned)

Status: **Accepted (EDW-2A).** Describes how GridDefence publishes the
authoritative, versioned Engineering Data Contract consumed by the Engineering
Data Workbench. See [ADR-029](../adr/ADR-029-engineering-data-contract-publication.md).

## 1. Ownership

GridDefence is the **sole authority** for the canonical engineering data
architecture: entity terminology and meaning, API-facing field names,
relationships, identifier types, reference-data identifiers, lifecycle semantics,
integration-boundary validation constraints, and **contract versioning**.

The Engineering Data Workbench **consumes** a pinned snapshot of this contract; it
never independently defines it and never edits a pinned copy (EDW-2B).

## 2. Publication location

```
contracts/engineering-data/
    contract-manifest.json
    schemas/
        substation-import.schema.json
        transformer-target.schema.json
        validation-error.schema.json
    README.md
```

Generator: `backend/app/contracts/engineering_data/export.py`.

## 3. Generation

```bash
python -m app.contracts.engineering_data.export          # write artefacts
python -m app.contracts.engineering_data.export --check  # fail if stale (CI/pre-commit)
```

Schemas are **derived from GridDefence's own Pydantic API DTOs**
(`SubstationCreate`, `TransformerCreate`) plus the shared structured-error shape.
Field lengths and required-ness are read from `model_json_schema()`, and
generation **guards** that the canonical reference dimensions still exist with the
expected required-ness — an incompatible model change fails generation rather than
emitting a stale contract. ORM/SQLAlchemy models are never the contract.

Determinism: output is sorted-key, fixed-indent JSON with a trailing newline and
**no volatile metadata** (no timestamps, no git revision), so regeneration is
byte-stable and drift detection is exact.

## 4. Scope

Narrow by design — only the shapes the workbench currently produces or previews:

- **`griddefence.substation.import`** — Substation create/import target in
  *portable* form (reference dimensions as codes/labels; surrogate ids resolved
  live). Corresponds to `SubstationCreate` (region/gm_zone/grid_owner/
  operational_status required; state optional per ADR-026).
- **`griddefence.transformer.target`** — Transformer target block, **preview-only**
  (the workbench does not import transformers today). Corresponds to
  `TransformerCreate`; `hv_switchyard_id`/`lv_switchyard_id`/`transformer_number`
  are the required create fields; `operational_status` is carried as a code.
- **`griddefence.validation-error`** — GridDefence's structured error body
  (`{"detail": {"code", "message"}}`).

Excluded until a current workflow requires them: Circuit, Circuit Terminal, Line
Connectivity, Relay/ALSF, Sensitive Customer, scheme objects.

## 5. Versioning and compatibility

Semantic version, **independent of** application version, git commit, Alembic
head, and OpenAPI version. Initial: `0.1.0` (pre-stable; shape may still evolve
under minor bumps before a 1.0.0 stability commitment).

| Bump | Meaning |
|---|---|
| Patch | Documentation / non-semantic correction |
| Minor | Backward-compatible optional addition (new optional field, new profile) |
| Major | Incompatible field/type/cardinality/terminology/semantic change |

**Reference-data values** (region/state/gm_zone/grid_owner/voltage-level/
operational-status codes) are **open strings**: consumers MUST tolerate unknown
values and MUST NOT hardcode enumerations. Adding a reference value is therefore
**not** a contract change.

## 6. Why Alembic head is not the external contract

Database migration head describes GridDefence's *internal* schema state. It
changes for reasons irrelevant to the integration boundary (indexes, internal
columns, unrelated modules) and does not change for some boundary-relevant reasons
(a DTO field rename with no migration). Using it as the compatibility key couples
consumers to GridDefence internals. The **contract version** is the external
compatibility key; Alembic head may remain *diagnostic* metadata only.

## 7. Consumer responsibilities

- Pin an exact contract version; never edit the pinned snapshot.
- Detect drift against the published artefact (exact checksum/version).
- Treat schema validation as a **pre-flight**, never as authoritative GridDefence
  validation — GridDefence re-validates authoritatively at apply time (future
  EDW-8). A matching contract version is **not** proof a change is safe to apply.

## 8. Release procedure

1. Change a DTO (or the generator) deliberately.
2. Bump `CONTRACT_VERSION` per §5.
3. Regenerate; run the contract tests (`app/contracts/engineering_data/tests`).
4. Commit the regenerated artefacts with the code change (CI runs `--check`).
5. Announce the new version to consumers, who re-pin (EDW-2B).

## 9. Schema-change review

Any change to a published schema is an engineering-contract change and must be
reviewed as one: confirm the version bump matches the compatibility impact,
confirm no internal/DB fields leak, and confirm the change is required by a real
consumer workflow (contract stays narrow).
