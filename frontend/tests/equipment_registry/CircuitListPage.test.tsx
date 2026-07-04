import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { CircuitCreatePage } from "../../src/modules/equipment_registry/pages/CircuitCreatePage";
import { CircuitListPage } from "../../src/modules/equipment_registry/pages/CircuitListPage";
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
  {
    method: "GET",
    pattern: /\/reference-data\/regions$/,
    respond: () => ({ status: 200, body: [] }),
  },
  {
    method: "GET",
    pattern: /\/reference-data\/states$/,
    respond: () => ({ status: 200, body: [] }),
  },
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
    respond: () => ({
      status: 200,
      body: [{ line_type_id: 1, code: "OVERHEAD", label: "Overhead Line" }],
    }),
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

function stubSessionWithOneCircuit(myPermissions: string[]) {
  stubFetch([
    ...SESSION_HANDLERS(myPermissions),
    {
      method: "GET",
      pattern: /\/api\/v1\/circuits\?/,
      respond: () => ({
        status: 200,
        body: {
          items: [
            {
              circuit_id: "33333333-3333-3333-3333-333333333333",
              bay_number: "1",
              // Canonical route name: sorted terminal mnemonics only, never
              // bay_number (Phase 3 close-out) — "IGBK" sorts before "PKLG".
              circuit_name: "IGBK–PKLG",
              voltage_level_id: 1,
              line_type_id: 1,
              operational_status_id: 1,
              is_interconnector: false,
              terminal_count: 2,
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

function stubSessionWithNoCircuits(myPermissions: string[]) {
  stubFetch([
    ...SESSION_HANDLERS(myPermissions),
    {
      method: "GET",
      pattern: /\/api\/v1\/circuits\?/,
      respond: () => ({
        status: 200,
        body: { items: [], page: 1, page_size: 20, total: 0 },
      }),
    },
    ...REFERENCE_DATA_HANDLERS,
  ]);
}

describe("CircuitListPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders circuit rows with reference data resolved to labels", async () => {
    authStorage.setToken("token");
    stubSessionWithOneCircuit([]);

    renderWithProviders(<CircuitListPage />, { route: "/circuits" });

    await waitFor(() => {
      expect(screen.getByText("IGBK–PKLG")).toBeInTheDocument();
    });
    const row = screen.getByText("IGBK–PKLG").closest("tr");
    expect(row).not.toBeNull();
    expect(within(row!).getByText("1")).toBeInTheDocument();
    expect(within(row!).getByText("500kV")).toBeInTheDocument();
    expect(within(row!).getByText("Overhead Line")).toBeInTheDocument();
    expect(within(row!).getByText("2")).toBeInTheDocument();
    expect(within(row!).getByText("Active")).toBeInTheDocument();
    expect(within(row!).getByText("No")).toBeInTheDocument();
  });

  it("shows circuit route/name and bay/circuit number as distinct columns, never combined (UAT regression)", async () => {
    // Regression test: circuit_name previously embedded bay_number (e.g.
    // "PKLG–IGBK Line 1"), which combined with the separate "Bay number"
    // column made the display look duplicated (e.g. "...1" next to "1").
    // circuit_name is now the canonical route only.
    authStorage.setToken("token");
    stubSessionWithOneCircuit([]);

    renderWithProviders(<CircuitListPage />, { route: "/circuits" });

    const row = (await screen.findByText("IGBK–PKLG")).closest("tr");
    expect(row).not.toBeNull();
    // The route/name cell itself must not also contain the bay number.
    expect(screen.getByText("IGBK–PKLG").textContent).toBe("IGBK–PKLG");
    // "1" (bay/circuit no.) appears exactly once in the row, as its own cell.
    expect(within(row!).getAllByText("1")).toHaveLength(1);
  });

  describe("New Circuit button", () => {
    it("is not shown to a user without equipment_registry.write", async () => {
      authStorage.setToken("token");
      stubSessionWithOneCircuit([]);

      renderWithProviders(<CircuitListPage />, { route: "/circuits" });

      await waitFor(() => {
        expect(screen.getByText("IGBK–PKLG")).toBeInTheDocument();
      });
      expect(screen.queryByRole("link", { name: "New Circuit" })).not.toBeInTheDocument();
    });

    it("is shown to a user with equipment_registry.write", async () => {
      authStorage.setToken("token");
      stubSessionWithOneCircuit(["equipment_registry.write"]);

      renderWithProviders(<CircuitListPage />, { route: "/circuits" });

      await waitFor(() => {
        expect(screen.getByRole("link", { name: "New Circuit" })).toBeInTheDocument();
      });
    });

    it("navigates to the circuit creation page when clicked", async () => {
      authStorage.setToken("token");
      stubFetch([
        ...SESSION_HANDLERS(["equipment_registry.write"]),
        {
          method: "GET",
          pattern: /\/api\/v1\/circuits\?/,
          respond: () => ({
            status: 200,
            body: { items: [], page: 1, page_size: 20, total: 0 },
          }),
        },
        {
          method: "GET",
          pattern: /\/api\/v1\/substations\?/,
          respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 200, total: 0 } }),
        },
        ...REFERENCE_DATA_HANDLERS,
      ]);

      renderWithProviders(
        <Routes>
          <Route path="/circuits" element={<CircuitListPage />} />
          <Route path="/circuits/new" element={<CircuitCreatePage />} />
        </Routes>,
        { route: "/circuits" },
      );

      const user = userEvent.setup();
      const link = await screen.findByRole("link", { name: "New Circuit" });
      expect(link).toHaveAttribute("href", "/circuits/new");

      await user.click(link);

      await waitFor(() => {
        expect(screen.getByRole("heading", { name: "Create circuit" })).toBeInTheDocument();
      });
    });
  });

  describe("empty state", () => {
    it("encourages a user with equipment_registry.write to register the first circuit", async () => {
      authStorage.setToken("token");
      stubSessionWithNoCircuits(["equipment_registry.write"]);

      renderWithProviders(<CircuitListPage />, { route: "/circuits" });

      // Wait on the permission-gated element itself, not just the
      // permission-independent paragraph — the roles/permissions fetch and
      // the circuits fetch resolve independently, so asserting on the
      // paragraph alone can race ahead of the permission-derived link.
      await waitFor(() => {
        expect(
          screen.getByRole("link", { name: "Register your first circuit" }),
        ).toBeInTheDocument();
      });
      expect(screen.getByText("No circuits have been registered yet.")).toBeInTheDocument();
      // No dead-end table with a bare "no rows" message once the empty state renders.
      expect(screen.queryByRole("table")).not.toBeInTheDocument();
    });

    it("does not offer a registration action to a user without equipment_registry.write", async () => {
      authStorage.setToken("token");
      stubSessionWithNoCircuits([]);

      renderWithProviders(<CircuitListPage />, { route: "/circuits" });

      await waitFor(() => {
        expect(screen.getByText("No circuits have been registered yet.")).toBeInTheDocument();
      });
      expect(
        screen.queryByRole("link", { name: "Register your first circuit" }),
      ).not.toBeInTheDocument();
    });
  });
});
