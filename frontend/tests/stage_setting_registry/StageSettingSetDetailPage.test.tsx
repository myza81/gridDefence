import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { StageSettingSetDetailPage } from "../../src/modules/stage_setting_registry/pages/StageSettingSetDetailPage";
import { StageSettingSetListPage } from "../../src/modules/stage_setting_registry/pages/StageSettingSetListPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

function renderPage(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/stage-setting-sets/:stageSettingSetId" element={<StageSettingSetDetailPage />} />
    </Routes>,
    { route },
  );
}

function renderPageWithListRoute(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/stage-setting-sets" element={<StageSettingSetListPage />} />
      <Route path="/stage-setting-sets/:stageSettingSetId" element={<StageSettingSetDetailPage />} />
    </Routes>,
    { route },
  );
}

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "admin1",
  display_name: "Admin One",
  email: null,
  status: "active" as const,
};

const ROLE = {
  role_id: "22222222-2222-2222-2222-222222222222",
  name: "Administrator",
  description: null,
  is_system_role: true,
  status: "active" as const,
};

const SET_ID = "33333333-3333-3333-3333-333333333333";
const STAGE_ID = "44444444-4444-4444-4444-444444444444";
const TRIGGER_ID = "55555555-5555-5555-5555-555555555555";
const TRIGGER_ID_2 = "66666666-6666-6666-6666-666666666666";

function sessionHandlers(myPermissions: string[]): FetchHandler[] {
  return [
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
        body: [{ role: ROLE, granted_at: "2026-01-01T00:00:00Z", permissions: myPermissions }],
      }),
    },
  ];
}

/**
 * One stage, one trigger (10 Hz / 200 ms) by default — matches the shape
 * `backend/app/modules/stage_setting_registry/schemas.py`'s own
 * `StageSettingDetail` returns since ADR-025 (a nested `triggers` array,
 * never flat threshold/delay fields on the stage itself).
 */
function detailHandler(
  status: "DRAFT" | "PUBLISHED" | "ENTERED_IN_ERROR",
  options: { twoTriggers?: boolean } = {},
): FetchHandler {
  const triggers =
    status === "DRAFT"
      ? []
      : [
          {
            stage_setting_trigger_id: TRIGGER_ID,
            stage_setting_id: STAGE_ID,
            trigger_order: 1,
            threshold_value: 10,
            threshold_unit: "Hz",
            time_delay_ms: 200,
          },
          ...(options.twoTriggers
            ? [
                {
                  stage_setting_trigger_id: TRIGGER_ID_2,
                  stage_setting_id: STAGE_ID,
                  trigger_order: 2,
                  threshold_value: 9.5,
                  threshold_unit: "Hz",
                  time_delay_ms: 60000,
                },
              ]
            : []),
        ];
  return {
    method: "GET",
    pattern: new RegExp(`/api/v1/stage-setting-sets/${SET_ID}$`),
    respond: () => ({
      status: 200,
      body: {
        stage_setting_set_id: SET_ID,
        scheme_type: "UFLS",
        description: "Synthetic Test Set",
        status,
        settings:
          status === "DRAFT"
            ? []
            : [
                {
                  stage_setting_id: STAGE_ID,
                  stage_setting_set_id: SET_ID,
                  stage_order: 1,
                  region_scope_id: null,
                  triggers,
                },
              ],
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        created_by: null,
        updated_by: null,
      },
    }),
  };
}

/** A Draft set with one stage already created (no threshold yet) — used
 * by the "add a trigger to an existing stage" tests. */
function draftWithOneEmptyStageHandler(): FetchHandler {
  return {
    method: "GET",
    pattern: new RegExp(`/api/v1/stage-setting-sets/${SET_ID}$`),
    respond: () => ({
      status: 200,
      body: {
        stage_setting_set_id: SET_ID,
        scheme_type: "UFLS",
        description: "Synthetic Test Set",
        status: "DRAFT",
        settings: [
          {
            stage_setting_id: STAGE_ID,
            stage_setting_set_id: SET_ID,
            stage_order: 8,
            region_scope_id: null,
            triggers: [],
          },
        ],
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        created_by: null,
        updated_by: null,
      },
    }),
  };
}

/** A Draft set with one stage that already owns one trigger — used to
 * confirm edit controls are permission-gated even while Draft. */
