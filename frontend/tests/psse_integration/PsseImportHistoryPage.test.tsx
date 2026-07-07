import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { PsseImportHistoryPage } from "../../src/modules/psse_integration/pages/PsseImportHistoryPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "engineer1",
  display_name: "Engineer One",
  email: null,
  status: "active" as const,
};

const SESSION_HANDLERS = (myPermissions: string[]): FetchHandler[] => [
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
        {
          role: {
            role_id: "22222222-2222-2222-2222-222222222222",
            name: "Engineer",
            description: null,
            is_system_role: true,
            status: "active",
          },
          granted_at: "2026-01-01T00:00:00Z",
          permissions: myPermissions,
        },
      ],
    }),
  },
];

describe("PsseImportHistoryPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("renders a batch row", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS([]),
      {
        method: "GET",
        pattern: /\/api\/v1\/psse-integration\/imports\/batches\?/,
        respond: () => ({
          status: 200,
          body: {
            items: [
              {
                batch_id: "33333333-3333-3333-3333-333333333333",
                source_file_reference: "110226n.raw",
                imported_by: { ...CURRENT_USER },
                import_type: "FULL_TOPOLOGY_WITH_LOAD",
                status: "Completed",
                computed_signature: "abc123",
                topology_version_id: "44444444-4444-4444-4444-444444444444",
                load_snapshot_id: "55555555-5555-5555-5555-555555555555",
                warnings: [],
                fatal_error: null,
                created_at: "2026-07-05T00:00:00Z",
              },
            ],
            page: 1,
            page_size: 20,
            total: 1,
          },
        }),
      },
    ]);

    renderWithProviders(<PsseImportHistoryPage />, { route: "/psse-integration/history" });

    await waitFor(() => {
      expect(screen.getByText("110226n.raw")).toBeInTheDocument();
    });
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("engineer1")).toBeInTheDocument();
  });

  it("shows an empty state with no import history", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS([]),
      {
        method: "GET",
        pattern: /\/api\/v1\/psse-integration\/imports\/batches\?/,
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 20, total: 0 } }),
      },
    ]);

    renderWithProviders(<PsseImportHistoryPage />, { route: "/psse-integration/history" });

    await waitFor(() => {
      expect(screen.getByText("No PSS/E imports have been made yet.")).toBeInTheDocument();
    });
  });

  it("shows 'New import' link only to a user with psse_integration.import", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS(["psse_integration.import"]),
      {
        method: "GET",
        pattern: /\/api\/v1\/psse-integration\/imports\/batches\?/,
        respond: () => ({ status: 200, body: { items: [], page: 1, page_size: 20, total: 0 } }),
      },
    ]);

    renderWithProviders(<PsseImportHistoryPage />, { route: "/psse-integration/history" });

    await waitFor(() => {
      expect(screen.getByRole("link", { name: "New import" })).toBeInTheDocument();
    });
  });
});
