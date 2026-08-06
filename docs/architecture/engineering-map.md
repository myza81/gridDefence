# Engineering Map — Framework, Offline Architecture & Operator Guide

Status: Implemented (Phase E.1A — cartographic enhancement + offline capability). Companion to [substation-registry-frontend.md](substation-registry-frontend.md). Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§15 Frontend, §22 Configuration, A7 Engineering vs Infrastructure config, A12 Frontend calculation boundary) and [EDR-006](../engineering/edr/EDR-006-operational-context-visualization.md) (visualisation is decision-support presentation, never a second source of engineering truth).

This document records how the **Engineering Map** is built and, critically, how it is expected to run **without internet connectivity**. It does not redefine any engineering behaviour: the map plots the *same* authoritative registry records the table shows, draws no lines, and computes no engineering facts.

---

## 0. Dual-mode map (current model — supersedes the operator-PMTiles requirement)

The map provides the richest resources actually available — nothing more, nothing less — in exactly two modes:

- **Rich mode** — when a configured online style (`VITE_MAP_STYLE_*`) and its resources load, the map shows that provider's detailed basemap (roads, water, land cover, place labels, boundaries, and satellite/terrain where configured), with attribution. It never claims a layer the loaded style does not actually provide.
- **Neutral mode** — the built-in fallback, used when no rich style is configured or one fails/times out. It renders a **small, locally bundled, public-domain** geographic reference (land / sea / coastlines / national borders) from **Natural Earth**, served app-relative from [`frontend/public/map-assets/neutral/`](../../frontend/public/map-assets/neutral/). It makes **no external font, sprite, tile, or glyph requests**, works immediately after clone + build (no Docker, no operator install, no internet), and shows **only** that geometry — no roads, rivers, forests, labels, landmarks, imagery, or terrain (none are packaged). Malaysian **State** boundaries are intentionally absent until a governed source passes the licensing gate.

In **both** modes GridDefence continues to show its own information: substation markers (lifecycle-coloured, drawn above the geography), clusters **with their numeric record count**, selected-marker highlight, details panel, registry search/filters, missing-coordinate summary, the accessible record list, and Open-Substation navigation. The metric scale bar and reset-to-Peninsular-Malaysia control work in both modes.

**Cluster counts without a glyph dependency.** The cluster *circle* is a MapLibre circle layer; the centred numeric *count* is rendered as a local **DOM marker** ([clusterCountMarkers.ts](../../frontend/src/components/map/clusterCountMarkers.ts)), not a MapLibre symbol/text layer. MapLibre text needs glyph resources, which the neutral offline style deliberately ships none of; DOM markers use the browser's own fonts, so the count is visible in **rich and neutral** modes with **no glyph/font request** (external or bundled) and no dependency on the basemap provider's fonts. The markers are pointer-transparent (clicks still hit the circle layer for expand/zoom), `aria-hidden` (the accessible record list is the non-visual equivalent), reconciled by `cluster_id` (reused as the map pans/zooms), cleared before a style change and rebuilt on `style.load` — so style reloads and rich↔neutral transitions never leave a cluster without its count.

**Mode detection & recovery.** Availability comes from actual style/resource load success or failure (not `navigator.onLine`). A rich load is time-bounded (default 8 s) — no indefinite spinner, no request storm, no continuous background probing, and it never silently switches to another public provider. States are `loading` → `rich` | `neutral`. In neutral mode a compact **"Retry rich map"** action attempts the configured rich style **once**; on success the map returns to rich mode preserving camera, selected substation, popup, filters and search; on failure it stays neutral (no retry loop). Mode is announced to assistive tech via a polite live region, and the status text says *"online geographic details unavailable"* — never "offline" — when the internet exists but the provider is simply unreachable.

