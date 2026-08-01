# Offline Standard Basemap — Acquisition Decision & Reproducible Build (Route A)

Status: Active (Phase E.1D). Companion to [engineering-map.md](engineering-map.md)
(§11b offline package) and governed by
[licensing-policy.md](../engineering/licensing-policy.md) +
[THIRD_PARTY_NOTICES.md](../../THIRD_PARTY_NOTICES.md).

This document records **how GridDefence's canonical offline Standard basemap for
Peninsular Malaysia is obtained**, why a pre-built package was rejected, and the
exact reproducible workflow that produces it. It changes no application
behaviour — the app already consumes `/map-assets/standard/**` (Phase E.1B).

---

## 1. Acquisition strategy & decision

Two routes were evaluated per the phase brief:

- **Route B (preferred):** adopt a professionally-maintained **pre-built PMTiles
  package**, accepted only if it satisfies *every* Phase E.1C governance
  requirement (licence, redistribution, attribution, provenance, checksum,
  enterprise suitability, technical fit).
- **Route A (fallback):** if no acceptable pre-built package exists, produce a
  fully documented, reproducible build from approved OpenStreetMap sources.

**Decision: Route A.** No pre-built package satisfies *all* requirements at once
(a pinned, region-scoped, freely-redistributable, checksummed Peninsular-Malaysia
artifact). Details below. Per the governance rule, we did **not** weaken any
E.1C requirement to force Route B.

## 2. Candidate discovery & comparison (verified, not assumed)

