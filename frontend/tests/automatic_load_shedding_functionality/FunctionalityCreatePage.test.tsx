import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { FunctionalityCreatePage } from "../../src/modules/automatic_load_shedding_functionality/pages/FunctionalityCreatePage";
import { FunctionalityDetailPage } from "../../src/modules/automatic_load_shedding_functionality/pages/FunctionalityDetailPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "engineer1",
  display_name: "Engineer One",
  email: null,
  status: "active" as const,
};

const SESSION_HANDLERS: FetchHandler[] = [
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
          permissions: ["automatic_load_shedding_functionality.write"],
        },
      ],
    }),
  },
];

const SUBSTATION_ID = "22222222-2222-2222-2222-222222222222";
const CIRCUIT_TERMINAL_ID = "55555555-5555-5555-5555-555555555555";
const NEW_ID = "66666666-6666-6666-6666-666666666666";

const SUBSTATION_OPTIONS_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/api\/v1\/substations/,
  respond: () => ({
    status: 200,
    body: {
      items: [{ substation_id: SUBSTATION_ID, mnemonic: "PKLG", official_name: "Pekan Lama" }],
      page: 1,
      page_size: 500,
      total: 1,
    },
  }),
};

const SUBSTATION_EQUIPMENT_HANDLER: FetchHandler = {
  method: "GET",
  pattern: new RegExp(`/network-model/substations/${SUBSTATION_ID}/equipment$`),
  respond: () => ({
    status: 200,
    body: {
      substation_id: SUBSTATION_ID,
      substation_mnemonic: "PKLG",
      substation_official_name: "Pekan Lama",
      transformer_bays: [],
      line_bays: [
        {
          circuit_terminal_id: CIRCUIT_TERMINAL_ID,
          circuit_id: "77777777-7777-7777-7777-777777777777",
          circuit_bay_number: "1",
          circuit_name: "IGBK–PKLG",
          breaker_number: "L11",
          voltage_level_label: "500kV",
          operational_status_code: "ACTIVE",
        },
      ],
    },
  }),
};