**PMTiles is now optional.** The operator-installed offline PMTiles Standard package (§11b) is **no longer required** for map acceptance; it remains a documented, optional enterprise enhancement for deployments that want a rich *locally hosted* basemap. Its governance, provenance, and the reusable `pmtiles://` protocol are retained; missing PMTiles assets simply mean the map runs in neutral mode (they never make the fallback look broken). Neutral geometry provenance: [`frontend/public/map-assets/neutral/manifest.json`](../../frontend/public/map-assets/neutral/manifest.json) (public-domain Natural Earth, checksummed; regenerate with `python scripts/build_neutral_geometry.py`, verify with `npm run map:audit-neutral`).

### 0.1 Enabling rich mode (configuration) & why it may stay neutral

Rich mode is **off until configured**. If the map shows *Neutral map* with no online detail, the usual cause is **`CONFIGURATION_MISSING`**: no `VITE_MAP_STYLE_STANDARD` is set (there is no committed `frontend/.env`, and `.env.example` leaves it blank), so `BASEMAP_STYLES` is empty and the map starts neutral by design. To enable rich mode, set a governed provider style URL in `frontend/.env` and **restart Vite** (env is read at startup):

```
# frontend/.env  (see frontend/.env.example for governed provider options)
VITE_MAP_STYLE_STANDARD=https://tiles.openfreemap.org/styles/liberty      # no key, OSM/ODbL
# or a domain-restricted key provider:
# VITE_MAP_STYLE_STANDARD=https://api.maptiler.com/maps/streets-v2/style.json?key=YOUR_RESTRICTED_KEY
```

Provider governance (accept/reject, attribution, keys) is in [licensing-policy.md §6b](../engineering/licensing-policy.md) and [THIRD_PARTY_NOTICES.md §5b](../../THIRD_PARTY_NOTICES.md). `VITE_*` values are browser-exposed build-time config, not secrets — but do not commit real provider tokens.

**Essential vs non-essential failure.** Rich mode activates when MapLibre fires `style.load` (bounded by `loadTimeoutMs`, default 8 s). Only an **essential** failure falls back to neutral: the style document itself failing to load, or the timeout elapsing before `style.load`. A **non-essential** sub-resource error (an individual sprite, glyph, font, or tile — classified by [mapDiagnostics.ts](../../frontend/src/components/map/mapDiagnostics.ts) `classifyStyleError`, which are non-fatal in MapLibre and still allow `style.load`) does **not** discard an otherwise-usable rich basemap. The fallback is bounded — no indefinite spinner, no retry storm, no continuous probing, and never a silent switch to another public provider.

**Diagnostics (safe).** When rich mode is unavailable the map reports a closed-set reason (`configuration_missing` | `style_load_failed` | `timeout` | `unknown`), surfaced as a compact human summary next to the neutral status (e.g. *"The online basemap could not be loaded (blocked, unreachable, or invalid)."*). Reasons carry **no URLs or tokens**; a developer console line redacts URLs (query string dropped) via `redactUrl`. Raw stack traces/credentials/full URLs are never shown in the UI.

**Corporate network / allow-list.** On a managed laptop, rich failure is often a proxy/TLS-interception/CSP/DNS/firewall block of the provider, not an app bug. The map falls back to neutral promptly and honestly; to *enable* rich mode, IT should allow-list the chosen provider's domains (minimum necessary, no broad wildcards):

| Function | OpenFreeMap | MapTiler |
|---|---|---|
| Style + tiles + glyphs + sprites | `tiles.openfreemap.org` | `api.maptiler.com` |

(Stadia: `tiles.stadiamaps.com`.) Do not disable TLS verification, add HTTP endpoints, or require admin rights. If no provider can be approved, leave rich unset — neutral mode is a complete, governed default.

---

## 1. What the Engineering Map is

`EngineeringMap` ([frontend/src/components/map/EngineeringMap.tsx](../../frontend/src/components/map/EngineeringMap.tsx)) is a **registry-agnostic MapLibre GL wrapper**. It owns the map instance, controls (navigation + compass, metric scale, reset-to-extent, style selector), clustering, marker selection (subtle pulse + popup), and offline-first failure handling. It knows nothing about substations — callers pass one or more `EngineeringMapLayer`s (GeoJSON points + a category→colour map). Future engineering layers (Transformer / Circuit / Relay / Sensitive-Customer / defence-scheme overlays) plug in without changing the component. It is **infrastructure, not a one-off**.

