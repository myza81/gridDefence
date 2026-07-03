import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { UsersPage } from "../../src/modules/iam/pages/UsersPage";
import { renderWithProviders, stubFetch } from "../testUtils";

const ADMIN = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "admin",
  display_name: "System Administrator",
  email: null,
  status: "active" as const,
};

const OTHER_USER = {
  user_id: "44444444-4444-4444-4444-444444444444",
  username: "engineer1",
  display_name: "Engineer One",
  email: null,
  status: "active" as const,
};

const ADMIN_ROLE = {
  role_id: "22222222-2222-2222-2222-222222222222",
  name: "Administrator",
  description: "Full administrative access.",
  is_system_role: true,
  status: "active" as const,
};

const ENGINEER_ROLE = {
  role_id: "55555555-5555-5555-5555-555555555555",
  name: "Engineer",
  description: null,
  is_system_role: true,
  status: "active" as const,
};

describe("UsersPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("tells a user without iam.user.manage that they cannot manage users, without listing anyone", async () => {
    authStorage.setToken("token");
    stubFetch([
      {
        method: "GET",
        pattern: /\/api\/v1\/users\/me$/,
        respond: () => ({ status: 200, body: OTHER_USER }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/users/${OTHER_USER.user_id}/roles$`),
        respond: () => ({ status: 200, body: [] }),
      },
    ]);

    renderWithProviders(<UsersPage />);

    await waitFor(() => {
      expect(screen.getByText("You do not have permission to manage users.")).toBeInTheDocument();
    });
  });

  it("lets a user with iam.user.manage grant a role to another user", async () => {
    authStorage.setToken("token");

    let grantedPayload: unknown = null;
    stubFetch([
      {
        method: "GET",
        pattern: /\/api\/v1\/users\/me$/,
        respond: () => ({ status: 200, body: ADMIN }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/users/${ADMIN.user_id}/roles$`),
        respond: () => ({
          status: 200,
          body: [{ role: ADMIN_ROLE, granted_at: "2026-01-01T00:00:00Z", permissions: ["iam.user.manage"] }],
        }),
      },
      {
        method: "GET",
        pattern: /\/api\/v1\/users\?/,
        respond: () => ({
          status: 200,
          body: { items: [OTHER_USER], page: 1, page_size: 50, total: 1 },
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/users/${OTHER_USER.user_id}/roles$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "GET",
        pattern: /\/api\/v1\/roles$/,
        respond: () => ({ status: 200, body: [ENGINEER_ROLE] }),
      },
      {
        method: "POST",
        pattern: new RegExp(`/api/v1/users/${OTHER_USER.user_id}/roles$`),
        respond: (_url, init) => {
          grantedPayload = init?.body ? JSON.parse(init.body as string) : null;
          return {
            status: 201,
            body: { role: ENGINEER_ROLE, granted_at: "2026-07-02T00:00:00Z", permissions: [] },
          };
        },
      },
    ]);

    renderWithProviders(<UsersPage />);

    const expandButton = await screen.findByRole("button", { name: "engineer1 (active)" });
    const user = userEvent.setup();
    await user.click(expandButton);

    await screen.findByText("Roles for engineer1");
    await user.selectOptions(screen.getByLabelText("Grant role to engineer1"), ENGINEER_ROLE.role_id);
    await user.click(screen.getByRole("button", { name: "Grant" }));

    await waitFor(() => {
      expect(grantedPayload).toEqual({ role_id: ENGINEER_ROLE.role_id });
    });
  });
});
