import type { StyleSpecification } from "maplibre-gl";

/**
 * Engineering Map Framework — environment configuration & offline model.
 *
 * The basemap is configured through MapLibre **style URLs** (not raw tile
 * URLs), one per selectable style, so a deployment chooses its own map stack
 * without code changes (see docs/architecture/engineering-map.md).
 *
 * Standard resolution (rich map is the default experience — no `.env` needed):
 *
 *   VITE_MAP_STYLE_STANDARD  →  VITE_MAP_STYLE_URL (legacy alias)
 *                            →  built-in governed default (OpenFreeMap Liberty)
 *
 * GridDefence is an internal, single-approved-provider engineering app, so the
 * Standard style ships with a **governed built-in default** (already passed the
 * licensing/engineering review — see docs/engineering/licensing-policy.md §6b);
 * the environment variable is an **override**, not a requirement. A fresh clone
 * therefore starts in rich mode when the internet is reachable, and drops to the
 * built-in neutral map only when the provider is genuinely unavailable (handled
 * at runtime by EngineeringMap). Satellite/Terrain remain optional env-only
 * styles. On failure the map never silently switches to a *different* public
 * provider — it falls back to the local neutral geometry.
 *
 * Critical/high-availability or air-gapped deployments should override
 * VITE_MAP_STYLE_STANDARD with a paid provider (domain-restricted key) or the
 * self-hosted offline package rather than relying on the community default.
 */

export interface EngineeringMapStyle {
  /** Stable id used in the selector and in URLs/state. */
  id: string;
  /** Human label shown in the style selector. */
  label: string;
  /** MapLibre style URL — external (dev) or internal/local (production). */
  styleUrl?: string;
  /** Inline MapLibre style (e.g. the built-in raster Satellite), used when no
   *  style URL is configured. Exactly one of styleUrl / inlineStyle is present. */
  inlineStyle?: StyleSpecification;
  /** Always true for catalogue entries (kept for API stability). */
  available: boolean;
  /** One-line description shown as a tooltip / caption. */
  description?: string;
}

/** What to hand MapLibre's `setStyle` for a catalogue entry — a URL or an inline
 *  style object (MapLibre `setStyle` accepts both). */
export function styleSource(style: EngineeringMapStyle): string | StyleSpecification {
  return style.inlineStyle ?? (style.styleUrl as string);
}

/** Read a Vite env var, treating empty/whitespace as unset. */
function env(name: string): string | undefined {
  const raw = (import.meta.env as Record<string, string | undefined>)[name];
  const value = typeof raw === "string" ? raw.trim() : "";
  return value === "" ? undefined : value;
}

/**
 * Governed built-in default Standard basemap (OpenFreeMap Liberty — OpenStreetMap
 * data under ODbL, no API key, CORS-enabled). Adopted per licensing-policy §6b so
 * the rich map is the out-of-the-box experience; overridable via env for a
 * paid/self-hosted provider. Attribution is rendered by MapLibre's attribution
 * control from the style's own metadata.
 */
export const DEFAULT_STANDARD_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";

/**
 * Governed built-in default Satellite imagery: EOX **Sentinel-2 cloudless**
 * (Copernicus Sentinel data), licensed **CC-BY-4.0** — free for internal/
 * enterprise/commercial use with attribution, no API key, CORS-enabled. It is
 * imagery-only (no roads/labels/boundaries); a deployment wanting a hybrid
 * imagery+labels style sets `VITE_MAP_STYLE_SATELLITE` to a provider style URL
 * (e.g. a domain-keyed MapTiler Satellite). See licensing-policy §6c.
 */
export const DEFAULT_SATELLITE_TILE_URL = "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg";
export const SATELLITE_ATTRIBUTION = 'Sentinel-2 cloudless — <a href="https://s2maps.eu">s2maps.eu</a> by EOX IT Services GmbH (Contains modified Copernicus Sentinel data), CC-BY-4.0';

/** Build a raster MapLibre style for satellite imagery. A defined dark
 *  background sits under the raster so an imagery outage shows a backdrop with
 *  markers on top — never a blank canvas. No glyphs/sprites (cluster counts are
 *  DOM markers, so they stay visible). */
export function buildSatelliteRasterStyle(tileUrl: string = DEFAULT_SATELLITE_TILE_URL, attribution: string = SATELLITE_ATTRIBUTION): StyleSpecification {
  return {
    version: 8,
    name: "satellite-raster",
    sources: { satellite: { type: "raster", tiles: [tileUrl], tileSize: 256, minzoom: 0, maxzoom: 16, attribution } },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#0B1220" } },
      { id: "satellite", type: "raster", source: "satellite" },
    ],
  };
}

/**
 * Style catalogue. Adding a future style (Dark, High Contrast, Utility,
 * Engineering) is a one-line addition here plus an env var — the EngineeringMap
 * component and every consumer are unchanged, keeping the map infrastructure
 * rather than a one-off. Standard falls back to the governed built-in default;
 * Satellite falls back to the governed built-in raster default; Terrain is
 * env-only. `VITE_MAP_STYLE_URL` is a back-compatible alias for Standard.
 */
type StyleDef = { id: string; label: string; description: string; styleUrl?: string; inlineStyle?: StyleSpecification };

function satelliteDef(): StyleDef {
  const override = env("VITE_MAP_STYLE_SATELLITE");
  if (override) return { id: "satellite", label: "Satellite", description: "Satellite imagery (configured provider).", styleUrl: override };
  return { id: "satellite", label: "Satellite", description: "Satellite imagery — Sentinel-2 cloudless (imagery-only; labels/boundaries limited).", inlineStyle: buildSatelliteRasterStyle() };
}

