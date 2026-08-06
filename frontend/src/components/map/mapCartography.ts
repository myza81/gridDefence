import type { StyleSpecification } from "maplibre-gl";

/**
 * Engineering cartography tuning for the Standard (OpenMapTiles/Liberty-schema)
 * basemap.
 *
 * What we CAN tune: a few **style-gated label** layers whose underlying data is
 * present earlier than the default zoom threshold — so engineers recognise the
 * area (road names, river names, town/village names) a little sooner. We only
 * ever LOWER a threshold, and only for layer ids that exist (so it is a no-op on
 * the neutral style or any non-OpenMapTiles provider).
 *
 * What we CANNOT tune (and deliberately do not fake): the appearance of minor
 * roads, waterways, buildings and POIs at low/mid zoom is governed by the vector
 * tiles' **data generalization** (those features are simply not encoded in
 * low-zoom tiles), not by style decluttering. No `setLayerZoomRange` can reveal
 * data that is not in the tile — that is a provider/schema property, addressed
 * by opening the map at an engineering zoom (fit-to-data), not by style edits.
 */
export interface LayerZoomOverride {
  id: string;
  minzoom: number;
  maxzoom: number;
}

/** Curated label thresholds to lower (engineering area-recognition). Values are
 *  the target minzoom; applied only when strictly lower than the style's own. */
export const STANDARD_LABEL_TUNING: { id: string; minzoom: number }[] = [
  { id: "highway-name-major", minzoom: 11 }, // major road names earlier (default ~12.2)
  { id: "highway-name-minor", minzoom: 14 }, // minor road names earlier (default ~15)
  { id: "waterway_line_label", minzoom: 9 }, // river names earlier (default ~10)
  { id: "label_village", minzoom: 8 }, // village names earlier (default ~9)
];

/**
 * Compute the zoom-range overrides to apply to a loaded style. Returns only the
 * entries whose layer exists and whose current threshold is higher than the
 * target (i.e. an actual lowering). Pure — the caller applies via
 * `map.setLayerZoomRange`.
 */
export function computeStandardTuning(style: Pick<StyleSpecification, "layers"> | undefined): LayerZoomOverride[] {
  const out: LayerZoomOverride[] = [];
  const layers = style?.layers ?? [];
  for (const layer of layers) {
    const tuning = STANDARD_LABEL_TUNING.find((t) => t.id === layer.id);
    if (tuning == null) continue;
    const current = (layer as { minzoom?: number }).minzoom;
    if (current == null || tuning.minzoom < current) {
      out.push({ id: layer.id, minzoom: tuning.minzoom, maxzoom: (layer as { maxzoom?: number }).maxzoom ?? 24 });
    }
  }
  return out;
}
