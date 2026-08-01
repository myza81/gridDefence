import maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";

/**
 * PMTiles ⇄ MapLibre integration.
 *
 * The offline Standard style's vector source uses a `pmtiles://` URL
 * (`pmtiles:///map-assets/standard/peninsular-malaysia.pmtiles`). MapLibre must
 * know how to resolve that scheme, which requires registering the PMTiles
 * protocol handler exactly once for the whole app — registering twice throws
 * ("Protocol already added"). `registerPmtilesProtocol()` is therefore
 * idempotent and safe to call from every map mount.
 *
 * PMTiles reads the archive with HTTP **range requests**, so the static server
 * hosting `/map-assets/**` must honour `Range`/`Accept-Ranges` (Vite dev and
 * most static servers do; see docs/architecture/engineering-map.md for the
 * IIS/Nginx note). Range/read failures surface as normal MapLibre source
 * errors and are handled by the map's bounded fallback — they never retry
 * indefinitely.
 */
let registered = false;

export function registerPmtilesProtocol(): void {
  if (registered) return;
  const protocol = new Protocol();
  maplibregl.addProtocol("pmtiles", protocol.tile);
  registered = true;
}

/** Test-only: reset the one-time guard so registration can be re-exercised. */
export function __resetPmtilesProtocolForTests(): void {
  if (registered) {
    try {
      maplibregl.removeProtocol("pmtiles");
    } catch {
      // ignore — best-effort teardown in tests
    }
  }
  registered = false;
}
