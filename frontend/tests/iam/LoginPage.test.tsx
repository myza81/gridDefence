import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LoginPage } from "../../src/modules/iam/pages/LoginPage";
import { authStorage } from "../../src/modules/iam/authStorage";
import { renderWithProviders, stubFetch } from "../testUtils";

const TOKEN_KEY = "griddefence.iam.access_token";

const USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "admin",
  display_name: "System Administrator",
  email: null,
  status: "active",
};

/** The three requests a successful sign-in triggers (login, /me, roles). */
function stubSuccessfulSession() {
  stubFetch([
    {
      method: "POST",
      pattern: /\/api\/v1\/auth\/login$/,
      respond: () => ({
        status: 200,
        body: { access_token: "signed-token", token_type: "bearer", user: USER },
      }),
    },
    { method: "GET", pattern: /\/api\/v1\/users\/me$/, respond: () => ({ status: 200, body: USER }) },
    { method: "GET", pattern: /\/api\/v1\/users\/.+\/roles$/, respond: () => ({ status: 200, body: [] }) },
  ]);
}

describe("LoginPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
    window.sessionStorage.clear();
  });

  it("stores the access token and shows no error on successful login", async () => {
    stubSuccessfulSession();
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
          body: { detail: { code: "invalid_credentials", message: "Invalid username or password." } },
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

  it("renders the approved GridDefence branding and accessible form controls", () => {
    renderWithProviders(<LoginPage />, { route: "/login" });
    expect(screen.getByRole("heading", { level: 1, name: "Welcome back" })).toBeInTheDocument();
    expect(screen.getByAltText("GridDefence")).toBeInTheDocument();
    expect(screen.getByLabelText("Username")).toBeInTheDocument();
    expect(screen.getByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("keeps the password masked and toggles visibility accessibly", async () => {
    renderWithProviders(<LoginPage />, { route: "/login" });
    const user = userEvent.setup();
    const password = screen.getByLabelText("Password");
    await user.type(password, "s3cret");

    // Masked by default — the value is never rendered as plain text.
    expect(password).toHaveAttribute("type", "password");
    expect(screen.queryByText("s3cret")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(password).toHaveAttribute("type", "text");
    expect(screen.getByRole("button", { name: "Hide password" })).toHaveAttribute("aria-pressed", "true");
  });

  it("submits via keyboard (Enter) using the real auth abstraction", async () => {
    stubSuccessfulSession();
    renderWithProviders(<LoginPage />, { route: "/login" });
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "change-me-immediately{Enter}");

    await waitFor(() => {
      expect(authStorage.getToken()).toBe("signed-token");
    });
  });

  it("respects 'Remember me': unchecked keeps the token in sessionStorage only", async () => {
    stubSuccessfulSession();
    renderWithProviders(<LoginPage />, { route: "/login" });
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "change-me-immediately");
    await user.click(screen.getByLabelText("Remember me")); // uncheck (defaults to checked)
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(window.sessionStorage.getItem(TOKEN_KEY)).toBe("signed-token");
    });
    expect(window.localStorage.getItem(TOKEN_KEY)).toBeNull();
  });

  it("shows a pending state and prevents duplicate submissions", async () => {
    let releaseLogin: () => void = () => {};
    const gate = new Promise<void>((resolve) => {
      releaseLogin = resolve;
    });
    const fetchSpy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = input.toString();
      const method = (init?.method ?? "GET").toUpperCase();
      if (/\/auth\/login$/.test(url) && method === "POST") {
        await gate; // hold the request open to observe the pending state
        return { ok: true, status: 200, json: async () => ({ access_token: "signed-token", token_type: "bearer", user: USER }) } as Response;
      }
      return { ok: true, status: 200, json: async () => (/\/roles$/.test(url) ? [] : USER) } as Response;
    });
    vi.stubGlobal("fetch", fetchSpy);

    renderWithProviders(<LoginPage />, { route: "/login" });
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Username"), "admin");
    await user.type(screen.getByLabelText("Password"), "change-me-immediately");

    const signIn = screen.getByRole("button", { name: "Sign in" });
    await user.click(signIn);

    // Pending: the button is busy/disabled and re-labelled — no layout-shifting swap.
    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Signing in…" })).toHaveAttribute("aria-busy", "true");
    });
    // A second activation attempt must not fire a second login request.
    await user.click(screen.getByRole("button", { name: "Signing in…" }));

    const loginCalls = fetchSpy.mock.calls.filter(
      ([input, init]) => /\/auth\/login$/.test(String(input)) && (init?.method ?? "GET").toUpperCase() === "POST",
    );
    expect(loginCalls).toHaveLength(1);

    releaseLogin();
    await waitFor(() => {
      expect(authStorage.getToken()).toBe("signed-token");
    });
  });

  it("presents SSO as honestly not-yet-available without authenticating", async () => {
    renderWithProviders(<LoginPage />, { route: "/login" });
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Single Sign-On (SSO)" }));

    expect(screen.getByText(/single sign-on isn't available yet/i)).toBeInTheDocument();
    expect(authStorage.getToken()).toBeNull();
  });
});
