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
  type Cat = { id: string; styleUrl?: string };
  const std = (b: Cat[]) => b.find((s) => s.id === "standard")!;

  it("offers a single Standard basemap by default (no Satellite/Hybrid/Terrain)", async () => {
    const { BASEMAP_STYLES, DEFAULT_STYLE_ID, DEFAULT_STANDARD_STYLE_URL } = await loadConfig({
      VITE_MAP_STYLE_STANDARD: undefined,
      VITE_MAP_STYLE_URL: undefined,
    });
    expect(BASEMAP_STYLES.map((s) => s.id)).toEqual(["standard"]);
    expect(DEFAULT_STYLE_ID).toBe("standard");
    expect(std(BASEMAP_STYLES).styleUrl).toBe(DEFAULT_STANDARD_STYLE_URL);
  });

  it("ignores removed Satellite/Hybrid/Terrain env vars — only Standard is ever offered", async () => {
    const { BASEMAP_STYLES } = await loadConfig({
      VITE_MAP_STYLE_SATELLITE: "https://x.example/satellite.json",
      VITE_MAP_STYLE_HYBRID: "https://x.example/hybrid.json",
      VITE_MAP_STYLE_TERRAIN: "https://x.example/terrain.json",
    });
    expect(BASEMAP_STYLES.map((s) => s.id)).toEqual(["standard"]);
  });

  it("lets VITE_MAP_STYLE_STANDARD override the built-in Standard default", async () => {
    const { BASEMAP_STYLES, DEFAULT_STANDARD_STYLE_URL } = await loadConfig({
      VITE_MAP_STYLE_STANDARD: "https://override.example/style.json",
      VITE_MAP_STYLE_URL: undefined,
    });
    expect(std(BASEMAP_STYLES).styleUrl).toBe("https://override.example/style.json");
    expect(std(BASEMAP_STYLES).styleUrl).not.toBe(DEFAULT_STANDARD_STYLE_URL);
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
