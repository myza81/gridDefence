import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { FacilityListPage } from "../../src/modules/sensitive_customer_registry/pages/FacilityListPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "admin1",
  display_name: "Admin One",
  email: null,
  status: "active" as const,
};

const FACILITY_SECTORS_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/reference-data\/facility-sectors$/,
  respond: () => ({
    status: 200,
    body: [
      { id: 1, code: "HEALTHCARE", label: "Healthcare", sort_order: 1, description: null, is_active: true },
    ],
  }),
};

const SENSITIVITY_CLASSIFICATIONS_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/reference-data\/sensitivity-classifications$/,
  respond: () => ({
    status: 200,
    body: [
      { id: 1, code: "HIGH", label: "High", sort_order: 1, description: null, is_active: true },
    ],
  }),
};

const SUMMARY_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/facilities\/summary$/,
  respond: () => ({
    status: 200,
    body: {
      active_count: 1,
      archived_count: 0,
      entered_in_error_count: 0,
      by_sector: { HEALTHCARE: 1 },
      by_sensitivity_classification: { HIGH: 1 },
      unresolved_terminal_count: 0,
    },
  }),
};

function sessionHandlers(permissions: string[]): FetchHandler[] {
  return [
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
              name: "Administrator",
              description: null,
              is_system_role: true,
              status: "active",
            },
            granted_at: "2026-01-01T00:00:00Z",
            permissions,
          },
        ],
      }),
    },
  ];
}

const FACILITY_ROW = {
  id: "44444444-4444-4444-4444-444444444444",
  name: "Hospital Kuala Lumpur",
  facility_sector: {
    id: 1,
    code: "HEALTHCARE",
    label: "Healthcare",
    sort_order: 1,
    description: null,
    is_active: true,
  },
  sensitivity_classification: {
    id: 1,
    code: "HIGH",
    label: "High",
    sort_order: 1,
    description: null,
    is_active: true,
  },
  transformer_terminals: [
    {
      transformer_terminal_id: "55555555-5555-5555-5555-555555555555",
      resolution: "RESOLVED" as const,
      substation_id: "66666666-6666-6666-6666-666666666666",
      substation_mnemonic: "IGBK",
      substation_official_name: "Ipoh Garden Substation",
      voltage_level_label: "33kV",
      bay_label: "Transformer T1",
      side: "LV",
    },
  ],
  transformer_terminal_resolution: "RESOLVED" as const,
  lifecycle_status: "ACTIVE" as const,
  updated_at: "2026-07-10T00:00:00Z",
};

function stubSessionWithOneRecord(permissions: string[]) {
  stubFetch([
    ...sessionHandlers(permissions),
    FACILITY_SECTORS_HANDLER,
    SENSITIVITY_CLASSIFICATIONS_HANDLER,
    SUMMARY_HANDLER,
    {
      method: "GET",
      pattern: /\/api\/v1\/sensitive-customer-registry\/facilities\?/,
      respond: () => ({
        status: 200,
        body: { items: [FACILITY_ROW], page: 1, page_size: 20, total: 1 },
      }),
    },
  ]);
}

describe("FacilityListPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders facility rows with resolved supply-point identity", async () => {
    authStorage.setToken("token");
    stubSessionWithOneRecord(["sensitive_customer_registry.read", "sensitive_customer_registry.write"]);

    renderWithProviders(<FacilityListPage />, { route: "/sensitive-customer-registry" });

    await waitFor(() => {
      expect(screen.getByRole("cell", { name: "Hospital Kuala Lumpur" })).toBeInTheDocument();
    });
    const row = screen.getByRole("cell", { name: "Hospital Kuala Lumpur" }).closest("tr");
    expect(row).not.toBeNull();
    expect(within(row!).getByText("IGBK | 33kV | Transformer T1 (LV)")).toBeInTheDocument();
    expect(within(row!).getByText("Healthcare")).toBeInTheDocument();
  });

  it("shows the summary strip with active/archived/entered-in-error counts", async () => {
    authStorage.setToken("token");
    stubSessionWithOneRecord(["sensitive_customer_registry.read"]);

    renderWithProviders(<FacilityListPage />, { route: "/sensitive-customer-registry" });

    await waitFor(() => {
      expect(screen.getByText("Active: 1")).toBeInTheDocument();
    });
    expect(screen.getByText("Archived: 0")).toBeInTheDocument();
    expect(screen.getByText("Entered in Error: 0")).toBeInTheDocument();
  });

  it("shows a primary Add Sensitive Facility action to a user with write permission", async () => {
    authStorage.setToken("token");
    stubSessionWithOneRecord(["sensitive_customer_registry.read", "sensitive_customer_registry.write"]);

    renderWithProviders(<FacilityListPage />, { route: "/sensitive-customer-registry" });

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "Add Sensitive Facility" })).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "Add Sensitive Facility" })).toHaveAttribute(
      "href",
      "/sensitive-customer-registry/new",
    );
  });

  it("explains, rather than silently hiding, why the create action is unavailable to a read-only (Engineer-tier) user", async () => {
    // Corrected permission model (Correction 1) — Engineer holds `.read`
    // only, never `.write`. This reproduces that session shape exactly.
    authStorage.setToken("token");
    stubSessionWithOneRecord(["sensitive_customer_registry.read"]);

    renderWithProviders(<FacilityListPage />, { route: "/sensitive-customer-registry" });

    await waitFor(() => {
      expect(screen.getByText("Hospital Kuala Lumpur")).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("link", { name: "Add Sensitive Facility" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Adding sensitive facility records requires administrator privileges."),
    ).toBeInTheDocument();
  });

  it("shows an unresolved-terminal explanation instead of a blank cell (Correction 4)", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["sensitive_customer_registry.read"]),
      FACILITY_SECTORS_HANDLER,
      SENSITIVITY_CLASSIFICATIONS_HANDLER,
      SUMMARY_HANDLER,
      {
        method: "GET",
        pattern: /\/api\/v1\/sensitive-customer-registry\/facilities\?/,
        respond: () => ({
          status: 200,
          body: {
            items: [
              {
                ...FACILITY_ROW,
                transformer_terminals: [
                  {
                    transformer_terminal_id: "55555555-5555-5555-5555-555555555555",
                    resolution: "UNRESOLVED",
                    substation_id: null,
                    substation_mnemonic: null,
                    substation_official_name: null,
                    voltage_level_label: null,
                    bay_label: null,
                    side: null,
                  },
                ],
                transformer_terminal_resolution: "UNRESOLVED",
              },
            ],
            page: 1,
            page_size: 20,
            total: 1,
          },
        }),
      },
    ]);

    renderWithProviders(<FacilityListPage />, { route: "/sensitive-customer-registry" });

    await waitFor(() => {
      expect(screen.getByRole("cell", { name: "Hospital Kuala Lumpur" })).toBeInTheDocument();
    });
    const row = screen.getByRole("cell", { name: "Hospital Kuala Lumpur" }).closest("tr");
    expect(row).not.toBeNull();
    expect(within(row!).getByText("Terminal could not be resolved")).toBeInTheDocument();
  });
});
