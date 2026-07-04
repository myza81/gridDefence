import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { CircuitDetailPage } from "../../src/modules/equipment_registry/pages/CircuitDetailPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const CIRCUIT_ID = "44444444-4444-4444-4444-444444444444";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "admin",
  display_name: "System Administrator",
  email: null,
  status: "active" as const,
};

function terminal(overrides: Record<string, unknown>) {
  return {
    circuit_terminal_id: "t1",
    voltage_yard_id: "vy1",
    substation_id: "s1",
    substation_mnemonic: "ABBA",
    substation_official_name: "ABBA Substation",
    voltage_level_id: 1,
    voltage_level_label: "500kV",
    breaker_number: "A1",
    commissioning_date: null,
    remarks: null,
    operational_status_id: 1,
    created_at: "2026-07-05T00:00:00Z",
    updated_at: "2026-07-05T00:00:00Z",
    ...overrides,
  };
}

// A tee-off — three terminals sharing one circuit
// (equipment-registry-module.md §7.13 Scenario B).
const CIRCUIT_DETAIL = {
  circuit_id: CIRCUIT_ID,
  bay_number: "1",
  // Canonical route name: sorted terminal mnemonics only, never bay_number
  // (Phase 3 close-out) — "ABBA" < "NLAI" < "SMRK" alphabetically.
  circuit_name: "ABBA–NLAI–SMRK",
  voltage_level_id: 1,
  line_type_id: 1,
  operational_status_id: 1,
  is_interconnector: false,
  remarks: null,
  created_at: "2026-07-05T00:00:00Z",
  updated_at: "2026-07-05T00:00:00Z",
  created_by: CURRENT_USER,
  updated_by: CURRENT_USER,
  terminals: [
    terminal({
      circuit_terminal_id: "t1",
      voltage_yard_id: "vy1",
      substation_mnemonic: "ABBA",
      substation_official_name: "ABBA Substation",
      breaker_number: "A1",
    }),
    terminal({
      circuit_terminal_id: "t2",
      voltage_yard_id: "vy2",
      substation_mnemonic: "SMRK",
      substation_official_name: "SMRK Substation",
      breaker_number: "S1",
    }),
    terminal({
      circuit_terminal_id: "t3",
      voltage_yard_id: "vy3",
      substation_mnemonic: "NLAI",
      substation_official_name: "NLAI Substation",
      breaker_number: "N1",
    }),
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
        { voltage_level_id: 2, label: "132kV", nominal_kv: 132, sort_order: 2 },
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
      body: [
        { operational_status_id: 1, code: "ACTIVE", label: "Active", is_terminal: false },
        {
          operational_status_id: 7,
          code: "ENTERED_IN_ERROR",
          label: "Entered in Error",
          is_terminal: true,
        },
      ],
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

function renderDetailPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/circuits/:circuitId" element={<CircuitDetailPage />} />
    </Routes>,
    { route: `/circuits/${CIRCUIT_ID}` },
  );
}

function stubSession(myPermissions: string[], overrideHandlers: FetchHandler[] = []) {
  stubFetch([
    // `stubFetch` resolves the first pattern match, so overrides must come
    // first — otherwise a base handler below with the same pattern (e.g.
    // GET /voltage-yards) would always win instead.
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
      pattern: new RegExp(`/api/v1/circuits/${CIRCUIT_ID}$`),
      respond: () => ({ status: 200, body: CIRCUIT_DETAIL }),
    },
    {
      method: "GET",
      pattern: new RegExp(`/api/v1/circuits/${CIRCUIT_ID}/audit-log`),
      respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
    },
    {
      method: "GET",
      pattern: /\/api\/v1\/voltage-yards$/,
      respond: () => ({
        status: 200,
        body: [
          {
            voltage_yard_id: "vy4",
            substation_id: "s4",
            substation_mnemonic: "NKST",
            substation_official_name: "NKST Substation",
            voltage_level_id: 1,
            voltage_level_label: "500kV",
            display_label: "NKST — 500kV",
          },
        ],
      }),
    },
    ...REFERENCE_DATA_HANDLERS,
  ]);
}