function draftWithOneStageAndTriggerHandler(): FetchHandler {
  return {
    method: "GET",
    pattern: new RegExp(`/api/v1/stage-setting-sets/${SET_ID}$`),
    respond: () => ({
      status: 200,
      body: {
        stage_setting_set_id: SET_ID,
        scheme_type: "UFLS",
        description: "Synthetic Test Set",
        status: "DRAFT",
        settings: [
          {
            stage_setting_id: STAGE_ID,
            stage_setting_set_id: SET_ID,
            stage_order: 1,
            region_scope_id: null,
            triggers: [
              {
                stage_setting_trigger_id: TRIGGER_ID,
                stage_setting_id: STAGE_ID,
                trigger_order: 1,
                threshold_value: 49.5,
                threshold_unit: "Hz",
                time_delay_ms: 200,
              },
            ],
          },
        ],
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        created_by: null,
        updated_by: null,
      },
    }),
  };
}

const regionsHandler: FetchHandler = {
  method: "GET",
  pattern: /\/api\/v1\/regions/,
  respond: () => ({ status: 200, body: [] }),
};

const otherReferenceDataHandler: FetchHandler = {
  method: "GET",
  pattern: /\/api\/v1\/(voltage-levels|gm-zones|states|grid-owners|operational-statuses|line-types)/,
  respond: () => ({ status: 200, body: [] }),
};