describe("FunctionalityCreatePage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("always shows a visible Save/Create button, even before the form is complete", async () => {
    authStorage.setToken("token");
    stubFetch([...SESSION_HANDLERS, SUBSTATION_OPTIONS_HANDLER, SUBSTATION_EQUIPMENT_HANDLER]);

    renderWithProviders(<FunctionalityCreatePage />, {
      route: "/automatic-load-shedding-functionality/new",
    });

    // The Create/Save action is always visible (just disabled until valid),
    // not hidden or absent — this is the primary reported UX gap.
    expect(screen.getByRole("button", { name: "Create" })).toBeInTheDocument();
  });

  it("disables submit until a bay and at least one function are selected", async () => {
    authStorage.setToken("token");
    stubFetch([...SESSION_HANDLERS, SUBSTATION_OPTIONS_HANDLER, SUBSTATION_EQUIPMENT_HANDLER]);

    renderWithProviders(<FunctionalityCreatePage />, {
      route: "/automatic-load-shedding-functionality/new",
    });

    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();

    const user = userEvent.setup();
    await screen.findByRole("option", { name: /PKLG/ });
    await user.selectOptions(screen.getByLabelText("Substation"), [SUBSTATION_ID]);

    await screen.findByRole("option", { name: /IGBK–PKLG/ });
    await user.selectOptions(screen.getByLabelText("Line Bay"), [CIRCUIT_TERMINAL_ID]);

    // Bay selected, but no function checked yet.
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();

    await user.click(screen.getByLabelText("UFLS function"));
    expect(screen.getByRole("button", { name: "Create" })).toBeEnabled();
  });

  it("displays the full engineering identity, including the bay identifier, in the terminal picker", async () => {
    authStorage.setToken("token");
    stubFetch([...SESSION_HANDLERS, SUBSTATION_OPTIONS_HANDLER, SUBSTATION_EQUIPMENT_HANDLER]);

    renderWithProviders(<FunctionalityCreatePage />, {
      route: "/automatic-load-shedding-functionality/new",
    });

    const user = userEvent.setup();
    await screen.findByRole("option", { name: /PKLG/ });
    await user.selectOptions(screen.getByLabelText("Substation"), [SUBSTATION_ID]);

    // Full "Substation | Voltage | Bay" identity, not just substation/type/
    // voltage — the bay identifier (route name + bay number) must be
    // visible so an engineer can pick the exact terminal unambiguously.
    expect(
      await screen.findByRole("option", { name: "PKLG | 500kV | Line IGBK–PKLG 1" }),
    ).toBeInTheDocument();
  });

  it("submits a create request and navigates to the new record's detail page", async () => {
    authStorage.setToken("token");
    let createPayload: unknown = null;
    stubFetch([
      ...SESSION_HANDLERS,
      SUBSTATION_OPTIONS_HANDLER,
      SUBSTATION_EQUIPMENT_HANDLER,
      {
        method: "POST",
        pattern: /\/automatic-load-shedding-functionality$/,
        respond: (_url, init) => {
          createPayload = init?.body ? JSON.parse(init.body as string) : null;
          return {
            status: 201,
            body: {
              id: NEW_ID,
              target_type: "CIRCUIT_TERMINAL",
              circuit_terminal_id: CIRCUIT_TERMINAL_ID,
              transformer_terminal_id: null,
              substation_id: SUBSTATION_ID,
              substation_mnemonic: "PKLG",
              substation_official_name: "Pekan Lama",
              voltage_level_label: "500kV",
              bay_label: "L11",
              ufls_function: true,
              uvls_function: false,
              status: "AVAILABLE",
              relay_make: null,
              relay_model: null,
              remarks: null,
              created_at: "2026-07-09T00:00:00Z",
              updated_at: "2026-07-09T00:00:00Z",
              created_by: null,
              updated_by: null,
            },
          };
        },
      },
      {
        method: "GET",
        pattern: new RegExp(`/automatic-load-shedding-functionality/${NEW_ID}$`),
        respond: () => ({
          status: 200,
          body: {
            id: NEW_ID,
            target_type: "CIRCUIT_TERMINAL",
            circuit_terminal_id: CIRCUIT_TERMINAL_ID,
            transformer_terminal_id: null,
            substation_id: SUBSTATION_ID,
            substation_mnemonic: "PKLG",
            substation_official_name: "Pekan Lama",
            voltage_level_label: "500kV",
            bay_label: "L11",
            ufls_function: true,
            uvls_function: false,
            status: "AVAILABLE",
            relay_make: null,
            relay_model: null,
            remarks: null,
            created_at: "2026-07-09T00:00:00Z",
            updated_at: "2026-07-09T00:00:00Z",
            created_by: null,
            updated_by: null,
          },
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/automatic-load-shedding-functionality/${NEW_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
    ]);

    renderWithProviders(
      <Routes>
        <Route path="/automatic-load-shedding-functionality/new" element={<FunctionalityCreatePage />} />
        <Route
          path="/automatic-load-shedding-functionality/:functionalityId"
          element={<FunctionalityDetailPage />}
        />
      </Routes>,
      { route: "/automatic-load-shedding-functionality/new" },
    );

    const user = userEvent.setup();
    await screen.findByRole("option", { name: /PKLG/ });
    await user.selectOptions(screen.getByLabelText("Substation"), [SUBSTATION_ID]);
    await screen.findByRole("option", { name: /IGBK–PKLG/ });
    await user.selectOptions(screen.getByLabelText("Line Bay"), [CIRCUIT_TERMINAL_ID]);
    await user.click(screen.getByLabelText("UFLS function"));
    await user.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(createPayload).toMatchObject({
        target_type: "CIRCUIT_TERMINAL",
        circuit_terminal_id: CIRCUIT_TERMINAL_ID,
        ufls_function: true,
        uvls_function: false,
      });
    });

    await waitFor(() => {
      expect(
        screen.getByRole("heading", {
          name: "Automatic Load Shedding Functionality — PKLG | 500kV | L11",
        }),
      ).toBeInTheDocument();
    });
  });
});
