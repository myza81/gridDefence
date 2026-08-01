/**
 * Offline map-asset availability.
 *
 * The offline Standard basemap is served from application-relative paths under
 * `/map-assets/standard/**` (style JSON committed; the heavy `.pmtiles`,
 * glyphs and sprites are fetched by scripts/fetch_map_assets.py — see
 * docs/architecture/engineering-map.md). Before promising the offline map, the
 * UI runs a **single, bounded, cached** probe of the PMTiles archive so it can
 * show an honest "not installed" setup message instead of an indefinite
 * spinner or a request storm. Availability is decided by an actual resource
 * fetch, never `navigator.onLine`.
 */

/** Conventional local paths for the offline Standard package. */
export const LOCAL_STANDARD_STYLE_URL = "/map-assets/standard/style.json";
export const LOCAL_STANDARD_ARCHIVE_URL = "/map-assets/standard/peninsular-malaysia.pmtiles";

/** True when a style URL is served from the local application asset area. */
export function isLocalMapAsset(styleUrl: string | undefined | null): boolean {
  return typeof styleUrl === "string" && styleUrl.startsWith("/map-assets/");
}

let cachedProbe: Promise<boolean> | null = null;

/**
 * Resolve true when the local PMTiles archive is present and byte-range
 * readable. One request (a 1-byte range), time-bounded, cached for the session
 * — no retries, no polling. Any failure (404, network, timeout, no range
 * support) resolves false so the caller can guide setup.
 */
export function probeLocalStandardInstalled(
  url: string = LOCAL_STANDARD_ARCHIVE_URL,
  timeoutMs = 3000,
): Promise<boolean> {
  if (cachedProbe) return cachedProbe;
  cachedProbe = (async () => {
    if (typeof fetch !== "function") return false;
    const controller = typeof AbortController === "function" ? new AbortController() : null;
    const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
    try {
      const res = await fetch(url, { method: "GET", headers: { Range: "bytes=0-0" }, signal: controller?.signal });
      return res.ok || res.status === 206;
    } catch {
      return false;
    } finally {
      if (timer) clearTimeout(timer);
    }
  })();
  return cachedProbe;
}

/** Test-only: clear the session probe cache. */
export function __resetMapAssetProbeCache(): void {
  cachedProbe = null;
}
