import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { FacilityCreatePage } from "../../src/modules/sensitive_customer_registry/pages/FacilityCreatePage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "admin1",
  display_name: "Admin One",
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
            name: "Administrator",
            description: null,
            is_system_role: true,
            status: "active",
          },
          granted_at: "2026-01-01T00:00:00Z",
          permissions: ["sensitive_customer_registry.write"],
        },
      ],
    }),
  },
];

const SECTORS_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/reference-data\/facility-sectors$/,
  respond: () => ({
    status: 200,
    body: [
      { id: 1, code: "HEALTHCARE", label: "Healthcare", sort_order: 1, description: null, is_active: true },
    ],
  }),
};

const CLASSIFICATIONS_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/reference-data\/sensitivity-classifications$/,
  respond: () => ({
    status: 200,
    body: [
      { id: 1, code: "HIGH", label: "High", sort_order: 1, description: null, is_active: true },
    ],
  }),
};

const TERMINAL_IDENTITIES_HANDLER: FetchHandler = {
  method: "GET",
  pattern: /\/transformer-terminals$/,
  respond: () => ({
    status: 200,
    body: [
      {
        transformer_terminal_id: "55555555-5555-5555-5555-555555555555",
        transformer_id: "77777777-7777-7777-7777-777777777777",
        generated_short_name: "T1",
        transformer_number: "1",
        side: "LV",
        breaker_number: "T12",
        substation_id: "22222222-2222-2222-2222-222222222222",
        substation_mnemonic: "PKLG",
        substation_official_name: "Pekan Lama Substation",
        voltage_level_id: 1,
        voltage_level_label: "33kV",
      },
    ],
  }),
};

function stubStandardSession() {
  stubFetch([
    ...SESSION_HANDLERS,
    SECTORS_HANDLER,
    CLASSIFICATIONS_HANDLER,
    TERMINAL_IDENTITIES_HANDLER,
  ]);
}

describe("FacilityCreatePage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("disables submit until name, sector, and sensitivity classification are all provided", async () => {
    authStorage.setToken("token");
    stubStandardSession();

    renderWithProviders(<FacilityCreatePage />, { route: "/sensitive-customer-registry/new" });

    await screen.findByLabelText("Facility Name");
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Facility Name"), "Hospital Kuala Lumpur");
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();

    await user.selectOptions(screen.getByLabelText("Facility Sector"), ["1"]);
    expect(screen.getByRole("button", { name: "Create" })).toBeDisabled();

    await user.selectOptions(screen.getByLabelText("Sensitivity Classification"), ["1"]);
    expect(screen.getByRole("button", { name: "Create" })).toBeEnabled();
  });

  it("submits without a Transformer Terminal association — it is optional", async () => {
    authStorage.setToken("token");
    let createdBody: Record<string, unknown> | undefined;
    stubFetch([
      ...SESSION_HANDLERS,
      SECTORS_HANDLER,
      CLASSIFICATIONS_HANDLER,
      TERMINAL_IDENTITIES_HANDLER,
      {
        method: "POST",
        pattern: /\/api\/v1\/sensitive-customer-registry\/facilities$/,
        respond: (_url, init) => {
          createdBody = JSON.parse(init?.body as string);
          return {
            status: 201,
            body: {
              id: "44444444-4444-4444-4444-444444444444",
              name: "Hospital Kuala Lumpur",
            },
          };
        },
      },
    ]);

    renderWithProviders(<FacilityCreatePage />, { route: "/sensitive-customer-registry/new" });

    const user = userEvent.setup();
    await screen.findByLabelText("Facility Name");
    await user.type(screen.getByLabelText("Facility Name"), "Hospital Kuala Lumpur");
    await user.selectOptions(screen.getByLabelText("Facility Sector"), ["1"]);
    await user.selectOptions(screen.getByLabelText("Sensitivity Classification"), ["1"]);
    await user.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(createdBody).toBeDefined();
    });
    expect(createdBody?.transformer_terminal_ids).toEqual([]);
    expect(createdBody?.name).toBe("Hospital Kuala Lumpur");
  });

  it("submits with a searchable multi-select Transformer Terminal association, no Transformer step required", async () => {
    authStorage.setToken("token");
    let createdBody: Record<string, unknown> | undefined;
    stubFetch([
      ...SESSION_HANDLERS,
      SECTORS_HANDLER,
      CLASSIFICATIONS_HANDLER,
      TERMINAL_IDENTITIES_HANDLER,
      {
        method: "POST",
        pattern: /\/api\/v1\/sensitive-customer-registry\/facilities$/,
        respond: (_url, init) => {
          createdBody = JSON.parse(init?.body as string);
          return {
            status: 201,
            body: {
              id: "44444444-4444-4444-4444-444444444444",
              name: "Hospital Kuala Lumpur",
            },
          };
        },
      },
    ]);

    renderWithProviders(<FacilityCreatePage />, { route: "/sensitive-customer-registry/new" });

    const user = userEvent.setup();
    await screen.findByLabelText("Facility Name");
    await user.type(screen.getByLabelText("Facility Name"), "Hospital Kuala Lumpur");
    await user.selectOptions(screen.getByLabelText("Facility Sector"), ["1"]);
    await user.selectOptions(screen.getByLabelText("Sensitivity Classification"), ["1"]);

    const option = await screen.findByText("PKLG | 33kV | Transformer T1 (LV)");
    await user.click(option);

    expect(await screen.findByRole("cell", { name: "PKLG" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "33kV" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Transformer T1" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "LV" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Transformer")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(createdBody).toBeDefined();
    });
    expect(createdBody?.transformer_terminal_ids).toEqual([
      "55555555-5555-5555-5555-555555555555",
    ]);
  });
});