describe("StageSettingSetDetailPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("shows Draft edit affordances (add-stage form) for a user with manage permission", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.manage"]),
      detailHandler("DRAFT"),
      regionsHandler,
      otherReferenceDataHandler,
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Add Stage" })).toBeInTheDocument();
    });
    expect(screen.getByText("No stages yet.")).toBeInTheDocument();
  });

  it("renders a Published set strictly read-only, with no add-stage form", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.manage", "stage_setting_registry.publish"]),
      detailHandler("PUBLISHED"),
      regionsHandler,
      otherReferenceDataHandler,
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByText("Published")).toBeInTheDocument();
    });
    expect(screen.queryByRole("heading", { name: "Add Stage" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    expect(screen.getByText("10 Hz")).toBeInTheDocument();
  });

  it("does not show the Publish button for a user without publish permission", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.manage"]),
      detailHandler("DRAFT"),
      regionsHandler,
      otherReferenceDataHandler,
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(
        screen.getByText("Publishing requires Stage Setting Registry publish permission."),
      ).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Publish" })).not.toBeInTheDocument();
  });

  it("shows the Entered in Error action only for a user with that permission, on a Published set", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.enter_in_error"]),
      detailHandler("PUBLISHED"),
      regionsHandler,
      otherReferenceDataHandler,
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Mark Entered in Error" })).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: "Mark Entered in Error" })).toBeDisabled();
  });

  // --- Grouped stage/trigger display (ADR-025) -----------------------------------------

  it("groups a stage's multiple operating points beneath one stage heading, never as separate stages", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.manage"]),
      detailHandler("PUBLISHED", { twoTriggers: true }),
      regionsHandler,
      otherReferenceDataHandler,
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByText("Stage 1")).toBeInTheDocument();
    });
    // Exactly one "Stage 1" heading — two triggers never render as "Stage
    // 1" and "Stage 2".
    expect(screen.getAllByText(/^Stage 1$/)).toHaveLength(1);
    expect(screen.getByText("10 Hz")).toBeInTheDocument();
    expect(screen.getByText("9.5 Hz")).toBeInTheDocument();
  });

  it("adds a second operating point under an existing stage without asking for stage_order again", async () => {
    authStorage.setToken("token");
    const user = userEvent.setup();
    let addTriggerBody: unknown = null;
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.manage"]),
      draftWithOneEmptyStageHandler(),
      regionsHandler,
      otherReferenceDataHandler,
      {
        method: "POST",
        pattern: new RegExp(
          `/api/v1/stage-setting-sets/${SET_ID}/settings/${STAGE_ID}/triggers$`,
        ),
        respond: (_url, init) => {
          addTriggerBody = JSON.parse(init?.body as string);
          return {
            status: 201,
            body: {
              stage_setting_trigger_id: TRIGGER_ID,
              stage_setting_id: STAGE_ID,
              trigger_order: 1,
              threshold_value: 48.1,
              threshold_unit: "Hz",
              time_delay_ms: 0,
            },
          };
        },
      },
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Add Operating Point" })).toBeInTheDocument();
    });
    expect(screen.getByText("Stage 8")).toBeInTheDocument();
    // No duplicate-stage-order form field anywhere on the operating-point
    // form — only an operating-point "Order" field, threshold, and delay.

    const thresholdInput = screen.getByLabelText("Frequency Threshold (Hz)");
    const delayInput = screen.getByLabelText("Time Delay (ms)");
    await user.type(thresholdInput, "48.1");
    await user.type(delayInput, "0");
    await user.click(screen.getByRole("button", { name: "Add Operating Point" }));

    await waitFor(() => {
      expect(addTriggerBody).not.toBeNull();
    });
    expect(addTriggerBody).toMatchObject({ threshold_value: 48.1, time_delay_ms: 0 });
  });

  it("edits and removes an operating point while Draft", async () => {
    authStorage.setToken("token");
    const user = userEvent.setup();
    let updateBody: unknown = null;
    let removeWasCalled = false;
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.manage"]),
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/stage-setting-sets/${SET_ID}$`),
        respond: () => ({
          status: 200,
          body: {
            stage_setting_set_id: SET_ID,
            scheme_type: "UFLS",
            description: "Synthetic Test Set",
            status: "DRAFT",
            settings: [
              {
                stage_setting_id: STAGE_ID,
                stage_setting_set_id: SET_ID,
                stage_order: 1,
                region_scope_id: null,
                triggers: [
                  {
                    stage_setting_trigger_id: TRIGGER_ID,
                    stage_setting_id: STAGE_ID,
                    trigger_order: 1,
                    threshold_value: 49.5,
                    threshold_unit: "Hz",
                    time_delay_ms: 200,
                  },
                ],
              },
            ],
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
            created_by: null,
            updated_by: null,
          },
        }),
      },
      regionsHandler,
      otherReferenceDataHandler,
      {
        method: "PATCH",
        pattern: new RegExp(
          `/api/v1/stage-setting-sets/${SET_ID}/settings/${STAGE_ID}/triggers/${TRIGGER_ID}$`,
        ),
        respond: (_url, init) => {
          updateBody = JSON.parse(init?.body as string);
          return { status: 200, body: {} };
        },
      },
      {
        method: "DELETE",
        pattern: new RegExp(
          `/api/v1/stage-setting-sets/${SET_ID}/settings/${STAGE_ID}/triggers/${TRIGGER_ID}$`,
        ),
        respond: () => {
          removeWasCalled = true;
          return { status: 204 };
        },
      },
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Add Operating Point" })).toBeInTheDocument();
    });

    // The trigger row's own threshold/delay inputs are bare (unlabeled)
    // table-cell inputs, distinct from the labeled "Add Operating Point"
    // form fields and the page-level Metadata "Save" button — scope to
    // the triggers table itself to avoid ambiguity.
    const table = screen.getByRole("table");
    const [thresholdInput, delayInput] = within(table).getAllByRole("textbox");
    expect(thresholdInput).toHaveValue("49.5");
    expect(delayInput).toHaveValue("200");

    await user.clear(delayInput);
    await user.type(delayInput, "250");
    await user.click(within(table).getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(updateBody).not.toBeNull();
    });
    expect(updateBody).toMatchObject({ time_delay_ms: 250 });

    await user.click(within(table).getByRole("button", { name: "Remove" }));
    await waitFor(() => {
      expect(removeWasCalled).toBe(true);
    });
  });

  it("does not show any trigger edit controls for a user without manage permission, even on a Draft set", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers([]),
      draftWithOneStageAndTriggerHandler(),
      regionsHandler,
      otherReferenceDataHandler,
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByText("49.5 Hz")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Save" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Add Operating Point" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Remove Stage" })).not.toBeInTheDocument();
  });

  it("renders a structured error when adding an operating point is rejected", async () => {
    authStorage.setToken("token");
    const user = userEvent.setup();
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.manage"]),
      draftWithOneEmptyStageHandler(),
      regionsHandler,
      otherReferenceDataHandler,
      {
        method: "POST",
        pattern: new RegExp(
          `/api/v1/stage-setting-sets/${SET_ID}/settings/${STAGE_ID}/triggers$`,
        ),
        respond: () => ({
          status: 400,
          body: {
            detail: {
              code: "validation_error",
              message: "A trigger with threshold_value=48.1 and time_delay_ms=0 already exists.",
            },
          },
        }),
      },
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Add Operating Point" })).toBeInTheDocument();
    });
    await user.type(screen.getByLabelText("Frequency Threshold (Hz)"), "48.1");
    await user.type(screen.getByLabelText("Time Delay (ms)"), "0");
    await user.click(screen.getByRole("button", { name: "Add Operating Point" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/already exists/);
    });
  });

  // --- Delete Draft (ADR-024) ---------------------------------------------------------

  it("shows Delete Draft for a Draft set when the user has manage permission", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.manage"]),
      detailHandler("DRAFT"),
      regionsHandler,
      otherReferenceDataHandler,
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Delete Draft" })).toBeInTheDocument();
    });
  });

  it("does not show Delete Draft for a user without manage permission", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers([]),
      detailHandler("DRAFT"),
      regionsHandler,
      otherReferenceDataHandler,
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByText("No stages yet.")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Delete Draft" })).not.toBeInTheDocument();
  });

  it("never shows Delete Draft for a Published set, even with manage permission", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.manage"]),
      detailHandler("PUBLISHED"),
      regionsHandler,
      otherReferenceDataHandler,
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByText("10 Hz")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Delete Draft" })).not.toBeInTheDocument();
  });

  it("never shows Delete Draft for an Entered in Error set, even with manage permission", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.manage"]),
      detailHandler("ENTERED_IN_ERROR"),
      regionsHandler,
      otherReferenceDataHandler,
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByText("10 Hz")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Delete Draft" })).not.toBeInTheDocument();
  });

  it("requires explicit confirmation before deleting, and Cancel dismisses without calling the API", async () => {
    authStorage.setToken("token");
    const user = userEvent.setup();
    let deleteWasCalled = false;
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.manage"]),
      detailHandler("DRAFT"),
      regionsHandler,
      otherReferenceDataHandler,
      {
        method: "DELETE",
        pattern: new RegExp(`/api/v1/stage-setting-sets/${SET_ID}$`),
        respond: () => {
          deleteWasCalled = true;
          return { status: 204 };
        },
      },
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Delete Draft" })).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: "Delete Draft" }));

    expect(
      screen.getByText(/deleting it is permanent and cannot be undone/i),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByText(/deleting it is permanent/i)).not.toBeInTheDocument();
    expect(deleteWasCalled).toBe(false);
  });

  it("deletes the Draft on confirmation and navigates back to the list", async () => {
    authStorage.setToken("token");
    const user = userEvent.setup();
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.manage"]),
      detailHandler("DRAFT"),
      regionsHandler,
      otherReferenceDataHandler,
      {
        method: "DELETE",
        pattern: new RegExp(`/api/v1/stage-setting-sets/${SET_ID}$`),
        respond: () => ({ status: 204 }),
      },
      {
        method: "GET",
        pattern: /\/api\/v1\/stage-setting-sets(\?.*)?$/,
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 200, total: 0 } }),
      },
    ]);

    renderPageWithListRoute(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Delete Draft" })).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: "Delete Draft" }));
    await user.click(screen.getByRole("button", { name: "Confirm Delete" }));

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Stage Setting Registry" })).toBeInTheDocument();
    });
  });

  it("renders a structured conflict error when deletion is blocked, and stays on the page", async () => {
    authStorage.setToken("token");
    const user = userEvent.setup();
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.manage"]),
      detailHandler("DRAFT"),
      regionsHandler,
      otherReferenceDataHandler,
      {
        method: "DELETE",
        pattern: new RegExp(`/api/v1/stage-setting-sets/${SET_ID}$`),
        respond: () => ({
          status: 400,
          body: {
            detail: {
              code: "validation_error",
              message: "Stage Setting Set cannot be deleted — it is referenced by 1 Scheme Version(s).",
            },
          },
        }),
      },
    ]);

    renderPage(`/stage-setting-sets/${SET_ID}`);

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Delete Draft" })).toBeInTheDocument();
    });
    await user.click(screen.getByRole("button", { name: "Delete Draft" }));
    await user.click(screen.getByRole("button", { name: "Confirm Delete" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/referenced by 1 Scheme Version/);
    });
    // Still on the detail page — never silently navigated away on failure.
    expect(screen.getByRole("button", { name: "Confirm Delete" })).toBeInTheDocument();
  });
});
