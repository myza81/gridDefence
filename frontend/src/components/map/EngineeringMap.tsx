import maplibregl from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import "maplibre-gl/dist/maplibre-gl.css";

import { tokens } from "../../theme/tokens";
import { MAP_STYLE_URL } from "./mapConfig";

/**
 * Engineering Map Framework — a generic, reusable MapLibre GL wrapper.
 *
 * It owns the map instance, the basemap (from a `VITE_MAP_STYLE_URL` style),
 * navigation + reset-to-extent controls, attribution, clustering, and graceful
 * basemap-failure handling. It knows nothing about substations: callers pass
 * one or more `EngineeringMapLayer`s (GeoJSON points + a category→colour map),
 * so future engineering layers (Transformers, Circuits, Relays, Sensitive
 * Customers, defence-scheme overlays, analytical layers) plug in without
 * changing this component. It draws NO lines/relationships — geographic
 * proximity is not electrical connectivity.
 *
 * The map is a progressive enhancement: it reports basemap availability via
 * `onBasemapStatus`, and the caller always keeps an accessible record list so
 * the map is never the only way to find or open a record.
 */
export interface EngineeringMapMarker {
  id: string;
  longitude: number;
  latitude: number;
  /** Category key used to colour the marker (e.g. a lifecycle code). */
  category: string;
  label: string;
}

export interface EngineeringMapLayer {
  id: string;
  markers: EngineeringMapMarker[];
  colorByCategory: Record<string, string>;
  fallbackColor: string;
}

interface EngineeringMapProps {
  layers: EngineeringMapLayer[];
  bounds: [number, number, number, number];
  selectedId?: string | null;
  onSelect?: (id: string | null) => void;
  onBasemapStatus?: (available: boolean) => void;
  /** Marker to fly to (e.g. a search hit). */
  focusId?: string | null;
  height?: string;
}

function toFeatureCollection(layer: EngineeringMapLayer): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: layer.markers.map((m) => ({
      type: "Feature",
      id: m.id,
      geometry: { type: "Point", coordinates: [m.longitude, m.latitude] },
      properties: { id: m.id, category: m.category, label: m.label },
    })),
  };
}

/** ["match", ["get","category"], k1, c1, …, fallback] for data-driven colour. */
function colorExpression(layer: EngineeringMapLayer): unknown {
  const entries = Object.entries(layer.colorByCategory);
  if (entries.length === 0) return layer.fallbackColor;
  return ["match", ["get", "category"], ...entries.flat(), layer.fallbackColor];
}

export function EngineeringMap({ layers, bounds, selectedId, onSelect, onBasemapStatus, focusId, height = "520px" }: EngineeringMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const loadedRef = useRef(false);
  const [basemapAvailable, setBasemapAvailable] = useState<boolean>(MAP_STYLE_URL != null);

  // --- Initialise the map once (graceful when WebGL / style is unavailable) ---
  useEffect(() => {
    if (MAP_STYLE_URL == null || containerRef.current == null) {
      setBasemapAvailable(false);
      onBasemapStatus?.(false);
      return;
    }
    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: containerRef.current,
        style: MAP_STYLE_URL,
        bounds,
        fitBoundsOptions: { padding: 40 },
        attributionControl: { compact: false },
      });
    } catch {
      setBasemapAvailable(false);
      onBasemapStatus?.(false);
      return;
    }
    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new ResetExtentControl(bounds), "top-right");

    map.on("error", (e) => {
      // A style/tile failure must not take the workspace down — degrade to the list.
      if (e?.error && /style|tile|source|sprite|glyph/i.test(String(e.error.message ?? ""))) {
        setBasemapAvailable(false);
        onBasemapStatus?.(false);
      }
    });

    map.on("load", () => {
      loadedRef.current = true;
      setBasemapAvailable(true);
      onBasemapStatus?.(true);
      for (const layer of layers) addLayer(map, layer, onSelect);
      applySelection(map, selectedId ?? null);
    });

    return () => {
      loadedRef.current = false;
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Keep layer data in sync ---
  useEffect(() => {
    const map = mapRef.current;
    if (map == null || !loadedRef.current) return;
    for (const layer of layers) {
      const source = map.getSource(sourceId(layer.id)) as maplibregl.GeoJSONSource | undefined;
      if (source) source.setData(toFeatureCollection(layer));
      else addLayer(map, layer, onSelect);
    }
  }, [layers, onSelect]);

  // --- Selection highlight ---
  useEffect(() => {
    const map = mapRef.current;
    if (map == null || !loadedRef.current) return;
    applySelection(map, selectedId ?? null);
  }, [selectedId]);

  // --- Fly to a focused marker (search hit) ---
  useEffect(() => {
    const map = mapRef.current;
    if (map == null || !loadedRef.current || focusId == null) return;
    const marker = layers.flatMap((l) => l.markers).find((m) => m.id === focusId);
    if (marker) map.flyTo({ center: [marker.longitude, marker.latitude], zoom: 11, essential: true });
  }, [focusId, layers]);

  if (!basemapAvailable) {
    return (
      <div
        role="img"
        aria-label="Basemap unavailable"
        style={{
          height,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: tokens.space[2],
          textAlign: "center",
          padding: tokens.space[6],
          background: tokens.color.surfaceSubtle,
          border: `1px dashed ${tokens.color.borderStrong}`,
          borderRadius: tokens.radius.lg,
          fontFamily: tokens.typography.fontFamily,
        }}
      >
        <p style={{ margin: 0, fontWeight: tokens.typography.weight.semibold, color: tokens.color.textPrimary }}>Basemap unavailable</p>
        <p style={{ margin: 0, maxWidth: "44ch", fontSize: tokens.typography.size.small, color: tokens.color.textSecondary, lineHeight: tokens.typography.lineHeight.normal }}>
          {MAP_STYLE_URL == null
            ? "No map style is configured (VITE_MAP_STYLE_URL). The substation list below remains fully usable."
            : "The map style could not be loaded. The substation list below remains fully usable."}
        </p>
      </div>
    );
  }

  return <div ref={containerRef} data-testid="engineering-map" style={{ height, borderRadius: tokens.radius.lg, overflow: "hidden" }} />;
}

