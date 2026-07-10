import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { FunctionalityListPage } from "../../src/modules/automatic_load_shedding_functionality/pages/FunctionalityListPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "engineer1",
  display_name: "Engineer One",
  email: null,
  status: "active" as const,
};

const REFERENCE_DATA_HANDLERS: FetchHandler[] = [
  {
    method: "GET",
    pattern: /\/reference-data\/voltage-levels$/,
    respond: () => ({
      status: 200,
      body: [{ voltage_level_id: 1, label: "500kV", nominal_kv: 500, sort_order: 1 }],
    }),
  },
  { method: "GET", pattern: /\/reference-data\/regions$/, respond: () => ({ status: 200, body: [] }) },
  { method: "GET", pattern: /\/reference-data\/states$/, respond: () => ({ status: 200, body: [] }) },
  {
    method: "GET",
    pattern: /\/reference-data\/grid-owners$/,
    respond: () => ({ status: 200, body: [] }),
  },
  {
    method: "GET",
    pattern: /\/reference-data\/operational-statuses$/,
    respond: () => ({ status: 200, body: [] }),
  },
  {
    method: "GET",
    pattern: /\/reference-data\/line-types$/,
    respond: () => ({ status: 200, body: [] }),
  },
];

const SUBSTATION_OPTIONS_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/api\/v1\/substations/,
  respond: () => ({
    status: 200,
    body: {
      items: [
        {
          substation_id: "22222222-2222-2222-2222-222222222222",
          mnemonic: "PKLG",
          official_name: "Pekan Lama",
        },
      ],
      page: 1,
      page_size: 500,
      total: 1,
    },
  }),
};

const SESSION_HANDLERS = (myPermissions: string[]): FetchHandler[] => [
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
            role_id: "33333333-3333-3333-3333-333333333333",
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
];

