import maplibregl from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import "maplibre-gl/dist/maplibre-gl.css";

import { tokens } from "../../theme/tokens";
import { BASEMAP_STYLES, DEFAULT_STYLE_ID, buildNeutralStyle, styleById } from "./mapConfig";
import type { EngineeringMapStyle } from "./mapConfig";
import { createClusterCountController } from "./clusterCountMarkers";
import type { ClusterCountController } from "./clusterCountMarkers";
import { registerPmtilesProtocol } from "./pmtilesProtocol";

/**
 * Engineering Map Framework — a generic, reusable MapLibre GL wrapper.
 *
 * **Dual-mode.** It provides the richest map that is actually available:
 *  - **Rich mode** — when a configured online style and its resources load, it
 *    shows that provider's detailed basemap (roads, water, land cover, labels,
 *    boundaries, and satellite/terrain where configured), with attribution.
 *  - **Neutral mode** — when no rich style is configured or one fails/times out,
 *    it shows a small, locally bundled, public-domain geographic reference
 *    (land / sea / coastlines / national borders from Natural Earth) that makes
 *    **no external requests**. It never silently switches to another public
 *    provider and never claims a layer it does not actually render.
 *
 * It knows nothing about substations: callers pass `EngineeringMapLayer`s
 * (GeoJSON points + a category→colour map). It draws NO relationship lines —
 * geographic proximity is not electrical connectivity. Mode is reported via
 * `onModeChange`; the caller renders the honest status + a user-triggered
 * "Retry rich map" by bumping `retryToken`. A style load is time-bounded (no
 * infinite spinner / retry loop), and the accessible record list is always the
 * non-map path to every record.
 */
export type MapMode = "loading" | "rich" | "neutral";

export interface EngineeringMapMarker {
  id: string;
  longitude: number;
  latitude: number;
  /** Category key used to colour the marker (e.g. a lifecycle code). */
  category: string;
  label: string;
  /** Optional pre-escaped HTML for the on-map popup (caller-owned content). */
  popupHtml?: string;
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
  /** Reports the active map mode so the caller can show honest status/retry. */
  onModeChange?: (mode: MapMode) => void;
  /** Changing this (e.g. a "Retry rich map" click) attempts the rich style once. */
  retryToken?: number;
  /** Invoked when the popup's "Open" action is used (SPA navigation). */
  onOpen?: (id: string) => void;
  /** Marker to fly to (e.g. a search hit). */
  focusId?: string | null;
  /** Selectable rich basemap styles; defaults to the configured catalogue. */
  styles?: EngineeringMapStyle[];
  /** Bound on a single style load before it is treated as failed (ms). */
  loadTimeoutMs?: number;
  height?: string;
}

function toFeatureCollection(layer: EngineeringMapLayer): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: layer.markers.map((m) => ({
      type: "Feature",
      id: m.id,
      geometry: { type: "Point", coordinates: [m.longitude, m.latitude] },
      properties: { id: m.id, category: m.category, label: m.label, popupHtml: m.popupHtml ?? "" },
    })),
  };
}

/** ["match", ["get","category"], k1, c1, …, fallback] for data-driven colour. */
function colorExpression(layer: EngineeringMapLayer): unknown {
  const entries = Object.entries(layer.colorByCategory);
  if (entries.length === 0) return layer.fallbackColor;
  return ["match", ["get", "category"], ...entries.flat(), layer.fallbackColor];
}