const STYLE_CATALOGUE: StyleDef[] = [
  { id: "standard", label: "Standard", description: "Engineering day map — boundaries, settlements, roads, water, land cover.", styleUrl: env("VITE_MAP_STYLE_STANDARD") ?? env("VITE_MAP_STYLE_URL") ?? DEFAULT_STANDARD_STYLE_URL },
  satelliteDef(),
  { id: "terrain", label: "Terrain", description: "Terrain / relief presentation (connected-only unless locally hosted).", styleUrl: env("VITE_MAP_STYLE_TERRAIN") },
];

/** Styles that have a source (a URL or a built-in inline style). Terrain is
 *  omitted unless configured; Standard and Satellite always resolve to a
 *  governed default. */
export const BASEMAP_STYLES: EngineeringMapStyle[] = STYLE_CATALOGUE
  .filter((s) => s.styleUrl != null || s.inlineStyle != null)
  .map((s) => ({ id: s.id, label: s.label, styleUrl: s.styleUrl, inlineStyle: s.inlineStyle, available: true, description: s.description }));

/** The style shown first: Standard when configured, else the first available. */
export const DEFAULT_STYLE_ID: string | null =
  BASEMAP_STYLES.find((s) => s.id === "standard")?.id ?? BASEMAP_STYLES[0]?.id ?? null;

export function styleById(id: string | null | undefined): EngineeringMapStyle | undefined {
  return BASEMAP_STYLES.find((s) => s.id === id);
}

/** Back-compatible export for any caller that still imports the single URL. */
export const MAP_STYLE_URL: string | undefined = styleById("standard")?.styleUrl;

/**
 * Neutral-mode geographic reference — the built-in fallback used when the
 * configured rich online basemap is unavailable. It renders a small, **locally
 * bundled, public-domain** geographic backdrop (land / sea / coastlines /
 * national borders) from Natural Earth, served app-relative — so it makes **no
 * external font, sprite, tile, or glyph requests** and works immediately after
 * clone + build, with no operator install, no Docker, no internet.
 *
 * It deliberately shows ONLY land/sea/coastline/borders — no roads, rivers,
 * forests, labels, landmarks, terrain, or imagery — because only that geometry
 * is packaged. Provenance/checksum: frontend/public/map-assets/neutral/manifest.json.
 * Malaysian State boundaries are intentionally absent until a governed source
 * passes the licensing gate (see docs/engineering/licensing-policy.md).
 */
export const NEUTRAL_GEOMETRY_URL = "/map-assets/neutral/southeast-asia.geojson";
export const NEUTRAL_STYLE_ID = "__neutral__";

/** Build the neutral geographic style from the bundled local GeoJSON. Colours
 *  keep a calm sea/land contrast so lifecycle-coloured markers stay prominent. */
export function buildNeutralStyle(geojsonUrl: string = NEUTRAL_GEOMETRY_URL): StyleSpecification {
  return {
    version: 8,
    name: "neutral-geographic",
    sources: {
      neutral: { type: "geojson", data: geojsonUrl, attribution: "Made with Natural Earth (public domain)" },
    },
    layers: [
      { id: "background", type: "background", paint: { "background-color": "#CBD9E6" } }, // sea
      { id: "neutral-land", type: "fill", source: "neutral", paint: { "fill-color": "#EEF1F4", "fill-outline-color": "#B7C3D2" } },
      { id: "neutral-border", type: "line", source: "neutral", paint: { "line-color": "#AFBED0", "line-width": 0.8 } },
    ],
  };
}

/** A ready neutral style instance (audited local-only). */
export const NEUTRAL_STYLE: StyleSpecification = buildNeutralStyle();

/**
 * Approximate Peninsular Malaysia extent [west, south, east, north] — the
 * default and reset viewport, with padding so coastal/border areas stay legible.
 * It is a display extent only and does NOT represent an engineering region or
 * operational boundary.
 */
export const PENINSULAR_MALAYSIA_BOUNDS: [number, number, number, number] = [99.3, 0.8, 104.9, 6.8];

/**
 * Audit a MapLibre style object for external (non-local) resource URLs —
 * absolute `http(s)://`, protocol-relative `//host`, or provider schemes like
 * `mapbox://`. Used by tests and by an operator to confirm a "local" style is
 * genuinely offline-capable (its top-level JSON being local is not sufficient:
 * glyphs, sprite, and tile/source URLs must resolve locally too). Returns the
 * offending URL strings (empty ⇒ no external dependency detected).
 */
export function auditStyleForExternalUrls(style: unknown): string[] {
  const found: string[] = [];
  // External ⇒ absolute (`https://…`, `mapbox://…`, any `scheme://…`) or
  // protocol-relative (`//host/…`). Local paths (`/map-assets/…`, `./x`,
  // `x/y`) and inline data are not external. A `pmtiles://` URL is unwrapped
  // first: `pmtiles:///map-assets/…` is local, `pmtiles://https://…` is not.
  const isExternal = (raw: string): boolean => {
    const value = raw.replace(/^pmtiles:\/\//i, "");
    return /^[a-z][a-z0-9+.-]*:\/\//i.test(value) || /^\/\//.test(value);
  };
  const visit = (node: unknown, key?: string): void => {
    // `attribution` legitimately carries display links (OSM/Protomaps credits);
    // it is rendered, never fetched as a map resource, so it is not audited.
    if (key === "attribution") return;
    if (typeof node === "string") {
      if (isExternal(node)) found.push(node);
      return;
    }
    if (Array.isArray(node)) {
      node.forEach((n) => visit(n));
      return;
    }
    if (node && typeof node === "object") {
      for (const [k, v] of Object.entries(node as Record<string, unknown>)) visit(v, k);
    }
  };
  visit(style);
  return Array.from(new Set(found));
}
