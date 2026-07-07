import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { PsseEquipmentTopologyMapPage } from "../../src/modules/psse_integration/pages/PsseEquipmentTopologyMapPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "engineer1",
  display_name: "Engineer One",
  email: null,
  status: "active" as const,
};

const TOPOLOGY_VERSION_ID = "44444444-4444-4444-4444-444444444444";

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
];

const DISCREPANCY_ENTRY = {
  map_id: "66666666-6666-6666-6666-666666666666",
  topology_version_id: TOPOLOGY_VERSION_ID,
  circuit_terminal_id: "77777777-7777-7777-7777-777777777777",
  circuit_id: "88888888-8888-8888-8888-888888888888",
  circuit_bay_number: "1",
  substation_mnemonic: "PKLG",
  topology_branch_id: 1,
  topology_transformer_id: null,
  match_outcome: "discrepancy",
  discrepancy_resolution: null,
  resolved_by: null,
  resolved_at: null,
  created_at: "2026-07-05T00:00:00Z",
};

function renderPage() {
  renderWithProviders(
    <Routes>
      <Route
        path="/psse-integration/topology-versions/:topologyVersionId/equipment-map"
        element={<PsseEquipmentTopologyMapPage />}
      />
    </Routes>,
    { route: `/psse-integration/topology-versions/${TOPOLOGY_VERSION_ID}/equipment-map` },
  );
}

describe("PsseEquipmentTopologyMapPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders a discrepancy row", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS([]),
      {
        method: "GET",
        pattern: new RegExp(
          `/api/v1/psse-integration/topology-versions/${TOPOLOGY_VERSION_ID}/equipment-map`,
        ),
        respond: () => ({
          status: 200,
          body: { items: [DISCREPANCY_ENTRY], page: 1, page_size: 50, total: 1 },
        }),
      },
    ]);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("discrepancy")).toBeInTheDocument();
    });
    expect(screen.getByText("PKLG")).toBeInTheDocument();
  });

  it("does not offer a resolve action to a user without psse_integration.import", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS([]),
      {
        method: "GET",
        pattern: new RegExp(
          `/api/v1/psse-integration/topology-versions/${TOPOLOGY_VERSION_ID}/equipment-map`,
        ),
        respond: () => ({
          status: 200,
          body: { items: [DISCREPANCY_ENTRY], page: 1, page_size: 50, total: 1 },
        }),
      },
    ]);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("discrepancy")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Accept" })).not.toBeInTheDocument();
  });

  it("resolves a discrepancy as accepted", async () => {
    authStorage.setToken("token");
    let resolvePayload: unknown = null;
    stubFetch([
      ...SESSION_HANDLERS(["psse_integration.import"]),
      {
        method: "GET",
        pattern: new RegExp(
          `/api/v1/psse-integration/topology-versions/${TOPOLOGY_VERSION_ID}/equipment-map`,
        ),
        respond: () => ({
          status: 200,
          body: { items: [DISCREPANCY_ENTRY], page: 1, page_size: 50, total: 1 },
        }),
      },
      {
        method: "POST",
        pattern: new RegExp(
          `/api/v1/psse-integration/equipment-map/${DISCREPANCY_ENTRY.map_id}/resolve$`,
        ),
        respond: (_url, init) => {
          resolvePayload = init?.body ? JSON.parse(init.body as string) : null;
          return {
            status: 200,
            body: { ...DISCREPANCY_ENTRY, discrepancy_resolution: "accepted" },
          };
        },
      },
    ]);

    renderPage();

    const user = userEvent.setup();
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Accept" })).toBeInTheDocument();
    });
    await user.type(
      screen.getByLabelText("Change reason for 1"),
      "Confirmed real network change",
    );
    await user.click(screen.getByRole("button", { name: "Accept" }));

    await waitFor(() => {
      expect(resolvePayload).toEqual({
        resolution: "accepted",
        change_reason: "Confirmed real network change",
      });
    });
  });
});
