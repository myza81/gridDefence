import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { SubstationListPage } from "../../src/modules/substation_registry/pages/SubstationListPage";
import { renderWithProviders, stubFetch } from "../testUtils";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "engineer1",
  display_name: "Engineer One",
  email: null,
  status: "active" as const,
};

const REFERENCE_DATA_HANDLERS = [
  {
    method: "GET",
    pattern: /\/reference-data\/voltage-levels$/,
    respond: () => ({
      status: 200,
      body: [{ voltage_level_id: 1, label: "500kV", nominal_kv: 500, sort_order: 1 }],
    }),
  },
  {
    method: "GET",
    pattern: /\/reference-data\/regions$/,
    respond: () => ({ status: 200, body: [{ region_id: 1, code: "NORTH", label: "Northern" }] }),
  },
  {
    method: "GET",
    pattern: /\/reference-data\/states$/,
    respond: () => ({ status: 200, body: [{ state_id: 1, code: "SEL", label: "Selangor" }] }),
  },
  {
    method: "GET",
    pattern: /\/reference-data\/grid-owners$/,
    respond: () => ({
      status: 200,
      body: [{ grid_owner_id: 1, code: "TNB", label: "Tenaga Nasional Berhad (TNB)" }],
    }),
  },
  {
    method: "GET",
    pattern: /\/reference-data\/operational-statuses$/,
    respond: () => ({
      status: 200,
      body: [
        { operational_status_id: 1, code: "ACTIVE", label: "Active", is_terminal: false },
        { operational_status_id: 2, code: "PLANNED", label: "Planned", is_terminal: false },
      ],
    }),
  },
];

function stubSession(myPermissions: string[]) {
  stubFetch([
    {
      method: "GET",
      pattern: /\/api\/v1\/users\/me$/,
      respond: () => ({ status: 200, body: CURRENT_USER }),
    },
    {
      method: "GET",
      pattern: new RegExp(`/api/v1/users/${CURRENT_USER.user_id}/roles$`),
      respond: () => ({
        status: 200,
        body: [
          {
            role: {
              role_id: "22222222-2222-2222-2222-222222222222",
              name: "Engineer",
              description: null,
              is_system_role: true,
              status: "active",
            },
            granted_at: "2026-01-01T00:00:00Z",
            permissions: myPermissions,
          },
        ],
      }),
    },
    {
      method: "GET",
      pattern: /\/api\/v1\/substations\?/,
      respond: () => ({
        status: 200,
        body: {
          items: [
            {
              substation_id: "33333333-3333-3333-3333-333333333333",
              mnemonic: "SUB1",
              official_name: "Substation One",
              voltage_level_id: 1,
              region_id: 1,
              state_id: 1,
              grid_owner_id: 1,
              operational_status_id: 1,
              psse_bus_number: null,
            },
          ],
          page: 1,
          page_size: 20,
          total: 1,
        },
      }),
    },
    ...REFERENCE_DATA_HANDLERS,
  ]);
}

describe("SubstationListPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders substation rows with reference data resolved to labels", async () => {
    authStorage.setToken("token");
    stubSession([]);

    renderWithProviders(<SubstationListPage />, { route: "/substations" });

    await waitFor(() => {
      expect(screen.getByText("SUB1")).toBeInTheDocument();
    });
    const row = screen.getByText("SUB1").closest("tr");
    expect(row).not.toBeNull();
    expect(within(row!).getByText("Substation One")).toBeInTheDocument();
    expect(within(row!).getByText("500kV")).toBeInTheDocument();
    expect(within(row!).getByText("Northern")).toBeInTheDocument();
    expect(within(row!).getByText("Active")).toBeInTheDocument();
  });

  it("does not show the create-substation link for a user without substation_registry.write", async () => {
    authStorage.setToken("token");
    stubSession([]);

    renderWithProviders(<SubstationListPage />, { route: "/substations" });

    await waitFor(() => {
      expect(screen.getByText("SUB1")).toBeInTheDocument();
    });
    expect(screen.queryByRole("link", { name: "Create substation" })).not.toBeInTheDocument();
  });

  it("shows the create-substation link for a user with substation_registry.write", async () => {
    authStorage.setToken("token");
    stubSession(["substation_registry.write"]);

    renderWithProviders(<SubstationListPage />, { route: "/substations" });

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "Create substation" })).toBeInTheDocument();
    });
  });
});
