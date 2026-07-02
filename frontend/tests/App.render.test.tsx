import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "../src/components/layout/AppShell";
import { StatusPage } from "../src/components/layout/StatusPage";

describe("App renders", () => {
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

  it("renders the landing page inside the app shell without crashing", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <AppShell>
          <StatusPage />
        </AppShell>
      </QueryClientProvider>,
    );

    expect(screen.getByRole("heading", { level: 1, name: "GridDefence" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByTestId("status-badge")).toBeInTheDocument();
    });
  });
});
