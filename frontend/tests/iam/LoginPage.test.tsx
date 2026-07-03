import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "../../src/modules/iam/pages/LoginPage";
import { authStorage } from "../../src/modules/iam/authStorage";
import { renderWithProviders, stubFetch } from "../testUtils";

describe("LoginPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("stores the access token and shows no error on successful login", async () => {
    stubFetch([
      {
        method: "POST",
        pattern: /\/api\/v1\/auth\/login$/,
        respond: () => ({
          status: 200,
          body: {
            access_token: "signed-token",
            token_type: "bearer",
            user: {
              user_id: "11111111-1111-1111-1111-111111111111",
              username: "admin",
              display_name: "System Administrator",
              email: null,
              status: "active",
            },
          },
        }),
      },
      {
        method: "GET",
        pattern: /\/api\/v1\/users\/me$/,
        respond: () => ({
          status: 200,
          body: {
            user_id: "11111111-1111-1111-1111-111111111111",
            username: "admin",
            display_name: "System Administrator",
            email: null,
            status: "active",
          },
        }),
      },
      {
        method: "GET",
        pattern: /\/api\/v1\/users\/.+\/roles$/,
        respond: () => ({ status: 200, body: [] }),
      },
    ]);

    renderWithProviders(<LoginPage />, { route: "/login" });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "change-me-immediately");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(authStorage.getToken()).toBe("signed-token");
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an error message and does not store a token on invalid credentials", async () => {
    stubFetch([
      {
        method: "POST",
        pattern: /\/api\/v1\/auth\/login$/,
        respond: () => ({
          status: 400,
          body: {
            detail: { code: "invalid_credentials", message: "Invalid username or password." },
          },
        }),
      },
    ]);

    renderWithProviders(<LoginPage />, { route: "/login" });

    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "wrong-password");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Invalid username or password.");
    });
    expect(authStorage.getToken()).toBeNull();
  });
});
