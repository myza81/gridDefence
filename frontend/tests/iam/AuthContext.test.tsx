import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { useAuth } from "../../src/modules/iam/AuthContext";
import { renderWithProviders, stubFetch } from "../testUtils";

function CurrentUserProbe() {
  const { currentUser, token } = useAuth();
  return <p data-testid="probe">{token === null ? "signed-out" : (currentUser?.username ?? "loading")}</p>;
}

describe("AuthContext session handling", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("clears the stored token when /users/me rejects with 401", async () => {
    authStorage.setToken("expired-token");
    stubFetch([
      {
        method: "GET",
        pattern: /\/api\/v1\/users\/me$/,
        respond: () => ({
          status: 401,
          body: { detail: { code: "unauthorized", message: "Token expired" } },
        }),
      },
    ]);

    renderWithProviders(<CurrentUserProbe />);

    await waitFor(() => {
      expect(screen.getByTestId("probe")).toHaveTextContent("signed-out");
    });
    expect(authStorage.getToken()).toBeNull();
  });

  it("keeps the stored token when /users/me fails with a non-401 (transient) error", async () => {
    authStorage.setToken("still-valid-token");
    stubFetch([
      {
        method: "GET",
        pattern: /\/api\/v1\/users\/me$/,
        respond: () => ({
          status: 503,
          body: { detail: { code: "unavailable", message: "Try again" } },
        }),
      },
    ]);

    renderWithProviders(<CurrentUserProbe />);

    await waitFor(() => {
      expect(screen.getByTestId("probe")).toHaveTextContent("loading");
    });
    expect(authStorage.getToken()).toBe("still-valid-token");
  });
});
