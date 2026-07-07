import { screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ConnectivityViewPage } from "../../src/modules/network_model/pages/ConnectivityViewPage";
import { renderWithProviders, stubFetch } from "../testUtils";

const SUBSTATION_ID = "44444444-4444-4444-4444-444444444444";
const NEIGHBOUR_ID = "55555555-5555-5555-5555-555555555555";

function renderConnectivityView() {
  return renderWithProviders(
    <Routes>
      <Route
        path="/network-model/substations/:substationId/connectivity"
        element={<ConnectivityViewPage />}
      />
    </Routes>,
    { route: `/network-model/substations/${SUBSTATION_ID}/connectivity` },
  );
}

describe("ConnectivityViewPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("groups a neighbour reached via two parallel lines under one navigable entry", async () => {
    const connectivity = {
      substation_id: SUBSTATION_ID,
      substation_mnemonic: "PKLG",
      substation_official_name: "Pekan Lama",
      connected_lines: [],
      neighbours: [
        {
          substation_id: NEIGHBOUR_ID,
          substation_mnemonic: "IGBK",
          substation_official_name: "Igan Baru",
          via_circuit_id: "c1",
          via_circuit_name: "IGBK–PKLG Line 1",
          via_bay_number: "1",
        },
        {
          substation_id: NEIGHBOUR_ID,
          substation_mnemonic: "IGBK",
          substation_official_name: "Igan Baru",
          via_circuit_id: "c2",
          via_circuit_name: "IGBK–PKLG Line 2",
          via_bay_number: "2",
        },
      ],
    };

    stubFetch([
      {
        method: "GET",
        pattern: new RegExp(`/network-model/substations/${SUBSTATION_ID}/connectivity$`),
        respond: () => ({ status: 200, body: connectivity }),
      },
    ]);

    renderConnectivityView();

    await waitFor(() => {
      expect(screen.getByRole("link", { name: /IGBK — Igan Baru/ })).toBeInTheDocument();
    });
    expect(screen.getByText("via IGBK–PKLG Line 1")).toBeInTheDocument();
    expect(screen.getByText("via IGBK–PKLG Line 2")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /IGBK — Igan Baru/ })).toHaveAttribute(
      "href",
      `/network-model/substations/${NEIGHBOUR_ID}/connectivity`,
    );
  });

  it("shows a plain message for a substation with no registered neighbours", async () => {
    const connectivity = {
      substation_id: SUBSTATION_ID,
      substation_mnemonic: "ABBA",
      substation_official_name: "ABBA Substation",
      connected_lines: [],
      neighbours: [],
    };
    stubFetch([
      {
        method: "GET",
        pattern: new RegExp(`/network-model/substations/${SUBSTATION_ID}/connectivity$`),
        respond: () => ({ status: 200, body: connectivity }),
      },
    ]);

    renderConnectivityView();

    await waitFor(() => {
      expect(screen.getByText("No neighbouring substations registered yet.")).toBeInTheDocument();
    });
  });
});
