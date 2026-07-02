import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient, getHealth } from "../src/api/client";

describe("api client", () => {
  it("exists and exposes get/post", () => {
    expect(apiClient).toBeDefined();
    expect(typeof apiClient.get).toBe("function");
    expect(typeof apiClient.post).toBe("function");
    expect(apiClient.baseUrl).toBeTruthy();
  });

  describe("getHealth", () => {
    beforeEach(() => {
      vi.stubGlobal(
        "fetch",
        vi.fn().mockResolvedValue({
          ok: true,
          json: async () => ({ status: "ok", environment: "test" }),
        }),
      );
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("calls the unversioned /health endpoint", async () => {
      const result = await getHealth();

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining("/health"),
        expect.objectContaining({ method: "GET" }),
      );
      expect(result.status).toBe("ok");
    });
  });
});
