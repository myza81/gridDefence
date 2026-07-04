import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { TransformerCreatePage } from "../../src/modules/equipment_registry/pages/TransformerCreatePage";
import { TransformerListPage } from "../../src/modules/equipment_registry/pages/TransformerListPage";
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
  {
    method: "GET",
    pattern: /\/reference-data\/transformer-breaker-numbering-conventions$/,
    respond: () => ({ status: 200, body: [] }),
  },
];

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

function stubSessionWithOneTransformer(myPermissions: string[]) {
  stubFetch([
    ...SESSION_HANDLERS(myPermissions),
    {
      method: "GET",
      pattern: /\/api\/v1\/transformers\?/,
      respond: () => ({
        status: 200,
        body: {
          items: [
            {
              transformer_id: "33333333-3333-3333-3333-333333333333",
              substation_id: "44444444-4444-4444-4444-444444444444",
              substation_mnemonic: "PKLG",
              substation_official_name: "PKLG Substation",
              transformer_number: "1",
              generated_short_name: "XGT1",
              hv_voltage_level_label: "500kV",
              lv_voltage_level_label: "275kV",
              capacity_mva: 500,
              operational_status_id: 1,
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

function stubSessionWithNoTransformers(myPermissions: string[]) {
  stubFetch([
    ...SESSION_HANDLERS(myPermissions),
    {
      method: "GET",
      pattern: /\/api\/v1\/transformers\?/,
      respond: () => ({
        status: 200,
        body: { items: [], page: 1, page_size: 20, total: 0 },
      }),
    },
    ...REFERENCE_DATA_HANDLERS,
  ]);
}

describe("TransformerListPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders the substation, generated short name, voltage transformation, capacity and status", async () => {
    authStorage.setToken("token");
    stubSessionWithOneTransformer([]);

    renderWithProviders(<TransformerListPage />, { route: "/transformers" });

    await waitFor(() => {
      expect(screen.getByText("XGT1")).toBeInTheDocument();
    });
    const row = screen.getByText("XGT1").closest("tr");
    expect(row).not.toBeNull();
    expect(within(row!).getByText("PKLG — PKLG Substation")).toBeInTheDocument();
    expect(within(row!).getByText("500kV ↔ 275kV")).toBeInTheDocument();
    expect(within(row!).getByText("500")).toBeInTheDocument();
    expect(within(row!).getByText("Active")).toBeInTheDocument();
  });

  describe("New Transformer button", () => {
    it("is not shown to a user without equipment_registry.write", async () => {
      authStorage.setToken("token");
      stubSessionWithOneTransformer([]);

      renderWithProviders(<TransformerListPage />, { route: "/transformers" });

      await waitFor(() => {
        expect(screen.getByText("XGT1")).toBeInTheDocument();
      });
      expect(screen.queryByRole("link", { name: "New Transformer" })).not.toBeInTheDocument();
    });

    it("is shown to a user with equipment_registry.write and navigates to the creation page", async () => {
      authStorage.setToken("token");
      stubFetch([
        ...SESSION_HANDLERS(["equipment_registry.write"]),
        {
          method: "GET",
          pattern: /\/api\/v1\/transformers\?/,
          respond: () => ({
            status: 200,
            body: { items: [], page: 1, page_size: 20, total: 0 },
          }),
        },
        {
          method: "GET",
          pattern: /\/api\/v1\/voltage-yards$/,
          respond: () => ({ status: 200, body: [] }),
        },
        {
          method: "GET",
          pattern: /\/api\/v1\/substations\?/,
          respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 500, total: 0 } }),
        },
        ...REFERENCE_DATA_HANDLERS,
      ]);

      renderWithProviders(
        <Routes>
          <Route path="/transformers" element={<TransformerListPage />} />
          <Route path="/transformers/new" element={<TransformerCreatePage />} />
        </Routes>,
        { route: "/transformers" },
      );

      const user = userEvent.setup();
      const link = await screen.findByRole("link", { name: "New Transformer" });
      expect(link).toHaveAttribute("href", "/transformers/new");

      await user.click(link);

      await waitFor(() => {
        expect(screen.getByRole("heading", { name: "Create transformer" })).toBeInTheDocument();
      });
    });
  });

  describe("empty state", () => {
    it("encourages a user with equipment_registry.write to register the first transformer", async () => {
      authStorage.setToken("token");
      stubSessionWithNoTransformers(["equipment_registry.write"]);

      renderWithProviders(<TransformerListPage />, { route: "/transformers" });

      await waitFor(() => {
        expect(
          screen.getByRole("link", { name: "Register your first transformer" }),
        ).toBeInTheDocument();
      });
      expect(screen.getByText("No transformers have been registered yet.")).toBeInTheDocument();
      expect(screen.queryByRole("table")).not.toBeInTheDocument();
    });

    it("does not offer a registration action to a user without equipment_registry.write", async () => {
      authStorage.setToken("token");
      stubSessionWithNoTransformers([]);

      renderWithProviders(<TransformerListPage />, { route: "/transformers" });

      await waitFor(() => {
        expect(screen.getByText("No transformers have been registered yet.")).toBeInTheDocument();
      });
      expect(
        screen.queryByRole("link", { name: "Register your first transformer" }),
      ).not.toBeInTheDocument();
    });
  });

  // --- Deletion/correction policy (Phase 3 follow-up) -------------------------------
  it("excludes entered-in-error transformers by default, and includes them once the toggle is checked", async () => {
    authStorage.setToken("token");
    let lastUrl = "";
    stubFetch([
      ...SESSION_HANDLERS([]),
      {
        method: "GET",
        pattern: /\/api\/v1\/transformers\?/,
        respond: (url) => {
          lastUrl = url;
          return { status: 200, body: { items: [], page: 1, page_size: 20, total: 0 } };
        },
      },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderWithProviders(<TransformerListPage />, { route: "/transformers" });

    await waitFor(() => {
      expect(lastUrl).not.toContain("include_entered_in_error=true");
    });

    const user = userEvent.setup();
    await user.click(screen.getByLabelText("Show entered-in-error transformers"));

    await waitFor(() => {
      expect(lastUrl).toContain("include_entered_in_error=true");
    });
  });
});