const sourceId = (layerId: string) => `layer-${layerId}`;

function addLayer(map: maplibregl.Map, layer: EngineeringMapLayer, onSelect?: (id: string | null) => void) {
  const sid = sourceId(layer.id);
  if (map.getSource(sid)) return;
  map.addSource(sid, { type: "geojson", data: toFeatureCollection(layer), cluster: true, clusterMaxZoom: 11, clusterRadius: 44 });

  map.addLayer({ id: `${sid}-clusters`, type: "circle", source: sid, filter: ["has", "point_count"], paint: { "circle-color": "#2540D8", "circle-opacity": 0.85, "circle-radius": ["step", ["get", "point_count"], 16, 10, 22, 50, 30] } });
  map.addLayer({ id: `${sid}-cluster-count`, type: "symbol", source: sid, filter: ["has", "point_count"], layout: { "text-field": ["get", "point_count_abbreviated"], "text-size": 12 }, paint: { "text-color": "#FFFFFF" } });
  map.addLayer({ id: `${sid}-points`, type: "circle", source: sid, filter: ["!", ["has", "point_count"]], paint: { "circle-color": colorExpression(layer) as maplibregl.ExpressionSpecification, "circle-radius": 7, "circle-stroke-width": 1.5, "circle-stroke-color": "#FFFFFF" } });
  map.addLayer({ id: `${sid}-selected`, type: "circle", source: sid, filter: ["==", ["get", "id"], "__none__"], paint: { "circle-color": "rgba(0,0,0,0)", "circle-radius": 12, "circle-stroke-width": 3, "circle-stroke-color": "#0F2340" } });

  map.on("click", `${sid}-points`, (e) => {
    const id = e.features?.[0]?.properties?.id;
    if (typeof id === "string") onSelect?.(id);
  });
  map.on("click", `${sid}-clusters`, (e) => {
    const feature = e.features?.[0];
    const clusterId = feature?.properties?.cluster_id;
    const src = map.getSource(sid) as maplibregl.GeoJSONSource;
    if (clusterId != null && src.getClusterExpansionZoom) {
      void src.getClusterExpansionZoom(clusterId).then((zoom) => {
        const geom = feature!.geometry as GeoJSON.Point;
        map.easeTo({ center: geom.coordinates as [number, number], zoom });
      });
    }
  });
  for (const cursorLayer of [`${sid}-points`, `${sid}-clusters`]) {
    map.on("mouseenter", cursorLayer, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", cursorLayer, () => (map.getCanvas().style.cursor = ""));
  }
}

function applySelection(map: maplibregl.Map, selectedId: string | null) {
  map.getStyle().layers.forEach((l) => {
    if (l.id.endsWith("-selected")) {
      map.setFilter(l.id, ["==", ["get", "id"], selectedId ?? "__none__"]);
    }
  });
}

/** Custom control that returns the map to its configured extent. */
class ResetExtentControl implements maplibregl.IControl {
  private container!: HTMLDivElement;
  constructor(private readonly bounds: [number, number, number, number]) {}
  onAdd(map: maplibregl.Map): HTMLElement {
    this.container = document.createElement("div");
    this.container.className = "maplibregl-ctrl maplibregl-ctrl-group";
    const button = document.createElement("button");
    button.type = "button";
    button.title = "Reset to Peninsular Malaysia";
    button.setAttribute("aria-label", "Reset to Peninsular Malaysia");
    button.textContent = "⤢";
    button.onclick = () => map.fitBounds(this.bounds, { padding: 40 });
    this.container.appendChild(button);
    return this.container;
  }
  onRemove(): void {
    this.container.parentNode?.removeChild(this.container);
  }
}
