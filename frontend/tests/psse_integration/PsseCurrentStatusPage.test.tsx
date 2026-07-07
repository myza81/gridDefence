import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { authStorage } from "../../src/modules/iam/authStorage";
import { PsseCurrentStatusPage } from "../../src/modules/psse_integration/pages/PsseCurrentStatusPage";
import { renderWithProviders, stubFetch } from "../testUtils";
import type { FetchHandler } from "../testUtils";

const CURRENT_USER = {
  user_id: "11111111-1111-1111-1111-111111111111",
  username: "engineer1",
  display_name: "Engineer One",
  email: null,
  status: "active" as const,
};

const SESSION_HANDLERS: FetchHandler[] = [
  {
    method: "GET",
    pattern: /\/api\/v1\/users\/me$/,
    respond: () => ({ status: 200, body: CURRENT_USER }),
  },
  {
    method: "GET",
    pattern: new RegExp(`/api/v1/users/${CURRENT_USER.user_id}/roles$`),
    respond: () => ({ status: 200, body: [] }),
  },
];

describe("PsseCurrentStatusPage", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("shows a message when nothing has been activated yet", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS,
      {
        method: "GET",
        pattern: /\/api\/v1\/psse-integration\/current-status$/,
        respond: () => ({
          status: 200,
          body: { current_topology_version: null, current_load_snapshot: null },
        }),
      },
    ]);

    renderWithProviders(<PsseCurrentStatusPage />, { route: "/psse-integration/current-status" });

    await waitFor(() => {
      expect(screen.getByText("No TopologyVersion has been activated yet.")).toBeInTheDocument();
    });
    expect(screen.getByText("No LoadSnapshot has been activated yet.")).toBeInTheDocument();
  });

  it("renders the current topology and load snapshot summaries", async () => {
    authStorage.setToken("token");
    stubFetch([
      ...SESSION_HANDLERS,
      {
        method: "GET",
        pattern: /\/api\/v1\/psse-integration\/current-status$/,
        respond: () => ({
          status: 200,
          body: {
            current_topology_version: {
              topology_version_id: "44444444-4444-4444-4444-444444444444",
              signature: "abc123",
              status: "Current",
              created_from_batch_id: "33333333-3333-3333-3333-333333333333",
              promoted_at: "2026-07-05T00:00:00Z",
              superseded_at: null,
              created_at: "2026-07-05T00:00:00Z",
              bus_count: 2,
              branch_count: 1,
              transformer_count: 0,
            },
            current_load_snapshot: {
              load_snapshot_id: "55555555-5555-5555-5555-555555555555",
              topology_version_id: "44444444-4444-4444-4444-444444444444",
              status: "Current",
              promoted_at: "2026-07-05T00:00:00Z",
              superseded_at: null,
              created_at: "2026-07-05T00:00:00Z",
              load_count: 2,
              generator_count: 0,
            },
          },
        }),
      },
    ]);

    renderWithProviders(<PsseCurrentStatusPage />, { route: "/psse-integration/current-status" });

    await waitFor(() => {
      expect(screen.getByText("abc123")).toBeInTheDocument();
    });
    expect(screen.getByText("2 / 1 / 0")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Review Equipment Registry correlation" }),
    ).toHaveAttribute(
      "href",
      "/psse-integration/topology-versions/44444444-4444-4444-4444-444444444444/equipment-map",
    );
  });
});
