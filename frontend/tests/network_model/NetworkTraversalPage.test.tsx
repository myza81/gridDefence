import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NetworkTraversalPage } from "../../src/modules/network_model/pages/NetworkTraversalPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const START_ID = "44444444-4444-4444-4444-444444444444";
const NEIGHBOUR_ID = "55555555-5555-5555-5555-555555555555";

const SUBSTATION_OPTIONS_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/api\/v1\/substations/,
  respond: () => ({
    status: 200,
    body: {
      items: [
        {
          substation_id: START_ID,
          mnemonic: "PKLG",
          official_name: "Pekan Lama",
          region_id: 1,
          state_id: 1,
          grid_owner_id: 1,
          operational_status_id: 1,
          psse_bus_number: null,
        },
        {
          substation_id: NEIGHBOUR_ID,
          mnemonic: "IGBK",
          official_name: "Igan Baru",
          region_id: 1,
          state_id: 1,
          grid_owner_id: 1,
          operational_status_id: 1,
          psse_bus_number: null,
        },
      ],
      page: 1,
      page_size: 500,
      total: 2,
    },
  }),
};

describe("NetworkTraversalPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("runs a traversal and shows reachable substations, their depth, and the lines within the reachable set", async () => {
    let traversalPayload: unknown = null;

    stubFetch([
      SUBSTATION_OPTIONS_HANDLER,
      {
        method: "POST",
        pattern: /\/api\/v1\/network-model\/traverse$/,
        respond: (_url, init) => {
          traversalPayload = init?.body ? JSON.parse(init.body as string) : null;
          return {
            status: 200,
            body: {
              start_substation_id: START_ID,
              excluded_circuit_ids: [],
              reachable_substations: [
                { substation_id: START_ID, substation_mnemonic: "PKLG", depth: 0 },
                { substation_id: NEIGHBOUR_ID, substation_mnemonic: "IGBK", depth: 1 },
              ],
            },
          };
        },
      },
      {
        method: "GET",
        pattern: new RegExp(`/network-model/substations/${START_ID}/connectivity$`),
        respond: () => ({
          status: 200,
          body: {
            substation_id: START_ID,
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
                terminals: [
                  { circuit_terminal_id: "ct1", substation_id: START_ID, substation_mnemonic: "PKLG", voltage_yard_id: "vy1", breaker_number: "1" },
                  { circuit_terminal_id: "ct2", substation_id: NEIGHBOUR_ID, substation_mnemonic: "IGBK", voltage_yard_id: "vy2", breaker_number: "2" },
                ],
              },
            ],
            neighbours: [],
          },
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/network-model/substations/${NEIGHBOUR_ID}/connectivity$`),
        respond: () => ({
          status: 200,
          body: {
            substation_id: NEIGHBOUR_ID,
            substation_mnemonic: "IGBK",
            substation_official_name: "Igan Baru",
            connected_lines: [],
            neighbours: [],
          },
        }),
      },
    ]);

    renderWithProviders(<NetworkTraversalPage />, { route: "/network-model/traversal" });

    const select = await screen.findByLabelText("Starting substation");
    await screen.findByRole("option", { name: /PKLG/ });
    const user = userEvent.setup();
    await user.selectOptions(select, START_ID);
    await user.click(screen.getByRole("button", { name: "Traverse" }));

    await waitFor(() => {
      expect(traversalPayload).toMatchObject({ start_substation_id: START_ID });
    });

    await waitFor(() => {
      expect(screen.getByText("Reachable Substations (2)")).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "IGBK" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("IGBK–PKLG (PKLG – IGBK)")).toBeInTheDocument();
    });
  });

  it("includes maximum depth in the traversal request when supplied", async () => {
    let traversalPayload: unknown = null;
    stubFetch([
      SUBSTATION_OPTIONS_HANDLER,
      {
        method: "POST",
        pattern: /\/api\/v1\/network-model\/traverse$/,
        respond: (_url, init) => {
          traversalPayload = init?.body ? JSON.parse(init.body as string) : null;
          return {
            status: 200,
            body: {
              start_substation_id: START_ID,
              excluded_circuit_ids: [],
              reachable_substations: [{ substation_id: START_ID, substation_mnemonic: "PKLG", depth: 0 }],
            },
          };
        },
      },
    ]);

    renderWithProviders(<NetworkTraversalPage />, { route: "/network-model/traversal" });

    const select = await screen.findByLabelText("Starting substation");
    await screen.findByRole("option", { name: /PKLG/ });
    const user = userEvent.setup();
    await user.selectOptions(select, START_ID);
    await user.type(screen.getByLabelText("Maximum depth (optional)"), "2");
    await user.click(screen.getByRole("button", { name: "Traverse" }));

    await waitFor(() => {
      expect(traversalPayload).toMatchObject({ start_substation_id: START_ID, max_depth: 2 });
    });
  });
});
