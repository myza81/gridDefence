"""Deterministic generator for the GridDefence Engineering Data Contract.

The contract is *derived* from GridDefence's own API DTOs (Pydantic v2 schemas)
so it can never silently diverge from them: field lengths and required-ness are
read from ``model_json_schema()``, and generation *guards* that the canonical
reference dimensions still exist and still have the expected required-ness — if a
model changes incompatibly, generation fails loudly rather than emitting a stale
contract.

Design constraints (see ``docs/architecture/engineering-data-contract-publication.md``
and ADR-029):

* **Deterministic** — running generation twice with unchanged models yields
  byte-identical output (sorted keys, fixed indent, trailing newline, and *no*
  volatile metadata such as timestamps or git revisions).
* **Narrow** — only the Substation/Transformer shapes the workbench uses, plus
  the shared validation-error shape. No unrelated endpoints.
* **Leak-free** — internal/DB-only fields (``substation_id`` server id,
  ``created_at``, ``created_by``, ``updated_by`` …) never appear in a *create*
  contract; the create/target shapes are input DTOs, which do not carry them.
* **ORM is never the contract** — schemas come from DTOs, not SQLAlchemy models.

Reference-data identifiers are expressed as *codes/labels* (open strings resolved
live by the consumer), never as environment-specific surrogate integer ids, per
the shared-contract design (EDW-0). Surrogate ids are deliberately out of scope.

Run:  ``python -m app.contracts.engineering_data.export``  (writes to
``<repo>/contracts/engineering-data/``).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from app.modules.equipment_registry.schemas import TransformerCreate
from app.modules.substation_registry.schemas import SubstationCreate

CONTRACT_NAME = "griddefence-engineering-data-contract"
# Semantic contract version — independent of app version, git commit, Alembic
# head, and OpenAPI version. 0.x = pre-stable: the shape may still evolve under
# minor bumps before a 1.0.0 stability commitment (see compatibility policy).
CONTRACT_VERSION = "0.1.0"
JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

# Payload profile identifiers — stable names the consumer stamps onto change-set
# envelopes and validates against.
PROFILE_SUBSTATION_IMPORT = "griddefence.substation.import"
PROFILE_TRANSFORMER_TARGET = "griddefence.transformer.target"
PROFILE_VALIDATION_ERROR = "griddefence.validation-error"


class ContractGenerationError(RuntimeError):
    """Raised when the authoritative models no longer support the contract's
    guaranteed shape — generation must fail rather than emit a stale artefact."""


# --- helpers ------------------------------------------------------------------


def _model_props(model: type) -> tuple[dict[str, Any], set[str]]:
    schema = model.model_json_schema()
    return schema.get("properties", {}), set(schema.get("required", []))


def _string_constraints(prop: dict[str, Any]) -> dict[str, int]:
    """Carry over min/max length from the model, so the contract stays derived."""
    out: dict[str, int] = {}
    if "minLength" in prop:
        out["minLength"] = prop["minLength"]
    if "maxLength" in prop:
        out["maxLength"] = prop["maxLength"]
    return out


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractGenerationError(message)


def _ref_object(required_code_label: bool = True, *, with_label: bool = True) -> dict[str, Any]:
    """A reference-data reference expressed as code (+optional label), both
    nullable — the workbench resolves the surrogate id live at write time."""
    props: dict[str, Any] = {"code": {"type": ["string", "null"]}}
    required = ["code"]
    if with_label:
        props["label"] = {"type": ["string", "null"]}
        required.append("label")
    return {
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": False,
    }


# --- schema builders (derived from the authoritative DTOs) --------------------


def build_substation_import_schema() -> dict[str, Any]:
    """Portable Substation create/import target, in reference-data code/label
    form — the shape the workbench's ``_portable_payload`` produces. Derived from
    ``SubstationCreate`` (field lengths + required-ness), expressed portably."""
    props, required = _model_props(SubstationCreate)

    # Guard: the canonical reference dimensions the workbench relies on must
    # still be required (region/gm_zone/grid_owner/operational_status), and
    # State must remain optional (ADR-026). If GridDefence changes these, the
    # contract must be revised deliberately, not regenerated silently.
    for field in ("mnemonic", "official_name", "region_id", "gm_zone_id",
                  "grid_owner_id", "operational_status_id"):
        _require(field in required, f"SubstationCreate.{field} is expected to be required")
    _require("state_id" not in required, "SubstationCreate.state_id is expected to be optional (ADR-026)")

    mnemonic_c = _string_constraints(props["mnemonic"])
    official_c = _string_constraints(props["official_name"])

    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": f"{CONTRACT_NAME}/{PROFILE_SUBSTATION_IMPORT}",
        "title": "Substation import target (portable reference-data form)",
        "description": (
            "Canonical Substation create/import payload in portable form: "
            "reference dimensions are carried as GridDefence reference-data "
            "codes/labels, resolved to surrogate ids live at write time. "
            "Corresponds to SubstationCreate (region_id/gm_zone_id/grid_owner_id/"
            "operational_status_id required; state_id optional, ADR-026)."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": [
            "mnemonic", "official_name", "region", "gm_zone", "state",
            "grid_owner", "operational_status", "latitude", "longitude",
            "commissioned_date", "voltage_yards",
        ],
        "properties": {
            "mnemonic": {"type": "string", **mnemonic_c},
            "official_name": {"type": "string", **official_c},
            "region": _ref_object(),
            "gm_zone": _ref_object(),
            "state": {
                "oneOf": [
                    {"type": "null"},
                    _ref_object(),
                ],
                "description": "Null when no State is assigned (ADR-026).",
            },
            "grid_owner": _ref_object(with_label=False),
            "operational_status": {"type": ["string", "null"]},
            "latitude": {"type": ["string", "null"]},
            "longitude": {"type": ["string", "null"]},
            "commissioned_date": {"type": ["string", "null"]},
            "voltage_yards": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "voltage_level_label", "origin", "transformer_evidence",
                        "commissioning_date", "latitude", "longitude",
                    ],
                    "properties": {
                        "voltage_level_label": {"type": ["string", "null"]},
                        "origin": {"type": "string"},
                        "transformer_evidence": {"type": "array", "items": {"type": "string"}},
                        "commissioning_date": {"type": ["string", "null"]},
                        "latitude": {"type": ["string", "null"]},
                        "longitude": {"type": ["string", "null"]},
                    },
                },
            },
        },
    }


def build_transformer_target_schema() -> dict[str, Any]:
    """Transformer target block the workbench previews (read/preview-only — the
    workbench does not import Transformers today). Derived from
    ``TransformerCreate``; expressed portably (operational_status as a code,
    values nullable at preview time)."""
    props, required = _model_props(TransformerCreate)

    for field in ("substation_id", "transformer_number", "hv_switchyard_id",
                  "hv_breaker_number", "lv_switchyard_id", "lv_breaker_number",
                  "operational_status_id"):
        _require(field in required, f"TransformerCreate.{field} is expected to be required")

    number_c = _string_constraints(props["transformer_number"])
    type_c = _string_constraints(props.get("transformer_type", {}))

    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": f"{CONTRACT_NAME}/{PROFILE_TRANSFORMER_TARGET}",
        "title": "Transformer target (preview-only)",
        "description": (
            "GridDefence-facing Transformer target block produced by the "
            "workbench's transformer_target_preview(). Read/preview-only: the "
            "workbench does not currently import Transformers, so values may be "
            "null before resolution. Corresponds to TransformerCreate "
            "(hv_switchyard_id/lv_switchyard_id/transformer_number required at "
            "create time; operational_status carried here as a code)."
        ),
        "x-workbench-preview-only": True,
        "type": "object",
        "additionalProperties": False,
        "required": [
            "substation_id", "substation_mnemonic", "transformer_number",
            "hv_switchyard_id", "hv_breaker_number", "lv_switchyard_id",
            "lv_breaker_number", "capacity_mva", "commissioning_date",
            "operational_status", "transformer_type", "remarks",
        ],
        "properties": {
            "substation_id": {"type": ["string", "null"]},
            "substation_mnemonic": {"type": ["string", "null"]},
            "transformer_number": {"type": ["string", "null"], **number_c},
            "hv_switchyard_id": {"type": ["string", "null"]},
            "hv_breaker_number": {"type": ["string", "null"]},
            "lv_switchyard_id": {"type": ["string", "null"]},
            "lv_breaker_number": {"type": ["string", "null"]},
            "capacity_mva": {"type": ["string", "null"]},
            "commissioning_date": {"type": ["string", "null"]},
            "operational_status": {"type": ["string", "null"]},
            "transformer_type": {"type": ["string", "null"], **type_c},
            "remarks": {"type": ["string", "null"]},
        },
    }


def build_validation_error_schema() -> dict[str, Any]:
    """GridDefence's structured business-error body at the integration boundary:
    ``{"detail": {"code": str, "message": str}}`` (FastAPI HTTPException detail;
    see app/shared/exceptions.py and each router's ``_error_response``)."""
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "$id": f"{CONTRACT_NAME}/{PROFILE_VALIDATION_ERROR}",
        "title": "GridDefence structured error",
        "description": (
            "Structured business-error body returned by GridDefence for a "
            "non-success response. (FastAPI request-shape 422 errors use "
            "FastAPI's own list-of-errors format and are out of scope.)"
        ),
        "type": "object",
        "additionalProperties": True,
        "required": ["detail"],
        "properties": {
            "detail": {
                "oneOf": [
                    {
                        "type": "object",
                        "required": ["code", "message"],
                        "properties": {
                            "code": {"type": "string"},
                            "message": {"type": "string"},
                        },
                        "additionalProperties": True,
                    },
                    {"type": "string"},
                ]
            }
        },
    }