function stubSessionWithOneRecord(myPermissions: string[]) {
  stubFetch([
    ...SESSION_HANDLERS(myPermissions),
    SUBSTATION_OPTIONS_HANDLER,
    {
      method: "GET",
      pattern: /\/api\/v1\/automatic-load-shedding-functionality\?/,
      respond: () => ({
        status: 200,
        body: {
          items: [
            {
              id: "44444444-4444-4444-4444-444444444444",
              target_type: "CIRCUIT_TERMINAL",
              circuit_terminal_id: "55555555-5555-5555-5555-555555555555",
              transformer_terminal_id: null,
              substation_id: "22222222-2222-2222-2222-222222222222",
              substation_mnemonic: "PKLG",
              voltage_level_label: "500kV",
              bay_label: "L11",
              ufls_function: true,
              uvls_function: false,
              status: "AVAILABLE",
              updated_at: "2026-07-09T00:00:00Z",
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

describe("FunctionalityListPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders functionality rows", async () => {
    authStorage.setToken("token");
    stubSessionWithOneRecord([]);

    renderWithProviders(<FunctionalityListPage />, {
      route: "/automatic-load-shedding-functionality",
    });

    await waitFor(() => {
      expect(screen.getByRole("cell", { name: "PKLG | 500kV | L11" })).toBeInTheDocument();
    });
    const row = screen.getByRole("cell", { name: "PKLG | 500kV | L11" }).closest("tr");
    expect(row).not.toBeNull();
    expect(within(row!).getByText("UFLS")).toBeInTheDocument();
    expect(within(row!).getByText("AVAILABLE")).toBeInTheDocument();
  });

  it("displays two ambiguous terminals at the same substation and voltage level distinctly", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS([]),
      SUBSTATION_OPTIONS_HANDLER,
      {
        method: "GET",
        pattern: /\/api\/v1\/automatic-load-shedding-functionality\?/,
        respond: () => ({
          status: 200,
          body: {
            items: [
              {
                id: "44444444-4444-4444-4444-444444444444",
                target_type: "TRANSFORMER_TERMINAL",
                circuit_terminal_id: null,
                transformer_terminal_id: "55555555-5555-5555-5555-555555555555",
                substation_id: "22222222-2222-2222-2222-222222222222",
                substation_mnemonic: "IGBK",
                voltage_level_label: "33kV",
                bay_label: "Transformer T1",
                ufls_function: true,
                uvls_function: false,
                status: "AVAILABLE",
                updated_at: "2026-07-09T00:00:00Z",
              },
              {
                id: "66666666-6666-6666-6666-666666666666",
                target_type: "TRANSFORMER_TERMINAL",
                circuit_terminal_id: null,
                transformer_terminal_id: "77777777-7777-7777-7777-777777777777",
                substation_id: "22222222-2222-2222-2222-222222222222",
                substation_mnemonic: "IGBK",
                voltage_level_label: "33kV",
                bay_label: "Transformer T2",
                ufls_function: true,
                uvls_function: false,
                status: "AVAILABLE",
                updated_at: "2026-07-09T00:00:00Z",
              },
            ],
            page: 1,
            page_size: 20,
            total: 2,
          },
        }),
      },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderWithProviders(<FunctionalityListPage />, {
      route: "/automatic-load-shedding-functionality",
    });

    await waitFor(() => {
      expect(
        screen.getByRole("cell", { name: "IGBK | 33kV | Transformer T1" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("cell", { name: "IGBK | 33kV | Transformer T2" })).toBeInTheDocument();
  });

  it("explains, rather than silently hiding, why the create action is unavailable to a user whose role has no write grant", async () => {
    // Reproduces the real incident, not a mocked happy path: an
    // authenticated user with a real role whose `permissions` array is
    // simply empty — exactly the shape returned by /users/{id}/roles when
    // a module's bootstrap.py was never run against the database and the
    // permission was consequently never granted to any role (see README's
    // "Seeding and Bootstrapping" incident notes). The UI must not go
    // silent in this case.
    authStorage.setToken("token");
    stubSessionWithOneRecord([]);

    renderWithProviders(<FunctionalityListPage />, {
      route: "/automatic-load-shedding-functionality",
    });

    await waitFor(() => {
      expect(screen.getByRole("cell", { name: "PKLG | 500kV | L11" })).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("link", { name: "Add Functionality Record" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "Adding functionality records requires automatic load shedding functionality write permission.",
      ),
    ).toBeInTheDocument();
  });

  it("shows a primary Add Functionality Record action to a user with write permission, linking to the create page", async () => {
    authStorage.setToken("token");
    stubSessionWithOneRecord(["automatic_load_shedding_functionality.write"]);

    renderWithProviders(<FunctionalityListPage />, {
      route: "/automatic-load-shedding-functionality",
    });

    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: "Add Functionality Record" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "Add Functionality Record" })).toHaveAttribute(
      "href",
      "/automatic-load-shedding-functionality/new",
    );
  });

  it("shows an empty-state create action when no records match the current filters", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS(["automatic_load_shedding_functionality.write"]),
      SUBSTATION_OPTIONS_HANDLER,
      {
        method: "GET",
        pattern: /\/api\/v1\/automatic-load-shedding-functionality\?/,
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 20, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderWithProviders(<FunctionalityListPage />, {
      route: "/automatic-load-shedding-functionality",
    });

    await waitFor(() => {
      expect(
        screen.getByText("No functionality records match your filters."),
      ).toBeInTheDocument();
    });
    const emptyStateLinks = await screen.findAllByRole("link", {
      name: "Add Functionality Record",
    });
    expect(emptyStateLinks.length).toBeGreaterThan(0);
    for (const link of emptyStateLinks) {
      expect(link).toHaveAttribute("href", "/automatic-load-shedding-functionality/new");
    }
  });

  it("shows a read-only explanation, not a create action, in the empty state for a Viewer-tier (read-only) user", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS(["automatic_load_shedding_functionality.read"]),
      SUBSTATION_OPTIONS_HANDLER,
      {
        method: "GET",
        pattern: /\/api\/v1\/automatic-load-shedding-functionality\?/,
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 20, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderWithProviders(<FunctionalityListPage />, {
      route: "/automatic-load-shedding-functionality",
    });

    await waitFor(() => {
      expect(
        screen.getByText("No functionality records match your filters."),
      ).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("link", { name: "Add Functionality Record" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/You do not have permission to add functionality records\./),
    ).toBeInTheDocument();
  });

  it("re-fetches with the substation filter applied when changed", async () => {
    authStorage.setToken("token");
    let lastUrl = "";
    stubFetch([
      ...SESSION_HANDLERS([]),
      SUBSTATION_OPTIONS_HANDLER,
      {
        method: "GET",
        pattern: /\/api\/v1\/automatic-load-shedding-functionality\?/,
        respond: (url) => {
          lastUrl = url;
          return { status: 200, body: { items: [], page: 1, page_size: 20, total: 0 } };
        },
      },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderWithProviders(<FunctionalityListPage />, {
      route: "/automatic-load-shedding-functionality",
    });

    await screen.findByRole("option", { name: "PKLG" });
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Filter by substation"), [
      "22222222-2222-2222-2222-222222222222",
    ]);

    await waitFor(() => {
      expect(lastUrl).toContain("substation_id=22222222-2222-2222-2222-222222222222");
    });
  });
});
