import maplibregl from "maplibre-gl";
import type { StyleSpecification } from "maplibre-gl";
import { useEffect, useRef, useState } from "react";
import "maplibre-gl/dist/maplibre-gl.css";

import { tokens } from "../../theme/tokens";
import {
  BASEMAP_STYLES,
  DEFAULT_STYLE_ID,
  NEUTRAL_FALLBACK_STYLE,
  NEUTRAL_FALLBACK_STYLE_ID,
  styleById,
} from "./mapConfig";
import type { EngineeringMapStyle } from "./mapConfig";

/**
 * Engineering Map Framework — a generic, reusable MapLibre GL wrapper.
 *
 * It owns the map instance, the basemap (selectable from configured styles),
 * navigation + scale + reset-to-extent + style-selector controls, clustering,
 * marker selection with a subtle highlight + popup, and **offline-first**
 * failure handling. It knows nothing about substations: callers pass one or
 * more `EngineeringMapLayer`s (GeoJSON points + a category→colour map), so
 * future engineering layers plug in without changing this component. It draws
 * NO lines/relationships — geographic proximity is not electrical connectivity.
 *
 * Offline behaviour (see docs/architecture/engineering-map.md):
 *  - Availability comes from configuration; the selector only offers configured
 *    styles.
 *  - A style load is time-bounded; there is no infinite retry. On failure the
 *    map walks a deliberate fallback: selected → local Standard → neutral local
 *    canvas → accessible record list. It never silently switches to a public
 *    provider.
 *  - Style, scale, selection, fly-to and search all work with local resources;
 *    the map is a progressive enhancement over the always-present record list.
 */
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
  /** false ⇒ no map canvas at all (WebGL/style init failed) — caller shows the list only. */
  onBasemapStatus?: (available: boolean) => void;
  /** Human notice when the map is degraded (e.g. running on the neutral canvas), or null. */
  onBasemapNotice?: (notice: string | null) => void;
  /** Invoked when the popup's "Open" action is used (SPA navigation). */
  onOpen?: (id: string) => void;
  /** Marker to fly to (e.g. a search hit). */
  focusId?: string | null;
  /** Selectable basemap styles; defaults to the configured catalogue. */
  styles?: EngineeringMapStyle[];
  /** Bound on a single style load before it is treated as failed (ms). */
  loadTimeoutMs?: number;
  height?: string;
}

