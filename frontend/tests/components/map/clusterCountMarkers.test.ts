import { describe, expect, it, vi } from "vitest";

// Fake MapLibre Marker so the DOM-marker controller runs without WebGL/a real
// map. Created instances are recorded so tests can assert add/remove/update.
vi.mock("maplibre-gl", () => {
  const created: Marker[] = [];
  class Marker {
    element: HTMLElement;
    lngLat: [number, number] | null = null;
    added = false;
    removed = false;
    constructor(opts: { element: HTMLElement }) {
      this.element = opts.element;
      created.push(this);
    }
    setLngLat(v: [number, number]) {
      this.lngLat = v;
      return this;
    }
    addTo() {
      this.added = true;
      return this;
    }
    remove() {
      this.removed = true;
    }
    getElement() {
      return this.element;
    }
  }
  return { default: { Marker, __created: created } };
});

import maplibregl from "maplibre-gl";

import {
  clusterCountLabel,
  createClusterCountController,
  createClusterCountElement,
  toClusterPoints,
} from "../../../src/components/map/clusterCountMarkers";

const cluster = (id: number, count: number, abbr?: string, lng = 101, lat = 3) => ({
  type: "Feature",
  properties: { cluster_id: id, point_count: count, ...(abbr ? { point_count_abbreviated: abbr } : {}) },
  geometry: { type: "Point", coordinates: [lng, lat] },
});

describe("clusterCountLabel", () => {
  it("prefers point_count_abbreviated, falls back to point_count", () => {
    expect(clusterCountLabel({ point_count: 1500, point_count_abbreviated: "1.5k" })).toBe("1.5k");
    expect(clusterCountLabel({ point_count: 42 })).toBe("42");
    expect(clusterCountLabel({})).toBe("");
  });
});

describe("toClusterPoints", () => {
  it("maps cluster features to keyed points and dedupes repeated cluster ids", () => {
    const points = toClusterPoints("layer-substations", [
      cluster(7, 156) as never,
      cluster(7, 156) as never, // same cluster from an adjacent tile
      cluster(9, 3, "3") as never,
      { type: "Feature", properties: { id: "x" }, geometry: { type: "Point", coordinates: [1, 2] } } as never, // not a cluster
    ]);
    expect(points.map((p) => p.key)).toEqual(["layer-substations:7", "layer-substations:9"]);
    expect(points[0].label).toBe("156");
    expect(points[1].label).toBe("3");
    expect(points[0]).toMatchObject({ lng: 101, lat: 3 });
  });
});

describe("createClusterCountElement", () => {
  it("renders a centred, high-contrast, pointer-transparent, decorative count", () => {
    for (const label of ["1", "12", "156"]) {
      const el = createClusterCountElement(label);
      expect(el.textContent).toBe(label); // 1-, 2- and 3-digit all render
      expect(el.style.color).toBe("rgb(255, 255, 255)");
      expect(el.style.pointerEvents).toBe("none"); // clicks pass through to the circle
      expect(el.style.textAlign).toBe("center");
      expect(el.style.fontWeight).toBe("700");
      expect(el.getAttribute("aria-hidden")).toBe("true"); // record list is the a11y path
    }
  });
});

describe("createClusterCountController", () => {
  function fakeMap(featuresBySource: Record<string, unknown[]>) {
    return {
      getSource: (id: string) => (featuresBySource[id] ? {} : undefined),
      isSourceLoaded: () => true,
      querySourceFeatures: (id: string) => featuresBySource[id] ?? [],
    } as never;
  }

  it("adds a marker per cluster, reuses on update, and removes vanished clusters", () => {
    const created = (maplibregl as unknown as { __created: { element: HTMLElement; added: boolean; removed: boolean }[] }).__created;
    created.length = 0;
    const state: Record<string, unknown[]> = { "layer-substations": [cluster(1, 10, "10") as never, cluster(2, 20, "20") as never] };
    const map = fakeMap(state);
    const controller = createClusterCountController(map, () => ["layer-substations"]);

    controller.update();
    expect(created).toHaveLength(2); // one marker per cluster
    expect(created.every((m) => m.added)).toBe(true);
    expect(created[0].element.textContent).toBe("10");

    // Cluster 2 vanishes; cluster 1's count changes → reuse marker 1, remove marker 2.
    state["layer-substations"] = [cluster(1, 11, "11") as never];
    controller.update();
    expect(created).toHaveLength(2); // no new marker created (cluster 1 reused)
    expect(created[0].element.textContent).toBe("11"); // label updated in place
    expect(created[1].removed).toBe(true); // vanished cluster removed

    controller.clear();
    expect(created[0].removed).toBe(true);
  });

  it("skips sources that are not present or not loaded (no throw, no markers)", () => {
    const map = {
      getSource: () => undefined,
      isSourceLoaded: () => false,
      querySourceFeatures: () => [],
    } as never;
    const controller = createClusterCountController(map, () => ["layer-substations"]);
    expect(() => controller.update()).not.toThrow();
  });
});
