import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { SubstationCreatePage } from "../../src/modules/substation_registry/pages/SubstationCreatePage";
import { renderWithProviders, stubFetch } from "../testUtils";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "admin",
  display_name: "System Administrator",
  email: null,
  status: "active" as const,
};

function stubSession() {
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
          {
            operational_status_id: 2,
            code: "UNDER_CONSTRUCTION",
            label: "Under Construction",
            is_terminal: false,
          },
          {
            operational_status_id: 3,
            code: "MOTHBALLED",
            label: "Mothballed",
            is_terminal: false,
          },
        ],
      }),
    },
  ]);
}

describe("SubstationCreatePage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("only offers Under Construction/Active as the initial status, per substation-registry.md §10", async () => {
    authStorage.setToken("token");
    stubSession();

    renderWithProviders(<SubstationCreatePage />, { route: "/substations/new" });

    const statusSelect = await screen.findByLabelText("Initial status");
    await waitFor(() => {
      expect(statusSelect.querySelectorAll("option").length).toBeGreaterThan(1);
    });
    const optionLabels = Array.from(statusSelect.querySelectorAll("option")).map((o) =>
      o.textContent?.trim(),
    );
    expect(optionLabels).toEqual(["Select...", "Active", "Under Construction"]);
    expect(optionLabels).not.toContain("Mothballed");
  });

  it("GM Zone is always required", async () => {
    authStorage.setToken("token");
    stubSession();

    renderWithProviders(<SubstationCreatePage />, { route: "/substations/new" });

    const gmZoneSelect = await screen.findByLabelText("GM Zone");
    expect(gmZoneSelect).toBeRequired();
  });

  it("submits the form and navigates to the new substation's detail page", async () => {
    authStorage.setToken("token");
    let createdPayload: unknown = null;
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
          body: [{ operational_status_id: 1, code: "ACTIVE", label: "Active", is_terminal: false }],
        }),
      },
      {
        method: "POST",
        pattern: /\/api\/v1\/substations$/,
        respond: (_url, init) => {
          createdPayload = init?.body ? JSON.parse(init.body as string) : null;
          return {
            status: 201,
            body: {
              substation_id: "44444444-4444-4444-4444-444444444444",
              mnemonic: "SUB1",
              official_name: "Substation One",
              region_id: 1,
              gm_zone_id: 1,
              state_id: 1,
              grid_owner_id: 1,
              operational_status_id: 1,
              psse_bus_number: null,
              latitude: null,
              longitude: null,
              commissioned_date: null,
              remarks: null,
              created_at: "2026-07-02T00:00:00Z",
              updated_at: "2026-07-02T00:00:00Z",
              created_by: CURRENT_USER,
              updated_by: CURRENT_USER,
            },
          };
        },
      },
    ]);

    renderWithProviders(<SubstationCreatePage />, { route: "/substations/new" });

    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Mnemonic"), "SUB1");
    await user.type(screen.getByLabelText("Official name"), "Substation One");
    await user.selectOptions(screen.getByLabelText("Region"), "1");
    await user.selectOptions(screen.getByLabelText("GM Zone"), "1");
    await user.selectOptions(screen.getByLabelText("State (Optional)"), "1");
    await user.selectOptions(screen.getByLabelText("Grid owner"), "1");
    await user.selectOptions(screen.getByLabelText("Initial status"), "1");
    await user.click(screen.getByRole("button", { name: "Create substation" }));

    await waitFor(() => {
      expect(createdPayload).toMatchObject({
        mnemonic: "SUB1",
        official_name: "Substation One",
        region_id: 1,
        gm_zone_id: 1,
        state_id: 1,
        grid_owner_id: 1,
        operational_status_id: 1,
      });
      expect(createdPayload).not.toHaveProperty("voltage_level_id");
    });
  });

  it("does not offer a voltage level field — voltage level is set via voltage yards after creation (ADR-009)", async () => {
    authStorage.setToken("token");
    stubSession();

    renderWithProviders(<SubstationCreatePage />, { route: "/substations/new" });

    await screen.findByLabelText("Mnemonic");
    expect(screen.queryByLabelText("Voltage level")).not.toBeInTheDocument();
  });

  it("State is optional — labelled 'State (Optional)', not required (ADR-026)", async () => {
    authStorage.setToken("token");
    stubSession();

    renderWithProviders(<SubstationCreatePage />, { route: "/substations/new" });

    const stateSelect = await screen.findByLabelText("State (Optional)");
    expect(stateSelect).not.toBeRequired();
    // The empty choice reads "None", not "Select..." — choosing nothing is valid.
    expect(stateSelect.querySelector("option")?.textContent).toBe("None");
    // The old exact "State" label no longer exists.
    expect(screen.queryByLabelText("State")).not.toBeInTheDocument();
  });

  it("creates a substation without a State — omits state_id entirely from the payload (ADR-026)", async () => {
    authStorage.setToken("token");
    let createdPayload: Record<string, unknown> | null = null;
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
        respond: () => ({ status: 200, body: [{ gm_zone_id: 1, code: "KEDP", label: "Alor Setar" }] }),
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
          body: [{ operational_status_id: 1, code: "ACTIVE", label: "Active", is_terminal: false }],
        }),
      },
      {
        method: "POST",
        pattern: /\/api\/v1\/substations$/,
        respond: (_url, init) => {
          createdPayload = init?.body ? JSON.parse(init.body as string) : null;
          return {
            status: 201,
            body: {
              substation_id: "44444444-4444-4444-4444-444444444444",
              mnemonic: "NOST",
              official_name: "Stateless One",
              region_id: 1,
              gm_zone_id: 1,
              state_id: null,
              grid_owner_id: 1,
              operational_status_id: 1,
              psse_bus_number: null,
              latitude: null,
              longitude: null,
              commissioned_date: null,
              remarks: null,
              created_at: "2026-07-02T00:00:00Z",
              updated_at: "2026-07-02T00:00:00Z",
              created_by: CURRENT_USER,
              updated_by: CURRENT_USER,
            },
          };
        },
      },
    ]);

    renderWithProviders(<SubstationCreatePage />, { route: "/substations/new" });

    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Mnemonic"), "NOST");
    await user.type(screen.getByLabelText("Official name"), "Stateless One");
    await user.selectOptions(screen.getByLabelText("Region"), "1");
    await user.selectOptions(screen.getByLabelText("GM Zone"), "1");
    // Deliberately leave State on "None".
    await user.selectOptions(screen.getByLabelText("Grid owner"), "1");
    await user.selectOptions(screen.getByLabelText("Initial status"), "1");
    await user.click(screen.getByRole("button", { name: "Create substation" }));

    await waitFor(() => {
      expect(createdPayload).not.toBeNull();
    });
    expect(createdPayload).not.toHaveProperty("state_id");
    expect(createdPayload).toMatchObject({ mnemonic: "NOST", region_id: 1, gm_zone_id: 1 });
  });
});
