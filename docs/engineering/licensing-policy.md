# Third-Party Licensing & Provenance Policy

- **Status:** Active
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§4 Engineering Truth Before Software Convenience, §22 Configuration Management, F7 Encryption & Data Protection, A15 Deferred Standards) and [01-engineering-philosophy.md](01-engineering-philosophy.md)
- **Companion artefacts:** [`../../THIRD_PARTY_NOTICES.md`](../../THIRD_PARTY_NOTICES.md) (inventory), [`../../licenses/`](../../licenses/) (verbatim texts)

GridDefence is deployed inside a utility engineering environment where legal
compliance is a **mandatory engineering requirement**. Every third-party
software component, font, icon, map asset, dataset, imagery source, or GIS
resource must be legally traceable, appropriately attributed, and suitable for
long-term enterprise deployment. **No implementation convenience overrides
licensing compliance.**

## 1. Guiding principle

> Do not introduce any third-party dependency, map dataset, imagery source,
> font, icon set, GIS package, or engineering dataset solely because it is
> technically convenient. Every external dependency must be justified by
> engineering value, have clearly documented licensing and provenance, be
> suitable for internal enterprise deployment, and be acceptable for long-term
> maintenance within a critical utility environment. If there is uncertainty
> regarding licensing, redistribution, attribution, or enterprise suitability,
> recommend against adoption until the issue is formally resolved.

This mirrors the platform's engineering stance: *truth and traceability before
convenience*. A dependency with unclear provenance is treated like ungoverned
engineering data — excluded until resolved.

## 2. Licence categories & risk

| Category | Licences | Risk | Meaning for GridDefence |
|---|---|---|---|
| **Permissive** | MIT, BSD-2-Clause, BSD-3-Clause, Apache-2.0, ISC, OFL-1.1 | **LOW** | Free commercial + internal use, redistribution, and modification. Attribution/NOTICE retention only (Apache-2.0 adds an explicit patent grant). |
| **Weak copyleft** | LGPL-2.1/3.0, MPL-2.0, **ODbL-1.0** (data) | **MEDIUM** | Usable, but with conditions: LGPL must stay dynamically linked/unmodified and replaceable; MPL is file-level copyleft; ODbL requires attribution and share-alike on derived **databases**. Requires review before adoption and documented mitigation. |
| **Strong copyleft** | GPL-2.0, GPL-3.0, AGPL-3.0 | **HIGH** | Can impose source-disclosure on the combined/served work. **Rejected** unless explicitly approved by the Project Owner with legal sign-off. AGPL is especially unsuitable for a served application. |
| **Proprietary / restricted** | vendor/EULA, "source-available", non-commercial | **HIGH** | Case-by-case; only with an explicit, compatible enterprise licence. |
| **Unknown / unstated** | no licence, ambiguous, conflicting | **UNKNOWN** | **Rejected** — absence of a licence means *no* rights are granted. |

Rationale: permissive licences pose negligible legal risk to an internally
deployed, partly proprietary platform. Copyleft risk scales with how the
component is combined and whether GridDefence *distributes* the result;
GridDefence is internally deployed and does not distribute its source, but
still honours all attribution and dynamic-linking conditions.

## 3. Approved licences (LOW — use freely, retain attribution)

- **MIT**, **BSD-2-Clause**, **BSD-3-Clause**, **ISC** — no material conditions
  beyond retaining the copyright/licence notice.
- **Apache-2.0** — approved; retain NOTICE and licence; includes an express
  patent grant (a benefit).
- **OFL-1.1** — approved for fonts/glyphs; honour the Reserved Font Name and
  no-standalone-sale conditions.

## 4. Licences requiring review before adoption (MEDIUM)

- **LGPL-3.0 / LGPL-2.1** — permitted **only** as an unmodified, dynamically
  used library (e.g. psycopg 3, in use). Must not be vendored, forked, or
  statically embedded without a fresh review. Ship the licence text and this
  notice.
- **MPL-2.0** — permitted with file-level compliance; review on adoption.
- **ODbL-1.0 / CC-BY / CC-BY-SA (data)** — permitted for internal, attributed
  use; do not publish a modified derived database externally without review.

## 5. Licences recommended against (HIGH — reject unless explicitly approved)

