import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { UflsSchemeListPage } from "../../src/modules/ufls/pages/UflsSchemeListPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

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

function schemesHandler(body: unknown): FetchHandler {
  return {
    method: "GET",
    pattern: /\/api\/v1\/ufls\/schemes$/,
    respond: () => ({ status: 200, body }),
  };
}

describe("UflsSchemeListPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders an empty state with no schemes", async () => {
    authStorage.setToken("token");
    stubFetch([...sessionHandlers([]), schemesHandler([])]);

    renderWithProviders(<UflsSchemeListPage />);

    await waitFor(() => {
      expect(screen.getByText("No UFLS schemes exist yet.")).toBeInTheDocument();
    });
  });

  it("renders scheme rows with published and draft version numbers", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...sessionHandlers([]),
      schemesHandler([
        {
          ufls_scheme_id: "33333333-3333-3333-3333-333333333333",
          name: "North Grid UFLS",
          description: "Primary UFLS scheme",
          published_version_number: 2,
          latest_draft_version_number: 3,
        },
      ]),
    ]);

    renderWithProviders(<UflsSchemeListPage />);

    await waitFor(() => {
      expect(screen.getByText("North Grid UFLS")).toBeInTheDocument();
    });
    expect(screen.getByText("v2")).toBeInTheDocument();
    expect(screen.getByText("v3")).toBeInTheDocument();
  });

  it("does not show the create-scheme form for a user without ufls.manage", async () => {
    authStorage.setToken("token");
    stubFetch([...sessionHandlers([]), schemesHandler([])]);

    renderWithProviders(<UflsSchemeListPage />);

    await waitFor(() => {
      expect(screen.getByText("No UFLS schemes exist yet.")).toBeInTheDocument();
    });
    expect(screen.queryByRole("heading", { name: "Create UFLS Scheme" })).not.toBeInTheDocument();
  });

  it("shows the create-scheme form and submits a new scheme for a user with ufls.manage", async () => {
    authStorage.setToken("token");
    const user = userEvent.setup();
    let created = false;
    stubFetch([
      ...sessionHandlers(["ufls.manage"]),
      {
        method: "GET",
        pattern: /\/api\/v1\/ufls\/schemes$/,
        respond: () => ({ status: 200, body: created ? [{
          ufls_scheme_id: "44444444-4444-4444-4444-444444444444",
          name: "New Scheme",
          description: null,
          published_version_number: null,
          latest_draft_version_number: null,
        }] : [] }),
      },
      {
        method: "POST",
        pattern: /\/api\/v1\/ufls\/schemes$/,
        respond: () => {
          created = true;
          return {
            status: 201,
            body: {
              ufls_scheme_id: "44444444-4444-4444-4444-444444444444",
              name: "New Scheme",
              description: null,
              created_at: "2026-01-01T00:00:00Z",
              updated_at: "2026-01-01T00:00:00Z",
            },
          };
        },
      },
    ]);

    renderWithProviders(<UflsSchemeListPage />);

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Create UFLS Scheme" })).toBeInTheDocument();
    });

    await user.type(screen.getByLabelText("Name"), "New Scheme");
    await user.click(screen.getByRole("button", { name: "Create Scheme" }));

    await waitFor(() => {
      expect(screen.getByText("New Scheme")).toBeInTheDocument();
    });
  });
});
