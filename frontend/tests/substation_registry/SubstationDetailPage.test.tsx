import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { SubstationDetailPage } from "../../src/modules/substation_registry/pages/SubstationDetailPage";
import { renderWithProviders, stubFetch } from "../testUtils";

const SUBSTATION_ID = "33333333-3333-3333-3333-333333333333";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "admin",
  display_name: "System Administrator",
  email: null,
  status: "active" as const,
};

const SUBSTATION_DETAIL = {
  substation_id: SUBSTATION_ID,
  mnemonic: "SUB1",
  official_name: "Substation One",
  region_id: 1,
  gm_zone_id: 1,
  state_id: 1,
  grid_owner_id: 1,
  operational_status_id: 2, // PLANNED
  psse_bus_number: null,
  latitude: null,
  longitude: null,
  commissioned_date: null,
  remarks: null,
  created_at: "2026-07-02T00:00:00Z",
  updated_at: "2026-07-02T00:00:00Z",
  created_by: CURRENT_USER,
  updated_by: CURRENT_USER,
};

const REFERENCE_DATA_HANDLERS = [
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
    respond: () => ({
      status: 200,
      body: [
        { region_id: 1, code: "NORTH", label: "Northern" },
        { region_id: 2, code: "CENTRAL", label: "Central" },
      ],
    }),
  },
  {
    method: "GET",
    pattern: /\/reference-data\/gm-zones$/,
    respond: () => ({
      status: 200,
      body: [
        { gm_zone_id: 1, code: "KEDP", label: "Alor Setar" },
        { gm_zone_id: 2, code: "PPNG", label: "Butterworth" },
      ],
    }),
  },
  {
    method: "GET",
    pattern: /\/reference-data\/states$/,
    respond: () => ({
      status: 200,
      body: [
        { state_id: 1, code: "SEL", label: "Selangor" },
        { state_id: 2, code: "NSN", label: "Negeri Sembilan" },
      ],
    }),
  },
  {
    method: "GET",
    pattern: /\/reference-data\/grid-owners$/,
    respond: () => ({
      status: 200,
      body: [
        { grid_owner_id: 1, code: "TNB", label: "Tenaga Nasional Berhad (TNB)" },
        { grid_owner_id: 2, code: "IPP", label: "Independent Power Producer (IPP)" },
      ],
    }),
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
          operational_status_id: 5,
          code: "DECOMMISSIONED",
          label: "Decommissioned",
          is_terminal: false,
        },
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
  {
    method: "GET",
    pattern: /\/api\/v1\/transformers\?/,
    respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 200, total: 0 } }),
  },
  {
    method: "GET",
    pattern: /\/api\/v1\/circuits\?/,
    respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 200, total: 0 } }),
  },
];

function renderDetailPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/substations/:substationId" element={<SubstationDetailPage />} />
    </Routes>,
    { route: `/substations/${SUBSTATION_ID}` },
  );
}

