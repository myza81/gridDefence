import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { SubstationDetailPage } from "../../src/modules/substation_registry/pages/SubstationDetailPage";
import { renderWithProviders, stubFetch } from "../testUtils";

const SUBSTATION_ID = "33333333-3333-3333-3333-333333333333";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "admin",
  display_name: "System Administrator",
  email: null,
  status: "active" as const,
};

const SUBSTATION_DETAIL = {
  substation_id: SUBSTATION_ID,
  mnemonic: "SUB1",
  official_name: "Substation One",
  voltage_level_id: 1,
  region_id: 1,
  state_id: 1,
  grid_owner_id: 1,
  operational_status_id: 2, // PLANNED
  psse_bus_number: null,
  latitude: null,
  longitude: null,
  commissioned_date: null,
  remarks: null,
  created_at: "2026-07-02T00:00:00Z",
  updated_at: "2026-07-02T00:00:00Z",
  created_by: CURRENT_USER,
  updated_by: CURRENT_USER,
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
        {
          operational_status_id: 5,
          code: "DECOMMISSIONED",
          label: "Decommissioned",
          is_terminal: false,
        },
      ],
    }),
  },
];

function renderDetailPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/substations/:substationId" element={<SubstationDetailPage />} />
    </Routes>,
    { route: `/substations/${SUBSTATION_ID}` },
  );
}

describe("SubstationDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("hides the edit and status-change forms for a user without substation_registry.write", async () => {
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
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: SUBSTATION_DETAIL }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByText("Substation One")).toBeInTheDocument();
    });
    expect(screen.queryByRole("heading", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Change status" })).not.toBeInTheDocument();
  });

  it("surfaces the backend's rejection message when an illegal status transition is attempted", async () => {
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
        respond: () => ({
          status: 200,
          body: [
            {
              role: {
                role_id: "role-1",
                name: "Administrator",
                description: null,
                is_system_role: true,
                status: "active",
              },
              granted_at: "2026-01-01T00:00:00Z",
              permissions: ["substation_registry.write"],
            },
          ],
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: SUBSTATION_DETAIL }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
      {
        method: "POST",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/status$`),
        respond: () => ({
          status: 400,
          body: {
            detail: {
              code: "validation_error",
              message:
                "Operational status cannot transition from 'PLANNED' to 'DECOMMISSIONED' — this is not a defined transition (substation-registry.md §10).",
            },
          },
        }),
      },
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Change status" })).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("New status"), "5");
    await user.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() => {
      expect(
        screen.getByText(
          "Operational status cannot transition from 'PLANNED' to 'DECOMMISSIONED' — this is not a defined transition (substation-registry.md §10).",
        ),
      ).toBeInTheDocument();
    });
  });

  it("lets a user with substation_registry.write submit an edit", async () => {
    authStorage.setToken("token");
    let updatePayload: unknown = null;
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
                role_id: "role-1",
                name: "Administrator",
                description: null,
                is_system_role: true,
                status: "active",
              },
              granted_at: "2026-01-01T00:00:00Z",
              permissions: ["substation_registry.write"],
            },
          ],
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: SUBSTATION_DETAIL }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
      {
        method: "PATCH",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: (_url, init) => {
          updatePayload = init?.body ? JSON.parse(init.body as string) : null;
          return { status: 200, body: { ...SUBSTATION_DETAIL, official_name: "Renamed" } };
        },
      },
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Edit" })).toBeInTheDocument();
    });

    const user = userEvent.setup();
    const nameInput = screen.getByLabelText("Official name");
    await user.clear(nameInput);
    await user.type(nameInput, "Renamed");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(updatePayload).toMatchObject({ official_name: "Renamed" });
    });
  });
});
