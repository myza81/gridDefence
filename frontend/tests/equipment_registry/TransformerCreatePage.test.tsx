import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { TransformerCreatePage } from "../../src/modules/equipment_registry/pages/TransformerCreatePage";
import { renderWithProviders, stubFetch } from "../testUtils";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "admin",
  display_name: "System Administrator",
  email: null,
  status: "active" as const,
};

const SUBSTATIONS = [
  {
    substation_id: "sub-pklg",
    mnemonic: "PKLG",
    official_name: "PKLG Substation",
    region_id: 1,
    state_id: 1,
    grid_owner_id: 1,
    operational_status_id: 1,
    psse_bus_number: null,
  },
  {
    substation_id: "sub-igbk",
    mnemonic: "IGBK",
    official_name: "IGBK Substation",
    region_id: 1,
    state_id: 1,
    grid_owner_id: 1,
    operational_status_id: 1,
    psse_bus_number: null,
  },
];

// PKLG has an HV (275kV) and LV (132kV) switchyard; IGBK has its own,
// independent pair — used to prove the HV/LV dropdowns are filtered to the
// selected substation only (UAT correction).
const VOLTAGE_YARDS = [
  {
    voltage_yard_id: "hv-yard",
    substation_id: "sub-pklg",
    substation_mnemonic: "PKLG",
    substation_official_name: "PKLG Substation",
    voltage_level_id: 2,
    voltage_level_label: "275kV",
    display_label: "PKLG — 275kV",
  },
  {
    voltage_yard_id: "lv-yard",
    substation_id: "sub-pklg",
    substation_mnemonic: "PKLG",
    substation_official_name: "PKLG Substation",
    voltage_level_id: 3,
    voltage_level_label: "132kV",
    display_label: "PKLG — 132kV",
  },
  {
    voltage_yard_id: "igbk-hv-yard",
    substation_id: "sub-igbk",
    substation_mnemonic: "IGBK",
    substation_official_name: "IGBK Substation",
    voltage_level_id: 2,
    voltage_level_label: "275kV",
    display_label: "IGBK — 275kV",
  },
  {
    voltage_yard_id: "igbk-lv-yard",
    substation_id: "sub-igbk",
    substation_mnemonic: "IGBK",
    substation_official_name: "IGBK Substation",
    voltage_level_id: 3,
    voltage_level_label: "132kV",
    display_label: "IGBK — 132kV",
  },
];

