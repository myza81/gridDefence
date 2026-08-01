// CLI guard: fail if the committed offline Standard style references any
// external host. Mirrors src/components/map/mapConfig.ts:auditStyleForExternalUrls
// (that TS function is unit-tested against the same style.json, so the two
// cannot silently drift). Usage:  node scripts/audit-standard-style.mjs
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const stylePath = resolve(here, "../public/map-assets/standard/style.json");

function auditStyleForExternalUrls(style) {
  const found = [];
  const isExternal = (raw) => {
    const value = raw.replace(/^pmtiles:\/\//i, "");
    return /^[a-z][a-z0-9+.-]*:\/\//i.test(value) || /^\/\//.test(value);
  };
  const visit = (node, key) => {
    if (key === "attribution") return;
    if (typeof node === "string") {
      if (isExternal(node)) found.push(node);
      return;
    }
    if (Array.isArray(node)) return node.forEach((n) => visit(n));
    if (node && typeof node === "object") {
      for (const [k, v] of Object.entries(node)) visit(v, k);
    }
  };
  visit(style);
  return [...new Set(found)];
}

const style = JSON.parse(readFileSync(stylePath, "utf8"));
const external = auditStyleForExternalUrls(style);
if (external.length > 0) {
  console.error(`FAIL: offline Standard style references ${external.length} external URL(s):`);
  for (const u of external) console.error(`  - ${u}`);
  process.exit(1);
}
console.log(`OK: offline Standard style is local-only (${style.layers.length} layers, no external hosts).`);
