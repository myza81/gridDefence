import { describe, expect, it } from "vitest";

import { computeStandardTuning, STANDARD_LABEL_TUNING } from "../../../src/components/map/mapCartography";

// Minimal synthetic style resembling the OpenMapTiles/Liberty label layers.
const style = {
  layers: [
    { id: "highway-name-major", type: "symbol", minzoom: 12.2 },
    { id: "highway-name-minor", type: "symbol", minzoom: 15 },
    { id: "waterway_line_label", type: "symbol", minzoom: 10 },
    { id: "label_village", type: "symbol", minzoom: 9 },
    { id: "label_city", type: "symbol", minzoom: 3 }, // not in the tuning set
    { id: "road_minor", type: "line" }, // data-generalized, no minzoom — untouched
    { id: "background", type: "background" },
  ],
} as never;

describe("computeStandardTuning", () => {
  it("lowers only the curated label thresholds, and only when data exists earlier", () => {
    const overrides = computeStandardTuning(style);
    const byId = Object.fromEntries(overrides.map((o) => [o.id, o.minzoom]));
    expect(byId["highway-name-major"]).toBe(11);
    expect(byId["highway-name-minor"]).toBe(14);
    expect(byId["waterway_line_label"]).toBe(9);
    expect(byId["label_village"]).toBe(8);
    // Untouched: not in the tuning set, or geometry that is data-generalized.
    expect(byId["label_city"]).toBeUndefined();
    expect(byId["road_minor"]).toBeUndefined();
    expect(byId["background"]).toBeUndefined();
  });

  it("only ever lowers a threshold (never raises) and skips absent layers", () => {
    // A style where the label is already earlier than our target ⇒ no override.
    const already = { layers: [{ id: "highway-name-major", type: "symbol", minzoom: 9 }] } as never;
    expect(computeStandardTuning(already)).toEqual([]);
    // No matching layers (e.g. the neutral style) ⇒ no-op.
    expect(computeStandardTuning({ layers: [{ id: "neutral-land", type: "fill" }] } as never)).toEqual([]);
    expect(computeStandardTuning(undefined)).toEqual([]);
  });

  it("carries a maxzoom so setLayerZoomRange gets a valid range", () => {
    const overrides = computeStandardTuning(style);
    expect(overrides.every((o) => typeof o.maxzoom === "number" && o.maxzoom > o.minzoom)).toBe(true);
    // Tuning table stays curated (labels only — never geometry).
    expect(STANDARD_LABEL_TUNING.every((t) => /name|label/.test(t.id))).toBe(true);
  });
});
