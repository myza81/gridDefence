import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { PsseOperationalContextInspectorPage } from "../../src/modules/psse_integration/pages/PsseOperationalContextInspectorPage";
import type { PreviewResult } from "../../src/modules/psse_integration/types";

const FULL_PREVIEW_RESULT: PreviewResult = {
  import_type: "FULL_TOPOLOGY_WITH_LOAD",
  raw_version: 34,
  bus_count: 2,
  branch_count: 1,
  transformer_count: 0,
  load_count: 0,
  generator_count: 0,
  computed_signature: "abc123",
  topology_reused: false,
  matched_bus_count: 2,
  unmatched_bus_count: 0,
  coverage_percent: 100.0,
  warnings: [],
  source_file_reference: "case1.raw",
  base_mva: 100.0,
  frequency_hz: 50.0,
  case_description: "CPF_03 JAN 2025",
  raw_created: "WED, FEB 11 2026 14:43",
  sync_validation: null,
  buses: [
    {
      bus_number: 100,
      bus_name: "PKLG132",
      base_kv: 132.0,
      ide: 1,
      area: 1,
      zone: 1,
      owner: 1,
      voltage_mag: 1.02,
      voltage_angle: 0.0,
      bus_classification: "SWITCHYARD_BUS",
      in_service: true,
      substation_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      substation_mnemonic: "PKLG",
      voltage_yard_id: null,
      correlation_status: "CORRELATED",
    },
    {
      bus_number: 200,
      bus_name: "IGBK132",
      base_kv: 132.0,
      ide: 1,
      area: 1,
      zone: 1,
      owner: 1,
      voltage_mag: 1.01,
      voltage_angle: -1.0,
      bus_classification: "SWITCHYARD_BUS",
      in_service: true,
      substation_id: null,
      substation_mnemonic: null,
      voltage_yard_id: null,
      correlation_status: "UNMATCHED_OPERATIONAL",
    },
  ],
  branches: [
    {
      from_bus: 100,
      to_bus: 200,
      ckt_id: "1",
      r: 0.001,
      x: 0.01,
      b: 0.0002,
      rate_a: null,
      rate_b: null,
      rate_c: null,
      status: true,
    },
  ],
  transformers: [],
  loads: [],
  generators: [],
};

function renderAtRoute(route: string, state?: { previewResult?: PreviewResult }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[{ pathname: route, state }]}>
        <Routes>
          <Route path="/psse-integration/import" element={<p>Import page</p>} />
          <Route
            path="/psse-integration/import/inspect"
            element={<PsseOperationalContextInspectorPage />}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("PsseOperationalContextInspectorPage", () => {
  it("shows a plain explanation, with a link back to Preview, when navigated to directly with no data", () => {
    renderAtRoute("/psse-integration/import/inspect");

    expect(screen.getByText(/No imported data is available to inspect/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Run a Preview" })).toHaveAttribute(
      "href",
      "/psse-integration/import",
    );
  });

  it("renders the Overview tab by default with snapshot-level fields", () => {
    renderAtRoute("/psse-integration/import/inspect", { previewResult: FULL_PREVIEW_RESULT });

    expect(screen.getByText("Operational Context Inspector")).toBeInTheDocument();
    expect(screen.getByText("case1.raw")).toBeInTheDocument();
    expect(screen.getByText("Full Network Topology + Load Snapshot")).toBeInTheDocument();
  });

  it("renders every tab, including empty ones with a graceful message", async () => {
    renderAtRoute("/psse-integration/import/inspect", { previewResult: FULL_PREVIEW_RESULT });
    const user = userEvent.setup();

    for (const label of ["Bus Data", "Branch Data", "Transformer Data", "Load Data", "Generator Data"]) {
      expect(screen.getByRole("tab", { name: label })).toBeInTheDocument();
    }

    await user.click(screen.getByRole("tab", { name: "Bus Data" }));
    expect(screen.getByText("PKLG132")).toBeInTheDocument();
    expect(screen.getByText("2 of 2 records")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Branch Data" }));
    expect(screen.getByText("1 of 1 records")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Generator Data" }));
    expect(screen.getByText("No records available.")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Load Data" }));
    expect(screen.getByText("No records available.")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Transformer Data" }));
    expect(screen.getByText("No records available.")).toBeInTheDocument();
  });

  it("displays Bus Classification and Load Owner (Phase 7A)", async () => {
    const previewResult: PreviewResult = {
      ...FULL_PREVIEW_RESULT,
      buses: [
        { ...FULL_PREVIEW_RESULT.buses[0], bus_classification: "FICTITIOUS_BUS" },
        { ...FULL_PREVIEW_RESULT.buses[1], bus_classification: "SPLIT_SWITCHYARD_BUS" },
      ],
      loads: [
        { bus_number: 100, load_id: "1", status: true, p_mw: 10.5, q_mvar: 2.1, owner: 99 },
      ],
    };
    renderAtRoute("/psse-integration/import/inspect", { previewResult });
    const user = userEvent.setup();

    await user.click(screen.getByRole("tab", { name: "Bus Data" }));
    expect(screen.getByText("Classification")).toBeInTheDocument();
    expect(screen.getByText("Fictitious Bus")).toBeInTheDocument();
    expect(screen.getByText("Split Switchyard Bus")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "Load Data" }));
    expect(screen.getByText("Owner")).toBeInTheDocument();
    expect(screen.getByText("99")).toBeInTheDocument();
  });

  it("displays correlated Substation and Correlation Status (Phase 7C)", async () => {
    renderAtRoute("/psse-integration/import/inspect", { previewResult: FULL_PREVIEW_RESULT });
    const user = userEvent.setup();

    await user.click(screen.getByRole("tab", { name: "Bus Data" }));
    expect(screen.getByText("Correlated Substation")).toBeInTheDocument();
    expect(screen.getByText("Correlation Status")).toBeInTheDocument();
    expect(screen.getByText("PKLG")).toBeInTheDocument();
    expect(screen.getByText("Correlated")).toBeInTheDocument();
    expect(screen.getByText("Unmatched (Operational)")).toBeInTheDocument();
  });
});
