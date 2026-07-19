import { screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { UflsDraftEditorPage } from "../../src/modules/ufls/pages/UflsDraftEditorPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

function renderPage(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/ufls/versions/:versionId" element={<UflsDraftEditorPage />} />
    </Routes>,
    { route },
  );
}

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "engineer1",
  display_name: "Engineer One",
  email: null,
  status: "active" as const,
};

const ROLE = {
  role_id: "22222222-2222-2222-2222-222222222222",
  name: "Engineer",
  description: null,
  is_system_role: true,
  status: "active" as const,
};

const VERSION_ID = "55555555-5555-5555-5555-555555555555";

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

function versionHandler(lifecycleStatus: string): FetchHandler {
  return {
    method: "GET",
    pattern: new RegExp(`/api/v1/ufls/versions/${VERSION_ID}$`),
    respond: () => ({
      status: 200,
      body: {
        version_id: VERSION_ID,
        scheme_id: "66666666-6666-6666-6666-666666666666",
        ufls_scheme_id: "66666666-6666-6666-6666-666666666666",
        version_number: 1,
        lifecycle_status: lifecycleStatus,
        published_at: lifecycleStatus === "PUBLISHED" ? "2026-02-01T00:00:00Z" : null,
        published_by: null,
        superseded_at: null,
        entered_in_error_at: null,
        entered_in_error_by: null,
        entered_in_error_reason: null,
        engineering_remarks: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
        stage_setting_set_id: null,
        study_reference: null,
        effective_date: null,
        topology_version_id: null,
        load_snapshot_id: null,
      },
    }),
  };
}

const stagesHandler: FetchHandler = {
  method: "GET",
  pattern: new RegExp(`/api/v1/ufls/versions/${VERSION_ID}/stages$`),
  respond: () => ({ status: 200, body: [] }),
};

const STAGE_SETTING_ID = "77777777-7777-7777-7777-777777777777";

/** A single UFLS stage (Stage 8) exposing two independent operating
 * criteria (ADR-025) — the worked UAT example. */
const multiTriggerStagesHandler: FetchHandler = {
  method: "GET",
  pattern: new RegExp(`/api/v1/ufls/versions/${VERSION_ID}/stages$`),
  respond: () => ({
    status: 200,
    body: [
      {
        ufls_stage_id: "88888888-8888-8888-8888-888888888888",
        scheme_version_id: VERSION_ID,
        stage_setting_id: STAGE_SETTING_ID,
        stage_order: 8,
        triggers: [
          {
            stage_setting_trigger_id: "99999999-9999-9999-9999-999999999999",
            trigger_order: 1,
            threshold_value: 48.1,
            threshold_unit: "Hz",
            time_delay_ms: 0,
          },
          {
            stage_setting_trigger_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            trigger_order: 2,
            threshold_value: 49.3,
            threshold_unit: "Hz",
            time_delay_ms: 60000,
          },
        ],
        target_mw: "50",
        engineering_remarks: null,
        direct_assignment_count: 0,
        pocket_assignment_count: 0,
      },
    ],
  }),
};

const publishedSetsHandler: FetchHandler = {
  method: "GET",
  pattern: /\/api\/v1\/stage-setting-sets/,
  respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 200, total: 0 } }),
};

describe("UflsDraftEditorPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("shows editable metadata fields for a Draft version when the user has ufls.manage", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["ufls.manage"]),
      versionHandler("DRAFT"),
      stagesHandler,
      publishedSetsHandler,
    ]);

    renderPage(`/ufls/versions/${VERSION_ID}`);

    await waitFor(() => {
      expect(screen.getByLabelText(/Stage Setting Set/)).toBeInTheDocument();
    });
    expect(screen.getByLabelText("Study Reference")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save Metadata" })).toBeInTheDocument();
  });

  it("links to the Stage Setting Registry when no Published UFLS Stage Setting Set exists", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["ufls.manage"]),
      versionHandler("DRAFT"),
      stagesHandler,
      publishedSetsHandler, // resolves to zero items, per its own definition above
    ]);

    renderPage(`/ufls/versions/${VERSION_ID}`);

    await waitFor(() => {
      expect(
        screen.getByRole("link", { name: "Stage Setting Registry" }),
      ).toBeInTheDocument();
    });
    expect(screen.getByRole("link", { name: "Stage Setting Registry" })).toHaveAttribute(
      "href",
      "/stage-setting-sets?scheme_type=UFLS",
    );
  });

  it("renders a Published version strictly read-only, with no metadata edit fields", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["ufls.manage"]),
      versionHandler("PUBLISHED"),
      stagesHandler,
      publishedSetsHandler,
    ]);

    renderPage(`/ufls/versions/${VERSION_ID}`);

    await waitFor(() => {
      expect(screen.getByTestId("lifecycle-badge")).toHaveTextContent("Published");
    });
    expect(screen.queryByLabelText(/Stage Setting Set/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Save Metadata" })).not.toBeInTheDocument();
  });

  // --- Multiple operating criteria per stage (ADR-025) -----------------------------------

  it("displays every operating point of a multi-trigger stage, never as separate stages", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["ufls.manage"]),
      versionHandler("DRAFT"),
      multiTriggerStagesHandler,
      publishedSetsHandler,
    ]);

    renderPage(`/ufls/versions/${VERSION_ID}`);

    await waitFor(() => {
      expect(screen.getByText(/Stage 8/)).toBeInTheDocument();
    });
    // Both operating criteria for Stage 8 are visible, on the one stage
    // card — never rendered as "Stage 8" and "Stage 9".
    expect(screen.getByText(/48\.1 Hz \/ 0 ms/)).toBeInTheDocument();
    expect(screen.getByText(/49\.3 Hz \/ 60,000 ms/)).toBeInTheDocument();
    expect(screen.queryByText(/^Stage 9/)).not.toBeInTheDocument();
  });
});
