import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../src/modules/iam/AuthContext";
import { authStorage } from "../../src/modules/iam/authStorage";
import { ProtectedRoute } from "../../src/modules/iam/ProtectedRoute";
import { BoundaryPocketEvaluatorPage } from "../../src/modules/network_model/pages/BoundaryPocketEvaluatorPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const NKST_ID = "44444444-4444-4444-4444-444444444444";
const PKLG_ID = "55555555-5555-5555-5555-555555555555";
const TERMINAL_A_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const TERMINAL_B_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";

const CIRCUIT_TERMINALS_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/api\/v1\/circuit-terminals$/,
  respond: () => ({
    status: 200,
    body: [
      {
        circuit_terminal_id: TERMINAL_A_ID,
        circuit_id: "circuit-1",
        circuit_name: "IGBK–NKST",
        bay_number: "Line 2",
        breaker_number: "L23",
        substation_id: NKST_ID,
        substation_mnemonic: "NKST",
        substation_official_name: "NKST Substation",
        voltage_level_id: 1,
        voltage_level_label: "500kV",
      },
      {
        circuit_terminal_id: TERMINAL_B_ID,
        circuit_id: "circuit-1",
        circuit_name: "IGBK–NKST",
        bay_number: "Line 2",
        breaker_number: "L22",
        substation_id: PKLG_ID,
        substation_mnemonic: "PKLG",
        substation_official_name: "PKLG Substation",
        voltage_level_id: 1,
        voltage_level_label: "500kV",
      },
    ],
  }),
};

const SNAPSHOT_SUMMARY_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/api\/v1\/network-model\/verification\/snapshot-summary$/,
  respond: () => ({
    status: 200,
    body: {
      topology_version_id: "topo-1",
      topology_version_status: "Current",
      load_snapshot_id: "snap-1",
      load_snapshot_status: "Current",
      import_date: null,
      bus_count: 4,
      branch_count: 2,
      transformer_count: 0,
      load_count: 0,
      generator_count: 0,
    },
  }),
};

const BASE_HANDLERS = [CIRCUIT_TERMINALS_HANDLER, SNAPSHOT_SUMMARY_HANDLER];

async function renderPageAndWaitForData() {
  renderWithProviders(<BoundaryPocketEvaluatorPage />, {
    route: "/network-model/boundary-pocket-evaluator",
  });
  await screen.findByLabelText("Select opening point NKST L23");
}

describe("BoundaryPocketEvaluatorPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the page title and the diagnostic notice", async () => {
    stubFetch(BASE_HANDLERS);
    await renderPageAndWaitForData();

    expect(screen.getByRole("heading", { name: "Boundary Pocket Evaluator" })).toBeInTheDocument();
    expect(
      screen.getByText("Diagnostic tool — results are transient and are not Scheme assignments."),
    ).toBeInTheDocument();
  });

  it("never shows Inside Substation or Rest-of-Grid Override controls", async () => {
    stubFetch(BASE_HANDLERS);
    await renderPageAndWaitForData();

    expect(screen.queryByText(/Inside Substation/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Rest-of-Grid Override/)).not.toBeInTheDocument();
  });

  it("lists Circuit Terminal candidates with substation, circuit, and opposite-substation context", async () => {
    stubFetch(BASE_HANDLERS);
    await renderPageAndWaitForData();

    const table = screen.getAllByRole("table")[0];
    const rows = within(table).getAllByRole("row");
    // header + 2 candidate rows
    expect(rows.length).toBe(3);
    expect(within(table).getAllByText("NKST").length).toBeGreaterThan(0);
    expect(within(table).getAllByText("PKLG").length).toBeGreaterThan(0);
  });

  it("selects a terminal, shows it in the review table, and prevents duplicate selection", async () => {
    stubFetch(BASE_HANDLERS);
    await renderPageAndWaitForData();
    const user = userEvent.setup();

    await user.click(screen.getByLabelText("Select opening point NKST L23"));

    expect(screen.getByText("Selected Opening Points (1)")).toBeInTheDocument();
    expect(screen.getByLabelText("Select opening point NKST L23")).toBeChecked();

    // Clicking again removes it (toggle), proving no duplicate can accumulate.
    await user.click(screen.getByLabelText("Select opening point NKST L23"));
    expect(screen.getByText("Selected Opening Points (0)")).toBeInTheDocument();
    expect(screen.getByText("No opening points selected yet.")).toBeInTheDocument();
  });

  it("removes a selected terminal via the review table's Remove action", async () => {
    stubFetch(BASE_HANDLERS);
    await renderPageAndWaitForData();
    const user = userEvent.setup();

    await user.click(screen.getByLabelText("Select opening point NKST L23"));
    expect(screen.getByText("Selected Opening Points (1)")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Remove" }));
    expect(screen.getByText("Selected Opening Points (0)")).toBeInTheDocument();
  });

  it("disables evaluation and explains why when no opening point is selected", async () => {
    stubFetch(BASE_HANDLERS);
    await renderPageAndWaitForData();

    expect(screen.getByRole("button", { name: "Evaluate Boundary" })).toBeDisabled();
    expect(
      screen.getByText("Select at least one opening point before evaluating."),
    ).toBeInTheDocument();
  });

  it("evaluates and renders a Boundary Effective result with isolated islands", async () => {
    let evaluationPayload: unknown = null;
    stubFetch([
      ...BASE_HANDLERS,
      {
        method: "POST",
        pattern: /\/api\/v1\/network-model\/boundary-pocket-evaluations$/,
        respond: (_url, init) => {
          evaluationPayload = init?.body ? JSON.parse(init.body as string) : null;
          return {
            status: 200,
            body: {
              topology_version_id: "topo-1",
              baseline_component_count: 1,
              baseline_main_grid_substation_count: 3,
              baseline_has_single_main_grid: true,
              post_opening_component_count: 2,
              is_boundary_effective: true,
              isolated_islands: [
                { substations: [{ substation_id: NKST_ID, substation_mnemonic: "NKST" }] },
              ],
              circuit_terminal_ids: [TERMINAL_A_ID],
              uncorrelated_circuit_terminal_ids: [],
              reason: "1 new isolated island formed relative to the Main Grid.",
            },
          };
        },
      },
    ]);
    await renderPageAndWaitForData();
    const user = userEvent.setup();

    await user.click(screen.getByLabelText("Select opening point NKST L23"));
    await user.click(screen.getByRole("button", { name: "Evaluate Boundary" }));

    await waitFor(() => {
      expect(evaluationPayload).toMatchObject({
        circuit_terminal_ids: [TERMINAL_A_ID],
      });
    });

    await waitFor(() => {
      expect(screen.getByText("Boundary Effective")).toBeInTheDocument();
    });
    expect(screen.getByText("Isolated Islands (1)")).toBeInTheDocument();
    const islandsList = screen.getByText("Isolated Islands (1)").parentElement as HTMLElement;
    expect(within(islandsList).getByText("NKST")).toBeInTheDocument();
    expect(
      screen.getByText("Baseline Main Grid: one connected Main Grid (3 substations)"),
    ).toBeInTheDocument();
  });

  it("evaluates and renders a Boundary Ineffective result with the backend's explanatory reason", async () => {
    stubFetch([
      ...BASE_HANDLERS,
      {
        method: "POST",
        pattern: /\/api\/v1\/network-model\/boundary-pocket-evaluations$/,
        respond: () => ({
          status: 200,
          body: {
            topology_version_id: "topo-1",
            baseline_component_count: 1,
            baseline_main_grid_substation_count: 3,
            baseline_has_single_main_grid: true,
            post_opening_component_count: 1,
            is_boundary_effective: false,
            isolated_islands: [],
            circuit_terminal_ids: [],
            uncorrelated_circuit_terminal_ids: [],
            reason:
              "No new island was formed — the selected opening points do not disconnect any " +
              "part of the Main Grid under the current snapshot.",
          },
        }),
      },
    ]);
    await renderPageAndWaitForData();
    const user = userEvent.setup();

    await user.click(screen.getByLabelText("Select opening point NKST L23"));
    await user.click(screen.getByRole("button", { name: "Evaluate Boundary" }));

    await waitFor(() => {
      expect(screen.getByText("Boundary Ineffective")).toBeInTheDocument();
    });
    expect(
      screen.getByText(/do not disconnect any part of the Main Grid/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/cannot become a Scheme assignment in this state/),
    ).toBeInTheDocument();
  });

  it("reports uncorrelated opening points without treating the request as an error", async () => {
    stubFetch([
      ...BASE_HANDLERS,
      {
        method: "POST",
        pattern: /\/api\/v1\/network-model\/boundary-pocket-evaluations$/,
        respond: () => ({
          status: 200,
          body: {
            topology_version_id: "topo-1",
            baseline_component_count: 1,
            baseline_main_grid_substation_count: 3,
            baseline_has_single_main_grid: true,
            post_opening_component_count: 1,
            is_boundary_effective: false,
            isolated_islands: [],
            circuit_terminal_ids: [TERMINAL_A_ID],
            uncorrelated_circuit_terminal_ids: [TERMINAL_A_ID],
            reason: "No new island was formed.",
          },
        }),
      },
    ]);
    await renderPageAndWaitForData();
    const user = userEvent.setup();

    await user.click(screen.getByLabelText("Select opening point NKST L23"));
    await user.click(screen.getByRole("button", { name: "Evaluate Boundary" }));

    await waitFor(() => {
      expect(screen.getByText(/Uncorrelated opening points/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Uncorrelated opening points.*NKST/)).toBeInTheDocument();
  });

  it("renders a safe backend error message", async () => {
    stubFetch([
      ...BASE_HANDLERS,
      {
        method: "POST",
        pattern: /\/api\/v1\/network-model\/boundary-pocket-evaluations$/,
        respond: () => ({
          status: 404,
          body: {
            detail: {
              code: "not_found",
              message: "CircuitTerminal 00000000-0000-0000-0000-000000000000 not found",
            },
          },
        }),
      },
    ]);
    await renderPageAndWaitForData();
    const user = userEvent.setup();

    await user.click(screen.getByLabelText("Select opening point NKST L23"));
    await user.click(screen.getByRole("button", { name: "Evaluate Boundary" }));

    await waitFor(() => {
      expect(
        screen.getByText(
          "Evaluation Error: CircuitTerminal 00000000-0000-0000-0000-000000000000 not found",
        ),
      ).toBeInTheDocument();
    });
  });

  it("supports add, remove, and re-evaluate without showing stale results", async () => {
    let callCount = 0;
    stubFetch([
      ...BASE_HANDLERS,
      {
        method: "POST",
        pattern: /\/api\/v1\/network-model\/boundary-pocket-evaluations$/,
        respond: () => {
          callCount += 1;
          return {
            status: 200,
            body: {
              topology_version_id: "topo-1",
              baseline_component_count: 1,
              baseline_main_grid_substation_count: 3,
              baseline_has_single_main_grid: true,
              post_opening_component_count: callCount > 1 ? 2 : 1,
              is_boundary_effective: callCount > 1,
              isolated_islands:
                callCount > 1
                  ? [{ substations: [{ substation_id: NKST_ID, substation_mnemonic: "NKST" }] }]
                  : [],
              circuit_terminal_ids: [],
              uncorrelated_circuit_terminal_ids: [],
              reason: callCount > 1 ? "1 new isolated island formed." : "No new island was formed.",
            },
          };
        },
      },
    ]);
    await renderPageAndWaitForData();
    const user = userEvent.setup();

    await user.click(screen.getByLabelText("Select opening point NKST L23"));
    await user.click(screen.getByRole("button", { name: "Evaluate Boundary" }));
    await waitFor(() => expect(screen.getByText("Boundary Ineffective")).toBeInTheDocument());

    // Selecting another opening point clears the stale result immediately.
    await user.click(screen.getByLabelText("Select opening point PKLG L22"));
    expect(screen.queryByText("Boundary Ineffective")).not.toBeInTheDocument();
    expect(screen.queryByText("Boundary Effective")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Evaluate Boundary" }));
    await waitFor(() => expect(screen.getByText("Boundary Effective")).toBeInTheDocument());
  });

  it("resets the diagnostic form", async () => {
    stubFetch([
      ...BASE_HANDLERS,
      {
        method: "POST",
        pattern: /\/api\/v1\/network-model\/boundary-pocket-evaluations$/,
        respond: () => ({
          status: 200,
          body: {
            topology_version_id: "topo-1",
            baseline_component_count: 1,
            baseline_main_grid_substation_count: 3,
            baseline_has_single_main_grid: true,
            post_opening_component_count: 1,
            is_boundary_effective: false,
            isolated_islands: [],
            circuit_terminal_ids: [TERMINAL_A_ID],
            uncorrelated_circuit_terminal_ids: [],
            reason: "No new island was formed.",
          },
        }),
      },
    ]);
    await renderPageAndWaitForData();
    const user = userEvent.setup();

    await user.click(screen.getByLabelText("Select opening point NKST L23"));
    await user.click(screen.getByRole("button", { name: "Evaluate Boundary" }));
    await waitFor(() => expect(screen.getByText("Boundary Ineffective")).toBeInTheDocument());

    await user.click(screen.getByRole("button", { name: "Reset" }));

    expect(screen.getByText("Selected Opening Points (0)")).toBeInTheDocument();
    expect(screen.queryByText("Boundary Ineffective")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Evaluate Boundary" })).toBeDisabled();
  });

  it("requires authentication, mirroring every other Network Model diagnostic route", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={["/network-model/boundary-pocket-evaluator"]}>
            <Routes>
              <Route path="/login" element={<p>Login page</p>} />
              <Route
                path="/network-model/boundary-pocket-evaluator"
                element={
                  <ProtectedRoute>
                    <BoundaryPocketEvaluatorPage />
                  </ProtectedRoute>
                }
              />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    );

    await waitFor(() => {
      expect(screen.getByText("Login page")).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("heading", { name: "Boundary Pocket Evaluator" }),
    ).not.toBeInTheDocument();

    authStorage.clearToken();
  });
});
