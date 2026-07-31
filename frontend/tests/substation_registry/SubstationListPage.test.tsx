import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
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
    pattern: /\/reference-data\/gm-zones$/,
    respond: () => ({
      status: 200,
      body: [{ gm_zone_id: 1, code: "KEDP", label: "Alor Setar" }],
    }),
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
              region_id: 1,
              gm_zone_id: 1,
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
    {
      method: "GET",
      pattern: /\/api\/v1\/voltage-yards$/,
      respond: () => ({
        status: 200,
        body: [
          {
            voltage_yard_id: "55555555-5555-5555-5555-555555555555",
            substation_id: "33333333-3333-3333-3333-333333333333",
            substation_mnemonic: "SUB1",
            substation_official_name: "Substation One",
            voltage_level_id: 1,
            voltage_level_label: "500kV",
            display_label: "SUB1 — 500kV",
          },
        ],
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
    expect(within(row!).getByText("Northern")).toBeInTheDocument();
    expect(within(row!).getByText("Active")).toBeInTheDocument();
  });

  it("left-aligns every semantic column header with its column values", async () => {
    authStorage.setToken("token");
    stubSession([]);

    renderWithProviders(<SubstationListPage />, { route: "/substations" });

    await screen.findByText("SUB1");
    const headers = screen.getAllByRole("columnheader");
    expect(headers.map((h) => h.textContent)).toEqual([
      "Mnemonic",
      "Substation",
      "Voltage",
      "Region",
      "GM Zone",
      "Grid Owner",
      "Status",
    ]);
    // Every header is a semantic <th> left-aligned (not the default centred th),
    // so it sits on the same axis as its left-aligned body cells.
    for (const header of headers) {
      expect(header.tagName).toBe("TH");
      expect(header).toHaveStyle({ textAlign: "left" });
    }
  });

  it("labels the voltage column 'Voltage' and shows the compact grid-owner abbreviation", async () => {
    authStorage.setToken("token");
    stubSession([]);

    renderWithProviders(<SubstationListPage />, { route: "/substations" });

    await screen.findByText("SUB1");
    // Column renamed Switchyards -> Voltage (presentation only).
    expect(screen.getByRole("columnheader", { name: "Voltage" })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Switchyards" })).toBeNull();
    // Grid Owner shows the engineering abbreviation (code), not the full label.
    const row = screen.getByText("SUB1").closest("tr")!;
    expect(within(row).getByText("TNB")).toBeInTheDocument();
    expect(within(row).queryByText("Tenaga Nasional Berhad (TNB)")).toBeNull();
  });

  it("displays a substation's voltage yards, not a single legacy voltage level (ADR-009)", async () => {
    authStorage.setToken("token");
    stubSession([]);

    renderWithProviders(<SubstationListPage />, { route: "/substations" });

    await waitFor(() => {
      expect(screen.getByText("SUB1")).toBeInTheDocument();
    });
    const row = screen.getByText("SUB1").closest("tr");
    expect(row).not.toBeNull();
    expect(within(row!).getByText("500kV")).toBeInTheDocument();
  });

  it("joins multiple voltage yards for the same substation, e.g. 'PKLG: 275kV, 132kV'", async () => {
    authStorage.setToken("token");
    stubFetch([
      {
        method: "GET",
        pattern: /\/api\/v1\/users\/me$/,
        respond: () => ({ status: 200, body: CURRENT_USER }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/users/${CURRENT_USER.user_id}/roles$`),
        respond: () => ({ status: 200, body: [] }),
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
                mnemonic: "PKLG",
                official_name: "Pekan Lama",
                region_id: 1,
                gm_zone_id: 1,
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
      {
        method: "GET",
        pattern: /\/api\/v1\/voltage-yards$/,
        respond: () => ({
          status: 200,
          body: [
            {
              voltage_yard_id: "66666666-6666-6666-6666-666666666666",
              substation_id: "33333333-3333-3333-3333-333333333333",
              substation_mnemonic: "PKLG",
              substation_official_name: "Pekan Lama",
              voltage_level_id: 2,
              voltage_level_label: "275kV",
              display_label: "PKLG — 275kV",
            },
            {
              voltage_yard_id: "77777777-7777-7777-7777-777777777777",
              substation_id: "33333333-3333-3333-3333-333333333333",
              substation_mnemonic: "PKLG",
              substation_official_name: "Pekan Lama",
              voltage_level_id: 3,
              voltage_level_label: "132kV",
              display_label: "PKLG — 132kV",
            },
          ],
        }),
      },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderWithProviders(<SubstationListPage />, { route: "/substations" });

    await waitFor(() => {
      expect(screen.getByText("PKLG")).toBeInTheDocument();
    });
    const row = screen.getByText("PKLG").closest("tr");
    expect(row).not.toBeNull();
    expect(within(row!).getByText("275kV, 132kV")).toBeInTheDocument();
  });

  it("does not show the create-substation link for a user without substation_registry.write", async () => {
    authStorage.setToken("token");
    stubSession([]);

    renderWithProviders(<SubstationListPage />, { route: "/substations" });

    await waitFor(() => {
      expect(screen.getByText("SUB1")).toBeInTheDocument();
    });
    expect(screen.queryByRole("link", { name: "Register substation" })).not.toBeInTheDocument();
  });

  it("shows the register-substation link for a user with substation_registry.write", async () => {
    authStorage.setToken("token");
    stubSession(["substation_registry.write"]);

    renderWithProviders(<SubstationListPage />, { route: "/substations" });

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "Register substation" })).toBeInTheDocument();
    });
  });

  it("uses the mnemonic itself as the row's navigation link (no separate Open action)", async () => {
    authStorage.setToken("token");
    stubSession([]);

    renderWithProviders(<SubstationListPage />, { route: "/substations" });

    const link = await screen.findByRole("link", { name: "Open SUB1 Substation One" });
    // The link IS the mnemonic, and points at the existing detail route.
    expect(link).toHaveTextContent("SUB1");
    expect(link).toHaveAttribute("href", "/substations/33333333-3333-3333-3333-333333333333");
    // The generic "Open" column/action is gone.
    expect(screen.queryByText("Open")).toBeNull();
    expect(screen.queryByRole("columnheader", { name: "Open" })).toBeNull();
  });

  function renderListWithDetailRoute(route = "/substations") {
    return renderWithProviders(
      <Routes>
        <Route path="/substations" element={<SubstationListPage />} />
        <Route path="/substations/:substationId" element={<div>Detail workspace marker</div>} />
      </Routes>,
      { route },
    );
  }

  it("opens the detail page when the mnemonic link is clicked", async () => {
    authStorage.setToken("token");
    stubSession([]);
    const user = userEvent.setup();

    renderListWithDetailRoute();

    await user.click(await screen.findByRole("link", { name: "Open SUB1 Substation One" }));
    expect(await screen.findByText("Detail workspace marker")).toBeInTheDocument();
  });

  it("opens the detail page when the focused mnemonic link is activated with Enter", async () => {
    authStorage.setToken("token");
    stubSession([]);
    const user = userEvent.setup();

    renderListWithDetailRoute();

    const link = await screen.findByRole("link", { name: "Open SUB1 Substation One" });
    link.focus();
    expect(link).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(await screen.findByText("Detail workspace marker")).toBeInTheDocument();
  });

  function stubEmpty(myPermissions: string[], total: number) {
    stubFetch([
      { method: "GET", pattern: /\/api\/v1\/users\/me$/, respond: () => ({ status: 200, body: CURRENT_USER }) },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/users/${CURRENT_USER.user_id}/roles$`),
        respond: () => ({
          status: 200,
          body: [
            {
              role: { role_id: "r", name: "Engineer", description: null, is_system_role: true, status: "active" },
              granted_at: "2026-01-01T00:00:00Z",
              permissions: myPermissions,
            },
          ],
        }),
      },
      {
        method: "GET",
        pattern: /\/api\/v1\/substations\?/,
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 20, total } }),
      },
      { method: "GET", pattern: /\/api\/v1\/voltage-yards$/, respond: () => ({ status: 200, body: [] }) },
      ...REFERENCE_DATA_HANDLERS,
    ]);
  }

  it("distinguishes an empty registry from an empty filtered result", async () => {
    authStorage.setToken("token");
    stubEmpty(["substation_registry.write"], 0);

    const { unmount } = renderWithProviders(<SubstationListPage />, { route: "/substations" });
    expect(await screen.findByText("No substations registered")).toBeInTheDocument();
    unmount();

    stubEmpty(["substation_registry.write"], 0);
    renderWithProviders(<SubstationListPage />, { route: "/substations?status=1" });
    expect(await screen.findByText("No substations match the current filters")).toBeInTheDocument();
  });

  it("shows an error state (not a blank page) when the registry request fails", async () => {
    authStorage.setToken("token");
    stubFetch([
      { method: "GET", pattern: /\/api\/v1\/users\/me$/, respond: () => ({ status: 200, body: CURRENT_USER }) },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/users/${CURRENT_USER.user_id}/roles$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: /\/api\/v1\/substations\?/,
        respond: () => ({ status: 500, body: { detail: { code: "app_error", message: "Registry unavailable." } } }),
      },
      { method: "GET", pattern: /\/api\/v1\/voltage-yards$/, respond: () => ({ status: 200, body: [] }) },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderWithProviders(<SubstationListPage />, { route: "/substations" });

    expect(await screen.findByText("Couldn't load substations")).toBeInTheDocument();
    expect(screen.getByText("Registry unavailable.")).toBeInTheDocument();
  });
});
