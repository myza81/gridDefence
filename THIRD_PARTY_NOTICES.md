# Third-Party Notices

GridDefence incorporates third-party software and data. This file is the
authoritative inventory of every direct third-party dependency, its licence,
source, purpose, and attribution obligation. Full licence texts are in
[`licenses/`](licenses/); the governing policy is
[`docs/engineering/licensing-policy.md`](docs/engineering/licensing-policy.md).

- **Scope:** direct dependencies declared by GridDefence (`frontend/package.json`,
  `backend/pyproject.toml`) and the map assets/data the application serves.
  Transitive dependencies inherit the same policy; their licences are captured
  by `npm`/`pip` metadata and audited by the future-dependency gate.
- **Versions:** the resolved versions in the committed lockfiles at the date
  below. Ranges are declared in the manifests.
- **GridDefence's own code** is proprietary (`backend/pyproject.toml:
  license = "Proprietary"`); this file covers third-party components only.
- **Last reviewed:** 2026-08-01.

---

## 1. Frontend — runtime dependencies (shipped to the browser)

| Name | Version | Licence | Copyright / holder | Source | Purpose | Attribution |
|---|---|---|---|---|---|---|
| react | 18.3.1 | MIT | Meta Platforms, Inc. and affiliates | https://github.com/facebook/react | UI library | Not required at runtime (MIT) |
| react-dom | 18.3.1 | MIT | Meta Platforms, Inc. and affiliates | https://github.com/facebook/react | React DOM renderer | — |
| react-router-dom | 6.30.4 | MIT | Remix Software, Inc. | https://github.com/remix-run/react-router | Client-side routing | — |
| @tanstack/react-query | 5.101.2 | MIT | Tanner Linsley | https://github.com/TanStack/query | Server-state/data fetching | — |
| @tanstack/react-table | 8.21.3 | MIT | Tanner Linsley | https://github.com/TanStack/table | Registry tables | — |
| echarts | 5.6.0 | Apache-2.0 | The Apache Software Foundation | https://github.com/apache/echarts | Engineering charts | Retain NOTICE/attribution per Apache-2.0 §4 |
| maplibre-gl | 4.7.1 | BSD-3-Clause | MapLibre contributors | https://github.com/maplibre/maplibre-gl-js | Engineering Map renderer | Retain copyright notice |
| pmtiles | 4.4.1 | BSD-3-Clause | Protomaps LLC / Brandon Liu | https://github.com/protomaps/PMTiles | Single-file offline tile archive protocol | Retain copyright notice |
| protomaps-themes-base | 4.5.0 | BSD-3-Clause | Protomaps LLC | https://github.com/protomaps/basemaps | Offline Standard map style layers | Retain copyright notice |

## 2. Frontend — development / build dependencies (not shipped)

| Name | Version | Licence | Source | Purpose |
|---|---|---|---|---|
| vite | 5.4.21 | MIT | https://github.com/vitejs/vite | Dev server / bundler |
| @vitejs/plugin-react | 4.7.0 | MIT | https://github.com/vitejs/vite-plugin-react | React fast-refresh/JSX |
| typescript | 5.9.3 | Apache-2.0 | https://github.com/microsoft/TypeScript | Type system / compiler |
| vitest | 2.1.9 | MIT | https://github.com/vitest-dev/vitest | Test runner |
| jsdom | 25.0.1 | MIT | https://github.com/jsdom/jsdom | DOM for tests |
| @testing-library/react | 16.3.2 | MIT | https://github.com/testing-library | Component testing |
| @testing-library/jest-dom | 6.9.1 | MIT | https://github.com/testing-library | DOM matchers |
| @testing-library/user-event | 14.6.1 | MIT | https://github.com/testing-library | Interaction testing |
| eslint | 8.57.1 | MIT | https://github.com/eslint/eslint | Linting |
| @typescript-eslint/parser | 8.62.1 | MIT | https://github.com/typescript-eslint/typescript-eslint | TS lint parser |
| @typescript-eslint/eslint-plugin | 8.62.1 | MIT | https://github.com/typescript-eslint/typescript-eslint | TS lint rules |
| eslint-plugin-react-hooks | 5.2.0 | MIT | https://github.com/facebook/react | Hooks lint rules |
| eslint-plugin-react-refresh | 0.4.26 | MIT | https://github.com/ArnaudBarre/eslint-plugin-react-refresh | Fast-refresh lint |
| @types/react | 18.3.31 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped | React type defs |
| @types/react-dom | 18.3.7 | MIT | https://github.com/DefinitelyTyped/DefinitelyTyped | React DOM type defs |

## 3. Backend — runtime dependencies

| Name | Version | Licence | Copyright / holder | Source | Purpose | Notes |
|---|---|---|---|---|---|---|
| fastapi | 0.139.0 | MIT | Sebastián Ramírez | https://github.com/fastapi/fastapi | Web framework | — |
| starlette | 1.3.1 | BSD-3-Clause | Encode OSS Ltd | https://github.com/encode/starlette | ASGI toolkit (FastAPI dep) | — |
| uvicorn | 0.50.0 | BSD-3-Clause | Encode OSS Ltd | https://github.com/encode/uvicorn | ASGI server | — |
| sqlalchemy | 2.0.51 | MIT | Michael Bayer | https://github.com/sqlalchemy/sqlalchemy | ORM / SQL toolkit | — |
| alembic | 1.18.5 | MIT | Michael Bayer | https://github.com/sqlalchemy/alembic | DB migrations | — |
| psycopg (+ psycopg-binary) | 3.3.4 | **LGPL-3.0-only** | The Psycopg Team / Daniele Varrazzo | https://github.com/psycopg/psycopg | PostgreSQL driver | **Weak copyleft — see §7.** Used unmodified via its public API (dynamic library); no psycopg source is modified or statically linked into proprietary code. |
| pydantic | 2.13.4 | MIT | Pydantic Services Inc. / Samuel Colvin | https://github.com/pydantic/pydantic | Validation / schemas | — |
| pydantic-core | 2.46.4 | MIT | Pydantic Services Inc. | https://github.com/pydantic/pydantic-core | Pydantic core (Rust) | — |
| pydantic-settings | 2.14.2 | MIT | Pydantic Services Inc. | https://github.com/pydantic/pydantic-settings | Settings management | — |
| bcrypt | 4.3.0 | Apache-2.0 | The Python Cryptographic Authority | https://github.com/pyca/bcrypt | Password hashing | Retain NOTICE per Apache-2.0 |
| redis | 5.3.1 | MIT | Redis Inc. / redis-py authors | https://github.com/redis/redis-py | Redis client (queue mode) | Client library only; the Redis server is a separate deployment choice |
| rq | 1.16.2 | BSD-2-Clause | Vincent Driessen | https://github.com/rq/rq | Background job queue | — |
| python-multipart | 0.0.32 | Apache-2.0 | Andrew Dunham | https://github.com/Kludex/python-multipart | Multipart form parsing | — |
| anyio | 4.14.1 | MIT | Alex Grönholm | https://github.com/agronholm/anyio | Async compatibility (transitive) | — |
| click | 8.4.2 | BSD-3-Clause | Pallets | https://github.com/pallets/click | CLI (uvicorn/rq dep) | — |
| h11 | 0.16.0 | MIT | Nathaniel J. Smith | https://github.com/python-hyper/h11 | HTTP/1.1 (uvicorn dep) | — |

## 4. Backend — development dependencies

| Name | Version | Licence | Source | Purpose |
|---|---|---|---|---|
| pytest | 8.4.2 | MIT | https://github.com/pytest-dev/pytest | Test framework |
| pytest-asyncio | 0.26.0 | Apache-2.0 | https://github.com/pytest-dev/pytest-asyncio | Async tests |
| httpx | 0.28.1 | BSD-3-Clause | https://github.com/encode/httpx | Test HTTP client |
| ruff | 0.15.20 | MIT | https://github.com/astral-sh/ruff | Lint / format |
| fakeredis | 2.36.2 | BSD-3-Clause | https://github.com/cunla/fakeredis-py | Redis fake for tests |

## 5. Map assets & data (offline Standard basemap — Phase E.1B)

These are **not committed** (git-ignored binaries fetched per workstation via
`scripts/fetch_map_assets.py`); this section records their provenance and the
committed style/manifest that reference them.
See [`frontend/public/map-assets/standard/`](frontend/public/map-assets/standard/).

| Component | Licence | Source / owner | Purpose | Attribution obligation |
|---|---|---|---|---|
| **Neutral-mode geometry** (bundled, committed) | **Public Domain** | Natural Earth (naturalearthdata.com), 1:50m Admin 0 Countries | Built-in land/sea/coastline/national-border reference for neutral mode (Southeast-Asia subset) — `frontend/public/map-assets/neutral/southeast-asia.geojson` | "Made with Natural Earth" (no attribution legally required); public domain |
| Map **data** (vector tiles) | **ODbL-1.0** | OpenStreetMap contributors | Roads, water, land cover, boundaries, place names for Peninsular Malaysia | "© OpenStreetMap contributors" must be shown; share-alike applies to derived **databases** |
| Vector-tile **build / schema** | BSD-3-Clause | Protomaps (build of OSM) | Tile packaging in the Protomaps basemaps schema | "© Protomaps" |
| Map **style layers** | BSD-3-Clause | protomaps-themes-base | Style/paint for the offline Standard map | Retain copyright notice |
| **Fonts / glyphs** | OFL-1.1 | Noto Sans (Google/Noto project) | Label rendering (Latin: English + Malay place names) | OFL: font name/RFN conditions; no standalone sale |
| **Sprites** | (per source) | Protomaps basemaps-assets | Icons for the style | Per the asset's own licence — record in its manifest before hosting |
| Included base data (Natural Earth) | Public domain | Natural Earth (naturalearthdata.com) | Small-scale base features inside the Protomaps schema | No attribution required |
| **Malaysian administrative boundaries** (as a separate governed layer) | **Not adopted** | — | Future ADR-030 State overlay | No enterprise-redistributable dataset confirmed — recommended against adoption until resolved |

### 5a. Build-time tools for the offline basemap (Route A — not shipped, not linked)

These are operator-provided, build-time-only tools used to generate the offline
Standard PMTiles (see [`docs/architecture/offline-basemap-build.md`](docs/architecture/offline-basemap-build.md)).
They are **not** bundled, **not** linked into the application, and **not**
required at runtime.

| Name | Licence | Source | Purpose |
|---|---|---|---|
| Planetiler | Apache-2.0 | https://github.com/onthegomap/planetiler | Generate Peninsular-Malaysia PMTiles from OSM (Protomaps profile) |
| pmtiles CLI (go-pmtiles) | BSD-3-Clause | https://github.com/protomaps/go-pmtiles | Alternative: `pmtiles extract` a regional subset from the open Protomaps build |

### 5b. Connected rich-basemap providers (runtime, environment-configured — none adopted by default)

Rich mode resolves the Standard style as `VITE_MAP_STYLE_STANDARD →
VITE_MAP_STYLE_URL → built-in governed default`. The **built-in default is
OpenFreeMap Liberty** (adopted, governed — see
[licensing-policy.md §6b](docs/engineering/licensing-policy.md)); the env vars
override it. No provider key/asset is committed or bundled; resources are fetched
at runtime under the provider's online-use terms (not offline redistribution),
and attribution is shown by MapLibre's attribution control.

| Provider | Underlying data | Attribution to display | Notes |
|---|---|---|---|
| **OpenFreeMap** (Standard built-in default) | OpenStreetMap (ODbL) | © OpenStreetMap contributors | No key; community-hosted (no SLA) — override for critical/HA production |
| MapTiler (override) | OSM (ODbL) + MapTiler | © MapTiler © OpenStreetMap contributors | Domain-restricted browser key; do not commit |
| Stadia Maps (override) | OSM (ODbL) | © Stadia Maps © OpenStreetMap contributors | Key / domain auth; do not commit |

Runtime attribution for the map is rendered by MapLibre's attribution control,
which aggregates each source's `attribution` field (the committed
`style.json` carries "© OpenStreetMap contributors, © Protomaps"). It remains
visible online and offline, on desktop/tablet/mobile. See
`frontend/public/map-assets/standard/attribution.txt`.

## 6. First-party assets

The GridDefence logo, login hero image, favicons, and all inline SVG icons are
first-party assets owned by the GridDefence project (not third-party) and are
covered by the project's proprietary licence.

## 7. Copyleft / attention items

- **psycopg 3 — LGPL-3.0-only (weak copyleft).** GridDefence uses psycopg as an
  unmodified PostgreSQL driver through its public Python API (dynamic use). The
  LGPL permits use in proprietary applications provided the LGPL component
  remains replaceable/upgradable and its licence + source availability are
  conveyed. GridDefence does **not** modify, fork, or statically embed psycopg
  source. Obligation satisfied by: shipping this notice, including
  `licenses/LGPL-3.0-only.txt` (and the referenced `GPL-3.0-only.txt`), and
  keeping psycopg an externally-installed dependency (pip), not vendored source.
  Flagged **MEDIUM** in the risk classification; approved for continued use as a
  dynamically-linked driver. Do not vendor or modify its source without a fresh
  licence review.
- **OpenStreetMap data — ODbL-1.0 (share-alike database licence).** Attribution
  is mandatory and provided. Share-alike applies if GridDefence publicly
  distributes a **derived database**; serving read-only tiles internally with
  attribution is compliant. Do not publish a modified OSM-derived dataset
  externally without a licence review.
- **Apache-2.0 components** (ECharts, TypeScript, bcrypt, python-multipart,
  pytest-asyncio) carry a NOTICE/attribution retention requirement and a patent
  grant — both satisfied by retaining `licenses/Apache-2.0.txt` and this notice.

## Maintenance

Regenerate/refresh this inventory whenever a dependency is added, removed, or
version-bumped, per the future-dependency gate in the licensing policy. The
frontend licence set can be re-derived from `frontend/node_modules/*/package.json`
`license` fields; the backend set from `importlib.metadata` in the `.venv`.
