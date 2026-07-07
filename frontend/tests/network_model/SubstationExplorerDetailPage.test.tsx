import { screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SubstationExplorerDetailPage } from "../../src/modules/network_model/pages/SubstationExplorerDetailPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const SUBSTATION_ID = "44444444-4444-4444-4444-444444444444";
const NEIGHBOUR_ID = "55555555-5555-5555-5555-555555555555";

function renderDetailPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/network-model/substations/:substationId" element={<SubstationExplorerDetailPage />} />
    </Routes>,
    { route: `/network-model/substations/${SUBSTATION_ID}` },
  );
}

describe("SubstationExplorerDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("dedupes a neighbour reached via two parallel transmission lines into one entry", async () => {
    const connectivity = {
      substation_id: SUBSTATION_ID,
      substation_mnemonic: "PKLG",
      substation_official_name: "Pekan Lama",
      connected_lines: [
        {
          circuit_id: "c1",
          bay_number: "1",
          circuit_name: "IGBK–PKLG",
          voltage_level_label: "500kV",
          line_type_label: "Overhead Line",
          operational_status_code: "ACTIVE",
          is_tee_off: false,
          terminals: [],
        },
        {
          circuit_id: "c2",
          bay_number: "2",
          circuit_name: "IGBK–PKLG",
          voltage_level_label: "500kV",
          line_type_label: "Overhead Line",
          operational_status_code: "ACTIVE",
          is_tee_off: false,
          terminals: [],
        },
      ],
      neighbours: [
        {
          substation_id: NEIGHBOUR_ID,
          substation_mnemonic: "IGBK",
          substation_official_name: "Igan Baru",
          via_circuit_id: "c1",
          via_circuit_name: "IGBK–PKLG",
          via_bay_number: "1",
        },
        {
          substation_id: NEIGHBOUR_ID,
          substation_mnemonic: "IGBK",
          substation_official_name: "Igan Baru",
          via_circuit_id: "c2",
          via_circuit_name: "IGBK–PKLG",
          via_bay_number: "2",
        },
      ],
    };
    const equipment = {
      substation_id: SUBSTATION_ID,
      substation_mnemonic: "PKLG",
      substation_official_name: "Pekan Lama",
      transformer_bays: [],
      line_bays: [],
    };

    stubFetch([
      {
        method: "GET",
        pattern: new RegExp(`/network-model/substations/${SUBSTATION_ID}/connectivity$`),
        respond: () => ({ status: 200, body: connectivity }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/network-model/substations/${SUBSTATION_ID}/equipment$`),
        respond: () => ({ status: 200, body: equipment }),
      },
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByText("Connected Substations (1)")).toBeInTheDocument();
    });
    expect(screen.getAllByText(/IGBK — Igan Baru/)).toHaveLength(1);
  });

  it("shows plain 'nothing registered yet' messages for an isolated, fully unregistered substation", async () => {
    const emptyConnectivity = {
      substation_id: SUBSTATION_ID,
      substation_mnemonic: "ABBA",
      substation_official_name: "ABBA Substation",
      connected_lines: [],
      neighbours: [],
    };
    const emptyEquipment = {
      substation_id: SUBSTATION_ID,
      substation_mnemonic: "ABBA",
      substation_official_name: "ABBA Substation",
      transformer_bays: [],
      line_bays: [],
    };

    stubFetch([
      {
        method: "GET",
        pattern: new RegExp(`/network-model/substations/${SUBSTATION_ID}/connectivity$`),
        respond: () => ({ status: 200, body: emptyConnectivity }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/network-model/substations/${SUBSTATION_ID}/equipment$`),
        respond: () => ({ status: 200, body: emptyEquipment }),
      },
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByText("ABBA — ABBA Substation")).toBeInTheDocument();
    });
    expect(screen.getByText("No Transformer Bays registered at this substation yet.")).toBeInTheDocument();
    expect(screen.getByText("No Line Bays registered at this substation yet.")).toBeInTheDocument();
    expect(screen.getByText("No neighbouring substations registered yet.")).toBeInTheDocument();
    expect(
      screen.getByText("No transmission lines registered at this substation yet."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a not-found message for a substation id the backend does not recognise", async () => {
    const notFoundHandler: FetchHandler = {
      method: "GET",
      pattern: new RegExp(`/network-model/substations/${SUBSTATION_ID}/(connectivity|equipment)$`),
      respond: () => ({ status: 404, body: { code: "not_found", message: "Substation not found" } }),
    };
    stubFetch([notFoundHandler]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Substation not found.");
    });
  });
});
