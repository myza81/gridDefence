// Reproducible generator for the OFFLINE Standard Engineering Map style.
//
// Emits frontend/public/map-assets/standard/style.json — a MapLibre style that
// references ONLY application-relative local assets (a PMTiles vector archive,
// local glyph ranges, and a local sprite). The layer styling comes from
// `protomaps-themes-base` (MIT), which matches the Protomaps "basemaps" vector
// schema (OpenStreetMap data, ODbL). No external hosts appear in the output;
// `npm run map:audit-style` (auditStyleForExternalUrls) enforces that.
//
// Usage (from frontend/):  node scripts/build-standard-style.mjs
// It writes a committed, human-auditable JSON file; the heavy binary assets
// (the .pmtiles archive, glyphs/, sprites/) are fetched separately by
// scripts/fetch_map_assets.py and are NOT committed.

import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { noLabels, labels } from "protomaps-themes-base";

const here = dirname(fileURLToPath(import.meta.url));
const outFile = resolve(here, "../public/map-assets/standard/style.json");

const SOURCE = "protomaps";
const ATTRIBUTION =
  '© <a href="https://openstreetmap.org">OpenStreetMap</a> contributors, © <a href="https://protomaps.com">Protomaps</a>';

const style = {
  version: 8,
  name: "GridDefence Standard (offline — Peninsular Malaysia)",
  metadata: {
    "griddefence:offline": true,
    "griddefence:coverage": "Peninsular Malaysia",
    "griddefence:source": "Protomaps basemaps build of OpenStreetMap",
  },
  // Local glyphs + sprite (see map-assets/standard/README.md for provenance).
  glyphs: "/map-assets/standard/glyphs/{fontstack}/{range}.pbf",
  sprite: "/map-assets/standard/sprites/light",
  sources: {
    [SOURCE]: {
      type: "vector",
      // Resolved by the registered `pmtiles://` MapLibre protocol against an
      // application-relative archive path — no external host.
      url: "pmtiles:///map-assets/standard/peninsular-malaysia.pmtiles",
      attribution: ATTRIBUTION,
    },
  },
  // Geometry (coastline, water, land cover/forest, landuse, roads, boundaries)
  // + labels (places, roads) so the offline map is genuinely informative.
  layers: [...noLabels(SOURCE, "light", "en"), ...labels(SOURCE, "light", "en")],
};

mkdirSync(dirname(outFile), { recursive: true });
writeFileSync(outFile, JSON.stringify(style, null, 2) + "\n", "utf8");

const fonts = new Set();
for (const l of style.layers) {
  const f = l.layout && l.layout["text-font"];
  if (Array.isArray(f)) f.forEach((x) => typeof x === "string" && fonts.add(x));
}
console.log(`Wrote ${outFile}`);
console.log(`Layers: ${style.layers.length}`);
console.log(`Font stacks referenced: ${[...fonts].join(", ") || "(none)"}`);
