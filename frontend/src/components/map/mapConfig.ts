/**
 * Engineering Map Framework — environment configuration.
 *
 * The basemap is configured through a MapLibre **style URL** (not a raw tile
 * URL), so a deployment can point at a public dev style during development and
 * an internally-hosted production map service later without code changes
 * (`VITE_MAP_STYLE_URL`). No public tile/style provider is hard-coded as a
 * production service: when the variable is unset, the map renders a
 * basemap-unavailable state while the engineering data (markers + accessible
 * record list) stays fully available.
 */
export const MAP_STYLE_URL: string | undefined = import.meta.env.VITE_MAP_STYLE_URL;

/** Approximate Peninsular Malaysia extent [west, south, east, north] — the
 *  default and reset viewport. It is a display extent only and does NOT
 *  represent an engineering region or operational boundary. */
export const PENINSULAR_MALAYSIA_BOUNDS: [number, number, number, number] = [99.3, 0.8, 104.9, 6.8];