describe("SubstationDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("hides the edit and status-change forms for a user without substation_registry.write", async () => {
    authStorage.setToken("token");
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
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: SUBSTATION_DETAIL }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Substation One" })).toBeInTheDocument();
    });
    // No editable surfaces for a read-only user: the Edit section and the
    // lifecycle "Change status" action are both absent.
    expect(screen.queryByRole("heading", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Change status" })).not.toBeInTheDocument();
  });

  it("only offers legal target statuses and surfaces a backend rejection inside the confirm dialog", async () => {
    authStorage.setToken("token");
    // Current status ACTIVE — its legal targets are Decommissioned and
    // Entered in Error (ADR-014); Active/Under Construction are never offered.
    const activeDetail = { ...SUBSTATION_DETAIL, operational_status_id: 1 };
    stubFetch([
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
              role: { role_id: "role-1", name: "Administrator", description: null, is_system_role: true, status: "active" },
              granted_at: "2026-01-01T00:00:00Z",
              permissions: ["substation_registry.write"],
            },
          ],
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: activeDetail }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
      {
        method: "POST",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/status$`),
        respond: () => ({
          status: 400,
          body: {
            detail: {
              code: "validation_error",
              message: "This substation was modified by another user; reload and try again.",
            },
          },
        }),
      },
    ]);

    renderDetailPage();

    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Change status" }));

    const dialog = screen.getByRole("dialog", { name: "Change substation status" });
    const targetSelect = within(dialog).getByLabelText("New status") as HTMLSelectElement;
    const offered = Array.from(targetSelect.querySelectorAll("option")).map((o) => o.textContent?.trim());
    // Only legal targets from ACTIVE — never Active/Under Construction/Planned.
    expect(offered).toEqual(["Select new status…", "Decommissioned", "Entered in Error"]);

    await user.selectOptions(targetSelect, "5");
    await user.click(within(dialog).getByRole("button", { name: "Change status" }));

    // The backend's own words are surfaced in the dialog, not a generic message.
    expect(
      await within(dialog).findByText("This substation was modified by another user; reload and try again."),
    ).toBeInTheDocument();
  });

  it("no longer shows a single 'Voltage level' field — voltage yards are the sole authoritative representation (ADR-009)", async () => {
    authStorage.setToken("token");
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
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: SUBSTATION_DETAIL }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      {
        method: "GET",
        pattern: /\/api\/v1\/voltage-yards\?/,
        respond: () => ({ status: 200, body: [] }),
      },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Substation One" })).toBeInTheDocument();
    });
    expect(screen.queryByText("Voltage level")).not.toBeInTheDocument();
  });

  function stubVoltageYardSession(
    myPermissions: string[],
    existingYards: Array<Record<string, unknown>>,
    overrideHandlers: Array<{
      method: string;
      pattern: RegExp;
      respond: (url: string, init?: RequestInit) => { status?: number; body?: unknown };
    }> = [],
  ) {
    stubFetch([
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
                role_id: "role-1",
                name: "Administrator",
                description: null,
                is_system_role: true,
                status: "active",
              },
              granted_at: "2026-01-01T00:00:00Z",
              // equipment_registry.write, not substation_registry.write —
              // voltage yards are owned by Equipment Registry
              // (equipment-registry-module.md §7.5a; ADR-008).
              permissions: myPermissions,
            },
          ],
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: SUBSTATION_DETAIL }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      {
        method: "GET",
        pattern: /\/api\/v1\/voltage-yards\?/,
        respond: () => ({ status: 200, body: existingYards }),
      },
      // Overrides must come before REFERENCE_DATA_HANDLERS — stubFetch
      // resolves the first pattern match, so an override handler (e.g. a
      // custom /transformers response) must be checked before
      // REFERENCE_DATA_HANDLERS's own default empty-transformers handler.
      ...overrideHandlers,
      ...REFERENCE_DATA_HANDLERS,
    ]);
  }

  it("excludes voltage levels the substation already has a yard at, from the add-voltage-yard dropdown (UAT regression)", async () => {
    // Regression test for a Phase 3 UAT fix-package defect: the dropdown
    // previously offered every voltage level, including ones this
    // substation already had a yard at. Picking one — the most natural
    // first attempt, since nothing distinguished them — always failed with
    // a confusing, non-actionable backend error, making the whole
    // add-voltage-yard workflow look broken.
    authStorage.setToken("token");
    stubVoltageYardSession(["equipment_registry.write"], [
      {
        voltage_yard_id: "yard-1",
        substation_id: SUBSTATION_ID,
        substation_mnemonic: "SUB1",
        substation_official_name: "Substation One",
        voltage_level_id: 1,
        voltage_level_label: "500kV",
        display_label: "SUB1 — 500kV",
        operational_status_id: 1,
      },
    ]);

    renderDetailPage();

    const yardSelect = await screen.findByLabelText("New switchyard voltage level");
    await waitFor(() => {
      expect(yardSelect.querySelectorAll("option").length).toBeGreaterThan(1);
    });
    const optionLabels = Array.from(yardSelect.querySelectorAll("option")).map((o) =>
      o.textContent?.trim(),
    );
    expect(optionLabels).toEqual(["Select voltage level...", "132kV"]);
    expect(optionLabels).not.toContain("500kV");
  });

  it("shows existing voltage yards and lets a user with equipment_registry.write add one at an available voltage level", async () => {
    authStorage.setToken("token");
    let createYardPayload: unknown = null;
    stubVoltageYardSession(
      ["equipment_registry.write"],
      [
        {
          voltage_yard_id: "yard-1",
          substation_id: SUBSTATION_ID,
          substation_mnemonic: "SUB1",
          substation_official_name: "Substation One",
          voltage_level_id: 1,
          voltage_level_label: "500kV",
          display_label: "SUB1 — 500kV",
          operational_status_id: 1,
        },
      ],
      [
        {
          method: "POST",
          pattern: /\/api\/v1\/voltage-yards$/,
          respond: (_url, init) => {
            createYardPayload = init?.body ? JSON.parse(init.body as string) : null;
            return {
              status: 201,
              body: {
                voltage_yard_id: "yard-2",
                substation_id: SUBSTATION_ID,
                substation_mnemonic: "SUB1",
                substation_official_name: "Substation One",
                voltage_level_id: 2,
                voltage_level_label: "132kV",
                display_label: "SUB1 — 132kV",
                operational_status_id: 1,
              },
            };
          },
        },
      ],
    );

    renderDetailPage();

    // Wait on the permission-gated form control itself — the roles fetch
    // (which determines canManageVoltageYards) and the voltage-yards fetch
    // resolve independently, so waiting on yard content alone can race
    // ahead of the permission-derived form rendering.
    await waitFor(() => {
      expect(screen.getByLabelText("New switchyard voltage level")).toBeInTheDocument();
    });
    // Scope to the voltage yards list specifically — voltage level is no
    // longer shown anywhere else on this page (ADR-009). Matched via a
    // function matcher (not a plain string) since the yard row now also
    // shows its status inline ("500kV (Active)"), and via getAllByText
    // since "500kV" also appears inside the field labels below it.
    expect(
      within(screen.getByTestId("voltage-yards-list")).getAllByText((_, element) =>
        element?.tagName.toLowerCase() === "li" && (element.textContent ?? "").includes("500kV"),
      ),
    ).toHaveLength(1);

    const user = userEvent.setup();
    // Only "132kV" is offered — the substation's existing "500kV" yard is
    // correctly excluded (see the regression test above).
    await user.selectOptions(screen.getByLabelText("New switchyard voltage level"), "2");
    await user.click(screen.getByRole("button", { name: "Add switchyard" }));

    await waitFor(() => {
      expect(createYardPayload).toMatchObject({
        substation_id: SUBSTATION_ID,
        voltage_level_id: 2,
      });
    });
  });

  // --- Deletion/correction policy (Phase 3 follow-up) -------------------------------
  it("lets a user with equipment_registry.write mark a switchyard as Entered in Error", async () => {
    authStorage.setToken("token");
    let updatePayload: unknown = null;
    stubVoltageYardSession(
      ["equipment_registry.write"],
      [
        {
          voltage_yard_id: "yard-1",
          substation_id: SUBSTATION_ID,
          substation_mnemonic: "SUB1",
          substation_official_name: "Substation One",
          voltage_level_id: 1,
          voltage_level_label: "500kV",
          display_label: "SUB1 — 500kV",
          operational_status_id: 1,
        },
      ],
      [
        {
          method: "PATCH",
          pattern: /\/api\/v1\/voltage-yards\/yard-1$/,
          respond: (_url, init) => {
            updatePayload = init?.body ? JSON.parse(init.body as string) : null;
            return {
              status: 200,
              body: {
                voltage_yard_id: "yard-1",
                substation_id: SUBSTATION_ID,
                substation_mnemonic: "SUB1",
                substation_official_name: "Substation One",
                voltage_level_id: 1,
                voltage_level_label: "500kV",
                display_label: "SUB1 — 500kV",
                operational_status_id: 7,
              },
            };
          },
        },
      ],
    );

    renderDetailPage();

    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    const reason = await screen.findByLabelText(
      "Reason for marking 500kV as Entered in Error",
    );
    await user.type(reason, "Created against the wrong substation");
    const button = await screen.findByRole("button", { name: "Mark as Entered in Error" });
    await user.click(button);

    await waitFor(() => {
      expect(updatePayload).toMatchObject({
        operational_status_id: 7,
        change_reason: "Created against the wrong substation",
      });
    });
    expect(confirmSpy).toHaveBeenCalled();
    confirmSpy.mockRestore();
    // Never a "Delete" button anywhere for a switchyard (CLAUDE.md §11.6 —
    // no hard delete for engineering registry records).
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });

  it("does not offer to correct a switchyard without equipment_registry.write", async () => {
    authStorage.setToken("token");
    stubVoltageYardSession(["substation_registry.write"], [
      {
        voltage_yard_id: "yard-1",
        substation_id: SUBSTATION_ID,
        substation_mnemonic: "SUB1",
        substation_official_name: "Substation One",
        voltage_level_id: 1,
        voltage_level_label: "500kV",
        display_label: "SUB1 — 500kV",
        operational_status_id: 1,
      },
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(
        within(screen.getByTestId("voltage-yards-list")).getByText(/500kV/),
      ).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("button", { name: "Mark as Entered in Error" }),
    ).not.toBeInTheDocument();
  });

  it("hides an entered-in-error switchyard by default and reveals it via the toggle", async () => {
    authStorage.setToken("token");
    stubVoltageYardSession(["equipment_registry.write"], [
      {
        voltage_yard_id: "yard-1",
        substation_id: SUBSTATION_ID,
        substation_mnemonic: "SUB1",
        substation_official_name: "Substation One",
        voltage_level_id: 1,
        voltage_level_label: "500kV",
        display_label: "SUB1 — 500kV",
        operational_status_id: 7,
      },
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByText("No switchyards registered yet.")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.click(screen.getByLabelText("Show entered-in-error switchyards"));

    // Matched via a function matcher, not a plain regex, since "500kV"
    // also appears inside this row's own field labels once it renders
    // editable (canWrite=true here).
    await waitFor(() => {
      expect(
        within(screen.getByTestId("voltage-yards-list")).getAllByText((_, element) =>
          element?.tagName.toLowerCase() === "li" &&
          (element.textContent ?? "").includes("Entered in Error"),
        ),
      ).toHaveLength(1);
    });
  });


  /* Voltage Yard restoration (ADR-027). The two lifecycle actions are mutually
     exclusive: an active yard offers "Mark as Entered in Error", an
     entered-in-error yard offers "Restore Voltage Yard". Neither is ever
     presented as a delete/undelete. */
  const ENTERED_IN_ERROR_YARD = {
    voltage_yard_id: "yard-1",
    substation_id: SUBSTATION_ID,
    substation_mnemonic: "SUB1",
    substation_official_name: "Substation One",
    voltage_level_id: 1,
    voltage_level_label: "500kV",
    display_label: "SUB1 — 500kV",
    operational_status_id: 7,
  };

  it("offers Restore Voltage Yard only for an entered-in-error switchyard", async () => {
    authStorage.setToken("token");
    stubVoltageYardSession(["equipment_registry.write"], [ENTERED_IN_ERROR_YARD]);

    renderDetailPage();

    const user = userEvent.setup();
    await user.click(await screen.findByLabelText(/show entered-in-error/i));

    expect(
      await screen.findByRole("button", { name: "Restore Voltage Yard" }),
    ).toBeInTheDocument();
    // Mutually exclusive with the correction action, and never a delete/undelete.
    expect(
      screen.queryByRole("button", { name: "Mark as Entered in Error" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /undelete/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
  });

  it("does not offer Restore Voltage Yard for an active switchyard", async () => {
    authStorage.setToken("token");
    stubVoltageYardSession(["equipment_registry.write"], [
      { ...ENTERED_IN_ERROR_YARD, operational_status_id: 1 },
    ]);

    renderDetailPage();

    expect(
      await screen.findByRole("button", { name: "Mark as Entered in Error" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Restore Voltage Yard" }),
    ).not.toBeInTheDocument();
  });

  it("does not offer Restore Voltage Yard without equipment_registry.write", async () => {
    authStorage.setToken("token");
    stubVoltageYardSession(["substation_registry.write"], [ENTERED_IN_ERROR_YARD]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByTestId("voltage-yards-list")).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("button", { name: "Restore Voltage Yard" }),
    ).not.toBeInTheDocument();
  });

  it("requires a reason and a confirmation before restoring", async () => {
    authStorage.setToken("token");
    let restoreCalls = 0;
    stubVoltageYardSession(
      ["equipment_registry.write"],
      [ENTERED_IN_ERROR_YARD],
      [
        {
          method: "POST",
          pattern: /\/api\/v1\/voltage-yards\/yard-1\/restore$/,
          respond: () => {
            restoreCalls += 1;
            return { status: 200, body: { ...ENTERED_IN_ERROR_YARD, operational_status_id: 1 } };
          },
        },
      ],
    );

    renderDetailPage();
    const user = userEvent.setup();
    await user.click(await screen.findByLabelText(/show entered-in-error/i));

    // No reason -> refused client-side, nothing sent.
    await user.click(await screen.findByRole("button", { name: "Restore Voltage Yard" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/reason is required/i);
    expect(restoreCalls).toBe(0);

    // Reason present but confirmation declined -> still nothing sent.
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    await user.type(
      await screen.findByLabelText("Reason for restoring 500kV"),
      "Marked in error by mistake",
    );
    await user.click(screen.getByRole("button", { name: "Restore Voltage Yard" }));
    expect(restoreCalls).toBe(0);
    confirmSpy.mockRestore();
  });

  it("restores an entered-in-error switchyard to Active and confirms success", async () => {
    authStorage.setToken("token");
    let restorePayload: unknown = null;
    let restoreUrl = "";
    stubVoltageYardSession(
      ["equipment_registry.write"],
      [ENTERED_IN_ERROR_YARD],
      [
        {
          method: "POST",
          pattern: /\/api\/v1\/voltage-yards\/yard-1\/restore$/,
          respond: (url, init) => {
            restoreUrl = url;
            restorePayload = init?.body ? JSON.parse(init.body as string) : null;
            return { status: 200, body: { ...ENTERED_IN_ERROR_YARD, operational_status_id: 1 } };
          },
        },
      ],
    );

    renderDetailPage();
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    await user.click(await screen.findByLabelText(/show entered-in-error/i));
    await user.type(
      await screen.findByLabelText("Reason for restoring 500kV"),
      "Marked in error by mistake",
    );
    await user.click(screen.getByRole("button", { name: "Restore Voltage Yard" }));

    await waitFor(() => {
      expect(restorePayload).toEqual({ change_reason: "Marked in error by mistake" });
    });
    // A dedicated lifecycle command — no operational_status_id is ever sent.
    expect(restoreUrl).toMatch(/\/voltage-yards\/yard-1\/restore$/);
    expect(restorePayload).not.toHaveProperty("operational_status_id");
    expect(confirmSpy).toHaveBeenCalled();
    expect(await screen.findByRole("status")).toHaveTextContent(/restored to Active/i);
    confirmSpy.mockRestore();
  });

  it("surfaces a backend lifecycle error such as an incompatible parent substation", async () => {
    authStorage.setToken("token");
    stubVoltageYardSession(
      ["equipment_registry.write"],
      [ENTERED_IN_ERROR_YARD],
      [
        {
          method: "POST",
          pattern: /\/api\/v1\/voltage-yards\/yard-1\/restore$/,
          respond: () => ({
            status: 400,
            body: {
              detail: {
                code: "validation_error",
                message:
                  "Switchyard cannot be restored while its substation 'SUB1' is " +
                  "'DECOMMISSIONED' — restore or correct the substation first.",
              },
            },
          }),
        },
      ],
    );

    renderDetailPage();
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    await user.click(await screen.findByLabelText(/show entered-in-error/i));
    await user.type(
      await screen.findByLabelText("Reason for restoring 500kV"),
      "Attempting restore",
    );
    await user.click(screen.getByRole("button", { name: "Restore Voltage Yard" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/DECOMMISSIONED/);
    confirmSpy.mockRestore();
  });

  it("submits commissioning date, latitude, and longitude when adding a voltage yard", async () => {
    authStorage.setToken("token");
    let createYardPayload: unknown = null;
    stubVoltageYardSession(
      ["equipment_registry.write"],
      [
        {
          voltage_yard_id: "yard-1",
          substation_id: SUBSTATION_ID,
          substation_mnemonic: "SUB1",
          substation_official_name: "Substation One",
          voltage_level_id: 1,
          voltage_level_label: "500kV",
          display_label: "SUB1 — 500kV",
          operational_status_id: 1,
          commissioning_date: null,
          latitude: null,
          longitude: null,
        },
      ],
      [
        {
          method: "POST",
          pattern: /\/api\/v1\/voltage-yards$/,
          respond: (_url, init) => {
            createYardPayload = init?.body ? JSON.parse(init.body as string) : null;
            return {
              status: 201,
              body: {
                voltage_yard_id: "yard-2",
                substation_id: SUBSTATION_ID,
                substation_mnemonic: "SUB1",
                substation_official_name: "Substation One",
                voltage_level_id: 2,
                voltage_level_label: "132kV",
                display_label: "SUB1 — 132kV",
                operational_status_id: 1,
                commissioning_date: "2020-06-01",
                latitude: 3.140853,
                longitude: 101.693207,
              },
            };
          },
        },
      ],
    );

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByLabelText("New switchyard voltage level")).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("New switchyard voltage level"), "2");
    await user.type(
      screen.getByLabelText("New switchyard commissioning date"),
      "2020-06-01",
    );
    await user.type(screen.getByLabelText("New switchyard latitude"), "3.140853");
    await user.type(screen.getByLabelText("New switchyard longitude"), "101.693207");
    await user.click(screen.getByRole("button", { name: "Add switchyard" }));

    await waitFor(() => {
      expect(createYardPayload).toMatchObject({
        substation_id: SUBSTATION_ID,
        voltage_level_id: 2,
        commissioning_date: "2020-06-01",
        latitude: 3.140853,
        longitude: 101.693207,
      });
    });
  });

  it("displays a voltage yard's commissioning date and coordinates, and lets an authorized user edit them", async () => {
    authStorage.setToken("token");
    let updateYardPayload: unknown = null;
    let updatedYardId: string | null = null;
    stubVoltageYardSession(
      ["equipment_registry.write"],
      [
        {
          voltage_yard_id: "yard-1",
          substation_id: SUBSTATION_ID,
          substation_mnemonic: "SUB1",
          substation_official_name: "Substation One",
          voltage_level_id: 1,
          voltage_level_label: "500kV",
          display_label: "SUB1 — 500kV",
          operational_status_id: 1,
          commissioning_date: "2018-01-01",
          latitude: 3.0,
          longitude: 101.0,
        },
      ],
      [
        {
          method: "PATCH",
          pattern: /\/api\/v1\/voltage-yards\/yard-1$/,
          respond: (url, init) => {
            updatedYardId = url;
            updateYardPayload = init?.body ? JSON.parse(init.body as string) : null;
            return {
              status: 200,
              body: {
                voltage_yard_id: "yard-1",
                substation_id: SUBSTATION_ID,
                substation_mnemonic: "SUB1",
                substation_official_name: "Substation One",
                voltage_level_id: 1,
                voltage_level_label: "500kV",
                display_label: "SUB1 — 500kV",
                operational_status_id: 1,
                commissioning_date: "2021-03-15",
                latitude: 3.5,
                longitude: 101.5,
              },
            };
          },
        },
      ],
    );

    renderDetailPage();

    const commissioningDateInput = await screen.findByLabelText("Commissioning date for 500kV");
    expect(commissioningDateInput).toHaveValue("2018-01-01");
    expect(screen.getByLabelText("Latitude for 500kV")).toHaveValue(3);
    expect(screen.getByLabelText("Longitude for 500kV")).toHaveValue(101);

    const user = userEvent.setup();
    await user.clear(commissioningDateInput);
    await user.type(commissioningDateInput, "2021-03-15");
    const latitudeInput = screen.getByLabelText("Latitude for 500kV");
    await user.clear(latitudeInput);
    await user.type(latitudeInput, "3.5");
    const longitudeInput = screen.getByLabelText("Longitude for 500kV");
    await user.clear(longitudeInput);
    await user.type(longitudeInput, "101.5");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(updateYardPayload).toMatchObject({
        commissioning_date: "2021-03-15",
        latitude: 3.5,
        longitude: 101.5,
      });
    });
    expect(updatedYardId).toContain("yard-1");
  });

  it("shows read-only commissioning date and coordinates without equipment_registry.write", async () => {
    authStorage.setToken("token");
    stubVoltageYardSession(["substation_registry.write"], [
      {
        voltage_yard_id: "yard-1",
        substation_id: SUBSTATION_ID,
        substation_mnemonic: "SUB1",
        substation_official_name: "Substation One",
        voltage_level_id: 1,
        voltage_level_label: "500kV",
        display_label: "SUB1 — 500kV",
        operational_status_id: 1,
        commissioning_date: "2018-01-01",
        latitude: 3.0,
        longitude: 101.0,
      },
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(
        within(screen.getByTestId("voltage-yards-list")).getByText(/2018-01-01/),
      ).toBeInTheDocument();
    });
    expect(screen.queryByLabelText("Commissioning date for 500kV")).not.toBeInTheDocument();
  });

  it("shows a clear message instead of the form when every voltage level already has a yard", async () => {
    authStorage.setToken("token");
    stubVoltageYardSession(["equipment_registry.write"], [
      {
        voltage_yard_id: "yard-1",
        substation_id: SUBSTATION_ID,
        substation_mnemonic: "SUB1",
        substation_official_name: "Substation One",
        voltage_level_id: 1,
        voltage_level_label: "500kV",
        display_label: "SUB1 — 500kV",
        operational_status_id: 1,
      },
      {
        voltage_yard_id: "yard-2",
        substation_id: SUBSTATION_ID,
        substation_mnemonic: "SUB1",
        substation_official_name: "Substation One",
        voltage_level_id: 2,
        voltage_level_label: "132kV",
        display_label: "SUB1 — 132kV",
        operational_status_id: 1,
      },
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(
        screen.getByText("This substation already has a switchyard at every known voltage level."),
      ).toBeInTheDocument();
    });
    expect(
      screen.queryByLabelText("New switchyard voltage level"),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add switchyard" })).not.toBeInTheDocument();
  });

  it("does not offer to add a voltage yard without equipment_registry.write", async () => {
    authStorage.setToken("token");
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
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: SUBSTATION_DETAIL }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      {
        method: "GET",
        pattern: /\/api\/v1\/voltage-yards\?/,
        respond: () => ({ status: 200, body: [] }),
      },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByText("No switchyards registered yet.")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Add switchyard" })).not.toBeInTheDocument();
  });

  it("shows which transformers are installed at this substation (UAT requirement)", async () => {
    authStorage.setToken("token");
    stubVoltageYardSession(
      [],
      [
        {
          voltage_yard_id: "yard-1",
          substation_id: SUBSTATION_ID,
          substation_mnemonic: "SUB1",
          substation_official_name: "Substation One",
          voltage_level_id: 1,
          voltage_level_label: "500kV",
          display_label: "SUB1 — 500kV",
          operational_status_id: 1,
        },
      ],
      [
        {
          method: "GET",
          pattern: /\/api\/v1\/transformers\?/,
          respond: () => ({
            status: 200,
            body: {
              items: [
                {
                  transformer_id: "txf-1",
                  substation_id: SUBSTATION_ID,
                  substation_mnemonic: "SUB1",
                  substation_official_name: "Substation One",
                  transformer_number: "1",
                  generated_short_name: "XGT1",
                  hv_voltage_level_label: "500kV",
                  lv_voltage_level_label: "132kV",
                  capacity_mva: 500,
                  operational_status_id: 1,
                },
              ],
              page: 1,
              page_size: 200,
              total: 1,
            },
          }),
        },
      ],
    );

    renderDetailPage();

    await waitFor(() => {
      expect(within(screen.getByTestId("transformers-list")).getByText("XGT1")).toBeInTheDocument();
    });
    expect(screen.getByText(/500kV ↔ 132kV/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "XGT1" })).toHaveAttribute(
      "href",
      "/transformers/txf-1",
    );
  });

  it("shows a message when no transformers are installed at this substation", async () => {
    authStorage.setToken("token");
    stubVoltageYardSession([], []);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByText("No transformers installed here yet.")).toBeInTheDocument();
    });
  });

  it("renders the Engineering Connectivity section with connected circuits", async () => {
    authStorage.setToken("token");
    stubVoltageYardSession(
      [],
      [],
      [
        {
          method: "GET",
          pattern: /\/api\/v1\/circuits\?/,
          respond: () => ({
            status: 200,
            body: {
              items: [
                {
                  circuit_id: "circuit-1",
                  bay_number: "1",
                  circuit_name: "IGBK–SUB1",
                  voltage_level_id: 1,
                  line_type_id: 1,
                  operational_status_id: 1,
                  is_interconnector: false,
                  terminal_count: 2,
                },
              ],
              page: 1,
              page_size: 200,
              total: 1,
            },
          }),
        },
      ],
    );

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Engineering Connectivity" })).toBeInTheDocument();
    });
    expect(screen.getByTestId("connected-circuits-count")).toHaveTextContent(
      "Connected Circuits: 1",
    );
    const table = screen.getByTestId("engineering-connectivity-table");
    expect(within(table).getByText("IGBK–SUB1")).toBeInTheDocument();
    expect(within(table).getByText("1")).toBeInTheDocument();
    expect(within(table).getByText("500kV")).toBeInTheDocument();
    expect(within(table).getByText("Overhead Line")).toBeInTheDocument();
    expect(within(table).getByText("Active")).toBeInTheDocument();
    // "Other Connected Substations" excludes this substation's own mnemonic (SUB1).
    expect(within(table).getByText("IGBK")).toBeInTheDocument();
    expect(within(table).getByRole("link", { name: "View" })).toHaveAttribute(
      "href",
      "/circuits/circuit-1",
    );
  });

  it("shows the empty-state message when no circuits are connected to this substation", async () => {
    authStorage.setToken("token");
    stubVoltageYardSession([], []);

    renderDetailPage();

    await waitFor(() => {
      expect(
        screen.getByText("No connected circuits recorded in the engineering registry."),
      ).toBeInTheDocument();
    });
    expect(screen.queryByTestId("engineering-connectivity-table")).not.toBeInTheDocument();
  });

  it("lets a user with substation_registry.write submit an edit", async () => {
    authStorage.setToken("token");
    let updatePayload: unknown = null;
    stubFetch([
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
                role_id: "role-1",
                name: "Administrator",
                description: null,
                is_system_role: true,
                status: "active",
              },
              granted_at: "2026-01-01T00:00:00Z",
              permissions: ["substation_registry.write"],
            },
          ],
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: SUBSTATION_DETAIL }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
      {
        method: "PATCH",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: (_url, init) => {
          updatePayload = init?.body ? JSON.parse(init.body as string) : null;
          return { status: 200, body: { ...SUBSTATION_DETAIL, official_name: "Renamed" } };
        },
      },
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Edit" })).toBeInTheDocument();
    });

    const user = userEvent.setup();
    const nameInput = screen.getByLabelText("Official name");
    await user.clear(nameInput);
    await user.type(nameInput, "Renamed");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(updatePayload).toMatchObject({ official_name: "Renamed" });
    });
  });

  it("displays the assigned GM Zone in the detail view", async () => {
    authStorage.setToken("token");
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
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: SUBSTATION_DETAIL }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByText("Alor Setar")).toBeInTheDocument();
    });
    // The detail workspace keeps the FULL engineering label for Grid Owner
    // (the compact abbreviation is a registry-list presentation choice only).
    expect(screen.getByText("Tenaga Nasional Berhad (TNB)")).toBeInTheDocument();
  });

  it("requires GM Zone in the edit form", async () => {
    authStorage.setToken("token");
    stubFetch([
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
                role_id: "role-1",
                name: "Administrator",
                description: null,
                is_system_role: true,
                status: "active",
              },
              granted_at: "2026-01-01T00:00:00Z",
              permissions: ["substation_registry.write"],
            },
          ],
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: { ...SUBSTATION_DETAIL, operational_status_id: 1 } }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Edit" })).toBeInTheDocument();
    });
    expect(screen.getByLabelText("GM Zone")).toBeRequired();
  });

  it("submits an edited GM Zone", async () => {
    authStorage.setToken("token");
    let updatePayload: unknown = null;
    stubFetch([
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
                role_id: "role-1",
                name: "Administrator",
                description: null,
                is_system_role: true,
                status: "active",
              },
              granted_at: "2026-01-01T00:00:00Z",
              permissions: ["substation_registry.write"],
            },
          ],
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: SUBSTATION_DETAIL }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
      {
        method: "PATCH",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: (_url, init) => {
          updatePayload = init?.body ? JSON.parse(init.body as string) : null;
          return { status: 200, body: { ...SUBSTATION_DETAIL, gm_zone_id: 2 } };
        },
      },
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Edit" })).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("GM Zone"), "2");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(updatePayload).toMatchObject({ gm_zone_id: 2 });
    });
  });

  it("preloads the current Region, State, and Grid Owner in the edit form", async () => {
    authStorage.setToken("token");
    stubFetch([
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
                role_id: "role-1",
                name: "Administrator",
                description: null,
                is_system_role: true,
                status: "active",
              },
              granted_at: "2026-01-01T00:00:00Z",
              permissions: ["substation_registry.write"],
            },
          ],
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: SUBSTATION_DETAIL }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Edit" })).toBeInTheDocument();
    });

    expect((screen.getByLabelText("Region") as HTMLSelectElement).value).toBe("1");
    expect((screen.getByLabelText("State (Optional)") as HTMLSelectElement).value).toBe("1");
    expect((screen.getByLabelText("Grid owner") as HTMLSelectElement).value).toBe("1");
  });

  it("submits multiple organizational metadata changes (Region, State, Grid Owner, GM Zone) in one request", async () => {
    authStorage.setToken("token");
    let updatePayload: unknown = null;
    stubFetch([
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
                role_id: "role-1",
                name: "Administrator",
                description: null,
                is_system_role: true,
                status: "active",
              },
              granted_at: "2026-01-01T00:00:00Z",
              permissions: ["substation_registry.write"],
            },
          ],
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: SUBSTATION_DETAIL }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
      {
        method: "PATCH",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: (_url, init) => {
          updatePayload = init?.body ? JSON.parse(init.body as string) : null;
          return {
            status: 200,
            body: { ...SUBSTATION_DETAIL, region_id: 2, gm_zone_id: 2, state_id: 2, grid_owner_id: 2 },
          };
        },
      },
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Edit" })).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Region"), "2");
    await user.selectOptions(screen.getByLabelText("GM Zone"), "2");
    await user.selectOptions(screen.getByLabelText("State (Optional)"), "2");
    await user.selectOptions(screen.getByLabelText("Grid owner"), "2");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(updatePayload).toMatchObject({
        region_id: 2,
        gm_zone_id: 2,
        state_id: 2,
        grid_owner_id: 2,
      });
    });
  });

  it("displays '—' for a substation that has no State (ADR-026)", async () => {
    authStorage.setToken("token");
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
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: { ...SUBSTATION_DETAIL, state_id: null } }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Substation One" })).toBeInTheDocument();
    });
    // The State term's value renders as an em dash, never "null" or a
    // placeholder State.
    const stateDd = screen.getByText("State", { selector: "dt" }).nextElementSibling;
    expect(stateDd?.textContent).toBe("—");
  });

  it("clears a substation's State when 'None' is selected and saved (ADR-026)", async () => {
    authStorage.setToken("token");
    let updatePayload: Record<string, unknown> | null = null;
    stubFetch([
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
                role_id: "role-1",
                name: "Administrator",
                description: null,
                is_system_role: true,
                status: "active",
              },
              granted_at: "2026-01-01T00:00:00Z",
              permissions: ["substation_registry.write"],
            },
          ],
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: SUBSTATION_DETAIL }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
      {
        method: "PATCH",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: (_url, init) => {
          updatePayload = init?.body ? JSON.parse(init.body as string) : null;
          return { status: 200, body: { ...SUBSTATION_DETAIL, state_id: null } };
        },
      },
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Edit" })).toBeInTheDocument();
    });
    // The current State (id 1) is preloaded; choosing "None" clears it.
    const stateSelect = screen.getByLabelText("State (Optional)") as HTMLSelectElement;
    expect(stateSelect.value).toBe("1");
    const user = userEvent.setup();
    await user.selectOptions(stateSelect, "");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(updatePayload).not.toBeNull();
    });
    // An explicit null clears it — never omitted, never a placeholder.
    expect(updatePayload).toHaveProperty("state_id", null);
  });

  it("displays a backend validation error when the edit form submission fails", async () => {
    authStorage.setToken("token");
    stubFetch([
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
                role_id: "role-1",
                name: "Administrator",
                description: null,
                is_system_role: true,
                status: "active",
              },
              granted_at: "2026-01-01T00:00:00Z",
              permissions: ["substation_registry.write"],
            },
          ],
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({ status: 200, body: SUBSTATION_DETAIL }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`),
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }),
      },
      ...REFERENCE_DATA_HANDLERS,
      {
        method: "PATCH",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`),
        respond: () => ({
          status: 400,
          body: {
            detail: {
              code: "validation_error",
              message: "region_id '99999' is not a recognized reference data value.",
            },
          },
        }),
      },
    ]);

    renderDetailPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Edit" })).toBeInTheDocument();
    });

    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Region"), "2");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => {
      expect(
        screen.getByText("region_id '99999' is not a recognized reference data value."),
      ).toBeInTheDocument();
    });
  });

  function stubActiveWriteSession(onStatusPost?: (payload: unknown) => { status?: number; body?: unknown }) {
    const activeDetail = { ...SUBSTATION_DETAIL, operational_status_id: 1 };
    stubFetch([
      { method: "GET", pattern: /\/api\/v1\/users\/me$/, respond: () => ({ status: 200, body: CURRENT_USER }) },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/users/${CURRENT_USER.user_id}/roles$`),
        respond: () => ({
          status: 200,
          body: [
            {
              role: { role_id: "role-1", name: "Administrator", description: null, is_system_role: true, status: "active" },
              granted_at: "2026-01-01T00:00:00Z",
              permissions: ["substation_registry.write"],
            },
          ],
        }),
      },
      { method: "GET", pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`), respond: () => ({ status: 200, body: activeDetail }) },
      { method: "GET", pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`), respond: () => ({ status: 200, body: [] }) },
      { method: "GET", pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`), respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 50, total: 0 } }) },
      { method: "GET", pattern: /\/api\/v1\/voltage-yards\?/, respond: () => ({ status: 200, body: [] }) },
      ...REFERENCE_DATA_HANDLERS,
      {
        method: "POST",
        pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/status$`),
        respond: (_url, init) => (onStatusPost ? onStatusPost(init?.body ? JSON.parse(init.body as string) : null) : { status: 200, body: activeDetail }),
      },
    ]);
  }

  it("makes no status request when the confirmation dialog is cancelled", async () => {
    authStorage.setToken("token");
    let statusCalls = 0;
    stubActiveWriteSession(() => {
      statusCalls += 1;
      return { status: 200, body: SUBSTATION_DETAIL };
    });

    renderDetailPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Change status" }));
    const dialog = screen.getByRole("dialog", { name: "Change substation status" });
    await user.selectOptions(within(dialog).getByLabelText("New status"), "5");
    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Change substation status" })).toBeNull());
    expect(statusCalls).toBe(0);
  });

  it("applies a legal status change and closes the dialog", async () => {
    authStorage.setToken("token");
    let statusPayload: unknown = null;
    stubActiveWriteSession((payload) => {
      statusPayload = payload;
      return { status: 200, body: { ...SUBSTATION_DETAIL, operational_status_id: 5 } };
    });

    renderDetailPage();
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Change status" }));
    const dialog = screen.getByRole("dialog", { name: "Change substation status" });
    await user.selectOptions(within(dialog).getByLabelText("New status"), "5");
    await user.type(within(dialog).getByLabelText("Change reason"), "End of service life");
    await user.click(within(dialog).getByRole("button", { name: "Change status" }));

    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Change substation status" })).toBeNull());
    expect(statusPayload).toMatchObject({ operational_status_id: 5, change_reason: "End of service life" });
  });

  it("shows a not-found state for a substation that does not exist", async () => {
    authStorage.setToken("token");
    stubFetch([
      { method: "GET", pattern: /\/api\/v1\/users\/me$/, respond: () => ({ status: 200, body: CURRENT_USER }) },
      { method: "GET", pattern: new RegExp(`/api/v1/users/${CURRENT_USER.user_id}/roles$`), respond: () => ({ status: 200, body: [] }) },
      { method: "GET", pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}$`), respond: () => ({ status: 404, body: { detail: "Substation not found" } }) },
      { method: "GET", pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/aliases$`), respond: () => ({ status: 404, body: { detail: "Substation not found" } }) },
      { method: "GET", pattern: new RegExp(`/api/v1/substations/${SUBSTATION_ID}/audit-log`), respond: () => ({ status: 404, body: { detail: "Substation not found" } }) },
      { method: "GET", pattern: /\/api\/v1\/voltage-yards\?/, respond: () => ({ status: 200, body: [] }) },
      ...REFERENCE_DATA_HANDLERS,
    ]);

    renderDetailPage();

    expect(await screen.findByText("Substation not found")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Back to Substation Registry/ })).toHaveAttribute("href", "/substations");
  });
});