| Candidate | Org | Licence (data / style) | Redistribution & offline hosting | Coverage / form | Decision |
|---|---|---|---|---|---|
| **Protomaps basemaps** (build profile + global build) | Protomaps LLC | **ODbL** tiles / **BSD-3 + CC0** styles (verified in [protomaps/basemaps README](https://github.com/protomaps/basemaps)) | **Permitted** — "free and unmodified redistributions of tiles and styles are permitted"; must visibly attribute © OpenStreetMap | **Global** rolling build (~100+ GB) **or on-demand generation** per named area (Planetiler). No pinned regional file. | **ACCEPT as the approved *source*** for Route A (not as a turnkey pre-built regional package) |
| **OpenMapTiles / MapTiler data** | MapTiler AG | Schema BSD; **prepared planet/region tiles are a MapTiler commercial product** (routed via maptiler.com/data) | **Not clearly granted** for free offline enterprise redistribution; commercial terms/attribution apply | Region-scoped, pre-built | **REJECT** — redistribution rights uncertain/commercial (E.1C: exclude when uncertain) |
| **Hosted PMTiles/tile services** (Stadia, demo buckets, etc.) | various | mixed / service ToS | Hosted APIs; offline redistribution not granted | online only | **REJECT** — not offline-redistributable |
| **Geofabrik extracts** | Geofabrik | **ODbL** (raw `.osm.pbf`) | Permitted with attribution | Raw OSM data, **not** vector tiles | **Not a Route B package** — it is a Route A *input* |

### Governance evaluation of the accepted source (Protomaps/OSM)

- **Licence:** tiles **ODbL-1.0** (OSM Produced Work); styles **BSD-3 / CC0**;
  Natural Earth (included) is public domain. All present in
  [`licenses/`](../../licenses/) and approved in the policy (ODbL = MEDIUM /
  review-required, permitted for internal offline serving with attribution).
- **Attribution:** "© OpenStreetMap contributors, © Protomaps" — carried in the
  committed `style.json` source `attribution` and rendered by MapLibre's
  attribution control (offline + online, all viewports).
- **Redistribution / offline hosting:** explicitly permitted for free, unmodified
  tiles/styles.
- **Enterprise suitability & sustainability:** actively maintained; the schema
  matches our already-committed `protomaps-themes-base` style; PMTiles is a
  public-domain open specification.
- **Why not adopt the global file directly:** packaging global data is
  disallowed (engineering-map.md §5) and impractical (~100+ GB); a regional
  subset is required — which means a build/extract step. Hence **Route A**.

## 3. External tools required (reported per engineering-map.md / E.1B §6)

The regional build cannot be produced by repository scripts alone. One of the
following operator-provided tools is required (neither is bundled; both are
portable, need no admin rights, and are licence-clean):

| Tool | Licence | Purpose | Notes |
|---|---|---|---|
| **Planetiler** (`planetiler.jar`) | Apache-2.0 | Generate `peninsular-malaysia.pmtiles` from OSM (Protomaps basemaps profile) | Needs a JRE (Java 21+). Downloads the Geofabrik extract automatically. 100% self-hosted build. |
| **`pmtiles` CLI** (alternative) | BSD-3-Clause | `pmtiles extract` a Peninsular-Malaysia bbox from the open Protomaps global build via HTTP range requests | Single portable binary. Smaller/faster than a full build; depends on Protomaps' hosted build being reachable at build time. |

These are **build-time** tools only — they are not shipped, not linked into the
application, and not required at runtime. IT approval to run a portable JRE or a
single static binary may be required in a locked-down environment; both are
open-source and licence-clean (Apache-2.0 / BSD-3).

## 4. Route A — reproducible workflow

All commands are Windows PowerShell from the repository root. Geographic target:
Peninsular Malaysia, bbox `[99.3, 0.8, 104.9, 6.8]`, zoom 0–14.

### 4a. Produce the PMTiles archive

**Path A1 — Planetiler (fully self-hosted build):**
```powershell
# Prerequisite: Java 21+ (JRE). Download planetiler.jar (Apache-2.0) from
# https://github.com/onthegomap/planetiler/releases and verify its checksum.
# Using the Protomaps basemaps profile (matches our committed style schema):
java -Xmx8g -jar planetiler.jar `
  --area=malaysia-singapore-brunei `
  --bounds=99.3,0.8,104.9,6.8 `
  --download `
  --output=frontend/public/map-assets/standard/peninsular-malaysia.pmtiles
# (See protomaps/basemaps 'tiles/' profile for the exact profile invocation.)
```

**Path A2 — pmtiles extract (subset the open Protomaps global build):**
```powershell
# Prerequisite: pmtiles CLI (BSD-3) from https://github.com/protomaps/go-pmtiles/releases
# <BUILD> = a specific dated Protomaps build you pin (record its id + date).
pmtiles extract https://build.protomaps.com/<BUILD>.pmtiles `
  frontend/public/map-assets/standard/peninsular-malaysia.pmtiles `
  --bbox=99.3,0.8,104.9,6.8 --maxzoom=14
```

### 4b. Produce glyphs & sprites (labels + icons)
```powershell
# Noto Sans glyph ranges (OFL-1.1) + the 'light' sprite (Protomaps basemaps-assets).
# Obtain from https://github.com/protomaps/basemaps-assets and place as:
#   frontend/public/map-assets/standard/glyphs/{fontstack}/{range}.pbf
#   frontend/public/map-assets/standard/sprites/light.{json,png}
```

### 4c. (Re)generate the local style
```powershell
cd frontend
npm run map:build-style     # writes public/map-assets/standard/style.json (local-only)
npm run map:audit-style     # fails if any external host slipped in
cd ..
```

### 4d. Record provenance + checksums (governance)
```powershell
python scripts/record_map_provenance.py archive `
  --file frontend/public/map-assets/standard/peninsular-malaysia.pmtiles `
  --source "OpenStreetMap via Planetiler (Protomaps basemaps profile)" --version 2026-08-01
python scripts/record_map_provenance.py glyphs  --file <glyphs.zip-or-dir> --source "Noto Sans (protomaps/basemaps-assets)"
python scripts/record_map_provenance.py sprites --file <sprites.zip-or-dir> --source "Protomaps basemaps-assets (light)"
# Then set assets.sprites.licence in the manifest to the sprite source's SPDX id.
```

### 4e. Sharing to other engineers (optional, governed)
Host the produced binaries at an **internal** artifact URL, set each asset's
`download_url` in the manifest, and other engineers install via the governed
`python scripts/fetch_map_assets.py` (which verifies the recorded checksum and
rejects any asset missing licence/attribution/provenance).

### 4f. Point the app at the local style & verify offline
```powershell
# frontend/.env:  VITE_MAP_STYLE_STANDARD=/map-assets/standard/style.json
cd frontend; npm run dev
# Open http://localhost:5173/substations?view=map, DISCONNECT the network, and
# confirm the Standard map renders. Capture DevTools > Network showing zero
# external requests (see §5).
```

## 5. Offline verification checklist (operator, browser required)

With the network disconnected / external map hosts blocked, at 1440×900,
1024×768 and 390×844, confirm: Standard basemap renders (roads, water, land
cover, boundaries, place labels); substation markers; registry search + fly-to;
clustering; popup; scale bar; style selector; reset extent; **zero external
network requests** for the map (capture the DevTools Network HAR/screenshot);
no indefinite spinner, no request storm, no horizontal overflow; Table view
stays usable. This gate needs a real browser/WebGL and installed binaries and is
therefore an operator step (it cannot run in a headless CI/sandbox).

## 6. Reproducibility & provenance guarantees

- Inputs are deterministic: a named OSM area + a fixed bbox + a pinned tool
  version (record the Planetiler/pmtiles version and, for A2, the Protomaps
  build id/date).
- `record_map_provenance.py` stamps the SHA-256 + date into the manifest; the
  governance gate enforces licence/attribution/provenance/checksum before any
  install.
- No undocumented manual GIS steps: every step above is a single command.
- The committed `style.json` is regenerated by `npm run map:build-style` and
  audited local-only by `npm run map:audit-style`.
