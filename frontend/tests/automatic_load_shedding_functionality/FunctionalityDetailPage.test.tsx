import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { FunctionalityDetailPage } from "../../src/modules/automatic_load_shedding_functionality/pages/FunctionalityDetailPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

function renderDetailPage(route: string) {
  return renderWithProviders(
    <Routes>
      <Route
        path="/automatic-load-shedding-functionality/:functionalityId"
        element={<FunctionalityDetailPage />}
      />
    </Routes>,
    { route },
  );
}

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "engineer1",
  display_name: "Engineer One",
  email: null,
  status: "active" as const,
};

const FUNCTIONALITY_ID = "44444444-4444-4444-4444-444444444444";

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
              name: "Engineer",
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

function detailBody(status: string) {
  return {
    id: FUNCTIONALITY_ID,
    target_type: "CIRCUIT_TERMINAL",
    circuit_terminal_id: "55555555-5555-5555-5555-555555555555",
    transformer_terminal_id: null,
    substation_id: "22222222-2222-2222-2222-222222222222",
    substation_mnemonic: "PKLG",
    substation_official_name: "Pekan Lama",
    voltage_level_label: "500kV",
    bay_label: "L11",
    ufls_function: true,
    uvls_function: false,
    status,
    relay_make: null,
    relay_model: null,
    remarks: null,
    created_at: "2026-07-09T00:00:00Z",
    updated_at: "2026-07-09T00:00:00Z",
    created_by: null,
    updated_by: null,
  };
}

function auditLogHandler(total: number): FetchHandler {
  return {
    method: "GET",
    pattern: new RegExp(`/automatic-load-shedding-functionality/${FUNCTIONALITY_ID}/audit-log`),
    respond: () => ({
      status: 200,
      body: {
        items: Array.from({ length: total }, (_, i) => ({
          log_id: i + 1,
          field_name: "lifecycle_status",
          old_value: null,
          new_value: "ACTIVE",
          changed_at: "2026-07-09T00:00:00Z",
          changed_by: null,
          change_reason: null,
        })),
        page: 1,
        page_size: 50,
        total,
      },
    }),
  };
}

describe("FunctionalityDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders detail fields", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers([]),
      {
        method: "GET",
        pattern: new RegExp(`/automatic-load-shedding-functionality/${FUNCTIONALITY_ID}$`),
        respond: () => ({ status: 200, body: detailBody("AVAILABLE") }),
      },
      auditLogHandler(0),
    ]);

    renderDetailPage(`/automatic-load-shedding-functionality/${FUNCTIONALITY_ID}`);

    await waitFor(() => {
      expect(screen.getByText("PKLG — Pekan Lama")).toBeInTheDocument();
    });
    expect(screen.getByText("No changes recorded yet.")).toBeInTheDocument();
    // Full engineering identity, not just substation/voltage separately.
    expect(
      screen.getByRole("heading", { name: "Automatic Load Shedding Functionality — PKLG | 500kV | L11" }),
    ).toBeInTheDocument();
    // The audit/history section must also show the same full identity.
    expect(
      screen.getByRole("heading", { name: "Audit log — PKLG | 500kV | L11" }),
    ).toBeInTheDocument();
  });

  it("does not show the lifecycle (decommission) action to a user without write permission", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers([]),
      {
        method: "GET",
        pattern: new RegExp(`/automatic-load-shedding-functionality/${FUNCTIONALITY_ID}$`),
        respond: () => ({ status: 200, body: detailBody("AVAILABLE") }),
      },
      auditLogHandler(0),
    ]);

    renderDetailPage(`/automatic-load-shedding-functionality/${FUNCTIONALITY_ID}`);

    await waitFor(() => {
      expect(screen.getByText("AVAILABLE")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Decommission" })).not.toBeInTheDocument();
  });

  it("shows Assigned status for a record referenced by an active scheme (backend-computed)", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers([]),
      {
        method: "GET",
        pattern: new RegExp(`/automatic-load-shedding-functionality/${FUNCTIONALITY_ID}$`),
        respond: () => ({ status: 200, body: detailBody("ASSIGNED") }),
      },
      auditLogHandler(0),
    ]);

    renderDetailPage(`/automatic-load-shedding-functionality/${FUNCTIONALITY_ID}`);

    await waitFor(() => {
      expect(screen.getByText("ASSIGNED")).toBeInTheDocument();
    });
  });

  it("requires a decommission reason before the Decommission button is enabled", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["automatic_load_shedding_functionality.write"]),
      {
        method: "GET",
        pattern: new RegExp(`/automatic-load-shedding-functionality/${FUNCTIONALITY_ID}$`),
        respond: () => ({ status: 200, body: detailBody("AVAILABLE") }),
      },
      auditLogHandler(0),
    ]);

    renderDetailPage(`/automatic-load-shedding-functionality/${FUNCTIONALITY_ID}`);

    await screen.findByRole("button", { name: "Decommission" });
    expect(screen.getByRole("button", { name: "Decommission" })).toBeDisabled();

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Decommission reason"), "Bay dismantled");
    expect(screen.getByRole("button", { name: "Decommission" })).toBeEnabled();
  });

  it("hides lifecycle actions and the edit form for a decommissioned record", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["automatic_load_shedding_functionality.write"]),
      {
        method: "GET",
        pattern: new RegExp(`/automatic-load-shedding-functionality/${FUNCTIONALITY_ID}$`),
        respond: () => ({ status: 200, body: detailBody("DECOMMISSIONED") }),
      },
      auditLogHandler(2),
    ]);

    renderDetailPage(`/automatic-load-shedding-functionality/${FUNCTIONALITY_ID}`);

    await waitFor(() => {
      expect(screen.getByText("DECOMMISSIONED")).toBeInTheDocument();
    });
    expect(
      screen.getByText("This record is decommissioned and cannot be edited."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Decommission" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
  });
});