function baseHandlers() {
  return [
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
      pattern: /\/api\/v1\/substations\?/,
      respond: () => ({
        status: 200,
        body: { items: SUBSTATIONS, page: 1, page_size: 500, total: SUBSTATIONS.length },
      }),
    },
    {
      method: "GET",
      pattern: /\/api\/v1\/voltage-yards$/,
      respond: () => ({ status: 200, body: VOLTAGE_YARDS }),
    },
    {
      method: "GET",
      pattern: /\/reference-data\/voltage-levels$/,
      respond: () => ({
        status: 200,
        body: [
          { voltage_level_id: 1, label: "500kV", nominal_kv: 500, sort_order: 1 },
          { voltage_level_id: 2, label: "275kV", nominal_kv: 275, sort_order: 2 },
          { voltage_level_id: 3, label: "132kV", nominal_kv: 132, sort_order: 3 },
        ],
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
        body: [
          { operational_status_id: 1, code: "ACTIVE", label: "Active", is_terminal: false },
          { operational_status_id: 2, code: "PLANNED", label: "Planned", is_terminal: false },
          {
            operational_status_id: 3,
            code: "MOTHBALLED",
            label: "Mothballed",
            is_terminal: false,
          },
        ],
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
      respond: () => ({
        status: 200,
        body: [
          // Matches the 275kV (voltage_level_id 2) / 132kV (voltage_level_id 3)
          // pair used by VOLTAGE_YARDS above.
          {
            convention_id: 1,
            hv_voltage_level_id: 2,
            lv_voltage_level_id: 3,
            side: "HV",
            pattern: "H{N}0",
            is_standard: true,
            notes: null,
          },
          {
            convention_id: 2,
            hv_voltage_level_id: 2,
            lv_voltage_level_id: 3,
            side: "LV",
            pattern: "{N}80",
            is_standard: true,
            notes: null,
          },
        ],
      }),
    },
  ];
}

async function selectSubstation(user: ReturnType<typeof userEvent.setup>, substationId: string) {
  const substationSelect = await screen.findByLabelText("Substation");
  await waitFor(() => {
    expect(substationSelect.querySelectorAll("option").length).toBeGreaterThan(1);
  });
  await user.selectOptions(substationSelect, substationId);
  return substationSelect;
}

describe("TransformerCreatePage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("only offers Planned/Active as the initial status", async () => {
    authStorage.setToken("token");
    stubFetch(baseHandlers());

    renderWithProviders(<TransformerCreatePage />, { route: "/transformers/new" });

    const statusSelect = await screen.findByLabelText("Initial status");
    await waitFor(() => {
      expect(statusSelect.querySelectorAll("option").length).toBeGreaterThan(1);
    });
    const optionLabels = Array.from(statusSelect.querySelectorAll("option")).map((o) =>
      o.textContent?.trim(),
    );
    expect(optionLabels).toEqual(["Select...", "Active", "Planned"]);
    expect(optionLabels).not.toContain("Mothballed");
  });

  it("does not offer any switchyard until a substation is selected", async () => {
    authStorage.setToken("token");
    stubFetch(baseHandlers());

    renderWithProviders(<TransformerCreatePage />, { route: "/transformers/new" });

    const hvSelect = await screen.findByLabelText("HV switchyard");
    const lvSelect = screen.getByLabelText("LV switchyard");
    expect(hvSelect).toBeDisabled();
    expect(lvSelect).toBeDisabled();
    const optionLabels = Array.from(hvSelect.querySelectorAll("option")).map((o) =>
      o.textContent?.trim(),
    );
    expect(optionLabels).toEqual(["Select..."]);
    expect(screen.getByText("Select a substation above to see its switchyards.")).toBeInTheDocument();
  });

  it("only offers switchyards belonging to the selected substation (UAT correction)", async () => {
    authStorage.setToken("token");
    stubFetch(baseHandlers());

    renderWithProviders(<TransformerCreatePage />, { route: "/transformers/new" });

    const user = userEvent.setup();
    const substationSelect = await screen.findByLabelText("Substation");
    await waitFor(() => {
      expect(substationSelect.querySelectorAll("option").length).toBeGreaterThan(1);
    });
    await user.selectOptions(substationSelect, "sub-pklg");

    const hvSelect = screen.getByLabelText("HV switchyard");
    await waitFor(() => {
      expect(hvSelect.querySelectorAll("option").length).toBeGreaterThan(1);
    });
    const pklgOptions = Array.from(hvSelect.querySelectorAll("option")).map((o) =>
      o.textContent?.trim(),
    );
    expect(pklgOptions).toEqual(["Select...", "PKLG — 275kV", "PKLG — 132kV"]);
    expect(pklgOptions).not.toContain("IGBK — 275kV");

    await user.selectOptions(substationSelect, "sub-igbk");
    const igbkOptions = Array.from(hvSelect.querySelectorAll("option")).map((o) =>
      o.textContent?.trim(),
    );
    expect(igbkOptions).toEqual(["Select...", "IGBK — 275kV", "IGBK — 132kV"]);
  });

  it("clears an already-selected switchyard when the substation changes", async () => {
    authStorage.setToken("token");
    stubFetch(baseHandlers());

    renderWithProviders(<TransformerCreatePage />, { route: "/transformers/new" });

    const user = userEvent.setup();
    const substationSelect = await selectSubstation(user, "sub-pklg");
    await user.selectOptions(screen.getByLabelText("HV switchyard"), "hv-yard");
    expect(screen.getByLabelText("HV switchyard")).toHaveValue("hv-yard");

    await user.selectOptions(substationSelect, "sub-igbk");
    expect(screen.getByLabelText("HV switchyard")).toHaveValue("");
  });

  it("auto-suggests HV and LV breaker numbers once the substation, switchyards and transformer number are chosen", async () => {
    authStorage.setToken("token");
    stubFetch(baseHandlers());

    renderWithProviders(<TransformerCreatePage />, { route: "/transformers/new" });

    const user = userEvent.setup();
    await selectSubstation(user, "sub-pklg");
    await user.type(screen.getByLabelText("Bay / Transformer Number"), "2");
    await waitFor(() => {
      expect(screen.getByLabelText("HV switchyard").querySelectorAll("option").length).toBe(3);
    });
    await user.selectOptions(screen.getByLabelText("HV switchyard"), "hv-yard");
    await user.selectOptions(screen.getByLabelText("LV switchyard"), "lv-yard");

    await waitFor(() => {
      expect(screen.getByLabelText("HV breaker number")).toHaveValue("H20");
    });
    expect(screen.getByLabelText("LV breaker number")).toHaveValue("280");
  });

  it("shows no suggestion and allows manual entry when no convention exists for the pair", async () => {
    authStorage.setToken("token");
    stubFetch([
      {
        method: "GET",
        pattern: /\/reference-data\/transformer-breaker-numbering-conventions$/,
        respond: () => ({ status: 200, body: [] }),
      },
      ...baseHandlers(),
    ]);

    renderWithProviders(<TransformerCreatePage />, { route: "/transformers/new" });

    const user = userEvent.setup();
    await selectSubstation(user, "sub-pklg");
    await user.type(screen.getByLabelText("Bay / Transformer Number"), "1");
    await user.selectOptions(screen.getByLabelText("HV switchyard"), "hv-yard");
    await user.selectOptions(screen.getByLabelText("LV switchyard"), "lv-yard");

    // Give the (empty) conventions query a chance to resolve — no
    // suggestion should ever appear, and the fields remain manually
    // editable.
    await waitFor(() => expect(screen.getByLabelText("Substation")).toHaveValue("sub-pklg"));
    expect(screen.getByLabelText("HV breaker number")).toHaveValue("");
    expect(screen.getByLabelText("LV breaker number")).toHaveValue("");

    await user.type(screen.getByLabelText("HV breaker number"), "MANUAL-HV");
    expect(screen.getByLabelText("HV breaker number")).toHaveValue("MANUAL-HV");
  });

  it("lets the user freely overwrite a suggested breaker number without it being reset", async () => {
    authStorage.setToken("token");
    stubFetch(baseHandlers());

    renderWithProviders(<TransformerCreatePage />, { route: "/transformers/new" });

    const user = userEvent.setup();
    await selectSubstation(user, "sub-pklg");
    await user.type(screen.getByLabelText("Bay / Transformer Number"), "2");
    // Numbering depends on the transformation pair, not either voltage
    // alone — both switchyards must be selected before a suggestion appears.
    await user.selectOptions(screen.getByLabelText("HV switchyard"), "hv-yard");
    await user.selectOptions(screen.getByLabelText("LV switchyard"), "lv-yard");

    await waitFor(() => {
      expect(screen.getByLabelText("HV breaker number")).toHaveValue("H20");
    });

    const hvBreakerInput = screen.getByLabelText("HV breaker number");
    await user.clear(hvBreakerInput);
    await user.type(hvBreakerInput, "CUSTOM1");

    // Changing the transformer number must not clobber the already-overridden HV value.
    await user.type(screen.getByLabelText("Bay / Transformer Number"), "1");

    expect(screen.getByLabelText("HV breaker number")).toHaveValue("CUSTOM1");
  });

  it("submits the transformer create payload with substation_id and the flattened HV/LV fields", async () => {
    authStorage.setToken("token");
    let createdPayload: unknown = null;
    stubFetch([
      ...baseHandlers(),
      {
        method: "POST",
        pattern: /\/api\/v1\/transformers$/,
        respond: (_url, init) => {
          createdPayload = init?.body ? JSON.parse(init.body as string) : null;
          return {
            status: 201,
            body: {
              transformer_id: "44444444-4444-4444-4444-444444444444",
              substation_id: "sub-pklg",
              substation_mnemonic: "PKLG",
              substation_official_name: "PKLG Substation",
              transformer_number: "2",
              generated_short_name: "SGT2",
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
              terminals: [],
            },
          };
        },
      },
    ]);

    renderWithProviders(<TransformerCreatePage />, { route: "/transformers/new" });

    const user = userEvent.setup();
    await selectSubstation(user, "sub-pklg");
    await user.type(screen.getByLabelText("Bay / Transformer Number"), "2");
    await user.selectOptions(screen.getByLabelText("HV switchyard"), "hv-yard");
    await user.selectOptions(screen.getByLabelText("LV switchyard"), "lv-yard");
    await user.selectOptions(screen.getByLabelText("Initial status"), "1");
    await user.type(screen.getByLabelText("Capacity (MVA)"), "500");

    await user.click(screen.getByRole("button", { name: "Create transformer" }));

    await waitFor(() => {
      expect(createdPayload).toMatchObject({
        substation_id: "sub-pklg",
        transformer_number: "2",
        hv_switchyard_id: "hv-yard",
        hv_breaker_number: "H20",
        lv_switchyard_id: "lv-yard",
        lv_breaker_number: "280",
        operational_status_id: 1,
        capacity_mva: 500,
      });
    });
  });
});
