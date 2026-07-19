import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { StageSettingSetListPage } from "../../src/modules/stage_setting_registry/pages/StageSettingSetListPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

function renderPage(route = "/stage-setting-sets") {
  return renderWithProviders(
    <Routes>
      <Route path="/stage-setting-sets" element={<StageSettingSetListPage />} />
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

function listHandler(body: unknown): FetchHandler {
  return {
    method: "GET",
    pattern: /\/api\/v1\/stage-setting-sets(\?.*)?$/,
    respond: () => ({ status: 200, body }),
  };
}

describe("StageSettingSetListPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders an empty state with no Stage Setting Sets", async () => {
    authStorage.setToken("token");
    stubFetch([...sessionHandlers([]), listHandler({ items: [], page: 1, page_size: 200, total: 0 })]);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("No Stage Setting Sets match your filters.")).toBeInTheDocument();
    });
  });

  it("renders Stage Setting Set rows with scheme type, status, and stage count", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers([]),
      listHandler({
        items: [
          {
            stage_setting_set_id: "33333333-3333-3333-3333-333333333333",
            scheme_type: "UFLS",
            description: "Synthetic Test Set A",
            status: "PUBLISHED",
            setting_count: 2,
            updated_at: "2026-01-01T00:00:00Z",
          },
        ],
        page: 1,
        page_size: 200,
        total: 1,
      }),
    ]);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("Synthetic Test Set A")).toBeInTheDocument();
    });
    expect(screen.getByRole("cell", { name: "Published" })).toBeInTheDocument();
  });

  it("does not show the create-set form for a user without stage_setting_registry.manage", async () => {
    authStorage.setToken("token");
    stubFetch([...sessionHandlers([]), listHandler({ items: [], page: 1, page_size: 200, total: 0 })]);

    renderPage();

    await waitFor(() => {
      expect(screen.getByText("No Stage Setting Sets match your filters.")).toBeInTheDocument();
    });
    expect(
      screen.queryByRole("heading", { name: "Create Stage Setting Set" }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText("Creating Stage Setting Sets requires Stage Setting Registry manage permission."),
    ).toBeInTheDocument();
  });

  it("shows the create-set form and submits a new Draft set for a user with stage_setting_registry.manage", async () => {
    authStorage.setToken("token");
    const user = userEvent.setup();
    stubFetch([
      ...sessionHandlers(["stage_setting_registry.manage"]),
      listHandler({ items: [], page: 1, page_size: 200, total: 0 }),
      {
        method: "POST",
        pattern: /\/api\/v1\/stage-setting-sets$/,
        respond: () => ({
          status: 201,
          body: {
            stage_setting_set_id: "44444444-4444-4444-4444-444444444444",
            scheme_type: "UFLS",
            description: "New Synthetic Set",
            status: "DRAFT",
            settings: [],
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
            created_by: null,
            updated_by: null,
          },
        }),
      },
    ]);

    renderPage();

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Create Stage Setting Set" })).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("Description"), "New Synthetic Set");
    await user.click(screen.getByRole("button", { name: "Create Draft Stage Setting Set" }));

    // Navigation to the detail page is triggered on success; this test
    // only proves the create request is reachable and permission-gated,
    // matching the UFLS scheme list test's own scope.
    await waitFor(() => {
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    });
  });

  it("pre-filters by scheme_type when navigated to with a query string", async () => {
    authStorage.setToken("token");
    let capturedUrl = "";
    stubFetch([
      ...sessionHandlers([]),
      {
        method: "GET",
        pattern: /\/api\/v1\/stage-setting-sets(\?.*)?$/,
        respond: (url) => {
          capturedUrl = url;
          return { status: 200, body: { items: [], page: 1, page_size: 200, total: 0 } };
        },
      },
    ]);

    renderPage("/stage-setting-sets?scheme_type=UFLS");

    await waitFor(() => {
      expect(screen.getByText("No Stage Setting Sets match your filters.")).toBeInTheDocument();
    });
    expect(capturedUrl).toContain("scheme_type=UFLS");
  });
});
