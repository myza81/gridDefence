import { afterEach, describe, expect, it, vi } from "vitest";

import { auditStyleForExternalUrls, NEUTRAL_STYLE, NEUTRAL_GEOMETRY_URL, buildNeutralStyle } from "../../../src/components/map/mapConfig";

/**
 * Offline-capability guardrails for the Engineering Map basemap configuration.
 * These are pure-module tests (no WebGL): they verify that availability comes
 * from configuration, that unconfigured styles are omitted, and that the
 * neutral fallback and any "local" style are genuinely free of external URLs.
 */

/** Re-import mapConfig with a fresh env so module-eval-time config is exercised. */
async function loadConfig(env: Record<string, string | undefined>) {
  vi.resetModules();
  vi.unstubAllEnvs();
  for (const [k, v] of Object.entries(env)) {
    if (v !== undefined) vi.stubEnv(k, v);
  }
  return import("../../../src/components/map/mapConfig");
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.resetModules();
});

describe("auditStyleForExternalUrls", () => {
  it("flags absolute, protocol-relative and provider-scheme URLs", () => {
    const style = {
      glyphs: "https://tiles.example/fonts/{fontstack}/{range}.pbf",
      sprite: "//cdn.example/sprite",
      sources: { osm: { type: "vector", url: "mapbox://styles/x" } },
      layers: [{ id: "bg", type: "background", paint: { "background-color": "#fff" } }],
    };
    const found = auditStyleForExternalUrls(style);
    expect(found).toContain("https://tiles.example/fonts/{fontstack}/{range}.pbf");
    expect(found).toContain("//cdn.example/sprite");
    expect(found).toContain("mapbox://styles/x");
  });

  it("treats local paths and inline values as offline-capable", () => {
    const style = {
      glyphs: "/map-assets/fonts/{fontstack}/{range}.pbf",
      sprite: "/map-assets/sprite",
      sources: { local: { type: "vector", tiles: ["/map-assets/tiles/{z}/{x}/{y}.pbf"] } },
      layers: [{ id: "water", type: "fill", paint: { "fill-color": "#a0c8f0" } }],
    };
    expect(auditStyleForExternalUrls(style)).toEqual([]);
  });

  it("confirms the neutral geographic style references only the local bundled geometry", () => {
    // No external hosts; only the app-relative Natural Earth GeoJSON is fetched.
    expect(auditStyleForExternalUrls(NEUTRAL_STYLE)).toEqual([]);
    expect(NEUTRAL_STYLE.glyphs).toBeUndefined();
    expect(NEUTRAL_STYLE.sprite).toBeUndefined();
    const source = (NEUTRAL_STYLE.sources as Record<string, { data?: string }>).neutral;
    expect(source.data).toBe(NEUTRAL_GEOMETRY_URL);
    expect(NEUTRAL_GEOMETRY_URL.startsWith("/map-assets/")).toBe(true);
    // The builder accepts an override but stays local by construction.
    expect(auditStyleForExternalUrls(buildNeutralStyle("/map-assets/neutral/x.geojson"))).toEqual([]);
  });
});

