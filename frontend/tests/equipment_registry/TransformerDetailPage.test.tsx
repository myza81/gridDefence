import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { TransformerDetailPage } from "../../src/modules/equipment_registry/pages/TransformerDetailPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const TRANSFORMER_ID = "44444444-4444-4444-4444-444444444444";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "admin",
  display_name: "System Administrator",
  email: null,
  status: "active" as const,
};

const TRANSFORMER_DETAIL = {
  transformer_id: TRANSFORMER_ID,
  substation_id: "s1",
  substation_mnemonic: "PKLG",
  substation_official_name: "PKLG Substation",
  transformer_number: "1",
  generated_short_name: "XGT1",
  capacity_mva: 500,
  commissioning_date: null,
  operational_status_id: 1,
  transformer_type: null,
  manufacturer: null,
  remarks: null,
  created_at: "2026-07-05T00:00:00Z",
  updated_at: "2026-07-05T00:00:00Z",
  created_by: CURRENT_USER,
  updated_by: CURRENT_USER,
  terminals: [
    {
      transformer_terminal_id: "term-hv",
      side: "HV",
      voltage_yard_id: "vy-hv",
      substation_id: "s1",
      substation_mnemonic: "PKLG",
      substation_official_name: "PKLG Substation",
      voltage_level_id: 1,
      voltage_level_label: "500kV",
      breaker_number: "H10",
    },
    {
      transformer_terminal_id: "term-lv",
      side: "LV",
      voltage_yard_id: "vy-lv",
      substation_id: "s1",
      substation_mnemonic: "PKLG",
      substation_official_name: "PKLG Substation",
      voltage_level_id: 2,
      voltage_level_label: "275kV",
      breaker_number: "H10",
    },
  ],
};

const REFERENCE_DATA_HANDLERS: FetchHandler[] = [
  {
    method: "GET",
    pattern: /\/reference-data\/voltage-levels$/,
    respond: () => ({
      status: 200,
      body: [
        { voltage_level_id: 1, label: "500kV", nominal_kv: 500, sort_order: 1 },
        { voltage_level_id: 2, label: "275kV", nominal_kv: 275, sort_order: 2 },
      ],
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
    respond: () => ({
      status: 200,
      body: [{ operational_status_id: 1, code: "ACTIVE", label: "Active", is_terminal: false }],
    }),
  },
  {
    method: "GET",
    pattern: /\/reference-data\/line-types$/,
    respond: () => ({ status: 200, body: [] }),
  },
];

function renderDetailPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/transformers/:transformerId" element={<TransformerDetailPage />} />
    </Routes>,
    { route: `/transformers/${TRANSFORMER_ID}` },
  );
}

function stubSession(myPermissions: string[], overrideHandlers: FetchHandler[] = []) {
  stubFetch([
    ...overrideHandlers,
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
      pattern: new RegExp(`/api/v1/transformers/${TRANSFORMER_ID}$`),
      respond: () => ({ status: 200, body: TRANSFORMER_DETAIL }),
    },
    {
      method: "GET",
      pattern: new RegExp(`/api/v1/transformers/${TRANSFORMER_ID}/audit-log`),
      respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
    },
    ...REFERENCE_DATA_HANDLERS,
  ]);
}

describe("TransformerDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the substation, generated short name, voltage transformation and both breaker numbers", async () => {
    authStorage.setToken("token");
    stubSession([]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByText("Transformer: XGT1 (PKLG)")).toBeInTheDocument();
    });
    expect(screen.getByText("PKLG — PKLG Substation")).toBeInTheDocument();
    expect(screen.getByText("500kV ↔ 275kV")).toBeInTheDocument();
    expect(screen.getAllByText("H10")).toHaveLength(2);
  });

  it("does not show the edit form without equipment_registry.write", async () => {
    authStorage.setToken("token");
    stubSession([]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByText("Transformer: XGT1 (PKLG)")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
  });

  it("shows the edit form with equipment_registry.write", async () => {
    authStorage.setToken("token");
    stubSession(["equipment_registry.write"]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Save changes" })).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Bay / Transformer Number")).toHaveValue("1");
  });

  it("submits edited breaker numbers and metadata", async () => {
    authStorage.setToken("token");
    let updatePayload: unknown = null;
    stubSession(
      ["equipment_registry.write"],
      [
        {
          method: "PATCH",
          pattern: new RegExp(`/api/v1/transformers/${TRANSFORMER_ID}$`),
          respond: (_url, init) => {
            updatePayload = init?.body ? JSON.parse(init.body as string) : null;
            return { status: 200, body: TRANSFORMER_DETAIL };
          },
        },
      ],
    );

    renderDetailPage();

    const hvBreakerInput = await screen.findByLabelText("HV breaker number");
    const user = userEvent.setup();
    await user.clear(hvBreakerInput);
    await user.type(hvBreakerInput, "H99");

    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(updatePayload).toMatchObject({
        hv_breaker_number: "H99",
      });
    });
  });
});
