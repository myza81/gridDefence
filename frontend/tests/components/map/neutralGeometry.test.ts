import { describe, expect, it } from "vitest";

import { auditStyleForExternalUrls, buildNeutralStyle, NEUTRAL_GEOMETRY_URL } from "../../../src/components/map/mapConfig";
// The bundled neutral-geometry provenance manifest (committed alongside the
// GeoJSON). Byte-exact checksum verification lives in the CLI guard
// `npm run map:audit-neutral`; here we assert provenance completeness + that the
// neutral style is genuinely local (no external requests).
import manifest from "../../../public/map-assets/neutral/manifest.json";

describe("neutral-mode bundled geometry", () => {
  it("declares complete, governed provenance (public-domain Natural Earth)", () => {
    expect(manifest.licence).toBe("Public Domain");
    expect(manifest.source).toMatch(/Natural Earth/i);
    expect(manifest.attribution).toMatch(/Natural Earth/i);
    expect(manifest.checksum).toMatch(/^sha256:[0-9a-f]{64}$/);
    expect(Array.isArray(manifest.geographic_extent)).toBe(true);
    expect(manifest.features).toBeGreaterThan(0);
    expect(manifest.simplification).toBeTruthy();
    expect(manifest.file).toBe("southeast-asia.geojson");
  });

  it("neutral style references only the local bundled geometry (no external requests)", () => {
    const style = buildNeutralStyle();
    expect(auditStyleForExternalUrls(style)).toEqual([]);
    const source = (style.sources as Record<string, { data?: string }>).neutral;
    expect(source.data).toBe(NEUTRAL_GEOMETRY_URL);
    expect(NEUTRAL_GEOMETRY_URL).toMatch(/^\/map-assets\/neutral\//);
    // Only land/sea/coastline/borders — no glyphs/sprite/tiles ⇒ no labels,
    // roads, rivers, forests, imagery or terrain are claimed.
    expect(style.glyphs).toBeUndefined();
    expect(style.sprite).toBeUndefined();
  });
});
