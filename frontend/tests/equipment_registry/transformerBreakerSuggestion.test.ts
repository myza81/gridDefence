import { describe, expect, it } from "vitest";

import type { TransformerBreakerNumberingConventionSummary } from "../../src/reference_data/types";
import { suggestBreakerNumber } from "../../src/modules/equipment_registry/transformerBreakerSuggestion";

// Voltage level ids mirror app/reference_data/seed.py's VOLTAGE_LEVELS
// insertion order (arbitrary here — the function keys on these ids, not on
// nominal kV directly, exactly as the backend reference table does).
const VL = { "500kV": 1, "275kV": 2, "132kV": 4, "33kV": 5, "22kV": 6, "11kV": 7 } as const;

function convention(
  hvLabel: keyof typeof VL,
  lvLabel: keyof typeof VL,
  side: "HV" | "LV",
  pattern: string | null,
  isStandard = pattern !== null,
): TransformerBreakerNumberingConventionSummary {
  return {
    convention_id: 0,
    hv_voltage_level_id: VL[hvLabel],
    lv_voltage_level_id: VL[lvLabel],
    side,
    pattern,
    is_standard: isStandard,
    notes: null,
  };
}

// Mirrors app/reference_data/seed.py's TRANSFORMER_BREAKER_NUMBERING_CONVENTIONS exactly.
const CONVENTIONS: TransformerBreakerNumberingConventionSummary[] = [
  convention("500kV", "275kV", "HV", null, false),
  convention("500kV", "275kV", "LV", "T{N}0"),
  convention("275kV", "132kV", "HV", "H{N}0"),
  convention("275kV", "132kV", "LV", "{N}80"),
  convention("132kV", "33kV", "HV", "{N}10"),
  convention("132kV", "33kV", "LV", "{N}T0"),
  convention("132kV", "22kV", "HV", "{N}10"),
  convention("132kV", "22kV", "LV", "{N}T0"),
  convention("132kV", "11kV", "HV", "{N}10"),
  convention("132kV", "11kV", "LV", "3{N}"),
];

describe("suggestBreakerNumber", () => {
  it.each([
    // [hvLabel, lvLabel, side, transformerNumber, expected]
    ["500kV", "275kV", "HV", "1", null], // 500kV side is non-standard — no suggestion.
    ["500kV", "275kV", "LV", "1", "T10"],
    ["275kV", "132kV", "HV", "1", "H10"],
    ["275kV", "132kV", "LV", "1", "180"],
    ["275kV", "132kV", "HV", "2", "H20"],
    ["275kV", "132kV", "LV", "2", "280"],
    ["132kV", "33kV", "HV", "1", "110"],
    ["132kV", "33kV", "LV", "1", "1T0"],
    ["132kV", "22kV", "HV", "1", "110"],
    ["132kV", "22kV", "LV", "1", "1T0"],
    ["132kV", "11kV", "HV", "3", "310"],
    ["132kV", "11kV", "LV", "1", "31"],
    ["132kV", "11kV", "LV", "3", "33"],
  ] as const)(
    "%skV/%skV %s side, bay %s -> %s",
    (hvLabel, lvLabel, side, transformerNumber, expected) => {
      expect(
        suggestBreakerNumber(
          CONVENTIONS,
          VL[hvLabel],
          VL[lvLabel],
          side,
          transformerNumber,
        ),
      ).toBe(expected);
    },
  );

  it("returns null when no convention row matches the pair (e.g. 230kV)", () => {
    expect(suggestBreakerNumber(CONVENTIONS, 3, VL["132kV"], "HV", "1")).toBeNull();
  });

  it("returns null for a non-numeric transformer number (e.g. 'Main')", () => {
    expect(
      suggestBreakerNumber(CONVENTIONS, VL["275kV"], VL["132kV"], "HV", "Main"),
    ).toBeNull();
  });

  it("returns null when the convention list is empty (not yet loaded)", () => {
    expect(suggestBreakerNumber([], VL["275kV"], VL["132kV"], "HV", "1")).toBeNull();
  });
});
