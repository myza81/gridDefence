import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { FacilityDetailPage } from "../../src/modules/sensitive_customer_registry/pages/FacilityDetailPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

function renderDetailPage(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/sensitive-customer-registry/:facilityId" element={<FacilityDetailPage />} />
    </Routes>,
    { route },
  );
}

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "admin1",
  display_name: "Admin One",
  email: null,
  status: "active" as const,
};

const FACILITY_ID = "44444444-4444-4444-4444-444444444444";

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

function facilityDetail(overrides: Record<string, unknown> = {}) {
  return {
    id: FACILITY_ID,
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
        resolution: "RESOLVED",
        substation_id: "66666666-6666-6666-6666-666666666666",
        substation_mnemonic: "IGBK",
        substation_official_name: "IGBK Substation",
        voltage_level_label: "33kV",
        bay_label: "Transformer T1",
        side: "LV",
      },
    ],
    transformer_terminal_resolution: "RESOLVED",
    lifecycle_status: "ACTIVE",
    remarks: null,
    created_at: "2026-07-01T00:00:00Z",
    updated_at: "2026-07-01T00:00:00Z",
    created_by: CURRENT_USER,
    updated_by: CURRENT_USER,
    ...overrides,
  };
}

const AUDIT_LOG_EMPTY = { items: [], page: 1, page_size: 50, total: 0 };
const SECTORS = [
  { id: 1, code: "HEALTHCARE", label: "Healthcare", sort_order: 1, description: null, is_active: true },
];
const CLASSIFICATIONS = [
  { id: 1, code: "HIGH", label: "High", sort_order: 1, description: null, is_active: true },
];
const TERMINAL_IDENTITIES = [
  {
    transformer_terminal_id: "55555555-5555-5555-5555-555555555555",
    transformer_id: "77777777-7777-7777-7777-777777777777",
    generated_short_name: "T1",
    transformer_number: "1",
    side: "LV",
    breaker_number: "T12",
    substation_id: "66666666-6666-6666-6666-666666666666",
    substation_mnemonic: "IGBK",
    substation_official_name: "IGBK Substation",
    voltage_level_id: 1,
    voltage_level_label: "33kV",
  },
];

function baseHandlers(permissions: string[], detail = facilityDetail()): FetchHandler[] {
  return [
    ...sessionHandlers(permissions),
    {
      method: "GET",
      pattern: new RegExp(`/facilities/${FACILITY_ID}$`),
      respond: () => ({ status: 200, body: detail }),
    },
    {
      method: "GET",
      pattern: new RegExp(`/facilities/${FACILITY_ID}/audit-log`),
      respond: () => ({ status: 200, body: AUDIT_LOG_EMPTY }),
    },
    {
      method: "GET",
      pattern: /\/reference-data\/facility-sectors$/,
      respond: () => ({ status: 200, body: SECTORS }),
    },
    {
      method: "GET",
      pattern: /\/reference-data\/sensitivity-classifications$/,
      respond: () => ({ status: 200, body: CLASSIFICATIONS }),
    },
    {
      method: "GET",
      pattern: /\/transformer-terminals$/,
      respond: () => ({ status: 200, body: TERMINAL_IDENTITIES }),
    },
  ];
}

