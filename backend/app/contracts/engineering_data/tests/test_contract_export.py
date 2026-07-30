"""Tests for the Engineering Data Contract publication (EDW-2A).

These are DB-free and dependency-light (no jsonschema): they exercise the
generator, the checked-in artefacts, determinism, manifest integrity, alignment
with the authoritative Pydantic DTOs, and internal-field exclusion.
"""

from __future__ import annotations

import hashlib
import json

from app.contracts.engineering_data import export
from app.modules.equipment_registry.schemas import TransformerCreate
from app.modules.substation_registry.schemas import SubstationCreate


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- determinism --------------------------------------------------------------


def test_generation_is_deterministic():
    a = export.generate()
    b = export.generate()
    assert a == b  # byte-identical across runs
    assert set(a) == {
        "contract-manifest.json",
        "schemas/substation-import.schema.json",
        "schemas/transformer-target.schema.json",
        "schemas/validation-error.schema.json",
    }


def test_checked_in_artefacts_match_generation():
    """Regenerating over the committed artefacts must produce no diff."""
    out = export.default_output_dir()
    for relpath, data in export.generate().items():
        on_disk = out / relpath
        assert on_disk.exists(), f"missing published artefact: {relpath}"
        assert on_disk.read_bytes() == data, f"stale published artefact: {relpath} (re-run generation)"


# --- valid JSON Schema (structural, no external validator) --------------------


def test_schemas_are_valid_json_and_declare_the_dialect():
    files = export.generate()
    for relpath, data in files.items():
        if not relpath.startswith("schemas/"):
            continue
        schema = json.loads(data)
        assert schema["$schema"] == export.JSON_SCHEMA_DIALECT
        assert schema["type"] == "object"
        assert "$id" in schema and schema["$id"].startswith(export.CONTRACT_NAME)


# --- manifest integrity -------------------------------------------------------


def test_manifest_references_existing_files_with_correct_checksums():
    files = export.generate()
    manifest = json.loads(files["contract-manifest.json"])
    for entry in manifest["schemas"]:
        path = entry["path"]
        assert path in files, f"manifest references missing file {path}"
        assert entry["sha256"] == _sha256(files[path])
    # payload_profiles checksums agree with the schema list.
    for profile, meta in manifest["payload_profiles"].items():
        assert meta["sha256"] == _sha256(files[meta["schema"]])


def test_manifest_digest_is_correct_and_excludes_itself():
    files = export.generate()
    manifest = json.loads(files["contract-manifest.json"])
    recorded = manifest.pop("manifest_digest")
    recomputed = _sha256(export._canonical_bytes(manifest))
    assert recorded == {"algorithm": "sha256", "value": recomputed}


def test_contract_version_present_and_semver():
    files = export.generate()
    manifest = json.loads(files["contract-manifest.json"])
    assert manifest["contract_name"] == export.CONTRACT_NAME
    parts = manifest["contract_version"].split(".")
    assert len(parts) == 3 and all(p.isdigit() for p in parts)


def test_manifest_has_no_volatile_metadata():
    """Deterministic drift comparison requires no timestamps/git-sha in the
    digested artefact."""
    text = export.generate()["contract-manifest.json"].decode("utf-8").lower()
    for volatile in ("generated_at", "timestamp", "git", "commit", "revision"):
        assert volatile not in text


# --- alignment with authoritative DTOs ----------------------------------------


def test_substation_schema_aligns_with_substation_create():
    schema = json.loads(export.generate()["schemas/substation-import.schema.json"])
    model = SubstationCreate.model_json_schema()
    required = set(model.get("required", []))
    # Canonical reference dimensions required in the model -> present+required here.
    for dim in ("region", "gm_zone", "grid_owner", "operational_status"):
        assert dim in schema["required"]
    assert {"region_id", "gm_zone_id", "grid_owner_id", "operational_status_id"} <= required
    # State optional (ADR-026): nullable in the contract, optional in the model.
    assert "state_id" not in required
    assert {"type": "null"} in schema["properties"]["state"]["oneOf"]
    # Length constraints carried over from the model.
    assert schema["properties"]["mnemonic"]["maxLength"] == model["properties"]["mnemonic"]["maxLength"]
    assert (
        schema["properties"]["official_name"]["maxLength"]
        == model["properties"]["official_name"]["maxLength"]
    )


def test_transformer_schema_aligns_with_transformer_create():
    schema = json.loads(export.generate()["schemas/transformer-target.schema.json"])
    required = set(TransformerCreate.model_json_schema().get("required", []))
    for field in ("hv_switchyard_id", "lv_switchyard_id", "transformer_number"):
        assert field in schema["required"]
        assert field in required
    assert schema["x-workbench-preview-only"] is True


# --- internal-field exclusion -------------------------------------------------


def test_no_internal_or_db_fields_leak():
    files = export.generate()
    sub = json.loads(files["schemas/substation-import.schema.json"])["properties"]
    tx = json.loads(files["schemas/transformer-target.schema.json"])["properties"]
    forbidden = {
        "created_at", "updated_at", "created_by", "updated_by",
        "region_id", "gm_zone_id", "state_id", "grid_owner_id", "operational_status_id",
        "substation_id_pk", "transformer_id", "psse_bus_number",
    }
    assert not (forbidden & set(sub))
    # Transformer preview legitimately carries substation_id (a resolved FK the
    # preview shows) but never server-generated audit/id fields.
    assert not ({"created_at", "updated_at", "created_by", "updated_by", "transformer_id"} & set(tx))


# --- alembic head is not the compatibility key --------------------------------


def test_alembic_head_is_not_the_compatibility_key():
    manifest = json.loads(export.generate()["contract-manifest.json"])

    def _keys(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from _keys(v)
        elif isinstance(obj, list):
            for item in obj:
                yield from _keys(item)

    # No manifest *field* is keyed on an Alembic head; compatibility is by version.
    assert not any("alembic" in k.lower() for k in _keys(manifest))
    assert manifest["compatibility_policy"]["scheme"] == "semver"
    # The contract explicitly documents that Alembic head is not the external key.
    assert "alembic" in manifest["source"]["note"].lower()