The map is always a **progressive enhancement** over an accessible, keyboard-operable record list ([SubstationMapView](../../frontend/src/modules/substation_registry/components/SubstationMapView.tsx)): the map is never the only way to find or open a substation.

---

## 2. Operating modes (configuration only)

Two modes are selected purely by configuration — no code change (CLAUDE.md §22, A7). Each selectable basemap is a MapLibre **style URL**, configured per style:

| Variable | Meaning |
|---|---|
| `VITE_MAP_STYLE_STANDARD` | Standard "engineering day" style. (`VITE_MAP_STYLE_URL` is honoured as a back-compatible alias.) |
| `VITE_MAP_STYLE_SATELLITE` | Satellite imagery style (optional). |
| `VITE_MAP_STYLE_TERRAIN` | Terrain / relief style (optional). |

**Connected development mode** — externally hosted styles (require internet):
```
VITE_MAP_STYLE_STANDARD=https://your-provider.example/standard/style.json
VITE_MAP_STYLE_SATELLITE=https://your-provider.example/satellite/style.json
VITE_MAP_STYLE_TERRAIN=https://your-provider.example/terrain/style.json
```

**Offline / internal production mode** — every resource served from the GridDefence deployment or an internal service (no internet):
```
VITE_MAP_STYLE_STANDARD=/map-assets/styles/standard/style.json
VITE_MAP_STYLE_SATELLITE=/map-assets/styles/satellite/style.json
VITE_MAP_STYLE_TERRAIN=/map-assets/styles/terrain/style.json
```

**Availability comes from configuration, not code** ([mapConfig.ts](../../frontend/src/components/map/mapConfig.ts)). A style is offered in the selector only when its variable is set; unset styles are omitted rather than offered and then failing. When *nothing* is configured, the map degrades to the record list and the registry stays fully usable. No public provider is hard-coded as a production service, and the map **never silently falls back to a public external provider**.

The recommended **initial production target** is a detailed **offline Standard** map for Peninsular Malaysia; Satellite and Terrain are enabled only when locally licensed and hosted.

---

## 3. Offline resource audit (a local style JSON is not enough)

A style is offline-capable only if **every** resource it references resolves locally: the top-level style JSON *plus* its `glyphs`, `sprite`, and each source's `tiles`/`url` (vector, raster, raster-DEM/hillshade, contour). A "local" style that still points `glyphs`/`sprite`/`tiles` at `https://…`, `//host/…` or `mapbox://…` is **not** offline-capable.

`auditStyleForExternalUrls(style)` ([mapConfig.ts](../../frontend/src/components/map/mapConfig.ts)) scans a style object and returns every external URL it finds (empty ⇒ offline-capable). It is exercised by [mapConfig.test.ts](../../frontend/tests/components/map/mapConfig.test.ts) and should be run by operators against any style they intend to host offline. Checklist of resources to localise:

- style JSON · glyph/font ranges (`.pbf`) · sprite (`.json`/`.png`) · vector tiles · raster tiles · satellite imagery tiles · raster-DEM/hillshade tiles · contour vector tiles · administrative boundaries · place labels · roads · rivers/water · forest/land-cover.

---

## 4. Local map-serving strategy (Docker Compose → Kubernetes)

