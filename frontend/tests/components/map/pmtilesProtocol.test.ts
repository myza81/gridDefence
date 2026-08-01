import maplibregl from "maplibre-gl";
import { afterEach, describe, expect, it, vi } from "vitest";

import { registerPmtilesProtocol, __resetPmtilesProtocolForTests } from "../../../src/components/map/pmtilesProtocol";

describe("registerPmtilesProtocol", () => {
  afterEach(() => {
    __resetPmtilesProtocolForTests();
    vi.restoreAllMocks();
  });

  it("registers the pmtiles protocol exactly once, even when called repeatedly", () => {
    __resetPmtilesProtocolForTests();
    const addProtocol = vi.spyOn(maplibregl, "addProtocol").mockImplementation(() => {});
    registerPmtilesProtocol();
    registerPmtilesProtocol();
    registerPmtilesProtocol();
    const pmtilesRegistrations = addProtocol.mock.calls.filter(([scheme]) => scheme === "pmtiles");
    expect(pmtilesRegistrations).toHaveLength(1);
  });
});
