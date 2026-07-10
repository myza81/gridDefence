import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { FunctionalityCandidatePage } from "../../src/modules/automatic_load_shedding_functionality/pages/FunctionalityCandidatePage";
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
    respond: () => ({ status: 200, body: [] }),
  },
  {
    method: "GET",
    pattern: /\/reference-data\/line-types$/,
    respond: () => ({ status: 200, body: [] }),
  },
];

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
          permissions: [],
        },
      ],
    }),
  },
];

const SUBSTATION_OPTIONS_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/api\/v1\/substations/,
  respond: () => ({
    status: 200,
    body: {
      items: [
        { substation_id: "22222222-2222-2222-2222-222222222222", mnemonic: "PKLG", official_name: "Pekan Lama" },
      ],
      page: 1,
      page_size: 500,
      total: 1,
    },
  }),
};

describe("FunctionalityCandidatePage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("requests UFLS candidates by default and renders results", async () => {
    authStorage.setToken("token");
    let lastUrl = "";
    stubFetch([
      ...SESSION_HANDLERS,
      SUBSTATION_OPTIONS_HANDLER,
      ...REFERENCE_DATA_HANDLERS,
      {
        method: "GET",
        pattern: /\/automatic-load-shedding-functionality\/candidates\?/,
        respond: (url) => {
          lastUrl = url;
          return {
            status: 200,
            body: {
              items: [
                {
                  id: "44444444-4444-4444-4444-444444444444",
                  target_type: "CIRCUIT_TERMINAL",
                  circuit_terminal_id: "55555555-5555-5555-5555-555555555555",
                  transformer_terminal_id: null,
                  substation_id: "22222222-2222-2222-2222-222222222222",
                  substation_mnemonic: "PKLG",
                  voltage_level_label: "500kV",
                  bay_label: "L11",
                  ufls_function: true,
                  uvls_function: false,
                },
              ],
              total: 1,
            },
          };
        },
      },
    ]);

    renderWithProviders(<FunctionalityCandidatePage />, {
      route: "/automatic-load-shedding-functionality/candidates",
    });

    await waitFor(() => {
      expect(lastUrl).toContain("scheme_type=UFLS");
    });
    await waitFor(() => {
      expect(screen.getByText("Candidates (1)")).toBeInTheDocument();
    });
    expect(screen.getByText("PKLG | 500kV | L11")).toBeInTheDocument();
  });

  it("re-queries with UVLS when the scheme type is switched", async () => {
    authStorage.setToken("token");
    let lastUrl = "";
    stubFetch([
      ...SESSION_HANDLERS,
      SUBSTATION_OPTIONS_HANDLER,
      ...REFERENCE_DATA_HANDLERS,
      {
        method: "GET",
        pattern: /\/automatic-load-shedding-functionality\/candidates\?/,
        respond: (url) => {
          lastUrl = url;
          return { status: 200, body: { items: [], total: 0 } };
        },
      },
    ]);

    renderWithProviders(<FunctionalityCandidatePage />, {
      route: "/automatic-load-shedding-functionality/candidates",
    });

    await waitFor(() => expect(lastUrl).toContain("scheme_type=UFLS"));

    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Scheme type"), ["UVLS"]);

    await waitFor(() => {
      expect(lastUrl).toContain("scheme_type=UVLS");
    });
  });
});
