import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { CircuitCreatePage } from "../../src/modules/equipment_registry/pages/CircuitCreatePage";
import { renderWithProviders, stubFetch } from "../testUtils";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "admin",
  display_name: "System Administrator",
  email: null,
  status: "active" as const,
};

const VOLTAGE_YARDS = [
  {
    voltage_yard_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    substation_id: "sub-pklg",
    substation_mnemonic: "PKLG",
    substation_official_name: "PKLG Substation",
    voltage_level_id: 1,
    voltage_level_label: "500kV",
    display_label: "PKLG — 500kV",
  },
  {
    voltage_yard_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    substation_id: "sub-igbk",
    substation_mnemonic: "IGBK",
    substation_official_name: "IGBK Substation",
    voltage_level_id: 1,
    voltage_level_label: "500kV",
    display_label: "IGBK — 500kV",
  },
  {
    voltage_yard_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
    substation_id: "sub-nkst",
    substation_mnemonic: "NKST",
    substation_official_name: "NKST Substation",
    voltage_level_id: 1,
    voltage_level_label: "500kV",
    display_label: "NKST — 500kV",
  },
  {
    voltage_yard_id: "dddddddd-dddd-dddd-dddd-dddddddddddd",
    substation_id: "sub-pklg",
    substation_mnemonic: "PKLG",
    substation_official_name: "PKLG Substation",
    voltage_level_id: 2,
    voltage_level_label: "132kV",
    display_label: "PKLG — 132kV",
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
          { voltage_level_id: 2, label: "132kV", nominal_kv: 132, sort_order: 2 },
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
      respond: () => ({
        status: 200,
        body: [{ line_type_id: 1, code: "OVERHEAD", label: "Overhead Line" }],
      }),
    },
  ];
}

describe("CircuitCreatePage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("only offers Planned/Active as the initial status", async () => {
    authStorage.setToken("token");
    stubFetch(baseHandlers());

    renderWithProviders(<CircuitCreatePage />, { route: "/circuits/new" });

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

  it("starts with exactly two terminal rows, per the two-terminal minimum", async () => {
    authStorage.setToken("token");
    stubFetch(baseHandlers());

    renderWithProviders(<CircuitCreatePage />, { route: "/circuits/new" });

    await screen.findByText("Terminal 1");
    expect(screen.getByText("Terminal 2")).toBeInTheDocument();
    expect(screen.queryByText("Terminal 3")).not.toBeInTheDocument();
    // Cannot remove below the two-terminal minimum.
    expect(screen.queryByRole("button", { name: "Remove terminal" })).not.toBeInTheDocument();
  });

  it("adding a terminal row supports a tee-off with three or more terminals", async () => {
    authStorage.setToken("token");
    stubFetch(baseHandlers());

    renderWithProviders(<CircuitCreatePage />, { route: "/circuits/new" });

    await screen.findByText("Terminal 1");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Add another terminal" }));

    expect(await screen.findByText("Terminal 3")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Remove terminal" }).length).toBe(3);
  });

  it("does not offer any voltage yard until a voltage level is selected", async () => {
    authStorage.setToken("token");
    stubFetch(baseHandlers());

    renderWithProviders(<CircuitCreatePage />, { route: "/circuits/new" });

    const yardSelects = await screen.findAllByLabelText("Switchyard");
    expect(yardSelects).toHaveLength(2);
    expect(yardSelects[0]).toBeDisabled();
    const optionLabels = Array.from(yardSelects[0].querySelectorAll("option")).map((o) =>
      o.textContent?.trim(),
    );
    expect(optionLabels).toEqual(["Select..."]);
    expect(
      screen.getByText("Select a voltage level above to see the matching switchyards."),
    ).toBeInTheDocument();
  });

  it("only offers voltage yards matching the selected voltage level (rule 6a guardrail)", async () => {
    // Regression test: the terminal voltage-yard dropdown previously
    // offered every voltage yard regardless of the circuit's own voltage
    // level, letting a mismatched yard be selected (Phase 3 UAT follow-up).
    authStorage.setToken("token");
    stubFetch(baseHandlers());

    renderWithProviders(<CircuitCreatePage />, { route: "/circuits/new" });

    const user = userEvent.setup();
    const voltageLevelSelect = await screen.findByLabelText("Voltage level");
    await waitFor(() => {
      expect(voltageLevelSelect.querySelectorAll("option").length).toBeGreaterThan(1);
    });
    await user.selectOptions(voltageLevelSelect, "1");

    const yardSelects = screen.getAllByLabelText("Switchyard");
    await waitFor(() => {
      expect(yardSelects[0].querySelectorAll("option").length).toBeGreaterThan(1);
    });
    const optionLabels500kv = Array.from(yardSelects[0].querySelectorAll("option")).map((o) =>
      o.textContent?.trim(),
    );
    expect(optionLabels500kv).toEqual(["Select...", "PKLG — 500kV", "IGBK — 500kV", "NKST — 500kV"]);
    expect(optionLabels500kv).not.toContain("PKLG — 132kV");

    await user.selectOptions(screen.getByLabelText("Voltage level"), "2");
    const optionLabels132kv = Array.from(yardSelects[0].querySelectorAll("option")).map((o) =>
      o.textContent?.trim(),
    );
    expect(optionLabels132kv).toEqual(["Select...", "PKLG — 132kV"]);
  });

  it("submits a two-terminal circuit with bay_number on the circuit, breaker_number and commissioning_date per terminal", async () => {
    authStorage.setToken("token");
    let createdPayload: unknown = null;
    stubFetch([
      ...baseHandlers(),
      {
        method: "POST",
        pattern: /\/api\/v1\/circuits$/,
        respond: (_url, init) => {
          createdPayload = init?.body ? JSON.parse(init.body as string) : null;
          return {
            status: 201,
            body: {
              circuit_id: "44444444-4444-4444-4444-444444444444",
              bay_number: "1",
              circuit_name: "IGBK–PKLG",
              voltage_level_id: 1,
              line_type_id: 1,
              operational_status_id: 1,
              is_interconnector: false,
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

    renderWithProviders(<CircuitCreatePage />, { route: "/circuits/new" });

    const user = userEvent.setup();
    await user.type(await screen.findByLabelText("Bay / Circuit No."), "1");
    await user.selectOptions(screen.getByLabelText("Voltage level"), "1");
    await user.selectOptions(screen.getByLabelText("Line type"), "1");
    await user.selectOptions(screen.getByLabelText("Initial status"), "1");

    const yardSelects = screen.getAllByLabelText("Switchyard");
    const breakerInputs = screen.getAllByLabelText("Breaker number");
    const dateInputs = screen.getAllByLabelText("Commissioning date (optional)");
    expect(yardSelects).toHaveLength(2);
    expect(breakerInputs).toHaveLength(2);

    await user.selectOptions(yardSelects[0], "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    await user.type(breakerInputs[0], "L25");
    await user.type(dateInputs[0], "2020-01-15");
    await user.selectOptions(yardSelects[1], "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");
    await user.type(breakerInputs[1], "805");
    await user.click(screen.getByRole("button", { name: "Create circuit" }));

    await waitFor(() => {
      expect(createdPayload).toMatchObject({
        bay_number: "1",
        voltage_level_id: 1,
        line_type_id: 1,
        operational_status_id: 1,
        terminals: [
          {
            voltage_yard_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            breaker_number: "L25",
            commissioning_date: "2020-01-15",
          },
          {
            voltage_yard_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            breaker_number: "805",
            commissioning_date: null,
          },
        ],
      });
    });
  });
});
