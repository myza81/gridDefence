import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient, getHealth } from "../src/api/client";

describe("api client", () => {
  it("exists and exposes get/post/postForm", () => {
    expect(apiClient).toBeDefined();
    expect(typeof apiClient.get).toBe("function");
    expect(typeof apiClient.post).toBe("function");
    expect(typeof apiClient.postForm).toBe("function");
    expect(apiClient.baseUrl).toBeTruthy();
  });

  describe("postForm", () => {
    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("sends a multipart request without a Content-Type header override", async () => {
      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 202,
        json: async () => ({ job_id: "job-1" }),
      });
      vi.stubGlobal("fetch", fetchMock);

      const formData = new FormData();
      formData.append("file", new File(["Q\n"], "case.raw"));
      const result = await apiClient.postForm<{ job_id: string }>("/api/v1/x/preview", formData);

      expect(result.job_id).toBe("job-1");
      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(init.method).toBe("POST");
      expect(init.body).toBe(formData);
      expect((init.headers as Record<string, string> | undefined)?.["Content-Type"]).toBeUndefined();
    });
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