export function EngineeringMap({
  layers,
  bounds,
  selectedId,
  onSelect,
  onModeChange,
  retryToken = 0,
  onOpen,
  focusId,
  styles = BASEMAP_STYLES,
  loadTimeoutMs = 8000,
  height = "520px",
}: EngineeringMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const popupRef = useRef<maplibregl.Popup | null>(null);
  const styleReadyRef = useRef(false);
  const pendingModeRef = useRef<Exclude<MapMode, "loading">>("neutral");
  const loadTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Cluster-count numbers are DOM markers (glyph-independent), so they render in
  // both rich and neutral modes without any font/glyph request.
  const clusterCountsRef = useRef<ClusterCountController | null>(null);

  // Refs mirror the latest props so the persistent map handlers (bound once)
  // always read current values without re-binding.
  const layersRef = useRef(layers);
  const selectedRef = useRef(selectedId ?? null);
  const onSelectRef = useRef(onSelect);
  const onOpenRef = useRef(onOpen);
  const onModeChangeRef = useRef(onModeChange);
  layersRef.current = layers;
  selectedRef.current = selectedId ?? null;
  onSelectRef.current = onSelect;
  onOpenRef.current = onOpen;
  onModeChangeRef.current = onModeChange;

  const available = styles.filter((s) => s.available);
  const initialRichId = available.some((s) => s.id === DEFAULT_STYLE_ID) ? (DEFAULT_STYLE_ID as string) : available[0]?.id ?? null;
  const [activeStyleId, setActiveStyleId] = useState<string | null>(initialRichId);
  const [mode, setModeState] = useState<MapMode>("loading");
  const [mapUsable, setMapUsable] = useState(true);

  function announce(next: MapMode) {
    setModeState(next);
    onModeChangeRef.current?.(next);
  }

  // --- Initialise the map once. ------------------------------------------------
  useEffect(() => {
    if (containerRef.current == null) return;
    registerPmtilesProtocol(); // idempotent — a rich style may be pmtiles://
    // Start in the richest available: a configured rich style, else neutral.
    pendingModeRef.current = initialRichId != null ? "rich" : "neutral";
    const initialStyle = initialRichId != null ? styleById(initialRichId)!.styleUrl : buildNeutralStyle();

    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: containerRef.current,
        style: initialStyle,
        bounds,
        fitBoundsOptions: { padding: 40 },
        attributionControl: { compact: false },
        maxTileCacheSize: 256,
        refreshExpiredTiles: false,
      });
    } catch {
      // Hard failure (e.g. no WebGL). The caller always keeps the record list.
      setMapUsable(false);
      announce("neutral");
      return;
    }
    mapRef.current = map;
    announce("loading");

    // Cluster-count DOM markers, tracking the current layer set across reloads.
    clusterCountsRef.current = createClusterCountController(map, () => layersRef.current.map((l) => sourceId(l.id)));
    map.on("render", () => clusterCountsRef.current?.update());

    map.addControl(new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }), "top-right");
    map.addControl(new ResetExtentControl(bounds), "top-right");
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-left");

    // `style.load` fires on the initial load AND after every setStyle — the one
    // place to (re)install our sources/layers and re-apply selection.
    map.on("style.load", () => {
      clearLoadTimer();
      styleReadyRef.current = true;
      installLayers(map, layersRef.current);
      applySelection(map, selectedRef.current);
      openPopupFor(selectedRef.current);
      clusterCountsRef.current?.update();
      announce(pendingModeRef.current);
    });

    map.on("error", (e) => {
      const message = String(e?.error?.message ?? "");
      // Only a style/glyph/sprite/source *load* failure of a rich style falls
      // back; a single missing tile must not tear the workspace down, and a
      // neutral (local) failure has nowhere safe left to go.
      if (/style|sprite|glyph|source/i.test(message) && !styleReadyRef.current && pendingModeRef.current === "rich") {
        goNeutral(map);
      }
    });

    startLoadTimer(map);

    return () => {
      clearLoadTimer();
      popupRef.current?.remove();
      popupRef.current = null;
      clusterCountsRef.current?.destroy();
      clusterCountsRef.current = null;
      styleReadyRef.current = false;
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Switch rich style from the selector. ------------------------------------
  const firstStyleEffect = useRef(true);
  useEffect(() => {
    if (firstStyleEffect.current) {
      firstStyleEffect.current = false;
      return; // constructor already loaded the initial style
    }
    const map = mapRef.current;
    if (map == null || activeStyleId == null) return;
    loadRich(map, activeStyleId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeStyleId]);

  // --- Retry rich map (user-triggered; one attempt per token change). ----------
  const firstRetryEffect = useRef(true);
  useEffect(() => {
    if (firstRetryEffect.current) {
      firstRetryEffect.current = false;
      return;
    }
    const map = mapRef.current;
    const target = activeStyleId ?? initialRichId;
    if (map == null || target == null) return;
    loadRich(map, target);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [retryToken]);

  // --- Keep layer data in sync. ------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (map == null || !styleReadyRef.current) return;
    for (const layer of layers) {
      const source = map.getSource(sourceId(layer.id)) as maplibregl.GeoJSONSource | undefined;
      if (source) source.setData(toFeatureCollection(layer));
      else installOneLayer(map, layer);
    }
    clusterCountsRef.current?.update();
    if (selectedRef.current) openPopupFor(selectedRef.current);
  }, [layers]);

  // --- Selection highlight + popup. --------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (map == null || !styleReadyRef.current) return;
    applySelection(map, selectedId ?? null);
    openPopupFor(selectedId ?? null);
  }, [selectedId]);

  // --- Subtle pulse on the selected marker. ------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (map == null || selectedId == null) return;
    let raf = 0;
    const start = performance.now();
    const tick = (t: number) => {
      if (!styleReadyRef.current) {
        raf = requestAnimationFrame(tick);
        return;
      }
      const phase = (Math.sin((t - start) / 480) + 1) / 2; // 0..1
      map.getStyle().layers.forEach((l) => {
        if (l.id.endsWith("-selected")) {
          map.setPaintProperty(l.id, "circle-radius", 11 + phase * 5);
          map.setPaintProperty(l.id, "circle-stroke-opacity", 0.9 - phase * 0.45);
        }
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [selectedId]);

  // --- Fly to a focused marker (search hit). -----------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (map == null || !styleReadyRef.current || focusId == null) return;
    const marker = layers.flatMap((l) => l.markers).find((m) => m.id === focusId);
    if (marker) map.flyTo({ center: [marker.longitude, marker.latitude], zoom: 12, essential: true });
  }, [focusId, layers]);

  // --- Transitions & helpers (closures over refs; bound once). -----------------
  function startLoadTimer(map: maplibregl.Map) {
    clearLoadTimer();
    loadTimerRef.current = setTimeout(() => {
      // Bounded: a stalled rich load falls back once; no infinite spinner/retry.
      if (!styleReadyRef.current && pendingModeRef.current === "rich") goNeutral(map);
    }, loadTimeoutMs);
  }
  function clearLoadTimer() {
    if (loadTimerRef.current != null) {
      clearTimeout(loadTimerRef.current);
      loadTimerRef.current = null;
    }
  }

  function loadRich(map: maplibregl.Map, styleId: string) {
    const style = styleById(styleId);
    if (style == null) return;
    styleReadyRef.current = false;
    pendingModeRef.current = "rich";
    clusterCountsRef.current?.clear(); // sources are rebuilt on style.load
    announce("loading");
    startLoadTimer(map);
    map.setStyle(style.styleUrl);
  }

  function goNeutral(map: maplibregl.Map) {
    clearLoadTimer();
    styleReadyRef.current = false;
    pendingModeRef.current = "neutral";
    clusterCountsRef.current?.clear(); // sources are rebuilt on style.load
    announce("neutral");
    startLoadTimer(map);
    map.setStyle(buildNeutralStyle());
  }

  function installLayers(map: maplibregl.Map, ls: EngineeringMapLayer[]) {
    for (const layer of ls) installOneLayer(map, layer);
  }

  function openPopupFor(id: string | null) {
    const map = mapRef.current;
    if (map == null) return;
    popupRef.current?.remove();
    popupRef.current = null;
    if (id == null) return;
    const marker = layersRef.current.flatMap((l) => l.markers).find((m) => m.id === id);
    if (!marker || !marker.popupHtml) return;
    const popup = new maplibregl.Popup({ closeButton: true, closeOnClick: false, maxWidth: "260px", offset: 12 })
      .setLngLat([marker.longitude, marker.latitude])
      .setHTML(marker.popupHtml)
      .addTo(map);
    const root = popup.getElement();
    root.querySelector("[data-map-open]")?.addEventListener("click", (ev) => {
      ev.preventDefault();
      onOpenRef.current?.(id);
    });
    popup.on("close", () => {
      if (selectedRef.current === id) onSelectRef.current?.(null);
    });
    popupRef.current = popup;
  }

  function installOneLayer(map: maplibregl.Map, layer: EngineeringMapLayer) {
    const sid = sourceId(layer.id);
    if (map.getSource(sid)) return;
    // Clustering is identical in both modes. The cluster *circle* is a MapLibre
    // layer; the numeric *count* is a DOM marker (see clusterCountMarkers.ts) so
    // it renders without any glyph/font request — visible in rich AND neutral.
    map.addSource(sid, { type: "geojson", data: toFeatureCollection(layer), cluster: true, clusterMaxZoom: 11, clusterRadius: 44 });

    map.addLayer({ id: `${sid}-clusters`, type: "circle", source: sid, filter: ["has", "point_count"], paint: { "circle-color": "#2540D8", "circle-opacity": 0.85, "circle-radius": ["step", ["get", "point_count"], 16, 10, 22, 50, 30] } });
    map.addLayer({ id: `${sid}-points`, type: "circle", source: sid, filter: ["!", ["has", "point_count"]], paint: { "circle-color": colorExpression(layer) as maplibregl.ExpressionSpecification, "circle-radius": 7, "circle-stroke-width": 1.5, "circle-stroke-color": "#FFFFFF" } });
    map.addLayer({ id: `${sid}-selected`, type: "circle", source: sid, filter: ["==", ["get", "id"], "__none__"], paint: { "circle-color": "rgba(0,0,0,0)", "circle-radius": 12, "circle-stroke-width": 3, "circle-stroke-color": "#0F2340" } });

    map.on("click", `${sid}-points`, (e) => {
      const id = e.features?.[0]?.properties?.id;
      if (typeof id === "string") onSelectRef.current?.(id);
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

  if (!mapUsable) {
    return (
      <div
        role="img"
        aria-label="Map unavailable"
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
        <p style={{ margin: 0, fontWeight: tokens.typography.weight.semibold, color: tokens.color.textPrimary }}>Map could not be initialised</p>
        <p style={{ margin: 0, maxWidth: "44ch", fontSize: tokens.typography.size.small, color: tokens.color.textSecondary, lineHeight: tokens.typography.lineHeight.normal }}>
          This browser could not start the map view. Substation Registry data remains available — use the record list or the Table view.
        </p>
      </div>
    );
  }

  return (
    <div style={{ position: "relative", height, borderRadius: tokens.radius.lg, overflow: "hidden" }}>
      <div ref={containerRef} data-testid="engineering-map" style={{ position: "absolute", inset: 0 }} />
      {/* Rich-style selector — only meaningful while rich styles are active. */}
      {mode === "rich" && available.length > 1 && (
        <StyleSelector
          styles={available}
          activeId={activeStyleId}
          onChange={(id) => {
            if (id !== activeStyleId) setActiveStyleId(id);
          }}
        />
      )}
    </div>
  );
}

function StyleSelector({ styles, activeId, onChange }: { styles: EngineeringMapStyle[]; activeId: string | null; onChange: (id: string) => void }) {
  return (
    <div
      role="group"
      aria-label="Basemap style"
      style={{
        position: "absolute",
        top: tokens.space[2],
        left: tokens.space[2],
        display: "inline-flex",
        gap: "2px",
        padding: "3px",
        background: "rgba(255,255,255,0.94)",
        backdropFilter: "blur(6px)",
        border: `1px solid ${tokens.color.borderDefault}`,
        borderRadius: tokens.radius.md,
        boxShadow: tokens.shadow.hairline,
        fontFamily: tokens.typography.fontFamily,
      }}
    >
      {styles.map((s) => {
        const active = s.id === activeId;
        return (
          <button
            key={s.id}
            type="button"
            onClick={() => onChange(s.id)}
            aria-pressed={active}
            title={s.description}
            style={{
              border: "none",
              cursor: "pointer",
              padding: "5px 10px",
              borderRadius: tokens.radius.sm,
              fontSize: "12px",
              fontWeight: active ? tokens.typography.weight.semibold : tokens.typography.weight.medium,
              color: active ? tokens.color.actionPrimaryText : tokens.color.textSecondary,
              background: active ? tokens.color.actionPrimary : "transparent",
            }}
          >
            {s.label}
          </button>
        );
      })}
    </div>
  );
}

const sourceId = (layerId: string) => `layer-${layerId}`;

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