# --- assembly -----------------------------------------------------------------


def _canonical_bytes(obj: Any) -> bytes:
    """Deterministic serialization: sorted keys, 2-space indent, trailing
    newline, UTF-8. The single source of byte-stability for the whole contract."""
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _schema_definitions() -> dict[str, dict[str, Any]]:
    """profile -> schema dict. Ordering is fixed by construction."""
    return {
        PROFILE_SUBSTATION_IMPORT: build_substation_import_schema(),
        PROFILE_TRANSFORMER_TARGET: build_transformer_target_schema(),
        PROFILE_VALIDATION_ERROR: build_validation_error_schema(),
    }


_SCHEMA_FILENAME = {
    PROFILE_SUBSTATION_IMPORT: "schemas/substation-import.schema.json",
    PROFILE_TRANSFORMER_TARGET: "schemas/transformer-target.schema.json",
    PROFILE_VALIDATION_ERROR: "schemas/validation-error.schema.json",
}

_PROFILE_META = {
    PROFILE_SUBSTATION_IMPORT: {"direction": "workbench_to_griddefence", "mode": "import"},
    PROFILE_TRANSFORMER_TARGET: {"direction": "workbench_to_griddefence", "mode": "preview_only"},
    PROFILE_VALIDATION_ERROR: {"direction": "griddefence_to_workbench", "mode": "read"},
}


