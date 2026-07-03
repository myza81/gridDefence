import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { RolesPage } from "../../src/modules/iam/pages/RolesPage";
import { renderWithProviders, stubFetch } from "../testUtils";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "engineer1",
  display_name: "Engineer One",
  email: null,
  status: "active" as const,
};

const VIEWER_ROLE = {
  role_id: "22222222-2222-2222-2222-222222222222",
  name: "Viewer",
  description: "Read-only",
  is_system_role: true,
  status: "active" as const,
};

function stubSession(myPermissions: string[]) {
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
        body: [{ role: VIEWER_ROLE, granted_at: "2026-01-01T00:00:00Z", permissions: myPermissions }],
      }),
    },
    {
      method: "GET",
      pattern: /\/api\/v1\/roles$/,
      respond: () => ({ status: 200, body: [VIEWER_ROLE] }),
    },
    {
      method: "GET",
      pattern: new RegExp(`/api/v1/roles/${VIEWER_ROLE.role_id}/permissions$`),
      respond: () => ({ status: 200, body: [] }),
    },
    {
      method: "GET",
      pattern: /\/api\/v1\/permissions$/,
      respond: () => ({
        status: 200,
        body: [{ permission_id: "iam.audit.read", label: "Read audit log", description: null, module_scope: "iam" }],
      }),
    },
  ]);
}

describe("RolesPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("does not show the create-role form for a user without iam.role.manage", async () => {
    authStorage.setToken("token");
    stubSession([]);

    renderWithProviders(<RolesPage />);

    await waitFor(() => {
      expect(screen.getByText("Viewer (active) [system]")).toBeInTheDocument();
    });
    expect(screen.queryByRole("heading", { name: "Create role" })).not.toBeInTheDocument();
  });

  it("shows the create-role form and submits a new role for a user with iam.role.manage", async () => {
    authStorage.setToken("token");
    stubSession(["iam.role.manage"]);

    let createdRolePayload: unknown = null;
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
            { role: VIEWER_ROLE, granted_at: "2026-01-01T00:00:00Z", permissions: ["iam.role.manage"] },
          ],
        }),
      },
      {
        method: "GET",
        pattern: /\/api\/v1\/roles$/,
        respond: () => ({ status: 200, body: [VIEWER_ROLE] }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/roles/${VIEWER_ROLE.role_id}/permissions$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: /\/api\/v1\/permissions$/,
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "POST",
        pattern: /\/api\/v1\/roles$/,
        respond: (_url, init) => {
          createdRolePayload = init?.body ? JSON.parse(init.body as string) : null;
          return {
            status: 201,
            body: {
              role_id: "33333333-3333-3333-3333-333333333333",
              name: "Engineer",
              description: "General engineering baseline role.",
              is_system_role: false,
              status: "active",
            },
          };
        },
      },
    ]);

    renderWithProviders(<RolesPage />);

    const heading = await screen.findByRole("heading", { name: "Create role" });
    const form = heading.closest("form") as HTMLFormElement;

    const user = userEvent.setup();
    await user.type(within(form).getByLabelText("Name"), "Engineer");
    await user.type(within(form).getByLabelText("Description"), "General engineering baseline role.");
    await user.click(within(form).getByRole("button", { name: "Create role" }));

    await waitFor(() => {
      expect(createdRolePayload).toEqual({
        name: "Engineer",
        description: "General engineering baseline role.",
      });
    });
  });
});
