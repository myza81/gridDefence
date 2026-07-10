import { describe, expect, it } from "vitest";

import {
  deriveFunctionLabel,
  formatTerminalIdentity,
  functionFilterToParams,
} from "../../src/modules/automatic_load_shedding_functionality/displayHelpers";

describe("deriveFunctionLabel", () => {
  it("labels UFLS-only", () => {
    expect(deriveFunctionLabel(true, false)).toBe("UFLS");
  });

  it("labels UVLS-only", () => {
    expect(deriveFunctionLabel(false, true)).toBe("UVLS");
  });

  it("labels both as UFLS & UVLS", () => {
    expect(deriveFunctionLabel(true, true)).toBe("UFLS & UVLS");
  });
});

describe("functionFilterToParams", () => {
  it("maps the empty filter to no params", () => {
    expect(functionFilterToParams("")).toEqual({});
  });

  it("maps UFLS to ufls_function only", () => {
    expect(functionFilterToParams("UFLS")).toEqual({ ufls_function: true });
  });

  it("maps UVLS to uvls_function only", () => {
    expect(functionFilterToParams("UVLS")).toEqual({ uvls_function: true });
  });

  it("maps BOTH to both flags true", () => {
    expect(functionFilterToParams("BOTH")).toEqual({ ufls_function: true, uvls_function: true });
  });
});

describe("formatTerminalIdentity", () => {
  it("composes the pipe-separated engineering identity", () => {
    expect(formatTerminalIdentity("IGBK", "33kV", "Transformer T1")).toBe(
      "IGBK | 33kV | Transformer T1",
    );
  });

  it("distinguishes two ambiguous terminals at the same substation and voltage level", () => {
    // Two transformers at the same substation and voltage level — only the
    // bay_label differs (T1 vs T2). Engineers must be able to tell them
    // apart at a glance (Complete Engineering Identity Display).
    const first = formatTerminalIdentity("IGBK", "33kV", "Transformer T1");
    const second = formatTerminalIdentity("IGBK", "33kV", "Transformer T2");
    expect(first).not.toBe(second);
  });

  it("distinguishes two parallel circuits at the same substation and voltage level", () => {
    const first = formatTerminalIdentity("IGBK", "132kV", "Line IGBK–ROMEO No.1");
    const second = formatTerminalIdentity("IGBK", "132kV", "Line IGBK–ROMEO No.2");
    expect(first).not.toBe(second);
  });
});
