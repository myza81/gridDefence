#!/usr/bin/env python3
"""Record provenance for a generated offline map asset (Route A).

The offline Standard basemap is produced by a reproducible build (see
docs/architecture/offline-basemap-build.md), not downloaded from a public URL.
After building an asset, run this to stamp its SHA-256 checksum, download/build
date, and optional source/version/URL into the map manifest so the governance
gate (scripts/fetch_map_assets.py + docs/engineering/licensing-policy.md) has a
verifiable provenance record.

Standard library only; no admin, no Docker. Windows (PowerShell), from repo root:
    .\\.venv\\Scripts\\Activate.ps1
    python scripts/record_map_provenance.py archive `
        --file frontend/public/map-assets/standard/peninsular-malaysia.pmtiles `
        --source "OpenStreetMap via Planetiler (Protomaps basemaps profile)" `
        --version 2026-08-01 `
        --url ""            # optional internal artifact URL for other engineers
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPO_ROOT / "frontend" / "public" / "map-assets" / "standard" / "manifest.json"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Stamp provenance for a generated map asset into the manifest.")
    parser.add_argument("asset", help="Asset key in manifest.assets (e.g. archive, glyphs, sprites)")
    parser.add_argument("--file", type=Path, required=True, help="Path to the produced asset file")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source", default=None, help="Provenance/source description (optional)")
    parser.add_argument("--version", default=None, help="Asset version, e.g. build date (optional)")
    parser.add_argument("--url", dest="url", default=None, help="Internal artifact download URL (optional)")
    parser.add_argument("--date", default=None, help="Override build/download date (default: today, UTC)")
    args = parser.parse_args(argv)

    if not args.manifest.exists():
        print(f"Manifest not found: {args.manifest}", file=sys.stderr)
        return 2
    if not args.file.exists():
        print(f"Asset file not found: {args.file}", file=sys.stderr)
        return 2

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    assets = manifest.get("assets", {})
    if args.asset not in assets:
        print(f"Unknown asset '{args.asset}'. Known: {', '.join(assets) or '(none)'}", file=sys.stderr)
        return 2

    spec = assets[args.asset]
    checksum = sha256_of(args.file)
    date = args.date or _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
    spec["checksum"] = checksum
    spec["download_date"] = date
    if args.source is not None:
        spec["source"] = args.source
    if args.version is not None:
        spec["version"] = args.version
    if args.url is not None:
        spec["download_url"] = args.url

    args.manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    size = args.file.stat().st_size
    print(f"[{args.asset}] recorded provenance in {args.manifest.name}")
    print(f"  file       : {args.file}  ({size} bytes)")
    print(f"  checksum   : sha256:{checksum}")
    print(f"  date       : {date}")
    if args.source is not None:
        print(f"  source     : {args.source}")
    print("Note: licence + attribution must already be set for this asset (governance gate).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
