// CLI guard for the bundled neutral-mode geometry. Verifies that the committed
// GeoJSON's SHA-256 matches the manifest checksum and that the manifest carries
// complete provenance (source, licence, attribution). Usage:
//   node scripts/audit-neutral-geometry.mjs
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const dir = resolve(here, "../public/map-assets/neutral");
const manifest = JSON.parse(readFileSync(resolve(dir, "manifest.json"), "utf8"));

const problems = [];
for (const field of ["source", "licence", "attribution", "checksum", "geographic_extent"]) {
  if (!manifest[field] || String(manifest[field]).trim() === "") problems.push(`manifest.${field} is missing`);
}

const geojsonPath = resolve(dir, manifest.file || "southeast-asia.geojson");
const bytes = readFileSync(geojsonPath);
const actual = "sha256:" + createHash("sha256").update(bytes).digest("hex");
if (manifest.checksum !== actual) {
  problems.push(`checksum mismatch: manifest ${manifest.checksum} vs file ${actual}`);
}

const fc = JSON.parse(bytes.toString("utf8"));
if (fc.type !== "FeatureCollection" || !Array.isArray(fc.features) || fc.features.length === 0) {
  problems.push("GeoJSON is not a non-empty FeatureCollection");
}
for (const f of fc.features ?? []) {
  const t = f.geometry?.type;
  if (t !== "Polygon" && t !== "MultiPolygon") problems.push(`unexpected geometry type: ${t}`);
}
const raw = bytes.toString("utf8");
if (/https?:\/\/|mapbox:\/\//i.test(raw)) problems.push("GeoJSON contains an external URL");

if (problems.length) {
  console.error("FAIL: neutral geometry audit:");
  for (const p of problems) console.error(`  - ${p}`);
  process.exit(1);
}
console.log(`OK: neutral geometry local + provenance verified (${fc.features.length} features, ${bytes.length} bytes, ${manifest.licence}).`);
