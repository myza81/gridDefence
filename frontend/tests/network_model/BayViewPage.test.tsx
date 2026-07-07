import { screen, waitFor, within } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { BayViewPage } from "../../src/modules/network_model/pages/BayViewPage";
import { renderWithProviders, stubFetch } from "../testUtils";

const SUBSTATION_ID = "44444444-4444-4444-4444-444444444444";

function renderBayView() {
  return renderWithProviders(
    <Routes>
      <Route path="/network-model/substations/:substationId/bays" element={<BayViewPage />} />
    </Routes>,
    { route: `/network-model/substations/${SUBSTATION_ID}/bays` },
  );
}

describe("BayViewPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("presents Transformer Bays and Line Bays as one unified list of Bays, using only engineering terminology", async () => {
    const equipment = {
      substation_id: SUBSTATION_ID,
      substation_mnemonic: "PKLG",
      substation_official_name: "Pekan Lama",
      transformer_bays: [
        {
          transformer_id: "t1",
          transformer_number: "1",
          generated_short_name: "XGT1",
          hv_voltage_level_label: "500kV",
          lv_voltage_level_label: "132kV",
          capacity_mva: 150,
          operational_status_code: "ACTIVE",
        },
      ],
      line_bays: [
        {
          circuit_terminal_id: "ct1",
          circuit_id: "c1",
          circuit_bay_number: "1",
          circuit_name: "IGBK–PKLG–NKST",
          breaker_number: "805",
          voltage_level_label: "500kV",
          operational_status_code: "ACTIVE",
        },
      ],
    };
    // A tee-off: two other substations terminate the same circuit.
    const connectivity = {
      substation_id: SUBSTATION_ID,
      substation_mnemonic: "PKLG",
      substation_official_name: "Pekan Lama",
      connected_lines: [
        {
          circuit_id: "c1",
          bay_number: "1",
          circuit_name: "IGBK–PKLG–NKST",
          voltage_level_label: "500kV",
          line_type_label: "Overhead Line",
          operational_status_code: "ACTIVE",
          is_tee_off: true,
          terminals: [
            { circuit_terminal_id: "ct1", substation_id: SUBSTATION_ID, substation_mnemonic: "PKLG", voltage_yard_id: "vy1", breaker_number: "805" },
            { circuit_terminal_id: "ct2", substation_id: "s2", substation_mnemonic: "IGBK", voltage_yard_id: "vy2", breaker_number: "12" },
            { circuit_terminal_id: "ct3", substation_id: "s3", substation_mnemonic: "NKST", voltage_yard_id: "vy3", breaker_number: "9" },
          ],
        },
      ],
      neighbours: [],
    };

    stubFetch([
      {
        method: "GET",
        pattern: new RegExp(`/network-model/substations/${SUBSTATION_ID}/equipment$`),
        respond: () => ({ status: 200, body: equipment }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/network-model/substations/${SUBSTATION_ID}/connectivity$`),
        respond: () => ({ status: 200, body: connectivity }),
      },
    ]);

    renderBayView();

    await waitFor(() => {
      expect(screen.getByText("XGT1")).toBeInTheDocument();
    });

    const transformerRow = screen.getByText("XGT1").closest("tr");
    expect(transformerRow).not.toBeNull();
    expect(within(transformerRow!).getByText("Transformer Bay")).toBeInTheDocument();
    expect(within(transformerRow!).getByText(/500kV\/132kV Transformer \(150 MVA\)/)).toBeInTheDocument();
    expect(within(transformerRow!).getByText("Not available")).toBeInTheDocument();

    const lineRow = screen.getByText("Bay 1").closest("tr");
    expect(lineRow).not.toBeNull();
    expect(within(lineRow!).getByText("Line Bay")).toBeInTheDocument();
    expect(within(lineRow!).getByText("805")).toBeInTheDocument();
    // A tee-off Line Bay has more than one neighbour — never assume exactly one.
    expect(within(lineRow!).getByText("IGBK, NKST")).toBeInTheDocument();

    // Official engineering terminology only — never implementation names.
    expect(screen.queryByText(/CircuitTerminal/)).not.toBeInTheDocument();
    expect(screen.queryByText(/TransformerTerminal/)).not.toBeInTheDocument();
  });

  it("shows a plain empty-registry message when a substation has no Bays yet", async () => {
    const emptyEquipment = {
      substation_id: SUBSTATION_ID,
      substation_mnemonic: "ABBA",
      substation_official_name: "ABBA Substation",
      transformer_bays: [],
      line_bays: [],
    };
    const emptyConnectivity = {
      substation_id: SUBSTATION_ID,
      substation_mnemonic: "ABBA",
      substation_official_name: "ABBA Substation",
      connected_lines: [],
      neighbours: [],
    };

    stubFetch([
      {
        method: "GET",
        pattern: new RegExp(`/network-model/substations/${SUBSTATION_ID}/equipment$`),
        respond: () => ({ status: 200, body: emptyEquipment }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/network-model/substations/${SUBSTATION_ID}/connectivity$`),
        respond: () => ({ status: 200, body: emptyConnectivity }),
      },
    ]);

    renderBayView();

    await waitFor(() => {
      expect(screen.getByText("No Bays registered at this substation yet.")).toBeInTheDocument();
    });
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });
});
