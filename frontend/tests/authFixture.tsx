import type { ReactElement } from "react";

import { authStorage } from "../src/modules/iam/authStorage";
import type { UserSummary } from "../src/modules/iam/types";
import { renderWithProviders, stubFetch } from "./testUtils";
import type { FetchHandler } from "./testUtils";

/**
 * Authenticated-render fixture (Phase D §18).
 *
 * Renders any UI as a signed-in engineer WITHOUT a live backend and WITHOUT
 * touching production routing: it seeds a session token and mocks exactly the
 * IAM calls AuthProvider makes (`GET /users/me`, `GET /users/:id/roles`) plus
 * `POST /auth/logout`. This is the reproducible way to render the authenticated
 * shell and Home in tests and (via the same idea) in the dev preview harness —
 * replacing Phase C's temporary unguarded-route workaround.
 *
 * It is test-only: it lives under tests/ and never ships in production code, so
 * it is not an authentication bypass in the app itself (the backend remains the
 * authority for every real request).
 */
export const TEST_USER: UserSummary = {
  user_id: "00000000-0000-4000-8000-000000000001",
  username: "sfong",
  display_name: "Su Fong",
  email: "su.fong@example.gov",
  status: "active",
};

interface RenderAuthenticatedOptions {
  route?: string;
  user?: UserSummary;
  /** Extra fetch handlers for the page under test (page-specific API calls). */
  handlers?: FetchHandler[];
}

export function renderAuthenticated(
  ui: ReactElement,
  { route = "/", user = TEST_USER, handlers = [] }: RenderAuthenticatedOptions = {},
) {
  authStorage.setToken("test-session-token", true);

  stubFetch([
    { method: "GET", pattern: /\/api\/v1\/users\/me$/, respond: () => ({ body: user }) },
    { method: "GET", pattern: /\/api\/v1\/users\/[^/]+\/roles$/, respond: () => ({ body: [] }) },
    { method: "POST", pattern: /\/api\/v1\/auth\/logout$/, respond: () => ({ status: 200, body: null }) },
    ...handlers,
  ]);

  return renderWithProviders(ui, { route });
}
