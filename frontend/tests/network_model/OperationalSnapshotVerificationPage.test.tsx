import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { OperationalSnapshotVerificationPage } from "../../src/modules/network_model/pages/OperationalSnapshotVerificationPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const PKLG_ID = "44444444-4444-4444-4444-444444444444";
const IGBK_ID = "55555555-5555-5555-5555-555555555555";
const TOPOLOGY_VERSION_ID = "66666666-6666-6666-6666-666666666666";
const YARD_ID = "77777777-7777-7777-7777-777777777777";

const SUBSTATION_OPTIONS_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/api\/v1\/substations/,
  respond: () => ({
    status: 200,
    body: {
      items: [
        {
          substation_id: PKLG_ID,
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
      page_size: 500,
      total: 1,
    },
  }),
};

const VOLTAGE_YARDS_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/api\/v1\/voltage-yards/,
  respond: () => ({
    status: 200,
    body: [
      {
        voltage_yard_id: YARD_ID,
        substation_id: PKLG_ID,
        substation_mnemonic: "PKLG",
        substation_official_name: "Pekan Lama",
        voltage_level_id: 1,
        voltage_level_label: "132kV",
        display_label: "PKLG 132kV",
        commissioning_date: null,
        latitude: null,
        longitude: null,
        operational_status_id: 1,
      },
    ],
  }),
};

const SNAPSHOT_SUMMARY_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/network-model\/verification\/snapshot-summary$/,
  respond: () => ({
    status: 200,
    body: {
      topology_version_id: TOPOLOGY_VERSION_ID,
      topology_version_status: "Current",
      load_snapshot_id: null,
      load_snapshot_status: null,
      import_date: "2026-07-08T00:00:00Z",
      bus_count: 2,
      branch_count: 1,
      transformer_count: 0,
      load_count: 0,
      generator_count: 0,
    },
  }),
};

function verificationResultBody() {
  return {
    start_substation_id: PKLG_ID,
    start_voltage_yard_id: null,
    topology_version_id: TOPOLOGY_VERSION_ID,
    path_steps: [
      {
        depth: 1,
        from_bus_number: 100,
        from_bus_name: "PKLG132",
        to_bus_number: 200,
        to_bus_name: "IGBK132",
        edge_type: "BRANCH",
        ckt_id: "1",
        topology_branch_id: 1,
        topology_transformer_id: null,
      },
    ],
    buses: [
      {
        depth: 0,
        base_kv: 132,
        bus: {
          topology_version_id: TOPOLOGY_VERSION_ID,
          bus_number: 100,
          bus_name: "PKLG132",
          bus_classification: "SWITCHYARD_BUS",
          in_service: true,
          substation_id: PKLG_ID,
          substation_mnemonic: "PKLG",
          voltage_yard_id: YARD_ID,
          correlation_status: "CORRELATED",
        },
      },
      {
        depth: 1,
        base_kv: 132,
        bus: {
          topology_version_id: TOPOLOGY_VERSION_ID,
          bus_number: 200,
          bus_name: "IGBK132",
          bus_classification: "SWITCHYARD_BUS",
          in_service: true,
          substation_id: IGBK_ID,
          substation_mnemonic: "IGBK",
          voltage_yard_id: null,
          correlation_status: "CORRELATED",
        },
      },
    ],
    branches: [
      {
        topology_version_id: TOPOLOGY_VERSION_ID,
        topology_branch_id: 1,
        from_bus_number: 100,
        to_bus_number: 200,
        ckt_id: "1",
        in_service: true,
        circuit_id: null,
        circuit_bay_number: null,
        correlation_status: "UNMATCHED_OPERATIONAL",
      },
    ],
    transformers: [],
    statistics: {
      operational_buses_traversed: 2,
      operational_branches_traversed: 1,
      operational_transformers_traversed: 0,
      operational_switchyards_traversed: 2,
      registered_substations_correlated: 2,
      registered_switchyards_correlated: 1,
    },
    correlation_summary: {
      bus: { total: 2, correlated: 2, unmatched: 0, outside_scope: 0 },
      branch: { total: 1, correlated: 0, unmatched: 1, outside_scope: 0 },
      transformer: { total: 0, correlated: 0, unmatched: 0, outside_scope: 0 },
    },
    projections: {
      bus_projection: [
        { bus_number: 100, bus_name: "PKLG132", depth: 0 },
        { bus_number: 200, bus_name: "IGBK132", depth: 1 },
      ],
      switchyard_projection: [
        {
          substation_id: PKLG_ID,
          substation_mnemonic: "PKLG",
          base_kv: 132,
          voltage_yard_id: YARD_ID,
          depth: 0,
          bus_count: 1,
        },
        {
          substation_id: IGBK_ID,
          substation_mnemonic: "IGBK",
          base_kv: 132,
          voltage_yard_id: null,
          depth: 1,
          bus_count: 1,
        },
      ],
      substation_projection: [
        { substation_id: PKLG_ID, substation_mnemonic: "PKLG", depth: 0 },
        { substation_id: IGBK_ID, substation_mnemonic: "IGBK", depth: 1 },
      ],
    },
  };
}

describe("OperationalSnapshotVerificationPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the Snapshot Summary section on load", async () => {
    stubFetch([SUBSTATION_OPTIONS_HANDLER, SNAPSHOT_SUMMARY_HANDLER]);

    renderWithProviders(<OperationalSnapshotVerificationPage />, {
      route: "/network-model/verification",
    });

    await waitFor(() => {
      expect(screen.getByText(TOPOLOGY_VERSION_ID, { exact: false })).toBeInTheDocument();
    });
    const busCountRow = screen.getByText("Bus Count").closest("tr");
    expect(within(busCountRow as HTMLElement).getByText("2")).toBeInTheDocument();
  });

  it("runs a path verification and displays the electrical path, statistics, and correlation summary", async () => {
    let requestPayload: unknown = null;
    stubFetch([
      SUBSTATION_OPTIONS_HANDLER,
      SNAPSHOT_SUMMARY_HANDLER,
      VOLTAGE_YARDS_HANDLER,
      {
        method: "POST",
        pattern: /\/network-model\/verification\/traverse$/,
        respond: (_url, init) => {
          requestPayload = init?.body ? JSON.parse(init.body as string) : null;
          return { status: 200, body: verificationResultBody() };
        },
      },
    ]);

    renderWithProviders(<OperationalSnapshotVerificationPage />, {
      route: "/network-model/verification",
    });

    const select = await screen.findByLabelText("Starting Substation");
    await screen.findByRole("option", { name: /PKLG/ });
    const user = userEvent.setup();
    await user.selectOptions(select, PKLG_ID);
    await user.click(screen.getByRole("button", { name: "Run Traversal" }));

    await waitFor(() => {
      expect(requestPayload).toMatchObject({ start_substation_id: PKLG_ID });
    });

    // Section 2 — Electrical Path (bus names appear more than once across
    // sections, so assert presence via getAllByText rather than an
    // ambiguous single match).
    await waitFor(() => {
      expect(screen.getAllByText(/PKLG132/).length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText(/IGBK132/).length).toBeGreaterThan(0);

    // Section 6 — Traversal Statistics.
    expect(screen.getByText("Operational Switchyards Traversed")).toBeInTheDocument();
    const statsRow = screen.getByText("Registered Switchyards Correlated").closest("tr");
    expect(statsRow).not.toBeNull();
    expect(within(statsRow as HTMLElement).getByText("1")).toBeInTheDocument();

    // Section 7 — Correlation Summary.
    expect(screen.getByRole("columnheader", { name: "Object Type" })).toBeInTheDocument();
    const branchRow = screen.getByText("Branch").closest("tr");
    expect(branchRow).not.toBeNull();
    // total=1, correlated=0, unmatched=1, outside_scope=0.
    expect(within(branchRow as HTMLElement).getAllByText("1")).toHaveLength(2);
  });

  it("switches between Bus, Switchyard, and Substation projections without a new request", async () => {
    stubFetch([
      SUBSTATION_OPTIONS_HANDLER,
      SNAPSHOT_SUMMARY_HANDLER,
      VOLTAGE_YARDS_HANDLER,
      {
        method: "POST",
        pattern: /\/network-model\/verification\/traverse$/,
        respond: () => ({ status: 200, body: verificationResultBody() }),
      },
    ]);

    renderWithProviders(<OperationalSnapshotVerificationPage />, {
      route: "/network-model/verification",
    });

    const select = await screen.findByLabelText("Starting Substation");
    await screen.findByRole("option", { name: /PKLG/ });
    const user = userEvent.setup();
    await user.selectOptions(select, PKLG_ID);
    await user.click(screen.getByRole("button", { name: "Run Traversal" }));

    await screen.findByText("Operational Switchyard Projection");

    // Default projection is Substation. Section 3's Operational Bus View
    // table already has its own "Bus Number" column, so the projection
    // table is distinguished by count (one occurrence pre-switch, two once
    // the Bus projection is also showing), not by an ambiguous single
    // lookup.
    expect(screen.getByRole("radio", { name: "Registered Substation Projection" })).toBeChecked();
    expect(screen.getAllByRole("columnheader", { name: "Bus Number" })).toHaveLength(1);

    await user.click(screen.getByRole("radio", { name: "Operational Bus Projection" }));
    await waitFor(() => {
      expect(screen.getAllByRole("columnheader", { name: "Bus Number" })).toHaveLength(2);
    });

    // "Registered Switchyard" is also Section 3's own column header, so
    // again assert by count rather than an ambiguous single lookup.
    await user.click(screen.getByRole("radio", { name: "Operational Switchyard Projection" }));
    await waitFor(() => {
      expect(screen.getAllByRole("columnheader", { name: "Registered Switchyard" })).toHaveLength(2);
    });
    expect(screen.getByText("Not registered")).toBeInTheDocument();
  });
});