- **GPL-2.0, GPL-3.0** — reject unless the Project Owner explicitly approves
  with legal review, and only where linkage does not impose source disclosure.
- **AGPL-3.0** — reject; its network-use clause is unsuitable for a served
  engineering platform.
- **Proprietary / non-commercial / "unknown"** — reject by default.

Existing dependencies are **not** removed by this policy; where an existing
dependency falls into MEDIUM (psycopg/LGPL, OSM/ODbL) the obligation is
documented and mitigated in `THIRD_PARTY_NOTICES.md §7`.

## 6. Map / GIS asset & dataset governance

Map data and imagery are held to the same bar as code, plus explicit
**redistribution** analysis because GridDefence packages assets for **offline**
serving:

- **MapLibre GL JS, PMTiles, protomaps-themes-base** — BSD-3-Clause: approved,
  redistributable, attribution retained.
- **OpenStreetMap-derived vector tiles** — ODbL-1.0: approved for internal
  offline serving **with** "© OpenStreetMap contributors" attribution; no
  external publication of a modified derived database without review.
- **Fonts/glyphs (Noto, OFL-1.1)** — approved; honour OFL conditions.
- **Sprites** — record the specific source licence in the asset manifest before
  hosting; reject if unstated.
- **Satellite imagery** — **excluded.** Common providers forbid or do not clearly
  grant offline redistribution. Do not bundle satellite imagery without confirmed
  written redistribution rights. Until then, Satellite is connected-only.
- **Terrain / DEM / hillshade** — **excluded** on the same basis; confirm the
  specific source's redistribution terms before any offline packaging. Never
  fabricate terrain/contours.
- **Malaysian administrative boundaries** — no dataset with confirmed
  enterprise redistribution rights has been established. **Recommended against
  adoption** until an owner/licence is verified (this also gates the future
  ADR-030 State-boundary overlay). Candidate sources (GADM, DOSM, OSM-derived)
  each need explicit licence + redistribution confirmation before use.

**When redistribution, attribution, or provenance is uncertain: exclude.**

## 7. Attribution policy

Mandatory attributions must remain visible in all modes — online, **offline**,
desktop, tablet, and mobile — and must never be hidden:

- The Engineering Map renders attribution via MapLibre's attribution control,
  aggregating each source's `attribution` (the offline `style.json` carries
  "© OpenStreetMap contributors, © Protomaps"); `attribution.txt` accompanies
  the package.
- Apache-2.0 NOTICE text and BSD/MIT copyright notices are retained via
  `licenses/` + `THIRD_PARTY_NOTICES.md`.

## 8. Enterprise approval workflow (before an asset/dependency enters the repo)

No third-party component or dataset is added until all of the following are
recorded:

1. **Engineering review** — genuine engineering value; not convenience-only.
2. **Licence review** — SPDX licence identified, categorised (§2), and text
   present in `licenses/`.
3. **Source verification** — authoritative origin (repo/homepage/dataset owner)
   recorded.
4. **Checksum verification** — for binary/data assets, a SHA-256 recorded in the
   asset manifest; the setup script verifies it.
5. **Provenance** — version, download URL, and download date recorded.
6. **Repository approval** — added to `THIRD_PARTY_NOTICES.md` (and the map
   manifest for assets), with attribution wired where required.

## 9. Future-dependency gate (mandatory)

Every future dependency — npm, Python, font, icon set, map dataset, imagery,
GIS package, or engineering dataset — must, **before** it enters the repository,
record:

- **Licence** (SPDX id) and category (§2),
- **Source** (authoritative URL/owner),
- **Justification** (engineering value),
- **Approval** (who approved; Project Owner sign-off for MEDIUM/HIGH).

A change that adds a dependency without these is not merge-ready. Any HIGH or
"unknown" licence requires an explicit Project Owner decision, recorded (an ADR
where it affects long-term architecture, per CLAUDE.md A13/A15).

## 10. Review cadence

Re-audit on every dependency add/remove/version-bump and at each phase close
that changes dependencies. The inventory is re-derivable from
`node_modules/*/package.json` (frontend) and `importlib.metadata` (backend);
keep `THIRD_PARTY_NOTICES.md` and `licenses/` in step.