def build_manifest(schema_bytes_by_profile: dict[str, bytes]) -> dict[str, Any]:
    """Assemble the deterministic contract manifest (no volatile metadata)."""
    schemas = []
    payload_profiles = {}
    for profile in _schema_definitions():  # fixed order
        path = _SCHEMA_FILENAME[profile]
        checksum = _sha256(schema_bytes_by_profile[profile])
        meta = _PROFILE_META[profile]
        schemas.append({"profile": profile, "path": path, "sha256": checksum})
        payload_profiles[profile] = {
            "schema": path,
            "sha256": checksum,
            "direction": meta["direction"],
            "mode": meta["mode"],
        }

    manifest: dict[str, Any] = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "json_schema_dialect": JSON_SCHEMA_DIALECT,
        "compatibility_policy": {
            "scheme": "semver",
            "patch": "documentation or non-semantic correction",
            "minor": "backward-compatible optional additions (new optional field, new profile)",
            "major": "incompatible field/type/cardinality/terminology/semantic change",
            "reference_data_values": (
                "reference-data codes/labels are open strings; consumers MUST tolerate "
                "unknown values and MUST NOT hardcode enumerations"
            ),
            "surrogate_ids": "environment-specific surrogate ids are never part of the contract",
        },
        "canonical_terminology": {
            "Substation": "Substation Registry identity (Substation)",
            "Switchyard": "SubstationVoltageYard (Equipment Registry); user-facing 'Switchyard' (ADR-008)",
            "Transformer": "Primary Equipment (transformer) — Equipment Registry",
            "TransformerTerminal": "Transformer Bay (EDR-005/EDR-011)",
        },
        "source": {
            "repository": "griddefence",
            "derived_from": [
                "app.modules.substation_registry.schemas.SubstationCreate",
                "app.modules.equipment_registry.schemas.TransformerCreate",
                "app.shared.exceptions (structured error)",
            ],
            "generator": "app.contracts.engineering_data.export",
            "note": (
                "Alembic migration head is NOT the external compatibility key; "
                "contract_version is. See docs/architecture/"
                "engineering-data-contract-publication.md."
            ),
        },
        "payload_profiles": payload_profiles,
        "schemas": schemas,
    }
    manifest["manifest_digest"] = {
        "algorithm": "sha256",
        "value": _sha256(_canonical_bytes(manifest)),
    }
    return manifest


