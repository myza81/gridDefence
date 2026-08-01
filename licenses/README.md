# Licence texts

Canonical, verbatim licence texts for every licence that applies to a
third-party component GridDefence uses. Texts were retrieved from the
authoritative [SPDX license-list-data](https://github.com/spdx/license-list-data)
on **2026-08-01** and are not modified.

Per-component licence assignment, versions, copyright holders, sources, and
attribution live in [`../THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md).
The governing policy (approved/prohibited licences, approval workflow, the
future-dependency gate) lives in
[`../docs/engineering/licensing-policy.md`](../docs/engineering/licensing-policy.md).

| File | SPDX id | Used by (examples) |
|---|---|---|
| `MIT.txt` | MIT | React, React DOM, React Router, TanStack Query/Table, Vite, Vitest, ESLint, TypeScript-ESLint, jsdom, FastAPI, SQLAlchemy, Alembic, Pydantic, redis-py, Ruff, pytest, anyio |
| `BSD-2-Clause.txt` | BSD-2-Clause | RQ |
| `BSD-3-Clause.txt` | BSD-3-Clause | MapLibre GL JS, PMTiles, protomaps-themes-base, uvicorn, Starlette, httpx, fakeredis, Click |
| `Apache-2.0.txt` | Apache-2.0 | Apache ECharts, TypeScript, bcrypt, python-multipart, pytest-asyncio |
| `LGPL-3.0-only.txt` | LGPL-3.0-only | psycopg 3 (PostgreSQL driver) — weak copyleft; see notes |
| `GPL-3.0-only.txt` | GPL-3.0-only | **Not** a licence of any GridDefence dependency. Included only because `LGPL-3.0-only` incorporates the GPL-3.0 terms by reference. GridDefence ships no GPL-licensed code. |
| `OFL-1.1.txt` | OFL-1.1 | Noto Sans glyphs (offline map fonts) |
| `ODbL-1.0.txt` | ODbL-1.0 | OpenStreetMap-derived map data (offline basemap) |

Only licences actually in use are stored here. Add a new file here (and a row
above) whenever a newly approved dependency introduces a licence not yet listed.
