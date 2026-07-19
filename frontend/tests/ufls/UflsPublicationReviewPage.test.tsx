import { screen, waitFor } from "@testing-library/react";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { UflsPublicationReviewPage } from "../../src/modules/ufls/pages/UflsPublicationReviewPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

function renderPage(route: string) {
  return renderWithProviders(
    <Routes>
      <Route
        path="/ufls/versions/:versionId/publication-review"
        element={<UflsPublicationReviewPage />}
      />
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

function versionHandler(): FetchHandler {
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
        lifecycle_status: "DRAFT",
        published_at: null,
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

function reviewHandler(allPassed: boolean): FetchHandler {
  return {
    method: "GET",
    pattern: new RegExp(`/api/v1/ufls/versions/${VERSION_ID}/publication-review$`),
    respond: () => ({
      status: 200,
      body: {
        scheme_version_id: VERSION_ID,
        all_prerequisites_passed: allPassed,
        prerequisites: [
          {
            prerequisite_code: "UFLS_AT_LEAST_ONE_STAGE",
            passed: allPassed,
            description: "At least one stage is required.",
            affected_object_type: "ufls_scheme_version",
            affected_object_id: VERSION_ID,
          },
        ],
        findings: allPassed
          ? []
          : [
              {
                finding_type: "ALSF_CAPABILITY_ABSENCE",
                severity: "CRITICAL",
                source: "ufls",
                description: "Assigned Transformer Terminal lacks confirmed ALSF capability.",
                affected_object_type: "ufls_direct_assignment",
                affected_object_id: "77777777-7777-7777-7777-777777777777",
                evidence: null,
              },
            ],
      },
    }),
  };
}

const summaryHandler: FetchHandler = {
  method: "GET",
  pattern: new RegExp(`/api/v1/ufls/versions/${VERSION_ID}/summary$`),
  respond: () => ({
    status: 200,
    body: {
      scheme_version_id: VERSION_ID,
      total_target_mw: "10.000",
      stage_summaries: [],
      direct_assignment_count: 1,
      pocket_assignment_count: 0,
      distinct_substation_count: 1,
      unresolved_finding_count: 0,
      sensitive_customer_finding_count: 0,
      alsf_finding_count: 0,
    },
  }),
};

describe("UflsPublicationReviewPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("disables Publish while a prerequisite is failing and shows the blocking reason", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["ufls.publish"]),
      versionHandler(),
      reviewHandler(false),
      summaryHandler,
    ]);

    renderPage(`/ufls/versions/${VERSION_ID}/publication-review`);

    await waitFor(() => {
      expect(screen.getByText("Blocking")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Publish" })).toBeDisabled();
    });
    expect(
      screen.getByText("Assigned Transformer Terminal lacks confirmed ALSF capability."),
    ).toBeInTheDocument();
  });

  it("enables Publish once every prerequisite passes, for a user with ufls.publish", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers(["ufls.publish"]),
      versionHandler(),
      reviewHandler(true),
      summaryHandler,
    ]);

    renderPage(`/ufls/versions/${VERSION_ID}/publication-review`);

    await waitFor(() => {
      expect(screen.getByText("Pass")).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Publish" })).toBeEnabled();
    });
    expect(screen.getByText("No findings.")).toBeInTheDocument();
  });

  it("does not show the Publish button for a user without ufls.publish", async () => {
    authStorage.setToken("token");
    stubFetch([...sessionHandlers([]), versionHandler(), reviewHandler(true), summaryHandler]);

    renderPage(`/ufls/versions/${VERSION_ID}/publication-review`);

    await waitFor(() => {
      expect(screen.getByText("Publishing requires UFLS publish permission.")).toBeInTheDocument();
    });
    expect(screen.queryByRole("button", { name: "Publish" })).not.toBeInTheDocument();
  });
});