def generate() -> dict[str, bytes]:
    """Produce the full contract as ``{relative_path: bytes}`` in memory.

    Deterministic and side-effect-free — the basis of both the writer and the
    reproducibility test."""
    files: dict[str, bytes] = {}
    schema_bytes_by_profile: dict[str, bytes] = {}
    for profile, schema in _schema_definitions().items():
        data = _canonical_bytes(schema)
        schema_bytes_by_profile[profile] = data
        files[_SCHEMA_FILENAME[profile]] = data

    manifest = build_manifest(schema_bytes_by_profile)
    files["contract-manifest.json"] = _canonical_bytes(manifest)
    return files


def repo_root() -> Path:
    # backend/app/contracts/engineering_data/export.py -> repo root is parents[4]
    return Path(__file__).resolve().parents[4]


def default_output_dir() -> Path:
    return repo_root() / "contracts" / "engineering-data"


def write(target_dir: Path) -> list[Path]:
    """Write the generated contract to ``target_dir``. Deterministic: an
    unchanged model produces identical bytes and therefore no VCS diff."""
    files = generate()
    written: list[Path] = []
    for relpath, data in files.items():
        dest = target_dir / relpath
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        written.append(dest)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the GridDefence Engineering Data Contract.")
    parser.add_argument(
        "--out", type=Path, default=default_output_dir(),
        help="Output directory (default: <repo>/contracts/engineering-data).",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Do not write; exit non-zero if on-disk artefacts differ from a fresh generation.",
    )
    args = parser.parse_args(argv)

    files = generate()
    if args.check:
        drift = []
        for relpath, data in files.items():
            existing = args.out / relpath
            if not existing.exists() or existing.read_bytes() != data:
                drift.append(relpath)
        if drift:
            print("Contract artefacts are stale; re-run generation. Changed:")
            for relpath in sorted(drift):
                print(f"  - {relpath}")
            return 1
        print(f"Contract artefacts up to date ({CONTRACT_NAME} {CONTRACT_VERSION}).")
        return 0

    written = write(args.out)
    print(f"Wrote {CONTRACT_NAME} {CONTRACT_VERSION} ({len(written)} files) to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