describe("CircuitDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders all three terminals of a tee-off circuit, each with its own breaker number and voltage yard", async () => {
    authStorage.setToken("token");
    stubSession([]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByText("Circuit: ABBA–NLAI–SMRK")).toBeInTheDocument();
    });
    expect(screen.getByText(/ABBA — 500kV/)).toBeInTheDocument();
    expect(screen.getByText(/SMRK — 500kV/)).toBeInTheDocument();
    expect(screen.getByText(/NLAI — 500kV/)).toBeInTheDocument();
    expect(screen.getByText("A1")).toBeInTheDocument();
    expect(screen.getByText("S1")).toBeInTheDocument();
    expect(screen.getByText("N1")).toBeInTheDocument();
  });

  it("does not show the edit/status/add-terminal forms without equipment_registry.write", async () => {
    authStorage.setToken("token");
    stubSession([]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByText("Circuit: ABBA–NLAI–SMRK")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Save changes" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add terminal" })).not.toBeInTheDocument();
    // Breaker number/commissioning date render as plain text, not inputs.
    expect(screen.queryByLabelText(/Breaker number for/)).not.toBeInTheDocument();
  });

  it("shows the edit/status/add-terminal forms with equipment_registry.write", async () => {
    authStorage.setToken("token");
    stubSession(["equipment_registry.write"]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Save changes" })).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Add terminal" })).toBeInTheDocument();
  });

  it("the circuit edit form includes line type and voltage level (must-fix item 2)", async () => {
    authStorage.setToken("token");
    stubSession(["equipment_registry.write"]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByLabelText("Bay / Circuit No.")).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Voltage level")).toBeInTheDocument();
    expect(screen.getByLabelText("Line type")).toBeInTheDocument();
  });

  it("submits an edited breaker number and commissioning date for one terminal (must-fix items 1-2)", async () => {
    authStorage.setToken("token");
    let updatePayload: unknown = null;
    stubSession(
      ["equipment_registry.write"],
      [
        {
          method: "PATCH",
          pattern: new RegExp(`/api/v1/circuits/${CIRCUIT_ID}/terminals/t1$`),
          respond: (_url, init) => {
            updatePayload = init?.body ? JSON.parse(init.body as string) : null;
            return { status: 200, body: CIRCUIT_DETAIL };
          },
        },
      ],
    );

    renderDetailPage();

    const breakerInput = await screen.findByLabelText("Breaker number for ABBA — 500kV");
    const user = userEvent.setup();
    await user.clear(breakerInput);
    await user.type(breakerInput, "A99");

    const dateInput = screen.getByLabelText("Commissioning date for ABBA — 500kV");
    await user.type(dateInput, "2020-01-15");

    const row = breakerInput.closest("tr");
    expect(row).not.toBeNull();
    await user.click(within(row!).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(updatePayload).toMatchObject({
        breaker_number: "A99",
        commissioning_date: "2020-01-15",
      });
    });
  });

  it("the add-terminal form offers voltage yards, not substations", async () => {
    authStorage.setToken("token");
    stubSession(["equipment_registry.write"]);

    renderDetailPage();

    const yardSelect = await screen.findByLabelText("New terminal switchyard");
    await waitFor(() => {
      expect(within(yardSelect).getByText("NKST — 500kV")).toBeInTheDocument();
    });
  });

  it("excludes voltage yards at a different voltage level than the circuit (rule 6a guardrail)", async () => {
    // Regression test: the Add Terminal dropdown previously offered every
    // voltage yard regardless of the circuit's own voltage level, letting
    // a mismatched yard be selected (Phase 3 UAT follow-up). This circuit
    // is at 500kV (voltage_level_id: 1); only the 500kV yard should appear.
    authStorage.setToken("token");
    stubSession(
      ["equipment_registry.write"],
      [
        {
          method: "GET",
          pattern: /\/api\/v1\/voltage-yards$/,
          respond: () => ({
            status: 200,
            body: [
              {
                voltage_yard_id: "vy4",
                substation_id: "s4",
                substation_mnemonic: "NKST",
                substation_official_name: "NKST Substation",
                voltage_level_id: 1,
                voltage_level_label: "500kV",
                display_label: "NKST — 500kV",
              },
              {
                voltage_yard_id: "vy5",
                substation_id: "s5",
                substation_mnemonic: "MHTA",
                substation_official_name: "MHTA Substation",
                voltage_level_id: 2,
                voltage_level_label: "132kV",
                display_label: "MHTA — 132kV",
              },
            ],
          }),
        },
      ],
    );

    renderDetailPage();

    const yardSelect = await screen.findByLabelText("New terminal switchyard");
    await waitFor(() => {
      expect(within(yardSelect).getByText("NKST — 500kV")).toBeInTheDocument();
    });
    const optionLabels = Array.from(yardSelect.querySelectorAll("option")).map((o) =>
      o.textContent?.trim(),
    );
    expect(optionLabels).toEqual(["Select switchyard...", "NKST — 500kV"]);
    expect(optionLabels).not.toContain("MHTA — 132kV");
  });

  it("does not offer inline voltage yard creation — that capability was removed from this page (ADR-009 addendum)", async () => {
    // Regression test: voltage yards are master topology data owned
    // exclusively by Substation Registry. Circuit pages must only consume
    // existing yards, never create them — see the "Need a different
    // voltage yard?" section removed from this page.
    authStorage.setToken("token");
    stubSession(["equipment_registry.write"]);

    renderDetailPage();

    await screen.findByLabelText("New terminal switchyard");
    expect(screen.queryByLabelText("New voltage yard substation")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("New voltage yard voltage level")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add voltage yard" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Need a different voltage yard?" })).not.toBeInTheDocument();
  });

  it("shows guidance pointing to the Substation Registry when no suitable voltage yard exists, instead of allowing inline creation", async () => {
    authStorage.setToken("token");
    stubSession(
      ["equipment_registry.write"],
      [
        {
          method: "GET",
          pattern: /\/api\/v1\/voltage-yards$/,
          // Only yard in the system is already used by this circuit's own
          // terminals (vy1/vy2/vy3) — none remain available to select.
          respond: () => ({
            status: 200,
            body: [
              {
                voltage_yard_id: "vy1",
                substation_id: "s1",
                substation_mnemonic: "ABBA",
                substation_official_name: "ABBA Substation",
                voltage_level_id: 1,
                voltage_level_label: "500kV",
                display_label: "ABBA — 500kV",
              },
            ],
          }),
        },
      ],
    );

    renderDetailPage();

    await waitFor(() => {
      expect(
        screen.getByText(
          "No suitable switchyard exists for this circuit. Please add the required switchyard from the Substation Registry.",
        ),
      ).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Add voltage yard" })).not.toBeInTheDocument();
  });

  // --- Deletion/correction policy (Phase 3 follow-up) -------------------------------
  it("shows each terminal's status and a Mark as Entered in Error action with write permission", async () => {
    authStorage.setToken("token");
    stubSession(["equipment_registry.write"]);

    renderDetailPage();

    // Wait on the permission-gated element itself — the roles fetch
    // (which determines canWrite) resolves independently of the circuit
    // fetch, so asserting on circuit content alone can race ahead of the
    // permission-derived correction buttons.
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Save changes" })).toBeInTheDocument();
    });
    const terminalsTable = screen.getByText("Substation — switchyard").closest("table");
    expect(terminalsTable).not.toBeNull();
    expect(within(terminalsTable!).getAllByText("Active")).toHaveLength(3);
    expect(screen.getAllByRole("button", { name: "Mark as Entered in Error" })).toHaveLength(3);
  });

  it("does not show a Mark as Entered in Error action without write permission", async () => {
    authStorage.setToken("token");
    stubSession([]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByText("Circuit: ABBA–NLAI–SMRK")).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("button", { name: "Mark as Entered in Error" }),
    ).not.toBeInTheDocument();
  });

  it("corrects a terminal as Entered in Error, never blocked, and it is never a delete action", async () => {
    authStorage.setToken("token");
    let updatePayload: unknown = null;
    stubSession(
      ["equipment_registry.write"],
      [
        {
          method: "PATCH",
          pattern: new RegExp(`/api/v1/circuits/${CIRCUIT_ID}/terminals/t1$`),
          respond: (_url, init) => {
            updatePayload = init?.body ? JSON.parse(init.body as string) : null;
            return { status: 200, body: CIRCUIT_DETAIL };
          },
        },
      ],
    );

    renderDetailPage();

    const breakerInput = await screen.findByLabelText("Breaker number for ABBA — 500kV");
    const row = breakerInput.closest("tr");
    expect(row).not.toBeNull();
    const user = userEvent.setup();
    await user.click(within(row!).getByRole("button", { name: "Mark as Entered in Error" }));

    await waitFor(() => {
      expect(updatePayload).toMatchObject({ operational_status_id: 7 });
    });
    // Never a "Delete" button anywhere on this page (CLAUDE.md §11.6 — no
    // hard delete for engineering registry records).
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });
});
