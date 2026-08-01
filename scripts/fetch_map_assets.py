#!/usr/bin/env python3
"""Fetch the offline Standard basemap binaries for the Engineering Map.

Reads ``frontend/public/map-assets/standard/manifest.json`` and downloads the
declared binary assets (the PMTiles archive, glyph ranges, and sprites) into
that folder, verifying checksums where provided. The small text assets
(``style.json``, ``manifest.json``, ``attribution.txt``, ``README.md``) are
committed; these binaries are git-ignored and obtained per workstation.

Design constraints (Phase E.1B):
  * Standard library only - no pip installs, no Docker, no admin rights.
  * No public provider is hard-coded: each asset URL comes from the manifest,
    so nothing unlicensed is fetched automatically. Assets with an empty URL are
    skipped with guidance.
  * Never overwrites an existing asset without ``--force``.
  * Checksum mismatch is a hard failure; nothing partial is left in place.

Windows (PowerShell), from the repository root:
    .\\.venv\\Scripts\\Activate.ps1
    python scripts/fetch_map_assets.py           # or: --force, --manifest PATH
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "frontend" / "public" / "map-assets" / "standard" / "manifest.json"

# Licence governance (see docs/engineering/licensing-policy.md). Permissive
# licences are approved outright; weak-copyleft/data licences are permitted but
# flagged for review; strong copyleft and unknown are rejected.
APPROVED_LICENCES = {"MIT", "BSD-2-Clause", "BSD-3-Clause", "Apache-2.0", "ISC", "OFL-1.1"}
REVIEW_LICENCES = {"LGPL-3.0-only", "LGPL-3.0", "LGPL-2.1-only", "LGPL-2.1", "MPL-2.0", "ODbL-1.0", "CC-BY-4.0", "CC-BY-SA-4.0"}
PROHIBITED_LICENCES = {"GPL-2.0", "GPL-2.0-only", "GPL-3.0", "GPL-3.0-only", "AGPL-3.0", "AGPL-3.0-only"}


def validate_governance(name: str, spec: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). An asset with any error must not be installed
    (missing licence/attribution/checksum/provenance/source, or a prohibited /
    unknown licence). Weak-copyleft/data licences are allowed with a warning."""
    errors: list[str] = []
    warnings: list[str] = []

    def missing(field: str, label: str) -> None:
        if not (spec.get(field) or "").strip():
            errors.append(f"{label} missing (assets.{name}.{field})")

    missing("source", "source / provenance")
    missing("download_url", "download URL (unknown source)")
    missing("download_date", "download date (provenance)")
    missing("checksum", "checksum")
    missing("attribution", "attribution")

    licence = (spec.get("licence") or "").strip()
    if not licence:
        errors.append(f"licence missing (assets.{name}.licence)")
    elif licence in PROHIBITED_LICENCES:
        errors.append(f"prohibited licence '{licence}' — rejected by policy")
    elif licence not in APPROVED_LICENCES and licence not in REVIEW_LICENCES:
        errors.append(f"unsupported/unknown licence '{licence}' — resolve before adoption")
    elif licence in REVIEW_LICENCES:
        warnings.append(f"licence '{licence}' is review-required (allowed with documented mitigation)")
    return errors, warnings


def human(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, dest: Path) -> None:
    print(f"  downloading {url}")
    # nosec: URL is operator-supplied in the manifest, not user input.
    with urllib.request.urlopen(url) as response, dest.open("wb") as out:  # noqa: S310
        shutil.copyfileobj(response, out)


def fetch_asset(name: str, spec: dict, base_dir: Path, force: bool) -> bool:
    rel_path = spec.get("path")
    if not rel_path:
        print(f"[{name}] manifest entry has no 'path' - skipping")
        return False
    target = base_dir / rel_path
    fmt = spec.get("archiveFormat")

    # Governance gate: no asset is installed without licence, attribution,
    # source, provenance and checksum (see docs/engineering/licensing-policy.md).
    errors, warnings = validate_governance(name, spec)
    for w in warnings:
        print(f"[{name}] NOTE: {w}")
    if errors:
        print(f"[{name}] REJECTED - governance requirements not met:")
        for e in errors:
            print(f"        - {e}")
        print(f"        Fix assets.{name} in the manifest, then re-run (see README.md / licensing-policy.md).")
        return False

    # `download_url`/`checksum` are the governed field names; the pre-governance
    # `url`/`sha256` are still accepted as fallbacks.
    url = (spec.get("download_url") or spec.get("url") or "").strip()

    exists = target.exists() and (any(target.iterdir()) if target.is_dir() else target.stat().st_size > 0)
    if exists and not force:
        print(f"[{name}] already installed at {target} - use --force to replace. Skipping.")
        return True

    with tempfile.TemporaryDirectory() as tmp:
        tmp_file = Path(tmp) / "download.bin"
        try:
            download(url, tmp_file)
        except Exception as exc:  # noqa: BLE001 - report and fail this asset only
            print(f"[{name}] download failed: {exc}")
            return False

        # Checksum presence is enforced by validate_governance(); verify it here.
        expected = (spec.get("checksum") or spec.get("sha256") or "").strip().lower()
        actual = sha256_of(tmp_file)
        if actual != expected:
            print(f"[{name}] CHECKSUM MISMATCH - expected {expected}, got {actual}. Not installing.")
            return False
        print(f"[{name}] checksum OK ({human(tmp_file.stat().st_size)})")

        if fmt == "zip":
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(tmp_file) as archive:
                archive.extractall(target)
            print(f"[{name}] extracted into {target}")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(tmp_file, target)
            print(f"[{name}] installed {target} ({human(target.stat().st_size)})")
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Fetch offline Standard basemap binaries.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST, help="Path to manifest.json")
    parser.add_argument("--force", action="store_true", help="Replace assets that are already installed")
    args = parser.parse_args(argv)

    if not args.manifest.exists():
        print(f"Manifest not found: {args.manifest}", file=sys.stderr)
        return 2

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    base_dir = args.manifest.parent
    assets = manifest.get("assets", {})
    print(f"Offline map package: {manifest.get('package')} v{manifest.get('version')}")
    print(f"Coverage: {manifest.get('coverage')}  zoom {manifest.get('minzoom')}-{manifest.get('maxzoom')}")
    print(f"Target folder: {base_dir}\n")

    configured = 0
    installed = 0
    for name, spec in assets.items():
        configured += 1
        if fetch_asset(name, spec, base_dir, args.force):
            installed += 1
        print()

    if installed == 0:
        print("No assets were installed. Configure asset URLs in the manifest (see README.md),")
        print("then re-run. The application shows an honest 'not installed' state until then.")
        return 1
    print(f"Done: {installed}/{configured} assets present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
