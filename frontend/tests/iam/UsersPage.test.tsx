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

  // --- IAM Completion Sprint: user status lifecycle controls -----------------------

  function baseHandlers() {
    return [
      {
        method: "GET" as const,
        pattern: /\/api\/v1\/users\/me$/,
        respond: () => ({ status: 200, body: ADMIN }),
      },
      {
        method: "GET" as const,
        pattern: new RegExp(`/api/v1/users/${ADMIN.user_id}/roles$`),
        respond: () => ({
          status: 200,
          body: [
            { role: ADMIN_ROLE, granted_at: "2026-01-01T00:00:00Z", permissions: ["iam.user.manage"] },
          ],
        }),
      },
      {
        method: "GET" as const,
        pattern: /\/api\/v1\/roles$/,
        respond: () => ({ status: 200, body: [ENGINEER_ROLE] }),
      },
    ];
  }

  it("shows the current status and Suspend/Deactivate actions for an active user", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...baseHandlers(),
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
    ]);

    renderWithProviders(<UsersPage />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "engineer1 (active)" }));

    expect(screen.getByText("Status: active")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Suspend" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Deactivate" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reactivate" })).not.toBeInTheDocument();
  });

  it("shows Reactivate/Deactivate for a suspended user, and no actions for a deactivated one", async () => {
    authStorage.setToken("token");
    const suspendedUser = { ...OTHER_USER, status: "suspended" as const };
    const deactivatedUser = {
      ...OTHER_USER,
      user_id: "66666666-6666-6666-6666-666666666666",
      username: "engineer2",
      status: "deactivated" as const,
    };
    stubFetch([
      ...baseHandlers(),
      {
        method: "GET",
        pattern: /\/api\/v1\/users\?/,
        respond: () => ({
          status: 200,
          body: { items: [suspendedUser, deactivatedUser], page: 1, page_size: 50, total: 2 },
        }),
      },
      {
        method: "GET",
        pattern: /\/api\/v1\/users\/[0-9a-f-]+\/roles$/,
        respond: () => ({ status: 200, body: [] }),
      },
    ]);

    renderWithProviders(<UsersPage />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "engineer1 (suspended)" }));
    expect(screen.getByRole("button", { name: "Reactivate" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Deactivate" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Suspend" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "engineer1 (suspended)" }));

    await user.click(screen.getByRole("button", { name: "engineer2 (deactivated)" }));
    expect(
      screen.getByText("A deactivated account has no further status changes available."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reactivate" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Suspend" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Deactivate" })).not.toBeInTheDocument();
  });

  it("requires a non-empty reason before Confirm can be clicked", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...baseHandlers(),
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
    ]);

    renderWithProviders(<UsersPage />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "engineer1 (active)" }));
    await user.click(screen.getByRole("button", { name: "Suspend" }));

    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
    await user.type(screen.getByLabelText("Reason (required)"), "Leaving the team");
    expect(screen.getByRole("button", { name: "Confirm" })).toBeEnabled();
  });

  it("submits the status change and refreshes the list on success", async () => {
    authStorage.setToken("token");
    let statusPayload: unknown = null;
    let listCallCount = 0;
    stubFetch([
      ...baseHandlers(),
      {
        method: "GET",
        pattern: /\/api\/v1\/users\?/,
        respond: () => {
          listCallCount += 1;
          const status = listCallCount > 1 ? "suspended" : "active";
          return {
            status: 200,
            body: { items: [{ ...OTHER_USER, status }], page: 1, page_size: 50, total: 1 },
          };
        },
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/users/${OTHER_USER.user_id}/roles$`),
        respond: () => ({ status: 200, body: [] }),
      },
      {
        method: "POST",
        pattern: new RegExp(`/api/v1/users/${OTHER_USER.user_id}/status$`),
        respond: (_url, init) => {
          statusPayload = init?.body ? JSON.parse(init.body as string) : null;
          return { status: 200, body: { ...OTHER_USER, status: "suspended" } };
        },
      },
    ]);

    renderWithProviders(<UsersPage />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "engineer1 (active)" }));
    await user.click(screen.getByRole("button", { name: "Suspend" }));
    await user.type(screen.getByLabelText("Reason (required)"), "Leaving the team");
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    await waitFor(() => {
      expect(statusPayload).toEqual({ status: "suspended", change_reason: "Leaving the team" });
    });
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "engineer1 (suspended)" })).toBeInTheDocument();
    });
  });

  it("presents the backend's error message when the last-Administrator safeguard rejects the change", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...baseHandlers(),
      {
        method: "GET",
        pattern: /\/api\/v1\/users\?/,
        respond: () => ({
          status: 200,
          body: { items: [ADMIN], page: 1, page_size: 50, total: 1 },
        }),
      },
      {
        method: "GET",
        pattern: new RegExp(`/api/v1/users/${ADMIN.user_id}/roles$`),
        respond: () => ({
          status: 200,
          body: [
            { role: ADMIN_ROLE, granted_at: "2026-01-01T00:00:00Z", permissions: ["iam.user.manage"] },
          ],
        }),
      },
      {
        method: "POST",
        pattern: new RegExp(`/api/v1/users/${ADMIN.user_id}/status$`),
        respond: () => ({
          status: 400,
          body: {
            detail: {
              code: "validation_error",
              message:
                "At least one active Administrator must remain — this action would leave the system with no active Administrator.",
            },
          },
        }),
      },
    ]);

    renderWithProviders(<UsersPage />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "admin (active)" }));
    await user.click(screen.getByRole("button", { name: "Deactivate" }));
    await user.type(screen.getByLabelText("Reason (required)"), "retiring recovery account");
    await user.click(screen.getByRole("button", { name: "Confirm" }));

    await waitFor(() => {
      expect(
        screen.getByText(/At least one active Administrator must remain/),
      ).toBeInTheDocument();
    });
  });

  it("never renders a delete or password control anywhere on the page", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...baseHandlers(),
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
    ]);

    renderWithProviders(<UsersPage />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "engineer1 (active)" }));

    // No delete control anywhere, and no *reset/change*-password control —
    // the pre-existing "Password" field on the unrelated Create User form
    // (for setting an initial password at creation time) is untouched and
    // deliberately not asserted against here.
    expect(screen.queryByRole("button", { name: /delete/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reset password/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /change password/i })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/reset password/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/new password/i)).not.toBeInTheDocument();
  });
});
