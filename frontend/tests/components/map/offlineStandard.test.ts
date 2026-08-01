import { afterEach, describe, expect, it, vi } from "vitest";

import { auditStyleForExternalUrls } from "../../../src/components/map/mapConfig";
import {
  isLocalMapAsset,
  probeLocalStandardInstalled,
  __resetMapAssetProbeCache,
  LOCAL_STANDARD_STYLE_URL,
} from "../../../src/components/map/mapAssets";
// The committed offline style — imported so the real auditor runs over the
// exact file the app serves (the CLI `npm run map:audit-style` guards it too).
import committedStyle from "../../../public/map-assets/standard/style.json";

describe("offline Standard style (committed)", () => {
  it("references only local application assets — no external hosts", () => {
    // The authoritative guard: the real auditor over the committed style.json.
    expect(auditStyleForExternalUrls(committedStyle)).toEqual([]);
  });

  it("uses application-relative glyphs, sprite, and a pmtiles source", () => {
    expect(committedStyle.glyphs).toBe("/map-assets/standard/glyphs/{fontstack}/{range}.pbf");
    expect(committedStyle.sprite).toBe("/map-assets/standard/sprites/light");
    expect(committedStyle.sources.protomaps.url).toBe("pmtiles:///map-assets/standard/peninsular-malaysia.pmtiles");
  });

  it("carries geometry and label layers", () => {
    expect(committedStyle.layers.length).toBeGreaterThan(30);
    expect(committedStyle.layers.some((l: { type: string }) => l.type === "symbol")).toBe(true);
  });

  it("still flags external glyph/sprite/tile URLs if they ever creep in", () => {
    expect(auditStyleForExternalUrls({ glyphs: "https://cdn.example/{fontstack}/{range}.pbf" })).toContain(
      "https://cdn.example/{fontstack}/{range}.pbf",
    );
    expect(auditStyleForExternalUrls({ sprite: "//cdn.example/sprite" })).toContain("//cdn.example/sprite");
    expect(
      auditStyleForExternalUrls({ sources: { s: { url: "pmtiles://https://cdn.example/a.pmtiles" } } }),
    ).toContain("pmtiles://https://cdn.example/a.pmtiles");
  });
});

describe("isLocalMapAsset", () => {
  it("recognises local /map-assets URLs and rejects external ones", () => {
    expect(isLocalMapAsset(LOCAL_STANDARD_STYLE_URL)).toBe(true);
    expect(isLocalMapAsset("/map-assets/standard/style.json")).toBe(true);
    expect(isLocalMapAsset("https://tiles.example/style.json")).toBe(false);
    expect(isLocalMapAsset(undefined)).toBe(false);
  });
});

describe("probeLocalStandardInstalled", () => {
  afterEach(() => {
    __resetMapAssetProbeCache();
    vi.unstubAllGlobals();
  });

  it("resolves true when the archive answers a range request", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 206 });
    vi.stubGlobal("fetch", fetchMock);
    await expect(probeLocalStandardInstalled()).resolves.toBe(true);
    // One bounded request, no retry storm.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0][1]).toMatchObject({ headers: { Range: "bytes=0-0" } });
  });

  it("resolves false when the archive is missing (404) — a clear unavailable signal", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
    await expect(probeLocalStandardInstalled()).resolves.toBe(false);
  });

  it("resolves false (never throws) when the fetch itself fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));
    await expect(probeLocalStandardInstalled()).resolves.toBe(false);
  });

  it("caches the result for the session (single probe, no polling)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200 });
    vi.stubGlobal("fetch", fetchMock);
    await probeLocalStandardInstalled();
    await probeLocalStandardInstalled();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
