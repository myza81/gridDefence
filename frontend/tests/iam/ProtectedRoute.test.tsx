import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../../src/modules/iam/AuthContext";
import { authStorage } from "../../src/modules/iam/authStorage";
import { ProtectedRoute } from "../../src/modules/iam/ProtectedRoute";
import { stubFetch } from "../testUtils";

function renderAt(route: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path="/login" element={<p>Login page</p>} />
            <Route
              path="/roles"
              element={
                <ProtectedRoute>
                  <p>Protected roles content</p>
                </ProtectedRoute>
              }
            />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("ProtectedRoute", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("redirects to /login when there is no session token", async () => {
    renderAt("/roles");

    await waitFor(() => {
      expect(screen.getByText("Login page")).toBeInTheDocument();
    });
    expect(screen.queryByText("Protected roles content")).not.toBeInTheDocument();
  });

  it("renders the protected content once a valid session resolves", async () => {
    authStorage.setToken("valid-token");
    stubFetch([
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

    renderAt("/roles");

    await waitFor(() => {
      expect(screen.getByText("Protected roles content")).toBeInTheDocument();
    });
  });
});
