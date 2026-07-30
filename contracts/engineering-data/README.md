# GridDefence Engineering Data Contract

**Generated artefact — do not edit by hand.** These files are produced
deterministically by `app.contracts.engineering_data.export` from GridDefence's
own API DTOs. Edit the DTOs (and the generator, if the contract shape must
change deliberately), then regenerate.

```bash
# from backend/
python -m app.contracts.engineering_data.export          # write
python -m app.contracts.engineering_data.export --check  # verify no drift (CI)
```

## What this is

The **authoritative, versioned canonical boundary** between GridDefence (the
owner of engineering truth) and external consumers — today, the Engineering Data
Workbench. GridDefence owns it; consumers pin a snapshot of it (they never
redefine it).

Contract: `griddefence-engineering-data-contract`, version `0.1.0` (see
`contract-manifest.json`).

## Scope (deliberately narrow)

| Profile | Schema | Mode |
|---|---|---|
| `griddefence.substation.import` | `schemas/substation-import.schema.json` | Substation create/import target, portable reference-data form |
| `griddefence.transformer.target` | `schemas/transformer-target.schema.json` | Transformer target block — **preview-only** (workbench does not import transformers today) |
| `griddefence.validation-error` | `schemas/validation-error.schema.json` | GridDefence structured error body |

Circuit, Circuit Terminal, Line Connectivity, Relay/ALSF, Sensitive Customer,
and scheme objects are intentionally excluded until a current workflow needs them.

## Key properties

- **Derived, not hand-written** — schemas come from `SubstationCreate` /
  `TransformerCreate` Pydantic DTOs; generation fails if the models drop a
  guaranteed canonical field.
- **Deterministic** — no timestamps or git revisions; regeneration is
  byte-stable, so drift detection is exact.
- **Reference data by code/label** — surrogate integer ids are environment-
  specific and never part of the contract; consumers resolve them live.
- **Alembic head is not the compatibility key** — `contract_version` is. See
  [../../docs/architecture/engineering-data-contract-publication.md](../../docs/architecture/engineering-data-contract-publication.md)
  and [ADR-029](../../docs/adr/ADR-029-engineering-data-contract-publication.md).
