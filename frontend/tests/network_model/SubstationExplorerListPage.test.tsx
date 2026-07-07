import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SubstationExplorerListPage } from "../../src/modules/network_model/pages/SubstationExplorerListPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const SUBSTATIONS_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/api\/v1\/substations/,
  respond: () => ({
    status: 200,
    body: {
      items: [
        {
          substation_id: "s1",
          mnemonic: "PKLG",
          official_name: "Pekan Lama",
          region_id: 1,
          state_id: 1,
          grid_owner_id: 1,
          operational_status_id: 1,
          psse_bus_number: null,
        },
      ],
      page: 1,
      page_size: 25,
      total: 1,
    },
  }),
};

describe("SubstationExplorerListPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders substations with a link into the Network Explorer's own detail view", async () => {
    stubFetch([SUBSTATIONS_HANDLER]);

    renderWithProviders(<SubstationExplorerListPage />, { route: "/network-model/substations" });

    await waitFor(() => {
      expect(screen.getByText("PKLG")).toBeInTheDocument();
    });
    expect(screen.getByText("Pekan Lama")).toBeInTheDocument();
    const link = screen.getByRole("link", { name: "Explore" });
    expect(link).toHaveAttribute("href", "/network-model/substations/s1");
  });

  it("shows an empty-registry message rather than an empty table", async () => {
    stubFetch([
      {
        method: "GET",
        pattern: /\/api\/v1\/substations/,
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 25, total: 0 } }),
      },
    ]);

    renderWithProviders(<SubstationExplorerListPage />, { route: "/network-model/substations" });

    await waitFor(() => {
      expect(screen.getByText("No substations match your search.")).toBeInTheDocument();
    });
  });
});