**Recommendation: package Peninsular-Malaysia vector tiles as a single [PMTiles](https://github.com/protomaps/PMTiles) archive, plus locally hosted MapLibre style + glyphs + sprite, served as static files by the existing frontend web server (or a small dedicated `map-assets` service).** Rationale: one immutable file, no tile database or tile-server process, HTTP range-request friendly, trivial to back up and version, and portable from Docker Compose to Kubernetes unchanged.

| Concern | Recommendation |
|---|---|
| Compose deployment | A `map-assets` static service (Nginx) mounting a versioned volume/image with `style.json`, `glyphs/`, `sprite.*`, and `peninsular-malaysia.pmtiles`; or serve the same folder from the frontend container. Frontend points `VITE_MAP_STYLE_STANDARD=/map-assets/styles/standard/style.json`. |
| Health check | HTTP `GET` on the style JSON. The map service being down must **not** make the wider GridDefence application unhealthy (see §9). |
| Startup | Deterministic — assets are baked into the image or a pre-populated named volume; **no runtime downloading of production tiles**. |
| Tile-data volume / size | Peninsular-Malaysia vector (Standard) at z0–z14 is typically ~a few hundred MB (confirm at packaging time). Satellite/terrain raster is far larger (§7). |
| Update process | Rebuild the assets image / replace the PMTiles file with a new dated version; documented in the operator runbook; frontend URL is unchanged. |
| Backup | The PMTiles + style/glyph/sprite bundle is a small, immutable artefact — back up with the deployment. |
| Caching | Long-lived `Cache-Control` on immutable tile/glyph/sprite assets; the style JSON short-lived so a re-packaged dataset is picked up. |
| Licensing / attribution | Only host data whose licence permits redistribution; keep the required attribution in the style's `attribution`/an on-map attribution control (see §7). |
| Kubernetes | Same static assets behind an Ingress path (or a small Deployment + Service); PMTiles on a ReadOnlyMany PVC or in the image. No change to the frontend contract. |

Alternatives evaluated and *not* chosen as the default: MBTiles behind a tile-server container (adds a stateful process), a full vector-tile server (operationally heavier), per-zoom static raster pyramids (simple but large and less crisp). Any of these remain compatible because the frontend only depends on a **style URL**.

**This document specifies the architecture; it does not fabricate map data.** Producing the actual PMTiles/style/glyph/sprite bundle for Peninsular Malaysia (from an appropriately licensed source such as OpenMapTiles/Protomaps builds of OSM) is a deployment/packaging step performed by an operator with confirmed redistribution rights — not invented here.

---

## 5. Required offline coverage

Initial locally hosted package should prioritise **Peninsular Malaysia**, with padding so coastal/border areas stay legible. The default and reset viewport is `PENINSULAR_MALAYSIA_BOUNDS = [99.3, 0.8, 104.9, 6.8]` (a display extent only — not an engineering region or operational boundary). Document at packaging time: geographic bounds, supported zoom range, approximate storage size, included layers, source-data version, and update procedure. Do **not** package global data without a justified requirement.

---

## 6. Failure behaviour, fallback hierarchy & connectivity detection

Map resource loading is **time-bounded** (`loadTimeoutMs`, default 8 s) — there is **no infinite retry** and no aggressive retry loop; a single missing *tile* does not tear the workspace down (only a style/glyph/sprite/source **load** failure triggers fallback). Availability is determined from **actual resource load success/failure**, not `navigator.onLine` (which does not indicate whether a map provider is reachable), and the app does not repeatedly probe external providers.

Deliberate fallback sequence, each stage attempted at most once (no loops):
```
Configured selected style
        ↓  (load fails / times out)
Configured local Standard style
        ↓  (load fails / times out)
Neutral local canvas  (inline style, zero network requests — markers still plotted)
        ↓  (only if even WebGL/canvas init fails)
Accessible Substation record list
```
The neutral style (`buildNeutralStyle()`, see §0) renders the bundled public-domain Natural Earth land/sea/coastline/border geometry with zero external requests. Clustering is **fully functional** in neutral mode — cluster circles (a MapLibre layer) and their numeric counts (local DOM markers, glyph-independent — see §0) both render, and click-to-expand works. Geometry is never fabricated; Malaysian State boundaries await a governed source.

When degraded, the UI shows an honest notice (e.g. *"The configured basemap could not be loaded. Showing a neutral offline canvas — every substation is still plotted and listed."*). When no map is possible at all it shows an explicit **Basemap unavailable — Substation Registry data remains available** state (never a permanent spinner or unexplained blank canvas). The **Table view and record list remain available at all times.**

---

## 7. Satellite & terrain — larger data and licence sensitivity

Satellite imagery and terrain/DEM data are far larger and often carry restrictive licences. For each offline style, document: source, licence, redistribution rights, storage estimate, supported zoom range, update process, and whether internal hosting is permitted. It is acceptable — and is the recommended initial posture — to ship an **offline Standard** basemap while leaving **Satellite and Terrain connected-only** until locally licensed and hosted; the selector then simply offers Standard alone, and the offline Standard map remains fully usable. **Do not package third-party imagery without confirmed redistribution rights, and do not fabricate contour/terrain geometry.** If the configured Standard style does not carry a layer (e.g. hillshade/contours), that limitation is documented honestly rather than faked.

---

## 8. Service worker & browser caching

Browser caching (or a service worker) may improve resilience for *previously loaded* assets, but it is **not** the offline strategy — locally hosted tiles + a controlled internal map service + deterministic deployment packaging are. The map must not be described as offline-capable merely because a previously visited tile might be cached. A service worker is **not** introduced by this phase; if considered later, document cache versioning, invalidation, maximum storage, partial-download behaviour, first-use limitation, browser support, and deployment risks first.

---

## 9. Docker Compose / deployment integration

Extend the deployment with a map-assets/tile service alongside `frontend`, `backend`, `postgres`, `redis`, and the worker. Requirements: health check on the style JSON; deterministic startup; a clear mounted-volume or image-packaging strategy; **no runtime downloading of production tiles**; environment-based style endpoints; a documented resource update procedure; and graceful operation when the map service is unavailable. Crucially, **the basemap service being unavailable must not make the whole GridDefence application unhealthy** — map failure is isolated to the map, and every other module keeps working.

---

## 10. Search, selection, scale — all offline

- **Search** is registry-only — GridDefence's own Substation data. No Nominatim, no Google, no external geocoding. Fly-to and selected-marker emphasis work entirely from local coordinates; records without coordinates remain disclosed.
- **Selection** highlights the marker (subtle pulse), opens a compact popup, and mirrors into the accessible side panel with the full record + **Open substation →** (SPA navigation).
- **Scale bar** (metric) is computed from the map projection/viewport and needs no network. It is *not* survey-grade; future distance measurement must also stay local and must never call an external API.

The popup is intentionally compact (mnemonic, official name, lifecycle, coordinate, Open) to avoid oversized popups; the full field set lives in the side panel. **Voltage is deliberately absent from the map** — it is a switchyard composition (per ADR-009/A2-F2), not part of the geographic registry projection; adding it would require a backend projection change and is out of scope for this cartographic phase (documented limitation).

---

## 11. Future authoritative boundary overlay (ADR-030 — not implemented here)

A future **governed** Malaysian State (admin level 1) boundary overlay belongs as an additional `EngineeringMapLayer` (line/fill), sourced from an authoritative, versioned, locally packaged dataset — exactly the dataset [ADR-030](../adr/ADR-030-coordinate-assisted-state-resolution.md) governs. The framework is already shaped for it: layers are additive, offline-served, and audited by `auditStyleForExternalUrls`. **This phase does not implement ADR-030** (coordinate→State resolution) and draws no boundary geometry; it only leaves the seam.

---

## 11b. Offline Standard package — implemented (Phase E.1B)

The offline Standard basemap is a concrete, no-Docker, no-tile-server package
served from the frontend's own static area at `/map-assets/standard/**`
([frontend/public/map-assets/standard/](../../frontend/public/map-assets/standard/)).

**Format — PMTiles.** A single-file vector archive read by MapLibre via the
`pmtiles://` protocol, registered exactly once by
[pmtilesProtocol.ts](../../frontend/src/components/map/pmtilesProtocol.ts)
(idempotent — safe on every map mount). Chosen over MBTiles-plus-a-tile-server
(no extra process) and loose raster pyramids (far larger). PMTiles reads via
HTTP **range requests**; Vite dev and most static servers honour this — for
IIS/Nginx production hosting, enable byte-range serving for `.pmtiles`
(Nginx does by default; IIS needs `Accept-Ranges` for the MIME type).

**Style.** [style.json](../../frontend/public/map-assets/standard/style.json) is
generated by [scripts/build-standard-style.mjs](../../frontend/scripts/build-standard-style.mjs)
using `protomaps-themes-base` (BSD-3-Clause) over the Protomaps "basemaps"
OpenStreetMap schema (ODbL). It references **only** application-relative assets:
`glyphs: /map-assets/standard/glyphs/{fontstack}/{range}.pbf`,
`sprite: /map-assets/standard/sprites/light`, and
`url: pmtiles:///map-assets/standard/peninsular-malaysia.pmtiles`. It has 68
layers (coastline, water, land cover/forest, landuse, roads, boundaries + place
& road labels). `npm run map:audit-style` (and a Vitest over the committed file
using `auditStyleForExternalUrls`) **fails** if any external host ever appears.

**Glyphs & sprites.** Font stacks are `Noto Sans Regular/Medium/Italic` (OFL
1.1) — Latin coverage, sufficient for English and Malay place names. Glyphs and
the `light` sprite are part of the fetched binaries, not committed.

**Repository-size strategy.** The committed, auditable text (style.json,
manifest.json, attribution.txt, README.md) lives in the repo; the heavy binaries
(`peninsular-malaysia.pmtiles`, `glyphs/`, `sprites/`) are **git-ignored**
(root `.gitignore`) and fetched per-workstation by
[scripts/fetch_map_assets.py](../../scripts/fetch_map_assets.py) (Python stdlib
only — no pip, no Docker, no admin), which reads
[manifest.json](../../frontend/public/map-assets/standard/manifest.json),
downloads each asset from an **operator-supplied** URL (no public provider is
hard-coded), verifies SHA-256, and refuses to overwrite without `--force`.

**Availability detection.** [mapAssets.ts](../../frontend/src/components/map/mapAssets.ts)
runs a single, bounded (3 s), session-cached range-request probe of the archive.
When the Standard style is the local package and the archive is absent,
`SubstationMapView` shows an explicit *"Offline Standard map assets are not
installed"* notice with the exact setup command, and the record list + Table
view stay usable. No `navigator.onLine`, no polling, no retry storm.

**Acquiring the basemap (Phase E.1D).** The canonical Peninsular-Malaysia
PMTiles is **generated (Route A)** from approved OpenStreetMap data (Protomaps
basemaps schema) — a pre-built package was evaluated and rejected on
licensing/provenance grounds. The full acquisition decision, candidate
comparison, external-tool requirements (Planetiler / pmtiles CLI), and the
reproducible build + provenance-recording steps are in
[offline-basemap-build.md](offline-basemap-build.md). The actual build and the
offline browser render check are operator steps (they need a build tool and a
real browser/WebGL).

**Windows setup (PowerShell, from repo root):**
```
.\.venv\Scripts\Activate.ps1
# edit frontend/public/map-assets/standard/manifest.json → set assets[*].url (+ sha256)
python scripts/fetch_map_assets.py
# set VITE_MAP_STYLE_STANDARD=/map-assets/standard/style.json in frontend/.env
cd frontend; npm run dev        # open /substations?view=map, then disconnect the network
```
See [DEVELOPMENT.md](../../DEVELOPMENT.md) → "Offline map assets" for the full
walkthrough and troubleshooting.

## 12. Configuration reference

See [frontend/.env.example](../../frontend/.env.example). Vite reads env from the `frontend/` directory; only `VITE_`-prefixed variables reach the browser bundle, and nothing secret belongs there. Attribution for any hosted data is carried in the style's own `attribution` and surfaced by MapLibre's attribution control.

## 13. Verification notes

`typecheck`, `lint`, `test`, and `build` are automated. Full **offline GL rendering** verification (the map drawing with internet disabled / external map hosts blocked, capturing network-request evidence that the offline Standard map makes no external calls) is a **browser/manual** step — jsdom has no WebGL, so it cannot run in the unit suite. The automated tests instead lock the offline *contract*: availability-from-configuration, unconfigured-styles-omitted, the neutral fallback and local styles being free of external URLs, and the registry data/list/search surviving basemap failure.
