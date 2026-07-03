import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

import { AuthProvider } from "../src/modules/iam/AuthContext";

export interface FetchHandler {
  method: string;
  pattern: RegExp;
  respond: (url: string, init?: RequestInit) => { status?: number; body?: unknown };
}

/**
 * Routes `fetch` calls to canned JSON responses by method + URL pattern, so
 * page tests can exercise real component -> TanStack Query -> apiClient
 * flows without a live backend. Shared across every module's tests (not
 * IAM-specific) — promoted here from tests/iam/testUtils.tsx once
 * Substation Registry (Phase 2) needed the same helper.
 */
export function stubFetch(handlers: FetchHandler[]): void {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      const method = (init?.method ?? "GET").toUpperCase();
      const handler = handlers.find((h) => h.method === method && h.pattern.test(url));

      if (!handler) {
        throw new Error(`No stub registered for ${method} ${url}`);
      }

      const { status = 200, body = {} } = handler.respond(url, init);
      return {
        ok: status >= 200 && status < 300,
        status,
        json: async () => body,
      } as Response;
    }),
  );
}

export function renderWithProviders(ui: ReactElement, { route = "/" }: { route?: string } = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  const result = render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );

  return { ...result, queryClient };
}