describe("BASEMAP_STYLES availability from configuration", () => {
  type Cat = { id: string; styleUrl?: string; inlineStyle?: unknown };
  const std = (b: Cat[]) => b.find((s) => s.id === "standard")!;
  const sat = (b: Cat[]) => b.find((s) => s.id === "satellite")!;

  it("offers Standard + Satellite by default (built-in governed defaults)", async () => {
    const { BASEMAP_STYLES, DEFAULT_STYLE_ID, DEFAULT_STANDARD_STYLE_URL, DEFAULT_SATELLITE_TILE_URL } = await loadConfig({
      VITE_MAP_STYLE_STANDARD: undefined,
      VITE_MAP_STYLE_SATELLITE: undefined,
      VITE_MAP_STYLE_TERRAIN: undefined,
      VITE_MAP_STYLE_URL: undefined,
    });
    // Standard AND Satellite are available out of the box (MVP parity); Terrain omitted.
    expect(BASEMAP_STYLES.map((s) => s.id)).toEqual(["standard", "satellite"]);
    expect(DEFAULT_STYLE_ID).toBe("standard"); // Standard remains the default
    expect(std(BASEMAP_STYLES).styleUrl).toBe(DEFAULT_STANDARD_STYLE_URL);
    // Satellite default is an inline raster style over the governed EOX tiles.
    const satStyle = sat(BASEMAP_STYLES).inlineStyle as { sources: Record<string, { tiles: string[] }> };
    expect(satStyle.sources.satellite.tiles[0]).toBe(DEFAULT_SATELLITE_TILE_URL);
    expect(sat(BASEMAP_STYLES).styleUrl).toBeUndefined();
  });

  it("lets VITE_MAP_STYLE_STANDARD override the built-in Standard default", async () => {
    const { BASEMAP_STYLES, DEFAULT_STANDARD_STYLE_URL } = await loadConfig({
      VITE_MAP_STYLE_STANDARD: "https://override.example/style.json",
      VITE_MAP_STYLE_URL: undefined,
    });
    expect(std(BASEMAP_STYLES).styleUrl).toBe("https://override.example/style.json");
    expect(std(BASEMAP_STYLES).styleUrl).not.toBe(DEFAULT_STANDARD_STYLE_URL);
  });

  it("lets VITE_MAP_STYLE_SATELLITE override the built-in Satellite default (provider style URL)", async () => {
    const { BASEMAP_STYLES } = await loadConfig({
      VITE_MAP_STYLE_SATELLITE: "https://api.maptiler.com/maps/satellite/style.json?key=X",
    });
    expect(sat(BASEMAP_STYLES).styleUrl).toBe("https://api.maptiler.com/maps/satellite/style.json?key=X");
    expect(sat(BASEMAP_STYLES).inlineStyle).toBeUndefined(); // configured URL, not the built-in raster
  });

  it("includes Terrain only when its URL is set; Standard remains default", async () => {
    const { BASEMAP_STYLES, DEFAULT_STYLE_ID } = await loadConfig({
      VITE_MAP_STYLE_STANDARD: "https://dev.example/standard.json",
      VITE_MAP_STYLE_TERRAIN: "https://dev.example/terrain.json",
    });
    expect(BASEMAP_STYLES.map((s) => s.id)).toEqual(["standard", "satellite", "terrain"]);
    expect(DEFAULT_STYLE_ID).toBe("standard");
  });

  it("honours VITE_MAP_STYLE_URL as the Standard alias", async () => {
    const { BASEMAP_STYLES } = await loadConfig({
      VITE_MAP_STYLE_STANDARD: undefined,
      VITE_MAP_STYLE_URL: "/map-assets/styles/standard/style.json",
    });
    expect(std(BASEMAP_STYLES).styleUrl).toBe("/map-assets/styles/standard/style.json");
  });

  it("treats an empty/whitespace Standard override as unset and uses the built-in default", async () => {
    const { BASEMAP_STYLES, DEFAULT_STANDARD_STYLE_URL } = await loadConfig({
      VITE_MAP_STYLE_STANDARD: "   ",
      VITE_MAP_STYLE_URL: undefined,
    });
    expect(std(BASEMAP_STYLES).styleUrl).toBe(DEFAULT_STANDARD_STYLE_URL);
  });
});

describe("buildSatelliteRasterStyle", () => {
  it("is a raster style over the governed EOX tiles with Sentinel-2/CC-BY attribution and a backdrop", async () => {
    const { buildSatelliteRasterStyle, DEFAULT_SATELLITE_TILE_URL, styleSource } = await loadConfig({});
    const style = buildSatelliteRasterStyle();
    const satSource = style.sources.satellite as { type: string; tiles: string[]; attribution?: string };
    expect(satSource).toMatchObject({ type: "raster", tiles: [DEFAULT_SATELLITE_TILE_URL] });
    expect(String(satSource.attribution)).toMatch(/Sentinel-2 cloudless|EOX|CC-BY/i);
    // A defined background sits under the imagery ⇒ an outage is a backdrop, not blank.
    expect(style.layers[0]).toMatchObject({ id: "background", type: "background" });
    expect(style.layers.some((l: { type: string }) => l.type === "raster")).toBe(true);
    // No glyphs/sprites (cluster counts are DOM markers, so still visible).
    expect(style.glyphs).toBeUndefined();
    expect(style.sprite).toBeUndefined();
    // styleSource hands MapLibre the inline style object when there is no URL.
    expect(styleSource({ id: "satellite", label: "Satellite", available: true, inlineStyle: style })).toBe(style);
    expect(styleSource({ id: "standard", label: "Standard", available: true, styleUrl: "u" })).toBe("u");
  });

  it("differs in attribution from Standard/Neutral (attribution changes by provider)", async () => {
    const { buildSatelliteRasterStyle, buildNeutralStyle } = await loadConfig({});
    const satAttr = String((buildSatelliteRasterStyle().sources.satellite as { attribution?: string }).attribution);
    const neutralAttr = String((buildNeutralStyle().sources as Record<string, { attribution?: string }>).neutral.attribution);
    expect(satAttr).not.toBe(neutralAttr);
    expect(satAttr).toMatch(/EOX|Sentinel/i);
    expect(neutralAttr).toMatch(/Natural Earth/i);
  });
});
