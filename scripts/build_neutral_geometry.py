#!/usr/bin/env python3
"""Build the bundled neutral-mode geographic geometry (public domain).

The Engineering Map's neutral mode renders a small, locally bundled geographic
reference (land / sea / coastlines / national borders) so the map is usable with
no online basemap and no operator install. This script produces that committed
GeoJSON from **Natural Earth** (public domain) reproducibly: download → subset to
the Southeast-Asia window → reduce coordinate precision → write GeoJSON + a
provenance/checksum manifest.

It is a build/maintenance tool, not a runtime dependency: the OUTPUT
(southeast-asia.geojson + manifest.json) is committed, so the app needs no
network. Natural Earth's coastline/borders are used verbatim (subset + rounded);
GridDefence never hand-draws or approximates Malaysia's coastline or borders.

Standard library only. From repo root:  python scripts/build_neutral_geometry.py
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "frontend" / "public" / "map-assets" / "neutral"
OUT_GEOJSON = OUT_DIR / "southeast-asia.geojson"
OUT_MANIFEST = OUT_DIR / "manifest.json"

# Natural Earth 1:50m Admin 0 countries (public domain) — gives land polygons,
# coastlines (outer rings) and national borders in one dataset.
SOURCE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_50m_admin_0_countries.geojson"
DATASET = "Natural Earth 1:50m Admin 0 – Countries"
NE_VERSION = "5.1.1"

# Southeast-Asia window: Peninsular Malaysia [99.3,0.8,104.9,6.8] plus surrounding
# context (Thailand, Singapore, Brunei, Indonesia, Borneo, Indochina, W. Philippines).
WINDOW = (92.0, -10.0, 122.0, 16.0)  # [west, south, east, north]
PRECISION = 3  # decimal places (~110 m) — documented simplification


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def overlaps(b: tuple[float, float, float, float], w: tuple[float, float, float, float]) -> bool:
    return not (b[2] < w[0] or b[0] > w[2] or b[3] < w[1] or b[1] > w[3])


def ring_bbox(polygon) -> tuple[float, float, float, float]:
    # polygon = list of rings; ring 0 is the exterior.
    xs = [pt[0] for pt in polygon[0]]
    ys = [pt[1] for pt in polygon[0]]
    return (min(xs), min(ys), max(xs), max(ys))


def clip_geometry(geom: dict, window: tuple[float, float, float, float]) -> dict | None:
    """Keep only the individual polygons that overlap the window. This drops
    distant territories/islands and avoids antimeridian-crossing false positives
    (Kiribati, NZ) that a whole-feature bbox would wrongly include. No coordinate
    clipping — whole real Natural Earth polygons are kept or dropped."""
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if gtype == "Polygon":
        return geom if overlaps(ring_bbox(coords), window) else None
    if gtype == "MultiPolygon":
        kept = [poly for poly in coords if overlaps(ring_bbox(poly), window)]
        if not kept:
            return None
        if len(kept) == 1:
            return {"type": "Polygon", "coordinates": kept[0]}
        return {"type": "MultiPolygon", "coordinates": kept}
    return None


def round_coords(node):
    if isinstance(node, list):
        if node and isinstance(node[0], (int, float)):
            return [round(float(node[0]), PRECISION), round(float(node[1]), PRECISION)]
        return [round_coords(c) for c in node]
    return node


def main() -> int:
    print(f"Downloading {DATASET} …")
    with urllib.request.urlopen(SOURCE_URL) as resp:  # noqa: S310 - fixed public-domain source
        raw = resp.read()
    upstream_sha = sha256_bytes(raw)
    fc = json.loads(raw)

    kept = []
    for feat in fc.get("features", []):
        geom = feat.get("geometry") or {}
        if geom.get("type") not in ("Polygon", "MultiPolygon"):
            continue
        clipped = clip_geometry(geom, WINDOW)
        if clipped is None:
            continue
        name = (feat.get("properties") or {}).get("NAME") or (feat.get("properties") or {}).get("ADMIN")
        kept.append({
            "type": "Feature",
            # Keep only a display name; the neutral map renders no labels but the
            # name aids provenance/debugging and stays tiny.
            "properties": {"name": name} if name else {},
            "geometry": {"type": clipped.get("type"), "coordinates": round_coords(clipped.get("coordinates"))},
        })

    out = {
        "type": "FeatureCollection",
        "metadata": {
            "source": DATASET,
            "note": "Public-domain Natural Earth subset for GridDefence neutral-mode context.",
            "window": list(WINDOW),
        },
        "features": kept,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    text = json.dumps(out, separators=(",", ":")) + "\n"
    OUT_GEOJSON.write_text(text, encoding="utf-8")
    out_sha = sha256_bytes(OUT_GEOJSON.read_bytes())
    size = OUT_GEOJSON.stat().st_size

    manifest = {
        "asset": "neutral-southeast-asia-geometry",
        "file": OUT_GEOJSON.name,
        "dataset": DATASET,
        "source": "Natural Earth (naturalearthdata.com), via nvkelso/natural-earth-vector",
        "source_url": SOURCE_URL,
        "version": NE_VERSION,
        "retrieved": _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d"),
        "licence": "Public Domain",
        "licence_note": "All Natural Earth vector/raster map data is in the public domain (naturalearthdata.com/about/terms-of-use).",
        "attribution": "Made with Natural Earth.",
        "checksum": f"sha256:{out_sha}",
        "upstream_checksum": f"sha256:{upstream_sha}",
        "geographic_extent": list(WINDOW),
        "features": len(kept),
        "simplification": f"Feature subset intersecting {list(WINDOW)}; coordinates rounded to {PRECISION} decimals (~110 m). No hand-editing of geometry.",
        "file_size_bytes": size,
        "update_procedure": "Re-run scripts/build_neutral_geometry.py (pins the NE source); commit the regenerated GeoJSON + manifest.",
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {OUT_GEOJSON} ({size} bytes, {len(kept)} features)")
    print(f"  checksum sha256:{out_sha}")
    print(f"Wrote {OUT_MANIFEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
