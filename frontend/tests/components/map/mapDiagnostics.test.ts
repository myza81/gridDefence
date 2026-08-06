import { describe, expect, it } from "vitest";

import { classifyStyleError, redactUrl, richFailureSummary } from "../../../src/components/map/mapDiagnostics";

describe("classifyStyleError (essential vs non-essential)", () => {
  it("treats a style-document load error as essential (fall back to neutral)", () => {
    expect(classifyStyleError({ error: { message: "Failed to fetch" } })).toBe("essential");
    expect(classifyStyleError({ error: { message: "Unexpected token in JSON" } })).toBe("essential");
  });

  it("treats sub-resource failures as non-essential (keep a usable rich map)", () => {
    // Source/tile errors carry a sourceId.
    expect(classifyStyleError({ sourceId: "openmaptiles", error: { message: "AJAXError" } })).toBe("non-essential");
    // Sprite/glyph/font failures are non-fatal in MapLibre.
    expect(classifyStyleError({ error: { message: "Error loading sprite" } })).toBe("non-essential");
    expect(classifyStyleError({ error: { message: "glyphs could not be loaded" } })).toBe("non-essential");
    expect(classifyStyleError({ error: { message: "failed to load tile 3/1/2" } })).toBe("non-essential");
  });

  it("defaults to non-essential on an empty/contentless event (timeout decides)", () => {
    expect(classifyStyleError(undefined)).toBe("non-essential");
    expect(classifyStyleError({})).toBe("non-essential");
    expect(classifyStyleError({ error: {} })).toBe("non-essential");
  });
});

describe("redactUrl", () => {
  it("drops the query string (where tokens live) but keeps origin + path", () => {
    expect(redactUrl("https://api.maptiler.com/maps/streets/style.json?key=SECRET123")).toBe(
      "https://api.maptiler.com/maps/streets/style.json [query redacted]",
    );
  });

  it("drops embedded credentials", () => {
    const out = redactUrl("https://user:pass@tiles.example/style.json");
    expect(out).not.toContain("pass");
    expect(out).toContain("tiles.example/style.json");
  });

  it("never leaks a token and handles non-URLs safely", () => {
    expect(redactUrl("not a url?key=abc")).not.toContain("abc");
    expect(redactUrl("")).toBe("");
  });
});

describe("richFailureSummary", () => {
  it("maps each reason to a short, safe, human message (no codes/URLs)", () => {
    expect(richFailureSummary("configuration_missing")).toMatch(/no online basemap is configured/i);
    expect(richFailureSummary("style_load_failed")).toMatch(/could not be loaded/i);
    expect(richFailureSummary("timeout")).toMatch(/did not respond in time/i);
    expect(richFailureSummary("unknown")).toMatch(/unavailable/i);
    for (const r of ["configuration_missing", "style_load_failed", "timeout", "unknown"] as const) {
      expect(richFailureSummary(r)).not.toMatch(/https?:\/\/|key=|token=/i);
    }
  });
});
