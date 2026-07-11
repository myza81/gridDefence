import { describe, expect, it } from "vitest";

import {
  describeTerminalResolution,
  formatTerminalIdentity,
  formatTerminalPickerLabel,
} from "../../src/modules/sensitive_customer_registry/displayHelpers";

describe("formatTerminalIdentity", () => {
  it("composes the pipe-separated identity when all three fields are resolved", () => {
    expect(formatTerminalIdentity("IGBK", "33kV", "Transformer T1")).toBe(
      "IGBK | 33kV | Transformer T1",
    );
  });

  it("appends the side in parentheses when provided (ADR-013)", () => {
    expect(formatTerminalIdentity("IGBK", "33kV", "Transformer T1", "LV")).toBe(
      "IGBK | 33kV | Transformer T1 (LV)",
    );
  });

  it("returns null when any field is null (unresolved or unassigned)", () => {
    expect(formatTerminalIdentity(null, "33kV", "Transformer T1")).toBeNull();
    expect(formatTerminalIdentity("IGBK", null, "Transformer T1")).toBeNull();
    expect(formatTerminalIdentity("IGBK", "33kV", null)).toBeNull();
  });
});

describe("formatTerminalPickerLabel", () => {
  it("composes the multi-select option label with substation, voltage, transformer, and side", () => {
    expect(
      formatTerminalPickerLabel({
        transformer_terminal_id: "55555555-5555-5555-5555-555555555555",
        transformer_id: "77777777-7777-7777-7777-777777777777",
        generated_short_name: "T1",
        transformer_number: "1",
        side: "LV",
        breaker_number: "T12",
        substation_id: "22222222-2222-2222-2222-222222222222",
        substation_mnemonic: "SARA",
        substation_official_name: "Sungai Ara Substation",
        voltage_level_id: 1,
        voltage_level_label: "33kV",
      }),
    ).toBe("SARA | 33kV | Transformer T1 (LV)");
  });
});

describe("describeTerminalResolution", () => {
  it("describes NOT_ASSIGNED", () => {
    expect(describeTerminalResolution("NOT_ASSIGNED")).toBe("No supply point recorded");
  });

  it("describes UNRESOLVED", () => {
    expect(describeTerminalResolution("UNRESOLVED")).toBe("Terminal could not be resolved");
  });

  it("returns an empty string for RESOLVED (identity string is used instead)", () => {
    expect(describeTerminalResolution("RESOLVED")).toBe("");
  });
});