describe("FacilityDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders facility detail with resolved supply-point identity", async () => {
    authStorage.setToken("token");
    stubFetch(baseHandlers(["sensitive_customer_registry.read", "sensitive_customer_registry.write"]));

    renderDetailPage(`/sensitive-customer-registry/${FACILITY_ID}`);

    await waitFor(() => {
      expect(screen.getByRole("cell", { name: "IGBK" })).toBeInTheDocument();
    });
    expect(screen.getByRole("cell", { name: "33kV" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Transformer T1" })).toBeInTheDocument();
    expect(screen.getByText("ACTIVE")).toBeInTheDocument();
  });

  it("shows an unresolved-terminal notice, never a blank field, when the terminal cannot be resolved (Correction 4)", async () => {
    authStorage.setToken("token");
    stubFetch(
      baseHandlers(
        ["sensitive_customer_registry.read"],
        facilityDetail({
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
        }),
      ),
    );

    renderDetailPage(`/sensitive-customer-registry/${FACILITY_ID}`);

    await waitFor(() => {
      expect(screen.getByText("Terminal could not be resolved")).toBeInTheDocument();
    });
  });

  it("disables lifecycle action buttons until a reason is entered", async () => {
    authStorage.setToken("token");
    stubFetch(baseHandlers(["sensitive_customer_registry.read", "sensitive_customer_registry.write"]));

    renderDetailPage(`/sensitive-customer-registry/${FACILITY_ID}`);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Archive" })).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Archive" })).toBeDisabled();

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Lifecycle change reason"), "Facility closed");
    expect(screen.getByRole("button", { name: "Archive" })).toBeEnabled();
  });

  it("archives the facility and refetches the updated status", async () => {
    authStorage.setToken("token");
    let archiveCalled = false;
    stubFetch([
      ...baseHandlers(["sensitive_customer_registry.read", "sensitive_customer_registry.write"]),
      {
        method: "POST",
        pattern: new RegExp(`/facilities/${FACILITY_ID}/archive`),
        respond: () => {
          archiveCalled = true;
          return { status: 200, body: facilityDetail({ lifecycle_status: "ARCHIVED" }) };
        },
      },
    ]);

    renderDetailPage(`/sensitive-customer-registry/${FACILITY_ID}`);

    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Archive" })).toBeInTheDocument();
    });
    await user.type(screen.getByLabelText("Lifecycle change reason"), "Facility closed");
    await user.click(screen.getByRole("button", { name: "Archive" }));

    await waitFor(() => {
      expect(archiveCalled).toBe(true);
    });
  });

  it("hides the edit form and lifecycle actions entirely once entered in error", async () => {
    authStorage.setToken("token");
    stubFetch(
      baseHandlers(
        ["sensitive_customer_registry.read", "sensitive_customer_registry.write"],
        facilityDetail({ lifecycle_status: "ENTERED_IN_ERROR" }),
      ),
    );

    renderDetailPage(`/sensitive-customer-registry/${FACILITY_ID}`);

    await waitFor(() => {
      expect(
        screen.getByText(/entered in error and is permanently terminal/),
      ).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Archive" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Mark Entered in Error" })).not.toBeInTheDocument();
  });

  it("requires a reason before saving a changed Transformer Terminal set, and sends it to PUT .../terminals", async () => {
    authStorage.setToken("token");
    let putBody: Record<string, unknown> | undefined;
    stubFetch([
      ...baseHandlers(["sensitive_customer_registry.read", "sensitive_customer_registry.write"]),
      {
        method: "PUT",
        pattern: new RegExp(`/facilities/${FACILITY_ID}/terminals`),
        respond: (_url, init) => {
          putBody = JSON.parse(init?.body as string);
          return { status: 200, body: facilityDetail({ transformer_terminals: [] }) };
        },
      },
    ]);

    renderDetailPage(`/sensitive-customer-registry/${FACILITY_ID}`);

    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Save Transformer Terminal(s)" })).toBeInTheDocument();
    });
    // Deselect the only currently-associated terminal — the set changes,
    // so Save must stay disabled until a reason is entered.
    const checkbox = screen.getByRole("checkbox", { name: "IGBK | 33kV | Transformer T1 (LV)" });
    await user.click(checkbox);
    expect(screen.getByRole("button", { name: "Save Transformer Terminal(s)" })).toBeDisabled();

    await user.type(
      screen.getByLabelText(
        "Change reason (required if changing the Transformer Terminal association(s))",
      ),
      "Supply point decommissioned",
    );
    expect(screen.getByRole("button", { name: "Save Transformer Terminal(s)" })).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Save Transformer Terminal(s)" }));

    await waitFor(() => {
      expect(putBody).toBeDefined();
    });
    expect(putBody?.transformer_terminal_ids).toEqual([]);
    expect(putBody?.change_reason).toBe("Supply point decommissioned");
  });

  it("shows no lifecycle or edit controls for a read-only (Engineer-tier) user", async () => {
    authStorage.setToken("token");
    stubFetch(baseHandlers(["sensitive_customer_registry.read"]));

    renderDetailPage(`/sensitive-customer-registry/${FACILITY_ID}`);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: /Hospital Kuala Lumpur/ })).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Archive" })).not.toBeInTheDocument();
  });
});
