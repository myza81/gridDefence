import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NetworkOverviewPage } from "../../src/modules/network_model/pages/NetworkOverviewPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

function overviewHandler(body: unknown): FetchHandler {
  return {
    method: "GET",
    pattern: /\/api\/v1\/network-model\/overview$/,
    respond: () => ({ status: 200, body }),
  };
}

describe("NetworkOverviewPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders registered-network counts", async () => {
    stubFetch([
      overviewHandler({
        substation_count: 4,
        circuit_count: 3,
        tee_off_circuit_count: 1,
        transformer_count: 2,
      }),
    ]);

    renderWithProviders(<NetworkOverviewPage />, { route: "/network-model" });

    await waitFor(() => {
      expect(screen.getByText("4")).toBeInTheDocument();
    });
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("renders an all-zero summary for an empty registry without error", async () => {
    stubFetch([
      overviewHandler({
        substation_count: 0,
        circuit_count: 0,
        tee_off_circuit_count: 0,
        transformer_count: 0,
      }),
    ]);

    renderWithProviders(<NetworkOverviewPage />, { route: "/network-model" });

    await waitFor(() => {
      expect(screen.getAllByText("0")).toHaveLength(4);
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
