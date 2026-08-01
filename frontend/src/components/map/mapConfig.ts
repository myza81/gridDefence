import type { StyleSpecification } from "maplibre-gl";

/**
 * Engineering Map Framework — environment configuration & offline model.
 *
 * The basemap is configured through MapLibre **style URLs** (not raw tile
 * URLs), one per selectable style, so a deployment chooses its own map stack
 * without code changes. Two operating modes are supported by configuration
 * alone (see docs/architecture/engineering-map.md):
 *
 *  - Connected development mode — style URLs may point at externally hosted
 *    styles (`https://…`).
 *  - Offline / internal production mode — style URLs point at resources served
 *    entirely from the GridDefence deployment or an internal service
 *    (e.g. `/map-assets/styles/standard/style.json`).
 *
 * No public tile/style provider is hard-coded as a production service. A style
 * is "available" only when its URL is configured; unconfigured styles are
 * omitted from the selector rather than offered and then failing. When *no*
 * style is configured the map degrades to the accessible record list, and the
 * engineering data stays fully usable.
 */

export interface EngineeringMapStyle {
  /** Stable id used in the selector and in URLs/state. */
  id: string;
  /** Human label shown in the style selector. */
  label: string;
  /** MapLibre style URL — external (dev) or internal/local (production). */
  styleUrl: string;
  /** Present only when the style's URL is configured. */
  available: boolean;
  /** One-line description shown as a tooltip / caption. */
  description?: string;
}

/** Read a Vite env var, treating empty/whitespace as unset. */
function env(name: string): string | undefined {
  const raw = (import.meta.env as Record<string, string | undefined>)[name];
  const value = typeof raw === "string" ? raw.trim() : "";
  return value === "" ? undefined : value;
}

/**
 * Style catalogue. Adding a future style (Dark, High Contrast, Utility,
 * Engineering) is a one-line addition here plus an env var — the EngineeringMap
 * component and every consumer are unchanged, keeping the map infrastructure
 * rather than a one-off. `VITE_MAP_STYLE_URL` is honoured as a back-compatible
 * alias for the Standard style.
 */
const STYLE_CATALOGUE: { id: string; label: string; url: string | undefined; description: string }[] = [
  { id: "standard", label: "Standard", url: env("VITE_MAP_STYLE_STANDARD") ?? env("VITE_MAP_STYLE_URL"), description: "Engineering day map — boundaries, settlements, roads, water, land cover." },
  { id: "satellite", label: "Satellite", url: env("VITE_MAP_STYLE_SATELLITE"), description: "Satellite imagery with labels (connected-only unless locally hosted)." },
  { id: "terrain", label: "Terrain", url: env("VITE_MAP_STYLE_TERRAIN"), description: "Terrain / relief presentation (connected-only unless locally hosted)." },
];

/** Only the styles a deployment has actually configured — availability comes
 *  from configuration, never a hard-coded assumption. */
export const BASEMAP_STYLES: EngineeringMapStyle[] = STYLE_CATALOGUE
  .filter((s): s is typeof s & { url: string } => typeof s.url === "string")
  .map((s) => ({ id: s.id, label: s.label, styleUrl: s.url, available: true, description: s.description }));

/** The style shown first: Standard when configured, else the first available. */
export const DEFAULT_STYLE_ID: string | null =
  BASEMAP_STYLES.find((s) => s.id === "standard")?.id ?? BASEMAP_STYLES[0]?.id ?? null;

export function styleById(id: string | null | undefined): EngineeringMapStyle | undefined {
  return BASEMAP_STYLES.find((s) => s.id === id);
}

/** Back-compatible export for any caller that still imports the single URL. */
export const MAP_STYLE_URL: string | undefined = styleById("standard")?.styleUrl;

/**
 * Neutral, fully-offline fallback style — the last *map* stage before the map
 * is dropped entirely for the record list. It is an inline MapLibre style with
 * a single background layer and **no external URLs** (no sources, glyphs, or
 * sprites), so it renders substation markers on a plain canvas without a single
 * network request. It never fabricates geographic geometry: a governed
 * Peninsular Malaysia / state-boundary overlay is a future addition (see the
 * offline-overlay section of docs/architecture/engineering-map.md), not
 * invented here.
 */
export const NEUTRAL_FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  name: "neutral-offline-canvas",
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#E7ECF3" } }],
};

/** Marker to identify the neutral fallback so consumers can label the state. */
export const NEUTRAL_FALLBACK_STYLE_ID = "__neutral__";

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
  // `x/y`) and inline data are not external.
  const isExternal = (value: string): boolean => /^[a-z][a-z0-9+.-]*:\/\//i.test(value) || /^\/\//.test(value);
  const visit = (node: unknown): void => {
    if (typeof node === "string") {
      if (isExternal(node)) found.push(node);
      return;
    }
    if (Array.isArray(node)) {
      node.forEach(visit);
      return;
    }
    if (node && typeof node === "object") {
      Object.values(node as Record<string, unknown>).forEach(visit);
    }
  };
  visit(style);
  return Array.from(new Set(found));
}
