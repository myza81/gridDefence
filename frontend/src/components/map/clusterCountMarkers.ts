import maplibregl from "maplibre-gl";

import { tokens } from "../../theme/tokens";

/**
 * Cluster-count labels rendered as local DOM markers (not a MapLibre symbol/
 * text layer). MapLibre text needs glyph resources; the neutral offline style
 * ships none, which previously left neutral-mode clusters without a visible
 * count. DOM markers render the count with the browser's own fonts, so the
 * number is visible in **both** rich and neutral modes with **no glyph/font
 * request** (external or bundled) and no dependency on the basemap provider's
 * fonts. The MapLibre cluster *circle* layer (and its click-to-expand) is
 * unchanged; these markers only overlay the centred number, and are
 * pointer-transparent so clicks still hit the circle layer.
 */
export interface ClusterPoint {
  /** Stable key: `${sourceId}:${cluster_id}`. */
  key: string;
  /** The count text — `point_count_abbreviated` when present, else `point_count`. */
  label: string;
  lng: number;
  lat: number;
}

/** Count text from a cluster feature's properties (abbreviated form preferred). */
export function clusterCountLabel(props: Record<string, unknown>): string {
  const value = props.point_count_abbreviated ?? props.point_count;
  return value == null ? "" : String(value);
}

/** Pure: cluster features → deduped points (multiple tiles can repeat a cluster). */
export function toClusterPoints(sourceId: string, features: GeoJSON.Feature[]): ClusterPoint[] {
  const out: ClusterPoint[] = [];
  const seen = new Set<string>();
  for (const feature of features) {
    const props = (feature.properties ?? {}) as Record<string, unknown>;
    if (props.cluster_id == null) continue;
    const key = `${sourceId}:${props.cluster_id}`;
    if (seen.has(key)) continue;
    seen.add(key);
    const geometry = feature.geometry as GeoJSON.Point;
    const [lng, lat] = geometry.coordinates as [number, number];
    out.push({ key, label: clusterCountLabel(props), lng, lat });
  }
  return out;
}

/** The centred, high-contrast, pointer-transparent count element. Decorative
 *  (aria-hidden): the accessible record list is the non-visual equivalent. */
export function createClusterCountElement(label: string): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "gd-cluster-count";
  el.textContent = label;
  el.setAttribute("aria-hidden", "true");
  el.style.color = "#FFFFFF";
  el.style.fontFamily = tokens.typography.fontFamily;
  el.style.fontSize = "12px";
  el.style.fontWeight = "700";
  el.style.lineHeight = "1";
  el.style.textAlign = "center";
  el.style.fontVariantNumeric = "tabular-nums";
  el.style.pointerEvents = "none";
  el.style.userSelect = "none";
  el.style.whiteSpace = "nowrap";
  return el;
}

export interface ClusterCountController {
  /** Reconcile markers with the clusters currently rendered on the map. */
  update(): void;
  /** Remove all markers (e.g. before a style change rebuilds the sources). */
  clear(): void;
  /** Remove all markers and stop. */
  destroy(): void;
}

/**
 * Manages a pool of cluster-count markers for the given (dynamic) source ids.
 * `getSourceIds` is a getter so the controller always tracks the current layer
 * set across style reloads. Reconciliation is keyed by cluster id, so markers
 * are reused (no per-frame churn) as the map pans/zooms.
 */
export function createClusterCountController(map: maplibregl.Map, getSourceIds: () => string[]): ClusterCountController {
  let onScreen: Record<string, maplibregl.Marker> = {};

  function update(): void {
    const next: Record<string, maplibregl.Marker> = {};
    for (const sourceId of getSourceIds()) {
      if (map.getSource(sourceId) == null) continue;
      let loaded = false;
      try {
        loaded = map.isSourceLoaded(sourceId);
      } catch {
        loaded = false;
      }
      if (!loaded) continue;
      let features: GeoJSON.Feature[] = [];
      try {
        features = map.querySourceFeatures(sourceId, { filter: ["has", "point_count"] }) as unknown as GeoJSON.Feature[];
      } catch {
        continue;
      }
      for (const point of toClusterPoints(sourceId, features)) {
        const existing = onScreen[point.key];
        if (existing) {
          const el = existing.getElement();
          if (el.textContent !== point.label) el.textContent = point.label;
          existing.setLngLat([point.lng, point.lat]);
          next[point.key] = existing;
        } else {
          next[point.key] = new maplibregl.Marker({ element: createClusterCountElement(point.label), anchor: "center" })
            .setLngLat([point.lng, point.lat])
            .addTo(map);
        }
      }
    }
    for (const key of Object.keys(onScreen)) {
      if (next[key] == null) onScreen[key].remove();
    }
    onScreen = next;
  }

  function clear(): void {
    for (const key of Object.keys(onScreen)) onScreen[key].remove();
    onScreen = {};
  }

  return { update, clear, destroy: clear };
}