type Stage = { kind: "configured"; style: EngineeringMapStyle } | { kind: "neutral" };

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
  onBasemapStatus,
  onBasemapNotice,
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
  const clusteredRef = useRef(true);
  const loadTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptedRef = useRef<Set<string>>(new Set());

  // Refs mirror the latest props so the persistent map event handlers (bound
  // once) always read current values without re-binding.
  const layersRef = useRef(layers);
  const selectedRef = useRef(selectedId ?? null);
  const onSelectRef = useRef(onSelect);
  const onOpenRef = useRef(onOpen);
  layersRef.current = layers;
  selectedRef.current = selectedId ?? null;
  onSelectRef.current = onSelect;
  onOpenRef.current = onOpen;

  const available = styles.filter((s) => s.available);
  const initialId = available.some((s) => s.id === DEFAULT_STYLE_ID) ? (DEFAULT_STYLE_ID as string) : available[0]?.id ?? null;
  const [activeStyleId, setActiveStyleId] = useState<string | null>(initialId);
  const [mapUsable, setMapUsable] = useState<boolean>(initialId != null);

  // --- Initialise the map once. ------------------------------------------------
  useEffect(() => {
    if (initialId == null || containerRef.current == null) {
      setMapUsable(false);
      onBasemapStatus?.(false);
      return;
    }
    let map: maplibregl.Map;
    try {
      map = new maplibregl.Map({
        container: containerRef.current,
        style: styleById(initialId)!.styleUrl,
        bounds,
        fitBoundsOptions: { padding: 40 },
        attributionControl: { compact: false },
        // Do not hammer unreachable providers: a failed tile is not retried
        // indefinitely, and the fallback machinery handles style-level failure.
        maxTileCacheSize: 256,
        refreshExpiredTiles: false,
      });
    } catch {
      setMapUsable(false);
      onBasemapStatus?.(false);
      return;
    }
    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl({ showCompass: true, visualizePitch: true }), "top-right");
    map.addControl(new ResetExtentControl(bounds), "top-right");
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 120, unit: "metric" }), "bottom-left");

    // `style.load` fires on the initial load AND after every setStyle — the one
    // place to (re)install our sources/layers and re-apply selection.
    map.on("style.load", () => {
      clearLoadTimer();
      styleReadyRef.current = true;
      setMapUsable(true);
      onBasemapStatus?.(true);
      installLayers(map, layersRef.current, clusteredRef.current);
      applySelection(map, selectedRef.current);
      openPopupFor(selectedRef.current);
    });

    map.on("error", (e) => {
      const message = String(e?.error?.message ?? "");
      // Only a style/glyph/sprite/source *load* failure triggers fallback; a
      // single missing tile must not tear the workspace down.
      if (/style|sprite|glyph|source/i.test(message) && !styleReadyRef.current) {
        failCurrentStyle();
      }
    });

    startLoadTimer();

    return () => {
      clearLoadTimer();
      popupRef.current?.remove();
      popupRef.current = null;
      styleReadyRef.current = false;
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // --- Load a style when the active selection changes. -------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (map == null || activeStyleId == null) return;
    const style = styleById(activeStyleId);
    if (style == null) return;
    // Skip the very first render: the constructor already loaded initialId.
    if (attemptedRef.current.size === 0 && activeStyleId === initialId) {
      attemptedRef.current.add(activeStyleId);
      return;
    }
    loadStage(map, { kind: "configured", style });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeStyleId]);

  // --- Keep layer data in sync. ------------------------------------------------
  useEffect(() => {
    const map = mapRef.current;
    if (map == null || !styleReadyRef.current) return;
    for (const layer of layers) {
      const source = map.getSource(sourceId(layer.id)) as maplibregl.GeoJSONSource | undefined;
      if (source) source.setData(toFeatureCollection(layer));
      else installOneLayer(map, layer, clusteredRef.current);
    }
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

  // --- Helpers (closures over refs; bound once). -------------------------------
  function startLoadTimer() {
    clearLoadTimer();
    loadTimerRef.current = setTimeout(() => {
      if (!styleReadyRef.current) failCurrentStyle();
    }, loadTimeoutMs);
  }
  function clearLoadTimer() {
    if (loadTimerRef.current != null) {
      clearTimeout(loadTimerRef.current);
      loadTimerRef.current = null;
    }
  }

  function loadStage(map: maplibregl.Map, stage: Stage) {
    styleReadyRef.current = false;
    if (stage.kind === "configured") {
      attemptedRef.current.add(stage.style.id);
      clusteredRef.current = true;
      onBasemapNotice?.(null);
      startLoadTimer();
      map.setStyle(stage.style.styleUrl);
    } else {
      attemptedRef.current.add(NEUTRAL_FALLBACK_STYLE_ID);
      clusteredRef.current = false; // no glyphs on the neutral canvas ⇒ no cluster labels
      onBasemapNotice?.("The configured basemap could not be loaded. Showing a neutral offline canvas — every substation is still plotted and listed.");
      startLoadTimer();
      map.setStyle(NEUTRAL_FALLBACK_STYLE as StyleSpecification);
    }
  }

  /** Advance the offline fallback: selected → Standard → neutral → list. */
  function failCurrentStyle() {
    clearLoadTimer();
    const map = mapRef.current;
    if (map == null) return;
    const standard = available.find((s) => s.id === "standard");
    if (standard && !attemptedRef.current.has(standard.id)) {
      onBasemapNotice?.(`The selected basemap could not be loaded. Falling back to the ${standard.label} map.`);
      setActiveStyleId(standard.id);
      loadStage(map, { kind: "configured", style: standard });
      return;
    }
    if (!attemptedRef.current.has(NEUTRAL_FALLBACK_STYLE_ID)) {
      loadStage(map, { kind: "neutral" });
      return;
    }
    // Even the neutral inline canvas failed ⇒ no usable map (e.g. no WebGL).
    styleReadyRef.current = false;
    setMapUsable(false);
    onBasemapStatus?.(false);
    onBasemapNotice?.(null);
  }

  function installLayers(map: maplibregl.Map, ls: EngineeringMapLayer[], clustered: boolean) {
    for (const layer of ls) installOneLayer(map, layer, clustered);
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
    // Wire the popup's "Open" affordance to SPA navigation and its close to deselect.
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

  function installOneLayer(map: maplibregl.Map, layer: EngineeringMapLayer, clustered: boolean) {
    const sid = sourceId(layer.id);
    if (map.getSource(sid)) return;
    map.addSource(sid, { type: "geojson", data: toFeatureCollection(layer), cluster: clustered, clusterMaxZoom: 11, clusterRadius: 44 });

    if (clustered) {
      map.addLayer({ id: `${sid}-clusters`, type: "circle", source: sid, filter: ["has", "point_count"], paint: { "circle-color": "#2540D8", "circle-opacity": 0.85, "circle-radius": ["step", ["get", "point_count"], 16, 10, 22, 50, 30] } });
      map.addLayer({ id: `${sid}-cluster-count`, type: "symbol", source: sid, filter: ["has", "point_count"], layout: { "text-field": ["get", "point_count_abbreviated"], "text-size": 12 }, paint: { "text-color": "#FFFFFF" } });
    }
    map.addLayer({ id: `${sid}-points`, type: "circle", source: sid, filter: clustered ? ["!", ["has", "point_count"]] : ["all"], paint: { "circle-color": colorExpression(layer) as maplibregl.ExpressionSpecification, "circle-radius": 7, "circle-stroke-width": 1.5, "circle-stroke-color": "#FFFFFF" } });
    map.addLayer({ id: `${sid}-selected`, type: "circle", source: sid, filter: ["==", ["get", "id"], "__none__"], paint: { "circle-color": "rgba(0,0,0,0)", "circle-radius": 12, "circle-stroke-width": 3, "circle-stroke-color": "#0F2340" } });

    map.on("click", `${sid}-points`, (e) => {
      const id = e.features?.[0]?.properties?.id;
      if (typeof id === "string") onSelectRef.current?.(id);
    });
    if (clustered) {
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
    }
    const cursorLayers = clustered ? [`${sid}-points`, `${sid}-clusters`] : [`${sid}-points`];
    for (const cursorLayer of cursorLayers) {
      map.on("mouseenter", cursorLayer, () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", cursorLayer, () => (map.getCanvas().style.cursor = ""));
    }
  }

  if (!mapUsable) {
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
          {initialId == null
            ? "No map style is configured (VITE_MAP_STYLE_STANDARD). Substation Registry data remains available — use the record list or the Table view."
            : "The map could not be loaded. Substation Registry data remains available — use the record list or the Table view."}
        </p>
      </div>
    );
  }

  return (
    <div style={{ position: "relative", height, borderRadius: tokens.radius.lg, overflow: "hidden" }}>
      <div ref={containerRef} data-testid="engineering-map" style={{ position: "absolute", inset: 0 }} />
      {available.length > 1 && (
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
